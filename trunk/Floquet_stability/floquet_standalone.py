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
import time

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.emt_floquet_driver import EmtFloquetDriver
from VeraGridEngine.Simulations.SmallSignalStabilityEmt.emt_floquet_options import EmtFloquetOptions


class _MockVar:
    def __init__(self, uid, name):
        self.uid = uid
        self.name = name

    def __str__(self): return self.name


class _MockParam:
    def __init__(self, value): self.value = value


class EmtProblemDaeMockHunt:
    """Mock simulating a 50Hz pumped system with 3 sub-synchronous modes."""

    def __init__(self, h=1e-4, f_pump=50.0):
        self.h = h
        self.omega = 2.0 * np.pi * f_pump
        self.n_states = 6
        self.n_algebraic = 0

        # Resonances: ~1.59 Hz, ~5.03 Hz, ~10.06 Hz
        self.k_vals = [100.0, 1000.0, 4000.0]
        self.d_vals = [2.0, 4.0, 6.0]
        self._states = [_MockVar(i, f"pos_{i}") for i in range(self.n_states)]

    def get_states_number(self): return self.n_states
    def get_algebraic_var_number(self): return self.n_algebraic
    def get_all_vars_number(self): return self.n_states + self.n_algebraic
    def get_dt(self): return self.h
    def get_state_vars(self): return self._states
    def get_variable_parameter_number(self): return 0
    def get_parameters_values(self): return [_MockParam(1.0)]
    def def_event_params_fn(self, ev, t): return ev

    def _get_A_cont(self, t):
        A = np.zeros((6, 6))
        for i in range(3):
            idx = i * 2
            k = self.k_vals[i] + (0.1 * self.k_vals[i]) * np.sin(self.omega * t)
            A[idx, idx + 1] = 1.0
            A[idx + 1, idx] = -k
            A[idx + 1, idx + 1] = -self.d_vals[i]
        return A

    def _jac_evaluator_mock(self, states, params, history, d_history, h, history2):
        A = self._get_A_cont(0.0)
        return sp.csc_matrix(np.eye(6) / h - A)

    def _inject_evaluator_override(self, driver):
        def _capture_mock(h):
            t_traj = np.arange(0, driver.options.target_period + h, h)
            y_traj = []
            x_prev = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
            for t in t_traj:
                A = self._get_A_cont(t)
                x_next = np.linalg.inv(np.eye(6) - h * A) @ x_prev
                y_traj.append(x_next)
                x_prev = x_next
            return y_traj, t_traj, self._jac_evaluator_mock, np.array([1.0]), 0, 'back_euler'

        driver._capture_limit_cycle_and_evaluator = _capture_mock


def run_target_validation(target_hz, name_tag):
    print(f"\n{'-' * 60}\n Executing Spectral Hunt for: {name_tag} (~{target_hz} Hz)\n{'-' * 60}")

    h = 1e-4
    f_pump = 50.0
    T_period = 1.0 / f_pump

    problem = EmtProblemDaeMockHunt(h=h, f_pump=f_pump)
    emt_options = EmtOptions(time_step=h, simulation_time=0.5, integration_method=DynamicIntegrationMethod.DaeBackEuler)

    # Shift-Invert Filter Active
    floquet_options = EmtFloquetOptions(k=2, target_period=T_period, target_frequency_hz=target_hz, verbose=0)
    driver = EmtFloquetDriver(grid=None, problem=problem, emt_options=emt_options, options=floquet_options)
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