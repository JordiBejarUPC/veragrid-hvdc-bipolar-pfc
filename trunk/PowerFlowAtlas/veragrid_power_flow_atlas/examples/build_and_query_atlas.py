from __future__ import annotations

from pathlib import Path

import numpy as np
import VeraGridEngine as vg
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation import (
    PfBasicFormulation,
)
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import (
    newton_raphson_fx,
)
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import (
    NumericPowerFlowResults,
    PowerFlowResults,
)
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from VeraGridEngine.Topology.simulation_indices import SimulationIndices

from power_flow_atlas.branch_flows import (
    AtlasBranchFlowResult,
    calculate_branch_flows,
)
from power_flow_atlas.enumerations import (
    AtlasBuildStatus,
    AtlasQueryStatus,
    AtlasStorageStatus,
)
from power_flow_atlas.model import AtlasBuildResult, AtlasStorageResult, PowerFlowAtlas
from power_flow_atlas.options import PowerFlowAtlasOptions
from power_flow_atlas.storage import save_power_flow_atlas
from power_flow_atlas.veragrid_integration import (
    VeraGridAtlasQueryResult,
    VeraGridPowerFlowAtlasBuilder,
    VeraGridPowerFlowAtlasEngine,
)


def build_example_candidate_s_mva(
    base_s_mva: np.ndarray,
    pv_indices: np.ndarray,
    pq_indices: np.ndarray,
    active_scale: float,
    reactive_scale: float,
    pv_redispatch_scale: float,
) -> np.ndarray:
    """Build one small continuation-style dispatch near the solved operating point.

    The example perturbs only the classical controlled quantities: active and
    reactive power at PQ buses, and active power at PV buses. The perturbation
    is deterministic and system-wide so the large ACTIVSg2000 case follows a
    mild continuation path instead of a collection of hard random jumps.

    :param base_s_mva: Solved VeraGrid nodal injections in MVA.
    :param pv_indices: PV-bus indices in VeraGrid bus order.
    :param pq_indices: PQ-bus indices in VeraGrid bus order.
    :param active_scale: Relative active-power perturbation applied at PQ buses.
    :param reactive_scale: Relative reactive-power perturbation applied at PQ buses.
    :param pv_redispatch_scale: Small PV redispatch bias used to diversify anchors.
    :return: One candidate nodal injection vector in MVA.
    """
    candidate_s_mva: np.ndarray = np.array(
        base_s_mva,
        dtype=np.complex128,
        copy=True,
    )
    pq_active_scale_mw: np.ndarray = np.maximum(
        np.abs(base_s_mva.real[pq_indices]),
        20.0,
    )
    pq_reactive_scale_mvar: np.ndarray = np.maximum(
        np.abs(base_s_mva.imag[pq_indices]),
        10.0,
    )
    pv_active_scale_mw: np.ndarray = np.maximum(
        np.abs(base_s_mva.real[pv_indices]),
        20.0,
    )

    # PQ buses are scaled coherently so each candidate remains a nearby global
    # dispatch variation of the solved operating point instead of a sparse local
    # disturbance that often drives this large case out of convergence.
    pq_active_delta_mw: np.ndarray = active_scale * pq_active_scale_mw
    pq_reactive_delta_mvar: np.ndarray = reactive_scale * pq_reactive_scale_mvar

    # PV buses absorb the net active change from the PQ perturbation. A small
    # deterministic bias across the PV fleet produces distinct anchors while
    # keeping the total redispatch balanced.
    pv_active_delta_mw: np.ndarray = np.zeros(pv_indices.size, dtype=float)
    net_pq_active_delta_mw: float = float(np.sum(pq_active_delta_mw))
    pv_weight_sum_mw: float = float(np.sum(pv_active_scale_mw))
    if pv_indices.size > 0 and pv_weight_sum_mw > 0.0:
        pv_balance_weights: np.ndarray = pv_active_scale_mw / pv_weight_sum_mw
        pv_active_delta_mw = -net_pq_active_delta_mw * pv_balance_weights
        pv_shape: np.ndarray = np.linspace(
            -1.0,
            1.0,
            pv_indices.size,
            dtype=float,
        )
        pv_shape = pv_shape - float(np.mean(pv_shape))
        pv_shape_norm: float = float(np.max(np.abs(pv_shape), initial=0.0))
        if pv_shape_norm > 0.0:
            pv_active_delta_mw = pv_active_delta_mw + (
                pv_redispatch_scale * pv_active_scale_mw * (pv_shape / pv_shape_norm)
            )
        else:
            pass
        pv_bias_sum_mw: float = float(np.sum(pv_active_delta_mw))
        pv_active_delta_mw = pv_active_delta_mw - pv_bias_sum_mw * pv_balance_weights
    else:
        pass

    candidate_s_mva[pq_indices] = (
        base_s_mva[pq_indices]
        + pq_active_delta_mw
        + 1.0j * pq_reactive_delta_mvar
    )
    candidate_s_mva[pv_indices] = (
        base_s_mva[pv_indices]
        + pv_active_delta_mw
        + 1.0j * 0.0
    )
    return candidate_s_mva


def build_example_anchor_set(
    numerical_circuit: NumericalCircuit,
    base_results: PowerFlowResults,
    power_flow_options: PowerFlowOptions,
    logger: vg.Logger,
    target_anchor_count: int,
) -> tuple[np.ndarray, tuple[PowerFlowResults, ...]]:
    """Build a small set of converged offline anchors around the base point.

    The atlas builder is strict: every supplied anchor must already converge.
    This helper therefore walks a mild deterministic continuation path, solves
    each candidate first with VeraGrid, and keeps only the converged ones.

    :param numerical_circuit: Compiled VeraGrid numerical circuit.
    :param base_results: Solved base power-flow results.
    :param power_flow_options: VeraGrid options used for the offline solves.
    :param logger: VeraGrid logger receiving solver diagnostics.
    :param target_anchor_count: Preferred number of converged anchors.
    :return: Converged scenario matrix in MVA and matching power-flow results.
    """
    base_s_mva: np.ndarray = (
        np.asarray(
            numerical_circuit.get_power_injections_pu(),
            dtype=np.complex128,
        )
        * numerical_circuit.Sbase
    )
    base_s_pu: np.ndarray = base_s_mva / numerical_circuit.Sbase
    indices: SimulationIndices = numerical_circuit.get_simulation_indices(
        Sbus=base_s_pu,
    )
    bus_count: int = numerical_circuit.nbus
    scenario_matrix: np.ndarray = np.empty(
        (target_anchor_count, bus_count),
        dtype=np.complex128,
    )
    anchor_array: np.ndarray = np.empty(target_anchor_count, dtype=object)
    accepted_count: int = 0
    voltage_guess: np.ndarray = np.asarray(
        base_results.voltage,
        dtype=np.complex128,
    )
    continuation_steps: tuple[tuple[float, float, float], ...] = (
        (-0.003, -0.003, -0.001),
        (0.003, 0.003, 0.001),
        (-0.006, -0.006, -0.002),
        (0.006, 0.006, 0.002),
        (-0.010, -0.010, -0.003),
        (0.010, 0.010, 0.003),
        (-0.014, -0.014, -0.004),
        (0.014, 0.014, 0.004),
        (-0.018, -0.018, -0.005),
        (0.018, 0.018, 0.005),
        (-0.022, -0.022, -0.006),
        (0.022, 0.022, 0.006),
    )
    step_index: int

    # The solved base operating point is always the first anchor because it is
    # known to converge and gives the subsequent continuation solves a safe seed.
    scenario_matrix[0, :] = base_s_mva
    anchor_array[0] = base_results
    accepted_count = 1

    for step_index in range(len(continuation_steps)):
        if accepted_count >= target_anchor_count:
            break
        else:
            pass
        active_scale: float
        reactive_scale: float
        pv_redispatch_scale: float
        active_scale, reactive_scale, pv_redispatch_scale = continuation_steps[step_index]
        candidate_s_mva: np.ndarray = build_example_candidate_s_mva(
            base_s_mva=base_s_mva,
            pv_indices=np.asarray(indices.pv, dtype=np.int64),
            pq_indices=np.asarray(indices.pq, dtype=np.int64),
            active_scale=active_scale,
            reactive_scale=reactive_scale,
            pv_redispatch_scale=pv_redispatch_scale,
        )
        candidate_result: PowerFlowResults = multi_island_pf_nc(
            nc=numerical_circuit,
            options=power_flow_options,
            logger=logger,
            V_guess=voltage_guess,
            Sbus_input=candidate_s_mva / numerical_circuit.Sbase,
        )
        if bool(candidate_result.converged):
            scenario_matrix[accepted_count, :] = candidate_s_mva
            anchor_array[accepted_count] = candidate_result
            voltage_guess = np.asarray(
                candidate_result.voltage,
                dtype=np.complex128,
            )
            accepted_count = accepted_count + 1
        else:
            pass

    if accepted_count >= 1:
        return (
            scenario_matrix[:accepted_count, :],
            tuple(anchor_array[:accepted_count]),
        )
    else:
        raise RuntimeError(
            "The example could not generate enough converged ACTIVSg2000 anchors"
        )


def build_example_query_s_mva(scenario_matrix: np.ndarray) -> np.ndarray:
    """Build one interior query target from the converged example anchors.

    The query point is chosen between already-converged anchors so the example
    exercises the online atlas path without extrapolating far outside the
    sampled offline region.

    :param scenario_matrix: Converged offline anchor matrix in MVA.
    :return: One query injection vector in MVA.
    """
    scenario_count: int = scenario_matrix.shape[0]
    if scenario_count >= 3:
        return (
            0.50 * scenario_matrix[0, :]
            + 0.30 * scenario_matrix[1, :]
            + 0.20 * scenario_matrix[2, :]
        )
    else:
        if scenario_count == 2:
            return 0.60 * scenario_matrix[0, :] + 0.40 * scenario_matrix[1, :]
        else:
            return np.array(scenario_matrix[0, :], dtype=np.complex128, copy=True)


def build_random_query_candidate_s_mva(
    base_s_mva: np.ndarray,
    pv_indices: np.ndarray,
    pq_indices: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Build one random combination of nodal injections near the anchor cloud.

    The query changes many PQ and PV buses independently. The perturbation band
    is intentionally wide so the example exercises materially different nodal
    injections while rebalancing total active and reactive power close to zero.

    :param base_s_mva: Base nodal injections in MVA.
    :param pv_indices: PV-bus indices in VeraGrid bus order.
    :param pq_indices: PQ-bus indices in VeraGrid bus order.
    :param rng: Random-number generator used for repeatable queries.
    :return: One random candidate injection vector in MVA.
    """
    candidate_s_mva: np.ndarray = np.array(
        base_s_mva,
        dtype=np.complex128,
        copy=True,
    )
    pq_active_scale_mw: np.ndarray = np.maximum(
        np.abs(base_s_mva.real[pq_indices]),
        20.0,
    )
    pq_reactive_scale_mvar: np.ndarray = np.maximum(
        np.abs(base_s_mva.imag[pq_indices]),
        10.0,
    )
    pv_active_scale_mw: np.ndarray = np.maximum(
        np.abs(base_s_mva.real[pv_indices]),
        20.0,
    )
    pq_active_delta_mw: np.ndarray = (
        0.080
        * pq_active_scale_mw
        * rng.normal(loc=0.0, scale=1.0, size=pq_indices.size)
    )
    pq_reactive_delta_mvar: np.ndarray = (
        0.080
        * pq_reactive_scale_mvar
        * rng.normal(loc=0.0, scale=1.0, size=pq_indices.size)
    )
    pv_active_delta_mw: np.ndarray = (
        0.060
        * pv_active_scale_mw
        * rng.normal(loc=0.0, scale=1.0, size=pv_indices.size)
    )

    # Independent PQ and PV perturbations change many buses at once. The net
    # active and reactive changes are rebalanced so the random combination stays
    # close to the base dispatch manifold instead of drifting the whole system.
    net_active_delta_mw: float = float(
        np.sum(pq_active_delta_mw) + np.sum(pv_active_delta_mw)
    )
    net_reactive_delta_mvar: float = float(np.sum(pq_reactive_delta_mvar))
    pv_weight_sum_mw: float = float(np.sum(pv_active_scale_mw))
    pq_reactive_weight_sum: float = float(np.sum(pq_reactive_scale_mvar))
    if pv_indices.size > 0 and pv_weight_sum_mw > 0.0:
        pv_balance_weights: np.ndarray = pv_active_scale_mw / pv_weight_sum_mw
        pv_active_delta_mw = pv_active_delta_mw - net_active_delta_mw * pv_balance_weights
    else:
        pass
    if pq_indices.size > 0 and pq_reactive_weight_sum > 0.0:
        pq_reactive_weights: np.ndarray = (
            pq_reactive_scale_mvar / pq_reactive_weight_sum
        )
        pq_reactive_delta_mvar = (
            pq_reactive_delta_mvar - net_reactive_delta_mvar * pq_reactive_weights
        )
    else:
        pass

    candidate_s_mva[pq_indices] = (
        base_s_mva[pq_indices]
        + pq_active_delta_mw
        + 1.0j * pq_reactive_delta_mvar
    )
    candidate_s_mva[pv_indices] = (
        base_s_mva[pv_indices]
        + pv_active_delta_mw
        + 1.0j * 0.0
    )
    return candidate_s_mva


def build_valid_query_set(
    numerical_circuit: NumericalCircuit,
    power_flow_options: PowerFlowOptions,
    logger: vg.Logger,
    base_s_mva: np.ndarray,
    query_count: int,
    random_seed: int,
    initial_voltage_guess: np.ndarray,
) -> tuple[np.ndarray, tuple[PowerFlowResults, ...]]:
    """Generate random valid query injections and their NR references.

    Valid means that the random candidate converges under VeraGrid's Newton-
    Raphson solver for the same compiled numerical circuit used by the atlas.
    The validation seed is held fixed across queries so VeraGrid's basic PV
    formulation does not inherit drifting PV magnitudes from a previous solve.

    :param numerical_circuit: Compiled VeraGrid numerical circuit.
    :param power_flow_options: VeraGrid options used for Newton-Raphson solves.
    :param logger: VeraGrid logger receiving solver diagnostics.
    :param base_s_mva: Base nodal injections in MVA.
    :param query_count: Number of accepted random queries required.
    :param random_seed: Seed used for repeatable random queries.
    :param initial_voltage_guess: Initial voltage seed for the first query.
    :return: Accepted query injection matrix and matching Newton results.
    """
    base_s_pu: np.ndarray = base_s_mva / numerical_circuit.Sbase
    indices: SimulationIndices = numerical_circuit.get_simulation_indices(
        Sbus=base_s_pu,
    )
    rng: np.random.Generator = np.random.default_rng(random_seed)
    query_matrix: np.ndarray = np.empty(
        (query_count, numerical_circuit.nbus),
        dtype=np.complex128,
    )
    nr_results_array: np.ndarray = np.empty(query_count, dtype=object)
    accepted_count: int = 0
    attempt_count: int = 0
    maximum_attempt_count: int = 12 * query_count
    while accepted_count < query_count and attempt_count < maximum_attempt_count:
        candidate_s_mva: np.ndarray = build_random_query_candidate_s_mva(
            base_s_mva=base_s_mva,
            pv_indices=np.asarray(indices.pv, dtype=np.int64),
            pq_indices=np.asarray(indices.pq, dtype=np.int64),
            rng=rng,
        )
        candidate_result: PowerFlowResults = multi_island_pf_nc(
            nc=numerical_circuit,
            options=power_flow_options,
            logger=logger,
            V_guess=np.asarray(
                initial_voltage_guess,
                dtype=np.complex128,
            ),
            Sbus_input=candidate_s_mva / numerical_circuit.Sbase,
        )
        if bool(candidate_result.converged):
            query_matrix[accepted_count, :] = candidate_s_mva
            nr_results_array[accepted_count] = candidate_result
            accepted_count = accepted_count + 1
        else:
            pass
        attempt_count = attempt_count + 1

    if accepted_count == query_count:
        return query_matrix, tuple(nr_results_array)
    else:
        raise RuntimeError(
            "The example could not generate enough random valid atlas queries"
        )

def calculate_voltage_error(
    atlas_voltage: np.ndarray,
    nr_voltage: np.ndarray,
) -> float:
    """Calculate the maximum complex-voltage difference in p.u.

    :param atlas_voltage: Atlas-returned complex voltage vector in p.u.
    :param nr_voltage: Newton-Raphson reference complex voltage vector in p.u.
    :return: Maximum absolute bus-voltage difference in p.u.
    """
    return float(
        np.max(
            np.abs(
                np.asarray(atlas_voltage, dtype=np.complex128)
                - np.asarray(nr_voltage, dtype=np.complex128)
            ),
            initial=0.0,
        )
    )


def calculate_branch_power_error(
    atlas_power_mva: np.ndarray,
    nr_power_mva: np.ndarray,
) -> float:
    """Calculate the maximum complex branch-power difference in MVA.

    :param atlas_power_mva: Atlas branch terminal powers in MVA.
    :param nr_power_mva: Newton-Raphson reference branch terminal powers in MVA.
    :return: Maximum absolute terminal-power difference in MVA.
    """
    return float(
        np.max(
            np.abs(
                np.asarray(atlas_power_mva, dtype=np.complex128)
                - np.asarray(nr_power_mva, dtype=np.complex128)
            ),
            initial=0.0,
        )
    )


def calculate_loading_error(
    atlas_power_mva: np.ndarray,
    nr_loading: np.ndarray,
    branch_rates_mva: np.ndarray,
) -> float:
    """Calculate the maximum branch-loading difference.

    :param atlas_power_mva: Atlas from-terminal branch powers in MVA.
    :param nr_loading: Newton-Raphson branch loading vector in p.u.
    :param branch_rates_mva: Branch thermal rates in MVA.
    :return: Maximum absolute branch-loading difference in p.u.
    """
    safe_rates_mva: np.ndarray = np.maximum(
        np.asarray(branch_rates_mva, dtype=float),
        1.0e-9,
    )
    atlas_loading: np.ndarray = (
        np.asarray(atlas_power_mva, dtype=np.complex128) / safe_rates_mva
    )
    return float(
        np.max(
            np.abs(
                atlas_loading
                - np.asarray(nr_loading, dtype=np.complex128)
            ),
            initial=0.0,
        )
    )


def run_fixed_regime_nr_reference(
    numerical_circuit: NumericalCircuit,
    power_flow_options: PowerFlowOptions,
    logger: vg.Logger,
    atlas: PowerFlowAtlas,
    patch_id: int,
    target_s_mva: np.ndarray,
    initial_voltage: np.ndarray,
) -> NumericPowerFlowResults:
    """Solve one atlas query with VeraGrid Newton-Raphson on the same regime.

    The atlas and the Newton reference must solve the same fixed slack/PV/PQ
    regime. Otherwise a parity check mixes two different mathematical problems
    and the comparison is meaningless.

    :param numerical_circuit: Compiled VeraGrid numerical circuit.
    :param power_flow_options: VeraGrid Newton-Raphson options.
    :param logger: VeraGrid logger receiving solver diagnostics.
    :param atlas: Built atlas containing the selected patch.
    :param patch_id: Stable patch identifier returned by the atlas query.
    :param target_s_mva: Target nodal injections in MVA.
    :param initial_voltage: Initial complex voltage in p.u.
    :return: Fixed-regime Newton-Raphson solution.
    """
    patch = atlas.get_patch(patch_id)
    if patch is None:
        raise RuntimeError("The atlas query returned an unavailable patch")
    else:
        pass

    circuit_for_regime: NumericalCircuit = numerical_circuit.copy()
    circuit_for_regime.bus_data.bus_types[:] = patch.get_bus_types()
    zero_injections: np.ndarray = np.zeros(
        circuit_for_regime.nbus,
        dtype=np.complex128,
    )
    problem: PfBasicFormulation = PfBasicFormulation(
        V0=np.asarray(initial_voltage, dtype=np.complex128),
        S0=np.asarray(target_s_mva, dtype=np.complex128) / circuit_for_regime.Sbase,
        I0=zero_injections,
        Y0=zero_injections,
        Qmin=patch.get_q_min(),
        Qmax=patch.get_q_max(),
        nc=circuit_for_regime,
        options=power_flow_options,
    )
    nr_result: NumericPowerFlowResults = newton_raphson_fx(
        problem=problem,
        tol=power_flow_options.tolerance,
        max_iter=power_flow_options.max_iter,
        verbose=0,
        logger=logger,
    )
    if bool(nr_result.converged):
        return nr_result
    else:
        raise RuntimeError(
            "Fixed-regime Newton-Raphson did not converge for an accepted query"
        )


def relax_example_reactive_limits(numerical_circuit: NumericalCircuit) -> None:
    """Disable reactive-limit binding for the standalone atlas example.

    The atlas core currently requires the stored PV/PQ regime and the compiled
    reactive limits to be perfectly consistent. The large ACTIVSg2000 example
    does not satisfy that requirement through ``PowerFlowResults`` alone, so
    the example uses non-binding limits to demonstrate the atlas flow on one
    fixed classical regime.

    :param numerical_circuit: Compiled numerical circuit modified in place.
    """
    large_limit_mvar: float = 1.0e9

    # Generators are the dominant reactive controllers in this case. Their
    # limits are widened so the fixed-regime residual check validates the same
    # regime that the example solves and stores.
    numerical_circuit.generator_data.qmin[:] = -large_limit_mvar
    numerical_circuit.generator_data.qmax[:] = large_limit_mvar

    # The remaining device classes are widened as well to keep the compiled
    # nodal limit arrays internally consistent for builder and runtime checks.
    numerical_circuit.battery_data.qmin[:] = -large_limit_mvar
    numerical_circuit.battery_data.qmax[:] = large_limit_mvar
    numerical_circuit.shunt_data.qmin[:] = -large_limit_mvar
    numerical_circuit.shunt_data.qmax[:] = large_limit_mvar
    numerical_circuit.hvdc_data.Qmin_f[:] = -large_limit_mvar
    numerical_circuit.hvdc_data.Qmax_f[:] = large_limit_mvar
    numerical_circuit.hvdc_data.Qmin_t[:] = -large_limit_mvar
    numerical_circuit.hvdc_data.Qmax_t[:] = large_limit_mvar


def run_example(
    grid_file_path: Path,
    artifact_directory_path: Path,
) -> None:
    """Build an atlas and compare random atlas queries against Newton-Raphson.

    :param grid_file_path: VeraGrid-supported input grid file.
    :param artifact_directory_path: Directory receiving the persisted atlas.
    """
    logger: vg.Logger = vg.Logger()
    grid: MultiCircuit = vg.open_file(filename=str(grid_file_path))
    power_flow_options: PowerFlowOptions = vg.PowerFlowOptions(
        solver_type=vg.SolverType.NR,
        retry_with_other_methods=True,
        tolerance=1.0e-10,
        control_q=True,
        control_taps_phase=False,
        control_taps_modules=False,
        verbose=False,
    )
    numerical_circuit: NumericalCircuit = compile_numerical_circuit_at(
        circuit=grid,
        t_idx=None,
        logger=logger,
    )
    relax_example_reactive_limits(numerical_circuit=numerical_circuit)
    base_results: PowerFlowResults = multi_island_pf_nc(
        nc=numerical_circuit,
        options=power_flow_options,
        logger=logger,
        V_guess=None,
        Sbus_input=numerical_circuit.get_power_injections_pu(),
    )

    if bool(base_results.converged):
        scenario_matrix: np.ndarray
        anchor_results: tuple[PowerFlowResults, ...]
        scenario_matrix, anchor_results = build_example_anchor_set(
            numerical_circuit=numerical_circuit,
            base_results=base_results,
            power_flow_options=power_flow_options,
            logger=logger,
            target_anchor_count=9,
        )

        atlas_options: PowerFlowAtlasOptions = PowerFlowAtlasOptions(
            series_order=10,
            series_tolerance=1.0e-8,
            newton_tolerance=1.0e-9,
            maximum_newton_iterations=0,
            validity_radius=0.20,
        )
        atlas_builder: VeraGridPowerFlowAtlasBuilder = (
            VeraGridPowerFlowAtlasBuilder(
                numerical_circuit=numerical_circuit,
                atlas_options=atlas_options,
                logger=logger,
            )
        )
        build_result: AtlasBuildResult = (
            atlas_builder.build_from_power_flow_results(
                anchor_results=anchor_results,
                anchor_target_s_mva=tuple(
                    np.asarray(scenario_matrix[row_index, :], dtype=np.complex128)
                    for row_index in range(scenario_matrix.shape[0])
                ),
            )
        )
        atlas: PowerFlowAtlas | None = build_result.get_atlas()
        print("Accepted anchors:", len(anchor_results))

        if build_result.get_status() == AtlasBuildStatus.Ready and atlas is not None:
            storage_result: AtlasStorageResult = save_power_flow_atlas(
                directory_path=artifact_directory_path,
                atlas=atlas,
            )
            if storage_result.get_status() == AtlasStorageStatus.Saved:
                engine: VeraGridPowerFlowAtlasEngine = VeraGridPowerFlowAtlasEngine(
                    numerical_circuit=numerical_circuit,
                    atlas=atlas,
                    atlas_options=atlas_options,
                    power_flow_options=power_flow_options,
                    logger=logger,
                )
                base_s_mva: np.ndarray = np.asarray(
                    numerical_circuit.get_power_injections_pu(),
                    dtype=np.complex128,
                ) * numerical_circuit.Sbase
                query_matrix: np.ndarray
                nr_validation_results: tuple[PowerFlowResults, ...]
                query_matrix, nr_validation_results = build_valid_query_set(
                    numerical_circuit=numerical_circuit,
                    power_flow_options=power_flow_options,
                    logger=logger,
                    base_s_mva=base_s_mva,
                    query_count=12,
                    random_seed=2001,
                    initial_voltage_guess=np.asarray(
                        numerical_circuit.bus_data.Vbus,
                        dtype=np.complex128,
                    ),
                )
                branch_rates_mva: np.ndarray = np.asarray(
                    numerical_circuit.passive_branch_data.rates,
                    dtype=float,
                )
                fixed_passed_count: int = 0
                full_passed_count: int = 0
                worst_fixed_voltage_error: float = 0.0
                worst_fixed_from_power_error: float = 0.0
                worst_fixed_to_power_error: float = 0.0
                worst_full_voltage_error: float = 0.0
                worst_full_from_power_error: float = 0.0
                worst_full_to_power_error: float = 0.0
                worst_full_loading_error: float = 0.0
                query_index: int

                print("query  status            patch  residual     dPsum_MW   dQsum_MVAr  full_dV    full_dSf_MVA  full_dL    fixed_dV   fixed_dSf_MVA")
                for query_index in range(query_matrix.shape[0]):
                    query_s_mva: np.ndarray = np.asarray(
                        query_matrix[query_index, :],
                        dtype=np.complex128,
                    )
                    net_active_delta_mw: float = float(
                        np.sum(query_s_mva.real - base_s_mva.real)
                    )
                    net_reactive_delta_mvar: float = float(
                        np.sum(query_s_mva.imag - base_s_mva.imag)
                    )
                    query_result: VeraGridAtlasQueryResult = engine.query_mva(
                        target_s_mva=query_s_mva,
                    )
                    full_voltage_error: float = float("inf")
                    full_from_power_error: float = float("inf")
                    full_to_power_error: float = float("inf")
                    full_loading_error: float = float("inf")
                    fixed_voltage_error: float = float("inf")
                    fixed_from_power_error: float = float("inf")
                    fixed_to_power_error: float = float("inf")

                    if query_result.get_status() != AtlasQueryStatus.Failed:
                        full_nr_reference: PowerFlowResults = nr_validation_results[query_index]
                        fixed_nr_reference: NumericPowerFlowResults = run_fixed_regime_nr_reference(
                            numerical_circuit=numerical_circuit,
                            power_flow_options=power_flow_options,
                            logger=logger,
                            atlas=atlas,
                            patch_id=query_result.get_patch_id(),
                            target_s_mva=query_s_mva,
                            initial_voltage=query_result.get_voltage(),
                        )
                        flow_result: AtlasBranchFlowResult = calculate_branch_flows(
                            atlas=atlas,
                            voltage=query_result.get_voltage(),
                        )
                        full_voltage_error = calculate_voltage_error(
                            atlas_voltage=query_result.get_voltage(),
                            nr_voltage=np.asarray(full_nr_reference.voltage, dtype=np.complex128),
                        )
                        fixed_voltage_error = calculate_voltage_error(
                            atlas_voltage=query_result.get_voltage(),
                            nr_voltage=np.asarray(fixed_nr_reference.V, dtype=np.complex128),
                        )
                        if flow_result.is_successful():
                            full_from_power_error = calculate_branch_power_error(
                                atlas_power_mva=flow_result.get_from_power_mva(),
                                nr_power_mva=np.asarray(full_nr_reference.Sf, dtype=np.complex128),
                            )
                            full_to_power_error = calculate_branch_power_error(
                                atlas_power_mva=flow_result.get_to_power_mva(),
                                nr_power_mva=np.asarray(full_nr_reference.St, dtype=np.complex128),
                            )
                            full_loading_error = calculate_loading_error(
                                atlas_power_mva=flow_result.get_from_power_mva(),
                                nr_loading=np.asarray(full_nr_reference.loading, dtype=np.complex128),
                                branch_rates_mva=branch_rates_mva,
                            )
                            fixed_from_power_error = calculate_branch_power_error(
                                atlas_power_mva=flow_result.get_from_power_mva(),
                                nr_power_mva=np.asarray(fixed_nr_reference.Sf, dtype=np.complex128),
                            )
                            fixed_to_power_error = calculate_branch_power_error(
                                atlas_power_mva=flow_result.get_to_power_mva(),
                                nr_power_mva=np.asarray(fixed_nr_reference.St, dtype=np.complex128),
                            )
                        else:
                            pass
                    else:
                        pass

                    fixed_passed: bool = bool(
                        query_result.get_status() == AtlasQueryStatus.CertifiedSeries
                        and fixed_voltage_error <= 1.0e-3
                        and fixed_from_power_error <= 1.0
                    )
                    full_passed: bool = bool(
                        query_result.get_status() == AtlasQueryStatus.CertifiedSeries
                        and float(query_result.get_residual_norm()) <= 1.0e-6
                        and full_voltage_error <= 1.0e-3
                        and full_from_power_error <= 1.0
                        and full_loading_error <= 2.0e-3
                    )
                    fixed_passed_count = fixed_passed_count + int(fixed_passed)
                    full_passed_count = full_passed_count + int(full_passed)
                    worst_fixed_voltage_error = max(worst_fixed_voltage_error, fixed_voltage_error)
                    worst_fixed_from_power_error = max(
                        worst_fixed_from_power_error,
                        fixed_from_power_error,
                    )
                    worst_fixed_to_power_error = max(
                        worst_fixed_to_power_error,
                        fixed_to_power_error,
                    )
                    worst_full_voltage_error = max(worst_full_voltage_error, full_voltage_error)
                    worst_full_from_power_error = max(
                        worst_full_from_power_error,
                        full_from_power_error,
                    )
                    worst_full_to_power_error = max(
                        worst_full_to_power_error,
                        full_to_power_error,
                    )
                    worst_full_loading_error = max(
                        worst_full_loading_error,
                        full_loading_error,
                    )
                    print(
                        f"{query_index:02d}     "
                        f"{query_result.get_status().name:<16}  "
                        f"{query_result.get_patch_id():>3}  "
                        f"{query_result.get_residual_norm():.3e}  "
                        f"{net_active_delta_mw:.3e}  "
                        f"{net_reactive_delta_mvar:.3e}  "
                        f"{full_voltage_error:.3e}  "
                        f"{full_from_power_error:.3e}  "
                        f"{full_loading_error:.3e}  "
                        f"{fixed_voltage_error:.3e}  "
                        f"{fixed_from_power_error:.3e}"
                    )

                print("\nACTIVSg2000 atlas example")
                print(f"patches={atlas.get_patch_count()}")
                print(f"queries={query_matrix.shape[0]}")
                print(f"validated_queries={len(nr_validation_results)}")
                print(f"passed_vs_full_nr={full_passed_count}/{query_matrix.shape[0]}")
                print(f"passed_vs_fixed_nr={fixed_passed_count}/{query_matrix.shape[0]}")
                print(f"worst_full_voltage_diff={worst_full_voltage_error:.3e}")
                print(f"worst_full_from_power_diff_mva={worst_full_from_power_error:.3e}")
                print(f"worst_full_to_power_diff_mva={worst_full_to_power_error:.3e}")
                print(f"worst_full_loading_diff={worst_full_loading_error:.3e}")
                print(f"worst_fixed_voltage_diff={worst_fixed_voltage_error:.3e}")
                print(f"worst_fixed_from_power_diff_mva={worst_fixed_from_power_error:.3e}")
                print(f"worst_fixed_to_power_diff_mva={worst_fixed_to_power_error:.3e}")
            else:
                print(storage_result.get_message())
        else:
            print(build_result.get_message())
    else:
        print("The base VeraGrid power flow did not converge.")


def main() -> None:
    """Run the editable example with explicit local paths."""
    grid_file_path: Path = Path(__file__).resolve().with_name("case_ACTIVSg2000.matpower")
    artifact_directory_path: Path = Path(__file__).resolve().with_name("power_flow_atlas_artifact")
    run_example(
        grid_file_path=grid_file_path,
        artifact_directory_path=artifact_directory_path,
    )


if __name__ == "__main__":
    main()
else:
    pass
