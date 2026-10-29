# SPDX-License-Identifier: MPL-2.0
"""
Benchmark 01: "The Cache Zone Benchmark"
--------------------------------------------------
Goal: Evaluate solvers in an intermediate sparse DAE system (750 states) with light
      cross-coupling.

Context: Compares Standard Arnoldi (Golden standard, Fortran ARPACK) against
         Hybrid Block-Arnoldi (Targeting high precision with BLAS-3 speed) in a
         scenario where the matrix size challenges the CPU's cache limits.
"""

import time
import numpy as np
import scipy.sparse as sp
import scipy.linalg as la

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod, SmallSignalEmtBuildTypes
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import \
    SmallSignalStabilityEmtDriver
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import \
    SmallSignalStabilityEmtOptions


class _MockVar:
    """Mock variable class to simulate VeraGrid symbolic state variables."""

    def __init__(self, uid: int, name: str):
        self.uid = uid
        self.name = name

    def __str__(self): return self.name


class _MockParam:
    """Mock parameter class to simulate VeraGrid symbolic parameters."""

    def __init__(self, value: float):
        self.value = value


class EmtProblemDaeMockIntermediate:
    """
    Sparse EMT DAE mock with light random cross-couplings.
    Simulates a power system with differential and algebraic equations (DAE).
    """

    def __init__(self, n_buses: int = 250, h: float = 1e-4, f_grid: float = 50.0):
        """
        Initializes the intermediate DAE mock.

        Args:
            n_buses (int): Number of three-phase buses in the system.
            h (float): Integration time step in seconds.
            f_grid (float): Grid frequency in Hz.
        """
        self.h = h
        self.omega = 2.0 * np.pi * f_grid
        self.n_states = 3 * n_buses
        self.n_algebraic = 3 * n_buses
        self.R = np.full(self.n_states, 0.04)
        self.L = np.full(self.n_states, 0.15)

        # Simulate sparse cross-coupling between states
        rng = np.random.default_rng(42)
        self.J_local = sp.random(self.n_states, self.n_states, density=0.002, format='csc', random_state=rng) * 5e-6

        # Simulate network admittance matrix (Ybus)
        main = 2.0 * np.ones(n_buses)
        off = -1.0 * np.ones(n_buses - 1)
        Y_scalar = sp.diags([off, main, off], offsets=[-1, 0, 1], shape=(n_buses, n_buses), format='csc')
        self.Y_net = sp.kron(Y_scalar, sp.eye(3, format='csc'), format='csc')

        self._states = [_MockVar(i, f"I_abc_{i}") for i in range(self.n_states)]

    # --- Standard VeraGrid Interface Methods ---
    def get_states_number(self) -> int:
        return self.n_states

    def get_algebraic_var_number(self) -> int:
        return self.n_algebraic

    def get_all_vars_number(self) -> int:
        return self.n_states + self.n_algebraic

    def get_dt(self) -> float:
        return self.h

    def get_state_vars(self) -> list:
        return self._states

    def get_variable_parameter_number(self) -> int:
        return 0

    def get_parameters_values(self) -> list:
        return [_MockParam(1.0)]

    def def_event_params_fn(self, ev, t):
        return ev

    def _jac_evaluator_mock(self, states, params, history, d_history, h, history2) -> sp.spmatrix:
        """
        Mocks the evaluation of the sparse DAE Jacobian matrix.

        Returns:
            sp.spmatrix: The evaluated sparse Jacobian block matrix.
        """
        j11 = sp.diags(1.0 / h + (self.R / self.L), 0, format='csc') + self.J_local
        j12 = sp.diags(-1.0 / self.L, 0, shape=(self.n_states, self.n_algebraic), format='csc')
        j21 = sp.eye(self.n_algebraic, self.n_states, format='csc')
        j22 = self.Y_net

        return sp.vstack([sp.hstack([j11, j12]), sp.hstack([j21, j22])], format='csc')

    def _inject_evaluator_override(self, driver: SmallSignalStabilityEmtDriver):
        """
        Injects a mock limit cycle capture function into the driver to bypass
        the need for a full non-linear solver.
        """

        def _capture_mock(h_step):
            t_traj = np.arange(0, driver.options.target_period + h_step, h_step)
            y_traj = []
            for t in t_traj:
                x = np.full(self.n_states, np.sin(self.omega * t))
                y = np.full(self.n_algebraic, np.cos(self.omega * t))
                y_traj.append(np.concatenate([x, y]))

            return np.array(y_traj), t_traj, self._jac_evaluator_mock, np.array([1.0]), 0

        driver._capture_limit_cycle_and_evaluator = _capture_mock

    def get_floquet_ak_stack(self, trajectory: np.ndarray, h: float, jac_evaluator=None,
                             static_params=None) -> np.ndarray:
        """
        HPC Mock Implementation: Calculates the A_k state-transition matrix stack
        using exact Kron Reduction optimized with Scipy Sparse Solvers.

        Args:
            trajectory (np.ndarray): The limit cycle trajectory captured by the driver.
            h (float): Integration time step.
            jac_evaluator (callable, optional): JIT Jacobian evaluator.
            static_params (np.ndarray, optional): Array of static system parameters.

        Returns:
            np.ndarray: A contiguous 3D array of shape (steps, n_states, n_states).
        """
        n = self.get_states_number()
        steps = len(trajectory) - 1
        stack = np.zeros((steps, n, n), order='C')

        # Obtain the static sparse Jacobian for this LTI mock
        J = self._jac_evaluator_mock(None, None, np.zeros(self.n_states), None, h, None)

        # Extract block matrices
        J11, J12 = J[:n, :n], J[:n, n:]
        J21, J22 = J[n:, :n], J[n:, n:]

        import scipy.sparse.linalg as spla

        # Exact Kron Reduction: Eliminate algebraic variables efficiently
        J22_inv_J21 = spla.spsolve(J22, J21)
        J_red = (J11 - J12 @ J22_inv_J21).toarray()

        # Transition matrix A_k = (h * J_reduced)^-1
        A_k = la.inv(h * J_red)

        # Populate the stack (constant for this specific linear mock)
        for i in range(steps):
            stack[i] = A_k

        return stack


def _run(driver_cls: type, problem: EmtProblemDaeMockIntermediate, emt_opts: EmtOptions,
         floquet_opts: SmallSignalStabilityEmtOptions) -> tuple:
    """
    Helper function to instantiate, inject, and execute the specified driver.
    """
    d = driver_cls(grid=None, problem=problem, emt_options=emt_opts, options=floquet_opts)
    problem._inject_evaluator_override(d)
    t0 = time.perf_counter()
    d.run()
    return d, time.perf_counter() - t0


def main():
    """Main execution block for Benchmark 01."""
    problem = EmtProblemDaeMockIntermediate(n_buses=250)
    print(f"\n{'=' * 80}\n TEST 01: CACHE ZONE | States = {problem.get_states_number()}\n{'=' * 80}")

    emt_options = EmtOptions(
        time_step=problem.h,
        simulation_time=0.05,
        integration_method=DynamicIntegrationMethod.DaeBackEuler
    )

    # --- 1. Standard Arnoldi Configuration ---
    opts_std = SmallSignalStabilityEmtOptions(
        k=6, target_period=0.02, max_krylov_dim=80, verbose=0, max_restarts=3,
        build_type=SmallSignalEmtBuildTypes.Arnoldi
    )
    d_std, t_std = _run(SmallSignalStabilityEmtDriver, problem, emt_options, opts_std)

    # --- 2. Hybrid Block-Arnoldi Configuration ---
    opts_hyb = SmallSignalStabilityEmtOptions(
        k=6, target_period=0.02, max_krylov_dim=80, verbose=0, max_restarts=3,
        prefer_ak_operator=True, use_numba_kernels=True,
        build_type=SmallSignalEmtBuildTypes.HybridArnoldi
    )
    d_hyb, t_hyb = _run(SmallSignalStabilityEmtDriver, problem, emt_options, opts_hyb)

    print("\n--- PERFORMANCE ---")
    print(f"1. Arnoldi (ARPACK): {t_std:8.4f} s")
    print(f"2. Hybrid Block:     {t_hyb:8.4f} s")

    print("\n--- ACCURACY (|Mu|) ---")
    print("Arnoldi: ", np.round(np.abs(d_std.results.multipliers[:5]), 4))
    print("Hybrid:  ", np.round(np.abs(d_hyb.results.multipliers[:5]), 4))


if __name__ == "__main__":
    main()