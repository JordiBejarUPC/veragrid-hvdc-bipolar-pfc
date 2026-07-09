"""
Build a locally queryable reduced-subspace MDHEM-PV artifact for ACTIVSg2000.

The full ``[PQ_P, PQ_Q, PV_P]`` artifact used on IEEE14 does not scale to a
2000-bus grid because the coefficient count grows combinatorially with the
number of embedding dimensions. This file keeps the same MDHEM-PV recurrence
but replaces the full per-bus query basis with a small set of balanced
full-network injection directions.

The result is still a persistent artifact:

1. train once on a VeraGrid ``MultiCircuit``,
2. save the coefficient tensor to disk,
3. query the artifact later with low-dimensional coordinates,
4. recover voltages and branch flows without running NR in the query path.

Newton-Raphson is used only as:

* an optional germ seed for artifact training,
* an external validation reference in the local report.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

import numpy as np
import scipy.sparse

from mdhelm import MDHEMQueryResult
from mdhelm import MultiIndexTable
from mdhelm import SparseLinearSolver
from mdhelm import VeraGridQueryCaseData
from mdhelm import build_system_matrix
from mdhelm import calculate_branch_results
from mdhelm import calculate_known_qx_convolution
from mdhelm import calculate_known_reciprocal_convolution
from mdhelm import calculate_known_voltage_convolution
from mdhelm import calculate_monomial_weights_from_table
from mdhelm import calculate_pv_voltage_error
from mdhelm import calculate_query_mismatch_norm
from mdhelm import calculate_rhs_power_numba
from mdhelm import compute_power_from_ybus
from mdhelm import create_full_to_local_lookup
from mdhelm import create_mdhelm_inputs
from mdhelm import create_multi_index_table
from mdhelm import determine_rhs_block_columns
from mdhelm import extract_slack_voltage_values
from mdhelm import import_veragrid_engine_modules
from mdhelm import load_multicircuit_from_file
from mdhelm import restore_csc_matrix
from mdhelm import solve_physical_germ
from mdhelm import store_csc_matrix
from mdhelm_pv_case14_fire_test import DeviceBusMapping
from mdhelm_pv_case14_fire_test import build_device_bus_mapping
from mdhelm_pv_case14_fire_test import calculate_distribution_weights
from mdhelm_pv_case14_fire_test import calculate_injection_write_error
from mdhelm_pv_case14_fire_test import compare_artifact_with_nr
from mdhelm_pv_case14_fire_test import create_nr_options
from mdhelm_pv_case14_fire_test import run_newton_reference
from mdhelm_pv_case14_fire_test import scenario_is_physical

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit
    from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults


class ReducedSubspaceScenario:
    """
    Store one reduced-coordinate scenario.

    :param name:
        Scenario name.
    :param coordinates:
        Reduced artifact coordinates.
    :param pq_active_power:
        PQ active powers in per unit.
    :param pq_reactive_power:
        PQ reactive powers in per unit.
    :param pv_active_power:
        PV active powers in per unit.
    :param active_delta_sum:
        Sum of active-power perturbations relative to the germ.
    :param reactive_delta_sum:
        Sum of PQ reactive-power perturbations relative to the germ.
    """

    __slots__ = (
        "name",
        "coordinates",
        "pq_active_power",
        "pq_reactive_power",
        "pv_active_power",
        "active_delta_sum",
        "reactive_delta_sum",
    )

    def __init__(
        self,
        name: str,
        coordinates: np.ndarray,
        pq_active_power: np.ndarray,
        pq_reactive_power: np.ndarray,
        pv_active_power: np.ndarray,
        active_delta_sum: float,
        reactive_delta_sum: float,
    ) -> None:
        self.name: str = name
        self.coordinates: np.ndarray = coordinates
        self.pq_active_power: np.ndarray = pq_active_power
        self.pq_reactive_power: np.ndarray = pq_reactive_power
        self.pv_active_power: np.ndarray = pv_active_power
        self.active_delta_sum: float = active_delta_sum
        self.reactive_delta_sum: float = reactive_delta_sum


class ReducedSubspaceMetrics:
    """
    Store the comparison metrics for one reduced-coordinate scenario.

    :param scenario_name:
        Scenario name.
    :param nr_converged:
        NR convergence flag.
    :param artifact_converged:
        Artifact convergence-like flag.
    :param injection_write_error:
        Maximum bus-injection write error in per unit.
    :param nr_error:
        NR reported error.
    :param artifact_error:
        Artifact mismatch norm.
    :param max_voltage_diff:
        Maximum voltage difference in per unit.
    :param max_flow_diff_mva:
        Maximum branch-from flow difference in MVA.
    :param max_loading_diff:
        Maximum branch-loading difference.
    :param passed:
        Scenario pass flag.
    """

    __slots__ = (
        "scenario_name",
        "nr_converged",
        "artifact_converged",
        "injection_write_error",
        "nr_error",
        "artifact_error",
        "max_voltage_diff",
        "max_flow_diff_mva",
        "max_loading_diff",
        "passed",
    )

    def __init__(
        self,
        scenario_name: str,
        nr_converged: bool,
        artifact_converged: bool,
        injection_write_error: float,
        nr_error: float,
        artifact_error: float,
        max_voltage_diff: float,
        max_flow_diff_mva: float,
        max_loading_diff: float,
        passed: bool,
    ) -> None:
        self.scenario_name: str = scenario_name
        self.nr_converged: bool = nr_converged
        self.artifact_converged: bool = artifact_converged
        self.injection_write_error: float = injection_write_error
        self.nr_error: float = nr_error
        self.artifact_error: float = artifact_error
        self.max_voltage_diff: float = max_voltage_diff
        self.max_flow_diff_mva: float = max_flow_diff_mva
        self.max_loading_diff: float = max_loading_diff
        self.passed: bool = passed


class MDHEMReducedSubspacePVArtifact:
    """
    Store a reduced-coordinate MDHEM-PV artifact.

    :param ybus:
        Full bus admittance matrix.
    :param yf:
        Branch-from admittance matrix.
    :param yt:
        Branch-to admittance matrix.
    :param slack:
        Slack bus indices.
    :param pq:
        PQ bus indices.
    :param pv:
        PV bus indices.
    :param no_slack:
        Non-slack bus indices.
    :param slack_voltage:
        Fixed slack voltage vector.
    :param voltage_setpoint:
        PV voltage-magnitude targets.
    :param scheduled_power_germ:
        Germ scheduled power vector.
    :param scheduled_basis:
        Reduced scheduled-power basis with shape ``(dims, n_no_slack)``.
    :param table:
        Multi-index lookup table.
    :param u_coefficients:
        Voltage coefficients.
    :param x_coefficients:
        Reciprocal-voltage coefficients.
    :param q_coefficients:
        PV reactive-power coefficients.
    :param bus_names:
        Full bus names.
    :param branch_from_indices:
        Branch-from bus indices.
    :param branch_to_indices:
        Branch-to bus indices.
    :param branch_rates:
        Branch thermal ratings in MVA.
    :param sbase:
        System base power in MVA.
    :param dimension_names:
        Human-readable reduced coordinate names.
    :param recommended_coordinate_radius:
        Recommended absolute coordinate bound for random local queries.
    """

    __slots__ = (
        "_ybus",
        "_yf",
        "_yt",
        "_slack",
        "_pq",
        "_pv",
        "_no_slack",
        "_slack_voltage",
        "_voltage_setpoint",
        "_scheduled_power_germ",
        "_scheduled_basis",
        "_table",
        "_u_coefficients",
        "_x_coefficients",
        "_q_coefficients",
        "_bus_names",
        "_branch_from_indices",
        "_branch_to_indices",
        "_branch_rates",
        "_sbase",
        "_dimension_names",
        "_recommended_coordinate_radius",
    )

    def __init__(
        self,
        ybus: scipy.sparse.csc_matrix,
        yf: scipy.sparse.csc_matrix,
        yt: scipy.sparse.csc_matrix,
        slack: np.ndarray,
        pq: np.ndarray,
        pv: np.ndarray,
        no_slack: np.ndarray,
        slack_voltage: np.ndarray,
        voltage_setpoint: np.ndarray,
        scheduled_power_germ: np.ndarray,
        scheduled_basis: np.ndarray,
        table: MultiIndexTable,
        u_coefficients: np.ndarray,
        x_coefficients: np.ndarray,
        q_coefficients: np.ndarray,
        bus_names: np.ndarray,
        branch_from_indices: np.ndarray,
        branch_to_indices: np.ndarray,
        branch_rates: np.ndarray,
        sbase: float,
        dimension_names: np.ndarray,
        recommended_coordinate_radius: float,
    ) -> None:
        self._ybus: scipy.sparse.csc_matrix = ybus
        self._yf: scipy.sparse.csc_matrix = yf
        self._yt: scipy.sparse.csc_matrix = yt
        self._slack: np.ndarray = slack
        self._pq: np.ndarray = pq
        self._pv: np.ndarray = pv
        self._no_slack: np.ndarray = no_slack
        self._slack_voltage: np.ndarray = slack_voltage
        self._voltage_setpoint: np.ndarray = voltage_setpoint
        self._scheduled_power_germ: np.ndarray = scheduled_power_germ
        self._scheduled_basis: np.ndarray = scheduled_basis
        self._table: MultiIndexTable = table
        self._u_coefficients: np.ndarray = u_coefficients
        self._x_coefficients: np.ndarray = x_coefficients
        self._q_coefficients: np.ndarray = q_coefficients
        self._bus_names: np.ndarray = bus_names
        self._branch_from_indices: np.ndarray = branch_from_indices
        self._branch_to_indices: np.ndarray = branch_to_indices
        self._branch_rates: np.ndarray = branch_rates
        self._sbase: float = sbase
        self._dimension_names: np.ndarray = dimension_names
        self._recommended_coordinate_radius: float = recommended_coordinate_radius

    def get_dimensions_count(self) -> int:
        """
        Get the reduced subspace dimension count.

        :return:
            Number of reduced coordinates.
        """
        return int(self._scheduled_basis.shape[0])

    def get_max_order(self) -> int:
        """
        Get the maximum total polynomial order.

        :return:
            Maximum total order.
        """
        return self._table.get_max_order()

    def get_dimension_names(self) -> np.ndarray:
        """
        Get the reduced coordinate names.

        :return:
            Coordinate names.
        """
        return np.asarray(self._dimension_names, dtype=str)

    def get_recommended_coordinate_radius(self) -> float:
        """
        Get the recommended absolute coordinate bound.

        :return:
            Recommended coordinate radius.
        """
        return float(self._recommended_coordinate_radius)

    def get_scheduled_basis(self) -> np.ndarray:
        """
        Get the reduced scheduled-power basis.

        :return:
            Scheduled basis with shape ``(dims, n_no_slack)``.
        """
        return np.asarray(self._scheduled_basis, dtype=np.complex128)

    def get_voltage_coefficients(self) -> np.ndarray:
        """
        Get the stored voltage coefficients.

        :return:
            Voltage coefficients with shape ``(n_terms, n_no_slack)``.
        """
        return np.asarray(self._u_coefficients, dtype=np.complex128)

    def get_pv_reactive_power_coefficients(self) -> np.ndarray:
        """
        Get the stored PV reactive-power coefficients.

        :return:
            PV reactive-power coefficients with shape ``(n_terms, n_pv)``.
        """
        return np.asarray(self._q_coefficients, dtype=np.float64)

    def validate_grid(self, grid: "MultiCircuit") -> None:
        """
        Validate that a VeraGrid grid matches this artifact.

        :param grid:
            VeraGrid circuit to validate.
        :return:
            None.
        """
        bus_names: np.ndarray = np.asarray(grid.get_bus_names(), dtype=str)
        branch_count: int = int(grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True))

        if bus_names.shape == self._bus_names.shape and branch_count == self._branch_from_indices.size:
            if np.array_equal(bus_names, self._bus_names):
                pass
            else:
                raise ValueError("grid bus names do not match the artifact")
        else:
            raise ValueError("grid size does not match the artifact")

    def reconstruct_linear_scheduled_power(self, coordinates: np.ndarray) -> np.ndarray:
        """
        Rebuild the scheduled powers represented directly by the reduced coordinates.

        The returned vector keeps the original germ reactive powers on PV buses.
        That is the correct representation for scenario replay, because NR only
        consumes PQ ``P,Q`` and PV ``P`` while solving PV reactive powers itself.

        :param coordinates:
            Reduced coordinate vector.
        :return:
            Full scheduled complex bus-power vector in per unit.
        """
        coordinate_array: np.ndarray = np.asarray(coordinates, dtype=np.complex128)
        expected_shape: tuple[int, ...] = (self.get_dimensions_count(),)

        if coordinate_array.shape == expected_shape:
            scheduled_power: np.ndarray = np.array(self._scheduled_power_germ, dtype=np.complex128)
            scheduled_power[self._no_slack] = scheduled_power[self._no_slack] + coordinate_array @ self._scheduled_basis
        else:
            raise ValueError("coordinates has an unexpected shape")

        return scheduled_power

    def evaluate_coordinates(self, coordinates: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Evaluate the artifact at one reduced-coordinate point.

        :param coordinates:
            Reduced coordinate vector.
        :return:
            Tuple ``(voltage, scheduled_power, pv_reactive_power)``.
        """
        coordinate_array: np.ndarray = np.asarray(coordinates, dtype=np.complex128)
        expected_shape: tuple[int, ...] = (self.get_dimensions_count(),)

        if coordinate_array.shape == expected_shape:
            # The online stage stays cheap because the artifact is queried in a
            # low-dimensional coordinate space and the precomputed coefficient
            # tensor is collapsed by one dense weighted sum.
            weights: np.ndarray = calculate_monomial_weights_from_table(
                table=self._table,
                values=coordinate_array,
            )
            voltage: np.ndarray = np.zeros(self._ybus.shape[0], dtype=np.complex128)
            voltage[self._slack] = extract_slack_voltage_values(
                slack_voltage=self._slack_voltage,
                slack=self._slack,
                nbus=self._ybus.shape[0],
            )
            voltage[self._no_slack] = weights @ self._u_coefficients
            pv_reactive_power: np.ndarray = weights @ self._q_coefficients
            scheduled_power: np.ndarray = self.reconstruct_linear_scheduled_power(coordinates=coordinate_array)
            pv_index: int

            # The coordinate basis only prescribes PV active-power changes. The
            # PV reactive powers are supplied by the MDHEM Q series exactly as
            # in the per-bus artifact.
            for pv_index in range(self._pv.size):
                full_bus_index: int = int(self._pv[pv_index])
                scheduled_power[full_bus_index] = scheduled_power[full_bus_index].real + 1j * pv_reactive_power[pv_index]
        else:
            raise ValueError("coordinates has an unexpected shape")

        return voltage, scheduled_power, pv_reactive_power

    def query_coordinates(self, coordinates: np.ndarray, tolerance: float) -> MDHEMQueryResult:
        """
        Query the artifact with reduced coordinates.

        :param coordinates:
            Reduced coordinate vector.
        :param tolerance:
            Convergence-like tolerance for mismatch and PV voltage error.
        :return:
            MDHEM query result with voltages, flows and mismatch metrics.
        """
        voltage: np.ndarray
        scheduled_power: np.ndarray
        pv_reactive_power: np.ndarray
        voltage, scheduled_power, pv_reactive_power = self.evaluate_coordinates(coordinates=coordinates)
        calculated_power: np.ndarray = compute_power_from_ybus(ybus=self._ybus, voltage=voltage)
        mismatch_norm: float = calculate_query_mismatch_norm(
            calculated_power=calculated_power,
            scheduled_power=scheduled_power,
            no_slack=self._no_slack,
            pq=self._pq,
        )
        pv_voltage_error: float = calculate_pv_voltage_error(
            voltage=voltage,
            pv=self._pv,
            voltage_setpoint=self._voltage_setpoint,
        )
        branch_from_power: np.ndarray
        branch_to_power: np.ndarray
        branch_loading: np.ndarray
        branch_losses: np.ndarray
        branch_from_power, branch_to_power, branch_loading, branch_losses = calculate_branch_results(
            voltage=voltage,
            yf=self._yf,
            yt=self._yt,
            branch_from_indices=self._branch_from_indices,
            branch_to_indices=self._branch_to_indices,
            branch_rates=self._branch_rates,
            sbase=self._sbase,
        )
        converged_like: bool = bool(mismatch_norm <= tolerance and pv_voltage_error <= tolerance)
        linear_scheduled_power: np.ndarray = self.reconstruct_linear_scheduled_power(coordinates=coordinates)

        return MDHEMQueryResult(
            pq_active_power=np.asarray(linear_scheduled_power[self._pq].real, dtype=np.float64),
            pq_reactive_power=np.asarray(linear_scheduled_power[self._pq].imag, dtype=np.float64),
            pv_active_power=np.asarray(linear_scheduled_power[self._pv].real, dtype=np.float64),
            voltage=voltage,
            scheduled_power=scheduled_power,
            calculated_power=calculated_power,
            pv_reactive_power=pv_reactive_power,
            mismatch_norm=mismatch_norm,
            pv_voltage_error=pv_voltage_error,
            converged_like=converged_like,
            branch_from_power=branch_from_power,
            branch_to_power=branch_to_power,
            branch_loading=branch_loading,
            branch_losses=branch_losses,
        )

    def to_veragrid_power_flow_results(
        self,
        grid: "MultiCircuit",
        query_result: MDHEMQueryResult,
    ) -> "PowerFlowResults":
        """
        Convert one reduced-coordinate query into a VeraGrid ``PowerFlowResults``.

        :param grid:
            VeraGrid grid associated with the artifact.
        :param query_result:
            Query result to translate.
        :return:
            VeraGrid-like power-flow result object.
        """
        self.validate_grid(grid=grid)
        vg: object
        cf: object
        vg, cf = import_veragrid_engine_modules()
        _ = cf
        from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
        from VeraGridEngine.basic_structures import ConvergenceReport

        numerical_circuit: object = vg.compile_numerical_circuit_at(circuit=grid, t_idx=None)
        branch_from_current: np.ndarray = np.asarray(self._yf @ query_result.voltage, dtype=np.complex128)
        branch_to_current: np.ndarray = np.asarray(self._yt @ query_result.voltage, dtype=np.complex128)
        branch_voltage: np.ndarray = (
            query_result.voltage[self._branch_from_indices] - query_result.voltage[self._branch_to_indices]
        )
        results: PowerFlowResults = PowerFlowResults(
            n=grid.get_bus_number(),
            m=grid.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True),
            n_hvdc=grid.get_hvdc_number(),
            n_vsc=grid.get_vsc_number(),
            n_gen=grid.get_generation_like_number(),
            n_batt=grid.get_batteries_number(),
            n_sh=grid.get_shunt_like_device_number(),
            bus_names=grid.get_bus_names(),
            branch_names=grid.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True),
            hvdc_names=grid.get_hvdc_names(),
            vsc_names=grid.get_vsc_names(),
            gen_names=grid.get_generation_like_names(),
            batt_names=grid.get_battery_names(),
            sh_names=grid.get_shunt_like_devices_names(),
            bus_types=np.asarray(numerical_circuit.bus_data.bus_types),
        )
        results.voltage = np.asarray(query_result.voltage, dtype=np.complex128)
        results.Sbus = np.asarray(query_result.calculated_power, dtype=np.complex128)
        results.Sf = np.asarray(query_result.branch_from_power, dtype=np.complex128)
        results.St = np.asarray(query_result.branch_to_power, dtype=np.complex128)
        results.If = branch_from_current
        results.It = branch_to_current
        results.Vbranch = branch_voltage
        results.loading = np.asarray(query_result.branch_loading, dtype=np.complex128)
        results.losses = np.asarray(query_result.branch_losses, dtype=np.complex128)
        results.fill_circuit_info(grid=grid)
        report: ConvergenceReport = ConvergenceReport()
        report.add(
            method="MDHEM-Reduced",
            converged=bool(query_result.converged_like),
            error=float(max(query_result.mismatch_norm, query_result.pv_voltage_error)),
            elapsed=0.0,
            iterations=0,
        )
        results.convergence_reports.append(report)
        return results

    def power_flow_coordinates(
        self,
        grid: "MultiCircuit",
        coordinates: np.ndarray,
        tolerance: float,
    ) -> "PowerFlowResults":
        """
        Run one reduced-coordinate artifact-backed power flow.

        :param grid:
            VeraGrid grid associated with the artifact.
        :param coordinates:
            Reduced coordinate vector.
        :param tolerance:
            Convergence-like tolerance.
        :return:
            VeraGrid-like power-flow result.
        """
        query_result: MDHEMQueryResult = self.query_coordinates(coordinates=coordinates, tolerance=tolerance)
        return self.to_veragrid_power_flow_results(grid=grid, query_result=query_result)


def build_random_reduced_basis(
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    n_dimensions: int,
    random_seed: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Build balanced random full-network injection directions.

    Each basis row is one moderate full-network perturbation of:

    * PQ active power,
    * PQ reactive power,
    * PV active power.

    The rows are centered so the total active and PQ reactive perturbations stay
    close to balanced. That keeps the local subspace close to the operating
    point used to seed the artifact.

    :param case_data:
        Base compiled network data.
    :param mapping:
        Device-to-bus mapping used to respect mutable buses.
    :param n_dimensions:
        Number of reduced coordinates.
    :param random_seed:
        Random seed for the basis generation.
    :return:
        Tuple ``(scheduled_basis, dimension_names, recommended_coordinate_radius)``.
    """
    rng: np.random.Generator = np.random.default_rng(random_seed)
    n_no_slack: int = case_data.no_slack.size
    basis: np.ndarray = np.zeros((n_dimensions, n_no_slack), dtype=np.complex128)
    full_to_local: np.ndarray = create_full_to_local_lookup(nbus=case_data.ybus.shape[0], no_slack=case_data.no_slack)
    pq_active_scale: np.ndarray = np.maximum(mapping.pq_base_load_active_total_mw / case_data.sbase, 0.03)
    pq_reactive_scale: np.ndarray = np.maximum(
        np.abs(mapping.pq_base_load_reactive_total_mvar) / case_data.sbase,
        0.02,
    )
    pv_positive_generator_mask: np.ndarray = np.logical_and(
        mapping.pv_bus_mutable,
        mapping.pv_base_generator_active_total_mw > 1.0e-9,
    )
    pv_active_scale: np.ndarray = np.maximum(mapping.pv_base_generator_active_total_mw / case_data.sbase, 0.03)
    pq_active_scale = pq_active_scale * mapping.pq_bus_mutable.astype(np.float64)
    pq_reactive_scale = pq_reactive_scale * mapping.pq_bus_mutable.astype(np.float64)
    pv_active_scale = pv_active_scale * pv_positive_generator_mask.astype(np.float64)
    active_balance_reference: np.ndarray = (
        mapping.pv_base_generator_active_total_mw / case_data.sbase
    ) * pv_positive_generator_mask.astype(np.float64)
    reactive_balance_reference: np.ndarray = (np.abs(mapping.pq_base_net_reactive) + 1.0e-6) * mapping.pq_bus_mutable.astype(
        np.float64
    )
    active_balance_weights: np.ndarray = calculate_distribution_weights(reference_values=active_balance_reference)
    reactive_balance_weights: np.ndarray = calculate_distribution_weights(reference_values=reactive_balance_reference)
    dimension_names: list[str] = list()
    dimension_index: int

    # Each dimension is a full-network perturbation direction. That is the one
    # change that makes the artifact practical on 2000 buses: the dimension
    # count is now chosen by us instead of by the raw number of controllable
    # bus-power variables.
    for dimension_index in range(n_dimensions):
        pq_active_delta: np.ndarray = rng.normal(0.0, 0.08, size=case_data.pq.size) * pq_active_scale
        pq_reactive_delta: np.ndarray = rng.normal(0.0, 0.08, size=case_data.pq.size) * pq_reactive_scale
        pv_active_delta: np.ndarray = rng.normal(0.0, 0.06, size=case_data.pv.size) * pv_active_scale
        active_delta_sum: float = float(np.sum(pq_active_delta) + np.sum(pv_active_delta))
        reactive_delta_sum: float = float(np.sum(pq_reactive_delta))
        pv_active_delta = pv_active_delta - active_delta_sum * active_balance_weights
        pq_reactive_delta = pq_reactive_delta - reactive_delta_sum * reactive_balance_weights
        row: np.ndarray = np.zeros(n_no_slack, dtype=np.complex128)
        pq_index: int

        for pq_index in range(case_data.pq.size):
            local_index: int = int(full_to_local[int(case_data.pq[pq_index])])
            row[local_index] = pq_active_delta[pq_index] + 1j * pq_reactive_delta[pq_index]

        pv_index: int
        for pv_index in range(case_data.pv.size):
            local_index = int(full_to_local[int(case_data.pv[pv_index])])
            row[local_index] = row[local_index] + pv_active_delta[pv_index]

        basis[dimension_index, :] = row
        dimension_names.append(f"random_direction_{dimension_index + 1:02d}")

    # A small default radius is deliberate. The artifact is meant to be a
    # local fast surrogate around the physical germ, and the parity target on a
    # 2000-bus system is much easier to defend than a wide but loose range.
    recommended_coordinate_radius: float = 0.02
    return basis, np.asarray(dimension_names, dtype=str), recommended_coordinate_radius


def solve_reduced_subspace_artifact(
    input_data: VeraGridQueryCaseData,
    germ_voltage: np.ndarray,
    germ_power: np.ndarray,
    scheduled_basis: np.ndarray,
    dimension_names: np.ndarray,
    max_order: int,
    recommended_coordinate_radius: float,
) -> MDHEMReducedSubspacePVArtifact:
    """
    Solve the reduced-coordinate MDHEM-PV coefficients.

    :param input_data:
        Compiled VeraGrid network data.
    :param germ_voltage:
        Germ bus-voltage vector.
    :param germ_power:
        Germ scheduled power vector.
    :param scheduled_basis:
        Reduced scheduled-power basis with shape ``(dims, n_no_slack)``.
    :param dimension_names:
        Human-readable reduced coordinate names.
    :param max_order:
        Maximum total polynomial order.
    :param recommended_coordinate_radius:
        Recommended local coordinate radius.
    :return:
        Built reduced-coordinate artifact.
    """
    n_no_slack: int = input_data.no_slack.size
    n_pv: int = input_data.pv.size
    n_dimensions: int = scheduled_basis.shape[0]
    voltage_setpoint: np.ndarray = np.asarray(input_data.voltage_setpoint, dtype=np.float64).copy()

    # The local artifact is centered around the chosen physical germ. Using the
    # germ magnitudes here makes the convergence-like PV check reflect the
    # operating surface that the artifact is actually built around, instead of
    # relying on imported setpoints that may not match the solved germ on large
    # public test cases.
    if input_data.pv.size > 0:
        voltage_setpoint[input_data.pv] = np.abs(germ_voltage[input_data.pv])
    else:
        pass

    if scheduled_basis.shape == (n_dimensions, n_no_slack):
        pass
    else:
        raise ValueError("scheduled_basis must have shape (dims, n_no_slack)")

    table: MultiIndexTable = create_multi_index_table(dims=n_dimensions, max_order=max_order)
    n_terms: int = table.get_terms_count()
    u_coefficients: np.ndarray = np.zeros((n_terms, n_no_slack), dtype=np.complex128)
    x_coefficients: np.ndarray = np.zeros((n_terms, n_no_slack), dtype=np.complex128)
    q_coefficients: np.ndarray = np.zeros((n_terms, n_pv), dtype=np.float64)
    pv_local: np.ndarray = np.zeros(input_data.pv.size, dtype=np.int64)
    full_to_local: np.ndarray = create_full_to_local_lookup(nbus=input_data.ybus.shape[0], no_slack=input_data.no_slack)
    pv_index: int

    for pv_index in range(input_data.pv.size):
        pv_local[pv_index] = int(full_to_local[int(input_data.pv[pv_index])])

    yred: scipy.sparse.csc_matrix = input_data.ybus[np.ix_(input_data.no_slack, input_data.no_slack)].tocsc()
    u_zero: np.ndarray = germ_voltage[input_data.no_slack].copy()
    x_zero: np.ndarray = 1.0 / np.conj(u_zero)
    c_germ: np.ndarray = np.conj(germ_power[input_data.no_slack])
    zero_position: int = 0
    u_coefficients[zero_position, :] = u_zero
    x_coefficients[zero_position, :] = x_zero

    # The Q series starts from the chosen physical germ so the reduced
    # coordinates still preserve the PV-voltage control structure.
    for pv_index in range(n_pv):
        q_coefficients[zero_position, pv_index] = germ_power[int(input_data.pv[pv_index])].imag

    system_matrix: scipy.sparse.csc_matrix = build_system_matrix(
        yred=yred,
        c_germ=c_germ,
        u_zero=u_zero,
        x_zero=x_zero,
        pv_local=pv_local,
    )
    basis_conjugate: np.ndarray = np.conj(scheduled_basis)
    linear_solver: SparseLinearSolver = SparseLinearSolver(
        factorization=scipy.sparse.linalg.splu(system_matrix)
    )
    unknown_count: int = 4 * n_no_slack + n_pv
    rhs_block_columns: int = determine_rhs_block_columns(
        unknown_count=unknown_count,
        target_block_bytes=64 * 1024 * 1024,
    )
    order_index: int

    # The sparse factorization is reused for every coefficient. Only the right
    # hand side changes with the reduced-coordinate convolution terms.
    for order_index in range(1, max_order + 1):
        order_start: int = table.get_order_start(order_index)
        order_stop: int = table.get_order_stop(order_index)
        block_start: int = order_start

        while block_start < order_stop:
            block_stop: int = min(order_stop, block_start + rhs_block_columns)
            block_size: int = block_stop - block_start
            rhs_block: np.ndarray = np.zeros((unknown_count, block_size), dtype=np.float64)
            block_offset: int

            for block_offset in range(block_size):
                position: int = block_start + block_offset
                active_dims_row: np.ndarray = table.get_active_dimension_positions(position)
                minus_e_previous_row: np.ndarray = table.get_minus_e_previous_positions(position)
                qx_known: np.ndarray = calculate_known_qx_convolution(
                    table=table,
                    position=position,
                    q_coefficients=q_coefficients,
                    x_coefficients=x_coefficients,
                    pv_local=pv_local,
                )
                rhs_power: np.ndarray = calculate_rhs_power_numba(
                    active_dims_row=active_dims_row,
                    minus_e_previous_row=minus_e_previous_row,
                    basis_conjugate=basis_conjugate,
                    x_coefficients=x_coefficients,
                    pv_local=pv_local,
                    qx_known=qx_known,
                )
                reciprocal_known: np.ndarray = calculate_known_reciprocal_convolution(
                    table=table,
                    position=position,
                    u_coefficients=u_coefficients,
                    x_coefficients=x_coefficients,
                )
                voltage_known: np.ndarray = calculate_known_voltage_convolution(
                    table=table,
                    position=position,
                    u_coefficients=u_coefficients,
                    pv_local=pv_local,
                )
                rhs_block[0:n_no_slack, block_offset] = rhs_power.real
                rhs_block[n_no_slack:2 * n_no_slack, block_offset] = rhs_power.imag
                rhs_block[2 * n_no_slack:3 * n_no_slack, block_offset] = -reciprocal_known.real
                rhs_block[3 * n_no_slack:4 * n_no_slack, block_offset] = -reciprocal_known.imag
                rhs_block[4 * n_no_slack:4 * n_no_slack + n_pv, block_offset] = -voltage_known

            solution_block: np.ndarray = linear_solver.solve(rhs=rhs_block)

            for block_offset in range(block_size):
                position = block_start + block_offset
                u_coefficients[position, :] = (
                    solution_block[0:n_no_slack, block_offset]
                    + 1j * solution_block[n_no_slack:2 * n_no_slack, block_offset]
                )
                x_coefficients[position, :] = (
                    solution_block[2 * n_no_slack:3 * n_no_slack, block_offset]
                    + 1j * solution_block[3 * n_no_slack:4 * n_no_slack, block_offset]
                )
                q_coefficients[position, :] = solution_block[
                    4 * n_no_slack:4 * n_no_slack + n_pv,
                    block_offset,
                ]

            block_start = block_stop

    return MDHEMReducedSubspacePVArtifact(
        ybus=input_data.ybus,
        yf=input_data.yf,
        yt=input_data.yt,
        slack=input_data.slack,
        pq=input_data.pq,
        pv=input_data.pv,
        no_slack=input_data.no_slack,
        slack_voltage=input_data.slack_voltage,
        voltage_setpoint=voltage_setpoint,
        scheduled_power_germ=germ_power,
        scheduled_basis=scheduled_basis,
        table=table,
        u_coefficients=u_coefficients,
        x_coefficients=x_coefficients,
        q_coefficients=q_coefficients,
        bus_names=input_data.bus_names,
        branch_from_indices=input_data.branch_from_indices,
        branch_to_indices=input_data.branch_to_indices,
        branch_rates=input_data.branch_rates,
        sbase=input_data.sbase,
        dimension_names=dimension_names,
        recommended_coordinate_radius=recommended_coordinate_radius,
    )


def build_reduced_subspace_artifact_from_case(
    grid: "MultiCircuit",
    max_order: int,
    n_dimensions: int,
    random_seed: int,
    germ_seed_results: Optional["PowerFlowResults"],
) -> tuple[VeraGridQueryCaseData, MDHEMReducedSubspacePVArtifact, float]:
    """
    Build a reduced-coordinate artifact from one VeraGrid grid.

    :param grid:
        Base VeraGrid grid.
    :param max_order:
        Maximum total polynomial order.
    :param n_dimensions:
        Number of reduced coordinates.
    :param random_seed:
        Random seed used to create the reduced basis.
    :param germ_seed_results:
        Optional converged power-flow result used as the physical germ.
    :return:
        Tuple ``(case_data, artifact, germ_error)``.
    """
    input_data: VeraGridQueryCaseData = create_mdhelm_inputs(grid=grid)
    mapping: DeviceBusMapping = build_device_bus_mapping(grid=grid, case_data=input_data)
    scheduled_basis: np.ndarray
    dimension_names: np.ndarray
    recommended_coordinate_radius: float
    scheduled_basis, dimension_names, recommended_coordinate_radius = build_random_reduced_basis(
        case_data=input_data,
        mapping=mapping,
        n_dimensions=n_dimensions,
        random_seed=random_seed,
    )
    germ_voltage: np.ndarray
    germ_power: np.ndarray
    germ_error: float
    germ_voltage, germ_power, germ_error = solve_physical_germ(
        grid=grid,
        case_data=input_data,
        germ_seed_results=germ_seed_results,
    )
    artifact: MDHEMReducedSubspacePVArtifact = solve_reduced_subspace_artifact(
        input_data=input_data,
        germ_voltage=germ_voltage,
        germ_power=germ_power,
        scheduled_basis=scheduled_basis,
        dimension_names=dimension_names,
        max_order=max_order,
        recommended_coordinate_radius=recommended_coordinate_radius,
    )
    return input_data, artifact, germ_error


def save_reduced_subspace_artifact(path: Path, artifact: MDHEMReducedSubspacePVArtifact) -> None:
    """
    Save the reduced-coordinate artifact to one compressed ``npz`` file.

    :param path:
        Output artifact path.
    :param artifact:
        Artifact to save.
    :return:
        None.
    """
    entries: dict[str, np.ndarray] = dict()
    store_csc_matrix(entries=entries, prefix="ybus", matrix=artifact._ybus)
    store_csc_matrix(entries=entries, prefix="yf", matrix=artifact._yf)
    store_csc_matrix(entries=entries, prefix="yt", matrix=artifact._yt)
    entries["slack"] = artifact._slack
    entries["pq"] = artifact._pq
    entries["pv"] = artifact._pv
    entries["no_slack"] = artifact._no_slack
    entries["slack_voltage"] = artifact._slack_voltage
    entries["voltage_setpoint"] = artifact._voltage_setpoint
    entries["scheduled_power_germ"] = artifact._scheduled_power_germ
    entries["scheduled_basis"] = artifact._scheduled_basis
    entries["u_coefficients"] = artifact._u_coefficients
    entries["x_coefficients"] = artifact._x_coefficients
    entries["q_coefficients"] = artifact._q_coefficients
    entries["bus_names"] = artifact._bus_names
    entries["branch_from_indices"] = artifact._branch_from_indices
    entries["branch_to_indices"] = artifact._branch_to_indices
    entries["branch_rates"] = artifact._branch_rates
    entries["sbase"] = np.asarray([artifact._sbase], dtype=np.float64)
    entries["max_order"] = np.asarray([artifact._table.get_max_order()], dtype=np.int64)
    entries["dims"] = np.asarray([artifact.get_dimensions_count()], dtype=np.int64)
    entries["dimension_names"] = artifact._dimension_names
    entries["recommended_coordinate_radius"] = np.asarray([artifact._recommended_coordinate_radius], dtype=np.float64)
    np.savez_compressed(path, **entries)


def load_reduced_subspace_artifact(path: Path) -> MDHEMReducedSubspacePVArtifact:
    """
    Load the reduced-coordinate artifact from disk.

    :param path:
        Artifact path.
    :return:
        Restored reduced-coordinate artifact.
    """
    with np.load(path, allow_pickle=False) as data:
        ybus: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix="ybus")
        yf: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix="yf")
        yt: scipy.sparse.csc_matrix = restore_csc_matrix(data=data, prefix="yt")
        dims: int = int(data["dims"][0])
        max_order: int = int(data["max_order"][0])
        table: MultiIndexTable = create_multi_index_table(dims=dims, max_order=max_order)
        artifact: MDHEMReducedSubspacePVArtifact = MDHEMReducedSubspacePVArtifact(
            ybus=ybus,
            yf=yf,
            yt=yt,
            slack=np.asarray(data["slack"], dtype=np.int64),
            pq=np.asarray(data["pq"], dtype=np.int64),
            pv=np.asarray(data["pv"], dtype=np.int64),
            no_slack=np.asarray(data["no_slack"], dtype=np.int64),
            slack_voltage=np.asarray(data["slack_voltage"], dtype=np.complex128),
            voltage_setpoint=np.asarray(data["voltage_setpoint"], dtype=np.float64),
            scheduled_power_germ=np.asarray(data["scheduled_power_germ"], dtype=np.complex128),
            scheduled_basis=np.asarray(data["scheduled_basis"], dtype=np.complex128),
            table=table,
            u_coefficients=np.asarray(data["u_coefficients"], dtype=np.complex128),
            x_coefficients=np.asarray(data["x_coefficients"], dtype=np.complex128),
            q_coefficients=np.asarray(data["q_coefficients"], dtype=np.float64),
            bus_names=np.asarray(data["bus_names"], dtype=str),
            branch_from_indices=np.asarray(data["branch_from_indices"], dtype=np.int64),
            branch_to_indices=np.asarray(data["branch_to_indices"], dtype=np.int64),
            branch_rates=np.asarray(data["branch_rates"], dtype=np.float64),
            sbase=float(data["sbase"][0]),
            dimension_names=np.asarray(data["dimension_names"], dtype=str),
            recommended_coordinate_radius=float(data["recommended_coordinate_radius"][0]),
        )

    return artifact


def create_nr_seed_results(grid: "MultiCircuit") -> "PowerFlowResults":
    """
    Run one NR solve to seed the large-grid artifact around a physical operating point.

    :param grid:
        VeraGrid grid.
    :return:
        Converged NR result.
    """
    vg: object
    cf: object
    vg, cf = import_veragrid_engine_modules()
    _ = cf
    nr_results: "PowerFlowResults" = vg.power_flow(
        grid=grid,
        options=create_nr_options(vg=vg),
    )
    return nr_results


def create_coordinate_scenarios(
    artifact: MDHEMReducedSubspacePVArtifact,
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    scenario_count: int,
    random_seed: int,
    coordinate_radius: float,
) -> list[ReducedSubspaceScenario]:
    """
    Create the random reduced-coordinate scenario batch.

    :param artifact:
        Trained reduced-coordinate artifact.
    :param case_data:
        Base compiled case data.
    :param mapping:
        Device-to-bus mapping used to reject non-physical replay points.
    :param scenario_count:
        Number of scenarios including the base point.
    :param random_seed:
        Scenario random seed.
    :param coordinate_radius:
        Absolute coordinate bound used in the random queries.
    :return:
        Scenario list.
    """
    zero_clip_tolerance: float = 1.0e-12
    scenarios: list[ReducedSubspaceScenario] = list()
    zero_coordinates: np.ndarray = np.zeros(artifact.get_dimensions_count(), dtype=np.float64)
    base_linear_power: np.ndarray = artifact.reconstruct_linear_scheduled_power(coordinates=zero_coordinates)
    base_linear_power.real[np.abs(base_linear_power.real) < zero_clip_tolerance] = 0.0
    base_linear_power.imag[np.abs(base_linear_power.imag) < zero_clip_tolerance] = 0.0
    scenarios.append(
        ReducedSubspaceScenario(
            name="base",
            coordinates=zero_coordinates,
            pq_active_power=base_linear_power[artifact._pq].real.copy(),
            pq_reactive_power=base_linear_power[artifact._pq].imag.copy(),
            pv_active_power=base_linear_power[artifact._pv].real.copy(),
            active_delta_sum=0.0,
            reactive_delta_sum=0.0,
        )
    )
    rng: np.random.Generator = np.random.default_rng(random_seed)
    scenario_index: int = 1

    while scenario_index < scenario_count:
        shrink_factor: float = 1.0
        trial_index: int = 0
        scenario_created: bool = False

        while trial_index < 8 and scenario_created is False:
            coordinates: np.ndarray = shrink_factor * rng.uniform(
                low=-coordinate_radius,
                high=coordinate_radius,
                size=artifact.get_dimensions_count(),
            )
            linear_power: np.ndarray = artifact.reconstruct_linear_scheduled_power(coordinates=coordinates)
            linear_power.real[np.abs(linear_power.real) < zero_clip_tolerance] = 0.0
            linear_power.imag[np.abs(linear_power.imag) < zero_clip_tolerance] = 0.0
            active_delta_sum: float = float(
                np.sum(linear_power[artifact._no_slack].real - artifact._scheduled_power_germ[artifact._no_slack].real)
            )
            reactive_delta_sum: float = float(
                np.sum(linear_power[artifact._pq].imag - artifact._scheduled_power_germ[artifact._pq].imag)
            )
            scenario: ReducedSubspaceScenario = ReducedSubspaceScenario(
                name=f"random_{scenario_index:02d}",
                coordinates=np.asarray(coordinates, dtype=np.float64),
                pq_active_power=linear_power[artifact._pq].real.copy(),
                pq_reactive_power=linear_power[artifact._pq].imag.copy(),
                pv_active_power=linear_power[artifact._pv].real.copy(),
                active_delta_sum=active_delta_sum,
                reactive_delta_sum=reactive_delta_sum,
            )

            if scenario_is_physical(mapping=mapping, case_data=case_data, scenario=scenario):
                scenarios.append(scenario)
                scenario_created = True
            else:
                shrink_factor = 0.5 * shrink_factor

            trial_index = trial_index + 1

        if scenario_created:
            scenario_index = scenario_index + 1
        else:
            raise RuntimeError(f"Could not create a physical scenario for index {scenario_index}")

    return scenarios


def evaluate_coordinate_scenario(
    base_grid: "MultiCircuit",
    case_data: VeraGridQueryCaseData,
    mapping: DeviceBusMapping,
    artifact: MDHEMReducedSubspacePVArtifact,
    scenario: ReducedSubspaceScenario,
    artifact_tolerance: float,
    voltage_threshold: float,
    branch_flow_threshold_mva: float,
    loading_threshold: float,
    injection_write_threshold: float,
) -> ReducedSubspaceMetrics:
    """
    Evaluate one reduced-coordinate scenario against the external NR reference.

    :param base_grid:
        Base VeraGrid grid.
    :param case_data:
        Base compiled case data.
    :param mapping:
        Device-to-bus mapping.
    :param artifact:
        Trained reduced-coordinate artifact.
    :param scenario:
        Scenario to evaluate.
    :param artifact_tolerance:
        Internal artifact tolerance.
    :param voltage_threshold:
        Voltage pass threshold.
    :param branch_flow_threshold_mva:
        Branch-flow pass threshold.
    :param loading_threshold:
        Loading pass threshold.
    :param injection_write_threshold:
        Injection write pass threshold.
    :return:
        Scenario metrics.
    """
    artifact_result: MDHEMQueryResult = artifact.query_coordinates(
        coordinates=scenario.coordinates,
        tolerance=artifact_tolerance,
    )
    nr_results: "PowerFlowResults"
    modified_case_data: VeraGridQueryCaseData
    nr_results, modified_case_data = run_newton_reference(
        base_grid=base_grid,
        case_data=case_data,
        mapping=mapping,
        scenario=scenario,
    )
    injection_write_error: float = calculate_injection_write_error(
        modified_case_data=modified_case_data,
        scenario=scenario,
    )
    max_voltage_diff: float
    max_flow_diff_mva: float
    max_loading_diff: float
    max_voltage_diff, max_flow_diff_mva, max_loading_diff = compare_artifact_with_nr(
        artifact_result=artifact_result,
        nr_results=nr_results,
    )
    passed: bool = False

    if nr_results.converged:
        if artifact_result.converged_like:
            if injection_write_error <= injection_write_threshold:
                if max_voltage_diff <= voltage_threshold:
                    if max_flow_diff_mva <= branch_flow_threshold_mva:
                        if max_loading_diff <= loading_threshold:
                            passed = True
                        else:
                            passed = False
                    else:
                        passed = False
                else:
                    passed = False
            else:
                passed = False
        else:
            passed = False
    else:
        passed = False

    return ReducedSubspaceMetrics(
        scenario_name=scenario.name,
        nr_converged=bool(nr_results.converged),
        artifact_converged=bool(artifact_result.converged_like),
        injection_write_error=injection_write_error,
        nr_error=float(nr_results.error),
        artifact_error=float(artifact_result.mismatch_norm),
        max_voltage_diff=max_voltage_diff,
        max_flow_diff_mva=max_flow_diff_mva,
        max_loading_diff=max_loading_diff,
        passed=passed,
    )


def write_reduced_subspace_report(
    report_path: Path,
    case_path: Path,
    artifact_path: Path,
    n_dimensions: int,
    max_order: int,
    coordinate_radius: float,
    germ_error: float,
    scenarios: list[ReducedSubspaceScenario],
    metrics_list: list[ReducedSubspaceMetrics],
) -> None:
    """
    Write the local ACTIVSg2000 markdown report.

    :param report_path:
        Output markdown path.
    :param case_path:
        MATPOWER case path.
    :param artifact_path:
        Saved artifact path.
    :param n_dimensions:
        Reduced coordinate count.
    :param max_order:
        Maximum polynomial order.
    :param coordinate_radius:
        Scenario coordinate radius.
    :param germ_error:
        Artifact germ error.
    :param scenarios:
        Scenario list.
    :param metrics_list:
        Scenario metrics.
    :return:
        None.
    """
    lines: list[str] = list()
    lines.append("# ACTIVSg2000 Reduced MDHEM-PV Local Report")
    lines.append("")
    lines.append(f"Generated: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"Case file: `{case_path}`")
    lines.append(f"Artifact file: `{artifact_path}`")
    lines.append("")
    lines.append("## Model")
    lines.append("")
    lines.append("This artifact uses a small random balanced injection subspace instead of one independent variable per bus quantity.")
    lines.append("The query path is MDHEM-only.")
    lines.append("NR is used only as the physical germ seed and as the external comparison reference.")
    lines.append("")
    lines.append("## Settings")
    lines.append("")
    lines.append(f"- `n_dimensions = {n_dimensions}`")
    lines.append(f"- `max_order = {max_order}`")
    lines.append(f"- `coordinate_radius = {coordinate_radius:.4f}`")
    lines.append(f"- `germ_error = {germ_error:.4e}`")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| scenario | dP sum | dQ sum | nr conv | art conv | write err | nr err | art err | max dV | max dSf | max dloading | passed |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    worst_voltage_diff: float = 0.0
    worst_flow_diff_mva: float = 0.0
    worst_loading_diff: float = 0.0
    passed_count: int = 0
    scenario_index: int

    for scenario_index in range(len(scenarios)):
        scenario: ReducedSubspaceScenario = scenarios[scenario_index]
        metrics: ReducedSubspaceMetrics = metrics_list[scenario_index]
        lines.append(
            f"| {scenario.name} | "
            f"{scenario.active_delta_sum:+.3e} | "
            f"{scenario.reactive_delta_sum:+.3e} | "
            f"{metrics.nr_converged} | "
            f"{metrics.artifact_converged} | "
            f"{metrics.injection_write_error:.3e} | "
            f"{metrics.nr_error:.3e} | "
            f"{metrics.artifact_error:.3e} | "
            f"{metrics.max_voltage_diff:.3e} | "
            f"{metrics.max_flow_diff_mva:.3e} | "
            f"{metrics.max_loading_diff:.3e} | "
            f"{metrics.passed} |"
        )
        if metrics.passed:
            passed_count = passed_count + 1
        else:
            passed_count = passed_count + 0
        worst_voltage_diff = max(worst_voltage_diff, metrics.max_voltage_diff)
        worst_flow_diff_mva = max(worst_flow_diff_mva, metrics.max_flow_diff_mva)
        worst_loading_diff = max(worst_loading_diff, metrics.max_loading_diff)

    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- passed scenarios: `{passed_count}/{len(metrics_list)}`")
    lines.append(f"- worst voltage diff: `{worst_voltage_diff:.4e}` p.u.")
    lines.append(f"- worst branch flow diff: `{worst_flow_diff_mva:.4e}` MVA")
    lines.append(f"- worst loading diff: `{worst_loading_diff:.4e}`")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def run_activsg2000_local_artifact_demo() -> None:
    """
    Build, save, load and validate the reduced-coordinate ACTIVSg2000 artifact.

    :return:
        None.
    """
    case_path: Path = Path(__file__).resolve().with_name("case_ACTIVSg2000.matpower")
    artifact_path: Path = Path(__file__).resolve().with_name("mdhelm_pv_activsg2000_local_artifact.npz")
    report_path: Path = Path(__file__).resolve().with_name("mdhelm_pv_activsg2000_local_report.md")
    max_order: int = 4
    n_dimensions: int = 6
    basis_seed: int = 2000
    scenario_seed: int = 2001
    scenario_count: int = 5
    artifact_tolerance: float = 1.0e-6
    voltage_threshold: float = 1.0e-3
    branch_flow_threshold_mva: float = 1.0
    loading_threshold: float = 2.0e-3
    injection_write_threshold: float = 2.0e-6
    base_grid: "MultiCircuit" = load_multicircuit_from_file(matpower_path=case_path)
    nr_seed_results: "PowerFlowResults" = create_nr_seed_results(grid=base_grid)
    case_data: VeraGridQueryCaseData
    artifact: MDHEMReducedSubspacePVArtifact
    germ_error: float
    case_data, artifact, germ_error = build_reduced_subspace_artifact_from_case(
        grid=base_grid,
        max_order=max_order,
        n_dimensions=n_dimensions,
        random_seed=basis_seed,
        germ_seed_results=nr_seed_results,
    )
    save_reduced_subspace_artifact(path=artifact_path, artifact=artifact)
    restored_artifact: MDHEMReducedSubspacePVArtifact = load_reduced_subspace_artifact(path=artifact_path)
    mapping: DeviceBusMapping = build_device_bus_mapping(grid=base_grid, case_data=case_data)
    coordinate_radius: float = restored_artifact.get_recommended_coordinate_radius()
    scenarios: list[ReducedSubspaceScenario] = create_coordinate_scenarios(
        artifact=restored_artifact,
        case_data=case_data,
        mapping=mapping,
        scenario_count=scenario_count,
        random_seed=scenario_seed,
        coordinate_radius=coordinate_radius,
    )
    metrics_list: list[ReducedSubspaceMetrics] = list()
    scenario: ReducedSubspaceScenario

    for scenario in scenarios:
        metrics: ReducedSubspaceMetrics = evaluate_coordinate_scenario(
            base_grid=base_grid,
            case_data=case_data,
            mapping=mapping,
            artifact=restored_artifact,
            scenario=scenario,
            artifact_tolerance=artifact_tolerance,
            voltage_threshold=voltage_threshold,
            branch_flow_threshold_mva=branch_flow_threshold_mva,
            loading_threshold=loading_threshold,
            injection_write_threshold=injection_write_threshold,
        )
        metrics_list.append(metrics)

    write_reduced_subspace_report(
        report_path=report_path,
        case_path=case_path,
        artifact_path=artifact_path,
        n_dimensions=n_dimensions,
        max_order=max_order,
        coordinate_radius=coordinate_radius,
        germ_error=germ_error,
        scenarios=scenarios,
        metrics_list=metrics_list,
    )

    print("\nACTIVSg2000 reduced MDHEM-PV local artifact")
    print("-------------------------------------------")
    print(f"Artifact path:           {artifact_path}")
    print(f"Report path:             {report_path}")
    print(f"Germ residual:           {germ_error:.4e}")
    print(f"Reduced dimensions:      {restored_artifact.get_dimensions_count()}")
    print(f"Maximum order:           {restored_artifact.get_max_order()}")
    print(f"Coordinate radius:       {coordinate_radius:.4f}")
    print(f"Scenarios:               {len(scenarios)}")
    metrics: ReducedSubspaceMetrics
    for metrics in metrics_list:
        print(
            f"{metrics.scenario_name}: "
            f"nr={metrics.nr_converged}, "
            f"art={metrics.artifact_converged}, "
            f"max_dV={metrics.max_voltage_diff:.3e}, "
            f"max_dSf={metrics.max_flow_diff_mva:.3e}, "
            f"passed={metrics.passed}"
        )


if __name__ == "__main__":
    run_activsg2000_local_artifact_demo()
