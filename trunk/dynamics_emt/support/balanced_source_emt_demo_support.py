# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_balanced_3ph_current_source_emt_template
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_balanced_3ph_voltage_source_emt_template
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_controlled_balanced_3ph_current_source_emt_template
from VeraGridEngine.Templates.Emt.balanced_source_emt_template import get_controlled_balanced_3ph_voltage_source_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicIntegrationMethod
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory


BALANCED_SOURCE_EVENT_TIME_S: float = 0.04
BALANCED_SOURCE_END_TIME_S: float = 0.08


class BalancedSourceEmtDemoProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the balanced-source demos.
    """

    __slots__ = ["grid"]

    def __init__(self, grid: MultiCircuit,
                 sys_block: Block,
                 glob_time: Var,
                 static_parameter_values_mapping:Dict[Var, Const]) -> None:
        self.grid = grid
        super().__init__(sys_block=sys_block, glob_time=glob_time,static_parameter_values_mapping=static_parameter_values_mapping)


class BalancedSourceEmtCaseResult:
    """
    Time-domain traces exported by one balanced-source EMT case.
    """

    __slots__ = [
        "case_name",
        "time",
        "amplitude_reference",
        "amplitude_command",
        "bus_voltage_a",
        "bus_voltage_b",
        "bus_voltage_c",
        "source_current_a",
        "source_current_b",
        "source_current_c",
        "png_path",
    ]

    def __init__(self,
                 case_name: str,
                 time: np.ndarray,
                 amplitude_reference: np.ndarray,
                 amplitude_command: np.ndarray,
                 bus_voltage_a: np.ndarray,
                 bus_voltage_b: np.ndarray,
                 bus_voltage_c: np.ndarray,
                 source_current_a: np.ndarray,
                 source_current_b: np.ndarray,
                 source_current_c: np.ndarray,
                 png_path: Path) -> None:
        self.case_name: str = str(case_name)
        self.time: np.ndarray = np.asarray(time, dtype=np.float64)
        self.amplitude_reference: np.ndarray = np.asarray(amplitude_reference, dtype=np.float64)
        self.amplitude_command: np.ndarray = np.asarray(amplitude_command, dtype=np.float64)
        self.bus_voltage_a: np.ndarray = np.asarray(bus_voltage_a, dtype=np.float64)
        self.bus_voltage_b: np.ndarray = np.asarray(bus_voltage_b, dtype=np.float64)
        self.bus_voltage_c: np.ndarray = np.asarray(bus_voltage_c, dtype=np.float64)
        self.source_current_a: np.ndarray = np.asarray(source_current_a, dtype=np.float64)
        self.source_current_b: np.ndarray = np.asarray(source_current_b, dtype=np.float64)
        self.source_current_c: np.ndarray = np.asarray(source_current_c, dtype=np.float64)
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

    raise ValueError(f"Unable to find one balanced source EMT event parameter starting with '{name_prefix}'")


def _build_balanced_source_case_problem(case_name: str,
                                        controlled: bool,
                                        voltage_source: bool,
                                        initial_amplitude: float,
                                        stepped_amplitude: float,
                                        frequency_hz: float = 50.0,
                                        controller_bandwidth: float = 150.0,
                                        load_conductance: float = 1.0,
                                        source_conductance: float = 100.0) -> tuple[BalancedSourceEmtDemoProblem, Var, Var, list[Var], list[Var], Path]:
    """
    Build one minimal balanced-source EMT case with one first-order amplitude loop.

    :param case_name: Case identifier.
    :param controlled: Whether the source is command-driven.
    :param voltage_source: Whether the source is voltage-driven.
    :param initial_amplitude: Initial common sinusoidal amplitude.
    :param stepped_amplitude: Amplitude reference after the event.
    :param frequency_hz: Common source frequency.
    :param controller_bandwidth: Amplitude-loop bandwidth.
    :param load_conductance: Per-phase conductive shunt load.
    :param source_conductance: Norton conductance for voltage-source variants.
    :return: Problem, amplitude reference, amplitude command, voltage vars, current vars, and PNG path.
    """
    vf: VarFactory = VarFactory()
    glob_time: Var = vf.add_var(f"t_glob_{case_name}")
    source_reference: Var = vf.add_var(f"src_ref_{case_name}")
    source_command: Var = vf.add_var(f"src_cmd_{case_name}")
    d_source_command = vf.add_diff_var(name=f"d_src_cmd_{case_name}", base_var=source_command)
    bus_voltage_a: Var = vf.add_var(f"v_bus_a_{case_name}")
    bus_voltage_b: Var = vf.add_var(f"v_bus_b_{case_name}")
    bus_voltage_c: Var = vf.add_var(f"v_bus_c_{case_name}")
    load_current_a: Var = vf.add_var(f"i_load_a_{case_name}")
    load_current_b: Var = vf.add_var(f"i_load_b_{case_name}")
    load_current_c: Var = vf.add_var(f"i_load_c_{case_name}")

    if voltage_source:
        if controlled:
            source_block = get_controlled_balanced_3ph_voltage_source_emt_template(
                vf=vf,
                frequency_hz=frequency_hz,
                phase_a_deg=0.0,
                offset_value=0.0,
                source_conductance_value=source_conductance,
                name=case_name,
            ).block
        else:
            source_block = get_balanced_3ph_voltage_source_emt_template(
                vf=vf,
                amplitude_value=initial_amplitude,
                frequency_hz=frequency_hz,
                phase_a_deg=0.0,
                offset_value=0.0,
                source_conductance_value=source_conductance,
                name=case_name,
            ).block
    else:
        if controlled:
            source_block = get_controlled_balanced_3ph_current_source_emt_template(
                vf=vf,
                frequency_hz=frequency_hz,
                phase_a_deg=0.0,
                offset_value=0.0,
                name=case_name,
            ).block
        else:
            source_block = get_balanced_3ph_current_source_emt_template(
                vf=vf,
                amplitude_value=initial_amplitude,
                frequency_hz=frequency_hz,
                phase_a_deg=0.0,
                offset_value=0.0,
                name=case_name,
            ).block

    source_block.update_model(source_block.in_vars[0], bus_voltage_a)
    source_block.update_model(source_block.in_vars[1], bus_voltage_b)
    source_block.update_model(source_block.in_vars[2], bus_voltage_c)
    source_current_vars: list[Var] = list(source_block.out_vars)

    if controlled:
        source_block.update_model(source_block.in_vars[3], source_command)
    else:
        pass

    root_block = Block(
        name=case_name,
        state_vars=[source_command],
        diff_vars=[d_source_command],
        state_eqs=[Const(float(controller_bandwidth)) * (source_reference - source_command)],
        algebraic_vars=[bus_voltage_a, bus_voltage_b, bus_voltage_c, load_current_a, load_current_b, load_current_c],
        algebraic_eqs=[
            source_current_vars[0] + load_current_a,
            source_current_vars[1] + load_current_b,
            source_current_vars[2] + load_current_c,
            load_current_a + Const(float(load_conductance)) * bus_voltage_a,
            load_current_b + Const(float(load_conductance)) * bus_voltage_b,
            load_current_c + Const(float(load_conductance)) * bus_voltage_c,
        ],
        children=[source_block],
        init_eqs={
            source_reference: Const(float(initial_amplitude)),
            source_command: Const(float(initial_amplitude)),
            bus_voltage_a: Const(0.0),
            bus_voltage_b: Const(0.0),
            bus_voltage_c: Const(0.0),
            load_current_a: Const(0.0),
            load_current_b: Const(0.0),
            load_current_c: Const(0.0),
        },
        event_dict={source_reference: Const(float(initial_amplitude), name=source_reference.name)},
    )

    if not controlled:
        if voltage_source:
            source_amplitude_var = _find_event_parameter_by_prefix(source_block, "V_amp_")
            source_block.event_dict[source_amplitude_var] = Const(float(initial_amplitude), name=source_amplitude_var.name)
        else:
            source_amplitude_var = _find_event_parameter_by_prefix(source_block, "I_amp_")
            source_block.event_dict[source_amplitude_var] = Const(float(initial_amplitude), name=source_amplitude_var.name)
    else:
        pass

    root_block.unify_blocks()
    grid: MultiCircuit = MultiCircuit()
    event_group: EmtEventsGroup = EmtEventsGroup(name=f"{case_name}_events")
    grid.add_emt_events_group(event_group)
    grid.add_emt_event(
        EmtEvent(
            parameter=source_reference,
            time=BALANCED_SOURCE_EVENT_TIME_S,
            value=float(stepped_amplitude),
            group=event_group,
            force_step_alignment=True,
            transition_type=DynamicEventTransitionType.Step,
            name=f"{case_name}_step",
        )
    )
    static_parameter_values_mapping: Dict[Var, Const] = dict()
    problem: BalancedSourceEmtDemoProblem = BalancedSourceEmtDemoProblem(grid=grid, sys_block=root_block, glob_time=glob_time, static_parameter_values_mapping=static_parameter_values_mapping)
    problem.set_events_group(event_group)
    output_dir: Path = get_plot_results_directory("balanced_source_emt", "symbolic")
    png_path: Path = output_dir / f"{case_name}.png"
    return problem, source_reference, source_command, [bus_voltage_a, bus_voltage_b, bus_voltage_c], source_current_vars, png_path


def run_balanced_source_case(case_name: str,
                             controlled: bool,
                             voltage_source: bool,
                             initial_amplitude: float,
                             stepped_amplitude: float,
                             enable_plots: bool = True) -> BalancedSourceEmtCaseResult:
    """
    Run one balanced-source EMT case and export one PNG.

    :param case_name: Case identifier.
    :param controlled: Whether the source is command-driven.
    :param voltage_source: Whether the source is voltage-driven.
    :param initial_amplitude: Initial common sinusoidal amplitude.
    :param stepped_amplitude: Amplitude after the event.
    :param enable_plots: Whether to show the figure.
    :return: Exported case result.
    """
    problem, source_reference, source_command, bus_voltage_vars, source_current_vars, png_path = _build_balanced_source_case_problem(
        case_name=case_name,
        controlled=controlled,
        voltage_source=voltage_source,
        initial_amplitude=initial_amplitude,
        stepped_amplitude=stepped_amplitude,
    )
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=BALANCED_SOURCE_END_TIME_S,
        h=1.0e-4,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )
    time_values, state_history, _diff_history, _converged, _diag = solver.simulate(boundary_updater=None)
    source_reference_trace = np.asarray([problem.def_event_params_fn(problem.event_params_values.copy(), float(tm))[0] for tm in time_values], dtype=np.float64)
    source_command_idx: int = problem.get_var_idx(source_command)
    bus_voltage_idx = [problem.get_var_idx(var) for var in bus_voltage_vars]
    source_current_idx = [problem.get_var_idx(var) for var in source_current_vars]

    figure, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(time_values, source_reference_trace, color="tab:orange", label="Amplitude ref")
    axes[0].plot(time_values, state_history[:, source_command_idx], color="tab:blue", label="Amplitude cmd")
    axes[0].axvline(BALANCED_SOURCE_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[0].grid(True)
    axes[0].legend()
    axes[0].set_ylabel("Amplitude [pu]")
    axes[0].set_title(case_name)

    axes[1].plot(time_values, state_history[:, bus_voltage_idx[0]], color="tab:blue", label="Va")
    axes[1].plot(time_values, state_history[:, bus_voltage_idx[1]], color="tab:red", label="Vb")
    axes[1].plot(time_values, state_history[:, bus_voltage_idx[2]], color="tab:green", label="Vc")
    axes[1].axvline(BALANCED_SOURCE_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[1].grid(True)
    axes[1].legend()
    axes[1].set_ylabel("Voltage [pu inst]")

    axes[2].plot(time_values, state_history[:, source_current_idx[0]], color="tab:blue", label="Ia")
    axes[2].plot(time_values, state_history[:, source_current_idx[1]], color="tab:red", label="Ib")
    axes[2].plot(time_values, state_history[:, source_current_idx[2]], color="tab:green", label="Ic")
    axes[2].axvline(BALANCED_SOURCE_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[2].grid(True)
    axes[2].legend()
    axes[2].set_xlabel("Time [s]")
    axes[2].set_ylabel("Current [pu inst]")
    figure.tight_layout()
    figure.savefig(png_path, dpi=200, bbox_inches="tight")

    if enable_plots:
        plt.show()
    else:
        plt.close(figure)

    return BalancedSourceEmtCaseResult(
        case_name=case_name,
        time=np.asarray(time_values, dtype=np.float64),
        amplitude_reference=source_reference_trace,
        amplitude_command=np.asarray(state_history[:, source_command_idx], dtype=np.float64),
        bus_voltage_a=np.asarray(state_history[:, bus_voltage_idx[0]], dtype=np.float64),
        bus_voltage_b=np.asarray(state_history[:, bus_voltage_idx[1]], dtype=np.float64),
        bus_voltage_c=np.asarray(state_history[:, bus_voltage_idx[2]], dtype=np.float64),
        source_current_a=np.asarray(state_history[:, source_current_idx[0]], dtype=np.float64),
        source_current_b=np.asarray(state_history[:, source_current_idx[1]], dtype=np.float64),
        source_current_c=np.asarray(state_history[:, source_current_idx[2]], dtype=np.float64),
        png_path=png_path,
    )


def run_all_balanced_source_cases(enable_plots: bool = True) -> dict[str, BalancedSourceEmtCaseResult]:
    """
    Run the balanced three-phase EMT source demo cases.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    return dict({
        "balanced_3ph_current_source": run_balanced_source_case(
            case_name="balanced_3ph_current_source",
            controlled=False,
            voltage_source=False,
            initial_amplitude=0.2,
            stepped_amplitude=0.6,
            enable_plots=enable_plots,
        ),
        "balanced_3ph_voltage_source": run_balanced_source_case(
            case_name="balanced_3ph_voltage_source",
            controlled=False,
            voltage_source=True,
            initial_amplitude=0.5,
            stepped_amplitude=1.0,
            enable_plots=enable_plots,
        ),
        "controlled_balanced_3ph_current_source": run_balanced_source_case(
            case_name="controlled_balanced_3ph_current_source",
            controlled=True,
            voltage_source=False,
            initial_amplitude=0.2,
            stepped_amplitude=0.6,
            enable_plots=enable_plots,
        ),
        "controlled_balanced_3ph_voltage_source": run_balanced_source_case(
            case_name="controlled_balanced_3ph_voltage_source",
            controlled=True,
            voltage_source=True,
            initial_amplitude=0.5,
            stepped_amplitude=1.0,
            enable_plots=enable_plots,
        ),
    })
