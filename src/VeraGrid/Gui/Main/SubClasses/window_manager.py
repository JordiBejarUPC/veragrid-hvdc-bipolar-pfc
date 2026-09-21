# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from functools import partial
from typing import Dict
from uuid import uuid4
import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QDialog
# from VeraGrid.Gui.dialog_lifecycle import delete_child_widgets_safely

class WindowManager:

    def __init__(self, main_window: QMainWindow):
        """
        Constructor
        :param main_window: Main window using this manager
        """
        self.__parent = main_window

        self.__win: Dict[str, QMainWindow | QDialog] = dict()

    def _cleanup_window_ref(self, key: str, destroyed_object: object = None) -> None:
        """
        Callback function on window deletion to delete its reference
        :param key: key
        :return:
        """
        _ = destroyed_object
        self.__win.pop(key, None)

    def get(self, key: str) -> QMainWindow | QDialog | None:
        """
        Try to obtain a window by its key
        :param key: key to refer to the window
        :return: Window or None if not found
        """
        return self.__win.get(key, None)

    def show(self, win: QMainWindow | QDialog, key: str | None = None) -> QMainWindow | QDialog:
        """
        Safely display a window
        :param win: Window instance
        :param key: key to refer to the window
        :return: Passed window if not registered, existing window if existing
        """

        if key is None:
            key = f"{win.__class__.__name__}_{id(win)}_{uuid4().hex}"
        else:
            pass

        existing_window: QMainWindow | QDialog | None = self.get(key=key)
        if existing_window is not None and shiboken6.isValid(existing_window):
            if existing_window is not win:
                win.deleteLater()
            else:
                pass

            existing_window.show()
            existing_window.raise_()
            existing_window.activateWindow()
            return existing_window
        else:
            self.__win.pop(key, None)

        win.destroyed.connect(partial(self._cleanup_window_ref, key))

        # Ensure the properly declared parent is actually the parent
        if win.parentWidget() != self.__parent:
            win.setParent(self.__parent)

        # 4. Enforce Window Flags & Deletion Attribute
        win.setWindowFlags(win.windowFlags() | Qt.WindowType.Window)
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # 6. Store and display
        self.__win[key] = win
        win.show()
        win.raise_()
        win.activateWindow()
        return win
