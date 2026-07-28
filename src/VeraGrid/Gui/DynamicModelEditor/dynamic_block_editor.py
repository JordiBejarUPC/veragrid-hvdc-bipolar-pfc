# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import copy
from typing import List, Dict, Optional, Any, Tuple
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtWidgets import (QGraphicsItem, QMenu, QDialog, QVBoxLayout, QDialogButtonBox, QLineEdit)
from PySide6.QtGui import (QAction, QDropEvent, QDragEnterEvent, QDragMoveEvent)
from PySide6.QtCore import Qt, QPointF, Signal

from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_graphics import PairedItem
from VeraGridEngine.Devices.Parents.branch_parent import BranchParent

from VeraGridEngine.Devices.Parents.injection_parent import InjectionParent
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType, ParamPowerFlowReferenceType, \
    DynamicSimulationMode, DynamicTableModelMode, DynEditorGraphicsModes
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template, \
    get_bus_emt_algebraic_vars
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.Templates.BasicBlockCatalog.predefined_blocks import signal_pair
from VeraGridEngine.Templates.BasicBlockCatalog import BasicBlockTemplateDescriptor

from VeraGridEngine.Templates.BasicBlockCatalog import load_basic_block_catalog_template

import VeraGridEngine.Templates.BasicBlockCatalog as BasicBlockTemplates
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic.block import Block, find_connections
from VeraGrid.Gui.DynamicModelEditor.block_editor import Ui_BlockEditorWindow
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_dialogs import AddBlockVariableDialog, AddEquationDialog, \
    AddParameterDialog, ExpressionTextEditorDialog, GenericBlockDialog
import VeraGrid.Gui.DynamicModelEditor.dynamic_editor_graphics as graph
from VeraGrid.Session.dynamic_editor_entries import DynamicEditorEntry
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_library import DynamicEditorLibrary, LibraryTreeFilterProxyModel
import VeraGrid.Gui.DynamicModelEditor.dynamic_editor_models as dialog_models
import VeraGrid.Gui.DynamicModelEditor.dynamic_editor_validation as valid
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_utilities import create_block_of_type, create_generic_block, get_blocktype2template_builder_dict

from VeraGrid.Gui.messages import yes_no_question
from VeraGrid.Gui.toast_widget import ToastManager
from VeraGridEngine.Utils.Symbolic.symbolic import (symbolic_to_string, string_to_symbolic,
                                                    Const, Comparison)
from VeraGridEngine.Utils.Symbolic.symbolic_io import duplicate_block
from VeraGridEngine.Utils.Symbolic.bus_rms_template import get_bus_rms_algebraic_vars
from VeraGridEngine.Utils.SugiyamaLayered import (
    SugiyamaEdge,
    SugiyamaGraph,
    SugiyamaLayeredPythonEngine,
    SugiyamaNode,
    SugiyamaPort,
)
from VeraGrid.Gui.DynamicModelEditor.dyn_template_editor_dialogue import DynTemplatesEditorDialog
from VeraGridEngine.enumerations import BlockType
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagram
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr
from dataclasses import dataclass


@dataclass
class ConnectionVarSpec:
    """
    Specification of one connection variable exposed by the block editor.
    """
    direction: str
    reference: VarPowerFlowReferenceType
    visible_name: str

def build_emt_injection_bus_mask_from_refs(refs: set[VarPowerFlowReferenceType]) -> list[bool]:
    """
    Build the AC bus phase mask implied by one injection editor interface.

    A phase is active when either its voltage input or its current output still
    exists in the saved root interface. This makes the user-edited interface
    the source of truth for the final EMT bus shell.

    :param refs: Power-flow references still exposed by the edited root block.
    :return: Phase mask ordered as ``[N, A, B, C]``.
    """
    mask: list[bool] = list([False, False, False, False])

    # Each phase can be kept either through its voltage input or through its
    # current output. This avoids requiring the user to keep both variables
    # just to declare that a phase exists.
    mask[0] = VarPowerFlowReferenceType.v_N in refs or VarPowerFlowReferenceType.i_N in refs
    mask[1] = VarPowerFlowReferenceType.v_A in refs or VarPowerFlowReferenceType.i_A in refs
    mask[2] = VarPowerFlowReferenceType.v_B in refs or VarPowerFlowReferenceType.i_B in refs
    mask[3] = VarPowerFlowReferenceType.v_C in refs or VarPowerFlowReferenceType.i_C in refs

    return mask


def build_emt_branch_bus_mask_from_refs(
        refs: set[VarPowerFlowReferenceType],
        side: str,
) -> list[bool]:
    """
    Build the AC bus phase mask implied by one branch-side editor interface.

    :param refs: Power-flow references still exposed by the edited root block.
    :param side: Branch side identifier. Expected values are ``from`` and ``to``.
    :return: Phase mask ordered as ``[N, A, B, C]``.
    """
    mask: list[bool] = list([False, False, False, False])

    # The branch interface has side-specific variables, so the mask must be
    # derived independently for the from and to terminals.
    if side == "from":
        mask[0] = VarPowerFlowReferenceType.vf_N in refs or VarPowerFlowReferenceType.if_N in refs
        mask[1] = VarPowerFlowReferenceType.vf_A in refs or VarPowerFlowReferenceType.if_A in refs
        mask[2] = VarPowerFlowReferenceType.vf_B in refs or VarPowerFlowReferenceType.if_B in refs
        mask[3] = VarPowerFlowReferenceType.vf_C in refs or VarPowerFlowReferenceType.if_C in refs
    elif side == "to":
        mask[0] = VarPowerFlowReferenceType.vt_N in refs or VarPowerFlowReferenceType.it_N in refs
        mask[1] = VarPowerFlowReferenceType.vt_A in refs or VarPowerFlowReferenceType.it_A in refs
        mask[2] = VarPowerFlowReferenceType.vt_B in refs or VarPowerFlowReferenceType.it_B in refs
        mask[3] = VarPowerFlowReferenceType.vt_C in refs or VarPowerFlowReferenceType.it_C in refs
    else:
        # Unsupported sides are handled as an empty mask. The caller decides
        # whether this is acceptable or whether the save operation must stop.
        pass

    return mask

# Todo: is this class necessary?
class _FallbackDocument:
    """
    Minimal document shim for legacy callers that don't pass a document.

    In the legacy code-path the editor edits the block directly (there is
    no separate working copy), so ``commit()`` is a no-op.
    """

    def commit(self) -> None:
        """No-op: edits already live on the block."""


class DynamicBlockEditorGUI(QtWidgets.QMainWindow):
    """
    DynamicModelEditorGUI
    """

    dirtyStateChanged = Signal(bool)

    UNARY_MATH_BLOCK_TYPES: set[BlockType] = {
        BlockType.CONST,
        BlockType.GAIN,
        BlockType.ABS,
        BlockType.INTEGRATOR,
        BlockType.POWER,
        BlockType.SIN,
        BlockType.COS,
        BlockType.TAN,
        BlockType.EXP,
        BlockType.LOG,
        BlockType.LOG10,
        BlockType.SQRT,
        BlockType.ASIN,
        BlockType.ACOS,
        BlockType.ATAN,
        BlockType.SINH,
        BlockType.COSH,
        BlockType.TANH,
        BlockType.REAL,
        BlockType.IMAG,
        BlockType.CONJ,
        BlockType.ANGLE,
    }

    def __init__(self,
                 var_factory: VarFactory,
                 api_object: ALL_DEV_TYPES,
                 circuit: MultiCircuit,
                 current_theme: DynEditorGraphicsModes,
                 mode: DynamicSimulationMode = DynamicSimulationMode.RMS,
                 templates_list: Optional[List[RmsModelTemplate | EmtModelTemplate | FmuTemplate]] = None,
                 is_root_editor=False,
                 modal: bool = True,
                 workspace_embedded: bool = False,
                 root_block: Block = Block(),
                 current_block: Block = Block(),
                 document=None,
                 block2blocktype: Dict[int, BlockType] = dict()):
        """
        Initializes a dynamic block editor window.

        In the new document-based architecture the editor receives two
        blocks that already live inside the working tree owned by
        :class:`DynamicEditorDocument`:

        * ``root_block`` — the top-level working block for the tab.
        * ``current_block`` — the specific node being edited right now.

        The editor never clones.  All edits target the working tree
        directly.

        Legacy callers that pass ``block=`` and ``main_editor=`` are
        still supported but deprecated.

        :param var_factory: Factory object responsible for variable creation and management.
        :param api_object: Optional API object associated with the dynamic model.
        :param circuit: Circuit context that owns the edited dynamic device.
        :param mode: Specifies the editor mode, either RMS or EMT.
        :param templates_list: Optional block-template catalogue entries exposed to the editor.
        :param is_root_editor: Indicates whether this instance is the root-level editor.
        :param modal: Specifies whether the editor window should be modal.
        :param workspace_embedded: Whether the editor is hosted inside the tabbed dynamic-editor workspace.
        :param root_block: Top-level working block (from the document).
        :param current_block: Block currently being edited (from the working tree).
        :param block: Deprecated — use ``current_block`` instead.
        :param main_editor: Deprecated — use ``is_root_editor`` instead.
        :return: None.
        """
        super().__init__()

        self.ui = Ui_BlockEditorWindow()
        self.ui.setupUi(self)

        # The editor owns its own toast manager so save notifications are
        # stacked above this page instead of behind it on the main window.
        self.toast_manager: ToastManager = ToastManager(parent=self, position_top=False)

        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.ui.deviceLabel.setText(api_object.name)

        self.block_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 300
        self.mime_type: str = "application/x-veragrid-dynamics-block"

        self.setWindowTitle(self.tr("Dynamic Model Editor"))

        self.ui.splitter.setStretchFactor(0, 6)
        self.ui.splitter.setStretchFactor(1, 10)

        self.var_factory = var_factory
        self.api_object = api_object

        self.circuit: MultiCircuit = circuit
        self.mode = mode
        self.is_root_editor = is_root_editor
        self.workspace_embedded = workspace_embedded

        self._document = document if document is not None else _FallbackDocument()
        self._block2blocktype: Dict[int, BlockType] = block2blocktype
        self._navigation_delegate = None
        self.templates_list: List[
            RmsModelTemplate | EmtModelTemplate | FmuTemplate] = templates_list if templates_list is not None else list()

        self._emt_bus_fallback_warning_shown: bool = False
        self._selected_side_block: Block | None = None
        self._validation_issue_overlay_active: bool = False
        self.setWindowTitle(self.tr("Dynamic Model Editor [{mode}]").format(mode=self.mode.name))
        self.block_counters: Dict[BlockType, int] = dict()
        self.scene: graph.DiagramScene = graph.DiagramScene(self)
        self.changes_applied: bool = False
        self.has_unapplied_changes: bool = False
        self.dynamic_editor_entry: DynamicEditorEntry | None = None
        self._prepared_to_delete: bool = False
        self.colors_palet: graph.EditorGraphicsDefaultsDark | graph.EditorGraphicsDefaultsLight = graph.EditorGraphicsDefaultsDark()
        self.current_theme: DynEditorGraphicsModes = current_theme
        self.set_colors_palet()

        self.root_block: Block = root_block
        self.main_block: Block = current_block

        self.blocktype2templatebuilder = get_blocktype2template_builder_dict()

        self.devices_static_params_mapping: Dict[DeviceType, List[ParamPowerFlowReferenceType]] = (
            self.circuit.get_devices_static_params_mapping()
        )

        self.diagram: BlockDiagram = self.main_block.diagram

        if self.workspace_embedded:
            self.menuBar().setVisible(False)
        else:
            pass

        # library
        self.library = DynamicEditorLibrary(self.api_object, self.mode, self.templates_list)
        self.library_proxy_model = LibraryTreeFilterProxyModel(
            search_role=graph.EditorGraphicsCommonFeatures.LIBRARY_SEARCH_TEXT_ROLE,
            parent=self.ui.libraryTreeView,
        )
        self.library_proxy_model.setSourceModel(self.library.library_model)

        self.ui.libraryTreeView.setModel(self.library_proxy_model)
        self.ui.libraryTreeView.setDragEnabled(True)
        self.ui.libraryTreeView.setHeaderHidden(False)
        self.ui.libraryTreeView.setUniformRowHeights(True)

        self.ui.librarySearchLineEdit.setVisible(True)
        self.ui.librarySearchLineEdit.setClearButtonEnabled(True)
        self.ui.librarySearchLineEdit.textChanged.connect(self.on_library_search_text_changed)
        self.library_find_shortcut = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Find, self)
        self.library_find_shortcut.activated.connect(self.focus_library_search)
        self.reset_library_tree_expansion()

        # Build variables table
        self.variables_model = dialog_models.WrappableBlockTableModel(
            var_factory=self.var_factory,
            parameter_value_type_role=graph.EditorGraphicsCommonFeatures.PARAMETER_VALUE_TYPE_ROLE,
            parameter_editable_role=graph.EditorGraphicsCommonFeatures.PARAMETER_EDITABLE_ROLE,
            block_search_role=graph.EditorGraphicsCommonFeatures.BLOCK_SEARCH_ROLE,
            parent=self.ui.variablesTableView
        )
        self.variables_model.set_mode(DynamicTableModelMode.VARIABLES)
        self.variables_model.set_delegates()
        self.variables_search = QLineEdit()
        self.variables_search.setPlaceholderText(self.tr("Search variables..."))
        self.variables_search.setClearButtonEnabled(True)
        self.ui.verticalLayout_7.insertWidget(0, self.variables_search)
        self.variables_proxy = dialog_models.BlockTableFilterProxyModel(search_role=graph.EditorGraphicsCommonFeatures.BLOCK_SEARCH_ROLE,
                                                          parent=self.ui.variablesTableView)
        self.variables_proxy.setSourceModel(self.variables_model)
        self.ui.variablesTableView.setModel(self.variables_proxy)
        self.variables_search.textChanged.connect(
            lambda text: self.variables_proxy.setFilterFixedString(text.strip())
        )
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

        # Build parameters table
        self.parameters_model = dialog_models.WrappableBlockTableModel(
            api_object=self.api_object,
            var_factory=self.var_factory,
            parameter_value_type_role=graph.EditorGraphicsCommonFeatures.PARAMETER_VALUE_TYPE_ROLE,
            parameter_editable_role=graph.EditorGraphicsCommonFeatures.PARAMETER_EDITABLE_ROLE,
            block_search_role=graph.EditorGraphicsCommonFeatures.BLOCK_SEARCH_ROLE,
            parent=self.ui.parametersTableView
        )
        self.parameters_model.set_mode(DynamicTableModelMode.PARAMETERS)
        self.parameters_model.set_delegates()
        self.parameters_search = QLineEdit()
        self.parameters_search.setPlaceholderText(self.tr("Search parameters..."))
        self.parameters_search.setClearButtonEnabled(True)
        self.ui.verticalLayout_8.insertWidget(0, self.parameters_search)
        self.parameters_proxy = dialog_models.BlockTableFilterProxyModel(search_role=graph.EditorGraphicsCommonFeatures.BLOCK_SEARCH_ROLE,
                                                           parent=self.ui.parametersTableView)
        self.parameters_proxy.setSourceModel(self.parameters_model)
        self.ui.parametersTableView.setModel(self.parameters_proxy)
        self.parameters_search.textChanged.connect(
            lambda text: self.parameters_proxy.setFilterFixedString(text.strip())
        )
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

        # Build equations table
        self.equations_model = dialog_models.WrappableBlockTableModel(
            var_factory=self.var_factory,
            parameter_value_type_role=graph.EditorGraphicsCommonFeatures.PARAMETER_VALUE_TYPE_ROLE,
            parameter_editable_role=graph.EditorGraphicsCommonFeatures.PARAMETER_EDITABLE_ROLE,
            block_search_role=graph.EditorGraphicsCommonFeatures.BLOCK_SEARCH_ROLE,
            parent=self.ui.equationsTableView
        )
        self.equations_model.set_mode(DynamicTableModelMode.EQUATIONS)
        self.equations_model.set_delegates()
        self._equations_latex_delegate = self.ui.equationsTableView.itemDelegateForColumn(1)
        self.equations_model.latex_invalidation_requested.connect(
            self._invalidate_equations_latex
        )
        self.equations_search = QLineEdit()
        self.equations_search.setPlaceholderText(self.tr("Search equations..."))
        self.equations_search.setClearButtonEnabled(True)
        self.ui.verticalLayout_9.insertWidget(0, self.equations_search)
        self.equations_proxy = dialog_models.BlockTableFilterProxyModel(search_role=graph.EditorGraphicsCommonFeatures.BLOCK_SEARCH_ROLE,
                                                          parent=self.ui.equationsTableView)
        self.equations_proxy.setSourceModel(self.equations_model)
        self.ui.equationsTableView.setModel(self.equations_proxy)
        self.equations_search.textChanged.connect(
            lambda text: self.equations_proxy.setFilterFixedString(text.strip())
        )
        equations_header: QtWidgets.QHeaderView = self.ui.equationsTableView.horizontalHeader()
        equations_header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        equations_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        equations_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        equations_vheader = self.ui.equationsTableView.verticalHeader()
        equations_vheader.setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        equations_vheader.setVisible(False)
        self.ui.equationsTableView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ui.equationsTableView.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.ui.equationsTableView.doubleClicked.connect(self.on_parameters_table_double_clicked)
        self.ui.equationsTableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.equationsTableView.customContextMenuRequested.connect(self.show_equations_table_context_menu)

        self.parameters_model.block_updated.connect(self.on_block_updated)
        self.variables_model.block_updated.connect(self.on_block_updated)
        self.equations_model.block_updated.connect(self.on_block_updated)

        self.view: graph.GraphicsView = graph.GraphicsView(self.scene)
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

        # Button do it to save built scene
        self.ui.doItButton.clicked.connect(self.apply_changes)

        self.ui.toolBox.currentChanged.connect(self.handle_side_panel_page_changed)
        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        # if self.mode == DynamicSimulationMode.EMT and self.is_root_editor:
        #     self._ensure_full_emt_editor_interface()
        # else:
        #     pass
        dialog_models._ensure_block_tree_names(self.main_block, prefix="block")

        # The root device editor is the only place where the dynamic model is
        # coupled to the network buses. Ensure the corresponding bus helper
        # models exist before any scene bootstrap path runs, so fresh opens,
        # reopens with saved diagrams, and child-containing models all observe
        # the same already-initialized bus-side contract.
        if self.is_root_editor:
            if self.mode == DynamicSimulationMode.RMS:
                if isinstance(self.api_object, InjectionParent):
                    dialog_models._initialize_editor_assigned_rms_bus_model(bus=self.api_object.bus,
                                                                            var_factory=self.var_factory)
                elif isinstance(self.api_object, BranchParent):
                    dialog_models._initialize_editor_assigned_rms_bus_model(bus=self.api_object.bus_from,
                                                                            var_factory=self.var_factory)
                    dialog_models._initialize_editor_assigned_rms_bus_model(bus=self.api_object.bus_to,
                                                                            var_factory=self.var_factory)
                else:
                    pass
            elif self.mode == DynamicSimulationMode.EMT:
                if isinstance(self.api_object, InjectionParent):
                    dialog_models._initialize_editor_assigned_emt_bus_model(bus=self.api_object.bus,
                                                                            api_object=self.api_object,
                                                                            circuit=self.circuit,
                                                                            var_factory=self.var_factory)
                elif isinstance(self.api_object, BranchParent):
                    dialog_models._initialize_editor_assigned_emt_bus_model(bus=self.api_object.bus_from,
                                                                            api_object=self.api_object,
                                                                            circuit=self.circuit,
                                                                            var_factory=self.var_factory)
                    dialog_models._initialize_editor_assigned_emt_bus_model(bus=self.api_object.bus_to,
                                                                            api_object=self.api_object,
                                                                            circuit=self.circuit,
                                                                            var_factory=self.var_factory)
                else:
                    pass
            else:
                pass
        else:
            pass

        requires_connection_bootstrap: bool = dialog_models.block_requires_editor_connection_bootstrap(self.main_block)

        # Automatically build items for models with no graphical info
        if not self.main_block.empty() and not self.main_block.diagram.node_data and not requires_connection_bootstrap:
            if self.main_block.children:
                input_output_blocks: List[Block] = list()
                block_positions_dict: Dict[int, Tuple[float, float]] = dict()

                # First of all create all Blocks that will be needed but without adding them to the scene and without creating the node in the diagram and add thme to the correspondant list:

                self.add_connection_blocks(input_output_blocks)
                # Blocks in children --> self.main_block.children

                layout_graph = self._build_elk_layout_graph(
                    self.main_block.children,
                    input_output_blocks,
                )
                layout_result = SugiyamaLayeredPythonEngine().compute(layout_graph)
                block_positions_dict.update(
                    {
                        int(node.identifier): (node.x or 0.0, node.y or 0.0)
                        for node in layout_result.graph.children
                    }
                )


                # Oce everything is calculated we build the items from the blocks and the calculated positions, add them to an items list and create the DiagramNodes:

                blockitems_list: List[graph.BlockItem | graph.GenericBlockItem | graph.RectBaseArithmeticOpItem | graph.RoundBaseArithmeticOpItem | graph.UnOpItem] = list()
                items_by_uid: Dict[int, graph.BlockItem | graph.GenericBlockItem] = dict()
                for child in self.main_block.children:
                    position = block_positions_dict[child.uid]
                    item = self.generate_block_item_for_block(child, position[0], position[1])
                    blockitems_list.append(item)
                    items_by_uid[child.uid] = item

                for blk in input_output_blocks:
                    position = block_positions_dict[blk.uid]
                    item = self.generate_ext_conn_block_item_for_block(blk, position[0], position[1])
                    blockitems_list.append(item)
                    items_by_uid[blk.uid] = item

                if len(blockitems_list) != 0:
                    self._connect_items_from_layout(items_by_uid, layout_result.graph)

                # we need an algorithm to create the connections properly:
                    # bends/corners not in the same place
                    # prevent them from overlapping with other blocks
                    # prevent them from overlapping with other connectors in the same direction
                    # allow only 90degree angles, no 180.
                # once we have all the items created and well positioned we build the connections


            elif not self.main_block.children and not self.main_block.is_eq_decomposable():
                self.add_connection_items()


        # Build items for models with graphical info
        elif not self.main_block.diagram.node_data:
            # here we add the connection variables to the main block
            if self.is_root_editor:
                self.add_connection_vars()
                # self.add_api_obj_mapping()

            self.add_connection_items()
        else:
            pass
        self.rebuild_scene_from_diagram()

    def set_colors_palet(self):
        if self.current_theme == DynEditorGraphicsModes.DARK:
            self.colors_palet = graph.EditorGraphicsDefaultsDark()
        else:
            self.colors_palet = graph.EditorGraphicsDefaultsLight()

    def set_navigation_delegate(self, delegate) -> None:
        """
        Register the navigation delegate responsible for opening child blocks.

        The delegate must expose a ``navigate_to_block(block: Block) -> None``
        method.  :class:`DynamicEditorTab` acts as the default delegate.

        :param delegate: Object that can open blocks for navigation.
        :return: None.
        """
        self._navigation_delegate = delegate

    def request_navigate_to_block(self, block: Block) -> None:
        """
        Request navigation into a child block.

        Delegates the request to the registered navigation delegate.
        If no delegate has been registered, the request is silently ignored.

        :param block: Child block to navigate into.
        :return: None.
        """
        if self._navigation_delegate is not None:
            self._navigation_delegate.navigate_to_block(block)

    def changeEvent(self, event: QtCore.QEvent) -> None:
        """
        Refresh runtime-owned editor strings after a Qt language change.

        :param event: Incoming Qt change event.
        :return: None.
        """
        QtWidgets.QMainWindow.changeEvent(self, event)

        if event.type() == QtCore.QEvent.Type.LanguageChange:
            self.ui.retranslateUi(self)
            self.refresh_runtime_translations()
        else:
            pass

    def refresh_runtime_translations(self) -> None:
        """
        Refresh the editor strings that are created from Python code.

        :return: None.
        """
        self.setWindowTitle(self.tr("Dynamic Model Editor [{mode}]").format(mode=self.mode.name))
        self.variables_search.setPlaceholderText(self.tr("Search variables..."))
        self.parameters_search.setPlaceholderText(self.tr("Search parameters..."))
        self.equations_search.setPlaceholderText(self.tr("Search equations..."))
        item: Any
        for item in self.scene.items():
            refresh_port_metadata = getattr(item, "refresh_port_metadata", None)
            if callable(refresh_port_metadata):
                refresh_port_metadata()
            else:
                pass
        self.scene.update()

    # Todo: remove this function when all the dialogs are unified
    def set_modal_template_metadata(self, block: Block,
                                    kind: str,
                                    config: Dict[str, Any]) -> None:
        """
        Persist the modal-builder metadata on one block.

        :param block: Target block.
        :param kind: Stable modal kind key.
        :param config: Serializable modal configuration.
        :return: None.
        """
        block.__dict__[graph.EditorGraphicsCommonFeatures.MODAL_TEMPLATE_KIND_ATTR] = kind
        block.__dict__[graph.EditorGraphicsCommonFeatures.MODAL_TEMPLATE_CONFIG_ATTR] = copy.deepcopy(config)

    # Todo: remove this function when all the dialogs are unified
    def get_modal_template_metadata(self, block: Block | None) -> tuple[str | None, Dict[str, Any] | None]:
        """
        Return the modal-builder metadata stored on one block.

        :param block: Candidate block.
        :return: `(kind, config)` or `(None, None)` when absent.
        """
        if block is None:
            return None, None
        else:
            pass

        kind: Any = block.__dict__.get(graph.EditorGraphicsCommonFeatures.MODAL_TEMPLATE_KIND_ATTR, None)
        config: Any = block.__dict__.get(graph.EditorGraphicsCommonFeatures.MODAL_TEMPLATE_CONFIG_ATTR, None)

        if isinstance(kind, str) and isinstance(config, dict):
            return kind, copy.deepcopy(config)
        else:
            return None, None

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
            payload = self.library.library_model.get_drag_payload(drag_token)

            if isinstance(payload,
                          (BlockType, BasicBlockTemplateDescriptor, RmsModelTemplate, EmtModelTemplate, FmuTemplate)):
                return payload
            else:
                return None
        else:
            return None

    def build_position_changed_callback(self, block_uid: int) -> graph.BlockPositionChangedCallback:
        """
        Build the explicit callback object used by graphics items to report movement.

        :param block_uid: Moved block uid.
        :return: Position change callback wrapper.
        """

        return graph.BlockPositionChangedCallback(self, block_uid)

    def create_item_using_blocktype_wizard(self,
                                           blocktype: BlockType,
                                           x_pos: float,
                                           y_pos: float) -> graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | None:
        """
        Materialize one library payload on the diagram scene.
        """

        count: int = self.block_counters.get(blocktype, 0) + 1
        item_name: str = f"{blocktype.name}_{count}"

        template_builder_class = self.blocktype2templatebuilder.get(blocktype, None)
        template_builder = template_builder_class(self.var_factory)
        name = "EMT fault"

        if template_builder is not None:
            dialog = DynTemplatesEditorDialog(name, template_builder.params)
        else:
            return

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:

            template = template_builder.eval()
            block_model = template.block

            block_item: graph.GenericBlockItem = graph.GenericBlockItem(
                editor=self,
                var_factory=self.var_factory,
                subsys=block_model,
                api_object=self.api_object,
                mode=self.mode,
                name=item_name,
                position_changed_callback=self.build_position_changed_callback(block_model.uid)
            )

            self.block_counters[blocktype] = count
            block_item.set_subsystem(block_model)
            block_item.position_changed_callback = self.build_position_changed_callback(block_model.uid)
            block_item.build_item()
            self.main_block.add(block_model)
            self.scene.addItem(block_item)
            block_item.setPos(QtCore.QPointF(x_pos, y_pos))
            self.diagram.add_node(
                name=item_name,
                x=x_pos,
                y=y_pos,
                tpe=blocktype.name,
                device_uid=block_model.uid,
            )
            self.mark_unapplied_changes()
            return block_item

        else:
            return

    def create_generic_block_item(self, block_type: BlockType, x_pos, y_pos) -> graph.GenericBlockItem | None:
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
            item = graph.GenericBlockItem(
                editor=self,
                var_factory=self.var_factory,
                subsys=model,
                api_object=self.api_object,
                mode=self.mode,
                name=model.name,
                position_changed_callback=self.build_position_changed_callback(model.uid)
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

    def create_basic_arithmetic_op_item(self, block_type: BlockType, x_pos: float,
                                        y_pos: float) -> graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | None:
        """
        Create a Sum item that represents addition and subtraction
        """

        count: int = self.block_counters.get(block_type, 0) + 1
        item_name: str = f"{block_type.name}_{count}"

        template_builder = None
        block_model = None
        name = ""

        if block_type == BlockType.SUM:
            template_builder = BasicBlockTemplates.AdderTemplate(vf=self.var_factory)
        elif block_type == BlockType.PRODUCT:
            template_builder = BasicBlockTemplates.ProductTemplate(vf=self.var_factory)

        if template_builder is not None:
            dialog = DynTemplatesEditorDialog(name, template_builder.params)
            dialog.exec()
            template = template_builder.eval()
            block_model = template

        if block_model is not None and len(block_model.in_vars) <= 3:
            round_base_op_item: graph.RoundBaseArithmeticOpItem = graph.RoundBaseArithmeticOpItem(var_factory=self.var_factory,
                                                                                      subsys=block_model,
                                                                                      block_type=block_type,
                                                                                      editor=self,
                                                                                      position_changed_callback=self.build_position_changed_callback(
                                                                                          block_model.uid))

            self.block_counters[block_type] = count
            graph.RoundBaseArithmeticOpItem.position_changed_callback = self.build_position_changed_callback(block_model.uid)
            self.main_block.add(block_model)
            self.scene.addItem(round_base_op_item)
            round_base_op_item.setPos(QtCore.QPointF(x_pos, y_pos))
            self.diagram.add_node(
                name=item_name,
                x=x_pos,
                y=y_pos,
                tpe=block_type.name,
                device_uid=block_model.uid,
            )
            self.mark_unapplied_changes()

            return round_base_op_item

        elif block_model is not None and len(block_model.in_vars) > 3:
            rect_base_op_item: graph.RectBaseArithmeticOpItem = graph.RectBaseArithmeticOpItem(var_factory=self.var_factory,
                                                                                   subsys=block_model,
                                                                                   block_type=block_type,
                                                                                   editor=self,
                                                                                   position_changed_callback=self.build_position_changed_callback(
                                                                                       block_model.uid))

            self.block_counters[block_type] = count
            graph.RoundBaseArithmeticOpItem.position_changed_callback = self.build_position_changed_callback(block_model.uid)
            self.main_block.add(block_model)
            self.scene.addItem(rect_base_op_item)
            rect_base_op_item.setPos(QtCore.QPointF(x_pos, y_pos))
            self.diagram.add_node(
                name=item_name,
                x=x_pos,
                y=y_pos,
                tpe=block_type.name,
                device_uid=block_model.uid,
            )
            self.mark_unapplied_changes()

            return rect_base_op_item

        return None

    def create_block_item_from_blocktype(self, block_type: BlockType, x_pos: float, y_pos: float) -> graph.GenericBlockItem | None:
        """
        Create and place a block item in the canvas scene.

        :param block_type:
        :param x_pos:
        :param y_pos:
        :return:
        """
        block_model = None
        item_name = ""
        count: int = self.block_counters.get(block_type, 0) + 1

        item_name: str = f"{block_type.name}_{count}"
        block_model: Block | None = create_block_of_type(
            var_factory=self.var_factory,
            block_type=block_type,
            item_name=item_name,
            api_object=self.api_object,
        )
        self.block_counters[block_type] = count

        # no we have the name and the block
        if block_model is not None:
            self.main_block.add(block_model)
            if block_type in self.UNARY_MATH_BLOCK_TYPES:
                item = graph.UnOpItem(
                    editor=self,
                    var_factory=self.var_factory,
                    subsys=block_model,
                    api_object=self.api_object,
                    mode=self.mode,
                    block_type=block_type,
                    name=block_model.name,
                    position_changed_callback=self.build_position_changed_callback(block_model.uid)
                )

            else:
                item = graph.GenericBlockItem(
                    editor=self,
                    var_factory=self.var_factory,
                    subsys=block_model,
                    api_object=self.api_object,
                    mode=self.mode,
                    name=block_model.name,
                    position_changed_callback=self.build_position_changed_callback(block_model.uid)
                )

            item.setPos(QtCore.QPointF(x_pos, y_pos))
            self.scene.addItem(item)

            self.diagram.add_node(
                name=item_name,
                x=x_pos,
                y=y_pos,
                tpe=block_type.name,
                device_uid=block_model.uid
            )

            self.mark_unapplied_changes()
            # Keep the diagram synchronized so later features can rebuild from the same data source.

            return item
        else:
            return None

    def create_block_item(self, block_type: BlockType, x_pos: float, y_pos: float) -> graph.BlockItem | None:
        """
        Create and place a block item in the canvas scene.

        :param block_type:
        :param x_pos:
        :param y_pos:
        :return:
        """
        count: int = self.block_counters.get(block_type, 0) + 1
        item_name: str = f"{block_type.name}_{count}"
        block_item: graph.BlockItem = graph.BlockItem(editor=self, var_factory=self.var_factory, api_object=self.api_object,
                                          mode=self.mode,
                                          name=item_name)
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
            block_item.position_changed_callback = self.build_position_changed_callback(block_model.uid)
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

    def connect_items(self, items_list: List[graph.BlockItem | graph.GenericBlockItem]):
        """
        create connection lines to show in editor
        :param items_list:
        :type items_list:
        :return:
        :rtype:
        """

        for item_1 in items_list:
            for item_2 in items_list:
                if item_1.subsys.uid != item_2.subsys.uid:
                    pairs, power_flow_pairs = find_connections(item_1.subsys, item_2.subsys)
                    if pairs:
                        self.create_conn_items(item_1, item_2, pairs)

                    if power_flow_pairs:
                        self.create_conn_items(item_1, item_2, power_flow_pairs)

                    pairs, power_flow_pairs = find_connections(item_2.subsys, item_1.subsys)
                    if pairs:
                        self.create_conn_items(item_2, item_1, pairs)

                    if power_flow_pairs:
                        self.create_conn_items(item_1, item_2, power_flow_pairs)

    def create_conn_items(self, item_source: graph.BlockItem | graph.GenericBlockItem, item_dest:graph.BlockItem | graph.GenericBlockItem,
                          pairs: List[tuple[Var, Var]]):
        """
        Create the connection items for two block items
        :param item_source:
        :type item_source:
        :param item_dest:
        :type item_dest:
        :param pairs:
        :type pairs:
        :return:
        :rtype:
        """
        for source_var, target_var in pairs:
            source_port = None
            for port in item_source.outputs:
                if port.base_var is not None and port.base_var.uid == source_var.uid:
                    source_port = port
                    break

            target_port = None
            for port in item_dest.inputs:
                if port.base_var is not None and port.base_var.uid == target_var.uid:
                    target_port = port
                    break
            if target_port is not None and source_port is not None:
                connection = graph.ConnectionItem(
                    source_port=source_port,
                    target_port=target_port,
                    diagram=self.diagram,
                    editor=self,
                    route_style="RETICULAR",
                    locked=False,
                )
                connection.recolour()
                self.scene.addItem(connection)
                self.diagram.add_branch(
                    connectionitem_uid=connection.uid,
                    device_uid_from=item_source.subsys.uid,
                    device_uid_to=item_dest.subsys.uid,
                    port_number_from=source_port.index,
                    port_number_to=target_port.index,
                    color=connection.pen().color().name(),
                    route_style=connection.route_style,
                    locked=connection.route_locked,
                )

    def generate_block_item_for_block(self, block_model: Block,
                                      x_pos: float,
                                      y_pos: float) -> graph.GenericBlockItem:
        """
        Create and place a block item in the canvas scene.

        :param block_model:
        :param x_pos: pre-computed x position (Sugiyama layout).
        :param y_pos: pre-computed y position (Sugiyama layout).
        :return:
        """
        item_name: str = f"{block_model.name}"

        block_type = self._block2blocktype.get(block_model.uid, None)

        if block_type == BlockType.SUM or block_type == BlockType.PRODUCT:

            count: int = self.block_counters.get(block_type, 0) + 1

            if len(block_model.in_vars) <= 3:
                item: graph.RoundBaseArithmeticOpItem = graph.RoundBaseArithmeticOpItem(
                    var_factory=self.var_factory,
                    subsys=block_model,
                    block_type=block_type,
                    editor=self,
                    position_changed_callback=self.build_position_changed_callback(
                        block_model.uid))
            else:
                item: graph.RectBaseArithmeticOpItem = graph.RectBaseArithmeticOpItem(
                    var_factory=self.var_factory,
                    subsys=block_model,
                    block_type=block_type,
                    editor=self,
                    position_changed_callback=self.build_position_changed_callback(
                        block_model.uid))

            self.block_counters[block_type] = count
            item.recolour()
            self.diagram.add_node(
                name=item_name,
                x=x_pos,
                y=y_pos,
                tpe=block_type.name,
                device_uid=block_model.uid
            )

        elif block_type in self.UNARY_MATH_BLOCK_TYPES:
            item = graph.UnOpItem(
                editor=self,
                var_factory=self.var_factory,
                subsys=block_model,
                api_object=self.api_object,
                mode=self.mode,
                block_type=block_type,
                name=item_name,
                position_changed_callback=self.build_position_changed_callback(block_model.uid)
            )
            self.diagram.add_node(
                name=item_name,
                x=x_pos,
                y=y_pos,
                tpe=block_type.name,
                device_uid=block_model.uid
            )

        else:

            item = graph.GenericBlockItem(
                editor=self,
                var_factory=self.var_factory,
                subsys=block_model,
                api_object=self.api_object,
                mode=self.mode,
                name=item_name,
                position_changed_callback=self.build_position_changed_callback(block_model.uid)
            )
            self.diagram.add_node(
                name=item_name,
                x=x_pos,
                y=y_pos,
                tpe=block_type.name if block_type is not None else "",
                device_uid=block_model.uid
            )

        # The symbolic block has to be attached first so the graphics item can build its ports from it.

        item.setPos(QtCore.QPointF(x_pos, y_pos))
        item.recolour()
        self.scene.addItem(item)
        self.mark_unapplied_changes()

        return item


    def generate_ext_conn_block_item_for_block(self, block_model: Block,
                                      x_pos: float,
                                      y_pos: float) -> graph.BlockItem:
        """
        Create and place a block item in the canvas scene.

        :param block_model:
        :param x_pos: Optional pre-computed x position (Sugiyama layout).
        :param y_pos: Optional pre-computed y position (Sugiyama layout).
        :return:
        """
        item_name: str = f"{block_model.name}"


        item: graph.ProtectedConnectionBlockItem = graph.ProtectedConnectionBlockItem(editor=self,
                                                                                            var_factory=self.var_factory,
                                                                                            name=item_name,
                                                                                            mode=self.mode,
                                                                                            api_object=self.api_object)
        item.set_subsystem(block_model)
        item.position_changed_callback = self.build_position_changed_callback(block_model.uid)
        item.build_item()

        item.setPos(QtCore.QPointF(x_pos, y_pos))
        item.recolour()
        self.scene.addItem(item)

        # Keep the diagram synchronized so later features can rebuild from the same data source.
        block_type = self._get_layout_block_kind(block_model)
        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=block_type,
            device_uid=block_model.uid
        )
        return item

    def _get_layout_block_kind(self, block_model: Block) -> str:
        if len(block_model.out_vars) > 0 and len(block_model.in_vars) == 0:
            return BlockType.INPUT_CONN.name
        if len(block_model.in_vars) > 0 and len(block_model.out_vars) == 0:
            return BlockType.OUTPUT_CONN.name
        return "internal"

    def _build_elk_layout_graph(
        self,
        child_blocks: List[Block],
        input_output_blocks: List[Block],
    ) -> SugiyamaGraph:
        layout_nodes: List[SugiyamaNode] = list()
        layout_edges: List[SugiyamaEdge] = list()
        all_blocks: List[Block] = list(child_blocks) + list(input_output_blocks)
        out_index_by_uid: Dict[int, Dict[int, int]] = dict()
        in_index_by_uid: Dict[int, Dict[int, int]] = dict()
        shared_out_refs: Dict[object, List[tuple[int, int]]] = dict()
        shared_in_refs: Dict[object, List[tuple[int, int]]] = dict()
        pf_out_refs: Dict[object, List[tuple[int, int]]] = dict()
        pf_in_refs: Dict[object, List[tuple[int, int]]] = dict()

        for block_model in all_blocks:
            ports: List[SugiyamaPort] = list()
            out_uid_lookup: Dict[int, int] = dict()
            in_uid_lookup: Dict[int, int] = dict()
            for port_index, in_var in enumerate(block_model.in_vars):
                in_uid_lookup[in_var.uid] = port_index
                if in_var.shared_ref is not None:
                    shared_in_refs.setdefault(in_var.shared_ref, list()).append((block_model.uid, port_index))
                if in_var.ref is not None:
                    pf_in_refs.setdefault(in_var.ref, list()).append((block_model.uid, port_index))
                ports.append(
                    SugiyamaPort(
                        identifier=f"{block_model.uid}:in:{port_index}",
                        width=6.0,
                        height=6.0,
                        properties={
                            "role": "input",
                            "port_index": port_index,
                            "var_uid": in_var.uid,
                            "var_ref": in_var.ref,
                            "shared_ref": in_var.shared_ref,
                        },
                        layout_options={
                            "org.vera.sugiyama.port.side": "WEST",
                        },
                    )
                )
            for port_index, out_var in enumerate(block_model.out_vars):
                out_uid_lookup[out_var.uid] = port_index
                if out_var.shared_ref is not None:
                    shared_out_refs.setdefault(out_var.shared_ref, list()).append((block_model.uid, port_index))
                if out_var.ref is not None:
                    pf_out_refs.setdefault(out_var.ref, list()).append((block_model.uid, port_index))
                ports.append(
                    SugiyamaPort(
                        identifier=f"{block_model.uid}:out:{port_index}",
                        width=6.0,
                        height=6.0,
                        properties={
                            "role": "output",
                            "port_index": port_index,
                            "var_uid": out_var.uid,
                            "var_ref": out_var.ref,
                            "shared_ref": out_var.shared_ref,
                        },
                        layout_options={
                            "org.vera.sugiyama.port.side": "EAST",
                        },
                    )
                )
            layout_nodes.append(
                SugiyamaNode(
                    identifier=str(block_model.uid),
                    width=160.0,
                    height=70.0,
                    ports=ports,
                    properties={
                        "name": block_model.name,
                        "kind": self._get_layout_block_kind(block_model),
                    },
                    layout_options={
                        "org.vera.sugiyama.portConstraints": "FIXED_ORDER",
                    },
                )
            )
            out_index_by_uid[block_model.uid] = out_uid_lookup
            in_index_by_uid[block_model.uid] = in_uid_lookup

        edge_uid = 1
        seen_edges: set[tuple[int, int, int, int]] = set()
        def add_edges_from_maps(
            source_map: Dict[object, List[tuple[int, int]]],
            target_map: Dict[object, List[tuple[int, int]]],
        ) -> None:
            nonlocal edge_uid
            for ref_value, sources in source_map.items():
                targets = target_map.get(ref_value, list())
                if not targets:
                    continue
                for source_uid, source_port_index in sources:
                    for target_uid, target_port_index in targets:
                        if source_uid == target_uid:
                            continue
                        edge_key = (
                            source_uid,
                            source_port_index,
                            target_uid,
                            target_port_index,
                        )
                        if edge_key in seen_edges:
                            continue
                        seen_edges.add(edge_key)
                        layout_edges.append(
                            SugiyamaEdge(
                                identifier=str(edge_uid),
                                sources=[f"{source_uid}:out:{source_port_index}"],
                                targets=[f"{target_uid}:in:{target_port_index}"],
                                properties={
                                    "source_uid": source_uid,
                                    "source_port_index": source_port_index,
                                    "target_uid": target_uid,
                                    "target_port_index": target_port_index,
                                },
                            )
                        )
                        edge_uid += 1

        add_edges_from_maps(shared_out_refs, shared_in_refs)
        add_edges_from_maps(pf_out_refs, pf_in_refs)

        return SugiyamaGraph(
            identifier="dynamic-block-editor",
            children=layout_nodes,
            edges=layout_edges,
            layout_options={
                "org.vera.sugiyama.algorithm": "layered",
                "org.vera.sugiyama.direction": "RIGHT",
                "org.vera.sugiyama.edgeRouting": "ORTHOGONAL",
                "org.vera.sugiyama.layered.layering.strategy": "NETWORK_SIMPLEX",
                "org.vera.sugiyama.layered.nodePlacement.strategy": "BRANDES_KOEPF",
            },
        )

    def _connect_items_from_layout(
        self,
        items_by_uid: Dict[int, graph.BlockItem | graph.GenericBlockItem],
        layout_graph: SugiyamaGraph,
    ) -> None:
        for edge in layout_graph.edges:
            src_uid = int(edge.properties["source_uid"])
            dst_uid = int(edge.properties["target_uid"])
            src_port_index = int(edge.properties["source_port_index"])
            dst_port_index = int(edge.properties["target_port_index"])

            src_item = items_by_uid.get(src_uid, None)
            dst_item = items_by_uid.get(dst_uid, None)
            if src_item is None or dst_item is None:
                continue

            try:
                src_port = src_item.outputs[src_port_index]
                dst_port = dst_item.inputs[dst_port_index]
            except IndexError:
                continue

            section = edge.sections[0] if edge.sections else None
            bend_points = section.bend_points if section is not None else []
            elbow_points = [QPointF(x, y) for x, y in bend_points]
            connection = graph.ConnectionItem(
                source_port=src_port,
                target_port=dst_port,
                diagram=self.diagram,
                con_uid=int(edge.identifier),
                elbow_points=elbow_points,
                route_style="RETICULAR",
                locked=False,
                editor=self,
            )
            connection.recolour()
            self.scene.addItem(connection)

    def generate_block_item_for_block_old(self, block_model: Block) -> GenericBlockItem | None:
        """
        Create and place a block item in the canvas scene.

        :param block_model:

        :return:
        """
        item_name: str = f"{block_model.name}"

        if block_model is not None:
            item = GenericBlockItem(
                var_factory=self.var_factory,
                subsys=block_model,
                api_object=self.api_object,
                mode=self.mode,
                name=item_name,
                position_changed_callback=self._build_position_changed_callback(block_model.uid)
            )

            # The symbolic block has to be attached first so the graphics item can build its ports from it.

            x, y = self._calculate_next_block_position(item)
            item.setPos(QtCore.QPointF(x, y))
            self.scene.addItem(item)

            self.diagram.add_node(
                name=item_name,
                x=x,
                y=y,
                tpe="",
                device_uid=block_model.uid
            )

            self.mark_unapplied_changes()

            return item
        else:
            return None

    def _calculate_next_block_position(self, item: graph.GenericBlockItem) -> tuple[float, float]:
        """
        Calculate the next available position for a block item using a grid layout.

        :param item: The block item to calculate position for (used to get its dimensions).
        :return: Tuple of (x, y) coordinates.
        """
        SCENE_WIDTH: float = 1200.0
        SCENE_HEIGHT: float = 800.0
        MARGIN_Y: float = 80.0
        COL_SPACING: float = 200.0
        ROW_SPACING: float = 150.0

        existing_count = sum(1 for i in self.scene.items() if isinstance(i, graph.GenericBlockItem))

        GRID_COLS: int = 3

        row: int = existing_count // GRID_COLS
        col: int = existing_count % GRID_COLS

        total_width: float = GRID_COLS * COL_SPACING
        start_x: float = (SCENE_WIDTH - total_width) / 2

        x: float = start_x + col * COL_SPACING
        y: float = MARGIN_Y + row * ROW_SPACING

        return x, y

    def create_connection_block_item(self, var: Var, block_type: BlockType, x_pos: float,
                                     y_pos: float, blocks_list: List[graph.BlockItem] | None) -> graph.BlockItem | None:
        """
        Create and place a block item in the canvas scene.

        :param var:
        :type var:
        :param block_type:
        :param x_pos:
        :param y_pos:
        :param blocks_list:
        :return:
        """
        count: int = self.block_counters.get(block_type, 0) + 1

        if var is None:
            # The RMS/EMT connection builders should never emit ``None``.
            # Keep this guard so a malformed editor interface does not crash the GUI.
            return None
        else:
            item_name: str = f"{var.name}"
            block_item: graph.ProtectedConnectionBlockItem = graph.ProtectedConnectionBlockItem(editor=self,
                                                                                    var_factory=self.var_factory,
                                                                                    name=item_name,
                                                                                    mode=self.mode,
                                                                                    api_object=self.api_object)
            block_model: Block = Block()

            if block_type == BlockType.INPUT_CONN:
                block_model.out_vars.append(var)

            elif block_type == BlockType.OUTPUT_CONN:
                block_model.in_vars.append(var)

            else:
                pass

            if block_model is not None:
                # The symbolic block has to be attached first so the graphics item can build its ports from it.

                block_item.set_subsystem(block_model)
                block_item.position_changed_callback = self.build_position_changed_callback(block_model.uid)
                block_item.build_item()

                # The editor block is the authoritative model container for later save/rebuild steps.
                self.main_block.add(block_model)
                self.scene.addItem(block_item)
                if blocks_list is not None:
                    blocks_list.append(block_item)
                else:
                    pass
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


    def create_connection_block(self, var: Var, block_type: BlockType, blocks_list: List[Block] | None):
        """
        Create and place a block item in the canvas scene.

        :param var:
        :type var:
        :param block_type:
        :param blocks_list:
        :return:
        """

        block_model: Block = Block()
        block_model.name = f"{var.name}"

        if block_type == BlockType.INPUT_CONN:
            block_model.out_vars.append(var)

        elif block_type == BlockType.OUTPUT_CONN:
            block_model.in_vars.append(var)

        else:
            pass

        if block_model is not None:
            # The symbolic block has to be attached first so the graphics item can build its ports from it.
            # The editor block is the authoritative model container for later save/rebuild steps.
            self.main_block.add(block_model)
            if blocks_list is not None:
                blocks_list.append(block_model)
            else:
                pass

    def create_template_block_item(self,
                                   template: RmsModelTemplate | EmtModelTemplate | FmuTemplate,
                                   x_pos: float,
                                   y_pos: float) -> graph.BlockItem | graph.GenericBlockItem | None:
        """
        Create and place a copied template block in the canvas scene.

        :param template:
        :param x_pos:
        :param y_pos:
        :return:
        """
        item_name: str = template.name
        block_model: Block = duplicate_block(template.block, var_factory=self.var_factory)
        self.main_block.add(block_model)
        item: graph.GenericBlockItem = graph.GenericBlockItem(
            editor=self,
            var_factory=self.var_factory,
            subsys=block_model,
            api_object=self.api_object,
            mode=self.mode,
            name=item_name,
            position_changed_callback=self.build_position_changed_callback(block_model.uid)
        )

        if item_name:
            block_model.name = item_name
        else:
            item_name = block_model.name
        item.setPos(QtCore.QPointF(x_pos, y_pos))
        self.scene.addItem(item)

        self.diagram.add_node(
            name=item_name,
            x=x_pos,
            y=y_pos,
            tpe=graph.EditorGraphicsCommonFeatures.TEMPLATE_NODE_TYPE,
            device_uid=block_model.uid
        )

        self.mark_unapplied_changes()

        return item

    # TODO: create PV power plant block item

    def _append_emt_branch_side_connection_specs(
            self,
            specs: List[ConnectionVarSpec],
            bus: Bus,
            side: str,
    ) -> None:
        """
        Append the default editable EMT connection specs for one branch side.

        The editor opens AC branch terminals with the full N/A/B/C voltage and
        current interface. The user can remove phases manually. When changes
        are applied, the connected bus EMT shell is rebuilt from the remaining
        visible ports.

        DC terminals are different because they do not have phases. They only
        expose one side-specific voltage input and one side-specific current
        output.

        :param specs: Connection specification list to extend.
        :param bus: Bus connected to the selected branch side.
        :param side: Branch side identifier. Expected values are ``from`` and ``to``.
        :return: None.
        """
        safe_bus_name: str = self._get_safe_bus_name(bus)
        voltage_refs: List[VarPowerFlowReferenceType] = list()
        current_refs: List[VarPowerFlowReferenceType] = list()

        # DC terminals must use side-specific references so that branch
        # interfaces do not mix the from and to bus quantities.
        if bus.is_dc:
            if side == "from":
                voltage_refs.append(VarPowerFlowReferenceType.Vf_dc)
                current_refs.append(VarPowerFlowReferenceType.If_dc)
            elif side == "to":
                voltage_refs.append(VarPowerFlowReferenceType.Vt_dc)
                current_refs.append(VarPowerFlowReferenceType.It_dc)
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "EMT branch interface",
                    f"Unsupported EMT branch side '{side}'. No ports were created for this side.",
                )
        else:
            # AC terminals intentionally open with the complete editable
            # phase set. The saved editor interface will later define the
            # effective bus phase mask.
            if side == "from":
                voltage_refs.append(VarPowerFlowReferenceType.vf_N)
                voltage_refs.append(VarPowerFlowReferenceType.vf_A)
                voltage_refs.append(VarPowerFlowReferenceType.vf_B)
                voltage_refs.append(VarPowerFlowReferenceType.vf_C)

                current_refs.append(VarPowerFlowReferenceType.if_N)
                current_refs.append(VarPowerFlowReferenceType.if_A)
                current_refs.append(VarPowerFlowReferenceType.if_B)
                current_refs.append(VarPowerFlowReferenceType.if_C)
            elif side == "to":
                voltage_refs.append(VarPowerFlowReferenceType.vt_N)
                voltage_refs.append(VarPowerFlowReferenceType.vt_A)
                voltage_refs.append(VarPowerFlowReferenceType.vt_B)
                voltage_refs.append(VarPowerFlowReferenceType.vt_C)

                current_refs.append(VarPowerFlowReferenceType.it_N)
                current_refs.append(VarPowerFlowReferenceType.it_A)
                current_refs.append(VarPowerFlowReferenceType.it_B)
                current_refs.append(VarPowerFlowReferenceType.it_C)
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "EMT branch interface",
                    f"Unsupported EMT branch side '{side}'. No ports were created for this side.",
                )

        reference: VarPowerFlowReferenceType

        for reference in voltage_refs:
            specs.append(ConnectionVarSpec("input", reference, f"{reference.value}_{safe_bus_name}"))

        for reference in current_refs:
            specs.append(ConnectionVarSpec(
                "output",
                reference,
                f"net_conn_{reference.value}_{safe_bus_name}_{self.api_object.name}",
            ))

    def create_library_payload_item(self,
                                    payload: BlockType | BasicBlockTemplateDescriptor | RmsModelTemplate | EmtModelTemplate | FmuTemplate,
                                    x_pos: float,
                                    y_pos: float) -> graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | graph.PairedItem | None:
        """
        Materialize one library payload on the diagram scene.
        """
        if isinstance(payload, BlockType) and payload in self.blocktype2templatebuilder:
            return self.create_item_using_blocktype_wizard(payload, x_pos, y_pos)

        # this ones cannot be included above because they are represented by a different item in the scene
        elif isinstance(payload, BlockType) and payload == BlockType.FROM_GOTO:
            items = self.create_signal_pair_item(x_pos=x_pos, y_pos=y_pos)
            return items[0] if items else None

        elif isinstance(payload, BlockType) and payload == BlockType.SUM:
            return self.create_basic_arithmetic_op_item(BlockType.SUM, x_pos, y_pos)

        elif isinstance(payload, BlockType) and payload == BlockType.PRODUCT:
            return self.create_basic_arithmetic_op_item(BlockType.PRODUCT, x_pos, y_pos)

        elif isinstance(payload, BlockType) and payload == BlockType.GENERIC:
            return self.create_generic_block_item(block_type=payload, x_pos=x_pos, y_pos=y_pos)

        elif isinstance(payload, BlockType):
            return self.create_block_item_from_blocktype(block_type=payload, x_pos=x_pos, y_pos=y_pos)

        elif isinstance(payload, BasicBlockTemplateDescriptor):
            template: EmtModelTemplate = load_basic_block_catalog_template(payload, self.var_factory)
            return self.create_template_block_item(template=template, x_pos=x_pos, y_pos=y_pos)

        elif isinstance(payload, (RmsModelTemplate, EmtModelTemplate, FmuTemplate)):
            return self.create_template_block_item(template=payload, x_pos=x_pos, y_pos=y_pos)
        else:
            return None

    def create_signal_pair_item(self,
                                x_pos: float,
                                y_pos: float) -> tuple[graph.PairedItem, graph.PairedItem] | None:
        """
        Create a signal pair (input + output blocks sharing the same variable).

        :param x_pos: X coordinate for the drop position.
        :param y_pos: Y coordinate for the drop position.
        :return: Tuple of (input_item, output_item) or None on failure.
        """
        count: int = self.block_counters.get(BlockType.FROM_GOTO, 0) + 1
        self.block_counters[BlockType.FROM_GOTO] = count
        item_name: str = str(count)

        blk_in, blk_out = signal_pair(self.var_factory, item_name)

        self.main_block.add(blk_in)
        self.main_block.add(blk_out)

        item_in = graph.PairedItem(editor=self,
                             var_factory=self.var_factory,
                             subsys=blk_in,
                             api_object=self.api_object,
                             mode=self.mode,
                             name=blk_in.name,
                             position_changed_callback=self.build_position_changed_callback(blk_in.uid)
                             )
        item_in.setPos(QtCore.QPointF(x_pos - 50.0, y_pos))
        self.scene.addItem(item_in)
        self.diagram.add_node(
            name=blk_in.name,
            x=x_pos - 50.0,
            y=y_pos,
            tpe="signal_in",
            device_uid=blk_in.uid
        )

        item_out = graph.PairedItem(editor=self,
                              var_factory=self.var_factory,
                              subsys=blk_out,
                              api_object=self.api_object,
                              mode=self.mode,
                              name=blk_out.name,
                              position_changed_callback=self.build_position_changed_callback(blk_out.uid)
                              )
        item_out.setPos(QtCore.QPointF(x_pos + 50.0, y_pos))
        self.scene.addItem(item_out)
        self.diagram.add_node(
            name=blk_out.name,
            x=x_pos + 50.0,
            y=y_pos,
            tpe="signal_out",
            device_uid=blk_out.uid
        )

        item_in.set_paired_item(item_out)
        item_out.set_paired_item(item_in)

        self.mark_unapplied_changes()
        return item_in, item_out

    def remove_connection_item(self, item: graph.ConnectionItem) -> None:
        """
        Remove a connection and restore the destination symbolic input.

        :param item:
        :return:
        """
        source_port: graph.PortItem | graph.BranchingItem = item.source_port
        target_port: graph.PortItem | graph.BranchingItem = item.target_port

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

        if isinstance(source_port, graph.PortItem):
            source_port.update_port_visibility()
        if isinstance(target_port, graph.PortItem):
            target_port.update_port_visibility()

        self.scene.removeItem(item)

        # disconnect variables
        if source_port.subsystem.subsys is not None and target_port.subsystem.subsys is not None:
            dst_var: Var = source_port.subsystem.subsys.out_vars[source_port.index]
            target_var: Var = target_port.subsystem.subsys.in_vars[target_port.index]

            if target_var.network_conn:
                self.var_factory.remove_connection(dst_var, target_var)
                if not isinstance(source_port.subsystem, (graph.RoundBaseArithmeticOpItem, graph.RectBaseArithmeticOpItem)):
                    source_port.subsystem.refresh_port_metadata()
            else:
                self.var_factory.remove_connection(target_var, dst_var)
                if not isinstance(target_port.subsystem, (graph.RoundBaseArithmeticOpItem, graph.RectBaseArithmeticOpItem)):
                    target_port.subsystem.refresh_port_metadata()

    def remove_block_item(self,
                          item: graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | graph.PairedItem) -> None:
        """
        Remove a block and all of its attached connections.

        :param item:
        :return:
        """
        port: graph.PortItem
        conn: graph.ConnectionItem
        connections_to_remove: List[graph.ConnectionItem] = list()
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
            self._remove_connection_interface_for_block(item)

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

    def _remove_connection_interface_for_block(self,
                                               item: graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | graph.PairedItem) -> None:
        """
        Remove the saved top-level connection variable for one editor port block.

        The connection blocks drawn on the canvas are only wrappers around the
        actual root-block interface variables stored in ``main_block``. When the
        user deletes one of those wrappers, the saved interface variable and its
        external-mapping entry must be deleted as well so later EMT assembly sees
        the edited interface exactly as shown in the editor.

        :param item: Scene item being removed.
        :return: None.
        """
        node_data: Any | None = None
        connection_var: Var | None = None

        if item.subsys is None:
            return
        else:
            pass

        node_data = self.diagram.node_data.get(item.subsys.uid, None)

        if node_data is None:
            return
        else:
            pass

        if node_data.tpe == BlockType.INPUT_CONN.name:
            if len(item.subsys.out_vars) > 0:
                connection_var = item.subsys.out_vars[0]
                self._remove_root_connection_var(connection_var=connection_var, direction="input")
            else:
                pass
        elif node_data.tpe == BlockType.OUTPUT_CONN.name:
            if len(item.subsys.in_vars) > 0:
                connection_var = item.subsys.in_vars[0]
                self._remove_root_connection_var(connection_var=connection_var, direction="output")
            else:
                pass
        else:
            pass

    def _remove_root_connection_var(self, connection_var: Var, direction: str) -> None:
        """
        Remove one saved root-block interface variable and its mapping entries.

        :param connection_var: Root-block network-connection variable to remove.
        :param direction: ``input`` for ``main_block.in_vars`` or ``output`` for
            ``main_block.out_vars``.
        :return: None.
        """
        mapping_keys_to_remove: List[VarPowerFlowReferenceType] = list()
        mapping_key: VarPowerFlowReferenceType
        mapped_var: Var | None

        if direction == "input":
            self.main_block.in_vars = [var for var in self.main_block.in_vars if var.uid != connection_var.uid]
        elif direction == "output":
            self.main_block.out_vars = [var for var in self.main_block.out_vars if var.uid != connection_var.uid]
        else:
            raise ValueError(f"Unsupported root connection direction {direction}")

        # Remove all external references that still point to the deleted port so
        # the persisted block interface matches the visible editor interface.
        for mapping_key, mapped_var in self.main_block.external_mapping.items():
            if mapped_var is not None and mapped_var.uid == connection_var.uid:
                mapping_keys_to_remove.append(mapping_key)
            else:
                pass

        for mapping_key in mapping_keys_to_remove:
            del self.main_block.external_mapping[mapping_key]

    def remove_item(self,
                    item: graph.BlockItem | graph.GenericBlockItem | graph.ConnectionItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | graph.PairedItem) -> None:
        """
        Remove a block or connection from scene and model state.

        :param item:
        :return:
        """
        if isinstance(item, graph.ConnectionItem):
            self.remove_connection_item(item)
            self.mark_unapplied_changes()
        elif isinstance(item, (graph.BlockItem, graph.GenericBlockItem, graph.RoundBaseArithmeticOpItem,
                               graph.RectBaseArithmeticOpItem | graph.PairedItem)):
            self.remove_block_item(item)
            self.mark_unapplied_changes()
        else:
            pass

    def add_connection_vars_rms(self):
        """
        Add a block with bus connection variables to connect the device (RMS)
        :return:
        """

        if isinstance(self.api_object, BranchParent):

            # connect bus variables
            # get bus variables for bus from
            if self.api_object.bus_from.is_dc:
                Vf_dc, _, _ = get_bus_rms_algebraic_vars(self.api_object.bus_from.rms_model)
                if Vf_dc is not None:
                    self.main_block.in_vars.append(Vf_dc)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.Vmf: Vf_dc})
                    # add connection variables
                    Pf = self.var_factory.add_var('net_conn_Pf', VarPowerFlowReferenceType.Pf, True)
                    self.main_block.out_vars.append(Pf)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.Pf: Pf})
                else:
                    raise ValueError("Invalid RMS bus model: expected Vdc, None, None")
            else:
                _, Vmf, Vaf = get_bus_rms_algebraic_vars(self.api_object.bus_from.rms_model)

                self.main_block.in_vars.append(Vmf)
                self.main_block.in_vars.append(Vaf)

                self.main_block.external_mapping.update(
                    {VarPowerFlowReferenceType.Vmf: Vmf})
                self.main_block.external_mapping.update(
                    {VarPowerFlowReferenceType.Vaf: Vaf})

                # add connection variables
                Pf = self.var_factory.add_var('net_conn_Pf', VarPowerFlowReferenceType.Pf, True)
                Qf = self.var_factory.add_var('net_conn_Qf', VarPowerFlowReferenceType.Qf, True)

                self.main_block.out_vars.append(Pf)
                self.main_block.out_vars.append(Qf)

                self.main_block.external_mapping.update({VarPowerFlowReferenceType.Pf: Pf})
                self.main_block.external_mapping.update({VarPowerFlowReferenceType.Qf: Qf})

            # get bus variables for bus to
            if self.api_object.bus_to.is_dc:
                Vt_dc, _, _ = get_bus_rms_algebraic_vars(self.api_object.bus_to.rms_model)
                if Vt_dc is not None:
                    self.main_block.in_vars.append(Vt_dc)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.Vt_dc: Vt_dc})
                    # add connection variables
                    Pt = self.var_factory.add_var('net_conn_Pt', VarPowerFlowReferenceType.Pt, True)
                    self.main_block.out_vars.append(Pt)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.Pt: Pt})
                else:
                    raise ValueError("Invalid RMS bus model: expected Vdc, None, None")

            else:
                _, Vmt, Vat = get_bus_rms_algebraic_vars(self.api_object.bus_to.rms_model)

                self.main_block.in_vars.append(Vmt)
                self.main_block.in_vars.append(Vat)

                self.main_block.external_mapping.update(
                    {VarPowerFlowReferenceType.Vmt: Vmt})
                self.main_block.external_mapping.update(
                    {VarPowerFlowReferenceType.Vat: Vat})
                # add connection variables
                Pt = self.var_factory.add_var('net_conn_Pt', VarPowerFlowReferenceType.Pt, True)
                Qt = self.var_factory.add_var('net_conn_Qt', VarPowerFlowReferenceType.Qt, True)

                self.main_block.out_vars.append(Pt)
                self.main_block.out_vars.append(Qt)

                self.main_block.external_mapping.update({VarPowerFlowReferenceType.Pt: Pt})
                self.main_block.external_mapping.update({VarPowerFlowReferenceType.Qt: Qt})

        elif isinstance(self.api_object, InjectionParent):

            # connect bus variables

            if self.api_object.bus.is_dc:
                Vdc, _, _ = get_bus_rms_algebraic_vars(self.api_object.bus.rms_model)
                if Vdc is not None:
                    self.main_block.in_vars.append(Vdc)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.Vdc: Vdc})

                    # add connection variables
                    P = self.var_factory.add_var('net_conn_P', VarPowerFlowReferenceType.P, True)

                    self.main_block.out_vars.append(P)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.P: P})
            else:
                _, Vm, Va = get_bus_rms_algebraic_vars(self.api_object.bus.rms_model)
                self.main_block.in_vars.append(Vm)
                self.main_block.in_vars.append(Va)

                self.main_block.external_mapping.update(
                    {VarPowerFlowReferenceType.Vm: Vm})
                self.main_block.external_mapping.update(
                    {VarPowerFlowReferenceType.Va: Va})

                # add connection variables
                P = self.var_factory.add_var('net_conn_P', VarPowerFlowReferenceType.P, True)
                Q = self.var_factory.add_var('net_conn_Q', VarPowerFlowReferenceType.Q, True)

                self.main_block.out_vars.append(P)
                self.main_block.out_vars.append(Q)

                self.main_block.external_mapping.update({VarPowerFlowReferenceType.P: P})
                self.main_block.external_mapping.update({VarPowerFlowReferenceType.Q: Q})

    def add_connection_vars_emt(self):
        """
        Add a block with bus connection variables to connect the device (EMT)
        :return:
        """

        if isinstance(self.api_object, BranchParent):

            # connect bus variables

            # get bus variables for bus from
            if self.api_object.bus_from.is_dc:
                Vf_dc, _, _, _ = get_bus_emt_algebraic_vars(self.api_object.bus_from.emt_model)

                if Vf_dc is not None:
                    self.main_block.in_vars.append(Vf_dc)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.Vdc: Vf_dc})
                    # add connection variables (currents)
                    If_dc = self.var_factory.add_var('net_conn_If_dc', VarPowerFlowReferenceType.If_dc, True)
                    self.main_block.out_vars.append(If_dc)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.If_dc: If_dc})
                else:
                    raise ValueError("Invalid EMT bus model: expected Vdc, None, None, None")
            else:
                vf_N, vf_A, vf_B, vf_C = get_bus_emt_algebraic_vars(self.api_object.bus_from.emt_model)

                if vf_N is not None:
                    self.main_block.in_vars.append(vf_N)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.vf_N: vf_N})
                    # add connection variables (currents)
                    if_N = self.var_factory.add_var('net_conn_if_N', VarPowerFlowReferenceType.if_N, True)
                    self.main_block.out_vars.append(if_N)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.if_N: if_N})
                if vf_A is not None:
                    self.main_block.in_vars.append(vf_A)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.vf_A: vf_A})
                    # add connection variables (currents)
                    if_A = self.var_factory.add_var('net_conn_if_A', VarPowerFlowReferenceType.if_A, True)
                    self.main_block.out_vars.append(if_A)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.if_A: if_A})
                if vf_B is not None:
                    self.main_block.in_vars.append(vf_B)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.vf_B: vf_B})
                    # add connection variables (currents)
                    if_B = self.var_factory.add_var('net_conn_if_B', VarPowerFlowReferenceType.if_B, True)
                    self.main_block.out_vars.append(if_B)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.if_B: if_B})
                if vf_C is not None:
                    self.main_block.in_vars.append(vf_C)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.vf_C: vf_C})
                    # add connection variables (currents)
                    if_C = self.var_factory.add_var('net_conn_if_C', VarPowerFlowReferenceType.if_C, True)
                    self.main_block.out_vars.append(if_C)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.if_C: if_C})


            # get bus variables for bus to
            if self.api_object.bus_to.is_dc:
                Vt_dc, _, _, _ = get_bus_emt_algebraic_vars(self.api_object.bus_to.emt_model)

                if Vt_dc is not None:
                    self.main_block.in_vars.append(Vt_dc)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.Vt_dc: Vt_dc})
                    # add connection variables (currents)
                    It_dc = self.var_factory.add_var('net_conn_It_dc', VarPowerFlowReferenceType.It_dc, True)
                    self.main_block.out_vars.append(It_dc)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.It_dc: It_dc})
                else:
                    raise ValueError("Invalid EMT bus model: expected Vdc, None, None, None")

            else:
                vt_N, vt_A, vt_B, vt_C = get_bus_emt_algebraic_vars(self.api_object.bus_to.emt_model)

                if vt_N is not None:
                    self.main_block.in_vars.append(vt_N)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.vt_N: vt_N})
                    # add connection variables (currents)
                    it_N = self.var_factory.add_var('net_conn_it_N', VarPowerFlowReferenceType.it_N, True)
                    self.main_block.out_vars.append(it_N)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.it_N: it_N})
                if vt_A is not None:
                    self.main_block.in_vars.append(vt_A)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.vt_A: vt_A})
                    # add connection variables (currents)
                    it_A = self.var_factory.add_var('net_conn_it_A', VarPowerFlowReferenceType.it_A, True)
                    self.main_block.out_vars.append(it_A)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.it_A: it_A})
                if vt_B is not None:
                    self.main_block.in_vars.append(vt_B)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.vt_B: vt_B})
                    # add connection variables (currents)
                    it_B = self.var_factory.add_var('net_conn_it_B', VarPowerFlowReferenceType.it_B, True)
                    self.main_block.out_vars.append(it_B)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.it_B: it_B})
                if vt_C is not None:
                    self.main_block.in_vars.append(vt_C)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.vt_C: vt_C})
                    # add connection variables (currents)
                    it_C = self.var_factory.add_var('net_conn_it_C', VarPowerFlowReferenceType.it_C, True)
                    self.main_block.out_vars.append(it_C)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.it_C: it_C})



        elif isinstance(self.api_object, InjectionParent):

            # connect bus variables

            if self.api_object.bus.is_dc:
                Vdc, _, _, _ = get_bus_emt_algebraic_vars(self.api_object.bus.emt_model)

                if Vdc is not None:
                    self.main_block.in_vars.append(Vdc)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.Vdc: Vdc})
                    # add connection variables (currents)
                    Idc = self.var_factory.add_var('net_conn_Idc', VarPowerFlowReferenceType.Idc, True)
                    self.main_block.out_vars.append(Idc)
                    self.main_block.external_mapping.update({VarPowerFlowReferenceType.Idc: Idc})
                else:
                    raise ValueError("Invalid EMT bus model: expected Vdc, None, None, None")
            else:
                v_N, v_A, v_B, v_C = get_bus_emt_algebraic_vars(self.api_object.bus.emt_model)

                if v_N is not None:
                    self.main_block.in_vars.append(v_N)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.v_N: v_N})
                    # add connection variables
                    i_N = self.var_factory.add_var('net_conn_i_N', VarPowerFlowReferenceType.i_N, True)
                    self.main_block.out_vars.append(i_N)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.i_N: i_N})
                if v_A is not None:
                    self.main_block.in_vars.append(v_A)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.v_A: v_A})
                    # add connection variables
                    i_A = self.var_factory.add_var('net_conn_i_A', VarPowerFlowReferenceType.i_A, True)
                    self.main_block.out_vars.append(i_A)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.i_A: i_A})
                if v_B is not None:
                    self.main_block.in_vars.append(v_B)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.v_B: v_B})
                    # add connection variables
                    i_B = self.var_factory.add_var('net_conn_i_B', VarPowerFlowReferenceType.i_B, True)
                    self.main_block.out_vars.append(i_B)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.i_B: i_B})
                if v_C is not None:
                    self.main_block.in_vars.append(v_C)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.v_C: v_C})
                    # add connection variables
                    i_C = self.var_factory.add_var('net_conn_i_C', VarPowerFlowReferenceType.i_C, True)
                    self.main_block.out_vars.append(i_C)
                    self.main_block.external_mapping.update(
                        {VarPowerFlowReferenceType.i_C: i_C})


    def add_connection_vars(self) -> None:
        """
        Add the connection variables required to couple the edited device with the grid.

        :return:
        """
        # specs: List[ConnectionVarSpec]

        if self.mode == DynamicSimulationMode.RMS:
            self.add_connection_vars_rms()
        elif self.mode == DynamicSimulationMode.EMT:
            self.add_connection_vars_emt()


        else:
            raise ValueError(f"Unsupported dynamic editor mode {self.mode}")

    def _compact_initial_layout(self) -> QtCore.QRectF | None:
        interface_items: list[graph.ProtectedConnectionBlockItem] = [
            item for item in self.scene.items()
            if isinstance(item, graph.ProtectedConnectionBlockItem)
        ]

        if not interface_items:
            return None

        bounding_rect = QtCore.QRectF()
        for item in interface_items:
            br = item.sceneBoundingRect()
            bounding_rect = br if bounding_rect.isNull() else bounding_rect.united(br)

        center = bounding_rect.center()

        for item in interface_items:
            offset = item.pos() - center
            item.setPos(center + offset * graph.EditorGraphicsCommonFeatures.INITIAL_LAYOUT_SCALE)

        for node in self.diagram.node_data.values():
            if node.tpe in {BlockType.INPUT_CONN.name, BlockType.OUTPUT_CONN.name}:
                for item in interface_items:
                    if item.subsys.uid == node.device_uid:
                        node.x = item.pos().x()
                        node.y = item.pos().y()
                        break

        new_br = QtCore.QRectF()
        for item in interface_items:
            br = item.sceneBoundingRect()
            new_br = br if new_br.isNull() else new_br.united(br)

        return new_br.adjusted(-graph.EditorGraphicsCommonFeatures.LAYOUT_MARGIN, -graph.EditorGraphicsCommonFeatures.LAYOUT_MARGIN,
                               graph.EditorGraphicsCommonFeatures.LAYOUT_MARGIN, graph.EditorGraphicsCommonFeatures.LAYOUT_MARGIN)

    def add_connection_blocks(self, blocks_list: List[Block] | None = None):
        """
        for every input and output var in the main block of the editor we build a block item to connect connection variables

        :return:
        :rtype:
        """

        for i, invar in enumerate(self.main_block.in_vars):
            self.create_connection_block(invar, BlockType.INPUT_CONN, blocks_list)

        for i, outvar in enumerate(self.main_block.out_vars):

            self.create_connection_block(outvar, BlockType.OUTPUT_CONN, blocks_list)





    def add_connection_items(self, blocks_list: List[graph.BlockItem] | None = None):
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
            self.create_connection_block_item(invar, BlockType.INPUT_CONN, MARGIN_X, y_pos, blocks_list)

        for i, outvar in enumerate(self.main_block.out_vars):
            y_pos = MARGIN_Y + output_spacing * (i + 1) - BLOCK_HEIGHT / 2
            x_pos: float = SCENE_WIDTH - MARGIN_X - BLOCK_HEIGHT
            self.create_connection_block_item(outvar, BlockType.OUTPUT_CONN, x_pos, y_pos, blocks_list)

        self.scene.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        fit_rect = self._compact_initial_layout()
        if fit_rect is not None:
            self.view.fitInView(fit_rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
            self.view.scale(graph.EditorGraphicsCommonFeatures.INITIAL_VIEW_SCALE, graph.EditorGraphicsCommonFeatures.INITIAL_VIEW_SCALE)
        else:
            self.view.fitInView(self.scene.sceneRect(), QtCore.Qt.AspectRatioMode.KeepAspectRatio)


    def _get_safe_bus_name(self, bus: Any) -> str:
        """
        Build a safe bus-name suffix for editor-visible connection variables.

        :param bus: Bus API object.
        :return: Bus name with spaces replaced by underscores.
        """
        return bus.name.replace(" ", "_")

    def _get_current_root_interface_refs(self) -> set[VarPowerFlowReferenceType]:
        """
        Return the references still present in the saved root interface.

        The root block interface is the authoritative result of the editor
        session. When the user removes a visible connection variable, the
        corresponding variable disappears from ``main_block.in_vars`` or
        ``main_block.out_vars`` and should not be recreated silently later.

        :return: Set of power-flow reference types still exposed by the block.
        """
        refs: set[VarPowerFlowReferenceType] = set()
        var: Var
        mapping_ref: VarPowerFlowReferenceType
        mapped_var: Var | None

        # Collect references from explicit root inputs.
        for var in self.main_block.in_vars:
            if var.ref is not None:
                refs.add(var.ref)
            else:
                pass

        # Collect references from explicit root outputs.
        for var in self.main_block.out_vars:
            if var.ref is not None:
                refs.add(var.ref)
            else:
                pass

        # Collect references from the external mapping because some variables
        # may be kept through mapping updates after connection edits.
        for mapping_ref, mapped_var in self.main_block.external_mapping.items():
            if mapped_var is not None:
                refs.add(mapping_ref)
            else:
                pass

        return refs

    def _is_interface_block_port_connected(self, item: graph.ProtectedConnectionBlockItem) -> bool:
        """
        Return whether one protected editor interface block owns a live wire.

        The protected interface blocks are always present in EMT mode, so the
        algorithm cannot use block existence anymore to infer whether one phase
        participates in the model. The only valid signal is whether the block's
        single public port currently owns at least one connection item.

        :param item: Protected connection-interface block.
        :return: ``True`` when the visible interface port is wired.
        """
        node_data: Any | None = None
        is_connected: bool = False
        port_item: graph.PortItem | None = None

        if item.subsys is not None:
            node_data = self.diagram.node_data.get(item.subsys.uid, None)
        else:
            node_data = None

        if node_data is not None:
            if node_data.tpe == BlockType.INPUT_CONN.name:
                if len(item.outputs) > 0:
                    port_item = item.outputs[0]
                else:
                    port_item = None
            else:
                if node_data.tpe == BlockType.OUTPUT_CONN.name:
                    if len(item.inputs) > 0:
                        port_item = item.inputs[0]
                    else:
                        port_item = None
                else:
                    port_item = None
        else:
            port_item = None

        if port_item is not None:
            if port_item.connections is not None:
                if len(port_item.connections) > 0:
                    is_connected = True
                else:
                    is_connected = False
            else:
                is_connected = False
        else:
            is_connected = False

        return is_connected

    def _get_connected_root_interface_refs(self) -> set[VarPowerFlowReferenceType]:
        """
        Return the root interface references backed by live editor connections.

        EMT interface blocks are now protected from deletion, so all candidate
        phase blocks always exist on the canvas. To rebuild the EMT bus shells
        correctly, the algorithm must inspect which interface ports are actually
        wired into the model and use only those references as active phases.

        :return: Connected root-interface references.
        """
        refs: set[VarPowerFlowReferenceType] = set()
        scene_item: QGraphicsItem
        protected_item: graph.ProtectedConnectionBlockItem
        node_data: Any | None = None
        reference_var: Var | None = None

        for scene_item in self.scene.items():
            if isinstance(scene_item, graph.ProtectedConnectionBlockItem):
                protected_item = scene_item
                if protected_item.subsys is not None:
                    node_data = self.diagram.node_data.get(protected_item.subsys.uid, None)
                else:
                    node_data = None

                if node_data is not None:
                    if self._is_interface_block_port_connected(protected_item):
                        if node_data.tpe == BlockType.INPUT_CONN.name:
                            if len(protected_item.subsys.out_vars) > 0:
                                reference_var = protected_item.subsys.out_vars[0]
                            else:
                                reference_var = None
                        else:
                            if node_data.tpe == BlockType.OUTPUT_CONN.name:
                                if len(protected_item.subsys.in_vars) > 0:
                                    reference_var = protected_item.subsys.in_vars[0]
                                else:
                                    reference_var = None
                            else:
                                reference_var = None

                        if reference_var is not None:
                            if reference_var.ref is not None:
                                refs.add(reference_var.ref)
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass
                else:
                    pass
            else:
                pass

        return refs



    def _remove_shared_branch_emt_root_refs(self) -> None:
        """
        Remove shared AC EMT root refs from one branch root contract.

        Branch EMT root contracts must expose side-specific references such as
        ``vf_A`` and ``vt_A``. Shared single-bus AC refs such as ``v_A`` are not
        valid on a two-terminal branch root contract and must be removed before
        the saved model is committed and attached to the bus shells.

        :return: None.
        """
        shared_branch_refs: set[VarPowerFlowReferenceType] = set([
            VarPowerFlowReferenceType.v_N,
            VarPowerFlowReferenceType.v_A,
            VarPowerFlowReferenceType.v_B,
            VarPowerFlowReferenceType.v_C,
            VarPowerFlowReferenceType.i_N,
            VarPowerFlowReferenceType.i_A,
            VarPowerFlowReferenceType.i_B,
            VarPowerFlowReferenceType.i_C,
        ])
        kept_in_vars: list[Var] = list()
        kept_out_vars: list[Var] = list()
        mapping_keys_to_remove: list[VarPowerFlowReferenceType] = list()
        var: Var
        mapping_key: VarPowerFlowReferenceType
        mapped_var: Var | None

        if isinstance(self.api_object, BranchParent):
            pass
        else:
            return

        # Branch root contracts may still carry legacy shared AC refs from old
        # templates or previously saved data. Keep only side-specific branch refs
        # in the root IO contract so later EMT validation sees the correct domain.
        for var in self.main_block.in_vars:
            if isinstance(var.ref, VarPowerFlowReferenceType) and var.ref in shared_branch_refs:
                pass
            else:
                kept_in_vars.append(var)

        for var in self.main_block.out_vars:
            if isinstance(var.ref, VarPowerFlowReferenceType) and var.ref in shared_branch_refs:
                pass
            else:
                kept_out_vars.append(var)

        for mapping_key, mapped_var in self.main_block.external_mapping.items():
            if mapping_key in shared_branch_refs:
                mapping_keys_to_remove.append(mapping_key)
            else:
                pass

        self.main_block.in_vars = kept_in_vars
        self.main_block.out_vars = kept_out_vars

        for mapping_key in mapping_keys_to_remove:
            if mapping_key in self.main_block.external_mapping:
                del self.main_block.external_mapping[mapping_key]
            else:
                pass

    def _is_emt_interface_reference(self, reference: VarPowerFlowReferenceType | None) -> bool:
        """
        Return whether one reference belongs to the EMT AC editor interface.

        The pruning step must only touch EMT phase-interface variables. Other
        references, such as RMS quantities, DC quantities, parameters, or user
        internals, must remain untouched when the editor applies the model.

        :param reference: Reference carried by one root-interface variable.
        :return: ``True`` when the reference is one EMT AC interface key.
        """
        emt_interface_refs: set[VarPowerFlowReferenceType] = set()
        is_interface_reference: bool = False

        emt_interface_refs.add(VarPowerFlowReferenceType.v_N)
        emt_interface_refs.add(VarPowerFlowReferenceType.v_A)
        emt_interface_refs.add(VarPowerFlowReferenceType.v_B)
        emt_interface_refs.add(VarPowerFlowReferenceType.v_C)
        emt_interface_refs.add(VarPowerFlowReferenceType.i_N)
        emt_interface_refs.add(VarPowerFlowReferenceType.i_A)
        emt_interface_refs.add(VarPowerFlowReferenceType.i_B)
        emt_interface_refs.add(VarPowerFlowReferenceType.i_C)
        emt_interface_refs.add(VarPowerFlowReferenceType.vf_N)
        emt_interface_refs.add(VarPowerFlowReferenceType.vf_A)
        emt_interface_refs.add(VarPowerFlowReferenceType.vf_B)
        emt_interface_refs.add(VarPowerFlowReferenceType.vf_C)
        emt_interface_refs.add(VarPowerFlowReferenceType.if_N)
        emt_interface_refs.add(VarPowerFlowReferenceType.if_A)
        emt_interface_refs.add(VarPowerFlowReferenceType.if_B)
        emt_interface_refs.add(VarPowerFlowReferenceType.if_C)
        emt_interface_refs.add(VarPowerFlowReferenceType.vt_N)
        emt_interface_refs.add(VarPowerFlowReferenceType.vt_A)
        emt_interface_refs.add(VarPowerFlowReferenceType.vt_B)
        emt_interface_refs.add(VarPowerFlowReferenceType.vt_C)
        emt_interface_refs.add(VarPowerFlowReferenceType.it_N)
        emt_interface_refs.add(VarPowerFlowReferenceType.it_A)
        emt_interface_refs.add(VarPowerFlowReferenceType.it_B)
        emt_interface_refs.add(VarPowerFlowReferenceType.it_C)

        if reference is not None:
            if reference in emt_interface_refs:
                is_interface_reference = True
            else:
                is_interface_reference = False
        else:
            is_interface_reference = False

        return is_interface_reference

    def _build_current_emt_injection_bus_mask(self) -> list[bool]:
        """
        Build the EMT injection bus mask from the current root interface refs.

        The editor root interface is now the only source of truth for which
        EMT phase ports remain part of the device contract. Whether those ports
        are graphically wired or not is no longer a save-time validity concern.

        :return: Current EMT mask.
        """
        refs: set[VarPowerFlowReferenceType] = self._get_current_root_interface_refs()
        return build_emt_injection_bus_mask_from_refs(refs=refs)

    def _build_current_emt_branch_bus_mask(self, side: str) -> list[bool]:
        """
        Build one EMT branch-side mask from the current root interface refs.

        The root interface determines which side-phase ports remain part of the
        saved EMT contract. Graphical wiring is not validated here.

        :param side: Branch side identifier. Expected values are ``from`` and ``to``.
        :return: Current EMT mask for the requested side.
        """
        refs: set[VarPowerFlowReferenceType] = self._get_current_root_interface_refs()
        return build_emt_branch_bus_mask_from_refs(refs=refs, side=side)

    def _get_requested_emt_bus_masks_from_current_interface(self) -> tuple[
        bool, list[bool] | None, list[bool] | None, list[bool] | None]:
        """
        Build the requested EMT bus masks from the currently connected editor ports.

        The editor path is the source of truth for which EMT phases the user
        kept connected. Once these masks are known, the actual bus-shell
        creation, expansion, reconnection, and registry update are delegated to
        the shared engine-side attachment flow.

        :return: Tuple ``(success, bus_mask, from_mask, to_mask)``.
        """
        success: bool = True
        bus_mask: list[bool] | None = None
        from_mask: list[bool] | None = None
        to_mask: list[bool] | None = None

        if isinstance(self.api_object, InjectionParent):
            if self.api_object.bus.is_dc:
                bus_mask = list([False, False, False, False])
            else:
                bus_mask = self._build_current_emt_injection_bus_mask()
                success = True
        else:
            if isinstance(self.api_object, BranchParent):
                if self.api_object.bus_from.is_dc:
                    from_mask = list([False, False, False, False])
                else:
                    from_mask = self._build_current_emt_branch_bus_mask(side="from")
                    success = True

                if self.api_object.bus_to.is_dc:
                    to_mask = list([False, False, False, False])
                else:
                    to_mask = self._build_current_emt_branch_bus_mask(side="to")
                    success = True
            else:
                success = True

        return success, bus_mask, from_mask, to_mask

    def _materialize_missing_non_interface_diagram_nodes(self) -> None:
        """
        Add default diagram nodes for non-interface blocks missing from the diagram.

        Template-assigned models can exist as symbolic children without any saved
        diagram node positions. The editor must create those missing diagram
        nodes so the symbolic blocks become visible on the canvas.

        :return: None.
        """
        existing_node_uids: set[int] = set(self.diagram.node_data.keys())
        child_block: Block

        for child_block in self.main_block.children:
            if child_block.uid in existing_node_uids:
                pass
            elif (len(child_block.in_vars) == 1
                  and len(child_block.out_vars) == 0
                  and child_block.name.startswith("net_conn_")):
                # Defensive guard for editor-generated output interface wrappers.
                pass
            elif (len(child_block.in_vars) == 0
                  and len(child_block.out_vars) == 1
                  and child_block.name.startswith(("v_", "Vdc_"))):
                # Defensive guard for editor-generated input interface wrappers.
                pass
            else:
                self.generate_block_item_for_block(child_block, x_pos=0, y_pos=0)  # TODO: Fill coordinates from layout

    def _rebuild_missing_non_interface_connections(self) -> None:
        """
        Recreate inferred symbolic wires after auto-materializing missing blocks.

        The no-diagram template-open path must rebuild the visible connection set
        from the symbolic graph once the missing block nodes have been placed.

        :return: None.
        """
        items_list: list[graph.GenericBlockItem] = self._collect_non_interface_scene_items()

        if len(items_list) > 0:
            self.connect_items(items_list)
            self._rebuild_editor_interface_graphical_connections(items_list)
        else:
            pass

    def _collect_non_interface_scene_items(self) -> list[graph.GenericBlockItem]:
        """
        Return the visible non-interface generic block items in the scene.

        The reconnect pass operates only on real model blocks. The protected
        editor interface wrappers are intentionally excluded from this list.

        :return: Generic block items excluding editor interface wrappers.
        """
        items_list: list[graph.GenericBlockItem] = list()
        scene_item: QGraphicsItem
        node_data: Any | None

        for scene_item in self.scene.items():
            if isinstance(scene_item, graph.GenericBlockItem):
                if scene_item.subsys is not None:
                    node_data: Any | None = self.diagram.node_data.get(scene_item.subsys.uid, None)
                else:
                    node_data = None

                if node_data is None:
                    pass
                elif node_data.tpe in {BlockType.INPUT_CONN.name, BlockType.OUTPUT_CONN.name}:
                    pass
                else:
                    items_list.append(scene_item)
            else:
                pass

        return items_list

    def _rebuild_visible_symbolic_connections(self, items_list: List[graph.GenericBlockItem]) -> None:
        """
        Recreate missing symbolic wires between all visible non-interface blocks.

        The saved diagram may miss some graphical arrows even when the symbolic
        block graph still carries enough metadata to infer them. Re-run the
        visible block-pair connection discovery so the scene reflects the actual
        symbolic connectivity.

        :param items_list: Visible non-interface block items.
        :return: None.
        """
        item_source: graph.GenericBlockItem
        item_target: graph.GenericBlockItem
        pairs: list[tuple[Var, Var]]
        power_flow_pairs: list[tuple[Var, Var]]

        for item_source in items_list:
            if item_source.subsys is None:
                pass
            else:
                for item_target in items_list:
                    if item_target.subsys is None:
                        pass
                    else:
                        if item_source.subsys.uid == item_target.subsys.uid:
                            pass
                        else:
                            pairs, power_flow_pairs = find_connections(item_source.subsys, item_target.subsys)
                            self._create_missing_connection_items(item_source, item_target, pairs)
                            self._create_missing_connection_items(item_source, item_target, power_flow_pairs)

    def _rebuild_editor_interface_graphical_connections(self, items_list: List[graph.GenericBlockItem]) -> None:
        """
        Recreate visible wires between editor interface blocks and visible model blocks.

        EMT template-open sessions can rebuild the full editor interface without a
        saved diagram that already contains those graphical wires. The root block
        still carries the semantic ``ref`` tags, so reconnect the visible editor
        interface to every visible block port that exposes the same EMT root ref.

        :param items_list: Visible non-interface block items.
        :return: None.
        """
        interface_inputs_by_ref: Dict[VarPowerFlowReferenceType, graph.ProtectedConnectionBlockItem] = dict()
        interface_outputs_by_ref: Dict[VarPowerFlowReferenceType, graph.ProtectedConnectionBlockItem] = dict()
        scene_item: QGraphicsItem
        node_data: Any | None
        reference_var: Var | None
        block_item: graph.GenericBlockItem
        input_index: int
        output_index: int
        input_var: Var
        output_var: Var
        protected_item: graph.ProtectedConnectionBlockItem | None

        for scene_item in self.scene.items():
            if isinstance(scene_item, graph.ProtectedConnectionBlockItem) and scene_item.subsys is not None:
                node_data = self.diagram.node_data.get(scene_item.subsys.uid, None)

                if node_data is None:
                    pass
                elif node_data.tpe == BlockType.INPUT_CONN.name:
                    if len(scene_item.subsys.out_vars) > 0:
                        reference_var = scene_item.subsys.out_vars[0]
                    else:
                        reference_var = None

                    if isinstance(reference_var, Var) and isinstance(reference_var.ref, VarPowerFlowReferenceType):
                        interface_inputs_by_ref[reference_var.ref] = scene_item
                    else:
                        pass
                elif node_data.tpe == BlockType.OUTPUT_CONN.name:
                    if len(scene_item.subsys.in_vars) > 0:
                        reference_var = scene_item.subsys.in_vars[0]
                    else:
                        reference_var = None

                    if isinstance(reference_var, Var) and isinstance(reference_var.ref, VarPowerFlowReferenceType):
                        interface_outputs_by_ref[reference_var.ref] = scene_item
                    else:
                        pass
                else:
                    pass
            else:
                pass

        for block_item in items_list:
            if block_item.subsys is None:
                pass
            else:
                for input_index, input_var in enumerate(block_item.subsys.in_vars):
                    if isinstance(input_var.ref, VarPowerFlowReferenceType):
                        protected_item = self._get_editor_interface_input_item_for_ref(
                            interface_inputs_by_ref=interface_inputs_by_ref,
                            model_ref=input_var.ref,
                        )
                        if protected_item is not None and len(protected_item.outputs) > 0 and input_index < len(
                                block_item.inputs):
                            if self._connection_exists_between_ports(protected_item.outputs[0],
                                                                     block_item.inputs[input_index]):
                                pass
                            else:
                                connection_item: graph.ConnectionItem = graph.ConnectionItem(
                                    source_port=protected_item.outputs[0],
                                    target_port=block_item.inputs[input_index],
                                    diagram=self.diagram,
                                    editor=self,
                                    route_style="RETICULAR",
                                    locked=False,
                                )
                                connection_item.recolour()
                                self.scene.addItem(connection_item)
                        else:
                            pass
                    else:
                        pass

                for output_index, output_var in enumerate(block_item.subsys.out_vars):
                    if isinstance(output_var.ref, VarPowerFlowReferenceType):
                        protected_item = self._get_editor_interface_output_item_for_ref(
                            interface_outputs_by_ref=interface_outputs_by_ref,
                            model_ref=output_var.ref,
                        )
                        if protected_item is not None and len(protected_item.inputs) > 0 and output_index < len(
                                block_item.outputs):
                            if self._connection_exists_between_ports(block_item.outputs[output_index],
                                                                     protected_item.inputs[0]):
                                pass
                            else:
                                connection_item = graph.ConnectionItem(
                                    source_port=block_item.outputs[output_index],
                                    target_port=protected_item.inputs[0],
                                    diagram=self.diagram,
                                    editor=self,
                                    route_style="RETICULAR",
                                    locked=False,
                                )
                                connection_item.recolour()
                                self.scene.addItem(connection_item)
                        else:
                            pass
                    else:
                        pass

    def _get_editor_interface_input_item_for_ref(self,
                                                 interface_inputs_by_ref: Dict[
                                                     VarPowerFlowReferenceType, graph.ProtectedConnectionBlockItem],
                                                 model_ref: VarPowerFlowReferenceType) -> graph.ProtectedConnectionBlockItem | None:
        """
        Resolve one editor input wrapper for one model-side EMT input reference.

        :param interface_inputs_by_ref: Editor input wrappers keyed by editor EMT ref.
        :param model_ref: Model-side EMT input ref.
        :return: Matching editor input wrapper or ``None``.
        """
        if isinstance(self.api_object, BranchParent) and self.api_object.device_type == DeviceType.VscDevice:
            ac_side_is_from: bool = False
            ac_side_is_to: bool = False

            if self.api_object.bus_from.is_dc:
                ac_side_is_to = True
            else:
                if self.api_object.bus_to.is_dc:
                    ac_side_is_from = True
                else:
                    ac_side_is_from = True

            if model_ref == VarPowerFlowReferenceType.v_N:
                if ac_side_is_to:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vt_N, None)
                elif ac_side_is_from:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vf_N, None)
                else:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vf_N, None)
            elif model_ref == VarPowerFlowReferenceType.v_A:
                if ac_side_is_to:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vt_A, None)
                elif ac_side_is_from:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vf_A, None)
                else:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vf_A, None)
            elif model_ref == VarPowerFlowReferenceType.v_B:
                if ac_side_is_to:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vt_B, None)
                elif ac_side_is_from:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vf_B, None)
                else:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vf_B, None)
            elif model_ref == VarPowerFlowReferenceType.v_C:
                if ac_side_is_to:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vt_C, None)
                elif ac_side_is_from:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vf_C, None)
                else:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.vf_C, None)
            elif model_ref == VarPowerFlowReferenceType.Vdc:
                if self.api_object.bus_from.is_dc:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.Vf_dc, None)
                elif self.api_object.bus_to.is_dc:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.Vt_dc, None)
                else:
                    return interface_inputs_by_ref.get(VarPowerFlowReferenceType.Vdc, None)
            else:
                return interface_inputs_by_ref.get(model_ref, None)
        else:
            return interface_inputs_by_ref.get(model_ref, None)

    def _get_editor_interface_output_item_for_ref(self,
                                                  interface_outputs_by_ref: Dict[
                                                      VarPowerFlowReferenceType, graph.ProtectedConnectionBlockItem],
                                                  model_ref: VarPowerFlowReferenceType) -> graph.ProtectedConnectionBlockItem | None:
        """
        Resolve one editor output wrapper for one model-side EMT output reference.

        :param interface_outputs_by_ref: Editor output wrappers keyed by editor EMT ref.
        :param model_ref: Model-side EMT output ref.
        :return: Matching editor output wrapper or ``None``.
        """
        if isinstance(self.api_object, BranchParent) and self.api_object.device_type == DeviceType.VscDevice:
            ac_side_is_from: bool = False
            ac_side_is_to: bool = False

            if self.api_object.bus_from.is_dc:
                ac_side_is_to = True
            else:
                if self.api_object.bus_to.is_dc:
                    ac_side_is_from = True
                else:
                    ac_side_is_from = True

            if model_ref == VarPowerFlowReferenceType.i_N:
                if ac_side_is_to:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.it_N, None)
                elif ac_side_is_from:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.if_N, None)
                else:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.if_N, None)
            elif model_ref == VarPowerFlowReferenceType.i_A:
                if ac_side_is_to:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.it_A, None)
                elif ac_side_is_from:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.if_A, None)
                else:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.if_A, None)
            elif model_ref == VarPowerFlowReferenceType.i_B:
                if ac_side_is_to:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.it_B, None)
                elif ac_side_is_from:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.if_B, None)
                else:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.if_B, None)
            elif model_ref == VarPowerFlowReferenceType.i_C:
                if ac_side_is_to:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.it_C, None)
                elif ac_side_is_from:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.if_C, None)
                else:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.if_C, None)
            elif model_ref == VarPowerFlowReferenceType.Idc:
                if self.api_object.bus_from.is_dc:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.If_dc, None)
                elif self.api_object.bus_to.is_dc:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.It_dc, None)
                else:
                    return interface_outputs_by_ref.get(VarPowerFlowReferenceType.Idc, None)
            else:
                return interface_outputs_by_ref.get(model_ref, None)
        else:
            return interface_outputs_by_ref.get(model_ref, None)

    def _create_missing_connection_items(self,
                                         item_source: graph.GenericBlockItem,
                                         item_dest: graph.GenericBlockItem,
                                         pairs: List[tuple[Var, Var]]) -> None:
        """
        Create only the currently missing connection items for one block pair.

        :param item_source: Source block item.
        :param item_dest: Destination block item.
        :param pairs: Candidate variable pairs.
        :return: None.
        """
        source_var: Var
        target_var: Var
        source_port: graph.PortItem | None
        target_port: graph.PortItem | None
        port: graph.PortItem

        for source_var, target_var in pairs:
            source_port = self._find_output_port_for_var(item_source=item_source, source_var=source_var)
            target_port = self._find_input_port_for_var(item_dest=item_dest, target_var=target_var)

            if source_port is not None and target_port is not None:
                if self._connection_exists_between_ports(source_port, target_port):
                    pass
                else:
                    connection = graph.ConnectionItem(
                        source_port=source_port,
                        target_port=target_port,
                        diagram=self.diagram,
                        editor=self,
                        route_style="RETICULAR",
                        locked=False,
                    )
                    connection.recolour()
                    self.scene.addItem(connection)
            else:
                pass

    @staticmethod
    def _vars_match_for_visible_connection(left_var: Var | None, right_var: Var | None) -> bool:
        """
        Return whether two visible port vars should be treated as the same wire.

        :param left_var: First visible port variable.
        :param right_var: Second visible port variable.
        :return: ``True`` when the ports represent the same symbolic connection.
        """
        if left_var is None or right_var is None:
            return False
        elif left_var.uid == right_var.uid:
            return True
        elif left_var.shared_ref is not None and left_var.shared_ref == right_var.shared_ref:
            return True
        elif left_var.ref is not None and left_var.ref == right_var.ref and left_var.network_conn and right_var.network_conn:
            return True
        else:
            return False

    def _find_output_port_for_var(self, item_source: graph.GenericBlockItem, source_var: Var) -> graph.PortItem | None:
        """
        Find the visible output port corresponding to one symbolic variable.

        :param item_source: Source item.
        :param source_var: Source variable.
        :return: Matching output port or ``None``.
        """
        port: graph.PortItem
        for port in item_source.outputs:
            if self._vars_match_for_visible_connection(port.base_var, source_var):
                return port
            else:
                pass
        return None

    def _find_input_port_for_var(self, item_dest: graph.GenericBlockItem, target_var: Var) -> graph.PortItem | None:
        """
        Find the visible input port corresponding to one symbolic variable.

        :param item_dest: Destination item.
        :param target_var: Target variable.
        :return: Matching input port or ``None``.
        """
        port: graph.PortItem
        for port in item_dest.inputs:
            if self._vars_match_for_visible_connection(port.base_var, target_var):
                return port
            else:
                pass
        return None

    @staticmethod
    def _connection_exists_between_ports(source_port: graph.PortItem | graph.BranchingItem,
                                         target_port: graph.PortItem | graph.BranchingItem) -> bool:
        """
        Return whether one visible connection already exists between two ports.

        :param source_port: Candidate source port.
        :param target_port: Candidate target port.
        :return: ``True`` when the connection is already present.
        """
        connection: graph.ConnectionItem

        if source_port.connections is None:
            return False

        for connection in source_port.connections:
            if connection.source_port is source_port and connection.target_port is target_port:
                return True
            else:
                pass

        return False

    def add_api_obj_mapping(self):

        # Todo: add static_parameters_maping logic to add this depending on the type of device
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
                ParamPowerFlowReferenceType.g: g,
                ParamPowerFlowReferenceType.b: b,
                ParamPowerFlowReferenceType.bsh: bsh,
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

            if isinstance(selected_item,
                          (graph.BlockItem, graph.GenericBlockItem, graph.RoundBaseArithmeticOpItem, graph.RectBaseArithmeticOpItem)):
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
        source_model = self._table_source_model(index)
        source_index = self._table_source_index(index)
        source_row = source_index.row()
        if source_model is self.parameters_model and source_index.column() == 0:
            self.open_edit_parameter_type_dialog(source_row)
        elif source_model is self.parameters_model and source_index.column() == 2:
            row_data: dialog_models.BlockParameterRow | None = self.parameters_model.get_row(source_row)
            if row_data is not None and row_data.kind != dialog_models.BlockParameterKind.FIXED_PARAMETER:
                self.open_expression_editor_for_parameters(source_row)
        elif source_model is self.equations_model:
            row_data: dialog_models.BlockParameterRow | None = self.equations_model.get_row(source_row)
            if row_data is not None:
                if row_data.opens_expression_editor and source_index.column() == 1:
                    self.open_expression_row_editor(source_row)

    def open_edit_parameter_type_dialog(self, row_index: int) -> None:
        """
        Open the dialog to edit a parameter's type (event, mode, or regular).

        :param row_index:
        :return:
        """
        row_data: dialog_models.BlockParameterRow | None = self.parameters_model.get_row(row_index)
        if row_data is None or self.parameters_model.block is None:
            return

        block = self.parameters_model.block

        api_object = self.parameters_model.api_object
        dialog: dialog_models.EditParameterDialog = dialog_models.EditParameterDialog(
            api_object=api_object,
            devices_static_params_mapping=self.devices_static_params_mapping,
            current_kind=row_data.kind,
            parent=self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                new_kind: dialog_models.BlockParameterKind = dialog.get_category_kind()
                old_kind: dialog_models.BlockParameterKind = row_data.kind

                if new_kind == old_kind:
                    return

                var_name = row_data.name

                if new_kind == dialog_models.BlockParameterKind.FIXED_PARAMETER:
                    static_var_ref = dialog.get_static_variable()
                    new_var = self.var_factory.add_var(name=var_name, reference=static_var_ref)
                    const_value = 0.0
                else:
                    new_var = self.var_factory.add_var(name=var_name)
                    const_value = dialog.get_parameter_value()

                old_var = row_data.key_var

                if old_kind == dialog_models.BlockParameterKind.EVENT_PARAMETER:
                    block.event_dict.pop(old_var, None)
                elif old_kind == dialog_models.BlockParameterKind.MODE_PARAMETER:
                    block.mode_dict.pop(old_var, None)
                elif old_kind == dialog_models.BlockParameterKind.FIXED_PARAMETER:
                    block.parameters.pop(old_var, None)

                if new_kind == dialog_models.BlockParameterKind.EVENT_PARAMETER:
                    block.event_dict[new_var] = Const(const_value, name=var_name)
                elif new_kind == dialog_models.BlockParameterKind.MODE_PARAMETER:
                    block.mode_dict[new_var] = Const(const_value, name=var_name)
                elif new_kind == dialog_models.BlockParameterKind.FIXED_PARAMETER:
                    block.parameters[new_var] = Const(const_value, name=var_name)

                self.parameters_model.set_block(block)
                self.parameters_model.block_updated.emit(block.uid)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Edit Parameter Type Error", str(exc))

    def open_expression_editor_for_parameters(self, row_index: int) -> None:
        """
        Open the expression text editor for a parameters-table row.

        :param row_index:
        :return:
        """
        row_data: dialog_models.BlockParameterRow | None = self.parameters_model.get_row(row_index)
        expression_text: str
        dialog: ExpressionTextEditorDialog
        symbol_namespace: Dict[str, Expr]
        parsed_expression: Expr | Comparison
        expression_value: Expr

        if row_data is not None and self.parameters_model.block is not None:
            if row_data.value is not None and isinstance(row_data.value, Expr):
                expression_text = symbolic_to_string(row_data.value)
            else:
                expression_text = str(row_data.value) if row_data.value is not None else ""
            symbol_namespace = dialog_models.build_block_symbol_namespace(self.parameters_model.block)
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

                    self.parameters_model.set_value_from_expression(row_index, expression_value)
                    print("")
                except Exception as exc:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Expression Error",
                        str(exc)
                    )

    @staticmethod
    def _table_source_index(index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        model = index.model()
        if isinstance(model, QtCore.QSortFilterProxyModel):
            return model.mapToSource(index)
        return index

    @staticmethod
    def _table_source_model(index: QtCore.QModelIndex) -> QtCore.QAbstractItemModel | None:
        model = index.model()
        if isinstance(model, QtCore.QSortFilterProxyModel):
            return model.sourceModel()
        return model

    def on_variables_table_double_clicked(self, index: QtCore.QModelIndex) -> None:
        """
        Open the expression text editor when the user double-clicks an init_eq cell.

        :param index:
        :return:
        """
        if index.column() == 2:
            source_index = self._table_source_index(index)
            self.open_expression_row_editor_for_variables(source_index.row())

    def open_expression_row_editor_for_variables(self, row_index: int) -> None:
        """
        Open the expression text editor for a variables-table row.

        :param row_index:
        :return:
        """
        row_data: dialog_models.BlockParameterRow | None = self.variables_model.get_row(row_index)
        expression_text: str
        dialog: ExpressionTextEditorDialog
        symbol_namespace: Dict[str, Expr]
        parsed_expression: Expr | Comparison
        expression_value: Expr

        if row_data is not None and self.variables_model.block is not None:
            if row_data.init_eq is not None and isinstance(row_data.init_eq, Expr):
                expression_text = symbolic_to_string(row_data.init_eq)
            else:
                expression_text = ""
            symbol_namespace = dialog_models.build_block_symbol_namespace(self.variables_model.block)
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

                    self.variables_model.set_init_eq(row_index, expression_value)
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
        add_parameter_action: QAction = menu.addAction("Add Parameter")
        remove_selected_action: QAction = menu.addAction("Remove Selected")

        add_parameter_action.setEnabled(selected_block is not None)
        remove_selected_action.setEnabled(selected_block is not None and has_selected_rows)

        selected_action: QAction | None = menu.exec(table_view.viewport().mapToGlobal(position))

        if selected_action == add_parameter_action:
            self.open_add_parameter_dialog()
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

                if not dialog_models.is_valid_symbol_name(name):
                    raise ValueError("The symbol name must be a valid identifier.")
                elif dialog_models.block_namespace_contains_name(block, name):
                    raise ValueError(f"The symbol '{name}' already exists in this block.")

                new_var = self.var_factory.add_var(name=name)
                dialog_models.add_variable_to_block(
                    block=block,
                    var=new_var,
                    var_type=category,
                    parameter_value=parameter_value
                )

                self.variables_model.set_block(block)
                self.parameters_model.set_block(block)
                self.equations_model.set_block(block)
                self.variables_model.block_updated.emit(block.uid)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Add Variable Error", str(exc))
        else:
            pass

    def open_add_parameter_dialog(self) -> None:
        """
        Open the dialog used to add a new parameter (event, mode, or regular) to the selected block.

        :return:
        """
        api_object = self.parameters_model.api_object
        dialog: AddParameterDialog = AddParameterDialog(
            api_object=api_object,
            devices_static_params_mapping=self.devices_static_params_mapping,
            parent=self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                block = self.get_selected_scene_block()
                if block is None:
                    raise ValueError("No block is selected in the editor.")

                name = dialog.get_name()
                category = dialog.get_category()

                if not dialog_models.is_valid_symbol_name(name):
                    raise ValueError("The symbol name must be a valid identifier.")
                elif dialog_models.block_namespace_contains_name(block, name):
                    raise ValueError(f"The symbol '{name}' already exists in this block.")

                if category == "parameter":
                    static_var_ref = dialog.get_static_variable()
                    new_var = self.var_factory.add_var(name=name, reference=static_var_ref)
                    parameter_value = None
                else:
                    new_var = self.var_factory.add_var(name=name)
                    parameter_value = dialog.get_parameter_value()
                dialog_models.add_variable_to_block(
                    block=block,
                    var=new_var,
                    var_type=category,
                    parameter_value=parameter_value
                )

                self.parameters_model.set_block(block)
                self.equations_model.set_block(block)
                self.parameters_model.block_updated.emit(block.uid)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Add Parameter Error", str(exc))
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

        symbol_namespace = dialog_models.build_block_symbol_namespace(block)
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

                self.equations_model.set_block(block)
                self.equations_model.block_updated.emit(block.uid)
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

        vars_model = self.variables_model
        vars_selected = [self._table_source_index(idx).row() for idx in
                         self.ui.variablesTableView.selectionModel().selectedRows()]
        if not vars_selected:
            return

        vars_to_remove_from_state = []
        vars_to_remove_from_algebraic = []
        init_keys_to_remove = []
        for row_idx in vars_selected:
            row_data = vars_model.rows[row_idx]
            var = row_data.key_var
            if row_data.kind == dialog_models.BlockParameterKind.STATE_VAR:
                if var in block.state_vars:
                    vars_to_remove_from_state.append(var)
                    if var in block.init_values:
                        init_keys_to_remove.append(var)
            elif row_data.kind == dialog_models.BlockParameterKind.ALGEBRAIC_VAR:
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

        params_model = self.parameters_model
        params_selected = [self._table_source_index(idx).row() for idx in
                           self.ui.parametersTableView.selectionModel().selectedRows()]
        if not params_selected:
            return

        for row_idx in params_selected:
            row_data = params_model.rows[row_idx]
            var = row_data.key_var
            if row_data.kind == dialog_models.BlockParameterKind.EVENT_PARAMETER:
                if var in block.event_dict:
                    del block.event_dict[var]
            elif row_data.kind == dialog_models.BlockParameterKind.MODE_PARAMETER:
                if var in block.mode_dict:
                    del block.mode_dict[var]
            elif row_data.kind == dialog_models.BlockParameterKind.FIXED_PARAMETER:
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

        equations_model = self.equations_model
        equations_selected = [self._table_source_index(idx).row() for idx in
                              self.ui.equationsTableView.selectionModel().selectedRows()]
        if not equations_selected:
            return

        state_indices_to_remove = set()
        alg_indices_to_remove = set()
        for row_idx in equations_selected:
            row_data = equations_model.rows[row_idx]
            if row_data.item_index is not None:
                if row_data.kind == dialog_models.BlockParameterKind.STATE_EQUATION:
                    state_indices_to_remove.add(row_data.item_index)
                elif row_data.kind == dialog_models.BlockParameterKind.ALGEBRAIC_EQUATION:
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
        row_data: dialog_models.BlockParameterRow | None = self.equations_model.get_row(row_index)
        expression_text: str
        dialog: ExpressionTextEditorDialog
        symbol_namespace: Dict[str, Expr]
        parsed_expression: Expr | Comparison
        expression_value: Expr

        if row_data is not None and self.equations_model.block is not None:
            if isinstance(row_data.value, Expr):
                old_expr = row_data.value
                expression_text = symbolic_to_string(row_data.value)
                self.equations_model.symbol_namespace = dialog_models.build_block_symbol_namespace(
                    self.equations_model.block)
                dialog = ExpressionTextEditorDialog(
                    expression_text=expression_text,
                    symbol_namespace=self.equations_model.symbol_namespace,
                    parent=self
                )

                if dialog.exec() == QDialog.DialogCode.Accepted:
                    try:
                        parsed_expression = string_to_symbolic(dialog.get_expression_text(),
                                                               self.equations_model.symbol_namespace)

                        if isinstance(parsed_expression, Comparison):
                            expression_value = parsed_expression.to_expression()
                        else:
                            expression_value = parsed_expression

                        index = self.equations_model.index(row_index, 1)
                        self.equations_model.setData(index, symbolic_to_string(expression_value),
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

    def delete_all_blocks_with_confirmation(self) -> None:
        """
        Ask the user for confirmation before deleting the complete model body.

        The operation is destructive for the internal implementation, so it must
        follow the same GUI confirmation style used across the rest of VeraGrid.
        Only after the user confirms the action can the editor clear all blocks
        except for the protected connection ports.

        :return: None.
        """
        confirmed: bool = yes_no_question(
            text="You are going to delete the complete model and start from scratch. Are you sure?",
            title="Delete all"
        )

        if confirmed:
            deletable_items: List[graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem] = list()
            scene_item: QGraphicsItem

            for scene_item in self.scene.items():
                if isinstance(scene_item, graph.ProtectedConnectionBlockItem):
                    pass
                else:
                    if isinstance(scene_item,
                                  (graph.BlockItem, graph.GenericBlockItem, graph.RoundBaseArithmeticOpItem, graph.RectBaseArithmeticOpItem)):
                        deletable_items.append(scene_item)
                    else:
                        pass

            deletable_item: graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem

            if len(deletable_items) == 0:
                self._selected_side_block = None
                self.refresh_active_side_panel()
            else:
                for deletable_item in deletable_items:
                    self.remove_block_item(deletable_item)

                self.scene.clearSelection()
                self._selected_side_block = None
                self.refresh_active_side_panel()
                self.mark_unapplied_changes()
        else:
            pass

    def on_scene_selection_changed(self) -> None:
        """
        Refresh the right-side parameters table from the selected block.

        :return:
        """
        selected_block: Block | None = self.get_selected_scene_block()
        self._selected_side_block = selected_block
        self.refresh_active_side_panel()

    @QtCore.Slot(int)
    def handle_side_panel_page_changed(self, index: int) -> None:
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
            self.variables_model.set_block(self._selected_side_block)
        else:
            if current_widget == self.ui.page_2:
                self.parameters_model.set_block(self._selected_side_block)
            else:
                if current_widget == self.ui.page_3:
                    self.equations_model.set_block(self._selected_side_block)
                else:
                    pass

    def edit_scene_item(self, item: graph.BlockItem | graph.GenericBlockItem | graph.ConnectionItem) -> None:
        """
        Open an editor for the selected scene item when supported.

        :param item: Scene item selected from the context menu.
        :return: None.
        """
        if isinstance(item, (graph.GenericBlockItem, graph.BlockItem)):
            if item.subsys is not None:
                self.request_navigate_to_block(item.subsys)

    def get_scene_item_by_block_uid(self,
                                    block_uid: int) -> graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | None:
        """
        Find the visible scene item representing a block uid.

        :param block_uid:
        :return:
        """
        item: QGraphicsItem

        for item in self.scene.items():
            if isinstance(item, (graph.BlockItem, graph.GenericBlockItem, graph.RoundBaseArithmeticOpItem,
                                 graph.RectBaseArithmeticOpItem)) and item.subsys is not None:
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
        item: graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | None = self.get_scene_item_by_block_uid(
            block_uid)

        if item is not None:
            self.scene.clearSelection()
            item.setSelected(True)
        else:
            pass

    def _invalidate_equations_latex(self, old_latex: str) -> None:
        """Drop one cached LaTeX pixmap after the source equation changed."""
        delegate = self._equations_latex_delegate
        if hasattr(delegate, "invalidate"):
            delegate.invalidate(old_latex)
        self.ui.equationsTableView.resizeRowsToContents()

    def on_block_updated(self, block_uid: int) -> None:
        """
        Refresh the scene after a block edit coming from the parameters tab.

        :param block_uid:
        :return:
        """
        self.mark_unapplied_changes()
        sender_obj: QtCore.QObject | None = self.sender()

        if sender_obj is self.parameters_model:
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
            # When the user overwrites a template-assigned EMT model, the device must
            # stop pointing to the reusable template object and keep only the edited
            # concrete model instance.
            if self.api_object.rms_template is not None:
                self.api_object.rms_template = None
            else:
                pass
            # Persist the edited RMS block back into the original model object.
            self._document.commit()
            # Rebuild the connected bus helper models so the saved block stays
            # consistent with the rest of the dynamic network representation.
            dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=self.api_object,
                                                                  circuit=self.circuit,
                                                                  var_factory=self.var_factory,
                                                                  mode=self.mode)
            # Mark the editor state as clean because all in-memory edits were
            # transferred back to the owned device model successfully.
            self.has_unapplied_changes = False
            self.changes_applied = True
            self.dirtyStateChanged.emit(False)
            self.toast_manager.show_info_toast("Model saved")
            if self.workspace_embedded:
                pass
            else:
                pass

        elif self.mode == DynamicSimulationMode.EMT:
            # When the user overwrites a template-assigned EMT model, the device must
            # stop pointing to the reusable template object and keep only the edited
            # concrete model instance.
            if self.api_object.emt_template is not None:
                self.api_object.emt_template = None
            else:
                pass
            # Persist the edited EMT block exactly as it exists in the editor,
            # just like the RMS save path does. The bus attachment helper is the
            # only stage that should connect the saved model to the bus shells.
            self._remove_shared_branch_emt_root_refs()
            self._document.commit()

            dialog_models.initialize_connected_bus_models_for_editor_assignment(api_object=self.api_object,
                                                                                circuit=self.circuit,
                                                                                var_factory=self.var_factory,
                                                                                mode=self.mode)
            if isinstance(self.api_object, InjectionParent):
                dialog_models.attach_editor_assigned_emt_injection_model(api_object=self.api_object,
                                                                         var_factory=self.var_factory)
            elif isinstance(self.api_object, BranchParent):
                dialog_models.attach_editor_assigned_emt_branch_model(api_object=self.api_object,
                                                                      var_factory=self.var_factory)
            else:
                pass
            # Mark the editor state as clean because all in-memory edits were
            # transferred back to the owned device model successfully.
            self.has_unapplied_changes = False
            self.changes_applied = True
            self.dirtyStateChanged.emit(False)
            self.toast_manager.show_info_toast("Model saved")
            if self.workspace_embedded:
                pass
            else:
                pass

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
        inspect_widget = dialog_models.InspectModel(block=self.main_block, parent=dialog)

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

    def _build_connected_port_sets(self) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
        """
        Build quick-lookup sets for connected inputs and outputs.

        :return: ``(connected_inputs, connected_outputs)``.
        """
        # The graph diagram stores connections by node UID and port index. The
        # validator precomputes these sets once so later checks are O(1) per port.
        connected_inputs: set[tuple[int, int]] = set()
        connected_outputs: set[tuple[int, int]] = set()
        con: Any
        for con in self.diagram.con_data.values():
            connected_outputs.add((con.from_uid, con.port_number_from))
            connected_inputs.add((con.to_uid, con.port_number_to))
        return connected_inputs, connected_outputs

    def _validate_equation_counts(self, section: valid.ValidationSection, blocks: list[Block]) -> None:
        """
        Append state/algebraic equation-count mismatches.

        :param section: Mutable grouped section results.
        :param blocks: Blocks to validate.
        :return: None.
        """
        block: Block
        for block in blocks:
            # The first structural consistency rule checks equation balance for
            # each symbolic subsystem independently.
            block_label: str = valid.format_validation_block_label(block)
            if len(block.state_vars) != len(block.state_eqs):
                valid.add_validation_detail(
                    section=section,
                    block_label=block_label,
                    detail=f"state vars={len(block.state_vars)}, state eqs={len(block.state_eqs)}",
                )
            else:
                pass

            if len(block.algebraic_vars) != len(block.algebraic_eqs):
                valid.add_validation_detail(
                    section=section,
                    block_label=block_label,
                    detail=f"algebraic vars={len(block.algebraic_vars)}, algebraic eqs={len(block.algebraic_eqs)}",
                )
            else:
                pass

    def _validate_duplicate_variable_names(self, section: valid.ValidationSection, blocks: list[Block]) -> None:
        """
        Append duplicate symbolic-name issues inside each block.

        :param section: Mutable grouped section results.
        :param blocks: Blocks to validate.
        :return: None.
        """
        block: Block
        for block in blocks:
            # Duplicate-name validation must inspect every collection that can
            # expose symbolic variables inside one block.
            name_to_uids: dict[str, set[int]] = dict()
            parameter_vars: list[Var] = list(block.parameters.keys())
            event_vars: list[Var] = list(block.event_dict.keys())
            mode_vars: list[Var] = list(block.mode_dict.keys())

            valid.append_vars_to_name_uid_map(name_to_uids=name_to_uids, vars_list=block.state_vars)
            valid.append_vars_to_name_uid_map(name_to_uids=name_to_uids, vars_list=block.algebraic_vars)
            valid.append_vars_to_name_uid_map(name_to_uids=name_to_uids, vars_list=block.diff_vars)
            valid.append_vars_to_name_uid_map(name_to_uids=name_to_uids, vars_list=block.in_vars)
            valid.append_vars_to_name_uid_map(name_to_uids=name_to_uids, vars_list=block.out_vars)
            valid.append_vars_to_name_uid_map(name_to_uids=name_to_uids, vars_list=parameter_vars)
            valid.append_vars_to_name_uid_map(name_to_uids=name_to_uids, vars_list=event_vars)
            valid.append_vars_to_name_uid_map(name_to_uids=name_to_uids, vars_list=mode_vars)

            # Out vars, in vars, mappings and parameter dictionaries often reuse
            # the exact same Var object that already exists in the block state or
            # algebraic collections. That is valid. We only flag names that map
            # to multiple distinct symbolic variables.
            duplicates: list[str] = sorted([name for name, uids in name_to_uids.items() if len(uids) > 1])
            if duplicates:
                valid.add_validation_detail(
                    section=section,
                    block_label=valid.format_validation_block_label(block),
                    detail=f"vars: {', '.join(duplicates)}",
                )
            else:
                pass

    def _validate_parameter_mappings(self, section: valid.ValidationSection, blocks: list[Block]) -> None:
        """
        Append parameter mapping and event-value issues.

        :param section: Mutable grouped section results.
        :param blocks: Blocks to validate.
        :return: None.
        """
        block: Block
        for block in blocks:
            # Static parameters are only meaningful if the wider model can reach
            # them through one of the supported mapping dictionaries.
            mapped_vars: set[Var] = {
                var for var in block.external_mapping.values() if isinstance(var, Var)
            }
            mapped_vars.update(var for var in block.api_obj_mapping.values() if isinstance(var, Var))
            mapped_vars.update(var for var in block.event_dict.keys() if isinstance(var, Var))

            unmapped_parameters: list[str] = sorted([
                var.name for var in block.parameters.keys() if isinstance(var, Var) and var not in mapped_vars
            ])
            missing_event_values: list[str] = sorted([
                var.name for var, expr in block.event_dict.items() if isinstance(var, Var) and expr is None
            ])

            if unmapped_parameters:
                valid.add_validation_detail(
                    section=section,
                    block_label=valid.format_validation_block_label(block),
                    detail=f"params missing mapping: {', '.join(unmapped_parameters)}",
                )
            else:
                pass

            if missing_event_values:
                valid.add_validation_detail(
                    section=section,
                    block_label=valid.format_validation_block_label(block),
                    detail=f"event params with no value: {', '.join(missing_event_values)}",
                )
            else:
                pass

    def _validate_variable_initialization(self, section: valid.ValidationSection,
                                          traversal_nodes: list[valid.ValidationTraversalNode]) -> None:
        """
        Append initialization issues for state, algebraic and diff variables.

        :param section: Mutable grouped section results.
        :param traversal_nodes: Recursive traversal nodes carrying effective mappings.
        :return: None.
        """
        traversal_node: valid.ValidationTraversalNode
        for traversal_node in traversal_nodes:
            block: Block = traversal_node.get_block()
            # Initialization validation checks which variables can be seeded from
            # the external interface and which ones must be seeded internally.
            external_vars: set[Var] = traversal_node.get_effective_external_vars()

            missing_init_vars: list[str] = list()
            var: Var
            for var in block.state_vars:
                if var not in external_vars and var not in block.init_eqs:
                    missing_init_vars.append(var.name)
                else:
                    pass

            for var in block.algebraic_vars:
                if var not in external_vars and var not in block.init_eqs:
                    missing_init_vars.append(var.name)
                else:
                    pass

            missing_init_vars = sorted(missing_init_vars)
            missing_diff_init_vars: list[str] = sorted([
                var.name
                for var in block.diff_vars
                if isinstance(var, Var) and var not in external_vars and var not in block.diff_init_eqs
            ])

            if missing_init_vars:
                valid.add_validation_detail(
                    section=section,
                    block_label=valid.format_validation_block_label(block),
                    detail=f"vars missing init/external mapping: {', '.join(missing_init_vars)}",
                )
            else:
                pass

            if missing_diff_init_vars:
                valid.add_validation_detail(
                    section=section,
                    block_label=valid.format_validation_block_label(block),
                    detail=f"diff vars missing diff init/external mapping: {', '.join(missing_diff_init_vars)}",
                )
            else:
                pass

    def _validate_port_connectivity(self, section: valid.ValidationSection) -> None:
        # todo: rethink this validation
        """
        Append missing-port-connection issues from the saved diagram.

        :param section: Mutable grouped section results.
        :return: None.
        """
        connected_inputs, connected_outputs = self._build_connected_port_sets()
        node_uid: int
        node: Any

        for node_uid, node in self.diagram.node_data.items():
            # Each diagram node is validated against the saved symbolic interface
            # so the report reflects exactly what the user wired in the editor.
            block: Block | None = self.get_block_from_main_block(node.device_uid)
            if block is None:
                pass
            else:
                missing_port_messages: list[str] = list()
                emt_missing_by_phase: dict[str, list[str]] = dict({"N": list(), "A": list(), "B": list(), "C": list()})
                missing_input_names: list[str] = list()
                missing_output_names: list[str] = list()
                missing_input_refs: list[VarPowerFlowReferenceType] = list()
                missing_output_refs: list[VarPowerFlowReferenceType] = list()
                valid.append_missing_port_messages_for_direction(
                    missing_port_messages=missing_port_messages,
                    emt_missing_by_phase=emt_missing_by_phase,
                    vars_list=block.in_vars,
                    node_uid=node_uid,
                    connected_ports=connected_inputs,
                    is_input=True,
                    mode=self.mode,
                )
                valid.append_missing_port_messages_for_direction(
                    missing_port_messages=missing_port_messages,
                    emt_missing_by_phase=emt_missing_by_phase,
                    vars_list=block.out_vars,
                    node_uid=node_uid,
                    connected_ports=connected_outputs,
                    is_input=False,
                    mode=self.mode,
                )

                if self.mode == DynamicSimulationMode.EMT:
                    # EMT allows a whole phase to be absent, but it does not allow
                    # partially connected ports for a phase that is otherwise present.
                    phase_total_ports_by_name: dict[str, int] = dict({"N": 0, "A": 0, "B": 0, "C": 0})
                    valid.append_port_vars_to_phase_count(phase_counts=phase_total_ports_by_name, vars_list=block.in_vars)
                    valid.append_port_vars_to_phase_count(phase_counts=phase_total_ports_by_name, vars_list=block.out_vars)
                    root_connected_interface_refs: set[
                        VarPowerFlowReferenceType] = self._get_connected_root_interface_refs()
                    root_injection_mask: list[bool] = build_emt_injection_bus_mask_from_refs(
                        refs=root_connected_interface_refs)
                    root_branch_from_mask: list[bool] = build_emt_branch_bus_mask_from_refs(
                        refs=root_connected_interface_refs,
                        side="from",
                    )
                    root_branch_to_mask: list[bool] = build_emt_branch_bus_mask_from_refs(
                        refs=root_connected_interface_refs,
                        side="to",
                    )
                    phase_index_by_name: dict[str, int] = dict({"N": 0, "A": 1, "B": 2, "C": 3})

                    phase_name: str
                    phase_missing_messages: list[str]
                    for phase_name, phase_missing_messages in emt_missing_by_phase.items():
                        if phase_missing_messages:
                            phase_total_ports: int = phase_total_ports_by_name[phase_name]
                            phase_missing_count: int = len(phase_missing_messages)
                            phase_index: int = phase_index_by_name[phase_name]
                            phase_is_fully_absent_at_root: bool = False
                            root_reference: VarPowerFlowReferenceType | None = None

                            if block in self.main_block.in_vars or block in self.main_block.out_vars:
                                root_reference = valid.get_var_reference(var=block)
                            else:
                                if node.tpe == BlockType.INPUT_CONN.name or node.tpe == BlockType.OUTPUT_CONN.name:
                                    reference_var: Var | None = None

                                    if node.tpe == BlockType.INPUT_CONN.name and len(block.out_vars) > 0:
                                        reference_var = block.out_vars[0]
                                    else:
                                        if node.tpe == BlockType.OUTPUT_CONN.name and len(block.in_vars) > 0:
                                            reference_var = block.in_vars[0]
                                        else:
                                            reference_var = None

                                    if reference_var is not None:
                                        root_reference = valid.get_var_reference(var=reference_var)
                                    else:
                                        root_reference = None
                                else:
                                    root_reference = None

                            if root_reference is not None:
                                if root_reference in {
                                    VarPowerFlowReferenceType.v_N,
                                    VarPowerFlowReferenceType.v_A,
                                    VarPowerFlowReferenceType.v_B,
                                    VarPowerFlowReferenceType.v_C,
                                    VarPowerFlowReferenceType.i_N,
                                    VarPowerFlowReferenceType.i_A,
                                    VarPowerFlowReferenceType.i_B,
                                    VarPowerFlowReferenceType.i_C,
                                }:
                                    phase_is_fully_absent_at_root = not root_injection_mask[phase_index]
                                else:
                                    if root_reference in {
                                        VarPowerFlowReferenceType.vf_N,
                                        VarPowerFlowReferenceType.vf_A,
                                        VarPowerFlowReferenceType.vf_B,
                                        VarPowerFlowReferenceType.vf_C,
                                        VarPowerFlowReferenceType.if_N,
                                        VarPowerFlowReferenceType.if_A,
                                        VarPowerFlowReferenceType.if_B,
                                        VarPowerFlowReferenceType.if_C,
                                    }:
                                        phase_is_fully_absent_at_root = not root_branch_from_mask[phase_index]
                                    else:
                                        if root_reference in {
                                            VarPowerFlowReferenceType.vt_N,
                                            VarPowerFlowReferenceType.vt_A,
                                            VarPowerFlowReferenceType.vt_B,
                                            VarPowerFlowReferenceType.vt_C,
                                            VarPowerFlowReferenceType.it_N,
                                            VarPowerFlowReferenceType.it_A,
                                            VarPowerFlowReferenceType.it_B,
                                            VarPowerFlowReferenceType.it_C,
                                        }:
                                            phase_is_fully_absent_at_root = not root_branch_to_mask[phase_index]
                                        else:
                                            phase_is_fully_absent_at_root = False
                            else:
                                phase_is_fully_absent_at_root = False

                            if phase_is_fully_absent_at_root and \
                                    (node.tpe == BlockType.INPUT_CONN.name or node.tpe == BlockType.OUTPUT_CONN.name):
                                pass
                            else:
                                if phase_total_ports > 0:
                                    missing_port_messages.extend(phase_missing_messages)
                                else:
                                    pass
                        else:
                            pass
                else:
                    pass

                port_message: str
                for port_message in missing_port_messages:
                    if port_message.startswith("input '") and port_message.endswith("' is not connected"):
                        missing_input_names.append(port_message[7:-18])
                    else:
                        if port_message.startswith("output '") and port_message.endswith("' is not connected"):
                            missing_output_names.append(port_message[8:-18])
                        else:
                            pass

                input_var: Var
                for input_var in block.in_vars:
                    if input_var.name in missing_input_names:
                        input_reference: VarPowerFlowReferenceType | None = valid.get_var_reference(var=input_var)
                        if input_reference is not None:
                            missing_input_refs.append(input_reference)
                        else:
                            pass
                    else:
                        pass

                output_var: Var
                for output_var in block.out_vars:
                    if output_var.name in missing_output_names:
                        output_reference: VarPowerFlowReferenceType | None = valid.get_var_reference(var=output_var)
                        if output_reference is not None:
                            missing_output_refs.append(output_reference)
                        else:
                            pass
                    else:
                        pass

                if self.mode == DynamicSimulationMode.EMT:
                    if node.tpe == BlockType.INPUT_CONN.name or node.tpe == BlockType.OUTPUT_CONN.name:
                        root_connected_interface_refs: set[
                            VarPowerFlowReferenceType] = self._get_connected_root_interface_refs()
                        root_injection_mask: list[bool] = build_emt_injection_bus_mask_from_refs(
                            refs=root_connected_interface_refs,
                        )
                        root_branch_from_mask: list[bool] = build_emt_branch_bus_mask_from_refs(
                            refs=root_connected_interface_refs,
                            side="from",
                        )
                        root_branch_to_mask: list[bool] = build_emt_branch_bus_mask_from_refs(
                            refs=root_connected_interface_refs,
                            side="to",
                        )
                        protected_reference: VarPowerFlowReferenceType | None = None
                        skip_protected_root_row: bool = False

                        if node.tpe == BlockType.INPUT_CONN.name and len(block.out_vars) > 0:
                            protected_reference = valid.get_var_reference(var=block.out_vars[0])
                        else:
                            if node.tpe == BlockType.OUTPUT_CONN.name and len(block.in_vars) > 0:
                                protected_reference = valid.get_var_reference(var=block.in_vars[0])
                            else:
                                protected_reference = None

                        # Keep protected EMT root rows visible even when a whole
                        # phase is currently disconnected, because Show Issues must
                        # still project those missing interface ports back onto the
                        # canvas for the user to fix them.
                        skip_protected_root_row = False

                        if skip_protected_root_row:
                            missing_input_names = list()
                            missing_output_names = list()
                        else:
                            pass
                    else:
                        pass
                else:
                    pass

                if missing_input_names or missing_output_names:
                    block_label: str = node.name

                    if block in self.main_block.in_vars or block in self.main_block.out_vars:
                        # Root interface rows must point back to the visible protected
                        # connector node on canvas, not to the synthetic internal root
                        # variable name used by some rebuilt test/editor states.
                        block_label = node.name
                    else:
                        pass

                    valid.add_validation_port_detail(
                        section=section,
                        block_label=block_label,
                        detail=valid.format_missing_port_detail(
                            input_names=missing_input_names,
                            output_names=missing_output_names,
                        ),
                        input_names=missing_input_names,
                        output_names=missing_output_names,
                        input_refs=missing_input_refs,
                        output_refs=missing_output_refs,
                    )

                    if self.mode == DynamicSimulationMode.EMT and \
                            (node.tpe == BlockType.OUTPUT_CONN.name or node.tpe == BlockType.INPUT_CONN.name):
                        internal_owner_block: Block | None
                        internal_owner_label: str

                        internal_owner_block = self._find_internal_block_owning_emt_refs(
                            excluded_block=block,
                            input_refs=set(missing_input_refs),
                            output_refs=set(missing_output_refs),
                        )

                        if internal_owner_block is not None:
                            internal_owner_label = valid.format_validation_block_label(internal_owner_block)
                            valid.add_validation_port_detail(
                                section=section,
                                block_label=internal_owner_label,
                                detail=valid.format_missing_port_detail(
                                    input_names=missing_input_names,
                                    output_names=missing_output_names,
                                ),
                                input_names=missing_input_names,
                                output_names=missing_output_names,
                                input_refs=missing_input_refs,
                                output_refs=missing_output_refs,
                            )
                        else:
                            pass
                else:
                    pass

    def _find_internal_block_owning_emt_refs(self,
                                             excluded_block: Block,
                                             input_refs: set[VarPowerFlowReferenceType],
                                             output_refs: set[VarPowerFlowReferenceType]) -> Block | None:
        """
        Return one non-interface block exposing the requested EMT refs.

        :param excluded_block: Interface wrapper block to ignore.
        :param input_refs: Candidate input refs.
        :param output_refs: Candidate output refs.
        :return: Matching internal block or ``None``.
        """
        child_block: Block
        node_data: Any | None
        input_var: Var
        output_var: Var

        for child_block in self.main_block.children:
            if child_block.uid == excluded_block.uid:
                continue

            node_data = self.diagram.node_data.get(child_block.uid, None)
            if node_data is not None and node_data.tpe in {BlockType.INPUT_CONN.name, BlockType.OUTPUT_CONN.name}:
                continue

            for input_var in child_block.in_vars:
                if valid.get_var_reference(var=input_var) in input_refs:
                    return child_block

            for output_var in child_block.out_vars:
                if valid.get_var_reference(var=output_var) in output_refs:
                    return child_block

        return None

    def collect_model_consistency_sections(self) -> list[valid.ValidationSection]:
        """
        Validate the current working model and return grouped section results.

        :return: Ordered validation sections.
        """
        # The full validation runs as a deterministic pipeline so the dialog keeps
        # a stable order and users can compare repeated checks easily.
        blocks: list[Block] = valid.collect_block_tree(root_block=self.main_block)
        traversal_root: valid.ValidationTraversalNode = valid.build_validation_traversal_node(
            block=self.main_block,
            inherited_external_vars=set(),
        )
        traversal_nodes: list[valid.ValidationTraversalNode] = valid.collect_validation_traversal_list(root_node=traversal_root)
        equation_section: valid.ValidationSection = valid.ValidationSection(title="Equation Counts")
        duplicate_section: valid.ValidationSection = valid.ValidationSection(title="Repeated Variable Names")
        parameter_section: valid.ValidationSection = valid.ValidationSection(title="Parameter Mappings")
        init_section: valid.ValidationSection = valid.ValidationSection(title="Variable Initialization")
        port_section: valid.ValidationSection = valid.ValidationSection(title="Port Connectivity")
        self._validate_equation_counts(section=equation_section, blocks=blocks)
        self._validate_duplicate_variable_names(section=duplicate_section, blocks=blocks)
        self._validate_parameter_mappings(section=parameter_section, blocks=blocks)
        self._validate_variable_initialization(section=init_section, traversal_nodes=traversal_nodes)
        self._validate_port_connectivity(section=port_section)

        sections: list[valid.ValidationSection] = list([
            equation_section,
            duplicate_section,
            parameter_section,
            init_section,
            port_section,
        ])

        return sections

    def show_model_consistency_validation(self) -> None:
        """
        Show the current non-blocking model consistency report.

        :return: None.
        """
        # The dialog is informational only. It must never stop the save path, so
        # the method only gathers messages and shows them in one modal report.
        section_results: list[valid.ValidationSection] = self.collect_model_consistency_sections()
        dialog: valid.ValidationSectionDialog = valid.ValidationSectionDialog(section_results=section_results, parent=self)
        dialog.exec()

    def _iter_scene_block_items(self) -> list[graph.BlockItem | graph.GenericBlockItem]:
        """
        Return the visible scene items that support validation highlighting.

        :return: Scene block items.
        """
        scene_block_items: list[graph.BlockItem | graph.GenericBlockItem] = list()
        scene_item: Any

        # Validation highlighting must cover both full generic blocks and the
        # compact connection/interface blocks because the validation report can
        # point to either one when a port is left disconnected.
        for scene_item in self.scene.items():
            if isinstance(scene_item, (graph.BlockItem, graph.GenericBlockItem)):
                scene_block_items.append(scene_item)
            else:
                pass

        return scene_block_items

    def clear_validation_issue_overlay(self) -> None:
        """
        Clear the current validation overlay from blocks and ports.

        :return: None.
        """
        scene_block_item: graph.BlockItem | graph.GenericBlockItem
        port_item: graph.PortItem

        # The overlay is transient GUI state. It must be fully reset before a
        # new overlay is applied and whenever the model changes afterwards.
        for scene_block_item in self._iter_scene_block_items():
            scene_block_item.set_validation_highlighted(False)

            for port_item in scene_block_item.inputs:
                port_item.set_validation_highlighted(False)

            for port_item in scene_block_item.outputs:
                port_item.set_validation_highlighted(False)

        self._validation_issue_overlay_active = False

    def _find_scene_block_item_by_validation_label(self, block_label: str) -> graph.BlockItem | graph.GenericBlockItem | None:
        """
        Resolve one validation block label to its visible scene block item.

        :param block_label: Validation block label.
        :return: Matching scene block item or ``None``.
        """
        scene_block_item: graph.BlockItem | graph.GenericBlockItem
        formatted_label: str

        # Validation rows use the same stable block label formatter as the model
        # traversal, so the scene lookup can remain string-based and local.
        for scene_block_item in self._iter_scene_block_items():
            if isinstance(scene_block_item, graph.ProtectedConnectionBlockItem) and scene_block_item.name == block_label:
                return scene_block_item
            else:
                pass

            if scene_block_item.subsys is not None:
                node_data: Any | None = self.diagram.node_data.get(scene_block_item.subsys.uid, None)
            else:
                node_data = None

            if node_data is not None and getattr(node_data, "name", None) == block_label:
                return scene_block_item
            else:
                pass

            formatted_label = valid.format_validation_block_label(scene_block_item.subsys)
            if formatted_label == block_label:
                return scene_block_item
            elif scene_block_item.subsys.name == block_label:
                return scene_block_item
            elif getattr(scene_block_item, "name", None) == block_label:
                return scene_block_item
            elif getattr(scene_block_item, "name_item", None) is not None and \
                    scene_block_item.name_item.toPlainText() == block_label:
                return scene_block_item
            else:
                pass

        return None

    def _highlight_ports_by_name(self, scene_block_item: graph.BlockItem | graph.GenericBlockItem, port_names: set[str]) -> bool:
        """
        Highlight the ports whose variable names match the validation report.

        :param scene_block_item: Scene block item that owns the candidate ports.
        :param port_names: Port names to highlight.
        :return: Whether at least one port was highlighted.
        """
        highlighted_any_port: bool = False
        port_item: graph.PortItem
        port_var: Var | None
        tooltip_text: str
        tooltip_name: str | None

        # Connection/interface blocks represent a single exported connection
        # variable. When such a row is reported by the validator, the visible
        # meaning for the user is simply "this exposed connector is wrong", so
        # all visible ports on that compact block are highlighted directly.
        if isinstance(scene_block_item, graph.ProtectedConnectionBlockItem):
            reference_var: Var | None = None

            if scene_block_item.subsys is not None:
                if len(scene_block_item.subsys.out_vars) > 0:
                    reference_var = scene_block_item.subsys.out_vars[0]
                elif len(scene_block_item.subsys.in_vars) > 0:
                    reference_var = scene_block_item.subsys.in_vars[0]
                else:
                    reference_var = None
            else:
                reference_var = None

            if reference_var is not None and reference_var.name in port_names:
                pass
            else:
                return False

            for port_item in scene_block_item.inputs:
                if port_item.isVisible():
                    port_item.set_validation_highlighted(True)
                    highlighted_any_port = True
                else:
                    pass

            for port_item in scene_block_item.outputs:
                if port_item.isVisible():
                    port_item.set_validation_highlighted(True)
                    highlighted_any_port = True
                else:
                    pass

            if not highlighted_any_port:
                for port_item in scene_block_item.inputs:
                    port_item.set_validation_highlighted(True)
                    highlighted_any_port = True

                for port_item in scene_block_item.outputs:
                    port_item.set_validation_highlighted(True)
                    highlighted_any_port = True
            else:
                pass

            return highlighted_any_port
        else:
            pass

        # Port connectivity issues are projected back using the visible symbolic
        # variable names already shown in the editor and in the validation text.
        # Connection/interface items sometimes expose the name more reliably in
        # the tooltip than in the direct variable lookup, so both sources are
        # checked before deciding that a port does not match.
        for port_item in scene_block_item.inputs:
            port_var = port_item.base_var
            tooltip_text = port_item.toolTip()
            tooltip_name = tooltip_text.split(": ", 1)[1] if ": " in tooltip_text else None

            if (port_var is not None and port_var.name in port_names) or \
                    (tooltip_name is not None and tooltip_name in port_names):
                port_item.set_validation_highlighted(True)
                highlighted_any_port = True
            else:
                pass

        for port_item in scene_block_item.outputs:
            port_var = port_item.base_var
            tooltip_text = port_item.toolTip()
            tooltip_name = tooltip_text.split(": ", 1)[1] if ": " in tooltip_text else None

            if (port_var is not None and port_var.name in port_names) or \
                    (tooltip_name is not None and tooltip_name in port_names):
                port_item.set_validation_highlighted(True)
                highlighted_any_port = True
            else:
                pass

        return highlighted_any_port

    def _highlight_ports_by_ref(self,
                                scene_block_item: graph.BlockItem | graph.GenericBlockItem,
                                port_refs: set[VarPowerFlowReferenceType]) -> bool:
        """
        Highlight ports whose semantic references match the validation report.

        :param scene_block_item: Scene block item that owns the candidate ports.
        :param port_refs: Port references to highlight.
        :return: Whether at least one port was highlighted.
        """
        highlighted_any_port: bool = False
        port_item: graph.PortItem
        port_reference: VarPowerFlowReferenceType | None
        candidate_refs: set[VarPowerFlowReferenceType]
        mapped_input_item: graph.ProtectedConnectionBlockItem | None
        mapped_output_item: graph.ProtectedConnectionBlockItem | None

        candidate_refs = set(port_refs)

        if isinstance(scene_block_item, graph.ProtectedConnectionBlockItem) and self.mode == DynamicSimulationMode.EMT:
            interface_inputs_by_ref: Dict[VarPowerFlowReferenceType, graph.ProtectedConnectionBlockItem] = dict()
            interface_outputs_by_ref: Dict[VarPowerFlowReferenceType, graph.ProtectedConnectionBlockItem] = dict()
            scene_item: QGraphicsItem
            protected_item: graph.ProtectedConnectionBlockItem
            reference_var: Var | None

            for scene_item in self.scene.items():
                if isinstance(scene_item, graph.ProtectedConnectionBlockItem):
                    protected_item = scene_item
                    reference_var = None

                    if protected_item.subsys is not None:
                        if len(protected_item.subsys.out_vars) > 0:
                            reference_var = protected_item.subsys.out_vars[0]
                            if isinstance(reference_var.ref, VarPowerFlowReferenceType):
                                interface_inputs_by_ref[reference_var.ref] = protected_item
                        elif len(protected_item.subsys.in_vars) > 0:
                            reference_var = protected_item.subsys.in_vars[0]
                            if isinstance(reference_var.ref, VarPowerFlowReferenceType):
                                interface_outputs_by_ref[reference_var.ref] = protected_item
                        else:
                            pass
                    else:
                        pass
                else:
                    pass

            source_ref: VarPowerFlowReferenceType
            for source_ref in list(port_refs):
                mapped_input_item = self._get_editor_interface_input_item_for_ref(
                    interface_inputs_by_ref=interface_inputs_by_ref,
                    model_ref=source_ref,
                )
                if mapped_input_item is not None and mapped_input_item.subsys is not None and len(
                        mapped_input_item.subsys.out_vars) > 0:
                    mapped_ref = valid.get_var_reference(var=mapped_input_item.subsys.out_vars[0])
                    if mapped_ref is not None:
                        candidate_refs.add(mapped_ref)
                    else:
                        pass
                else:
                    pass

                mapped_output_item = self._get_editor_interface_output_item_for_ref(
                    interface_outputs_by_ref=interface_outputs_by_ref,
                    model_ref=source_ref,
                )
                if mapped_output_item is not None and mapped_output_item.subsys is not None and len(
                        mapped_output_item.subsys.in_vars) > 0:
                    mapped_ref = valid.get_var_reference(var=mapped_output_item.subsys.in_vars[0])
                    if mapped_ref is not None:
                        candidate_refs.add(mapped_ref)
                    else:
                        pass
                else:
                    pass
        else:
            pass

        if isinstance(scene_block_item, graph.ProtectedConnectionBlockItem):
            reference_var: Var | None = None

            if scene_block_item.subsys is not None:
                if len(scene_block_item.subsys.out_vars) > 0:
                    reference_var = scene_block_item.subsys.out_vars[0]
                elif len(scene_block_item.subsys.in_vars) > 0:
                    reference_var = scene_block_item.subsys.in_vars[0]
                else:
                    reference_var = None
            else:
                reference_var = None

            if reference_var is None:
                return False

            reference_var_ref = valid.get_var_reference(var=reference_var)
            if reference_var_ref not in candidate_refs:
                return False

            for port_item in scene_block_item.inputs:
                if port_item.isVisible():
                    port_item.set_validation_highlighted(True)
                    highlighted_any_port = True
                else:
                    pass

            for port_item in scene_block_item.outputs:
                if port_item.isVisible():
                    port_item.set_validation_highlighted(True)
                    highlighted_any_port = True
                else:
                    pass

            if not highlighted_any_port:
                for port_item in scene_block_item.inputs:
                    port_item.set_validation_highlighted(True)
                    highlighted_any_port = True

                for port_item in scene_block_item.outputs:
                    port_item.set_validation_highlighted(True)
                    highlighted_any_port = True
            else:
                pass

            return highlighted_any_port
        else:
            pass

        for port_item in scene_block_item.inputs:
            if port_item.base_var is None:
                continue

            port_reference = valid.get_var_reference(var=port_item.base_var)
            if port_reference in port_refs:
                port_item.set_validation_highlighted(True)
                highlighted_any_port = True
            else:
                pass

        for port_item in scene_block_item.outputs:
            if port_item.base_var is None:
                continue

            port_reference = valid.get_var_reference(var=port_item.base_var)
            if port_reference in port_refs:
                port_item.set_validation_highlighted(True)
                highlighted_any_port = True
            else:
                pass

        return highlighted_any_port

    def show_validation_issues_in_model(self, section_results: list[valid.ValidationSection]) -> None:
        """
        Apply one transient validation overlay to the current scene.

        :param section_results: Validation sections describing the current issues.
        :return: None.
        """
        valid.build_validation_row_highlight_metadata(section_results=section_results)
        self.clear_validation_issue_overlay()

        section: valid.ValidationSection
        row: valid.ValidationRow
        scene_block_item: graph.BlockItem | graph.GenericBlockItem | None
        highlighted_any_port: bool

        # The overlay keeps port-level connectivity issues more specific than the
        # generic block-border fallback used for all other validation failures.
        for section in section_results:
            for row in section.get_rows():
                scene_block_item = self._find_scene_block_item_by_validation_label(block_label=row.get_block_label())

                if scene_block_item is None:
                    pass
                else:
                    highlighted_any_port = False

                    if len(row.get_highlight_port_refs()) > 0:
                        highlighted_any_port = self._highlight_ports_by_ref(
                            scene_block_item=scene_block_item,
                            port_refs=row.get_highlight_port_refs(),
                        )
                    else:
                        pass

                    if not highlighted_any_port and len(row.get_highlight_port_names()) > 0:
                        highlighted_any_port = self._highlight_ports_by_name(
                            scene_block_item=scene_block_item,
                            port_names=row.get_highlight_port_names(),
                        )
                    else:
                        pass

                    if row.get_highlight_block() or not highlighted_any_port:
                        scene_block_item.set_validation_highlighted(True)
                    else:
                        pass

        self._highlight_connectivity_issue_ports_globally(section_results=section_results)

        self._validation_issue_overlay_active = True

    def _highlight_connectivity_issue_ports_globally(self, section_results: list[valid.ValidationSection]) -> None:
        """
        Highlight visible ports referenced by Port Connectivity across the scene.

        :param section_results: Validation sections describing the current issues.
        :return: None.
        """
        section: valid.ValidationSection
        row: valid.ValidationRow
        scene_block_item: graph.BlockItem | graph.GenericBlockItem
        port_item: graph.PortItem
        port_var: Var | None
        port_ref: VarPowerFlowReferenceType | None
        tooltip_text: str
        tooltip_name: str | None
        port_refs: set[VarPowerFlowReferenceType] = set()
        port_names: set[str] = set()

        for section in section_results:
            if section.get_title() != "Port Connectivity":
                continue

            for row in section.get_rows():
                port_refs.update(row.get_highlight_port_refs())
                port_names.update(row.get_highlight_port_names())

        if len(port_refs) == 0 and len(port_names) == 0:
            return
        else:
            pass

        # The per-row highlighting path can miss visible ports when one
        # connectivity issue is attached to one wrapper/root row but the user
        # expects every matching scene port to light up. This global pass keeps
        # the algorithm generic by scanning every visible in/out port directly
        # against the collected validation names and refs.
        for scene_block_item in self._iter_scene_block_items():
            all_ports: list[graph.PortItem] = list()
            for port_item in scene_block_item.inputs:
                all_ports.append(port_item)
            for port_item in scene_block_item.outputs:
                all_ports.append(port_item)

            for port_item in all_ports:
                port_var = port_item.base_var

                if port_var is not None:
                    port_ref = valid.get_var_reference(var=port_var)
                else:
                    port_ref = None

                tooltip_text = port_item.toolTip()
                if ": " in tooltip_text:
                    tooltip_name = tooltip_text.split(": ", 1)[1]
                else:
                    tooltip_name = None

                if port_ref is not None and port_ref in port_refs:
                    port_item.set_validation_highlighted(True)
                else:
                    if port_var is not None and port_var.name in port_names:
                        port_item.set_validation_highlighted(True)
                    else:
                        if tooltip_name is not None and tooltip_name in port_names:
                            port_item.set_validation_highlighted(True)
                        else:
                            pass

    def rebuild_scene_from_diagram(self) -> None:
        """
        Rebuild the visible scene from the persisted block diagram.

        :return:
        """
        uid_to_blockitem: Dict[
            int, graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | PairedItem] = dict()
        uid: int
        node: Any
        con: Any

        self.scene.clear()

        # Recreate nodes
        signal_in_items: Dict[str, graph.PairedItem] = {}
        signal_out_items: Dict[str, graph.PairedItem] = {}

        for uid, node in self.diagram.node_data.items():
            if node.tpe in BlockType.__members__:
                block_type = BlockType[node.tpe]
            else:
                block_type = None

            block_model: Block = self.get_block_from_main_block(node.device_uid)

            item = None
            if block_type == BlockType.INPUT_CONN or block_type == BlockType.OUTPUT_CONN:
                block_item: graph.ProtectedConnectionBlockItem = graph.ProtectedConnectionBlockItem(editor=self,
                                                                                        var_factory=self.var_factory,
                                                                                        name=node.name,
                                                                                        mode=self.mode,
                                                                                        api_object=self.api_object
                                                                                        )
                block_item.set_subsystem(block_model)
                block_item.position_changed_callback = self.build_position_changed_callback(block_model.uid)
                block_item.build_item()
                block_item.recolour()

                self.scene.addItem(block_item)
                block_item.setPos(QPointF(node.x, node.y))

                # brush: QBrush = block_item.brush()
                # brush.setColor(QColor(node.color))
                # block_item.setBrush(brush)
                uid_to_blockitem[uid] = block_item


                current_count: int = self.block_counters.get(block_type, 0) + 1
                self.block_counters[block_type] = current_count


            elif node.tpe in ("signal_in", "signal_out"):
                item = graph.PairedItem(editor=self,
                                  var_factory=self.var_factory,
                                  subsys=block_model,
                                  api_object=self.api_object,
                                  mode=self.mode,
                                  name=block_model.name,
                                  position_changed_callback=self.build_position_changed_callback(
                                      block_model.uid)
                                  )
                item.recolour()
                suffix = block_model.name.replace("From_", "").replace("To_", "")
                if node.tpe == "signal_in":
                    signal_in_items[suffix] = item
                else:
                    signal_out_items[suffix] = item

            elif block_type == BlockType.SUM or block_type == BlockType.PRODUCT:

                count: int = self.block_counters.get(block_type, 0) + 1

                if len(block_model.in_vars) <= 3:
                    item: graph.RoundBaseArithmeticOpItem = graph.RoundBaseArithmeticOpItem(
                        var_factory=self.var_factory,
                        subsys=block_model,
                        block_type=block_type,
                        editor=self,
                        position_changed_callback=self.build_position_changed_callback(
                            block_model.uid))
                else:
                    item: graph.RectBaseArithmeticOpItem = graph.RectBaseArithmeticOpItem(
                        var_factory=self.var_factory,
                        subsys=block_model,
                        block_type=block_type,
                        editor=self,
                        position_changed_callback=self.build_position_changed_callback(
                            block_model.uid))


                self.block_counters[block_type] = count
                item.recolour()

            elif block_type in self.UNARY_MATH_BLOCK_TYPES:
                item = graph.UnOpItem(
                    editor=self,
                    var_factory=self.var_factory,
                    subsys=block_model,
                    api_object=self.api_object,
                    mode=self.mode,
                    block_type=block_type,
                    name=block_model.name,
                    position_changed_callback=self.build_position_changed_callback(block_model.uid)
                )
                item.recolour()

            else:
                item = graph.GenericBlockItem(
                    editor=self,
                    var_factory=self.var_factory,
                    subsys=block_model,
                    api_object=self.api_object,
                    mode=self.mode,
                    name=block_model.name,
                    position_changed_callback=self.build_position_changed_callback(block_model.uid)
                )
                item.recolour()

            if item is not None:
                self.scene.addItem(item)
                item.setPos(QPointF(node.x, node.y))

                # if not isinstance(item, graph.PairedItem):
                #     brush = item.brush()
                #     brush.setColor(QColor(node.color))
                #     item.setBrush(brush)

                uid_to_blockitem[uid] = item

        # Pair signal_in and signal_out items
        for suffix, in_item in signal_in_items.items():
            out_item = signal_out_items.get(suffix)
            if out_item is not None:
                in_item.set_paired_item(out_item)
                out_item.set_paired_item(in_item)
        # Recreate connections
        for uid, con in self.diagram.con_data.items():
            src_item: graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | None = uid_to_blockitem.get(con.from_uid, None)
            dst_item: graph.BlockItem | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem | None = uid_to_blockitem.get(con.to_uid, None)
            src_port: graph.PortItem | None = None
            dst_port: graph.PortItem | None = None

            if src_item is not None and dst_item is not None:
                try:
                    src_port = src_item.outputs[con.port_number_from]
                    dst_port = dst_item.inputs[con.port_number_to]
                except IndexError:
                    src_port = None
                    dst_port = None

                if src_port is not None and dst_port is not None:
                    elbow_points: List[QPointF] = [QPointF(x, y) for x, y in
                                                   con.elbow_points] if con.elbow_points else []
                    connection: graph.ConnectionItem = graph.ConnectionItem(
                        src_port, dst_port,
                        diagram=self.diagram,
                        con_uid=uid,
                        elbow_points=elbow_points,
                        route_style=con.route_style,
                        locked=con.locked,
                        editor=self,
                    )
                    connection.recolour()
                    self.scene.addItem(connection)
                else:
                    pass
            else:
                pass

        if self.mode == DynamicSimulationMode.EMT and self.is_root_editor:
            pass
        else:
            pass

    def mark_unapplied_changes(self) -> None:
        """
        Mark the editor state as modified with unapplied changes.

        :return:
        """
        if self._validation_issue_overlay_active:
            self.clear_validation_issue_overlay()
        else:
            pass

        self.has_unapplied_changes = True
        self.changes_applied = False
        self.dirtyStateChanged.emit(True)

    def get_dynamic_editor_display_title(self) -> str:
        """
        Return the user-facing title for this editor instance.

        :return: Visible title for the workspace tab and window.
        """

        object_name = self.api_object.name if self.api_object is not None else "Dynamic object"
        return f"{object_name} [{self.mode.name}]"

    def get_dynamic_editor_entry(self) -> DynamicEditorEntry | None:
        """
        Return the workspace entry associated with this editor page.

        :return: Dynamic-editor entry or ``None`` when none is assigned.
        """
        return self.dynamic_editor_entry

    def set_dynamic_editor_entry(self, entry: DynamicEditorEntry | None) -> None:
        """
        Store the workspace entry associated with this editor page.

        :param entry: Dynamic-editor entry assigned by the workspace session.
        :return: None.
        """
        self.dynamic_editor_entry = entry

    def get_dynamic_editor_mode(self) -> DynamicSimulationMode:
        """
        Return the workspace mode associated with this editor page.

        :return: Dynamic simulation mode for this page.
        """
        return self.mode

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
            self.ui.toolBox.currentChanged.disconnect(self.handle_side_panel_page_changed)
        except (RuntimeError, TypeError):
            pass

        try:
            self.scene.selectionChanged.disconnect(self.on_scene_selection_changed)
        except (RuntimeError, TypeError):
            pass

    def prepare_to_delete(self) -> None:
        """
        Release editor-owned Qt objects before deleting this editor widget.

        :return: None.
        """
        if self._prepared_to_delete:
            return

        self._prepared_to_delete = True
        self.disconnect_editor_signals()
        self.scene.clear()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Close the editor. Ask for confirmation when there are unapplied changes.

        :param event:
        :return:
        """
        if self._prepared_to_delete:
            event.accept()
            return

        if self.can_close_editor(self):
            self.prepare_to_delete()
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
        block_item: graph.BlockItem | None | graph.GenericBlockItem | graph.RoundBaseArithmeticOpItem | graph.RectBaseArithmeticOpItem

        if payload is not None:

            block_item = self.create_library_payload_item(
                payload=payload,
                x_pos=scene_position.x(),
                y_pos=scene_position.y(),
            )

            if block_item is not None:
                block_item.recolour()
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def set_dark_mode(self):
        """
        Set the dark mode
        :return:
        """
        self.current_theme = DynEditorGraphicsModes.DARK
        self.set_colors_palet()
        for item in self.scene.items():
            if isinstance(item, (graph.GenericBlockItem, graph.PairedItem, graph.ConnectionItem, graph.RectBaseArithmeticOpItem,
                                 graph.RoundBaseArithmeticOpItem, graph.PortItem, graph.ElbowItem, graph.ResizeHandle, graph.BlockItem)):
                item.recolour()

    def set_light_mode(self):
        """
        Set the dark mode
        :return:
        """
        self.current_theme = DynEditorGraphicsModes.LIGHT
        self.set_colors_palet()
        for item in self.scene.items():
            if isinstance(item, (graph.GenericBlockItem, graph.PairedItem, graph.ConnectionItem, graph.RectBaseArithmeticOpItem,
                                 graph.RoundBaseArithmeticOpItem, graph.PortItem, graph.ElbowItem, graph.ResizeHandle, graph.BlockItem)):
                item.recolour()


if __name__ == "__main__":
    import sys
    import VeraGridEngine.Devices as dev

    app = QtWidgets.QApplication(sys.argv)

    vf = VarFactory()
    bl = Block()
    device = dev.Generator()
    window = DynamicBlockEditorGUI(
        var_factory=vf,
        root_block=bl,
        current_block=bl,
        api_object=device,
        circuit=MultiCircuit(),
        current_theme= DynEditorGraphicsModes.DARK,
    )
    window.show()
    app.exec_()
