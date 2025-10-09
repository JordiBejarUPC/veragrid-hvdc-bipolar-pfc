# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


from PySide6 import QtWidgets
from VeraGridEngine.Devices.types import ALL_RMS_TEMPLATES_TYPE

class RmsChoiceDialog(QtWidgets.QDialog):
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

        # ---- Template Section ----
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


class RmsParameterDialog(QtWidgets.QDialog):
    def __init__(self, template: ALL_RMS_TEMPLATES_TYPE, parent=None):
        super().__init__(parent)
        self.template = template
        self.setWindowTitle("Edit RMS Template Parameters")

        layout = QtWidgets.QFormLayout()
        self.inputs = {}

        # Create input (QLineEdit) for each parámetro
        for param_name in template.parameters:
            param_value = getattr(template, param_name).value  # obtener valor actual del Const
            line_edit = QtWidgets.QLineEdit(str(param_value))
            self.inputs[param_name] = line_edit
            layout.addRow(param_name, line_edit)

        # Botones OK/Cancel
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)

    def get_values(self):
        """Devuelve un diccionario con los valores ingresados por el usuario."""
        return {name: float(edit.text()) for name, edit in self.inputs.items()}
