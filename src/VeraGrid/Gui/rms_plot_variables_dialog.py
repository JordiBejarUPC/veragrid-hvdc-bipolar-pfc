# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List
import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QDialogButtonBox
)
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults, ResultsTable
from VeraGridEngine.enumerations import DeviceType
import matplotlib.pyplot as plt


class RmsPlotDialog(QDialog):
    """
    Special plot for dynamic variables
    """

    def __init__(self, grid: MultiCircuit, results: RmsResults, parent=None):
        """

        :param grid: MultiCircuit
        :param results: RmsResults
        :param parent:
        """
        super().__init__(parent)

        buses = [bus for bus in grid.get_buses()]
        branches = [branch for branch in grid.get_branches_iter()]
        injections = [injection for injection in grid.get_injection_devices_iter()]

        devices = buses + branches + injections

        devices_options: Dict[str, List[str]] = dict()

        for device in devices:
            devices_options[device.name] = [results.uid2vars_glob_name[var.uid] for var in
                                            device.rms_model.model.state_vars + device.rms_model.model.algebraic_vars]

        self.setWindowTitle("Plot Variables")
        self.uid2idx = results.uid2idx
        self.vars_glob_name2uid = results.vars_glob_name2uid
        self.devices = devices_options
        self.results_table = ResultsTable(
                data=np.array(results.values),
                index=np.array(pd.to_datetime(results.time_array).total_seconds().astype(str), dtype=np.str_),
                columns=results.variable_array,
                title="Rms Simulation Results",
                units=results.units,
                idx_device_type=DeviceType.TimeDevice,
                cols_device_type=DeviceType.NoDevice,
                xlabel=" time (s)",
                ylabel="",
            )
        self.selected_vars = []

        layout = QVBoxLayout(self)

        # --- Device selector ---
        dev_layout = QHBoxLayout()
        dev_layout.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(list(devices_options.keys()))
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
        """

        :param index:
        :return:
        """
        device = self.device_combo.currentText()
        self.var_combo.clear()
        self.var_combo.addItems(self.devices[device])

    def add_variable(self):
        """

        :return:
        """
        var = self.var_combo.currentText()
        item_str = var
        if item_str not in self.selected_vars:
            self.selected_vars.append(self.vars_glob_name2uid[item_str])
            self.list_widget.addItem(item_str)

    def plot_selected(self):
        """

        :return:
        """
        selected_col_idx = [self.uid2idx[uid] for uid in self.selected_vars]
        self.results_table.plot(selected_col_idx=selected_col_idx)
        plt.show()
