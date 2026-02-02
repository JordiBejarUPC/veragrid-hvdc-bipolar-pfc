# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Implicit Methods Benchmark: Boost Converter Stiff Test.

This script compares the 3 implemented implicit methods (BackEuler, Trapezoidal, BDF2)
on a stiff switched-mode power supply (Boost Converter).

Objective: Demonstrate the trade-off between STABILITY (Damping) and ACCURACY (Ripple preservation).
"""

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import time

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod


def create_boost_system():
    """Creates the Boost Converter Block."""
    i_L = Var("i_L")
    v_C = Var("v_C")
    Vin = Var("Vin")
    Sw = Var("Sw")
    R = Var("R")
    L = Var("L")
    C = Var("C")

    # Stiff Parameters (Low L = High Dynamics)
    # L=50uH causes significant current ripple, challenging for solvers.
    boost = Block(
        name="Boost_Benchmark",
        state_vars=[i_L, v_C],
        state_eqs=[
            (Vin - (Const(1.0) - Sw) * v_C) / L,
            ((Const(1.0) - Sw) * i_L - v_C / R) / C
        ],
        parameters={
            Vin: Const(12.0),
            Sw: Const(1.0),
            R: Const(10.0),
            L: Const(50e-6),  # STIFF!
            C: Const(220e-6)
        }
    )
    return boost, Sw, Vin


def run_method_benchmark():
    print("==================================================================")
    print("   IMPLICIT METHODS BENCHMARK: STABILITY VS ACCURACY")
    print("==================================================================")

    # Simulation Config
    V_IN = 12.0
    V_OUT = 24.0
    DUTY = 0.5
    F_SW = 25e3
    DT = 1e-6
    T_END = 0.004  # 4ms (Fast run)

    methods = [
        (DynamicIntegrationMethod.BackEuler, "Backward Euler (L-Stable)"),
        (DynamicIntegrationMethod.Trapezoid, "Trapezoidal (A-Stable)"),
        (DynamicIntegrationMethod.BDF2, "BDF2 (L-Stable)")
    ]

    results = {}
    kpis = []

    for method_enum, method_name in methods:
        print(f"\n> Testing: {method_name}...")

        sys_block, sw_var, _ = create_boost_system()
        glob_time = Var("t_glob")
        solver = BlockSolver(sys_block, glob_time)

        # Controller
        def pwm_ctrl(t, x, params):
            sw_val = 1.0 if (t % (1 / F_SW)) < (DUTY / F_SW) else 0.0
            idx = len(solver._event_parameters) + solver.uid2idx_params[sw_var.uid]
            params[idx] = sw_val

        # Init
        x0 = np.zeros(2)
        dx0 = np.array([V_IN / 50e-6, 0.0])  # Accurate dx0

        # Run
        t0 = time.perf_counter()
        t_arr, y_arr = solver.simulate_unified(
            t0=0.0, t_end=T_END, h=DT,
            x0=x0, dx0=dx0, params0=None,
            method=method_enum,
            boundary_update_fn=pwm_ctrl,
            dense_threshold=100
        )
        elapsed = time.perf_counter() - t0

        # Extract Data
        i_L = y_arr[:, solver.uid2idx_vars[sys_block.state_vars[0].uid]]
        v_C = y_arr[:, solver.uid2idx_vars[sys_block.state_vars[1].uid]]

        # Calculate Metrics (Last 20% of sim)
        mask_ss = t_arr > (T_END * 0.8)
        ripple_current = np.max(i_L[mask_ss]) - np.min(i_L[mask_ss])
        avg_voltage = np.mean(v_C[mask_ss])

        kpis.append({
            "Method": method_name.split(' ')[0],  # Short name
            "Sim Time (s)": f"{elapsed:.4f}",
            "V_out Avg (V)": f"{avg_voltage:.2f}",
            "Ripple I_L (A)": f"{ripple_current:.3f}",
            "Behavior": "High Damping" if ripple_current < 1.0 else "Accurate"
        })

        results[method_name] = {'t': t_arr, 'i': i_L, 'v': v_C}

    # --- REPORT ---
    print("\n=== BENCHMARK RESULTS ===")
    df = pd.DataFrame(kpis)
    print(df.to_string(index=False))

    # --- PLOTS ---
    plt.figure(figsize=(12, 8))

    # Plot 1: Transient Voltage (How they handle the jump)
    plt.subplot(2, 1, 1)
    for name, data in results.items():
        plt.plot(data['t'] * 1000, data['v'], linewidth=1.5, label=name)
    plt.title('Transient Response Comparison')
    plt.ylabel('Output Voltage [V]')
    plt.legend()
    plt.grid(True)

    # Plot 2: Steady State Ripple (The Truth Test)
    plt.subplot(2, 1, 2)
    for name, data in results.items():
        # Zoom in on last 0.5ms
        mask = data['t'] > (T_END - 0.0005)
        plt.plot(data['t'][mask] * 1000, data['i'][mask], linewidth=1.5, marker='.', markersize=4, label=name)

    plt.title('Ripple Accuracy Detail (Zoomeado)')
    plt.xlabel('Time [ms]')
    plt.ylabel('Inductor Current [A]')
    plt.grid(True)
    plt.legend()

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    run_method_benchmark()