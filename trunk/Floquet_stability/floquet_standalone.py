# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import scipy.sparse as sp
import time

# Base EMT Imports
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod

# Floquet Module Imports
from VeraGridEngine.Simulations.SmallSignalStability_EMT_Floquet.emt_floquet_driver import EmtFloquetDriver, RandnlaFloquetDriver
from VeraGridEngine.Simulations.SmallSignalStability_EMT_Floquet.emt_floquet_options import EmtFloquetOptions

class MockMultiModeProblem:
    """
    PhD-Level Mock of EmtProblemBase.
    Simulates a 50Hz pumped system with 3 sub-synchronous modes.
    """

    def __init__(self, h=1e-4, f_pump=50.0):
        self.h = h
        self.omega = 2.0 * np.pi * f_pump  # 50 Hz limit cycle
        self.t = 0.0
        self.n_states = 6
        self.n_algebraic = 0
        self.x = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])

        # Sub-synchronous resonances: ~1.59 Hz, ~5.03 Hz, ~10.06 Hz
        self.k_vals = [100.0, 1000.0, 4000.0]
        # Distinct damping for each mode
        self.d_vals = [2.0, 4.0, 6.0]

    def get_states_number(self): return self.n_states

    def get_algebraic_var_number(self): return self.n_algebraic

    def get_dt(self): return self.h

    def get_x(self): return self.x

    def get_x0(self): return self.x

    def get_state_vars(self):
        return ["pos1", "vel1", "pos2", "vel2", "pos3", "vel3"]

    def step(self, x_prev):
        A_mat = self._get_A_cont(self.t)
        phi = np.linalg.inv(np.eye(6) - self.h * A_mat)
        self.x = phi @ x_prev
        self.t += self.h
        return self.x, np.array([])

    def _get_A_cont(self, t):
        """Block-diagonal continuous system with 3 distinct frequencies."""
        A = np.zeros((6, 6))
        for i in range(3):
            idx = i * 2
            # Base stiffness + 10% periodic fluctuation from the 50Hz grid
            k = self.k_vals[i] + (0.1 * self.k_vals[i]) * np.sin(self.omega * t)
            A[idx, idx + 1] = 1.0
            A[idx + 1, idx] = -k
            A[idx + 1, idx + 1] = -self.d_vals[i]
        return A

    def get_j11(self, x, y, h):
        A = self._get_A_cont(self.t)
        return sp.csc_matrix(np.eye(6) - h * A)

    def get_j12(self, x, y, h): return sp.csc_matrix((6, 0))

    def get_j21(self, x, y, h): return sp.csc_matrix((0, 6))

    def get_j22(self, x, y, h): return sp.csc_matrix((0, 0))


def run_target_validation(target_hz, name_tag):
    print(f"\n{'=' * 60}")
    print(f"Executing Spectral Hunt for: {name_tag} (~{target_hz} Hz)")
    print(f"{'=' * 60}")

    h = 1e-4  # High precision step for 50Hz
    f_pump = 50.0
    T_period = 1.0 / f_pump  # 0.02s

    problem = MockMultiModeProblem(h=h, f_pump=f_pump)

    emt_options = EmtOptions(
        time_step=h,
        simulation_time=0.5,
        integration_method=DynamicIntegrationMethod.BackEuler
    )

    # Shift-Invert Filter Active
    floquet_options = EmtFloquetOptions(
        k=2,
        target_period=T_period,
        target_frequency_hz=target_hz,
        verbose=0
    )

    driver = EmtFloquetDriver(
        grid=None,
        problem=problem,
        emt_options=emt_options,
        options=floquet_options
    )

    t0 = time.perf_counter()
    driver.run()
    t1 = time.perf_counter()

    res = driver.results
    print(f"Hunt Time: {t1 - t0:.4f} s")

    for i, mu in enumerate(res.multipliers):
        print(f"Mode {i} isolated: |mu| = {np.abs(mu):.4f}, Freq = {res.conjugate_frequencies[i]:.2f} Hz")


if __name__ == "__main__":
    print("Initializing 50Hz Grid Periodic Problem...")

    # Target the slow electro-mechanical mode
    run_target_validation(target_hz=1.59, name_tag="Slow Mode")

    # Target the intermediate control mode
    run_target_validation(target_hz=5.03, name_tag="Intermediate Mode")

    # Target the fast sub-synchronous mode
    run_target_validation(target_hz=10.06, name_tag="Sub-Synchronous Fast Mode")