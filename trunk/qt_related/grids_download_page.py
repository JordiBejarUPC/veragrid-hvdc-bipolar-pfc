#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

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


# =============================================================================
# Domain model (immutable)
# =============================================================================

@dataclass(frozen=True)
class GridEntry:
    uuid: str
    category: str
    name: str
    filename: str
    local_path: Optional[Path]
    remote_url: Optional[str]
    buses: Optional[int]
    branches: Optional[int]

    def resolved_path(self, cache_dir: Path) -> Path:
        return self.local_path if self.local_path else (cache_dir / self.filename)

    def is_available(self, cache_dir: Path) -> bool:
        return self.resolved_path(cache_dir).exists()

    def source(self) -> str:
        if self.local_path:
            return "Local"
        if self.remote_url:
            return "Remote"
        return "Unknown"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert GridEntry to a plain dictionary.
        Paths are converted to strings.
        """
        return {
            "uuid": self.uuid,
            "category": self.category,
            "name": self.name,
            "filename": self.filename,
            "local_path": str(self.local_path) if self.local_path else None,
            "remote_url": self.remote_url,
            "buses": self.buses,
            "branches": self.branches,
        }

    # ------------------------------------------------------------------
    # Deserialization
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GridEntry:
        """
        Create GridEntry from a dictionary.
        Missing UUID is generated automatically.
        """
        return cls(
            uuid=data.get("uuid") or str(uuid.uuid4()),
            category=data["category"],
            name=data["name"],
            filename=data["filename"],
            local_path=Path(data["local_path"]) if data.get("local_path") else None,
            remote_url=data.get("remote_url"),
            buses=data.get("buses"),
            branches=data.get("branches"),
        )

# =============================================================================
# SQLite catalogue (UUID-based, idempotent)
# =============================================================================

class GridDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS grids (
                    uuid TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    local_path TEXT,
                    remote_url TEXT,
                    buses INTEGER,
                    branches INTEGER
                )
                """
            )

    def upsert_from_dict(self, data: Dict[str, Any]) -> str:
        uid = data.get("uuid") or str(uuid.uuid4())
        local_path = data.get("local_path")
        local_path = str(local_path) if local_path else None

        with self._connect() as con:
            con.execute(
                """
                INSERT INTO grids (
                    uuid, category, name, filename,
                    local_path, remote_url, buses, branches
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET
                    category=excluded.category,
                    name=excluded.name,
                    filename=excluded.filename,
                    local_path=excluded.local_path,
                    remote_url=excluded.remote_url,
                    buses=excluded.buses,
                    branches=excluded.branches
                """,
                (
                    uid,
                    data["category"],
                    data["name"],
                    data["filename"],
                    local_path,
                    data.get("remote_url"),
                    data.get("buses"),
                    data.get("branches"),
                ),
            )
        return uid

    def list_entries(self) -> List[GridEntry]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT uuid, category, name, filename,
                       local_path, remote_url, buses, branches
                FROM grids
                ORDER BY category, name
                """
            ).fetchall()

        return [
            GridEntry(
                uuid=r[0],
                category=r[1],
                name=r[2],
                filename=r[3],
                local_path=Path(r[4]) if r[4] else None,
                remote_url=r[5],
                buses=r[6],
                branches=r[7],
            )
            for r in rows
        ]


# =============================================================================
# Background downloader (Qt-safe)
# =============================================================================

class GridDownloadWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, entry: GridEntry, cache_dir: Path, parent: QWidget):
        super().__init__(parent)
        self.entry = entry
        self.cache_dir = cache_dir

    def run(self):
        try:
            if not self.entry.remote_url:
                raise RuntimeError("No remote URL available")

            r = requests.get(self.entry.remote_url, timeout=60)
            r.raise_for_status()

            target = self.entry.resolved_path(self.cache_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(r.content)

            self.finished.emit(self.entry.uuid)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Viewer window (defensive Qt usage)
# =============================================================================

class GridLibraryWindow(QWidget):
    def __init__(self, db: GridDatabase, cache_dir: Path):
        super().__init__()

        self.db = db
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.worker: Optional[GridDownloadWorker] = None
        self.entries: Dict[str, GridEntry] = dict()

        self.setWindowTitle("Grid Library")
        self.resize(1100, 700)

        # ------------------------------------------------------------------
        # UI
        # ------------------------------------------------------------------

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Name", "Buses", "Branches"])
        self.tree.setTextElideMode(Qt.TextElideMode.ElideRight)

        self.load_btn = QPushButton("Download / Load")

        self.meta = QTableWidget(0, 2)
        self.meta.setHorizontalHeaderLabels(["Field", "Value"])
        self.meta.verticalHeader().setVisible(False)
        self.meta.horizontalHeader().setStretchLastSection(True)
        self.meta.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.desc = QTextEdit()
        self.desc.setReadOnly(True)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.addWidget(self.tree)
        ll.addWidget(self.load_btn)

        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self.meta)
        right.addWidget(self.desc)

        main = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(left)
        main.addWidget(right)
        main.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.addWidget(main)

        # ------------------------------------------------------------------
        # Signals (exact Qt signatures)
        # ------------------------------------------------------------------

        self.tree.currentItemChanged.connect(self._on_select)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.load_btn.clicked.connect(self._on_load_clicked)

        self.reload()

    # ------------------------------------------------------------------

    def reload(self):
        self.tree.clear()
        self.entries.clear()

        categories: Dict[str, QTreeWidgetItem] = {}

        for e in self.db.list_entries():
            self.entries[e.uuid] = e

            if e.category not in categories:
                parent = QTreeWidgetItem([e.category])
                parent.setFirstColumnSpanned(True)
                parent.setFlags(Qt.ItemFlag.ItemIsEnabled)
                parent.setData(0, Qt.ItemDataRole.UserRole, "")
                self.tree.addTopLevelItem(parent)
                categories[e.category] = parent

            item = QTreeWidgetItem([
                e.name,
                "" if e.buses is None else str(e.buses),
                "" if e.branches is None else str(e.branches),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, e.uuid)
            categories[e.category].addChild(item)

        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)

        MAX_NAME_WIDTH = 300  # pixels

        header = self.tree.header()
        current_width = header.sectionSize(0)

        if current_width > MAX_NAME_WIDTH:
            header.resizeSection(0, MAX_NAME_WIDTH)

        header.setSectionResizeMode(0, header.ResizeMode.Interactive)

    # ------------------------------------------------------------------

    def _entry_from_item(self, item: Optional[QTreeWidgetItem]) -> Optional[GridEntry]:
        if not item:
            return None
        uid = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(uid, str) or not uid:
            return None
        return self.entries.get(uid)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_select(self, current, _previous):
        entry = self._entry_from_item(current)
        if not entry:
            self.meta.setRowCount(0)
            self.desc.clear()
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

        self.meta.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.meta.setItem(i, 0, QTableWidgetItem(str(k)))
            self.meta.setItem(i, 1, QTableWidgetItem("" if v is None else str(v)))

        self.meta.resizeRowsToContents()
        self.desc.clear()

    def _on_double_click(self, item, _column):
        entry = self._entry_from_item(item)
        if entry:
            self._load_or_download(entry)

    def _on_load_clicked(self):
        entry = self._entry_from_item(self.tree.currentItem())
        if entry:
            self._load_or_download(entry)

    # ------------------------------------------------------------------

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
        self._on_select(self.tree.currentItem(), None)

    def _on_download_error(self, msg: str):
        self.worker = None
        QMessageBox.critical(self, "Download error", msg)

    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait(3000)
        event.accept()


# =============================================================================
# Scanner
# =============================================================================

def scan_grids_folder(root: Path, extensions: Iterable[str] = (".gridcal", ".veragrid", ".m"), ) -> List[GridEntry]:
    """
    Scan a folder recursively and return GridEntry objects.

    Parameters
    ----------
    root : Path
        Root folder containing grid files.
    extensions : iterable of str
        File extensions to consider as grid files.

    Returns
    -------
    List[GridEntry]
    """

    root = root.resolve()
    entries: List[GridEntry] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in extensions:
            continue

        # Category = first directory under root
        try:
            rel = path.relative_to(root)
            category = rel.parts[0] if len(rel.parts) > 1 else "Uncategorized"
        except ValueError:
            category = "Uncategorized"

        entry = GridEntry(
            uuid=str(uuid.uuid4()),
            category=category,
            name=path.stem,
            filename=path.name,
            local_path=path,
            remote_url=None,
            buses=None,
            branches=None,
        )

        entries.append(entry)

    return entries


# =============================================================================
# Entry point
# =============================================================================

def main():
    lib_root = Path.home() / ".grid_library"
    db_path = lib_root / "library.db"
    cache_dir = lib_root / "cache"

    db = GridDatabase(db_path)

    # Example entry (idempotent)
    db.upsert_from_dict({
        "uuid": "9f1b9d9a-0f6c-4a53-bb2a-4a64a5c0c111",
        "category": "IEEE Test Systems",
        "name": "IEEE 14 Bus",
        "filename": "ieee14.grid",
        "remote_url": "https://raw.githubusercontent.com/USER/REPO/main/grids/ieee14.grid",
        "buses": 14,
        "branches": 20,
    })

    # entries = scan_grids_folder(root=Path("/Users/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids"))
    # for entry in entries:
    #     db.upsert_from_dict(entry.to_dict())

    app = QApplication(sys.argv)
    w = GridLibraryWindow(db, cache_dir)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
