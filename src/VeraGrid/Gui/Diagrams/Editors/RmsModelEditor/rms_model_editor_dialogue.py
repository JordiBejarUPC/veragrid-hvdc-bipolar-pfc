# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Dict, Union

from PySide6 import QtWidgets
from VeraGridEngine.Devices.types import ALL_RMS_TEMPLATES_TYPE
from VeraGridEngine.Utils.Symbolic import Var, Expr, Const


class RmsChoiceDialog(QtWidgets.QDialog): #TODO: This dialog has to be deleted and the general editor will contain the add template option
    """
    In-between dialog to choose between using an existing template
    or opening the RMS Model Editor.
    """
    def __init__(self, templates: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("RMS Editing Options")
        self.setModal(True)

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel("Choose how to proceed with RMS editing:")
        layout.addWidget(label)


        # ---- Template Section ---- # TODO: Move this section to the template page in the general editor
        self.template_label = QtWidgets.QLabel("Select an existing template:")
        layout.addWidget(self.template_label)

        self.template_combo = QtWidgets.QComboBox()
        self.template_combo.addItems(templates if templates else ["<No templates available>"])
        layout.addWidget(self.template_combo)

        self.btn_template = QtWidgets.QPushButton("Use selected template")
        layout.addWidget(self.btn_template)

        # ---- Editor Section ----
        self.btn_editor = QtWidgets.QPushButton("Open RMS Model Editor")
        layout.addWidget(self.btn_editor)

        # ---- Cancel ----
        self.btn_cancel = QtWidgets.QPushButton("Cancel")
        layout.addWidget(self.btn_cancel)

        # Result tracking
        self.choice = None
        self.selected_template = None

        # Connections
        self.btn_template.clicked.connect(self.choose_template)
        self.btn_editor.clicked.connect(self.choose_editor)
        self.btn_cancel.clicked.connect(self.reject)

    def choose_template(self):
        self.choice = "template"
        self.selected_template = self.template_combo.currentText()
        self.accept()

    def choose_editor(self):
        self.choice = "editor"
        self.accept()


class RmsParameterDialog(QtWidgets.QDialog): #TODO: Move this section to the template page in the general editor
    def __init__(self, event_dict: Dict[Var, Const], parent=None):
        super().__init__(parent)
        # self.event_dict = event_dict
        self.setWindowTitle("Edit RMS Template Parameters")

        layout = QtWidgets.QFormLayout()
        self.inputs = {}

        # Create input (QLineEdit) for each parameter
        for param, equ in event_dict.items():
            # param_value = getattr(template, param_name).value
            line_edit = QtWidgets.QLineEdit(str(equ.value))
            self.inputs[param] = line_edit
            layout.addRow(param.name, line_edit)

        # Botones OK/Cancel
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)

    def get_new_event_dict(self):
        """Devuelve un diccionario con los valores ingresados por el usuario."""
        return {param: Const(float(edit.text())) for param, edit in self.inputs.items()}


class RmsEventDialogue(QtWidgets.QDialog): #TODO: Move this section to the events page in the general editor
    def __init__(self, parameters_list: List[str], target_device_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RMS Event Editor")
        self.setMinimumWidth(400)

        self.parameters_list = parameters_list
        self.target_device_name = target_device_name

        # ---- Main Layout ----
        layout = QtWidgets.QVBoxLayout(self)

        # --- Target device name ---
        label_device = QtWidgets.QLabel(f"<b>Target device:</b> {target_device_name}")
        layout.addWidget(label_device)

        # --- Available parameters ---
        layout.addWidget(QtWidgets.QLabel("Available parameters:"))
        self.param_selector = QtWidgets.QComboBox()
        self.param_selector.addItems(parameters_list)
        layout.addWidget(self.param_selector)

        # --- Target times ---
        layout.addWidget(QtWidgets.QLabel("Target times (comma-separated floats):"))
        self.times_input = QtWidgets.QLineEdit()
        self.times_input.setPlaceholderText("e.g., 0.1, 0.2, 0.5")
        layout.addWidget(self.times_input)

        # --- New value ---
        layout.addWidget(QtWidgets.QLabel("New values (comma-separated floats):"))
        self.values_input = QtWidgets.QLineEdit()
        self.values_input.setPlaceholderText("e.g., 1.0, 0.95, 1.1")
        layout.addWidget(self.values_input)

        # --- Buttons ---
        button_layout = QtWidgets.QHBoxLayout()
        self.ok_button = QtWidgets.QPushButton("OK")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # --- Connections ---
        self.ok_button.clicked.connect(self.accept_dialog)
        self.cancel_button.clicked.connect(self.reject)

    def accept_dialog(self):
        """ """
        try:
            times_str = self.times_input.text().strip()
            values_str = self.values_input.text().strip()

            self.target_times = [float(x) for x in times_str.split(",") if x.strip()]
            self.new_values = [float(x) for x in values_str.split(",") if x.strip()]
            self.selected_param = self.param_selector.currentText()

            if len(self.target_times) != len(self.new_values):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    "Number of times and values must match.",
                )
                return

            self.accept()

        except ValueError:
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                "Insert coma separated values.",
            )

    def get_data(self) -> Dict[str,Union[str,List]]:
        """Return event data in dictionary form."""
        return {
            "parameter": self.selected_param,
            "target_times": self.target_times,
            "new_values": self.new_values,
        }

