from __future__ import annotations

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import SuperLU, splu

from power_flow_atlas.enumerations import AtlasBuildStatus
from power_flow_atlas.model import (
    AtlasBuildResult,
    AtlasPatchBuildResult,
    FixedRegimeResidual,
    PowerFlowAtlas,
    PowerFlowAtlasPatch,
)
from power_flow_atlas.rectangular_series import (
    build_ordered_free_indices,
    build_rectangular_jacobian,
    build_topology_signature,
    calculate_fixed_regime_residual,
)


def build_power_flow_atlas_patch(
    patch_id: int,
    y_bus: csc_matrix,
    anchor_s: np.ndarray,
    anchor_v: np.ndarray,
    bus_types: np.ndarray,
    slack_indices: np.ndarray,
    pv_indices: np.ndarray,
    pq_indices: np.ndarray,
    q_min: np.ndarray,
    q_max: np.ndarray,
    series_order: int,
    validity_radius: float,
    anchor_tolerance: float,
) -> AtlasPatchBuildResult:
    """Build one fixed-regime quadratic atlas patch from solved arrays.

    :param patch_id: Stable numeric patch identifier.
    :param y_bus: CSC nodal admittance matrix.
    :param anchor_s: Solved anchor nodal injections in p.u.
    :param anchor_v: Solved anchor complex bus voltage in p.u.
    :param bus_types: VeraGrid bus-type codes for this regime.
    :param slack_indices: Slack-bus indices.
    :param pv_indices: PV-bus indices.
    :param pq_indices: PQ-bus indices.
    :param q_min: Nodal reactive lower limits in p.u.
    :param q_max: Nodal reactive upper limits in p.u.
    :param series_order: Maximum directional voltage-series order.
    :param validity_radius: Maximum normalized first-order displacement.
    :param anchor_tolerance: Maximum accepted anchor mismatch.
    :return: Explicit patch-build result.
    """
    bus_count: int = anchor_v.size
    sizes_valid: bool = (
        y_bus.shape == (bus_count, bus_count)
        and anchor_s.size == bus_count
        and bus_types.size == bus_count
        and q_min.size == bus_count
        and q_max.size == bus_count
    )
    values_finite: bool = bool(
        np.all(np.isfinite(anchor_s))
        and np.all(np.isfinite(anchor_v))
        and np.all(np.isfinite(y_bus.data))
    )
    index_count_valid: bool = (
        slack_indices.size + pv_indices.size + pq_indices.size == bus_count
    )

    result: AtlasPatchBuildResult
    if sizes_valid and values_finite and index_count_valid:
        free_indices: np.ndarray = build_ordered_free_indices(
            pv_indices=pv_indices,
            pq_indices=pq_indices,
        )
        vm2_setpoint: np.ndarray = np.square(np.abs(anchor_v[pv_indices]))

        # The residual check certifies that the stored anchor lies on the same
        # fixed-regime manifold represented by the quadratic chart.
        temporary_jacobian: csc_matrix = build_rectangular_jacobian(
            y_bus=y_bus,
            anchor_v=anchor_v,
            pv_indices=pv_indices,
            pq_indices=pq_indices,
            free_indices=free_indices,
        )
        factorization: SuperLU | None = None
        factorization_successful: bool = True
        try:
            factorization = splu(temporary_jacobian)
        except RuntimeError:
            factorization_successful = False

        if factorization_successful and factorization is not None:
            provisional_patch: PowerFlowAtlasPatch = PowerFlowAtlasPatch(
                patch_id=patch_id,
                anchor_s=anchor_s,
                anchor_v=anchor_v,
                bus_types=bus_types,
                slack_indices=slack_indices,
                pv_indices=pv_indices,
                pq_indices=pq_indices,
                free_indices=free_indices,
                vm2_setpoint=vm2_setpoint,
                q_min=q_min,
                q_max=q_max,
                rectangular_jacobian=temporary_jacobian,
                factorization=factorization,
                validity_radius=validity_radius,
                series_order=series_order,
                anchor_residual=0.0,
            )
            anchor_residual: FixedRegimeResidual = calculate_fixed_regime_residual(
                y_bus=y_bus,
                voltage=anchor_v,
                target_s=anchor_s,
                patch=provisional_patch,
                reactive_limit_tolerance=0.0,
            )
            anchor_residual_norm: float = anchor_residual.get_norm()

            if anchor_residual_norm <= anchor_tolerance:
                patch: PowerFlowAtlasPatch = PowerFlowAtlasPatch(
                    patch_id=patch_id,
                    anchor_s=anchor_s,
                    anchor_v=anchor_v,
                    bus_types=bus_types,
                    slack_indices=slack_indices,
                    pv_indices=pv_indices,
                    pq_indices=pq_indices,
                    free_indices=free_indices,
                    vm2_setpoint=vm2_setpoint,
                    q_min=q_min,
                    q_max=q_max,
                    rectangular_jacobian=temporary_jacobian,
                    factorization=factorization,
                    validity_radius=validity_radius,
                    series_order=series_order,
                    anchor_residual=anchor_residual_norm,
                )
                result = AtlasPatchBuildResult(
                    status=AtlasBuildStatus.Ready,
                    patch=patch,
                    message="Patch built and anchor certified",
                )
            else:
                result = AtlasPatchBuildResult(
                    status=AtlasBuildStatus.AnchorNotConverged,
                    patch=None,
                    message="Anchor residual exceeds the configured tolerance",
                )
        else:
            result = AtlasPatchBuildResult(
                status=AtlasBuildStatus.SingularJacobian,
                patch=None,
                message="The rectangular anchor Jacobian cannot be factorized",
            )
    else:
        result = AtlasPatchBuildResult(
            status=AtlasBuildStatus.InvalidInput,
            patch=None,
            message="Patch arrays have incompatible sizes, indices, or values",
        )

    return result


def finalize_power_flow_atlas(
    system_base_power: float,
    y_bus: csc_matrix,
    patches: tuple[PowerFlowAtlasPatch, ...],
    y_from: csc_matrix | None = None,
    y_to: csc_matrix | None = None,
    branch_from_indices: np.ndarray | None = None,
    branch_to_indices: np.ndarray | None = None,
) -> AtlasBuildResult:
    """Finalize an immutable power-flow atlas from compatible patches.

    :param system_base_power: VeraGrid system base power in MVA.
    :param y_bus: Shared CSC nodal admittance matrix.
    :param patches: Finalized local patches for the same topology.
    :param y_from: Optional CSC from-terminal branch admittance matrix.
    :param y_to: Optional CSC to-terminal branch admittance matrix.
    :param branch_from_indices: Optional from-terminal bus indices.
    :param branch_to_indices: Optional to-terminal bus indices.
    :return: Explicit atlas-build result.
    """
    patch_count: int = len(patches)
    result: AtlasBuildResult
    if patch_count > 0:
        first_patch: PowerFlowAtlasPatch = patches[0]
        bus_count: int = first_patch.get_anchor_v().size
        compatible: bool = y_bus.shape == (bus_count, bus_count)
        branch_data_complete: bool = bool(
            y_from is not None
            and y_to is not None
            and branch_from_indices is not None
            and branch_to_indices is not None
        )
        branch_data_absent: bool = bool(
            y_from is None
            and y_to is None
            and branch_from_indices is None
            and branch_to_indices is None
        )
        if branch_data_complete:
            branch_count: int = int(branch_from_indices.size)
            branch_compatible: bool = bool(
                branch_to_indices.size == branch_count
                and y_from.shape == (branch_count, bus_count)
                and y_to.shape == (branch_count, bus_count)
            )
        else:
            if branch_data_absent:
                branch_compatible = True
            else:
                branch_compatible = False
        compatible = compatible and branch_compatible
        patch_index: int
        for patch_index in range(patch_count):
            patch: PowerFlowAtlasPatch = patches[patch_index]
            patch_bus_count: int = patch.get_anchor_v().size
            if patch_bus_count == bus_count:
                compatible = compatible and True
            else:
                compatible = False

        if compatible:
            topology_signature: str = build_topology_signature(
                system_base_power=system_base_power,
                y_bus=y_bus,
                y_from=y_from,
                y_to=y_to,
                branch_from_indices=branch_from_indices,
                branch_to_indices=branch_to_indices,
            )
            atlas: PowerFlowAtlas = PowerFlowAtlas(
                topology_signature=topology_signature,
                system_base_power=system_base_power,
                bus_count=bus_count,
                y_bus=y_bus,
                y_from=y_from,
                y_to=y_to,
                branch_from_indices=branch_from_indices,
                branch_to_indices=branch_to_indices,
                patches=patches,
            )
            result = AtlasBuildResult(
                status=AtlasBuildStatus.Ready,
                atlas=atlas,
                message="Atlas finalized",
            )
        else:
            result = AtlasBuildResult(
                status=AtlasBuildStatus.InvalidInput,
                atlas=None,
                message="Patches are not compatible with the shared topology",
            )
    else:
        result = AtlasBuildResult(
            status=AtlasBuildStatus.InvalidInput,
            atlas=None,
            message="At least one patch is required",
        )
    return result
