from __future__ import annotations

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import SuperLU

from power_flow_atlas.enumerations import AtlasBuildStatus, AtlasStorageStatus


class PowerFlowAtlasPatch:
    """Immutable local chart of one classical AC power-flow control regime."""

    __slots__ = (
        "_patch_id",
        "_anchor_s",
        "_anchor_v",
        "_bus_types",
        "_slack_indices",
        "_pv_indices",
        "_pq_indices",
        "_free_indices",
        "_vm2_setpoint",
        "_q_min",
        "_q_max",
        "_rectangular_jacobian",
        "_factorization",
        "_validity_radius",
        "_series_order",
        "_anchor_residual",
    )

    def __init__(
        self,
        patch_id: int,
        anchor_s: np.ndarray,
        anchor_v: np.ndarray,
        bus_types: np.ndarray,
        slack_indices: np.ndarray,
        pv_indices: np.ndarray,
        pq_indices: np.ndarray,
        free_indices: np.ndarray,
        vm2_setpoint: np.ndarray,
        q_min: np.ndarray,
        q_max: np.ndarray,
        rectangular_jacobian: csc_matrix,
        factorization: SuperLU,
        validity_radius: float,
        series_order: int,
        anchor_residual: float,
    ) -> None:
        """Create one finalized atlas patch.

        :param patch_id: Stable numeric patch identifier.
        :param anchor_s: Anchor nodal injections in p.u.
        :param anchor_v: Anchor complex bus voltages in p.u.
        :param bus_types: VeraGrid bus-type codes for the fixed regime.
        :param slack_indices: Slack-bus indices.
        :param pv_indices: PV-bus indices.
        :param pq_indices: PQ-bus indices.
        :param free_indices: State buses ordered as PV followed by PQ buses.
        :param vm2_setpoint: Squared voltage setpoint at every PV bus.
        :param q_min: Nodal reactive lower limits in p.u.
        :param q_max: Nodal reactive upper limits in p.u.
        :param rectangular_jacobian: CSC Jacobian of the quadratic chart.
        :param factorization: Reusable sparse LU factorization of the Jacobian.
        :param validity_radius: Maximum normalized first-order displacement.
        :param series_order: Maximum directional series order.
        :param anchor_residual: Fixed-regime residual at the anchor.
        """
        self._patch_id: int = patch_id
        self._anchor_s: np.ndarray = anchor_s.copy()
        self._anchor_v: np.ndarray = anchor_v.copy()
        self._bus_types: np.ndarray = bus_types.copy()
        self._slack_indices: np.ndarray = slack_indices.copy()
        self._pv_indices: np.ndarray = pv_indices.copy()
        self._pq_indices: np.ndarray = pq_indices.copy()
        self._free_indices: np.ndarray = free_indices.copy()
        self._vm2_setpoint: np.ndarray = vm2_setpoint.copy()
        self._q_min: np.ndarray = q_min.copy()
        self._q_max: np.ndarray = q_max.copy()
        self._rectangular_jacobian: csc_matrix = rectangular_jacobian.copy()
        self._factorization: SuperLU = factorization
        self._validity_radius: float = validity_radius
        self._series_order: int = series_order
        self._anchor_residual: float = anchor_residual

    def get_patch_id(self) -> int:
        """Return the stable numeric patch identifier."""
        return self._patch_id

    def get_anchor_s(self) -> np.ndarray:
        """Return a read-only-use copy of the anchor injections."""
        return self._anchor_s.copy()

    def get_anchor_v(self) -> np.ndarray:
        """Return a read-only-use copy of the anchor voltages."""
        return self._anchor_v.copy()

    def get_bus_types(self) -> np.ndarray:
        """Return a copy of the fixed VeraGrid bus-type codes."""
        return self._bus_types.copy()

    def get_slack_indices(self) -> np.ndarray:
        """Return a copy of the slack-bus indices."""
        return self._slack_indices.copy()

    def get_pv_indices(self) -> np.ndarray:
        """Return a copy of the PV-bus indices."""
        return self._pv_indices.copy()

    def get_pq_indices(self) -> np.ndarray:
        """Return a copy of the PQ-bus indices."""
        return self._pq_indices.copy()

    def get_free_indices(self) -> np.ndarray:
        """Return a copy of the ordered non-slack state-bus indices."""
        return self._free_indices.copy()

    def get_vm2_setpoint(self) -> np.ndarray:
        """Return a copy of the PV squared-voltage setpoints."""
        return self._vm2_setpoint.copy()

    def get_q_min(self) -> np.ndarray:
        """Return a copy of the nodal reactive lower limits."""
        return self._q_min.copy()

    def get_q_max(self) -> np.ndarray:
        """Return a copy of the nodal reactive upper limits."""
        return self._q_max.copy()

    def get_rectangular_jacobian(self) -> csc_matrix:
        """Return a copy of the stored CSC rectangular Jacobian."""
        return self._rectangular_jacobian.copy()

    def solve_jacobian(self, right_hand_side: np.ndarray) -> np.ndarray:
        """Solve the stored local linear system.

        :param right_hand_side: Dense real right-hand side.
        :return: Dense real solution vector.
        """
        solution: np.ndarray = self._factorization.solve(right_hand_side)
        return solution

    def get_validity_radius(self) -> float:
        """Return the normalized first-order validity radius."""
        return self._validity_radius

    def get_series_order(self) -> int:
        """Return the maximum directional series order."""
        return self._series_order

    def get_anchor_residual(self) -> float:
        """Return the fixed-regime residual at the patch anchor."""
        return self._anchor_residual


class PowerFlowAtlas:
    """Finalized collection of local charts for one compiled grid topology."""

    __slots__ = (
        "_topology_signature",
        "_system_base_power",
        "_bus_count",
        "_y_bus",
        "_y_from",
        "_y_to",
        "_branch_from_indices",
        "_branch_to_indices",
        "_patches",
    )

    def __init__(
        self,
        topology_signature: str,
        system_base_power: float,
        bus_count: int,
        y_bus: csc_matrix,
        y_from: csc_matrix | None,
        y_to: csc_matrix | None,
        branch_from_indices: np.ndarray | None,
        branch_to_indices: np.ndarray | None,
        patches: tuple[PowerFlowAtlasPatch, ...],
    ) -> None:
        """Create a finalized atlas.

        :param topology_signature: Stable hash of the compiled electrical model.
        :param system_base_power: VeraGrid system base power in MVA.
        :param bus_count: Number of compiled buses.
        :param y_bus: Shared CSC nodal admittance matrix.
        :param y_from: Optional CSC from-terminal branch admittance matrix.
        :param y_to: Optional CSC to-terminal branch admittance matrix.
        :param branch_from_indices: Optional from-terminal bus indices.
        :param branch_to_indices: Optional to-terminal bus indices.
        :param patches: Immutable tuple of local atlas patches.
        """
        self._topology_signature: str = topology_signature
        self._system_base_power: float = system_base_power
        self._bus_count: int = bus_count
        self._y_bus: csc_matrix = y_bus.copy()
        if y_from is not None:
            self._y_from: csc_matrix | None = y_from.copy()
        else:
            self._y_from = None
        if y_to is not None:
            self._y_to: csc_matrix | None = y_to.copy()
        else:
            self._y_to = None
        if branch_from_indices is not None:
            self._branch_from_indices: np.ndarray | None = (
                branch_from_indices.copy()
            )
        else:
            self._branch_from_indices = None
        if branch_to_indices is not None:
            self._branch_to_indices: np.ndarray | None = branch_to_indices.copy()
        else:
            self._branch_to_indices = None
        self._patches: tuple[PowerFlowAtlasPatch, ...] = patches

    def get_topology_signature(self) -> str:
        """Return the stable topology signature."""
        return self._topology_signature

    def get_system_base_power(self) -> float:
        """Return the system base power in MVA."""
        return self._system_base_power

    def get_bus_count(self) -> int:
        """Return the number of buses represented by the atlas."""
        return self._bus_count

    def get_y_bus(self) -> csc_matrix:
        """Return a copy of the shared CSC nodal admittance matrix."""
        return self._y_bus.copy()

    def get_y_from(self) -> csc_matrix | None:
        """Return a copy of the from-terminal branch matrix when stored."""
        y_from: csc_matrix | None
        if self._y_from is not None:
            y_from = self._y_from.copy()
        else:
            y_from = None
        return y_from

    def get_y_to(self) -> csc_matrix | None:
        """Return a copy of the to-terminal branch matrix when stored."""
        y_to: csc_matrix | None
        if self._y_to is not None:
            y_to = self._y_to.copy()
        else:
            y_to = None
        return y_to

    def get_branch_from_indices(self) -> np.ndarray | None:
        """Return a copy of the branch from-terminal indices when stored."""
        branch_from_indices: np.ndarray | None
        if self._branch_from_indices is not None:
            branch_from_indices = self._branch_from_indices.copy()
        else:
            branch_from_indices = None
        return branch_from_indices

    def get_branch_to_indices(self) -> np.ndarray | None:
        """Return a copy of the branch to-terminal indices when stored."""
        branch_to_indices: np.ndarray | None
        if self._branch_to_indices is not None:
            branch_to_indices = self._branch_to_indices.copy()
        else:
            branch_to_indices = None
        return branch_to_indices

    def has_branch_model(self) -> bool:
        """Return whether complete terminal branch matrices are stored."""
        present: bool = bool(
            self._y_from is not None
            and self._y_to is not None
            and self._branch_from_indices is not None
            and self._branch_to_indices is not None
        )
        return present

    def get_patch_count(self) -> int:
        """Return the number of finalized local charts."""
        return len(self._patches)

    def get_patch(self, patch_index: int) -> PowerFlowAtlasPatch | None:
        """Return one patch when the index is valid.

        :param patch_index: Zero-based patch position.
        :return: Patch reference or ``None`` when the index is invalid.
        """
        patch: PowerFlowAtlasPatch | None
        if 0 <= patch_index < len(self._patches):
            patch = self._patches[patch_index]
        else:
            patch = None
        return patch


class AtlasPatchBuildResult:
    """Explicit result wrapper used while building one atlas patch."""

    __slots__ = ("_status", "_patch", "_message")

    def __init__(
        self,
        status: AtlasBuildStatus,
        patch: PowerFlowAtlasPatch | None,
        message: str,
    ) -> None:
        """Create a patch-build result.

        :param status: Build status.
        :param patch: Constructed patch when successful.
        :param message: Human-readable diagnostic.
        """
        self._status: AtlasBuildStatus = status
        self._patch: PowerFlowAtlasPatch | None = patch
        self._message: str = message

    def get_status(self) -> AtlasBuildStatus:
        """Return the patch-build status."""
        return self._status

    def get_patch(self) -> PowerFlowAtlasPatch | None:
        """Return the patch when construction succeeded."""
        return self._patch

    def get_message(self) -> str:
        """Return the build diagnostic."""
        return self._message


class DirectionalSeriesResult:
    """Result of generating and evaluating one query-direction series."""

    __slots__ = (
        "_successful",
        "_message",
        "_voltage_coefficients",
        "_voltage",
        "_normalized_distance",
        "_pade_safe",
    )

    def __init__(
        self,
        successful: bool,
        message: str,
        voltage_coefficients: np.ndarray,
        voltage: np.ndarray,
        normalized_distance: float,
        pade_safe: bool,
    ) -> None:
        """Create a directional-series result.

        :param successful: Whether coefficient generation completed.
        :param message: Human-readable diagnostic.
        :param voltage_coefficients: Per-order, per-bus complex coefficients.
        :param voltage: Evaluated complex bus-voltage estimate.
        :param normalized_distance: First-order state displacement metric.
        :param pade_safe: Whether all requested Padé evaluations were safe.
        """
        self._successful: bool = successful
        self._message: str = message
        self._voltage_coefficients: np.ndarray = voltage_coefficients
        self._voltage: np.ndarray = voltage
        self._normalized_distance: float = normalized_distance
        self._pade_safe: bool = pade_safe

    def is_successful(self) -> bool:
        """Return whether coefficient generation completed."""
        return self._successful

    def get_message(self) -> str:
        """Return the directional-series diagnostic."""
        return self._message

    def get_voltage_coefficients(self) -> np.ndarray:
        """Return a copy of the per-order, per-bus coefficients."""
        return self._voltage_coefficients.copy()

    def get_voltage(self) -> np.ndarray:
        """Return a copy of the evaluated voltage estimate."""
        return self._voltage.copy()

    def get_normalized_distance(self) -> float:
        """Return the first-order normalized state displacement."""
        return self._normalized_distance

    def is_pade_safe(self) -> bool:
        """Return whether every requested Padé evaluation was safe."""
        return self._pade_safe


class FixedRegimeResidual:
    """Exact classical AC residual and regime checks for one voltage vector."""

    __slots__ = (
        "_mismatch",
        "_norm",
        "_calculated_power",
        "_reactive_limits_valid",
    )

    def __init__(
        self,
        mismatch: np.ndarray,
        norm: float,
        calculated_power: np.ndarray,
        reactive_limits_valid: bool,
    ) -> None:
        """Create a fixed-regime residual result.

        :param mismatch: Ordered fixed-regime mismatch vector.
        :param norm: Infinity norm of the mismatch vector.
        :param calculated_power: Calculated nodal complex powers in p.u.
        :param reactive_limits_valid: Whether PV reactive outputs remain valid.
        """
        self._mismatch: np.ndarray = mismatch
        self._norm: float = norm
        self._calculated_power: np.ndarray = calculated_power
        self._reactive_limits_valid: bool = reactive_limits_valid

    def get_mismatch(self) -> np.ndarray:
        """Return a copy of the ordered mismatch vector."""
        return self._mismatch.copy()

    def get_norm(self) -> float:
        """Return the mismatch infinity norm."""
        return self._norm

    def get_calculated_power(self) -> np.ndarray:
        """Return a copy of the calculated nodal complex powers."""
        return self._calculated_power.copy()

    def are_reactive_limits_valid(self) -> bool:
        """Return whether the fixed PV regime respects reactive limits."""
        return self._reactive_limits_valid


class AtlasBuildResult:
    """Explicit result wrapper used while finalizing a complete atlas."""

    __slots__ = ("_status", "_atlas", "_message")

    def __init__(
        self,
        status: AtlasBuildStatus,
        atlas: PowerFlowAtlas | None,
        message: str,
    ) -> None:
        """Create an atlas-build result.

        :param status: Build status.
        :param atlas: Finalized atlas when successful.
        :param message: Human-readable diagnostic.
        """
        self._status: AtlasBuildStatus = status
        self._atlas: PowerFlowAtlas | None = atlas
        self._message: str = message

    def get_status(self) -> AtlasBuildStatus:
        """Return the atlas-build status."""
        return self._status

    def get_atlas(self) -> PowerFlowAtlas | None:
        """Return the finalized atlas when construction succeeded."""
        return self._atlas

    def get_message(self) -> str:
        """Return the atlas-build diagnostic."""
        return self._message


class PatchSelectionResult:
    """Result of selecting the nearest local chart for one query."""

    __slots__ = ("_found", "_patch_index", "_normalized_distance", "_message")

    def __init__(
        self,
        found: bool,
        patch_index: int,
        normalized_distance: float,
        message: str,
    ) -> None:
        """Create a patch-selection result.

        :param found: Whether a compatible patch was found.
        :param patch_index: Selected zero-based patch position.
        :param normalized_distance: Predicted first-order state displacement.
        :param message: Human-readable diagnostic.
        """
        self._found: bool = found
        self._patch_index: int = patch_index
        self._normalized_distance: float = normalized_distance
        self._message: str = message

    def is_found(self) -> bool:
        """Return whether a compatible patch was found."""
        return self._found

    def get_patch_index(self) -> int:
        """Return the selected zero-based patch position."""
        return self._patch_index

    def get_normalized_distance(self) -> float:
        """Return the predicted first-order state displacement."""
        return self._normalized_distance

    def get_message(self) -> str:
        """Return the patch-selection diagnostic."""
        return self._message


class AtlasStorageResult:
    """Explicit save/load result for an atlas artifact."""

    __slots__ = ("_status", "_atlas", "_message")

    def __init__(
        self,
        status: AtlasStorageStatus,
        atlas: PowerFlowAtlas | None,
        message: str,
    ) -> None:
        """Create an atlas storage result.

        :param status: Atlas-storage status enum.
        :param atlas: Loaded atlas when available.
        :param message: Human-readable storage diagnostic.
        """
        self._status: AtlasStorageStatus = status
        self._atlas: PowerFlowAtlas | None = atlas
        self._message: str = message

    def get_status(self) -> AtlasStorageStatus:
        """Return the atlas-storage status enum."""
        return self._status

    def get_atlas(self) -> PowerFlowAtlas | None:
        """Return the loaded atlas when available."""
        return self._atlas

    def get_message(self) -> str:
        """Return the storage diagnostic."""
        return self._message
