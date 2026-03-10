from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Tuple

import numpy as np


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src")

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


BACKEND_ORDER: Tuple[str, ...] = ("SD", "AD", "VEC", "COMPILED")
BACKEND_LABELS: Dict[str, str] = {
    "SD": "Symbolic",
    "AD": "AD",
    "VEC": "StructuralVec",
    "COMPILED": "StructuralCompiled",
}

CASE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "Small / overhead-dominated",
        "n_masses": 20,
        "h": 2e-5,
        "t_end": 1e-3,
    },
    {
        "name": "Large / throughput-dominated",
        "n_masses": 80,
        "h": 1e-5,
        "t_end": 5e-3,
    },
]


def create_linear_chain(n_masses: int, k_value: float = 500.0, c_value: float = 0.5) -> Block:
    k: Const = Const(k_value)
    c: Const = Const(c_value)

    pos_vars: List[Var] = [Var(f"x_{i}") for i in range(n_masses)]
    vel_vars: List[Var] = [Var(f"v_{i}") for i in range(n_masses)]

    d_pos_vars: List[Var] = [Var(f"d_x_{i}", base_var=pos_vars[i]) for i in range(n_masses)]
    d_vel_vars: List[Var] = [Var(f"d_v_{i}", base_var=vel_vars[i]) for i in range(n_masses)]

    state_vars: List[Var] = list()
    diff_vars: List[Var] = list()
    state_eqs: List[Expr] = list()

    for i in range(n_masses):
        x_i: Var = pos_vars[i]
        v_i: Var = vel_vars[i]
        d_x_i: Var = d_pos_vars[i]
        d_v_i: Var = d_vel_vars[i]

        x_l: Expr = pos_vars[i - 1] if i > 0 else Const(0.0)
        x_r: Expr = pos_vars[i + 1] if i < n_masses - 1 else Const(0.0)

        force: Expr = k * (x_l - x_i) + k * (x_r - x_i) - c * v_i

        state_vars.extend([x_i, v_i])
        diff_vars.extend([d_x_i, d_v_i])
        state_eqs.extend([v_i, force])

    block = Block(
        name=f"LinearChain_{n_masses}",
        state_vars=state_vars,
        state_eqs=state_eqs,
        diff_vars=diff_vars,
        parameters=dict(),
    )
    block.unify_blocks()
    return block


def build_initial_conditions(
    problem: GenericEmtProblem,
    block: Block,
    n_masses: int,
    k_value: float = 500.0,
    c_value: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = problem.get_dx0()
    params0: np.ndarray = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)

    pos0 = np.zeros(n_masses, dtype=np.float64)

    for i in range(n_masses):
        pos0[i] = 0.25 * np.sin(2.0 * np.pi * i / max(n_masses, 1))

    for i in range(n_masses):
        x_var: Var = block.state_vars[2 * i]
        v_var: Var = block.state_vars[2 * i + 1]

        x_idx: int = problem.get_var_idx(x_var)
        v_idx: int = problem.get_var_idx(v_var)

        x_i: float = float(pos0[i])
        v_i: float = 0.0

        x0[x_idx] = x_i
        x0[v_idx] = v_i

        dx0[2 * i] = v_i

        x_l: float = float(pos0[i - 1]) if i > 0 else 0.0
        x_r: float = float(pos0[i + 1]) if i < n_masses - 1 else 0.0
        dx0[2 * i + 1] = k_value * (x_l - x_i) + k_value * (x_r - x_i) - c_value * v_i

    return x0, dx0, params0


def make_solver(
    backend: str,
    problem: GenericEmtProblem,
    t_end: float,
    h: float,
    method: DynamicIntegrationMethod,
) -> Any:
    common_kwargs: Dict[str, Any] = dict(
        problem=problem,
        t0=0.0,
        t_end=t_end,
        h=h,
        method=method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )

    if backend == "SD":
        return JitSymbolicSolver(**common_kwargs)
    if backend == "AD":
        return JitAdSolver(**common_kwargs)
    if backend == "VEC":
        return StructuralVectorizedSolver(auto_vectorization=False, **common_kwargs)
    if backend == "COMPILED":
        return StructuralCompiledSolver(auto_build=False, **common_kwargs)

    raise ValueError(f"Unknown backend: {backend}")


def build_backend(solver: Any, backend: str, method: DynamicIntegrationMethod) -> None:
    if backend == "SD":
        solver.build_jit_kernel(method)
        solver._build_jit_symbolic_hybrid(method, use_sparse=True)
    elif backend == "AD":
        solver.build_jit_ad()
    elif backend == "VEC":
        solver.auto_detect_vectorization(method)
    elif backend == "COMPILED":
        solver._build_vectorized_backend(method)
    else:
        raise ValueError(f"Unknown backend: {backend}")


def run_once(
    solver: Any,
    x0: np.ndarray,
    dx0: np.ndarray,
    params0: np.ndarray,
) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    t0: float = time.perf_counter()
    t_arr, y_arr, dy_arr = solver.simulate(
        x0=x0.copy(),
        dx0=dx0.copy(),
        params0=params0.copy(),
    )
    elapsed: float = time.perf_counter() - t0
    return elapsed, t_arr, y_arr, dy_arr


def measure_backend(
    backend: str,
    n_masses: int,
    t_end: float,
    h: float,
    method: DynamicIntegrationMethod,
    steady_repeats: int = 2,
) -> Dict[str, Any]:
    block: Block = create_linear_chain(n_masses=n_masses)
    problem: GenericEmtProblem = GenericEmtProblem(sys_block=block, glob_time=Var("t_glob"))
    x0, dx0, params0 = build_initial_conditions(problem=problem, block=block, n_masses=n_masses)

    t_setup_start: float = time.perf_counter()
    solver: Any = make_solver(
        backend=backend,
        problem=problem,
        t_end=t_end,
        h=h,
        method=method,
    )
    build_backend(solver=solver, backend=backend, method=method)
    setup_s: float = time.perf_counter() - t_setup_start

    first_run_s, t_arr, y_arr, dy_arr = run_once(
        solver=solver,
        x0=x0,
        dx0=dx0,
        params0=params0,
    )

    steady_times: List[float] = list()
    steady_y: np.ndarray = y_arr
    steady_dy: np.ndarray = dy_arr

    for _ in range(steady_repeats):
        run_s, _, y_tmp, dy_tmp = run_once(
            solver=solver,
            x0=x0,
            dx0=dx0,
            params0=params0,
        )
        steady_times.append(run_s)
        steady_y = y_tmp
        steady_dy = dy_tmp

    steady_run_s: float = float(np.mean(steady_times)) if steady_times else first_run_s
    steps: int = int(np.ceil(t_end / h))

    if not np.all(np.isfinite(steady_y)):
        raise RuntimeError(f"{backend} produced non-finite y values")
    if not np.all(np.isfinite(steady_dy)):
        raise RuntimeError(f"{backend} produced non-finite dy values")

    if hasattr(solver, "get_backend_build_stats"):
        build_stats: Dict[str, float] = solver.get_backend_build_stats()
    else:
        build_stats = dict()

    return {
        "backend": backend,
        "label": BACKEND_LABELS[backend],
        "solver": solver,
        "setup_s": setup_s,
        "first_run_s": first_run_s,
        "steady_run_s": steady_run_s,
        "one_shot_s": setup_s + first_run_s,
        "ms_per_step": 1000.0 * steady_run_s / max(steps, 1),
        "steps": steps,
        "t": t_arr,
        "y": steady_y,
        "dy": steady_dy,
        "build_stats": build_stats,
    }


def speedup(reference_s: float, candidate_s: float) -> float:
    if candidate_s <= 0.0:
        return np.inf
    return reference_s / candidate_s


def break_even_runs(
    fast_setup: float,
    fast_run: float,
    base_setup: float,
    base_run: float,
) -> float:
    if fast_setup <= base_setup and fast_run <= base_run:
        return 0.0

    if fast_setup >= base_setup and fast_run >= base_run:
        return np.inf

    denom: float = base_run - fast_run
    if abs(denom) < 1e-15:
        return np.inf

    runs: float = (fast_setup - base_setup) / denom
    return np.inf if runs < 0.0 else runs


def serialize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a JSON-safe summary of one backend measurement.

    :param result: Raw benchmark result.
    :type result: Dict[str, Any]
    :return: JSON-safe summary.
    :rtype: Dict[str, Any]
    """
    return {
        "backend": result["backend"],
        "label": result["label"],
        "setup_s": float(result["setup_s"]),
        "first_run_s": float(result["first_run_s"]),
        "steady_run_s": float(result["steady_run_s"]),
        "one_shot_s": float(result["one_shot_s"]),
        "ms_per_step": float(result["ms_per_step"]),
        "steps": int(result["steps"]),
        "build_stats": {k: float(v) for k, v in result.get("build_stats", dict()).items()},
    }


def _extract_last_json_line(stdout: str) -> Dict[str, Any]:
    """
    Parse the final JSON payload produced by a subprocess run.

    :param stdout: Full standard output of the subprocess.
    :type stdout: str
    :return: Parsed JSON payload.
    :rtype: Dict[str, Any]
    """
    lines: List[str] = [line.strip() for line in stdout.splitlines() if line.strip()]

    if len(lines) == 0:
        raise RuntimeError("Subprocess produced no output")

    return json.loads(lines[-1])


def _run_single_backend_subprocess(
    backend: str,
    case_cfg: Dict[str, Any],
    method: DynamicIntegrationMethod,
) -> Dict[str, Any]:
    """
    Run one backend measurement in a clean Python subprocess.

    :param backend: Backend key.
    :type backend: str
    :param case_cfg: Benchmark case configuration.
    :type case_cfg: Dict[str, Any]
    :param method: Integration method.
    :type method: DynamicIntegrationMethod
    :return: Parsed JSON payload.
    :rtype: Dict[str, Any]
    """
    command: List[str] = [
        sys.executable,
        os.path.abspath(__file__),
        "--single-backend",
        backend,
        "--n-masses",
        str(case_cfg["n_masses"]),
        "--t-end",
        repr(case_cfg["t_end"]),
        "--h",
        repr(case_cfg["h"]),
        "--method",
        method.name,
    ]

    proc = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return _extract_last_json_line(proc.stdout)


def print_subprocess_protocol_summary(
    case_name: str,
    cold_results: Dict[str, Dict[str, Any]],
    warm_results: Dict[str, Dict[str, Any]],
) -> None:
    """
    Print cold-start and warm-start benchmark tables.

    :param case_name: Human-readable case name.
    :type case_name: str
    :param cold_results: First subprocess measurements.
    :type cold_results: Dict[str, Dict[str, Any]]
    :param warm_results: Second subprocess measurements.
    :type warm_results: Dict[str, Dict[str, Any]]
    :return: None
    :rtype: None
    """
    print("\n" + "=" * 120)
    print(f"Subprocess Protocol | {case_name}")
    print("=" * 120)
    print(
        f"{'Backend':<18}"
        f"{'Cold build':>12}"
        f"{'Cold 1st':>12}"
        f"{'Cold steady':>14}"
        f"{'Warm build':>12}"
        f"{'Warm 1st':>12}"
        f"{'Warm steady':>14}"
    )

    for backend in BACKEND_ORDER:
        cold = cold_results[backend]
        warm = warm_results[backend]
        print(
            f"{BACKEND_LABELS[backend]:<18}"
            f"{cold['setup_s']:>12.6f}"
            f"{cold['first_run_s']:>12.6f}"
            f"{cold['steady_run_s']:>14.6f}"
            f"{warm['setup_s']:>12.6f}"
            f"{warm['first_run_s']:>12.6f}"
            f"{warm['steady_run_s']:>14.6f}"
        )

    compiled_cold = cold_results["COMPILED"]
    compiled_warm = warm_results["COMPILED"]
    vec_cold = cold_results["VEC"]
    vec_warm = warm_results["VEC"]

    print("\nStructuralCompiled vs StructuralVec")
    print(f"  Cold one-shot speedup : {speedup(vec_cold['setup_s'] + vec_cold['first_run_s'], compiled_cold['setup_s'] + compiled_cold['first_run_s']):.2f}x")
    print(f"  Warm one-shot speedup : {speedup(vec_warm['setup_s'] + vec_warm['first_run_s'], compiled_warm['setup_s'] + compiled_warm['first_run_s']):.2f}x")
    print(f"  Cold steady speedup   : {speedup(vec_cold['steady_run_s'], compiled_cold['steady_run_s']):.2f}x")
    print(f"  Warm steady speedup   : {speedup(vec_warm['steady_run_s'], compiled_warm['steady_run_s']):.2f}x")


def run_subprocess_protocol(method: DynamicIntegrationMethod) -> None:
    """
    Measure cold-start and warm-start behavior using fresh subprocesses.

    :param method: Integration method.
    :type method: DynamicIntegrationMethod
    :return: None
    :rtype: None
    """
    print("\n" + "#" * 120)
    print("SUBPROCESS PROTOCOL: cold-start vs warm-start")
    print("#" * 120)

    for case_cfg in CASE_DEFINITIONS:
        cold_results: Dict[str, Dict[str, Any]] = dict()
        warm_results: Dict[str, Dict[str, Any]] = dict()

        for backend in BACKEND_ORDER:
            print(f"  -> Cold subprocess {case_cfg['name']} | {BACKEND_LABELS[backend]}")
            cold_results[backend] = _run_single_backend_subprocess(backend, case_cfg, method)
            print(f"  -> Warm subprocess {case_cfg['name']} | {BACKEND_LABELS[backend]}")
            warm_results[backend] = _run_single_backend_subprocess(backend, case_cfg, method)

        print_subprocess_protocol_summary(case_cfg["name"], cold_results, warm_results)


def print_case_summary(case_name: str, results: Dict[str, Dict[str, Any]]) -> None:
    reference_y: np.ndarray = results["SD"]["y"]

    print("\n" + "=" * 108)
    print(case_name)
    print("=" * 108)
    print(
        f"{'Backend':<18}"
        f"{'Setup [s]':>14}"
        f"{'1st run [s]':>14}"
        f"{'Steady [s]':>14}"
        f"{'One-shot [s]':>16}"
        f"{'ms/step':>12}"
        f"{'Max |dy| err':>20}"
    )

    for backend in BACKEND_ORDER:
        y_arr: np.ndarray = results[backend]["y"]
        max_err: float = 0.0 if backend == "SD" else float(np.max(np.abs(reference_y - y_arr)))

        print(
            f"{results[backend]['label']:<18}"
            f"{results[backend]['setup_s']:>14.6f}"
            f"{results[backend]['first_run_s']:>14.6f}"
            f"{results[backend]['steady_run_s']:>14.6f}"
            f"{results[backend]['one_shot_s']:>16.6f}"
            f"{results[backend]['ms_per_step']:>12.6f}"
            f"{max_err:>20.3e}"
        )

    sd = results["SD"]
    ad = results["AD"]
    vec = results["VEC"]
    compiled = results["COMPILED"]

    print("\nSpeedups (one-shot)")
    print(f"  StructuralCompiled vs Symbolic      : {speedup(sd['one_shot_s'], compiled['one_shot_s']):.2f}x")
    print(f"  StructuralCompiled vs AD            : {speedup(ad['one_shot_s'], compiled['one_shot_s']):.2f}x")
    print(f"  StructuralCompiled vs StructuralVec : {speedup(vec['one_shot_s'], compiled['one_shot_s']):.2f}x")

    print("\nSpeedups (steady run)")
    print(f"  StructuralCompiled vs Symbolic      : {speedup(sd['steady_run_s'], compiled['steady_run_s']):.2f}x")
    print(f"  StructuralCompiled vs AD            : {speedup(ad['steady_run_s'], compiled['steady_run_s']):.2f}x")
    print(f"  StructuralCompiled vs StructuralVec : {speedup(vec['steady_run_s'], compiled['steady_run_s']):.2f}x")

    be_fast_vs_vec: float = break_even_runs(
        fast_setup=compiled["setup_s"],
        fast_run=compiled["steady_run_s"],
        base_setup=vec["setup_s"],
        base_run=vec["steady_run_s"],
    )

    if np.isfinite(be_fast_vs_vec):
        print(f"\nBreak-even StructuralCompiled vs StructuralVec: ~{be_fast_vs_vec:.2f} runs")
    else:
        print("\nBreak-even StructuralCompiled vs StructuralVec: no crossover")

    max_compiled_err: float = float(np.max(np.abs(reference_y - compiled["y"])))
    if max_compiled_err > 1e-6:
        print(f"[WARNING] StructuralCompiled deviates from SD by {max_compiled_err:.3e}")

    compiled_build_stats: Dict[str, float] = compiled.get("build_stats", dict())
    if compiled_build_stats:
        print("\nStructuralCompiled build breakdown")
        ordered_keys: Tuple[str, ...] = (
            "grouping_s",
            "vec_kernel_compile_s",
            "residual_assembler_s",
            "residual_dispatcher_s",
            "residual_buffer_alloc_s",
            "jacobian_evaluator_s",
            "jac_column_rows_s",
            "jac_csc_shell_s",
            "jac_coloring_s",
            "jac_scatter_map_s",
            "jac_ad_kernels_s",
            "jac_dispatcher_s",
            "total_s",
        )

        for key in ordered_keys:
            if key in compiled_build_stats:
                print(f"  {key:<24}: {compiled_build_stats[key]:.6f} s")


def run_case(
    case_name: str,
    n_masses: int,
    t_end: float,
    h: float,
    method: DynamicIntegrationMethod,
) -> None:
    print("\n" + "-" * 108)
    print(
        f"Running case '{case_name}' | masses={n_masses} | states={2 * n_masses} | "
        f"h={h:.2e} | t_end={t_end:.2e} | steps={int(np.ceil(t_end / h))}"
    )
    print("-" * 108)

    results: Dict[str, Dict[str, Any]] = dict()

    for backend in BACKEND_ORDER:
        print(f"  -> Measuring {BACKEND_LABELS[backend]}")
        results[backend] = measure_backend(
            backend=backend,
            n_masses=n_masses,
            t_end=t_end,
            h=h,
            method=method,
            steady_repeats=2,
        )

    print_case_summary(case_name=case_name, results=results)


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    :return: Parsed arguments.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(description="EMT solver overhead benchmark")
    parser.add_argument("--single-backend", choices=BACKEND_ORDER, default=None)
    parser.add_argument("--n-masses", type=int, default=None)
    parser.add_argument("--t-end", type=float, default=None)
    parser.add_argument("--h", type=float, default=None)
    parser.add_argument("--method", type=str, default=DynamicIntegrationMethod.DaeTrapezoidal.name)
    parser.add_argument("--subprocess-protocol", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    method: DynamicIntegrationMethod = DynamicIntegrationMethod[args.method]

    if args.single_backend is not None:
        if args.n_masses is None or args.t_end is None or args.h is None:
            raise ValueError("single-backend mode requires --n-masses, --t-end and --h")

        result = measure_backend(
            backend=args.single_backend,
            n_masses=args.n_masses,
            t_end=args.t_end,
            h=args.h,
            method=method,
            steady_repeats=2,
        )
        print(json.dumps(serialize_result(result), sort_keys=True))
        return

    if args.subprocess_protocol:
        print("=" * 108)
        print("EMT SOLVER OVERHEAD DEMO")
        print("=" * 108)
        print("Running subprocess protocol only. Each measurement uses a fresh Python process.\n")
        run_subprocess_protocol(method)
        return

    print("=" * 108)
    print("EMT SOLVER OVERHEAD DEMO")
    print("=" * 108)
    print("Note: for true cold-start numbers, launch this script in a fresh Python process.")
    print("      Deterministic JIT names + disk cache can make repeated launches faster.\n")

    for case in CASE_DEFINITIONS:
        run_case(
            case_name=case["name"],
            n_masses=case["n_masses"],
            t_end=case["t_end"],
            h=case["h"],
            method=method,
        )


if __name__ == "__main__":
    main()
