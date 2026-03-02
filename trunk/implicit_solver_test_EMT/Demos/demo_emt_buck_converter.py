# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
EMT simulation of a DC-DC Buck Converter using the NEW ARCHITECTURE.

This demo compares:
  - SD: Symbolic Jacobian Engine
  - AD: Sparse Automatic Differentiation Engine
  - StructuralVectorizedSolver: Auto-Vectorized AD Engine
"""

import time
import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate

from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod

class GenericEmtProblem(EmtProblemTemplate):
    pass

# -----------------------------------------------------------------------------
# Model definition
# -----------------------------------------------------------------------------

def create_buck_converter_system():
    i_L = Var("i_L")
    v_C = Var("v_C")

    Vin_sw = Var("Vin_sw")
    R = Var("R")
    L = Var("L")
    C = Var("C")

    block = Block(
        name="BuckConverter",
        state_vars=[i_L, v_C],
        state_eqs=[
            (Vin_sw - v_C) / L,
            (i_L - v_C / R) / C,
        ],
        parameters={
            Vin_sw: Const(0.0),
            R: Const(5.0),
            L: Const(100e-6),
            C: Const(470e-6),
        },
    )

    return block, Vin_sw


# -----------------------------------------------------------------------------
# Simulation runner
# -----------------------------------------------------------------------------

def run_case(backend_str: str):
    print("\n" + "=" * 70)
    print(f"Running Buck Converter | Backend: {backend_str}")
    print("=" * 70)

    # --- Electrical / control parameters ---
    V_IN = 48.0
    V_OUT_REF = 12.0
    F_SW = 20e3
    T_SW = 1.0 / F_SW
    DUTY = V_OUT_REF / V_IN

    DT = 1e-6
    T_TOTAL = 0.020

    block, vin_var = create_buck_converter_system()
    block.unify_blocks()
    glob_time = Var("t_glob")

    problem = GenericEmtProblem(sys_block=block, glob_time=glob_time)
    problem.set_newton_trace_collector(NewtonTraceCollector())

    integration_method = DynamicIntegrationMethod.DaeTrapezoidal

    if backend_str == "SD":
        solver = JitSymbolicSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    elif backend_str == "AD":
        solver = JitAdSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    elif backend_str == "StructuralVectorizedSolver":
        solver = StructuralVectorizedSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    else:
        raise ValueError(f"Backend desconocido: {backend_str}")

    def pwm_controller(t_curr, x_prev, full_params):
        t_mod = t_curr % T_SW
        val = V_IN if t_mod < (DUTY * T_SW) else 0.0

        offset = problem.get_variable_parameter_number()
        idx = problem.uid2idx_params[vin_var.uid]
        full_params[offset + idx] = val

    t_start = time.time()

    if backend_str == "SD":
        t_arr, y_arr = solver.simulate(boundary_update_fn=pwm_controller)
    else:
        x0 = problem.get_x0()
        dx0 = np.zeros(problem.get_all_vars_number())
        params0 = np.zeros(problem.get_variable_parameter_number())
        t_arr, y_arr = solver.simulate(x0=x0, dx0=dx0, params0=params0, boundary_update_fn=pwm_controller)

    elapsed = time.time() - t_start

    idx_iL = problem.get_var_idx(block.state_vars[0])
    idx_vC = problem.get_var_idx(block.state_vars[1])

    sol_i = y_arr[:, idx_iL]
    sol_v = y_arr[:, idx_vC]

    print(f"Elapsed time : {elapsed:.4f} s")
    print(f"Final V_out  : {sol_v[-1]:.6f} V")
    print(f"Final I_L    : {sol_i[-1]:.6f} A")

    collector = problem.get_newton_trace_collector()
    if collector:
        print(f"Newton iters : {len(collector.records)}")

    return t_arr, sol_v, sol_i, elapsed

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    t_sym, v_sym, i_sym, time_sym = run_case("SD")
    t_ad, v_ad, i_ad, time_ad = run_case("AD")
    t_vec, v_vec, i_vec, time_vec = run_case("StructuralVectorizedSolver")

    print("\n" + "-" * 70)
    print("COMPARISON SUMMARY (NEW SOLVERS)")
    print("-" * 70)
    print(f"SD (Symbolic) time : {time_sym:.4f} s")
    print(f"AD time            : {time_ad:.4f} s")
    print(f"StructuralVectorizedSolver time        : {time_vec:.4f} s")

    err_ad_v = np.max(np.abs(v_sym - v_ad))
    err_vec_v = np.max(np.abs(v_sym - v_vec))

    print("-" * 30)
    print(f"Max Error AD vs SD      : {err_ad_v:.3e}")
    print(f"Max Error StructuralVectorizedSolver vs SD  : {err_vec_v:.3e}")

    assert np.allclose(v_sym, v_ad, atol=1e-5), "AD Solver Failed Accuracy Check!"
    assert np.allclose(v_sym, v_vec, atol=1e-5), "StructuralVectorizedSolver Solver Failed Accuracy Check!"

    print("\n>>> SUCCESS: All new engines produced identical physical results.")

    plt.figure(figsize=(10, 8))

    plt.subplot(2, 1, 1)
    plt.plot(t_sym * 1000, v_sym, 'k-', linewidth=4, alpha=0.3, label='SD (Reference)')
    plt.plot(t_ad * 1000, v_ad, 'b--', label='AD')
    plt.plot(t_vec * 1000, v_vec, 'r:', linewidth=2, label='StructuralVectorizedSolver')
    plt.ylabel('Voltage [V]')
    plt.title('Buck Converter: New Architecture Consistency Check')
    plt.legend()
    plt.grid(True)

    plt.subplot(2, 1, 2)
    plt.plot(t_sym * 1000, i_sym, 'k-', linewidth=4, alpha=0.3, label='SD')
    plt.plot(t_ad * 1000, i_ad, 'b--', label='AD')
    plt.plot(t_vec * 1000, i_vec, 'r:', linewidth=2, label='StructuralVectorizedSolver')
    plt.ylabel('Current [A]')
    plt.xlabel('Time [ms]')
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()