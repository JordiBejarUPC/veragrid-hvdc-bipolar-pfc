# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.DynamicModelEditor.dyn_editor_multiwindow_engine import DetachableEditorTabWidget
from VeraGrid.Gui.DynamicModelEditor.dyn_editor_multiwindow_engine import DynamicEditorEntry
from VeraGrid.Gui.DynamicModelEditor.dyn_editor_multiwindow_engine import build_dynamic_editor_entry
from VeraGrid.Gui.DynamicModelEditor.dyn_editor_multiwindow_engine import get_block_for_entry
from VeraGrid.Gui.DynamicModelEditor.dyn_editor_multiwindow_engine import get_templates_for_entry
from VeraGrid.Gui.DynamicModelEditor.dyn_editor_multiwindow_engine import iter_dynamic_editor_entries
from VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_workspace import Ui_DynamicEditorWorkspaceWindow
from VeraGrid.Gui.gui_functions import add_menu_entry
from VeraGridEngine.enumerations import DynamicSimulationMode


_ACTIVE_DYNAMIC_EDITOR_SESSIONS: list["DynamicEditorWorkspaceSession"] = list()


def _get_page_entry(page: QtWidgets.QWidget | None) -> DynamicEditorEntry | None:
    """
    Return the cached dynamic-editor entry stored on one page widget.

    :param page: Candidate workspace page.
    :return: Cached entry or ``None`` when unavailable.
    """
    if page is None:
        return None
    entry = getattr(page, "_dynamic_editor_entry", None)
    if isinstance(entry, DynamicEditorEntry):
        return entry
    return None


def _get_page_mode(page: QtWidgets.QWidget | None) -> DynamicSimulationMode | None:
    """
    Return the cached dynamic-editor mode stored on one page widget.

    :param page: Candidate workspace page.
    :return: Cached mode or ``None`` when unavailable.
    """
    if page is None:
        return None
    mode = getattr(page, "_dynamic_editor_mode", None)
    if isinstance(mode, DynamicSimulationMode):
        return mode
    return None


class DynamicEditorWorkspaceSession(QtCore.QObject):
    """
    Shared state for one family of detachable workspace windows.
    """

    def __init__(self) -> None:
        """
        Initialize the shared session state for one workspace family.

        :return: None.
        """
        super().__init__()
        self._open_workspaces: list[DynamicEditorWorkspaceWindow] = list()
        self._session_pages: dict[str, DynamicBlockEditorGUI] = dict()
        self._last_mode_by_key_base: dict[str, DynamicSimulationMode] = dict()
        self._last_active_workspace: DynamicEditorWorkspaceWindow | None = None
        self._pending_drag_page: DynamicBlockEditorGUI | None = None
        self._pending_drag_workspace: DynamicEditorWorkspaceWindow | None = None
        self._retained_workspaces: list[DynamicEditorWorkspaceWindow] = list()
        self._retained_pages: list[DynamicBlockEditorGUI] = list()

    def register_workspace(self, workspace: "DynamicEditorWorkspaceWindow") -> None:
        """
        Register one live workspace window in this shared session.

        :param workspace: Workspace to register.
        :return: None.
        """
        if workspace not in self._open_workspaces:
            self._open_workspaces.append(workspace)
        if workspace not in self._retained_workspaces:
            self._retained_workspaces.append(workspace)
        self._last_active_workspace = workspace
        if self not in _ACTIVE_DYNAMIC_EDITOR_SESSIONS:
            _ACTIVE_DYNAMIC_EDITOR_SESSIONS.append(self)

    def unregister_workspace(self, workspace: "DynamicEditorWorkspaceWindow") -> None:
        """
        Remove one workspace window from this shared session.

        :param workspace: Workspace to unregister.
        :return: None.
        """
        if workspace in self._open_workspaces:
            self._open_workspaces.remove(workspace)
        if self._last_active_workspace is workspace:
            self._last_active_workspace = self._open_workspaces[-1] if self._open_workspaces else None
        if len(self._open_workspaces) == 0 and self in _ACTIVE_DYNAMIC_EDITOR_SESSIONS:
            _ACTIVE_DYNAMIC_EDITOR_SESSIONS.remove(self)

    def get_open_workspaces(self) -> list["DynamicEditorWorkspaceWindow"]:
        """
        Return the currently open workspaces belonging to this session.

        :return: Open workspaces for this session.
        """
        return list(self._open_workspaces)

    def get_last_active_workspace(self) -> "DynamicEditorWorkspaceWindow | None":
        """
        Return the workspace that should receive newly opened editor tabs.

        :return: Preferred workspace or ``None`` when no window is open.
        """
        if self._last_active_workspace is not None:
            return self._last_active_workspace
        if len(self._open_workspaces) > 0:
            return self._open_workspaces[-1]
        return None

    def reset_for_tests(self) -> None:
        """
        Close every workspace and clear all retained session state.

        :return: None.
        """
        for workspace in list(self._open_workspaces):
            workspace.close()
            workspace.deleteLater()

        app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
        if app is not None:
            app.processEvents()

        self._open_workspaces.clear()
        self._session_pages.clear()
        self._last_mode_by_key_base.clear()
        self._last_active_workspace = None
        self._pending_drag_page = None
        self._pending_drag_workspace = None
        self._retained_workspaces.clear()
        self._retained_pages.clear()
        if self in _ACTIVE_DYNAMIC_EDITOR_SESSIONS:
            _ACTIVE_DYNAMIC_EDITOR_SESSIONS.remove(self)

    def workspace_for_page(self, page: QtWidgets.QWidget) -> "DynamicEditorWorkspaceWindow | None":
        """
        Locate the workspace that currently owns one editor page.

        :param page: Page to resolve.
        :return: Owning workspace or ``None``.
        """
        window = page.window()
        if isinstance(window, DynamicEditorWorkspaceWindow) and window.session is self and window.index_of_page(page) >= 0:
            return window

        workspace: DynamicEditorWorkspaceWindow
        for workspace in self._open_workspaces:
            if workspace.index_of_page(page) >= 0:
                return workspace

        return None

    def note_page_activated(self, page: QtWidgets.QWidget) -> None:
        """
        Record the active page so reopen operations reuse the right mode and window.

        :param page: Newly activated page.
        :return: None.
        """
        entry = _get_page_entry(page)
        mode = _get_page_mode(page)
        workspace = self.workspace_for_page(page)
        if entry is not None and mode is not None:
            self._last_mode_by_key_base[entry.key_base] = mode
        if workspace is not None:
            self._last_active_workspace = workspace

    def build_page_tab_title(self, page: QtWidgets.QWidget) -> str:
        """
        Build the tab title shown for one page, including dirty-state marker.

        :param page: Page whose title will be shown.
        :return: User-facing tab title.
        """
        if isinstance(page, DynamicBlockEditorGUI):
            title = page.get_dynamic_editor_display_title()
        else:
            title = page.windowTitle() or "Dynamic object"
        if getattr(page, "has_unapplied_changes", False):
            return f"* {title}"
        return title

    def refresh_open_page_title(self, page: QtWidgets.QWidget) -> None:
        """
        Refresh the tab title for one open page if its workspace is still alive.

        :param page: Page whose title should be refreshed.
        :return: None.
        """
        workspace = self.workspace_for_page(page)
        if workspace is not None:
            workspace.set_page_tab_title(page, self.build_page_tab_title(page))

    def connect_page_signals(self, page: DynamicBlockEditorGUI) -> None:
        """
        Connect long-lived page signals needed by the workspace session.

        :param page: Editor page whose signals will be connected.
        :return: None.
        """
        page.dirtyStateChanged.connect(self._on_page_dirty_state_changed)

    def _on_page_dirty_state_changed(self, _dirty: bool) -> None:
        """
        Refresh the sender page title after its dirty state changes.

        :param _dirty: New dirty-state flag emitted by the page.
        :return: None.
        """
        page = self.sender()
        if isinstance(page, QtWidgets.QWidget):
            self.refresh_open_page_title(page)

    def create_workspace(self, global_pos: QtCore.QPoint | None = None) -> "DynamicEditorWorkspaceWindow":
        """
        Create, show, and register a new workspace window for this session.

        :param global_pos: Optional top-left window position.
        :return: Newly created workspace window.
        """
        workspace = DynamicEditorWorkspaceWindow(session=self)
        if global_pos is not None:
            workspace.move(global_pos)
        workspace.show()
        workspace.raise_()
        workspace.activateWindow()
        return workspace

    def resolve_workspace(
        self,
        preferred_workspace: "DynamicEditorWorkspaceWindow | None" = None,
    ) -> "DynamicEditorWorkspaceWindow":
        """
        Return the workspace that should receive a newly opened editor page.

        :param preferred_workspace: Explicit target workspace, if any.
        :return: Workspace that should host the new page.
        """
        if preferred_workspace is not None:
            self._last_active_workspace = preferred_workspace
            return preferred_workspace
        workspace = self.get_last_active_workspace()
        if workspace is not None:
            return workspace
        return self.create_workspace()

    def resolve_mode(
        self,
        entry: DynamicEditorEntry,
        preferred_mode: DynamicSimulationMode | None = None,
    ) -> DynamicSimulationMode:
        """
        Choose the dynamic mode to open for one entry.

        :param entry: Entry being opened.
        :param preferred_mode: Explicit requested mode, if any.
        :return: Mode that should be opened.
        """
        if preferred_mode is not None:
            return preferred_mode
        last_mode = self._last_mode_by_key_base.get(entry.key_base, None)
        if last_mode is not None and last_mode in entry.available_modes:
            return last_mode
        if DynamicSimulationMode.RMS in entry.available_modes:
            return DynamicSimulationMode.RMS
        return entry.available_modes[0]

    def create_page(self, entry: DynamicEditorEntry, mode: DynamicSimulationMode) -> DynamicBlockEditorGUI:
        """
        Instantiate one embedded block editor for the requested entry and mode.

        :param entry: Entry being edited.
        :param mode: Dynamic mode to open.
        :return: Newly created embedded editor page.
        """
        page = DynamicBlockEditorGUI(
            var_factory=entry.circuit.var_factory,
            block=get_block_for_entry(entry, mode),
            api_object=entry.api_object,
            mode=mode,
            templates_list=get_templates_for_entry(entry, mode),
            circuit=entry.circuit,
            main_editor=True,
            modal=False,
            workspace_embedded=True,
        )
        page._dynamic_editor_entry = entry
        page._dynamic_editor_mode = mode
        self.connect_page_signals(page)
        self._retained_pages.append(page)
        return page

    def open_entry(
        self,
        entry: DynamicEditorEntry,
        preferred_mode: DynamicSimulationMode | None = None,
        target_workspace: "DynamicEditorWorkspaceWindow | None" = None,
    ) -> DynamicBlockEditorGUI:
        """
        Open one entry in the session, reusing an existing page when possible.

        :param entry: Entry to open.
        :param preferred_mode: Explicit requested mode, if any.
        :param target_workspace: Preferred destination workspace.
        :return: Open editor page for the requested entry.
        """
        mode = self.resolve_mode(entry, preferred_mode)
        session_key = entry.session_key(mode)
        existing_page = self._session_pages.get(session_key, None)
        if existing_page is not None:
            workspace = self.workspace_for_page(existing_page)
            if workspace is None:
                self.unregister_page(existing_page)
            else:
                workspace.editor_tabs.setCurrentWidget(existing_page)
                workspace.showNormal()
                workspace.raise_()
                workspace.activateWindow()
                self.note_page_activated(existing_page)
                return existing_page

        workspace = self.resolve_workspace(target_workspace)
        page = self.create_page(entry, mode)
        self._session_pages[session_key] = page
        self._last_mode_by_key_base[entry.key_base] = mode
        workspace.add_editor_page(page, self.build_page_tab_title(page), activate=True)
        self._last_active_workspace = workspace
        return page

    def open_dynamic_editor_for(
        self,
        api_object: Any,
        circuit: Any,
        preferred_mode: DynamicSimulationMode | None = None,
        target_workspace: "DynamicEditorWorkspaceWindow | None" = None,
    ) -> DynamicBlockEditorGUI | None:
        """
        Build and open the dynamic-editor entry for one API object.

        :param api_object: Device or template to edit.
        :param circuit: Circuit that owns the device.
        :param preferred_mode: Explicit requested mode, if any.
        :param target_workspace: Preferred destination workspace.
        :return: Open editor page or ``None`` when no dynamic editor exists.
        """
        entry = build_dynamic_editor_entry(api_object, circuit)
        if entry is None:
            return None
        return self.open_entry(entry, preferred_mode=preferred_mode, target_workspace=target_workspace)

    def unregister_page(self, page: QtWidgets.QWidget) -> None:
        """
        Forget one page in the session registries.

        :param page: Page being removed.
        :return: None.
        """
        entry = _get_page_entry(page)
        mode = _get_page_mode(page)
        if entry is not None and mode is not None:
            self._session_pages.pop(entry.session_key(mode), None)

        if self._pending_drag_page is page:
            self._pending_drag_page = None
            self._pending_drag_workspace = None

    def handle_tab_drag_started(self, workspace: "DynamicEditorWorkspaceWindow", index: int) -> None:
        """
        Remember which page started a detach or reattach drag gesture.

        :param workspace: Source workspace.
        :param index: Dragged tab index.
        :return: None.
        """
        page = workspace.page_at(index)
        if isinstance(page, DynamicBlockEditorGUI):
            self._pending_drag_page = page
            self._pending_drag_workspace = workspace

    def handle_tab_detach(self, global_pos: QtCore.QPoint) -> None:
        """
        Move the dragged page into a newly created workspace window.

        :param global_pos: Screen position where the new window should appear.
        :return: None.
        """
        page = self._pending_drag_page
        source_workspace = self._pending_drag_workspace
        if page is None or source_workspace is None:
            return

        source_workspace.remove_page(page)
        new_workspace = self.create_workspace(global_pos)
        if source_workspace._current_circuit is not None:
            new_workspace._set_workspace_circuit(source_workspace._current_circuit)
        new_workspace.add_editor_page(page, self.build_page_tab_title(page), activate=True)
        if source_workspace.editor_tabs.count() == 0:
            source_workspace.close()
        self._last_active_workspace = new_workspace
        self._pending_drag_page = None
        self._pending_drag_workspace = None

    def handle_tab_reattach(
        self,
        target_workspace: "DynamicEditorWorkspaceWindow",
        target_index: int,
    ) -> None:
        """
        Move the dragged page into another existing workspace window.

        :param target_workspace: Destination workspace.
        :param target_index: Destination tab index.
        :return: None.
        """
        page = self._pending_drag_page
        source_workspace = self._pending_drag_workspace
        if page is None or source_workspace is None:
            return

        if source_workspace is target_workspace:
            self._pending_drag_page = None
            self._pending_drag_workspace = None
            return

        if source_workspace._current_circuit is not None:
            target_workspace._set_workspace_circuit(source_workspace._current_circuit)
        source_workspace.remove_page(page)
        target_workspace.add_editor_page(page, self.build_page_tab_title(page), activate=True, insert_index=target_index)
        if source_workspace.editor_tabs.count() == 0:
            source_workspace.close()
        target_workspace.showNormal()
        target_workspace.raise_()
        target_workspace.activateWindow()
        self._last_active_workspace = target_workspace
        self._pending_drag_page = None
        self._pending_drag_workspace = None


class DynamicEditorWorkspaceWindow(QtWidgets.QMainWindow):
    """
    Tabbed workspace hosting one or more dynamic editor pages.
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        session: DynamicEditorWorkspaceSession | None = None,
    ) -> None:
        """
        Initialize one dynamic-editor workspace window.

        :param parent: Optional Qt parent widget.
        :param session: Optional shared workspace session.
        :return: None.
        """
        super().__init__(parent)
        self.__session = session if session is not None else DynamicEditorWorkspaceSession()
        self._current_circuit: Any | None = None
        self._tree_model = QtGui.QStandardItemModel(self)
        self._tree_proxy = QtCore.QSortFilterProxyModel(self)
        self._tree_proxy.setRecursiveFilteringEnabled(True)
        self._tree_proxy.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self._tree_proxy.setSourceModel(self._tree_model)
        self.ui = Ui_DynamicEditorWorkspaceWindow()
        self.ui.setupUi(self)

        self.ui.splitter.setStretchFactor(0, 1)
        self.ui.splitter.setStretchFactor(1, 10)

        self.editor_tabs = DetachableEditorTabWidget(self)
        self.ui.editorFrameLayout.addWidget(self.editor_tabs)
        self.ui.editorTabs = self.editor_tabs

        self.editor_tabs.tabCloseRequested.connect(self.close_tab_at)
        self.editor_tabs.currentChanged.connect(self._on_current_tab_changed)
        self.editor_tabs.tabDragStarted.connect(self._on_tab_drag_started)
        self.editor_tabs.detachRequested.connect(self._on_tab_detach_requested)
        self.editor_tabs.reattachRequested.connect(self._on_tab_reattach_requested)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.session.register_workspace(self)
        self._refresh_window_title()

        self.ui.actionview_tree.triggered.connect(self.show_hide_tree)
        self.ui.block_editor_actionCheckModel.triggered.connect(self.open_inspect_dialog)
        self.ui.actionCenter.triggered.connect(self.center_view_on_items)
        self.ui.actionZoom_in.triggered.connect(self.zoom_in_view)
        self.ui.actionZoom_out.triggered.connect(self.zoom_out_view)
        self.ui.action_delete_all.triggered.connect(self.delete_all_blocks_with_confirmation)
        self.ui.actionValidate.triggered.connect(self.show_model_consistency_validation)
        self.ui.treeView.setModel(self._tree_proxy)
        self.ui.treeView.setHeaderHidden(True)
        self.ui.treeView.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.ui.treeView.doubleClicked.connect(self._on_tree_double_clicked)
        self.ui.treeView.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.ui.searchInTreeLineEdit.textChanged.connect(self._apply_tree_filter)
        self.ui.searchInTreeButton.clicked.connect(self._expand_tree_matches)

    def get_open_workspaces(self) -> list["DynamicEditorWorkspaceWindow"]:
        """
        Return the open workspaces that share this window session.

        :return: Open workspaces for this session.
        """
        return self.session.get_open_workspaces()

    @property
    def session(self) -> DynamicEditorWorkspaceSession:
        """
        Return the shared session that coordinates this workspace family.

        :return: Shared workspace session.
        """
        return self.__session

    def workspace_for_page(self, page: QtWidgets.QWidget) -> "DynamicEditorWorkspaceWindow | None":
        """
        Return the workspace in this session that owns one page.

        :param page: Page to resolve.
        :return: Owning workspace or ``None``.
        """
        return self.session.workspace_for_page(page)

    def note_page_activated(self, page: QtWidgets.QWidget) -> None:
        """
        Forward page-activation bookkeeping to the shared session.

        :param page: Newly activated page.
        :return: None.
        """
        self.session.note_page_activated(page)

    def open_entry(
        self,
        entry: DynamicEditorEntry,
        preferred_mode: DynamicSimulationMode | None = None,
        target_workspace: "DynamicEditorWorkspaceWindow | None" = None,
    ) -> DynamicBlockEditorGUI:
        """
        Open one editor entry in this workspace session.

        :param entry: Entry to open.
        :param preferred_mode: Explicit requested mode, if any.
        :param target_workspace: Preferred destination workspace.
        :return: Open editor page for the requested entry.
        """
        target = target_workspace if target_workspace is not None else self
        target._set_workspace_circuit(entry.circuit)
        return self.session.open_entry(
            entry,
            preferred_mode=preferred_mode,
            target_workspace=target,
        )

    def open_dynamic_editor_for(
        self,
        api_object: Any,
        circuit: Any,
        preferred_mode: DynamicSimulationMode | None = None,
        target_workspace: "DynamicEditorWorkspaceWindow | None" = None,
    ) -> DynamicBlockEditorGUI | None:
        """
        Open the dynamic editor for one API object in this workspace session.

        :param api_object: Device or template to edit.
        :param circuit: Circuit that owns the device.
        :param preferred_mode: Explicit requested mode, if any.
        :param target_workspace: Preferred destination workspace.
        :return: Open editor page or ``None`` when no dynamic editor exists.
        """
        entry = build_dynamic_editor_entry(api_object, circuit)
        if entry is None:
            return None
        return self.open_entry(
            entry,
            preferred_mode=preferred_mode,
            target_workspace=target_workspace,
        )

    def show_hide_tree(self):
        """
        Toggle visibility of the device tree panel.

        :return: None.
        """
        self.ui.treeFrame.setVisible(not self.ui.treeFrame.isVisible())

    def set_tree_visible(self, visible: bool) -> None:
        """
        Set visibility of the device tree panel explicitly.

        :param visible: Desired visibility state.
        :return: None.
        """
        self.ui.treeFrame.setVisible(visible)

    def get_current_block_editor(self) -> DynamicBlockEditorGUI | None:
        """
        Return the currently selected block editor tab, if any.

        :return: Active block editor or ``None``.
        """
        page = self.current_page()
        if isinstance(page, DynamicBlockEditorGUI):
            return page
        return None

    def open_inspect_dialog(self):
        """
        Open the inspect dialog on the active block editor.

        :return: None.
        """
        editor = self.get_current_block_editor()
        if editor is not None:
            editor.open_inspect_dialog()

    def center_view_on_items(self):
        """
        Center the active block editor view on its scene items.

        :return: None.
        """
        editor = self.get_current_block_editor()
        if editor is not None:
            editor.center_view_on_items()

    def zoom_in_view(self):
        """
        Zoom in the active block editor view.

        :return: None.
        """
        editor = self.get_current_block_editor()
        if editor is not None:
            editor.zoom_in_view()

    def zoom_out_view(self):
        """
        Zoom out the active block editor view.

        :return: None.
        """
        editor = self.get_current_block_editor()
        if editor is not None:
            editor.zoom_out_view()

    def delete_all_blocks_with_confirmation(self):
        """
        Delete all blocks from the active editor after confirmation.

        :return: None.
        """
        editor = self.get_current_block_editor()
        if editor is not None:
            editor.delete_all_blocks_with_confirmation()

    def show_model_consistency_validation(self):
        """
        Run the model-consistency validation on the active editor.

        :return: None.
        """
        editor = self.get_current_block_editor()
        if editor is not None:
            editor.show_model_consistency_validation()

    def _set_workspace_circuit(self, circuit: Any) -> None:
        """
        Bind this workspace tree to one circuit and rebuild its contents.

        :param circuit: Circuit to display in the tree.
        :return: None.
        """
        if self._current_circuit is circuit:
            return
        self._current_circuit = circuit
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        """
        Rebuild the left-side device tree from the current circuit.

        :return: None.
        """
        self._tree_model.clear()
        root = self._tree_model.invisibleRootItem()
        if self._current_circuit is None:
            return

        groups: dict[str, QtGui.QStandardItem] = dict()
        entries = sorted(
            iter_dynamic_editor_entries(self._current_circuit),
            key=self._entry_sort_key,
        )

        entry: DynamicEditorEntry
        for entry in entries:
            group_item = groups.get(entry.type_label)
            if group_item is None:
                group_item = QtGui.QStandardItem(entry.type_label)
                group_item.setEditable(False)
                groups[entry.type_label] = group_item
                root.appendRow(group_item)

            item = QtGui.QStandardItem(entry.display_name)
            item.setEditable(False)
            item.setData(entry, QtCore.Qt.ItemDataRole.UserRole)
            item.setToolTip(entry.display_name)
            group_item.appendRow(item)

        self._apply_tree_filter(self.ui.searchInTreeLineEdit.text())

    @staticmethod
    def _entry_sort_key(entry: DynamicEditorEntry) -> tuple[str, str]:
        """
        Return the sorting key used for tree entries.

        :param entry: Entry to sort.
        :return: Lowercase type and name tuple.
        """
        return entry.type_label.lower(), entry.display_name.lower()

    def _apply_tree_filter(self, text: str) -> None:
        """
        Apply the current search text to the device tree.

        :param text: Search text entered by the user.
        :return: None.
        """
        needle = text.strip()
        if needle == "":
            self._tree_proxy.setFilterRegularExpression(QtCore.QRegularExpression())
        else:
            regex = QtCore.QRegularExpression(
                QtCore.QRegularExpression.escape(needle),
                QtCore.QRegularExpression.PatternOption.CaseInsensitiveOption,
            )
            self._tree_proxy.setFilterRegularExpression(regex)
        self._expand_tree_matches()
        self._select_first_tree_match()

    def _expand_tree_matches(self) -> None:
        """
        Expand the device tree so current matches remain visible.

        :return: None.
        """
        self.ui.treeView.expandAll()

    def _select_first_tree_match(self) -> None:
        """
        Select the first visible device entry after filtering.

        :return: None.
        """
        index = self._first_visible_tree_entry_index()
        if index.isValid():
            self.ui.treeView.setCurrentIndex(index)
            self.ui.treeView.scrollTo(index)

    def _first_visible_tree_entry_index(
        self,
        parent: QtCore.QModelIndex = QtCore.QModelIndex(),
    ) -> QtCore.QModelIndex:
        """
        Return the first visible device-entry index under one tree node.

        :param parent: Parent index to search below.
        :return: First visible matching device index, if any.
        """
        row_count = self._tree_proxy.rowCount(parent)
        row: int
        for row in range(row_count):
            index = self._tree_proxy.index(row, 0, parent)
            if self._entry_from_tree_index(index) is not None:
                return index
            child_index = self._first_visible_tree_entry_index(index)
            if child_index.isValid():
                return child_index
        return QtCore.QModelIndex()

    def _entry_from_tree_index(self, index: QtCore.QModelIndex) -> DynamicEditorEntry | None:
        """
        Resolve one visible tree index back to its dynamic-editor entry.

        :param index: Visible proxy-model index.
        :return: Backing entry or ``None``.
        """
        source_index = self._tree_proxy.mapToSource(index)
        if not source_index.isValid():
            return None
        data = self._tree_model.data(source_index, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(data, DynamicEditorEntry):
            return data
        return None

    def _get_tree_entry_modes(self, index: QtCore.QModelIndex) -> tuple[DynamicSimulationMode, ...]:
        """
        Return the modes supported by the tree entry at one index.

        :param index: Visible proxy-model index.
        :return: Supported dynamic modes for that entry.
        """
        entry = self._entry_from_tree_index(index)
        if entry is None:
            return tuple()
        return entry.available_modes

    def _open_tree_entry(self, index: QtCore.QModelIndex, mode: DynamicSimulationMode) -> DynamicBlockEditorGUI | None:
        """
        Open one tree entry in the requested dynamic mode.

        :param index: Visible proxy-model index.
        :param mode: Requested dynamic mode.
        :return: Open editor page or ``None`` when opening is invalid.
        """
        entry = self._entry_from_tree_index(index)
        if entry is None or mode not in entry.available_modes:
            return None
        return self.open_entry(entry, preferred_mode=mode, target_workspace=self)

    def _on_tree_double_clicked(self, index: QtCore.QModelIndex) -> None:
        """
        Open the double-clicked tree entry in RMS mode.

        :param index: Double-clicked tree index.
        :return: None.
        """
        self._open_tree_entry(index, DynamicSimulationMode.RMS)

    def _show_tree_context_menu(self, position: QtCore.QPoint) -> None:
        """
        Show the RMS/EMT context menu for the tree entry under the cursor.

        :param position: Tree viewport position where the menu was requested.
        :return: None.
        """
        index = self.ui.treeView.indexAt(position)
        entry = self._entry_from_tree_index(index)
        if entry is None:
            return

        menu = QtWidgets.QMenu(self.ui.treeView)
        if DynamicSimulationMode.RMS in entry.available_modes:
            action = add_menu_entry(menu=menu, text="Open RMS", function_ptr=self._open_tree_rms_from_menu)
            action.setData(QtCore.QPersistentModelIndex(index))
        if DynamicSimulationMode.EMT in entry.available_modes:
            action = add_menu_entry(menu=menu, text="Open EMT", function_ptr=self._open_tree_emt_from_menu)
            action.setData(QtCore.QPersistentModelIndex(index))

        if menu.isEmpty():
            return

        menu.exec(self.ui.treeView.viewport().mapToGlobal(position))

    def _open_tree_rms_from_menu(self, _checked: bool = False) -> None:
        """
        Open the tree entry referenced by the sender action in RMS mode.

        :param _checked: QAction checked flag.
        :return: None.
        """
        index = self._tree_menu_index_from_sender()
        if index is not None:
            self._open_tree_entry(index, DynamicSimulationMode.RMS)

    def _open_tree_emt_from_menu(self, _checked: bool = False) -> None:
        """
        Open the tree entry referenced by the sender action in EMT mode.

        :param _checked: QAction checked flag.
        :return: None.
        """
        index = self._tree_menu_index_from_sender()
        if index is not None:
            self._open_tree_entry(index, DynamicSimulationMode.EMT)

    def _tree_menu_index_from_sender(self) -> QtCore.QModelIndex | None:
        """
        Return the tree index stored on the sender context-menu action.

        :return: Stored tree index or ``None``.
        """
        action = self.sender()
        if not isinstance(action, QtGui.QAction):
            return None
        data = action.data()
        if isinstance(data, QtCore.QPersistentModelIndex) and data.isValid():
            return QtCore.QModelIndex(data)
        return None

    def _on_tab_drag_started(self, index: int) -> None:
        """
        Forward tab-drag bookkeeping to the shared session.

        :param index: Dragged tab index.
        :return: None.
        """
        self.session.handle_tab_drag_started(self, index)

    def _on_tab_detach_requested(self, global_pos: QtCore.QPoint) -> None:
        """
        Detach the dragged tab into a new workspace window.

        :param global_pos: Screen position for the new window.
        :return: None.
        """
        self.session.handle_tab_detach(global_pos)

    def _on_tab_reattach_requested(self, _global_pos: QtCore.QPoint | int, target_index: int) -> None:
        """
        Reattach the dragged tab into this workspace window.

        :param _global_pos: Drop position emitted by the tab widget.
        :param target_index: Destination tab index.
        :return: None.
        """
        self.session.handle_tab_reattach(self, target_index)

    def _on_current_tab_changed(self, index: int) -> None:
        """
        Refresh window state after the current tab changes.

        :param index: Newly selected tab index.
        :return: None.
        """
        page = self.page_at(index)
        if page is not None:
            self.note_page_activated(page)
        self._refresh_window_title()

    def add_editor_page(
        self,
        page: QtWidgets.QWidget,
        tab_title: str,
        activate: bool = True,
        insert_index: int = -1,
    ) -> None:
        """
        Insert one editor page into the tab widget.

        :param page: Page widget to insert.
        :param tab_title: Visible tab title.
        :param activate: Whether to activate the inserted page.
        :param insert_index: Target insertion index, or ``-1`` to append.
        :return: None.
        """
        if insert_index < 0 or insert_index > self.editor_tabs.count():
            index = self.editor_tabs.addTab(page, tab_title)
        else:
            index = self.editor_tabs.insertTab(insert_index, page, tab_title)

        if activate:
            self.editor_tabs.setCurrentIndex(index)

        self._refresh_window_title()

    def index_of_page(self, page: QtWidgets.QWidget) -> int:
        """
        Return the tab index for one page, or ``-1`` when absent.

        :param page: Page to locate.
        :return: Tab index or ``-1``.
        """
        return self.editor_tabs.indexOf(page)

    def page_at(self, index: int) -> QtWidgets.QWidget | None:
        """
        Return the page at one tab index.

        :param index: Tab index to inspect.
        :return: Page at that index or ``None``.
        """
        if index < 0 or index >= self.editor_tabs.count():
            return None
        return self.editor_tabs.widget(index)

    def current_page(self) -> QtWidgets.QWidget | None:
        """
        Return the currently selected tab page.

        :return: Current page or ``None``.
        """
        return self.page_at(self.editor_tabs.currentIndex())

    def remove_page(self, page: QtWidgets.QWidget) -> None:
        """
        Remove one page from the tab widget.

        :param page: Page to remove.
        :return: None.
        """
        index = self.index_of_page(page)
        if index >= 0:
            self.editor_tabs.removeTab(index)
        self._refresh_window_title()

    def set_page_tab_title(self, page: QtWidgets.QWidget, title: str) -> None:
        """
        Update the visible tab title for one page.

        :param page: Page whose title should be updated.
        :param title: New visible title.
        :return: None.
        """
        index = self.index_of_page(page)
        if index >= 0:
            self.editor_tabs.setTabText(index, title)
        self._refresh_window_title()

    def close_tab_at(self, index: int) -> None:
        """
        Close the page at one tab index after running close guards.

        :param index: Tab index to close.
        :return: None.
        """
        page = self.page_at(index)
        if page is None:
            return

        can_close = True
        if hasattr(page, "can_close_editor"):
            can_close = bool(page.can_close_editor(self))
        if not can_close:
            return

        self.session.unregister_page(page)
        self.remove_page(page)
        page.deleteLater()

        if self.editor_tabs.count() == 0:
            self.close()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Close the workspace window after checking every open page.

        :param event: Qt close event.
        :return: None.
        """
        for index in range(self.editor_tabs.count() - 1, -1, -1):
            page = self.page_at(index)
            if page is None:
                continue
            if hasattr(page, "can_close_editor") and not bool(page.can_close_editor(self)):
                event.ignore()
                return

        pages = [self.page_at(index) for index in range(self.editor_tabs.count())]
        for page in pages:
            if page is None:
                continue
            self.session.unregister_page(page)

        self.session.unregister_workspace(self)
        event.accept()

    def _refresh_window_title(self) -> None:
        """
        Refresh the top-level window title from the active tab.

        :return: None.
        """
        current_page = self.current_page()
        if current_page is None:
            self.setWindowTitle("Dynamic Editor Workspace")
            return

        current_title = self.editor_tabs.tabText(self.editor_tabs.currentIndex())
        self.setWindowTitle(f"Dynamic Editor - {current_title}")


def get_open_dynamic_editor_workspaces() -> list[DynamicEditorWorkspaceWindow]:
    """
    Return every open dynamic-editor workspace across all active sessions.

    :return: Flattened list of open workspace windows.
    """
    workspaces: list[DynamicEditorWorkspaceWindow] = list()
    session: DynamicEditorWorkspaceSession
    for session in _ACTIVE_DYNAMIC_EDITOR_SESSIONS:
        workspaces.extend(session.get_open_workspaces())
    return workspaces


def reset_dynamic_editor_workspaces_for_tests() -> None:
    """
    Close every tracked workspace and clear global session state.

    :return: None.
    """
    session: DynamicEditorWorkspaceSession
    for session in list(_ACTIVE_DYNAMIC_EDITOR_SESSIONS):
        session.reset_for_tests()


def _get_last_active_dynamic_editor_workspace() -> DynamicEditorWorkspaceWindow | None:
    """
    Return the most recently active dynamic-editor workspace, if any.

    :return: Last active workspace or ``None``.
    """
    session: DynamicEditorWorkspaceSession
    for session in reversed(_ACTIVE_DYNAMIC_EDITOR_SESSIONS):
        workspace = session.get_last_active_workspace()
        if workspace is not None:
            return workspace
    return None


def open_dynamic_editor(
    api_object: Any,
    circuit: Any,
    preferred_mode: DynamicSimulationMode | None = None,
    target_workspace: DynamicEditorWorkspaceWindow | None = None,
    show_tree: bool = False,
) -> DynamicBlockEditorGUI | None:
    """
    Open one dynamic editor, optionally reusing an existing workspace.

    :param api_object: Device or template to edit.
    :param circuit: Circuit that owns the device.
    :param preferred_mode: Explicit requested mode, if any.
    :param target_workspace: Preferred destination workspace.
    :param show_tree: Whether the destination workspace should show its tree panel.
    :return: Open editor page or ``None`` when no dynamic editor exists.
    """

    workspace = target_workspace if target_workspace is not None else _get_last_active_dynamic_editor_workspace()
    if workspace is None:
        workspace = DynamicEditorWorkspaceWindow()
        workspace.set_tree_visible(show_tree)
        workspace.show()
        workspace.raise_()
        workspace.activateWindow()
    else:
        workspace.set_tree_visible(show_tree)

    return workspace.open_dynamic_editor_for(
        api_object=api_object,
        circuit=circuit,
        preferred_mode=preferred_mode,
        target_workspace=workspace,
    )
