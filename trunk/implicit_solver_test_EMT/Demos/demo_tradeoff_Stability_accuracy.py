# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Implicit Methods Benchmark: Boost Converter Stiff Test.

This script compares the 3 implemented implicit methods (BackEuler, Trapezoidal, BDF2)
on a stiff switched-mode power supply (Boost Converter).

Objective: Demonstrate the trade-off between STABILITY (Damping) and ACCURACY (Ripple preservation).

NEW ARCHITECTURE UPDATE: Uses BaseProblem + JitSymbolicSolver.
"""

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import time

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod

class GenericEmtProblem(EmtProblemTemplate):
    pass

def create_boost_system():
    i_L = Var("i_L")
    v_C = Var("v_C")
    Vin = Var("Vin")
    Sw = Var("Sw")
    R = Var("R")
    L = Var("L")
    C = Var("C")

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
            L: Const(50e-6),
            C: Const(220e-6)
        }
    )
    return boost, Sw, Vin


def run_method_benchmark():
    print("==================================================================")
    print("   IMPLICIT METHODS BENCHMARK: STABILITY VS ACCURACY")
    print("==================================================================")

    V_IN = 12.0
    DUTY = 0.5
    F_SW = 25e3
    DT = 1e-6
    T_END = 0.004

    # Using string identifiers for the new JIT architecture
    methods = [
        (DynamicIntegrationMethod.DaeBackEuler, "Backward Euler (L-Stable)"),
        (DynamicIntegrationMethod.DaeTrapezoidal, "Trapezoidal (A-Stable)"),
        (DynamicIntegrationMethod.DaeBDF2, "BDF2 (L-Stable)")
    ]

    results = {}
    kpis = []

    sys_block, sw_var, _ = create_boost_system()
    sys_block.unify_blocks()
    glob_time = Var("t_glob")

    # 1. Create BaseProblem (Network Topology & Equations)
    problem = GenericEmtProblem(sys_block, glob_time)

    # Controller
    def pwm_ctrl(t, x, params):
        sw_val = 1.0 if (t % (1 / F_SW)) < (DUTY / F_SW) else 0.0
        offset = problem.get_variable_parameter_number()
        idx = offset + problem.uid2idx_params[sw_var.uid]
        params[idx] = sw_val

    for method_enum, method_name in methods:
        print(f"\n> Testing: {method_name}...")

        # 2. Instantiate JIT Solver
        solver = JitSymbolicSolver(
            problem=problem, t0=0.0, t_end=T_END, h=DT,
            method=method_enum, verbose=False
        )

        # 3. Simulate (JitSymbolicSolver extracts x0 internally)
        t0 = time.perf_counter()
        t_arr, y_arr = solver.simulate(boundary_update_fn=pwm_ctrl)
        elapsed = time.perf_counter() - t0

        # Extract Data
        i_L = y_arr[:, problem.get_var_idx(sys_block.state_vars[0])]
        v_C = y_arr[:, problem.get_var_idx(sys_block.state_vars[1])]

        # Metrics
        mask_ss = t_arr > (T_END * 0.8)
        ripple_current = np.max(i_L[mask_ss]) - np.min(i_L[mask_ss])
        avg_voltage = np.mean(v_C[mask_ss])

        kpis.append({
            "Method": method_name.split(' ')[0],
            "Sim Time (s)": f"{elapsed:.4f}",
            "V_out Avg (V)": f"{avg_voltage:.2f}",
            "Ripple I_L (A)": f"{ripple_current:.3f}",
            "Behavior": "High Damping" if ripple_current < 1.0 else "Accurate"
        })

        results[method_name] = {'t': t_arr, 'i': i_L, 'v': v_C}

    print("\n=== BENCHMARK RESULTS ===")
    df = pd.DataFrame(kpis)
    print(df.to_string(index=False))

    plt.figure(figsize=(12, 8))
    plt.subplot(2, 1, 1)
    for name, data in results.items():
        plt.plot(data['t'] * 1000, data['v'], linewidth=1.5, label=name)
    plt.title('Transient Response Comparison')
    plt.ylabel('Output Voltage [V]')
    plt.legend()
    plt.grid(True)

    plt.subplot(2, 1, 2)
    for name, data in results.items():
        mask = data['t'] > (T_END - 0.0005)
        plt.plot(data['t'][mask] * 1000, data['i'][mask], linewidth=1.5, marker='.', markersize=4, label=name)
    plt.title('Ripple Accuracy Detail (Zoomed)')
    plt.xlabel('Time [ms]')
    plt.ylabel('Inductor Current [A]')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    run_method_benchmark()