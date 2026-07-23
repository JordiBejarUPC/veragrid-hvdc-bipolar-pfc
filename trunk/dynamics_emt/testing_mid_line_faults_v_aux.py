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


class AuxiliaryBusComparison:
    """
    Store the estimated-versus-simulated auxiliary-bus voltage comparison.

    :param auxiliary_bus_names: Names of the auxiliary buses in corridor order.
    :param auxiliary_bus_positions: Positions in per unit from the sending bus.
    :param estimated_voltage: Estimated complex auxiliary-bus voltages.
    :param simulated_voltage: Simulated complex auxiliary-bus voltages.
    :param delta_voltage: Complex voltage difference.
    :param estimated_voltage_mag: Estimated voltage magnitudes.
    :param simulated_voltage_mag: Simulated voltage magnitudes.
    :param delta_voltage_mag: Voltage-magnitude difference.
    :param voltage_mag_error_pct: Voltage-magnitude percentage error.
    :param estimated_voltage_angle_deg: Estimated voltage angles in degrees.
    :param simulated_voltage_angle_deg: Simulated voltage angles in degrees.
    :param delta_voltage_angle_deg: Voltage-angle difference in degrees.
    :param voltage_angle_error_pct: Voltage-angle percentage error.
    :param equal_voltage_exactly: Exact equality flag for the complex-voltage vector.
    """

    __slots__ = (
        "auxiliary_bus_names",
        "auxiliary_bus_positions",
        "estimated_voltage",
        "simulated_voltage",
        "delta_voltage",
        "estimated_voltage_mag",
        "simulated_voltage_mag",
        "delta_voltage_mag",
        "voltage_mag_error_pct",
        "estimated_voltage_angle_deg",
        "simulated_voltage_angle_deg",
        "delta_voltage_angle_deg",
        "voltage_angle_error_pct",
        "equal_voltage_exactly",
    )

    def __init__(self,
                 auxiliary_bus_names: np.ndarray,
                 auxiliary_bus_positions: np.ndarray,
                 estimated_voltage: np.ndarray,
                 simulated_voltage: np.ndarray,
                 delta_voltage: np.ndarray,
                 estimated_voltage_mag: np.ndarray,
                 simulated_voltage_mag: np.ndarray,
                 delta_voltage_mag: np.ndarray,
                 voltage_mag_error_pct: np.ndarray,
                 estimated_voltage_angle_deg: np.ndarray,
                 simulated_voltage_angle_deg: np.ndarray,
                 delta_voltage_angle_deg: np.ndarray,
                 voltage_angle_error_pct: np.ndarray,
                 equal_voltage_exactly: bool) -> None:
        """
        Build one auxiliary-bus comparison container.

        :param auxiliary_bus_names: Names of the auxiliary buses in corridor order.
        :param auxiliary_bus_positions: Positions in per unit from the sending bus.
        :param estimated_voltage: Estimated complex auxiliary-bus voltages.
        :param simulated_voltage: Simulated complex auxiliary-bus voltages.
        :param delta_voltage: Complex voltage difference.
        :param estimated_voltage_mag: Estimated voltage magnitudes.
        :param simulated_voltage_mag: Simulated voltage magnitudes.
        :param delta_voltage_mag: Voltage-magnitude difference.
        :param voltage_mag_error_pct: Voltage-magnitude percentage error.
        :param estimated_voltage_angle_deg: Estimated voltage angles in degrees.
        :param simulated_voltage_angle_deg: Simulated voltage angles in degrees.
        :param delta_voltage_angle_deg: Voltage-angle difference in degrees.
        :param voltage_angle_error_pct: Voltage-angle percentage error.
        :param equal_voltage_exactly: Exact equality flag for the complex-voltage vector.
        :return: None.
        """
        self.auxiliary_bus_names = auxiliary_bus_names
        self.auxiliary_bus_positions = auxiliary_bus_positions
        self.estimated_voltage = estimated_voltage
        self.simulated_voltage = simulated_voltage
        self.delta_voltage = delta_voltage
        self.estimated_voltage_mag = estimated_voltage_mag
        self.simulated_voltage_mag = simulated_voltage_mag
        self.delta_voltage_mag = delta_voltage_mag
        self.voltage_mag_error_pct = voltage_mag_error_pct
        self.estimated_voltage_angle_deg = estimated_voltage_angle_deg
        self.simulated_voltage_angle_deg = simulated_voltage_angle_deg
        self.delta_voltage_angle_deg = delta_voltage_angle_deg
        self.voltage_angle_error_pct = voltage_angle_error_pct
        self.equal_voltage_exactly = equal_voltage_exactly


class AuxiliaryVoltageStudyCaseResult:
    """
    Store the metrics of one segmented auxiliary-voltage study case.

    :param segments: Number of series line segments.
    :param converged: Power-flow convergence flag.
    :param split_branch_count: Number of created split branches.
    :param split_branch_total_loss_mva: Total losses of the split branches.
    :param split_branch_total_loading_max: Maximum loading among the split branches.
    :param auxiliary_bus_comparison: Estimated-versus-simulated auxiliary-bus comparison.
    """

    __slots__ = (
        "segments",
        "converged",
        "split_branch_count",
        "split_branch_total_loss_mva",
        "split_branch_total_loading_max",
        "auxiliary_bus_comparison",
    )

    def __init__(self,
                 segments: int,
                 converged: bool,
                 split_branch_count: int,
                 split_branch_total_loss_mva: complex,
                 split_branch_total_loading_max: float,
                 auxiliary_bus_comparison: AuxiliaryBusComparison) -> None:
        """
        Build one study-case container.

        :param segments: Number of series line segments.
        :param converged: Power-flow convergence flag.
        :param split_branch_count: Number of created split branches.
        :param split_branch_total_loss_mva: Total losses of the split branches.
        :param split_branch_total_loading_max: Maximum loading among the split branches.
        :param auxiliary_bus_comparison: Estimated-versus-simulated auxiliary-bus comparison.
        :return: None.
        """
        self.segments = segments
        self.converged = converged
        self.split_branch_count = split_branch_count
        self.split_branch_total_loss_mva = split_branch_total_loss_mva
        self.split_branch_total_loading_max = split_branch_total_loading_max
        self.auxiliary_bus_comparison = auxiliary_bus_comparison


class AuxiliaryVoltageLineStudyResult:
    """
    Store the complete auxiliary-voltage study for one original line.

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
    grid_path: str = os.path.join(repo_root, 'Grids_and_profiles', 'grids', 'IEEE 9 Bus.gridcal')
    return grid_path


def _get_output_directory_path() -> str:
    """
    Compute the output directory used to store the generated auxiliary-voltage PNGs.

    :return: Absolute path to the output directory.
    """
    output_directory_path: str = os.path.join(module_dir, 'mid_line_faults_testing_v_aux')
    return output_directory_path


def _get_power_flow_options() -> PowerFlowOptions:
    """
    Build one deterministic power-flow configuration for the study.

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
    power_flow_options: PowerFlowOptions = _get_power_flow_options()
    power_flow_driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=power_flow_options)
    power_flow_driver.run()
    return power_flow_driver.results


def _get_lines_array(grid: MultiCircuit) -> np.ndarray:
    """
    Copy the line collection into a fixed-size numpy object array.

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


def _create_auxiliary_bus(reference_line: Line,
                          segment_index: int,
                          total_segments: int) -> Bus:
    """
    Create one auxiliary bus used to chain the line segments.

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


def _build_segmented_grid(base_grid_path: str,
                          target_line_index: int,
                          total_segments: int) -> tuple[MultiCircuit, np.ndarray, Line]:
    """
    Load the base grid and replace one line by a series chain of equal segments.

    :param base_grid_path: Source grid file path.
    :param target_line_index: Index of the line to replace.
    :param total_segments: Number of equal series PI lines.
    :return: Tuple with the modified grid, auxiliary-bus names, and original line object.
    """
    grid: MultiCircuit = gce.open_file(base_grid_path)
    lines_array: np.ndarray = _get_lines_array(grid)
    target_line: Line = lines_array[target_line_index]
    segment_scale: float = 1.0 / float(total_segments)
    bus_chain: np.ndarray = np.empty(total_segments + 1, dtype=object)
    auxiliary_bus_names: np.ndarray = np.empty(total_segments - 1, dtype=object)
    segment_idx: int

    # The chain starts at the original sending bus and ends at the original receiving bus.
    bus_chain[0] = target_line.bus_from
    bus_chain[total_segments] = target_line.bus_to

    # The internal buses are created first so the split branches can be connected in order.
    for segment_idx in range(1, total_segments):
        auxiliary_bus: Bus = _create_auxiliary_bus(target_line, segment_idx, total_segments)
        grid.add_bus(auxiliary_bus)
        bus_chain[segment_idx] = auxiliary_bus
        auxiliary_bus_names[segment_idx - 1] = auxiliary_bus.name
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

    grid.delete_line(target_line)
    return grid, auxiliary_bus_names, target_line


def _get_bus_indices_by_name(names: np.ndarray, selected_names: np.ndarray) -> np.ndarray:
    """
    Map one ordered list of bus names to indices in one results vector.

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

    for name_idx in range(name_count):
        lookup[str(names[name_idx])] = name_idx
    else:
        pass

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


def _safe_file_name_fragment(text: str) -> str:
    """
    Convert one free-form label into a filesystem-safe file-name fragment.

    :param text: Original text.
    :return: Sanitized file-name fragment.
    """
    safe_chars: list[str] = list()
    char_idx: int
    char_count: int = len(text)

    for char_idx in range(char_count):
        character: str = text[char_idx]
        if character.isalnum():
            safe_chars.append(character)
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


def _estimate_auxiliary_bus_voltages(bus_from_voltage: complex,
                                     bus_to_voltage: complex,
                                     total_segments: int) -> np.ndarray:
    """
    Estimate the auxiliary-bus voltages using proportional voltage drop.

    The complex voltage drop is assumed to be uniformly distributed along the
    equally divided series corridor.

    :param bus_from_voltage: Sending-end complex voltage.
    :param bus_to_voltage: Receiving-end complex voltage.
    :param total_segments: Number of line sections.
    :return: Estimated auxiliary-bus complex voltages.
    """
    auxiliary_bus_count: int = total_segments - 1
    estimated_voltages: np.ndarray = np.empty(auxiliary_bus_count, dtype=complex)
    total_voltage_drop: complex = bus_from_voltage - bus_to_voltage
    segment_idx: int

    # The estimate places each auxiliary voltage at the proportional complex drop position.
    for segment_idx in range(1, total_segments):
        position: float = float(segment_idx) / float(total_segments)
        estimated_voltages[segment_idx - 1] = bus_from_voltage - position * total_voltage_drop
    else:
        pass

    return estimated_voltages


def _compute_auxiliary_bus_comparison(base_results: Any,
                                      segmented_results: Any,
                                      original_line: Line,
                                      auxiliary_bus_names: np.ndarray,
                                      total_segments: int) -> AuxiliaryBusComparison:
    """
    Compare estimated auxiliary-bus voltages with simulated split-grid voltages.

    :param base_results: Original-grid power-flow results.
    :param segmented_results: Split-grid power-flow results.
    :param original_line: Original line before splitting.
    :param auxiliary_bus_names: Names of the created auxiliary buses.
    :param total_segments: Number of series line segments.
    :return: Auxiliary-bus comparison metrics.
    """
    base_bus_names: np.ndarray = np.asarray(base_results.bus_names, dtype=object)
    segmented_bus_names: np.ndarray = np.asarray(segmented_results.bus_names, dtype=object)
    line_terminal_names: np.ndarray = np.empty(2, dtype=object)
    line_terminal_names[0] = original_line.bus_from.name
    line_terminal_names[1] = original_line.bus_to.name
    base_terminal_indices: np.ndarray = _get_bus_indices_by_name(base_bus_names, line_terminal_names)
    segmented_auxiliary_indices: np.ndarray = _get_bus_indices_by_name(segmented_bus_names, auxiliary_bus_names)

    if _all_indices_are_valid(base_terminal_indices) and _all_indices_are_valid(segmented_auxiliary_indices):
        pass
    else:
        auxiliary_bus_count: int = int(auxiliary_bus_names.size)
        inf_real: np.ndarray = np.full(auxiliary_bus_count, np.inf, dtype=float)
        inf_complex: np.ndarray = np.full(auxiliary_bus_count, np.inf + 0.0j, dtype=complex)
        auxiliary_positions: np.ndarray = np.empty(auxiliary_bus_count, dtype=float)
        aux_idx: int
        for aux_idx in range(auxiliary_bus_count):
            auxiliary_positions[aux_idx] = float(aux_idx + 1) / float(total_segments)
        else:
            pass
        return AuxiliaryBusComparison(
            auxiliary_bus_names=auxiliary_bus_names.copy(),
            auxiliary_bus_positions=auxiliary_positions,
            estimated_voltage=inf_complex.copy(),
            simulated_voltage=inf_complex.copy(),
            delta_voltage=inf_complex.copy(),
            estimated_voltage_mag=inf_real.copy(),
            simulated_voltage_mag=inf_real.copy(),
            delta_voltage_mag=inf_real.copy(),
            voltage_mag_error_pct=inf_real.copy(),
            estimated_voltage_angle_deg=inf_real.copy(),
            simulated_voltage_angle_deg=inf_real.copy(),
            delta_voltage_angle_deg=inf_real.copy(),
            voltage_angle_error_pct=inf_real.copy(),
            equal_voltage_exactly=False,
        )

    bus_from_voltage: complex = complex(base_results.voltage[int(base_terminal_indices[0])])
    bus_to_voltage: complex = complex(base_results.voltage[int(base_terminal_indices[1])])
    estimated_voltage: np.ndarray = _estimate_auxiliary_bus_voltages(bus_from_voltage, bus_to_voltage, total_segments)
    simulated_voltage: np.ndarray = segmented_results.voltage[segmented_auxiliary_indices]
    delta_voltage: np.ndarray = simulated_voltage - estimated_voltage
    estimated_voltage_mag: np.ndarray = np.abs(estimated_voltage)
    simulated_voltage_mag: np.ndarray = np.abs(simulated_voltage)
    delta_voltage_mag: np.ndarray = simulated_voltage_mag - estimated_voltage_mag
    estimated_voltage_angle_deg: np.ndarray = np.rad2deg(np.angle(estimated_voltage))
    simulated_voltage_angle_deg: np.ndarray = np.rad2deg(np.angle(simulated_voltage))
    delta_voltage_angle_deg: np.ndarray = simulated_voltage_angle_deg - estimated_voltage_angle_deg
    voltage_mag_error_pct: np.ndarray = _compute_percentage_error(delta_voltage_mag, estimated_voltage_mag)
    voltage_angle_error_pct: np.ndarray = _compute_percentage_error(delta_voltage_angle_deg, estimated_voltage_angle_deg)
    auxiliary_positions: np.ndarray = np.empty(int(auxiliary_bus_names.size), dtype=float)
    aux_idx: int

    for aux_idx in range(int(auxiliary_bus_names.size)):
        auxiliary_positions[aux_idx] = float(aux_idx + 1) / float(total_segments)
    else:
        pass

    comparison: AuxiliaryBusComparison = AuxiliaryBusComparison(
        auxiliary_bus_names=auxiliary_bus_names.copy(),
        auxiliary_bus_positions=auxiliary_positions,
        estimated_voltage=estimated_voltage,
        simulated_voltage=simulated_voltage,
        delta_voltage=delta_voltage,
        estimated_voltage_mag=estimated_voltage_mag,
        simulated_voltage_mag=simulated_voltage_mag,
        delta_voltage_mag=delta_voltage_mag,
        voltage_mag_error_pct=voltage_mag_error_pct,
        estimated_voltage_angle_deg=estimated_voltage_angle_deg,
        simulated_voltage_angle_deg=simulated_voltage_angle_deg,
        delta_voltage_angle_deg=delta_voltage_angle_deg,
        voltage_angle_error_pct=voltage_angle_error_pct,
        equal_voltage_exactly=bool(np.array_equal(estimated_voltage, simulated_voltage)),
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

    split_losses: np.ndarray = results.Sf[split_indices] + results.St[split_indices]
    split_loading: np.ndarray = np.abs(results.loading[split_indices])
    total_losses: complex = complex(np.sum(split_losses))
    max_loading: float = float(np.max(split_loading))
    return split_count, total_losses, max_loading


def _run_segment_study(base_grid_path: str,
                       target_line_index: int,
                       base_results: Any,
                       total_segments: int) -> AuxiliaryVoltageStudyCaseResult:
    """
    Run one segmented auxiliary-voltage study case.

    :param base_grid_path: Source grid file path.
    :param target_line_index: Line index to split.
    :param base_results: Original-grid power-flow results.
    :param total_segments: Number of series segments.
    :return: Study metrics for the case.
    """
    segmented_grid: MultiCircuit
    auxiliary_bus_names: np.ndarray
    original_line: Line
    segmented_grid, auxiliary_bus_names, original_line = _build_segmented_grid(base_grid_path, target_line_index, total_segments)
    segmented_results: Any = _run_power_flow(segmented_grid)
    split_branch_count: int
    split_branch_total_loss_mva: complex
    split_branch_total_loading_max: float
    split_branch_count, split_branch_total_loss_mva, split_branch_total_loading_max = _compute_split_branch_metrics(
        segmented_results,
        split_branch_name_prefix=f"{original_line.name} split ",
    )
    auxiliary_bus_comparison: AuxiliaryBusComparison = _compute_auxiliary_bus_comparison(
        base_results,
        segmented_results,
        original_line,
        auxiliary_bus_names,
        total_segments,
    )

    study_case_result: AuxiliaryVoltageStudyCaseResult = AuxiliaryVoltageStudyCaseResult(
        segments=total_segments,
        converged=bool(segmented_results.converged),
        split_branch_count=split_branch_count,
        split_branch_total_loss_mva=split_branch_total_loss_mva,
        split_branch_total_loading_max=split_branch_total_loading_max,
        auxiliary_bus_comparison=auxiliary_bus_comparison,
    )
    return study_case_result


def _build_line_study_results(grid_path: str,
                              max_segments: int,
                              target_line_index: int,
                              target_line: Line,
                              base_results: Any) -> AuxiliaryVoltageLineStudyResult:
    """
    Run the auxiliary-voltage study for one original line over all segment counts.

    :param grid_path: Source grid path.
    :param max_segments: Maximum number of line sections to test.
    :param target_line_index: Selected line index.
    :param target_line: Selected line.
    :param base_results: Original-grid power-flow results.
    :return: Per-line study result.
    """
    case_count: int = max_segments - 1
    study_cases: np.ndarray = np.empty(case_count, dtype=object)
    write_idx: int = 0
    total_segments: int

    for total_segments in range(2, max_segments + 1):
        study_cases[write_idx] = _run_segment_study(
            base_grid_path=grid_path,
            target_line_index=target_line_index,
            base_results=base_results,
            total_segments=total_segments,
        )
        write_idx += 1
    else:
        pass

    return AuxiliaryVoltageLineStudyResult(
        line_index=target_line_index,
        line_name=target_line.name,
        bus_from_name=target_line.bus_from.name,
        bus_to_name=target_line.bus_to.name,
        study_cases=study_cases,
    )


def _sanitize_matrix_for_plotting(values: np.ndarray) -> np.ndarray:
    """
    Replace non-finite values before plotting one matrix as a heatmap.

    :param values: Matrix to sanitize.
    :return: Sanitized matrix.
    """
    sanitized_values: np.ndarray = np.array(values, dtype=float, copy=True)
    finite_mask: np.ndarray = np.isfinite(sanitized_values)

    if bool(np.any(finite_mask)):
        pass
    else:
        sanitized_values.fill(np.nan)
        return sanitized_values

    sanitized_values[~finite_mask] = np.nan
    return sanitized_values


def _build_masked_matrix_for_plotting(values: np.ndarray) -> np.ma.MaskedArray:
    """
    Build one masked matrix so unused cells are not colored as valid values.

    :param values: Matrix to convert.
    :return: Masked matrix.
    """
    raw_values: np.ndarray = np.array(values, dtype=float, copy=True)
    invalid_mask: np.ndarray = ~np.isfinite(raw_values)
    masked_values: np.ma.MaskedArray = np.ma.array(raw_values, mask=invalid_mask)
    return masked_values


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

    for row_idx in range(row_count):
        col_idx: int
        for col_idx in range(col_count):
            if np.isfinite(values[row_idx, col_idx]):
                axis.text(col_idx, row_idx, f"{values[row_idx, col_idx]:.6e}", ha='center', va='center', fontsize=6, color='black')
            else:
                pass
        else:
            pass
    else:
        pass


def _build_global_error_matrices(line_study_results: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build the global worst-error matrices for all lines and segment counts.

    :param line_study_results: Array of per-line study results.
    :return: Tuple with segment labels and the Vmag and Vang error matrices.
    """
    line_count: int = int(line_study_results.size)
    segment_count: int = int(line_study_results[0].study_cases.size)
    segment_labels: np.ndarray = np.empty(segment_count, dtype=int)
    voltage_mag_error_matrix: np.ndarray = np.empty((line_count, segment_count), dtype=float)
    voltage_angle_error_matrix: np.ndarray = np.empty((line_count, segment_count), dtype=float)
    line_idx: int

    for line_idx in range(segment_count):
        segment_labels[line_idx] = int(line_study_results[0].study_cases[line_idx].segments)
    else:
        pass

    for line_idx in range(line_count):
        line_study_result: AuxiliaryVoltageLineStudyResult = line_study_results[line_idx]
        case_idx: int
        for case_idx in range(segment_count):
            study_case: AuxiliaryVoltageStudyCaseResult = line_study_result.study_cases[case_idx]
            comparison: AuxiliaryBusComparison = study_case.auxiliary_bus_comparison
            voltage_mag_error_matrix[line_idx, case_idx] = float(np.max(comparison.voltage_mag_error_pct))
            voltage_angle_error_matrix[line_idx, case_idx] = float(np.max(comparison.voltage_angle_error_pct))
        else:
            pass
    else:
        pass

    return segment_labels, voltage_mag_error_matrix, voltage_angle_error_matrix


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
    line_labels: list[str] = list()
    line_count: int = int(line_study_results.size)
    line_idx: int
    figure: Any
    axes: Any

    segment_labels, voltage_mag_error_matrix, voltage_angle_error_matrix = _build_global_error_matrices(line_study_results)

    for line_idx in range(line_count):
        line_study_result: AuxiliaryVoltageLineStudyResult = line_study_results[line_idx]
        line_labels.append(f"[{line_study_result.line_index}] {line_study_result.bus_from_name}->{line_study_result.bus_to_name}")
    else:
        pass

    figure, axes = plt.subplots(2, 1, figsize=(18.0, max(8.0, 1.2 * float(line_count))), constrained_layout=True)
    matrices: list[np.ndarray] = [voltage_mag_error_matrix, voltage_angle_error_matrix]
    titles: list[str] = ["Max Auxiliary Voltage Magnitude Error [%]", "Max Auxiliary Voltage Angle Error [%]"]
    plot_idx: int

    for plot_idx in range(2):
        matrix_values: np.ndarray = _sanitize_matrix_for_plotting(matrices[plot_idx])
        masked_values: np.ma.MaskedArray = _build_masked_matrix_for_plotting(matrices[plot_idx])
        cmap: Any = plt.get_cmap('YlOrRd').copy()
        cmap.set_bad(color='lightgray')
        image: Any = axes[plot_idx].imshow(masked_values, aspect='auto', cmap=cmap)
        axes[plot_idx].set_title(titles[plot_idx])
        axes[plot_idx].set_xticks(np.arange(int(segment_labels.size)))
        axes[plot_idx].set_xticklabels(segment_labels)
        axes[plot_idx].set_yticks(np.arange(len(line_labels)))
        axes[plot_idx].set_yticklabels(line_labels)
        axes[plot_idx].set_xlabel('Segments')
        axes[plot_idx].set_ylabel('Line')
        figure.colorbar(image, ax=axes[plot_idx], fraction=0.02, pad=0.01)
        _annotate_heatmap(axes[plot_idx], matrix_values)
    else:
        pass

    figure.savefig(os.path.join(output_directory_path, 'global_summary.png'), dpi=200)
    plt.close(figure)


def _save_line_png(output_directory_path: str,
                   line_study_result: AuxiliaryVoltageLineStudyResult) -> None:
    """
    Save one per-line PNG heatmap comparing estimated and simulated auxiliary-bus voltages.

    :param output_directory_path: Target output directory.
    :param line_study_result: Per-line study result.
    :return: None.
    """
    case_count: int = int(line_study_result.study_cases.size)
    last_comparison: AuxiliaryBusComparison = line_study_result.study_cases[case_count - 1].auxiliary_bus_comparison
    auxiliary_bus_names: np.ndarray = last_comparison.auxiliary_bus_names.copy()
    auxiliary_bus_count: int = int(auxiliary_bus_names.size)
    segment_labels: np.ndarray = np.empty(case_count + 1, dtype=int)
    estimated_voltage_mag_matrix: np.ndarray = np.full((auxiliary_bus_count, case_count + 1), np.nan, dtype=float)
    simulated_voltage_mag_matrix: np.ndarray = np.full((auxiliary_bus_count, case_count + 1), np.nan, dtype=float)
    voltage_mag_error_matrix: np.ndarray = np.full((auxiliary_bus_count, case_count + 1), np.nan, dtype=float)
    estimated_voltage_angle_matrix: np.ndarray = np.full((auxiliary_bus_count, case_count + 1), np.nan, dtype=float)
    simulated_voltage_angle_matrix: np.ndarray = np.full((auxiliary_bus_count, case_count + 1), np.nan, dtype=float)
    voltage_angle_error_matrix: np.ndarray = np.full((auxiliary_bus_count, case_count + 1), np.nan, dtype=float)
    case_idx: int
    figure: Any
    axes: Any
    safe_line_name: str = _safe_file_name_fragment(line_study_result.line_name)
    file_path: str = os.path.join(output_directory_path, f"line_{line_study_result.line_index:03d}_{safe_line_name}.png")

    # The first column is intentionally left blank because the unsplit original grid has no auxiliary buses.
    segment_labels[0] = 1
    estimated_voltage_mag_matrix[:, 0] = np.nan
    simulated_voltage_mag_matrix[:, 0] = np.nan
    voltage_mag_error_matrix[:, 0] = np.nan
    estimated_voltage_angle_matrix[:, 0] = np.nan
    simulated_voltage_angle_matrix[:, 0] = np.nan
    voltage_angle_error_matrix[:, 0] = np.nan

    for case_idx in range(case_count):
        study_case: AuxiliaryVoltageStudyCaseResult = line_study_result.study_cases[case_idx]
        comparison: AuxiliaryBusComparison = study_case.auxiliary_bus_comparison
        current_auxiliary_bus_count: int = int(comparison.auxiliary_bus_names.size)
        segment_labels[case_idx + 1] = int(study_case.segments)
        estimated_voltage_mag_matrix[0:current_auxiliary_bus_count, case_idx + 1] = comparison.estimated_voltage_mag
        simulated_voltage_mag_matrix[0:current_auxiliary_bus_count, case_idx + 1] = comparison.simulated_voltage_mag
        voltage_mag_error_matrix[0:current_auxiliary_bus_count, case_idx + 1] = comparison.voltage_mag_error_pct
        estimated_voltage_angle_matrix[0:current_auxiliary_bus_count, case_idx + 1] = comparison.estimated_voltage_angle_deg
        simulated_voltage_angle_matrix[0:current_auxiliary_bus_count, case_idx + 1] = comparison.simulated_voltage_angle_deg
        voltage_angle_error_matrix[0:current_auxiliary_bus_count, case_idx + 1] = comparison.voltage_angle_error_pct
    else:
        pass

    figure, axes = plt.subplots(6, 1, figsize=(18.0, max(10.0, 1.2 * float(auxiliary_bus_count))), constrained_layout=True)
    matrices: list[np.ndarray] = [
        estimated_voltage_mag_matrix,
        simulated_voltage_mag_matrix,
        voltage_mag_error_matrix,
        estimated_voltage_angle_matrix,
        simulated_voltage_angle_matrix,
        voltage_angle_error_matrix,
    ]
    titles: list[str] = [
        "Estimated Auxiliary Voltage Magnitude [p.u.]",
        "Power-Flow Auxiliary Voltage Magnitude [p.u.]",
        "Auxiliary Voltage Magnitude Error [%]",
        "Estimated Auxiliary Voltage Angle [deg]",
        "Power-Flow Auxiliary Voltage Angle [deg]",
        "Auxiliary Voltage Angle Error [%]",
    ]
    plot_idx: int

    for plot_idx in range(6):
        matrix_values: np.ndarray = _sanitize_matrix_for_plotting(matrices[plot_idx])
        masked_values: np.ma.MaskedArray = _build_masked_matrix_for_plotting(matrices[plot_idx])
        cmap: Any = plt.get_cmap('viridis' if plot_idx in (0, 1, 3, 4) else 'YlOrRd').copy()
        cmap.set_bad(color='lightgray')
        image: Any = axes[plot_idx].imshow(masked_values, aspect='auto', cmap=cmap)
        axes[plot_idx].set_title(
            f"Line [{line_study_result.line_index}] {line_study_result.line_name}: "
            f"{line_study_result.bus_from_name} -> {line_study_result.bus_to_name}\n{titles[plot_idx]}"
        )
        axes[plot_idx].set_xticks(np.arange(int(segment_labels.size)))
        axes[plot_idx].set_xticklabels(segment_labels)
        axes[plot_idx].set_yticks(np.arange(auxiliary_bus_count))
        axes[plot_idx].set_yticklabels(auxiliary_bus_names)
        axes[plot_idx].set_xlabel('Segments')
        axes[plot_idx].set_ylabel('Auxiliary bus')
        figure.colorbar(image, ax=axes[plot_idx], fraction=0.02, pad=0.01)
        _annotate_heatmap(axes[plot_idx], matrix_values)
    else:
        pass

    figure.savefig(file_path, dpi=200)
    plt.close(figure)


def _run_all_lines_study(grid_path: str,
                         max_segments: int,
                         base_grid: MultiCircuit,
                         base_results: Any) -> np.ndarray:
    """
    Run the auxiliary-voltage study for every line in the grid.

    :param grid_path: Source grid path.
    :param max_segments: Maximum number of line sections to test.
    :param base_grid: Original grid used to enumerate the lines.
    :param base_results: Original-grid power-flow results.
    :return: Array with the complete study result of each line.
    """
    lines_array: np.ndarray = _get_lines_array(base_grid)
    line_count: int = int(lines_array.size)
    line_study_results: np.ndarray = np.empty(line_count, dtype=object)
    line_idx: int

    for line_idx in range(line_count):
        target_line: Line = lines_array[line_idx]
        print(f"Studying line [{line_idx}] {target_line.name}: {target_line.bus_from.name} -> {target_line.bus_to.name}")
        line_study_results[line_idx] = _build_line_study_results(
            grid_path=grid_path,
            max_segments=max_segments,
            target_line_index=line_idx,
            target_line=target_line,
            base_results=base_results,
        )
    else:
        pass

    return line_study_results


def _write_output_reports(output_directory_path: str,
                          line_study_results: np.ndarray) -> None:
    """
    Write PNG summary plots for the global study and for each line.

    :param output_directory_path: Target output directory.
    :param line_study_results: Array of per-line study results.
    :return: None.
    """
    os.makedirs(output_directory_path, exist_ok=True)
    _save_global_summary_png(output_directory_path, line_study_results)

    line_count: int = int(line_study_results.size)
    line_idx: int
    for line_idx in range(line_count):
        line_study_result: AuxiliaryVoltageLineStudyResult = line_study_results[line_idx]
        _save_line_png(output_directory_path, line_study_result)
    else:
        pass


def main() -> None:
    """
    Compare estimated auxiliary-bus voltages against split-grid power-flow voltages.

    :return: None.
    """
    grid_path: str = _get_default_grid_path()
    output_directory_path: str = _get_output_directory_path()
    max_segments: int = 20
    base_grid: MultiCircuit = gce.open_file(grid_path)

    if max_segments >= 2:
        pass
    else:
        print("The maximum number of segments must be at least 2.")
        return

    # The original power flow provides the terminal-bus voltages used by the proportional-drop estimate.
    base_results: Any = _run_power_flow(base_grid)
    line_study_results: np.ndarray = _run_all_lines_study(
        grid_path=grid_path,
        max_segments=max_segments,
        base_grid=base_grid,
        base_results=base_results,
    )

    _write_output_reports(output_directory_path, line_study_results)
    print(f"Stored output tables in: {output_directory_path}")


if __name__ == "__main__":
    main()
