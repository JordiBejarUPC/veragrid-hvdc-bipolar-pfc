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
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
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
    Add the repository source folders to ``sys.path`` when the script is run as a loose file.

    The example is meant to be copied under ``trunk/dynamics_emt`` of the VeraGrid
    repository. When the script is executed from an IDE, the repository roots may
    already be present in ``sys.path``. This function adds them only if they are not
    already available.

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

    The search is local to the provided block tree. This keeps the example explicit
    and avoids any global registry of symbolic variables.

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
    Build the standard PF options used by the EMT examples.

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
        simulation_time=0.05,
        tolerance=1e-8,
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )
    return options


def build_two_bus_grid_with_two_loads() -> Tuple[MultiCircuit, Bus, Bus, Line, Generator, Load, Load]:
    """
    Build a two-bus EMT test system with two loads connected to the same non-slack bus.

    The topology is intentionally minimal. The only purpose of the case is to verify
    that the EMT initialization does not assign the total bus power to every load when
    more than one injection shares the same bus.

    :return: Grid, buses, line, slack generator and the two loads.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=3.0, fbase=50.0)
    vnom_kv: float = 10.0

    # The slack bus provides the source. The second bus hosts the two injections
    # under test, namely two independent load devices.
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

    generator: Generator = Generator(name="SlackGen", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)
    grid.add_generator(bus=bus0, api_obj=generator)

    # Two different load devices are placed on the same non-slack bus.
    # The phase values are intentionally different so the 3ph PF and EMT seed
    # must preserve each load identity.
    load_1: Load = Load(
        name="Load1",
        P=0.90,
        Q=0.18,
        P1=0.30,
        P2=0.30,
        P3=0.30,
        Q1=0.06,
        Q2=0.06,
        Q3=0.06,
    )
    load_1.conn = ShuntConnectionType.GroundedStar

    load_2: Load = Load(
        name="Load2",
        P=0.60,
        Q=0.12,
        P1=0.20,
        P2=0.20,
        P3=0.20,
        Q1=0.04,
        Q2=0.04,
        Q3=0.04,
    )
    load_2.conn = ShuntConnectionType.GroundedStar

    grid.add_load(bus=bus1, api_obj=load_1)
    grid.add_load(bus=bus1, api_obj=load_2)

    return grid, bus0, bus1, line, generator, load_1, load_2


def attach_emt_models(
        grid: MultiCircuit,
        line: Line,
        generator: Generator,
        load_1: Load,
        load_2: Load,
) -> Tuple[Block, Block, Block, Block]:
    """
    Attach EMT templates to all devices of the test system.

    :param grid: Grid model.
    :param line: Transmission line.
    :param generator: Slack generator.
    :param load_1: First load.
    :param load_2: Second load.
    :return: Line, generator and the two load EMT blocks.
    """
    bus: Bus
    line_block: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True).block
    generator_block: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    load_1_block: Block = get_load_ZIP_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True, name="Load1_ZIP").block
    load_2_block: Block = get_load_ZIP_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True, name="Load2_ZIP").block

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    configure_zip_load_impedance(grid=grid, load_block=load_1_block)
    configure_zip_load_impedance(grid=grid, load_block=load_2_block)

    set_emt_model(device=line, model=line_block, var_factory=grid.var_factory)
    set_emt_model(device=generator, model=generator_block, var_factory=grid.var_factory)
    set_emt_model(device=load_1, model=load_1_block, var_factory=grid.var_factory)
    set_emt_model(device=load_2, model=load_2_block, var_factory=grid.var_factory)

    return line_block, generator_block, load_1_block, load_2_block



def configure_zip_load_impedance(grid: MultiCircuit, load_block: Block) -> None:
    """
    Configure one EMT ZIP-load block as a constant-power device.

    The ZIP template exposes the classic six ZIP coefficients through runtime
    parameters. For this validation example the static load device already defines
    the target per-phase ``P`` and ``Q`` values, so the EMT dynamic block must use
    the constant-power corner of the ZIP polynomial. This is achieved by setting

    - ``a1 = a2 = 0`` and ``a3 = 1`` for active power,
    - ``a4 = a5 = 0`` and ``a6 = 1`` for reactive power.

    :param grid: Network model providing the symbolic constant factory.
    :param load_block: ZIP EMT block to be configured.
    :return: None.
    """
    coefficient_names: List[Tuple[str, float]] = list([
        (f"a1_{load_block.name}", 1.0),
        (f"a2_{load_block.name}", 0.0),
        (f"a3_{load_block.name}", 0.0),
        (f"a4_{load_block.name}", 1.0),
        (f"a5_{load_block.name}", 0.0),
        (f"a6_{load_block.name}", 0.0),
    ])
    coefficient_index: int = 0

    while coefficient_index < len(coefficient_names):
        coefficient_name: str = coefficient_names[coefficient_index][0]
        coefficient_value: float = coefficient_names[coefficient_index][1]
        coefficient_var: Optional[Var] = find_name_in_block(coefficient_name, load_block)

        if coefficient_var is None:
            raise KeyError(f"ZIP coefficient '{coefficient_name}' was not found in block '{load_block.name}'.")
        else:
            load_block.event_dict[coefficient_var] = grid.var_factory.add_const(coefficient_value)

        coefficient_index += 1

def run_three_phase_power_flow(grid: MultiCircuit) -> Any:
    """
    Run the three-phase PF used to seed the EMT problem.

    :param grid: Grid model.
    :return: Three-phase PF result object.
    """
    options: PowerFlowOptions = build_power_flow_options()
    driver: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, options)
    driver.run()
    return driver.results


def build_emt_problem(grid: MultiCircuit, power_flow_results_3ph: Any) -> EmtProblemDae:
    """
    Build the EMT problem from the grid and the 3ph PF result.

    :param grid: Grid model.
    :param power_flow_results_3ph: Three-phase PF results.
    :return: EMT problem.
    """
    options: EmtOptions = build_emt_options()
    problem: EmtProblemDae = EmtProblemDae(
        grid=grid,
        options=options,
        pf_results_3Ph=power_flow_results_3ph,
        pf_results_3ph=power_flow_results_3ph,
        pf_results=None,
    )
    return problem


def compute_expected_phase_current(power_value: complex, voltage_value: complex) -> float:
    """
    Convert one PF complex power seed into the EMT instantaneous current initialization.

    The EMT convention used by the VeraGrid templates is
    ``i(0) = sqrt(2) * imag(I_phasor)``.

    :param power_value: Complex power seed.
    :param voltage_value: Complex phase voltage.
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
    :param block: Device block that owns the variable.
    :param variable_name: Variable name inside the block hierarchy.
    :return: Initialized variable value.
    :raises ValueError: If the variable is not found in the block.
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

    The helper keeps the plotting code explicit. Each plot requests the exact
    symbolic variable that must be visualized and then extracts that variable
    from the global EMT state matrix.

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

    The order of the returned columns follows the order of ``variables``.

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
    plt.close(figure)
    return file_path


def export_plots_two_loads_same_bus(
        problem: EmtProblemDae,
        time_values: np.ndarray,
        y_values: np.ndarray,
        bus0: Bus,
        bus1: Bus,
        line_block: Block,
        generator_block: Block,
        load_1_block: Block,
        load_2_block: Block,
) -> List[Path]:
    """
    Export diagnostic plots for the two-load same-bus example.

    The exported plots follow the same visual structure as the reference EMT demo:
    bus voltages, source/load currents and line internal currents. An additional
    phase-A split plot is also exported to make the duplicated-load behaviour
    explicit.

    :param problem: EMT problem.
    :param time_values: Time vector.
    :param y_values: EMT state trajectory matrix.
    :param bus0: Slack bus.
    :param bus1: Remote bus containing the duplicated loads.
    :param line_block: Line EMT block.
    :param generator_block: Slack generator EMT block.
    :param load_1_block: First load EMT block.
    :param load_2_block: Second load EMT block.
    :return: Saved plot paths.
    """
    output_directory: Path = Path(__file__).resolve().parent / 'plot_results' / 'emt_two_loads_same_bus_3ph'
    paths: List[Path] = list()

    bus0_voltages: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(bus0.emt_model.out_vars[:3]))
    bus1_voltages: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(bus1.emt_model.out_vars[:3]))
    generator_currents: np.ndarray = extract_three_phase_matrix(problem, y_values, tuple(generator_block.out_vars[:3]))

    load_1_currents: np.ndarray = np.column_stack((
        get_state_series(problem, load_1_block, f'i_A_{load_1_block.name}', y_values),
        get_state_series(problem, load_1_block, f'i_B_{load_1_block.name}', y_values),
        get_state_series(problem, load_1_block, f'i_C_{load_1_block.name}', y_values),
    ))
    load_2_currents: np.ndarray = np.column_stack((
        get_state_series(problem, load_2_block, f'i_A_{load_2_block.name}', y_values),
        get_state_series(problem, load_2_block, f'i_B_{load_2_block.name}', y_values),
        get_state_series(problem, load_2_block, f'i_C_{load_2_block.name}', y_values),
    ))
    total_load_currents: np.ndarray = -(load_1_currents + load_2_currents)

    line_series_currents: np.ndarray = np.column_stack((
        get_state_series(problem, line_block, 'i_ser_Pi_A', y_values),
        get_state_series(problem, line_block, 'i_ser_Pi_B', y_values),
        get_state_series(problem, line_block, 'i_ser_Pi_C', y_values),
    ))
    line_from_shunt_currents: np.ndarray = np.column_stack((
        get_state_series(problem, line_block, 'i_cap_f_Pi_A', y_values),
        get_state_series(problem, line_block, 'i_cap_f_Pi_B', y_values),
        get_state_series(problem, line_block, 'i_cap_f_Pi_C', y_values),
    ))
    line_to_shunt_currents: np.ndarray = np.column_stack((
        get_state_series(problem, line_block, 'i_cap_t_Pi_A', y_values),
        get_state_series(problem, line_block, 'i_cap_t_Pi_B', y_values),
        get_state_series(problem, line_block, 'i_cap_t_Pi_C', y_values),
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
            top_triplet=(generator_currents[:, 0], generator_currents[:, 1], generator_currents[:, 2]),
            top_title='Generator Currents',
            top_ylabel='Current [pu]',
            top_legend_prefix='Gen',
            bottom_triplet=(total_load_currents[:, 0], total_load_currents[:, 1], total_load_currents[:, 2]),
            bottom_title='Total Load Currents (Load1 + Load2)',
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
            file_path=output_directory / 'duplicated_load_phase_a_split.png',
            time_values=time_values,
            first_current=load_1_currents[:, 0],
            second_current=load_2_currents[:, 0],
            first_label='Load1 i_A',
            second_label='Load2 i_A',
            total_label='Load1 + Load2 i_A',
            title='Duplicated Loads on Bus 1: Phase-A Currents',
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
    Execute the EMT example with two loads on the same non-slack bus.

    The checks that matter are:
    1. each load gets its own PF-consistent phase-A initialization,
    2. the sum of both initialized currents equals the total expected bus load current,
    3. the EMT problem still simulates.

    :return: None.
    """
    configure_repo_python_path()

    grid: MultiCircuit
    bus0: Bus
    bus1: Bus
    line: Line
    generator: Generator
    load_1: Load
    load_2: Load
    power_flow_results_3ph: Any
    problem: EmtProblemDae
    line_block: Block
    generator_block: Block
    load_1_block: Block
    load_2_block: Block
    phase_a_voltage: complex
    expected_load_1_current_a: float
    expected_load_2_current_a: float
    expected_total_current_a: float
    initialized_load_1_current_a: float
    initialized_load_2_current_a: float

    grid, bus0, bus1, line, generator, load_1, load_2 = build_two_bus_grid_with_two_loads()
    line_block, generator_block, load_1_block, load_2_block = attach_emt_models(grid, line, generator, load_1, load_2)

    # The 3ph PF is required because the two loads are intentionally different per phase.
    power_flow_results_3ph = run_three_phase_power_flow(grid)
    print("Converged 3ph power flow:", power_flow_results_3ph.converged)
    print(power_flow_results_3ph.get_bus_df())
    print(power_flow_results_3ph.get_branch_df())

    problem = build_emt_problem(grid, power_flow_results_3ph)

    # The phase-A voltage at bus1 is the common denominator for both load seeds.
    phase_a_voltage = complex(power_flow_results_3ph.voltage_A[1])

    # Each load must be seeded with its own phase-A power, not with the total bus S_A.
    expected_load_1_current_a = compute_expected_phase_current(
        power_value=complex(-float(load_1.Pa) / grid.Sbase, -float(load_1.Qa) / grid.Sbase),
        voltage_value=phase_a_voltage,
    )
    expected_load_2_current_a = compute_expected_phase_current(
        power_value=complex(-float(load_2.Pa) / grid.Sbase, -float(load_2.Qa) / grid.Sbase),
        voltage_value=phase_a_voltage,
    )
    expected_total_current_a = expected_load_1_current_a + expected_load_2_current_a

    initialized_load_1_current_a = get_external_init_value(problem, load_1_block, f"i_A_{load_1_block.name}")
    initialized_load_2_current_a = get_external_init_value(problem, load_2_block, f"i_A_{load_2_block.name}")

    assert_close(
        label="Load1 phase-A EMT initialization",
        value=initialized_load_1_current_a,
        expected=expected_load_1_current_a,
        tolerance=1.0e-8,
    )
    assert_close(
        label="Load2 phase-A EMT initialization",
        value=initialized_load_2_current_a,
        expected=expected_load_2_current_a,
        tolerance=1.0e-8,
    )
    assert_close(
        label="Total bus1 phase-A load current",
        value=initialized_load_1_current_a + initialized_load_2_current_a,
        expected=expected_total_current_a,
        tolerance=1.0e-8,
    )

    # The final stage of the example is to prove that the fully assembled EMT case
    # still runs after allowing multiple injections on the same bus.
    time_values: np.ndarray
    y_values: np.ndarray
    plot_paths: List[Path]

    time_values, y_values = run_short_emt_simulation(problem)
    plot_paths = export_plots_two_loads_same_bus(
        problem=problem,
        time_values=time_values,
        y_values=y_values,
        bus0=bus0,
        bus1=bus1,
        line_block=line_block,
        generator_block=generator_block,
        load_1_block=load_1_block,
        load_2_block=load_2_block,
    )
    print('Generated plots:')
    for plot_path in plot_paths:
        print(f'  {plot_path}')


if __name__ == "__main__":
    main()
