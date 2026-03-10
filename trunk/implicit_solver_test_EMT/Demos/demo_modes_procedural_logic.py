import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Tuple

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper, JitSymbolicSolver
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    """Minimal generic EMT problem used for demo purposes."""

    __slots__ = []


class RichProtectionChainWrapper(BoundaryUpdateWrapper):
    """
    Rich protection chain with comparator, timer, latch, retained mode, and optional reset.

    Logic
    -----
    1. Comparator:
       comparator = measured_value >= threshold

    2. Timer:
       When the comparator rises and there is no active timer, a delayed trip time is scheduled.

    3. Latch:
       When the delayed trip time is reached, the protection latches and the controlled mode is set to 0.

    4. Optional reset:
       If ``reset_delay`` is not None, a reset is scheduled at:
           reset_time = trip_time + reset_delay
       When reset happens, the latch is cleared and the mode returns to 1.

    Notes
    -----
    - The wrapper stores internal traces so the logical chain can be plotted afterwards.
    - The solver can force exact substep alignment at both trip and reset times.
    """

    __slots__ = [
        "mode_idx",
        "monitored_idx",
        "threshold",
        "delay",
        "reset_delay",
        "pickup_time",
        "pending_trip_time",
        "pending_reset_time",
        "tripped",
        "trip_applied_time",
        "trip_applied_solver_time",
        "reset_applied_time",
        "reset_applied_solver_time",
        "last_t_prev",
        "trace_t",
        "trace_measure",
        "trace_comparator",
        "trace_timer_armed",
        "trace_latched",
        "trace_mode",
    ]

    def __init__(
        self,
        problem: EmtProblemTemplate,
        monitored_var: Var,
        mode_var: Var,
        threshold: float,
        delay: float,
        reset_delay: Optional[float] = None,
    ) -> None:
        self.mode_idx: int = problem.uid2idx_event_params[mode_var.uid]
        self.monitored_idx: int = problem.get_var_idx(monitored_var)
        self.threshold: float = float(threshold)
        self.delay: float = float(delay)
        self.reset_delay: Optional[float] = None if reset_delay is None else float(reset_delay)

        self.pickup_time: Optional[float] = None
        self.pending_trip_time: Optional[float] = None
        self.pending_reset_time: Optional[float] = None

        self.tripped: bool = False
        self.trip_applied_time: Optional[float] = None
        self.trip_applied_solver_time: Optional[float] = None
        self.reset_applied_time: Optional[float] = None
        self.reset_applied_solver_time: Optional[float] = None

        self.last_t_prev: Optional[float] = None

        self.trace_t: List[float] = []
        self.trace_measure: List[float] = []
        self.trace_comparator: List[float] = []
        self.trace_timer_armed: List[float] = []
        self.trace_latched: List[float] = []
        self.trace_mode: List[float] = []

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return a forced-alignment time if a pending trip or reset lies inside the current EMT step.
        """
        self.last_t_prev = float(t_prev)

        candidate_times: List[float] = []

        if self.pending_trip_time is not None and t_prev < self.pending_trip_time <= t_target:
            candidate_times.append(float(self.pending_trip_time))

        if self.pending_reset_time is not None and t_prev < self.pending_reset_time <= t_target:
            candidate_times.append(float(self.pending_reset_time))

        if len(candidate_times) == 0:
            return None

        return min(candidate_times)

    def _append_trace_point(
            self,
            trace_time: float,
            measured_value: float,
            comparator: float,
            timer_armed: float,
            latched: float,
            mode_value: float,
    ) -> None:
        """
        Append one logic sample to the plotting traces.
        """
        self.trace_t.append(float(trace_time))
        self.trace_measure.append(float(measured_value))
        self.trace_comparator.append(float(comparator))
        self.trace_timer_armed.append(float(timer_armed))
        self.trace_latched.append(float(latched))
        self.trace_mode.append(float(mode_value))

    def _record_sample_trace(
            self,
            sample_time: float,
            measured_value: float,
            params: np.ndarray,
    ) -> None:
        """
        Record the logical state at the physical sample time associated with x.
        """
        comparator: float = 1.0 if measured_value >= self.threshold else 0.0
        timer_armed: float = 1.0 if self.pending_trip_time is not None else 0.0
        latched: float = 1.0 if self.tripped else 0.0
        mode_value: float = float(params[self.mode_idx])

        self._append_trace_point(
            trace_time=sample_time,
            measured_value=measured_value,
            comparator=comparator,
            timer_armed=timer_armed,
            latched=latched,
            mode_value=mode_value,
        )

    def get_trace_arrays(
        self,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Return recorded logic traces as numpy arrays.
        """
        return (
            np.asarray(self.trace_t, dtype=float),
            np.asarray(self.trace_measure, dtype=float),
            np.asarray(self.trace_comparator, dtype=float),
            np.asarray(self.trace_timer_armed, dtype=float),
            np.asarray(self.trace_latched, dtype=float),
            np.asarray(self.trace_mode, dtype=float),
        )

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """
        Update the protection chain and the retained runtime mode.

        Important
        ---------
        - ``x`` corresponds to the previously accepted state, i.e. to ``sample_time``.
        - Therefore comparator/timer traces must be recorded at ``sample_time``.
        - Trip/reset actions, however, must be recorded at the actual event time ``t``.
        """
        tol: float = 1.0e-15
        sample_time: float = float(self.last_t_prev if self.last_t_prev is not None else t)
        measured_value: float = float(x[self.monitored_idx])
        comparator_on: bool = measured_value >= self.threshold
        comparator_value: float = 1.0 if comparator_on else 0.0

        # Case 1: protection already latched
        if self.tripped:
            params[self.mode_idx] = 0.0

            # Optional reset event
            if self.pending_reset_time is not None and t >= (self.pending_reset_time - tol):
                self.tripped = False
                self.reset_applied_time = float(self.pending_reset_time)
                self.reset_applied_solver_time = float(t)

                self.pickup_time = None
                self.pending_trip_time = None
                self.pending_reset_time = None

                params[self.mode_idx] = 1.0

                # Record the reset exactly at the event time
                self._append_trace_point(
                    trace_time=t,
                    measured_value=measured_value,
                    comparator=comparator_value,
                    timer_armed=0.0,
                    latched=0.0,
                    mode_value=1.0,
                )
                return

            # Normal latched evolution: record at physical sample time
            self._record_sample_trace(
                sample_time=sample_time,
                measured_value=measured_value,
                params=params,
            )
            return

        # Case 2: not latched yet, evaluate comparator and timer
        if comparator_on:
            if self.pickup_time is None:
                self.pickup_time = sample_time
                self.pending_trip_time = sample_time + self.delay
        else:
            self.pickup_time = None
            self.pending_trip_time = None

        # Apply trip if the delayed trip time is reached
        if self.pending_trip_time is not None and t >= (self.pending_trip_time - tol):
            self.tripped = True
            self.trip_applied_time = float(self.pending_trip_time)
            self.trip_applied_solver_time = float(t)
            params[self.mode_idx] = 0.0

            if self.reset_delay is not None:
                self.pending_reset_time = self.trip_applied_time + self.reset_delay

            self.pending_trip_time = None

            # Record the trip exactly at the event time
            self._append_trace_point(
                trace_time=t,
                measured_value=measured_value,
                comparator=comparator_value,
                timer_armed=0.0,
                latched=1.0,
                mode_value=0.0,
            )
            return

        # Normal non-tripped case
        params[self.mode_idx] = 1.0
        self._record_sample_trace(
            sample_time=sample_time,
            measured_value=measured_value,
            params=params,
        )


def create_integrator_trip_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    """
    Demo system where the protection freezes the integrator.

    Dynamics
    --------
    x_i_dot = mode_int_enable * k_i * (ref - y)
    y_dot   = (x_i - y) / tau
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
        name="ModeProtectionIntegratorDemo",
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
        "d_y": d_y,
        "mode_var": mode_int_enable,
    }


def create_antiwindup_trip_system(vf: VarFactory) -> Tuple[Block, Dict[str, Var]]:
    """
    Demo system where the protection disables an anti-windup branch.

    Dynamics
    --------
    x_i_dot   = k_i * (ref - y) - mode_aw_enable * k_aw * (x_i - u_act)
    u_act_dot = (x_i - u_act) / tau_act
    y_dot     = (u_act - y) / tau_y
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
        name="ModeProtectionAntiWindupDemo",
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
        "mode_var": mode_aw_enable,
    }


def run_case(
    builder,
    threshold: float,
    delay: float,
    t_end: float,
    dt: float,
    reset_delay: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, EmtProblemTemplate, Dict[str, Var], RichProtectionChainWrapper]:
    """
    Build, simulate, and return a demo case.
    """
    vf = VarFactory()
    block, vars_map = builder(vf=vf)
    block.unify_blocks()

    glob_time: Var = vf.add_var("t_glob")
    problem = GenericEmtProblem(sys_block=block, glob_time=glob_time)

    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=t_end,
        h=dt,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )

    protection = RichProtectionChainWrapper(
        problem=problem,
        monitored_var=vars_map["y"],
        mode_var=vars_map["mode_var"],
        threshold=threshold,
        delay=delay,
        reset_delay=reset_delay,
    )

    params0 = problem.event_params_values.copy()
    t, y_hist, dy_hist = solver.simulate(params0=params0, boundary_updater=protection)

    return t, y_hist, dy_hist, problem, vars_map, protection


def add_event_lines(ax: plt.Axes, protection: RichProtectionChainWrapper) -> None:
    """
    Add vertical lines for pickup, trip, and optional reset.
    """
    if protection.pickup_time is not None:
        ax.axvline(
            protection.pickup_time,
            linestyle=":",
            linewidth=1.5,
            label=f"pickup = {protection.pickup_time:.6f} s",
        )

    if protection.trip_applied_time is not None:
        ax.axvline(
            protection.trip_applied_time,
            linestyle="--",
            linewidth=1.5,
            label=f"trip = {protection.trip_applied_time:.6f} s",
        )

    if protection.reset_applied_time is not None:
        ax.axvline(
            protection.reset_applied_time,
            linestyle="-.",
            linewidth=1.5,
            label=f"reset = {protection.reset_applied_time:.6f} s",
        )


def plot_logic_panel(
    ax: plt.Axes,
    protection: RichProtectionChainWrapper,
) -> None:
    """
    Plot internal logic signals of the protection chain.
    """
    logic_t, _, comparator, timer_armed, latched, mode_value = protection.get_trace_arrays()

    ax.step(logic_t, comparator + 0.0, where="post", label="comparator")
    ax.step(logic_t, timer_armed + 1.2, where="post", label="timer armed")
    ax.step(logic_t, latched + 2.4, where="post", label="latch")
    ax.step(logic_t, mode_value + 3.6, where="post", label="mode")

    add_event_lines(ax=ax, protection=protection)

    ax.set_yticks([0.5, 1.7, 2.9, 4.1])
    ax.set_yticklabels(["cmp", "timer", "latch", "mode"])
    ax.set_ylim(-0.2, 4.8)
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Logic")
    ax.grid(True)
    ax.legend(loc="upper right")


def plot_integrator_case(
    t: np.ndarray,
    y_hist: np.ndarray,
    dy_hist: np.ndarray,
    problem: EmtProblemTemplate,
    vars_map: Dict[str, Var],
    protection: RichProtectionChainWrapper,
) -> None:
    """
    Plot the integrator-freeze demo plus its internal logic.
    """
    idx_x_i: int = problem.get_var_idx(vars_map["x_i"])
    idx_y: int = problem.get_var_idx(vars_map["y"])
    idx_d_x_i: int = problem.get_diff_var_idx(vars_map["d_x_i"])

    fig, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(11, 8),
        sharex=True,
        height_ratios=[3.0, 1.6],
    )

    ax_dyn = axes[0]
    ax_logic = axes[1]

    ax_dyn.plot(t, y_hist[:, idx_x_i], label="x_i")
    ax_dyn.plot(t, y_hist[:, idx_y], label="y")
    ax_dyn.plot(t, dy_hist[:, idx_d_x_i], label="d_x_i")
    ax_dyn.axhline(protection.threshold, linestyle=":", linewidth=1.2, label=f"threshold = {protection.threshold:.3f}")

    add_event_lines(ax=ax_dyn, protection=protection)

    ax_dyn.set_title("Demo 1: Protection freezes integrator")
    ax_dyn.set_ylabel("Value")
    ax_dyn.grid(True)
    ax_dyn.legend(loc="upper right")

    plot_logic_panel(ax=ax_logic, protection=protection)

    fig.tight_layout()


def plot_antiwindup_case(
    t: np.ndarray,
    y_hist: np.ndarray,
    dy_hist: np.ndarray,
    problem: EmtProblemTemplate,
    vars_map: Dict[str, Var],
    protection: RichProtectionChainWrapper,
) -> None:
    """
    Plot the anti-windup-disable demo plus its internal logic.
    """
    idx_x_i: int = problem.get_var_idx(vars_map["x_i"])
    idx_u_act: int = problem.get_var_idx(vars_map["u_act"])
    idx_y: int = problem.get_var_idx(vars_map["y"])
    idx_d_x_i: int = problem.get_diff_var_idx(vars_map["d_x_i"])

    fig, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(11, 8),
        sharex=True,
        height_ratios=[3.0, 1.6],
    )

    ax_dyn = axes[0]
    ax_logic = axes[1]

    ax_dyn.plot(t, y_hist[:, idx_x_i], label="x_i")
    ax_dyn.plot(t, y_hist[:, idx_u_act], label="u_act")
    ax_dyn.plot(t, y_hist[:, idx_y], label="y")
    ax_dyn.plot(t, dy_hist[:, idx_d_x_i], label="d_x_i")
    ax_dyn.axhline(protection.threshold, linestyle=":", linewidth=1.2, label=f"threshold = {protection.threshold:.3f}")

    add_event_lines(ax=ax_dyn, protection=protection)

    ax_dyn.set_title("Demo 2: Protection disables anti-windup branch")
    ax_dyn.set_ylabel("Value")
    ax_dyn.grid(True)
    ax_dyn.legend(loc="upper right")

    plot_logic_panel(ax=ax_logic, protection=protection)

    fig.tight_layout()


def print_case_summary(name: str, protection: RichProtectionChainWrapper) -> None:
    """
    Print a compact summary of the protection sequence.
    """
    print(f"=== {name} ===")
    print(f"pickup_time:             {protection.pickup_time}")
    print(f"trip_applied_time:       {protection.trip_applied_time}")
    print(f"trip_solver_time:        {protection.trip_applied_solver_time}")
    print(f"reset_applied_time:      {protection.reset_applied_time}")
    print(f"reset_solver_time:       {protection.reset_applied_solver_time}")
    print(f"final_latched_state:     {protection.tripped}")
    print("")


def main() -> None:
    """
    Run the two demos.

    Notes
    -----
    To demonstrate the optional reset, you can set for example:
        reset_delay = 8.0e-3
    in one of the calls below.
    """
    dt: float = 1.0e-3

    t1, y1, dy1, problem1, vars1, prot1 = run_case(
        builder=create_integrator_trip_system,
        threshold=0.20,
        delay=1.5e-3,
        t_end=2.0e-2,
        dt=dt,
        reset_delay=None,
    )

    t2, y2, dy2, problem2, vars2, prot2 = run_case(
        builder=create_antiwindup_trip_system,
        threshold=0.12,
        delay=1.5e-3,
        t_end=3.0e-2,
        dt=dt,
        reset_delay=None,
    )

    print_case_summary(name="Demo 1: Integrator freeze", protection=prot1)
    print_case_summary(name="Demo 2: Anti-windup disable", protection=prot2)

    plot_integrator_case(t1, y1, dy1, problem1, vars1, prot1)
    plot_antiwindup_case(t2, y2, dy2, problem2, vars2, prot2)
    plt.show()


if __name__ == "__main__":
    main()