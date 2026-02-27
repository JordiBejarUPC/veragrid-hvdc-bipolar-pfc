# SPDX-License-Identifier: MPL-2.0
"""
Benchmark 02: "Spectral Target Hunt (Shift-Invert Filtering)"
-------------------------------------------------------------
Goal: Prove the algorithm's capability to isolate hidden resonance modes
      (Sub-synchronous interactions) by targeting specific frequencies.

Context: In complex grids with IBRs (Inverter-Based Resources), dominant 50Hz
         modes often mask critical high-frequency control instabilities.
         This test shifts the Krylov projection space to hunt them down.
"""

import numpy as np
import scipy.sparse as sp
import scipy.linalg as la
import time

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod, SmallSignalEmtBuildTypes
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_driver import \
    SmallSignalStabilityEmtDriver
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.small_signal_stability_emt_options import \
    SmallSignalStabilityEmtOptions


class _MockVar:
    """Mock variable class."""

    def __init__(self, uid: int, name: str):
        self.uid = uid
        self.name = name

    def __str__(self): return self.name


class _MockParam:
    """Mock parameter class."""

    def __init__(self, value: float):
        self.value = value


class EmtProblemDaeMockHunt:
    """
    Mock simulating a 50Hz pumped continuous system with 3 sub-synchronous resonance modes.
    Contains no algebraic variables to test pure ODE limit cycle stability.
    """

    def __init__(self, h: float = 1e-4, f_pump: float = 50.0):
        """
        Initializes the Spectral Hunt Mock.

        Args:
            h (float): Integration time step.
            f_pump (float): Fundamental pumping frequency in Hz.
        """
        self.h = h
        self.omega = 2.0 * np.pi * f_pump
        self.n_states = 6
        self.n_algebraic = 0

        # Hidden Resonances: ~1.59 Hz, ~5.03 Hz, ~10.06 Hz
        self.k_vals = [100.0, 1000.0, 4000.0]
        self.d_vals = [2.0, 4.0, 6.0]
        self._states = [_MockVar(i, f"pos_{i}") for i in range(self.n_states)]

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

    def _get_A_cont(self, t: float) -> np.ndarray:
        """
        Calculates the continuous time-varying state matrix A(t).

        Args:
            t (float): Current simulation time.

        Returns:
            np.ndarray: Continuous state matrix.
        """
        A = np.zeros((6, 6))
        for i in range(3):
            idx = i * 2
            # Stiffness modulates at the fundamental pump frequency
            k = self.k_vals[i] + (0.1 * self.k_vals[i]) * np.sin(self.omega * t)
            A[idx, idx + 1] = 1.0
            A[idx + 1, idx] = -k
            A[idx + 1, idx + 1] = -self.d_vals[i]
        return A

    def _jac_evaluator_mock(self, states, params, history, d_history, h, history2) -> sp.spmatrix:
        """
        Mocks the sparse Jacobian evaluator at t=0.
        """
        A = self._get_A_cont(0.0)
        return sp.csc_matrix(np.eye(6) / h - A)

    def _inject_evaluator_override(self, driver: SmallSignalStabilityEmtDriver):
        """
        Injects a mock limit cycle capturing the dynamic response of the system.
        """

        def _capture_mock(h_step):
            t_traj = np.arange(0, driver.options.target_period + h_step, h_step)
            y_traj = []
            x_prev = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
            for t in t_traj:
                A = self._get_A_cont(t)
                x_next = np.linalg.inv(np.eye(6) - h_step * A) @ x_prev
                y_traj.append(x_next)
                x_prev = x_next

            return np.array(y_traj), t_traj, self._jac_evaluator_mock, np.array([1.0]), 0

        driver._capture_limit_cycle_and_evaluator = _capture_mock

    def get_floquet_ak_stack(self, trajectory: np.ndarray, h: float, jac_evaluator=None,
                             static_params=None) -> np.ndarray:
        """
        HPC Mock Implementation for Time-Varying ODEs.
        Computes the A_k stack by evaluating the continuous matrix A(t) at each step.

        Args:
            trajectory (np.ndarray): The limit cycle trajectory.
            h (float): Integration time step.
            jac_evaluator (callable, optional): Ignored in this mock.
            static_params (np.ndarray, optional): Ignored in this mock.

        Returns:
            np.ndarray: A contiguous 3D array of time-varying transition matrices.
        """
        n = self.get_states_number()
        steps = len(trajectory) - 1
        stack = np.zeros((steps, n, n), order='C')

        # Reconstruct time axis for dynamic evaluation
        t_traj = np.arange(0, steps * h + h, h)

        for i in range(steps):
            A_cont = self._get_A_cont(t_traj[i])
            # A_k = (I - h * A(t))^-1
            stack[i] = la.inv(np.eye(6) - h * A_cont)

        return stack


def run_target_validation(target_hz: float, name_tag: str):
    """
    Executes the Floquet driver aiming for a specific spectral target frequency.

    Args:
        target_hz (float): The frequency in Hz to hunt for.
        name_tag (str): A descriptive name for the targeted resonance mode.
    """
    print(f"\n{'-' * 60}\n Executing Spectral Hunt for: {name_tag} (~{target_hz} Hz)\n{'-' * 60}")

    h = 1e-4
    f_pump = 50.0
    T_period = 1.0 / f_pump

    problem = EmtProblemDaeMockHunt(h=h, f_pump=f_pump)
    emt_options = EmtOptions(
        time_step=h,
        simulation_time=0.5,
        integration_method=DynamicIntegrationMethod.BackEuler
    )

    # Shift-Invert Filter Active configuration
    floquet_options = SmallSignalStabilityEmtOptions(
        k=2,
        target_period=T_period,
        target_frequency_hz=target_hz,
        verbose=0,
        build_type=SmallSignalEmtBuildTypes.Arnoldi  # We test the shift-invert on Arnoldi
    )

    driver = SmallSignalStabilityEmtDriver(grid=None, problem=problem, emt_options=emt_options, options=floquet_options)
    problem._inject_evaluator_override(driver)

    t0 = time.perf_counter()
    driver.run()

    res = driver.results
    print(f"Hunt Time: {time.perf_counter() - t0:.4f} s")
    for i, mu in enumerate(res.multipliers):
        print(f" -> Mode {i} isolated: |mu| = {np.abs(mu):.4f}, Freq = {res.conjugate_frequencies[i]:.2f} Hz")


if __name__ == "__main__":
    print("Initializing 50Hz Grid Periodic Problem...")
    run_target_validation(target_hz=1.59, name_tag="Slow Electro-Mechanical Mode")
    run_target_validation(target_hz=5.03, name_tag="Intermediate Control Mode")
    run_target_validation(target_hz=10.06, name_tag="Fast Sub-Synchronous Mode")