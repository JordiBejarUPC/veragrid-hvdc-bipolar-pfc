# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.001--.0-
from __future__ import annotations

from typing import List

from PySide6 import QtCore, QtGui, QtWidgets

from VeraGridEngine.enumerations import VarPowerFlowReferenceType


class DeviceSelectionLabel(QtWidgets.QLabel):
    """Label that requests device selection through pointer or keyboard input."""

    __slots__ = ()

    clicked = QtCore.Signal()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Emit the selection request for a left-button click.

        :param event: Incoming label mouse event.
        :return: None.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            QtWidgets.QLabel.mousePressEvent(self, event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Emit the selection request for Enter, Return or Space.

        :param event: Incoming label key event.
        :return: None.
        """
        selection_keys: tuple[QtCore.Qt.Key, ...] = (
            QtCore.Qt.Key.Key_Enter,
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Space,
        )
        if event.key() in selection_keys:
            self.clicked.emit()
            event.accept()
        else:
            QtWidgets.QLabel.keyPressEvent(self, event)


class MeasurementReferenceList(QtWidgets.QListWidget):
    """One direction list that accepts dragged measurement references."""

    __slots__ = ("_target_direction",)

    moveRequested = QtCore.Signal(object, int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """Create one input or output reference list.

        :param parent: Optional owning widget.
        :return: None.
        """
        super().__init__(parent)
        self._target_direction: int = 0
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

    def set_target_direction(self, target_direction: int) -> None:
        """Set the direction emitted when an item is dropped on this list.

        :param target_direction: Zero for inputs or one for outputs.
        :return: None.
        """
        self._target_direction = target_direction

    def startDrag(self, supported_actions: QtCore.Qt.DropAction) -> None:
        """Start a drag carrying one typed measurement reference.

        :param supported_actions: Actions accepted by the initiating view.
        :return: None.
        """
        selected_items: List[QtWidgets.QListWidgetItem] = self.selectedItems()
        if len(selected_items) == 1:
            selected_item: QtWidgets.QListWidgetItem = selected_items[0]
            reference_data: object = selected_item.data(QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(reference_data, VarPowerFlowReferenceType):
                mime_data: QtCore.QMimeData = QtCore.QMimeData()
                mime_data.setText(reference_data.name)
                drag: QtGui.QDrag = QtGui.QDrag(self)
                drag.setMimeData(mime_data)
                drag.exec(QtCore.Qt.DropAction.MoveAction)
            else:
                pass
        else:
            pass

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        """Accept drags containing one measurement-reference name.

        :param event: Incoming drag event.
        :return: None.
        """
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        """Keep a valid measurement drag active over this direction list.

        :param event: Incoming drag-move event.
        :return: None.
        """
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        """Request moving the dropped reference into this list's direction.

        :param event: Incoming drop event.
        :return: None.
        """
        reference_name: str = event.mimeData().text()
        if reference_name in VarPowerFlowReferenceType.__members__:
            reference: VarPowerFlowReferenceType = VarPowerFlowReferenceType[reference_name]
            self.moveRequested.emit(reference, self._target_direction)
            event.acceptProposedAction()
        else:
            event.ignore()
