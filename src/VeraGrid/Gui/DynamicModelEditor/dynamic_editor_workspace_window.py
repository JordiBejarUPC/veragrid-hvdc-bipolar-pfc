# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.DynamicModelEditor.dyn_editor_multiwindow_engine import DynamicEditorAddButton
from VeraGrid.Gui.DynamicModelEditor.dyn_editor_multiwindow_engine import DetachableEditorTabWidget
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_workspace import Ui_DynamicEditorWorkspaceWindow

from VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor import DynamicBlockEditorGUI

if TYPE_CHECKING:
    from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_workspace_manager import DynamicEditorWorkspaceManager


class DynamicEditorWorkspaceWindow(QtWidgets.QMainWindow):
    """
    Tabbed workspace hosting one or more dynamic editor pages.
    """

    def __init__(self, manager: DynamicEditorWorkspaceManager, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.ui = Ui_DynamicEditorWorkspaceWindow()
        self.ui.setupUi(self)

        self.manager: DynamicEditorWorkspaceManager = manager

        self.ui.splitter.setStretchFactor(0, 6)
        self.ui.splitter.setStretchFactor(1, 10)

        self.editor_tabs = DetachableEditorTabWidget(self)
        self.ui.editorFrameLayout.addWidget(self.editor_tabs)

        self.editor_tabs.tabCloseRequested.connect(self.close_tab_at)
        self.editor_tabs.currentChanged.connect(self._on_current_tab_changed)
        self.editor_tabs.tabDragStarted.connect(self._on_tab_drag_started)
        self.editor_tabs.detachRequested.connect(self._on_tab_detach_requested)
        self.editor_tabs.reattachRequested.connect(self._on_tab_reattach_requested)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self._refresh_window_title()

        self.ui.actionview_tree.triggered.connect(self.show_hide_tree)
        self.ui.block_editor_actionCheckModel.triggered.connect(self.open_inspect_dialog)
        self.ui.actionCenter.triggered.connect(self.center_view_on_items)
        self.ui.actionZoom_in.triggered.connect(self.zoom_in_view)
        self.ui.actionZoom_out.triggered.connect(self.zoom_out_view)
        self.ui.action_delete_all.triggered.connect(self.delete_all_blocks_with_confirmation)
        self.ui.actionValidate.triggered.connect(self.show_model_consistency_validation)

    def show_hide_tree(self):
        """

        :return:
        """
        self.ui.treeFrame.setVisible(not self.ui.treeFrame.isVisible())

    def get_current_block_editor(self) -> DynamicBlockEditorGUI:

        return self.current_page().children()[0]

    def open_inspect_dialog(self):
        pass

    def center_view_on_items(self):
        pass

    def zoom_in_view(self):
        pass

    def zoom_out_view(self):
        pass

    def delete_all_blocks_with_confirmation(self):
        pass

    def show_model_consistency_validation(self):
        pass

    def _open_picker(self) -> None:
        self.manager.open_picker(self)

    def _on_tab_drag_started(self, index: int) -> None:
        self.manager.handle_tab_drag_started(self, index)

    def _on_tab_detach_requested(self, global_pos: QtCore.QPoint) -> None:
        self.manager.handle_tab_detach(self, global_pos)

    def _on_tab_reattach_requested(self, global_pos: QtCore.QPoint, target_index: int) -> None:
        self.manager.handle_tab_reattach(self, global_pos, target_index)

    def _on_current_tab_changed(self, index: int) -> None:
        page = self.page_at(index)
        if page is not None:
            self.manager.note_page_activated(page)
        else:
            pass
        self._refresh_window_title()

    def add_editor_page(self,
                        page: QtWidgets.QWidget,
                        tab_title: str,
                        activate: bool = True,
                        insert_index: int = -1) -> None:
        if insert_index < 0 or insert_index > self.editor_tabs.count():
            index = self.editor_tabs.addTab(page, tab_title)
        else:
            index = self.editor_tabs.insertTab(insert_index, page, tab_title)

        if activate:
            self.editor_tabs.setCurrentIndex(index)

        self._refresh_window_title()

    def index_of_page(self, page: QtWidgets.QWidget) -> int:
        return self.editor_tabs.indexOf(page)

    def page_at(self, index: int) -> QtWidgets.QWidget | None:
        if index < 0 or index >= self.editor_tabs.count():
            return None
        return self.editor_tabs.widget(index)

    def current_page(self) -> QtWidgets.QWidget | None:
        return self.page_at(self.editor_tabs.currentIndex())

    def remove_page(self, page: QtWidgets.QWidget) -> None:
        index = self.index_of_page(page)
        if index >= 0:
            self.editor_tabs.removeTab(index)
        self._refresh_window_title()

    def set_page_tab_title(self, page: QtWidgets.QWidget, title: str) -> None:
        index = self.index_of_page(page)
        if index >= 0:
            self.editor_tabs.setTabText(index, title)
        self._refresh_window_title()

    def close_tab_at(self, index: int) -> None:
        page = self.page_at(index)
        if page is None:
            return

        can_close = True
        # Todo:remove hasattr
        if hasattr(page, "can_close_editor"):
            can_close = bool(page.can_close_editor(self))
        if not can_close:
            return

        self.manager.unregister_page(page)
        self.remove_page(page)
        page.deleteLater()

        if self.editor_tabs.count() == 0:
            self.close()
        else:
            pass

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        for index in range(self.editor_tabs.count() - 1, -1, -1):
            page = self.page_at(index)
            if page is None:
                continue
            # Todo:remove hasattr
            if hasattr(page, "can_close_editor") and not bool(page.can_close_editor(self)):
                event.ignore()
                return

        pages = [self.page_at(index) for index in range(self.editor_tabs.count())]
        for page in pages:
            if page is None:
                continue
            self.manager.unregister_page(page)

        self.manager.unregister_workspace(self)
        event.accept()

    def _refresh_window_title(self) -> None:
        current_page = self.current_page()
        if current_page is None:
            self.setWindowTitle("Dynamic Editor Workspace")
            return

        current_title = self.editor_tabs.tabText(self.editor_tabs.currentIndex())
        self.setWindowTitle(f"Dynamic Editor - {current_title}")
