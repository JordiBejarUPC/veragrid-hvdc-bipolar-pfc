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
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicIntegrationMethod
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory


CONTROLLED_SOURCE_EVENT_TIME_S: float = 0.04
CONTROLLED_SOURCE_END_TIME_S: float = 0.08


class ControlledSourceEmtDemoProblem(EmtProblemTemplate):
    """
    Minimal EMT problem used by the controlled-source demos.
    """

    __slots__ = ["grid"]

    def __init__(self, grid: MultiCircuit, sys_block: Block, glob_time: Var) -> None:
        self.grid = grid
        super().__init__(sys_block=sys_block, glob_time=glob_time)


class ControlledSourceEmtCaseResult:
    """
    Time-domain traces exported by one controlled EMT source demo case.
    """

    __slots__ = [
        "case_name",
        "time",
        "amplitude_reference",
        "amplitude_command",
        "bus_voltage",
        "source_current",
        "load_current",
        "png_path",
    ]

    def __init__(self,
                 case_name: str,
                 time: np.ndarray,
                 amplitude_reference: np.ndarray,
                 amplitude_command: np.ndarray,
                 bus_voltage: np.ndarray,
                 source_current: np.ndarray,
                 load_current: np.ndarray,
                 png_path: Path) -> None:
        self.case_name: str = str(case_name)
        self.time: np.ndarray = np.asarray(time, dtype=np.float64)
        self.amplitude_reference: np.ndarray = np.asarray(amplitude_reference, dtype=np.float64)
        self.amplitude_command: np.ndarray = np.asarray(amplitude_command, dtype=np.float64)
        self.bus_voltage: np.ndarray = np.asarray(bus_voltage, dtype=np.float64)
        self.source_current: np.ndarray = np.asarray(source_current, dtype=np.float64)
        self.load_current: np.ndarray = np.asarray(load_current, dtype=np.float64)
        self.png_path: Path = png_path


def _build_controlled_source_case_problem(case_name: str,
                                          voltage_source: bool,
                                          initial_amplitude: float,
                                          stepped_amplitude: float,
                                          frequency_hz: float = 50.0,
                                          controller_bandwidth: float = 150.0,
                                          load_conductance: float = 1.0,
                                          source_conductance: float = 100.0) -> tuple[ControlledSourceEmtDemoProblem, Var, Var, Var, Var, Path]:
    """
    Build one minimal EMT controlled-source case with one first-order amplitude loop.

    :param case_name: Case identifier.
    :param voltage_source: Whether the source is voltage-driven instead of current-driven.
    :param initial_amplitude: Initial sinusoidal amplitude.
    :param stepped_amplitude: Amplitude reference after the event.
    :param frequency_hz: Common sinusoidal frequency.
    :param controller_bandwidth: First-order command bandwidth.
    :param load_conductance: Conductive shunt load tied to the bus.
    :param source_conductance: Norton conductance for voltage-source variants.
    :return: Problem, amplitude reference, command state, bus voltage, source current, and PNG path.
    """
    vf: VarFactory = VarFactory()
    glob_time: Var = vf.add_var(f"t_glob_{case_name}")
    bus_voltage: Var = vf.add_var(f"v_bus_{case_name}")
    load_current: Var = vf.add_var(f"i_load_{case_name}")
    amplitude_reference: Var = vf.add_var(f"amp_ref_{case_name}")
    amplitude_command: Var = vf.add_var(f"amp_cmd_{case_name}")
    d_amplitude_command = vf.add_diff_var(name=f"d_amp_cmd_{case_name}", base_var=amplitude_command)

    if voltage_source:
        source_block = get_controlled_voltage_source_emt_template(
            vf=vf,
            phN=False,
            phA=True,
            phB=False,
            phC=False,
            frequency_hz=frequency_hz,
            phase_angle_deg=dict({"A": 0.0}),
            offset_values=dict({"A": 0.0}),
            source_conductance_value=source_conductance,
            name=case_name,
        ).block
    else:
        source_block = get_controlled_current_source_emt_template(
            vf=vf,
            phN=False,
            phA=True,
            phB=False,
            phC=False,
            frequency_hz=frequency_hz,
            phase_angle_deg=dict({"A": 0.0}),
            offset_values=dict({"A": 0.0}),
            name=case_name,
        ).block

    source_current: Var = source_block.out_vars[0]
    source_block.update_model(source_block.in_vars[0], bus_voltage)
    source_block.update_model(source_block.in_vars[1], amplitude_command)

    root_block: Block = Block(
        name=case_name,
        state_vars=list([amplitude_command]),
        diff_vars=list([d_amplitude_command]),
        state_eqs=list([Const(float(controller_bandwidth)) * (amplitude_reference - amplitude_command)]),
        algebraic_vars=list([bus_voltage, load_current]),
        algebraic_eqs=list([
            source_current + load_current,
            load_current + Const(float(load_conductance)) * bus_voltage,
        ]),
        children=list([source_block]),
        init_eqs=dict({amplitude_command: Const(float(initial_amplitude)), amplitude_reference: Const(float(initial_amplitude)), bus_voltage: Const(0.0), load_current: Const(0.0)}),
        event_dict=dict({amplitude_reference: Const(float(initial_amplitude), name=amplitude_reference.name)}),
    )
    root_block.unify_blocks()

    grid: MultiCircuit = MultiCircuit()
    event_group: EmtEventsGroup = EmtEventsGroup(name=f"{case_name}_events")
    grid.add_emt_events_group(event_group)
    grid.add_emt_event(
        EmtEvent(
            parameter=amplitude_reference,
            time=CONTROLLED_SOURCE_EVENT_TIME_S,
            value=float(stepped_amplitude),
            group=event_group,
            force_step_alignment=True,
            transition_type=DynamicEventTransitionType.Step,
            name=f"{case_name}_amplitude_step",
        )
    )

    problem: ControlledSourceEmtDemoProblem = ControlledSourceEmtDemoProblem(grid=grid, sys_block=root_block, glob_time=glob_time)
    problem.set_events_group(event_group)
    output_dir: Path = get_plot_results_directory("controlled_source_emt", "symbolic")
    png_path: Path = output_dir / f"{case_name}.png"
    return problem, amplitude_reference, amplitude_command, bus_voltage, source_current, load_current, png_path


def run_controlled_source_case(case_name: str,
                               voltage_source: bool,
                               initial_amplitude: float,
                               stepped_amplitude: float,
                               enable_plots: bool = True) -> ControlledSourceEmtCaseResult:
    """
    Run one controlled EMT source case and export one PNG.

    :param case_name: Case identifier.
    :param voltage_source: Whether the source is voltage-driven.
    :param initial_amplitude: Initial sinusoidal amplitude.
    :param stepped_amplitude: Amplitude reference after the event.
    :param enable_plots: Whether to show the figure.
    :return: Exported case result.
    """
    problem, amplitude_reference, amplitude_command, bus_voltage, source_current, load_current, png_path = _build_controlled_source_case_problem(
        case_name=case_name,
        voltage_source=voltage_source,
        initial_amplitude=initial_amplitude,
        stepped_amplitude=stepped_amplitude,
    )
    solver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=CONTROLLED_SOURCE_END_TIME_S,
        h=1.0e-4,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False,
    )
    time_values, state_history, _diff_history, _converged, _diag = solver.simulate(boundary_updater=None)
    amplitude_reference_trace = np.asarray([problem.def_event_params_fn(problem.event_params_values.copy(), float(tm))[0] for tm in time_values], dtype=np.float64)
    amplitude_command_idx: int = problem.get_var_idx(amplitude_command)
    bus_voltage_idx: int = problem.get_var_idx(bus_voltage)
    source_current_idx: int = problem.get_var_idx(source_current)
    load_current_idx: int = problem.get_var_idx(load_current)

    figure, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(time_values, amplitude_reference_trace, color="tab:orange", label="Amplitude ref")
    axes[0].plot(time_values, state_history[:, amplitude_command_idx], color="tab:blue", label="Amplitude cmd")
    axes[0].axvline(CONTROLLED_SOURCE_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[0].grid(True)
    axes[0].legend()
    axes[0].set_ylabel("Amplitude [pu]")
    axes[0].set_title(case_name)

    axes[1].plot(time_values, state_history[:, bus_voltage_idx], color="tab:green", label="Bus voltage")
    axes[1].axvline(CONTROLLED_SOURCE_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
    axes[1].grid(True)
    axes[1].legend()
    axes[1].set_ylabel("Voltage [pu inst]")

    axes[2].plot(time_values, state_history[:, source_current_idx], color="tab:purple", label="Source current")
    axes[2].plot(time_values, state_history[:, load_current_idx], color="tab:red", linestyle="--", label="Load current")
    axes[2].axvline(CONTROLLED_SOURCE_EVENT_TIME_S, color="black", linestyle="--", linewidth=1.0)
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

    return ControlledSourceEmtCaseResult(
        case_name=case_name,
        time=np.asarray(time_values, dtype=np.float64),
        amplitude_reference=amplitude_reference_trace,
        amplitude_command=np.asarray(state_history[:, amplitude_command_idx], dtype=np.float64),
        bus_voltage=np.asarray(state_history[:, bus_voltage_idx], dtype=np.float64),
        source_current=np.asarray(state_history[:, source_current_idx], dtype=np.float64),
        load_current=np.asarray(state_history[:, load_current_idx], dtype=np.float64),
        png_path=png_path,
    )


def run_all_controlled_source_cases(enable_plots: bool = True) -> dict[str, ControlledSourceEmtCaseResult]:
    """
    Run the controlled current-source and controlled voltage-source EMT demos.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Case results keyed by case name.
    """
    return dict({
        "controlled_current_source_control": run_controlled_source_case(
            case_name="controlled_current_source_control",
            voltage_source=False,
            initial_amplitude=0.2,
            stepped_amplitude=0.6,
            enable_plots=enable_plots,
        ),
        "controlled_voltage_source_control": run_controlled_source_case(
            case_name="controlled_voltage_source_control",
            voltage_source=True,
            initial_amplitude=0.5,
            stepped_amplitude=1.0,
            enable_plots=enable_plots,
        ),
    })
