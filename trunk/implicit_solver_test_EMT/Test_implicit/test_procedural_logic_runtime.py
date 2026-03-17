import unittest

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Utils.procedural_logic import (
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
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = []


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
            ifelse(master_trip > 0.5, 0.0, k_mem * (x_fast - x_mem)),
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


class TestProceduralLogicRuntime(unittest.TestCase):

    def test_boolean_helper_exprs_eval_like_pf_logic(self) -> None:
        x = Var("x_eval")
        y = Var("y_eval")

        expr_and = bool_and(x > 0.5, y > 0.5)
        expr_or = bool_or(x > 0.5, y > 0.5)
        expr_select = select(x > 0.5, 10.0, 20.0)
        expr_ifelse = ifelse(y > 0.5, x + 1.0, x - 1.0)

        self.assertEqual(expr_and.eval(x_eval=1.0, y_eval=1.0), 1)
        self.assertEqual(expr_and.eval(x_eval=1.0, y_eval=0.0), 0)
        self.assertEqual(expr_or.eval(x_eval=0.0, y_eval=1.0), 1)
        self.assertEqual(expr_or.eval(x_eval=0.0, y_eval=0.0), 0)
        self.assertEqual(expr_select.eval(x_eval=1.0, y_eval=0.0), 10.0)
        self.assertEqual(expr_select.eval(x_eval=0.0, y_eval=0.0), 20.0)
        self.assertEqual(expr_ifelse.eval(x_eval=2.0, y_eval=1.0), 3.0)
        self.assertEqual(expr_ifelse.eval(x_eval=2.0, y_eval=0.0), 1.0)

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


if __name__ == "__main__":
    unittest.main()
