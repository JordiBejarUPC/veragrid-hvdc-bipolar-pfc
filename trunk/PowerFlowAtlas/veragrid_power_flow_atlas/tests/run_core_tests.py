from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

from power_flow_atlas.branch_flows import (
    AtlasBranchFlowResult,
    calculate_branch_flows,
)
from power_flow_atlas.builder import (
    build_power_flow_atlas_patch,
    finalize_power_flow_atlas,
)
from power_flow_atlas.enumerations import (
    AtlasBuildStatus,
    AtlasFallbackMode,
    AtlasStorageStatus,
    SeriesEvaluationMethod,
)
from power_flow_atlas.model import (
    AtlasBuildResult,
    AtlasPatchBuildResult,
    AtlasStorageResult,
    DirectionalSeriesResult,
    FixedRegimeResidual,
    PowerFlowAtlas,
    PowerFlowAtlasPatch,
)
from power_flow_atlas.options import PowerFlowAtlasOptions
from power_flow_atlas.rectangular_series import (
    build_ordered_free_indices,
    build_rectangular_jacobian,
    calculate_directional_voltage_series,
    calculate_fixed_regime_residual,
)
from power_flow_atlas.storage import load_power_flow_atlas, save_power_flow_atlas


def build_three_bus_network_matrices() -> tuple[
    csc_matrix,
    csc_matrix,
    csc_matrix,
    np.ndarray,
    np.ndarray,
]:
    """Build deterministic nodal and terminal matrices for a meshed grid.

    :return: Ybus, Yf, Yt, from-bus indices, and to-bus indices.
    """
    bus_count: int = 3
    branch_count: int = 3
    y_bus_dense: np.ndarray = np.zeros(
        (bus_count, bus_count),
        dtype=np.complex128,
    )
    y_from_dense: np.ndarray = np.zeros(
        (branch_count, bus_count),
        dtype=np.complex128,
    )
    y_to_dense: np.ndarray = np.zeros(
        (branch_count, bus_count),
        dtype=np.complex128,
    )
    branch_from_indices: np.ndarray = np.asarray((0, 1, 0), dtype=np.int64)
    branch_to_indices: np.ndarray = np.asarray((1, 2, 2), dtype=np.int64)
    line_impedance: np.ndarray = np.asarray(
        (0.02 + 0.20j, 0.025 + 0.25j, 0.03 + 0.30j),
        dtype=np.complex128,
    )
    branch_index: int
    for branch_index in range(branch_count):
        from_bus: int = int(branch_from_indices[branch_index])
        to_bus: int = int(branch_to_indices[branch_index])
        line_admittance: complex = complex(1.0 / line_impedance[branch_index])

        # Ybus represents the nodal equations. Yf and Yt preserve the exact
        # branch decomposition needed to reconstruct both terminal flows.
        y_bus_dense[from_bus, from_bus] += line_admittance
        y_bus_dense[to_bus, to_bus] += line_admittance
        y_bus_dense[from_bus, to_bus] -= line_admittance
        y_bus_dense[to_bus, from_bus] -= line_admittance
        y_from_dense[branch_index, from_bus] = line_admittance
        y_from_dense[branch_index, to_bus] = -line_admittance
        y_to_dense[branch_index, from_bus] = -line_admittance
        y_to_dense[branch_index, to_bus] = line_admittance

    y_bus: csc_matrix = csc_matrix(y_bus_dense)
    y_from: csc_matrix = csc_matrix(y_from_dense)
    y_to: csc_matrix = csc_matrix(y_to_dense)
    return (
        y_bus,
        y_from,
        y_to,
        branch_from_indices,
        branch_to_indices,
    )


def build_fixed_equation_vector(
    y_bus: csc_matrix,
    voltage: np.ndarray,
    target_s: np.ndarray,
    pv_indices: np.ndarray,
    pq_indices: np.ndarray,
    free_indices: np.ndarray,
    vm2_setpoint: np.ndarray,
) -> np.ndarray:
    """Build the exact rectangular fixed-regime equation vector.

    :param y_bus: CSC nodal admittance matrix.
    :param voltage: Complex bus voltage in p.u.
    :param target_s: Specified bus injections in p.u.
    :param pv_indices: PV-bus indices.
    :param pq_indices: PQ-bus indices.
    :param free_indices: Ordered PV-then-PQ bus indices.
    :param vm2_setpoint: Squared voltage target at each PV bus.
    :return: Dense real equation vector.
    """
    free_count: int = free_indices.size
    pq_count: int = pq_indices.size
    pv_count: int = pv_indices.size
    calculated_s: np.ndarray = voltage * np.conj(y_bus @ voltage)
    equations: np.ndarray = np.zeros(2 * free_count, dtype=float)
    equations[:free_count] = (
        calculated_s.real[free_indices] - target_s.real[free_indices]
    )
    equations[free_count:free_count + pq_count] = (
        calculated_s.imag[pq_indices] - target_s.imag[pq_indices]
    )
    equations[free_count + pq_count:free_count + pq_count + pv_count] = (
        np.square(np.abs(voltage[pv_indices])) - vm2_setpoint
    )
    return equations


def solve_fixed_power_flow(
    y_bus: csc_matrix,
    initial_voltage: np.ndarray,
    target_s: np.ndarray,
    pv_indices: np.ndarray,
    pq_indices: np.ndarray,
    vm2_setpoint: np.ndarray,
) -> tuple[np.ndarray, bool]:
    """Solve the test fixed-regime equations by rectangular Newton iterations.

    This solver exists only as an independent test oracle. Production queries
    use the stored atlas factorization and VeraGrid's own correction solver.

    :param y_bus: CSC nodal admittance matrix.
    :param initial_voltage: Initial complex voltage in p.u.
    :param target_s: Specified complex bus injections in p.u.
    :param pv_indices: PV-bus indices.
    :param pq_indices: PQ-bus indices.
    :param vm2_setpoint: Squared voltage target at each PV bus.
    :return: Solved voltage and convergence flag.
    """
    free_indices: np.ndarray = build_ordered_free_indices(
        pv_indices=pv_indices,
        pq_indices=pq_indices,
    )
    free_count: int = free_indices.size
    voltage: np.ndarray = initial_voltage.copy()
    converged: bool = False
    iteration_index: int = 0
    maximum_iterations: int = 30

    while iteration_index < maximum_iterations and not converged:
        equations: np.ndarray = build_fixed_equation_vector(
            y_bus=y_bus,
            voltage=voltage,
            target_s=target_s,
            pv_indices=pv_indices,
            pq_indices=pq_indices,
            free_indices=free_indices,
            vm2_setpoint=vm2_setpoint,
        )
        residual_norm: float = float(np.max(np.abs(equations), initial=0.0))
        if residual_norm <= 1.0e-13:
            converged = True
        else:
            jacobian: csc_matrix = build_rectangular_jacobian(
                y_bus=y_bus,
                anchor_v=voltage,
                pv_indices=pv_indices,
                pq_indices=pq_indices,
                free_indices=free_indices,
            )
            correction: np.ndarray = splu(jacobian).solve(-equations)
            voltage[free_indices] += (
                correction[:free_count]
                + 1.0j * correction[free_count:]
            )
            iteration_index += 1

    return voltage, converged


def build_test_patch() -> tuple[csc_matrix, PowerFlowAtlasPatch, np.ndarray]:
    """Build one certified mixed PV/PQ patch and its target injection vector.

    :return: Ybus, certified patch, and nearby target injections.
    """
    y_bus: csc_matrix
    y_from: csc_matrix
    y_to: csc_matrix
    branch_from_indices: np.ndarray
    branch_to_indices: np.ndarray
    (
        y_bus,
        y_from,
        y_to,
        branch_from_indices,
        branch_to_indices,
    ) = build_three_bus_network_matrices()
    slack_indices: np.ndarray = np.asarray((0,), dtype=np.int64)
    pv_indices: np.ndarray = np.asarray((1,), dtype=np.int64)
    pq_indices: np.ndarray = np.asarray((2,), dtype=np.int64)
    bus_types: np.ndarray = np.asarray((3, 2, 1), dtype=np.int64)
    vm2_setpoint: np.ndarray = np.asarray((1.02 * 1.02,), dtype=float)
    specified_anchor_s: np.ndarray = np.asarray(
        (0.0 + 0.0j, 0.40 + 0.0j, -0.80 - 0.30j),
        dtype=np.complex128,
    )
    initial_voltage: np.ndarray = np.asarray(
        (1.0 + 0.0j, 1.02 + 0.0j, 1.0 + 0.0j),
        dtype=np.complex128,
    )
    anchor_v: np.ndarray
    anchor_converged: bool
    anchor_v, anchor_converged = solve_fixed_power_flow(
        y_bus=y_bus,
        initial_voltage=initial_voltage,
        target_s=specified_anchor_s,
        pv_indices=pv_indices,
        pq_indices=pq_indices,
        vm2_setpoint=vm2_setpoint,
    )
    assert anchor_converged

    # VeraGrid results contain the solved output powers at slack and PV buses.
    # The test reproduces that representation before constructing the patch.
    anchor_s: np.ndarray = anchor_v * np.conj(y_bus @ anchor_v)
    anchor_s[pq_indices] = specified_anchor_s[pq_indices]
    q_min: np.ndarray = np.full(3, -2.0, dtype=float)
    q_max: np.ndarray = np.full(3, 2.0, dtype=float)
    patch_result: AtlasPatchBuildResult = build_power_flow_atlas_patch(
        patch_id=7,
        y_bus=y_bus,
        anchor_s=anchor_s,
        anchor_v=anchor_v,
        bus_types=bus_types,
        slack_indices=slack_indices,
        pv_indices=pv_indices,
        pq_indices=pq_indices,
        q_min=q_min,
        q_max=q_max,
        series_order=10,
        validity_radius=0.25,
        anchor_tolerance=1.0e-11,
    )
    patch: PowerFlowAtlasPatch | None = patch_result.get_patch()
    assert patch_result.get_status() == AtlasBuildStatus.Ready
    assert patch is not None

    target_s: np.ndarray = anchor_s.copy()
    target_s[1] = complex(0.42, anchor_s[1].imag)
    target_s[2] = -0.82 - 0.31j
    return y_bus, patch, target_s


def test_rectangular_jacobian() -> None:
    """Verify the analytic CSC Jacobian against central finite differences."""
    y_bus: csc_matrix
    patch: PowerFlowAtlasPatch
    target_s: np.ndarray
    y_bus, patch, target_s = build_test_patch()
    voltage: np.ndarray = patch.get_anchor_v()
    pv_indices: np.ndarray = patch.get_pv_indices()
    pq_indices: np.ndarray = patch.get_pq_indices()
    free_indices: np.ndarray = patch.get_free_indices()
    vm2_setpoint: np.ndarray = patch.get_vm2_setpoint()
    free_count: int = free_indices.size
    analytic_jacobian: np.ndarray = patch.get_rectangular_jacobian().toarray()
    numeric_jacobian: np.ndarray = np.zeros_like(analytic_jacobian)
    perturbation: float = 1.0e-7
    column_index: int

    for column_index in range(2 * free_count):
        positive_voltage: np.ndarray = voltage.copy()
        negative_voltage: np.ndarray = voltage.copy()
        state_bus_position: int = column_index % free_count
        bus_index: int = int(free_indices[state_bus_position])
        if column_index < free_count:
            positive_voltage[bus_index] += perturbation
            negative_voltage[bus_index] -= perturbation
        else:
            positive_voltage[bus_index] += 1.0j * perturbation
            negative_voltage[bus_index] -= 1.0j * perturbation
        positive_equations: np.ndarray = build_fixed_equation_vector(
            y_bus=y_bus,
            voltage=positive_voltage,
            target_s=target_s,
            pv_indices=pv_indices,
            pq_indices=pq_indices,
            free_indices=free_indices,
            vm2_setpoint=vm2_setpoint,
        )
        negative_equations: np.ndarray = build_fixed_equation_vector(
            y_bus=y_bus,
            voltage=negative_voltage,
            target_s=target_s,
            pv_indices=pv_indices,
            pq_indices=pq_indices,
            free_indices=free_indices,
            vm2_setpoint=vm2_setpoint,
        )
        numeric_jacobian[:, column_index] = (
            positive_equations - negative_equations
        ) / (2.0 * perturbation)

    maximum_error: float = float(
        np.max(np.abs(analytic_jacobian - numeric_jacobian), initial=0.0)
    )
    assert maximum_error <= 1.0e-7


def test_directional_series() -> None:
    """Verify the directional series against an independently solved target."""
    y_bus: csc_matrix
    patch: PowerFlowAtlasPatch
    target_s: np.ndarray
    y_bus, patch, target_s = build_test_patch()
    series_result: DirectionalSeriesResult = calculate_directional_voltage_series(
        y_bus=y_bus,
        target_s=target_s,
        patch=patch,
        evaluation_method=SeriesEvaluationMethod.Pade,
        minimum_pade_denominator=1.0e-12,
    )
    residual: FixedRegimeResidual = calculate_fixed_regime_residual(
        y_bus=y_bus,
        voltage=series_result.get_voltage(),
        target_s=target_s,
        patch=patch,
        reactive_limit_tolerance=1.0e-10,
    )
    exact_voltage: np.ndarray
    exact_converged: bool
    exact_voltage, exact_converged = solve_fixed_power_flow(
        y_bus=y_bus,
        initial_voltage=patch.get_anchor_v(),
        target_s=target_s,
        pv_indices=patch.get_pv_indices(),
        pq_indices=patch.get_pq_indices(),
        vm2_setpoint=patch.get_vm2_setpoint(),
    )
    maximum_voltage_error: float = float(
        np.max(
            np.abs(series_result.get_voltage() - exact_voltage),
            initial=0.0,
        )
    )
    assert series_result.is_successful()
    assert exact_converged
    assert residual.are_reactive_limits_valid()
    assert residual.get_norm() <= 1.0e-10
    assert maximum_voltage_error <= 1.0e-10


def test_storage_round_trip() -> None:
    """Verify that CSC data reloads and reproduces the same atlas query."""
    y_bus: csc_matrix
    patch: PowerFlowAtlasPatch
    target_s: np.ndarray
    y_bus, patch, target_s = build_test_patch()
    network_y_bus: csc_matrix
    y_from: csc_matrix
    y_to: csc_matrix
    branch_from_indices: np.ndarray
    branch_to_indices: np.ndarray
    (
        network_y_bus,
        y_from,
        y_to,
        branch_from_indices,
        branch_to_indices,
    ) = build_three_bus_network_matrices()
    assert np.max(np.abs((network_y_bus - y_bus).data), initial=0.0) == 0.0
    build_result: AtlasBuildResult = finalize_power_flow_atlas(
        system_base_power=100.0,
        y_bus=y_bus,
        patches=(patch,),
        y_from=y_from,
        y_to=y_to,
        branch_from_indices=branch_from_indices,
        branch_to_indices=branch_to_indices,
    )
    atlas: PowerFlowAtlas | None = build_result.get_atlas()
    assert build_result.get_status() == AtlasBuildStatus.Ready
    assert atlas is not None

    temporary_directory: str
    with TemporaryDirectory() as temporary_directory:
        directory_path: Path = Path(temporary_directory)
        save_result: AtlasStorageResult = save_power_flow_atlas(
            directory_path=directory_path,
            atlas=atlas,
        )
        load_result: AtlasStorageResult = load_power_flow_atlas(
            directory_path=directory_path,
        )
        loaded_atlas: PowerFlowAtlas | None = load_result.get_atlas()
        assert save_result.get_status() == AtlasStorageStatus.Saved
        assert load_result.get_status() == AtlasStorageStatus.Loaded
        assert loaded_atlas is not None
        assert (
            loaded_atlas.get_topology_signature()
            == atlas.get_topology_signature()
        )
        loaded_patch: PowerFlowAtlasPatch | None = loaded_atlas.get_patch(0)
        assert loaded_patch is not None
        assert loaded_atlas.has_branch_model()
        original_series: DirectionalSeriesResult = calculate_directional_voltage_series(
            y_bus=y_bus,
            target_s=target_s,
            patch=patch,
            evaluation_method=SeriesEvaluationMethod.Pade,
            minimum_pade_denominator=1.0e-12,
        )
        loaded_series: DirectionalSeriesResult = calculate_directional_voltage_series(
            y_bus=loaded_atlas.get_y_bus(),
            target_s=target_s,
            patch=loaded_patch,
            evaluation_method=SeriesEvaluationMethod.Pade,
            minimum_pade_denominator=1.0e-12,
        )
        maximum_difference: float = float(
            np.max(
                np.abs(original_series.get_voltage() - loaded_series.get_voltage()),
                initial=0.0,
            )
        )
        assert maximum_difference <= 1.0e-14


def test_branch_flow_reconstruction() -> None:
    """Verify exact terminal powers and losses from stored VeraGrid matrices."""
    y_bus: csc_matrix
    patch: PowerFlowAtlasPatch
    target_s: np.ndarray
    y_bus, patch, target_s = build_test_patch()
    network_y_bus: csc_matrix
    y_from: csc_matrix
    y_to: csc_matrix
    branch_from_indices: np.ndarray
    branch_to_indices: np.ndarray
    (
        network_y_bus,
        y_from,
        y_to,
        branch_from_indices,
        branch_to_indices,
    ) = build_three_bus_network_matrices()
    assert np.max(np.abs((network_y_bus - y_bus).data), initial=0.0) == 0.0
    build_result: AtlasBuildResult = finalize_power_flow_atlas(
        system_base_power=100.0,
        y_bus=y_bus,
        patches=(patch,),
        y_from=y_from,
        y_to=y_to,
        branch_from_indices=branch_from_indices,
        branch_to_indices=branch_to_indices,
    )
    atlas: PowerFlowAtlas | None = build_result.get_atlas()
    assert atlas is not None
    series_result: DirectionalSeriesResult = calculate_directional_voltage_series(
        y_bus=y_bus,
        target_s=target_s,
        patch=patch,
        evaluation_method=SeriesEvaluationMethod.Pade,
        minimum_pade_denominator=1.0e-12,
    )
    flow_result: AtlasBranchFlowResult = calculate_branch_flows(
        atlas=atlas,
        voltage=series_result.get_voltage(),
    )
    assert flow_result.is_successful()
    nodal_from_branches: np.ndarray = np.zeros(3, dtype=np.complex128)
    branch_index: int
    from_power_mva: np.ndarray = flow_result.get_from_power_mva()
    to_power_mva: np.ndarray = flow_result.get_to_power_mva()
    for branch_index in range(branch_from_indices.size):
        from_bus: int = int(branch_from_indices[branch_index])
        to_bus: int = int(branch_to_indices[branch_index])
        nodal_from_branches[from_bus] += from_power_mva[branch_index]
        nodal_from_branches[to_bus] += to_power_mva[branch_index]
    voltage: np.ndarray = series_result.get_voltage()
    nodal_from_y_bus: np.ndarray = (
        voltage * np.conj(y_bus @ voltage) * atlas.get_system_base_power()
    )
    maximum_power_difference: float = float(
        np.max(np.abs(nodal_from_branches - nodal_from_y_bus), initial=0.0)
    )
    assert maximum_power_difference <= 1.0e-11
    assert np.all(flow_result.get_losses_mva().real >= -1.0e-12)


def test_option_validation() -> None:
    """Verify that invalid option inputs leave a complete valid object."""
    options: PowerFlowAtlasOptions = PowerFlowAtlasOptions(
        series_order=0,
        series_method="not-an-enum",  # type: ignore[arg-type]
        series_tolerance=0.0,
        newton_tolerance=-1.0,
        maximum_newton_iterations=-2,
        validity_radius=0.0,
        minimum_pade_denominator=0.0,
        reactive_limit_tolerance=-1.0,
        fallback_mode="not-an-enum",  # type: ignore[arg-type]
    )
    assert options.get_series_order() == 1
    assert options.get_series_method() == SeriesEvaluationMethod.Pade
    assert options.get_series_tolerance() == 1.0e-8
    assert options.get_newton_tolerance() == 1.0e-10
    assert options.get_maximum_newton_iterations() == 0
    assert options.get_validity_radius() == 0.15
    assert options.get_minimum_pade_denominator() == 1.0e-10
    assert options.get_reactive_limit_tolerance() == 0.0
    assert options.get_fallback_mode() == AtlasFallbackMode.FullPowerFlow


def main() -> None:
    """Run all dependency-free numerical core tests."""
    test_rectangular_jacobian()
    test_directional_series()
    test_storage_round_trip()
    test_branch_flow_reconstruction()
    test_option_validation()
    print("All power-flow atlas core tests passed.")


if __name__ == "__main__":
    main()
else:
    pass
