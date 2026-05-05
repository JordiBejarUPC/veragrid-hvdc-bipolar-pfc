# ==============================================================================
# Scalability Benchmark (LINEAR ONLY): AD vs VECTORIZED
# ==============================================================================

import time
import numpy as np
from typing import List, Dict, Any

# VeraGridEngine Imports
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


# -----------------------------------------------------------------------------
# 1) Linear system factory (repeated structure)
# -----------------------------------------------------------------------------
def create_linear_chain(n_masses: int,
                        vf: VarFactory) -> Block:
    print(f" > [Linear Model] Building Chain (N={n_masses})...")

    pos_vars: List[Var] = list()
    d_pos_vars: List[Var] = list()
    vel_vars: List[Var] = list()
    d_vel_vars: List[Var] = list()
    for i in range(n_masses):
        pos_vars.append(vf.add_var(f"x_{i}"))
        d_pos_vars.append(vf.add_diff_var(name = f"d_x_{i}", base_var= pos_vars[i]))
        vel_vars.append(vf.add_var(f"v_{i}"))
        d_vel_vars.append(vf.add_diff_var(name=f"d_v_{i}", base_var=vel_vars[i]))

    k: Const = Const(5000.0)
    c: Const = Const(0.5)

    state_vars: List[Var] = list()
    state_eqs: List[Expr] = list()
    diff_vars: List[Var] = list()

    for i in range(n_masses):
        x_i, d_x_i, v_i, d_v_i = pos_vars[i], d_pos_vars[i], vel_vars[i], d_vel_vars[i]
        if i > 0:
            x_L: Expr = pos_vars[i - 1]
        else:
            x_L = Const(0.0)

        if i < n_masses - 1:
            x_R: Expr = pos_vars[i + 1]
        else:
            x_R = Const(0.0)

        force: Expr = k * (x_L - x_i) + k * (x_R - x_i) - c * v_i

        state_vars.append(x_i)
        diff_vars.append(d_x_i)
        state_vars.append(v_i)
        diff_vars.append(d_v_i)
        state_eqs.append(v_i)
        state_eqs.append(force)

    return Block(
        name=f"Linear_N{n_masses}",
        state_vars=state_vars,
        state_eqs=state_eqs,
        diff_vars=diff_vars,
        parameters=dict()
    )

# -----------------------------------------------------------------------------
# 2) Utilities
# -----------------------------------------------------------------------------
def compute_steps(t0: float, t_end: float, h: float) -> int:
    return int(np.ceil((t_end - t0) / h))


def break_even_runs(vec_setup: float, vec_sim: float, ad_setup: float, ad_sim: float) -> float:
    """
    Calculates the number of runs R where cumulative time equalizes.
    Formula: Setup_VEC + R*Sim_VEC = Setup_AD + R*Sim_AD
    """
    # Scenario 1: VEC is dominant (Better in both)
    if vec_setup <= ad_setup and vec_sim <= ad_sim:
        return 0.0  # Already better from the first run

    # Scenario 2: VEC is worse in both (Never compensates)
    if vec_setup >= ad_setup and vec_sim >= ad_sim:
        return np.inf

    # Scenario 3: The classic cross-over (VEC has slow setup but fast sim)
    denom: float = ad_sim - vec_sim
    if abs(denom) < 1e-15:
        # If speeds are equal, they never cross if setups differ
        return np.inf
    else:
        r: float = (vec_setup - ad_setup) / denom

    # If r is negative here, it means the lines are diverging away from each other
    return np.inf if r < 0 else r


def setup_initial_condition(problem: GenericEmtProblem, block: Block, n_nodes: int) -> None:
    """Injects a sinusoidal initial condition into the Problem."""
    x0: np.ndarray = problem.get_x0()

    for i in range(n_nodes):
        idx_state: int = 2 * i  # x_i in state_vars ordering [x_i, v_i, ...]
        if idx_state < len(block.state_vars):
            var_xi: Var = block.state_vars[idx_state]
            if var_xi.uid in problem.uid2idx_vars:
                x0[problem.get_var_idx(var_xi)] = 0.5 * np.sin(2.0 * np.pi * i / max(n_nodes, 1))
            else:
                pass
        else:
            pass

    # Override method safety
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
) -> Dict[str, Any]:
    vf: VarFactory = VarFactory()
    block: Block = create_linear_chain(n_masses=n_nodes, vf=vf)
    block.unify_blocks()
    t_sym: Var = Var("t_glob")

    mode: str = "VEC" if vectorized else "AD"
    print(f"   [{label} | {mode}] Compiling & Initializing...")

    t_setup_start: float = time.perf_counter()

    static_parameter_values_mapping: Dict[Var, Const] = dict(block.parameters)
    problem: GenericEmtProblem = GenericEmtProblem(
        sys_block=block,
        glob_time=t_sym,
        static_parameter_values_mapping=static_parameter_values_mapping,
    )
    setup_initial_condition(problem, block, n_nodes)

    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
    params0: np.ndarray = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)

    target_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal

    if vectorized:
        solver_vec = StructuralVectorizedSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=target_method, verbose=verbose
        )
        solver_vec.auto_detect_vectorization(method=target_method)
        solver = solver_vec
    else:
        solver_ad = JitAdSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=target_method, verbose=verbose
        )
        solver_ad.build_jit_ad()
        solver = solver_ad

    # Warmup step
    solver.simulate()

    setup_s: float = time.perf_counter() - t_setup_start
    # -----------------------------------------------

    n_steps: int = compute_steps(0.0, t_end, h)
    print(f"   [{label} | {mode}] Simulating pure loop... (steps={n_steps})")

    t_sim_start: float = time.perf_counter()
    _, y_arr, _ = solver.simulate()

    if hasattr(solver, 'last_pure_sim_time'):
        sim_s: float = getattr(solver, 'last_pure_sim_time')
    else:
        sim_s = time.perf_counter() - t_sim_start

    total_s: float = setup_s + sim_s
    ms_step: float = (sim_s / max(n_steps, 1)) * 1000.0
    activity: float = float(np.mean(np.abs(y_arr)))

    print(
        f"   >>> RESULT [{mode}] "
        f"Setup={setup_s:.4f}s | Sim={sim_s:.4f}s | Total={total_s:.4f}s | ms/step={ms_step:.6f}"
    )

    return dict({
        "mode": mode,
        "setup_s": setup_s,
        "sim_s": sim_s,
        "total_s": total_s,
        "ms_step": ms_step,
        "n_steps": n_steps,
        "activity": activity,
    })


def print_case_summary(case_name: str, ad: Dict[str, Any], vec: Dict[str, Any]) -> None:
    print("\n" + "-" * 96)
    print(f"[Summary] {case_name}")
    print("-" * 96)
    print(f"{'Mode':<8}{'Setup [s]':>14}{'Sim [s]':>14}{'Total [s]':>14}{'ms/step':>14}{'steps':>12}")
    print(
        f"{'AD':<8}{ad['setup_s']:>14.4f}{ad['sim_s']:>14.4f}{ad['total_s']:>14.4f}{ad['ms_step']:>14.6f}{ad['n_steps']:>12d}")
    print(
        f"{'VEC':<8}{vec['setup_s']:>14.4f}{vec['sim_s']:>14.4f}{vec['total_s']:>14.4f}{vec['ms_step']:>14.6f}{vec['n_steps']:>12d}")

    be: float = break_even_runs(vec["setup_s"], vec["sim_s"], ad["setup_s"], ad["sim_s"])

    if be == 0.0:
        print("\nBreak-even VEC vs AD: 0.00 runs (VEC is dominant in both Setup and Sim!)")
    elif np.isfinite(be):
        print(f"\nBreak-even VEC vs AD: ~{be:.2f} runs")
    else:
        print("\nBreak-even VEC vs AD: Does not compensate (VEC is slower in throughput)")

    one_shot: str = "AD" if ad["total_s"] <= vec["total_s"] else "VEC"
    throughput: str = "AD" if ad["sim_s"] <= vec["sim_s"] else "VEC"
    print(f"Best one-shot (Setup+Sim): {one_shot}")
    print(f"Best throughput (Sim only): {throughput}")


# -----------------------------------------------------------------------------
# 4) Main experiment plan
# -----------------------------------------------------------------------------
def main() -> None:
    print("=================================================================")
    print("  SCALABILITY BENCHMARK (LINEAR ONLY): AD vs VECTORIZED")
    print("=================================================================")

    N_LIN: int = 500

    experiments: List[Dict[str, Any]] = list([
        dict({"h": 1e-7, "t_end": 1e-4, "name": "1k steps"}),
        dict({"h": 1e-7, "t_end": 1e-3, "name": "10k steps"}),
        dict({"h": 1e-7, "t_end": 5e-3, "name": "50k steps"}),
        dict({"h": 1e-8, "t_end": 1e-3, "name": "100k steps"}),
        dict({"h": 1e-8, "t_end": 2e-3, "name": "200k steps"}),
    ])

    for k, cfg in enumerate(experiments, start=1):
        h: float = cfg["h"]
        t_end: float = cfg["t_end"]
        n_steps: int = compute_steps(0.0, t_end, h)

        print("\n" + "=" * 96)
        print(f"CASE {k}: Linear repeated | N={N_LIN} | h={h:.1e} | t_end={t_end:.1e} | steps={n_steps}")
        print("=" * 96)

        # AD baseline
        ad: Dict[str, Any] = run_backend(
            label="LIN",
            n_nodes=N_LIN,
            vectorized=False,
            t_end=t_end,
            h=h,
            verbose=False
        )

        # VEC
        vec: Dict[str, Any] = run_backend(
            label="LIN",
            n_nodes=N_LIN,
            vectorized=True,
            t_end=t_end,
            h=h,
            verbose=False
        )

        print_case_summary(
            case_name=f"Linear N={N_LIN}, h={h:.1e}, t_end={t_end:.1e}",
            ad=ad,
            vec=vec
        )

    print("\nBenchmark complete.")


if __name__ == "__main__":
    main()
