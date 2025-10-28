# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pdb
import re

from typing import List, Dict, Union

from PySide6 import QtWidgets, QtCore, QtGui

from VeraGridEngine.Devices.Aggregation.rms_event import RmsEvent
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Symbolic import Var, Expr, Const


# TODO: This dialog has to be deleted and the general editor will contain the add template option
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


class RmsParameterDialog(QtWidgets.QDialog):  # TODO: Move this section to the template page in the general editor
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
#
# class RmsEventEditor(QtWidgets.QDialog):
#     def __init__(self, devices: List[ALL_DEV_TYPES], event:RmsEvent, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("RMS Event Editor")
#         self.setMinimumWidth(400)
#
#         self.devices = devices
#         self.event = event
#         device = self.event.device
#         param = self.event.parameter
#         time = self.event.time
#         value = self.event.value
#
#         self.parameters: List[Var] = [param for param in device.rms_model.model.event_dict]
#         self.parameters_str: List[str] = [param.name for param in self.parameters]
#
#         # create list with all the devices str
#         self.dev_str = [device.name for device in self.devices]
#
#         # ---- Main Layout ----
#         layout = QtWidgets.QVBoxLayout(self)
#
#         #--- Available devices ---
#         layout.addWidget(QtWidgets.QLabel("Available devices:"))
#         self.dev_selector = QtWidgets.QComboBox()
#         self.dev_selector.addItems(self.dev_str)
#         layout.addWidget(self.dev_selector)
#
#         # --- Available parameters ---
#         layout.addWidget(QtWidgets.QLabel("Available parameters:"))
#         self.param_selector = QtWidgets.QComboBox()
#         self.param_selector.addItems(self.parameters_str)
#         layout.addWidget(self.param_selector)
#
#         # --- Target time ---
#         layout.addWidget(QtWidgets.QLabel("Target time:"))
#         self.time_input = QtWidgets.QLineEdit()
#         self.time_input.setPlaceholderText("e.g., 0.1")
#         layout.addWidget(self.time_input)
#
#         # --- New value ---
#         layout.addWidget(QtWidgets.QLabel("New value:"))
#         self.value_input = QtWidgets.QLineEdit()
#         self.value_input.setPlaceholderText("e.g., 1.0")
#         layout.addWidget(self.value_input)
#
#         # --- Target device name ---
#         label_device = QtWidgets.QLabel(f"<b>Target device:</b> {event.device_type}")
#         layout.addWidget(label_device)
#
#     def get_dev_parameters(self, current_device: ALL_DEV_TYPES):
#         self.parameters = [param for param in current_device.rms_model.model.event_dict]
#
#     def get_updated_event(self):
#         selected_device = self.devices[self.dev_str.index(current_device)]
#         selected_param = self.parameters[self.parameters_str.index(current_parameter)]
#         time = input_time
#         value = input_value
#         return RmsEvent(selected_device, selected_param, time, value)


class RmsEventEditor(QtWidgets.QDialog):
    def __init__(self, devices: List[ALL_DEV_TYPES], event, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RMS Event Editor")
        self.setMinimumWidth(400)

        self.devices = devices

        # Extract parameters for initial device
        if event.device is not None:
            device = event.device
            self.current_device = device
            self.parameters: List = [p for p in device.rms_model.model.event_dict]
            self.parameters_str: List[str] = [p.name for p in self.parameters]
        else:
            self.parameters: List = []
            self.parameters_str: List[str] = []
            self.current_device = None

        # Initial event values
        param = event.parameter if event.parameter is not None else None
        time = event.time if event.time is not None else 0.0
        value = event.value if event.value is not None else 0.0

        # Store current selections
        self.current_parameter = param
        self.current_time = time
        self.current_value = value

        # Devices names
        self.dev_str = [d.name for d in self.devices]

        # ---- Main Layout ----
        layout = QtWidgets.QVBoxLayout(self)

        # --- Device selector ---
        layout.addWidget(QtWidgets.QLabel("Available devices:"))
        self.dev_selector = QtWidgets.QComboBox()
        self.dev_selector.addItems(self.dev_str)
        layout.addWidget(self.dev_selector)

        # Button to update parameters
        self.select_device_btn = QtWidgets.QPushButton("Select Device")
        layout.addWidget(self.select_device_btn)

        # --- Parameter selector ---
        layout.addWidget(QtWidgets.QLabel("Available parameters:"))
        self.param_selector = QtWidgets.QComboBox()
        self.param_selector.addItems(self.parameters_str)
        layout.addWidget(self.param_selector)

        # --- Target time ---
        layout.addWidget(QtWidgets.QLabel("Target time:"))
        self.time_input = QtWidgets.QDoubleSpinBox()
        self.time_input.setRange(-1e6, 1e6)
        self.time_input.setDecimals(6)
        self.time_input.setValue(time)
        layout.addWidget(self.time_input)

        # --- New value ---
        layout.addWidget(QtWidgets.QLabel("New value:"))
        self.value_input = QtWidgets.QDoubleSpinBox()
        self.value_input.setRange(-1e6, 1e6)
        self.value_input.setDecimals(6)
        self.value_input.setValue(value)
        layout.addWidget(self.value_input)

        # --- 🔹 Buttons layout (OK / Cancel) ---
        button_layout = QtWidgets.QHBoxLayout()
        self.ok_button = QtWidgets.QPushButton("OK")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        button_layout.addStretch(1)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # --- Connections ---
        self.select_device_btn.clicked.connect(self.on_select_device)
        self.dev_selector.currentIndexChanged.connect(self.on_device_changed)
        self.param_selector.currentIndexChanged.connect(self.on_param_changed)
        self.time_input.valueChanged.connect(self.on_time_changed)
        self.value_input.valueChanged.connect(self.on_value_changed)
        self.ok_button.clicked.connect(self.accept)       # 🔹 Accepts dialog
        self.cancel_button.clicked.connect(self.reject)   # 🔹 Cancels dialog

        # Set initial selections
        if self.current_device is not None:
            self.dev_selector.setCurrentText(self.current_device.name)
        if param is not None:
            self.param_selector.setCurrentText(param.name)

    # --------------------------
    # Event handlers
    # --------------------------
    def on_select_device(self):
        """Update parameters list when device is selected."""
        index = self.dev_selector.currentIndex()
        self.current_device = self.devices[index]
        self.get_dev_parameters(self.current_device)
        # Update parameter combo
        self.param_selector.clear()
        self.param_selector.addItems([p.name for p in self.parameters])
        # Reset current parameter
        if self.parameters:
            self.current_parameter = self.parameters[0]

    def on_device_changed(self, index):
        self.current_device = self.devices[index]

    def on_param_changed(self, index):
        if 0 <= index < len(self.parameters):
            self.current_parameter = self.parameters[index]

    def on_time_changed(self, value):
        self.current_time = value

    def on_value_changed(self, value):
        self.current_value = value

    def get_dev_parameters(self, current_device):
        self.parameters = [p for p in current_device.rms_model.model.event_dict]

    def get_updated_event(self):
        """Return an updated RmsEvent with the edited fields."""
        return RmsEvent(
            device=self.current_device,
            parameter=self.current_parameter,
            time=self.current_time,
            value=self.current_value
        )



#
# class RmsEventDialogue(QtWidgets.QDialog):  # TODO: Move this section to the events page in the general editor
#     def __init__(self, parameters_list: List[str], target_device_name, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("RMS Event Editor")
#         self.setMinimumWidth(400)
#
#         self.parameters_list = parameters_list
#         self.target_device_name = target_device_name
#
#         # ---- Main Layout ----
#         layout = QtWidgets.QVBoxLayout(self)
#
        # --- Target device name ---
        # label_device = QtWidgets.QLabel(f"<b>Target device:</b> {target_device_name}")
        # layout.addWidget(label_device)
#
#         # --- Available parameters ---
#         layout.addWidget(QtWidgets.QLabel("Available parameters:"))
#         self.param_selector = QtWidgets.QComboBox()
#         self.param_selector.addItems(parameters_list)
#         layout.addWidget(self.param_selector)
#
#         # --- Target times ---
#         layout.addWidget(QtWidgets.QLabel("Target times (comma-separated floats):"))
#         self.times_input = QtWidgets.QLineEdit()
#         self.times_input.setPlaceholderText("e.g., 0.1, 0.2, 0.5")
#         layout.addWidget(self.times_input)
#
#         # --- New value ---
#         layout.addWidget(QtWidgets.QLabel("New values (comma-separated floats):"))
#         self.values_input = QtWidgets.QLineEdit()
#         self.values_input.setPlaceholderText("e.g., 1.0, 0.95, 1.1")
#         layout.addWidget(self.values_input)
#
#         # --- Buttons ---
#         button_layout = QtWidgets.QHBoxLayout()
#         self.ok_button = QtWidgets.QPushButton("OK")
#         self.cancel_button = QtWidgets.QPushButton("Cancel")
#         button_layout.addWidget(self.ok_button)
#         button_layout.addWidget(self.cancel_button)
#         layout.addLayout(button_layout)
#
#         # --- Connections ---
#         self.ok_button.clicked.connect(self.accept_dialog)
#         self.cancel_button.clicked.connect(self.reject)
#
#     def accept_dialog(self):
#         """ """
#         try:
#             times_str = self.times_input.text().strip()
#             values_str = self.values_input.text().strip()
#
#             self.target_times = [float(x) for x in times_str.split(",") if x.strip()]
#             self.new_values = [float(x) for x in values_str.split(",") if x.strip()]
#             self.selected_param = self.param_selector.currentText()
#
#             if len(self.target_times) != len(self.new_values):
#                 QtWidgets.QMessageBox.warning(
#                     self,
#                     "Error",
#                     "Number of times and values must match.",
#                 )
#                 return
#
#             self.accept()
#
#         except ValueError:
#             QtWidgets.QMessageBox.warning(
#                 self,
#                 "Error",
#                 "Insert coma separated values.",
#             )
#
#     def get_data(self) -> Dict[str, Union[str, List]]:
#         """Return event data in dictionary form."""
#         return {
#             "parameter": self.selected_param,
#             "target_times": self.target_times,
#             "new_values": self.new_values,
#         }


def parse_float(s: str) -> float:
    """
    Parse a float from a string accepting both comma and dot as decimal separators.
    Handles cases like:
      - "1.5" -> 1.5
      - "1,5" -> 1.5
      - "1.234,56" -> 1234.56  (common European)
      - "1,234.56" -> 1234.56  (common US)
    Raises ValueError if it cannot be parsed.
    """
    if s is None:
        raise ValueError("Empty string")

    s = s.strip()
    if s == "":
        raise ValueError("Empty string")

    # Remove spaces
    s = s.replace(" ", "")

    # If there are both '.' and ',' assume the last one is the decimal separator:
    # common convention: "1.234,56" (dot thousands, comma decimal) -> remove dots, comma->dot
    # or "1,234.56" (comma thousands, dot decimal) -> remove commas, keep dot.
    if '.' in s and ',' in s:
        # decide which occurs last
        if s.rfind(',') > s.rfind('.'):
            # comma is decimal separator
            s = s.replace('.', '')
            s = s.replace(',', '.')
        else:
            # dot is decimal separator
            s = s.replace(',', '')
    else:
        # only comma or only dot or none: normalize comma -> dot
        s = s.replace(',', '.')

    # Now s should look like a normal Python float literal, maybe with +/-
    if not re.fullmatch(r'[+-]?\d+(\.\d+)?', s):
        raise ValueError(f"Not a valid float: {s}")

    return float(s)


class RmsEventDialogue(QtWidgets.QDialog):
    def __init__(self, parameters_list: List[str], target_device_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RMS Event Editor")
        self.setMinimumWidth(600)

        self.parameters_list = parameters_list
        self.target_device_name = target_device_name

        # ---- Main Layout ----
        layout = QtWidgets.QVBoxLayout(self)

        # --- Device label ---
        label_device = QtWidgets.QLabel(f"<b>Target device:</b> {target_device_name}")
        layout.addWidget(label_device)

        # --- Events Table ---
        self.table = QtWidgets.QTableWidget(0, 4)  # 4 columns: checkbox + 3 data columns
        self.table.setHorizontalHeaderLabels(["", "Parameter", "Time", "New Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.table)

        # --- Table control buttons ---
        table_button_layout = QtWidgets.QHBoxLayout()
        self.add_row_btn = QtWidgets.QPushButton("➕ Add New Event")
        self.remove_row_btn = QtWidgets.QPushButton("❌ Remove Selected Rows")
        table_button_layout.addWidget(self.add_row_btn)
        table_button_layout.addWidget(self.remove_row_btn)
        layout.addLayout(table_button_layout)

        # --- Bottom buttons ---
        button_layout = QtWidgets.QHBoxLayout()
        self.ok_button = QtWidgets.QPushButton("✅ Add Events")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # --- Connections ---
        self.add_row_btn.clicked.connect(self.add_row)
        self.remove_row_btn.clicked.connect(self.remove_checked_rows)
        self.ok_button.clicked.connect(self.accept_dialog)
        self.cancel_button.clicked.connect(self.reject)

    # ------------------------------------------------------------------
    # Row management
    # ------------------------------------------------------------------
    def add_row(self):
        """Add a new empty editable event row."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # --- Checkbox column ---
        checkbox = QtWidgets.QTableWidgetItem()
        checkbox.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        checkbox.setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.table.setItem(row, 0, checkbox)

        # --- Parameter selector ---
        combo = QtWidgets.QComboBox()
        combo.addItems(self.parameters_list)
        self.table.setCellWidget(row, 1, combo)

        # --- Time and Value as plain QLineEdit (no strict validator) ---
        # We'll validate/parse robustly on accept to allow both ',' and '.'
        time_edit = QtWidgets.QLineEdit()
        time_edit.setPlaceholderText("e.g. 1.5 or 1,5")
        value_edit = QtWidgets.QLineEdit()
        value_edit.setPlaceholderText("e.g. 0.95 or 0,95")

        self.table.setCellWidget(row, 2, time_edit)
        self.table.setCellWidget(row, 3, value_edit)

    def remove_checked_rows(self):
        """Remove all rows with checkbox checked."""
        rows_to_remove = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == QtCore.Qt.CheckState.Checked:
                rows_to_remove.append(row)

        if not rows_to_remove:
            QtWidgets.QMessageBox.information(
                self,
                "No Rows Selected",
                "Please check at least one row to remove.",
            )
            return

        # Remove from bottom to top to avoid index shifting
        for row in reversed(rows_to_remove):
            self.table.removeRow(row)

    # ------------------------------------------------------------------
    # Data handling
    # ------------------------------------------------------------------
    def accept_dialog(self):
        """Validate and collect all event data."""
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.warning(
                self,
                "No Events",
                "Please add at least one event before confirming.",
            )
            return

        parameters, target_times, values = [], [], []

        for row in range(self.table.rowCount()):
            combo_widget = self.table.cellWidget(row, 1)
            time_widget = self.table.cellWidget(row, 2)
            value_widget = self.table.cellWidget(row, 3)

            param = combo_widget.currentText().strip() if isinstance(combo_widget, QtWidgets.QComboBox) else ""
            time_text = time_widget.text().strip() if isinstance(time_widget, QtWidgets.QLineEdit) else ""
            value_text = value_widget.text().strip() if isinstance(value_widget, QtWidgets.QLineEdit) else ""

            if not param or not time_text or not value_text:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Incomplete Data",
                    f"Row {row + 1} has missing fields.",
                )
                return

            try:
                t = parse_float(time_text)
                v = parse_float(value_text)
            except ValueError as exc:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Invalid Input",
                    f"Row {row + 1} contains invalid numerical values: {exc}",
                )
                return

            parameters.append(param)
            target_times.append(t)
            values.append(v)

        self.data = {
            "parameters": parameters,
            "target_times": target_times,
            "values": values,
        }

        self.accept()

    def get_data(self) -> Dict[str, Union[List[str], List[float]]]:
        """Return collected data."""
        return getattr(self, "data", {"parameters": [], "target_times": [], "values": []})





