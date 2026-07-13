from __future__ import annotations

import numpy as np

from power_flow_atlas.model import PatchSelectionResult, PowerFlowAtlas, PowerFlowAtlasPatch
from power_flow_atlas.rectangular_series import compose_first_order_right_hand_side


def calculate_patch_linear_distance(
    target_s: np.ndarray,
    patch: PowerFlowAtlasPatch,
) -> float:
    """Estimate query distance using the patch's first state coefficient.

    :param target_s: Target nodal complex injections in p.u.
    :param patch: Candidate local chart.
    :return: Maximum normalized first-order bus-voltage displacement.
    """
    anchor_v: np.ndarray = patch.get_anchor_v()
    free_indices: np.ndarray = patch.get_free_indices()
    right_hand_side: np.ndarray = compose_first_order_right_hand_side(
        target_s=target_s,
        patch=patch,
    )
    state_coefficient: np.ndarray = patch.solve_jacobian(right_hand_side)
    free_count: int = free_indices.size
    first_voltage_coefficient: np.ndarray = (
        state_coefficient[:free_count]
        + 1.0j * state_coefficient[free_count:]
    )
    voltage_scale: np.ndarray = np.maximum(np.abs(anchor_v[free_indices]), 0.1)
    relative_motion: np.ndarray = np.abs(first_voltage_coefficient) / voltage_scale
    distance: float
    if relative_motion.size > 0 and np.all(np.isfinite(relative_motion)):
        distance = float(np.max(relative_motion))
    else:
        if relative_motion.size == 0:
            distance = 0.0
        else:
            distance = float("inf")
    return distance


def select_nearest_atlas_patch(
    atlas: PowerFlowAtlas,
    target_s: np.ndarray,
) -> PatchSelectionResult:
    """Select the local chart with the smallest sensitivity-scaled distance.

    :param atlas: Finalized power-flow atlas.
    :param target_s: Target nodal complex injections in p.u.
    :return: Explicit patch-selection result.
    """
    patch_count: int = atlas.get_patch_count()
    bus_count: int = atlas.get_bus_count()
    result: PatchSelectionResult
    if target_s.size == bus_count and patch_count > 0:
        distances: np.ndarray = np.full(patch_count, np.inf, dtype=float)
        patch_index: int
        for patch_index in range(patch_count):
            patch: PowerFlowAtlasPatch | None = atlas.get_patch(patch_index)
            if patch is not None:
                distances[patch_index] = calculate_patch_linear_distance(
                    target_s=target_s,
                    patch=patch,
                )
            else:
                distances[patch_index] = np.inf

        best_patch_index: int = int(np.argmin(distances))
        best_distance: float = float(distances[best_patch_index])
        if np.isfinite(best_distance):
            result = PatchSelectionResult(
                found=True,
                patch_index=best_patch_index,
                normalized_distance=best_distance,
                message="Nearest patch selected by first-order state displacement",
            )
        else:
            result = PatchSelectionResult(
                found=False,
                patch_index=-1,
                normalized_distance=float("inf"),
                message="Every patch produced a non-finite linear predictor",
            )
    else:
        result = PatchSelectionResult(
            found=False,
            patch_index=-1,
            normalized_distance=float("inf"),
            message="Target injection size or atlas patch count is invalid",
        )
    return result
