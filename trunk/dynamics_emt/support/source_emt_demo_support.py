# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Templates.Emt.source_emt_template import get_controlled_current_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_controlled_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_current_source_emt_template
from VeraGridEngine.Templates.Emt.source_emt_template import get_voltage_source_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicIntegrationMethod
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory


SOURCE_DEMO_EVENT_TIME_S: float = 0.04
SOURCE_DEMO_END_TIME_S: float = 0.08


class SourceEmtDemoProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the source demos.
    """

    __slots__ = ["grid"]

    def __init__(self, grid: MultiCircuit, sys_block: Block, glob_time: Var) -> None:
        self.grid = grid
        super().__init__(sys_block=sys_block, glob_time=glob_time)


class SourceEmtCaseResult:
    """
    Time-domain traces exported by one EMT source demo case.
    """

    __slots__ = ["case_name", "time", "bus_voltage", "source_current", "load_current", "png_path"]

    def __init__(self,
                 case_name: str,
                 time: np.ndarray,
                 bus_voltage: np.ndarray,
                 source_current: np.ndarray,
                 load_current: np.ndarray,
                 png_path: Path) -> None:
        self.case_name: str = str(case_name)
        self.time: np.ndarray = np.asarray(time, dtype=np.float64)
        self.bus_voltage: np.ndarray = np.asarray(bus_voltage, dtype=np.float64)
        self.source_current: np.ndarray = np.asarray(source_current, dtype=np.float64)
        self.load_current: np.ndarray = np.asarray(load_current, dtype=np.float64)
        self.png_path: Path = png_path


def _find_event_parameter_by_prefix(block: Block, name_prefix: str) -> Var:
    """
    Return the first event parameter whose name starts with one prefix.

    :param block: Candidate symbolic block.
    :param name_prefix: Required name prefix.
    :return: Matching event parameter variable.
    :raises ValueError: If no variable matches.
    """
    event_var: Var

    for event_var in block.event_dict.keys():
        if event_var.name.startswith(name_prefix):
            return event_var
        else:
            pass

    raise ValueError(f"Unable to find one source EMT event parameter starting with '{name_prefix}'")


def _build_source_case_problem(case_name: str,
                               controlled: bool,
                               voltage_source: bool,
                               initial_value: float,
                               stepped_value: float,
                               load_conductance: float = 1.0,
                               source_conductance: float = 50.0) -> tuple[SourceEmtDemoProblem, Var, Var, Var, Path]:
    """
    Build one minimal EMT source case around one scalar bus voltage.

    :param case_name: Case identifier.
    :param controlled: Whether the source value comes from one command input.
    :param voltage_source: Whether the source is voltage-driven instead of current-driven.
    :param initial_value: Initial source value or command.
    :param stepped_value: Post-event source value or command.
    :param load_conductance: Conductive shunt load tied to the bus.
    :param source_conductance: Norton conductance used by voltage-source variants.
    :return: Problem, bus voltage, source current, load current, and output PNG path.
    """
    vf: VarFactory = VarFactory()
    glob_time: Var = vf.add_var(f"t_glob_{case_name}")
    bus_voltage: Var = vf.add_var(f"v_bus_{case_name}")
    load_current: Var = vf.add_var(f"i_load_{case_name}")
    command_var: Var | None = None
    source_block: Block

    if voltage_source:
        if controlled:
            source_block = get_controlled_voltage_source_emt_template(
                vf=vf,
                phN=False,
                phA=True,
                phB=False,
                phC=False,
                source_conductance_value=source_conductance,
                name=case_name,
            ).block
        else:
            source_block = get_voltage_source_emt_template(
                vf=vf,
                phN=False,
                phA=True,
                phB=False,
                phC=False,
                amplitude_values=dict({"A": initial_value}),
                source_conductance_value=source_conductance,
                name=case_name,
            ).block
    else:
        if controlled:
            source_block = get_controlled_current_source_emt_template(
                vf=vf,
                phN=False,
                phA=True,
                phB=False,
                phC=False,
                name=case_name,
            ).block
        else:
            source_block = get_current_source_emt_template(
                vf=vf,
                phN=False,
                phA=True,
                phB=False,
                phC=False,
                amplitude_values=dict({"A": initial_value}),
                name=case_name,
            ).block

    source_current: Var = source_block.out_vars[0]
    source_block.update_model(source_block.in_vars[0], bus_voltage)

    if controlled:
        command_var = vf.add_var(f"cmd_{case_name}")
        source_block.update_model(source_block.in_vars[1], command_var)
    else:
        command_var = None

    root_block: Block = Block(
        name=case_name,
        algebraic_vars=list([bus_voltage, load_current]),
        algebraic_eqs=list([
            source_current + load_current,
            load_current + Const(float(load_conductance)) * bus_voltage,
        ]),
        children=list([source_block]),
        init_eqs=dict({bus_voltage: Const(0.0), load_current: Const(0.0)}),
    )

    if controlled and command_var is not None:
        root_block.event_dict[command_var] = Const(float(initial_value), name=command_var.name)
    else:
        if voltage_source:
            source_voltage_var: Var = _find_event_parameter_by_prefix(source_block, "V_amp_A_")
            source_block.event_dict[source_voltage_var] = Const(float(initial_value), name=source_voltage_var.name)
        else:
            source_current_var: Var = _find_event_parameter_by_prefix(source_block, "I_amp_A_")
            source_block.event_dict[source_current_var] = Const(float(initial_value), name=source_current_var.name)

    root_block.unify_blocks()
    grid: MultiCircuit = MultiCircuit()
    event_group: EmtEventsGroup = EmtEventsGroup(name=f"{case_name}_events")
    grid.add_emt_events_group(event_group)

    if controlled and command_var is not None:
        grid.add_emt_event(
            EmtEvent(
                parameter=command_var,
                time=SOURCE_DEMO_EVENT_TIME_S,
                value=float(stepped_value),
                group=event_group,
                force_step_alignment=True,
                transition_type=DynamicEventTransitionType.Step,
                name=f"{case_name}_cmd_step",
            )
        )
    else:
        if voltage_source:
            source_voltage_var = _find_event_parameter_by_prefix(root_block, "V_amp_A_")
            grid.add_emt_event(
                EmtEvent(
                    parameter=source_voltage_var,
                    time=SOURCE_DEMO_EVENT_TIME_S,
                    value=float(stepped_value),
                    group=event_group,
                    force_step_alignment=True,
                    transition_type=DynamicEventTransitionType.Step,
                    name=f"{case_name}_voltage_step",
                )
            )
        else:
            source_current_var = _find_event_parameter_by_prefix(root_block, "I_amp_A_")
            grid.add_emt_event(
                EmtEvent(
                    parameter=source_current_var,
                    time=SOURCE_DEMO_EVENT_TIME_S,
                    value=float(stepped_value),
                    group=event_group,
                    force_step_alignment=True,
                    transition_type=DynamicEventTransitionType.Step,
                    name=f"{case_name}_current_step",
                )
            )

    problem: SourceEmtDemoProblem = SourceEmtDemoProblem(grid=grid, sys_block=root_block, glob_time=glob_time)
    problem.set_events_group(event_group)
    output_dir: Path = get_plot_results_directory("source_emt", "symbolic")
    png_path: Path = output_dir / f"{case_name}.png"
    return problem, bus_voltage, source_current, load_current, png_path


def run_source_case(case_name: str,
                    controlled: bool,
                    voltage_source: bool,
                    initial_value: float,
                    stepped_value: float,
                    enable_plots: bool = True) -> SourceEmtCaseResult:
    """
    Run one minimal EMT source case and export one PNG.

    :param case_name: Case identifier.
    :param controlled: Whether the source is command-driven.
    :param voltage_source: Whether the source is voltage-driven.
    :param initial_value: Initial source value or command.
    :param stepped_value: Value after the step event.
    :param enable_plots: Whether to show the figure.
    :return: Exported case result.
    """
    problem, bus_voltage, source_current, load_current, png_path = _build_source_case_problem(
        case_name=case_name,
        controlled=controlled,
        voltage_source=voltage_source,
        initial_value=initial_value,
        stepped_value=stepped_value,
    )
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=SOURCE_DEMO_END_TIME_S,
        h=1.0e-4,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )
    time_values, state_history, _diff_history, _converged, _diag = solver.simulate(boundary_updater=None)
    voltage_idx: int = problem.get_var_idx(bus_voltage)
    source_current_idx: int = problem.get_var_idx(source_current)
    load_current_idx: int = problem.get_var_idx(load_current)
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    axes[0].plot(time_values, state_history[:, voltage_idx], color="tab:blue", label="Bus voltage")
    axes[0].axvline(SOURCE_DEMO_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[0].grid(True)
    axes[0].legend()
    axes[0].set_ylabel("Voltage [pu inst]")
    axes[0].set_title(case_name)

    axes[1].plot(time_values, state_history[:, source_current_idx], color="tab:green", label="Source current")
    axes[1].plot(time_values, state_history[:, load_current_idx], color="tab:red", linestyle="--", label="Load current")
    axes[1].axvline(SOURCE_DEMO_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[1].grid(True)
    axes[1].legend()
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Current [pu inst]")
    figure.tight_layout()
    figure.savefig(png_path, dpi=200, bbox_inches="tight")

    if enable_plots:
        plt.show()
    else:
        plt.close(figure)

    return SourceEmtCaseResult(
        case_name=case_name,
        time=np.asarray(time_values, dtype=np.float64),
        bus_voltage=np.asarray(state_history[:, voltage_idx], dtype=np.float64),
        source_current=np.asarray(state_history[:, source_current_idx], dtype=np.float64),
        load_current=np.asarray(state_history[:, load_current_idx], dtype=np.float64),
        png_path=png_path,
    )


def run_all_source_cases(enable_plots: bool = True) -> dict[str, SourceEmtCaseResult]:
    """
    Run all four EMT source demo cases.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    return dict({
        "fixed_current_source": run_source_case(
            case_name="fixed_current_source",
            controlled=False,
            voltage_source=False,
            initial_value=0.2,
            stepped_value=0.5,
            enable_plots=enable_plots,
        ),
        "fixed_voltage_source": run_source_case(
            case_name="fixed_voltage_source",
            controlled=False,
            voltage_source=True,
            initial_value=0.5,
            stepped_value=1.0,
            enable_plots=enable_plots,
        ),
        "controlled_current_source": run_source_case(
            case_name="controlled_current_source",
            controlled=True,
            voltage_source=False,
            initial_value=0.2,
            stepped_value=0.5,
            enable_plots=enable_plots,
        ),
        "controlled_voltage_source": run_source_case(
            case_name="controlled_voltage_source",
            controlled=True,
            voltage_source=True,
            initial_value=0.5,
            stepped_value=1.0,
            enable_plots=enable_plots,
        ),
    })
