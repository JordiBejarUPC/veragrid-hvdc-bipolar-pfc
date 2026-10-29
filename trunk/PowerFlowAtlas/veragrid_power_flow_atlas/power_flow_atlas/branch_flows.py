from __future__ import annotations

import numpy as np
from scipy.sparse import csc_matrix

from power_flow_atlas.model import PowerFlowAtlas


class AtlasBranchFlowResult:
    """Calculated terminal currents and powers for the stored branch model."""

    __slots__ = (
        "_successful",
        "_message",
        "_from_current_pu",
        "_to_current_pu",
        "_from_power_mva",
        "_to_power_mva",
        "_losses_mva",
    )

    def __init__(
        self,
        successful: bool,
        message: str,
        from_current_pu: np.ndarray,
        to_current_pu: np.ndarray,
        from_power_mva: np.ndarray,
        to_power_mva: np.ndarray,
        losses_mva: np.ndarray,
    ) -> None:
        """Create a branch-flow calculation result.

        :param successful: Whether all terminal quantities were calculated.
        :param message: Human-readable diagnostic.
        :param from_current_pu: From-terminal branch currents in p.u.
        :param to_current_pu: To-terminal branch currents in p.u.
        :param from_power_mva: From-terminal complex powers in MVA.
        :param to_power_mva: To-terminal complex powers in MVA.
        :param losses_mva: Sum of terminal powers for each branch in MVA.
        """
        self._successful: bool = successful
        self._message: str = message
        self._from_current_pu: np.ndarray = from_current_pu.copy()
        self._to_current_pu: np.ndarray = to_current_pu.copy()
        self._from_power_mva: np.ndarray = from_power_mva.copy()
        self._to_power_mva: np.ndarray = to_power_mva.copy()
        self._losses_mva: np.ndarray = losses_mva.copy()

    def is_successful(self) -> bool:
        """Return whether all terminal quantities were calculated."""
        return self._successful

    def get_message(self) -> str:
        """Return the branch-flow calculation diagnostic."""
        return self._message

    def get_from_current_pu(self) -> np.ndarray:
        """Return a copy of the from-terminal currents in p.u."""
        return self._from_current_pu.copy()

    def get_to_current_pu(self) -> np.ndarray:
        """Return a copy of the to-terminal currents in p.u."""
        return self._to_current_pu.copy()

    def get_from_power_mva(self) -> np.ndarray:
        """Return a copy of the from-terminal powers in MVA."""
        return self._from_power_mva.copy()

    def get_to_power_mva(self) -> np.ndarray:
        """Return a copy of the to-terminal powers in MVA."""
        return self._to_power_mva.copy()

    def get_losses_mva(self) -> np.ndarray:
        """Return a copy of the branch complex losses in MVA."""
        return self._losses_mva.copy()


def calculate_branch_flows(
    atlas: PowerFlowAtlas,
    voltage: np.ndarray,
) -> AtlasBranchFlowResult:
    """Calculate exact branch terminal quantities from an atlas voltage.

    This operation is algebraic rather than approximate. The atlas voltage is
    multiplied by the exact compiled VeraGrid terminal admittance matrices, so
    line and transformer flows remain consistent with the represented network.

    :param atlas: Atlas containing the compiled terminal branch model.
    :param voltage: Complex bus-voltage vector in p.u.
    :return: Explicit branch-flow result.
    """
    empty_complex: np.ndarray = np.empty(0, dtype=np.complex128)
    voltage_vector: np.ndarray = np.asarray(voltage, dtype=np.complex128).reshape(-1)
    voltage_valid: bool = bool(
        voltage_vector.size == atlas.get_bus_count()
        and np.all(np.isfinite(voltage_vector))
    )
    result: AtlasBranchFlowResult

    if voltage_valid and atlas.has_branch_model():
        y_from: csc_matrix | None = atlas.get_y_from()
        y_to: csc_matrix | None = atlas.get_y_to()
        branch_from_indices: np.ndarray | None = atlas.get_branch_from_indices()
        branch_to_indices: np.ndarray | None = atlas.get_branch_to_indices()
        branch_data_available: bool = bool(
            y_from is not None
            and y_to is not None
            and branch_from_indices is not None
            and branch_to_indices is not None
        )
        if branch_data_available:
            branch_count: int = int(branch_from_indices.size)
            branch_data_valid: bool = bool(
                branch_to_indices.size == branch_count
                and y_from.shape == (branch_count, atlas.get_bus_count())
                and y_to.shape == (branch_count, atlas.get_bus_count())
                and np.all(branch_from_indices >= 0)
                and np.all(branch_to_indices >= 0)
                and np.all(branch_from_indices < atlas.get_bus_count())
                and np.all(branch_to_indices < atlas.get_bus_count())
            )
            if branch_data_valid:
                from_current_pu: np.ndarray = np.asarray(
                    y_from @ voltage_vector,
                    dtype=np.complex128,
                ).reshape(-1)
                to_current_pu: np.ndarray = np.asarray(
                    y_to @ voltage_vector,
                    dtype=np.complex128,
                ).reshape(-1)
                system_base_power: float = atlas.get_system_base_power()
                from_power_mva: np.ndarray = (
                    voltage_vector[branch_from_indices]
                    * np.conj(from_current_pu)
                    * system_base_power
                )
                to_power_mva: np.ndarray = (
                    voltage_vector[branch_to_indices]
                    * np.conj(to_current_pu)
                    * system_base_power
                )
                losses_mva: np.ndarray = from_power_mva + to_power_mva
                result = AtlasBranchFlowResult(
                    successful=True,
                    message="Branch terminal quantities calculated",
                    from_current_pu=from_current_pu,
                    to_current_pu=to_current_pu,
                    from_power_mva=from_power_mva,
                    to_power_mva=to_power_mva,
                    losses_mva=losses_mva,
                )
            else:
                result = AtlasBranchFlowResult(
                    successful=False,
                    message="Stored branch model has incompatible dimensions or indices",
                    from_current_pu=empty_complex,
                    to_current_pu=empty_complex,
                    from_power_mva=empty_complex,
                    to_power_mva=empty_complex,
                    losses_mva=empty_complex,
                )
        else:
            result = AtlasBranchFlowResult(
                successful=False,
                message="Stored branch model is incomplete",
                from_current_pu=empty_complex,
                to_current_pu=empty_complex,
                from_power_mva=empty_complex,
                to_power_mva=empty_complex,
                losses_mva=empty_complex,
            )
    else:
        if voltage_valid:
            message: str = "Atlas does not contain terminal branch matrices"
        else:
            message = "Voltage vector has an incompatible size or invalid values"
        result = AtlasBranchFlowResult(
            successful=False,
            message=message,
            from_current_pu=empty_complex,
            to_current_pu=empty_complex,
            from_power_mva=empty_complex,
            to_power_mva=empty_complex,
            losses_mva=empty_complex,
        )
    return result
