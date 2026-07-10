from __future__ import annotations

import numpy as np
from scipy.sparse import csc_matrix

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation import PfBasicFormulation
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import (
    NumericPowerFlowResults,
    PowerFlowResults,
)
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from VeraGridEngine.Topology.admittance_matrices import AdmittanceMatrices
from VeraGridEngine.Topology.simulation_indices import SimulationIndices

from power_flow_atlas.builder import build_power_flow_atlas_patch, finalize_power_flow_atlas
from power_flow_atlas.enumerations import (
    AtlasBuildStatus,
    AtlasFallbackMode,
    AtlasQueryStatus,
)
from power_flow_atlas.model import (
    AtlasBuildResult,
    AtlasPatchBuildResult,
    DirectionalSeriesResult,
    FixedRegimeResidual,
    PatchSelectionResult,
    PowerFlowAtlas,
    PowerFlowAtlasPatch,
)
from power_flow_atlas.options import PowerFlowAtlasOptions
from power_flow_atlas.rectangular_series import (
    build_topology_signature,
    calculate_directional_voltage_series,
    calculate_fixed_regime_residual,
)
from power_flow_atlas.selector import select_nearest_atlas_patch


class VeraGridAtlasQueryResult:
    """Certified atlas output together with optional native VeraGrid results."""

    __slots__ = (
        "_status",
        "_message",
        "_patch_id",
        "_normalized_distance",
        "_residual_norm",
        "_voltage_coefficients",
        "_voltage",
        "_numeric_results",
        "_power_flow_results",
    )

    def __init__(
        self,
        status: AtlasQueryStatus,
        message: str,
        patch_id: int,
        normalized_distance: float,
        residual_norm: float,
        voltage_coefficients: np.ndarray,
        voltage: np.ndarray,
        numeric_results: NumericPowerFlowResults | None,
        power_flow_results: PowerFlowResults | None,
    ) -> None:
        """Create a VeraGrid atlas query result.

        :param status: Final query status.
        :param message: Human-readable diagnostic.
        :param patch_id: Stable selected patch identifier.
        :param normalized_distance: First-order patch distance.
        :param residual_norm: Exact fixed-regime residual in p.u.
        :param voltage_coefficients: Per-order, per-bus series coefficients.
        :param voltage: Returned complex bus voltage in p.u.
        :param numeric_results: Native single-formulation VeraGrid results.
        :param power_flow_results: Native full VeraGrid fallback results.
        """
        self._status: AtlasQueryStatus = status
        self._message: str = message
        self._patch_id: int = patch_id
        self._normalized_distance: float = normalized_distance
        self._residual_norm: float = residual_norm
        self._voltage_coefficients: np.ndarray = voltage_coefficients
        self._voltage: np.ndarray = voltage
        self._numeric_results: NumericPowerFlowResults | None = numeric_results
        self._power_flow_results: PowerFlowResults | None = power_flow_results

    def get_status(self) -> AtlasQueryStatus:
        """Return the final query status."""
        return self._status

    def get_message(self) -> str:
        """Return the query diagnostic."""
        return self._message

    def get_patch_id(self) -> int:
        """Return the stable selected patch identifier."""
        return self._patch_id

    def get_normalized_distance(self) -> float:
        """Return the first-order normalized patch distance."""
        return self._normalized_distance

    def get_residual_norm(self) -> float:
        """Return the exact fixed-regime residual in p.u."""
        return self._residual_norm

    def get_voltage_coefficients(self) -> np.ndarray:
        """Return a copy of the per-order, per-bus voltage coefficients."""
        return self._voltage_coefficients.copy()

    def get_voltage(self) -> np.ndarray:
        """Return a copy of the returned complex bus voltage."""
        return self._voltage.copy()

    def get_numeric_results(self) -> NumericPowerFlowResults | None:
        """Return native VeraGrid chart or correction results when available."""
        return self._numeric_results

    def get_power_flow_results(self) -> PowerFlowResults | None:
        """Return native VeraGrid full-fallback results when available."""
        return self._power_flow_results


class VeraGridPowerFlowAtlasBuilder:
    """Build classical AC atlas patches from solved VeraGrid operating points."""

    __slots__ = ("_numerical_circuit", "_atlas_options", "_logger")

    def __init__(
        self,
        numerical_circuit: NumericalCircuit,
        atlas_options: PowerFlowAtlasOptions,
        logger: Logger,
    ) -> None:
        """Create a VeraGrid atlas builder.

        :param numerical_circuit: Compiled VeraGrid numerical circuit.
        :param atlas_options: Atlas construction and query options.
        :param logger: VeraGrid logger receiving compatibility diagnostics.
        """
        self._numerical_circuit: NumericalCircuit = numerical_circuit
        self._atlas_options: PowerFlowAtlasOptions = atlas_options
        self._logger: Logger = logger

    def build_from_injection_scenarios(
        self,
        scenario_s_mva: np.ndarray,
        power_flow_options: PowerFlowOptions,
    ) -> AtlasBuildResult:
        """Solve an injection matrix with VeraGrid and build one chart per row.

        Scenarios are solved sequentially. The previous converged voltage is
        used as the next initial guess, which makes an ordered continuation-like
        scenario matrix inexpensive while preserving VeraGrid as the authority
        for every offline anchor.

        :param scenario_s_mva: Complex matrix shaped ``(scenario, bus)`` in MVA.
        :param power_flow_options: VeraGrid options used for offline anchor solves.
        :return: Explicit atlas-build result.
        """
        scenario_array: np.ndarray = np.asarray(
            scenario_s_mva,
            dtype=np.complex128,
        )
        shape_valid: bool = bool(
            scenario_array.ndim == 2
            and scenario_array.shape[0] > 0
            and scenario_array.shape[1] == self._numerical_circuit.nbus
        )
        values_finite: bool = bool(np.all(np.isfinite(scenario_array)))
        bus_types_frozen: bool = bool(not power_flow_options.control_Q)
        result: AtlasBuildResult

        if shape_valid and values_finite and bus_types_frozen:
            scenario_count: int = int(scenario_array.shape[0])
            anchor_array: np.ndarray = np.empty(scenario_count, dtype=object)
            voltage_guess: np.ndarray | None = None
            all_converged: bool = True
            failed_scenario_index: int = -1
            scenario_index: int
            for scenario_index in range(scenario_count):
                target_s_pu: np.ndarray = (
                    scenario_array[scenario_index, :]
                    / self._numerical_circuit.Sbase
                )
                anchor_result: PowerFlowResults = multi_island_pf_nc(
                    nc=self._numerical_circuit,
                    options=power_flow_options,
                    logger=self._logger,
                    V_guess=voltage_guess,
                    Sbus_input=target_s_pu,
                )
                if bool(anchor_result.converged):
                    anchor_array[scenario_index] = anchor_result
                    voltage_guess = np.asarray(
                        anchor_result.voltage,
                        dtype=np.complex128,
                    )
                else:
                    all_converged = False
                    failed_scenario_index = scenario_index

            if all_converged:
                anchors: tuple[PowerFlowResults, ...] = tuple(anchor_array)
                result = self.build_from_power_flow_results(anchors)
            else:
                result = AtlasBuildResult(
                    status=AtlasBuildStatus.AnchorNotConverged,
                    atlas=None,
                    message=(
                        "Offline VeraGrid solve failed at scenario index "
                        + str(failed_scenario_index)
                    ),
                )
        else:
            if not bus_types_frozen:
                result = AtlasBuildResult(
                    status=AtlasBuildStatus.UnsupportedControlRegime,
                    atlas=None,
                    message=(
                        "Offline scenario generation requires control_Q=False "
                        "because VeraGrid PowerFlowResults does not expose the "
                        "solver-final PV/PQ active set"
                    ),
                )
            else:
                result = AtlasBuildResult(
                    status=AtlasBuildStatus.InvalidInput,
                    atlas=None,
                    message=(
                        "Scenario matrix must be finite and shaped "
                        "(scenario_count, numerical_circuit.nbus)"
                    ),
                )
        return result

    def build_from_power_flow_results(
        self,
        anchor_results: tuple[PowerFlowResults, ...],
        anchor_target_s_mva: tuple[np.ndarray, ...] | None = None,
    ) -> AtlasBuildResult:
        """Build an atlas from already-solved VeraGrid operating points.

        Each result becomes one local active-set chart. All results must refer
        to the same compiled topology and bus ordering.

        :param anchor_results: Solved VeraGrid power-flow results.
        :param anchor_target_s_mva: Optional specified nodal injections in MVA.
            When supplied, each vector is used as the patch target instead of
            ``PowerFlowResults.Sbus`` because VeraGrid stores calculated bus
            power there rather than the specified injection vector.
        :return: Explicit atlas-build result.
        """
        anchor_count: int = len(anchor_results)
        result: AtlasBuildResult
        admittances: AdmittanceMatrices = (
            self._numerical_circuit.get_admittance_matrices()
        )
        y_bus: csc_matrix = csc_matrix(admittances.Ybus, copy=False)
        current_injections: np.ndarray = self._numerical_circuit.get_current_injections_pu()
        admittance_injections: np.ndarray = self._numerical_circuit.get_admittance_injections_pu()
        constant_power_only: bool = bool(
            np.max(np.abs(current_injections), initial=0.0) <= 1.0e-14
            and np.max(np.abs(admittance_injections), initial=0.0) <= 1.0e-14
        )
        classical_network: bool = bool(
            self._numerical_circuit.nvsc == 0
            and self._numerical_circuit.nhvdc == 0
            and not self._numerical_circuit.active_branch_data.any_pf_control
        )
        csc_available: bool = bool(y_bus.format == "csc")
        explicit_targets_valid: bool
        if anchor_target_s_mva is None:
            explicit_targets_valid = True
        else:
            explicit_targets_valid = bool(len(anchor_target_s_mva) == anchor_count)

        if (
            anchor_count > 0
            and constant_power_only
            and classical_network
            and csc_available
            and explicit_targets_valid
        ):
            patch_array: np.ndarray = np.empty(anchor_count, dtype=object)
            build_successful: bool = True
            failure_status: AtlasBuildStatus = AtlasBuildStatus.Ready
            diagnostic: str = "All patches built"
            anchor_index: int
            for anchor_index in range(anchor_count):
                anchor_result: PowerFlowResults = anchor_results[anchor_index]
                if bool(anchor_result.converged):
                    circuit_for_regime: NumericalCircuit = self._numerical_circuit.copy()
                    circuit_for_regime.bus_data.bus_types[:] = anchor_result.bus_types
                    anchor_s_mva: np.ndarray
                    if anchor_target_s_mva is None:
                        anchor_s_mva = np.asarray(
                            anchor_result.Sbus,
                            dtype=np.complex128,
                        )
                    else:
                        anchor_s_mva = np.asarray(
                            anchor_target_s_mva[anchor_index],
                            dtype=np.complex128,
                        )
                    anchor_s: np.ndarray = anchor_s_mva / circuit_for_regime.Sbase
                    anchor_v: np.ndarray = np.asarray(
                        anchor_result.voltage,
                        dtype=np.complex128,
                    )
                    target_shape_valid: bool = bool(
                        anchor_s_mva.ndim == 1
                        and anchor_s_mva.size == circuit_for_regime.nbus
                        and np.all(np.isfinite(anchor_s_mva))
                    )
                    indices: SimulationIndices = (
                        circuit_for_regime.get_simulation_indices(Sbus=anchor_s)
                    )
                    unsupported_special_modes: bool = bool(
                        indices.p.size > 0 or indices.pqv.size > 0
                    )
                    all_buses_classified: bool = bool(
                        indices.vd.size + indices.pv.size + indices.pq.size
                        == circuit_for_regime.nbus
                    )

                    if (
                        target_shape_valid
                        and not unsupported_special_modes
                        and all_buses_classified
                    ):
                        q_max: np.ndarray
                        q_min: np.ndarray
                        q_max, q_min = circuit_for_regime.get_reactive_power_limits()
                        patch_result: AtlasPatchBuildResult = build_power_flow_atlas_patch(
                            patch_id=anchor_index,
                            y_bus=y_bus,
                            anchor_s=anchor_s,
                            anchor_v=anchor_v,
                            bus_types=np.asarray(anchor_result.bus_types, dtype=np.int64),
                            slack_indices=np.asarray(indices.vd, dtype=np.int64),
                            pv_indices=np.asarray(indices.pv, dtype=np.int64),
                            pq_indices=np.asarray(indices.pq, dtype=np.int64),
                            q_min=np.asarray(q_min, dtype=float),
                            q_max=np.asarray(q_max, dtype=float),
                            series_order=self._atlas_options.get_series_order(),
                            validity_radius=self._atlas_options.get_validity_radius(),
                            anchor_tolerance=self._atlas_options.get_series_tolerance(),
                        )
                        patch: PowerFlowAtlasPatch | None = patch_result.get_patch()
                        if (
                            patch_result.get_status() == AtlasBuildStatus.Ready
                            and patch is not None
                        ):
                            patch_array[anchor_index] = patch
                        else:
                            build_successful = False
                            failure_status = patch_result.get_status()
                            diagnostic = patch_result.get_message()
                    else:
                        if not target_shape_valid:
                            build_successful = False
                            failure_status = AtlasBuildStatus.InvalidInput
                            diagnostic = (
                                "Explicit anchor target injections must be finite "
                                "vectors of length numerical_circuit.nbus"
                            )
                        else:
                            build_successful = False
                            failure_status = AtlasBuildStatus.UnsupportedControlRegime
                            diagnostic = (
                                "Only classical slack/PV/PQ regimes are supported by "
                                "the analytic chart"
                            )
                else:
                    build_successful = False
                    failure_status = AtlasBuildStatus.AnchorNotConverged
                    diagnostic = "Every anchor result must be converged"

            if build_successful:
                patches: tuple[PowerFlowAtlasPatch, ...] = tuple(patch_array)
                result = finalize_power_flow_atlas(
                    system_base_power=self._numerical_circuit.Sbase,
                    y_bus=y_bus,
                    patches=patches,
                    y_from=csc_matrix(admittances.Yf, copy=False),
                    y_to=csc_matrix(admittances.Yt, copy=False),
                    branch_from_indices=np.asarray(
                        self._numerical_circuit.passive_branch_data.F,
                        dtype=np.int64,
                    ),
                    branch_to_indices=np.asarray(
                        self._numerical_circuit.passive_branch_data.T,
                        dtype=np.int64,
                    ),
                )
            else:
                result = AtlasBuildResult(
                    status=failure_status,
                    atlas=None,
                    message=diagnostic,
                )
        else:
            if not constant_power_only:
                status: AtlasBuildStatus = AtlasBuildStatus.UnsupportedInjectionModel
                message: str = "Nonzero ZIP current or admittance injections were detected"
            else:
                if not explicit_targets_valid:
                    status = AtlasBuildStatus.InvalidInput
                    message = (
                        "Explicit anchor target injections must match the number "
                        "of supplied power-flow results"
                    )
                else:
                    if not classical_network:
                        status = AtlasBuildStatus.UnsupportedControlRegime
                        message = (
                            "VSC, HVDC, or active branch-control equations require "
                            "the full VeraGrid solver"
                        )
                    else:
                        status = AtlasBuildStatus.InvalidInput
                        message = "No anchors were supplied or Ybus is not stored as CSC"
            result = AtlasBuildResult(
                status=status,
                atlas=None,
                message=message,
            )
        return result


class VeraGridPowerFlowAtlasEngine:
    """Evaluate a certified atlas and delegate corrections to VeraGrid."""

    __slots__ = (
        "_numerical_circuit",
        "_atlas",
        "_atlas_options",
        "_power_flow_options",
        "_logger",
    )

    def __init__(
        self,
        numerical_circuit: NumericalCircuit,
        atlas: PowerFlowAtlas,
        atlas_options: PowerFlowAtlasOptions,
        power_flow_options: PowerFlowOptions,
        logger: Logger,
    ) -> None:
        """Create an online atlas engine.

        :param numerical_circuit: Compiled VeraGrid numerical circuit.
        :param atlas: Finalized atlas for the same electrical topology.
        :param atlas_options: Atlas evaluation and fallback options.
        :param power_flow_options: VeraGrid correction and fallback options.
        :param logger: VeraGrid logger receiving runtime diagnostics.
        """
        self._numerical_circuit: NumericalCircuit = numerical_circuit
        self._atlas: PowerFlowAtlas = atlas
        self._atlas_options: PowerFlowAtlasOptions = atlas_options
        self._power_flow_options: PowerFlowOptions = power_flow_options
        self._logger: Logger = logger

    def query_mva(self, target_s_mva: np.ndarray) -> VeraGridAtlasQueryResult:
        """Evaluate bus injections expressed in MW and MVAr.

        :param target_s_mva: Complex nodal injections in VeraGrid bus order.
        :return: Certified atlas result or an explicit fallback result.
        """
        target_s_pu: np.ndarray = (
            np.asarray(target_s_mva, dtype=np.complex128)
            / self._numerical_circuit.Sbase
        )
        result: VeraGridAtlasQueryResult = self.query_pu(target_s_pu)
        return result

    def query_pu(self, target_s_pu: np.ndarray) -> VeraGridAtlasQueryResult:
        """Evaluate bus injections expressed in per unit.

        :param target_s_pu: Complex nodal injections in VeraGrid bus order.
        :return: Certified atlas result or an explicit fallback result.
        """
        query_target_s: np.ndarray = np.asarray(
            target_s_pu,
            dtype=np.complex128,
        ).reshape(-1)
        admittances: AdmittanceMatrices = (
            self._numerical_circuit.get_admittance_matrices()
        )
        y_bus: csc_matrix = csc_matrix(admittances.Ybus, copy=False)
        y_from: csc_matrix = csc_matrix(admittances.Yf, copy=False)
        y_to: csc_matrix = csc_matrix(admittances.Yt, copy=False)
        branch_from_indices: np.ndarray = np.asarray(
            self._numerical_circuit.passive_branch_data.F,
            dtype=np.int64,
        )
        branch_to_indices: np.ndarray = np.asarray(
            self._numerical_circuit.passive_branch_data.T,
            dtype=np.int64,
        )
        runtime_signature: str = build_topology_signature(
            system_base_power=self._numerical_circuit.Sbase,
            y_bus=y_bus,
            y_from=y_from,
            y_to=y_to,
            branch_from_indices=branch_from_indices,
            branch_to_indices=branch_to_indices,
        )
        topology_matches: bool = (
            runtime_signature == self._atlas.get_topology_signature()
        )
        size_matches: bool = query_target_s.size == self._atlas.get_bus_count()
        values_finite: bool = bool(np.all(np.isfinite(query_target_s)))
        current_injections: np.ndarray = (
            self._numerical_circuit.get_current_injections_pu()
        )
        admittance_injections: np.ndarray = (
            self._numerical_circuit.get_admittance_injections_pu()
        )
        constant_power_only: bool = bool(
            np.max(np.abs(current_injections), initial=0.0) <= 1.0e-14
            and np.max(np.abs(admittance_injections), initial=0.0) <= 1.0e-14
        )
        classical_network: bool = bool(
            self._numerical_circuit.nvsc == 0
            and self._numerical_circuit.nhvdc == 0
            and not self._numerical_circuit.active_branch_data.any_pf_control
        )
        runtime_model_supported: bool = constant_power_only and classical_network
        result: VeraGridAtlasQueryResult

        if (
            topology_matches
            and size_matches
            and values_finite
            and runtime_model_supported
        ):
            selection: PatchSelectionResult = select_nearest_atlas_patch(
                atlas=self._atlas,
                target_s=query_target_s,
            )
            if selection.is_found():
                patch: PowerFlowAtlasPatch | None = self._atlas.get_patch(
                    selection.get_patch_index()
                )
                if patch is not None:
                    limits_match: bool = self._patch_limits_match(patch)
                    if limits_match:
                        series_result: DirectionalSeriesResult = (
                            calculate_directional_voltage_series(
                                y_bus=y_bus,
                                target_s=query_target_s,
                                patch=patch,
                                evaluation_method=(
                                    self._atlas_options.get_series_method()
                                ),
                                minimum_pade_denominator=(
                                    self._atlas_options.get_minimum_pade_denominator()
                                ),
                            )
                        )
                        if series_result.is_successful():
                            residual: FixedRegimeResidual = (
                                calculate_fixed_regime_residual(
                                    y_bus=y_bus,
                                    voltage=series_result.get_voltage(),
                                    target_s=query_target_s,
                                    patch=patch,
                                    reactive_limit_tolerance=(
                                        self._atlas_options.get_reactive_limit_tolerance()
                                    ),
                                )
                            )
                            within_patch: bool = bool(
                                series_result.get_normalized_distance()
                                <= patch.get_validity_radius()
                            )
                            residual_certified: bool = bool(
                                residual.get_norm()
                                <= self._atlas_options.get_series_tolerance()
                            )
                            regime_valid: bool = (
                                residual.are_reactive_limits_valid()
                            )

                            if (
                                within_patch
                                and residual_certified
                                and regime_valid
                            ):
                                numeric_results: NumericPowerFlowResults = (
                                    self._build_native_results_without_solving(
                                        target_s_pu=query_target_s,
                                        voltage=series_result.get_voltage(),
                                        patch=patch,
                                    )
                                )
                                result = VeraGridAtlasQueryResult(
                                    status=AtlasQueryStatus.CertifiedSeries,
                                    message=(
                                        "Directional series certified without "
                                        "Newton iterations"
                                    ),
                                    patch_id=patch.get_patch_id(),
                                    normalized_distance=(
                                        series_result.get_normalized_distance()
                                    ),
                                    residual_norm=residual.get_norm(),
                                    voltage_coefficients=(
                                        series_result.get_voltage_coefficients()
                                    ),
                                    voltage=series_result.get_voltage(),
                                    numeric_results=numeric_results,
                                    power_flow_results=None,
                                )
                            else:
                                result = self._correct_or_fallback(
                                    target_s_pu=query_target_s,
                                    patch=patch,
                                    series_result=series_result,
                                    series_residual=residual,
                                    within_patch=within_patch,
                                    regime_valid=regime_valid,
                                )
                        else:
                            fallback_mode: AtlasFallbackMode = (
                                self._atlas_options.get_fallback_mode()
                            )
                            if fallback_mode == AtlasFallbackMode.FullPowerFlow:
                                result = self._run_full_fallback(
                                    target_s_pu=query_target_s,
                                    voltage_guess=patch.get_anchor_v(),
                                    patch=patch,
                                    voltage_coefficients=(
                                        series_result.get_voltage_coefficients()
                                    ),
                                    normalized_distance=(
                                        series_result.get_normalized_distance()
                                    ),
                                    residual_norm=float("inf"),
                                    message=series_result.get_message(),
                                )
                            else:
                                result = self._failed_result(
                                    series_result.get_message()
                                )
                    else:
                        result = self._failed_result(
                            "Compiled VeraGrid reactive limits do not match the atlas"
                        )
                else:
                    result = self._failed_result("Selected patch is unavailable")
            else:
                result = self._failed_result(selection.get_message())
        else:
            if not topology_matches:
                message: str = "Compiled VeraGrid topology does not match the atlas"
            else:
                if not size_matches:
                    message = "Target injection vector has the wrong bus count"
                else:
                    if not values_finite:
                        message = (
                            "Target injection vector contains non-finite values"
                        )
                    else:
                        if not constant_power_only:
                            message = (
                                "Runtime VeraGrid model contains ZIP current or "
                                "admittance injections"
                            )
                        else:
                            message = (
                                "Runtime VeraGrid model contains VSC, HVDC, or "
                                "active branch controls"
                            )
            result = self._failed_result(message)
        return result

    def _patch_limits_match(self, patch: PowerFlowAtlasPatch) -> bool:
        """Check that runtime nodal reactive limits match one stored patch.

        :param patch: Selected local chart.
        :return: Whether both limit arrays are dimensionally and numerically equal.
        """
        runtime_q_max: np.ndarray
        runtime_q_min: np.ndarray
        runtime_q_max, runtime_q_min = (
            self._numerical_circuit.get_reactive_power_limits()
        )
        stored_q_min: np.ndarray = patch.get_q_min()
        stored_q_max: np.ndarray = patch.get_q_max()
        sizes_match: bool = bool(
            runtime_q_min.shape == stored_q_min.shape
            and runtime_q_max.shape == stored_q_max.shape
        )
        limits_match: bool
        if sizes_match:
            limits_match = bool(
                np.allclose(
                    runtime_q_min,
                    stored_q_min,
                    rtol=0.0,
                    atol=1.0e-12,
                )
                and np.allclose(
                    runtime_q_max,
                    stored_q_max,
                    rtol=0.0,
                    atol=1.0e-12,
                )
            )
        else:
            limits_match = False
        return limits_match

    def _build_problem(
        self,
        target_s_pu: np.ndarray,
        voltage: np.ndarray,
        patch: PowerFlowAtlasPatch,
    ) -> PfBasicFormulation:
        """Build VeraGrid's native fixed-regime formulation at a candidate state.

        :param target_s_pu: Target nodal injections in p.u.
        :param voltage: Candidate complex bus voltage in p.u.
        :param patch: Selected fixed-regime local chart.
        :return: VeraGrid basic power-flow formulation.
        """
        circuit_for_regime: NumericalCircuit = self._numerical_circuit.copy()
        circuit_for_regime.bus_data.bus_types[:] = patch.get_bus_types()
        zero_injections: np.ndarray = np.zeros(
            circuit_for_regime.nbus,
            dtype=np.complex128,
        )
        problem: PfBasicFormulation = PfBasicFormulation(
            V0=voltage,
            S0=target_s_pu,
            I0=zero_injections,
            Y0=zero_injections,
            Qmin=patch.get_q_min(),
            Qmax=patch.get_q_max(),
            nc=circuit_for_regime,
            options=self._power_flow_options,
        )
        return problem

    def _build_native_results_without_solving(
        self,
        target_s_pu: np.ndarray,
        voltage: np.ndarray,
        patch: PowerFlowAtlasPatch,
    ) -> NumericPowerFlowResults:
        """Use VeraGrid only for exact result post-processing.

        :param target_s_pu: Target nodal injections in p.u.
        :param voltage: Certified complex bus voltage in p.u.
        :param patch: Selected fixed-regime local chart.
        :return: Native VeraGrid numeric power-flow results.
        """
        problem: PfBasicFormulation = self._build_problem(
            target_s_pu=target_s_pu,
            voltage=voltage,
            patch=patch,
        )
        state: np.ndarray = problem.var2x()
        problem.update(x=state, update_controls=False)
        results: NumericPowerFlowResults = problem.get_solution(
            elapsed=0.0,
            iterations=0,
        )
        return results

    def _correct_or_fallback(
        self,
        target_s_pu: np.ndarray,
        patch: PowerFlowAtlasPatch,
        series_result: DirectionalSeriesResult,
        series_residual: FixedRegimeResidual,
        within_patch: bool,
        regime_valid: bool,
    ) -> VeraGridAtlasQueryResult:
        """Apply bounded VeraGrid correction and the configured fallback policy.

        :param target_s_pu: Target nodal injections in p.u.
        :param patch: Selected fixed-regime local chart.
        :param series_result: Completed directional-series result.
        :param series_residual: Exact residual at the series estimate.
        :param within_patch: Whether the query lies inside the patch radius.
        :param regime_valid: Whether the selected PV active set remains valid.
        :return: Corrected, fallback, or explicit failed result.
        """
        fallback_mode: AtlasFallbackMode = self._atlas_options.get_fallback_mode()
        can_try_newton: bool = bool(
            within_patch
            and regime_valid
            and fallback_mode != AtlasFallbackMode.NoneMode
            and self._atlas_options.get_maximum_newton_iterations() > 0
        )
        result: VeraGridAtlasQueryResult

        if can_try_newton:
            problem: PfBasicFormulation = self._build_problem(
                target_s_pu=target_s_pu,
                voltage=series_result.get_voltage(),
                patch=patch,
            )
            corrected_results: NumericPowerFlowResults = newton_raphson_fx(
                problem=problem,
                tol=self._atlas_options.get_newton_tolerance(),
                max_iter=self._atlas_options.get_maximum_newton_iterations(),
                trust=self._power_flow_options.trust_radius,
                verbose=self._power_flow_options.verbose,
                logger=self._logger,
            )
            corrected_voltage: np.ndarray = np.asarray(
                corrected_results.V,
                dtype=np.complex128,
            )
            corrected_residual: FixedRegimeResidual = (
                calculate_fixed_regime_residual(
                    y_bus=self._atlas.get_y_bus(),
                    voltage=corrected_voltage,
                    target_s=target_s_pu,
                    patch=patch,
                    reactive_limit_tolerance=(
                        self._atlas_options.get_reactive_limit_tolerance()
                    ),
                )
            )
            correction_converged: bool = bool(
                corrected_results.converged
                and corrected_residual.get_norm()
                <= self._atlas_options.get_newton_tolerance()
                and corrected_residual.are_reactive_limits_valid()
            )
            if correction_converged:
                result = VeraGridAtlasQueryResult(
                    status=AtlasQueryStatus.CertifiedNewton,
                    message=(
                        "Series estimate certified after bounded VeraGrid "
                        "Newton correction"
                    ),
                    patch_id=patch.get_patch_id(),
                    normalized_distance=series_result.get_normalized_distance(),
                    residual_norm=corrected_residual.get_norm(),
                    voltage_coefficients=series_result.get_voltage_coefficients(),
                    voltage=corrected_voltage,
                    numeric_results=corrected_results,
                    power_flow_results=None,
                )
            else:
                if fallback_mode == AtlasFallbackMode.FullPowerFlow:
                    result = self._run_full_fallback(
                        target_s_pu=target_s_pu,
                        voltage_guess=series_result.get_voltage(),
                        patch=patch,
                        voltage_coefficients=series_result.get_voltage_coefficients(),
                        normalized_distance=series_result.get_normalized_distance(),
                        residual_norm=series_residual.get_norm(),
                        message="Bounded Newton correction did not certify the query",
                    )
                else:
                    result = VeraGridAtlasQueryResult(
                        status=AtlasQueryStatus.Failed,
                        message="Bounded Newton correction did not certify the query",
                        patch_id=patch.get_patch_id(),
                        normalized_distance=series_result.get_normalized_distance(),
                        residual_norm=series_residual.get_norm(),
                        voltage_coefficients=series_result.get_voltage_coefficients(),
                        voltage=series_result.get_voltage(),
                        numeric_results=corrected_results,
                        power_flow_results=None,
                    )
        else:
            if fallback_mode == AtlasFallbackMode.FullPowerFlow:
                if regime_valid:
                    message: str = "Query lies outside the certified patch radius"
                else:
                    message = "Selected PV/PQ active set violates reactive limits"
                result = self._run_full_fallback(
                    target_s_pu=target_s_pu,
                    voltage_guess=series_result.get_voltage(),
                    patch=patch,
                    voltage_coefficients=series_result.get_voltage_coefficients(),
                    normalized_distance=series_result.get_normalized_distance(),
                    residual_norm=series_residual.get_norm(),
                    message=message,
                )
            else:
                if regime_valid:
                    status: AtlasQueryStatus = AtlasQueryStatus.OutsideAtlas
                    message = "Query lies outside the certified patch radius"
                else:
                    status = AtlasQueryStatus.RegimeMismatch
                    message = "Selected PV/PQ active set violates reactive limits"
                result = VeraGridAtlasQueryResult(
                    status=status,
                    message=message,
                    patch_id=patch.get_patch_id(),
                    normalized_distance=series_result.get_normalized_distance(),
                    residual_norm=series_residual.get_norm(),
                    voltage_coefficients=series_result.get_voltage_coefficients(),
                    voltage=series_result.get_voltage(),
                    numeric_results=None,
                    power_flow_results=None,
                )
        return result

    def _run_full_fallback(
        self,
        target_s_pu: np.ndarray,
        voltage_guess: np.ndarray,
        patch: PowerFlowAtlasPatch,
        voltage_coefficients: np.ndarray,
        normalized_distance: float,
        residual_norm: float,
        message: str,
    ) -> VeraGridAtlasQueryResult:
        """Run VeraGrid's full multi-island power-flow fallback.

        :param target_s_pu: Target nodal injections in p.u.
        :param voltage_guess: Atlas-generated initial voltage.
        :param patch: Selected local chart.
        :param voltage_coefficients: Per-order, per-bus series coefficients.
        :param normalized_distance: First-order patch distance.
        :param residual_norm: Residual before fallback.
        :param message: Reason for invoking the fallback.
        :return: Full VeraGrid fallback result.
        """
        fallback_results: PowerFlowResults = multi_island_pf_nc(
            nc=self._numerical_circuit,
            options=self._power_flow_options,
            logger=self._logger,
            V_guess=voltage_guess,
            Sbus_input=target_s_pu,
        )
        if bool(fallback_results.converged):
            status: AtlasQueryStatus = AtlasQueryStatus.FullPowerFlowFallback
            final_message: str = message + "; VeraGrid fallback converged"
        else:
            status = AtlasQueryStatus.Failed
            final_message = message + "; VeraGrid fallback did not converge"
        result: VeraGridAtlasQueryResult = VeraGridAtlasQueryResult(
            status=status,
            message=final_message,
            patch_id=patch.get_patch_id(),
            normalized_distance=normalized_distance,
            residual_norm=residual_norm,
            voltage_coefficients=voltage_coefficients,
            voltage=np.asarray(fallback_results.voltage, dtype=np.complex128),
            numeric_results=None,
            power_flow_results=fallback_results,
        )
        return result

    def _failed_result(self, message: str) -> VeraGridAtlasQueryResult:
        """Create an explicit failed result without inventing electrical data.

        :param message: Failure diagnostic.
        :return: Failed query result containing correctly sized empty arrays.
        """
        bus_count: int = self._atlas.get_bus_count()
        voltage_coefficients: np.ndarray = np.zeros(
            (self._atlas_options.get_series_order() + 1, bus_count),
            dtype=np.complex128,
        )
        voltage: np.ndarray = np.zeros(bus_count, dtype=np.complex128)
        result: VeraGridAtlasQueryResult = VeraGridAtlasQueryResult(
            status=AtlasQueryStatus.Failed,
            message=message,
            patch_id=-1,
            normalized_distance=float("inf"),
            residual_norm=float("inf"),
            voltage_coefficients=voltage_coefficients,
            voltage=voltage,
            numeric_results=None,
            power_flow_results=None,
        )
        return result
