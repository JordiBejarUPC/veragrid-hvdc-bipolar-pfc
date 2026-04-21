import unittest
from typing import Dict, List, Optional, Tuple

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper, JitSymbolicSolver
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    """Minimal generic EMT problem used for unit testing."""

    __slots__ = []


class ThresholdDelayTripWrapper(BoundaryUpdateWrapper):
    """
    Protection chain that latches a trip after a threshold pickup plus a delay.

    The wrapper drives a retained runtime mode parameter stored in ``mode_dict``.
    When the monitored state exceeds the threshold, the protection starts a timer.
    Once the delay expires, the wrapper forces the solver to align an EMT substep
    exactly at the trip time and then sets the mode to zero.
    """

    __slots__ = [
        "mode_idx",
        "monitored_idx",
        "threshold",
        "delay",
        "pickup_time",
        "pending_trip_time",
        "tripped",
        "trip_applied_time",
        "trip_applied_solver_time",
        "last_t_prev",
    ]

    def __init__(
        self,
        problem: EmtProblemTemplate,
        monitored_var: Var,
        mode_var: Var,
        threshold: float,
        delay: float,
    ) -> None:
        self.mode_idx: int = problem.uid2idx_event_params[mode_var.uid]
        self.monitored_idx: int = problem.get_var_idx(monitored_var)
        self.threshold: float = float(threshold)
        self.delay: float = float(delay)

        self.pickup_time: Optional[float] = None
        self.pending_trip_time: Optional[float] = None
        self.tripped: bool = False
        self.trip_applied_time: Optional[float] = None
        self.trip_applied_solver_time: Optional[float] = None
        self.last_t_prev: Optional[float] = None

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return a forced-alignment time if the pending trip lies inside the current EMT step.
        """
        self.last_t_prev = float(t_prev)

        if self.pending_trip_time is None:
            return None

        if t_prev < self.pending_trip_time <= t_target:
            return float(self.pending_trip_time)

        return None

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Update the retained mode parameter from the protection logic.

        Notes
        -----
        ``x`` is the previously accepted state vector. Therefore, the physical
        sample time associated with ``x`` is the last accepted time ``t_prev``,
        not the target time ``t`` passed by the solver.
        """
        if self.tripped:
            params[self.mode_idx] = 0.0
            return

        sample_time: float = float(self.last_t_prev if self.last_t_prev is not None else t)
        measured_value: float = float(x[self.monitored_idx])

        if measured_value >= self.threshold:
            if self.pickup_time is None:
                self.pickup_time = sample_time
                self.pending_trip_time = sample_time + self.delay
        else:
            self.pickup_time = None
            self.pending_trip_time = None

        if self.pending_trip_time is not None and t >= (self.pending_trip_time - 1e-15):
            params[self.mode_idx] = 0.0
            self.tripped = True
            self.trip_applied_time = float(self.pending_trip_time)
            self.trip_applied_solver_time = float(t)
            self.pending_trip_time = None
        else:
            params[self.mode_idx] = 1.0


def create_integrator_trip_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    """
    Build a compact dynamic system to test retained runtime modes.

    Dynamics
    --------
    x_i_dot = mode_int_enable * k_i * (ref - y)
    y_dot   = (x_i - y) / tau

    The protection acts on ``mode_int_enable``. Before the trip, the integrator is
    active. After the trip, the integrator derivative becomes exactly zero and the
    state ``x_i`` must remain frozen.
    """
    x_i: Var = vf.add_var("x_i")
    y: Var = vf.add_var("y")

    d_x_i: Var = vf.add_diff_var(name="d_x_i", base_var=x_i)
    d_y: Var = vf.add_diff_var(name="d_y", base_var=y)

    mode_int_enable: Var = vf.add_var("mode_int_enable")

    ref: Var = vf.add_var("ref")
    k_i: Var = vf.add_var("k_i")
    tau: Var = vf.add_var("tau")

    state_vars: List[Var] = [x_i, y]
    diff_vars: List[Var] = [d_x_i, d_y]
    state_eqs: List[Expr] = [
        mode_int_enable * k_i * (ref - y),
        (x_i - y) / tau,
    ]

    parameters: Dict[Var, Const] = {
        ref: Const(1.0),
        k_i: Const(200.0),
        tau: Const(2.0e-3),
    }

    mode_dict: Dict[Var, Const] = {
        mode_int_enable: Const(1.0),
    }

    block = Block(
        name="ModeProtectionIntegratorTest",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters=parameters,
        mode_dict=mode_dict,
    )

    return block, {
        "x_i": x_i,
        "y": y,
        "d_x_i": d_x_i,
        "mode_int_enable": mode_int_enable,
    }

def create_antiwindup_trip_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    """
    Build a compact dynamic system to test a retained mode that disables an
    anti-windup-like feedback branch.

    Dynamics
    --------
    x_i_dot   = k_i * (ref - y) - mode_aw_enable * k_aw * (x_i - u_act)
    u_act_dot = (x_i - u_act) / tau_act
    y_dot     = (u_act - y) / tau_y

    Interpretation
    --------------
    - ``x_i`` is the controller integrator state.
    - ``u_act`` is a delayed actuator / limited actuator proxy.
    - ``(x_i - u_act)`` plays the role of the back-calculation mismatch.
    - ``mode_aw_enable`` enables/disables the anti-windup branch.

    Before the trip, the anti-windup branch damps the integrator derivative.
    After the trip, the protection sets ``mode_aw_enable = 0`` and the
    anti-windup term disappears, but the integrator remains dynamic.
    """
    x_i: Var = vf.add_var("x_i_aw")
    u_act: Var = vf.add_var("u_act_aw")
    y: Var = vf.add_var("y_aw")

    d_x_i: Var = vf.add_diff_var(name="d_x_i_aw", base_var=x_i)
    d_u_act: Var = vf.add_diff_var(name="d_u_act_aw", base_var=u_act)
    d_y: Var = vf.add_diff_var(name="d_y_aw", base_var=y)

    mode_aw_enable: Var = vf.add_var("mode_aw_enable")

    ref: Var = vf.add_var("ref_aw")
    k_i: Var = vf.add_var("k_i_aw")
    k_aw: Var = vf.add_var("k_aw")
    tau_act: Var = vf.add_var("tau_act")
    tau_y: Var = vf.add_var("tau_y")

    state_vars: List[Var] = [x_i, u_act, y]
    diff_vars: List[Var] = [d_x_i, d_u_act, d_y]
    state_eqs: List[Expr] = [
        k_i * (ref - y) - mode_aw_enable * k_aw * (x_i - u_act),
        (x_i - u_act) / tau_act,
        (u_act - y) / tau_y,
    ]

    parameters: Dict[Var, Const] = {
        ref: Const(1.0),
        k_i: Const(200.0),
        k_aw: Const(150.0),
        tau_act: Const(4.0e-3),
        tau_y: Const(2.0e-3),
    }

    mode_dict: Dict[Var, Const] = {
        mode_aw_enable: Const(1.0),
    }

    block = Block(
        name="ModeProtectionAntiWindupTest",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters=parameters,
        mode_dict=mode_dict,
    )

    return block, {
        "x_i": x_i,
        "u_act": u_act,
        "y": y,
        "d_x_i": d_x_i,
        "d_u_act": d_u_act,
        "d_y": d_y,
        "mode_aw_enable": mode_aw_enable,
    }


class TestRetainedModesWithProtectionChain(unittest.TestCase):
    """Validate retained modes with a simple dynamic protection chain."""

    def test_protection_chain_freezes_integrator_with_exact_substep_alignment(self) -> None:
        """
        The retained mode parameter must freeze the integrator after the protection trips.

        This test validates four behaviours:
        1. ``mode_dict`` parameters are classified as retained runtime modes.
        2. The protection chain can latch a future trip time.
        3. The solver can align a substep exactly at a non-grid trip time.
        4. After the trip, the integrator derivative is zero and the integrator state is frozen.
        """
        vf = VarFactory()
        block, vars_map = create_integrator_trip_system(vf=vf)
        block.unify_blocks()

        glob_time: Var = vf.add_var("t_glob")
        problem = GenericEmtProblem(sys_block=block, glob_time=glob_time)

        mode_params: List[Var] = problem.get_runtime_mode_parameters()
        self.assertEqual(len(mode_params), 1)
        self.assertEqual(mode_params[0].uid, vars_map["mode_int_enable"].uid)

        dt: float = 1.0e-3
        solver = JitSymbolicSolver(
            problem=problem,
            t0=0.0,
            t_end=2.0e-2,
            h=dt,
            method=DynamicIntegrationMethod.DaeTrapezoidal,
            verbose=False,
        )

        protection = ThresholdDelayTripWrapper(
            problem=problem,
            monitored_var=vars_map["y"],
            mode_var=vars_map["mode_int_enable"],
            threshold=0.20,
            delay=1.5e-3,
        )

        # Important: runtime parameters must start from the initialized mode/event vector,
        # not from an all-zero array.
        params0 = problem.event_params_values.copy()

        t, y_hist, dy_hist = solver.simulate(params0=params0, boundary_updater=protection)

        self.assertTrue(protection.tripped)
        self.assertIsNotNone(protection.trip_applied_time)
        self.assertIsNotNone(protection.trip_applied_solver_time)

        trip_time: float = float(protection.trip_applied_time)
        trip_solver_time: float = float(protection.trip_applied_solver_time)

        # The trip delay is intentionally off the macro-step grid to force EMT substep splitting.
        self.assertGreater(abs((trip_time / dt) - round(trip_time / dt)), 1.0e-9)
        self.assertAlmostEqual(trip_time, trip_solver_time, places=12)

        idx_x_i: int = problem.get_var_idx(vars_map["x_i"])
        idx_y: int = problem.get_var_idx(vars_map["y"])
        idx_d_x_i: int = problem.get_diff_var_idx(vars_map["d_x_i"])

        x_i_hist: np.ndarray = y_hist[:, idx_x_i]
        y_hist_only: np.ndarray = y_hist[:, idx_y]
        d_x_i_hist: np.ndarray = dy_hist[:, idx_d_x_i]

        pre_mask = t <= (trip_time - dt)
        post_mask = t >= (trip_time + dt)

        self.assertTrue(np.any(pre_mask))
        self.assertTrue(np.any(post_mask))

        # Before the trip, the integrator must be active.
        self.assertGreater(np.max(np.abs(d_x_i_hist[pre_mask])), 1.0e-6)

        # After the trip, the retained mode must freeze the integrator exactly.
        self.assertLess(np.max(np.abs(d_x_i_hist[post_mask])), 1.0e-10)
        self.assertLess(np.max(np.abs(np.diff(x_i_hist[post_mask]))), 1.0e-10)

        # The monitored state should have actually crossed the pickup threshold before the trip.
        self.assertGreater(np.max(y_hist_only[pre_mask]), protection.threshold)

    def test_protection_chain_disables_antiwindup_branch_with_exact_substep_alignment(self) -> None:
        """
        The retained mode parameter must disable the anti-windup branch after the protection trips.

        This test validates:
        1. ``mode_dict`` parameters are classified as retained runtime modes.
        2. The protection can latch a future trip time and force exact EMT substep alignment.
        3. Before the trip, the anti-windup term actively modifies the integrator derivative.
        4. After the trip, the anti-windup term disappears, but the integrator remains dynamic.
        """
        vf = VarFactory()
        block, vars_map = create_antiwindup_trip_system(vf=vf)
        block.unify_blocks()

        glob_time: Var = vf.add_var("t_glob")
        problem = GenericEmtProblem(sys_block=block, glob_time=glob_time)

        mode_params: List[Var] = problem.get_runtime_mode_parameters()
        self.assertEqual(len(mode_params), 1)
        self.assertEqual(mode_params[0].uid, vars_map["mode_aw_enable"].uid)

        dt: float = 1.0e-3
        solver = JitSymbolicSolver(
            problem=problem,
            t0=0.0,
            t_end=3.0e-2,
            h=dt,
            method=DynamicIntegrationMethod.DaeTrapezoidal,
            verbose=False,
        )

        protection = ThresholdDelayTripWrapper(
            problem=problem,
            monitored_var=vars_map["y"],
            mode_var=vars_map["mode_aw_enable"],
            threshold=0.12,
            delay=1.5e-3,
        )

        # Important: runtime parameters must start from the initialized mode/event vector,
        # not from an all-zero array.
        params0 = problem.event_params_values.copy()

        t, y_hist, dy_hist = solver.simulate(params0=params0, boundary_updater=protection)

        self.assertTrue(protection.tripped)
        self.assertIsNotNone(protection.trip_applied_time)
        self.assertIsNotNone(protection.trip_applied_solver_time)

        trip_time: float = float(protection.trip_applied_time)
        trip_solver_time: float = float(protection.trip_applied_solver_time)

        # The trip delay is intentionally off the macro-step grid to force EMT substep splitting.
        self.assertGreater(abs((trip_time / dt) - round(trip_time / dt)), 1.0e-9)
        self.assertAlmostEqual(trip_time, trip_solver_time, places=12)

        idx_x_i: int = problem.get_var_idx(vars_map["x_i"])
        idx_u_act: int = problem.get_var_idx(vars_map["u_act"])
        idx_y: int = problem.get_var_idx(vars_map["y"])
        idx_d_x_i: int = problem.get_diff_var_idx(vars_map["d_x_i"])

        x_i_hist: np.ndarray = y_hist[:, idx_x_i]
        u_act_hist: np.ndarray = y_hist[:, idx_u_act]
        y_hist_only: np.ndarray = y_hist[:, idx_y]
        d_x_i_hist: np.ndarray = dy_hist[:, idx_d_x_i]

        pre_idx = np.where(t <= (trip_time - dt))[0]
        post_idx = np.where(t >= (trip_time + dt))[0]

        self.assertGreater(pre_idx.size, 0)
        self.assertGreater(post_idx.size, 0)

        i_pre: int = int(pre_idx[-1])
        i_post: int = int(post_idx[0])

        ref: float = 1.0
        k_i: float = 200.0
        k_aw: float = 150.0

        # Before the trip, the anti-windup branch must be active.
        aw_feedback_pre: float = k_aw * (x_i_hist[i_pre] - u_act_hist[i_pre])
        expected_pre: float = k_i * (ref - y_hist_only[i_pre]) - aw_feedback_pre

        # After the trip, the anti-windup term must disappear, but the integrator must remain active.
        expected_post: float = k_i * (ref - y_hist_only[i_post])

        self.assertGreater(abs(aw_feedback_pre), 1.0e-6)
        self.assertAlmostEqual(d_x_i_hist[i_pre], expected_pre, places=6)
        self.assertAlmostEqual(d_x_i_hist[i_post], expected_post, places=6)

        # The integrator is still dynamic after the trip: it must not freeze.
        self.assertGreater(np.max(np.abs(d_x_i_hist[post_idx])), 1.0e-6)
        self.assertGreater(np.max(np.abs(np.diff(x_i_hist[post_idx]))), 1.0e-8)

        # Disabling anti-windup should increase the integrator derivative.
        self.assertGreater(d_x_i_hist[i_post], d_x_i_hist[i_pre] + 1.0)

        # The monitored state should have crossed the pickup threshold before the trip.
        self.assertGreater(np.max(y_hist_only[pre_idx]), protection.threshold)


if __name__ == "__main__":
    unittest.main()