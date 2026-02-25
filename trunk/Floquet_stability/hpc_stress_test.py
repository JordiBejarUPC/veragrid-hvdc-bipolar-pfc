# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
hpc_stress_test.py

Benchmark 1 ("The Cache Zone") for EMT Floquet small-signal stability.

Goal
----
A sparse, cache-friendly EMT mock (750 differential states) used to compare:
  1) SciPy/ARPACK Arnoldi (reference)
  2) RandNLA RSI (very fast, lower fidelity on dense spectra)
  3) Hybrid restarted Block-Arnoldi (target: approach ARPACK time)

This test is intentionally sparse/local to emulate the regime where ARPACK is hard to beat.
"""

from __future__ import annotations

import time
import numpy as np
import scipy.sparse as sp

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.SmallSignalStability_EMT_Floquet.emt_floquet_driver import (
    EmtFloquetDriver,
    RandnlaFloquetDriver,
    HybridBlockArnoldiDriver,
)
from VeraGridEngine.Simulations.SmallSignalStability_EMT_Floquet.emt_floquet_options import EmtFloquetOptions


class MockCacheZoneEmtNetwork:
    """
    Sparse EMT DAE mock in abc coordinates.

    Differential states: 3 per bus (currents)  -> n_states = 3 * n_buses
    Algebraic vars:      3 per bus (voltages)  -> n_algebraic = 3 * n_buses

    The Jacobian is mostly local/banded. This favours SpMV and therefore is the
    hardest regime for the Hybrid solver to dominate.
    """

    def __init__(self, n_buses: int = 250, h: float = 1e-4, f_grid: float = 50.0, seed: int = 42):
        self.h = h
        self.omega = 2.0 * np.pi * f_grid
        self.t = 0.0
        self.seed = seed

        self.n_states = 3 * n_buses
        self.n_algebraic = 3 * n_buses
        self.x = np.ones(self.n_states)
        self.y = np.ones(self.n_algebraic)

        # Simple abc RL coefficients (per state)
        self.R = np.full(self.n_states, 0.04)
        self.L = np.full(self.n_states, 0.15)

        # Sparse local cross-couplings (very light) to avoid a trivial diagonal J11
        rng = np.random.default_rng(seed)
        density_local = 0.002  # cache-friendly sparse regime
        self.J_local = (sp.random(self.n_states, self.n_states,
                                  density=density_local,
                                  format='csc',
                                  random_state=rng) * 5e-6)

        # 1D feeder-like network admittance (tridiagonal), replicated in abc
        main = 2.0 * np.ones(n_buses)
        off = -1.0 * np.ones(n_buses - 1)
        Y_scalar = sp.diags([off, main, off], offsets=[-1, 0, 1], shape=(n_buses, n_buses), format='csc')
        self.Y_net = sp.kron(Y_scalar, sp.eye(3, format='csc'), format='csc')

    # VeraGrid EMT problem interface
    def get_states_number(self): return self.n_states
    def get_algebraic_var_number(self): return self.n_algebraic
    def get_dt(self): return self.h
    def get_x(self): return self.x
    def get_x0(self): return self.x
    def get_state_vars(self): return [f"I_abc_{i}" for i in range(self.n_states)]

    def step(self, x_prev):
        # We do not simulate real EMT dynamics here; we only encode a periodic marker in x/y
        # so the Jacobian changes with time and the monodromy is nontrivial.
        self.t += self.h
        marker = np.sin(self.omega * self.t)
        self.x = np.full(self.n_states, marker, dtype=float)
        self.y = np.full(self.n_algebraic, np.cos(self.omega * self.t), dtype=float)
        return self.x, self.y

    def _periodic_mod(self, x, y):
        # stable periodic modulation in [1-eps, 1+eps]
        eps = 0.03
        s = float(x[0]) if len(x) else 0.0
        c = float(y[0]) if len(y) else 1.0
        return 1.0 + eps * (0.8 * s + 0.2 * c)

    def get_j11(self, x, y, h):
        mod = self._periodic_mod(x, y)
        diag_sparse = sp.diags(1.0 + h * mod * (self.R / self.L), 0, format='csc')
        return diag_sparse + mod * self.J_local

    def get_j12(self, x, y, h):
        mod = self._periodic_mod(x, y)
        return sp.diags(-(h * mod) / self.L, 0, shape=(self.n_states, self.n_algebraic), format='csc')

    def get_j21(self, x, y, h):
        # Algebraic current injection mapping (identity pick-up)
        return sp.eye(self.n_algebraic, self.n_states, format='csc')

    def get_j22(self, x, y, h):
        # Slight periodic perturbation to avoid exact commuting products
        mod = self._periodic_mod(x, y)
        return (1.0 + 0.01 * (mod - 1.0)) * self.Y_net


def _run_driver(driver_cls, grid, problem, emt_options, floquet_options):
    d = driver_cls(grid=grid, problem=problem, emt_options=emt_options, options=floquet_options)
    t0 = time.perf_counter()
    d.run()
    dt = time.perf_counter() - t0
    return d, dt


def main():
    problem = MockCacheZoneEmtNetwork(n_buses=250)  # 750 differential states

    print("\n" + "=" * 80)
    print(f" TEST 1: CACHE ZONE (Sparse EMT) | States = {problem.get_states_number()}")
    print("=" * 80)

    emt_options = EmtOptions(
        time_step=problem.h,
        simulation_time=0.05,
        integration_method=DynamicIntegrationMethod.BackEuler,
    )

    floquet_options = EmtFloquetOptions(
        k=10,
        target_period=0.02,      # 50 Hz period
        max_krylov_dim=96,
        verbose=1,
        max_restarts=3,
        restart_tol=1e-5,
        use_refined_ritz=True,
        adaptive_restart=True,
        prefer_ak_operator=False,
        use_numba_kernels=True,
        min_block_size=8,
        max_block_size=16,
        max_krylov_dim_cap=160,
    )

    print("[1] Arnoldi Driver (SciPy / ARPACK)...")
    d_std, t_std = _run_driver(EmtFloquetDriver, None, problem, emt_options, floquet_options)

    print("[2] RandNLA RSI Driver...")
    d_rsi, t_rsi = _run_driver(RandnlaFloquetDriver, None, problem, emt_options, floquet_options)

    print("[3] Hybrid Block-Arnoldi Driver...")
    d_hyb, t_hyb = _run_driver(HybridBlockArnoldiDriver, None, problem, emt_options, floquet_options)

    print("\n------------------------------ RENDIMIENTO ------------------------------")
    print(f"1. Arnoldi (SciPy):  {t_std:8.4f} s")
    print(f"2. RandNLA (RSI):    {t_rsi:8.4f} s | Speedup: {t_std / max(t_rsi, 1e-12):5.2f}x")
    print(f"3. Híbrido (Block):  {t_hyb:8.4f} s | Speedup: {t_std / max(t_hyb, 1e-12):5.2f}x")

    print("\n------------------------------ PRECISIÓN (|Mu|) ------------------------------")
    print("1. Arnoldi:", np.round(np.abs(d_std.results.multipliers[:5]), 4), "... (Golden Standard)")
    print("2. RandNLA:", np.round(np.abs(d_rsi.results.multipliers[:5]), 4), "... (RSI)")
    print("3. Híbrido:", np.round(np.abs(d_hyb.results.multipliers[:5]), 4), "... (Restarted Block-Arnoldi)")


if __name__ == "__main__":
    main()
