# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import uuid
import re
from enum import Enum
from typing import List, Dict, Optional, Any, Set
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QGraphicsScene, QGraphicsView, QGraphicsItem,
                               QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QMenu, QGraphicsPathItem,
                               QDialog, QVBoxLayout, QDialogButtonBox, QLabel, QListWidget, QWidget,
                               QListWidgetItem, QFormLayout, QSpinBox, QLineEdit, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
                               QColorDialog, QPlainTextEdit)
from PySide6.QtGui import (QPen, QBrush, QPainterPath, QAction, QPainter,
                           QDropEvent, QDragEnterEvent, QDragMoveEvent, QColor)
from PySide6.QtCore import QAbstractItemModel
from PySide6.QtCore import Qt, QPointF, QModelIndex, Signal, QAbstractTableModel


from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, ParamPowerFlowRefferenceType
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms, get_bus_rms_algebraic_vars
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGrid.Gui.RmsModelEditor.block_editor import Ui_BlockEditorWindow
from VeraGridEngine.Utils.Symbolic.symbolic import (symbolic_to_string, string_to_symbolic,
                                                    get_symbolic_parser_function_names,
                                                    Expr, Var, Const, Comparison)
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagram
from VeraGridEngine.enumerations import BlockType
from VeraGridEngine.Templates.Rms.common import create_block_of_type, create_generic_block

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
PORT_LABEL_COLOR: QColor = QColor("#173042")
WIRE_ELBOW_OFFSET: float = 36.0
PORT_LABEL_MAX_CHARS: int = 12
BLOCK_HEADER_HEIGHT: float = 32.0
BLOCK_PORT_ROW_HEIGHT: float = 18.0
BLOCK_PORT_SECTION_PADDING: float = 14.0
BLOCK_MIN_WIDTH: float = 186.0
BLOCK_MIN_HEIGHT: float = 60.0
TEMPLATE_NODE_TYPE: str = "TEMPLATE"
PARAMETER_VALUE_TYPE_ROLE: int = int(QtCore.Qt.ItemDataRole.UserRole) + 500
PARAMETER_EDITABLE_ROLE: int = int(QtCore.Qt.ItemDataRole.UserRole) + 501


def _new_uid() -> int:
    """
    Generate a fresh integer identifier.

    :return:
    """
    return uuid.uuid4().int


def truncate_port_label(text: str, max_chars: int = PORT_LABEL_MAX_CHARS) -> str:
    """
    Truncate a port label to the requested visible length.

    :param text:
    :param max_chars:
    :return:
    """
    if len(text) <= max_chars:
        return text
    else:
        return text[:max_chars]


def build_orthogonal_connection_path(start: QPointF, end: QPointF) -> QPainterPath:
    """
    Build an orthogonal wire path with elbow segments.

    :param start:
    :param end:
    :return:
    """
    path: QPainterPath = QPainterPath(start)
    delta_x: float = end.x() - start.x()
    offset: float = min(WIRE_ELBOW_OFFSET, abs(delta_x) / 2.0) if delta_x != 0 else WIRE_ELBOW_OFFSET
    start_elbow_x: float = start.x() + offset
    end_elbow_x: float = end.x() - offset

    if end.x() >= start.x():
        path.lineTo(start_elbow_x, start.y())
        path.lineTo(start_elbow_x, end.y())
    else:
        middle_x: float = start.x() + max(WIRE_ELBOW_OFFSET, abs(delta_x) / 2.0)
        path.lineTo(middle_x, start.y())
        path.lineTo(middle_x, end.y())

    path.lineTo(end_elbow_x, end.y())
    path.lineTo(end)
    return path


def clone_template_block(template_block: Block) -> Block:
    """
    Build a structural copy of a template block for editor insertion.

    :param template_block:
    :return:
    """
    uid_map: Dict[int, int] = dict()
    block_data: Dict[str, Any] = template_block.to_dict()
    cloned_data: Dict[str, Any] = remap_serialized_uids(block_data, uid_map)
    cloned_block: Block = Block.parse(cloned_data)
    cloned_block.diagram = clone_template_diagram(template_block.diagram, uid_map)
    return cloned_block


def remap_serialized_uids(data: Any, uid_map: Dict[int, int]) -> Any:
    """
    Recursively replace serialized UIDs with fresh values while preserving references.

    :param data:
    :param uid_map:
    :return:
    """
    key: str
    value: Any
    remapped_data: Dict[str, Any]

    if isinstance(data, dict):
        remapped_data = dict()

        for key, value in data.items():
            if key == "uid" and isinstance(value, int):
                if value in uid_map:
                    remapped_data[key] = uid_map[value]
                else:
                    uid_map[value] = _new_uid()
                    remapped_data[key] = uid_map[value]
            else:
                remapped_data[key] = remap_serialized_uids(value, uid_map)

        return remapped_data
    elif isinstance(data, list):
        return [remap_serialized_uids(value, uid_map) for value in data]
    else:
        return data


def clone_template_diagram(diagram: BlockDiagram, uid_map: Dict[int, int]) -> BlockDiagram:
    """
    Clone a template diagram while remapping block and connection identifiers.

    :param diagram:
    :param uid_map:
    :return:
    """
    cloned_diagram: BlockDiagram = BlockDiagram()
    node: Any
    con: Any
    mapped_uid: int
    subdiagram: BlockDiagram | None

    cloned_diagram.status = diagram.status

    for _, node in diagram.node_data.items():
        mapped_uid = uid_map.get(node.device_uid, node.device_uid)

        if node.sub_diagram is not None:
            subdiagram = clone_template_diagram(node.sub_diagram, uid_map)
        else:
            subdiagram = None

        cloned_diagram.add_node(
            name=node.name,
            x=node.x,
            y=node.y,
            tpe=node.tpe,
            device_uid=mapped_uid,
            api_object_name=node.api_object_name,
            state_ins=node.state_ins,
            state_outs=list(node.state_outs),
            algeb_ins=node.algeb_ins,
            algeb_outs=list(node.algeb_outs),
            color=node.color,
            subdiagram=subdiagram
        )

    for _, con in diagram.con_data.items():
        cloned_diagram.add_branch(
            connectionitem_uid=_new_uid(),
            device_uid_from=uid_map.get(con.from_uid, con.from_uid),
            device_uid_to=uid_map.get(con.to_uid, con.to_uid),
            port_number_from=con.port_number_from,
            port_number_to=con.port_number_to,
            color=con.color
        )

    return cloned_diagram


def is_supported_library_payload(item_data: object) -> bool:
    """
    Check whether a tree item payload can be dragged into the editor scene.

    :param item_data:
    :return:
    """
    if isinstance(item_data, BlockType):
        return True
    elif isinstance(item_data, (RmsModelTemplate, EmtModelTemplate)):
        return True
    else:
        return False


def clone_block_for_editing(block: Block) -> Block:
    """
    Build an isolated editable copy of a block, including its diagram.

    :param block:
    :return:
    """
    editable_block: Block = block.copy()
    # editable_block.diagram = block.diagram.copy()
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
    target_block.diagram = source_block.diagram


def build_block_symbol_namespace(block: Block) -> Dict[str, Expr]:
    """
    Build the symbol namespace used to parse textual expressions for a block.

    :param block:
    :return:
    """
    namespace: Dict[str, Expr] = dict()
    block_item: Block
    var: Var

    for block_item in block.get_all_blocks():
        for var in block_item.algebraic_vars:
            namespace[var.name] = var

        for var in block_item.state_vars:
            namespace[var.name] = var

        for var in block_item.diff_vars:
            namespace[var.name] = var

        for var in block_item.in_vars:
            namespace[var.name] = var

        for var in block_item.out_vars:
            namespace[var.name] = var

        for var in block_item.parameters.keys():
            namespace[var.name] = var

        for var in block_item.event_dict.keys():
            namespace[var.name] = var

        for var in block_item.mode_dict.keys():
            namespace[var.name] = var

        for var in block_item.init_values.keys():
            namespace[var.name] = var

    return namespace


def is_valid_symbol_name(name: str) -> bool:
    """
    Check whether a string is a valid symbolic identifier.

    :param name:
    :return:
    """
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is not None


def block_namespace_contains_name(block: Block, name: str, exclude_var: Var | None = None) -> bool:
    """
    Check whether a symbol name already exists in the block namespace.

    :param block:
    :param name:
    :param exclude_var:
    :return:
    """
    namespace: Dict[str, Expr] = build_block_symbol_namespace(block)
    current_symbol: Expr | None = namespace.get(name, None)

    if current_symbol is None:
        return False
    elif exclude_var is not None and current_symbol is exclude_var:
        return False
    else:
        return True


def add_variable_to_block(block: Block,
                          var: Var,
                          var_type: str,
                          parameter_value: float = 0.0) -> None:
    if var_type == "state":
        block.state_vars.append(var)
    elif var_type == "algebraic":
        block.algebraic_vars.append(var)
    elif var_type == "in":
        block.in_vars.append(var)
    elif var_type == "out":
        block.out_vars.append(var)
    elif var_type == "parameter":
        block.parameters[var] = Const(parameter_value, name=var.name)
    else:
        raise ValueError(f"Unknown var_type {var_type}")

def build_block_tree(block: Block):
    root = Node(block.name)

    state_vars_node = Node("State Vars")
    for v in block.state_vars:
        state_vars_node.add_child(Node(v.name, v))

    alg_vars_node = Node("Algebraic Vars")
    for v in block.algebraic_vars:
        alg_vars_node.add_child(Node(v.name, v))

    state_eq_node = Node("State Equations")
    for eq in block.state_eqs:
        state_eq_node.add_child(Node(symbolic_to_string(eq), eq))

    alg_eq_node = Node("Algebraic Equations")
    for eq in block.algebraic_eqs:
        alg_eq_node.add_child(Node(symbolic_to_string(eq), eq))

    root.add_child(state_vars_node)
    root.add_child(alg_vars_node)
    root.add_child(state_eq_node)
    root.add_child(alg_eq_node)

    return root

class Node:
    def __init__(self, name, data=None, parent=None):
        self.name = name
        self.data = data
        self.parent = parent
        self.children = []

    def add_child(self, node):
        self.children.append(node)
        node.parent = self

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
                min_width: float
                min_height: float
                min_width, min_height = self.block.get_minimum_block_size()
                new_width: float = max(new_pos.x(), min_width)
                new_height: float = max(new_pos.y(), min_height)

                # The block geometry must be updated from the handle movement.
                self.block.resize_block(new_width, new_height)
                return QPointF(new_width, new_height)
            else:
                return super().itemChange(change, value)
        else:
            return super().itemChange(change, value)


class GenericBlockDialog(QDialog):
    """
    Dialog to edit the created generic block
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Generic Block")

        layout = QFormLayout(self)

        # --- New: name field ---
        self.name_edit = QLineEdit()
        layout.addRow("Block name:", self.name_edit)

        # --- Existing fields ---
        self.state_inputs_spin = QSpinBox()
        self.state_inputs_spin.setMinimum(0)
        layout.addRow("Number of state inputs:", self.state_inputs_spin)

        self.state_outputs_edit = QLineEdit()
        layout.addRow("State outputs (comma separated):", self.state_outputs_edit)

        self.algeb_inputs_spin = QSpinBox()
        self.algeb_inputs_spin.setMinimum(0)
        layout.addRow("Number of algebraic inputs:", self.algeb_inputs_spin)

        self.algeb_outputs_edit = QLineEdit()
        layout.addRow("Algebraic outputs (comma separated):", self.algeb_outputs_edit)

        # --- Buttons ---
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_values(self):
        """Return all dialog values."""
        name = self.name_edit.text().strip()
        state_ins = self.state_inputs_spin.value()
        state_outs = [s.strip() for s in self.state_outputs_edit.text().split(",") if s.strip()]
        algeb_ins = self.algeb_inputs_spin.value()
        algeb_outs = [s.strip() for s in self.algeb_outputs_edit.text().split(",") if s.strip()]
        return name, state_ins, state_outs, algeb_ins, algeb_outs


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
        self.base_var: Var | None = None

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
    Orthogonal graphical connection between two ports.
    """

    def __init__(self, source_port: PortItem, target_port: PortItem,
                 diagram=None, con_uid=None, elbow_points=None, uid=None):
        """
        Build the connection item.

        :param source_port:
        :param target_port:
        :param diagram: BlockDiagram reference to update on elbow change
        :param con_uid: Connection uid in the diagram
        :param elbow_points: Custom elbow points (list of QPointF)
        :param uid: Optional specific uid to use
        """
        super().__init__()
        self.uid: int = uid if uid is not None else _new_uid()
        self.setZValue(-1)
        self.source_port: PortItem = source_port
        self.target_port: PortItem = target_port
        self.diagram = diagram
        self.con_uid = con_uid if con_uid is not None else self.uid
        self.custom_elbow_points: List[QPointF] = []
        self._dragging: bool = False
        self._drag_type: str = None  # 'horizontal' or 'vertical'
        self._drag_segment_idx: int = -1
        self._original_elbows: List[QPointF] = []

        if elbow_points:
            self.custom_elbow_points = [QPointF(x, y) for x, y in elbow_points]

        if self.source_port.connections is None:
            self.source_port.connections = list()
        self.source_port.connections.append(self)

        if self.target_port.connections is None:
            self.target_port.connections = list()
        self.target_port.connections.append(self)

        self.setPen(QPen(WIRE_COLOR, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        self.update_path()

    def update_path(self) -> None:
        """
        Recompute the orthogonal path from current port positions.
        Uses custom elbow points if available, otherwise builds default path.

        :return:
        """
        start: QPointF = self.source_port.scenePos()
        end: QPointF = self.target_port.scenePos()

        if self.custom_elbow_points:
            path: QPainterPath = self._build_path_with_elbows(start, end, self.custom_elbow_points)
        else:
            path = build_orthogonal_connection_path(start, end)
        self.setPath(path)

    def _build_path_with_elbows(self, start: QPointF, end: QPointF, elbows: List[QPointF]) -> QPainterPath:
        """
        Build a path through the given elbow points.

        :param start:
        :param end:
        :param elbows:
        :return:
        """
        path: QPainterPath = QPainterPath(start)
        for elbow in elbows:
            path.lineTo(elbow)
        path.lineTo(end)
        return path

    def _get_path_points(self) -> List[QPointF]:
        """
        Get all points that define the path (start, elbows, end).

        :return: List of QPointF
        """
        start: QPointF = self.source_port.scenePos()
        end: QPointF = self.target_port.scenePos()

        if self.custom_elbow_points:
            points = [start] + list(self.custom_elbow_points) + [end]
        else:
            points = self._get_default_elbows(start, end)
        return points

    def _get_default_elbows(self, start: QPointF, end: QPointF) -> List[QPointF]:
        """
        Get default elbow points for the path.

        :param start:
        :param end:
        :return:
        """
        delta_x: float = end.x() - start.x()
        offset: float = min(WIRE_ELBOW_OFFSET, abs(delta_x) / 2.0) if delta_x != 0 else WIRE_ELBOW_OFFSET
        start_elbow_x: float = start.x() + offset
        end_elbow_x: float = end.x() - offset

        if end.x() >= start.x():
            mid1 = QPointF(start_elbow_x, start.y())
            mid2 = QPointF(start_elbow_x, end.y())
        else:
            middle_x: float = start.x() + max(WIRE_ELBOW_OFFSET, abs(delta_x) / 2.0)
            mid1 = QPointF(middle_x, start.y())
            mid2 = QPointF(middle_x, end.y())

        return [start, mid1, mid2, end]

    def _find_segment_at_point(self, pos: QPointF) -> tuple[int, str, QPointF, QPointF] | None:
        """
        Find which segment contains the given point.

        :param pos: Point to check
        :return: (segment_index, segment_direction, segment_start, segment_end) or None
        """
        points = self._get_path_points()
        threshold = 15.0

        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]

            if abs(p1.y() - p2.y()) < 1:
                min_x, max_x = min(p1.x(), p2.x()), max(p1.x(), p2.x())
                if min_x - threshold <= pos.x() <= max_x + threshold and abs(pos.y() - p1.y()) <= threshold:
                    return (i, 'horizontal', p1, p2)
            elif abs(p1.x() - p2.x()) < 1:
                min_y, max_y = min(p1.y(), p2.y()), max(p1.y(), p2.y())
                if min_y - threshold <= pos.y() <= max_y + threshold and abs(pos.x() - p1.x()) <= threshold:
                    return (i, 'vertical', p1, p2)

        return None

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Handle mouse press to start dragging a segment.

        :param event:
        :return:
        """
        pos = event.scenePos()
        segment_info = self._find_segment_at_point(pos)

        if segment_info is not None:
            self._drag_segment_idx, self._drag_type, p1, p2 = segment_info

            if not self.custom_elbow_points:
                self.custom_elbow_points = [QPointF(p) for p in self._get_default_elbows(
                    self.source_port.scenePos(), self.target_port.scenePos()
                )][1:-1]

            elbow_idx = self._drag_segment_idx - 1
            if elbow_idx < 0 or elbow_idx >= len(self.custom_elbow_points):
                super().mousePressEvent(event)
                return

            self._dragging = True
            self._original_elbows = [QPointF(p) for p in self.custom_elbow_points]
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Handle mouse move to drag a segment.

        :param event:
        :return:
        """
        if self._dragging:
            pos = event.scenePos()
            elbow_idx = self._drag_segment_idx - 1

            if self._drag_type == 'horizontal':
                new_y = pos.y()
                self.custom_elbow_points[elbow_idx] = QPointF(
                    self.custom_elbow_points[elbow_idx].x(), new_y
                )
                if elbow_idx + 1 < len(self.custom_elbow_points):
                    self.custom_elbow_points[elbow_idx + 1] = QPointF(
                        self.custom_elbow_points[elbow_idx + 1].x(), new_y
                    )
            else:
                new_x = pos.x()
                self.custom_elbow_points[elbow_idx] = QPointF(
                    new_x, self.custom_elbow_points[elbow_idx].y()
                )
                if elbow_idx + 1 < len(self.custom_elbow_points):
                    self.custom_elbow_points[elbow_idx + 1] = QPointF(
                        new_x, self.custom_elbow_points[elbow_idx + 1].y()
                    )

            self.update_path()
            self._update_diagram()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Handle mouse release to stop dragging.

        :param event:
        :return:
        """
        self._dragging = False
        self._drag_segment_idx = -1
        self._drag_type = None
        self._original_elbows = []
        super().mouseReleaseEvent(event)

    def _update_diagram(self) -> None:
        """
        Update the diagram's connection data with new elbow points.

        :return:
        """
        if self.diagram is not None and self.con_uid is not None:
            if self.con_uid in self.diagram.con_data:
                self.diagram.con_data[self.con_uid].elbow_points = [
                    (p.x(), p.y()) for p in self.custom_elbow_points
                ]

    def set_elbow_points(self, elbows: List[QPointF]) -> None:
        """
        Set custom elbow points and update the path.

        :param elbows:
        :return:
        """
        self.custom_elbow_points = [QPointF(x, y) for x, y in elbows]
        self.update_path()

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

# class ParametersTableModel(QAbstractTableModel):
#     """
#     Table model to display event parameters (editable) and fixed parameters (read-only).
#     """
#
#     dataChangedSignal = Signal(dict)  # emit updated event_dict
#
#     def __init__(self, var_factory, block: Block):
#         super().__init__()
#
#         self.var_factory = var_factory
#
#
#         # Store two lists of tuples (var, expr)
#         self.event_params = list(block.event_dict.items())      # editable
#         self.fixed_params = list(block.parameters.items()) # read-only
#
#         # Combine for easy row indexing
#         self.all_params = self.event_params + self.fixed_params
#
#     def rowCount(self, parent=QModelIndex()) -> int:
#         return len(self.all_params)
#
#     def columnCount(self, parent=QModelIndex()) -> int:
#         return 2  # Parameter name, Value
#
#     def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
#         if not index.isValid():
#             return None
#
#         var, expr = self.all_params[index.row()]
#
#         if role in (Qt.DisplayRole, Qt.EditRole):
#             if index.column() == 0:  # Parameter name
#                 return var.name
#             elif index.column() == 1:  # Value
#                 if hasattr(expr, "value"):
#                     return str(expr.value)
#                 return str(expr)
#
#         # Optional: different background for fixed params
#         if role == Qt.BackgroundRole and index.row() >= len(self.event_params):
#             return QColor("#f0f0f0")  # gray for read-only
#
#         return None
#
#     def headerData(self, section, orientation, role=Qt.DisplayRole):
#         if role != Qt.DisplayRole:
#             return None
#         if orientation == Qt.Horizontal:
#             return ["Parameter", "Value"][section]
#         return str(section + 1)
#
#     def flags(self, index: QModelIndex):
#         if not index.isValid():
#             return Qt.ItemFlag.ItemIsEnabled
#
#         flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
#
#         # Only editable if it's an event parameter and the Value column
#         if index.row() < len(self.event_params) and index.column() == 1:
#             flags |= Qt.ItemFlag.ItemIsEditable
#
#         return flags
#
#     def setData(self, index: QModelIndex, value, role=Qt.EditRole):
#         if (
#             not index.isValid()
#             or role != Qt.EditRole
#             or index.column() != 1
#             or index.row() >= len(self.event_params)
#         ):
#             return False
#
#         var, expr = self.event_params[index.row()]
#
#         try:
#             value_float = float(value)
#         except ValueError:
#             value_float = value
#
#         # Update the event_dict copy
#         self.event_params[index.row()] = (var, self.var_factory.add_const(value=value_float, name=var.name))
#
#         # Also update the combined list
#         self.all_params[index.row()] = self.event_params[index.row()]
#
#         self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
#         self.dataChangedSignal.emit(dict(self.event_params))  # emit updated event_dict
#         return True
# #
#

# class ParamTreeItem:
#     """
#     class to represent a node in the params tree
#     """
#     def __init__(self, name, parent=None, block=None, var=None, expr=None,
#                  is_param=False, editable=False):
#         self.name = name
#         self.parent = parent
#         self.children = []
#
#         self.block = block
#         self.var = var
#         self.expr = expr
#
#         self.is_param = is_param
#         self.editable = editable
#
#     def append_child(self, child):
#         self.children.append(child)
#
#     def child(self, row):
#         if 0 <= row < len(self.children):
#             return self.children[row]
#         return None
#
#     def child_count(self):
#         return len(self.children)
#
#     def row(self):
#         if self.parent:
#             return self.parent.children.index(self)
#         return 0
#
#
# class ParametersTreeModel(QAbstractItemModel):
#     """
#     Tree model for the parameters
#     """
#
#     dataChangedSignal = Signal()
#
#     def __init__(self, var_factory, main_block):
#         super().__init__()
#         self.var_factory = var_factory
#         self.blocks: List[Block] = [blk for blk in main_block.get_all_blocks()]
#         self.root_item = ParamTreeItem("root")
#         self.build_tree_from_block(main_block, self.root_item)
#
#
#     def add_block(self, block: Block):
#         """
#         add a node to the tree and refresh
#         :param block:
#         :type block:
#         :return:
#         :rtype:
#         """
#         if block not in self.blocks:
#             self.beginResetModel()
#             self.blocks.append(block)
#             self.build_tree_from_block(block, self.root_item)
#             self.endResetModel()
#
#     def build_tree_from_block(self, block, parent_item):
#         """
#         create nodes and build tree
#         :param block:
#         :type block:
#         :param parent_item:
#         :type parent_item:
#         :return:
#         :rtype:
#         """
#         block_item = ParamTreeItem(
#             name=block.name if block.name else f"Block_{block.uid}",
#             parent=parent_item,
#             block=block
#         )
#         parent_item.append_child(block_item)
#
#         if block.event_dict:
#             event_group = ParamTreeItem("Editable Parameters", parent=block_item)
#             block_item.append_child(event_group)
#
#             for var, expr in block.event_dict.items():
#                 param_item = ParamTreeItem(
#                     name=var.name,
#                     parent=event_group,
#                     block=block,
#                     var=var,
#                     expr=expr,
#                     is_param=True,
#                     editable=True
#                 )
#                 event_group.append_child(param_item)
#
#         if block.parameters:
#             param_group = ParamTreeItem("Non Editable Parameters", parent=block_item)
#             block_item.append_child(param_group)
#
#             for var, expr in block.parameters.items():
#                 param_item = ParamTreeItem(
#                     name=var.name,
#                     parent=param_group,
#                     block=block,
#                     var=var,
#                     expr=expr,
#                     is_param=True,
#                     editable=False
#                 )
#                 param_group.append_child(param_item)
#
#         for child in block.children:
#             self.build_tree_from_block(child, block_item)
#
#     def columnCount(self, parent=QModelIndex()):
#         return 2
#
#     def rowCount(self, parent=QModelIndex()):
#         parent_item = parent.internalPointer() if parent.isValid() else self.root_item
#         return parent_item.child_count()
#
#     def index(self, row, column, parent=QModelIndex()):
#         if not self.hasIndex(row, column, parent):
#             return QModelIndex()
#
#         parent_item = parent.internalPointer() if parent.isValid() else self.root_item
#         child_item = parent_item.child(row)
#
#         if child_item:
#             return self.createIndex(row, column, child_item)
#
#         return QModelIndex()
#
#     def parent(self, index):
#         if not index.isValid():
#             return QModelIndex()
#
#         item = index.internalPointer()
#         parent_item = item.parent
#
#         if parent_item is None or parent_item == self.root_item:
#             return QModelIndex()
#
#         return self.createIndex(parent_item.row(), 0, parent_item)
#
#     def data(self, index, role=Qt.DisplayRole):
#         if not index.isValid():
#             return None
#
#         item = index.internalPointer()
#
#         if role in (Qt.DisplayRole, Qt.EditRole):
#
#             if index.column() == 0:
#                 return item.name
#
#             elif index.column() == 1:
#                 if item.is_param:
#                     if hasattr(item.expr, "value"):
#                         return str(item.expr.value)
#                     return str(item.expr)
#                 return ""
#
#         if role == Qt.BackgroundRole:
#             if item.is_param and not item.editable:
#                 return QColor("#f0f0f0")
#
#         return None
#
#     def headerData(self, section, orientation, role=Qt.DisplayRole):
#         if role != Qt.DisplayRole:
#             return None
#
#         if orientation == Qt.Horizontal:
#             return ["Name", "Value"][section]
#
#         return str(section + 1)
#
#     # -----------------------------
#     # EDITING
#     # -----------------------------
#     def flags(self, index):
#         if not index.isValid():
#             return Qt.ItemIsEnabled
#
#         item = index.internalPointer()
#
#         flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
#
#         if item.is_param and item.editable and index.column() == 1:
#             flags |= Qt.ItemIsEditable
#
#         return flags
#
#     def setData(self, index, value, role=Qt.EditRole):
#         if role != Qt.EditRole:
#             return False
#
#         item = index.internalPointer()
#
#         if not item.is_param or not item.editable:
#             return False
#
#         try:
#             value_float = float(value)
#         except ValueError:
#             value_float = value
#
#         new_expr = self.var_factory.add_const(
#             value=value_float,
#             name=item.var.name
#         )
#
#         # 🔥 ACTUALIZA EL BLOCK REAL
#         item.block.event_dict[item.var] = new_expr
#
#         # actualizar nodo
#         item.expr = new_expr
#
#         self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
#         self.dataChangedSignal.emit()
#
#         return True


class ExpressionTextEditorDialog(QDialog):
    """
    Dialog used to inspect or edit a symbolic expression as text.
    """

    def __init__(self,
                 expression_text: str,
                 symbol_namespace: Dict[str, Expr],
                 parent: Optional[QtWidgets.QWidget] = None):
        """
        Build the expression text editor dialog.

        :param expression_text:
        :param symbol_namespace:
        :param parent:
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Expression")
        self.resize(520, 260)
        self.symbol_namespace: Dict[str, Expr] = symbol_namespace
        self.validation_label: QLabel
        self.button_box: QDialogButtonBox
        self.ok_button: QtWidgets.QPushButton
        self.highlighter: ExpressionValidationHighlighter

        layout: QVBoxLayout = QVBoxLayout(self)
        info_label: QLabel = QLabel("Edit the symbolic expression text:")
        layout.addWidget(info_label)

        self.text_editor: QPlainTextEdit = QPlainTextEdit(self)
        editor_font: QtGui.QFont = QtGui.QFont("DejaVu Sans Mono", 10)
        self.text_editor.setFont(editor_font)
        self.text_editor.setPlainText(expression_text)
        self.text_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.text_editor)

        self.validation_label = QLabel("")
        layout.addWidget(self.validation_label)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.highlighter = ExpressionValidationHighlighter(
            document=self.text_editor.document(),
            symbol_names=set(self.symbol_namespace.keys()),
            function_names=set(get_symbolic_parser_function_names())
        )
        self.text_editor.textChanged.connect(self.update_validation_state)
        self.update_validation_state()

    def get_expression_text(self) -> str:
        """
        Return the edited expression text.

        :return:
        """
        return self.text_editor.toPlainText().strip()

    def update_validation_state(self) -> None:
        """
        Validate the current expression text and update the dialog status widgets.

        :return:
        """
        expression_text: str = self.get_expression_text()
        unknown_identifiers: List[str] = self.highlighter.get_unknown_identifiers(expression_text)

        if len(unknown_identifiers) > 0:
            self.validation_label.setText(
                "Unknown symbols: " + ", ".join(sorted(set(unknown_identifiers)))
            )
            self.validation_label.setStyleSheet("color: #b42318;")
            self.ok_button.setEnabled(False)
        else:
            try:
                string_to_symbolic(expression_text, self.symbol_namespace)
                self.validation_label.setText("Expression is valid.")
                self.validation_label.setStyleSheet("color: #027a48;")
                self.ok_button.setEnabled(True)
            except Exception as exc:
                self.validation_label.setText(str(exc))
                self.validation_label.setStyleSheet("color: #b42318;")
                self.ok_button.setEnabled(False)


class AddBlockVariableDialog(QDialog):
    """
    Dialog used to create a new variable or parameter in the selected block.
    """

    CATEGORY_OPTIONS: List[tuple[str, str]] = [
        ("State", "state"),
        ("Algebraic", "algebraic"),
        ("Input", "in"),
        ("Output", "out"),
        ("Parameter", "parameter"),
    ]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Variable")
        self.resize(360, 160)

        layout: QVBoxLayout = QVBoxLayout(self)
        form_layout: QFormLayout = QFormLayout()
        layout.addLayout(form_layout)

        self.name_edit: QLineEdit = QLineEdit(self)
        self.category_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(self)
        self.parameter_value_spin: QDoubleSpinBox = QDoubleSpinBox(self)
        self.parameter_value_spin.setDecimals(8)
        self.parameter_value_spin.setMinimum(-1e200)
        self.parameter_value_spin.setMaximum(1e200)
        self.parameter_value_spin.setValue(0.0)

        label: str
        value: str
        for label, value in self.CATEGORY_OPTIONS:
            self.category_combo.addItem(label, value)

        form_layout.addRow("Name", self.name_edit)
        form_layout.addRow("Category", self.category_combo)
        form_layout.addRow("Initial value", self.parameter_value_spin)

        self.validation_label: QLabel = QLabel("", self)
        layout.addWidget(self.validation_label)

        self.button_box: QDialogButtonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self
        )
        self.ok_button: QtWidgets.QPushButton = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.name_edit.textChanged.connect(self.update_validation_state)
        self.category_combo.currentIndexChanged.connect(self.update_validation_state)
        self.update_validation_state()

    def get_name(self) -> str:
        return self.name_edit.text().strip()

    def get_category(self) -> str:
        return str(self.category_combo.currentData())

    def get_parameter_value(self) -> float:
        return float(self.parameter_value_spin.value())

    def update_validation_state(self) -> None:
        """
        Validate the new symbol data before allowing acceptance.

        :return:
        """
        category: str = self.get_category()
        name: str = self.get_name()
        is_parameter: bool = category == "parameter"

        self.parameter_value_spin.setEnabled(is_parameter)

        if len(name) == 0:
            self.validation_label.setText("Enter a symbol name.")
            self.validation_label.setStyleSheet("color: #b42318;")
            self.ok_button.setEnabled(False)
        elif not is_valid_symbol_name(name):
            self.validation_label.setText("Use a valid identifier: letters, digits, and underscore.")
            self.validation_label.setStyleSheet("color: #b42318;")
            self.ok_button.setEnabled(False)
        else:
            self.validation_label.setText("New symbol is valid.")
            self.validation_label.setStyleSheet("color: #027a48;")
            self.ok_button.setEnabled(True)


class ExpressionValidationHighlighter(QtGui.QSyntaxHighlighter):
    """
    Syntax highlighter that validates symbolic identifiers against the selected block namespace.
    """

    IDENTIFIER_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")

    def __init__(self,
                 document: QtGui.QTextDocument,
                 symbol_names: Set[str],
                 function_names: Set[str]):
        """
        Build the expression validation highlighter.

        :param document:
        :param symbol_names:
        :param function_names:
        """
        super().__init__(document)
        self.symbol_names: Set[str] = symbol_names
        self.function_names: Set[str] = function_names
        self.ignored_tokens: Set[str] = {"True", "False", "None"}
        self.valid_symbol_format: QtGui.QTextCharFormat = QtGui.QTextCharFormat()
        self.function_format: QtGui.QTextCharFormat = QtGui.QTextCharFormat()
        self.invalid_format: QtGui.QTextCharFormat = QtGui.QTextCharFormat()

        self.valid_symbol_format.setFontWeight(QtGui.QFont.Weight.Bold)
        self.function_format.setForeground(QColor("#0b5394"))
        self.invalid_format.setForeground(QColor("#b42318"))

    def highlightBlock(self, text: str) -> None:
        """
        Highlight one text block according to identifier validity.

        :param text:
        :return:
        """
        match: re.Match[str]
        token: str
        start_pos: int
        token_length: int
        classification: str

        for match in self.IDENTIFIER_PATTERN.finditer(text):
            token = match.group(0)
            start_pos = match.start()
            token_length = match.end() - match.start()
            classification = self.classify_identifier(text, token, match.end())

            if classification == "valid_symbol":
                self.setFormat(start_pos, token_length, self.valid_symbol_format)
            elif classification == "valid_function":
                self.setFormat(start_pos, token_length, self.function_format)
            elif classification == "invalid":
                self.setFormat(start_pos, token_length, self.invalid_format)
            else:
                pass

    def classify_identifier(self, text: str, token: str, token_end: int) -> str:
        """
        Classify an identifier as a valid symbol, a valid function, or invalid.

        :param text:
        :param token:
        :param token_end:
        :return:
        """
        if self.is_function_call(text, token_end):
            if token in self.function_names:
                return "valid_function"
            else:
                return "invalid"
        elif token in self.symbol_names:
            return "valid_symbol"
        elif token in self.ignored_tokens:
            return "ignored"
        else:
            return "invalid"

    def is_function_call(self, text: str, token_end: int) -> bool:
        """
        Check whether an identifier is followed by a function-call parenthesis.

        :param text:
        :param token_end:
        :return:
        """
        current_index: int = token_end

        while current_index < len(text) and text[current_index].isspace():
            current_index += 1

        if current_index < len(text):
            return text[current_index] == "("
        else:
            return False

    def get_unknown_identifiers(self, text: str) -> List[str]:
        """
        Return the list of currently unknown identifiers in the editor text.

        :param text:
        :return:
        """
        unknown_identifiers: List[str] = list()
        line_text: str
        match: re.Match[str]
        token: str

        for line_text in text.splitlines():
            for match in self.IDENTIFIER_PATTERN.finditer(line_text):
                token = match.group(0)

                if self.classify_identifier(line_text, token, match.end()) == "invalid":
                    unknown_identifiers.append(token)
                else:
                    pass

        return unknown_identifiers


class BlockParameterKind(Enum):
    """
    Row kinds shown in the side editor table.
    """

    SECTION = "Section"
    STATE_VAR = "State Var"
    ALGEBRAIC_VAR = "Algebraic Var"
    INPUT_VAR = "Input Var"
    OUTPUT_VAR = "Output Var"
    STATE_EQUATION = "State Equation"
    ALGEBRAIC_EQUATION = "Algebraic Equation"
    EVENT_PARAMETER = "Event Parameter"
    FIXED_PARAMETER = "Parameter"


class BlockParameterRow:
    """
    Row description for the selected block editor table.
    """

    __slots__ = ("name", "kind", "key_var", "value", "editable_name", "editable_value", "value_type", "item_index")

    def __init__(self,
                 name: str,
                 kind: BlockParameterKind,
                 key_var: Var | None,
                 value: Any,
                 editable_name: bool,
                 editable_value: bool,
                 value_type: type,
                 item_index: int | None = None):
        """
         Build a parameter row descriptor.

        :param name:
        :param kind:
        :param key_var:
        :param value:
        :param editable_name:
        :param editable_value:
        :param value_type:
        :param item_index:
        """
        self.name: str = name
        self.kind: BlockParameterKind = kind
        self.key_var: Var | None = key_var
        self.value: Any = value
        self.editable_name: bool = editable_name
        self.editable_value: bool = editable_value
        self.value_type: type = value_type
        self.item_index: int | None = item_index

    @property
    def is_section(self) -> bool:
        return self.kind == BlockParameterKind.SECTION

    @property
    def opens_expression_editor(self) -> bool:
        return self.kind in {
            BlockParameterKind.STATE_EQUATION,
            BlockParameterKind.ALGEBRAIC_EQUATION,
            BlockParameterKind.EVENT_PARAMETER,
            BlockParameterKind.FIXED_PARAMETER,
        } and isinstance(self.value, Expr)


class BlockParameterValueDelegate(QtWidgets.QStyledItemDelegate):
    """
    Delegate that chooses a numeric or text editor depending on the parameter row metadata.
    """

    def createEditor(self,
                     parent: QtWidgets.QWidget,
                     option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> QtWidgets.QWidget | None:
        """
        Create the editor widget for the parameter value cell.

        :param parent:
        :param option:
        :param index:
        :return:
        """
        value_type_name: str = str(index.model().data(index, PARAMETER_VALUE_TYPE_ROLE))
        editable: bool = bool(index.model().data(index, PARAMETER_EDITABLE_ROLE))

        if not editable:
            return None
        elif value_type_name == "float":
            editor: QDoubleSpinBox = QDoubleSpinBox(parent)
            editor.setDecimals(8)
            editor.setMinimum(-1e200)
            editor.setMaximum(1e200)
            return editor
        elif value_type_name == "int":
            editor_int: QSpinBox = QSpinBox(parent)
            editor_int.setMinimum(-999999999)
            editor_int.setMaximum(999999999)
            return editor_int
        else:
            return QLineEdit(parent)

    def setEditorData(self, editor: QtWidgets.QWidget, index: QtCore.QModelIndex) -> None:
        """
        Load the current model value into the editor widget.

        :param editor:
        :param index:
        :return:
        """
        value: Any = index.model().data(index, QtCore.Qt.ItemDataRole.EditRole)

        if isinstance(editor, QDoubleSpinBox):
            editor.setValue(float(value))
        elif isinstance(editor, QSpinBox):
            editor.setValue(int(value))
        elif isinstance(editor, QLineEdit):
            editor.setText(str(value))
        else:
            pass

    def setModelData(self,
                     editor: QtWidgets.QWidget,
                     model: QtCore.QAbstractItemModel,
                     index: QtCore.QModelIndex) -> None:
        """
        Push the editor value back into the model.

        :param editor:
        :param model:
        :param index:
        :return:
        """
        if isinstance(editor, QDoubleSpinBox):
            model.setData(index, editor.value(), QtCore.Qt.ItemDataRole.EditRole)
        elif isinstance(editor, QSpinBox):
            model.setData(index, editor.value(), QtCore.Qt.ItemDataRole.EditRole)
        elif isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), QtCore.Qt.ItemDataRole.EditRole)
        else:
            pass

class BlockParametersTableModel(QtCore.QAbstractTableModel):
    """
    Table model that exposes the selected block variables, equations, and parameters.
    """

    block_updated = Signal(object)

    def __init__(self,
                 var_factory: VarFactory,
                 parent: Optional[QtCore.QObject] = None):
        """
        Build the side-panel parameter table model.

        :param var_factory:
        :param parent:
        """
        super().__init__(parent)
        self.var_factory: VarFactory = var_factory
        self.block: Block | None = None
        self.rows: List[BlockParameterRow] = list()
        self.headers: List[str] = ["Name", "Value", "Kind"]

    def set_block(self, block: Block | None) -> None:
        """
        Set the block whose parameters are shown in the table.

        :param block:
        :return:
        """
        self.beginResetModel()
        self.block = block
        self.rows = self.build_rows()
        self.endResetModel()

    def build_rows(self) -> List[BlockParameterRow]:
        """
        Build the visible rows for the current block.

        :return:
        """
        rows: List[BlockParameterRow] = list()
        var: Var
        expr: Expr | Const
        const: Const
        equation: Expr
        index: int

        if self.block is not None:
            rows.append(self.build_section_row("State Vars"))
            for var in self.block.state_vars:
                rows.append(BlockParameterRow(
                    name=var.name,
                    kind=BlockParameterKind.STATE_VAR,
                    key_var=var,
                    value="",
                    editable_name=True,
                    editable_value=False,
                    value_type=str
                ))

            rows.append(self.build_section_row("Algebraic Vars"))
            for var in self.block.algebraic_vars:
                rows.append(BlockParameterRow(
                    name=var.name,
                    kind=BlockParameterKind.ALGEBRAIC_VAR,
                    key_var=var,
                    value="",
                    editable_name=True,
                    editable_value=False,
                    value_type=str
                ))

            rows.append(self.build_section_row("Input Vars"))
            for var in self.block.in_vars:
                rows.append(BlockParameterRow(
                    name=var.name,
                    kind=BlockParameterKind.INPUT_VAR,
                    key_var=var,
                    value="",
                    editable_name=True,
                    editable_value=False,
                    value_type=str
                ))

            rows.append(self.build_section_row("Output Vars"))
            for var in self.block.out_vars:
                rows.append(BlockParameterRow(
                    name=var.name,
                    kind=BlockParameterKind.OUTPUT_VAR,
                    key_var=var,
                    value="",
                    editable_name=True,
                    editable_value=False,
                    value_type=str
                ))

            rows.append(self.build_section_row("State Equations"))
            for index, equation in enumerate(self.block.state_eqs):
                rows.append(BlockParameterRow(
                    name=f"State Eq {index + 1}",
                    kind=BlockParameterKind.STATE_EQUATION,
                    key_var=None,
                    value=equation,
                    editable_name=False,
                    editable_value=False,
                    value_type=str,
                    item_index=index
                ))

            rows.append(self.build_section_row("Algebraic Equations"))
            for index, equation in enumerate(self.block.algebraic_eqs):
                rows.append(BlockParameterRow(
                    name=f"Algebraic Eq {index + 1}",
                    kind=BlockParameterKind.ALGEBRAIC_EQUATION,
                    key_var=None,
                    value=equation,
                    editable_name=False,
                    editable_value=False,
                    value_type=str,
                    item_index=index
                ))

            rows.append(self.build_section_row("Parameters"))
            for var, expr in self.block.event_dict.items():
                if isinstance(expr, Const):
                    rows.append(BlockParameterRow(
                        name=var.name,
                        kind=BlockParameterKind.EVENT_PARAMETER,
                        key_var=var,
                        value=expr.value,
                        editable_name=True,
                        editable_value=True,
                        value_type=self.get_python_value_type(expr.value)
                    ))
                else:
                    rows.append(BlockParameterRow(
                        name=var.name,
                        kind=BlockParameterKind.EVENT_PARAMETER,
                        key_var=var,
                        value=expr,
                        editable_name=True,
                        editable_value=False,
                        value_type=str
                    ))

            for var, const in self.block.parameters.items():
                rows.append(BlockParameterRow(
                    name=var.name,
                    kind=BlockParameterKind.FIXED_PARAMETER,
                    key_var=var,
                    value=const.value,
                    editable_name=True,
                    editable_value=True,
                    value_type=self.get_python_value_type(const.value)
                ))
        else:
            pass

        return rows

    def build_section_row(self, title: str) -> BlockParameterRow:
        """
        Build a non-editable section row.

        :param title:
        :return:
        """
        return BlockParameterRow(
            name=title,
            kind=BlockParameterKind.SECTION,
            key_var=None,
            value="",
            editable_name=False,
            editable_value=False,
            value_type=str
        )

    def get_row(self, row_index: int) -> BlockParameterRow | None:
        """
        Return the row descriptor for a given table row.

        :param row_index:
        :return:
        """
        if 0 <= row_index < len(self.rows):
            return self.rows[row_index]
        else:
            return None

    def update_expression_row(self, row_index: int, expression: Expr) -> None:
        """
        Replace an expression row value and propagate it into the selected block.

        :param row_index:
        :param expression:
        :return:
        """
        row_data: BlockParameterRow | None = self.get_row(row_index)
        top_left: QtCore.QModelIndex
        bottom_right: QtCore.QModelIndex

        if row_data is not None and self.block is not None:
            if row_data.kind == BlockParameterKind.STATE_EQUATION and row_data.item_index is not None:
                self.block.state_eqs[row_data.item_index] = expression
                row_data.value = expression
            elif row_data.kind == BlockParameterKind.ALGEBRAIC_EQUATION and row_data.item_index is not None:
                self.block.algebraic_eqs[row_data.item_index] = expression
                row_data.value = expression
            elif row_data.kind in {BlockParameterKind.EVENT_PARAMETER, BlockParameterKind.FIXED_PARAMETER} and row_data.key_var is not None:
                if row_data.kind == BlockParameterKind.EVENT_PARAMETER:
                    self.block.event_dict[row_data.key_var] = expression
                else:
                    if isinstance(expression, Const):
                        self.block.parameters[row_data.key_var] = expression
                    else:
                        raise ValueError("Fixed parameters only support constant values.")

                row_data.value = expression
            else:
                return

            top_left = self.index(row_index, 1)
            bottom_right = self.index(row_index, 1)
            self.dataChanged.emit(top_left, bottom_right, [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole])
            self.block_updated.emit(self.block.uid)
        else:
            pass

    def add_new_variable(self, name: str, category: str, parameter_value: float = 0.0) -> None:
        """
        Add a new symbol into the selected block and refresh the table.

        :param name:
        :param category:
        :param parameter_value:
        :return:
        """
        new_var: Var

        if self.block is None:
            raise ValueError("No block is currently selected.")
        elif len(name.strip()) == 0:
            raise ValueError("The symbol name cannot be empty.")
        elif not is_valid_symbol_name(name):
            raise ValueError("The symbol name must be a valid identifier.")
        elif block_namespace_contains_name(self.block, name):
            raise ValueError(f"The symbol '{name}' already exists in this block.")
        else:
            new_var = self.var_factory.add_var(name=name)
            add_variable_to_block(
                block=self.block,
                var=new_var,
                var_type=category,
                parameter_value=parameter_value
            )
            self.set_block(self.block)
            self.block_updated.emit(self.block.uid)

    def rename_variable(self, row_data: BlockParameterRow, new_name: str) -> None:
        """
        Rename a block variable or parameter symbol.

        :param row_data:
        :param new_name:
        :return:
        """
        if self.block is None or row_data.key_var is None:
            raise ValueError("No symbol is available to rename.")

        normalized_name: str = new_name.strip()

        if len(normalized_name) == 0:
            raise ValueError("The symbol name cannot be empty.")
        elif not is_valid_symbol_name(normalized_name):
            raise ValueError("The symbol name must be a valid identifier.")
        elif block_namespace_contains_name(self.block, normalized_name, exclude_var=row_data.key_var):
            raise ValueError(f"The symbol '{normalized_name}' already exists in this block.")
        else:
            row_data.key_var.name = normalized_name
            row_data.name = normalized_name

            if row_data.kind == BlockParameterKind.FIXED_PARAMETER:
                const_value: Const | None = self.block.parameters.get(row_data.key_var, None)
                if const_value is not None:
                    const_value.name = normalized_name
            elif row_data.kind == BlockParameterKind.EVENT_PARAMETER:
                event_value: Expr | None = self.block.event_dict.get(row_data.key_var, None)
                if isinstance(event_value, Const):
                    event_value.name = normalized_name

    def set_numeric_parameter_value(self, row_data: BlockParameterRow, value: Any) -> Any:
        """
        Update the value of a parameter row backed by a constant.

        :param row_data:
        :param value:
        :return:
        """
        if row_data.key_var is None:
            raise ValueError("The selected parameter row has no symbol.")

        if row_data.value_type is float:
            new_value: Any = float(value)
        elif row_data.value_type is int:
            new_value = int(value)
        else:
            new_value = str(value)

        new_const: Const = self.var_factory.add_const(
            value=new_value,
            name=row_data.key_var.name
        )

        if self.block is not None:
            if row_data.kind == BlockParameterKind.EVENT_PARAMETER:
                self.block.event_dict[row_data.key_var] = new_const
            elif row_data.kind == BlockParameterKind.FIXED_PARAMETER:
                self.block.parameters[row_data.key_var] = new_const
            else:
                raise ValueError("The selected row is not a parameter row.")

        row_data.value = new_value

    def get_python_value_type(self, value: Any) -> type:
        """
        Normalize the editor type used for a parameter value.

        :param value:
        :return:
        """
        if isinstance(value, bool):
            return str
        elif isinstance(value, int):
            return int
        elif isinstance(value, float):
            return float
        else:
            return str

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """
        Return the visible row count.

        :param parent:
        :return:
        """
        if parent.isValid():
            return 0
        else:
            return len(self.rows)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        """
        Return the visible column count.

        :param parent:
        :return:
        """
        if parent.isValid():
            return 0
        else:
            return len(self.headers)

    def data(self,
             index: QtCore.QModelIndex,
             role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Return the data requested by the Qt view.

        :param index:
        :param role:
        :return:
        """
        row_data: BlockParameterRow

        if index.isValid():
            row_data = self.rows[index.row()]

            if role == QtCore.Qt.ItemDataRole.DisplayRole or role == QtCore.Qt.ItemDataRole.EditRole:
                if index.column() == 0:
                    return row_data.name
                elif index.column() == 1:
                    if row_data.value is None:
                        return ""
                    elif isinstance(row_data.value, Expr):
                        return symbolic_to_string(row_data.value)
                    else:
                        return row_data.value
                elif index.column() == 2:
                    if row_data.is_section:
                        return ""
                    else:
                        return row_data.kind.value
                else:
                    return None
            elif role == PARAMETER_VALUE_TYPE_ROLE and index.column() == 1:
                if row_data.value_type is float:
                    return "float"
                elif row_data.value_type is int:
                    return "int"
                else:
                    return "text"
            elif role == PARAMETER_EDITABLE_ROLE and index.column() == 1:
                return row_data.editable_value
            elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
                if row_data.is_section:
                    return QColor("#dce6f2")
                elif row_data.kind == BlockParameterKind.FIXED_PARAMETER:
                    return QColor("#f7fafc")
                else:
                    return None
            elif role == QtCore.Qt.ItemDataRole.FontRole and row_data.is_section:
                font: QtGui.QFont = QtGui.QFont("DejaVu Sans", 9)
                font.setBold(True)
                return font
            elif role == QtCore.Qt.ItemDataRole.ForegroundRole and row_data.is_section:
                return QColor("#333333")
            else:
                return None
        else:
            return None

    def headerData(self,
                   section: int,
                   orientation: QtCore.Qt.Orientation,
                   role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Return table header data.

        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return self.headers[section]
            else:
                return str(section + 1)
        else:
            return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """
        Return the Qt flags for a parameter cell.

        :param index:
        :return:
        """
        if index.isValid():
            row_data: BlockParameterRow = self.rows[index.row()]

            flags: QtCore.Qt.ItemFlag = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

            if index.column() == 0 and row_data.editable_name:
                flags |= QtCore.Qt.ItemFlag.ItemIsEditable
            elif index.column() == 1 and row_data.editable_value:
                flags |= QtCore.Qt.ItemFlag.ItemIsEditable
            else:
                pass

            return flags
        else:
            return QtCore.Qt.ItemFlag.NoItemFlags

    def setData(self,
                index: QtCore.QModelIndex,
                value: Any,
                role: int = QtCore.Qt.ItemDataRole.EditRole) -> bool:
        """
        Update an editable parameter value in the selected block.

        :param index:
        :param value:
        :param role:
        :return:
        """
        row_data: BlockParameterRow
        new_value: Any

        if index.isValid() and role == QtCore.Qt.ItemDataRole.EditRole:
            row_data = self.rows[index.row()]

            try:
                if self.block is None or row_data.is_section:
                    return False
                elif index.column() == 0 and row_data.editable_name:
                    self.rename_variable(row_data, str(value))
                elif index.column() == 1 and row_data.editable_value:
                    new_value = self.set_numeric_parameter_value(row_data, value)
                    row_data.value = new_value
                elif index.column() == 1 and row_data.kind in {
                    BlockParameterKind.STATE_EQUATION,
                    BlockParameterKind.ALGEBRAIC_EQUATION,
                    BlockParameterKind.EVENT_PARAMETER,
                    BlockParameterKind.FIXED_PARAMETER,
                }:
                    parsed_expression: Expr | Comparison = string_to_symbolic(str(value), build_block_symbol_namespace(self.block))
                    if isinstance(parsed_expression, Comparison):
                        self.update_expression_row(index.row(), parsed_expression.to_expression())
                    else:
                        self.update_expression_row(index.row(), parsed_expression)
                    return True
                else:
                    return False

                self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole])
                self.block_updated.emit(self.block.uid)
                return True
            except Exception:
                return False
        else:
            return False



class InspectModel(QWidget):
    """
    InspectModel
    """

    def __init__(self, block: Block, parent=None):
        super().__init__(parent)

        self.block = block  # DynamicModelHost

        main_layout = QHBoxLayout(self)
        self.setLayout(main_layout)

        # ----------------- LEFT PANEL -----------------
        left_panel = QVBoxLayout()
        main_layout.addLayout(left_panel)

        # Variables
        var_header_layout = QHBoxLayout()
        var_label = QLabel("Variables")
        var_header_layout.addWidget(var_label)
        left_panel.addLayout(var_header_layout)

        self.list_vars = QListWidget()
        left_panel.addWidget(self.list_vars)

        # Parameters (table)
        param_header_layout = QHBoxLayout()
        param_label = QLabel("Parameters")
        param_header_layout.addWidget(param_label)
        left_panel.addLayout(param_header_layout)

        self.table_params = QTableWidget()
        self.table_params.setColumnCount(2)
        self.table_params.setHorizontalHeaderLabels(["Name", "Value"])
        self.table_params.horizontalHeader().setStretchLastSection(True)
        self.table_params.verticalHeader().setVisible(False)
        self.table_params.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # make read-only for now
        left_panel.addWidget(self.table_params)

        # ----------------- RIGHT PANEL -----------------
        right_panel = QVBoxLayout()
        main_layout.addLayout(right_panel)

        eqn_header_layout = QHBoxLayout()
        eqn_label = QLabel("Equations")
        eqn_header_layout.addWidget(eqn_label)
        right_panel.addLayout(eqn_header_layout)

        self.list_eqns = QListWidget()
        right_panel.addWidget(self.list_eqns)

        # Initial population
        self.refresh_lists(self.block)

    def refresh_lists(self, model=None, clear=True):
        """Load current model variables, parameters, equations into lists."""
        if model is None:
            model = self.block

        if clear:
            self.list_vars.clear()
            self.table_params.setRowCount(0)
            self.list_eqns.clear()

        # --- Variables ---
        for var in model.state_vars + model.algebraic_vars:
            item = QListWidgetItem(f"{var.name} ")
            # ({'state' if var in model.state_vars else 'algebraic'})
            self.list_vars.addItem(item)

        # --- Parameters ---
        for param, value in model.parameters.items():
            row = self.table_params.rowCount()
            self.table_params.insertRow(row)
            self.table_params.setItem(row, 0, QTableWidgetItem(str(param)))
            self.table_params.setItem(row, 1, QTableWidgetItem(str(model.parameters[param])))

        for param, value in model.event_dict.items():
            row = self.table_params.rowCount()
            self.table_params.insertRow(row)
            self.table_params.setItem(row, 0, QTableWidgetItem(param.name))
            self.table_params.setItem(row, 1, QTableWidgetItem(str(model.event_dict[param])))

        # --- Equations ---
        for eq in model.state_eqs + model.algebraic_eqs:
            eq_type = "state" if eq in model.state_eqs else "algebraic"
            item = QListWidgetItem(f"{symbolic_to_string(eq)} ({eq_type})")
            self.list_eqns.addItem(item)

        # Recurse into submodels
        for submodel in getattr(model, "children", []):
            self.refresh_lists(submodel, clear=False)


class GenericBlockItem(QGraphicsRectItem):
    """
           Class to represent generic block to construct devices in the editor
           :param name:
           """

    def __init__(self,
                 var_factory: VarFactory,
                 block: Block,
                 api_object,
                 mode: DynamicEditorMode,
                 position_changed_callback=None
                 ):
        """

        :param var_factory:
        :param block_sys:
        :param api_object_name:
        :param api_object:
        :param templates_list:
        :param templates_catalogue:
        :param position_changed_callback:
        """
        super().__init__(0, 0, 100, 60)

        # ------------------------
        # API
        # ------------------------
        self.var_factory = var_factory
        self.block = block
        self.mode = mode
        self.api_object = api_object
        self.position_changed_callback = position_changed_callback

        self.resize_handle: ResizeHandle | None = None
        self.resizing_from_handle = False

        self.name_item = QGraphicsTextItem(self.block.name, self)
        self.inputs: List[PortItem] = list()
        self.outputs: List[PortItem] = list()

        self.editor_window = DynamicBlockEditorGUI(
            var_factory=self.var_factory,
            block=self.block,
            api_object=self.api_object,
            mode=self.mode
        )

        self.setBrush(QBrush(QColor("#C0C0C0")))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
        )
        self.setAcceptHoverEvents(True)
        self.name_item.setPos(10, 5)

        n_inputs = len(self.block.in_vars)
        n_outputs = len(self.block.out_vars)

        self.inputs = [PortItem(self, True, i, n_inputs) for i in range(n_inputs)]
        self.outputs = [PortItem(self, False, i, n_outputs) for i in range(n_outputs)]

        # --- assign tooltips to portItems with the assigned variable name ---
        for i, port in enumerate(self.inputs):
            var_name = self.block.in_vars[i].name
            port.setToolTip(f"Input {i}: {var_name}")

        for i, port in enumerate(self.outputs):
            var_name = self.block.out_vars[i].name
            port.setToolTip(f"Output {i}: {var_name}")

        self.resize_handle = ResizeHandle(self)

        super().setRect(0, 0, 100, 60)
        self.update_ports()
        self.update_handle_position()

    @property
    def subsys(self):
        return self.block

    def mouseDoubleClickEvent(self, event):
        """
        opens the editor
        Parameters
        ----------
        event :

        Returns
        -------

        """
        self.editor_window.show()

    def resize_block(self, width, height):
        # Update geometry safely
        self.prepareGeometryChange()
        min_width: float
        min_height: float
        min_width, min_height = self.get_minimum_block_size()
        QGraphicsRectItem.setRect(self, 0, 0, max(width, min_width), max(height, min_height))
        self.update_ports()
        self.update_handle_position()

    def update_handle_position(self):
        rect = self.rect()
        self.resizing_from_handle = False
        self.resize_handle.setPos(rect.width(), rect.height())
        self.resizing_from_handle = True

    def _set_rect_internal(self, w, h):
        QGraphicsRectItem.setRect(self, 0, 0, w, h)
        self.update_ports()
        self.update_handle_position()

    def set_rectangle(self, x, y, w, h):
        if not getattr(self, '_suppress_resize', False):
            self._set_rect_internal(w, h)

    def get_minimum_block_size(self) -> tuple[float, float]:
        """
        Compute the minimum generic block size required by its ports.

        :return:
        """
        port_rows: int = max(len(self.inputs), len(self.outputs), 1)
        min_height: float = max(
            BLOCK_MIN_HEIGHT,
            BLOCK_HEADER_HEIGHT + BLOCK_PORT_SECTION_PADDING + port_rows * BLOCK_PORT_ROW_HEIGHT
        )
        return BLOCK_MIN_WIDTH, min_height

    def update_ports(self):
        for i, port in enumerate(self.inputs):
            spacing = self.rect().height() / (len(self.inputs) + 1)
            port.setPos(0, spacing * (i + 1))
        for i, port in enumerate(self.outputs):
            spacing = self.rect().height() / (len(self.outputs) + 1)
            port.setPos(self.rect().width(), spacing * (i + 1))
        self.update_handle_position()
        # Also update connections
        for port in self.inputs + self.outputs:
            if port.connections:
                for conn in port.connections:
                    conn.update_path()

    def hoverEnterEvent(self, event):
        QApplication.setOverrideCursor(Qt.CursorShape.OpenHandCursor)

    def hoverLeaveEvent(self, event):
        QApplication.restoreOverrideCursor()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            for port in self.inputs + self.outputs:
                if port.connections:
                    for conn in port.connections:
                        conn.update_path()
            if self.position_changed_callback is not None:
                self.position_changed_callback(value.x(), value.y())
        return super().itemChange(change, value)


class BlockItem(QGraphicsRectItem):
    """
    Graphics item representing a symbolic block.
    """

    def __init__(self, var_factory: VarFactory, name: str, position_changed_callback=None):
        """
        Build the graphical block item.

        :param var_factory:
        :param name:
        :param position_changed_callback:
        """
        super().__init__(0, 0, 100, 60)

        self.var_factory: VarFactory = var_factory
        self.name: str = name
        self.position_changed_callback = position_changed_callback
        self.resize_handle: ResizeHandle | None = None
        self.resizing_from_handle: bool = False
        self.subsys: Block | None = None
        self.name_item: QGraphicsTextItem | None = None
        self.inputs: List[PortItem] = list()
        self.outputs: List[PortItem] = list()
        self.input_labels: List[QGraphicsTextItem] = list()
        self.output_labels: List[QGraphicsTextItem] = list()

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
            self.input_labels = [self.create_port_label_item() for _ in range(n_inputs)]
            self.output_labels = [self.create_port_label_item() for _ in range(n_outputs)]
            self.refresh_port_metadata()

            self.resize_handle = ResizeHandle(self)
            self.resize_to_content()
        else:
            pass

    def create_port_label_item(self) -> QGraphicsTextItem:
        """
        Create a compact label item used beside a port.

        :return:
        """
        label_item: QGraphicsTextItem = QGraphicsTextItem("", self)
        label_font: QtGui.QFont = QtGui.QFont("DejaVu Sans", 7)
        label_item.setFont(label_font)
        label_item.setDefaultTextColor(PORT_LABEL_COLOR)
        label_item.setZValue(4)
        return label_item

    def get_minimum_block_size(self) -> tuple[float, float]:
        """
        Compute the minimum block size required by the port count.

        :return:
        """
        port_rows: int = max(len(self.inputs), len(self.outputs), 1)
        min_height: float = max(
            BLOCK_MIN_HEIGHT,
            BLOCK_HEADER_HEIGHT + BLOCK_PORT_SECTION_PADDING + port_rows * BLOCK_PORT_ROW_HEIGHT
        )
        return BLOCK_MIN_WIDTH, min_height

    def resize_to_content(self) -> None:
        """
        Resize the block to the minimum size required by its ports.

        :return:
        """
        min_width: float
        min_height: float
        min_width, min_height = self.get_minimum_block_size()
        QGraphicsRectItem.setRect(self, 0, 0, min_width, min_height)
        self.update_ports()
        self.update_handle_position()

    def refresh_port_metadata(self) -> None:
        """
        Refresh tooltips and visible labels for all ports.

        :return:
        """
        i: int
        port: PortItem
        label_item: QGraphicsTextItem
        variable_name: str

        if self.subsys is not None:
            for i, port in enumerate(self.inputs):
                if port.base_var is None:
                    port.base_var = self.subsys.in_vars[i]
                else:
                    pass

                variable_name = self.subsys.in_vars[i].name
                port.setToolTip(f"Input {i}: {variable_name}")
                label_item = self.input_labels[i]
                label_item.setPlainText(truncate_port_label(variable_name))

            for i, port in enumerate(self.outputs):
                if port.base_var is None:
                    port.base_var = self.subsys.out_vars[i]
                else:
                    pass

                variable_name = self.subsys.out_vars[i].name
                port.setToolTip(f"Output {i}: {variable_name}")
                label_item = self.output_labels[i]
                label_item.setPlainText(truncate_port_label(variable_name))
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
        Keep double click on a regular block as a passive scene interaction.

        :param event:
        :return:
        """
        super().mouseDoubleClickEvent(event)
    # def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
    #     """
    #     Open the parameter editor for the current block.
    #
    #     :param event:
    #     :return:
    #     """
    #     if self.subsys is not None:
    #         dialog: ParameterEditorDialog = ParameterEditorDialog(
    #             var_factory=self.var_factory,
    #             event_dict=self.subsys.event_dict,
    #             parameters_dict=self.subsys.parameters,
    #             parent=None
    #         )
    #
    #         if dialog.exec() == QDialog.DialogCode.Accepted:
    #             self.subsys.event_dict = dialog.event_dict
    #             self.subsys.parameters = dialog.parameters
    #         else:
    #             pass
    #
    #         event.accept()
    #     else:
    #         pass
    #
    #     super().mouseDoubleClickEvent(event)

    def resize_block(self, width: float, height: float) -> None:
        """
        Resize the block geometry and keep ports aligned.

        :param width:
        :param height:
        :return:
        """
        self.prepareGeometryChange()
        min_width: float
        min_height: float
        min_width, min_height = self.get_minimum_block_size()
        QGraphicsRectItem.setRect(self, 0, 0, max(width, min_width), max(height, min_height))
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
        input_spacing: float
        output_spacing: float
        port_section_height: float = max(self.rect().height() - BLOCK_HEADER_HEIGHT - 8.0, 1.0)

        for i, port in enumerate(self.inputs):
            input_spacing = port_section_height / (len(self.inputs) + 1)
            port.setPos(0, BLOCK_HEADER_HEIGHT + input_spacing * (i + 1))

        for i, port in enumerate(self.outputs):
            output_spacing = port_section_height / (len(self.outputs) + 1)
            port.setPos(self.rect().width(), BLOCK_HEADER_HEIGHT + output_spacing * (i + 1))

        for i, label_item in enumerate(self.input_labels):
            port = self.inputs[i]
            label_item.setPos(14.0, port.pos().y() - 8.0)

        for i, label_item in enumerate(self.output_labels):
            port = self.outputs[i]
            label_width: float = label_item.boundingRect().width()
            label_item.setPos(self.rect().width() - label_width - 14.0, port.pos().y() - 8.0)

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
            if self.position_changed_callback is not None:
                self.position_changed_callback(value.x(), value.y())
            return super().itemChange(change, value)
        else:
            return super().itemChange(change, value)


class GraphicsView(QGraphicsView):
    """
    Graphics view with zoom and middle-button pan.
    """

    ZOOM_FACTOR: float = 1.15

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
        self.apply_zoom(zoom_in)

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

    def apply_zoom(self, zoom_in: bool) -> None:
        """
        Apply a zoom step to the view.

        :param zoom_in:
        :return:
        """
        zoom_factor: float

        if zoom_in:
            zoom_factor = self.ZOOM_FACTOR
        else:
            zoom_factor = 1.0 / self.ZOOM_FACTOR

        self.scale(zoom_factor, zoom_factor)

    def zoom_in(self) -> None:
        """
        Zoom into the current view.

        :return:
        """
        self.apply_zoom(True)

    def zoom_out(self) -> None:
        """
        Zoom out from the current view.

        :return:
        """
        self.apply_zoom(False)

    def center_items(self) -> None:
        """
        Fit the view to the selected block items or, if none are selected, to all block items.

        :return:
        """
        target_items: List[QGraphicsItem]
        target_rect: QtCore.QRectF
        item: QGraphicsItem
        block_items: List[QGraphicsItem] = list()
        margin_x: float
        margin_y: float

        target_items = self.scene().selectedItems()

        if len(target_items) == 0:
            for item in self.scene().items():
                if isinstance(item, (BlockItem, GenericBlockItem)):
                    block_items.append(item)
                else:
                    pass

            target_items = block_items
        else:
            target_items = [item for item in target_items if isinstance(item, (BlockItem, GenericBlockItem))]

        if len(target_items) > 0:
            target_rect = QtCore.QRectF()

            for item in target_items:
                if target_rect.isNull():
                    target_rect = item.sceneBoundingRect()
                else:
                    target_rect = target_rect.united(item.sceneBoundingRect())

            margin_x = max(target_rect.width() * 0.08, 30.0)
            margin_y = max(target_rect.height() * 0.08, 30.0)
            target_rect = target_rect.adjusted(-margin_x, -margin_y, margin_x, margin_y)
            self.fitInView(target_rect, Qt.AspectRatioMode.KeepAspectRatio)
        else:
            pass


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
                path: QPainterPath = build_orthogonal_connection_path(start, end)
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
            connection: ConnectionItem = ConnectionItem(
                source_port, target_port,
                diagram=self.editor.diagram
            )
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
            target_block.refresh_port_metadata()
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
    __slots__ = ("_block_role", "_mime_type", "_drag_token_role", "_drag_payloads")

    def __init__(self, block_role: int, mime_type: str):
        """
        Build the library tree model

        :param block_role:
        :param mime_type:
        """
        super().__init__()
        self._block_role = block_role
        self._mime_type = mime_type
        self._drag_token_role = block_role + 1
        self._drag_payloads: Dict[str, object] = dict()

        self.setHorizontalHeaderLabels(["Models Library"])

    def register_drag_payload(self, item: QtGui.QStandardItem, payload: object) -> None:
        """
        Register a draggable payload and attach its token to the tree item.

        :param item:
        :param payload:
        :return:
        """
        token: str = str(_new_uid())
        self._drag_payloads[token] = payload
        item.setData(payload, self._block_role)
        item.setData(token, self._drag_token_role)

    def get_drag_payload(self, token: str) -> object | None:
        """
        Resolve a dragged token back into the original payload object.

        :param token:
        :return:
        """
        return self._drag_payloads.get(token, None)

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """
        Get the Qt flags for an item.

        :param index:
        """

        if index.isValid():

            item: QtGui.QStandardItem | None = self.itemFromIndex(index)
            if item is not None:
                item_data: object = item.data(self._block_role)
                if is_supported_library_payload(item_data):
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
                    item_token: object = item.data(self._drag_token_role)
                    item_data: object = item.data(self._block_role)
                    if isinstance(item_token, str) and is_supported_library_payload(item_data):
                        mime_data.setData(self._mime_type, QtCore.QByteArray(item_token.encode("utf-8")))
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

    # block_added = Signal(object)

    def __init__(self,
                 var_factory: VarFactory,
                 block: Block,
                 api_object: ALL_DEV_TYPES | None = None,
                 mode: DynamicEditorMode = DynamicEditorMode.RMS,
                 templates_list: Optional[List[RmsModelTemplate | EmtModelTemplate]] = None,
                 main_editor=False,
                 modal: bool = True):
        """
        Initializes a dynamic block editor window used for editing and managing blocks within a graphical model.

        This constructor sets up the user interface, initializes required attributes, creates a library model
        for draggable block items, and optionally constructs a tree structure based on the specified mode.
        It also configures drag-and-drop functionality for graphical items, connects various UI components
        to their associated event handlers, and reconstructs the scene from an existing diagram.

        :param var_factory: Factory object responsible for variable creation and management.
        :type var_factory: VarFactory
        :param block: The original block to be edited.
        :type block: Block
        :param api_object: Optional API object associated with the dynamic model.
        :type api_object: ALL_DEV_TYPES | None
        :param mode: Specifies the editor mode, either RMS or EMT.
        :type mode: DynamicEditorMode
        :param main_editor: Indicates whether this instance is the main editor for the block.
        :type main_editor: bool
        :param modal: Specifies whether the editor window should be modal.
        :type modal: bool
        """
        super().__init__()

        self.ui = Ui_BlockEditorWindow()
        self.ui.setupUi(self)

        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        # set object label
        if api_object is not None:
            self.ui.deviceLabel.setText(api_object.name)
        else:
            self.ui.deviceLabel.setText("")

        self.block_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 300
        self.mime_type: str = "application/x-veragrid-dynamics-block"

        self.setWindowTitle("Dynamic Model Editor")

        self.ui.splitter.setStretchFactor(0, 1)
        self.ui.splitter.setStretchFactor(1, 10)
        self.ui.block_editor_actionCheckModel.triggered.connect(self.open_inspect_dialog)
        self.ui.actionCenter.triggered.connect(self.center_view_on_items)
        self.ui.actionZoom_in.triggered.connect(self.zoom_in_view)
        self.ui.actionZoom_out.triggered.connect(self.zoom_out_view)

        self.var_factory = var_factory
        # Todo: is this correct?
        self.original_block: Block = block  # api_object.rms_model
        self.main_block: Block = clone_block_for_editing(block)

        self.diagram: BlockDiagram = self.main_block.diagram
        self.api_object = api_object
        self.mode = mode
        self.main_editor = main_editor
        self.block_counters: Dict[BlockType, int] = dict()
        self.scene: DiagramScene = DiagramScene(self)
        self.changes_applied: bool = False
        self.parameters_table_model: BlockParametersTableModel = BlockParametersTableModel(
            var_factory=self.var_factory,
            parent=self.ui.parametersTableView
        )
        self.parameters_toolbar_widget: QWidget = QWidget(self.ui.tab_2)
        self.parameters_toolbar_layout: QHBoxLayout = QHBoxLayout(self.parameters_toolbar_widget)
        self.parameters_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.add_symbol_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Add Variable", self.parameters_toolbar_widget)
        self.parameters_hint_label: QLabel = QLabel("Select one block to edit its symbols and equations.", self.parameters_toolbar_widget)
        self.parameters_toolbar_layout.addWidget(self.add_symbol_button)
        self.parameters_toolbar_layout.addWidget(self.parameters_hint_label)
        self.parameters_toolbar_layout.addStretch(1)

        self.templates_list: List[RmsModelTemplate | EmtModelTemplate] = templates_list if templates_list is not None else list()

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
                    ("Generic", BlockType.GENERIC),
                ],
            }
        elif mode == DynamicEditorMode.EMT:
            self.tree_structure = dict()
        else:
            self.tree_structure = dict()

        if self.templates_list:
            self.tree_structure["Templates"] = [(template.name, template) for template in self.templates_list]
        else:
            pass

        # build and add library model
        self.library_model = self.build_library_tree_model(
            block_role=self.block_role,
            mime_type=self.mime_type
        )

        self.ui.libraryTreeView.setModel(self.library_model)
        self.ui.libraryTreeView.expandAll()
        self.ui.libraryTreeView.setDragEnabled(True)
        self.ui.libraryTreeView.setHeaderHidden(False)


        self.ui.verticalLayout_2.insertWidget(0, self.parameters_toolbar_widget)
        self.ui.parametersTableView.setModel(self.parameters_table_model)
        self.ui.parametersTableView.setItemDelegateForColumn(
            1,
            BlockParameterValueDelegate(self.ui.parametersTableView)
        )
        self.ui.parametersTableView.horizontalHeader().setStretchLastSection(True)
        self.ui.parametersTableView.verticalHeader().setVisible(False)
        self.ui.parametersTableView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ui.parametersTableView.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.ui.parametersTableView.doubleClicked.connect(self.on_parameters_table_double_clicked)
        self.add_symbol_button.clicked.connect(self.open_add_variable_dialog)
        self.parameters_table_model.block_updated.connect(self.on_parameters_model_block_updated)
        self.add_symbol_button.setEnabled(False)



        self.ui.parametersTableView.horizontalHeader().setStretchLastSection(True)
        self.ui.parametersTableView.verticalHeader().setVisible(False)

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
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        if not self.main_block.diagram.node_data and self.main_editor:
            self.add_connection_vars()
            self.add_external_mapping_block()
            self.add_api_obj_mapping()
        self.rebuild_scene_from_diagram()

        # self.parameters_model = ParametersTreeModel(var_factory=self.var_factory, main_block=self.main_block)
        # self.ui.parametersTreeView.setModel(self.parameters_model)
        # self.ui.parametersTreeView.expandAll()
        #
        # # Conecta el signal del editor al métod de añadir bloque
        # self.block_added.connect(self.parameters_model.add_block)
        #
        #
        # self.ui.parametersTreeView.header().setStretchLastSection(True)
        # header = self.ui.parametersTreeView.header()
        # header.setStretchLastSection(True)
        # header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)

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

            for label, payload in blocks:
                item: QtGui.QStandardItem = QtGui.QStandardItem(label)
                item.setEditable(False)
                model.register_drag_payload(item, payload)
                cat_item.appendRow(item)

        return model

    def get_library_payload_from_mime_data(self,
                                           mime_data: QtCore.QMimeData) -> BlockType | RmsModelTemplate | EmtModelTemplate | None:
        """
        Decode the dragged library payload from the tree-view mime payload.

        :param mime_data:
        :return:
        """
        drag_token: str
        payload: object | None

        if mime_data.hasFormat(self.mime_type):
            drag_token = bytes(mime_data.data(self.mime_type)).decode("utf-8")
            payload = self.library_model.get_drag_payload(drag_token)

            if isinstance(payload, BlockType):
                return payload
            elif isinstance(payload, (RmsModelTemplate, EmtModelTemplate)):
                return payload
            else:
                return None
        else:
            return None

    def create_generic_block_item(self, block_type: BlockType, x_pos, y_pos) -> BlockItem:
        """
        Create and place a generic block item.

        :param block_type:
        :param x_pos:
        :param y_pos:
        :return:
        """

        dialog = GenericBlockDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, state_ins, state_outs, algeb_ins, algeb_outs = dialog.get_values()

            model = create_generic_block(self.var_factory, state_ins, state_outs, algeb_ins, algeb_outs)
            self.main_block.add(model)
            item = GenericBlockItem(
                var_factory=self.var_factory,
                block=model,
                api_object=self.api_object,
                mode=self.mode,
                position_changed_callback=lambda x, y: self.on_block_position_changed(model.uid, x, y)
            )

            item.setPos(QtCore.QPointF(x_pos, y_pos))
            self.scene.addItem(item)
            # save nodes in diagram
            self.diagram.add_node(
                name=name,
                x=x_pos,
                y=y_pos,
                device_uid=model.uid,
                tpe=block_type.name,
                state_ins=state_ins,
                state_outs=state_outs,
                algeb_ins=algeb_ins,
                algeb_outs=algeb_outs,
                subdiagram=model.diagram
            )

            # self.block_added.emit(item.subsys)

            return item
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
            block_item.position_changed_callback = lambda x, y: self.on_block_position_changed(block_model.uid, x, y)
            block_item.build_item()

            # The editor block is the authoritative model container for later save/rebuild steps.
            self.main_block.add(block_model)
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

            # self.block_added.emit(block_item.subsys)

            return block_item
        else:
            return None

    def create_template_block_item(self,
                                   template: RmsModelTemplate | EmtModelTemplate,
                                   x_pos: float,
                                   y_pos: float) -> BlockItem | None:
        """
        Create and place a copied template block in the canvas scene.

        :param template:
        :param x_pos:
        :param y_pos:
        :return:
        """
        item_name: str = template.name
        block_model: Block = clone_template_block(template.block)
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)

        if item_name:
            block_model.name = item_name
        else:
            item_name = block_model.name

        block_item.set_subsystem(block_model)
        block_item.position_changed_callback = lambda x, y: self.on_block_position_changed(block_model.uid, x, y)
        block_item.build_item()
        self.block.add(block_model)
        self.scene.addItem(block_item)
        block_item.setPos(QtCore.QPointF(x_pos, y_pos))
        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=TEMPLATE_NODE_TYPE,
            device_uid=block_model.uid
        )
        return block_item

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
            target_var: Var
            i: int
            eq: Expr

            if target_port.base_var is not None:
                target_var = target_port.base_var
            else:
                target_var = target_port.subsystem.subsys.in_vars[target_port.index]

            # The destination equations must be restored to the original local input variable.
            for i, eq in enumerate(target_port.subsystem.subsys.algebraic_eqs):
                target_port.subsystem.subsys.algebraic_eqs[i] = eq.subs({dst_var: target_var})

            for i, eq in enumerate(target_port.subsystem.subsys.state_eqs):
                target_port.subsystem.subsys.state_eqs[i] = eq.subs({dst_var: target_var})

            target_port.subsystem.subsys.in_vars[target_port.index] = target_var
            target_port.subsystem.refresh_port_metadata()
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

    def add_connection_vars(self):
        """
        Add a block with bus connection variables to connect the device
        :return:
        """
        bus_con_item = None
        tpe = BlockType.BUS_CONNECTION

        if isinstance(self.api_object, BranchParent):

            # add con bus from
            x0, y0 = 0, 0
            name = "Conn From"
            bus_from_con_item = BlockItem(var_factory=self.var_factory, name=name)

            if self.api_object.bus_from.rms_model.empty():
                initialize_bus_rms(self.api_object.bus_from, self.var_factory)

            Vmf, Vaf = get_bus_rms_algebraic_vars(self.api_object.bus_from.rms_model)

            bus_from_con_blk = Block(
                algebraic_vars=[Vmf, Vaf],
                out_vars=[Vmf, Vaf],
                name=name
            )

            self.main_block.add(bus_from_con_blk)

            bus_from_con_item.set_subsystem(bus_from_con_blk)
            bus_from_con_item.build_item()

            if bus_from_con_item.subsys is not None:
                bus_from_con_item.setPos(x0, y0)
                self.scene.addItem(bus_from_con_item)

                # save nodes in diagram
                self.diagram.add_node(
                    name=name,
                    x=x0,
                    y=y0,
                    tpe=tpe.name,
                    device_uid=bus_from_con_item.subsys.uid,
                )
            self.main_block.external_mapping.update(
                {VarPowerFlowRefferenceType.Vmf: Vmf})
            self.main_block.external_mapping.update(
                {VarPowerFlowRefferenceType.Vaf: Vaf})

            # add con bus to
            name = "Conn To"
            x0, y0 = 0, 100

            bus_to_con_item = BlockItem(var_factory=self.var_factory, name=name)

            if self.api_object.bus_to.rms_model.empty():
                initialize_bus_rms(self.api_object.bus_to, self.var_factory)

            Vmt, Vat = get_bus_rms_algebraic_vars(self.api_object.bus_to.rms_model)

            bus_to_con_blk = Block(
                algebraic_vars=[Vmt, Vat],
                out_vars=[Vmt, Vat],
                name=name
            )

            self.main_block.add(bus_to_con_blk)

            bus_to_con_item.set_subsystem(bus_to_con_blk)
            bus_to_con_item.build_item()

            # Add to scene
            if bus_to_con_item.subsys is not None:
                bus_to_con_item.setPos(QPointF(x0, y0))
                self.scene.addItem(bus_to_con_item)

                # save nodes in diagram
                self.diagram.add_node(
                    name=name,
                    x=x0,
                    y=y0,
                    tpe=tpe.name,
                    device_uid=bus_to_con_item.subsys.uid,
                )

            self.main_block.external_mapping.update(
                {VarPowerFlowRefferenceType.Vmt: Vmt})
            self.main_block.external_mapping.update(
                {VarPowerFlowRefferenceType.Vat: Vat})

        elif isinstance(self.api_object, InjectionParent):
            x0, y0 = 0, 0
            name = "Conn Bus"
            bus_con_item = BlockItem(var_factory=self.var_factory, name=name)
            if self.api_object.bus.rms_model.empty():
                initialize_bus_rms(self.api_object.bus, self.var_factory)

            Vm, Va = get_bus_rms_algebraic_vars(self.api_object.bus.rms_model)

            bus_con_blk = Block(
                out_vars=[Vm, Va],
                name=name
            )

            self.main_block.add(bus_con_blk)

            bus_con_item.set_subsystem(bus_con_blk)
            bus_con_item.build_item()

            if bus_con_item.subsys is not None:
                bus_con_item.setPos(x0, y0)
                self.scene.addItem(bus_con_item)

                # save nodes in diagram
                self.diagram.add_node(
                    name=name,
                    x=x0,
                    y=y0,
                    tpe=tpe.name,
                    device_uid=bus_con_item.subsys.uid,
                )

            self.main_block.external_mapping.update(
                {VarPowerFlowRefferenceType.Vm: Vm})
            self.main_block.external_mapping.update(
                {VarPowerFlowRefferenceType.Va: Va})

        else:
            pass

    def add_external_mapping_block(self):
        """
        Add a block with the external mapping vars needed to connect the device to the grid
        :return:
        """
        bus_con_item = None
        tpe = BlockType.EXTERNAL_MAPPING

        if isinstance(self.api_object, BranchParent):

            # add mapping bus from
            x0, y0 = 200, 200
            name = "mapping From"
            bus_from_mapping_item = BlockItem(var_factory=self.var_factory, name=name)

            Pf = self.var_factory.add_var('Pf_placeholder')
            Qf = self.var_factory.add_var('Qf_placeholder')

            bus_from_mapping_blk = Block(
                in_vars=[Pf, Qf],
                name=name
            )

            self.main_block.add(bus_from_mapping_blk)

            bus_from_mapping_item.set_subsystem(bus_from_mapping_blk)
            bus_from_mapping_item.build_item()

            if bus_from_mapping_item.subsys is not None:
                self.scene.addItem(bus_from_mapping_item)
                bus_from_mapping_item.setPos(x0, y0)
                # save nodes in diagram
                self.diagram.add_node(
                    name=name,
                    x=x0,
                    y=y0,
                    tpe=tpe.name,
                    device_uid=bus_from_mapping_item.subsys.uid,
                )
            self.main_block.external_mapping.update({VarPowerFlowRefferenceType.Pf: bus_from_mapping_blk.in_vars[0]})
            self.main_block.external_mapping.update({VarPowerFlowRefferenceType.Qf: bus_from_mapping_blk.in_vars[1]})

            # add con bus to
            name = "mapping To"
            x0, y0 = 0, 200

            bus_to_mapping_item = BlockItem(var_factory=self.var_factory, name=name)

            bus_to_mapping_blk = Block(
                in_vars=[
                    self.var_factory.add_var('Pt_placeholder'),  # Pt
                    self.var_factory.add_var('Qt_placeholder')  # Qt
                ],
                name=name
            )
            self.main_block.add(bus_to_mapping_blk)

            bus_to_mapping_item.set_subsystem(bus_to_mapping_blk)
            bus_to_mapping_item.build_item()

            # Add to scene
            bus_to_mapping_item.setPos(QPointF(x0, y0))
            if bus_to_mapping_item.subsys is not None:
                self.scene.addItem(bus_to_mapping_item)
                bus_to_mapping_item.setPos(QPointF(x0, y0))
                # save nodes in diagram
                self.diagram.add_node(
                    name=name,
                    x=x0,
                    y=y0,
                    tpe=tpe.name,
                    device_uid=bus_to_mapping_item.subsys.uid,
                )
            self.main_block.external_mapping.update({VarPowerFlowRefferenceType.Pt: bus_to_mapping_blk.in_vars[0]})
            self.main_block.external_mapping.update({VarPowerFlowRefferenceType.Qt: bus_to_mapping_blk.in_vars[1]})

        elif isinstance(self.api_object, InjectionParent):
            x0, y0 = 0, 0
            name = "mapping Bus"

            bus_mapping_item = BlockItem(var_factory=self.var_factory, name=name)
            P = self.var_factory.add_var('P_placeholder')
            Q = self.var_factory.add_var('Q_placeholder')

            bus_mapping_blk = Block(
                in_vars=[P, Q],
                name=name
            )

            self.main_block.add(bus_mapping_blk)

            bus_mapping_item.set_subsystem(bus_mapping_blk)
            bus_mapping_item.build_item()

            if bus_mapping_item.subsys is not None:
                self.scene.addItem(bus_mapping_item)
                bus_mapping_item.setPos(x0, y0)
                # save nodes in diagram
                self.diagram.add_node(
                    name=name,
                    x=x0,
                    y=y0,
                    tpe=tpe.name,
                    device_uid=bus_mapping_item.subsys.uid,
                )
            self.main_block.external_mapping.update({VarPowerFlowRefferenceType.P: bus_mapping_blk.in_vars[0]})
            self.main_block.external_mapping.update({VarPowerFlowRefferenceType.Q: bus_mapping_blk.in_vars[1]})

        else:
            pass

    def add_api_obj_mapping(self):
        """
        Adds API object mapping for the main block based on the device type.

        This method checks the device type of the API object. If it matches the
        `DeviceType.LineDevice`, it performs the following actions:
        - Creates three new variables: g, b, and bsh using the variable factory.
        - Assigns constant values to these variables as parameters for the main block.
        - Maps the power flow reference type parameters to the corresponding newly
          created variables within the main block's API object mapping.

        :raises RuntimeError: Raised if required attributes or methods are missing.
        :return: None
        """
        if isinstance(self.api_object, BranchParent):
            g = self.var_factory.add_var("g")
            b = self.var_factory.add_var("b")
            bsh = self.var_factory.add_var("bsh")

            self.main_block.parameters[g] = self.var_factory.add_const(0.029585)
            self.main_block.parameters[b] = self.var_factory.add_const(0.0710059)
            self.main_block.parameters[bsh] = self.var_factory.add_const(0.03)

            self.main_block.api_obj_mapping = {
                ParamPowerFlowRefferenceType.g: g,
                ParamPowerFlowRefferenceType.b: b,
                ParamPowerFlowRefferenceType.bsh: bsh,
            }

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

    def on_block_position_changed(self, device_uid: int, x: float, y: float) -> None:
        """
        Update the diagram node position when a block is moved by the user.

        :param device_uid:
        :param x:
        :param y:
        :return:
        """
        if device_uid in self.diagram.node_data:
            self.diagram.node_data[device_uid].x = x
            self.diagram.node_data[device_uid].y = y
            print("")

    def get_selected_scene_block(self) -> Block | None:
        """
        Return the single selected block, if the current selection is unambiguous.

        :return:
        """
        selected_items: List[QGraphicsItem] = self.scene.selectedItems()
        selected_item: QGraphicsItem

        if len(selected_items) == 1:
            selected_item = selected_items[0]

            if isinstance(selected_item, BlockItem):
                return selected_item.subsys
            elif isinstance(selected_item, GenericBlockItem):
                return selected_item.subsys
            else:
                return None
        else:
            return None

    def on_parameters_table_double_clicked(self, index: QtCore.QModelIndex) -> None:
        """
        Open the expression text editor when the user double-clicks an expression row.

        :param index:
        :return:
        """
        row_data: BlockParameterRow | None = self.parameters_table_model.get_row(index.row())

        if row_data is not None:
            if row_data.opens_expression_editor and index.column() == 1:
                self.open_expression_row_editor(index.row())
            else:
                pass
        else:
            pass

    def open_add_variable_dialog(self) -> None:
        """
        Open the dialog used to add a new block symbol.

        :return:
        """
        dialog: AddBlockVariableDialog = AddBlockVariableDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.parameters_table_model.add_new_variable(
                    name=dialog.get_name(),
                    category=dialog.get_category(),
                    parameter_value=dialog.get_parameter_value()
                )
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Add Variable Error", str(exc))
        else:
            pass

    def open_expression_row_editor(self, row_index: int) -> None:
        """
        Open the expression text editor for a parameter-table row.

        :param row_index:
        :return:
        """
        row_data: BlockParameterRow | None = self.parameters_table_model.get_row(row_index)
        expression_text: str
        dialog: ExpressionTextEditorDialog
        symbol_namespace: Dict[str, Expr]
        parsed_expression: Expr | Comparison
        expression_value: Expr

        if row_data is not None and self.parameters_table_model.block is not None:
            if isinstance(row_data.value, Expr):
                # converts symbolic expression to text
                expression_text = symbolic_to_string(row_data.value)
                # save a dictionary [var.name, var]
                symbol_namespace = build_block_symbol_namespace(self.parameters_table_model.block)
                dialog = ExpressionTextEditorDialog(
                    expression_text=expression_text,
                    symbol_namespace=symbol_namespace,
                    parent=self
                )

                if dialog.exec() == QDialog.DialogCode.Accepted:
                    try:
                        parsed_expression = string_to_symbolic(dialog.get_expression_text(), symbol_namespace)

                        if isinstance(parsed_expression, Comparison):
                            expression_value = parsed_expression.to_expression()
                        else:
                            expression_value = parsed_expression

                        self.parameters_table_model.update_expression_row(row_index, expression_value)
                    except Exception as exc:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Expression Error",
                            str(exc)
                        )
                else:
                    pass
            else:
                pass
        else:
            pass

    def center_view_on_items(self) -> None:
        """
        Center the graphics view on the current selection or, if none exists, on all items.

        :return:
        """
        self.view.center_items()

    def zoom_in_view(self) -> None:
        """
        Zoom the graphics view in.

        :return:
        """
        self.view.zoom_in()

    def zoom_out_view(self) -> None:
        """
        Zoom the graphics view out.

        :return:
        """
        self.view.zoom_out()

    def on_scene_selection_changed(self) -> None:
        """
        Refresh the right-side parameters table from the selected block.

        :return:
        """
        selected_block: Block | None = self.get_selected_scene_block()
        self.parameters_table_model.set_block(selected_block)
        self.add_symbol_button.setEnabled(selected_block is not None)

    def get_scene_item_by_block_uid(self, block_uid: int) -> BlockItem | GenericBlockItem | None:
        """
        Find the visible scene item representing a block uid.

        :param block_uid:
        :return:
        """
        item: QGraphicsItem

        for item in self.scene.items():
            if isinstance(item, (BlockItem, GenericBlockItem)) and item.subsys is not None:
                if item.subsys.uid == block_uid:
                    return item
                else:
                    pass
            else:
                pass

        return None

    def select_block_by_uid(self, block_uid: int) -> None:
        """
        Restore the selection for a block after a scene refresh.

        :param block_uid:
        :return:
        """
        item: BlockItem | GenericBlockItem | None = self.get_scene_item_by_block_uid(block_uid)

        if item is not None:
            self.scene.clearSelection()
            item.setSelected(True)
        else:
            pass

    def on_parameters_model_block_updated(self, block_uid: int) -> None:
        """
        Refresh the scene after a block edit coming from the parameters tab.

        :param block_uid:
        :return:
        """
        self.rebuild_scene_from_diagram()
        self.select_block_by_uid(block_uid)

    def apply_changes(self) -> None:
        """
        Commit the edited working copy back into the original block.

        :return:
        """
        copy_block_state(source_block=self.main_block, target_block=self.original_block)
        self.changes_applied = True
        self.close()

    def open_inspect_dialog(self):
        """
        creates and opens the dialog containing the model info (read only)
        :return:
        """
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Inspect Model")
        dialog.resize(600, 400)

        # create layout
        layout = QVBoxLayout(dialog)

        # Instantiate inspector class
        inspect_widget = InspectModel(block=self.main_block, parent=dialog)

        # Add inspector to layout
        layout.addWidget(inspect_widget)

        # Add (OK / Cancel)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                      QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        # Show dialog
        dialog.exec()

    def rebuild_scene_from_diagram(self) -> None:
        """
        Rebuild the visible scene from the persisted block diagram.

        :return:
        """
        uid_to_blockitem: Dict[int, BlockItem | GenericBlockItem] = dict()
        uid: int
        node: Any
        con: Any

        self.scene.clear()

        # Recreate nodes
        for uid, node in self.diagram.node_data.items():
            block_type: BlockType | None
            block_model: Block | None = self.get_block_from_main_block(node.device_uid)

            if node.tpe in BlockType.__members__:
                block_type = BlockType[node.tpe]
            else:
                block_type = None

            if block_model is not None:

                if block_type == BlockType.GENERIC:

                    generic_item = GenericBlockItem(
                        var_factory=self.var_factory,
                        block=block_model,
                        api_object=self.api_object,
                        mode=self.mode,
                        position_changed_callback=lambda x, y, uid=block_model.uid: self.on_block_position_changed(uid, x, y)
                    )
                    self.scene.addItem(generic_item)
                    generic_item.setPos(QPointF(node.x, node.y))
                    brush = generic_item.brush()
                    brush.setColor(QColor(node.color))
                    generic_item.setBrush(brush)

                    uid_to_blockitem[uid] = generic_item


                else:
                    block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=node.name)
                    block_item.set_subsystem(block_model)
                    block_item.position_changed_callback = lambda x, y, uid=block_model.uid: self.on_block_position_changed(uid, x, y)
                    block_item.build_item()
                    self.scene.addItem(block_item)
                    block_item.setPos(QPointF(node.x, node.y))

                    brush: QBrush = block_item.brush()
                    brush.setColor(QColor(node.color))
                    block_item.setBrush(brush)
                    uid_to_blockitem[uid] = block_item

                    if block_type is not None:
                        current_count: int = self.block_counters.get(block_type, 0) + 1
                        self.block_counters[block_type] = current_count
                    else:
                        pass

        # Recreate connections
        for uid, con in self.diagram.con_data.items():
            src_item: BlockItem | None = uid_to_blockitem.get(con.from_uid, None)
            dst_item: BlockItem | None = uid_to_blockitem.get(con.to_uid, None)

            if src_item is not None and dst_item is not None:
                try:
                    src_port: PortItem = src_item.outputs[con.port_number_from]
                    dst_port: PortItem = dst_item.inputs[con.port_number_to]
                except IndexError:
                    continue

                elbow_points: List[QPointF] = [QPointF(x, y) for x, y in con.elbow_points] if con.elbow_points else []
                connection: ConnectionItem = ConnectionItem(
                    src_port, dst_port,
                    diagram=self.diagram,
                    con_uid=uid,
                    elbow_points=elbow_points
                )

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
        payload: BlockType | RmsModelTemplate | EmtModelTemplate | None = self.get_library_payload_from_mime_data(
            event.mimeData()
        )

        if payload is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def graphicsDragMoveEvent(self, event: QDragMoveEvent) -> None:
        """
        Keep the drag active while the payload remains a valid block entry.

        :param event:
        :return:
        """
        payload: BlockType | RmsModelTemplate | EmtModelTemplate | None = self.get_library_payload_from_mime_data(
            event.mimeData()
        )

        if payload is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def graphicsDropEvent(self, event: QDropEvent) -> None:
        """
        Create a dropped block in scene coordinates.

        :param event:
        :return:
        """
        payload: BlockType | RmsModelTemplate | EmtModelTemplate | None = self.get_library_payload_from_mime_data(
            event.mimeData()
        )
        scene_position: QtCore.QPointF = self.ui.graphicsView.mapToScene(
            int(event.position().x()),
            int(event.position().y())
        )
        block_item: BlockItem | None

        if payload is not None:

            block_item = None

            if isinstance(payload, BlockType) and payload == BlockType.GENERIC:

                block_item = self.create_generic_block_item(
                    block_type=payload,
                    x_pos=scene_position.x(),
                    y_pos=scene_position.y()
                )

            elif isinstance(payload, BlockType):
                block_item = self.create_block_item(
                    block_type=payload,
                    x_pos=scene_position.x(),
                    y_pos=scene_position.y()
                )
                print("")

            elif isinstance(payload, (RmsModelTemplate, EmtModelTemplate)):
                block_item = self.create_template_block_item(
                    template=payload,
                    x_pos=scene_position.x(),
                    y_pos=scene_position.y()
                )
            else:
                block_item = None

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
        api_object=device,
    )
    window.show()
    app.exec_()
