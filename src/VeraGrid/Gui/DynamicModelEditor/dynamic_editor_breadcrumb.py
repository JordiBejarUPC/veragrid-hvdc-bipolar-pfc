# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import List

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal

from VeraGridEngine.Utils.Symbolic.block import Block


class DynamicEditorBreadcrumb(QtWidgets.QWidget):
    """
    Visual breadcrumb showing the path from the root block to the current block.

    Each block in the path is rendered as a ``QToolButton`` separated by a
    ``QLabel(">")``.  Clicking a button emits :pyattr:`blockClicked` with the
    corresponding :class:`Block`.

    This widget knows nothing about editors or navigation — it purely
    represents a static path.
    """

    blockClicked = Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addStretch(1)

    def set_path(self, blocks: List[Block]) -> None:
        """
        Replace the current breadcrumb with a new path.

        :param blocks: Ordered list of blocks from root to current.
        :return: None.
        """
        self._clear()

        for i, block in enumerate(blocks):
            if i > 0:
                separator = QtWidgets.QLabel(" > ")
                separator.setStyleSheet("color: #888; padding: 0 4px;")
                self._layout.addWidget(separator)

            button = QtWidgets.QToolButton()
            button.setText(block.name)
            button.setAutoRaise(True)
            button.setToolButtonStyle(
                QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly
            )
            button.setCursor(
                QtCore.Qt.CursorShape.PointingHandCursor
            )
            is_last = i == len(blocks) - 1
            if is_last:
                font = button.font()
                font.setBold(True)
                button.setFont(font)

            button.clicked.connect(
                lambda _checked=False, b=block: self.blockClicked.emit(b)
            )
            self._layout.addWidget(button)

    def _clear(self) -> None:
        """Remove all widgets from the layout."""
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                pass
