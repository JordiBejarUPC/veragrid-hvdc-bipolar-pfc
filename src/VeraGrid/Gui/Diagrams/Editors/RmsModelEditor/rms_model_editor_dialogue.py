# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import sys
from PySide6 import QtWidgets
from PySide6.QtGui import QStandardItemModel, QStandardItem

from VeraGrid.Gui.gui_functions import get_icon_list_model
from VeraGrid.Gui.RmsModelEditor.rms_model_editor import Ui_MainWindow
from VeraGrid.Gui.RmsModelEditor.block_editor import BlockEditor
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
import VeraGridEngine.Devices as dev

def add_vars(model, data_table_model):
    if model.children:
        for submodel in model.children:
            for var, eq in zip(submodel.state_vars, submodel.state_eqs):
                data_table_model.appendRow([
                    QStandardItem(var.name),
                    QStandardItem("state"),
                    QStandardItem(str(eq)),
                ])
            for var, eq in zip(submodel.algebraic_vars, submodel.algebraic_eqs):
                data_table_model.appendRow([
                    QStandardItem(var.name),
                    QStandardItem("algebraic"),
                    QStandardItem(str(eq)),
                ])
            for const in submodel.parameters:
                data_table_model.appendRow([
                    QStandardItem(const.name),
                    QStandardItem("parameter"),
                    QStandardItem(str(const.value)),
                ])
            add_vars(submodel, data_table_model)


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



class RmsModelEditorGUI(QtWidgets.QMainWindow):
    """
    RmsModelEditorGUI
    """
    def __init__(self, api_object, parent=None, ):
        """

        :param parent:
        """
        QtWidgets.QMainWindow.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.api_object = api_object
        self.setWindowTitle('RMS Model editor')

        self.model_host: DynamicModelHost = api_object.rms_model
        self.editor = BlockEditor(block=self.model_host.model,
                                  diagram=self.model_host.diagram)
        self.editor.rebuild_scene_from_diagram()

        self.ui.editorLayout.addWidget(self.editor)

        # Table model for variables/equations (right side)
        self._data_table_model = QStandardItemModel()
        self.ui.datatableView.setModel(self._data_table_model)

        # Connect category selection to table update
        self.ui.datalistWidget.itemSelectionChanged.connect(self.update_table)


    @property
    def model(self):
        return self.editor.main_block


    def update_table(self):
        items = self.ui.datalistWidget.selectedItems()
        if not items:
            return

        category = items[0].text()
        self._data_table_model.clear()
        self._data_table_model.setHorizontalHeaderLabels(["Name", "Type", "Equation"])

        add_vars(self.model, self._data_table_model)

    def extract_dae(self):
        eqs = self.editor.run()

        for eq in eqs:
            print(str(eq))

    # def exec(self):
    #     app = QtWidgets.QApplication(sys.argv)
    #     self.resize(1.61 * 700.0, 600.0)  # golden ratio
    #     self.show()
    #     sys.exit(app.exec())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    md = dev.DynamicModelHost()
    window = RmsModelEditorGUI(md)
    window.resize(1.61 * 700.0, 600.0)  # golden ratio
    window.show()
    sys.exit(app.exec())
