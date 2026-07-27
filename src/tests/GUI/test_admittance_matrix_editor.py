from __future__ import annotations

import numpy as np
from PySide6 import QtCore

from VeraGrid.Gui.DeviceEditors.TemplateDeviceEditor.admittance_matrix_editor import (
    AdmittanceMatrixTableModel,
    project_admittance_matrix_to_phase_state,
)
from VeraGridEngine.Devices.admittance_matrix import AdmittanceMatrix


def _build_demo_admittance_matrix() -> AdmittanceMatrix:
    """
    Build one three-phase admittance matrix for editor tests.

    :return: Configured admittance matrix.
    """
    admittance_matrix: AdmittanceMatrix = AdmittanceMatrix(size=3)
    admittance_matrix.phN = False
    admittance_matrix.phA = True
    admittance_matrix.phB = True
    admittance_matrix.phC = True
    admittance_matrix.values = np.array(
        [
            [1.0 + 2.0j, 3.0 + 4.0j, 5.0 + 6.0j],
            [7.0 + 8.0j, 9.0 + 10.0j, 11.0 + 12.0j],
            [13.0 + 14.0j, 15.0 + 16.0j, 17.0 + 18.0j],
        ],
        dtype=complex,
    )
    return admittance_matrix


def test_admittance_matrix_model_preserves_surviving_entries() -> None:
    """
    Verify that toggling phases resizes the matrix without scrambling matching rows and columns.
    """
    app: QtCore.QCoreApplication | None = QtCore.QCoreApplication.instance()
    if app is None:
        app = QtCore.QCoreApplication([])
    else:
        pass

    model: AdmittanceMatrixTableModel = AdmittanceMatrixTableModel(
        admittance_matrix=_build_demo_admittance_matrix(),
    )

    model.set_phase_enabled("B", False)
    reduced_matrix: AdmittanceMatrix = model.to_admittance_matrix()

    assert reduced_matrix.size == 2
    assert reduced_matrix.phA is True
    assert reduced_matrix.phB is False
    assert reduced_matrix.phC is True
    assert reduced_matrix.values[0, 0] == 1.0 + 2.0j
    assert reduced_matrix.values[0, 1] == 5.0 + 6.0j
    assert reduced_matrix.values[1, 0] == 13.0 + 14.0j
    assert reduced_matrix.values[1, 1] == 17.0 + 18.0j

    model.set_phase_enabled("N", True)
    expanded_matrix: AdmittanceMatrix = model.to_admittance_matrix()

    assert expanded_matrix.size == 3
    assert expanded_matrix.phN is True
    assert expanded_matrix.phA is True
    assert expanded_matrix.phB is False
    assert expanded_matrix.phC is True
    assert expanded_matrix.values[1, 1] == 1.0 + 2.0j
    assert expanded_matrix.values[1, 2] == 5.0 + 6.0j
    assert expanded_matrix.values[2, 1] == 13.0 + 14.0j
    assert expanded_matrix.values[2, 2] == 17.0 + 18.0j
    assert expanded_matrix.values[0, 0] == 0.0 + 0.0j


def test_project_admittance_matrix_to_phase_state_keeps_selected_abc_subset() -> None:
    """
    Verify that projecting a full ABC matrix to an ABC subset preserves the expected entries.
    """
    source_matrix: AdmittanceMatrix = AdmittanceMatrix(size=4)
    source_matrix.phN = False
    source_matrix.phA = True
    source_matrix.phB = True
    source_matrix.phC = True
    source_matrix.values = np.array(
        [
            [0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j],
            [0.0 + 0.0j, 1.0 + 1.0j, 2.0 + 2.0j, 3.0 + 3.0j],
            [0.0 + 0.0j, 4.0 + 4.0j, 5.0 + 5.0j, 6.0 + 6.0j],
            [0.0 + 0.0j, 7.0 + 7.0j, 8.0 + 8.0j, 9.0 + 9.0j],
        ],
        dtype=complex,
    )

    projected_matrix: AdmittanceMatrix = project_admittance_matrix_to_phase_state(
        admittance_matrix=source_matrix,
        phase_state={"N": False, "A": True, "B": False, "C": True},
    )

    assert projected_matrix.size == 2
    assert projected_matrix.phN is False
    assert projected_matrix.phA is True
    assert projected_matrix.phB is False
    assert projected_matrix.phC is True
    assert projected_matrix.values[0, 0] == 1.0 + 1.0j
    assert projected_matrix.values[0, 1] == 3.0 + 3.0j
    assert projected_matrix.values[1, 0] == 7.0 + 7.0j
    assert projected_matrix.values[1, 1] == 9.0 + 9.0j
