import statistics
import time
from typing import Dict, List, Optional, Tuple
import pandas as pd

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper, JitSymbolicSolver
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.Utils.Symbolic.symbolic import Comparison, Const, Expr, Var
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block, picdro
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = []


def _unsafe_bool_expr(expr: Expr | Comparison | float | int) -> Expr:
    if isinstance(expr, Comparison):
        return expr.to_expression()
    if isinstance(expr, Expr):
        return expr
    return Const(float(expr))


def _unsafe_value_expr(expr: Expr | Comparison | float | int) -> Expr:
    if isinstance(expr, Comparison):
        return expr.to_expression()
    if isinstance(expr, Expr):
        return expr
    return Const(float(expr))


def _unsafe_select_expr(
    boolexpr: Expr | Comparison | float | int,
    when_true: Expr | Comparison | float | int,
    when_false: Expr | Comparison | float | int,
) -> Expr:
    cond_expr = _unsafe_bool_expr(boolexpr)
    true_expr = _unsafe_value_expr(when_true)
    false_expr = _unsafe_value_expr(when_false)
    return cond_expr * true_expr + (Const(1.0) - cond_expr) * false_expr


def _unsafe_ifelse_expr(
    boolexpr: Expr | Comparison | float | int,
    when_true: Expr | Comparison | float | int,
    when_false: Expr | Comparison | float | int,
) -> Expr:
    return _unsafe_select_expr(boolexpr, when_true, when_false)


class ModeTraceUpdater(BoundaryUpdateWrapper):
    __slots__ = ["base_updater", "tracked_indices", "trace_t", "trace_values"]

    def __init__(self, base_updater: BoundaryUpdateWrapper, tracked_indices: Dict[str, int]) -> None:
        self.base_updater = base_updater
        self.tracked_indices = tracked_indices
        self.trace_t: List[float] = list()
        self.trace_values: Dict[str, List[float]] = {name: list() for name in tracked_indices.keys()}

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        self.base_updater.update(t, x, params)
        self.trace_t.append(float(t))
        for name, idx in self.tracked_indices.items():
            self.trace_values[name].append(float(params[idx]))

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        return self.base_updater.get_next_forced_event_time(t_prev, t_target)

    def get_trace(self, name: str) -> np.ndarray:
        return np.asarray(self.trace_values[name], dtype=float)


def create_internal_ifelse_switch_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    x = vf.add_var("x_ifelse")
    d_x = vf.add_diff_var(name="d_x_ifelse", base_var=x)
    gain = vf.add_var("gain_ifelse")

    block = Block(
        name="InternalIfElseSwitchDemo",
        state_vars=[x],
        diff_vars=[d_x],
        state_eqs=[gain * (_unsafe_ifelse_expr(x > 0.5, 0.0, 1.0) - x)],
        parameters={gain: Const(2000.0)},
        init_eqs={x: Const(0.49)},
    )
    return block, {"x": x}


def create_internal_select_switch_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    x = vf.add_var("x_select")
    d_x = vf.add_diff_var(name="d_x_select", base_var=x)
    gain = vf.add_var("gain_select")

    block = Block(
        name="InternalSelectSwitchDemo",
        state_vars=[x],
        diff_vars=[d_x],
        state_eqs=[gain * (_unsafe_select_expr(x > 0.5, 0.0, 1.0) - x)],
        parameters={gain: Const(2000.0)},
        init_eqs={x: Const(0.49)},
    )
    return block, {"x": x}


def create_procedural_mode_switch_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    x = vf.add_var("x_mode")
    d_x = vf.add_diff_var(name="d_x_mode", base_var=x)
    gain = vf.add_var("gain_mode")
    mode_switch = vf.add_var("mode_switch")

    block = Block(
        name="ProceduralModeSwitchDemo",
        state_vars=[x],
        diff_vars=[d_x],
        state_eqs=[gain * ((Const(1.0) - mode_switch) - x)],
        parameters={gain: Const(2000.0)},
        mode_dict={mode_switch: Const(0.0)},
        init_eqs={x: Const(0.49)},
    )
    block.procedural_logic = [
        picdro(x > 0.5, Const(0.0), Const(0.0), output=mode_switch, name="external_switch_mode"),
    ]
    return block, {"x": x, "mode_switch": mode_switch}


def _collector_step_metrics(collector: NewtonTraceCollector) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    grouped: Dict[Tuple[int, float], Dict[str, float]] = dict()

    for record in collector.records:
        key = (int(record["step"]), round(float(record["t"]), 12))
        item = grouped.get(key)
        if item is None:
            grouped[key] = {
                "t": float(record["t"]),
                "iterations": float(int(record["newton_iter"]) + 1),
                "final_residual": float(record["res_norm_inf"] if record["res_norm_inf"] is not None else np.nan),
            }
        else:
            item["iterations"] = max(item["iterations"], float(int(record["newton_iter"]) + 1))
            item["final_residual"] = float(record["res_norm_inf"] if record["res_norm_inf"] is not None else np.nan)

    ordered = [grouped[key] for key in sorted(grouped.keys(), key=lambda item: item[1])]
    return (
        np.asarray([item["t"] for item in ordered], dtype=float),
        np.asarray([item["iterations"] for item in ordered], dtype=float),
        np.asarray([item["final_residual"] for item in ordered], dtype=float),
    )


def _collector_worst_step_curve(collector: NewtonTraceCollector) -> Tuple[np.ndarray, np.ndarray, float, str]:
    grouped: Dict[Tuple[int, float], List[dict]] = dict()
    for record in collector.records:
        key = (int(record["step"]), round(float(record["t"]), 12))
        grouped.setdefault(key, []).append(record)

    worst_key = max(grouped.keys(), key=lambda item: (len(grouped[item]), -item[1]))
    records = sorted(grouped[worst_key], key=lambda item: int(item["newton_iter"]))

    residual_curve = np.asarray([
        float(item["res_norm_inf"]) if item["res_norm_inf"] is not None else np.nan
        for item in records
    ], dtype=float)

    if np.all(np.isnan(residual_curve)):
        residual_curve = np.asarray([
            float(item["dx_norm_inf"]) if item.get("dx_norm_inf", None) is not None else np.nan
            for item in records
        ], dtype=float)
        metric_label = "||dx||_inf on the worst local step"
    else:
        metric_label = "||res||_inf on the worst local step"

    finite_mask = np.isfinite(residual_curve)
    if np.any(finite_mask):
        min_positive = np.min(np.abs(residual_curve[finite_mask]))
        floor = max(1.0e-16, min_positive * 1.0e-3)
        residual_curve = np.where(np.abs(residual_curve) < floor, floor, residual_curve)

    return (
        np.asarray([int(item["newton_iter"]) + 1 for item in records], dtype=float),
        residual_curve,
        float(records[0]["t"]),
        metric_label,
    )


def _first_true_time(time_array: np.ndarray, signal: np.ndarray, threshold: float = 0.5) -> Optional[float]:
    idx = np.flatnonzero(signal > threshold)
    if len(idx) == 0:
        return None
    return float(time_array[int(idx[0])])


def _add_vertical_marker(ax: plt.Axes, time_value: Optional[float], text: str, *, color: str, linestyle: str) -> None:
    if time_value is None:
        return
    ax.axvline(time_value, color=color, linestyle=linestyle, linewidth=1.3, label=f"{text} = {time_value:.4f} s")


def _build_case(builder) -> Tuple[GenericEmtProblem, JitSymbolicSolver, Dict[str, Var], List[dict]]:
    vf = VarFactory()
    block, vars_map = builder(vf)
    block.unify_blocks()

    problem = GenericEmtProblem(sys_block=block, glob_time=vf.add_var(f"t_{block.name}"))
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=1.0e-2,
        h=1.0e-3,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )
    return problem, solver, vars_map, problem.sys_block._procedural_logic_to_dict()


def _run_case_once(
    problem: GenericEmtProblem,
    solver: JitSymbolicSolver,
    vars_map: Dict[str, Var],
    logic_snapshot: List[dict],
) -> Dict[str, object]:
    problem.sys_block.procedural_logic = Block._procedural_logic_from_dict(logic_snapshot)

    collector = NewtonTraceCollector()
    problem.set_newton_trace_collector(collector)

    updater = build_boundary_updater_from_block(problem)
    mode_trace: Optional[ModeTraceUpdater] = None
    if updater is not None and "mode_switch" in vars_map:
        mode_trace = ModeTraceUpdater(
            base_updater=updater,
            tracked_indices={"mode_switch": problem.uid2idx_event_params[vars_map["mode_switch"].uid]},
        )
        updater = mode_trace

    t_start = time.perf_counter()
    t, y_hist, _ = solver.simulate(
        params0=problem.event_params_values.copy(),
        boundary_updater=updater,
    )
    elapsed_s = time.perf_counter() - t_start

    step_t, step_iters, step_residual = _collector_step_metrics(collector)
    worst_iter_axis, worst_residual, worst_time, worst_metric_label = _collector_worst_step_curve(collector)

    return {
        "elapsed_s": elapsed_s,
        "t": t,
        "y_hist": y_hist,
        "x_idx": problem.get_var_idx(vars_map["x"]),
        "step_t": step_t,
        "step_iters": step_iters,
        "step_residual": step_residual,
        "worst_iter_axis": worst_iter_axis,
        "worst_residual": worst_residual,
        "worst_time": worst_time,
        "worst_metric_label": worst_metric_label,
        "mode_t": None if mode_trace is None else np.asarray(mode_trace.trace_t, dtype=float),
        "mode_v": None if mode_trace is None else mode_trace.get_trace("mode_switch"),
    }


def benchmark_case(label: str, builder, measured_runs: int = 3) -> Dict[str, object]:
    problem, solver, vars_map, logic_snapshot = _build_case(builder)

    _run_case_once(problem, solver, vars_map, logic_snapshot)
    measured = [
        _run_case_once(problem, solver, vars_map, logic_snapshot)
        for _ in range(measured_runs)
    ]
    plot_run = measured[0]

    elapsed_samples = [float(item["elapsed_s"]) for item in measured]
    mean_iteration_samples = [float(np.mean(item["step_iters"])) for item in measured]
    max_iteration_samples = [float(np.max(item["step_iters"])) for item in measured]

    plot_run.update({
        "label": label,
        "median_elapsed_s": statistics.median(elapsed_samples),
        "mean_newton_iterations": statistics.median(mean_iteration_samples),
        "max_newton_iterations": statistics.median(max_iteration_samples),
        "elapsed_samples": elapsed_samples,
    })
    return plot_run


def plot_benchmark_comparison(cases: List[Dict[str, object]]) -> None:
    colors = {
        "ifelse inside state_eq": "tab:red",
        "select inside state_eq": "tab:orange",
        "procedural mode in state_eq": "tab:green",
    }

    fig = plt.figure(figsize=(14, 12))
    grid = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 0.6])
    ax_state = fig.add_subplot(grid[0, 0])
    ax_branch = fig.add_subplot(grid[0, 1])
    ax_iters = fig.add_subplot(grid[1, 0])
    ax_res = fig.add_subplot(grid[1, 1])
    ax_runtime = fig.add_subplot(grid[2, :])

    runtime_labels: List[str] = list()
    runtime_values: List[float] = list()
    metric_label = str(cases[0]["worst_metric_label"])

    for case in cases:
        label = str(case["label"])
        color = colors[label]
        t = np.asarray(case["t"], dtype=float)
        x_hist = np.asarray(case["y_hist"], dtype=float)[:, int(case["x_idx"])]
        step_t = np.asarray(case["step_t"], dtype=float)
        step_iters = np.asarray(case["step_iters"], dtype=float)
        worst_iter_axis = np.asarray(case["worst_iter_axis"], dtype=float)
        worst_residual = np.asarray(case["worst_residual"], dtype=float)

        ax_state.plot(t, x_hist, color=color, linewidth=2.0, label=label)
        ax_iters.step(step_t, step_iters, where="post", color=color, linewidth=2.0, label=label)
        finite_mask = np.isfinite(worst_residual)
        ax_res.semilogy(
            worst_iter_axis[finite_mask],
            worst_residual[finite_mask],
            marker="o",
            color=color,
            linewidth=1.8,
            label=f"{label} @ t={float(case['worst_time']):.4f} s",
        )

        switch_time: Optional[float]
        mode_t = case["mode_t"]
        mode_v = case["mode_v"]
        if mode_t is None or mode_v is None:
            branch_signal = (x_hist > 0.5).astype(float)
            ax_branch.step(t, branch_signal, where="post", color=color, linewidth=2.0, label=label)
            switch_time = _first_true_time(t, branch_signal)
        else:
            branch_signal = np.asarray(mode_v, dtype=float)
            ax_branch.step(np.asarray(mode_t, dtype=float), branch_signal, where="post", color=color, linewidth=2.0, label=label)
            switch_time = _first_true_time(np.asarray(mode_t, dtype=float), branch_signal)

        _add_vertical_marker(ax_state, switch_time, f"{label} switch", color=color, linestyle="--")
        _add_vertical_marker(ax_branch, switch_time, f"{label} switch", color=color, linestyle="--")

        runtime_labels.append(label)
        runtime_values.append(float(case["median_elapsed_s"]))

    ax_state.axhline(0.5, color="black", linestyle=":", linewidth=1.1, label="switch threshold")
    ax_state.set_title("State trajectory near the discontinuity")
    ax_state.set_ylabel("x")
    ax_state.grid(True)
    ax_state.legend(loc="best")

    ax_branch.set_title("Active branch / procedural mode")
    ax_branch.set_ylabel("branch = 1 when switched")
    ax_branch.set_ylim(-0.1, 1.1)
    ax_branch.grid(True)
    ax_branch.legend(loc="best")

    ax_iters.set_title("Newton iterations per local step")
    ax_iters.set_xlabel("Time [s]")
    ax_iters.set_ylabel("iterations")
    ax_iters.grid(True)
    ax_iters.legend(loc="best")

    ax_res.set_title(metric_label)
    ax_res.set_xlabel("Newton iteration")
    ax_res.set_ylabel(metric_label.split(" on ")[0])
    ax_res.grid(True)
    ax_res.legend(loc="best")

    ax_runtime.bar(runtime_labels, runtime_values, color=[colors[label] for label in runtime_labels])
    ax_runtime.set_ylabel("median runtime [s]")
    ax_runtime.set_title("Warm benchmark runtime")
    ax_runtime.grid(True, axis="y")

    fig.tight_layout()


def print_benchmark_summary(cases: List[Dict[str, object]]) -> None:
    print("=== Conditional Placement Benchmark ===")
    print("Compare the same switch resolved in three places:")
    print("1) ifelse(...) inside state_eq")
    print("2) select(...) inside state_eq")
    print("3) procedural mode outside Newton + algebraic mode consumption inside state_eq")
    print("")

    for case in cases:
        print(f"--- {case['label']} ---")
        print(f"median runtime [s]:       {float(case['median_elapsed_s']):.6f}")
        print(f"mean Newton iterations:  {float(case['mean_newton_iterations']):.3f}")
        print(f"max Newton iterations:   {float(case['max_newton_iterations']):.3f}")
        print(f"worst-step time [s]:     {float(case['worst_time']):.6f}")
        print("")


def _build_export_dataframe(cases: List[Dict[str, object]]) -> pd.DataFrame:
    export_frames: List[pd.DataFrame] = list()

    for case in cases:
        label = str(case["label"])
        t = np.asarray(case["t"], dtype=float)
        x_hist = np.asarray(case["y_hist"], dtype=float)[:, int(case["x_idx"])]
        step_t = np.asarray(case["step_t"], dtype=float)
        step_iters = np.asarray(case["step_iters"], dtype=float)
        worst_iter_axis = np.asarray(case["worst_iter_axis"], dtype=float)
        worst_residual = np.asarray(case["worst_residual"], dtype=float)
        worst_metric_label = str(case["worst_metric_label"])
        worst_time = float(case["worst_time"])

        mode_t = case["mode_t"]
        mode_v = case["mode_v"]
        if mode_t is None or mode_v is None:
            branch_t = t
            branch_signal = (x_hist > 0.5).astype(float)
        else:
            branch_t = np.asarray(mode_t, dtype=float)
            branch_signal = np.asarray(mode_v, dtype=float)

        export_frames.append(pd.DataFrame({
            "case_label": label,
            "plot_title": "State trajectory near the discontinuity",
            "time_s": t,
            "state_x": x_hist,
        }))

        export_frames.append(pd.DataFrame({
            "case_label": label,
            "plot_title": "Active branch / procedural mode",
            "time_s": branch_t,
            "active_branch": branch_signal,
        }))

        export_frames.append(pd.DataFrame({
            "case_label": label,
            "plot_title": "Newton iterations per local step",
            "time_s": step_t,
            "newton_iterations": step_iters,
        }))

        export_frames.append(pd.DataFrame({
            "case_label": label,
            "plot_title": worst_metric_label,
            "worst_step_time_s": worst_time,
            "newton_iteration": worst_iter_axis,
            "worst_step_metric_value": worst_residual,
        }))

    return pd.concat(export_frames, ignore_index=True, sort=False)


def main() -> None:
    cases = [
        benchmark_case("ifelse inside state_eq", create_internal_ifelse_switch_system),
        benchmark_case("select inside state_eq", create_internal_select_switch_system),
        benchmark_case("procedural mode in state_eq", create_procedural_mode_switch_system),
    ]

    results_df = _build_export_dataframe(cases)
    name = "demo_conditional_placement_benchmark.csv"
    results_df.to_csv(name, index=False)

    print_benchmark_summary(cases)
    plot_benchmark_comparison(cases)
    plt.show()


if __name__ == "__main__":
    main()
