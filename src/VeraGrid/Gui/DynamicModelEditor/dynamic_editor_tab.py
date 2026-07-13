# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any, List, Optional

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal

from VeraGrid.Gui.DynamicModelEditor.dynamic_block_preparation import prepare_block_for_editing
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_breadcrumb import DynamicEditorBreadcrumb
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_document import DynamicEditorDocument
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_navigation import DynamicEditorNavigation
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DynamicSimulationMode
from VeraGridEngine.Utils.Symbolic.block import Block

if False:
    from VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor import DynamicBlockEditorGUI
    from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_library import DynamicEditorLibrary
    from VeraGrid.Session.dynamic_editor_entries import DynamicEditorEntry


class DynamicEditorTab(QtWidgets.QWidget):
    """
    Coordinator widget that replaces a bare :class:`DynamicBlockEditorGUI`
    inside the workspace tab bar.

    It owns:

    * A :class:`DynamicEditorDocument` (one working copy per tab).
    * A :class:`DynamicEditorBreadcrumb` at the top.
    * Exactly one :class:`DynamicBlockEditorGUI` below the breadcrumb.

    Navigation (going into a child block) destroys the current editor and
    creates a new one.  There is never more than one editor alive inside
    a tab.  All edits target the single working tree owned by the document.
    """

    dirtyStateChanged = Signal(bool)

    def __init__(
        self,
        var_factory: VarFactory,
        block: Block,
        api_object: Any,
        circuit: MultiCircuit,
        mode: DynamicSimulationMode,
        templates_list: Optional[List[Any]] = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._var_factory = var_factory
        self._api_object = api_object
        self._circuit = circuit
        self._mode = mode
        self._templates_list = templates_list if templates_list is not None else list()
        self._dynamic_editor_entry: "DynamicEditorEntry | None" = None

        # ---- Document: single working copy per tab ----
        self._document = DynamicEditorDocument(block)
        working_root = self._document.working_root_block
        prepare_block_for_editing(working_root, var_factory)

        # ---- Navigation over the working tree ----
        self._navigation = DynamicEditorNavigation(working_root)

        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._breadcrumb = DynamicEditorBreadcrumb()
        self._breadcrumb.blockClicked.connect(self._on_breadcrumb_clicked)
        self._layout.addWidget(self._breadcrumb)

        self._editor: "DynamicBlockEditorGUI | None" = None
        self._create_editor(working_root)

    # ------------------------------------------------------------------
    # Public API — session / workspace compatibility
    # ------------------------------------------------------------------

    @property
    def document(self) -> DynamicEditorDocument:
        """Return the document backing this tab."""
        return self._document

    def get_dynamic_editor_entry(self) -> "DynamicEditorEntry | None":
        return self._dynamic_editor_entry

    def set_dynamic_editor_entry(self, entry: "DynamicEditorEntry") -> None:
        self._dynamic_editor_entry = entry

    def get_dynamic_editor_mode(self) -> DynamicSimulationMode:
        return self._mode

    def get_dynamic_editor_display_title(self) -> str:
        object_name = self._api_object.name if self._api_object is not None else "Dynamic object"
        return f"{object_name} [{self._mode.name}]"

    @property
    def has_unapplied_changes(self) -> bool:
        if self._editor is not None:
            return self._editor.has_unapplied_changes
        return False

    def can_close_editor(self, parent: QtWidgets.QWidget | None = None) -> bool:
        if self._editor is not None:
            return self._editor.can_close_editor(parent)
        return True

    def prepare_to_delete(self) -> None:
        if self._editor is not None:
            self._editor.prepare_to_delete()

    def set_dark_mode(self) -> None:
        if self._editor is not None:
            self._editor.set_dark_mode()

    def set_light_mode(self) -> None:
        if self._editor is not None:
            self._editor.set_light_mode()

    # ------------------------------------------------------------------
    # Navigation — always over the working tree
    # ------------------------------------------------------------------

    def navigate_to_block(self, block: Block) -> None:
        """
        Navigate into a child block: prepare it in-place, update state,
        recreate the editor, and refresh the breadcrumb.

        No new copy is created; the block already lives in the working tree.

        :param block: Child block to navigate into.
        :return: None.
        """
        prepare_block_for_editing(block, self._var_factory)
        self._navigation.open_child(block)
        self._replace_editor()

    def navigate_to_breadcrumb_block(self, block: Block) -> None:
        """
        Navigate to a specific ancestor block via breadcrumb click.

        :param block: An ancestor block in the current path.
        :return: None.
        """
        self._navigation.go_to(block)
        self._replace_editor()

    def navigate_to_root(self) -> None:
        """Navigate back to the root block."""
        self._navigation.go_to_root()
        self._replace_editor()

    # ------------------------------------------------------------------
    # Editor delegation — forward commonly accessed attributes
    # ------------------------------------------------------------------

    @property
    def editor(self) -> "DynamicBlockEditorGUI | None":
        return self._editor

    @property
    def is_root_editor(self) -> bool:
        return self._navigation.is_root()

    @property
    def root_block(self) -> Block:
        return self._document.working_root_block

    @property
    def current_block(self) -> Block:
        return self._navigation.current_block

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _create_editor(self, block: Block) -> None:
        from VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor import DynamicBlockEditorGUI

        self._editor = DynamicBlockEditorGUI(
            var_factory=self._var_factory,
            root_block=self._document.working_root_block,
            current_block=block,
            api_object=self._api_object,
            circuit=self._circuit,
            mode=self._mode,
            templates_list=self._templates_list,
            is_root_editor=self._navigation.is_root(),
            modal=False,
            workspace_embedded=True,
            document=self._document,
        )
        self._editor.set_navigate_callback(self.navigate_to_block)
        self._editor.dirtyStateChanged.connect(self.dirtyStateChanged)
        self._layout.addWidget(self._editor)
        self._refresh_breadcrumb()

    def _replace_editor(self) -> None:
        if self._editor is not None:
            self._editor.prepare_to_delete()
            self._layout.removeWidget(self._editor)
            self._editor.deleteLater()
            self._editor = None

        self._create_editor(self._navigation.current_block)

    def _refresh_breadcrumb(self) -> None:
        path: List[Block] = self._navigation.breadcrumb_path()
        self._breadcrumb.set_path(path)

    def _on_breadcrumb_clicked(self, block: Block) -> None:
        self.navigate_to_breadcrumb_block(block)
