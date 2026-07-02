# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from PySide6 import QtCore, QtWidgets


def _tr(text: str) -> str:
    """
    Translate one message-box helper string.

    :param text: Source text.
    :returns: Translated text.
    """
    return QtCore.QCoreApplication.translate("messages", text)


class CenteredMessageBox(QtWidgets.QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            parent_geo = self.parent().geometry()
            self.move(
                parent_geo.center().x() - self.width() // 2,
                parent_geo.center().y() - self.height() // 2
            )


def info_msg(text, title=None):
    """
    Message box
    :param text: Text to display
    :param title: Name of the window
    """
    msg = CenteredMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
    msg.setText(text)
    msg.setWindowTitle(_tr("Information") if title is None else title)
    msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    return msg.exec()


def warning_msg(text: str, title: str | None = None) -> int:
    """
    Message box
    :param text: Text to display
    :param title: Name of the window
    """
    msg = CenteredMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    msg.setText(text)
    msg.setWindowTitle(_tr("Warning") if title is None else title)
    msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    return msg.exec()


def error_msg(text: str, title: str | None = None) -> int:
    """
    Message box
    :param text: Text to display
    :param title: Name of the window
    """
    msg = CenteredMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    msg.setText(text)
    msg.setWindowTitle(_tr("Error") if title is None else title)
    msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    return msg.exec()


def yes_no_question(text: str, title: str | None = None) -> bool:
    """
    Question message
    :param text:
    :param title:
    :return: True / False
    """
    buttonReply = QtWidgets.QMessageBox.question(
        None,
        _tr("Question") if title is None else title,
        text,
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        QtWidgets.QMessageBox.StandardButton.No
    )
    return buttonReply == QtWidgets.QMessageBox.StandardButton.Yes.value
