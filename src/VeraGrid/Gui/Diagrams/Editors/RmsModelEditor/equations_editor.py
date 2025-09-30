# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QComboBox, QLineEdit, QLabel

from VeraGridEngine.Utils.Symbolic.block import variable, equation
from VeraGridEngine.Utils.Symbolic.symbolic import symbolic_to_string

class EditEquations(QWidget):
    def __init__(self, model_host, parent=None):
        super().__init__(parent)

        self.model_host = model_host  # DynamicModelHost

        main_layout = QHBoxLayout(self)
        self.setLayout(main_layout)

        # ----------------- LEFT PANEL -----------------
        left_panel = QVBoxLayout()
        main_layout.addLayout(left_panel)

        # Variables
        var_header_layout = QHBoxLayout()
        var_label = QLabel("Variables")
        self.btn_add_var = QPushButton("+")
        var_header_layout.addWidget(var_label)
        var_header_layout.addWidget(self.btn_add_var)
        left_panel.addLayout(var_header_layout)

        self.list_vars = QListWidget()
        left_panel.addWidget(self.list_vars)

        # Parameters
        param_header_layout = QHBoxLayout()
        param_label = QLabel("Parameters")
        self.btn_add_param = QPushButton("+")
        param_header_layout.addWidget(param_label)
        param_header_layout.addWidget(self.btn_add_param)
        left_panel.addLayout(param_header_layout)

        self.list_params = QListWidget()
        left_panel.addWidget(self.list_params)

        # ----------------- RIGHT PANEL -----------------
        right_panel = QVBoxLayout()
        main_layout.addLayout(right_panel)

        eqn_header_layout = QHBoxLayout()
        eqn_label = QLabel("Equations")
        self.btn_add_eqn = QPushButton("+")
        eqn_header_layout.addWidget(eqn_label)
        eqn_header_layout.addWidget(self.btn_add_eqn)
        right_panel.addLayout(eqn_header_layout)

        self.list_eqns = QListWidget()
        right_panel.addWidget(self.list_eqns)

        # ----------------- Connections -----------------
        self.btn_add_var.clicked.connect(self.add_variable)
        self.btn_add_param.clicked.connect(self.add_parameter)
        self.btn_add_eqn.clicked.connect(self.add_equation)

        self.refresh_lists()

    # ----------------- Methods -----------------
    def refresh_lists(self):
        """Load current model variables, parameters, equations into lists."""
        self.list_vars.clear()
        self.list_params.clear()
        self.list_eqns.clear()

        for model in self.model_host.model.children:
            for var in model.state_vars + model.algebraic_vars:
                print(var)
                item = QListWidgetItem(f"{var.name} ({'state' if var in model.state_vars else 'algebraic'})")
                self.list_vars.addItem(item)

            # for param in self.model_host.get_parameters():
            #     item = QListWidgetItem(param.name)
            #     self.list_params.addItem(item)

            for eq in model.state_eqs + model.algebraic_eqs:
                print(eq)
                item = QListWidgetItem(f"{symbolic_to_string(eq)} ({'state' if eq in model.state_eqs else 'algebraic'})")
                self.list_eqns.addItem(item)

    def add_variable(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add Variable", "Variable name:")
        if not ok or not name:
            return
        # Ask type
        vtype, ok = QInputDialog.getItem(self, "Variable Type", "Select type:", ["state", "algebraic"], 0, False)
        if not ok:
            return
        # Add to model
        var, blk = variable(name, vtype)
        self.model_host.model.add(blk)
        self.refresh_lists()

    # find a way to add parameters

    def add_parameter(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add Parameter", "Parameter name:")
        if not ok or not name:
            return
        value, ok = QInputDialog.getDouble(self, "Parameter Value", f"Value for {name}:")
        if not ok:
            return
        self.model_host.add_parameter(name, value)
        self.refresh_lists()

    def add_equation(self):
        from PySide6.QtWidgets import QInputDialog
        expr, ok = QInputDialog.getText(self, "Add Equation", "Equation:")
        if not ok or not expr:
            return
        etype, ok = QInputDialog.getItem(self, "Equation Type", "Select type:", ["state", "algebraic"], 0, False)
        if not ok:
            return
        blk = equation(expr, etype)
        self.model_host.model.add(blk)
        self.refresh_lists()
