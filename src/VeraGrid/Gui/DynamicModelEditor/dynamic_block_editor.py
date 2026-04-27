# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import math
import uuid
import re
import copy
from enum import Enum
from typing import List, Dict, Optional, Any, Set
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QGraphicsScene, QGraphicsView, QGraphicsItem,
                               QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QMenu, QGraphicsPathItem,
                               QDialog, QVBoxLayout, QDialogButtonBox, QLabel, QListWidget, QWidget,
                               QListWidgetItem, QFormLayout, QSpinBox, QLineEdit, QDoubleSpinBox, QTableWidget,
                               QTableWidgetItem,
                               QColorDialog, QPlainTextEdit, QCheckBox)
from PySide6.QtGui import (QPen, QBrush, QPainterPath, QAction, QPainter,
                           QDropEvent, QDragEnterEvent, QDragMoveEvent, QColor)
from PySide6.QtCore import QAbstractItemModel, QLineF
from PySide6.QtCore import Qt, QPointF, QModelIndex, Signal, QAbstractTableModel

from VeraGridEngine.Devices.Parents.branch_parent import BranchParent
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Branches.transformer_type import TransformerType
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType, ParamPowerFlowRefferenceType, \
    DynamicSimulationMode, ShuntConnectionType, WindingType
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms, get_bus_rms_algebraic_vars
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template, get_bus_emt_algebraic_vars
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.Templates.BasicBlockCatalog import BasicBlockTemplateDescriptor
from VeraGridEngine.Templates.BasicBlockCatalog import get_editor_ready_basic_block_catalog_descriptors
from VeraGridEngine.Templates.BasicBlockCatalog import load_basic_block_catalog_template
from VeraGridEngine.Templates.BasicBlockCatalog.catalog import build_basic_block_catalog_branch_skeleton
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import build_lookup_array_linear_runtime_template
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import build_inverse_lookup_array_linear_runtime_template
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import build_lookup_matrix_linear_runtime_template
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import build_lookup_array_spline_runtime_template
from VeraGridEngine.Templates.BasicBlockCatalog.lookup_array_runtime_templates import build_lookup_matrix_spline_runtime_template
from VeraGridEngine.Templates.Emt.load_exponential_emt_template import get_exponential_load_emt
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_grounding_link_emt_template
from VeraGridEngine.Templates.Emt.nonlinear_resistor_emt_template import get_nonlinear_resistor_emt_template
from VeraGridEngine.Templates.Emt.switch_emt_template import get_switch_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_rlc_combo_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGrid.Gui.DynamicModelEditor.block_editor import Ui_BlockEditorWindow
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_utilities import create_block_of_type, create_generic_block, \
    create_emt_wizard_block
from VeraGrid.Gui.DynamicModelEditor.lookup_table_dialog import LookupArrayLinearDialog
from VeraGrid.Gui.DynamicModelEditor.lookup_table_dialog import LookupMatrixLinearDialog
from VeraGrid.Gui.DynamicModelEditor.grounding_link_emt_dialog import GroundingLinkEmtDialog
from VeraGrid.Gui.DynamicModelEditor.load_topology_emt_dialog import LoadTopologyEmtDialog
from VeraGrid.Gui.DynamicModelEditor.rlc_combo_emt_dialog import RlcComboEmtDialog
from VeraGrid.Gui.DynamicModelEditor.shunt_component_emt_dialog import ShuntComponentEmtDialog
from VeraGrid.Gui.DynamicModelEditor.transformer_topology_emt_dialog import TransformerTopologyEmtDialog
from VeraGrid.Gui.DynamicModelEditor.switch_emt_dialog import SwitchEmtDialog
from VeraGrid.Gui.Icons.icon_associations import device_type_icons
from VeraGridEngine.Utils.Symbolic.symbolic import (symbolic_to_string, string_to_symbolic,
                                                    get_symbolic_parser_function_names,
                                                    Expr, Var, Const, Comparison)
from VeraGridEngine.Utils.Symbolic.symbolic_io import duplicate_block
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagram
from VeraGridEngine.enumerations import BlockType
from dataclasses import dataclass

# from VeraGridEngine.Templates.Rms.common import create_block_of_type, create_generic_block, create_emt_wizard_block

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
BLOCK_HEADER_HEIGHT: float = 30.0
BLOCK_PORT_ROW_HEIGHT: float = 20.0
BLOCK_PORT_SECTION_PADDING: float = 10.0
BLOCK_MIN_WIDTH: float = 160.0
BLOCK_MIN_HEIGHT: float = 70.0
TEMPLATE_NODE_TYPE: str = "TEMPLATE"
PARAMETER_VALUE_TYPE_ROLE: int = int(QtCore.Qt.ItemDataRole.UserRole) + 500
PARAMETER_EDITABLE_ROLE: int = int(QtCore.Qt.ItemDataRole.UserRole) + 501
LIBRARY_SEARCH_TEXT_ROLE: int = int(QtCore.Qt.ItemDataRole.UserRole) + 502
MODAL_TEMPLATE_KIND_ATTR: str = "_modal_template_kind"
MODAL_TEMPLATE_CONFIG_ATTR: str = "_modal_template_config"
LOOKUP_ARRAY_LINEAR_DESCRIPTOR_KEYS: set[str] = {
    "lookup_array_linear",
    "lookup_array_linear_noclipping",
    "lookup_array_object_linear",
    "lookup_array_object_linear_noclipping",
}
INVERSE_LOOKUP_ARRAY_LINEAR_DESCRIPTOR_KEYS: set[str] = {
    "inverse_lookup_array_linear",
    "inverse_lookup_array_object_linear",
}
LOOKUP_ARRAY_SPLINE_DESCRIPTOR_KEYS: set[str] = {
    "lookup_array_spline",
    "lookup_array_object_spline",
}
LOOKUP_MATRIX_LINEAR_DESCRIPTOR_KEYS: set[str] = {
    "lookup_matrix_linear",
    "lookup_matrix_object_linear",
}
LOOKUP_MATRIX_SPLINE_DESCRIPTOR_KEYS: set[str] = {
    "lookup_matrix_spline",
    "lookup_matrix_object_spline",
}


def set_modal_template_metadata(block: Block, kind: str, config: Dict[str, Any]) -> None:
    """
    Persist the modal-builder metadata on one block.

    :param block: Target block.
    :param kind: Stable modal kind key.
    :param config: Serializable modal configuration.
    :return: None.
    """
    block.__dict__[MODAL_TEMPLATE_KIND_ATTR] = kind
    block.__dict__[MODAL_TEMPLATE_CONFIG_ATTR] = copy.deepcopy(config)


def _iter_child_blocks(block: Block) -> List[Block]:
    """
    Return all descendant blocks of one block.

    :param block: Root block.
    :return: Descendant blocks.
    """
    descendants: List[Block] = list()
    child_block: Block

    for child_block in block.children:
        descendants.append(child_block)
        descendants.extend(_iter_child_blocks(child_block))

    return descendants


def _get_shunt_component_kind(block_type: BlockType) -> str | None:
    """
    Return the single-component shunt kind handled by one block type.

    :param block_type: Candidate block type.
    :return: ``R``, ``L``, ``C`` or ``None``.
    """
    if block_type == BlockType.R_LOAD_EMT:
        return "R"
    elif block_type == BlockType.L_LOAD_EMT:
        return "L"
    elif block_type == BlockType.C_LOAD_EMT:
        return "C"
    else:
        return None


def _is_load_topology_block_type(block_type: BlockType) -> bool:
    """
    Return whether one block type uses the EMT load-topology modal.

    :param block_type: Candidate block type.
    :return: Boolean state.
    """
    return block_type in {BlockType.EXP_LOAD_EMT, BlockType.ZIP_LOAD_EMT}


def get_modal_template_metadata(block: Block | None) -> tuple[str | None, Dict[str, Any] | None]:
    """
    Return the modal-builder metadata stored on one block.

    :param block: Candidate block.
    :return: `(kind, config)` or `(None, None)` when absent.
    """
    if block is None:
        return None, None
    else:
        pass

    kind: Any = block.__dict__.get(MODAL_TEMPLATE_KIND_ATTR, None)
    config: Any = block.__dict__.get(MODAL_TEMPLATE_CONFIG_ATTR, None)

    if isinstance(kind, str) and isinstance(config, dict):
        return kind, copy.deepcopy(config)
    else:
        return None, None


class ParametersEditorDialog(QDialog):
    """
    Dialog to inspect and edit block parameters (event_dict, parameters, mode_dict).
    """

    def __init__(self,
                 var_factory: VarFactory,
                 block: Block,
                 parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.var_factory = var_factory
        self.block = block
        self.setWindowTitle(f"Parameters Editor - {block.name}")
        self.resize(500, 400)

        layout: QVBoxLayout = QVBoxLayout(self)

        self.table_view = QtWidgets.QTableView()
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.doubleClicked.connect(self.on_double_click)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table_view)

        self.model = ParametersTableModel(var_factory=var_factory, block=block, parent=self.table_view)
        self.table_view.setModel(self.model)
        self.model.block_updated.connect(self.on_block_updated)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def on_double_click(self, index: QtCore.QModelIndex) -> None:
        if index.model() == self.model and index.column() == 2:
            self.open_expression_editor(index.row())

    def open_expression_editor(self, row_index: int) -> None:
        row_data: BlockParameterRow | None = self.model.get_row(row_index)
        expression_text: str
        dialog: ExpressionTextEditorDialog
        symbol_namespace: Dict[str, Expr]
        parsed_expression: Expr | Comparison
        expression_value: Expr

        if row_data is not None and self.model.block is not None:
            if row_data.value is not None and isinstance(row_data.value, Expr):
                expression_text = symbolic_to_string(row_data.value)
            else:
                expression_text = str(row_data.value) if row_data.value is not None else ""
            symbol_namespace = build_block_symbol_namespace(self.model.block)
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

                    self.model.set_value_from_expression(row_index, expression_value)
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Expression Error",
                        str(exc)
                    )

    def show_context_menu(self, position: QtCore.QPoint) -> None:
        table_view: QtWidgets.QTableView = self.table_view
        self.select_table_context_row(table_view=table_view, position=position)

        has_selected_rows: bool = bool(table_view.selectionModel().selectedRows())

        menu: QMenu = QMenu(table_view)
        add_variable_action: QAction = menu.addAction("Add Variable")
        remove_selected_action: QAction = menu.addAction("Remove Selected")

        add_variable_action.setEnabled(self.block is not None)
        remove_selected_action.setEnabled(self.block is not None and has_selected_rows)

        selected_action: QAction | None = menu.exec(table_view.viewport().mapToGlobal(position))

        if selected_action == add_variable_action:
            self.open_add_variable_dialog()
        elif selected_action == remove_selected_action:
            self.remove_selected_parameters()

    def select_table_context_row(self, table_view: QtWidgets.QTableView, position: QtCore.QPoint) -> None:
        index = table_view.indexAt(position)
        if index.isValid():
            table_view.selectionModel().select(index, QtCore.QItemSelectionModel.SelectionFlag.Select)

    def open_add_variable_dialog(self) -> None:
        dialog = AddBlockVariableDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.get_name()
            category = dialog.get_category()
            parameter_value = dialog.get_parameter_value()

            new_var = self.var_factory.add_var(name=name)

            if category == "state":
                self.block.state_vars.append(new_var)
                if parameter_value != 0.0:
                    self.block.init_values[new_var] = self.var_factory.add_const(parameter_value, name=name)
            elif category == "algebraic":
                self.block.algebraic_vars.append(new_var)
            else:
                raise ValueError(f"Unsupported category for VariablesTableModel: {category}")

            self.model.set_block(self.block)
            self.model.block_updated.emit(self.block.uid)

    def remove_selected_parameters(self) -> None:
        params_model = self.model
        params_selected = [idx.row() for idx in self.table_view.selectionModel().selectedRows()]
        if not params_selected:
            return

        for row_idx in params_selected:
            row_data = params_model.rows[row_idx]
            var = row_data.key_var
            if row_data.kind == BlockParameterKind.EVENT_PARAMETER:
                if var in self.block.event_dict:
                    del self.block.event_dict[var]
            elif row_data.kind == BlockParameterKind.FIXED_PARAMETER:
                if var in self.block.parameters:
                    del self.block.parameters[var]
            elif row_data.kind == BlockParameterKind.MODE_PARAM:
                if var in self.block.mode_dict:
                    del self.block.mode_dict[var]

        params_model.set_block(self.block)
        params_model.block_updated.emit(self.block.uid)

    def on_block_updated(self, block_uid: int) -> None:
        self.model.set_block(self.block)


def _new_uid() -> int:
    """
    Generate a fresh integer identifier.

    :return:
    """
    return uuid.uuid4().int


def _grid_node_f_cost_sort_key(node: Any) -> float:
    """
    Return the A* sorting key for one grid node.

    :param node: Router grid node.
    :return: Node total cost.
    """
    return float(node.f_cost)


def _library_leaf_label_sort_key(leaf: "LibraryLeafSpec") -> str:
    """
    Return the case-insensitive sort key for one library leaf.

    :param leaf: Library leaf specification.
    :return: Lower-case label.
    """
    return leaf.label.lower()


def open_dyn_params_editor(var_factory: VarFactory, api_object: Any,
                           preferred_mode: DynamicSimulationMode | None = None):
    """
    Opens the dynamic parameters editor dialog.

    :param var_factory: Variable factory for creating new variables.
    :param api_object: Device/API object containing rms_model or emt_model.
    :param preferred_mode: Simulation mode (RMS or EMT).
    :return: None
    """
    if preferred_mode == DynamicSimulationMode.RMS:
        blk = api_object.rms_model
        print("")
    else:
        blk = api_object.emt_model

    dialog = ParametersEditorDialog(var_factory=var_factory, block=blk)
    dialog.exec()


def build_variables_rows(block: Block | None, rows: List[BlockParameterRow]):
    if block is not None:
        build_block_variables_rows(block, rows)
        if block.children:
            for child in block.children:
                build_variables_rows(child, rows)


def build_block_variables_rows(block: Block, rows: List[BlockParameterRow]):
    for var in block.state_vars:
        init_eq = block.init_eqs.get(var)
        rows.append(BlockParameterRow(
            name=var.name,
            kind=BlockParameterKind.STATE_VAR,
            key_var=var,
            value=block.init_values.get(var, ""),
            editable_name=True,
            editable_value=True,
            value_type=float,
            init_eq=init_eq
        ))

    for var in block.algebraic_vars:
        init_eq = block.init_eqs.get(var)
        rows.append(BlockParameterRow(
            name=var.name,
            kind=BlockParameterKind.ALGEBRAIC_VAR,
            key_var=var,
            value="",
            editable_name=True,
            editable_value=False,
            value_type=str,
            init_eq=init_eq
        ))


def build_parameters_rows(table_model, block: Block | None, rows: List[BlockParameterRow]):
    if block is not None:
        build_block_parameters_rows(table_model, block, rows)
        if block.children:
            for child in block.children:
                build_block_parameters_rows(table_model, child, rows)


def build_block_parameters_rows(table_model: Any, blk: Block, rows: List[BlockParameterRow]):
    for var, expr in blk.event_dict.items():
        if isinstance(expr, Const):
            rows.append(BlockParameterRow(
                name=var.name,
                kind=BlockParameterKind.EVENT_PARAMETER,
                key_var=var,
                value=expr.value,
                editable_name=True,
                editable_value=True,
                value_type=table_model.get_python_value_type(expr.value),
                source_dict_name="event_dict"
            ))
        else:
            rows.append(BlockParameterRow(
                name=var.name,
                kind=BlockParameterKind.EVENT_PARAMETER,
                key_var=var,
                value=expr,
                editable_name=True,
                editable_value=True,
                value_type=str,
                source_dict_name="event_dict"
            ))

    for var, expr in blk.mode_dict.items():
        if isinstance(expr, Const):
            rows.append(BlockParameterRow(
                name=var.name,
                kind=BlockParameterKind.MODE_PARAMETER,
                key_var=var,
                value=expr.value,
                editable_name=True,
                editable_value=True,
                value_type=table_model.get_python_value_type(expr.value),
                source_dict_name="mode_dict"
            ))
        else:
            rows.append(BlockParameterRow(
                name=var.name,
                kind=BlockParameterKind.MODE_PARAMETER,
                key_var=var,
                value=expr,
                editable_name=True,
                editable_value=True,
                value_type=str,
                source_dict_name="mode_dict"
            ))

    for var, const in blk.parameters.items():
        rows.append(BlockParameterRow(
            name=var.name,
            kind=BlockParameterKind.FIXED_PARAMETER,
            key_var=var,
            value=const.value,
            editable_name=True,
            editable_value=True,
            value_type=table_model.get_python_value_type(const.value),
            source_dict_name="parameters"
        ))

    return rows


def update_source_dict(block: Block | None, row: BlockParameterRow, value: Any, old_expr: Any = None) -> None:
    if block is not None and row is not None:
        update_param_value(block, row, value, old_expr)
        if block.children:
            for child in block.children:
                update_source_dict(child, row, value, old_expr)


def update_param_value(blk: Block, row: BlockParameterRow, value: Any, old_expr: Any):
    if blk is not None and row is not None:
        if row.key_var is not None:
            if row.kind == BlockParameterKind.EVENT_PARAMETER:
                if row.key_var in blk.event_dict:
                    blk.event_dict[row.key_var] = value
            elif row.kind == BlockParameterKind.MODE_PARAMETER:
                if row.key_var in blk.mode_dict:
                    blk.mode_dict[row.key_var] = value
            elif row.kind == BlockParameterKind.FIXED_PARAMETER:
                if row.key_var in blk.parameters:
                    blk.parameters[row.key_var] = value
            elif row.kind == BlockParameterKind.STATE_VAR:
                if row.key_var in blk.init_eqs:
                    blk.init_eqs[row.key_var] = value
            elif row.kind == BlockParameterKind.ALGEBRAIC_VAR:
                if row.key_var in blk.init_eqs:
                    blk.init_eqs[row.key_var] = value
        if row.kind == BlockParameterKind.STATE_EQUATION and row.item_index is not None:
            if old_expr is not None and old_expr in blk.state_eqs:
                blk.state_eqs[row.item_index] = value
        elif row.kind == BlockParameterKind.ALGEBRAIC_EQUATION and row.item_index is not None:
            if old_expr is not None and old_expr in blk.algebraic_eqs:
                blk.algebraic_eqs[row.item_index] = value


def build_equations_rows(block: Block | None, rows):
    """

    :return:
    """
    if block is not None:
        build_block_equations_rows(block, rows)
        if block.children:
            for child in block.children:
                build_equations_rows(child, rows)


def build_block_equations_rows(blk: Block, rows: List[BlockParameterRow]):
    for idx, eq in enumerate(blk.state_eqs):
        rows.append(BlockParameterRow(
            name=f"State Eq {idx + 1}",
            kind=BlockParameterKind.STATE_EQUATION,
            key_var=None,
            value=eq,
            editable_name=False,
            editable_value=True,
            value_type=str,
            item_index=idx
        ))

    for idx, eq in enumerate(blk.algebraic_eqs):
        rows.append(BlockParameterRow(
            name=f"Algebraic Eq {idx + 1}",
            kind=BlockParameterKind.ALGEBRAIC_EQUATION,
            key_var=None,
            value=eq,
            editable_name=False,
            editable_value=True,
            value_type=str,
            item_index=idx
        ))


class BlockPositionChangedCallback:
    """
    Callable wrapper used by graphics items to report block moves without lambdas.
    """

    __slots__ = ("_editor", "_block_uid")

    def __init__(self, editor: DynamicBlockEditorGUI, block_uid: int) -> None:
        """
        Build the callback wrapper.

        :param editor: Owning dynamic editor.
        :param block_uid: Moved block uid.
        :return: None.
        """

        self._editor = editor
        self._block_uid = block_uid

    def __call__(self, x_pos: float, y_pos: float) -> None:
        """
        Forward one position change to the editor.

        :param x_pos: New x coordinate.
        :param y_pos: New y coordinate.
        :return: None.
        """

        self._editor.on_block_position_changed(self._block_uid, x_pos, y_pos)


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
    Only adds elbows when the path changes direction.

    :param start:
    :param end:
    :return:
    """
    path: QPainterPath = QPainterPath(start)
    delta_x: float = end.x() - start.x()
    delta_y: float = end.y() - start.y()

    if abs(delta_y) < 1:
        path.lineTo(end)
        return path

    if abs(delta_x) < 1:
        path.lineTo(end)
        return path

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


class OrthogonalRouter:
    """
    Global orthogonal router for connection paths.
    Uses A* pathfinding on a grid to compute Manhattan-style paths avoiding obstacles.
    """

    GRID_SIZE: float = 10.0
    BASE_COST: int = 1
    TURN_COST: int = 10
    BLOCKED_COST: int = 1000000

    class GridNode:
        def __init__(self, x: int, y: int):
            self.x = x
            self.y = y
            self.g_cost: int = 0
            self.h_cost: int = 0
            self.f_cost: int = 0
            self.parent: "OrthogonalRouter.GridNode | None" = None
            self.direction: str | None = None

        def __hash__(self):
            return hash((self.x, self.y))

        def __eq__(self, other):
            return self.x == other.x and self.y == other.y

    @staticmethod
    def _pos_to_grid(pos: QPointF) -> tuple[int, int]:
        return (int(pos.x() / OrthogonalRouter.GRID_SIZE),
                int(pos.y() / OrthogonalRouter.GRID_SIZE))

    @staticmethod
    def _grid_to_pos(gx: int, gy: int) -> QPointF:
        return QPointF(gx * OrthogonalRouter.GRID_SIZE, gy * OrthogonalRouter.GRID_SIZE)

    @staticmethod
    def _get_neighbors(node: "OrthogonalRouter.GridNode") -> List[tuple]:
        return [
            (node.x + 1, node.y, 'right'),
            (node.x - 1, node.y, 'left'),
            (node.x, node.y + 1, 'down'),
            (node.x, node.y - 1, 'up')
        ]

    @staticmethod
    def _heuristic(x1: int, y1: int, x2: int, y2: int) -> int:
        return abs(x2 - x1) + abs(y2 - y1)

    @staticmethod
    def _is_blocked(gx: int, gy: int, scene: "QGraphicsScene | None",
                    source_port: "PortItem | BranchingItem | None",
                    target_port: "PortItem | BranchingItem | None") -> bool:
        if scene is None:
            return False

        pos = QPointF(gx * OrthogonalRouter.GRID_SIZE, gy * OrthogonalRouter.GRID_SIZE)
        rect = QtCore.QRectF(pos.x() - OrthogonalRouter.GRID_SIZE / 2,
                             pos.y() - OrthogonalRouter.GRID_SIZE / 2,
                             OrthogonalRouter.GRID_SIZE, OrthogonalRouter.GRID_SIZE)

        items = scene.items(rect)
        for item in items:
            if isinstance(item, (ConnectionItem, PortItem, BranchingItem)):
                pass
            else:
                if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable:
                    if source_port is not None and item == source_port.subsystem:
                        pass
                    else:
                        if target_port is not None and item == target_port.subsystem:
                            pass
                        else:
                            return True
                else:
                    pass
        return False

    @staticmethod
    def compute_path(source_pos: QPointF, target_pos: QPointF,
                     source_port: "PortItem | BranchingItem | None" = None,
                     target_port: "PortItem | BranchingItem | None" = None,
                     scene: "QGraphicsScene | None" = None) -> QPainterPath:
        """
        Compute an orthogonal path using A* pathfinding on a grid.

        :param source_pos: Start point
        :param target_pos: End point
        :param source_port: Source port for context
        :param target_port: Target port for context
        :param scene: Graphics scene for obstacle detection
        :return: QPainterPath with orthogonal segments avoiding obstacles
        """
        if scene is None:
            return build_orthogonal_connection_path(source_pos, target_pos)

        start_gx, start_gy = OrthogonalRouter._pos_to_grid(source_pos)
        end_gx, end_gy = OrthogonalRouter._pos_to_grid(target_pos)

        open_set: List[OrthogonalRouter.GridNode] = []
        closed_set: set = set()

        start_node = OrthogonalRouter.GridNode(start_gx, start_gy)
        start_node.g_cost = 0
        start_node.h_cost = OrthogonalRouter._heuristic(start_gx, start_gy, end_gx, end_gy)
        start_node.f_cost = start_node.g_cost + start_node.h_cost
        start_node.direction = None

        open_set.append(start_node)

        while open_set:
            open_set.sort(key=_grid_node_f_cost_sort_key)
            current = open_set.pop(0)

            if current.x == end_gx and current.y == end_gy:
                path_points = OrthogonalRouter._reconstruct_path(current)
                return OrthogonalRouter._build_qpainterpath(path_points, source_pos, target_pos)

            closed_set.add((current.x, current.y))

            for gx, gy, direction in OrthogonalRouter._get_neighbors(current):
                if (gx, gy) in closed_set:
                    pass
                else:
                    if OrthogonalRouter._is_blocked(gx, gy, scene, source_port, target_port):
                        pass
                    else:
                        g_cost = current.g_cost + OrthogonalRouter.BASE_COST

                        if current.direction is not None and current.direction != direction:
                            g_cost += OrthogonalRouter.TURN_COST
                        else:
                            pass

                        neighbor = OrthogonalRouter.GridNode(gx, gy)

                        in_open = False
                        for node in open_set:
                            if node.x == gx and node.y == gy:
                                in_open = True
                                if g_cost < node.g_cost:
                                    node.g_cost = g_cost
                                    node.f_cost = node.g_cost + node.h_cost
                                    node.parent = current
                                    node.direction = direction
                                else:
                                    pass
                                break
                            else:
                                pass

                        if not in_open:
                            neighbor.g_cost = g_cost
                            neighbor.h_cost = OrthogonalRouter._heuristic(gx, gy, end_gx, end_gy)
                            neighbor.f_cost = neighbor.g_cost + neighbor.h_cost
                            neighbor.parent = current
                            neighbor.direction = direction
                            open_set.append(neighbor)
                        else:
                            pass

        fallback_path = build_orthogonal_connection_path(source_pos, target_pos)
        return fallback_path

    @staticmethod
    def _reconstruct_path(end_node: "OrthogonalRouter.GridNode") -> List[QPointF]:
        path = []
        current = end_node
        while current is not None:
            path.append(OrthogonalRouter._grid_to_pos(current.x, current.y))
            current = current.parent
        path.reverse()
        return path

    @staticmethod
    def _build_qpainterpath(grid_path: List[QPointF], source_pos: QPointF, target_pos: QPointF) -> QPainterPath:
        if len(grid_path) < 2:
            path = QPainterPath(source_pos)
            path.lineTo(target_pos)
            return path

        path = QPainterPath(source_pos)
        path.lineTo(grid_path[0])

        simplified = OrthogonalRouter._simplify_path(grid_path)

        for point in simplified:
            path.lineTo(point)

        path.lineTo(target_pos)
        return path

    @staticmethod
    def _simplify_path(points: List[QPointF]) -> List[QPointF]:
        if len(points) < 3:
            return points

        simplified = [points[0]]
        prev_dir = None

        for i in range(1, len(points) - 1):
            dx1 = points[i].x() - points[i - 1].x()
            dy1 = points[i].y() - points[i - 1].y()
            dx2 = points[i + 1].x() - points[i].x()
            dy2 = points[i + 1].y() - points[i].y()

            dir1 = None
            if abs(dx1) > abs(dy1):
                dir1 = 'h'
            else:
                dir1 = 'v'

            dir2 = None
            if abs(dx2) > abs(dy2):
                dir2 = 'h'
            else:
                dir2 = 'v'

            if dir1 != dir2:
                simplified.append(points[i])

        simplified.append(points[-1])
        return simplified

    @staticmethod
    def compute_path_simple(source_pos: QPointF, target_pos: QPointF) -> QPainterPath:
        """
        Compute a simple orthogonal path without obstacle avoidance.

        :param source_pos: Start point
        :param target_pos: End point
        :return: QPainterPath with orthogonal segments
        """
        return build_orthogonal_connection_path(source_pos, target_pos)


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
    elif isinstance(item_data, BasicBlockTemplateDescriptor):
        return True
    elif isinstance(item_data, (RmsModelTemplate, EmtModelTemplate, FmuTemplate)):
        return True
    else:
        return False


@dataclass(frozen=True)
class LibraryLeafSpec:
    """
    One draggable leaf entry in the library tree.
    """

    label: str
    payload: object
    search_text: str = ""


class LibraryTreeFilterProxyModel(QtCore.QSortFilterProxyModel):
    """
    Tree proxy used by the block editor library search.
    """

    __slots__ = ("_search_role",)

    def __init__(self, search_role: int, parent: QtCore.QObject | None = None):
        super().__init__(parent)
        self._search_role = search_role
        self.setRecursiveFilteringEnabled(True)
        self.setAutoAcceptChildRows(True)
        self.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterRole(search_role)
        self.setFilterKeyColumn(0)

    def mimeData(self, indexes: List[QtCore.QModelIndex]) -> QtCore.QMimeData:
        """
        Forward drag mime building to the source library model.
        """

        source_model: QtCore.QAbstractItemModel | None = self.sourceModel()
        if isinstance(source_model, DynamicsLibraryTreeModel):
            source_indexes: List[QtCore.QModelIndex] = [self.mapToSource(index) for index in indexes if index.isValid()]
            return source_model.mimeData(source_indexes)
        else:
            return super().mimeData(indexes)

    def supportedDragActions(self) -> QtCore.Qt.DropAction:
        """
        Reuse the drag action exposed by the source model.
        """

        source_model: QtCore.QAbstractItemModel | None = self.sourceModel()
        if isinstance(source_model, DynamicsLibraryTreeModel):
            return source_model.supportedDragActions()
        else:
            return super().supportedDragActions()


def clone_block_for_editing(block: Block) -> Block:
    """
    Build an isolated editable copy of a block, including its diagram.

    :param block:
    :return:
    """
    return copy.deepcopy(block)


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
    # target_block.alter_params = source_clone.alter_params
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
    elif var_type == "event_parameter":
        block.event_dict[var] = Const(parameter_value, name=var.name)
    elif var_type == "mode_parameter":
        block.mode_dict[var] = Const(parameter_value, name=var.name)
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

    def __init__(self, block_item: BlockItem | GenericBlockItem, size: int = 10):
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

        self.name_edit = QLineEdit()
        layout.addRow("Block name:", self.name_edit)

        self.inputs_spin = QSpinBox()
        self.inputs_spin.setMinimum(1)
        self.inputs_spin.setValue(1)
        layout.addRow("Number of inputs:", self.inputs_spin)

        self.outputs_spin = QSpinBox()
        self.outputs_spin.setMinimum(1)
        self.outputs_spin.setValue(1)
        layout.addRow("Number of outputs:", self.outputs_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_values(self):
        """Return all dialog values."""
        name = self.name_edit.text().strip() or "generic"
        inputs = self.inputs_spin.value()
        outputs = self.outputs_spin.value()
        return name, inputs, outputs


class EmtTemplateWizardDialog(QDialog):
    """
    Dialog to configure EMT template wizard block phases.
    """

    def __init__(self,
                 parent=None,
                 initial_values: tuple[bool, bool, bool, bool] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Configure EMT Block Phases")

        layout = QVBoxLayout(self)

        label = QLabel("Select the phases for this EMT block:")
        layout.addWidget(label)

        self.phase_n_check = QCheckBox("phase_n")
        self.phase_a_check = QCheckBox("phase_a")
        self.phase_b_check = QCheckBox("phase_b")
        self.phase_c_check = QCheckBox("phase_c")

        layout.addWidget(self.phase_n_check)
        layout.addWidget(self.phase_a_check)
        layout.addWidget(self.phase_b_check)
        layout.addWidget(self.phase_c_check)

        if initial_values is not None:
            self.phase_n_check.setChecked(bool(initial_values[0]))
            self.phase_a_check.setChecked(bool(initial_values[1]))
            self.phase_b_check.setChecked(bool(initial_values[2]))
            self.phase_c_check.setChecked(bool(initial_values[3]))
        else:
            pass

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        """Return phase selection as a tuple of booleans."""
        return (
            self.phase_n_check.isChecked(),
            self.phase_a_check.isChecked(),
            self.phase_b_check.isChecked(),
            self.phase_c_check.isChecked()
        )


class PortItem(QGraphicsEllipseItem):
    """
    Graphical input or output port attached to a block item.
    """

    def __init__(self,
                 subsystem: BlockItem | GenericBlockItem,
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


class BranchingItem(QGraphicsEllipseItem):
    """
    Graphical branching point that can have one input and multiple outputs.
    Created when splitting a connection via double-click.
    """

    def __init__(self,
                 subsystem: BlockItem,
                 index: int,
                 radius: int = 6):
        """
        Build a connection branching point.

        :param source_connection: The connection to branch from.
        :param radius:
        """
        super().__init__(-radius, -radius, 2 * radius, 2 * radius)
        fill_color: QColor = OUTPUT_PORT_FILL
        self.setBrush(QBrush(fill_color))
        self.setPen(QPen(PORT_BORDER, 1.5))
        self.setZValue(3)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.subsystem: BlockItem = subsystem
        self.index: int = index
        self.connections: List["ConnectionItem"] | None = None

        self.base_var: Var | None = None

        # self.input_port: PortItem = PortItem(self, True, 0, 1, radius=5)
        # self.output_port: PortItem = PortItem(self, False, 0, 1, radius=5)
        # self.input_port.connections = None
        # self.output_port.connections = None

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
    Uses global OrthogonalRouter for path computation.
    """

    def __init__(self, source_port: PortItem | BranchingItem, target_port: PortItem | BranchingItem,
                 diagram=None, con_uid=None, uid=None):
        """
        Build the connection item.

        :param source_port:
        :param target_port:
        :param diagram: BlockDiagram reference
        :param con_uid: Connection uid in the diagram
        :param uid: Optional specific uid to use
        """
        super().__init__()
        self.uid: int = uid if uid is not None else _new_uid()
        self.setZValue(-1)
        self.source_port: PortItem | BranchingItem = source_port
        self.target_port: PortItem | BranchingItem = target_port
        self.diagram = diagram
        self.con_uid = con_uid if con_uid is not None else self.uid

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
        Recompute the orthogonal path from current port positions using the global router.

        :return:
        """
        scene = self.source_port.scene()
        path = OrthogonalRouter.compute_path(
            self.source_port.scenePos(),
            self.target_port.scenePos(),
            source_port=self.source_port,
            target_port=self.target_port,
            scene=scene
        )
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
        ("Event Parameter", "event_parameter"),
        ("Mode Parameter", "mode_parameter"),
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
        is_parameter: bool = category in {"parameter", "event_parameter", "mode_parameter"}

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


class AddEquationDialog(QDialog):
    """
    Dialog used to create a new equation (state or algebraic) in the selected block.
    """

    CATEGORY_OPTIONS: List[tuple[str, str]] = [
        ("State", "state"),
        ("Algebraic", "algebraic"),
    ]

    def __init__(self, symbol_namespace: Dict[str, Expr], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Equation")
        self.resize(500, 200)
        self.symbol_namespace = symbol_namespace

        layout: QVBoxLayout = QVBoxLayout(self)
        form_layout: QFormLayout = QFormLayout()
        layout.addLayout(form_layout)

        self.equation_edit: QPlainTextEdit = QPlainTextEdit(self)
        editor_font: QtGui.QFont = QtGui.QFont("DejaVu Sans Mono", 10)
        self.equation_edit.setFont(editor_font)
        self.equation_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.type_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(self)

        for label, value in self.CATEGORY_OPTIONS:
            self.type_combo.addItem(label, value)

        form_layout.addRow("Equation", self.equation_edit)
        form_layout.addRow("Type", self.type_combo)

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

        self.equation_edit.textChanged.connect(self.update_validation_state)
        self.update_validation_state()

    def get_equation_text(self) -> str:
        return self.equation_edit.toPlainText().strip()

    def get_category(self) -> str:
        return str(self.type_combo.currentData())

    def update_validation_state(self) -> None:
        """
        Validate the equation text before allowing acceptance.

        :return:
        """
        equation_text: str = self.get_equation_text()

        if len(equation_text) == 0:
            self.validation_label.setText("Enter an equation.")
            self.validation_label.setStyleSheet("color: #b42318;")
            self.ok_button.setEnabled(False)
            return

        try:
            parsed = string_to_symbolic(equation_text, self.symbol_namespace)
            self.validation_label.setText("Equation is valid.")
            self.validation_label.setStyleSheet("color: #027a48;")
            self.ok_button.setEnabled(True)
        except Exception as exc:
            self.validation_label.setText(str(exc))
            self.validation_label.setStyleSheet("color: #b42318;")
            self.ok_button.setEnabled(False)


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
    MODE_PARAMETER = "Mode Parameter"
    FIXED_PARAMETER = "Parameter"
    MODE_PARAM = "Mode Parameter"


class BlockParameterRow:
    """
    Row description for the selected block editor table.
    """

    __slots__ = ("name", "kind", "key_var", "value", "editable_name", "editable_value", "value_type", "item_index",
                 "init_eq", "source_dict_name", "display_value", "display_init_eq")

    def __init__(self,
                 name: str,
                 kind: BlockParameterKind,
                 key_var: Var | None,
                 value: Any,
                 editable_name: bool,
                 editable_value: bool,
                 value_type: type,
                 item_index: int | None = None,
                 init_eq: Expr | None = None,
                 source_dict_name: str | None = None):
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
        :param init_eq: Initial equation from block.init_eqs for this variable
        :param source_dict_name: Name of the source dict ('event_dict' or 'parameters')
        """
        self.name: str = name
        self.kind: BlockParameterKind = kind
        self.key_var: Var | None = key_var
        self.value: Any = value
        self.editable_name: bool = editable_name
        self.editable_value: bool = editable_value
        self.value_type: type = value_type
        self.item_index: int | None = item_index
        self.init_eq: Expr | None = init_eq
        self.source_dict_name: str | None = source_dict_name
        self.display_value: Any = None
        self.display_init_eq: Any = None
        refresh_block_parameter_row_cache(self)

    @property
    def is_section(self) -> bool:
        return self.kind == BlockParameterKind.SECTION

    @property
    def opens_expression_editor(self) -> bool:
        return self.kind in {
            BlockParameterKind.STATE_EQUATION,
            BlockParameterKind.ALGEBRAIC_EQUATION,
            BlockParameterKind.EVENT_PARAMETER,
            BlockParameterKind.MODE_PARAMETER,
            BlockParameterKind.FIXED_PARAMETER,
        } and isinstance(self.value, Expr)


def build_block_parameter_display_value(value: Any) -> Any:
    """
    Return the cached visible representation for one table value.

    :param value: Raw row value.
    :return: Display-friendly cached value.
    """
    if isinstance(value, Expr):
        return symbolic_to_string(value)
    else:
        return value


def refresh_block_parameter_row_cache(row: BlockParameterRow) -> None:
    """
    Refresh the cached visible text for one row.

    :param row: Row to update.
    :return: None.
    """
    row.display_value = build_block_parameter_display_value(row.value)

    if row.init_eq is not None:
        row.display_init_eq = build_block_parameter_display_value(row.init_eq)
    else:
        row.display_init_eq = None


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


class VariablesTableModel(QtCore.QAbstractTableModel):
    """
    Table model for block variables (state and algebraic only).
    Columns: Type, Name, Init Equation
    """

    block_updated = Signal(object)

    def __init__(self, var_factory: VarFactory, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self.var_factory = var_factory
        self.block = None
        self.rows = []
        self.headers = ["Type", "Name", "Init Equation"]

    def set_block(self, block: Block | None) -> None:
        self.beginResetModel()
        self.block = block
        self.rows: List[BlockParameterRow] = list()
        build_variables_rows(self.block, self.rows)
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return 3

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self.block is None:
            return None
        row = self.rows[index.row()]
        if role == QtCore.Qt.ItemDataRole.DisplayRole or role == QtCore.Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                if row.kind == BlockParameterKind.STATE_VAR:
                    return "State"
                elif row.kind == BlockParameterKind.ALGEBRAIC_VAR:
                    return "Algebraic"
            elif index.column() == 1:
                return row.name
            elif index.column() == 2:
                if row.init_eq is not None:
                    return row.display_init_eq
                else:
                    return row.display_value
        elif role == PARAMETER_VALUE_TYPE_ROLE and index.column() == 2:
            return "float" if row.value_type == float else "text"
        elif role == PARAMETER_EDITABLE_ROLE and index.column() == 2:
            return row.editable_value
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return QColor("#f7fafc")
        elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
            return QColor("#333333")
        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        row = self.rows[index.row()]
        if role == QtCore.Qt.ItemDataRole.EditRole:
            if index.column() == 1:
                row.name = value
                row.key_var.name = value
            elif index.column() == 2 and row.editable_value:
                row.value = value
                refresh_block_parameter_row_cache(row)
            else:
                return False
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def set_init_eq(self, row_index: int, init_eq: Expr) -> None:
        if 0 <= row_index < len(self.rows):
            row = self.rows[row_index]
            row.init_eq = init_eq
            refresh_block_parameter_row_cache(row)
            if self.block is not None and row.key_var is not None:
                update_source_dict(self.block, row, init_eq)
            index = self.index(row_index, 2)
            self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.EditRole])

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags
        flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if index.column() == 1:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        elif index.column() == 2:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        return flags

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def get_row(self, row_index: int) -> BlockParameterRow | None:
        if 0 <= row_index < len(self.rows):
            return self.rows[row_index]
        return None

    def get_last_index_of_type(self, var_type: str) -> int:
        """
        Return the last row index for a given variable type.
        State vars come first, then algebraic vars.

        :param var_type: "state" or "algebraic"
        :return: Last row index for that type, or -1 if none found
        """
        if var_type == "state":
            return len(self.block.state_vars) - 1 if self.block and self.block.state_vars else -1
        elif var_type == "algebraic":
            return len(self.rows) - 1 if self.block and self.block.algebraic_vars else -1
        return -1

    def add_variable_at_end_of_type(self, name: str, category: str, parameter_value: float = 0.0) -> None:
        """
        Add a new variable to the block, inserting it after the last variable of the same type.
        State vars are added after the last state var, algebraic vars after the last algebraic var.

        :param name: Variable name
        :param category: "state" or "algebraic"
        :param parameter_value: Initial value for state variables
        """
        if self.block is None:
            raise ValueError("No block is currently selected.")

        new_var = self.var_factory.add_var(name=name)

        if category == "state":
            self.block.state_vars.append(new_var)
            if parameter_value != 0.0:
                self.block.init_values[new_var] = self.var_factory.add_const(parameter_value, name=name)
        elif category == "algebraic":
            self.block.algebraic_vars.append(new_var)
        else:
            raise ValueError(f"Unsupported category for VariablesTableModel: {category}")

        self.set_block(self.block)
        self.block_updated.emit(self.block.uid)


class ParametersTableModel(QtCore.QAbstractTableModel):
    """
    Table model for block parameters (fixed and event).
    Columns: , Name, Kind, Value
    """

    block_updated = Signal(object)

    def __init__(self, var_factory: VarFactory, block=Block(), parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self.var_factory = var_factory
        self.block = None
        self.rows = []
        self.headers = ["Type", "Name", "Value"]
        if block is not None:
            self.block = block
            build_parameters_rows(self, self.block, self.rows)

    def set_block(self, block: Block | None) -> None:
        self.beginResetModel()
        self.block = block
        self.rows: List[BlockParameterRow] = list()
        build_parameters_rows(self, self.block, self.rows)
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return 3

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self.block is None:
            return None
        row = self.rows[index.row()]
        if role == QtCore.Qt.ItemDataRole.DisplayRole or role == QtCore.Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                return row.kind.value
            elif index.column() == 1:
                return row.name
            elif index.column() == 2:
                return row.display_value
        elif role == PARAMETER_EDITABLE_ROLE and index.column() == 2:
            return row.editable_value
        elif role == PARAMETER_VALUE_TYPE_ROLE and index.column() == 2:
            return self.get_python_value_type(row.value)
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return QColor("#f7fafc")
        elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
            return QColor("#333333")
        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        row = self.rows[index.row()]
        if role == QtCore.Qt.ItemDataRole.EditRole:
            if index.column() == 1:
                row.name = value
                row.key_var.name = value
            elif index.column() == 2 and row.editable_value:
                row.value = value
                refresh_block_parameter_row_cache(row)
                update_source_dict(self.block, row, value)
            else:
                return False
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def set_value_from_expression(self, row_index: int, expr: Expr) -> None:
        if 0 <= row_index < len(self.rows):
            row = self.rows[row_index]
            row.value = expr
            refresh_block_parameter_row_cache(row)
            update_source_dict(self.block, row, expr)
            index = self.index(row_index, 2)
            self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.EditRole])

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags
        flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if index.column() == 1:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        elif index.column() == 2 and self.rows[index.row()].editable_value:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        return flags

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    @staticmethod
    def get_python_value_type(value) -> type:
        if isinstance(value, int):
            return int
        elif isinstance(value, float):
            return float
        return str

    def get_row(self, row_index: int) -> BlockParameterRow | None:
        if 0 <= row_index < len(self.rows):
            return self.rows[row_index]
        return None


class EquationsTableModel(QtCore.QAbstractTableModel):
    """
    Table model for block equations (state and algebraic).
    Columns: Type, Equation
    """

    block_updated = Signal(object)
    equation_edited = Signal(int, object)

    def __init__(self, var_factory: VarFactory, parent: Optional[QtCore.QObject] = None):
        """

        :param var_factory:
        :param parent:
        """
        super().__init__(parent)
        self.var_factory = var_factory
        self.block = None
        self.rows = []
        self.headers = ["Type", "Equation"]
        self.symbol_namespace = None

    def set_block(self, block: Block | None) -> None:
        """

        :param block:
        :return:
        """
        self.beginResetModel()
        self.block = block
        self.rows: List[BlockParameterRow] = list()
        build_equations_rows(self.block, self.rows)
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        """

        :param parent:
        :return:
        """
        return len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        """

        :param parent:
        :return:
        """
        return 2

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param index:
        :param role:
        :return:
        """
        if not index.isValid() or self.block is None:
            return None
        row = self.rows[index.row()]
        if role == QtCore.Qt.ItemDataRole.DisplayRole or role == QtCore.Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                if row.kind == BlockParameterKind.STATE_EQUATION:
                    return "State"
                elif row.kind == BlockParameterKind.ALGEBRAIC_EQUATION:
                    return "Algebraic"
            elif index.column() == 1:
                return row.display_value
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            return QColor("#f7fafc")
        elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
            return QColor("#333333")
        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        """

        :param index:
        :param value:
        :param role:
        :return:
        """
        if not index.isValid():
            return False
        row = self.rows[index.row()]
        old_expr = row.value
        if role == QtCore.Qt.ItemDataRole.EditRole:
            if index.column() == 1:
                try:

                    new_expr = string_to_symbolic(value, self.symbol_namespace)
                    row.value = new_expr
                    refresh_block_parameter_row_cache(row)
                    update_source_dict(self.block, row, row.value, old_expr)
                    self.dataChanged.emit(index, index, [role])
                    self.block_updated.emit(self.block.uid)
                    return True
                except:
                    return False
        return False

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """

        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def flags(self, index):
        """

        :param index:
        :return:
        """
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags
        flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if index.column() == 1:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        return flags

    def get_row(self, row_index: int) -> BlockParameterRow | None:
        """

        :param row_index:
        :return:
        """
        if 0 <= row_index < len(self.rows):
            return self.rows[row_index]
        return None


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
        for submodel in model.children:
            self.refresh_lists(submodel, clear=False)


class GenericBlockItem(QGraphicsRectItem):
    """
           Class to represent generic block to construct devices in the editor
           :param name:
           """

    def __init__(self,
                 var_factory: VarFactory,
                 subsys: Block,
                 api_object,
                 mode: DynamicSimulationMode,
                 position_changed_callback=None):
        """

        :param var_factory:
        :param subsys:
        :param api_object:
        :param position_changed_callback:
        """
        super().__init__(0, 0, 100, 60)

        # ------------------------
        # API
        # ------------------------
        self.var_factory = var_factory
        self.subsys = subsys
        self.mode = mode
        self.api_object = api_object
        self.position_changed_callback = position_changed_callback

        self.resize_handle: ResizeHandle | None = None
        self.resizing_from_handle = False
        self._suppress_resize: bool = False

        self.name_item = QGraphicsTextItem(self.subsys.name, self)
        self.inputs: List[PortItem] = list()
        self.outputs: List[PortItem] = list()
        self.input_labels: List[QGraphicsTextItem] = list()
        self.output_labels: List[QGraphicsTextItem] = list()

        self.editor_window = DynamicBlockEditorGUI(
            var_factory=self.var_factory,
            block=self.subsys,
            api_object=self.api_object,
            mode=self.mode
        )

        self.setBrush(QBrush(DEFAULT_BLOCK_FILL))
        self.setPen(QPen(Qt.GlobalColor.transparent, 0))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
        )
        self.setAcceptHoverEvents(True)

        self.name_item.setDefaultTextColor(BLOCK_TITLE)
        name_font: QtGui.QFont = QtGui.QFont("DejaVu Sans", 9)
        name_font.setBold(True)
        self.name_item.setFont(name_font)
        self.name_item.setPos(6, 4)

        n_inputs = len(self.subsys.in_vars)
        n_outputs = len(self.subsys.out_vars)

        self.inputs = [PortItem(self, True, i, n_inputs) for i in range(n_inputs)]
        self.outputs = [PortItem(self, False, i, n_outputs) for i in range(n_outputs)]
        self.input_labels = [self.create_port_label_item() for _ in range(n_inputs)]
        self.output_labels = [self.create_port_label_item() for _ in range(n_outputs)]

        self.refresh_port_metadata()

        self.resize_handle = ResizeHandle(self)

        self.resize_to_content()

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

    def paint(self,
              painter: QPainter,
              option: QtWidgets.QStyleOptionGraphicsItem,
              widget: Optional[QWidget] = None) -> None:
        """
        Paint the generic block with a rounded card style and a subtle shadow.

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

    def _set_rect_internal(self, w, h):
        QGraphicsRectItem.setRect(self, 0, 0, w, h)
        self.update_ports()
        self.update_handle_position()

    def set_rectangle(self, x, y, w, h):
        if not self._suppress_resize:
            self._set_rect_internal(w, h)

    def get_minimum_block_size(self) -> tuple[float, float]:
        """
        Compute the minimum generic block size required by its ports and name.

        :return:
        """
        port_rows: int = max(len(self.inputs), len(self.outputs), 1)
        min_height: float = 50 + port_rows * 18

        name_width = len(self.subsys.name) * 7
        max_label_length = 0
        for var in self.subsys.in_vars:
            max_label_length = max(max_label_length, len(var.name))
        for var in self.subsys.out_vars:
            max_label_length = max(max_label_length, len(var.name))

        port_width = max_label_length * 7
        min_width = max(100, name_width + 14, port_width + 30)

        return min_width, min_height

    def resize_to_content(self) -> None:
        """
        Resize the block to the minimum size required by its ports.

        :return:
        """
        self.prepareGeometryChange()
        min_width: float
        min_height: float
        min_width, min_height = self.get_minimum_block_size()
        QGraphicsRectItem.setRect(self, 0, 0, min_width, min_height)
        self.update_ports()
        self.update_handle_position()

    def create_port_label_item(self) -> QGraphicsTextItem:
        """
        Create a compact label item used beside a port.

        :return:
        """
        label_item: QGraphicsTextItem = QGraphicsTextItem("", self)
        label_font: QtGui.QFont = QtGui.QFont("DejaVu Sans", 9)
        label_item.setFont(label_font)
        label_item.setDefaultTextColor(PORT_LABEL_COLOR)
        label_item.setZValue(4)
        return label_item

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

    def update_ports(self):
        for i, port in enumerate(self.inputs):
            spacing = self.rect().height() / (len(self.inputs) + 1)
            port.setPos(0, spacing * (i + 1))
        for i, port in enumerate(self.outputs):
            spacing = self.rect().height() / (len(self.outputs) + 1)
            port.setPos(self.rect().width(), spacing * (i + 1))

        for i, label_item in enumerate(self.input_labels):
            port = self.inputs[i]
            label_item.setPos(14.0, port.pos().y() - 8.0)

        for i, label_item in enumerate(self.output_labels):
            port = self.outputs[i]
            label_width: float = label_item.boundingRect().width()
            label_item.setPos(self.rect().width() - label_width - 14.0, port.pos().y() - 8.0)

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
        self.editor_window: DynamicBlockEditorGUI | None = None

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
            name_font: QtGui.QFont = QtGui.QFont("DejaVu Sans", 9)
            name_font.setBold(True)
            self.name_item.setFont(name_font)
            self.name_item.setPos(6, 4)

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
        label_font: QtGui.QFont = QtGui.QFont("DejaVu Sans", 9)
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

        name_width = len(self.name) * 7
        max_label_length = 0
        if self.subsys:
            for var in self.subsys.in_vars:
                max_label_length = max(max_label_length, len(var.name))
            for var in self.subsys.out_vars:
                max_label_length = max(max_label_length, len(var.name))

        port_width = max_label_length * 7
        min_width = max(BLOCK_MIN_WIDTH, name_width + 14, port_width + 28)

        return min_width, min_height

    def resize_to_content(self) -> None:
        """
        Resize the block to the minimum size required by its ports.

        :return:
        """
        self.prepareGeometryChange()
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
        self.source_port: PortItem | BranchingItem | None = None
        self.context_item: BlockItem | ConnectionItem | None = None

    def change_item_fill_color(self, item: BlockItem | GenericBlockItem | ConnectionItem) -> None:
        """
        Change the color of a block or connection and persist it in the diagram.

        :param item:
        :return:
        """
        new_color: QColor = QColorDialog.getColor()

        if new_color.isValid():
            if isinstance(item, (BlockItem, GenericBlockItem)):
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

    def edit_context_item(self) -> None:
        """
        Open the hierarchy editor for the item currently selected by the context menu.

        :return: None.
        """
        if self.context_item is not None:
            self.editor.edit_scene_item(self.context_item)
        else:
            pass

    def modify_context_item_template(self) -> None:
        """
        Reopen the modal configuration for the selected block when available.

        :return: None.
        """
        if self.context_item is not None:
            self.editor.modify_scene_item_template(self.context_item)
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
            if isinstance(item, (BlockItem, GenericBlockItem, ConnectionItem)):
                menu: QMenu = QMenu()
                self.context_item = item

                if isinstance(item, (BlockItem, GenericBlockItem)):
                    if isinstance(item, BlockItem) and item.subsys is not None:
                        modal_kind, _modal_config = get_modal_template_metadata(item.subsys)
                    else:
                        modal_kind = None

                    if modal_kind is not None:
                        modify_action: QAction = QAction("Modify Template", menu)
                        modify_action.triggered.connect(self.modify_context_item_template)
                        menu.addAction(modify_action)
                    else:
                        pass

                    edit_action: QAction = QAction("Edit Hierarchy", menu)
                    edit_action.triggered.connect(self.edit_context_item)
                    menu.addAction(edit_action)
                else:
                    pass

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

            if isinstance(item, BranchingItem):

                self.source_port = item
                path: QPainterPath = QPainterPath(item.scenePos())
                self.temp_line = self.addPath(path, QPen(Qt.PenStyle.DashLine))
                return

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

            self.editor.mark_unapplied_changes()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """
        Handle double-click on the scene.
        If the click is on a ConnectionItem, create a BranchingItem and two new connections.

        :param event:
        :return:
        """
        item: QGraphicsItem

        # scene_position: QtCore.QPointF = self.editor.ui.graphicsView.mapToScene(
        #     int(event.position().x()),
        #     int(event.position().y())
        # )

        for item in self.items(event.scenePos()):
            if isinstance(item, ConnectionItem):
                connection: ConnectionItem = item
                source_port: PortItem = connection.source_port
                target_port: PortItem = connection.target_port

                branching_item: BranchingItem = BranchingItem(connection.source_port.subsystem,
                                                              connection.source_port.index)
                branching_item.setPos(event.scenePos())
                self.addItem(branching_item)

                conn1: ConnectionItem = ConnectionItem(
                    source_port, branching_item,
                    diagram=self.editor.diagram
                )
                self.addItem(conn1)

                conn2: ConnectionItem = ConnectionItem(
                    branching_item, target_port,
                    diagram=self.editor.diagram
                )
                self.addItem(conn2)

                self.editor.diagram.add_branch(
                    connectionitem_uid=conn1.uid,
                    device_uid_from=source_port.subsystem.subsys.uid,
                    device_uid_to=branching_item.subsystem.subsys.uid,
                    port_number_from=source_port.index,
                    port_number_to=0,
                    color=conn1.pen().color().name()
                )

                self.editor.diagram.add_branch(
                    connectionitem_uid=conn2.uid,
                    device_uid_from=branching_item.subsystem.subsys.uid,
                    device_uid_to=target_port.subsystem.subsys.uid,
                    port_number_from=0,
                    port_number_to=target_port.index,
                    color=conn2.pen().color().name()
                )

                if source_port.connections is not None and connection in source_port.connections:
                    source_port.connections.remove(connection)

                if target_port.connections is not None and connection in target_port.connections:
                    target_port.connections.remove(connection)

                if connection.uid in self.editor.diagram.con_data:
                    del self.editor.diagram.con_data[connection.uid]

                self.removeItem(connection)
                return

        super().mouseDoubleClickEvent(event)

    def connect_ports(self, source_port: PortItem | BranchingItem, target_port: PortItem) -> None:
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
            #
            if target_input_var.network_conn:
                source_block.subsys.update_model(dst_var, target_input_var)

                for key, value in self.editor.main_block.external_mapping.items():
                    if value is dst_var:
                        self.editor.main_block.external_mapping[key] = target_input_var
                    else:
                        pass

                    source_block.subsys.out_vars[source_port.index] = target_input_var
                    source_block.refresh_port_metadata()



            else:
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


@dataclass
class ConnectionVarSpec:
    """
    Specification of one connection variable exposed by the block editor.
    """

    direction: str
    reference: VarPowerFlowRefferenceType
    visible_name: str


class DynamicBlockEditorGUI(QtWidgets.QMainWindow):
    """
    DynamicModelEditorGUI
    """

    dirtyStateChanged = Signal(bool)

    def __init__(self,
                 var_factory: VarFactory,
                 block: Block,
                 api_object: ALL_DEV_TYPES | None = None,
                 mode: DynamicSimulationMode = DynamicSimulationMode.RMS,
                 templates_list: Optional[List[RmsModelTemplate | EmtModelTemplate | FmuTemplate]] = None,
                 circuit: Any | None = None,
                 main_editor=False,
                 modal: bool = True,
                 workspace_embedded: bool = False):
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
        :type mode: DynamicSimulationMode
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
        self.ui.deviceLabel.setText(api_object.name if api_object is not None else "")

        self.block_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 300
        self.mime_type: str = "application/x-veragrid-dynamics-block"

        self.setWindowTitle("Dynamic Model Editor")

        self.ui.splitter.setStretchFactor(0, 6)
        self.ui.splitter.setStretchFactor(1, 10)
        self.ui.block_editor_actionCheckModel.triggered.connect(self.open_inspect_dialog)
        self.ui.actionCenter.triggered.connect(self.center_view_on_items)
        self.ui.actionZoom_in.triggered.connect(self.zoom_in_view)
        self.ui.actionZoom_out.triggered.connect(self.zoom_out_view)

        self.var_factory = var_factory
        self.api_object = api_object

        # Todo: is this correct?
        self.original_block: Block = block  # api_object.rms_model

        try:
            if mode == DynamicSimulationMode.RMS and self.api_object.rms_template is not None:
                self.main_block: Block = Block()
            elif mode == DynamicSimulationMode.EMT and self.api_object.emt_template is not None:
                self.main_block: Block = Block()
            else:
                self.main_block: Block = clone_block_for_editing(block)

        except AttributeError:  # happens when editing templates from database (they are not connected to any physical device)
            self.main_block: Block = clone_block_for_editing(block)

        self.diagram: BlockDiagram = self.main_block.diagram
        self.circuit = circuit
        self.mode = mode
        self.main_editor = main_editor
        self.workspace_embedded = workspace_embedded
        self._emt_bus_fallback_warning_shown: bool = False
        self._selected_side_block: Block | None = None
        self.setWindowTitle(f"Dynamic Model Editor [{self.mode.name}]")
        self.block_counters: Dict[BlockType, int] = dict()
        self.scene: DiagramScene = DiagramScene(self)
        self.changes_applied: bool = False
        self.has_unapplied_changes: bool = False

        if self.workspace_embedded:
            self.menuBar().setVisible(False)
        else:
            pass

        self.templates_list: List[
            RmsModelTemplate | EmtModelTemplate | FmuTemplate] = templates_list if templates_list is not None else list()

        device_rms_related_blocks = {
            DeviceType.GeneratorDevice: [
                LibraryLeafSpec("Generic", BlockType.GENERIC),
                LibraryLeafSpec("Generator basic", BlockType.GENRAW),
                LibraryLeafSpec("Generator QEC", BlockType.GENQEC),
                LibraryLeafSpec("Governor", BlockType.GOV_RMS),
                LibraryLeafSpec("Stabilizer", BlockType.STAB_RMS),
                LibraryLeafSpec("Exciter", BlockType.EXCITER_RMS),
            ],
            DeviceType.LineDevice: [
                LibraryLeafSpec("Generic", BlockType.GENERIC),
                LibraryLeafSpec("Line", BlockType.LINE_RMS),
            ],
            DeviceType.LoadDevice: [
                LibraryLeafSpec("Generic", BlockType.GENERIC),
                LibraryLeafSpec("Load", BlockType.LOAD_RMS),
            ],
        }

        device_emt_related_blocks = {
            DeviceType.GeneratorDevice: [
                LibraryLeafSpec("Generic", BlockType.GENERIC),
                LibraryLeafSpec("Generator", BlockType.EMT_GENERATOR),
                LibraryLeafSpec("Thevenin eq. generator", BlockType.EMT_THEVENIN),
                LibraryLeafSpec("Governor", BlockType.GOV_EMT),
                LibraryLeafSpec("Stabilizer", BlockType.STAB_EMT),
                LibraryLeafSpec("Exciter", BlockType.EXCITER_EMT),
            ],
            DeviceType.LineDevice: [
                LibraryLeafSpec("Generic", BlockType.GENERIC),
                LibraryLeafSpec("Emt pi line", BlockType.EMT_PI_LINE),
                LibraryLeafSpec("Emt Bergeron line", BlockType.EMT_BERGERON_LINE),
                LibraryLeafSpec("Switch EMT", BlockType.SWITCH_EMT),
            ],
            DeviceType.LoadDevice: [
                LibraryLeafSpec("Generic", BlockType.GENERIC),
                LibraryLeafSpec("Ground EMT", BlockType.GROUND_EMT),
                LibraryLeafSpec("Grounding Link EMT", BlockType.GROUNDING_LINK_EMT),
                LibraryLeafSpec("Nonlinear Resistor EMT", BlockType.NONLINEAR_RESISTOR_EMT),
                LibraryLeafSpec("RLC Combo", BlockType.RLC_COMBO_EMT),
                LibraryLeafSpec("R load", BlockType.R_LOAD_EMT),
                LibraryLeafSpec("L load", BlockType.L_LOAD_EMT),
                LibraryLeafSpec("C load", BlockType.C_LOAD_EMT),
                LibraryLeafSpec("Exponential load", BlockType.EXP_LOAD_EMT),
                LibraryLeafSpec("ZIP load", BlockType.ZIP_LOAD_EMT),
                LibraryLeafSpec("DC load", BlockType.DC_LOAD_EMT),
            ],
            DeviceType.Transformer2WDevice: [
                LibraryLeafSpec("Generic", BlockType.GENERIC),
                LibraryLeafSpec("Transformer", BlockType.TRAFO_EMT),
                LibraryLeafSpec("XFMR Transformer", BlockType.XFMR_TRANSFORMER),
            ],
            DeviceType.TransformerTypeDevice: [
                LibraryLeafSpec("Generic", BlockType.GENERIC),
                LibraryLeafSpec("Transformer", BlockType.TRAFO_EMT),
                LibraryLeafSpec("XFMR Transformer", BlockType.XFMR_TRANSFORMER),
            ],
        }

        self.tree_structure: Dict[str, Any] = dict()
        if mode == DynamicSimulationMode.RMS:
            self.tree_structure["Basic"] = self.build_basic_library_branch()
            self.tree_structure["Devices"] = device_rms_related_blocks.get(api_object.device_type, dict())

        elif mode == DynamicSimulationMode.EMT:
            self.tree_structure["Basic"] = self.build_basic_library_branch()
            self.tree_structure["Devices"] = device_emt_related_blocks.get(api_object.device_type, dict())

        else:
            pass

        if self.templates_list:
            self.tree_structure["Templates"] = {
                "Available": [LibraryLeafSpec(template.name, template, template.name) for template in
                              self.templates_list]
            }
        else:
            pass

        # build and add library model
        self.library_model = self.build_library_tree_model(
            block_role=self.block_role,
            mime_type=self.mime_type
        )

        self.library_proxy_model = LibraryTreeFilterProxyModel(
            search_role=LIBRARY_SEARCH_TEXT_ROLE,
            parent=self.ui.libraryTreeView,
        )
        self.library_proxy_model.setSourceModel(self.library_model)

        self.ui.libraryTreeView.setModel(self.library_proxy_model)
        self.ui.libraryTreeView.setDragEnabled(True)
        self.ui.libraryTreeView.setHeaderHidden(False)
        self.ui.libraryTreeView.setUniformRowHeights(True)

        self.ui.librarySearchButton.setIcon(QtGui.QIcon(":/Icons/icons/magnifying_glass.png"))
        self.ui.librarySearchLineEdit.setVisible(True)
        self.ui.librarySearchLineEdit.setClearButtonEnabled(True)
        self.ui.librarySearchButton.clicked.connect(self.focus_library_search)
        self.ui.librarySearchLineEdit.textChanged.connect(self.on_library_search_text_changed)
        self.library_find_shortcut = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Find, self)
        self.library_find_shortcut.activated.connect(self.focus_library_search)
        self.reset_library_tree_expansion()

        self.variables_table_model = VariablesTableModel(
            var_factory=self.var_factory,
            parent=self.ui.variablesTableView
        )
        self.ui.variablesTableView.setModel(self.variables_table_model)
        variables_header: QtWidgets.QHeaderView = self.ui.variablesTableView.horizontalHeader()
        variables_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        variables_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        variables_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ui.variablesTableView.verticalHeader().setVisible(False)
        self.ui.variablesTableView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ui.variablesTableView.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.ui.variablesTableView.doubleClicked.connect(self.on_variables_table_double_clicked)
        self.ui.variablesTableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.variablesTableView.customContextMenuRequested.connect(self.show_variables_table_context_menu)

        self.parameters_table_model = ParametersTableModel(
            var_factory=self.var_factory,
            parent=self.ui.parametersTableView
        )
        self.ui.parametersTableView.setModel(self.parameters_table_model)
        parameters_header: QtWidgets.QHeaderView = self.ui.parametersTableView.horizontalHeader()
        parameters_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        parameters_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        parameters_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ui.parametersTableView.verticalHeader().setVisible(False)
        self.ui.parametersTableView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ui.parametersTableView.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.ui.parametersTableView.doubleClicked.connect(self.on_parameters_table_double_clicked)
        self.ui.parametersTableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.parametersTableView.customContextMenuRequested.connect(self.show_parameters_table_context_menu)

        self.equations_table_model = EquationsTableModel(
            var_factory=self.var_factory,
            parent=self.ui.equationsTableView
        )
        self.ui.equationsTableView.setModel(self.equations_table_model)
        equations_header: QtWidgets.QHeaderView = self.ui.equationsTableView.horizontalHeader()
        equations_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        equations_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        equations_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ui.equationsTableView.verticalHeader().setVisible(False)
        self.ui.equationsTableView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ui.equationsTableView.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.ui.equationsTableView.doubleClicked.connect(self.on_parameters_table_double_clicked)
        self.ui.equationsTableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.equationsTableView.customContextMenuRequested.connect(self.show_equations_table_context_menu)

        self.parameters_table_model.block_updated.connect(self.on_parameters_model_block_updated)
        self.variables_table_model.block_updated.connect(self.on_parameters_model_block_updated)

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
        self.ui.toolBox.currentChanged.connect(self.on_side_panel_page_changed)
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        if not self.main_block.diagram.node_data:
            # here we add the connection variables to the main block
            if self.main_editor:
                self.add_connection_vars()
                self.add_api_obj_mapping()
            self.add_connection_items()
        self.rebuild_scene_from_diagram()

        # for every in variable and our variable in the main block of the editor we build a block item to connect these variables

    @staticmethod
    def _insert_library_leaf(branch: Dict[str, Any], category_path: tuple[str, ...], leaf: LibraryLeafSpec) -> None:
        """
        Insert one library leaf into a nested dictionary branch.
        """

        head: str = category_path[0]
        if len(category_path) == 1:
            leaves: Any = branch.setdefault(head, list())
            if isinstance(leaves, list):
                leaves.append(leaf)
            else:
                raise TypeError(f"Category '{head}' is already used as a branch node")
        else:
            child_branch: Any = branch.setdefault(head, dict())
            if isinstance(child_branch, dict):
                DynamicBlockEditorGUI._insert_library_leaf(child_branch, category_path[1:], leaf)
            else:
                raise TypeError(f"Category '{head}' is already used as a leaf collection")

    def build_basic_block_catalog_branch(self) -> Dict[str, Any]:
        """
        Build the nested branch used to expose the imported basic block catalog.
        """

        # The catalog owns the static library skeleton so the GUI does not need to
        # duplicate category dictionaries that can drift during refactors.
        branch: Dict[str, Any] = build_basic_block_catalog_branch_skeleton()

        descriptor: BasicBlockTemplateDescriptor
        for descriptor in get_editor_ready_basic_block_catalog_descriptors():
            category_path: tuple[str, ...] = descriptor.category_path[1:] if descriptor.category_path and \
                                                                             descriptor.category_path[
                                                                                 0] == "Native" else descriptor.category_path
            if len(category_path) == 0:
                category_path = ("Miscellaneous", "Other")
            else:
                pass

            self._insert_library_leaf(
                branch=branch,
                category_path=category_path,
                leaf=LibraryLeafSpec(
                    label=descriptor.display_label,
                    payload=descriptor,
                    search_text=descriptor.search_text,
                ),
            )

        if len(branch["Miscellaneous"]["Other"]) == 0:
            del branch["Miscellaneous"]
        else:
            pass

        return branch

    def build_basic_library_branch(self) -> Dict[str, Any]:
        """
        Build the nested Basic branch used by both RMS and EMT editors.
        """

        native_branch: Dict[str, Any] = {
            "Arithmetic": [
                LibraryLeafSpec("Const", BlockType.CONST),
                LibraryLeafSpec("Gain", BlockType.GAIN),
                LibraryLeafSpec("Sum", BlockType.SUM),
                LibraryLeafSpec("Substr", BlockType.SUBSTR),
                LibraryLeafSpec("Product", BlockType.PRODUCT),
                LibraryLeafSpec("Divide", BlockType.DIVIDE),
                LibraryLeafSpec("Abs", BlockType.ABS),
            ],
        }
        native_branch.update(self.build_basic_block_catalog_branch())

        return {
            "Native": native_branch,
        }

    def focus_library_search(self) -> None:
        """
        Reveal and focus the library search box.
        """

        self.ui.toolBox.setCurrentWidget(self.ui.page_7)
        self.activateWindow()
        self.raise_()
        self.ui.librarySearchLineEdit.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
        self.ui.librarySearchLineEdit.selectAll()

    def reset_library_tree_expansion(self) -> None:
        """
        Restore the default expansion depth for the library tree.
        """

        self.ui.libraryTreeView.collapseAll()
        self.ui.libraryTreeView.expandToDepth(1)

    def on_library_search_text_changed(self, text: str) -> None:
        """
        Filter the library tree according to the current search text.
        """

        search_text: str = text.strip()
        self.library_proxy_model.setFilterFixedString(search_text)
        if search_text:
            self.ui.libraryTreeView.expandAll()
        else:
            self.reset_library_tree_expansion()

    @staticmethod
    def _set_library_item_icon(item: QtGui.QStandardItem, payload: object) -> None:
        """
        Apply the best matching icon for one draggable library leaf.
        """

        if isinstance(payload, FmuTemplate):
            item.setIcon(QtGui.QIcon(device_type_icons[DeviceType.FmuTemplateDevice.value]))
        elif isinstance(payload, RmsModelTemplate):
            item.setIcon(QtGui.QIcon(device_type_icons[DeviceType.RmsModelTemplateDevice.value]))
        elif isinstance(payload, (EmtModelTemplate, BasicBlockTemplateDescriptor)):
            item.setIcon(QtGui.QIcon(device_type_icons[DeviceType.EmtModelTemplateDevice.value]))
        else:
            pass

    def _append_library_branch(self,
                               model: DynamicsLibraryTreeModel,
                               parent_item: QtGui.QStandardItem,
                               branch_label: str,
                               branch_data: Any,
                               path_tokens: tuple[str, ...] = tuple()) -> None:
        """
        Append one recursive library branch into the tree model.
        """

        branch_item: QtGui.QStandardItem = QtGui.QStandardItem(branch_label)
        branch_item.setEditable(False)
        branch_item.setData(" ".join((*path_tokens, branch_label)).strip(), LIBRARY_SEARCH_TEXT_ROLE)
        parent_item.appendRow(branch_item)

        if len(path_tokens) == 0:
            category_icon_path: str | None = device_type_icons.get(branch_label, None)
            if category_icon_path is not None:
                branch_item.setIcon(QtGui.QIcon(category_icon_path))
            else:
                pass
        else:
            pass

        if isinstance(branch_data, dict):
            child_label: str
            child_data: Any
            for child_label, child_data in branch_data.items():
                self._append_library_branch(model, branch_item, child_label, child_data, (*path_tokens, branch_label))
        else:
            if isinstance(branch_data, list):
                leaf: LibraryLeafSpec
                for leaf in sorted(branch_data, key=_library_leaf_label_sort_key):
                    item: QtGui.QStandardItem = QtGui.QStandardItem(leaf.label)
                    item.setEditable(False)
                    item.setData(leaf.search_text if leaf.search_text else leaf.label, LIBRARY_SEARCH_TEXT_ROLE)
                    self._set_library_item_icon(item, leaf.payload)
                    model.register_drag_payload(item, leaf.payload)
                    branch_item.appendRow(item)
            else:
                raise TypeError(f"Unsupported library branch data type {type(branch_data)!r}")

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

        category: str
        branch_data: Any
        for category, branch_data in self.tree_structure.items():
            self._append_library_branch(model, root_item, category, branch_data)

        return model

    def get_library_payload_from_mime_data(self,
                                           mime_data: QtCore.QMimeData) -> BlockType | BasicBlockTemplateDescriptor | RmsModelTemplate | EmtModelTemplate | FmuTemplate | None:
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
            elif isinstance(payload, BasicBlockTemplateDescriptor):
                return payload
            elif isinstance(payload, (RmsModelTemplate, EmtModelTemplate, FmuTemplate)):
                return payload
            else:
                return None
        else:
            return None

    def _build_position_changed_callback(self, block_uid: int) -> BlockPositionChangedCallback:
        """
        Build the explicit callback object used by graphics items to report movement.

        :param block_uid: Moved block uid.
        :return: Position change callback wrapper.
        """

        return BlockPositionChangedCallback(self, block_uid)

    def create_generic_block_item(self, block_type: BlockType, x_pos, y_pos) -> GenericBlockItem | None:
        """
        Create and place a generic block item.

        :param block_type:
        :param x_pos:
        :param y_pos:
        :return:
        """

        dialog = GenericBlockDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, inputs, outputs = dialog.get_values()

            model = create_generic_block(self.var_factory, inputs, outputs, name)
            self.main_block.add(model)
            item = GenericBlockItem(
                var_factory=self.var_factory,
                subsys=model,
                api_object=self.api_object,
                mode=self.mode,
                position_changed_callback=self._build_position_changed_callback(model.uid)
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
                state_ins=inputs,
                state_outs=[],
                algeb_ins=0,
                algeb_outs=[],
                subdiagram=model.diagram
            )

            self.mark_unapplied_changes()

            return item
        else:
            return None

    def create_emt_wizard_block_item(self, block_type: BlockType, x_pos, y_pos) -> BlockItem | None:
        """
        Create and place a generic block item.

        :param block_type:
        :param x_pos:
        :param y_pos:
        :return:
        """

        dialog = EmtTemplateWizardDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            phase_n, phase_a, phase_b, phase_c = dialog.get_values()
            count: int = self.block_counters.get(block_type, 0) + 1
            item_name: str = f"{block_type.name}_{count}"
            block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
            block_model = create_emt_wizard_block(phase_n, phase_a, phase_b, phase_c, self.var_factory,
                                                  block_type=block_type, item_name=item_name)

            if block_model is not None:
                set_modal_template_metadata(
                    block_model,
                    kind="emt_phase_wizard",
                    config=dict({
                        "block_type": block_type.name,
                        "phase_n": phase_n,
                        "phase_a": phase_a,
                        "phase_b": phase_b,
                        "phase_c": phase_c,
                    }),
                )

                # The symbolic block has to be attached first so the graphics item can build its ports from it.
                self.block_counters[block_type] = count
                block_item.set_subsystem(block_model)
                block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
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

                self.mark_unapplied_changes()

                return block_item
            else:
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
            item_name=item_name,
            api_object=self.api_object,
        )

        if block_model is not None:
            # The symbolic block has to be attached first so the graphics item can build its ports from it.
            self.block_counters[block_type] = count
            block_item.set_subsystem(block_model)
            block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
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

            self.mark_unapplied_changes()

            return block_item
        else:
            return None

    def create_connection_block_item(self, var: Var, block_type: BlockType, x_pos: float,
                                     y_pos: float) -> BlockItem | None:
        """
        Create and place a block item in the canvas scene.

        :param var:
        :type var:
        :param block_type:
        :param x_pos:
        :param y_pos:
        :return:
        """
        count: int = self.block_counters.get(block_type, 0) + 1
        item_name: str = f"{var.name}"
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
        block_model: Block = Block()

        if block_type == BlockType.INPUT_CONN:
            block_model.out_vars.append(var)

        elif block_type == BlockType.OUTPUT_CONN:
            block_model.in_vars.append(var)

        if block_model is not None:
            # The symbolic block has to be attached first so the graphics item can build its ports from it.

            block_item.set_subsystem(block_model)
            block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
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

            return block_item
        else:
            return None

    def create_template_block_item(self,
                                   template: RmsModelTemplate | EmtModelTemplate | FmuTemplate,
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
        block_model: Block = duplicate_block(template.block, var_factory=self.var_factory)
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)

        if item_name:
            block_model.name = item_name
        else:
            item_name = block_model.name

        block_item.set_subsystem(block_model)
        block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
        block_item.build_item()
        self.main_block.add(block_model)
        self.scene.addItem(block_item)
        block_item.setPos(QtCore.QPointF(x_pos, y_pos))
        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=TEMPLATE_NODE_TYPE,
            device_uid=block_model.uid
        )

        self.mark_unapplied_changes()

        return block_item

    def create_lookup_array_linear_descriptor_item(self,
                                                   descriptor: BasicBlockTemplateDescriptor,
                                                   x_pos: float,
                                                   y_pos: float) -> BlockItem | None:
        """
        Materialize one modal-configured 1D lookup-table descriptor.

        :param descriptor: Lookup descriptor selected from the native catalog.
        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog: LookupArrayLinearDialog = LookupArrayLinearDialog(block_label=descriptor.display_label, parent=self)
        dialog_result: int = dialog.exec()

        if dialog_result == QDialog.DialogCode.Accepted:
            x_points, y_points = dialog.get_points()
        else:
            return None

        clip_enabled: bool = descriptor.template_key not in {
            "lookup_array_linear_noclipping",
            "lookup_array_object_linear_noclipping",
        }
        count: int = len(self.main_block.children) + 1
        item_name: str = f"{descriptor.template_key}_{count}"
        template: EmtModelTemplate = build_lookup_array_linear_runtime_template(
            vf=self.var_factory,
            x_points=x_points,
            y_points=y_points,
            clip=clip_enabled,
            name=item_name,
        )
        set_modal_template_metadata(
            template.block,
            kind="lookup_array_1d",
            config=dict({
                "descriptor_key": descriptor.template_key,
                "display_label": descriptor.display_label,
                "x_points": x_points,
                "y_points": y_points,
            }),
        )
        return self.create_template_block_item(template=template, x_pos=x_pos, y_pos=y_pos)

    def create_switch_emt_block_item(self, x_pos: float, y_pos: float) -> BlockItem | None:
        """
        Create one EMT switch block configured through the switch modal.

        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog = SwitchEmtDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            switch_config = dialog.get_switch_configuration()
            count: int = self.block_counters.get(BlockType.SWITCH_EMT, 0) + 1
            item_name: str = f"switch_emt_{count}"
            block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
            block_model = get_switch_emt_template(vf=self.var_factory, name=item_name, **switch_config).block
            set_modal_template_metadata(
                block_model,
                kind="switch_emt",
                config=dict(switch_config),
            )

            self.block_counters[BlockType.SWITCH_EMT] = count
            block_item.set_subsystem(block_model)
            block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
            block_item.build_item()
            self.main_block.add(block_model)
            self.scene.addItem(block_item)
            block_item.setPos(QtCore.QPointF(x_pos, y_pos))
            self.diagram.add_node(
                name=item_name,
                x=x_pos,
                y=y_pos,
                tpe=BlockType.SWITCH_EMT.name,
                device_uid=block_model.uid,
            )
            self.mark_unapplied_changes()
            return block_item
        else:
            return None

    def create_rlc_combo_emt_block_item(self, x_pos: float, y_pos: float) -> BlockItem | None:
        """
        Create one combined EMT RLC shunt block configured through its modal.

        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog = self._build_rlc_combo_emt_dialog()

        if dialog.exec() == QDialog.DialogCode.Accepted:
            rlc_config = dialog.get_configuration()
        else:
            return None

        try:
            template_kwargs = self._build_rlc_combo_emt_template_kwargs(rlc_config)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "RLC Combo", str(exc))
            return None

        count: int = self.block_counters.get(BlockType.RLC_COMBO_EMT, 0) + 1
        item_name: str = f"rlc_combo_emt_{count}"
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
        block_model = get_shunt_rlc_combo_emt_template(vf=self.var_factory, name=item_name, **template_kwargs).block
        set_modal_template_metadata(block_model, kind="rlc_combo_emt", config=dict(rlc_config))
        self._annotate_internal_grounding_link_blocks(block_model)
        self._sync_rlc_combo_load_base_values(template_kwargs)

        if isinstance(self.api_object, InjectionParent):
            try:
                self.api_object.conn = rlc_config["connection_type"]
            except Exception:
                pass
        else:
            pass

        self.block_counters[BlockType.RLC_COMBO_EMT] = count
        block_item.set_subsystem(block_model)
        block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
        block_item.build_item()
        self.main_block.add(block_model)
        self.scene.addItem(block_item)
        block_item.setPos(QtCore.QPointF(x_pos, y_pos))
        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=BlockType.RLC_COMBO_EMT.name,
            device_uid=block_model.uid,
        )
        self.mark_unapplied_changes()
        return block_item

    def create_shunt_component_emt_block_item(self,
                                              block_type: BlockType,
                                              x_pos: float,
                                              y_pos: float) -> BlockItem | None:
        """
        Create one modal-configured single-component EMT shunt block.

        :param block_type: ``R_LOAD_EMT``, ``L_LOAD_EMT`` or ``C_LOAD_EMT``.
        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog = self._build_shunt_component_emt_dialog(block_type=block_type)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            shunt_config = dialog.get_configuration()
        else:
            return None

        try:
            template_kwargs = self._build_shunt_component_emt_template_kwargs(block_type=block_type, modal_config=shunt_config)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "EMT Shunt", str(exc))
            return None

        count: int = self.block_counters.get(block_type, 0) + 1
        item_name: str = f"{block_type.name}_{count}"
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
        block_model = get_shunt_rlc_combo_emt_template(vf=self.var_factory, name=item_name, **template_kwargs).block
        set_modal_template_metadata(block_model, kind="shunt_component_emt", config=dict(shunt_config, block_type=block_type.name))
        self._annotate_internal_grounding_link_blocks(block_model)
        self._sync_rlc_combo_load_base_values(template_kwargs)

        if isinstance(self.api_object, InjectionParent):
            try:
                self.api_object.conn = shunt_config["connection_type"]
            except Exception:
                pass
        else:
            pass

        self.block_counters[block_type] = count
        block_item.set_subsystem(block_model)
        block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
        block_item.build_item()
        self.main_block.add(block_model)
        self.scene.addItem(block_item)
        block_item.setPos(QtCore.QPointF(x_pos, y_pos))
        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=block_type.name,
            device_uid=block_model.uid,
        )
        self.mark_unapplied_changes()
        return block_item

    def create_load_topology_emt_block_item(self,
                                            block_type: BlockType,
                                            x_pos: float,
                                            y_pos: float) -> BlockItem | None:
        """
        Create one modal-configured EMT load block with explicit neutral/ground topology.

        :param block_type: ``EXP_LOAD_EMT`` or ``ZIP_LOAD_EMT``.
        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog = self._build_load_topology_emt_dialog(block_type=block_type)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            load_config = dialog.get_configuration()
        else:
            return None

        count: int = self.block_counters.get(block_type, 0) + 1
        item_name: str = f"{block_type.name}_{count}"
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
        block_model = self._build_load_topology_emt_block_model(
            block_type=block_type,
            item_name=item_name,
            modal_config=load_config,
        )
        if block_model is None:
            return None
        else:
            pass

        set_modal_template_metadata(block_model, kind="load_topology_emt", config=dict(load_config, block_type=block_type.name))
        self._annotate_internal_grounding_link_blocks(block_model)

        if isinstance(self.api_object, InjectionParent):
            try:
                self.api_object.conn = load_config["connection_type"]
            except Exception:
                pass
        else:
            pass

        self.block_counters[block_type] = count
        block_item.set_subsystem(block_model)
        block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
        block_item.build_item()
        self.main_block.add(block_model)
        self.scene.addItem(block_item)
        block_item.setPos(QtCore.QPointF(x_pos, y_pos))
        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=block_type.name,
            device_uid=block_model.uid,
        )
        self.mark_unapplied_changes()
        return block_item

    def create_grounding_link_emt_block_item(self, x_pos: float, y_pos: float) -> BlockItem | None:
        """
        Create one modal-configured EMT grounding-link block.

        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog = self._build_grounding_link_emt_dialog()

        if dialog.exec() == QDialog.DialogCode.Accepted:
            grounding_config = dialog.get_configuration()
        else:
            return None

        try:
            template_kwargs = self._build_grounding_link_emt_template_kwargs(grounding_config)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Grounding Link", str(exc))
            return None

        count: int = self.block_counters.get(BlockType.GROUNDING_LINK_EMT, 0) + 1
        item_name: str = f"grounding_link_emt_{count}"
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
        block_model = get_grounding_link_emt_template(vf=self.var_factory, name=item_name, **template_kwargs).block
        set_modal_template_metadata(block_model, kind="grounding_link_emt", config=dict(grounding_config))

        self.block_counters[BlockType.GROUNDING_LINK_EMT] = count
        block_item.set_subsystem(block_model)
        block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
        block_item.build_item()
        self.main_block.add(block_model)
        self.scene.addItem(block_item)
        block_item.setPos(QtCore.QPointF(x_pos, y_pos))
        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=BlockType.GROUNDING_LINK_EMT.name,
            device_uid=block_model.uid,
        )
        self.mark_unapplied_changes()
        return block_item

    def create_nonlinear_resistor_emt_block_item(self, x_pos: float, y_pos: float) -> BlockItem | None:
        """
        Create one modal-configured ATP-like EMT nonlinear resistor block.

        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog = LookupArrayLinearDialog(
            block_label="Nonlinear resistor EMT V-I curve",
            initial_points=list([(0.0, 0.0), (1.0, 0.1), (1.5, 1.0), (2.0, 10.0)]),
            parent=self,
            x_label="V",
            y_label="I",
            preview_enabled=True,
            preview_title="Nonlinear resistor EMT V-I curve",
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            voltage_points, current_points = dialog.get_points()
        else:
            return None

        count: int = self.block_counters.get(BlockType.NONLINEAR_RESISTOR_EMT, 0) + 1
        item_name: str = f"nonlinear_resistor_emt_{count}"
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
        block_model = get_nonlinear_resistor_emt_template(
            vf=self.var_factory,
            voltage_points=voltage_points,
            current_points=current_points,
            name=item_name,
        ).block
        set_modal_template_metadata(
            block_model,
            kind="nonlinear_resistor_emt",
            config=dict({
                "voltage_points": voltage_points,
                "current_points": current_points,
            }),
        )

        self.block_counters[BlockType.NONLINEAR_RESISTOR_EMT] = count
        block_item.set_subsystem(block_model)
        block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
        block_item.build_item()
        self.main_block.add(block_model)
        self.scene.addItem(block_item)
        block_item.setPos(QtCore.QPointF(x_pos, y_pos))
        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=BlockType.NONLINEAR_RESISTOR_EMT.name,
            device_uid=block_model.uid,
        )
        self.mark_unapplied_changes()
        return block_item

    def create_transformer_topology_emt_block_item(self,
                                                   block_type: BlockType,
                                                   x_pos: float,
                                                   y_pos: float) -> BlockItem | None:
        """
        Create one modal-configured EMT transformer block.

        :param block_type: ``TRAFO_EMT`` or ``XFMR_TRANSFORMER``.
        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        topology_config: Dict[str, Any] | None = self._resolve_transformer_topology_configuration()

        if topology_config is None:
            dialog = self._build_transformer_topology_emt_dialog(block_type=block_type)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                topology_config = dialog.get_configuration()
            else:
                return None
        else:
            topology_config = dict(topology_config)

        count: int = self.block_counters.get(block_type, 0) + 1
        item_name: str = f"{block_type.name}_{count}"
        block_item: BlockItem = BlockItem(var_factory=self.var_factory, name=item_name)
        block_model = self._build_transformer_topology_emt_block_model(
            block_type=block_type,
            item_name=item_name,
            modal_config=topology_config,
        )

        if block_model is None:
            return None
        else:
            pass

        set_modal_template_metadata(block_model, kind="transformer_topology_emt", config=dict(topology_config, block_type=block_type.name))

        if isinstance(self.api_object, BranchParent):
            try:
                self.api_object.conn_f = topology_config["conn_f"]
                self.api_object.conn_t = topology_config["conn_t"]
            except Exception:
                pass
        else:
            pass

        self.block_counters[block_type] = count
        block_item.set_subsystem(block_model)
        block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
        block_item.build_item()
        self.main_block.add(block_model)
        self.scene.addItem(block_item)
        block_item.setPos(QtCore.QPointF(x_pos, y_pos))
        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=block_type.name,
            device_uid=block_model.uid,
        )
        self.mark_unapplied_changes()
        return block_item

    def _resolve_transformer_topology_configuration(self) -> Dict[str, Any] | None:
        """
        Resolve one EMT transformer topology directly from the bound API object.

        When the editor is attached to one real transformer device or one
        transformer-type object, the winding connections already belong to that
        object and should not be asked again through a modal dialog.

        :return: Resolved topology configuration or ``None`` when unavailable.
        """
        if isinstance(self.api_object, Transformer2W):
            return dict({
                "conn_f": self.api_object.conn_f,
                "conn_t": self.api_object.conn_t,
            })
        else:
            if isinstance(self.api_object, TransformerType):
                return dict({
                    "conn_f": self.api_object.conn_hv,
                    "conn_t": self.api_object.conn_lv,
                })
            else:
                return None

    def _build_rlc_combo_emt_dialog(self,
                                    initial_config: Dict[str, Any] | None = None) -> RlcComboEmtDialog:
        """
        Build the modal dialog used by the EMT combined RLC workflow.

        :param initial_config: Optional persisted modal configuration.
        :return: Configured dialog instance.
        """
        nominal_voltage_kv, base_power_mva, base_frequency_hz = self._get_rlc_combo_base_values()
        return RlcComboEmtDialog(
            self,
            initial_config=initial_config,
            nominal_voltage_kv=nominal_voltage_kv,
            base_power_mva=base_power_mva,
            base_frequency_hz=base_frequency_hz,
        )

    def _build_grounding_link_emt_dialog(self,
                                         initial_config: Dict[str, Any] | None = None) -> GroundingLinkEmtDialog:
        """
        Build the modal dialog used by the EMT grounding-link workflow.

        :param initial_config: Optional persisted modal configuration.
        :return: Configured dialog instance.
        """
        nominal_voltage_kv, base_power_mva, base_frequency_hz = self._get_rlc_combo_base_values()
        return GroundingLinkEmtDialog(
            self,
            initial_config=initial_config,
            nominal_voltage_kv=nominal_voltage_kv,
            base_power_mva=base_power_mva,
            base_frequency_hz=base_frequency_hz,
        )

    def _build_shunt_component_emt_dialog(self,
                                          block_type: BlockType,
                                          initial_config: Dict[str, Any] | None = None) -> ShuntComponentEmtDialog:
        """
        Build the modal dialog used by one simple EMT shunt block.

        :param block_type: ``R_LOAD_EMT``, ``L_LOAD_EMT`` or ``C_LOAD_EMT``.
        :param initial_config: Optional persisted modal configuration.
        :return: Configured dialog instance.
        """
        component_kind: str | None = _get_shunt_component_kind(block_type)
        nominal_voltage_kv, base_power_mva, base_frequency_hz = self._get_rlc_combo_base_values()

        if component_kind is None:
            raise ValueError(f"Unsupported simple EMT shunt block type '{block_type.name}'")
        else:
            pass

        return ShuntComponentEmtDialog(
            component_kind=component_kind,
            parent=self,
            initial_config=initial_config,
            nominal_voltage_kv=nominal_voltage_kv,
            base_power_mva=base_power_mva,
            base_frequency_hz=base_frequency_hz,
        )

    @staticmethod
    def _get_transformer_topology_dialog_title(block_type: BlockType) -> str:
        """
        Return the dialog title for one EMT transformer block.

        :param block_type: ``TRAFO_EMT`` or ``XFMR_TRANSFORMER``.
        :return: Window title.
        """
        if block_type == BlockType.TRAFO_EMT:
            return "Configure EMT Transformer Topology"
        elif block_type == BlockType.XFMR_TRANSFORMER:
            return "Configure EMT XFMR Transformer Topology"
        else:
            raise ValueError(f"Unsupported EMT transformer block type '{block_type.name}'")

    def _build_transformer_topology_emt_dialog(self,
                                               block_type: BlockType,
                                               initial_config: Dict[str, Any] | None = None) -> TransformerTopologyEmtDialog:
        """
        Build the modal dialog used by one EMT transformer block.

        :param block_type: ``TRAFO_EMT`` or ``XFMR_TRANSFORMER``.
        :param initial_config: Optional persisted modal configuration.
        :return: Configured dialog instance.
        """
        resolved_config: Dict[str, Any]
        if initial_config is not None:
            resolved_config = dict(initial_config)
        else:
            auto_config: Dict[str, Any] | None = self._resolve_transformer_topology_configuration()

            if auto_config is not None:
                resolved_config = auto_config
            else:
                resolved_config = dict({
                    "conn_f": WindingType.GroundedStar,
                    "conn_t": WindingType.GroundedStar,
                })

        return TransformerTopologyEmtDialog(
            title=self._get_transformer_topology_dialog_title(block_type),
            parent=self,
            initial_config=resolved_config,
        )

    @staticmethod
    def _get_load_topology_dialog_title(block_type: BlockType) -> str:
        """
        Return the dialog title for one EMT load-topology block.

        :param block_type: ``EXP_LOAD_EMT`` or ``ZIP_LOAD_EMT``.
        :return: Window title.
        """
        if block_type == BlockType.EXP_LOAD_EMT:
            return "Configure EMT Exponential Load"
        elif block_type == BlockType.ZIP_LOAD_EMT:
            return "Configure EMT ZIP Load"
        else:
            raise ValueError(f"Unsupported EMT load-topology block type '{block_type.name}'")

    def _build_load_topology_emt_dialog(self,
                                        block_type: BlockType,
                                        initial_config: Dict[str, Any] | None = None) -> LoadTopologyEmtDialog:
        """
        Build the modal dialog used by one EMT load-topology block.

        :param block_type: ``EXP_LOAD_EMT`` or ``ZIP_LOAD_EMT``.
        :param initial_config: Optional persisted modal configuration.
        :return: Configured dialog instance.
        """
        return LoadTopologyEmtDialog(
            title=self._get_load_topology_dialog_title(block_type),
            parent=self,
            initial_config=initial_config,
        )

    @staticmethod
    def _annotate_internal_grounding_link_blocks(block_model: Block) -> None:
        """
        Attach modal metadata to auto-generated internal grounding-link blocks.

        :param block_model: Parent block that may own nested grounding-link children.
        :return: None.
        """
        child_block: Block
        grounding_config: Dict[str, Any] = dict({
            "solid_connection": True,
            "include_r": False,
            "include_l": False,
            "include_c": False,
            "input_mode": "physical",
            "resistance_ohm": 1.0,
            "inductive_value": 0.01,
            "capacitive_value": 1.0e-6,
        })

        for child_block in _iter_child_blocks(block_model):
            if child_block.name.endswith("_grounding_link"):
                set_modal_template_metadata(child_block, kind="grounding_link_emt", config=grounding_config)
            else:
                pass

    def _get_rlc_combo_base_values(self) -> tuple[float | None, float | None, float | None]:
        """
        Resolve the host base values used by the EMT combined RLC modal.

        :return: ``(Vnom_kV, Sbase_MVA, fbase_Hz)`` tuple.
        """
        nominal_voltage_kv: float | None = None
        base_power_mva: float | None = None
        base_frequency_hz: float | None = None

        if isinstance(self.api_object, InjectionParent):
            bus = self.api_object.bus
            if bus is not None:
                try:
                    nominal_voltage_kv = float(bus.Vnom)
                except (TypeError, ValueError):
                    nominal_voltage_kv = None
            else:
                pass
        else:
            pass

        if self.circuit is not None:
            try:
                base_power_mva = float(self.circuit.Sbase)
            except (AttributeError, TypeError, ValueError):
                base_power_mva = None

            try:
                base_frequency_hz = float(self.circuit.fBase)
            except (AttributeError, TypeError, ValueError):
                base_frequency_hz = None
        else:
            pass

        return nominal_voltage_kv, base_power_mva, base_frequency_hz

    def _get_rlc_combo_base_frequency_hz(self) -> float:
        """
        Return the frequency used to convert reactances into EMT L/C values.

        :return: Frequency in hertz.
        """
        _, _, base_frequency_hz = self._get_rlc_combo_base_values()

        if base_frequency_hz is not None and base_frequency_hz > 0.0:
            return base_frequency_hz
        else:
            return 50.0

    def _build_rlc_direct_values_from_modal_config(self, modal_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert one R/L/C modal configuration into direct EMT values.

        :param modal_config: Raw modal configuration.
        :return: Direct-value dictionary shared by EMT RLC modal builders.
        :raises ValueError: If the modal configuration is not numerically valid.
        """
        include_r: bool = bool(modal_config.get("include_r", False))
        include_l: bool = bool(modal_config.get("include_l", False))
        include_c: bool = bool(modal_config.get("include_c", False))
        solid_connection: bool = bool(modal_config.get("solid_connection", False))
        input_mode: str = str(modal_config.get("input_mode", "physical"))
        resistance_ohm: float = float(modal_config.get("resistance_ohm", 1.0))
        inductive_value: float = float(modal_config.get("inductive_value", 0.01))
        capacitive_value: float = float(modal_config.get("capacitive_value", 1.0e-6))
        angular_frequency: float = 2.0 * math.pi * self._get_rlc_combo_base_frequency_hz()

        if solid_connection:
            return dict({
                "solid_connection": True,
                "include_r": False,
                "include_l": False,
                "include_c": False,
                "direct_r_value": None,
                "direct_l_value": None,
                "direct_c_value": None,
            })
        else:
            pass

        if input_mode in {"physical", "reactance"}:
            pass
        else:
            raise ValueError(f"Unsupported RLC input mode '{input_mode}'.")

        if include_r and resistance_ohm <= 0.0:
            raise ValueError("Resistance must be greater than zero when the resistor branch is enabled.")
        else:
            pass

        if include_l and inductive_value <= 0.0:
            if input_mode == "reactance":
                raise ValueError("Inductive reactance must be greater than zero when the inductor branch is enabled.")
            else:
                raise ValueError("Inductance must be greater than zero when the inductor branch is enabled.")
        else:
            pass

        if include_c and capacitive_value <= 0.0:
            if input_mode == "reactance":
                raise ValueError("Capacitive reactance must be greater than zero when the capacitor branch is enabled.")
            else:
                raise ValueError("Capacitance must be greater than zero when the capacitor branch is enabled.")
        else:
            pass

        direct_l_value: float | None = None
        if include_l:
            if input_mode == "physical":
                direct_l_value = inductive_value
            else:
                direct_l_value = inductive_value / angular_frequency
        else:
            pass

        direct_c_value: float | None = None
        if include_c:
            if input_mode == "physical":
                direct_c_value = capacitive_value
            else:
                direct_c_value = 1.0 / (angular_frequency * capacitive_value)
        else:
            pass

        return dict({
            "solid_connection": False,
            "include_r": include_r,
            "include_l": include_l,
            "include_c": include_c,
            "direct_r_value": resistance_ohm if include_r else None,
            "direct_l_value": direct_l_value,
            "direct_c_value": direct_c_value,
        })

    def _build_rlc_combo_emt_template_kwargs(self, modal_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert one modal configuration into the EMT template builder arguments.

        ``Physical R/L/C`` values are forwarded directly. ``R + Reactances`` is
        converted into the physical inductance and capacitance expected by the
        current EMT child templates.

        :param modal_config: Raw modal configuration.
        :return: Template-builder keyword arguments.
        :raises ValueError: If the modal configuration is not numerically valid.
        """
        template_kwargs: Dict[str, Any] = dict(self._build_rlc_direct_values_from_modal_config(modal_config))
        if "solid_connection" in template_kwargs:
            del template_kwargs["solid_connection"]
        else:
            pass
        template_kwargs.update({
            "phA": bool(modal_config.get("phA", True)),
            "phB": bool(modal_config.get("phB", True)),
            "phC": bool(modal_config.get("phC", True)),
            "connection_type": modal_config.get("connection_type", ShuntConnectionType.GroundedStar),
        })

        return template_kwargs

    def _build_grounding_link_emt_template_kwargs(self, modal_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert one grounding-link modal configuration into template arguments.

        :param modal_config: Raw modal configuration.
        :return: Template-builder keyword arguments.
        """
        return self._build_rlc_direct_values_from_modal_config(modal_config)

    def _build_shunt_component_emt_template_kwargs(self,
                                                   block_type: BlockType,
                                                   modal_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert one single-component EMT shunt modal configuration into template arguments.

        :param block_type: ``R_LOAD_EMT``, ``L_LOAD_EMT`` or ``C_LOAD_EMT``.
        :param modal_config: Raw modal configuration.
        :return: Template-builder keyword arguments.
        """
        template_kwargs: Dict[str, Any] = dict(self._build_rlc_direct_values_from_modal_config(modal_config))
        if "solid_connection" in template_kwargs:
            del template_kwargs["solid_connection"]
        else:
            pass

        component_kind: str | None = _get_shunt_component_kind(block_type)
        if component_kind == "R":
            template_kwargs["include_r"] = True
            template_kwargs["include_l"] = False
            template_kwargs["include_c"] = False
        elif component_kind == "L":
            template_kwargs["include_r"] = False
            template_kwargs["include_l"] = True
            template_kwargs["include_c"] = False
        elif component_kind == "C":
            template_kwargs["include_r"] = False
            template_kwargs["include_l"] = False
            template_kwargs["include_c"] = True
        else:
            raise ValueError(f"Unsupported simple EMT shunt block type '{block_type.name}'")

        template_kwargs.update({
            "phA": bool(modal_config.get("phA", True)),
            "phB": bool(modal_config.get("phB", True)),
            "phC": bool(modal_config.get("phC", True)),
            "connection_type": modal_config.get("connection_type", ShuntConnectionType.GroundedStar),
        })
        return template_kwargs

    def _build_load_topology_emt_block_model(self,
                                             block_type: BlockType,
                                             item_name: str,
                                             modal_config: Dict[str, Any]) -> Block | None:
        """
        Build one EMT load block with explicit neutral/ground topology.

        :param block_type: ``EXP_LOAD_EMT`` or ``ZIP_LOAD_EMT``.
        :param item_name: Symbolic block name.
        :param modal_config: Modal configuration.
        :return: Block model or ``None``.
        """
        ph_a: bool = bool(modal_config.get("phA", True))
        ph_b: bool = bool(modal_config.get("phB", True))
        ph_c: bool = bool(modal_config.get("phC", True))
        connection_type = modal_config.get("connection_type", ShuntConnectionType.GroundedStar)

        if block_type == BlockType.EXP_LOAD_EMT:
            block_model = get_exponential_load_emt(
                vf=self.var_factory,
                phA=ph_a,
                phB=ph_b,
                phC=ph_c,
                connection_type=connection_type,
                name=item_name,
            ).block
        elif block_type == BlockType.ZIP_LOAD_EMT:
            block_model = get_load_ZIP_emt_template(
                vf=self.var_factory,
                phA=ph_a,
                phB=ph_b,
                phC=ph_c,
                connection_type=connection_type,
                name=item_name,
            ).block
        else:
            raise ValueError(f"Unsupported EMT load-topology block type '{block_type.name}'")

        block_model.name = item_name
        return block_model

    def _build_transformer_topology_emt_block_model(self,
                                                    block_type: BlockType,
                                                    item_name: str,
                                                    modal_config: Dict[str, Any]) -> Block | None:
        """
        Build one EMT transformer block with explicit winding topology.

        :param block_type: ``TRAFO_EMT`` or ``XFMR_TRANSFORMER``.
        :param item_name: Symbolic block name.
        :param modal_config: Modal configuration.
        :return: Block model or ``None``.
        """
        conn_f = modal_config.get("conn_f", WindingType.GroundedStar)
        conn_t = modal_config.get("conn_t", WindingType.GroundedStar)

        if block_type == BlockType.TRAFO_EMT:
            block_model = create_block_of_type(
                var_factory=self.var_factory,
                block_type=block_type,
                item_name=item_name,
                api_object=type("_TrafoApiConfig", (), {"conn_f": conn_f, "conn_t": conn_t})(),
            )
        elif block_type == BlockType.XFMR_TRANSFORMER:
            block_model = create_block_of_type(
                var_factory=self.var_factory,
                block_type=block_type,
                item_name=item_name,
                api_object=type("_XfmrApiConfig", (), {"conn_f": conn_f, "conn_t": conn_t})(),
            )
        else:
            raise ValueError(f"Unsupported EMT transformer block type '{block_type.name}'")

        if block_model is None:
            return None
        else:
            block_model.name = item_name
            return block_model

    def _sync_rlc_combo_load_base_values(self, template_kwargs: Dict[str, Any]) -> None:
        """
        Sync one real load API object with the equivalent RLC snapshot powers.

        The combined EMT template now stores physical R/L/C values directly so it
        can work standalone. When the editor is attached to a real load, we also
        refresh the load snapshot powers so the power-flow-based EMT initialization
        stays aligned with the same electrical values.

        :param template_kwargs: Resolved EMT template arguments.
        :return: None.
        """
        if isinstance(self.api_object, Load):
            load: Load = self.api_object
        else:
            return

        if load.bus is None or load.bus.is_dc:
            return
        else:
            pass

        nominal_voltage_kv: float = float(load.bus.Vnom)
        phase_voltage_kv: float = nominal_voltage_kv / math.sqrt(3.0)
        phase_voltage_sq: float = phase_voltage_kv * phase_voltage_kv
        line_voltage_sq: float = nominal_voltage_kv * nominal_voltage_kv
        angular_frequency: float = 2.0 * math.pi * self._get_rlc_combo_base_frequency_hz()
        direct_r_value: float | None = template_kwargs.get("direct_r_value", None)
        direct_l_value: float | None = template_kwargs.get("direct_l_value", None)
        direct_c_value: float | None = template_kwargs.get("direct_c_value", None)
        connection_type = template_kwargs.get("connection_type", ShuntConnectionType.GroundedStar)
        phase_enabled: List[bool] = list([
            bool(template_kwargs.get("phA", True)),
            bool(template_kwargs.get("phB", True)),
            bool(template_kwargs.get("phC", True)),
        ])
        active_powers: List[float] = list([0.0, 0.0, 0.0])
        reactive_powers: List[float] = list([0.0, 0.0, 0.0])
        idx: int

        if connection_type == ShuntConnectionType.Delta:
            branch_specs: list[tuple[int, int, int]] = list()
            if phase_enabled[0] and phase_enabled[1]:
                branch_specs.append((0, 0, 1))
            else:
                pass

            if phase_enabled[1] and phase_enabled[2]:
                branch_specs.append((1, 1, 2))
            else:
                pass

            if phase_enabled[2] and phase_enabled[0]:
                branch_specs.append((2, 2, 0))
            else:
                pass

            for idx, _phase_from, _phase_to in branch_specs:
                if direct_r_value is not None:
                    active_powers[idx] = active_powers[idx] + line_voltage_sq / direct_r_value
                else:
                    pass

                if direct_l_value is not None:
                    reactive_powers[idx] = reactive_powers[idx] + line_voltage_sq / (angular_frequency * direct_l_value)
                else:
                    pass

                if direct_c_value is not None:
                    reactive_powers[idx] = reactive_powers[idx] + line_voltage_sq * angular_frequency * direct_c_value
                else:
                    pass
        else:
            for idx in range(3):
                if phase_enabled[idx]:
                    if direct_r_value is not None:
                        active_powers[idx] = active_powers[idx] + phase_voltage_sq / direct_r_value
                    else:
                        pass

                    if direct_l_value is not None:
                        reactive_powers[idx] = reactive_powers[idx] + phase_voltage_sq / (angular_frequency * direct_l_value)
                    else:
                        pass

                    if direct_c_value is not None:
                        reactive_powers[idx] = reactive_powers[idx] + phase_voltage_sq * angular_frequency * direct_c_value
                    else:
                        pass
                else:
                    pass

        load.Pa = active_powers[0]
        load.Pb = active_powers[1]
        load.Pc = active_powers[2]
        load.Qa = reactive_powers[0]
        load.Qb = reactive_powers[1]
        load.Qc = reactive_powers[2]
        load.P = sum(active_powers)
        load.Q = sum(reactive_powers)
        load.Pa_prof.default_value = load.Pa
        load.Pb_prof.default_value = load.Pb
        load.Pc_prof.default_value = load.Pc
        load.Qa_prof.default_value = load.Qa
        load.Qb_prof.default_value = load.Qb
        load.Qc_prof.default_value = load.Qc
        load.P_prof.default_value = load.P
        load.Q_prof.default_value = load.Q

    def create_inverse_lookup_array_linear_descriptor_item(self,
                                                           descriptor: BasicBlockTemplateDescriptor,
                                                           x_pos: float,
                                                           y_pos: float) -> BlockItem | None:
        """
        Materialize one modal-configured inverse 1D lookup-table descriptor.

        :param descriptor: Lookup descriptor selected from the native catalog.
        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog: LookupArrayLinearDialog = LookupArrayLinearDialog(block_label=descriptor.display_label, parent=self)
        dialog_result: int = dialog.exec()

        if dialog_result == QDialog.DialogCode.Accepted:
            x_points, y_points = dialog.get_points()
        else:
            return None

        count: int = len(self.main_block.children) + 1
        item_name: str = f"{descriptor.template_key}_{count}"
        template: EmtModelTemplate = build_inverse_lookup_array_linear_runtime_template(
            vf=self.var_factory,
            x_points=x_points,
            y_points=y_points,
            name=item_name,
        )
        set_modal_template_metadata(
            template.block,
            kind="lookup_array_inverse",
            config=dict({
                "descriptor_key": descriptor.template_key,
                "display_label": descriptor.display_label,
                "x_points": x_points,
                "y_points": y_points,
            }),
        )
        return self.create_template_block_item(template=template, x_pos=x_pos, y_pos=y_pos)

    def create_lookup_array_spline_descriptor_item(self,
                                                   descriptor: BasicBlockTemplateDescriptor,
                                                   x_pos: float,
                                                   y_pos: float) -> BlockItem | None:
        """
        Materialize one modal-configured 1D spline lookup descriptor.

        :param descriptor: Lookup descriptor selected from the native catalog.
        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog: LookupArrayLinearDialog = LookupArrayLinearDialog(block_label=descriptor.display_label, parent=self)
        dialog_result: int = dialog.exec()

        if dialog_result == QDialog.DialogCode.Accepted:
            x_points, y_points = dialog.get_points()
        else:
            return None

        count: int = len(self.main_block.children) + 1
        item_name: str = f"{descriptor.template_key}_{count}"
        template: EmtModelTemplate = build_lookup_array_spline_runtime_template(
            vf=self.var_factory,
            x_points=x_points,
            y_points=y_points,
            name=item_name,
        )
        set_modal_template_metadata(
            template.block,
            kind="lookup_array_spline",
            config=dict({
                "descriptor_key": descriptor.template_key,
                "display_label": descriptor.display_label,
                "x_points": x_points,
                "y_points": y_points,
            }),
        )
        return self.create_template_block_item(template=template, x_pos=x_pos, y_pos=y_pos)

    def create_lookup_matrix_linear_descriptor_item(self,
                                                    descriptor: BasicBlockTemplateDescriptor,
                                                    x_pos: float,
                                                    y_pos: float) -> BlockItem | None:
        """
        Materialize one modal-configured 2D lookup-matrix descriptor.

        :param descriptor: Lookup descriptor selected from the native catalog.
        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog: LookupMatrixLinearDialog = LookupMatrixLinearDialog(block_label=descriptor.display_label, parent=self)
        dialog_result: int = dialog.exec()

        if dialog_result == QDialog.DialogCode.Accepted:
            x_points, y_points, z_matrix = dialog.get_matrix_data()
        else:
            return None

        count: int = len(self.main_block.children) + 1
        item_name: str = f"{descriptor.template_key}_{count}"
        template: EmtModelTemplate = build_lookup_matrix_linear_runtime_template(
            vf=self.var_factory,
            x_points=x_points,
            y_points=y_points,
            z_matrix=z_matrix,
            name=item_name,
        )
        set_modal_template_metadata(
            template.block,
            kind="lookup_matrix_linear",
            config=dict({
                "descriptor_key": descriptor.template_key,
                "display_label": descriptor.display_label,
                "x_points": x_points,
                "y_points": y_points,
                "z_matrix": z_matrix,
            }),
        )
        return self.create_template_block_item(template=template, x_pos=x_pos, y_pos=y_pos)

    def create_lookup_matrix_spline_descriptor_item(self,
                                                    descriptor: BasicBlockTemplateDescriptor,
                                                    x_pos: float,
                                                    y_pos: float) -> BlockItem | None:
        """
        Materialize one modal-configured 2D spline lookup-matrix descriptor.

        :param descriptor: Lookup descriptor selected from the native catalog.
        :param x_pos: Drop x position.
        :param y_pos: Drop y position.
        :return: Created block item or None when the dialog is cancelled.
        """
        dialog: LookupMatrixLinearDialog = LookupMatrixLinearDialog(block_label=descriptor.display_label, parent=self)
        dialog_result: int = dialog.exec()

        if dialog_result == QDialog.DialogCode.Accepted:
            x_points, y_points, z_matrix = dialog.get_matrix_data()
        else:
            return None

        count: int = len(self.main_block.children) + 1
        item_name: str = f"{descriptor.template_key}_{count}"
        template: EmtModelTemplate = build_lookup_matrix_spline_runtime_template(
            vf=self.var_factory,
            x_points=x_points,
            y_points=y_points,
            z_matrix=z_matrix,
            name=item_name,
        )
        set_modal_template_metadata(
            template.block,
            kind="lookup_matrix_spline",
            config=dict({
                "descriptor_key": descriptor.template_key,
                "display_label": descriptor.display_label,
                "x_points": x_points,
                "y_points": y_points,
                "z_matrix": z_matrix,
            }),
        )
        return self.create_template_block_item(template=template, x_pos=x_pos, y_pos=y_pos)

    def create_library_payload_item(self,
                                    payload: BlockType | BasicBlockTemplateDescriptor | RmsModelTemplate | EmtModelTemplate | FmuTemplate,
                                    x_pos: float,
                                    y_pos: float) -> BlockItem | None:
        """
        Materialize one library payload on the diagram scene.
        """

        if isinstance(payload, BlockType) and payload == BlockType.GENERIC:
            return self.create_generic_block_item(block_type=payload, x_pos=x_pos, y_pos=y_pos)
        elif isinstance(payload, BlockType) and payload in {
            BlockType.EMT_PI_LINE,
            BlockType.EMT_BERGERON_LINE,
            BlockType.SWITCH_EMT,
            BlockType.GROUNDING_LINK_EMT,
            BlockType.NONLINEAR_RESISTOR_EMT,
            BlockType.RLC_COMBO_EMT,
        }:
            if payload == BlockType.SWITCH_EMT:
                return self.create_switch_emt_block_item(x_pos=x_pos, y_pos=y_pos)
            elif payload == BlockType.GROUNDING_LINK_EMT:
                return self.create_grounding_link_emt_block_item(x_pos=x_pos, y_pos=y_pos)
            elif payload == BlockType.NONLINEAR_RESISTOR_EMT:
                return self.create_nonlinear_resistor_emt_block_item(x_pos=x_pos, y_pos=y_pos)
            elif payload == BlockType.RLC_COMBO_EMT:
                return self.create_rlc_combo_emt_block_item(x_pos=x_pos, y_pos=y_pos)
            else:
                return self.create_emt_wizard_block_item(block_type=payload, x_pos=x_pos, y_pos=y_pos)
        elif isinstance(payload, BlockType) and _is_load_topology_block_type(payload):
            return self.create_load_topology_emt_block_item(block_type=payload, x_pos=x_pos, y_pos=y_pos)
        elif isinstance(payload, BlockType) and payload in {
            BlockType.R_LOAD_EMT,
            BlockType.L_LOAD_EMT,
            BlockType.C_LOAD_EMT,
        }:
            return self.create_shunt_component_emt_block_item(block_type=payload, x_pos=x_pos, y_pos=y_pos)
        elif isinstance(payload, BlockType) and payload in {
            BlockType.TRAFO_EMT,
            BlockType.XFMR_TRANSFORMER,
        }:
            return self.create_transformer_topology_emt_block_item(block_type=payload, x_pos=x_pos, y_pos=y_pos)
        elif isinstance(payload, BlockType):
            return self.create_block_item(block_type=payload, x_pos=x_pos, y_pos=y_pos)
        elif isinstance(payload, BasicBlockTemplateDescriptor):
            if payload.template_key in LOOKUP_ARRAY_LINEAR_DESCRIPTOR_KEYS:
                return self.create_lookup_array_linear_descriptor_item(payload, x_pos, y_pos)
            elif payload.template_key in INVERSE_LOOKUP_ARRAY_LINEAR_DESCRIPTOR_KEYS:
                return self.create_inverse_lookup_array_linear_descriptor_item(payload, x_pos, y_pos)
            elif payload.template_key in LOOKUP_ARRAY_SPLINE_DESCRIPTOR_KEYS:
                return self.create_lookup_array_spline_descriptor_item(payload, x_pos, y_pos)
            elif payload.template_key in LOOKUP_MATRIX_LINEAR_DESCRIPTOR_KEYS:
                return self.create_lookup_matrix_linear_descriptor_item(payload, x_pos, y_pos)
            elif payload.template_key in LOOKUP_MATRIX_SPLINE_DESCRIPTOR_KEYS:
                return self.create_lookup_matrix_spline_descriptor_item(payload, x_pos, y_pos)
            else:
                template: EmtModelTemplate = load_basic_block_catalog_template(payload, self.var_factory)
                return self.create_template_block_item(template=template, x_pos=x_pos, y_pos=y_pos)
        elif isinstance(payload, (RmsModelTemplate, EmtModelTemplate, FmuTemplate)):
            return self.create_template_block_item(template=payload, x_pos=x_pos, y_pos=y_pos)
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

        if source_port.subsystem.subsys is not None:
            dst_var: Var = source_port.subsystem.subsys.out_vars[source_port.index]

            if dst_var.network_conn:

                target_var: Var
                # i: int
                # eq: Expr

                if source_port.base_var is not None:
                    target_var = source_port.base_var
                else:
                    target_var = source_port.subsystem.subsys.out_vars[source_port.index]

                # The destination equations and variables must be restored to the original local input variable.
                source_port.subsystem.subsys.update_model(dst_var, target_var)

                source_port.subsystem.subsys.out_vars[source_port.index] = target_var
                source_port.subsystem.refresh_port_metadata()

        if target_port.subsystem.subsys is not None:
            dst_var: Var = source_port.subsystem.subsys.out_vars[source_port.index]

            if not dst_var.network_conn:
                if target_port.base_var is not None:
                    target_var = target_port.base_var
                else:
                    target_var = target_port.subsystem.subsys.in_vars[target_port.index]

                # The destination equations and variables must be restored to the original local input variable.
                target_port.subsystem.subsys.update_model(dst_var, target_var)

                target_port.subsystem.subsys.in_vars[target_port.index] = target_var
                target_port.subsystem.refresh_port_metadata()

        else:
            pass

    def remove_block_item(self, item: BlockItem | GenericBlockItem) -> None:
        """
        Remove a block and all of its attached connections.

        :param item:
        :return:
        """
        port: PortItem
        conn: ConnectionItem
        connections_to_remove: List[ConnectionItem] = list()
        child_block: Block

        # find connections to remove
        for port in item.inputs + item.outputs:
            if port.connections is not None:
                for conn in port.connections:
                    if conn not in connections_to_remove:
                        connections_to_remove.append(conn)
                    else:
                        pass
            else:
                pass

        # remove item from scene
        self.scene.removeItem(item)

        # remove blocks and diagrams from main_block
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

        # remove connections
        for conn in connections_to_remove:
            self.remove_connection_item(conn)

    def remove_item(self, item: BlockItem | GenericBlockItem | ConnectionItem) -> None:
        """
        Remove a block or connection from scene and model state.

        :param item:
        :return:
        """
        if isinstance(item, ConnectionItem):
            self.remove_connection_item(item)
            self.mark_unapplied_changes()
        elif isinstance(item, (BlockItem, GenericBlockItem)):
            self.remove_block_item(item)
            self.mark_unapplied_changes()
        else:
            pass

    def add_connection_vars(self) -> None:
        """
        Add the connection variables required to couple the edited device with the grid.

        :return:
        """
        specs: List[ConnectionVarSpec]

        if self.mode == DynamicSimulationMode.RMS:
            if isinstance(self.api_object, BranchParent):
                specs = self._build_rms_branch_connection_specs()
            elif isinstance(self.api_object, InjectionParent):
                specs = self._build_rms_injection_connection_specs()
            else:
                specs = list()

        elif self.mode == DynamicSimulationMode.EMT:
            if isinstance(self.api_object, BranchParent):
                specs = self._build_emt_branch_connection_specs()
            elif isinstance(self.api_object, InjectionParent):
                specs = self._build_emt_injection_connection_specs()
            else:
                specs = list()

        else:
            raise ValueError(f"Unsupported dynamic editor mode {self.mode}")

        self._materialize_connection_specs(specs)

    def add_connection_items(self):
        """
        for every input and output var in the main block of the editor we build a block item to connect connection variables

        :return:
        :rtype:
        """
        SCENE_WIDTH: float = 1200.0
        SCENE_HEIGHT: float = 800.0
        MARGIN_X: float = 100.0
        MARGIN_Y: float = 80.0
        BLOCK_HEIGHT: float = 80.0
        MIN_SPACING: float = 60.0
        MAX_SPACING: float = 180.0

        num_inputs: int = len(self.main_block.in_vars)
        num_outputs: int = len(self.main_block.out_vars)

        if num_inputs > 0:
            available_height: float = SCENE_HEIGHT - 2 * MARGIN_Y
            input_spacing: float = min(MAX_SPACING, max(MIN_SPACING, available_height / (num_inputs + 1)))
        else:
            input_spacing: float = MAX_SPACING

        if num_outputs > 0:
            available_height = SCENE_HEIGHT - 2 * MARGIN_Y
            output_spacing: float = min(MAX_SPACING, max(MIN_SPACING, available_height / (num_outputs + 1)))
        else:
            output_spacing = MAX_SPACING

        for i, invar in enumerate(self.main_block.in_vars):
            y_pos: float = MARGIN_Y + input_spacing * (i + 1) - BLOCK_HEIGHT / 2
            self.create_connection_block_item(invar, BlockType.INPUT_CONN, MARGIN_X, y_pos)

        for i, outvar in enumerate(self.main_block.out_vars):
            y_pos = MARGIN_Y + output_spacing * (i + 1) - BLOCK_HEIGHT / 2
            x_pos: float = SCENE_WIDTH - MARGIN_X - BLOCK_HEIGHT
            self.create_connection_block_item(outvar, BlockType.OUTPUT_CONN, x_pos, y_pos)

        self.scene.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self.view.fitInView(self.scene.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def _ensure_emt_bus_model(self, bus: Any) -> None:
        """
        Ensure that one bus already owns an EMT model before the editor tries to expose its ports.

        :param bus: Bus API object.
        :return: None.
        """

        if bus.emt_model.empty():
            if self.circuit is None:
                raise ValueError("The EMT dynamic editor requires the circuit context to initialize bus EMT models.")
            else:
                if self._bus_requires_default_emt_shell(bus):
                    self._show_emt_bus_fallback_warning(bus)
                else:
                    pass
                get_bus_emt_template(self.circuit, bus)
        else:
            pass

    def _bus_requires_default_emt_shell(self, bus: Any) -> bool:
        """
        Detect whether the editor will have to synthesize the default ABC EMT bus shell.

        The warning matters because the user may expect existing EMT network connectivity,
        but in an empty or RMS-only network the editor must fabricate a generic bus shell
        so the EMT model can still be edited.

        :param bus: Bus API object.
        :return: ``True`` when the editor must synthesize the default EMT bus shell.
        """

        if bus.is_dc:
            return False
        else:
            if self.circuit is None:
                return False
            else:
                has_connected_branch: bool = False
                branch = None
                for branch in self.circuit.get_branches_iter(add_vsc=True, add_switch=True, add_hvdc=True):
                    if bus == branch.bus_from or bus == branch.bus_to:
                        has_connected_branch = True
                    else:
                        pass
                return not has_connected_branch

    def _show_emt_bus_fallback_warning(self, bus: Any) -> None:
        """
        Show one warning when the editor fabricates the default ABC EMT bus shell.

        :param bus: Bus API object.
        :return: None.
        """

        if self._emt_bus_fallback_warning_shown:
            pass
        else:
            application = QtWidgets.QApplication.instance()
            if application is None:
                self._emt_bus_fallback_warning_shown = True
            else:
                platform_name: str = application.platformName().lower()
                if platform_name == "offscreen":
                    self._emt_bus_fallback_warning_shown = True
                else:
                    QtWidgets.QMessageBox.information(
                        self,
                        "EMT bus shell created",
                        (
                            f"The bus '{bus.name}' does not have an EMT bus shell yet.\n\n"
                            "VeraGrid will create a default ABC EMT bus shell so the EMT model can be edited. "
                            "If you need the exact EMT network ports, create the EMT network elements first and reopen the editor."
                        ),
                    )
                    self._emt_bus_fallback_warning_shown = True

    def get_injection_emt_voltage_pairs(self, bus: Any) -> List[tuple[VarPowerFlowRefferenceType, Any]]:
        """
        Get the ordered EMT bus-voltage references used by injection models.

        :param bus: Bus API object.
        :return: Reference-variable pairs.
        """

        self._ensure_emt_bus_model(bus)
        if bus.is_dc:
            v_dc, _, _, _ = get_bus_emt_algebraic_vars(bus.emt_model)
            return [(VarPowerFlowRefferenceType.Vdc, v_dc)]
        else:
            v_n, v_a, v_b, v_c = get_bus_emt_algebraic_vars(bus.emt_model)
            pairs: List[tuple[VarPowerFlowRefferenceType, Any]] = list()
            if v_n is not None:
                pairs.append((VarPowerFlowRefferenceType.v_N, v_n))
            else:
                pass
            if v_a is not None:
                pairs.append((VarPowerFlowRefferenceType.v_A, v_a))
            else:
                pass
            if v_b is not None:
                pairs.append((VarPowerFlowRefferenceType.v_B, v_b))
            else:
                pass
            if v_c is not None:
                pairs.append((VarPowerFlowRefferenceType.v_C, v_c))
            else:
                pass
            return pairs

    def get_branch_emt_voltage_pairs(self,
                                     bus: Any,
                                     side: str) -> List[tuple[VarPowerFlowRefferenceType, Any]]:
        """
        Get the ordered EMT bus-voltage references used by branch models.

        :param bus: Bus API object.
        :param side: Branch side, either ``from`` or ``to``.
        :return: Reference-variable pairs.
        """

        self._ensure_emt_bus_model(bus)
        if bus.is_dc:
            return list()
        else:
            v_n, v_a, v_b, v_c = get_bus_emt_algebraic_vars(bus.emt_model)
            if side == "from":
                refs = [
                    VarPowerFlowRefferenceType.vf_N,
                    VarPowerFlowRefferenceType.vf_A,
                    VarPowerFlowRefferenceType.vf_B,
                    VarPowerFlowRefferenceType.vf_C,
                ]
            else:
                if side == "to":
                    refs = [
                        VarPowerFlowRefferenceType.vt_N,
                        VarPowerFlowRefferenceType.vt_A,
                        VarPowerFlowRefferenceType.vt_B,
                        VarPowerFlowRefferenceType.vt_C,
                    ]
                else:
                    raise ValueError(f"Unsupported branch EMT side {side}")

            pairs: List[tuple[VarPowerFlowRefferenceType, Any]] = list()
            for reference, variable in zip(refs, [v_n, v_a, v_b, v_c]):
                if variable is not None:
                    pairs.append((reference, variable))
                else:
                    pass
            return pairs

    def _materialize_connection_specs(self, specs: List[ConnectionVarSpec]) -> None:
        """
        Create all connection variables described by the given specs and attach them to the main block.

        :param specs:
        :return:
        """
        spec: ConnectionVarSpec
        for spec in specs:
            var = self.var_factory.add_var(spec.visible_name, spec.reference, True)

            if spec.direction == "input":
                self.main_block.in_vars.append(var)
            elif spec.direction == "output":
                self.main_block.out_vars.append(var)
            else:
                raise ValueError(f"Unsupported connection direction {spec.direction}")

            self.main_block.external_mapping[spec.reference] = var

    def _build_rms_injection_connection_specs(self) -> List[ConnectionVarSpec]:
        """
        Build all RMS connection-variable specs for an injection device.

        :return:
        """
        if self.api_object.bus.rms_model.empty():
            initialize_bus_rms(self.api_object.bus, self.var_factory)

        safe_bus_name: str = self._get_safe_bus_name(self.api_object.bus)

        specs: List[ConnectionVarSpec] = list()
        specs.append(ConnectionVarSpec("input", VarPowerFlowRefferenceType.Vm, f"Vm_{safe_bus_name}"))
        specs.append(ConnectionVarSpec("input", VarPowerFlowRefferenceType.Va, f"Va_{safe_bus_name}"))
        specs.append(ConnectionVarSpec("output", VarPowerFlowRefferenceType.P, f"net_conn_P_{safe_bus_name}"))
        specs.append(ConnectionVarSpec("output", VarPowerFlowRefferenceType.Q, f"net_conn_Q_{safe_bus_name}"))

        return specs

    def _build_rms_branch_connection_specs(self) -> List[ConnectionVarSpec]:
        """
        Build all RMS connection-variable specs for a branch device.

        :return:
        """
        if self.api_object.bus_from.rms_model.empty():
            initialize_bus_rms(self.api_object.bus_from, self.var_factory)

        if self.api_object.bus_to.rms_model.empty():
            initialize_bus_rms(self.api_object.bus_to, self.var_factory)

        safe_bus_from: str = self._get_safe_bus_name(self.api_object.bus_from)
        safe_bus_to: str = self._get_safe_bus_name(self.api_object.bus_to)

        specs: List[ConnectionVarSpec] = list()

        specs.append(ConnectionVarSpec("input", VarPowerFlowRefferenceType.Vmf, f"Vm_{safe_bus_from}"))
        specs.append(ConnectionVarSpec("input", VarPowerFlowRefferenceType.Vaf, f"Va_{safe_bus_from}"))
        specs.append(ConnectionVarSpec("input", VarPowerFlowRefferenceType.Vmt, f"Vm_{safe_bus_to}"))
        specs.append(ConnectionVarSpec("input", VarPowerFlowRefferenceType.Vat, f"Va_{safe_bus_to}"))

        specs.append(ConnectionVarSpec("output", VarPowerFlowRefferenceType.Pf, f"net_conn_P_{safe_bus_from}"))
        specs.append(ConnectionVarSpec("output", VarPowerFlowRefferenceType.Qf, f"net_conn_Q_{safe_bus_from}"))
        specs.append(ConnectionVarSpec("output", VarPowerFlowRefferenceType.Pt, f"net_conn_P_{safe_bus_to}"))
        specs.append(ConnectionVarSpec("output", VarPowerFlowRefferenceType.Qt, f"net_conn_Q_{safe_bus_to}"))

        return specs

    def _build_emt_injection_connection_specs(self) -> List[ConnectionVarSpec]:
        """
        Build all EMT connection-variable specs for an injection device.

        :return:
        """
        voltage_pairs = self.get_injection_emt_voltage_pairs(self.api_object.bus)
        specs: List[ConnectionVarSpec] = list()

        reference: VarPowerFlowRefferenceType
        variable: Any
        for reference, variable in voltage_pairs:
            specs.append(ConnectionVarSpec("input", reference, str(variable.name)))

        current_refs = self.build_emt_injection_current_refs(self.api_object.bus)
        for reference in current_refs:
            specs.append(ConnectionVarSpec("output", reference, f"net_conn_{reference.value}_{self.api_object.name}"))

        return specs

    def _build_emt_branch_connection_specs(self) -> List[ConnectionVarSpec]:
        """
        Build all EMT connection-variable specs for a branch device.

        Inputs expose the voltages of both terminal buses.
        Outputs expose the currents of both terminal buses using the same visible-name
        pattern as injection devices plus the bus-name suffix.

        :return:
        """
        specs: List[ConnectionVarSpec] = list()

        voltage_pairs_from = self.get_branch_emt_voltage_pairs(self.api_object.bus_from, "from")
        voltage_pairs_to = self.get_branch_emt_voltage_pairs(self.api_object.bus_to, "to")

        reference: VarPowerFlowRefferenceType
        variable: Any
        for reference, variable in voltage_pairs_from:
            specs.append(ConnectionVarSpec("input", reference, str(variable.name)))

        for reference, variable in voltage_pairs_to:
            specs.append(ConnectionVarSpec("input", reference, str(variable.name)))

        safe_bus_from = self._get_safe_bus_name(self.api_object.bus_from)
        safe_bus_to = self._get_safe_bus_name(self.api_object.bus_to)

        current_name_map_from: Dict[VarPowerFlowRefferenceType, str] = {
            VarPowerFlowRefferenceType.if_N: f"net_conn_i_N_{safe_bus_from}_{self.api_object.name}",
            VarPowerFlowRefferenceType.if_A: f"net_conn_i_A_{safe_bus_from}_{self.api_object.name}",
            VarPowerFlowRefferenceType.if_B: f"net_conn_i_B_{safe_bus_from}_{self.api_object.name}",
            VarPowerFlowRefferenceType.if_C: f"net_conn_i_C_{safe_bus_from}_{self.api_object.name}",
        }

        current_name_map_to: Dict[VarPowerFlowRefferenceType, str] = {
            VarPowerFlowRefferenceType.it_N: f"net_conn_i_N_{safe_bus_to}_{self.api_object.name}",
            VarPowerFlowRefferenceType.it_A: f"net_conn_i_A_{safe_bus_to}_{self.api_object.name}",
            VarPowerFlowRefferenceType.it_B: f"net_conn_i_B_{safe_bus_to}_{self.api_object.name}",
            VarPowerFlowRefferenceType.it_C: f"net_conn_i_C_{safe_bus_to}_{self.api_object.name}",
        }

        current_refs_from = self._build_emt_branch_current_refs(self.api_object.bus_from, "from")
        current_refs_to = self._build_emt_branch_current_refs(self.api_object.bus_to, "to")

        for reference in current_refs_from:
            visible_name = current_name_map_from.get(reference, None)
            if visible_name is not None:
                specs.append(ConnectionVarSpec("output", reference, visible_name))

        for reference in current_refs_to:
            visible_name = current_name_map_to.get(reference, None)
            if visible_name is not None:
                specs.append(ConnectionVarSpec("output", reference, visible_name))

        return specs

    def build_emt_injection_current_refs(self, bus: Any) -> List[VarPowerFlowRefferenceType]:
        """
        Return the ordered EMT current references that should be exposed for one injection device.

        :param bus: Bus API object.
        :return: EMT current references.
        """

        if bus.is_dc:
            current_refs: List[VarPowerFlowRefferenceType] = list()
            current_refs.append(VarPowerFlowRefferenceType.Idc)
            return current_refs
        else:
            voltage_pairs = self.get_injection_emt_voltage_pairs(bus)
            current_refs: List[VarPowerFlowRefferenceType] = list()
            voltage_to_current_map: Dict[VarPowerFlowRefferenceType, VarPowerFlowRefferenceType] = dict()
            voltage_to_current_map[VarPowerFlowRefferenceType.v_N] = VarPowerFlowRefferenceType.i_N
            voltage_to_current_map[VarPowerFlowRefferenceType.v_A] = VarPowerFlowRefferenceType.i_A
            voltage_to_current_map[VarPowerFlowRefferenceType.v_B] = VarPowerFlowRefferenceType.i_B
            voltage_to_current_map[VarPowerFlowRefferenceType.v_C] = VarPowerFlowRefferenceType.i_C
            reference: VarPowerFlowRefferenceType
            for reference, _ in voltage_pairs:
                mapped_reference = voltage_to_current_map.get(reference, None)
                if mapped_reference is not None:
                    current_refs.append(mapped_reference)
                else:
                    pass
            return current_refs

    def _build_emt_branch_current_refs(self, bus: Any, side: str) -> List[VarPowerFlowRefferenceType]:
        """
        Return the ordered EMT branch-current references that should be exposed for one branch side.

        :param bus: Terminal bus.
        :param side: Branch side, either ``from`` or ``to``.
        :return: EMT branch current references.
        """

        voltage_pairs = self.get_branch_emt_voltage_pairs(bus, side)
        if side == "from":
            voltage_to_current_map: Dict[VarPowerFlowRefferenceType, VarPowerFlowRefferenceType] = dict()
            voltage_to_current_map[VarPowerFlowRefferenceType.vf_N] = VarPowerFlowRefferenceType.if_N
            voltage_to_current_map[VarPowerFlowRefferenceType.vf_A] = VarPowerFlowRefferenceType.if_A
            voltage_to_current_map[VarPowerFlowRefferenceType.vf_B] = VarPowerFlowRefferenceType.if_B
            voltage_to_current_map[VarPowerFlowRefferenceType.vf_C] = VarPowerFlowRefferenceType.if_C
        else:
            if side == "to":
                voltage_to_current_map = dict()
                voltage_to_current_map[VarPowerFlowRefferenceType.vt_N] = VarPowerFlowRefferenceType.it_N
                voltage_to_current_map[VarPowerFlowRefferenceType.vt_A] = VarPowerFlowRefferenceType.it_A
                voltage_to_current_map[VarPowerFlowRefferenceType.vt_B] = VarPowerFlowRefferenceType.it_B
                voltage_to_current_map[VarPowerFlowRefferenceType.vt_C] = VarPowerFlowRefferenceType.it_C
            else:
                raise ValueError(f"Unsupported branch EMT side {side}")

        current_refs: List[VarPowerFlowRefferenceType] = list()
        reference: VarPowerFlowRefferenceType
        for reference, _ in voltage_pairs:
            mapped_reference = voltage_to_current_map.get(reference, None)
            if mapped_reference is not None:
                current_refs.append(mapped_reference)
            else:
                pass
        return current_refs

    def _get_safe_bus_name(self, bus: Any) -> str:
        """
        Build a safe bus-name suffix for editor-visible connection variables.

        :param bus: Bus API object.
        :return: Bus name with spaces replaced by underscores.
        """
        return bus.name.replace(" ", "_")

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
        if self.mode == DynamicSimulationMode.EMT:
            return
        else:
            pass

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
        Open the expression text editor when the user double-clicks an expression row
        in either the equations table or the parameters table.

        :param index:
        :return:
        """
        if index.model() == self.parameters_table_model and index.column() == 2:
            self.open_expression_editor_for_parameters(index.row())
        elif index.model() == self.equations_table_model:
            row_data: BlockParameterRow | None = self.equations_table_model.get_row(index.row())
            if row_data is not None:
                if row_data.opens_expression_editor and index.column() == 1:
                    self.open_expression_row_editor(index.row())

    def open_expression_editor_for_parameters(self, row_index: int) -> None:
        """
        Open the expression text editor for a parameters-table row.

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
            if row_data.value is not None and isinstance(row_data.value, Expr):
                expression_text = symbolic_to_string(row_data.value)
            else:
                expression_text = str(row_data.value) if row_data.value is not None else ""
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

                    self.parameters_table_model.set_value_from_expression(row_index, expression_value)
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Expression Error",
                        str(exc)
                    )

    def on_variables_table_double_clicked(self, index: QtCore.QModelIndex) -> None:
        """
        Open the expression text editor when the user double-clicks an init_eq cell.

        :param index:
        :return:
        """
        if index.column() == 2:
            self.open_expression_row_editor_for_variables(index.row())

    def open_expression_row_editor_for_variables(self, row_index: int) -> None:
        """
        Open the expression text editor for a variables-table row.

        :param row_index:
        :return:
        """
        row_data: BlockParameterRow | None = self.variables_table_model.get_row(row_index)
        expression_text: str
        dialog: ExpressionTextEditorDialog
        symbol_namespace: Dict[str, Expr]
        parsed_expression: Expr | Comparison
        expression_value: Expr

        if row_data is not None and self.variables_table_model.block is not None:
            if row_data.init_eq is not None and isinstance(row_data.init_eq, Expr):
                expression_text = symbolic_to_string(row_data.init_eq)
            else:
                expression_text = ""
            symbol_namespace = build_block_symbol_namespace(self.variables_table_model.block)
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

                    self.variables_table_model.set_init_eq(row_index, expression_value)
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Expression Error",
                        str(exc)
                    )

    def select_table_context_row(self,
                                 table_view: QtWidgets.QTableView,
                                 position: QtCore.QPoint) -> None:
        """
        Select the row under a table context menu request when it is not already selected.

        :param table_view:
        :param position:
        :return:
        """
        index: QtCore.QModelIndex = table_view.indexAt(position)

        if index.isValid() and not table_view.selectionModel().isRowSelected(index.row(), QtCore.QModelIndex()):
            table_view.selectRow(index.row())
        else:
            pass

    def show_variables_table_context_menu(self, position: QtCore.QPoint) -> None:
        """
        Show the variables table context menu.

        :param position:
        :return:
        """
        table_view: QtWidgets.QTableView = self.ui.variablesTableView
        self.select_table_context_row(table_view=table_view, position=position)

        selected_block: Block | None = self.get_selected_scene_block()
        has_selected_rows: bool = bool(table_view.selectionModel().selectedRows())

        menu: QMenu = QMenu(table_view)
        add_variable_action: QAction = menu.addAction("Add Variable")
        remove_selected_action: QAction = menu.addAction("Remove Selected")

        add_variable_action.setEnabled(selected_block is not None)
        remove_selected_action.setEnabled(selected_block is not None and has_selected_rows)

        selected_action: QAction | None = menu.exec(table_view.viewport().mapToGlobal(position))

        if selected_action == add_variable_action:
            self.open_add_variable_dialog()
        elif selected_action == remove_selected_action:
            self.remove_selected_variables()
        else:
            pass

    def show_parameters_table_context_menu(self, position: QtCore.QPoint) -> None:
        """
        Show the parameters table context menu.

        :param position:
        :return:
        """
        table_view: QtWidgets.QTableView = self.ui.parametersTableView
        self.select_table_context_row(table_view=table_view, position=position)

        selected_block: Block | None = self.get_selected_scene_block()
        has_selected_rows: bool = bool(table_view.selectionModel().selectedRows())

        menu: QMenu = QMenu(table_view)
        add_variable_action: QAction = menu.addAction("Add Variable")
        remove_selected_action: QAction = menu.addAction("Remove Selected")

        add_variable_action.setEnabled(selected_block is not None)
        remove_selected_action.setEnabled(selected_block is not None and has_selected_rows)

        selected_action: QAction | None = menu.exec(table_view.viewport().mapToGlobal(position))

        if selected_action == add_variable_action:
            self.open_add_variable_dialog()
        elif selected_action == remove_selected_action:
            self.remove_selected_parameters()
        else:
            pass

    def show_equations_table_context_menu(self, position: QtCore.QPoint) -> None:
        """
        Show the equations table context menu.

        :param position:
        :return:
        """
        table_view: QtWidgets.QTableView = self.ui.equationsTableView
        self.select_table_context_row(table_view=table_view, position=position)

        selected_block: Block | None = self.get_selected_scene_block()
        has_selected_rows: bool = bool(table_view.selectionModel().selectedRows())

        menu: QMenu = QMenu(table_view)
        add_equation_action: QAction = menu.addAction("Add Equation")
        remove_selected_action: QAction = menu.addAction("Remove Selected")

        add_equation_action.setEnabled(selected_block is not None)
        remove_selected_action.setEnabled(selected_block is not None and has_selected_rows)

        selected_action: QAction | None = menu.exec(table_view.viewport().mapToGlobal(position))

        if selected_action == add_equation_action:
            self.open_add_equation_dialog()
        elif selected_action == remove_selected_action:
            self.remove_selected_equations()
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
                block = self.get_selected_scene_block()
                if block is None:
                    raise ValueError("No block is selected in the editor.")

                name = dialog.get_name()
                category = dialog.get_category()
                parameter_value = dialog.get_parameter_value()

                if not is_valid_symbol_name(name):
                    raise ValueError("The symbol name must be a valid identifier.")
                elif block_namespace_contains_name(block, name):
                    raise ValueError(f"The symbol '{name}' already exists in this block.")

                new_var = self.var_factory.add_var(name=name)
                add_variable_to_block(
                    block=block,
                    var=new_var,
                    var_type=category,
                    parameter_value=parameter_value
                )

                self.variables_table_model.set_block(block)
                self.parameters_table_model.set_block(block)
                self.equations_table_model.set_block(block)
                self.variables_table_model.block_updated.emit(block.uid)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Add Variable Error", str(exc))
        else:
            pass

    def open_add_equation_dialog(self) -> None:
        """
        Open the dialog used to add a new equation.

        :return:
        """
        block = self.get_selected_scene_block()
        if block is None:
            QtWidgets.QMessageBox.warning(self, "Add Equation Error", "No block is selected in the editor.")
            return

        symbol_namespace = build_block_symbol_namespace(block)
        dialog = AddEquationDialog(symbol_namespace=symbol_namespace, parent=self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                equation_text = dialog.get_equation_text()
                category = dialog.get_category()

                parsed_expr = string_to_symbolic(equation_text, symbol_namespace)

                if category == "state":
                    block.state_eqs.append(parsed_expr)
                elif category == "algebraic":
                    block.algebraic_eqs.append(parsed_expr)
                else:
                    raise ValueError(f"Unknown equation type: {category}")

                self.equations_table_model.set_block(block)
                self.equations_table_model.block_updated.emit(block.uid)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Add Equation Error", str(exc))
        else:
            pass

    def remove_selected_variables(self) -> None:
        """
        Remove selected variables from the selected block.

        :return:
        """
        block = self.get_selected_scene_block()
        if block is None:
            return

        vars_model = self.variables_table_model
        vars_selected = [idx.row() for idx in self.ui.variablesTableView.selectionModel().selectedRows()]
        if not vars_selected:
            return

        vars_to_remove_from_state = []
        vars_to_remove_from_algebraic = []
        init_keys_to_remove = []
        for row_idx in vars_selected:
            row_data = vars_model.rows[row_idx]
            var = row_data.key_var
            if row_data.kind == BlockParameterKind.STATE_VAR:
                if var in block.state_vars:
                    vars_to_remove_from_state.append(var)
                    if var in block.init_values:
                        init_keys_to_remove.append(var)
            elif row_data.kind == BlockParameterKind.ALGEBRAIC_VAR:
                if var in block.algebraic_vars:
                    vars_to_remove_from_algebraic.append(var)

        block.state_vars = [v for v in block.state_vars if v not in set(vars_to_remove_from_state)]
        block.algebraic_vars = [v for v in block.algebraic_vars if v not in set(vars_to_remove_from_algebraic)]
        for key in init_keys_to_remove:
            if key in block.init_values:
                del block.init_values[key]

        vars_model.set_block(block)
        vars_model.block_updated.emit(block.uid)

    def remove_selected_parameters(self) -> None:
        """
        Remove selected parameters from the selected block.

        :return:
        """
        block = self.get_selected_scene_block()
        if block is None:
            return

        params_model = self.parameters_table_model
        params_selected = [idx.row() for idx in self.ui.parametersTableView.selectionModel().selectedRows()]
        if not params_selected:
            return

        for row_idx in params_selected:
            row_data = params_model.rows[row_idx]
            var = row_data.key_var
            if row_data.kind == BlockParameterKind.EVENT_PARAMETER:
                if var in block.event_dict:
                    del block.event_dict[var]
            elif row_data.kind == BlockParameterKind.MODE_PARAMETER:
                if var in block.mode_dict:
                    del block.mode_dict[var]
            elif row_data.kind == BlockParameterKind.FIXED_PARAMETER:
                if var in block.parameters:
                    del block.parameters[var]

        params_model.set_block(block)
        params_model.block_updated.emit(block.uid)

    def remove_selected_equations(self) -> None:
        """
        Remove selected equations from the selected block.

        :return:
        """
        block = self.get_selected_scene_block()
        if block is None:
            return

        equations_model = self.equations_table_model
        equations_selected = [idx.row() for idx in self.ui.equationsTableView.selectionModel().selectedRows()]
        if not equations_selected:
            return

        state_indices_to_remove = set()
        alg_indices_to_remove = set()
        for row_idx in equations_selected:
            row_data = equations_model.rows[row_idx]
            if row_data.item_index is not None:
                if row_data.kind == BlockParameterKind.STATE_EQUATION:
                    state_indices_to_remove.add(row_data.item_index)
                elif row_data.kind == BlockParameterKind.ALGEBRAIC_EQUATION:
                    alg_indices_to_remove.add(row_data.item_index)

        new_state_eqs = [eq for idx, eq in enumerate(block.state_eqs) if idx not in state_indices_to_remove]
        new_algebraic_eqs = [eq for idx, eq in enumerate(block.algebraic_eqs) if idx not in alg_indices_to_remove]
        block.state_eqs = new_state_eqs
        block.algebraic_eqs = new_algebraic_eqs

        equations_model.set_block(block)
        equations_model.block_updated.emit(block.uid)

    def open_expression_row_editor(self, row_index: int) -> None:
        """
        Open the expression text editor for a parameter-table row.

        :param row_index:
        :return:
        """
        row_data: BlockParameterRow | None = self.equations_table_model.get_row(row_index)
        expression_text: str
        dialog: ExpressionTextEditorDialog
        symbol_namespace: Dict[str, Expr]
        parsed_expression: Expr | Comparison
        expression_value: Expr

        if row_data is not None and self.equations_table_model.block is not None:
            if isinstance(row_data.value, Expr):
                old_expr = row_data.value
                expression_text = symbolic_to_string(row_data.value)
                self.equations_table_model.symbol_namespace = build_block_symbol_namespace(
                    self.equations_table_model.block)
                dialog = ExpressionTextEditorDialog(
                    expression_text=expression_text,
                    symbol_namespace=self.equations_table_model.symbol_namespace,
                    parent=self
                )

                if dialog.exec() == QDialog.DialogCode.Accepted:
                    try:
                        parsed_expression = string_to_symbolic(dialog.get_expression_text(),
                                                               self.equations_table_model.symbol_namespace)

                        if isinstance(parsed_expression, Comparison):
                            expression_value = parsed_expression.to_expression()
                        else:
                            expression_value = parsed_expression

                        index = self.equations_table_model.index(row_index, 1)
                        self.equations_table_model.setData(index, symbolic_to_string(expression_value),
                                                           QtCore.Qt.ItemDataRole.EditRole)
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
        self._selected_side_block = selected_block
        self.refresh_active_side_panel()

    @QtCore.Slot(int)
    def on_side_panel_page_changed(self, index: int) -> None:
        """
        Refresh only the side panel that just became visible.

        :param index: Newly selected toolbox page index.
        :return: None.
        """
        _unused_index: int = index
        self.refresh_active_side_panel()

    def refresh_active_side_panel(self) -> None:
        """
        Refresh only the currently visible side panel.

        :return: None.
        """
        current_widget: QtWidgets.QWidget = self.ui.toolBox.currentWidget()

        if current_widget == self.ui.page:
            self.variables_table_model.set_block(self._selected_side_block)
        else:
            if current_widget == self.ui.page_2:
                self.parameters_table_model.set_block(self._selected_side_block)
            else:
                if current_widget == self.ui.page_3:
                    self.equations_table_model.set_block(self._selected_side_block)
                else:
                    pass

    def edit_scene_item(self, item: BlockItem | GenericBlockItem | ConnectionItem) -> None:
        """
        Open an editor for the selected scene item when supported.

        :param item: Scene item selected from the context menu.
        :return: None.
        """
        if isinstance(item, GenericBlockItem):
            item.editor_window.show()
            item.editor_window.raise_()
            item.editor_window.activateWindow()
        else:
            if isinstance(item, BlockItem):
                self.open_block_subeditor(item)
            else:
                pass

    def open_block_subeditor(self, item: BlockItem) -> None:
        """
        Open a nested block editor for one block item.

        :param item: Target block item.
        :return: None.
        """
        if item.subsys is None:
            return
        else:
            pass

        editor_window: DynamicBlockEditorGUI | None = item.editor_window

        if editor_window is None:
            editor_window = DynamicBlockEditorGUI(
                var_factory=self.var_factory,
                block=item.subsys,
                api_object=self.api_object,
                mode=self.mode,
                modal=False,
            )
            item.editor_window = editor_window
        else:
            pass

        editor_window.show()
        editor_window.raise_()
        editor_window.activateWindow()

    def modify_scene_item_template(self, item: BlockItem | GenericBlockItem | ConnectionItem) -> None:
        """
        Reopen the modal configuration of a block item when metadata is available.

        :param item: Scene item selected from the context menu.
        :return: None.
        """
        if not isinstance(item, BlockItem) or item.subsys is None:
            return
        else:
            pass

        modal_kind, modal_config = get_modal_template_metadata(item.subsys)

        if modal_kind is None or modal_config is None:
            return
        else:
            pass

        if modal_kind == "lookup_array_1d":
            self._modify_lookup_array_like_block(item, modal_config, build_lookup_array_linear_runtime_template)
        elif modal_kind == "lookup_array_inverse":
            self._modify_lookup_array_like_block(item, modal_config, build_inverse_lookup_array_linear_runtime_template)
        elif modal_kind == "lookup_array_spline":
            self._modify_lookup_array_like_block(item, modal_config, build_lookup_array_spline_runtime_template)
        elif modal_kind == "emt_phase_wizard":
            self._modify_emt_phase_wizard_block(item, modal_config)
        elif modal_kind == "lookup_matrix_linear":
            self._modify_lookup_matrix_like_block(item, modal_config, build_lookup_matrix_linear_runtime_template)
        elif modal_kind == "lookup_matrix_spline":
            self._modify_lookup_matrix_like_block(item, modal_config, build_lookup_matrix_spline_runtime_template)
        elif modal_kind == "grounding_link_emt":
            self._modify_grounding_link_emt_block(item, modal_config)
        elif modal_kind == "nonlinear_resistor_emt":
            self._modify_nonlinear_resistor_emt_block(item, modal_config)
        elif modal_kind == "load_topology_emt":
            self._modify_load_topology_emt_block(item, modal_config)
        elif modal_kind == "transformer_topology_emt":
            self._modify_transformer_topology_emt_block(item, modal_config)
        elif modal_kind == "shunt_component_emt":
            self._modify_shunt_component_emt_block(item, modal_config)
        elif modal_kind == "rlc_combo_emt":
            self._modify_rlc_combo_emt_block(item, modal_config)
        elif modal_kind == "switch_emt":
            self._modify_switch_emt_block(item, modal_config)
        else:
            pass

    def _replace_scene_block_from_template(self, item: BlockItem, new_block: Block, modal_kind: str, modal_config: Dict[str, Any]) -> None:
        """
        Replace one scene block contents while preserving its identity and diagram node.

        :param item: Existing scene block item.
        :param new_block: Newly built block contents.
        :param modal_kind: Modal kind metadata key.
        :param modal_config: Modal configuration metadata.
        :return: None.
        """
        if item.subsys is None:
            return
        else:
            pass

        target_block: Block = item.subsys
        preserved_uid: int = target_block.uid
        preserved_diagram = target_block.diagram
        source_clone: Block = clone_block_for_editing(new_block)
        source_clone.uid = preserved_uid
        copy_block_state(source_block=source_clone, target_block=target_block)
        target_block.uid = preserved_uid

        if source_clone.diagram.node_data:
            target_block.diagram = source_clone.diagram
        else:
            target_block.diagram = preserved_diagram
        set_modal_template_metadata(target_block, modal_kind, modal_config)
        self.rebuild_scene_from_diagram()
        self.select_block_by_uid(preserved_uid)
        self.mark_unapplied_changes()

    def _modify_lookup_array_like_block(self, item: BlockItem, modal_config: Dict[str, Any], builder) -> None:
        """
        Reconfigure one modal-created 1D lookup block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :param builder: Lookup builder callable.
        :return: None.
        """
        dialog = LookupArrayLinearDialog(
            block_label=str(modal_config["display_label"]),
            initial_points=list(zip(modal_config["x_points"], modal_config["y_points"])),
            parent=self,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            x_points, y_points = dialog.get_points()
        else:
            return

        if item.subsys is None:
            return
        else:
            pass

        descriptor_key: str = str(modal_config["descriptor_key"])
        if builder is build_lookup_array_linear_runtime_template:
            new_block = builder(
                vf=self.var_factory,
                x_points=x_points,
                y_points=y_points,
                clip=descriptor_key not in {"lookup_array_linear_noclipping", "lookup_array_object_linear_noclipping"},
                name=item.subsys.name,
            ).block
        else:
            new_block = builder(
                vf=self.var_factory,
                x_points=x_points,
                y_points=y_points,
                name=item.subsys.name,
            ).block

        updated_config = dict(modal_config)
        updated_config["x_points"] = x_points
        updated_config["y_points"] = y_points
        self._replace_scene_block_from_template(item, new_block, str(get_modal_template_metadata(item.subsys)[0]), updated_config)

    def _modify_lookup_matrix_like_block(self, item: BlockItem, modal_config: Dict[str, Any], builder) -> None:
        """
        Reconfigure one modal-created 2D lookup block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :param builder: Lookup builder callable.
        :return: None.
        """
        dialog = LookupMatrixLinearDialog(
            block_label=str(modal_config["display_label"]),
            initial_x_points=modal_config["x_points"],
            initial_y_points=modal_config["y_points"],
            initial_z_matrix=modal_config["z_matrix"],
            parent=self,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            x_points, y_points, z_matrix = dialog.get_matrix_data()
        else:
            return

        if item.subsys is None:
            return
        else:
            pass

        new_block = builder(
            vf=self.var_factory,
            x_points=x_points,
            y_points=y_points,
            z_matrix=z_matrix,
            name=item.subsys.name,
        ).block
        updated_config = dict(modal_config)
        updated_config["x_points"] = x_points
        updated_config["y_points"] = y_points
        updated_config["z_matrix"] = z_matrix
        self._replace_scene_block_from_template(item, new_block, str(get_modal_template_metadata(item.subsys)[0]), updated_config)

    def _modify_emt_phase_wizard_block(self, item: BlockItem, modal_config: Dict[str, Any]) -> None:
        """
        Reconfigure one modal-created EMT phase-wizard block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :return: None.
        """
        initial_values = (
            bool(modal_config.get("phase_n", False)),
            bool(modal_config.get("phase_a", True)),
            bool(modal_config.get("phase_b", True)),
            bool(modal_config.get("phase_c", True)),
        )
        dialog = EmtTemplateWizardDialog(self, initial_values=initial_values)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            phase_n, phase_a, phase_b, phase_c = dialog.get_values()
        else:
            return

        if item.subsys is None:
            return
        else:
            pass

        block_type_name: str = str(modal_config["block_type"])
        block_type = BlockType[block_type_name]

        if _get_shunt_component_kind(block_type) is not None:
            migrated_config: Dict[str, Any] = dict({
                "block_type": block_type.name,
                "phA": bool(modal_config.get("phase_a", True)),
                "phB": bool(modal_config.get("phase_b", True)),
                "phC": bool(modal_config.get("phase_c", True)),
                "connection_type": (
                    ShuntConnectionType.NeutralStar
                    if bool(modal_config.get("phase_n", False))
                    else ShuntConnectionType.GroundedStar
                ),
                "input_mode": "physical",
                "include_r": block_type == BlockType.R_LOAD_EMT,
                "include_l": block_type == BlockType.L_LOAD_EMT,
                "include_c": block_type == BlockType.C_LOAD_EMT,
                "resistance_ohm": 1.0,
                "inductive_value": 0.01,
                "capacitive_value": 1.0e-6,
            })
            self._modify_shunt_component_emt_block(item, migrated_config)
            return
        elif _is_load_topology_block_type(block_type):
            migrated_config = dict({
                "block_type": block_type.name,
                "phA": bool(modal_config.get("phase_a", True)),
                "phB": bool(modal_config.get("phase_b", True)),
                "phC": bool(modal_config.get("phase_c", True)),
                "connection_type": (
                    ShuntConnectionType.NeutralStar
                    if bool(modal_config.get("phase_n", False))
                    else ShuntConnectionType.GroundedStar
                ),
            })
            self._modify_load_topology_emt_block(item, migrated_config)
            return
        else:
            pass

        new_block = create_emt_wizard_block(
            phase_n,
            phase_a,
            phase_b,
            phase_c,
            self.var_factory,
            block_type=block_type,
            item_name=item.subsys.name,
        )

        if new_block is None:
            return
        else:
            pass

        updated_config = dict(modal_config)
        updated_config["phase_n"] = phase_n
        updated_config["phase_a"] = phase_a
        updated_config["phase_b"] = phase_b
        updated_config["phase_c"] = phase_c
        self._replace_scene_block_from_template(item, new_block, "emt_phase_wizard", updated_config)

    def _modify_switch_emt_block(self, item: BlockItem, modal_config: Dict[str, Any]) -> None:
        """
        Reconfigure one modal-created EMT switch block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :return: None.
        """
        dialog = SwitchEmtDialog(self, initial_config=modal_config)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            switch_config = dialog.get_switch_configuration()
        else:
            return

        if item.subsys is None:
            return
        else:
            pass

        new_block = get_switch_emt_template(vf=self.var_factory, name=item.subsys.name, **switch_config).block
        self._replace_scene_block_from_template(item, new_block, "switch_emt", dict(switch_config))

    def _modify_rlc_combo_emt_block(self, item: BlockItem, modal_config: Dict[str, Any]) -> None:
        """
        Reconfigure one modal-created EMT combined RLC shunt block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :return: None.
        """
        dialog = self._build_rlc_combo_emt_dialog(initial_config=modal_config)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            rlc_config = dialog.get_configuration()
        else:
            return

        try:
            template_kwargs = self._build_rlc_combo_emt_template_kwargs(rlc_config)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "RLC Combo", str(exc))
            return

        if item.subsys is None:
            return
        else:
            pass

        if isinstance(self.api_object, InjectionParent):
            try:
                self.api_object.conn = rlc_config["connection_type"]
            except Exception:
                pass
        else:
            pass

        new_block = get_shunt_rlc_combo_emt_template(vf=self.var_factory, name=item.subsys.name, **template_kwargs).block
        self._annotate_internal_grounding_link_blocks(new_block)
        self._sync_rlc_combo_load_base_values(template_kwargs)
        self._replace_scene_block_from_template(item, new_block, "rlc_combo_emt", dict(rlc_config))

    def _modify_grounding_link_emt_block(self, item: BlockItem, modal_config: Dict[str, Any]) -> None:
        """
        Reconfigure one modal-created EMT grounding-link block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :return: None.
        """
        dialog = self._build_grounding_link_emt_dialog(initial_config=modal_config)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            grounding_config = dialog.get_configuration()
        else:
            return

        try:
            template_kwargs = self._build_grounding_link_emt_template_kwargs(grounding_config)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Grounding Link", str(exc))
            return

        if item.subsys is None:
            return
        else:
            pass

        nested_variant: bool = len(item.subsys.external_mapping) == 0
        new_block = get_grounding_link_emt_template(
            vf=self.var_factory,
            name=item.subsys.name,
            nested=nested_variant,
            **template_kwargs,
        ).block
        self._replace_scene_block_from_template(item, new_block, "grounding_link_emt", dict(grounding_config))

    def _modify_nonlinear_resistor_emt_block(self, item: BlockItem, modal_config: Dict[str, Any]) -> None:
        """
        Reconfigure one modal-created nonlinear resistor EMT block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :return: None.
        """
        initial_points = list(zip(
            list(float(value) for value in modal_config.get("voltage_points", [0.0, 1.0, 2.0])),
            list(float(value) for value in modal_config.get("current_points", [0.0, 10.0, 20.0])),
        ))
        dialog = LookupArrayLinearDialog(
            block_label="Nonlinear resistor EMT V-I curve",
            initial_points=initial_points,
            parent=self,
            x_label="V",
            y_label="I",
            preview_enabled=True,
            preview_title="Nonlinear resistor EMT V-I curve",
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            voltage_points, current_points = dialog.get_points()
        else:
            return

        if item.subsys is None:
            return
        else:
            pass

        new_block = get_nonlinear_resistor_emt_template(
            vf=self.var_factory,
            voltage_points=voltage_points,
            current_points=current_points,
            name=item.subsys.name,
        ).block
        self._replace_scene_block_from_template(
            item,
            new_block,
            "nonlinear_resistor_emt",
            dict({
                "voltage_points": voltage_points,
                "current_points": current_points,
            }),
        )

    def _modify_load_topology_emt_block(self, item: BlockItem, modal_config: Dict[str, Any]) -> None:
        """
        Reconfigure one modal-created EMT load-topology block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :return: None.
        """
        block_type_name: str = str(modal_config.get("block_type", ""))
        block_type: BlockType = BlockType[block_type_name]
        dialog = self._build_load_topology_emt_dialog(block_type=block_type, initial_config=modal_config)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            load_config = dialog.get_configuration()
        else:
            return

        if item.subsys is None:
            return
        else:
            pass

        new_block = self._build_load_topology_emt_block_model(
            block_type=block_type,
            item_name=item.subsys.name,
            modal_config=load_config,
        )
        if new_block is None:
            return
        else:
            pass

        self._annotate_internal_grounding_link_blocks(new_block)

        if isinstance(self.api_object, InjectionParent):
            try:
                self.api_object.conn = load_config["connection_type"]
            except Exception:
                pass
        else:
            pass

        self._replace_scene_block_from_template(
            item,
            new_block,
            "load_topology_emt",
            dict(load_config, block_type=block_type.name),
        )

    def _modify_transformer_topology_emt_block(self, item: BlockItem, modal_config: Dict[str, Any]) -> None:
        """
        Reconfigure one modal-created EMT transformer block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :return: None.
        """
        block_type_name: str = str(modal_config.get("block_type", ""))
        block_type: BlockType = BlockType[block_type_name]
        topology_config: Dict[str, Any] | None = self._resolve_transformer_topology_configuration()

        if topology_config is None:
            dialog = self._build_transformer_topology_emt_dialog(block_type=block_type, initial_config=modal_config)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                topology_config = dialog.get_configuration()
            else:
                return
        else:
            topology_config = dict(topology_config)

        if item.subsys is None:
            return
        else:
            pass

        if isinstance(self.api_object, BranchParent):
            try:
                self.api_object.conn_f = topology_config["conn_f"]
                self.api_object.conn_t = topology_config["conn_t"]
            except Exception:
                pass
        else:
            pass

        new_block = self._build_transformer_topology_emt_block_model(
            block_type=block_type,
            item_name=item.subsys.name,
            modal_config=topology_config,
        )
        if new_block is None:
            return
        else:
            pass

        self._replace_scene_block_from_template(
            item,
            new_block,
            "transformer_topology_emt",
            dict(topology_config, block_type=block_type.name),
        )

    def _modify_shunt_component_emt_block(self, item: BlockItem, modal_config: Dict[str, Any]) -> None:
        """
        Reconfigure one modal-created simple EMT shunt block.

        :param item: Target block item.
        :param modal_config: Stored modal configuration.
        :return: None.
        """
        block_type_name: str = str(modal_config.get("block_type", ""))
        block_type: BlockType = BlockType[block_type_name]
        dialog = self._build_shunt_component_emt_dialog(block_type=block_type, initial_config=modal_config)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            shunt_config = dialog.get_configuration()
        else:
            return

        try:
            template_kwargs = self._build_shunt_component_emt_template_kwargs(block_type=block_type, modal_config=shunt_config)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "EMT Shunt", str(exc))
            return

        if item.subsys is None:
            return
        else:
            pass

        if isinstance(self.api_object, InjectionParent):
            try:
                self.api_object.conn = shunt_config["connection_type"]
            except Exception:
                pass
        else:
            pass

        new_block = get_shunt_rlc_combo_emt_template(vf=self.var_factory, name=item.subsys.name, **template_kwargs).block
        self._annotate_internal_grounding_link_blocks(new_block)
        self._sync_rlc_combo_load_base_values(template_kwargs)
        self._replace_scene_block_from_template(
            item,
            new_block,
            "shunt_component_emt",
            dict(shunt_config, block_type=block_type.name),
        )

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
        self.mark_unapplied_changes()
        sender_obj: QtCore.QObject | None = self.sender()

        if sender_obj is self.parameters_table_model:
            self.refresh_active_side_panel()
        else:
            self.rebuild_scene_from_diagram()
            self.select_block_by_uid(block_uid)

    def apply_changes(self) -> None:
        """
        Commit the edited working copy back into the original block.

        :return:
        """
        if self.mode == DynamicSimulationMode.RMS:
            if self.api_object.rms_template is not None:
                # Todo: Here are the changes
                self.api_object.rms_template = None
            copy_block_state(source_block=self.main_block, target_block=self.original_block)
            self.has_unapplied_changes = False
            self.changes_applied = True
            self.dirtyStateChanged.emit(False)
            if self.workspace_embedded:
                pass
            else:
                self.close()

        elif self.mode == DynamicSimulationMode.EMT:
            if self.api_object.emt_template is not None:
                # Todo: Here are the changes
                self.api_object.emt_template = None
            copy_block_state(source_block=self.main_block, target_block=self.original_block)
            self.has_unapplied_changes = False
            self.changes_applied = True
            self.dirtyStateChanged.emit(False)
            if self.workspace_embedded:
                pass
            else:
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
                        position_changed_callback=self._build_position_changed_callback(block_model.uid)
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
                    block_item.position_changed_callback = self._build_position_changed_callback(block_model.uid)
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
            src_port: PortItem | None = None
            dst_port: PortItem | None = None

            if src_item is not None and dst_item is not None:
                try:
                    src_port = src_item.outputs[con.port_number_from]
                    dst_port = dst_item.inputs[con.port_number_to]
                except IndexError:
                    src_port = None
                    dst_port = None

                if src_port is not None and dst_port is not None:
                    elbow_points: List[QPointF] = [QPointF(x, y) for x, y in con.elbow_points] if con.elbow_points else []
                    connection: ConnectionItem = ConnectionItem(
                        src_port, dst_port,
                        diagram=self.diagram,
                        con_uid=uid
                    )

                    pen: QPen = connection.pen()
                    pen.setColor(QColor(con.color))
                    connection.setPen(pen)
                    self.scene.addItem(connection)
                else:
                    pass
            else:
                pass

    def mark_unapplied_changes(self) -> None:
        """
        Mark the editor state as modified with unapplied changes.

        :return:
        """
        self.has_unapplied_changes = True
        self.changes_applied = False
        self.dirtyStateChanged.emit(True)

    def get_dynamic_editor_display_title(self) -> str:
        """
        Return the user-facing title for this editor instance.
        """

        object_name = self.api_object.name if self.api_object is not None else "Dynamic object"
        return f"{object_name} [{self.mode.name}]"

    def can_close_editor(self, parent: QtWidgets.QWidget | None = None) -> bool:
        """
        Return whether this editor can be closed without losing unapplied changes silently.
        """

        if not self.has_unapplied_changes:
            return True

        reply = QtWidgets.QMessageBox.question(
            parent if parent is not None else self,
            "Unsaved changes",
            "There are unapplied changes. Do you want to close without applying them?",
            QtWidgets.QMessageBox.StandardButton.Yes,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        return reply == QtWidgets.QMessageBox.StandardButton.Yes

    def disconnect_editor_signals(self) -> None:
        """
        Disconnect long-lived UI signals before the editor gets destroyed.

        :return: None.
        """
        try:
            self.ui.toolBox.currentChanged.disconnect(self.on_side_panel_page_changed)
        except (RuntimeError, TypeError):
            pass

        try:
            self.scene.selectionChanged.disconnect(self.on_scene_selection_changed)
        except (RuntimeError, TypeError):
            pass

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Close the editor. Ask for confirmation when there are unapplied changes.

        :param event:
        :return:
        """
        if self.can_close_editor(self):
            self.disconnect_editor_signals()
            event.accept()
        else:
            event.ignore()

    def graphicsDragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Validate whether the drag entering the graphics view contains a block entry.

        :param event:
        :return:
        """
        payload: BlockType | BasicBlockTemplateDescriptor | RmsModelTemplate | EmtModelTemplate | FmuTemplate | None = self.get_library_payload_from_mime_data(
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
        payload: BlockType | BasicBlockTemplateDescriptor | RmsModelTemplate | EmtModelTemplate | FmuTemplate | None = self.get_library_payload_from_mime_data(
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
        payload: BlockType | BasicBlockTemplateDescriptor | RmsModelTemplate | EmtModelTemplate | FmuTemplate | None = self.get_library_payload_from_mime_data(
            event.mimeData()
        )
        scene_position: QtCore.QPointF = self.ui.graphicsView.mapToScene(
            int(event.position().x()),
            int(event.position().y())
        )
        block_item: BlockItem | None

        if payload is not None:

            block_item = self.create_library_payload_item(
                payload=payload,
                x_pos=scene_position.x(),
                y_pos=scene_position.y(),
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
        api_object=device,
    )
    window.show()
    app.exec_()
