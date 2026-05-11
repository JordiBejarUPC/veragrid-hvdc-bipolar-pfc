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
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_controlled_dc_current_source_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_controlled_dc_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_current_source_emt_template
from VeraGridEngine.Templates.Emt.dc_source_emt_template import get_dc_voltage_source_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicIntegrationMethod
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory


DC_SOURCE_EVENT_TIME_S: float = 0.02
DC_SOURCE_END_TIME_S: float = 0.04


class DcSourceEmtDemoProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the DC source demos.
    """

    __slots__ = ["grid"]

    def __init__(self, grid: MultiCircuit, sys_block: Block, glob_time: Var,
                 static_parameter_values_mapping: Dict[Var, Const]) -> None:
        self.grid = grid
        super().__init__(sys_block=sys_block, glob_time=glob_time,static_parameter_values_mapping=static_parameter_values_mapping)


class DcSourceEmtCaseResult:
    """
    Time-domain traces exported by one DC source demo case.
    """

    __slots__ = ["case_name", "time", "source_reference", "source_command", "bus_voltage", "source_current", "load_current", "png_path"]

    def __init__(self,
                 case_name: str,
                 time: np.ndarray,
                 source_reference: np.ndarray,
                 source_command: np.ndarray,
                 bus_voltage: np.ndarray,
                 source_current: np.ndarray,
                 load_current: np.ndarray,
                 png_path: Path) -> None:
        self.case_name: str = str(case_name)
        self.time: np.ndarray = np.asarray(time, dtype=np.float64)
        self.source_reference: np.ndarray = np.asarray(source_reference, dtype=np.float64)
        self.source_command: np.ndarray = np.asarray(source_command, dtype=np.float64)
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

    raise ValueError(f"Unable to find one DC source EMT event parameter starting with '{name_prefix}'")


def _build_dc_source_case_problem(case_name: str,
                                  controlled: bool,
                                  voltage_source: bool,
                                  initial_value: float,
                                  stepped_value: float,
                                  controller_bandwidth: float = 200.0,
                                  load_conductance: float = 1.0,
                                  source_conductance: float = 100.0) -> tuple[DcSourceEmtDemoProblem, Var, Var, Var, Var, Path]:
    """
    Build one minimal EMT DC source case.

    :param case_name: Case identifier.
    :param controlled: Whether the source uses one command input.
    :param voltage_source: Whether the source is voltage-driven.
    :param initial_value: Initial DC source value.
    :param stepped_value: Post-event DC source value.
    :param controller_bandwidth: First-order command bandwidth for controlled cases.
    :param load_conductance: Conductive DC load.
    :param source_conductance: Norton conductance for DC voltage-source variants.
    :return: Problem, reference, command state, bus voltage, source current, and PNG path.
    """
    vf: VarFactory = VarFactory()
    glob_time: Var = vf.add_var(f"t_glob_{case_name}")
    bus_voltage: Var = vf.add_var(f"v_bus_{case_name}")
    load_current: Var = vf.add_var(f"i_load_{case_name}")
    source_reference: Var = vf.add_var(f"src_ref_{case_name}")
    source_command: Var = vf.add_var(f"src_cmd_{case_name}")
    d_source_command = vf.add_diff_var(name=f"d_src_cmd_{case_name}", base_var=source_command)

    if voltage_source:
        if controlled:
            source_block = get_controlled_dc_voltage_source_emt_template(
                vf=vf,
                source_conductance_value=source_conductance,
                name=case_name,
            ).block
        else:
            source_block = get_dc_voltage_source_emt_template(
                vf=vf,
                source_voltage_value=initial_value,
                source_conductance_value=source_conductance,
                name=case_name,
            ).block
    else:
        if controlled:
            source_block = get_controlled_dc_current_source_emt_template(vf=vf, name=case_name).block
        else:
            source_block = get_dc_current_source_emt_template(vf=vf, source_current_value=initial_value, name=case_name).block

    source_current: Var = source_block.out_vars[0]
    source_block.update_model(source_block.in_vars[0], bus_voltage)

    if controlled:
        source_block.update_model(source_block.in_vars[1], source_command)
    else:
        pass

    root_block = Block(
        name=case_name,
        state_vars=[source_command],
        diff_vars=[d_source_command],
        state_eqs=[Const(float(controller_bandwidth)) * (source_reference - source_command)],
        algebraic_vars=[bus_voltage, load_current],
        algebraic_eqs=[
            source_current + load_current,
            load_current + Const(float(load_conductance)) * bus_voltage,
        ],
        children=[source_block],
        init_eqs={
            source_reference: Const(float(initial_value)),
            source_command: Const(float(initial_value)),
            bus_voltage: Const(0.0),
            load_current: Const(0.0),
        },
        event_dict={source_reference: Const(float(initial_value), name=source_reference.name)},
    )

    if not controlled:
        if voltage_source:
            source_voltage_var = _find_event_parameter_by_prefix(source_block, "V_src_")
            source_block.event_dict[source_voltage_var] = Const(float(initial_value), name=source_voltage_var.name)
        else:
            source_current_var = _find_event_parameter_by_prefix(source_block, "I_src_")
            source_block.event_dict[source_current_var] = Const(float(initial_value), name=source_current_var.name)
    else:
        pass

    root_block.unify_blocks()
    grid: MultiCircuit = MultiCircuit()
    event_group: EmtEventsGroup = EmtEventsGroup(name=f"{case_name}_events")
    grid.add_emt_events_group(event_group)
    grid.add_emt_event(
        EmtEvent(
            parameter=source_reference,
            time=DC_SOURCE_EVENT_TIME_S,
            value=float(stepped_value),
            group=event_group,
            force_step_alignment=True,
            transition_type=DynamicEventTransitionType.Step,
            name=f"{case_name}_step",
        )
    )
    static_parameter_values_mapping: Dict[Var, Const] = dict()
    problem: DcSourceEmtDemoProblem = DcSourceEmtDemoProblem(grid=grid, sys_block=root_block, glob_time=glob_time,static_parameter_values_mapping=static_parameter_values_mapping)
    problem.set_events_group(event_group)
    output_dir: Path = get_plot_results_directory("dc_source_emt", "symbolic")
    png_path: Path = output_dir / f"{case_name}.png"
    return problem, source_reference, source_command, bus_voltage, source_current, load_current, png_path


def run_dc_source_case(case_name: str,
                       controlled: bool,
                       voltage_source: bool,
                       initial_value: float,
                       stepped_value: float,
                       enable_plots: bool = True) -> DcSourceEmtCaseResult:
    """
    Run one EMT DC source case and export one PNG.

    :param case_name: Case identifier.
    :param controlled: Whether the source uses one command input.
    :param voltage_source: Whether the source is voltage-driven.
    :param initial_value: Initial DC source value.
    :param stepped_value: Post-event DC source value.
    :param enable_plots: Whether to show the figure.
    :return: Exported case result.
    """
    problem, source_reference, source_command, bus_voltage, source_current, load_current, png_path = _build_dc_source_case_problem(
        case_name=case_name,
        controlled=controlled,
        voltage_source=voltage_source,
        initial_value=initial_value,
        stepped_value=stepped_value,
    )
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=DC_SOURCE_END_TIME_S,
        h=1.0e-4,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )
    time_values, state_history, _diff_history, _converged, _diag = solver.simulate(boundary_updater=None)
    source_reference_trace = np.asarray([problem.def_event_params_fn(problem.event_params_values.copy(), float(tm))[0] for tm in time_values], dtype=np.float64)
    source_command_idx: int = problem.get_var_idx(source_command)
    bus_voltage_idx: int = problem.get_var_idx(bus_voltage)
    source_current_idx: int = problem.get_var_idx(source_current)
    load_current_idx: int = problem.get_var_idx(load_current)

    figure, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(time_values, source_reference_trace, color="tab:orange", label="Source ref")
    axes[0].plot(time_values, state_history[:, source_command_idx], color="tab:blue", label="Source cmd")
    axes[0].axvline(DC_SOURCE_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[0].grid(True)
    axes[0].legend()
    axes[0].set_ylabel("Command")
    axes[0].set_title(case_name)

    axes[1].plot(time_values, state_history[:, bus_voltage_idx], color="tab:green", label="Bus voltage")
    axes[1].axvline(DC_SOURCE_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[1].grid(True)
    axes[1].legend()
    axes[1].set_ylabel("Voltage [pu]")

    axes[2].plot(time_values, state_history[:, source_current_idx], color="tab:purple", label="Source current")
    axes[2].plot(time_values, state_history[:, load_current_idx], color="tab:red", linestyle="--", label="Load current")
    axes[2].axvline(DC_SOURCE_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[2].grid(True)
    axes[2].legend()
    axes[2].set_xlabel("Time [s]")
    axes[2].set_ylabel("Current [pu]")
    figure.tight_layout()
    figure.savefig(png_path, dpi=200, bbox_inches="tight")

    if enable_plots:
        plt.show()
    else:
        plt.close(figure)

    return DcSourceEmtCaseResult(
        case_name=case_name,
        time=np.asarray(time_values, dtype=np.float64),
        source_reference=source_reference_trace,
        source_command=np.asarray(state_history[:, source_command_idx], dtype=np.float64),
        bus_voltage=np.asarray(state_history[:, bus_voltage_idx], dtype=np.float64),
        source_current=np.asarray(state_history[:, source_current_idx], dtype=np.float64),
        load_current=np.asarray(state_history[:, load_current_idx], dtype=np.float64),
        png_path=png_path,
    )


def run_all_dc_source_cases(enable_plots: bool = True) -> dict[str, DcSourceEmtCaseResult]:
    """
    Run all four EMT DC source demo cases.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    return dict({
        "fixed_dc_current_source": run_dc_source_case(
            case_name="fixed_dc_current_source",
            controlled=False,
            voltage_source=False,
            initial_value=0.2,
            stepped_value=0.5,
            enable_plots=enable_plots,
        ),
        "fixed_dc_voltage_source": run_dc_source_case(
            case_name="fixed_dc_voltage_source",
            controlled=False,
            voltage_source=True,
            initial_value=0.5,
            stepped_value=1.0,
            enable_plots=enable_plots,
        ),
        "controlled_dc_current_source": run_dc_source_case(
            case_name="controlled_dc_current_source",
            controlled=True,
            voltage_source=False,
            initial_value=0.2,
            stepped_value=0.5,
            enable_plots=enable_plots,
        ),
        "controlled_dc_voltage_source": run_dc_source_case(
            case_name="controlled_dc_voltage_source",
            controlled=True,
            voltage_source=True,
            initial_value=0.5,
            stepped_value=1.0,
            enable_plots=enable_plots,
        ),
    })
