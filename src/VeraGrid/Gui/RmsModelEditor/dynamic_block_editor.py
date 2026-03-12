# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import uuid
import copy
from enum import Enum
from typing import List, Dict, Optional, Any
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QGraphicsScene, QGraphicsView, QGraphicsItem,
                               QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QMenu, QGraphicsPathItem,
                               QDialog, QVBoxLayout, QDialogButtonBox, QSplitter, QLabel, QDoubleSpinBox,
                               QListView, QAbstractItemView, QPushButton, QListWidget, QWidget,
                               QListWidgetItem, QFormLayout, QSpinBox, QLineEdit, QTableWidget, QTableWidgetItem,
                               QColorDialog, QCheckBox)
from PySide6.QtGui import (QPen, QBrush, QPainterPath, QAction, QPainter, QIcon, QStandardItemModel, QStandardItem,
                           QDropEvent, QDragEnterEvent, QDragMoveEvent, QColor)
from PySide6.QtCore import Qt, QPointF, QByteArray, QDataStream, QIODevice, QModelIndex, QMimeData, Signal

from VeraGridEngine import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGrid.Gui.RmsModelEditor.block_editor import Ui_BlockEditorWindow
from VeraGridEngine.Utils.Symbolic.symbolic import symbolic_to_string, Expr, Var, Const
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagram
from VeraGridEngine.enumerations import BlockType
from VeraGridEngine.Templates.Rms.common import create_block_of_type

BLOCK_BORDER: QColor = QColor("#36536b")
BLOCK_BORDER_SELECTED: QColor = QColor("#cc6f2c")
BLOCK_TITLE: QColor = QColor("#173042")
BLOCK_SHADOW: QColor = QColor(24, 42, 56, 45)
INPUT_PORT_FILL: QColor = QColor("#2d7dd2")
OUTPUT_PORT_FILL: QColor = QColor("#2a9d6f")
PORT_BORDER: QColor = QColor("#173042")
WIRE_COLOR: QColor = QColor("#587291")
WIRE_HOVER_COLOR: QColor = QColor("#cc6f2c")
HANDLE_FILL: QColor = QColor("#36536b")
DEFAULT_BLOCK_FILL: QColor = QColor("#d9e7f5")


def _new_uid() -> int:
    """
    Generate a fresh integer identifier.

    :return:
    """
    return uuid.uuid4().int


def clone_block_for_editing(block: Block) -> Block:
    """
    Build an isolated editable copy of a block, including its diagram.

    :param block:
    :return:
    """
    editable_block: Block = block.copy()
    editable_block.diagram = block.diagram.copy()
    return editable_block


def copy_block_state(source_block: Block, target_block: Block) -> None:
    """
    Copy the complete edited block state back into the original block instance.

    :param source_block:
    :param target_block:
    :return:
    """
    source_clone: Block = clone_block_for_editing(source_block)

    # The original object identity must be preserved for external references in the GUI and device model.
    target_block.name = source_clone.name
    target_block.uid = source_clone.uid
    target_block.vars_glob_name2uid = source_clone.vars_glob_name2uid
    target_block.state_vars = source_clone.state_vars
    target_block.state_eqs = source_clone.state_eqs
    target_block.algebraic_vars = source_clone.algebraic_vars
    target_block.algebraic_eqs = source_clone.algebraic_eqs
    target_block.diff_vars = source_clone.diff_vars
    target_block.reformulated_vars = source_clone.reformulated_vars
    target_block.differential_eqs = source_clone.differential_eqs
    target_block.init_eqs = source_clone.init_eqs
    target_block.diff_init_eqs = source_clone.diff_init_eqs
    target_block.children = source_clone.children
    target_block.in_vars = source_clone.in_vars
    target_block.out_vars = source_clone.out_vars
    target_block.parameters = source_clone.parameters
    target_block.alter_params = source_clone.alter_params
    target_block.discrete_eqs = source_clone.discrete_eqs
    target_block.external_mapping = source_clone.external_mapping
    target_block.api_obj_mapping = source_clone.api_obj_mapping
    target_block.init_values = source_clone.init_values
    target_block.var_mapping = source_clone.var_mapping
    target_block.event_dict = source_clone.event_dict
    target_block.mode_dict = source_clone.mode_dict
    target_block.diagram = source_clone.diagram


class ResizeHandle(QGraphicsRectItem):
    """
    Interactive resize handle attached to a block item.
    """

    def __init__(self, block_item: "BlockItem", size: int = 10):
        """
        Build the resize handle.

        :param block_item:
        :param size:
        """
        super().__init__(0, 0, size, size, block_item)
        self.setBrush(QBrush(HANDLE_FILL))
        self.setPen(QPen(QColor("#ffffff"), 1))
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setZValue(2)
        self.block: BlockItem = block_item
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.setAcceptHoverEvents(True)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """
        Propagate handle movement into block resizing.

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self.block.resizing_from_handle:
                new_pos: QPointF = value
                min_width: int = 40
                min_height: int = 30
                new_width: float = max(new_pos.x(), min_width)
                new_height: float = max(new_pos.y(), min_height)

                # The block geometry must be updated from the handle movement.
                self.block.resize_block(new_width, new_height)
                return QPointF(new_width, new_height)
            else:
                return super().itemChange(change, value)
        else:
            return super().itemChange(change, value)


class PortItem(QGraphicsEllipseItem):
    """
    Graphical input or output port attached to a block item.
    """

    def __init__(self,
                 subsystem: "BlockItem",
                 is_input: bool,
                 index: int,
                 total: int,
                 radius: int = 6):
        """
        Build a block port.

        :param subsystem:
        :param is_input:
        :param index:
        :param total:
        :param radius:
        """
        super().__init__(-radius, -radius, 2 * radius, 2 * radius, subsystem)
        fill_color: QColor = INPUT_PORT_FILL if is_input else OUTPUT_PORT_FILL
        self.setBrush(QBrush(fill_color))
        self.setPen(QPen(PORT_BORDER, 1.5))
        self.setZValue(3)
        self.setAcceptHoverEvents(True)
        self.subsystem: BlockItem = subsystem
        self.is_input: bool = is_input
        self.connections: List["ConnectionItem"] | None = None
        self.index: int = index
        self.total: int = total

        spacing: float = subsystem.rect().height() / (total + 1)
        y_pos: float = spacing * (index + 1)
        x_pos: float = 0 if is_input else subsystem.rect().width()
        self.setPos(x_pos, y_pos)

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Show a pointer cursor over the port.

        :param event:
        :return:
        """
        QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Restore the cursor when the pointer leaves the port.

        :param event:
        :return:
        """
        QApplication.restoreOverrideCursor()

    def is_connected(self) -> bool:
        """
        Check whether the port already owns a connection list.

        :return:
        """
        if self.connections is not None:
            return True
        else:
            return False


class ConnectionItem(QGraphicsPathItem):
    """
    Curved graphical connection between two ports.
    """

    def __init__(self, source_port: PortItem, target_port: PortItem):
        """
        Build the connection item.

        :param source_port:
        :param target_port:
        """
        super().__init__()
        self.uid: int = _new_uid()
        self.setZValue(-1)
        self.source_port: PortItem = source_port
        self.target_port: PortItem = target_port
        if self.source_port.connections is None:
            self.source_port.connections = list()
        else:
            pass
        self.source_port.connections.append(self)

        if self.target_port.connections is None:
            self.target_port.connections = list()
        else:
            pass
        self.target_port.connections.append(self)
        self.setPen(QPen(WIRE_COLOR, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        self.setAcceptHoverEvents(True)

        self.update_path()

    def update_path(self) -> None:
        """
        Recompute the bezier path from current port positions.

        :return:
        """
        start: QPointF = self.source_port.scenePos()
        end: QPointF = self.target_port.scenePos()
        mid_x: float = (start.x() + end.x()) / 2
        control_1: QPointF = QPointF(mid_x, start.y())
        control_2: QPointF = QPointF(mid_x, end.y())
        path: QPainterPath = QPainterPath(start)
        path.cubicTo(control_1, control_2, end)
        self.setPath(path)

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Show a pointer cursor over the connection.

        :param event:
        :return:
        """
        QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)
        pen: QPen = self.pen()
        pen.setColor(WIRE_HOVER_COLOR)
        pen.setWidthF(3.5)
        self.setPen(pen)

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Restore the cursor when the pointer leaves the connection.

        :param event:
        :return:
        """
        QApplication.restoreOverrideCursor()
        pen: QPen = self.pen()
        pen.setColor(WIRE_COLOR)
        pen.setWidthF(2.5)
        self.setPen(pen)


class ParameterEditorDialog(QDialog):
    """
    Dialog to edit event parameters and fixed parameters of a block.
    """

    parametersUpdated = Signal(dict)

    def __init__(self,
                 var_factory: VarFactory,
                 event_dict: Dict[Var, Expr],
                 parameters_dict: Dict[Var, Const],
                 parent: Optional[QtWidgets.QWidget] = None):
        """
        Build the parameter editor dialog.

        :param var_factory:
        :param event_dict:
        :param parameters_dict:
        :param parent:
        """
        super().__init__(parent)

        self.setWindowTitle("Edit Model Parameters")
        self.resize(450, 350)

        self.var_factory: VarFactory = var_factory
        self.event_dict: Dict[Var, Expr] = copy.deepcopy(event_dict)
        self.parameters: Dict[Var, Const] = copy.deepcopy(parameters_dict)
        self._vars_order: List[Var] = list()

        layout: QVBoxLayout = QVBoxLayout(self)
        layout.addWidget(QLabel("Edit the values:"))

        self.params_table: QTableWidget = QTableWidget(self)
        self.params_table.setColumnCount(2)
        self.params_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.params_table.horizontalHeader().setStretchLastSection(True)
        self.params_table.verticalHeader().setVisible(False)
        self.params_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.AllEditTriggers)
        layout.addWidget(self.params_table)

        buttons: QDialogButtonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load_params_table()
        self.load_fix_params_table()
        self.params_table.cellChanged.connect(self.on_cell_changed)

    def load_params_table(self) -> None:
        """
        Load editable event parameters into the table.

        :return:
        """
        var: Var
        expr: Expr

        self.params_table.blockSignals(True)

        for var, expr in self.event_dict.items():
            row: int = self.params_table.rowCount()
            self.params_table.insertRow(row)
            self._vars_order.append(var)

            name_item: QTableWidgetItem = QTableWidgetItem(var.name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.params_table.setItem(row, 0, name_item)

            if hasattr(expr, "value"):
                value_item: QTableWidgetItem = QTableWidgetItem(str(expr.value))
                value_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
            else:
                value_item = QTableWidgetItem(str(expr))
                value_item.setFlags(Qt.ItemFlag.ItemIsEnabled)

            self.params_table.setItem(row, 1, value_item)

        self.params_table.blockSignals(False)
        self.params_table.resizeColumnsToContents()

    def load_fix_params_table(self) -> None:
        """
        Load fixed parameters into the table.

        :return:
        """
        var: Var
        const: Const

        self.params_table.blockSignals(True)

        for var, const in self.parameters.items():
            row: int = self.params_table.rowCount()
            self.params_table.insertRow(row)

            name_item: QTableWidgetItem = QTableWidgetItem(var.name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.params_table.setItem(row, 0, name_item)

            value: str = "" if const.value is None else str(const.value)
            value_item: QTableWidgetItem = QTableWidgetItem(value)
            value_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.params_table.setItem(row, 1, value_item)

        self.params_table.blockSignals(False)
        self.params_table.resizeColumnsToContents()

    def on_cell_changed(self, row: int, column: int) -> None:
        """
        Update the event dictionary after user edits.

        :param row:
        :param column:
        :return:
        """
        if column == 1:
            if row < len(self._vars_order):
                var: Var = self._vars_order[row]
                item: QTableWidgetItem | None = self.params_table.item(row, 1)

                if item is not None:
                    text: str = item.text()

                    try:
                        value: float | str = float(text)
                    except ValueError:
                        value = text

                    self.event_dict[var] = self.var_factory.add_const(value=value, name=var.name)
                    self.parametersUpdated.emit(self.event_dict)
                else:
                    pass
            else:
                pass
        else:
            pass


class BlockItem(QGraphicsRectItem):
    """
    Graphics item representing a symbolic block.
    """

    def __init__(self, var_factory: VarFactory, name: str):
        """
        Build the graphical block item.

        :param var_factory:
        :param name:
        """
        super().__init__(0, 0, 100, 60)

        self.var_factory: VarFactory = var_factory
        self.name: str = name
        self.resize_handle: ResizeHandle | None = None
        self.resizing_from_handle: bool = False
        self.subsys: Block | None = None
        self.name_item: QGraphicsTextItem | None = None
        self.inputs: List[PortItem] = list()
        self.outputs: List[PortItem] = list()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
        )
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(Qt.GlobalColor.transparent, 0))
        self.setBrush(QBrush(DEFAULT_BLOCK_FILL))

    def set_subsystem(self, block: Block) -> None:
        """
        Attach the symbolic block to the graphics item.

        :param block:
        :return:
        """
        self.subsys = block

    def build_item(self) -> None:
        """
        Build the label, ports, and resize handle from the symbolic block.

        :return:
        """
        if self.subsys is not None:
            self.name_item = QGraphicsTextItem(self.name, self)
            self.name_item.setDefaultTextColor(BLOCK_TITLE)
            name_font: QtGui.QFont = QtGui.QFont("DejaVu Sans", 10)
            name_font.setBold(True)
            self.name_item.setFont(name_font)
            self.name_item.setPos(12, 9)

            n_inputs: int = len(self.subsys.in_vars)
            n_outputs: int = len(self.subsys.out_vars)

            self.inputs = [PortItem(self, True, i, n_inputs) for i in range(n_inputs)]
            self.outputs = [PortItem(self, False, i, n_outputs) for i in range(n_outputs)]

            # Each port tooltip mirrors the symbolic variable so the editor state is inspectable.
            for i, port in enumerate(self.inputs):
                var_name: str = self.subsys.in_vars[i].name
                port.setToolTip(f"Input {i}: {var_name}")

            for i, port in enumerate(self.outputs):
                var_name = self.subsys.out_vars[i].name
                port.setToolTip(f"Output {i}: {var_name}")

            self.resize_handle = ResizeHandle(self)
            super().setRect(0, 0, 100, 60)
            self.update_ports()
            self.update_handle_position()
        else:
            pass

    def paint(self,
              painter: QPainter,
              option: QtWidgets.QStyleOptionGraphicsItem,
              widget: Optional[QWidget] = None) -> None:
        """
        Paint the block with a rounded card style and a subtle header band.

        :param painter:
        :param option:
        :param widget:
        :return:
        """
        rect: QtCore.QRectF = self.rect()
        outer_rect: QtCore.QRectF = rect.adjusted(2, 2, -2, -2)
        shadow_rect: QtCore.QRectF = outer_rect.translated(2.5, 3.0)
        body_rect: QtCore.QRectF = outer_rect
        border_color: QColor = BLOCK_BORDER_SELECTED if self.isSelected() else BLOCK_BORDER
        fill_color: QColor = self.brush().color()
        body_path: QPainterPath = QPainterPath()
        shadow_path: QPainterPath = QPainterPath()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        shadow_path.addRoundedRect(shadow_rect, 12.0, 12.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(BLOCK_SHADOW))
        painter.drawPath(shadow_path)

        body_path.addRoundedRect(body_rect, 12.0, 12.0)
        painter.setBrush(QBrush(fill_color))
        painter.drawPath(body_path)

        painter.setPen(QPen(border_color, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body_rect, 12.0, 12.0)

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Open the parameter editor for the current block.

        :param event:
        :return:
        """
        if self.subsys is not None:
            dialog: ParameterEditorDialog = ParameterEditorDialog(
                var_factory=self.var_factory,
                event_dict=self.subsys.event_dict,
                parameters_dict=self.subsys.parameters,
                parent=None
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.subsys.event_dict = dialog.event_dict
                self.subsys.parameters = dialog.parameters
            else:
                pass

            event.accept()
        else:
            pass

        super().mouseDoubleClickEvent(event)

    def resize_block(self, width: float, height: float) -> None:
        """
        Resize the block geometry and keep ports aligned.

        :param width:
        :param height:
        :return:
        """
        self.prepareGeometryChange()
        QGraphicsRectItem.setRect(self, 0, 0, width, height)
        self.update_ports()
        self.update_handle_position()

    def update_handle_position(self) -> None:
        """
        Keep the resize handle attached to the lower-right corner.

        :return:
        """
        rect = self.rect()

        if self.resize_handle is not None:
            self.resizing_from_handle = False
            self.resize_handle.setPos(rect.width(), rect.height())
            self.resizing_from_handle = True
        else:
            pass

    def update_ports(self) -> None:
        """
        Reposition ports after a size or position change.

        :return:
        """
        i: int
        port: PortItem

        for i, port in enumerate(self.inputs):
            spacing: float = self.rect().height() / (len(self.inputs) + 1)
            port.setPos(0, spacing * (i + 1))

        for i, port in enumerate(self.outputs):
            spacing = self.rect().height() / (len(self.outputs) + 1)
            port.setPos(self.rect().width(), spacing * (i + 1))

        self.update_handle_position()

        # Existing connections must be recomputed whenever port positions change.
        for port in self.inputs + self.outputs:
            if port.connections is not None:
                conn: ConnectionItem
                for conn in port.connections:
                    conn.update_path()
            else:
                pass

    def hoverEnterEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Show a hand cursor when hovering the block.

        :param event:
        :return:
        """
        QApplication.setOverrideCursor(Qt.CursorShape.OpenHandCursor)
        self.update()

    def hoverLeaveEvent(self, event: QtWidgets.QGraphicsSceneHoverEvent) -> None:
        """
        Restore the cursor when leaving the block.

        :param event:
        :return:
        """
        QApplication.restoreOverrideCursor()
        self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        """
        Update connection geometry when the block moves.

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            port: PortItem
            for port in self.inputs + self.outputs:
                if port.connections is not None:
                    conn: ConnectionItem
                    for conn in port.connections:
                        conn.update_path()
                else:
                    pass
            return super().itemChange(change, value)
        else:
            return super().itemChange(change, value)


class GraphicsView(QGraphicsView):
    """
    Graphics view with zoom and middle-button pan.
    """

    def __init__(self, scene: QGraphicsScene):
        """
        Build the graphics view.

        :param scene:
        """
        super().__init__(scene)
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)
        self._panning: bool = False
        self._pan_start: QPointF = QPointF()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """
        Apply wheel zoom around the mouse anchor.

        :param event:
        :return:
        """
        zoom_in: bool = event.angleDelta().y() > 0
        zoom_factor: float = 1.15 if zoom_in else 1 / 1.15
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Start panning on middle mouse press.

        :param event:
        :return:
        """
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            if event.button() == Qt.MouseButton.LeftButton and bool(
                    event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            else:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Move the viewport while panning.

        :param event:
        :return:
        """
        if self._panning:
            delta: QPointF = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Stop panning on middle mouse release.

        :param event:
        :return:
        """
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)
            self.setDragMode(QGraphicsView.DragMode.NoDrag)


class DiagramScene(QGraphicsScene):
    """
    Scene that manages interactive block connections.
    """

    def __init__(self, editor: "DynamicBlockEditorGUI"):
        """
        Build the scene wrapper around the editor state.

        :param editor:
        """
        super().__init__()
        self.editor: DynamicBlockEditorGUI = editor
        self.temp_line: QGraphicsPathItem | None = None
        self.source_port: PortItem | None = None
        self.context_item: BlockItem | ConnectionItem | None = None

    def change_item_fill_color(self, item: BlockItem | ConnectionItem) -> None:
        """
        Change the color of a block or connection and persist it in the diagram.

        :param item:
        :return:
        """
        new_color: QColor = QColorDialog.getColor()

        if new_color.isValid():
            if isinstance(item, BlockItem):
                if item.subsys is not None:
                    brush: QBrush = item.brush()
                    brush.setColor(new_color)
                    item.setBrush(brush)
                    self.update()

                    if item.subsys.uid in self.editor.diagram.node_data:
                        self.editor.diagram.node_data[item.subsys.uid].color = new_color.name()
                    else:
                        pass
                else:
                    pass
            elif isinstance(item, ConnectionItem):
                pen: QPen = item.pen()
                pen.setColor(new_color)
                item.setPen(pen)
                self.update()

                if item.uid in self.editor.diagram.con_data:
                    self.editor.diagram.con_data[item.uid].color = new_color.name()
                else:
                    pass
            else:
                pass
        else:
            pass

    def remove_context_item(self) -> None:
        """
        Remove the item currently selected by the scene context menu.

        :return:
        """
        if self.context_item is not None:
            self.editor.remove_item(self.context_item)
        else:
            pass

    def recolor_context_item(self) -> None:
        """
        Recolor the item currently selected by the scene context menu.

        :return:
        """
        if self.context_item is not None:
            self.change_item_fill_color(self.context_item)
        else:
            pass

    def contextMenuEvent(self, event: QtWidgets.QGraphicsSceneContextMenuEvent) -> None:
        """
        Show scene actions for blocks and connections.

        :param event:
        :return:
        """
        item: QGraphicsItem

        for item in self.items(event.scenePos()):
            if isinstance(item, (BlockItem, ConnectionItem)):
                menu: QMenu = QMenu()
                self.context_item = item

                remove_action: QAction = QAction("Remove", menu)
                remove_action.triggered.connect(self.remove_context_item)
                menu.addAction(remove_action)

                color_action: QAction = QAction("Change Color", menu)
                color_action.triggered.connect(self.recolor_context_item)
                menu.addAction(color_action)

                menu.exec(event.screenPos())
                self.context_item = None
                return
            else:
                pass

        super().contextMenuEvent(event)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Start a temporary connection when the user presses an output port.

        :param event:
        :return:
        """
        item: QGraphicsItem

        for item in self.items(event.scenePos()):
            if isinstance(item, PortItem):
                if not item.is_input:
                    self.source_port = item
                    path: QPainterPath = QPainterPath(item.scenePos())
                    self.temp_line = self.addPath(path, QPen(Qt.PenStyle.DashLine))
                    return
                else:
                    pass
            else:
                pass

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Update the temporary connection while dragging.

        :param event:
        :return:
        """
        if self.temp_line is not None:
            if self.source_port is not None:
                start: QPointF = self.source_port.scenePos()
                end: QPointF = event.scenePos()
                mid_x: float = (start.x() + end.x()) / 2
                control_1: QPointF = QPointF(mid_x, start.y())
                control_2: QPointF = QPointF(mid_x, end.y())
                path: QPainterPath = QPainterPath(start)
                path.cubicTo(control_1, control_2, end)
                self.temp_line.setPath(path)
            else:
                pass
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Finalize a connection if the cursor is released over a free input port.

        :param event:
        :return:
        """
        if self.temp_line is not None:
            if self.source_port is not None:
                item: QGraphicsItem

                for item in self.items(event.scenePos()):
                    if isinstance(item, PortItem):
                        if item.is_input and not item.is_connected():
                            self.connect_ports(self.source_port, item)
                            break
                        else:
                            pass
                    else:
                        pass
            else:
                pass

            self.removeItem(self.temp_line)
            self.temp_line = None
            self.source_port = None
        else:
            super().mouseReleaseEvent(event)

    def connect_ports(self, source_port: PortItem, target_port: PortItem) -> None:
        """
        Connect two ports and update the symbolic model.

        :param source_port:
        :param target_port:
        :return:
        """
        source_block: BlockItem = source_port.subsystem
        target_block: BlockItem = target_port.subsystem

        if source_block.subsys is not None and target_block.subsys is not None:
            connection: ConnectionItem = ConnectionItem(source_port, target_port)
            dst_var: Var = source_block.subsys.out_vars[source_port.index]
            target_input_var: Var = target_block.subsys.in_vars[target_port.index]
            # key: VarPowerFlowRefferenceType
            # value: Var | None

            # The destination model must substitute its local input placeholder with the source variable.
            target_block.subsys.update_model(target_input_var, dst_var)

            for key, value in self.editor.main_block.external_mapping.items():
                if value is target_input_var:
                    self.editor.main_block.external_mapping[key] = dst_var
                else:
                    pass

            target_block.subsys.in_vars[target_port.index] = dst_var
            self.addItem(connection)

            self.editor.diagram.add_branch(
                connectionitem_uid=connection.uid,
                device_uid_from=source_block.subsys.uid,
                device_uid_to=target_block.subsys.uid,
                port_number_from=source_port.index,
                port_number_to=target_port.index,
                color=connection.pen().color().name()
            )
        else:
            pass


class DynamicsLibraryTreeModel(QtGui.QStandardItemModel):
    __slots__ = ("_block_role", "_mime_type")

    def __init__(self, block_role: int, mime_type: str):
        """
        Build the library tree model

        :param block_role:
        :param mime_type:
        """
        super().__init__()
        self._block_role = block_role
        self._mime_type = mime_type

        self.setHorizontalHeaderLabels(["Models Library"])

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """
        Get the Qt flags for an item.

        :param index:
        """

        if index.isValid():

            item: QtGui.QStandardItem | None = self.itemFromIndex(index)
            if item is not None:
                item_data: object = item.data(self._block_role)
                if isinstance(item_data, BlockType):
                    return (QtCore.Qt.ItemFlag.ItemIsEnabled
                            | QtCore.Qt.ItemFlag.ItemIsSelectable
                            | QtCore.Qt.ItemFlag.ItemIsDragEnabled)
                else:
                    return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
            else:
                return QtCore.Qt.ItemFlag.ItemIsEnabled

        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def mimeTypes(self) -> List[str]:
        """
        Get the supported mime types.

        :return: Mime types exported by the model.
        """
        return [self._mime_type]

    def supportedDragActions(self) -> QtCore.Qt.DropAction:
        """
        Get the supported drag actions.

        :return: Copy action.
        """
        return QtCore.Qt.DropAction.CopyAction

    def mimeData(self, indexes: List[QtCore.QModelIndex]) -> QtCore.QMimeData:
        """
        Build mime data from the selected variable item.

        :param indexes: Selected indexes.
        :return: Mime payload containing the dragged variable uid.
        """
        mime_data: QtCore.QMimeData = QtCore.QMimeData()

        index: QtCore.QModelIndex
        for index in indexes:
            if index.isValid():
                item: QtGui.QStandardItem | None = self.itemFromIndex(index)
                if item is not None:
                    item_data: object = item.data(self._block_role)
                    if isinstance(item_data, BlockType):
                        mime_data.setData(self._mime_type, QtCore.QByteArray(item_data.name.encode("utf-8")))
                        return mime_data
                    else:
                        pass
                else:
                    pass
            else:
                pass

        return mime_data


class DynamicEditorMode(Enum):
    RMS = "rms",
    EMT = "emt",


class DynamicBlockEditorGUI(QtWidgets.QMainWindow):
    """
    RmsModelEditorGUI
    """

    def __init__(self,
                 var_factory: VarFactory,
                 block: Block,
                 templates_list: List[RmsModelTemplate],
                 api_object: ALL_DEV_TYPES | None = None,
                 mode: DynamicEditorMode = DynamicEditorMode.RMS,
                 main_editor=False):
        """

        :param block:
        :param templates_list:
        :param api_object:
        """
        super().__init__()

        self.ui = Ui_BlockEditorWindow()
        self.ui.setupUi(self)

        self.block_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 300
        self.mime_type: str = "application/x-veragrid-dynamics-block"

        self.setWindowTitle("Dynamic Model Editor")

        self.ui.splitter.setStretchFactor(0, 1)
        self.ui.splitter.setStretchFactor(1, 10)

        self.var_factory = var_factory
        self.original_block: Block = block
        self.block: Block = clone_block_for_editing(block)
        self.main_block: Block = self.block
        self.diagram: BlockDiagram = self.block.diagram
        self.templates_list = templates_list
        self.api_object = api_object
        self.main_editor = main_editor
        self.block_counters: Dict[BlockType, int] = dict()
        self.scene: DiagramScene = DiagramScene(self)
        self.changes_applied: bool = False

        if mode == DynamicEditorMode.RMS:
            self.tree_structure = {
                "Basic": [
                    ("Const", BlockType.CONST),
                    ("Gain", BlockType.GAIN),
                    ("Sum", BlockType.SUM),
                    ("Substr", BlockType.SUBSTR),
                    ("Product", BlockType.PRODUCT),
                    ("Divide", BlockType.DIVIDE),
                    ("Abs", BlockType.ABS),
                ],
                "Devices": [
                    ("Generator basic", BlockType.GENRAW),
                    ("Generator QEC", BlockType.GENQEC),
                    ("Governor", BlockType.GOV),
                    ("Stabilizer", BlockType.STAB),
                    ("Exciter", BlockType.EXCITER),
                    ("Line", BlockType.LINE),
                    ("Load", BlockType.LOAD),
                ]
            }
        elif mode == DynamicEditorMode.EMT:
            self.tree_structure = {}

        # build and add library model
        self.library_model = self.build_library_tree_model(
            block_role=self.block_role,
            mime_type=self.mime_type
        )

        self.ui.libraryTreeView.setModel(self.library_model)
        self.ui.libraryTreeView.expandAll()
        self.ui.libraryTreeView.setDragEnabled(True)
        self.ui.libraryTreeView.setHeaderHidden(False)

        self.view: GraphicsView = GraphicsView(self.scene)
        self.ui.verticalLayout_3.removeWidget(self.ui.graphicsView)
        self.ui.graphicsView.deleteLater()
        self.ui.graphicsView = self.view
        self.ui.verticalLayout_3.addWidget(self.ui.graphicsView)

        # The canvas scene owns the graphical block items dropped from the tree library.
        self.ui.graphicsView.setAcceptDrops(True)
        self.ui.graphicsView.viewport().setAcceptDrops(True)
        self.ui.graphicsView.dragEnterEvent = self.graphicsDragEnterEvent
        self.ui.graphicsView.dragMoveEvent = self.graphicsDragMoveEvent
        self.ui.graphicsView.dropEvent = self.graphicsDropEvent

        self.ui.doItButton.clicked.connect(self.apply_changes)
        self.rebuild_scene_from_diagram()

    def build_library_tree_model(self,
                                 block_role: int,
                                 mime_type: str) -> DynamicsLibraryTreeModel:
        """
        Build the source tree-view model for dynamic library.

        :param block_role:
        :type block_role:
        :param mime_type:
        :type mime_type:
        :return:
        :rtype:
        """

        model: DynamicsLibraryTreeModel = DynamicsLibraryTreeModel(block_role, mime_type)
        model.setHorizontalHeaderLabels(["Dynamic library"])
        root_item: QtGui.QStandardItem = model.invisibleRootItem()

        for category, blocks in self.tree_structure.items():
            cat_item: QtGui.QStandardItem = QtGui.QStandardItem(category)
            cat_item.setEditable(False)
            root_item.appendRow(cat_item)

            for label, block_type in blocks:
                item: QtGui.QStandardItem = QtGui.QStandardItem(label)
                item.setEditable(False)

                item.setData(block_type, block_role)
                cat_item.appendRow(item)

        return model

    def get_block_type_from_mime_data(self, mime_data: QtCore.QMimeData) -> BlockType | None:
        """
        Decode the dragged block type from the tree-view mime payload.

        :param mime_data:
        :return:
        """
        block_type_name: str
        block_type: BlockType

        if mime_data.hasFormat(self.mime_type):
            block_type_name = bytes(mime_data.data(self.mime_type)).decode("utf-8")

            for block_type in BlockType:
                if block_type.name == block_type_name:
                    return block_type
                else:
                    pass

            return None
        else:
            return None

    def create_block_item(self, block_type: BlockType, x_pos: float, y_pos: float) -> BlockItem | None:
        """
        Create and place a block item in the canvas scene.

        :param block_type:
        :param x_pos:
        :param y_pos:
        :return:
        """
        count: int = self.block_counters.get(block_type, 0) + 1
        item_name: str = f"{block_type.name}_{count}"
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
        block_model: Block | None = create_block_of_type(
            var_factory=self.var_factory,
            block_type=block_type,
            item_name=item_name
        )

        if block_model is not None:
            # The symbolic block has to be attached first so the graphics item can build its ports from it.
            self.block_counters[block_type] = count
            block_item.set_subsystem(block_model)
            block_item.build_item()

            # The editor block is the authoritative model container for later save/rebuild steps.
            self.block.add(block_model)
            self.scene.addItem(block_item)
            block_item.setPos(QtCore.QPointF(x_pos, y_pos))

            # Keep the diagram synchronized so later features can rebuild from the same data source.
            self.diagram.add_node(
                name=item_name,
                x=x_pos,
                y=y_pos,
                tpe=block_type.name,
                device_uid=block_model.uid
            )
            return block_item
        else:
            return None

    def remove_connection_item(self, item: ConnectionItem) -> None:
        """
        Remove a connection and restore the destination symbolic input.

        :param item:
        :return:
        """
        source_port: PortItem = item.source_port
        target_port: PortItem = item.target_port

        if item.uid in self.diagram.con_data:
            del self.diagram.con_data[item.uid]
        else:
            pass

        if source_port.connections is not None:
            if item in source_port.connections:
                source_port.connections.remove(item)
            else:
                pass

            if len(source_port.connections) == 0:
                source_port.connections = None
            else:
                pass
        else:
            pass

        if target_port.connections is not None:
            if item in target_port.connections:
                target_port.connections.remove(item)
            else:
                pass

            if len(target_port.connections) == 0:
                target_port.connections = None
            else:
                pass
        else:
            pass

        self.scene.removeItem(item)

        if source_port.subsystem.subsys is not None and target_port.subsystem.subsys is not None:
            dst_var: Var = source_port.subsystem.subsys.out_vars[source_port.index]
            target_var: Var = target_port.subsystem.subsys.in_vars[target_port.index]
            i: int
            eq: Expr

            # The destination equations must be restored to the original local input variable.
            for i, eq in enumerate(target_port.subsystem.subsys.algebraic_eqs):
                target_port.subsystem.subsys.algebraic_eqs[i] = eq.subs({dst_var: target_var})

            for i, eq in enumerate(target_port.subsystem.subsys.state_eqs):
                target_port.subsystem.subsys.state_eqs[i] = eq.subs({dst_var: target_var})
        else:
            pass

    def remove_block_item(self, item: BlockItem) -> None:
        """
        Remove a block and all of its attached connections.

        :param item:
        :return:
        """
        port: PortItem
        conn: ConnectionItem
        connections_to_remove: List[ConnectionItem] = list()
        child_block: Block

        for port in item.inputs + item.outputs:
            if port.connections is not None:
                for conn in port.connections:
                    if conn not in connections_to_remove:
                        connections_to_remove.append(conn)
                    else:
                        pass
            else:
                pass

        for conn in connections_to_remove:
            self.remove_connection_item(conn)

        self.scene.removeItem(item)

        if item.subsys is not None:
            for child_block in list(self.main_block.children):
                if child_block.uid == item.subsys.uid:
                    self.main_block.children.remove(child_block)
                else:
                    pass

            if item.subsys.uid in self.diagram.node_data:
                del self.diagram.node_data[item.subsys.uid]
            else:
                pass
        else:
            pass

    def remove_item(self, item: BlockItem | ConnectionItem) -> None:
        """
        Remove a block or connection from scene and model state.

        :param item:
        :return:
        """
        if isinstance(item, ConnectionItem):
            self.remove_connection_item(item)
        elif isinstance(item, BlockItem):
            self.remove_block_item(item)
        else:
            pass

    def get_block_from_main_block(self, device_uid: int) -> Block | None:
        """
        Find a child block by uid in the editor root block.

        :param device_uid:
        :return:
        """
        block_model: Block

        for block_model in self.main_block.get_all_blocks():
            if block_model.uid == device_uid:
                return block_model
            else:
                pass

        return None

    def apply_changes(self) -> None:
        """
        Commit the edited working copy back into the original block.

        :return:
        """
        copy_block_state(source_block=self.main_block, target_block=self.original_block)
        self.changes_applied = True
        self.close()

    def rebuild_scene_from_diagram(self) -> None:
        """
        Rebuild the visible scene from the persisted block diagram.

        :return:
        """
        uid_to_blockitem: Dict[int, BlockItem] = dict()
        uid: int
        node: Any
        con: Any

        self.scene.clear()

        for uid, node in self.diagram.node_data.items():
            block_type: BlockType = BlockType[node.tpe]
            block_model: Block | None = self.get_block_from_main_block(node.device_uid)

            if block_model is not None:
                block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=node.name)
                block_item.set_subsystem(block_model)
                block_item.build_item()
                self.scene.addItem(block_item)
                block_item.setPos(QPointF(node.x, node.y))

                brush: QBrush = block_item.brush()
                brush.setColor(QColor(node.color))
                block_item.setBrush(brush)
                uid_to_blockitem[uid] = block_item

                current_count: int = self.block_counters.get(block_type, 0) + 1
                self.block_counters[block_type] = current_count
            else:
                pass

        for uid, con in self.diagram.con_data.items():
            src_item: BlockItem | None = uid_to_blockitem.get(con.from_uid, None)
            dst_item: BlockItem | None = uid_to_blockitem.get(con.to_uid, None)

            if src_item is not None and dst_item is not None:
                try:
                    src_port: PortItem = src_item.outputs[con.port_number_from]
                    dst_port: PortItem = dst_item.inputs[con.port_number_to]
                except IndexError:
                    continue

                connection: ConnectionItem = ConnectionItem(src_port, dst_port)
                connection.uid = uid

                pen: QPen = connection.pen()
                pen.setColor(QColor(con.color))
                connection.setPen(pen)
                self.scene.addItem(connection)
            else:
                pass

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Close the editor. Unapplied changes are discarded by design.

        :param event:
        :return:
        """
        event.accept()

    def graphicsDragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Validate whether the drag entering the graphics view contains a block entry.

        :param event:
        :return:
        """
        block_type: BlockType | None = self.get_block_type_from_mime_data(event.mimeData())

        if block_type is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def graphicsDragMoveEvent(self, event: QDragMoveEvent) -> None:
        """
        Keep the drag active while the payload remains a valid block entry.

        :param event:
        :return:
        """
        block_type: BlockType | None = self.get_block_type_from_mime_data(event.mimeData())

        if block_type is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def graphicsDropEvent(self, event: QDropEvent) -> None:
        """
        Create a dropped block in scene coordinates.

        :param event:
        :return:
        """
        block_type: BlockType | None = self.get_block_type_from_mime_data(event.mimeData())
        scene_position: QtCore.QPointF = self.ui.graphicsView.mapToScene(
            int(event.position().x()),
            int(event.position().y())
        )
        block_item: BlockItem | None

        if block_type is not None:
            block_item = self.create_block_item(
                block_type=block_type,
                x_pos=scene_position.x(),
                y_pos=scene_position.y()
            )

            if block_item is not None:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()


if __name__ == "__main__":
    import sys
    import VeraGridEngine.Devices as dev

    app = QtWidgets.QApplication(sys.argv)

    vf = VarFactory()
    bl = Block()
    device = dev.Generator()
    window = DynamicBlockEditorGUI(
        var_factory=vf,
        block=bl,
        templates_list=[],
        api_object=device,
    )
    window.show()
    app.exec_()
