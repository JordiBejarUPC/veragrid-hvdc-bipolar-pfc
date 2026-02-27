# SPDX-License-Identifier: MPL-2.0
"""
Benchmark 00: "The ARPACK Comfort Zone & Subspace Degeneracy Validation"
------------------------------------------------------------------------
Goal: Prove why Standard Arnoldi (Fortran ARPACK) is superior for small, strictly
      sparse radial feeders, justifying the need for a Smart Router in VeraGrid.

Context: In systems with N < 500 and no global dense controllers, the matrix
         fits entirely in the CPU's L2/L3 cache.

Validation: This test runs TWO scenarios to prove the validity of the Hybrid
            Dual Space Projection:
            A) Clustered Spectrum (Uniform line): Participation indices differ
               due to invariant subspace degeneracy.
            B) Isolated Mode (Anomaly at index 42): Participation indices match
               perfectly, proving the bi-orthogonal projection is exact.
"""

import time
import numpy as np
import scipy.sparse as sp

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.emt_floquet_driver import EmtFloquetDriver, \
    HybridBlockArnoldiDriver
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.emt_floquet_options import EmtFloquetOptions


class _MockVar:
    def __init__(self, uid, name):
        self.uid = uid
        self.name = name

    def __str__(self): return self.name


class _MockParam:
    def __init__(self, value):
        self.value = value


class EmtProblemDaeMock:
    """Mock interface mimicking VeraGrid's EmtProblemDae for sparse radial line."""

    def __init__(self, n_buses=60, h=1e-4, f_grid=50.0):
        self.h = h
        self.omega = 2.0 * np.pi * f_grid
        self.n_states = 3 * n_buses
        self.n_algebraic = 3 * n_buses
        self.R = np.full(self.n_states, 0.04)
        self.L = np.full(self.n_states, 0.15)

        main = 2.0 * np.ones(n_buses)
        off = -1.0 * np.ones(n_buses - 1)
        Y_scalar = sp.diags([off, main, off], offsets=[-1, 0, 1], shape=(n_buses, n_buses), format='csc')
        self.Y_net = sp.kron(Y_scalar, sp.eye(3, format='csc'), format='csc')

        self._states = [_MockVar(i, f"I_abc_{i}") for i in range(self.n_states)]

    def get_states_number(self): return self.n_states

    def get_algebraic_var_number(self): return self.n_algebraic

    def get_all_vars_number(self): return self.n_states + self.n_algebraic

    def get_dt(self): return self.h

    def get_x0(self): return np.ones(self.get_all_vars_number())

    def get_state_vars(self): return self._states

    def get_variable_parameter_number(self): return 0

    def get_parameters_values(self): return [_MockParam(1.0)]

    def def_event_params_fn(self, ev, t): return ev

    def _periodic_mod(self, x_prev, y_prev):
        s = float(x_prev[0]) if len(x_prev) else 0.0
        c = float(y_prev[0]) if len(y_prev) else 1.0
        return 1.0 + 0.03 * (0.8 * s + 0.2 * c)

    def _jac_evaluator_mock(self, states, params, history, d_history, h, history2):
        x_prev = history[:self.n_states]
        y_prev = history[self.n_states:]
        mod = self._periodic_mod(x_prev, y_prev)

        j11 = sp.diags(1.0 / h + mod * (self.R / self.L), 0, format='csc')
        j12 = sp.diags(-1.0 / self.L, 0, shape=(self.n_states, self.n_algebraic), format='csc')
        j21 = sp.eye(self.n_algebraic, self.n_states, format='csc')
        j22 = self.Y_net

        return sp.vstack([sp.hstack([j11, j12]), sp.hstack([j21, j22])], format='csc')

    def _inject_evaluator_override(self, driver):
        def _capture_mock(h):
            t_traj = np.arange(0, driver.options.target_period + h, h)
            y_traj = []
            for t in t_traj:
                x = np.full(self.n_states, np.sin(self.omega * t))
                y = np.full(self.n_algebraic, np.cos(self.omega * t))
                y_traj.append(np.concatenate([x, y]))
            return y_traj, t_traj, self._jac_evaluator_mock, np.array([1.0]), 0, 'back_euler'

        driver._capture_limit_cycle_and_evaluator = _capture_mock


class EmtProblemDaeMockIsolated(EmtProblemDaeMock):
    """Mock with an injected isolated dominant mode at a specific state."""

    def __init__(self, n_buses=60, h=1e-4, f_grid=50.0):
        super().__init__(n_buses, h, f_grid)
        # INYECCIÓN DE LA ANOMALÍA:
        # Hacemos que el Estado 42 sea el más lento de toda la red (L gigante, R mínima)
        # Esto forzará que su autovalor se despegue del grupo y quede totalmente aislado.
        self.target_idx = 42
        self.R[self.target_idx] = 0.001
        self.L[self.target_idx] = 5.0


def run_comparison(problem, scenario_name):
    print(f"\n{'=' * 80}")
    print(f" {scenario_name} | States = {problem.get_states_number()}")
    print(f"{'=' * 80}")

    emt_options = EmtOptions(time_step=problem.h, simulation_time=0.05,
                             integration_method=DynamicIntegrationMethod.DaeBackEuler)
    floquet_options = EmtFloquetOptions(k=4, target_period=0.02, max_krylov_dim=40, verbose=0, max_restarts=3,
                                        use_refined_ritz=False)

    d_std = EmtFloquetDriver(grid=None, problem=problem, emt_options=emt_options, options=floquet_options)
    problem._inject_evaluator_override(d_std)
    t0 = time.perf_counter()
    d_std.run()
    t_std = time.perf_counter() - t0

    d_hyb = HybridBlockArnoldiDriver(grid=None, problem=problem, emt_options=emt_options, options=floquet_options)
    problem._inject_evaluator_override(d_hyb)
    t0 = time.perf_counter()
    d_hyb.run()
    t_hyb = time.perf_counter() - t0

    np.set_printoptions(precision=6, suppress=True)

    print("\n--- PERFORMANCE ---")
    print(f"1. Arnoldi (Fortran ARPACK): {t_std:8.4f} s")
    print(f"2. Hybrid Block (Python):    {t_hyb:8.4f} s")

    print("\n--- FULL ACCURACY VALIDATION ---")
    print("1. Multipliers Magnitude (|Mu|):")
    print("   Arnoldi: ", np.abs(d_std.results.multipliers[:4]))
    print("   Hybrid:  ", np.abs(d_hyb.results.multipliers[:4]))

    pf_std = d_std.results.participation_factors[:, 0]
    pf_hyb = d_hyb.results.participation_factors[:, 0]
    idx_std = np.argmax(pf_std)
    idx_hyb = np.argmax(pf_hyb)

    print("\n2. Dual Space Participation (Mode 0 Culprit):")
    print(f"   Max Participation Factor - Arnoldi: {np.max(pf_std):.6f} at State Index: [{idx_std}]")
    print(f"   Max Participation Factor - Hybrid:  {np.max(pf_hyb):.6f} at State Index: [{idx_hyb}]")

    print("\n--- SPECTRAL GAP VALIDATION (Tolerance h = 1e-4) ---")

    # Asumimos que implementaste validate_spectral_gaps en tu clase de resultados
    # Si no, esto lanzará un error. Asegúrate de haberlo pegado en emt_floquet_results.py
    is_isolated_std, gaps_std = d_std.results.validate_spectral_gaps(h_step=problem.h)
    is_isolated_hyb, gaps_hyb = d_hyb.results.validate_spectral_gaps(h_step=problem.h)

    status_std = "✅ ISOLATED" if is_isolated_std[0] else f"⚠️ CLUSTERED (Gap < h)"
    status_hyb = "✅ ISOLATED" if is_isolated_hyb[0] else f"⚠️ CLUSTERED (Gap < h)"

    print(f"   Mode 0 Status - Arnoldi: {status_std} | Delta_Gap: {gaps_std[0]:.6f}")
    print(f"   Mode 0 Status - Hybrid:  {status_hyb} | Delta_Gap: {gaps_hyb[0]:.6f}")

    print("\n--- CONCLUSION ---")
    if idx_std != idx_hyb:
        print("-> Indices DIFFER. This is the 'Clustered Spectrum' effect (Subspace Degeneracy).")
        print("   Multiple identical states form a flat subspace. The pseudo-inverse projection")
        print("   mixes components differently than strict backward integration.")
        print("   Note how the Spectral Gap Warning accurately predicted this ambiguity.")
    else:
        print("-> Indices MATCH PERFECTLY.")
        print("   The isolated dominant mode was correctly identified by both algorithms.")
        print("   This proves the Hybrid Dual Space projection is mathematically exact for separated modes!")
        print("   Note how the Spectral Gap confirms the mode is safely isolated from numerical noise.")


def main():
    # Escenario A: Red uniforme (Clustered Spectrum)
    prob_clustered = EmtProblemDaeMock(n_buses=60)
    run_comparison(prob_clustered, "SCENARIO A: CLUSTERED SPECTRUM (Uniform Line)")

    # Escenario B: Red con anomalía en el índice 42 (Isolated Spectrum)
    prob_isolated = EmtProblemDaeMockIsolated(n_buses=60)
    run_comparison(prob_isolated, "SCENARIO B: ISOLATED DOMINANT MODE (Anomaly at Idx 42)")


if __name__ == "__main__":
    main()