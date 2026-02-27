# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Scalability Benchmark (LINEAR ONLY): AD vs VECTORIZED

Objective:
- Force long simulations (many steps) by varying h and t_end.
- Measure if the higher setup time of VEC is compensated by better throughput in simulation.

Metrics:
- Setup [s]
- Sim [s]
- Total [s] = Setup + Sim
- ms/step
- Break-even runs (VEC vs AD)

UPDATED ARCHITECTURE: Uses GenericEmtProblem, JitAdSolver, and StructuralVectorizedSolver.
"""

import time
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod

class GenericEmtProblem(EmtProblemTemplate):
    pass

# -----------------------------------------------------------------------------
# 1) Linear system factory (repeated structure)
# -----------------------------------------------------------------------------
def create_linear_chain(n_masses: int) -> Block:
    print(f" > [Linear Model] Building Chain (N={n_masses})...")
    pos_vars = [Var(f"x_{i}") for i in range(n_masses)]
    vel_vars = [Var(f"v_{i}") for i in range(n_masses)]
    k, c = Const(5000.0), Const(0.5)

    state_vars, state_eqs = [], []
    for i in range(n_masses):
        x_i, v_i = pos_vars[i], vel_vars[i]
        x_L = pos_vars[i - 1] if i > 0 else Const(0.0)
        x_R = pos_vars[i + 1] if i < n_masses - 1 else Const(0.0)

        force = k * (x_L - x_i) + k * (x_R - x_i) - c * v_i

        state_vars.extend([x_i, v_i])
        state_eqs.extend([v_i, force])

    return Block(
        name=f"Linear_N{n_masses}",
        state_vars=state_vars,
        state_eqs=state_eqs,
        parameters={}
    )


# -----------------------------------------------------------------------------
# 2) Utilities
# -----------------------------------------------------------------------------
def compute_steps(t0: float, t_end: float, h: float) -> int:
    return int(np.ceil((t_end - t0) / h))


def break_even_runs(vec_setup, vec_sim, ad_setup, ad_sim):
    """
    Find R where:
      vec_setup + R*vec_sim = ad_setup + R*ad_sim
    => R = (vec_setup - ad_setup) / (ad_sim - vec_sim)
    """
    denom = (ad_sim - vec_sim)
    if abs(denom) < 1e-15:
        return np.inf
    r = (vec_setup - ad_setup) / denom
    return np.inf if r < 0 else r


def setup_initial_condition(problem: GenericEmtProblem, block: Block, n_nodes: int):
    """Injects a sinusoidal initial condition into the Problem."""
    x0 = problem.get_x0()
    for i in range(n_nodes):
        idx_state = 2 * i  # x_i in state_vars ordering [x_i, v_i, ...]
        if idx_state < len(block.state_vars):
            var_xi = block.state_vars[idx_state]
            if var_xi.uid in problem.uid2idx_vars:
                x0[problem.get_var_idx(var_xi)] = 0.5 * np.sin(2.0 * np.pi * i / max(n_nodes, 1))

    # Override method to ensure Solver gets this custom array
    problem.get_x0 = lambda: x0.copy()


# -----------------------------------------------------------------------------
# 3) Runner (AD or VEC)
# -----------------------------------------------------------------------------
def run_backend(
        label: str,
        n_nodes: int,
        vectorized: bool,
        t_end: float,
        h: float,
        verbose: bool = False
):
    block = create_linear_chain(n_nodes)
    block.unify_blocks()
    t_sym = Var("t_glob")

    mode = "VEC" if vectorized else "AD"
    print(f"   [{label} | {mode}] Compiling & Initializing...")

    t_setup_start = time.perf_counter()

    problem = GenericEmtProblem(sys_block=block, glob_time=t_sym)
    setup_initial_condition(problem, block, n_nodes)

    x0 = problem.get_x0()
    dx0 = np.zeros_like(x0)
    params0 = np.zeros(problem.get_variable_parameter_number())

    target_method = DynamicIntegrationMethod.Trapezoid

    if vectorized:
        solver = StructuralVectorizedSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=target_method, verbose=verbose
        )
        solver.auto_detect_vectorization(method=target_method)
    else:
        solver = JitAdSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=target_method, verbose=verbose
        )
        solver.build_jit_ad()

    solver.simulate(x0=x0, dx0=dx0, params0=params0)

    setup_s = time.perf_counter() - t_setup_start
    # -----------------------------------------------

    n_steps = compute_steps(0.0, t_end, h)
    print(f"   [{label} | {mode}] Simulating pure loop... (steps={n_steps})")

    t_sim_start = time.perf_counter()
    _, y_arr = solver.simulate(x0=x0, dx0=dx0, params0=params0)

    if hasattr(solver, 'last_pure_sim_time'):
        sim_s = solver.last_pure_sim_time
    else:
        sim_s = time.perf_counter() - t_sim_start

    total_s = setup_s + sim_s
    ms_step = (sim_s / max(n_steps, 1)) * 1000.0
    activity = float(np.mean(np.abs(y_arr)))

    print(
        f"   >>> RESULT [{mode}] "
        f"Setup={setup_s:.4f}s | Sim={sim_s:.4f}s | Total={total_s:.4f}s | ms/step={ms_step:.6f}"
    )

    return {
        "mode": mode,
        "setup_s": setup_s,
        "sim_s": sim_s,
        "total_s": total_s,
        "ms_step": ms_step,
        "n_steps": n_steps,
        "activity": activity,
    }

def print_case_summary(case_name: str, ad: dict, vec: dict):
    print("\n" + "-" * 96)
    print(f"[Summary] {case_name}")
    print("-" * 96)
    print(f"{'Mode':<8}{'Setup [s]':>14}{'Sim [s]':>14}{'Total [s]':>14}{'ms/step':>14}{'steps':>12}")
    print(
        f"{'AD':<8}{ad['setup_s']:>14.4f}{ad['sim_s']:>14.4f}{ad['total_s']:>14.4f}{ad['ms_step']:>14.6f}{ad['n_steps']:>12d}")
    print(
        f"{'VEC':<8}{vec['setup_s']:>14.4f}{vec['sim_s']:>14.4f}{vec['total_s']:>14.4f}{vec['ms_step']:>14.6f}{vec['n_steps']:>12d}")

    be = break_even_runs(vec["setup_s"], vec["sim_s"], ad["setup_s"], ad["sim_s"])
    if np.isfinite(be):
        print(f"\nBreak-even VEC vs AD: ~{be:.2f} runs")
    else:
        print("\nBreak-even VEC vs AD: Does not compensate (or sim times are almost identical)")

    one_shot = "AD" if ad["total_s"] <= vec["total_s"] else "VEC"
    throughput = "AD" if ad["sim_s"] <= vec["sim_s"] else "VEC"
    print(f"Best one-shot (Setup+Sim): {one_shot}")
    print(f"Best throughput (Sim only): {throughput}")


# -----------------------------------------------------------------------------
# 4) Main experiment plan
# -----------------------------------------------------------------------------
def main():
    print("=================================================================")
    print("  SCALABILITY BENCHMARK (LINEAR ONLY): AD vs VECTORIZED")
    print("=================================================================")

    # Keep linear case only as requested
    N_LIN = 500

    experiments = [
        {"h": 1e-7, "t_end": 1e-4, "name": "1k steps"},
        {"h": 1e-7, "t_end": 1e-3, "name": "10k steps"},
        {"h": 1e-7, "t_end": 5e-3, "name": "50k steps"},
        {"h": 1e-8, "t_end": 1e-3, "name": "100k steps"},
        {"h": 1e-8, "t_end": 2e-3, "name": "200k steps"},
    ]

    for k, cfg in enumerate(experiments, start=1):
        h = cfg["h"]
        t_end = cfg["t_end"]
        n_steps = compute_steps(0.0, t_end, h)

        print("\n" + "=" * 96)
        print(f"CASE {k}: Linear repeated | N={N_LIN} | h={h:.1e} | t_end={t_end:.1e} | steps={n_steps}")
        print("=" * 96)

        # AD baseline
        ad = run_backend(
            label="LIN",
            n_nodes=N_LIN,
            vectorized=False,
            t_end=t_end,
            h=h,
            verbose=False
        )

        # VEC
        vec = run_backend(
            label="LIN",
            n_nodes=N_LIN,
            vectorized=True,
            t_end=t_end,
            h=h,
            verbose=True
        )

        print_case_summary(
            case_name=f"Linear N={N_LIN}, h={h:.1e}, t_end={t_end:.1e}",
            ad=ad,
            vec=vec
        )

    print("\nBenchmark complete.")


if __name__ == "__main__":
    main()