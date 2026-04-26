# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.switch_emt_template import get_switch_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType, SolverType
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory

import VeraGridEngine.api as gce


def _get_switch_demo_options() -> EmtOptions:
    return EmtOptions(
        time_step=5e-6,
        simulation_time=0.08,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=0,
    )


def _build_switch_sequence() -> List[Tuple[float, float]]:
    """
    Return the richer switch open/close event sequence used by the demo.

    :return: Ordered `(time, mode)` pairs.
    """
    return list([
        (0.015, 0.0),
        (0.028, 1.0),
        (0.041, 0.0),
        (0.056, 1.0),
        (0.068, 0.0),
    ])


def _build_switch_demo_grid() -> tuple[gce.MultiCircuit, gce.Generator, gce.Switch, gce.Load]:
    grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)
    bus0 = gce.Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=10.0)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    switch = gce.Switch(name="SW", bus_from=bus0, bus_to=bus1, r=1.0e-6, x=1.0e-6, active=True)
    load = gce.Load(name="load", P1=0.2, P2=0.2, P3=0.2, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.GroundedStar
    gen = gce.Generator(name="Gen", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)

    grid.add_switch(switch)
    grid.add_generator(bus=bus0, api_obj=gen)
    grid.add_load(bus=bus1, api_obj=load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    gen_mdl = get_generator_thevenin_rl_emt_template(vf=grid.var_factory, name="Gen").block
    switch_mdl = get_switch_emt_template(vf=grid.var_factory, signal_controlled=False, name="SW").block
    load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True, name="Shunt_R_3ph").block

    set_emt_model(device=gen, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=switch, model=switch_mdl, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)
    return grid, gen, switch, load


def _run_power_flow(grid: gce.MultiCircuit):
    pf_options = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        generate_report=False,
    )
    power_flow = PowerFlowDriver3Ph(grid, pf_options)
    power_flow.run()
    return power_flow.results


def run_switch_emt_case(enable_plots: bool = True) -> Dict[str, object]:
    grid, _gen, switch, _load = _build_switch_demo_grid()
    pf_res_3ph = _run_power_flow(grid)

    switch_mode_var = find_name_in_block("switch_closed_mode_SW", switch.emt_model)
    if switch_mode_var is None:
        for candidate_var in switch.emt_model.mode_dict.keys():
            if candidate_var.name == "switch_closed_mode_SW":
                switch_mode_var = candidate_var
                break
            else:
                pass

    if switch_mode_var is None:
        raise KeyError("Switch EMT mode variable was not found")

    event_group = EmtEventsGroup(name="switch_emt_demo")
    grid.add_emt_events_group(event_group)
    event_time: float
    event_value: float
    event_schedule: List[Tuple[float, float]] = _build_switch_sequence()

    for event_time, event_value in event_schedule:
        grid.add_emt_event(
            EmtEvent(
                device=switch,
                parameter=switch_mode_var,
                time=event_time,
                value=event_value,
                group=event_group,
                force_step_alignment=True,
            )
        )

    problem = EmtProblemDae(grid=grid, options=_get_switch_demo_options(), pf_results=None, pf_results_3ph=pf_res_3ph)
    problem.set_events_group(event_group)

    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=problem.options.simulation_time,
        h=problem.options.time_step,
        method=problem.options.integration_method,
        verbose=False,
    )
    tme, y_hist, _dy_hist, _converged, _diag = solver.simulate(boundary_updater=problem)

    mode_idx = problem.uid2idx_event_params[switch_mode_var.uid]
    mode_trace = np.zeros(len(tme), dtype=float)
    sample_index: int
    current_mode_value: float = float(problem.event_params_values[mode_idx])
    event_cursor: int = 0

    for sample_index in range(len(tme)):
        while event_cursor < len(event_schedule) and float(tme[sample_index]) >= float(event_schedule[event_cursor][0]):
            current_mode_value = float(event_schedule[event_cursor][1])
            event_cursor += 1
        mode_trace[sample_index] = current_mode_value

    bus1_var = find_name_in_block("v_A_Bus1_emt_template", problem.sys_block)
    if bus1_var is None:
        raise KeyError("Bus1 phase-A voltage was not found")

    current_var = find_name_in_block("if_A_SW", problem.sys_block)
    if current_var is None:
        raise KeyError("Switch phase-A current was not found")

    traces = dict({
        "time": np.asarray(tme, dtype=float),
        "switch_mode": mode_trace,
        "bus1_v_a": np.asarray(y_hist[:, problem.get_var_idx(bus1_var)], dtype=float),
        "switch_i_a": np.asarray(y_hist[:, problem.get_var_idx(current_var)], dtype=float),
        "event_times": np.asarray([item[0] for item in event_schedule], dtype=float),
        "event_values": np.asarray([item[1] for item in event_schedule], dtype=float),
    })

    output_dir: Path = get_plot_results_directory("switch_emt", "symbolic")
    mode_png_path: Path = output_dir / "switch_emt_mode_sequence.png"
    response_png_path: Path = output_dir / "switch_emt_bus_voltage_and_current.png"

    figure_mode = plt.figure(figsize=(10, 4))
    axis_mode = figure_mode.add_subplot(1, 1, 1)
    axis_mode.step(traces["time"], traces["switch_mode"], where="post", label="switch_mode", color="tab:blue")
    axis_mode.scatter(traces["event_times"], traces["event_values"], color="tab:red", zorder=3, label="scheduled events")
    axis_mode.grid(True)
    axis_mode.legend()
    axis_mode.set_ylabel("Mode")
    axis_mode.set_xlabel("Time [s]")
    axis_mode.set_title("Switch EMT Mode Sequence")
    figure_mode.tight_layout()
    figure_mode.savefig(mode_png_path, dpi=200, bbox_inches="tight")

    figure_response, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(traces["time"], traces["bus1_v_a"], label="Bus1 v_A", color="tab:green")
    axes[0].grid(True)
    axes[0].legend()
    axes[0].set_ylabel("Voltage")
    axes[0].set_title("Switch EMT Electrical Response")

    axes[1].plot(traces["time"], traces["switch_i_a"], label="Switch if_A", linestyle="--", color="tab:orange")
    axes[1].grid(True)
    axes[1].legend()
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Current")
    figure_response.tight_layout()
    figure_response.savefig(response_png_path, dpi=200, bbox_inches="tight")

    if enable_plots:
        plt.show()
    else:
        plt.close(figure_mode)
        plt.close(figure_response)

    traces["mode_png_path"] = str(mode_png_path)
    traces["response_png_path"] = str(response_png_path)
    return traces


if __name__ == "__main__":
    run_switch_emt_case(enable_plots=True)
