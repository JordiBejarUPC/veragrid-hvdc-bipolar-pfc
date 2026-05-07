# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ShuntConnectionType,
    SolverType,
)


def configure_repo_python_path() -> None:
    """
    Add repository source folders to ``sys.path`` when the file is run as a loose script.

    :return: None.
    """
    current_file: Path = Path(__file__).resolve()
    repo_root: Path = current_file.parent.parent
    src_root: Path = repo_root / "src"
    repo_root_text: str = str(repo_root)
    src_root_text: str = str(src_root)

    if src_root_text in sys.path:
        pass
    else:
        sys.path.insert(0, src_root_text)

    if repo_root_text in sys.path:
        pass
    else:
        sys.path.insert(0, repo_root_text)


def find_name_in_block(name: str, block: Block) -> Optional[Var]:
    """
    Search one symbolic variable by name inside one block hierarchy.

    :param name: Variable name to search.
    :param block: Root symbolic block.
    :return: Matching symbolic variable or ``None``.
    """
    local_var: Var
    child_block: Block
    nested_var: Optional[Var]

    for local_var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == local_var.name:
            return local_var
        else:
            pass

    for child_block in block.children:
        nested_var = find_name_in_block(name, child_block)
        if nested_var is None:
            pass
        else:
            return nested_var

    return None


def build_power_flow_options() -> PowerFlowOptions:
    """
    Build the balanced PF options used by the example.

    :return: Power-flow options.
    """
    options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-8,
        max_iter=40,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    return options


def build_emt_options() -> EmtOptions:
    """
    Build the EMT options used by the example.

    :return: EMT options.
    """
    options: EmtOptions = EmtOptions(
        time_step=5e-6,
        simulation_time=0.1,
        tolerance=1e-8,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Auto,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )
    return options


def build_two_bus_grid_with_two_slack_generators() -> Tuple[MultiCircuit, Bus, Bus, Line, Generator, Generator, Load]:
    """
    Build a two-bus EMT test system with two generators connected to the same slack bus.

    The case is designed to verify the new EMT residual-distribution logic for
    multiple source-like injections on the slack bus.

    :return: Grid, buses, line, the two generators and the remote load.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=6.0, fbase=50.0)
    vnom_kv: float = 10.0

    bus0: Bus = Bus(name="Bus0", Vnom=vnom_kv, is_slack=True)
    bus1: Bus = Bus(name="Bus1", Vnom=vnom_kv)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line: Line = Line(name="Line01", bus_from=bus0, bus_to=bus1, length=10.0, rate=900.0)
    tower: OverheadLineType = OverheadLineType(name="Tower", Vnom=vnom_kv)
    wire: Wire = Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1.0,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line.apply_template(tower, grid.Sbase, grid.fBase)
    grid.add_line(line)

    # The two generators have different nominal powers. The EMT seed logic should
    # therefore distribute the slack-bus residual according to the 1:3 ratio.
    generator_1: Generator = Generator(name="SlackGen1", vset=1.0, Snom=1.5, freq=50.0, r1=0.001, x1=1.7)
    generator_2: Generator = Generator(name="SlackGen2", vset=1.0, Snom=4.5, freq=50.0, r1=0.001, x1=1.7)
    grid.add_generator(bus=bus0, api_obj=generator_1)
    grid.add_generator(bus=bus0, api_obj=generator_2)

    load: Load = Load(
        name="RemoteLoad",
        P=3.60,
        Q=0.0,
        P1=1.20,
        P2=1.20,
        P3=1.20,
        Q1=0.0,
        Q2=0.0,
        Q3=0.0,
    )
    load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus1, api_obj=load)

    return grid, bus0, bus1, line, generator_1, generator_2, load


def attach_emt_models(
        grid: MultiCircuit,
        line: Line,
        generator_1: Generator,
        generator_2: Generator,
        load: Load,
) -> Tuple[Block, Block, Block, Block]:
    """
    Attach EMT templates to all devices of the test case.

    :param grid: Grid model.
    :param line: Transmission line.
    :param generator_1: First generator.
    :param generator_2: Second generator.
    :param load: Remote load.
    :return: Line, the two generator and the load EMT blocks.
    """
    bus: Bus

    line_block: Block = get_pi_line_emt_template(
        vf=grid.var_factory,
        phN=False,
        phA=True,
        phB=True,
        phC=True,
        name="Line01_Pi",
    ).block

    generator_1_block: Block = get_simple_generator_emt_template(
        vf=grid.var_factory,
        name="SlackGen1_SimpleEmt",
    ).block

    generator_2_block: Block = get_simple_generator_emt_template(
        vf=grid.var_factory,
        name="SlackGen2_SimpleEmt",
    ).block

    load_block: Block = get_shunt_r_emt_template(
        vf=grid.var_factory,
        phA=True,
        phB=True,
        phC=True,
    ).block

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    set_emt_model(device=line, model=line_block, var_factory=grid.var_factory)
    set_emt_model(device=generator_1, model=generator_1_block, var_factory=grid.var_factory)
    set_emt_model(device=generator_2, model=generator_2_block, var_factory=grid.var_factory)
    set_emt_model(device=load, model=load_block, var_factory=grid.var_factory)

    generator_1.emt_model.set_parameter_in_model(var_name="Kp_SlackGen1_SimpleEmt", new_value=0.02)
    generator_1.emt_model.set_parameter_in_model(var_name="Ki_SlackGen1_SimpleEmt", new_value=0.0)
    generator_1.emt_model.set_parameter_in_model(var_name="Kq_share_SlackGen1_SimpleEmt", new_value=0.000)
    generator_1.emt_model.set_parameter_in_model(var_name="D_SlackGen1_SimpleEmt", new_value=10.0)
    # generator_1.emt_model.set_parameter_in_model(var_name="Tg_SlackGen1_SimpleEmt", new_value=0.1)

    generator_2.emt_model.set_parameter_in_model(var_name="Kp_SlackGen2_SimpleEmt", new_value=0.06)
    generator_2.emt_model.set_parameter_in_model(var_name="Ki_SlackGen2_SimpleEmt", new_value=0.0)
    generator_2.emt_model.set_parameter_in_model(var_name="Kq_share_SlackGen2_SimpleEmt", new_value=0.00)
    generator_2.emt_model.set_parameter_in_model(var_name="D_SlackGen2_SimpleEmt", new_value=10.0)
    # generator_2.emt_model.set_parameter_in_model(var_name="Tg_SlackGen2_SimpleEmt", new_value=0.1)

    return line.emt_model, generator_1.emt_model, generator_2.emt_model, load.emt_model


def run_balanced_power_flow(grid: MultiCircuit) -> Any:
    """
    Run the balanced PF used to seed the EMT problem.

    :param grid: Grid model.
    :return: Balanced PF result object.
    """
    options: PowerFlowOptions = build_power_flow_options()
    driver: PowerFlowDriver = PowerFlowDriver(grid, options)
    driver.run()
    return driver.results


def build_emt_problem(grid: MultiCircuit, power_flow_results: Any) -> EmtProblemDae:
    """
    Build the EMT problem from the grid and the balanced PF result.

    :param grid: Grid model.
    :param power_flow_results: Balanced PF results.
    :return: EMT problem.
    """
    options: EmtOptions = build_emt_options()
    problem: EmtProblemDae = EmtProblemDae(
        grid=grid,
        options=options,
        pf_results_3Ph=None,
        pf_results_3ph=None,
        pf_results=power_flow_results,
    )
    return problem


def compute_expected_balanced_phase_current(power_value: complex, voltage_value: complex) -> float:
    """
    Convert one balanced phase power into the EMT instantaneous current initialization.

    :param power_value: Per-phase complex power.
    :param voltage_value: Per-phase voltage phasor.
    :return: Expected instantaneous current initialization.
    """
    current_value: complex

    if abs(voltage_value) > 1.0e-12:
        current_value = np.conj(power_value / voltage_value)
    else:
        current_value = 0.0 + 0.0j

    return float(np.sqrt(2.0) * np.imag(current_value))


def get_external_init_value(problem: EmtProblemDae, block: Block, variable_name: str) -> float:
    """
    Read one initialized EMT variable value from the global EMT state vector.

    :param problem: EMT problem.
    :param block: Device block.
    :param variable_name: Variable name inside the block hierarchy.
    :return: Initialized variable value.
    :raises ValueError: If the variable is not found.
    """
    variable: Optional[Var] = find_name_in_block(variable_name, block)
    x0: np.ndarray = problem.get_x0()
    variable_index: int

    if variable is None:
        raise ValueError(f"Variable '{variable_name}' was not found in the block '{block.name}'.")
    else:
        variable_index = problem.get_var_idx(variable)
        return float(x0[variable_index])


def assert_close(label: str, value: float, expected: float, tolerance: float) -> None:
    """
    Check one scalar numerical result.

    :param label: Human-readable check name.
    :param value: Computed value.
    :param expected: Expected value.
    :param tolerance: Absolute tolerance.
    :return: None.
    :raises ValueError: If the check fails.
    """
    error_value: float = abs(value - expected)

    if error_value <= tolerance:
        print(f"[OK] {label}: value={value:.10f}, expected={expected:.10f}, error={error_value:.3e}")
    else:
        raise ValueError(
            f"Check '{label}' failed: value={value:.10f}, expected={expected:.10f}, error={error_value:.3e}"
        )




def get_state_series(problem: EmtProblemDae, block: Block, variable_name: str, y_values: np.ndarray) -> np.ndarray:
    """
    Return one state or algebraic trajectory from the EMT state matrix.

    :param problem: EMT problem.
    :param block: Block that owns the variable.
    :param variable_name: Variable name inside the block hierarchy.
    :param y_values: EMT state trajectory matrix.
    :return: Variable trajectory.
    :raises ValueError: If the variable is not found.
    """
    variable: Optional[Var] = find_name_in_block(variable_name, block)
    variable_index: int

    if variable is None:
        raise ValueError(f"Variable '{variable_name}' was not found in the block '{block.name}'.")
    else:
        variable_index = problem.get_var_idx(variable)
        return y_values[:, variable_index]


def extract_three_phase_matrix(
        problem: EmtProblemDae,
        y_values: np.ndarray,
        variables: Tuple[Any, Any, Any],
) -> np.ndarray:
    """
    Extract one three-phase trajectory matrix from the global EMT state matrix.

    :param problem: EMT problem.
    :param y_values: EMT state trajectory matrix.
    :param variables: Three symbolic variables.
    :return: Matrix of shape ``(n_steps, 3)``.
    """
    out_matrix: np.ndarray = np.zeros((y_values.shape[0], 3), dtype=np.float64)
    phase_index: int = 0
    variable_index: int
    variable: Any

    while phase_index < 3:
        variable = variables[phase_index]
        variable_index = problem.get_var_idx(variable)
        out_matrix[:, phase_index] = y_values[:, variable_index]
        phase_index += 1

    return out_matrix


def save_two_panel_three_phase_plot(
        file_path: Path,
        time_values: np.ndarray,
        top_triplet: Tuple[np.ndarray, np.ndarray, np.ndarray],
        top_title: str,
        top_ylabel: str,
        top_legend_prefix: str,
        bottom_triplet: Tuple[np.ndarray, np.ndarray, np.ndarray],
        bottom_title: str,
        bottom_ylabel: str,
        bottom_legend_prefix: str,
) -> Path:
    """
    Save one two-panel three-phase plot.

    :param file_path: Output file path.
    :param time_values: Time vector.
    :param top_triplet: Top-panel three-phase signals.
    :param top_title: Top-panel title.
    :param top_ylabel: Top-panel y label.
    :param top_legend_prefix: Top-panel legend prefix.
    :param bottom_triplet: Bottom-panel three-phase signals.
    :param bottom_title: Bottom-panel title.
    :param bottom_ylabel: Bottom-panel y label.
    :param bottom_legend_prefix: Bottom-panel legend prefix.
    :return: Saved file path.
    """
    figure: plt.Figure
    axes: np.ndarray

    figure, axes = plt.subplots(2, 1, figsize=(11.0, 7.0), sharex=True)

    axes[0].plot(time_values, top_triplet[0], label=f"{top_legend_prefix} A")
    axes[0].plot(time_values, top_triplet[1], label=f"{top_legend_prefix} B")
    axes[0].plot(time_values, top_triplet[2], label=f"{top_legend_prefix} C")
    axes[0].set_title(top_title)
    axes[0].set_ylabel(top_ylabel)
    axes[0].grid(True)
    axes[0].legend(loc='upper left')


    axes[1].plot(time_values, bottom_triplet[0], label=f"{bottom_legend_prefix} A")
    axes[1].plot(time_values, bottom_triplet[1], label=f"{bottom_legend_prefix} B")
    axes[1].plot(time_values, bottom_triplet[2], label=f"{bottom_legend_prefix} C")
    axes[1].set_title(bottom_title)
    axes[1].set_xlabel('Time [s]')
    axes[1].set_ylabel(bottom_ylabel)
    axes[1].grid(True)
    axes[1].legend(loc='upper left')

    figure.tight_layout()
    figure.savefig(file_path, dpi=200)
    plt.show()
    plt.close(figure)
    return file_path


def save_line_internal_currents_plot(
        file_path: Path,
        time_values: np.ndarray,
        series_currents: np.ndarray,
        from_shunt_currents: np.ndarray,
        to_shunt_currents: np.ndarray,
) -> Path:
    """
    Save one line-internal-current plot analogous to the base EMT demo.

    :param file_path: Output file path.
    :param time_values: Time vector.
    :param series_currents: Series-current matrix.
    :param from_shunt_currents: Sending-end shunt-current matrix.
    :param to_shunt_currents: Receiving-end shunt-current matrix.
    :return: Saved file path.
    """
    figure: plt.Figure
    axes: np.ndarray

    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.0), sharex=True)

    axes[0, 0].plot(time_values, series_currents[:, 0], label='Series A')
    axes[0, 0].plot(time_values, series_currents[:, 1], label='Series B')
    axes[0, 0].plot(time_values, series_currents[:, 2], label='Series C')
    axes[0, 0].set_title('Line Series Currents')
    axes[0, 0].set_ylabel('Current [pu]')
    axes[0, 0].grid(True)
    axes[0, 0].legend(loc='upper left')

    axes[1, 0].plot(time_values, from_shunt_currents[:, 0], label='From shunt A')
    axes[1, 0].plot(time_values, from_shunt_currents[:, 1], label='From shunt B')
    axes[1, 0].plot(time_values, from_shunt_currents[:, 2], label='From shunt C')
    axes[1, 0].set_title('Line From-End Shunt Currents')
    axes[1, 0].set_xlabel('Time [s]')
    axes[1, 0].set_ylabel('Current [pu]')
    axes[1, 0].grid(True)
    axes[1, 0].legend(loc='upper left')

    axes[1, 1].plot(time_values, to_shunt_currents[:, 0], label='To shunt A')
    axes[1, 1].plot(time_values, to_shunt_currents[:, 1], label='To shunt B')
    axes[1, 1].plot(time_values, to_shunt_currents[:, 2], label='To shunt C')
    axes[1, 1].set_title('Line To-End Shunt Currents')
    axes[1, 1].set_xlabel('Time [s]')
    axes[1, 1].set_ylabel('Current [pu]')
    axes[1, 1].grid(True)
    axes[1, 1].legend(loc='upper left')

    axes[0, 1].axis('off')

    figure.tight_layout()
    figure.savefig(file_path, dpi=200)
    plt.show()
    plt.close(figure)
    return file_path


def save_phase_a_split_plot(
        file_path: Path,
        time_values: np.ndarray,
        first_current: np.ndarray,
        second_current: np.ndarray,
        first_label: str,
        second_label: str,
        total_label: str,
        title: str,
) -> Path:
    """
    Save one phase-A split-current plot for duplicated devices on the same bus.

    :param file_path: Output file path.
    :param time_values: Time vector.
    :param first_current: First current trajectory.
    :param second_current: Second current trajectory.
    :param first_label: First curve label.
    :param second_label: Second curve label.
    :param total_label: Total curve label.
    :param title: Plot title.
    :return: Saved file path.
    """
    total_current: np.ndarray = first_current + second_current
    figure: plt.Figure
    axis: plt.Axes

    figure, axis = plt.subplots(figsize=(10.0, 5.0))
    axis.plot(time_values, first_current, label=first_label)
    axis.plot(time_values, second_current, label=second_label)
    axis.plot(time_values, total_current, label=total_label, linestyle='--')
    axis.set_xlabel('Time [s]')
    axis.set_ylabel('Current [pu]')
    axis.set_title(title)
    axis.grid(True)
    axis.legend(loc='upper left')

    figure.tight_layout()
    figure.savefig(file_path, dpi=200)
    plt.show()
    plt.close(figure)
    return file_path


def export_plots_two_slack_generators_same_bus(
        problem: EmtProblemDae,
        time_values: np.ndarray,
        y_values: np.ndarray,
        bus0: Bus,
        bus1: Bus,
        line_block: Block,
        generator_1_block: Block,
        generator_2_block: Block,
        load_block: Block,
) -> List[Path]:
    """
    Export diagnostic plots for the two-slack-generators same-bus example.

    The exported plots follow the same visual structure as the reference EMT demo:
    bus voltages, source/load currents and line internal currents. An additional
    phase-A split plot is also exported to make the duplicated-generator behaviour
    explicit.

    :param problem: EMT problem.
    :param time_values: Time vector.
    :param y_values: EMT state trajectory matrix.
    :param bus0: Slack bus.
    :param bus1: Remote bus.
    :param line_block: Line EMT block.
    :param generator_1_block: First generator EMT block.
    :param generator_2_block: Second generator EMT block.
    :param load_block: Load EMT block.
    :return: Saved plot paths.
    """
    output_directory: Path = Path(__file__).resolve().parent / 'plot_results' / 'emt_two_slack_generators_same_bus_balanced'
    paths: List[Path] = list()

    bus0_voltages: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(bus0.emt_model.out_vars[:3]))
    bus1_voltages: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(bus1.emt_model.out_vars[:3]))

    generator_1_currents: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(generator_1_block.out_vars[:3]))
    generator_2_currents: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(generator_2_block.out_vars[:3]))
    total_generator_currents: np.ndarray = generator_1_currents + generator_2_currents

    load_currents: np.ndarray = -np.column_stack((
        get_state_series(problem, load_block, 'i_A_R_shunt_3ph', y_values),
        get_state_series(problem, load_block, 'i_B_R_shunt_3ph', y_values),
        get_state_series(problem, load_block, 'i_C_R_shunt_3ph', y_values),
    ))

    line_series_currents: np.ndarray = np.column_stack((
        get_state_series(problem, line_block, 'i_ser_Line01_Pi_A', y_values),
        get_state_series(problem, line_block, 'i_ser_Line01_Pi_B', y_values),
        get_state_series(problem, line_block, 'i_ser_Line01_Pi_C', y_values),
    ))
    line_from_shunt_currents: np.ndarray = np.column_stack((
        get_state_series(problem, line_block, 'i_cap_f_Line01_Pi_A', y_values),
        get_state_series(problem, line_block, 'i_cap_f_Line01_Pi_B', y_values),
        get_state_series(problem, line_block, 'i_cap_f_Line01_Pi_C', y_values),
    ))
    line_to_shunt_currents: np.ndarray = np.column_stack((
        get_state_series(problem, line_block, 'i_cap_t_Line01_Pi_A', y_values),
        get_state_series(problem, line_block, 'i_cap_t_Line01_Pi_B', y_values),
        get_state_series(problem, line_block, 'i_cap_t_Line01_Pi_C', y_values),
    ))

    output_directory.mkdir(parents=True, exist_ok=True)

    paths.append(
        save_two_panel_three_phase_plot(
            file_path=output_directory / 'bus_voltages.png',
            time_values=time_values,
            top_triplet=(bus0_voltages[:, 0], bus0_voltages[:, 1], bus0_voltages[:, 2]),
            top_title='Bus 0 Voltages',
            top_ylabel='Voltage [pu]',
            top_legend_prefix='Bus0',
            bottom_triplet=(bus1_voltages[:, 0], bus1_voltages[:, 1], bus1_voltages[:, 2]),
            bottom_title='Bus 1 Voltages',
            bottom_ylabel='Voltage [pu]',
            bottom_legend_prefix='Bus1',
        )
    )

    paths.append(
        save_two_panel_three_phase_plot(
            file_path=output_directory / 'source_load_currents.png',
            time_values=time_values,
            top_triplet=(total_generator_currents[:, 0], total_generator_currents[:, 1], total_generator_currents[:, 2]),
            top_title='Total Slack-Generator Currents (Gen1 + Gen2)',
            top_ylabel='Current [pu]',
            top_legend_prefix='Gen',
            bottom_triplet=(load_currents[:, 0], load_currents[:, 1], load_currents[:, 2]),
            bottom_title='Remote Load Currents',
            bottom_ylabel='Current [pu]',
            bottom_legend_prefix='Load',
        )
    )

    paths.append(
        save_line_internal_currents_plot(
            file_path=output_directory / 'line_internal_currents.png',
            time_values=time_values,
            series_currents=line_series_currents,
            from_shunt_currents=line_from_shunt_currents,
            to_shunt_currents=line_to_shunt_currents,
        )
    )

    paths.append(
        save_phase_a_split_plot(
            file_path=output_directory / 'duplicated_slack_generators_phase_a_split.png',
            time_values=time_values,
            first_current=generator_1_currents[:, 0],
            second_current=generator_2_currents[:, 0],
            first_label='Gen1 i_A',
            second_label='Gen2 i_A',
            total_label='Gen1 + Gen2 i_A',
            title='Duplicated Slack Generators on Bus 0: Phase-A Currents',
        )
    )

    return paths


def run_short_emt_simulation(problem: EmtProblemDae) -> Tuple[np.ndarray, np.ndarray]:
    """
    Run one short EMT simulation only to verify that the case remains executable.

    :param problem: EMT problem.
    :return: Time and state trajectories.
    """
    options: EmtOptions = build_emt_options()
    solver: JitSymbolicSolver = JitSymbolicSolver(
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        method=options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=True,
    )

    solver.build_jit_kernel(options.integration_method)
    solver._build_jit_symbolic_hybrid(options.integration_method, use_sparse=True)

    if options.integration_method == DynamicIntegrationMethod.DaeTrapezoidal:
        solver.build_jit_kernel(DynamicIntegrationMethod.DaeBackEuler)
        solver._build_jit_symbolic_hybrid(DynamicIntegrationMethod.DaeBackEuler, use_sparse=True)
    else:
        pass

    boundary_updater: Any = problem
    t_values: np.ndarray
    y_values: np.ndarray
    dy_values: np.ndarray
    well_initialized: bool
    converged: bool

    t_values, y_values, dy_values, well_initialized, converged = solver.simulate(boundary_updater=boundary_updater)

    print(f"well_initialized = {well_initialized}")
    print(f"converged = {converged}")
    print(f"steps = {len(t_values) - 1}")
    print(f"state_shape = {y_values.shape}")
    print(f"diff_shape = {dy_values.shape}")

    return t_values, y_values


def main() -> None:
    """
    Execute the EMT example with two generators connected to the slack bus.

    The checks that matter are:
    1. each generator receives only its allocated share of the slack-bus residual,
    2. the 1:3 Snom ratio is visible in the initial phase-A currents,
    3. the sum of both initialized currents equals the total expected slack current,
    4. the EMT problem still simulates.

    :return: None.
    """
    configure_repo_python_path()

    grid: MultiCircuit
    bus0: Bus
    bus1: Bus
    line: Line
    generator_1: Generator
    generator_2: Generator
    load: Load
    line_block: Block
    generator_1_block: Block
    generator_2_block: Block
    load_block: Block
    power_flow_results: Any
    problem: EmtProblemDae
    slack_bus_power: complex
    slack_phase_power_total: complex
    slack_phase_power_1: complex
    slack_phase_power_2: complex
    bus_voltage_a: complex
    expected_current_1_a: float
    expected_current_2_a: float
    initialized_current_1_a: float
    initialized_current_2_a: float

    grid, bus0, bus1, line, generator_1, generator_2, load = build_two_bus_grid_with_two_slack_generators()
    line_block, generator_1_block, generator_2_block, load_block = attach_emt_models(grid, line, generator_1, generator_2, load)

    power_flow_results = run_balanced_power_flow(grid)
    print("Converged balanced power flow:", power_flow_results.converged)
    print(power_flow_results.get_bus_df())
    print(power_flow_results.get_branch_df())

    problem = build_emt_problem(grid, power_flow_results)

    # The balanced PF provides one three-phase slack-bus power. The EMT seed logic
    # must split it between the two generators according to their Snom values.
    slack_bus_power = complex(power_flow_results.Sbus[0] / grid.Sbase)
    slack_phase_power_total = slack_bus_power / 3.0
    slack_phase_power_1 = slack_phase_power_total * (float(generator_1.Snom) / (float(generator_1.Snom) + float(generator_2.Snom)))
    slack_phase_power_2 = slack_phase_power_total * (float(generator_2.Snom) / (float(generator_1.Snom) + float(generator_2.Snom)))

    bus_voltage_a = complex(power_flow_results.voltage[0])
    expected_current_1_a = compute_expected_balanced_phase_current(slack_phase_power_1, bus_voltage_a)
    expected_current_2_a = compute_expected_balanced_phase_current(slack_phase_power_2, bus_voltage_a)

    initialized_current_1_a = get_external_init_value(
        problem,
        generator_1_block,
        "i_A_SlackGen1_SimpleEmt",
    )
    initialized_current_2_a = get_external_init_value(
        problem,
        generator_2_block,
        "i_A_SlackGen2_SimpleEmt",
    )

    assert_close(
        label="Slack generator 1 phase-A EMT initialization",
        value=initialized_current_1_a,
        expected=expected_current_1_a,
        tolerance=1.0e-8,
    )
    assert_close(
        label="Slack generator 2 phase-A EMT initialization",
        value=initialized_current_2_a,
        expected=expected_current_2_a,
        tolerance=1.0e-8,
    )
    assert_close(
        label="Total slack phase-A current",
        value=initialized_current_1_a + initialized_current_2_a,
        expected=expected_current_1_a + expected_current_2_a,
        tolerance=1.0e-8,
    )
    assert_close(
        label="Slack current sharing ratio",
        value=initialized_current_2_a / initialized_current_1_a,
        expected=float(generator_2.Snom) / float(generator_1.Snom),
        tolerance=1.0e-8,
    )

    time_values: np.ndarray
    y_values: np.ndarray
    plot_paths: List[Path]

    time_values, y_values = run_short_emt_simulation(problem)
    plot_paths = export_plots_two_slack_generators_same_bus(
        problem=problem,
        time_values=time_values,
        y_values=y_values,
        bus0=bus0,
        bus1=bus1,
        line_block=line_block,
        generator_1_block=generator_1_block,
        generator_2_block=generator_2_block,
        load_block=load_block,
    )
    print('Generated plots:')
    for plot_path in plot_paths:
        print(f'  {plot_path}')


if __name__ == "__main__":
    main()
