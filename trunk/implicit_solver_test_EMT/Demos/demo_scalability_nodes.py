# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Scalability Benchmark (LINEAR ONLY): AD vs VECTORIZED

Objetivo:
- Forzar simulaciones largas (muchos steps) variando h y t_end
- Medir si compensa setup más alto de VEC por mejor throughput en simulación

Métricas:
- Setup [s]
- Sim [s]
- Total [s] = Setup + Sim
- ms/step
- Break-even runs (VEC vs AD)
"""

import time
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    SimulationBackend,
    JacobianBackend,
)


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


def make_initial_condition(solver: BlockSolver, block: Block, n_nodes: int) -> np.ndarray:
    x0 = np.zeros(solver._n_vars, dtype=np.float64)
    for i in range(n_nodes):
        idx_state = 2 * i  # x_i in state_vars ordering [x_i, v_i, ...]
        if idx_state < len(block.state_vars):
            uid = block.state_vars[idx_state].uid
            if uid in solver.uid2idx_vars:
                x0[solver.uid2idx_vars[uid]] = 0.5 * np.sin(2.0 * np.pi * i / max(n_nodes, 1))
    return x0


# -----------------------------------------------------------------------------
# 3) Runner (AD or VEC)
# -----------------------------------------------------------------------------
def run_backend(
    label: str,
    n_nodes: int,
    jac_backend: JacobianBackend,
    vectorized: bool,
    t_end: float,
    h: float,
    dense_threshold: int = 50,
    verbose: bool = False
):
    block = create_linear_chain(n_nodes)
    t_sym = Var("t")

    mode = "VEC" if vectorized else ("AD" if jac_backend == JacobianBackend.Automatic else "SD")
    print(f"   [{label} | {mode}] Compiling & Initializing...")

    t0 = time.perf_counter()
    solver = BlockSolver(
        block_system=block,
        glob_time=t_sym,
        use_jit=True,
        jacobian_backend=jac_backend,
        backend=SimulationBackend.SymbolicImplicit
    )

    x0 = make_initial_condition(solver, block, n_nodes)

    # Warmup: trigger compilation path (micro-run)
    solver.simulate_unified(
        t0=0.0, t_end=1e-9, h=1e-9,
        x0=x0, dx0=None, params0=None,
        dense_threshold=dense_threshold,
        verbose=False,
        vectorized=vectorized
    )
    setup_s = time.perf_counter() - t0

    n_steps = compute_steps(0.0, t_end, h)
    print(f"   [{label} | {mode}] Simulating... (h={h:.1e}, t_end={t_end:.1e}, steps={n_steps})")

    t1 = time.perf_counter()
    _, y_arr = solver.simulate_unified(
        t0=0.0, t_end=t_end, h=h,
        x0=x0, dx0=None, params0=None,
        method=DynamicIntegrationMethod.Trapezoid,
        dense_threshold=dense_threshold,
        verbose=verbose,
        vectorized=vectorized
    )
    sim_s = time.perf_counter() - t1

    total_s = setup_s + sim_s
    ms_step = (sim_s / max(n_steps, 1)) * 1000.0
    activity = float(np.mean(np.abs(y_arr)))

    print(
        f"   >>> RESULT [{mode}] "
        f"Setup={setup_s:.4f}s | Sim={sim_s:.4f}s | Total={total_s:.4f}s | ms/step={ms_step:.6f} | Activity={activity:.4f}"
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
    print(f"{'AD':<8}{ad['setup_s']:>14.4f}{ad['sim_s']:>14.4f}{ad['total_s']:>14.4f}{ad['ms_step']:>14.6f}{ad['n_steps']:>12d}")
    print(f"{'VEC':<8}{vec['setup_s']:>14.4f}{vec['sim_s']:>14.4f}{vec['total_s']:>14.4f}{vec['ms_step']:>14.6f}{vec['n_steps']:>12d}")

    be = break_even_runs(vec["setup_s"], vec["sim_s"], ad["setup_s"], ad["sim_s"])
    if np.isfinite(be):
        print(f"\nBreak-even VEC vs AD: ~{be:.2f} corridas")
    else:
        print("\nBreak-even VEC vs AD: no compensa (o sim times casi iguales)")

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

    # Escalera segura (nanostep incluido)
    # steps = t_end / h
    experiments = [
        # sanity
        {"h": 1e-7, "t_end": 1e-4},   # 1,000 steps
        {"h": 1e-8, "t_end": 1e-4},   # 10,000 steps
        # nano-step
        {"h": 1e-9, "t_end": 1e-4},   # 100,000 steps
        # heavy (descomenta cuando quieras)
        # {"h": 1e-9, "t_end": 1e-3}, # 1,000,000 steps
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
            jac_backend=JacobianBackend.Automatic,
            vectorized=False,
            t_end=t_end,
            h=h,
            dense_threshold=50,
            verbose=False
        )

        # VEC
        vec = run_backend(
            label="LIN",
            n_nodes=N_LIN,
            jac_backend=JacobianBackend.Automatic,
            vectorized=True,
            t_end=t_end,
            h=h,
            dense_threshold=50,
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
