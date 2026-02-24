# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import time
import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.base_problem import BaseProblem

# Unified Solver Suite
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver


def estimate_big_o(ns, times):
    """Calculates empirical complexity using Log-Log regression slope (m)."""
    if len(ns) < 2: return "N/A"
    valid = [i for i, t in enumerate(times) if t > 0.000001]
    if len(valid) < 2: return "O(1) Constant"

    log_n = np.log([ns[i] for i in valid])
    log_t = np.log([times[i] for i in valid])
    slope, _ = np.polyfit(log_n, log_t, 1)

    if slope < 0.3: return f"O(1) (m={slope:.2f})"
    if 0.8 <= slope <= 1.3: return f"O(N) Linear (m={slope:.2f})"
    if 1.8 <= slope <= 2.5: return f"O(N^2) Quadratic (m={slope:.2f})"
    return f"O(N^{slope:.2f})"


def benchmark_new_architecture(n_oscillators, n_steps, backend="SD"):
    """Isolates Setup (Assembly) and Run (Physics) phases for complexity analysis."""
    # Physics Model: Linear Coupled Chain
    vars_pos = [Var(f"x_{i}") for i in range(n_oscillators)]
    vars_vel = [Var(f"v_{i}") for i in range(n_oscillators)]
    k_sym = Var("k")
    state_vars, state_eqs = [], []
    for i in range(n_oscillators):
        x_i, v_i = vars_pos[i], vars_vel[i]
        x_L = vars_pos[i - 1] if i > 0 else Const(0.0)
        x_R = vars_pos[i + 1] if i < n_oscillators - 1 else Const(0.0)
        force = k_sym * (x_L - x_i) + k_sym * (x_R - x_i) - 0.5 * v_i
        state_vars.extend([x_i, v_i]);
        state_eqs.extend([v_i, force])

    block = Block(name="Chain", state_vars=state_vars, state_eqs=state_eqs, parameters={k_sym: Const(10.0)})
    block.unify_blocks()
    problem = BaseProblem(block, Var("t_glob"))
    h = 0.01

    # --- PHASE 1: ASSEMBLY/SETUP COMPLEXITY ---
    t_setup_start = time.perf_counter()
    if backend == "SD":
        solver = JitSymbolicSolver(problem, t0=0.0, t_end=h * n_steps, h=h, method_str='trapezoidal')
        solver._build_jit_kernel('trapezoidal')
    elif backend == "AD":
        solver = JitAdSolver(problem, t0=0.0, t_end=h * n_steps, h=h, method_str='trapezoidal')
        solver._build_jit_ad()
    elif backend == "StructuralVectorizedSolver":
        solver = StructuralVectorizedSolver(problem, t0=0.0, t_end=h * n_steps, h=h, method_str='trapezoidal')
        solver._auto_detect_vectorization()

    # Mandatory JIT Warmup (must be counted in Setup Tax)
    x0, dx0 = problem.get_x0(), np.zeros(len(state_vars))
    p0 = np.zeros(problem.get_variable_parameter_number())
    solver.t_end = h
    if backend == "SD":
        solver.simulate()
    else:
        solver.simulate(x0=x0, dx0=dx0, params0=p0)
    t_setup = time.perf_counter() - t_setup_start

    # --- PHASE 2: INTEGRATION/SIMULATION COMPLEXITY ---
    solver.t_end = h * n_steps
    t_run_start = time.perf_counter()
    if backend == "SD":
        solver.simulate()
    else:
        solver.simulate(x0=x0, dx0=dx0, params0=p0)

    # Precision bypass: Extract internal loop time if available
    t_run = getattr(solver, 'last_sim_loop_time', time.perf_counter() - t_run_start)

    return {'run': t_run, 'setup': t_setup}


def run_full_analysis():
    print("=" * 100)
    print(f"{'ARCHITECTURAL DUAL-COMPLEXITY ANALYSIS (BIG-O)':^100}")
    print("=" * 100)

    sizes = [10, 50, 100, 200, 400]
    backends = ["SD", "AD", "StructuralVectorizedSolver"]
    results = {b: {'run': [], 'setup': []} for b in backends}

    for b in backends:
        print(f"\n>>> Profiling Backend: {b}")
        print(f"{'States (2N)':<14} | {'Run Time (s)':<16} | {'Setup Time (s)':<12}")
        print("-" * 50)
        for N in sizes:
            res = benchmark_new_architecture(N, 100, backend=b)
            results[b]['run'].append(res['run'])
            results[b]['setup'].append(res['setup'])
            print(f"{N * 2:<14} | {res['run']:.6f}         | {res['setup']:.4f}")

    # Final Comparative Complexity Table
    print("\n" + "=" * 100)
    print(f"{'COMPLEXITY CLASS SUMMARY':^100}")
    print("=" * 100)
    print(f"{'Backend':<30} | {'Setup Complexity':<30} | {'Sim Complexity':<30}")
    print("-" * 100)
    for b in backends:
        setup_comp = estimate_big_o(np.array(sizes) * 2, np.array(results[b]['setup']))
        sim_comp = estimate_big_o(np.array(sizes) * 2, np.array(results[b]['run']))
        print(f"{b:<30} | {setup_comp:<30} | {sim_comp:<30}")
    print("=" * 100)


if __name__ == "__main__":
    run_full_analysis()