# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import io
import numpy as np
import pandas as pd
from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.messages import error_msg
from VeraGrid.Gui.wrappable_table_model import WrappableTableModel
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Utils.Filtering.results_table_filtering import FilterResultsTable

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QDialogButtonBox
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

class RmsPlotDialog(QDialog):
    def __init__(self, devices: dict, parent=None):
        """
        :param devices: dict {device: [Var]}
        """
        super().__init__(parent)
        self.setWindowTitle("Plot Variables")

        self.devices = devices
        self.selected_vars = []

        layout = QVBoxLayout(self)

        # --- Device selector ---
        dev_layout = QHBoxLayout()
        dev_layout.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(devices.keys())
        self.device_combo.currentIndexChanged.connect(self.update_variables)
        dev_layout.addWidget(self.device_combo)
        layout.addLayout(dev_layout)

        # --- Variable selector ---
        var_layout = QHBoxLayout()
        var_layout.addWidget(QLabel("Variable:"))
        self.var_combo = QComboBox()
        var_layout.addWidget(self.var_combo)
        layout.addLayout(var_layout)

        # --- Add button ---
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self.add_variable)
        layout.addWidget(add_btn)

        # --- List of selected vars ---
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # --- Buttons ---
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.plot_selected)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.update_variables(0)

    def update_variables(self, index):
        device = self.device_combo.currentText()
        self.var_combo.clear()
        self.var_combo.addItems(self.devices[device])

    def add_variable(self):
        device = self.device_combo.currentText()
        var = self.var_combo.currentText()
        item_str = f"{device}.{var}"
        if item_str not in self.selected_vars:
            self.selected_vars.append(item_str)
            self.list_widget.addItem(item_str)

    def plot_selected(self):
        if not self.selected_vars:
            return
        plt.figure()
        for var in self.selected_vars:
            # Aquí deberías sustituir por los datos reales de tu simulación
            import numpy as np
            t = np.linspace(0, 10, 100)
            y = np.sin(t) + np.random.normal(0, 0.1, len(t))
            plt.plot(t, y, label=var)

        plt.legend()
        plt.show()
