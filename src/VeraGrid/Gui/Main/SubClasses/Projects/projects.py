# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import sys
import uuid
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List, Iterable

import requests
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QPushButton,
    QVBoxLayout,
    QSplitter,
    QMessageBox,
)
from PySide6.QtGui import Qt
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

from VeraGridEngine.IO.file_system import get_create_veragrid_folder
from VeraGridEngine.IO.file_system import scripts_path
from VeraGrid.Gui.Main.SubClasses.Scripting.scripting import ScriptingMain
from VeraGrid.Gui.gui_functions import CustomFileSystemModel
import VeraGrid.Gui.gui_functions as gf
from VeraGrid.Gui.messages import error_msg, yes_no_question
from VeraGrid.Gui.Main.SubClasses.Projects.projects_logic import GridEntry, GridDatabase, GridDownloadWorker


class ProjectsMain(ScriptingMain):
    """
    Diagrams Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        ScriptingMain.__init__(self, parent)

        folder = Path(get_create_veragrid_folder()) / "projects"
        self.db = GridDatabase(Path(folder) / "projects")
        self.cache_dir = folder / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.worker: Optional[GridDownloadWorker] = None
        self.entries: Dict[str, GridEntry] = dict()

        self.ui.projectTreeWidget.currentItemChanged.connect(self._on_select)
        self.ui.projectTreeWidget.itemDoubleClicked.connect(self._on_double_click)
        # self.load_btn.clicked.connect(self._on_load_clicked)

        self.reload()

    def reload(self):
        self.ui.projectTreeWidget.clear()
        self.entries.clear()

        categories: Dict[str, QTreeWidgetItem] = {}

        for e in self.db.list_entries():
            self.entries[e.uuid] = e

            if e.category not in categories:
                parent = QTreeWidgetItem([e.category])
                parent.setFirstColumnSpanned(True)
                parent.setFlags(Qt.ItemFlag.ItemIsEnabled)
                parent.setData(0, Qt.ItemDataRole.UserRole, "")
                self.ui.projectTreeWidget.addTopLevelItem(parent)
                categories[e.category] = parent

            item = QTreeWidgetItem([
                e.name,
                "" if e.buses is None else str(e.buses),
                "" if e.branches is None else str(e.branches),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, e.uuid)
            categories[e.category].addChild(item)

        self.ui.projectTreeWidget.expandAll()
        self.ui.projectTreeWidget.resizeColumnToContents(0)

        MAX_NAME_WIDTH = 300  # pixels

        header = self.ui.projectTreeWidget.header()
        current_width = header.sectionSize(0)

        if current_width > MAX_NAME_WIDTH:
            header.resizeSection(0, MAX_NAME_WIDTH)

        header.setSectionResizeMode(0, header.ResizeMode.Interactive)

    def _entry_from_item(self, item: Optional[QTreeWidgetItem]) -> Optional[GridEntry]:
        if not item:
            return None
        uid = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(uid, str) or not uid:
            return None
        return self.entries.get(uid)

    def _on_select(self, current, _previous):
        entry = self._entry_from_item(current)
        if not entry:
            self.ui.projectTableWidget.setRowCount(0)
            self.ui.projectsTextEdit.clear()
            return

        rows = [
            ("UUID", entry.uuid),
            ("Name", entry.name),
            ("Category", entry.category),
            ("Source", entry.source()),
            ("Buses", entry.buses),
            ("Branches", entry.branches),
            ("Path", str(entry.resolved_path(self.cache_dir))),
            ("Available", "Yes" if entry.is_available(self.cache_dir) else "No"),
        ]

        self.ui.projectsTableView.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.ui.projectTableWidget.setItem(i, 0, QTableWidgetItem(str(k)))
            self.ui.projectTableWidget.setItem(i, 1, QTableWidgetItem("" if v is None else str(v)))

        self.ui.projectTableWidget.resizeRowsToContents()
        self.ui.projectsTextEdit.clear()

    def _on_double_click(self, item, _column):
        entry = self._entry_from_item(item)
        if entry:
            self._load_or_download(entry)

    def _on_load_clicked(self):
        entry = self._entry_from_item(self.ui.projectTreeWidget.currentItem())
        if entry:
            self._load_or_download(entry)

    def _load_or_download(self, entry: GridEntry):
        if self.worker:
            return

        if entry.is_available(self.cache_dir):
            return

        if not entry.remote_url:
            QMessageBox.warning(
                self,
                "Grid unavailable",
                "This grid has no local file and no remote URL.",
            )
            return

        self.worker = GridDownloadWorker(entry, self.cache_dir, parent=self)
        self.worker.finished.connect(self._on_download_finished)
        self.worker.error.connect(self._on_download_error)
        self.worker.start()

    def _on_download_finished(self, _uuid: str):
        self.worker = None
        self._on_select(self.ui.projectTreeWidget.currentItem(), None)

    def _on_download_error(self, msg: str):
        self.worker = None
        QMessageBox.critical(self, "Download error", msg)

    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(3000)
        event.accept()


