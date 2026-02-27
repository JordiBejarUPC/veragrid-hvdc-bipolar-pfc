# SPDX-License-Identifier: MPL-2.0
"""
Benchmark 01: "The Cache Zone Benchmark"
--------------------------------------------------
Goal: Evaluate solvers in an intermediate sparse DAE system (750 states) with light
      cross-coupling.

Context: Compares Standard Arnoldi (Golden standard, Fortran ARPACK) against
         Hybrid Block-Arnoldi (Targeting high precision with BLAS-3 speed).
"""

import time
import numpy as np
import scipy.sparse as sp

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.emt_floquet_driver import EmtFloquetDriver, HybridBlockArnoldiDriver
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.emt_floquet_options import EmtFloquetOptions


class _MockVar:
    def __init__(self, uid, name):
        self.uid = uid
        self.name = name
    def __str__(self): return self.name


class _MockParam:
    def __init__(self, value): self.value = value


class EmtProblemDaeMockIntermediate:
    """Sparse EMT DAE mock with light random cross-couplings."""
    def __init__(self, n_buses=250, h=1e-4, f_grid=50.0):
        self.h = h
        self.omega = 2.0 * np.pi * f_grid
        self.n_states = 3 * n_buses
        self.n_algebraic = 3 * n_buses
        self.R = np.full(self.n_states, 0.04)
        self.L = np.full(self.n_states, 0.15)

        rng = np.random.default_rng(42)
        self.J_local = sp.random(self.n_states, self.n_states, density=0.002, format='csc', random_state=rng) * 5e-6

        main = 2.0 * np.ones(n_buses)
        off = -1.0 * np.ones(n_buses - 1)
        Y_scalar = sp.diags([off, main, off], offsets=[-1, 0, 1], shape=(n_buses, n_buses), format='csc')
        self.Y_net = sp.kron(Y_scalar, sp.eye(3, format='csc'), format='csc')

        self._states = [_MockVar(i, f"I_abc_{i}") for i in range(self.n_states)]

    def get_states_number(self): return self.n_states
    def get_algebraic_var_number(self): return self.n_algebraic
    def get_all_vars_number(self): return self.n_states + self.n_algebraic
    def get_dt(self): return self.h
    def get_state_vars(self): return self._states
    def get_variable_parameter_number(self): return 0
    def get_parameters_values(self): return [_MockParam(1.0)]
    def def_event_params_fn(self, ev, t): return ev

    def _jac_evaluator_mock(self, states, params, history, d_history, h, history2):
        j11 = sp.diags(1.0 / h + (self.R / self.L), 0, format='csc') + self.J_local
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


def _run(driver_cls, problem, emt_opts, floquet_opts):
    d = driver_cls(grid=None, problem=problem, emt_options=emt_opts, options=floquet_opts)
    problem._inject_evaluator_override(d)
    t0 = time.perf_counter()
    d.run()
    return d, time.perf_counter() - t0


def main():
    problem = EmtProblemDaeMockIntermediate(n_buses=250)
    print(f"\n{'=' * 80}\n TEST 01: CACHE ZONE | States = {problem.get_states_number()}\n{'=' * 80}")

    emt_options = EmtOptions(time_step=problem.h, simulation_time=0.05,
                             integration_method=DynamicIntegrationMethod.DaeBackEuler)
    floquet_options = EmtFloquetOptions(k=6, target_period=0.02, max_krylov_dim=80, verbose=0, max_restarts=3)

    d_std, t_std = _run(EmtFloquetDriver, problem, emt_options, floquet_options)
    d_hyb, t_hyb = _run(HybridBlockArnoldiDriver, problem, emt_options, floquet_options)

    print("\n--- PERFORMANCE ---")
    print(f"1. Arnoldi (ARPACK): {t_std:8.4f} s")
    print(f"2. Hybrid Block:     {t_hyb:8.4f} s")

    print("\n--- ACCURACY (|Mu|) ---")
    print("Arnoldi: ", np.round(np.abs(d_std.results.multipliers[:5]), 4))
    print("Hybrid:  ", np.round(np.abs(d_hyb.results.multipliers[:5]), 4))


if __name__ == "__main__":
    main()