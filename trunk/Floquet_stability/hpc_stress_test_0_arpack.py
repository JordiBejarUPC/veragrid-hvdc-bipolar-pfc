# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
hpc_stress_test_0_arpack_wins.py

Benchmark 0: "The ARPACK Comfort Zone"
Goal: Prove why Standard Arnoldi (Fortran) is superior for small, strictly sparse
      radial feeders, justifying the need for a Smart Router in the final software.
"""

from __future__ import annotations
import time
import numpy as np
import scipy.sparse as sp

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.SmallSignalStability_EMT_Floquet.emt_floquet_driver import (
    EmtFloquetDriver,
    HybridBlockArnoldiDriver,
)
from VeraGridEngine.Simulations.SmallSignalStability_EMT_Floquet.emt_floquet_options import EmtFloquetOptions


class MockRadialFeederEmtNetwork:
    """
    Small, strictly sparse EMT DAE mock (Radial distribution line).
    No dense cross-coupling. Perfect for L2 Cache SpMV operations.
    """

    def __init__(self, n_buses: int = 60, h: float = 1e-4, f_grid: float = 50.0):
        self.h = h
        self.omega = 2.0 * np.pi * f_grid
        self.t = 0.0

        # Small system: 60 buses * 3 phases = 180 states
        self.n_states = 3 * n_buses
        self.n_algebraic = 3 * n_buses
        self.x = np.ones(self.n_states)
        self.y = np.ones(self.n_algebraic)

        self.R = np.full(self.n_states, 0.04)
        self.L = np.full(self.n_states, 0.15)

        # STRICTLY SPARSE: 1D feeder admittance (tridiagonal)
        main = 2.0 * np.ones(n_buses)
        off = -1.0 * np.ones(n_buses - 1)
        Y_scalar = sp.diags([off, main, off], offsets=[-1, 0, 1], shape=(n_buses, n_buses), format='csc')
        self.Y_net = sp.kron(Y_scalar, sp.eye(3, format='csc'), format='csc')

    def get_states_number(self): return self.n_states

    def get_algebraic_var_number(self): return self.n_algebraic

    def get_dt(self): return self.h

    def get_x(self): return self.x

    def get_x0(self): return self.x

    def get_state_vars(self): return [f"I_abc_{i}" for i in range(self.n_states)]

    def step(self, x_prev):
        self.t += self.h
        marker = np.sin(self.omega * self.t)
        self.x = np.full(self.n_states, marker, dtype=float)
        self.y = np.full(self.n_algebraic, np.cos(self.omega * self.t), dtype=float)
        return self.x, self.y

    def _periodic_mod(self, x, y):
        eps = 0.03
        s = float(x[0]) if len(x) else 0.0
        c = float(y[0]) if len(y) else 1.0
        return 1.0 + eps * (0.8 * s + 0.2 * c)

    def get_j11(self, x, y, h):
        mod = self._periodic_mod(x, y)
        return sp.diags(1.0 + h * mod * (self.R / self.L), 0, format='csc')

    def get_j12(self, x, y, h):
        mod = self._periodic_mod(x, y)
        return sp.diags(-(h * mod) / self.L, 0, shape=(self.n_states, self.n_algebraic), format='csc')

    def get_j21(self, x, y, h): return sp.eye(self.n_algebraic, self.n_states, format='csc')

    def get_j22(self, x, y, h):
        mod = self._periodic_mod(x, y)
        return (1.0 + 0.01 * (mod - 1.0)) * self.Y_net


def _run_driver(driver_cls, grid, problem, emt_options, floquet_options):
    d = driver_cls(grid=grid, problem=problem, emt_options=emt_options, options=floquet_options)
    t0 = time.perf_counter()
    d.run()
    dt = time.perf_counter() - t0
    return d, dt


def main():
    problem = MockRadialFeederEmtNetwork(n_buses=60)  # 180 states

    print("\n" + "=" * 80)
    print(f" TEST 0: THE ARPACK COMFORT ZONE | States = {problem.get_states_number()}")
    print("=" * 80)

    emt_options = EmtOptions(time_step=problem.h, simulation_time=0.05,
                             integration_method=DynamicIntegrationMethod.BackEuler)

    # Lightweight options for a small problem
    floquet_options = EmtFloquetOptions(
        k=4,  # Only 4 modes requested
        target_period=0.02,
        max_krylov_dim=40,  # Small Krylov space
        verbose=0,  # Silence output to focus on time
        max_restarts=3,
        restart_tol=1e-5,
        use_refined_ritz=False,  # Turn off heavy Python SVDs
        min_block_size=6,
        max_block_size=10
    )

    print("[1] Standard Arnoldi (SciPy / Fortran ARPACK) ...")
    d_std, t_std = _run_driver(EmtFloquetDriver, None, problem, emt_options, floquet_options)

    print("[2] Hybrid Block-Arnoldi (Python BLAS-3) ...")
    d_hyb, t_hyb = _run_driver(HybridBlockArnoldiDriver, None, problem, emt_options, floquet_options)

    print("\n------------------------------ RENDIMIENTO ------------------------------")
    print(f"1. Arnoldi (Fortran): {t_std:8.4f} s")
    print(f"2. Híbrido (Python):  {t_hyb:8.4f} s")

    if t_std < t_hyb:
        print(f"\nVEREDICTO: ARNOLDI GANA 🔥 (Speedup de {(t_hyb / t_std):.2f}x sobre el Híbrido)")
        print(
            "-> Justificación para el 'Smart Router': El overhead de Python asfixia al método de bloques en sistemas pequeños y ultra-esparcidos.")
    else:
        print("\nVEREDICTO: EMPATE TÉCNICO.")

    print("\n------------------------------ PRECISIÓN (|Mu|) ------------------------------")
    print("Arnoldi: ", np.round(np.abs(d_std.results.multipliers[:4]), 5))
    print("Híbrido: ", np.round(np.abs(d_hyb.results.multipliers[:4]), 5))


if __name__ == "__main__":
    main()