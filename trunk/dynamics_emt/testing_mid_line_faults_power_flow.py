# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import sys
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

module_dir: str = os.path.dirname(__file__)
repo_root: str = os.path.abspath(os.path.join(module_dir, '..', '..'))
src_root: str = os.path.join(repo_root, 'src')

if src_root not in sys.path:
    sys.path.insert(0, src_root)
else:
    pass

if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
else:
    pass

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
from VeraGridEngine.enumerations import BranchImpedanceMode, SolverType


class BusComparison:
    """
    Store the comparison metrics for the original buses only.

    :param bus_names: Names of the original buses in comparison order.
    :param base_voltage: Base-case complex bus voltages.
    :param test_voltage: Test-case complex bus voltages.
    :param delta_voltage: Complex voltage difference.
    :param base_voltage_mag: Base-case voltage magnitudes.
    :param test_voltage_mag: Test-case voltage magnitudes.
    :param delta_voltage_mag: Voltage-magnitude difference.
    :param voltage_mag_error_pct: Voltage-magnitude percentage error.
    :param base_voltage_angle_deg: Base-case voltage angles in degrees.
    :param test_voltage_angle_deg: Test-case voltage angles in degrees.
    :param delta_voltage_angle_deg: Voltage-angle difference in degrees.
    :param voltage_angle_error_pct: Voltage-angle percentage error.
    :param base_sbus: Base-case complex injected powers.
    :param test_sbus: Test-case complex injected powers.
    :param delta_sbus: Injected-power difference.
    :param sbus_error_pct: Injected-power percentage error.
    :param equal_voltage_exactly: Exact equality flag for the voltage vector.
    :param equal_sbus_exactly: Exact equality flag for the injected-power vector.
    """

    __slots__ = (
        "bus_names",
        "bus_is_line_terminal",
        "base_voltage",
        "test_voltage",
        "delta_voltage",
        "base_voltage_mag",
        "test_voltage_mag",
        "delta_voltage_mag",
        "voltage_mag_error_pct",
        "base_voltage_angle_deg",
        "test_voltage_angle_deg",
        "delta_voltage_angle_deg",
        "voltage_angle_error_pct",
        "base_sbus",
        "test_sbus",
        "delta_sbus",
        "sbus_error_pct",
        "equal_voltage_exactly",
        "equal_sbus_exactly",
    )

    def __init__(self,
                 bus_names: np.ndarray,
                 bus_is_line_terminal: np.ndarray,
                 base_voltage: np.ndarray,
                 test_voltage: np.ndarray,
                 delta_voltage: np.ndarray,
                 base_voltage_mag: np.ndarray,
                 test_voltage_mag: np.ndarray,
                 delta_voltage_mag: np.ndarray,
                 voltage_mag_error_pct: np.ndarray,
                 base_voltage_angle_deg: np.ndarray,
                 test_voltage_angle_deg: np.ndarray,
                 delta_voltage_angle_deg: np.ndarray,
                 voltage_angle_error_pct: np.ndarray,
                 base_sbus: np.ndarray,
                 test_sbus: np.ndarray,
                 delta_sbus: np.ndarray,
                 sbus_error_pct: np.ndarray,
                 equal_voltage_exactly: bool,
                 equal_sbus_exactly: bool) -> None:
        """
        Build one bus-comparison container.

        :param bus_names: Names of the original buses in comparison order.
        :param base_voltage: Base-case complex bus voltages.
        :param test_voltage: Test-case complex bus voltages.
        :param delta_voltage: Complex voltage difference.
        :param base_voltage_mag: Base-case voltage magnitudes.
        :param test_voltage_mag: Test-case voltage magnitudes.
        :param delta_voltage_mag: Voltage-magnitude difference.
        :param voltage_mag_error_pct: Voltage-magnitude percentage error.
        :param base_voltage_angle_deg: Base-case voltage angles in degrees.
        :param test_voltage_angle_deg: Test-case voltage angles in degrees.
        :param delta_voltage_angle_deg: Voltage-angle difference in degrees.
        :param voltage_angle_error_pct: Voltage-angle percentage error.
        :param base_sbus: Base-case complex injected powers.
        :param test_sbus: Test-case complex injected powers.
        :param delta_sbus: Injected-power difference.
        :param sbus_error_pct: Injected-power percentage error.
        :param equal_voltage_exactly: Exact equality flag for the voltage vector.
        :param equal_sbus_exactly: Exact equality flag for the injected-power vector.
        :return: None.
        """
        self.bus_names = bus_names
        self.bus_is_line_terminal = bus_is_line_terminal
        self.base_voltage = base_voltage
        self.test_voltage = test_voltage
        self.delta_voltage = delta_voltage
        self.base_voltage_mag = base_voltage_mag
        self.test_voltage_mag = test_voltage_mag
        self.delta_voltage_mag = delta_voltage_mag
        self.voltage_mag_error_pct = voltage_mag_error_pct
        self.base_voltage_angle_deg = base_voltage_angle_deg
        self.test_voltage_angle_deg = test_voltage_angle_deg
        self.delta_voltage_angle_deg = delta_voltage_angle_deg
        self.voltage_angle_error_pct = voltage_angle_error_pct
        self.base_sbus = base_sbus
        self.test_sbus = test_sbus
        self.delta_sbus = delta_sbus
        self.sbus_error_pct = sbus_error_pct
        self.equal_voltage_exactly = equal_voltage_exactly
        self.equal_sbus_exactly = equal_sbus_exactly


class StudyCaseResult:
    """
    Store the metrics of one segmented-line study case.

    :param segments: Number of series line segments.
    :param converged: Power-flow convergence flag.
    :param bus_comparison: Comparison metrics on original buses.
    :param split_branch_count: Number of created split branches.
    :param split_branch_total_loss_mva: Total losses of the split branches.
    :param split_branch_total_loading_max: Maximum loading among the split branches.
    """

    __slots__ = (
        "segments",
        "converged",
        "bus_comparison",
        "split_branch_count",
        "split_branch_total_loss_mva",
        "split_branch_total_loading_max",
    )

    def __init__(self,
                 segments: int,
                 converged: bool,
                 bus_comparison: BusComparison,
                 split_branch_count: int,
                 split_branch_total_loss_mva: complex,
                 split_branch_total_loading_max: float) -> None:
        """
        Build one study-case container.

        :param segments: Number of series line segments.
        :param converged: Power-flow convergence flag.
        :param bus_comparison: Comparison metrics on original buses.
        :param split_branch_count: Number of created split branches.
        :param split_branch_total_loss_mva: Total losses of the split branches.
        :param split_branch_total_loading_max: Maximum loading among the split branches.
        :return: None.
        """
        self.segments = segments
        self.converged = converged
        self.bus_comparison = bus_comparison
        self.split_branch_count = split_branch_count
        self.split_branch_total_loss_mva = split_branch_total_loss_mva
        self.split_branch_total_loading_max = split_branch_total_loading_max


class LineStudyResult:
    """
    Store the complete set of study cases for one original line.

    :param line_index: Original line index.
    :param line_name: Original line name.
    :param bus_from_name: Sending-end bus name.
    :param bus_to_name: Receiving-end bus name.
    :param study_cases: Study cases from 2 to the maximum segment count.
    """

    __slots__ = (
        "line_index",
        "line_name",
        "bus_from_name",
        "bus_to_name",
        "study_cases",
    )

    def __init__(self,
                 line_index: int,
                 line_name: str,
                 bus_from_name: str,
                 bus_to_name: str,
                 study_cases: np.ndarray) -> None:
        """
        Build one line-study container.

        :param line_index: Original line index.
        :param line_name: Original line name.
        :param bus_from_name: Sending-end bus name.
        :param bus_to_name: Receiving-end bus name.
        :param study_cases: Study cases from 2 to the maximum segment count.
        :return: None.
        """
        self.line_index = line_index
        self.line_name = line_name
        self.bus_from_name = bus_from_name
        self.bus_to_name = bus_to_name
        self.study_cases = study_cases


def _get_default_grid_path() -> str:
    """
    Compute the default IEEE 9-bus grid path.

    :return: Absolute path to the IEEE 9-bus ``.gridcal`` file.
    """
    module_dir: str = os.path.dirname(__file__)
    repo_root: str = os.path.abspath(os.path.join(module_dir, '..', '..'))
    grid_path: str = os.path.join(repo_root, 'Grids_and_profiles', 'grids', 'IEEE 9 Bus.gridcal')
    return grid_path


def _get_output_directory_path() -> str:
    """
    Compute the output directory used to store the generated study tables.

    :return: Absolute path to the output directory.
    """
    output_directory_path: str = os.path.join(module_dir, 'mid_line_faults_testing')
    return output_directory_path


def _get_power_flow_options() -> PowerFlowOptions:
    """
    Build one deterministic power-flow configuration for the comparison study.

    The tighter tolerance helps quantify only the numerical effects introduced by
    the equivalent line partitioning rather than loose solver stopping criteria.

    :return: Configured power-flow options.
    """
    power_flow_options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=False,
        tolerance=1.0e-12,
        max_iter=50,
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
    return power_flow_options


def _run_power_flow(grid: MultiCircuit) -> Any:
    """
    Run one snapshot power flow.

    :param grid: Grid to simulate.
    :return: Power-flow results.
    """
    # The driver object encapsulates the solver execution and stores the final results.
    power_flow_options: PowerFlowOptions = _get_power_flow_options()
    power_flow_driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=power_flow_options)

    # The simulation must run before the results object contains meaningful values.
    power_flow_driver.run()

    return power_flow_driver.results


def _get_lines_array(grid: MultiCircuit) -> np.ndarray:
    """
    Copy the line collection into a fixed-size numpy object array.

    This keeps the collection size explicit and stable while the selection logic
    and reporting code inspect the line catalogue.

    :param grid: Grid to inspect.
    :return: Fixed-size line array.
    """
    line_list: list[Line] = list(grid.get_lines())
    line_count: int = len(line_list)
    lines_array: np.ndarray = np.empty(line_count, dtype=object)
    line_idx: int

    for line_idx in range(line_count):
        lines_array[line_idx] = line_list[line_idx]
    else:
        pass

    return lines_array


def _resolve_target_line_by_index(grid: MultiCircuit,
                                  line_index: int) -> tuple[int, Line | None]:
    """
    Resolve one line from the grid using one explicit index.

    Invalid selections are handled by returning ``None`` for the line instead of
    throwing an exception, so the main flow can decide how to report the issue.

    :param grid: Study grid.
    :param line_index: Explicit line index.
    :return: Tuple with the selected line index and line object or ``None``.
    """
    lines_array: np.ndarray = _get_lines_array(grid)
    line_count: int = int(lines_array.size)
    selected_index: int = -1
    selected_line: Line | None = None

    if line_count > 0:
        pass
    else:
        return selected_index, selected_line

    # The demo intentionally uses one explicit line index so the selected case is obvious in the code.
    if 0 <= line_index < line_count:
        selected_index = line_index
        selected_line = lines_array[line_index]
    else:
        selected_index = -1
        selected_line = None

    return selected_index, selected_line


def _create_auxiliary_bus(reference_line: Line,
                          segment_index: int,
                          total_segments: int) -> Bus:
    """
    Create one auxiliary bus used to chain the line segments.

    The auxiliary bus inherits the electrical base values of the original line
    corridor so that the equivalent topology remains compatible with the branch.

    :param reference_line: Original line being divided.
    :param segment_index: Internal auxiliary-bus index.
    :param total_segments: Number of equivalent series segments.
    :return: Newly created bus.
    """
    auxiliary_bus: Bus = Bus(
        name=f"{reference_line.name} split bus {segment_index}/{total_segments}",
        Vnom=reference_line.bus_from.Vnom,
        vmin=reference_line.bus_from.Vmin,
        vmax=reference_line.bus_from.Vmax,
        voltage_level=reference_line.bus_from.voltage_level,
    )
    return auxiliary_bus


def _copy_original_bus_names(grid: MultiCircuit) -> np.ndarray:
    """
    Copy the original bus names into a fixed-size numpy object array.

    The comparison stage later uses this array to ignore the auxiliary buses that
    are created only for the segmented equivalent topology.

    :param grid: Base grid before inserting auxiliary buses.
    :return: Fixed-size array of original bus names.
    """
    bus_count: int = len(grid.buses)
    bus_names: np.ndarray = np.empty(bus_count, dtype=object)
    bus_idx: int

    for bus_idx in range(bus_count):
        bus_names[bus_idx] = grid.buses[bus_idx].name
    else:
        pass

    return bus_names


def _build_segmented_grid(base_grid_path: str,
                          target_line_index: int,
                          total_segments: int) -> tuple[MultiCircuit, np.ndarray]:
    """
    Load the base grid and replace one line by a series chain of equal segments.

    The algorithm keeps the same total series impedance and shunt susceptance by
    scaling each created line section by ``1 / total_segments``.

    :param base_grid_path: Source grid file path.
    :param target_line_index: Index of the line to replace.
    :param total_segments: Number of equal series PI lines.
    :return: Tuple with the modified grid and the original bus names.
    """
    grid: MultiCircuit = gce.open_file(base_grid_path)
    original_bus_names: np.ndarray = _copy_original_bus_names(grid)
    lines_array: np.ndarray = _get_lines_array(grid)
    target_line: Line = lines_array[target_line_index]
    segment_scale: float = 1.0 / float(total_segments)
    bus_chain: np.ndarray = np.empty(total_segments + 1, dtype=object)
    segment_idx: int

    # The chain starts at the original sending bus and ends at the original receiving bus.
    bus_chain[0] = target_line.bus_from
    bus_chain[total_segments] = target_line.bus_to

    # The internal buses are created first so the split branches can be connected in order.
    for segment_idx in range(1, total_segments):
        auxiliary_bus: Bus = _create_auxiliary_bus(target_line, segment_idx, total_segments)
        grid.add_bus(auxiliary_bus)
        bus_chain[segment_idx] = auxiliary_bus
    else:
        pass

    # Each new line receives one equal fraction of the original electrical parameters.
    for segment_idx in range(total_segments):
        segment_line: Line = Line(
            name=f"{target_line.name} split {segment_idx + 1}/{total_segments}",
            bus_from=bus_chain[segment_idx],
            bus_to=bus_chain[segment_idx + 1],
            r=target_line.R * segment_scale,
            x=target_line.X * segment_scale,
            b=target_line.B * segment_scale,
            r0=target_line.R0 * segment_scale,
            x0=target_line.X0 * segment_scale,
            b0=target_line.B0 * segment_scale,
            r2=target_line.R2 * segment_scale,
            x2=target_line.X2 * segment_scale,
            b2=target_line.B2 * segment_scale,
            length=target_line.length * segment_scale,
            rate=target_line.rate,
            active=target_line.active,
            tolerance=target_line.tolerance,
            cost=target_line.Cost,
            mttf=target_line.mttf,
            mttr=target_line.mttr,
            r_fault=target_line.r_fault,
            x_fault=target_line.x_fault,
            fault_pos=target_line.fault_pos,
            temp_base=target_line.temp_base,
            temp_oper=target_line.temp_oper,
            alpha=target_line.alpha,
            template=target_line.template,
            contingency_factor=target_line.contingency_factor,
            protection_rating_factor=target_line.protection_rating_factor,
            contingency_enabled=target_line.contingency_enabled,
            monitor_loading=target_line.monitor_loading,
            capex=target_line.capex,
            opex=target_line.opex,
            build_status=target_line.build_status,
        )
        grid.add_line(segment_line)
    else:
        pass

    # The original branch is removed so only the equivalent segmented representation remains.
    grid.delete_line(target_line)

    return grid, original_bus_names


def _get_bus_indices_by_name(names: np.ndarray, selected_names: np.ndarray) -> np.ndarray:
    """
    Map one ordered list of bus names to indices in one results vector.

    A name-to-index dictionary is acceptable here because the task is a strict
    lookup problem and the mapping is local to the comparison stage.

    :param names: Available result bus names.
    :param selected_names: Required bus names, preserving order.
    :return: Array of indices.
    """
    lookup: dict[str, int] = dict()
    name_count: int = int(names.size)
    selected_count: int = int(selected_names.size)
    selected_indices: np.ndarray = np.empty(selected_count, dtype=int)
    name_idx: int
    selected_idx: int

    # The lookup is built once so the ordered remapping stays linear for the selected buses.
    for name_idx in range(name_count):
        lookup[str(names[name_idx])] = name_idx
    else:
        pass

    # The ordered original-bus subset must be preserved so both cases are compared bus by bus.
    for selected_idx in range(selected_count):
        selected_name: str = str(selected_names[selected_idx])
        mapped_index: int | None = lookup.get(selected_name, None)
        if mapped_index is not None:
            selected_indices[selected_idx] = mapped_index
        else:
            selected_indices[selected_idx] = -1
    else:
        pass

    return selected_indices


def _all_indices_are_valid(indices: np.ndarray) -> bool:
    """
    Check whether all indices are valid non-negative positions.

    :param indices: Array of indices.
    :return: ``True`` when all indices are valid.
    """
    index_count: int = int(indices.size)
    index_idx: int

    for index_idx in range(index_count):
        if int(indices[index_idx]) >= 0:
            pass
        else:
            return False
    else:
        pass

    return True


def _compute_percentage_error(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """
    Compute one absolute percentage error vector with safe zero-denominator handling.

    :param numerator: Error numerator vector.
    :param denominator: Reference denominator vector.
    :return: Percentage error vector.
    """
    value_count: int = int(numerator.size)
    percentage_error: np.ndarray = np.empty(value_count, dtype=float)
    value_idx: int

    # Each percentage error is computed independently so zero-valued references remain well defined.
    for value_idx in range(value_count):
        reference_value: float = float(np.abs(denominator[value_idx]))
        delta_value: float = float(np.abs(numerator[value_idx]))

        if reference_value > 0.0:
            percentage_error[value_idx] = 100.0 * delta_value / reference_value
        else:
            if delta_value > 0.0:
                percentage_error[value_idx] = np.inf
            else:
                percentage_error[value_idx] = 0.0
    else:
        pass

    return percentage_error


def _build_line_terminal_flags(bus_names: np.ndarray,
                               line_bus_from_name: str,
                               line_bus_to_name: str) -> np.ndarray:
    """
    Mark which compared buses are terminals of the line currently being split.

    :param bus_names: Bus names in comparison order.
    :param line_bus_from_name: Name of the sending-end bus of the original line.
    :param line_bus_to_name: Name of the receiving-end bus of the original line.
    :return: Boolean flag array marking the terminal buses.
    """
    bus_count: int = int(bus_names.size)
    terminal_flags: np.ndarray = np.zeros(bus_count, dtype=bool)
    bus_idx: int

    # The terminal flags make the two buses directly connected to the studied line easy to spot in the tables.
    for bus_idx in range(bus_count):
        bus_name: str = str(bus_names[bus_idx])
        if bus_name == line_bus_from_name or bus_name == line_bus_to_name:
            terminal_flags[bus_idx] = True
        else:
            terminal_flags[bus_idx] = False
    else:
        pass

    return terminal_flags


def _safe_file_name_fragment(text: str) -> str:
    """
    Convert one free-form label into a filesystem-safe file-name fragment.

    :param text: Original text.
    :return: Sanitized file-name fragment.
    """
    safe_chars: list[str] = list()
    char_idx: int
    char_count: int = len(text)

    # The file name keeps readable alphanumeric content and replaces the rest by underscores.
    for char_idx in range(char_count):
        character: str = text[char_idx]
        if character.isalnum():
            safe_chars.append(character)
        else:
            if character in (' ', '-', '_'):
                safe_chars.append('_')
            else:
                safe_chars.append('_')
    else:
        pass

    safe_fragment: str = ''.join(safe_chars).strip('_')

    if len(safe_fragment) > 0:
        pass
    else:
        safe_fragment = 'line'

    return safe_fragment


def _sanitize_matrix_for_plotting(values: np.ndarray) -> np.ndarray:
    """
    Replace non-finite values before plotting one matrix as a heatmap.

    :param values: Matrix to sanitize.
    :return: Sanitized matrix.
    """
    sanitized_values: np.ndarray = np.array(values, dtype=float, copy=True)
    finite_mask: np.ndarray = np.isfinite(sanitized_values)

    # Non-finite percentage errors are mapped to zero for plotting stability and will still be visible in the labels.
    if bool(np.any(finite_mask)):
        pass
    else:
        sanitized_values.fill(0.0)
        return sanitized_values

    sanitized_values[~finite_mask] = 0.0
    return sanitized_values


def _compute_bus_comparison(reference_results: Any,
                            candidate_results: Any,
                            original_bus_names: np.ndarray,
                            line_bus_from_name: str,
                            line_bus_to_name: str) -> BusComparison:
    """
    Compare bus-level power-flow outputs only on the original buses.

    The auxiliary buses are intentionally excluded because the invariance claim is
    about the physical equivalence seen from the original network nodes.

    :param reference_results: Base-case power-flow results.
    :param candidate_results: Segmented-line case results.
    :param original_bus_names: Names of the buses that existed before inserting auxiliaries.
    :param line_bus_from_name: Sending-end bus name of the split line.
    :param line_bus_to_name: Receiving-end bus name of the split line.
    :return: Comparison metrics.
    """
    ref_bus_names: np.ndarray = np.asarray(reference_results.bus_names, dtype=object)
    cand_bus_names: np.ndarray = np.asarray(candidate_results.bus_names, dtype=object)
    ref_indices: np.ndarray = _get_bus_indices_by_name(ref_bus_names, original_bus_names)
    cand_indices: np.ndarray = _get_bus_indices_by_name(cand_bus_names, original_bus_names)

    # If one original bus cannot be recovered in the results, the comparison returns a safe mismatch state.
    if _all_indices_are_valid(ref_indices) and _all_indices_are_valid(cand_indices):
        pass
    else:
        bus_count: int = int(original_bus_names.size)
        empty_real: np.ndarray = np.full(bus_count, np.inf, dtype=float)
        empty_complex: np.ndarray = np.full(bus_count, np.inf + 0.0j, dtype=complex)
        terminal_flags: np.ndarray = _build_line_terminal_flags(original_bus_names, line_bus_from_name, line_bus_to_name)
        return BusComparison(
            bus_names=original_bus_names.copy(),
            bus_is_line_terminal=terminal_flags,
            base_voltage=empty_complex.copy(),
            test_voltage=empty_complex.copy(),
            delta_voltage=empty_complex.copy(),
            base_voltage_mag=empty_real.copy(),
            test_voltage_mag=empty_real.copy(),
            delta_voltage_mag=empty_real.copy(),
            voltage_mag_error_pct=empty_real.copy(),
            base_voltage_angle_deg=empty_real.copy(),
            test_voltage_angle_deg=empty_real.copy(),
            delta_voltage_angle_deg=empty_real.copy(),
            voltage_angle_error_pct=empty_real.copy(),
            base_sbus=empty_complex.copy(),
            test_sbus=empty_complex.copy(),
            delta_sbus=empty_complex.copy(),
            sbus_error_pct=empty_real.copy(),
            equal_voltage_exactly=False,
            equal_sbus_exactly=False,
        )

    bus_names: np.ndarray = original_bus_names.copy()
    terminal_flags = _build_line_terminal_flags(bus_names, line_bus_from_name, line_bus_to_name)
    ref_voltage: np.ndarray = reference_results.voltage[ref_indices]
    cand_voltage: np.ndarray = candidate_results.voltage[cand_indices]
    ref_sbus: np.ndarray = reference_results.Sbus[ref_indices]
    cand_sbus: np.ndarray = candidate_results.Sbus[cand_indices]

    # ``max |dV|`` was the absolute magnitude of the complex phasor difference ``|V_test - V_base|``.
    # ``max |d|V||`` was only the difference of voltage magnitudes ``||V_test| - |V_base||``.
    # The detailed vectors below preserve both viewpoints bus by bus instead of collapsing them to one scalar.
    voltage_delta: np.ndarray = cand_voltage - ref_voltage
    sbus_delta: np.ndarray = cand_sbus - ref_sbus
    ref_voltage_mag: np.ndarray = np.abs(ref_voltage)
    cand_voltage_mag: np.ndarray = np.abs(cand_voltage)
    voltage_mag_delta: np.ndarray = cand_voltage_mag - ref_voltage_mag
    ref_voltage_angle_deg: np.ndarray = np.rad2deg(np.angle(ref_voltage))
    cand_voltage_angle_deg: np.ndarray = np.rad2deg(np.angle(cand_voltage))
    voltage_angle_delta_deg: np.ndarray = cand_voltage_angle_deg - ref_voltage_angle_deg
    voltage_mag_error_pct: np.ndarray = _compute_percentage_error(voltage_mag_delta, ref_voltage_mag)
    voltage_angle_error_pct: np.ndarray = _compute_percentage_error(voltage_angle_delta_deg, ref_voltage_angle_deg)
    sbus_error_pct: np.ndarray = _compute_percentage_error(sbus_delta, ref_sbus)

    comparison: BusComparison = BusComparison(
        bus_names=bus_names,
        bus_is_line_terminal=terminal_flags,
        base_voltage=ref_voltage,
        test_voltage=cand_voltage,
        delta_voltage=voltage_delta,
        base_voltage_mag=ref_voltage_mag,
        test_voltage_mag=cand_voltage_mag,
        delta_voltage_mag=voltage_mag_delta,
        voltage_mag_error_pct=voltage_mag_error_pct,
        base_voltage_angle_deg=ref_voltage_angle_deg,
        test_voltage_angle_deg=cand_voltage_angle_deg,
        delta_voltage_angle_deg=voltage_angle_delta_deg,
        voltage_angle_error_pct=voltage_angle_error_pct,
        base_sbus=ref_sbus,
        test_sbus=cand_sbus,
        delta_sbus=sbus_delta,
        sbus_error_pct=sbus_error_pct,
        equal_voltage_exactly=bool(np.array_equal(cand_voltage, ref_voltage)),
        equal_sbus_exactly=bool(np.array_equal(cand_sbus, ref_sbus)),
    )
    return comparison


def _collect_split_branch_indices(results: Any, split_branch_name_prefix: str) -> np.ndarray:
    """
    Collect the indices of all split branches created for one study case.

    :param results: Power-flow results.
    :param split_branch_name_prefix: Prefix used when creating the split branches.
    :return: Array of matching branch indices.
    """
    branch_names: np.ndarray = np.asarray(results.branch_names, dtype=object)
    branch_count: int = int(branch_names.size)
    match_flags: np.ndarray = np.zeros(branch_count, dtype=bool)
    branch_idx: int
    match_count: int = 0

    # A first pass counts matches and records them without resizing containers repeatedly.
    for branch_idx in range(branch_count):
        branch_name: str = str(branch_names[branch_idx])
        if branch_name.startswith(split_branch_name_prefix):
            match_flags[branch_idx] = True
            match_count += 1
        else:
            match_flags[branch_idx] = False
    else:
        pass

    matching_indices: np.ndarray = np.empty(match_count, dtype=int)
    write_idx: int = 0

    # A second pass writes the exact matching indices into a fixed-size result array.
    for branch_idx in range(branch_count):
        if bool(match_flags[branch_idx]):
            matching_indices[write_idx] = branch_idx
            write_idx += 1
        else:
            pass
    else:
        pass

    return matching_indices


def _compute_split_branch_metrics(results: Any,
                                  split_branch_name_prefix: str) -> tuple[int, complex, float]:
    """
    Aggregate branch metrics for the inserted series segments.

    :param results: Power-flow results.
    :param split_branch_name_prefix: Prefix used when creating the split branches.
    :return: Tuple with branch count, total losses, and max loading.
    """
    split_indices: np.ndarray = _collect_split_branch_indices(results, split_branch_name_prefix)
    split_count: int = int(split_indices.size)

    if split_count > 0:
        pass
    else:
        return 0, 0.0 + 0.0j, 0.0

    # The aggregate losses and loading summarize the internal behavior of the equivalent chain.
    split_losses: np.ndarray = results.Sf[split_indices] + results.St[split_indices]
    split_loading: np.ndarray = np.abs(results.loading[split_indices])
    total_losses: complex = complex(np.sum(split_losses))
    max_loading: float = float(np.max(split_loading))

    return split_count, total_losses, max_loading


def _run_segment_study(base_grid_path: str,
                       target_line_index: int,
                       reference_results: Any,
                       original_bus_names: np.ndarray,
                       original_line_name: str,
                       line_bus_from_name: str,
                       line_bus_to_name: str,
                       total_segments: int) -> StudyCaseResult:
    """
    Run one segmented-line equivalence case.

    :param base_grid_path: Source grid file path.
    :param target_line_index: Line index to split.
    :param reference_results: Original power-flow results.
    :param original_bus_names: Original bus names.
    :param original_line_name: Name of the line being replaced.
    :param line_bus_from_name: Sending-end bus name of the split line.
    :param line_bus_to_name: Receiving-end bus name of the split line.
    :param total_segments: Number of series segments.
    :return: Study metrics for the case.
    """
    # A fresh grid is loaded for every segmentation count so cases remain independent.
    segmented_grid: MultiCircuit
    ignored_original_bus_names: np.ndarray
    segmented_grid, ignored_original_bus_names = _build_segmented_grid(base_grid_path, target_line_index, total_segments)

    # The segmented grid is solved independently and then compared with the base solution.
    segmented_results: Any = _run_power_flow(segmented_grid)
    bus_comparison: BusComparison = _compute_bus_comparison(
        reference_results,
        segmented_results,
        original_bus_names,
        line_bus_from_name,
        line_bus_to_name,
    )
    split_branch_count: int
    split_branch_total_loss_mva: complex
    split_branch_total_loading_max: float
    split_branch_count, split_branch_total_loss_mva, split_branch_total_loading_max = _compute_split_branch_metrics(
        segmented_results,
        split_branch_name_prefix=f"{original_line_name} split ",
    )

    # The case result groups all outputs that belong to one segmentation count.
    study_case_result: StudyCaseResult = StudyCaseResult(
        segments=total_segments,
        converged=bool(segmented_results.converged),
        bus_comparison=bus_comparison,
        split_branch_count=split_branch_count,
        split_branch_total_loss_mva=split_branch_total_loss_mva,
        split_branch_total_loading_max=split_branch_total_loading_max,
    )
    return study_case_result


def _print_results(original_line_name: str,
                   target_line_index: int,
                   study_results: np.ndarray) -> None:
    """
    Print one detailed report for all segmented cases.

    :param original_line_name: Studied line name.
    :param target_line_index: Studied line index.
    :param study_results: Study results from 2 to ``max_segments``.
    :return: None.
    """
    result_count: int = int(study_results.size)
    result_idx: int

    print(f"Studied line [{target_line_index}] {original_line_name}")

    # The report is ordered by segment count so numerical drift can be inspected progressively.
    for result_idx in range(result_count):
        result: StudyCaseResult = study_results[result_idx]
        comparison: BusComparison = result.bus_comparison
        bus_count: int = int(comparison.bus_names.size)
        bus_idx: int

        print(
            f"  Segments={result.segments}, "
            f"Converged={result.converged}, "
            f"ExactVoltage={comparison.equal_voltage_exactly}, "
            f"ExactSbus={comparison.equal_sbus_exactly}, "
            f"SplitBranches={result.split_branch_count}, "
            f"SplitLosses={result.split_branch_total_loss_mva.real:.6e}+{result.split_branch_total_loss_mva.imag:.6e}j, "
            f"MaxSplitLoading={result.split_branch_total_loading_max:.6e}"
        )
        print("    Terminal buses of the compared line are marked with '*'.")
        print("    Voltage magnitude comparison:")
        print("      bus | mark | base [p.u.] | test [p.u.] | diff [p.u.] | error [%]")

        for bus_idx in range(bus_count):
            terminal_mark: str = "*" if bool(comparison.bus_is_line_terminal[bus_idx]) else " "
            print(
                f"      {str(comparison.bus_names[bus_idx]):>6s} | "
                f"  {terminal_mark}  | "
                f"{comparison.base_voltage_mag[bus_idx]:11.6f} | "
                f"{comparison.test_voltage_mag[bus_idx]:11.6f} | "
                f"{comparison.delta_voltage_mag[bus_idx]:+11.6e} | "
                f"{comparison.voltage_mag_error_pct[bus_idx]:9.6e}"
            )
        else:
            pass

        print("    Voltage angle comparison:")
        print("      bus | mark | base [deg] | test [deg] | diff [deg] | error [%]")

        for bus_idx in range(bus_count):
            terminal_mark = "*" if bool(comparison.bus_is_line_terminal[bus_idx]) else " "
            print(
                f"      {str(comparison.bus_names[bus_idx]):>6s} | "
                f"  {terminal_mark}  | "
                f"{comparison.base_voltage_angle_deg[bus_idx]:10.6f} | "
                f"{comparison.test_voltage_angle_deg[bus_idx]:10.6f} | "
                f"{comparison.delta_voltage_angle_deg[bus_idx]:+11.6e} | "
                f"{comparison.voltage_angle_error_pct[bus_idx]:9.6e}"
            )
        else:
            pass

        print("    Complex bus power comparison:")
        print("      bus | mark | base Sbus [MVA] | test Sbus [MVA] | diff Sbus [MVA] | error [%]")

        for bus_idx in range(bus_count):
            terminal_mark = "*" if bool(comparison.bus_is_line_terminal[bus_idx]) else " "
            print(
                f"      {str(comparison.bus_names[bus_idx]):>6s} | "
                f"  {terminal_mark}  | "
                f"{comparison.base_sbus[bus_idx].real:+10.6f}{comparison.base_sbus[bus_idx].imag:+10.6f}j | "
                f"{comparison.test_sbus[bus_idx].real:+10.6f}{comparison.test_sbus[bus_idx].imag:+10.6f}j | "
                f"{comparison.delta_sbus[bus_idx].real:+10.6e}{comparison.delta_sbus[bus_idx].imag:+10.6e}j | "
                f"{comparison.sbus_error_pct[bus_idx]:9.6e}"
            )
        else:
            pass

        print("")
    else:
        pass


def _build_global_error_matrices(line_study_results: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build the global worst-error matrices for all lines and segment counts.

    :param line_study_results: Array of per-line study results.
    :return: Tuple with segment labels and the Vmag, Vang, and Sbus error matrices.
    """
    line_count: int = int(line_study_results.size)
    segment_count: int = int(line_study_results[0].study_cases.size)
    segment_labels: np.ndarray = np.empty(segment_count, dtype=int)
    voltage_mag_error_matrix: np.ndarray = np.empty((line_count, segment_count), dtype=float)
    voltage_angle_error_matrix: np.ndarray = np.empty((line_count, segment_count), dtype=float)
    sbus_error_matrix: np.ndarray = np.empty((line_count, segment_count), dtype=float)
    line_idx: int

    # The first line defines the common segment labels because every line is tested over the same range.
    for line_idx in range(segment_count):
        segment_labels[line_idx] = int(line_study_results[0].study_cases[line_idx].segments)
    else:
        pass

    # Each cell stores the worst bus error for one line and one number of segments.
    for line_idx in range(line_count):
        line_study_result: LineStudyResult = line_study_results[line_idx]
        case_idx: int
        for case_idx in range(segment_count):
            study_case: StudyCaseResult = line_study_result.study_cases[case_idx]
            comparison: BusComparison = study_case.bus_comparison
            voltage_mag_error_matrix[line_idx, case_idx] = float(np.max(comparison.voltage_mag_error_pct))
            voltage_angle_error_matrix[line_idx, case_idx] = float(np.max(comparison.voltage_angle_error_pct))
            sbus_error_matrix[line_idx, case_idx] = float(np.max(comparison.sbus_error_pct))
        else:
            pass
    else:
        pass

    return segment_labels, voltage_mag_error_matrix, voltage_angle_error_matrix, sbus_error_matrix


def _build_line_error_matrices(line_study_result: LineStudyResult) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build the per-bus error matrices for one original line.

    :param line_study_result: Study results of one original line.
    :return: Tuple with bus names, segment labels, and the Vmag, Vang, and Sbus error matrices.
    """
    case_count: int = int(line_study_result.study_cases.size)
    first_comparison: BusComparison = line_study_result.study_cases[0].bus_comparison
    bus_names: np.ndarray = first_comparison.bus_names.copy()
    segment_labels: np.ndarray = np.empty(case_count, dtype=int)
    bus_count: int = int(bus_names.size)
    voltage_mag_error_matrix: np.ndarray = np.empty((bus_count, case_count), dtype=float)
    voltage_angle_error_matrix: np.ndarray = np.empty((bus_count, case_count), dtype=float)
    sbus_error_matrix: np.ndarray = np.empty((bus_count, case_count), dtype=float)
    case_idx: int

    # Each column corresponds to one number of segments and each row corresponds to one original bus.
    for case_idx in range(case_count):
        study_case: StudyCaseResult = line_study_result.study_cases[case_idx]
        comparison: BusComparison = study_case.bus_comparison
        segment_labels[case_idx] = int(study_case.segments)
        voltage_mag_error_matrix[:, case_idx] = comparison.voltage_mag_error_pct
        voltage_angle_error_matrix[:, case_idx] = comparison.voltage_angle_error_pct
        sbus_error_matrix[:, case_idx] = comparison.sbus_error_pct
    else:
        pass

    return bus_names, segment_labels, voltage_mag_error_matrix, voltage_angle_error_matrix, sbus_error_matrix


def _annotate_heatmap(axis: Any, values: np.ndarray) -> None:
    """
    Add numeric labels to one heatmap.

    :param axis: Matplotlib axis.
    :param values: Displayed matrix.
    :return: None.
    """
    row_count: int = int(values.shape[0])
    col_count: int = int(values.shape[1])
    row_idx: int

    # The annotations keep the images useful even when the color differences are subtle.
    for row_idx in range(row_count):
        col_idx: int
        for col_idx in range(col_count):
            axis.text(col_idx, row_idx, f"{values[row_idx, col_idx]:.6e}", ha='center', va='center', fontsize=6, color='black')
        else:
            pass
    else:
        pass


def _save_global_summary_png(output_directory_path: str,
                             line_study_results: np.ndarray) -> None:
    """
    Save one global PNG heatmap summarizing all lines and segment counts.

    :param output_directory_path: Target output directory.
    :param line_study_results: Array of per-line study results.
    :return: None.
    """
    segment_labels: np.ndarray
    voltage_mag_error_matrix: np.ndarray
    voltage_angle_error_matrix: np.ndarray
    sbus_error_matrix: np.ndarray
    figure: Any
    axes: Any
    line_labels: list[str] = list()
    line_count: int = int(line_study_results.size)
    line_idx: int

    segment_labels, voltage_mag_error_matrix, voltage_angle_error_matrix, sbus_error_matrix = _build_global_error_matrices(line_study_results)

    for line_idx in range(line_count):
        line_study_result: LineStudyResult = line_study_results[line_idx]
        line_labels.append(f"[{line_study_result.line_index}] {line_study_result.bus_from_name}->{line_study_result.bus_to_name}")
    else:
        pass

    # The three stacked heatmaps expose where the largest errors concentrate across lines and segment counts.
    figure, axes = plt.subplots(3, 1, figsize=(18.0, max(8.0, 1.2 * float(line_count))), constrained_layout=True)
    matrices: list[np.ndarray] = [voltage_mag_error_matrix, voltage_angle_error_matrix, sbus_error_matrix]
    titles: list[str] = ["Max Voltage Magnitude Error [%]", "Max Voltage Angle Error [%]", "Max Sbus Error [%]"]
    plot_idx: int

    for plot_idx in range(3):
        matrix_values: np.ndarray = _sanitize_matrix_for_plotting(matrices[plot_idx])
        image: Any = axes[plot_idx].imshow(matrix_values, aspect='auto', cmap='YlOrRd')
        axes[plot_idx].set_title(titles[plot_idx])
        axes[plot_idx].set_xticks(np.arange(int(segment_labels.size)))
        axes[plot_idx].set_xticklabels(segment_labels)
        axes[plot_idx].set_yticks(np.arange(len(line_labels)))
        axes[plot_idx].set_yticklabels(line_labels)
        axes[plot_idx].set_xlabel('Segments')
        axes[plot_idx].set_ylabel('Line')
        figure.colorbar(image, ax=axes[plot_idx], fraction=0.02, pad=0.01)
    else:
        pass

    global_summary_path: str = os.path.join(output_directory_path, 'global_summary.png')
    figure.savefig(global_summary_path, dpi=200)
    plt.close(figure)


def _save_line_summary_png(output_directory_path: str,
                           line_study_result: LineStudyResult) -> None:
    """
    Save one per-line PNG heatmap with bus-by-bus errors across segment counts.

    :param output_directory_path: Target output directory.
    :param line_study_result: Study results of one original line.
    :return: None.
    """
    bus_names: np.ndarray
    segment_labels: np.ndarray
    voltage_mag_error_matrix: np.ndarray
    voltage_angle_error_matrix: np.ndarray
    sbus_error_matrix: np.ndarray
    figure: Any
    axes: Any
    safe_line_name: str = _safe_file_name_fragment(line_study_result.line_name)
    file_path: str = os.path.join(output_directory_path, f"line_{line_study_result.line_index:03d}_{safe_line_name}.png")

    bus_names, segment_labels, voltage_mag_error_matrix, voltage_angle_error_matrix, sbus_error_matrix = _build_line_error_matrices(line_study_result)

    # Terminal buses are highlighted directly in the y labels so the critical buses stand out in the heatmap.
    first_comparison: BusComparison = line_study_result.study_cases[0].bus_comparison
    bus_labels: list[str] = list()
    bus_count: int = int(bus_names.size)
    bus_idx: int

    for bus_idx in range(bus_count):
        bus_label: str = str(bus_names[bus_idx])
        if bool(first_comparison.bus_is_line_terminal[bus_idx]):
            bus_labels.append(f"* {bus_label}")
        else:
            bus_labels.append(f"  {bus_label}")
    else:
        pass

    figure, axes = plt.subplots(3, 1, figsize=(18.0, max(8.0, 0.8 * float(bus_count))), constrained_layout=True)
    matrices: list[np.ndarray] = [voltage_mag_error_matrix, voltage_angle_error_matrix, sbus_error_matrix]
    titles: list[str] = ["Voltage Magnitude Error [%]", "Voltage Angle Error [%]", "Sbus Error [%]"]
    plot_idx: int

    # The three heatmaps show which original buses become sensitive as the line is divided in more sections.
    for plot_idx in range(3):
        matrix_values = _sanitize_matrix_for_plotting(matrices[plot_idx])
        image: Any = axes[plot_idx].imshow(matrix_values, aspect='auto', cmap='YlOrRd')
        axes[plot_idx].set_title(
            f"Line [{line_study_result.line_index}] {line_study_result.line_name}: "
            f"{line_study_result.bus_from_name} -> {line_study_result.bus_to_name}\n{titles[plot_idx]}"
        )
        axes[plot_idx].set_xticks(np.arange(int(segment_labels.size)))
        axes[plot_idx].set_xticklabels(segment_labels)
        axes[plot_idx].set_yticks(np.arange(bus_count))
        axes[plot_idx].set_yticklabels(bus_labels)
        axes[plot_idx].set_xlabel('Segments')
        axes[plot_idx].set_ylabel('Original bus')
        figure.colorbar(image, ax=axes[plot_idx], fraction=0.02, pad=0.01)
        _annotate_heatmap(axes[plot_idx], matrix_values)
    else:
        pass

    figure.savefig(file_path, dpi=200)
    plt.close(figure)


def _save_line_power_flow_values_png(output_directory_path: str,
                                     line_study_result: LineStudyResult) -> None:
    """
    Save one per-line PNG heatmap with the actual power-flow values.

    :param output_directory_path: Target output directory.
    :param line_study_result: Study results of one original line.
    :return: None.
    """
    first_comparison: BusComparison = line_study_result.study_cases[0].bus_comparison
    bus_names: np.ndarray = first_comparison.bus_names.copy()
    bus_count: int = int(bus_names.size)
    case_count: int = int(line_study_result.study_cases.size)
    total_column_count: int = case_count + 1
    segment_labels: np.ndarray = np.empty(total_column_count, dtype=int)
    base_voltage_mag_matrix: np.ndarray = np.empty((bus_count, total_column_count), dtype=float)
    test_voltage_mag_matrix: np.ndarray = np.empty((bus_count, total_column_count), dtype=float)
    base_voltage_angle_matrix: np.ndarray = np.empty((bus_count, total_column_count), dtype=float)
    test_voltage_angle_matrix: np.ndarray = np.empty((bus_count, total_column_count), dtype=float)
    base_sbus_abs_matrix: np.ndarray = np.empty((bus_count, total_column_count), dtype=float)
    test_sbus_abs_matrix: np.ndarray = np.empty((bus_count, total_column_count), dtype=float)
    case_idx: int

    # The first column explicitly represents the unsplit base grid, labelled as one segment.
    segment_labels[0] = 1
    base_voltage_mag_matrix[:, 0] = first_comparison.base_voltage_mag
    test_voltage_mag_matrix[:, 0] = first_comparison.base_voltage_mag
    base_voltage_angle_matrix[:, 0] = first_comparison.base_voltage_angle_deg
    test_voltage_angle_matrix[:, 0] = first_comparison.base_voltage_angle_deg
    base_sbus_abs_matrix[:, 0] = np.abs(first_comparison.base_sbus)
    test_sbus_abs_matrix[:, 0] = np.abs(first_comparison.base_sbus)

    # The remaining columns correspond to the segmented test cases from 2 to the maximum number of sections.
    for case_idx in range(case_count):
        study_case: StudyCaseResult = line_study_result.study_cases[case_idx]
        comparison: BusComparison = study_case.bus_comparison
        segment_labels[case_idx + 1] = int(study_case.segments)
        base_voltage_mag_matrix[:, case_idx + 1] = comparison.base_voltage_mag
        test_voltage_mag_matrix[:, case_idx + 1] = comparison.test_voltage_mag
        base_voltage_angle_matrix[:, case_idx + 1] = comparison.base_voltage_angle_deg
        test_voltage_angle_matrix[:, case_idx + 1] = comparison.test_voltage_angle_deg
        base_sbus_abs_matrix[:, case_idx + 1] = np.abs(comparison.base_sbus)
        test_sbus_abs_matrix[:, case_idx + 1] = np.abs(comparison.test_sbus)
    else:
        pass

    bus_labels: list[str] = list()
    bus_idx: int
    for bus_idx in range(bus_count):
        bus_label: str = str(bus_names[bus_idx])
        if bool(first_comparison.bus_is_line_terminal[bus_idx]):
            bus_labels.append(f"* {bus_label}")
        else:
            bus_labels.append(f"  {bus_label}")
    else:
        pass

    safe_line_name: str = _safe_file_name_fragment(line_study_result.line_name)
    file_path: str = os.path.join(output_directory_path, f"line_{line_study_result.line_index:03d}_{safe_line_name}_values.png")
    figure: Any
    axes: Any
    matrices: list[np.ndarray] = [
        base_voltage_mag_matrix,
        test_voltage_mag_matrix,
        base_voltage_angle_matrix,
        test_voltage_angle_matrix,
        base_sbus_abs_matrix,
        test_sbus_abs_matrix,
    ]
    titles: list[str] = [
        "Base Voltage Magnitude [p.u.]",
        "Test Voltage Magnitude [p.u.]",
        "Base Voltage Angle [deg]",
        "Test Voltage Angle [deg]",
        "Base |Sbus| [MVA]",
        "Test |Sbus| [MVA]",
    ]
    plot_idx: int

    figure, axes = plt.subplots(6, 1, figsize=(18.0, max(14.0, 1.3 * float(bus_count))), constrained_layout=True)

    # These heatmaps help explain whether a large error percentage is caused by a tiny base quantity such as |Sbus| close to zero.
    for plot_idx in range(6):
        matrix_values: np.ndarray = _sanitize_matrix_for_plotting(matrices[plot_idx])
        image: Any = axes[plot_idx].imshow(matrix_values, aspect='auto', cmap='viridis')
        axes[plot_idx].set_title(
            f"Line [{line_study_result.line_index}] {line_study_result.line_name}: "
            f"{line_study_result.bus_from_name} -> {line_study_result.bus_to_name}\n{titles[plot_idx]}"
        )
        axes[plot_idx].set_xticks(np.arange(int(segment_labels.size)))
        axes[plot_idx].set_xticklabels(segment_labels)
        axes[plot_idx].set_yticks(np.arange(bus_count))
        axes[plot_idx].set_yticklabels(bus_labels)
        axes[plot_idx].set_xlabel('Segments')
        axes[plot_idx].set_ylabel('Original bus')
        figure.colorbar(image, ax=axes[plot_idx], fraction=0.02, pad=0.01)
        _annotate_heatmap(axes[plot_idx], matrix_values)
    else:
        pass

    figure.savefig(file_path, dpi=200)
    plt.close(figure)


def _write_output_reports(output_directory_path: str,
                          line_study_results: np.ndarray) -> None:
    """
    Write PNG summary plots for the global study and for each line.

    :param output_directory_path: Target output directory.
    :param line_study_results: Array of per-line study results.
    :return: None.
    """
    line_count: int = int(line_study_results.size)
    line_idx: int

    # The output directory is created on demand so the script can be run in a clean workspace.
    os.makedirs(output_directory_path, exist_ok=True)

    _save_global_summary_png(output_directory_path, line_study_results)

    # Each original line gets one PNG heatmap summarizing the bus-by-bus errors across all segment counts.
    for line_idx in range(line_count):
        line_study_result: LineStudyResult = line_study_results[line_idx]
        _save_line_summary_png(output_directory_path, line_study_result)
        _save_line_power_flow_values_png(output_directory_path, line_study_result)
    else:
        pass


def _build_study_results(grid_path: str,
                         max_segments: int,
                         target_line_index: int,
                         target_line: Line,
                         reference_results: Any,
                         original_bus_names: np.ndarray) -> np.ndarray:
    """
    Run the study for all segmentation counts from 2 to the configured maximum.

    :param grid_path: Source grid path.
    :param max_segments: Maximum number of line sections to test.
    :param target_line_index: Selected line index.
    :param target_line: Selected line.
    :param reference_results: Original power-flow results.
    :param original_bus_names: Original bus names.
    :return: Fixed-size array of study-case results.
    """
    segment_case_count: int = max_segments - 1
    study_results: np.ndarray = np.empty(segment_case_count, dtype=object)
    write_idx: int = 0
    total_segments: int

    # Each iteration builds a new equivalent chain with one more series PI section.
    for total_segments in range(2, max_segments + 1):
        study_results[write_idx] = _run_segment_study(
            base_grid_path=grid_path,
            target_line_index=target_line_index,
            reference_results=reference_results,
            original_bus_names=original_bus_names,
            original_line_name=target_line.name,
            line_bus_from_name=target_line.bus_from.name,
            line_bus_to_name=target_line.bus_to.name,
            total_segments=total_segments,
        )
        write_idx += 1
    else:
        pass

    return study_results


def _run_all_lines_study(grid_path: str,
                         max_segments: int,
                         base_grid: MultiCircuit,
                         reference_results: Any,
                         original_bus_names: np.ndarray) -> np.ndarray:
    """
    Run the segmented-line equivalence study for every line in the grid.

    :param grid_path: Source grid path.
    :param max_segments: Maximum number of line sections to test.
    :param base_grid: Original grid used to enumerate the lines.
    :param reference_results: Original power-flow results.
    :param original_bus_names: Original bus names.
    :return: Array with the complete study result of each line.
    """
    lines_array: np.ndarray = _get_lines_array(base_grid)
    line_count: int = int(lines_array.size)
    line_study_results: np.ndarray = np.empty(line_count, dtype=object)
    line_idx: int

    # The study is repeated independently for each original line so all corridors are checked.
    for line_idx in range(line_count):
        target_line: Line = lines_array[line_idx]
        study_results: np.ndarray

        # The line under study is printed explicitly so the grouped output is easy to inspect.
        print(
            f"Studying line [{line_idx}] {target_line.name}: "
            f"{target_line.bus_from.name} -> {target_line.bus_to.name}"
        )

        # Each line index is passed to the existing split builder so only one line is replaced at a time.
        study_results = _build_study_results(
            grid_path=grid_path,
            max_segments=max_segments,
            target_line_index=line_idx,
            target_line=target_line,
            reference_results=reference_results,
            original_bus_names=original_bus_names,
        )

        line_study_results[line_idx] = LineStudyResult(
            line_index=line_idx,
            line_name=target_line.name,
            bus_from_name=target_line.bus_from.name,
            bus_to_name=target_line.bus_to.name,
            study_cases=study_results,
        )

        # The report stays grouped by original line before advancing to the next corridor.
        _print_results(target_line.name, line_idx, study_results)
        print("")
    else:
        pass

    return line_study_results


def _run_first_line_study_only(grid_path: str,
                               max_segments: int,
                               base_grid: MultiCircuit,
                               reference_results: Any,
                               original_bus_names: np.ndarray) -> None:
    """
    Run the detailed study only for the first line of the grid.

    This helper is used only for quick validation of the very verbose reporting.

    :param grid_path: Source grid path.
    :param max_segments: Maximum number of line sections to test.
    :param base_grid: Original grid used to enumerate the lines.
    :param reference_results: Original power-flow results.
    :param original_bus_names: Original bus names.
    :return: None.
    """
    lines_array: np.ndarray = _get_lines_array(base_grid)

    if int(lines_array.size) > 0:
        target_line: Line = lines_array[0]
        study_results: np.ndarray = _build_study_results(
            grid_path=grid_path,
            max_segments=max_segments,
            target_line_index=0,
            target_line=target_line,
            reference_results=reference_results,
            original_bus_names=original_bus_names,
        )
        _print_results(target_line.name, 0, study_results)
    else:
        pass


def main() -> None:
    """
    Compare the original IEEE 9-bus power flow against equivalent multi-section PI lines.

    :return: None.
    """
    # The demo keeps the main inputs explicit here so the studied grid and segment count are easy to inspect.
    grid_path: str = _get_default_grid_path()
    output_directory_path: str = _get_output_directory_path()
    max_segments: int = 20

    # This study loads the IEEE 9-bus case and repeats the segmented equivalent test for every line.
    base_grid: MultiCircuit = gce.open_file(grid_path)

    if max_segments >= 2:
        pass
    else:
        print("The maximum number of segments must be at least 2.")
        return

    # The original case is the numerical reference used for every segmented equivalent comparison.
    original_bus_names: np.ndarray = _copy_original_bus_names(base_grid)
    reference_results: Any = _run_power_flow(base_grid)
    line_study_results: np.ndarray

    # The segmented cases are solved independently for every original line to avoid cross-case state contamination.
    line_study_results = _run_all_lines_study(
        grid_path=grid_path,
        max_segments=max_segments,
        base_grid=base_grid,
        reference_results=reference_results,
        original_bus_names=original_bus_names,
    )

    # The reports are also stored on disk so the results can be inspected line by line after the run.
    _write_output_reports(output_directory_path, line_study_results)
    print(f"Stored output tables in: {output_directory_path}")


if __name__ == "__main__":
    main()
