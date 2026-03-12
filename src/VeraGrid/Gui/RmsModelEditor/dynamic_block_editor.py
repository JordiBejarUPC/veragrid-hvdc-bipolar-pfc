# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import uuid
import copy
from enum import Enum
from typing import List, Dict, Optional, Union, Sequence, Any
import VeraGrid.Gui.gui_functions as gf
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
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import (get_genqec,
                                                                      get_governor,
                                                                      get_stabilizer,
                                                                      get_exciter)
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Templates.predefined_blocks import (
    constant,
    gain,
    adder,
    substract,
    product,
    divide,
    absolut,
    generic
)
from VeraGridEngine.Templates.Rms.bus_rms_template import initialize_bus_rms, get_bus_rms_algebraic_vars

from VeraGrid.Gui.RmsModelEditor.block_editor import Ui_BlockEditorWindow
from VeraGrid.Gui.messages import error_msg
from VeraGridEngine.Utils.Symbolic.symbolic import symbolic_to_string, Expr, Var, Const
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagram
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType, ParamPowerFlowRefferenceType, BlockType

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

class RmsModelEditorGUI(QtWidgets.QMainWindow):
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

        self.var_factory = var_factory
        self.block = block
        self.templates_list = templates_list
        self.api_object = api_object
        self.main_editor = main_editor

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

        self.library_model = self.build_library_tree_model(
            block_role=self.block_role,
            mime_type=self.mime_type
        )

        self.ui.libraryTreeView.setModel(self.library_model)
        self.ui.libraryTreeView.expandAll()
        self.ui.libraryTreeView.setDragEnabled(True)
        self.ui.libraryTreeView.setHeaderHidden(False)

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

        model:DynamicsLibraryTreeModel = DynamicsLibraryTreeModel(block_role, mime_type)
        model.setHorizontalHeaderLabels(["Dynamic library"])
        root_item: QtGui.QStandardItem = model.invisibleRootItem()

        for category, blocks in self.tree_structure.items():
            cat_item: QtGui.QStandardItem = QtGui.QStandardItem(category)
            cat_item.setEditable(False)
            root_item.appendRow(cat_item)

            for label, block_type in blocks:
                item:QtGui.QStandardItem = QtGui.QStandardItem(label)
                item.setEditable(False)

                item.setData(block_type, block_role)
                cat_item.appendRow(item)

        return model



if __name__ == "__main__":
    import sys
    import VeraGridEngine.Devices as dev
    app = QtWidgets.QApplication(sys.argv)

    vf = VarFactory()
    bl = Block()
    device = dev.Generator()
    window = RmsModelEditorGUI(
        var_factory=vf,
        block=bl,
        templates_list=[],
        api_object=device,
    )
    window.show()
    app.exec_()
