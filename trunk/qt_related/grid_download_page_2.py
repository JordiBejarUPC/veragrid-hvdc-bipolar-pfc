#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
from pathlib import Path
import requests

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QLabel,
    QTextEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)


# =============================================================================
# Domain model
# =============================================================================

class GridEntry:
    """
    Represents a power system grid and its downloadable artefacts.
    """

    def __init__(
        self,
        category: str,
        name: str,
        buses: int,
        branches: int,
        filename: str,
        grid_url: str,
        image_url: str | None,
        description_url: str | None,
        base_dir: Path,
    ):
        self.category = category
        self.name = name
        self.buses = buses
        self.branches = branches
        self.filename = filename
        self.grid_url = grid_url
        self.image_url = image_url
        self.description_url = description_url
        self.base_dir = base_dir

    # ---------------------------------------------------------------------

    @property
    def stem(self) -> str:
        return Path(self.filename).stem

    @property
    def grid_path(self) -> Path:
        return self.base_dir / self.filename

    @property
    def image_path(self) -> Path:
        return self.base_dir / f"{self.stem}.png"

    @property
    def description_path(self) -> Path:
        return self.base_dir / f"{self.stem}.txt"


# =============================================================================
# Background worker (simple, no progress)
# =============================================================================

class GridDownloadWorker(QThread):

    finished = Signal(GridEntry)
    error = Signal(str)

    def __init__(self, entry: GridEntry):
        super().__init__()
        self.entry = entry

    def _download_if_missing(self, url: str | None, target: Path):
        if not url or target.exists():
            return

        r = requests.get(url, timeout=60)
        r.raise_for_status()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.content)

    def run(self):
        try:
            self._download_if_missing(self.entry.grid_url, self.entry.grid_path)
            self._download_if_missing(self.entry.image_url, self.entry.image_path)
            self._download_if_missing(self.entry.description_url, self.entry.description_path)
            self.finished.emit(self.entry)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Main window
# =============================================================================

class GridBrowserWindow(QWidget):

    def __init__(self, entries: list[GridEntry]):
        super().__init__()

        self.entries = entries
        self.worker: GridDownloadWorker | None = None

        self.setWindowTitle("Power System Grid Library")
        self.resize(1000, 620)

        # ---------------------------------------------------------------------
        # Widgets
        # ---------------------------------------------------------------------

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Name", "Buses", "Branches"])
        self.tree.setIndentation(18)

        self.image_label = QLabel(alignment=Qt.AlignCenter)
        self.image_label.setMinimumHeight(260)

        self.description = QTextEdit()
        self.description.setReadOnly(True)

        self.load_btn = QPushButton("Download / Load")

        # ---------------------------------------------------------------------
        # Layout
        # ---------------------------------------------------------------------

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.tree)
        left_layout.addWidget(self.load_btn)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.image_label)
        right_layout.addWidget(self.description)

        main_layout = QHBoxLayout(self)
        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 2)

        # ---------------------------------------------------------------------
        # Populate tree
        # ---------------------------------------------------------------------

        self._populate_tree()

        # ---------------------------------------------------------------------
        # Signals
        # ---------------------------------------------------------------------

        self.tree.currentItemChanged.connect(self._on_item_selected)
        self.load_btn.clicked.connect(self._on_download_clicked)

    # -------------------------------------------------------------------------

    def _populate_tree(self):
        categories: dict[str, QTreeWidgetItem] = {}

        for entry in self.entries:
            if entry.category not in categories:
                parent = QTreeWidgetItem([entry.category])
                parent.setFirstColumnSpanned(True)
                parent.setFlags(Qt.ItemIsEnabled)
                self.tree.addTopLevelItem(parent)
                categories[entry.category] = parent

            item = QTreeWidgetItem([
                entry.name,
                str(entry.buses),
                str(entry.branches),
            ])
            item.setData(0, Qt.UserRole, entry)
            categories[entry.category].addChild(item)

        self.tree.expandAll()

    # -------------------------------------------------------------------------

    def _current_entry(self) -> GridEntry | None:
        item = self.tree.currentItem()
        if not item:
            return None
        return item.data(0, Qt.UserRole)

    # -------------------------------------------------------------------------
    # UI actions
    # -------------------------------------------------------------------------

    def _on_item_selected(self, current, _previous):
        entry = self._current_entry()
        if not entry:
            self.image_label.clear()
            self.description.clear()
            return

        self._preview_entry(entry)

    def _on_download_clicked(self):
        entry = self._current_entry()
        if not entry:
            return

        self.load_btn.setEnabled(False)
        self.load_btn.setText("Downloading...")

        self.worker = GridDownloadWorker(entry)
        self.worker.finished.connect(self._on_download_finished)
        self.worker.error.connect(self._on_download_error)
        self.worker.start()

    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------

    def _on_download_finished(self, entry: GridEntry):
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Download / Load")
        self._preview_entry(entry)

    def _on_download_error(self, msg: str):
        QMessageBox.critical(self, "Download error", msg)
        self.load_btn.setEnabled(True)
        self.load_btn.setText("Download / Load")

    # -------------------------------------------------------------------------
    # Preview
    # -------------------------------------------------------------------------

    def _preview_entry(self, entry: GridEntry):
        if entry.image_path.exists():
            pix = QPixmap(str(entry.image_path))
            self.image_label.setPixmap(
                pix.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        else:
            self.image_label.clear()

        if entry.description_path.exists():
            self.description.setPlainText(
                entry.description_path.read_text(encoding="utf-8")
            )
        else:
            self.description.clear()


# =============================================================================
# Entry point
# =============================================================================

def main():
    base_dir = Path("grids")

    entries = [
        GridEntry(
            category="IEEE Test Systems",
            name="IEEE 14 Bus",
            buses=14,
            branches=20,
            filename="ieee14.grid",
            grid_url="https://raw.githubusercontent.com/USER/REPO/main/grids/ieee14.grid",
            image_url="https://raw.githubusercontent.com/USER/REPO/main/grids/ieee14.png",
            description_url="https://raw.githubusercontent.com/USER/REPO/main/grids/ieee14.txt",
            base_dir=base_dir,
        ),
        GridEntry(
            category="IEEE Test Systems",
            name="IEEE 39 Bus",
            buses=39,
            branches=46,
            filename="ieee39.grid",
            grid_url="https://raw.githubusercontent.com/USER/REPO/main/grids/ieee39.grid",
            image_url="https://raw.githubusercontent.com/USER/REPO/main/grids/ieee39.png",
            description_url="https://raw.githubusercontent.com/USER/REPO/main/grids/ieee39.txt",
            base_dir=base_dir,
        ),
    ]

    app = QApplication(sys.argv)
    window = GridBrowserWindow(entries)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()