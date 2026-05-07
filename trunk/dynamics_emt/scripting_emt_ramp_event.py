# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicIntegrationMethod
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory


class RampEventDemoProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the ramp-event scripting demo.
    """

    __slots__ = ["grid"]

    def __init__(self, grid: MultiCircuit, sys_block: Block, glob_time: Var) -> None:
        self.grid = grid
        static_parameter_values_mapping: Dict[Var, Const] = dict(sys_block.parameters)
        super().__init__(
            sys_block=sys_block,
            glob_time=glob_time,
            static_parameter_values_mapping=static_parameter_values_mapping,
        )


def build_ramp_event_demo_problem() -> tuple[RampEventDemoProblem, EmtEventsGroup, Var]:
    """
    Build one minimal EMT problem driven by a ramp event.

    :return: Problem, events group, and tracked runtime parameter.
    """
    vf = VarFactory()
    glob_time = vf.add_var("t_glob_ramp_demo")
    u_input = vf.add_var("u_input_ramp_demo")
    x_state = vf.add_var("x_state_ramp_demo")
    dx_state = vf.add_diff_var(name="dx_state_ramp_demo", base_var=x_state)
    y_output = vf.add_var("y_output_ramp_demo")

    root_block = Block(
        name="RampEventDemo",
        state_vars=list([x_state]),
        diff_vars=list([dx_state]),
        state_eqs=list([Const(8.0) * (u_input - x_state)]),
        algebraic_vars=list([y_output]),
        algebraic_eqs=list([y_output - x_state]),
        event_dict=dict({u_input: Const(0.0, name="u_input")}),
        init_eqs=dict({x_state: Const(0.0), y_output: Const(0.0)}),
    )

    grid = MultiCircuit()
    event_group = EmtEventsGroup(name="ramp_event_demo")
    grid.add_emt_events_group(event_group)
    grid.add_emt_event(
        EmtEvent(
            parameter=u_input,
            time=0.2,
            end_time=0.5,
            value=1.0,
            group=event_group,
            transition_type=DynamicEventTransitionType.Ramp,
        )
    )

    problem = RampEventDemoProblem(grid=grid, sys_block=root_block, glob_time=glob_time)
    problem.set_events_group(event_group)
    problem.init_guess[x_state.uid] = 0.0
    problem.init_guess[y_output.uid] = 0.0
    return problem, event_group, u_input


def evaluate_runtime_parameter_trace(problem: RampEventDemoProblem, parameter: Var, time_values: np.ndarray) -> np.ndarray:
    """
    Evaluate one runtime parameter trace at explicit time samples.

    :param problem: Demo problem.
    :param parameter: Runtime parameter to evaluate.
    :param time_values: Time samples.
    :return: Parameter trace.
    """
    runtime_idx = problem.uid2idx_event_params[parameter.uid]
    trace = np.zeros(len(time_values), dtype=float)
    sample_index: int

    for sample_index in range(len(time_values)):
        runtime_values = problem.event_params_values.copy()
        runtime_values = problem.def_event_params_fn(runtime_values, float(time_values[sample_index]))
        trace[sample_index] = float(runtime_values[runtime_idx])

    return trace


def run_ramp_event_case(enable_plots: bool = True) -> Dict[str, object]:
    """
    Run the minimal ramp-event EMT demo.

    :param enable_plots: If True, show the resulting plots.
    :return: Trace dictionary.
    """
    output_dir: Path = get_plot_results_directory("emt_ramp_event", "symbolic")
    png_path: Path = output_dir / "emt_ramp_event_demo.png"

    problem, _event_group, parameter = build_ramp_event_demo_problem()
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=1.0,
        h=1.0e-3,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )
    tme, y_hist, _dy_hist, _converged, _diag = solver.simulate(boundary_updater=None)
    parameter_trace = evaluate_runtime_parameter_trace(problem, parameter, np.asarray(tme, dtype=float))
    state_idx = problem.get_var_idx(problem.get_state_vars()[0])
    output_idx = problem.get_var_idx(problem.get_algebraic_vars()[0])

    traces = dict({
        "time": np.asarray(tme, dtype=float),
        "u_input": parameter_trace,
        "x_state": np.asarray(y_hist[:, state_idx], dtype=float),
        "y_output": np.asarray(y_hist[:, output_idx], dtype=float),
    })

    if enable_plots:
        plt.figure(figsize=(10, 7))
        plt.subplot(2, 1, 1)
        plt.plot(traces["time"], traces["u_input"], label="u_input")
        plt.grid(True)
        plt.legend()
        plt.title("EMT Ramp Event Runtime Parameter")

        plt.subplot(2, 1, 2)
        plt.plot(traces["time"], traces["x_state"], label="x_state")
        plt.plot(traces["time"], traces["y_output"], label="y_output", linestyle="--")
        plt.grid(True)
        plt.legend()
        plt.xlabel("Time [s]")
        plt.tight_layout()
        plt.savefig(png_path, dpi=200, bbox_inches="tight")
        plt.show()
    else:
        plt.figure(figsize=(10, 7))
        plt.subplot(2, 1, 1)
        plt.plot(traces["time"], traces["u_input"], label="u_input")
        plt.grid(True)
        plt.legend()
        plt.title("EMT Ramp Event Runtime Parameter")

        plt.subplot(2, 1, 2)
        plt.plot(traces["time"], traces["x_state"], label="x_state")
        plt.plot(traces["time"], traces["y_output"], label="y_output", linestyle="--")
        plt.grid(True)
        plt.legend()
        plt.xlabel("Time [s]")
        plt.tight_layout()
        plt.savefig(png_path, dpi=200, bbox_inches="tight")
        plt.close()

    traces["png_path"] = str(png_path)
    return traces


if __name__ == "__main__":
    run_ramp_event_case(enable_plots=True)
