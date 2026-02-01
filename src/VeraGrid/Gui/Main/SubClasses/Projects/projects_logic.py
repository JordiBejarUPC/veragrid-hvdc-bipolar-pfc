# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
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
