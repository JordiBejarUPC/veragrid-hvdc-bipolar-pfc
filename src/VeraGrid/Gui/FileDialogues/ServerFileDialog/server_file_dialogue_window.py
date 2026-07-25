# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Any, Dict, List

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from VeraGrid.Gui.FileDialogues.ServerFileDialog.server_file_dialogue import Ui_ServerFileDialog
from VeraGrid.Gui.messages import yes_no_question


class ServerFileDialogue(QtWidgets.QDialog):
    """
    Browse and operate on server-side database files and nested models.
    """

    __slots__ = (
        "ui",
        "_app",
        "_model",
    )

    _ROLE_KIND: int = int(Qt.ItemDataRole.UserRole) + 1
    _ROLE_FILE: int = int(Qt.ItemDataRole.UserRole) + 2
    _ROLE_MODEL: int = int(Qt.ItemDataRole.UserRole) + 3

    def __init__(self, parent: QtWidgets.QWidget, app: Any) -> None:
        """
        Build the server file dialogue.

        :param parent: Parent widget.
        :param app: Main GUI instance owning the server driver helpers.
        :return: None.
        """
        QtWidgets.QDialog.__init__(self, parent)

        self._app: Any = app
        self.ui = Ui_ServerFileDialog()
        self.ui.setupUi(self)

        self._model: QStandardItemModel = QStandardItemModel()
        self._model.setHorizontalHeaderLabels(["Name", "Kind", "Identifier", "Owner / Parent", "Created"])
        self.ui.filesTreeView.setModel(self._model)
        self.ui.filesTreeView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ui.filesTreeView.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.ui.filesTreeView.selectionModel().selectionChanged.connect(self.update_selection_details)

        self.ui.refreshButton.clicked.connect(self.refresh_tree)
        self.ui.loadFileButton.clicked.connect(self.load_selected_file)
        self.ui.loadBaseButton.clicked.connect(self.load_selected_base_model)
        self.ui.loadModelButton.clicked.connect(self.load_selected_model)
        self.ui.saveCurrentButton.clicked.connect(self.save_current_project)
        self.ui.deleteButton.clicked.connect(self.delete_selected_item)
        self.ui.buttonBox.rejected.connect(self.reject)
        self.ui.filesTreeView.doubleClicked.connect(self.on_tree_double_clicked)

        self.refresh_tree()

    def set_status_text(self, text: str) -> None:
        """
        Update the status text in the dialogue footer.

        :param text: Status text.
        :return: None.
        """
        self.ui.statusLabel.setText(text)

    def refresh_tree(self) -> None:
        """
        Reload the server file tree from the database API.

        :return: None.
        """
        self._model.removeRows(0, self._model.rowCount())
        self.set_status_text("Refreshing server file tree...")

        files_payload: List[Dict[str, Any]] = self._app.server_driver.list_database_files_tree()
        file_payload: Dict[str, Any]

        for file_payload in files_payload:
            file_item_name: QStandardItem = QStandardItem(str(file_payload["name"]))
            file_item_kind: QStandardItem = QStandardItem("File")
            file_item_id: QStandardItem = QStandardItem(str(file_payload["idtag"]))
            file_item_owner: QStandardItem = QStandardItem(str(file_payload["user"]))
            file_item_created: QStandardItem = QStandardItem(str(file_payload["created_at"]))
            file_row: List[QStandardItem] = [
                file_item_name,
                file_item_kind,
                file_item_id,
                file_item_owner,
                file_item_created,
            ]

            item: QStandardItem
            for item in file_row:
                item.setEditable(False)
                item.setData("file", self._ROLE_KIND)
                item.setData(file_payload, self._ROLE_FILE)
            else:
                pass

            model_payload: Dict[str, Any]
            for model_payload in file_payload["models"]:
                model_item_name: QStandardItem = QStandardItem(str(model_payload["name"]))
                model_item_kind: QStandardItem = QStandardItem(
                    "Base model" if bool(model_payload["is_base_model"]) else "Delta model"
                )
                model_item_id: QStandardItem = QStandardItem(str(model_payload["idtag"]))
                model_item_parent: QStandardItem = QStandardItem(
                    str(model_payload["parent_model_idtag"])
                    if model_payload["parent_model_idtag"] is not None else "-"
                )
                model_item_created: QStandardItem = QStandardItem("")
                model_row: List[QStandardItem] = [
                    model_item_name,
                    model_item_kind,
                    model_item_id,
                    model_item_parent,
                    model_item_created,
                ]

                for item in model_row:
                    item.setEditable(False)
                    item.setData("model", self._ROLE_KIND)
                    item.setData(file_payload, self._ROLE_FILE)
                    item.setData(model_payload, self._ROLE_MODEL)
                else:
                    pass

                file_item_name.appendRow(model_row)

            self._model.appendRow(file_row)

        self.ui.filesTreeView.expandAll()
        self.ui.filesTreeView.resizeColumnToContents(0)
        self.ui.filesTreeView.resizeColumnToContents(1)
        self.ui.filesTreeView.resizeColumnToContents(2)
        self.update_selection_details()
        self.set_status_text(f"Loaded {len(files_payload)} server files.")

    def get_selected_item(self) -> QStandardItem | None:
        """
        Return the first selected tree item.

        :return: Selected item or ``None``.
        """
        current_index = self.ui.filesTreeView.currentIndex()

        if current_index.isValid():
            item: QStandardItem | None = self._model.itemFromIndex(current_index)
            return item
        else:
            return None

    def get_selected_file_payload(self) -> Dict[str, Any] | None:
        """
        Return the selected file payload regardless of whether the current item is a file or model.

        :return: File payload or ``None``.
        """
        item: QStandardItem | None = self.get_selected_item()

        if item is None:
            return None
        else:
            payload: Any = item.data(self._ROLE_FILE)
            if isinstance(payload, dict):
                return payload
            else:
                return None

    def get_selected_model_payload(self) -> Dict[str, Any] | None:
        """
        Return the selected model payload when one model row is selected.

        :return: Model payload or ``None``.
        """
        item: QStandardItem | None = self.get_selected_item()

        if item is None:
            return None
        else:
            payload: Any = item.data(self._ROLE_MODEL)
            if isinstance(payload, dict):
                return payload
            else:
                return None

    def update_selection_details(self) -> None:
        """
        Reflect the current tree selection in the detail panel.

        :return: None.
        """
        file_payload: Dict[str, Any] | None = self.get_selected_file_payload()
        model_payload: Dict[str, Any] | None = self.get_selected_model_payload()

        if file_payload is None:
            self.ui.kindValueLabel.setText("-")
            self.ui.fileNameValueLabel.setText("-")
            self.ui.fileIdValueLabel.setText("-")
            self.ui.modelNameValueLabel.setText("-")
            self.ui.modelIdValueLabel.setText("-")
            self.ui.ownerValueLabel.setText("-")
            self.ui.createdValueLabel.setText("-")
            self.ui.loadFileButton.setEnabled(False)
            self.ui.loadBaseButton.setEnabled(False)
            self.ui.loadModelButton.setEnabled(False)
            self.ui.saveCurrentButton.setEnabled(False)
            self.ui.deleteButton.setEnabled(False)
        else:
            if model_payload is None:
                self.ui.kindValueLabel.setText("File")
                self.ui.modelNameValueLabel.setText("-")
                self.ui.modelIdValueLabel.setText("-")
                self.ui.loadModelButton.setEnabled(False)
            else:
                self.ui.kindValueLabel.setText(
                    "Base model" if bool(model_payload["is_base_model"]) else "Delta model"
                )
                self.ui.modelNameValueLabel.setText(str(model_payload["name"]))
                self.ui.modelIdValueLabel.setText(str(model_payload["idtag"]))
                self.ui.loadModelButton.setEnabled(True)

            self.ui.fileNameValueLabel.setText(str(file_payload["name"]))
            self.ui.fileIdValueLabel.setText(str(file_payload["idtag"]))
            self.ui.ownerValueLabel.setText(str(file_payload["user"]))
            self.ui.createdValueLabel.setText(str(file_payload["created_at"]))
            self.ui.loadFileButton.setEnabled(True)
            self.ui.loadBaseButton.setEnabled(True)
            self.ui.saveCurrentButton.setEnabled(True)
            self.ui.deleteButton.setEnabled(True)

    def load_selected_file(self) -> None:
        """
        Load the full multiverse for the selected file.

        :return: None.
        """
        file_payload: Dict[str, Any] | None = self.get_selected_file_payload()

        if file_payload is None:
            self.set_status_text("Select one file first.")
        else:
            self.set_status_text("Downloading selected file from server...")
            self._app.load_remote_database_entry(
                file_idtag=str(file_payload["idtag"]),
                file_name=str(file_payload["name"]),
                model_idtag="",
                base_only=False,
            )
            self.accept()

    def load_selected_base_model(self) -> None:
        """
        Load only the base model for the selected file.

        :return: None.
        """
        file_payload: Dict[str, Any] | None = self.get_selected_file_payload()

        if file_payload is None:
            self.set_status_text("Select one file first.")
        else:
            self.set_status_text("Downloading base model from server...")
            self._app.load_remote_database_entry(
                file_idtag=str(file_payload["idtag"]),
                file_name=str(file_payload["name"]),
                model_idtag="",
                base_only=True,
            )
            self.accept()

    def load_selected_model(self) -> None:
        """
        Load the selected model as one flat circuit.

        :return: None.
        """
        file_payload: Dict[str, Any] | None = self.get_selected_file_payload()
        model_payload: Dict[str, Any] | None = self.get_selected_model_payload()

        if file_payload is None or model_payload is None:
            self.set_status_text("Select one model first.")
        else:
            self.set_status_text("Downloading selected model from server...")
            self._app.load_remote_database_entry(
                file_idtag=str(file_payload["idtag"]),
                file_name=str(file_payload["name"]),
                model_idtag=str(model_payload["idtag"]),
                base_only=False,
            )
            self.accept()

    def save_current_project(self) -> None:
        """
        Save the current GUI project into the selected remote file.

        :return: None.
        """
        file_payload: Dict[str, Any] | None = self.get_selected_file_payload()
        model_payload: Dict[str, Any] | None = self.get_selected_model_payload()

        if file_payload is None:
            self.set_status_text("Select one file first.")
        else:
            self.set_status_text("Uploading current project to server...")
            self._app.save_remote_database_entry(
                file_idtag=str(file_payload["idtag"]),
                file_name=str(file_payload["name"]),
                model_idtag="" if model_payload is None else str(model_payload["idtag"]),
            )
            self.refresh_tree()

    def delete_selected_item(self) -> None:
        """
        Delete the selected file or model after one confirmation prompt.

        :return: None.
        """
        file_payload: Dict[str, Any] | None = self.get_selected_file_payload()
        model_payload: Dict[str, Any] | None = self.get_selected_model_payload()

        if file_payload is None:
            self.set_status_text("Select one file or model first.")
        elif model_payload is None:
            ok: bool = yes_no_question(
                text=self.tr("Delete the selected file and every model inside it?"),
                title=self.tr("Delete server file"),
            )

            if ok:
                self._app.delete_remote_database_file(file_idtag=str(file_payload["idtag"]))
                self.refresh_tree()
            else:
                self.set_status_text("Deletion cancelled.")
        else:
            ok = yes_no_question(
                text=self.tr("Delete the selected model from the server database?"),
                title=self.tr("Delete server model"),
            )

            if ok:
                self._app.delete_remote_database_model(
                    file_idtag=str(file_payload["idtag"]),
                    model_idtag=str(model_payload["idtag"]),
                )
                self.refresh_tree()
            else:
                self.set_status_text("Deletion cancelled.")

    def on_tree_double_clicked(self) -> None:
        """
        Load the double-clicked row using the natural file/model action.

        :return: None.
        """
        model_payload: Dict[str, Any] | None = self.get_selected_model_payload()

        if model_payload is None:
            self.load_selected_file()
        else:
            self.load_selected_model()
