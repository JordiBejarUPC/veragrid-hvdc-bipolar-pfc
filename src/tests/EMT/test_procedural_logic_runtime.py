# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import unittest
import time
import statistics

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Utils.procedural_logic import (
    aflipflop,
    DelayedThresholdLatchLogic,
    bool_and,
    bool_or,
    build_boundary_updater_from_block,
    flipflop,
    ifelse,
    lastvalue,
    picdro,
    reset,
    select,
)
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Comparison, Const, Expr, Var
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


def create_integrator_trip_system(vf: VarFactory) -> tuple[Block, dict[str, Var]]:
    x_i = vf.add_var("x_i")
    y = vf.add_var("y")

    d_x_i = vf.add_diff_var(name="d_x_i", base_var=x_i)
    d_y = vf.add_diff_var(name="d_y", base_var=y)

    mode_int_enable = vf.add_var("mode_int_enable")

    ref = vf.add_var("ref")
    k_i = vf.add_var("k_i")
    tau = vf.add_var("tau")

    state_vars = [x_i, y]
    diff_vars = [d_x_i, d_y]
    state_eqs: list[Expr] = [
        mode_int_enable * k_i * (ref - y),
        (x_i - y) / tau,
    ]

    parameters = {
        ref: Const(1.0),
        k_i: Const(200.0),
        tau: Const(2.0e-3),
    }
    mode_dict = {mode_int_enable: Const(1.0)}

    block = Block(
        name="ModeProtectionIntegratorDemo",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters=parameters,
        mode_dict=mode_dict,
    )

    block.procedural_logic = [
        DelayedThresholdLatchLogic(
            monitored_var_name="y",
            mode_var_name="mode_int_enable",
            threshold=0.2,
            delay=1.5e-3,
            reset_delay=None,
            name="trip_logic",
        )
    ]

    return block, {
        "x_i": x_i,
        "y": y,
        "mode_var": mode_int_enable,
    }


def create_boolean_operator_system(vf: VarFactory) -> tuple[Block, dict[str, Var]]:
    x_fast = vf.add_var("x_fast")
    x_slow = vf.add_var("x_slow")
    x_mem = vf.add_var("x_mem")

    d_x_fast = vf.add_diff_var(name="d_x_fast", base_var=x_fast)
    d_x_slow = vf.add_diff_var(name="d_x_slow", base_var=x_slow)
    d_x_mem = vf.add_diff_var(name="d_x_mem", base_var=x_mem)

    trip_fast = vf.add_var("trip_fast")
    trip_and = vf.add_var("trip_and")
    master_trip = vf.add_var("master_trip")
    x_mem_last = vf.add_var("x_mem_last")

    tau_fast = vf.add_var("tau_fast")
    tau_slow = vf.add_var("tau_slow")
    k_mem = vf.add_var("k_mem")

    block = Block(
        name="BooleanOperatorProceduralDemo",
        state_vars=[x_fast, x_slow, x_mem],
        diff_vars=[d_x_fast, d_x_slow, d_x_mem],
        state_eqs=[
            (Const(1.0) - x_fast) / tau_fast,
            (Const(1.0) - x_slow) / tau_slow,
            (Const(1.0) - master_trip) * k_mem * (x_fast - x_mem),
        ],
        parameters={
            tau_fast: Const(3.0e-3),
            tau_slow: Const(8.0e-3),
            k_mem: Const(120.0),
        },
        mode_dict={
            trip_fast: Const(0.0),
            trip_and: Const(0.0),
            master_trip: Const(0.0),
            x_mem_last: Const(0.0),
        },
    )

    block.procedural_logic = [
        picdro(x_fast > 0.65, 1.0e-3, 0.0, output=trip_fast),
        picdro(bool_and(x_fast > 0.45, x_slow > 0.30), 2.0e-3, 0.0, output=trip_and),
        flipflop(bool_or(trip_fast > 0.5, trip_and > 0.5), 0.0, output=master_trip),
        lastvalue(x_mem, output=x_mem_last),
        reset(x_mem, master_trip > 0.5, 0.0),
    ]

    return block, {
        "x_fast": x_fast,
        "x_slow": x_slow,
        "x_mem": x_mem,
        "trip_fast": trip_fast,
        "trip_and": trip_and,
        "master_trip": master_trip,
        "x_mem_last": x_mem_last,
    }


def create_analog_flipflop_system(vf: VarFactory) -> tuple[Block, dict[str, Var]]:
    x_in = vf.add_var("x_in_af")
    x_reset = vf.add_var("x_reset_af")

    d_x_in = vf.add_diff_var(name="d_x_in_af", base_var=x_in)
    d_x_reset = vf.add_diff_var(name="d_x_reset_af", base_var=x_reset)

    y_hold = vf.add_var("y_hold_af")
    ff_state = vf.add_var("ff_state_af")

    tau_in = vf.add_var("tau_in_af")
    tau_reset = vf.add_var("tau_reset_af")

    block = Block(
        name="AnalogFlipFlopDemo",
        state_vars=[x_in, x_reset],
        diff_vars=[d_x_in, d_x_reset],
        state_eqs=[
            (Const(1.0) - x_in) / tau_in,
            (Const(1.0) - x_reset) / tau_reset,
        ],
        parameters={
            tau_in: Const(2.5e-3),
            tau_reset: Const(7.5e-3),
        },
        mode_dict={
            y_hold: Const(0.0),
            ff_state: Const(0.0),
        },
    )

    set_expr = x_in > 0.45
    reset_expr = x_reset > 0.70
    block.procedural_logic = [
        aflipflop(x_in, set_expr, reset_expr, output=y_hold, name="analog_hold"),
        flipflop(set_expr, reset_expr, output=ff_state, name="analog_hold_state"),
    ]

    return block, {
        "x_in": x_in,
        "x_reset": x_reset,
        "y_hold": y_hold,
        "ff_state": ff_state,
    }


def create_internal_ifelse_switch_system(vf: VarFactory) -> tuple[Block, dict[str, Var]]:
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


def create_internal_select_switch_system(vf: VarFactory) -> tuple[Block, dict[str, Var]]:
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


def create_procedural_mode_switch_system(vf: VarFactory) -> tuple[Block, dict[str, Var]]:
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


def _collector_iterations_per_local_step(collector: NewtonTraceCollector) -> np.ndarray:
    per_step: dict[tuple[int, float], int] = dict()
    for record in collector.records:
        key = (int(record["step"]), round(float(record["t"]), 12))
        per_step[key] = max(per_step.get(key, 0), int(record["newton_iter"]) + 1)
    return np.asarray(list(per_step.values()), dtype=float)


def _build_benchmark_case(builder) -> tuple[GenericEmtProblem, JitSymbolicSolver, list[dict[str, object]]]:
    vf = VarFactory()
    block, _ = builder(vf)
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
    logic_snapshot = problem.sys_block._procedural_logic_to_dict()
    return problem, solver, logic_snapshot


def _run_benchmark_simulation(
    problem: GenericEmtProblem,
    solver: JitSymbolicSolver,
    logic_snapshot: list[dict[str, object]],
) -> dict[str, object]:
    problem.sys_block.procedural_logic = Block._procedural_logic_from_dict(logic_snapshot)
    updater = build_boundary_updater_from_block(problem)

    collector = NewtonTraceCollector()
    problem.set_newton_trace_collector(collector)

    t_start = time.perf_counter()
    t, y_hist, _ = solver.simulate(
        params0=problem.event_params_values.copy(),
        boundary_updater=updater,
    )
    elapsed_s = time.perf_counter() - t_start

    return {
        "elapsed_s": elapsed_s,
        "iterations_per_step": _collector_iterations_per_local_step(collector),
        "trace_records": len(collector.records),
        "t": t,
        "y_hist": y_hist,
    }


def benchmark_switch_formulation(builder, measured_runs: int = 3) -> dict[str, object]:
    problem, solver, logic_snapshot = _build_benchmark_case(builder)

    _run_benchmark_simulation(problem, solver, logic_snapshot)
    measured = [
        _run_benchmark_simulation(problem, solver, logic_snapshot)
        for _ in range(measured_runs)
    ]

    elapsed = [float(item["elapsed_s"]) for item in measured]
    mean_iterations = [float(np.mean(item["iterations_per_step"])) for item in measured]
    max_iterations = [float(np.max(item["iterations_per_step"])) for item in measured]

    return {
        "median_elapsed_s": statistics.median(elapsed),
        "mean_newton_iterations": statistics.median(mean_iterations),
        "max_newton_iterations": statistics.median(max_iterations),
        "records_per_run": [int(item["trace_records"]) for item in measured],
        "elapsed_samples": elapsed,
        "mean_iteration_samples": mean_iterations,
        "max_iteration_samples": max_iterations,
    }


class TestProceduralLogicRuntime(unittest.TestCase):

    def test_boolean_helper_exprs_eval_like_pf_logic(self) -> None:
        x = Var("x_eval")
        y = Var("y_eval")

        expr_and = bool_and(x > 0.5, y > 0.5)
        expr_or = bool_or(x > 0.5, y > 0.5)

        self.assertEqual(expr_and.eval(x_eval=1.0, y_eval=1.0), 1)
        self.assertEqual(expr_and.eval(x_eval=1.0, y_eval=0.0), 0)
        self.assertEqual(expr_or.eval(x_eval=0.0, y_eval=1.0), 1)
        self.assertEqual(expr_or.eval(x_eval=0.0, y_eval=0.0), 0)

    def test_select_and_ifelse_are_blocked_in_equation_api(self) -> None:
        x = Var("x_eval_guard")

        with self.assertRaises(RuntimeError):
            _ = select(x > 0.5, 10.0, 20.0)

        with self.assertRaises(RuntimeError):
            _ = ifelse(x > 0.5, 10.0, 20.0)

    def test_block_roundtrip_preserves_procedural_logic(self) -> None:
        vf = VarFactory()
        block, _ = create_integrator_trip_system(vf)

        restored = Block.parse(block.to_dict())

        self.assertEqual(len(restored.procedural_logic), 1)
        logic = restored.procedural_logic[0]
        self.assertIsInstance(logic, DelayedThresholdLatchLogic)
        self.assertEqual(logic.monitored_var_name, "y")
        self.assertEqual(logic.mode_var_name, "mode_int_enable")
        self.assertAlmostEqual(logic.threshold, 0.2)

    def test_boundary_updater_builds_from_block_logic(self) -> None:
        vf = VarFactory()
        block, vars_map = create_integrator_trip_system(vf)
        block.unify_blocks()
        problem = GenericEmtProblem(sys_block=block, glob_time=vf.add_var("t_glob"))

        updater = build_boundary_updater_from_block(problem)
        self.assertIsNotNone(updater)

        assert updater is not None
        self.assertEqual(len(updater.logic_entries), 1)

        params = problem.event_params_values.copy()
        x = problem.get_x0().copy()
        x[problem.get_var_idx(vars_map["y"])] = 0.25

        updater.update(0.0, x, params)
        forced_time = updater.get_next_forced_event_time(0.0, 0.01)
        self.assertIsNotNone(forced_time)
        assert forced_time is not None
        self.assertAlmostEqual(forced_time, 1.5e-3, places=7)

    def test_procedural_logic_demo_path_trips_mode_during_simulation(self) -> None:
        vf = VarFactory()
        block, vars_map = create_integrator_trip_system(vf)
        block.unify_blocks()
        problem = GenericEmtProblem(sys_block=block, glob_time=vf.add_var("t_glob"))

        solver = JitSymbolicSolver(
            problem=problem,
            t0=0.0,
            t_end=2.0e-2,
            h=1.0e-3,
            method=DynamicIntegrationMethod.DaeTrapezoidal,
            verbose=False,
        )

        updater = build_boundary_updater_from_block(problem)
        assert updater is not None
        logic = updater.logic_entries[0]

        params0 = problem.event_params_values.copy()
        _, y_hist, _ = solver.simulate(params0=params0, boundary_updater=updater)

        self.assertIsNotNone(logic.trip_applied_time)
        self.assertGreater(logic.trip_applied_time, 0.0)
        self.assertGreater(len(logic.trace_t), 0)
        self.assertGreater(np.max(y_hist[:, problem.get_var_idx(vars_map["y"])]), 0.2)

    def test_helper_based_logic_supports_and_or_picdro_flipflop_reset(self) -> None:
        vf = VarFactory()
        block, vars_map = create_boolean_operator_system(vf)
        block.unify_blocks()
        problem = GenericEmtProblem(sys_block=block, glob_time=vf.add_var("t_glob_bool"))

        updater = build_boundary_updater_from_block(problem)
        assert updater is not None

        params = problem.event_params_values.copy()
        x = problem.get_x0().copy()

        idx_x_fast = problem.get_var_idx(vars_map["x_fast"])
        idx_x_slow = problem.get_var_idx(vars_map["x_slow"])
        idx_x_mem = problem.get_var_idx(vars_map["x_mem"])

        idx_trip_fast = problem.uid2idx_event_params[vars_map["trip_fast"].uid]
        idx_trip_and = problem.uid2idx_event_params[vars_map["trip_and"].uid]
        idx_master_trip = problem.uid2idx_event_params[vars_map["master_trip"].uid]

        x[idx_x_fast] = 0.70
        x[idx_x_slow] = 0.10
        x[idx_x_mem] = 0.35

        updater.update(0.0, x, params)
        forced_time = updater.get_next_forced_event_time(0.0, 0.01)
        self.assertIsNotNone(forced_time)
        assert forced_time is not None
        self.assertAlmostEqual(forced_time, 1.0e-3, places=7)

        updater.update(forced_time, x, params)
        self.assertEqual(params[idx_trip_fast], 1.0)
        self.assertEqual(params[idx_master_trip], 1.0)
        self.assertEqual(x[idx_x_mem], 0.0)
        self.assertEqual(params[idx_trip_and], 0.0)

    def test_helper_based_logic_supports_and_branch_pickup(self) -> None:
        vf = VarFactory()
        block, vars_map = create_boolean_operator_system(vf)
        block.unify_blocks()
        problem = GenericEmtProblem(sys_block=block, glob_time=vf.add_var("t_glob_bool_2"))

        updater = build_boundary_updater_from_block(problem)
        assert updater is not None

        params = problem.event_params_values.copy()
        x = problem.get_x0().copy()

        idx_x_fast = problem.get_var_idx(vars_map["x_fast"])
        idx_x_slow = problem.get_var_idx(vars_map["x_slow"])

        idx_trip_fast = problem.uid2idx_event_params[vars_map["trip_fast"].uid]
        idx_trip_and = problem.uid2idx_event_params[vars_map["trip_and"].uid]
        idx_master_trip = problem.uid2idx_event_params[vars_map["master_trip"].uid]

        x[idx_x_fast] = 0.55
        x[idx_x_slow] = 0.40

        updater.update(0.0, x, params)
        forced_time = updater.get_next_forced_event_time(0.0, 0.01)
        self.assertIsNotNone(forced_time)
        assert forced_time is not None
        self.assertAlmostEqual(forced_time, 2.0e-3, places=7)

        updater.update(forced_time, x, params)
        self.assertEqual(params[idx_trip_fast], 0.0)
        self.assertEqual(params[idx_trip_and], 1.0)
        self.assertEqual(params[idx_master_trip], 1.0)

    def test_aflipflop_holds_analog_value_until_reset(self) -> None:
        vf = VarFactory()
        block, vars_map = create_analog_flipflop_system(vf)
        block.unify_blocks()
        problem = GenericEmtProblem(sys_block=block, glob_time=vf.add_var("t_glob_af"))

        updater = build_boundary_updater_from_block(problem)
        assert updater is not None

        params = problem.event_params_values.copy()
        x = problem.get_x0().copy()

        idx_x_in = problem.get_var_idx(vars_map["x_in"])
        idx_x_reset = problem.get_var_idx(vars_map["x_reset"])
        idx_y_hold = problem.uid2idx_event_params[vars_map["y_hold"].uid]
        idx_ff_state = problem.uid2idx_event_params[vars_map["ff_state"].uid]

        x[idx_x_in] = 0.30
        x[idx_x_reset] = 0.10
        updater.update(0.0, x, params)
        self.assertAlmostEqual(params[idx_y_hold], 0.30)
        self.assertEqual(params[idx_ff_state], 0.0)

        x[idx_x_in] = 0.55
        updater.update(0.001, x, params)
        self.assertAlmostEqual(params[idx_y_hold], 0.55)
        self.assertEqual(params[idx_ff_state], 1.0)

        x[idx_x_in] = 0.90
        updater.update(0.002, x, params)
        self.assertAlmostEqual(params[idx_y_hold], 0.55)
        self.assertEqual(params[idx_ff_state], 1.0)

        x[idx_x_in] = 0.20
        x[idx_x_reset] = 0.80
        updater.update(0.003, x, params)
        self.assertAlmostEqual(params[idx_y_hold], 0.20)
        self.assertEqual(params[idx_ff_state], 0.0)


class TestConditionalPlacementBenchmark(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.internal_ifelse_stats = benchmark_switch_formulation(create_internal_ifelse_switch_system)
        cls.internal_select_stats = benchmark_switch_formulation(create_internal_select_switch_system)
        cls.procedural_stats = benchmark_switch_formulation(create_procedural_mode_switch_system)

    def test_procedural_switch_reduces_newton_iterations(self) -> None:
        procedural_mean = float(self.procedural_stats["mean_newton_iterations"])
        procedural_max = float(self.procedural_stats["max_newton_iterations"])

        for label, stats in {
            "ifelse_internal": self.internal_ifelse_stats,
            "select_internal": self.internal_select_stats,
        }.items():
            internal_mean = float(stats["mean_newton_iterations"])
            internal_max = float(stats["max_newton_iterations"])

            self.assertGreater(
                internal_mean,
                4.0 * procedural_mean,
                msg=f"Expected embedded {label} to require much more Newton work: internal={stats}, procedural={self.procedural_stats}",
            )
            self.assertGreaterEqual(
                internal_max,
                10.0,
                msg=f"Expected embedded {label} to push Newton near the iteration cap: {stats}",
            )

        self.assertLessEqual(
            procedural_max,
            2.0,
            msg=f"Expected procedural mode switch to keep Newton nearly linear per step: {self.procedural_stats}",
        )

    def test_procedural_switch_reduces_runtime_after_warmup(self) -> None:
        procedural_elapsed = float(self.procedural_stats["median_elapsed_s"])

        for label, stats in {
            "ifelse_internal": self.internal_ifelse_stats,
            "select_internal": self.internal_select_stats,
        }.items():
            internal_elapsed = float(stats["median_elapsed_s"])

            self.assertLess(
                procedural_elapsed,
                internal_elapsed,
                msg=f"Expected procedural mode switch to be faster after warm-up than {label}: internal={stats}, procedural={self.procedural_stats}",
            )

    def test_internal_select_and_ifelse_have_same_benchmark_profile(self) -> None:
        self.assertAlmostEqual(
            float(self.internal_ifelse_stats["mean_newton_iterations"]),
            float(self.internal_select_stats["mean_newton_iterations"]),
            places=9,
        )
        self.assertAlmostEqual(
            float(self.internal_ifelse_stats["max_newton_iterations"]),
            float(self.internal_select_stats["max_newton_iterations"]),
            places=9,
        )


if __name__ == "__main__":
    unittest.main()
