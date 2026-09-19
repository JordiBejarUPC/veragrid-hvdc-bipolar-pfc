# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.DeviceEditors.TowerBuilder.tower_builder import Ui_TowerBuilderDialog
from VeraGrid.Gui.DeviceEditors.UndergroundCableBuilder.table_models import (
    UndergroundCableCatalogueModel,
    UndergroundCableSystemModel,
)
from VeraGrid.Gui.general_dialogues import LogsDialogue
from VeraGrid.Gui.pandas_model import PandasModel
from VeraGridEngine.basic_structures import CxMat, Logger
from VeraGridEngine.Devices.Branches.underground_cable_type import UndergroundCableType
from VeraGridEngine.Devices.Branches.underground_line_type import CableInSystem, UndergroundLineType


class UndergroundCableBuilderGUI(QtWidgets.QDialog):
    """Edit and calculate a PowerFactory-style underground cable system."""

    __slots__ = ('ui', 'system', 'catalogue_model', 'composition_model', 'rated_current_spin_box')

    def __init__(self,
                 system: UndergroundLineType | None = None,
                 cables_catalogue: List[UndergroundCableType] | None = None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """Create the cable-system builder.

        :param system: Existing underground-line template, or ``None`` for a new one.
        :param cables_catalogue: Physical cable constructions available to the system.
        :param parent: Optional Qt parent widget.
        :return: None.
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui: Ui_TowerBuilderDialog = Ui_TowerBuilderDialog()
        self.ui.setupUi(self)
        self.system: UndergroundLineType = UndergroundLineType() if system is None else system
        catalogue: List[UndergroundCableType] = list() if cables_catalogue is None else cables_catalogue

        # The existing tower form already has exactly the controls needed by a
        # physical cable system, so only its visible terminology changes.
        self.setWindowTitle(self.tr('Underground cable builder'))
        self.ui.label_12.setText(self.tr('Cable construction catalogue'))
        self.ui.label_10.setText(self.tr('Cable system composition'))
        self.ui.label_4.setText(self.tr('Cable positions'))
        self.ui.rho_doubleSpinBox.setSuffix(self.tr(' Ω·m'))
        self.ui.add_to_tower_pushButton.setToolTip(self.tr('Add cable to system'))
        self.ui.delete_from_tower_pushButton.setToolTip(self.tr('Delete cable from system'))

        self.ui.name_lineEdit.setText(self.system.name)
        self.ui.rho_doubleSpinBox.setValue(self.system.earth_resistivity)
        self.ui.frequency_doubleSpinBox.setValue(self.system.freq)
        self.ui.voltage_doubleSpinBox.setValue(self.system.Vnom)

        # Rated current belongs to TypCabsys (dInom), not to the physical
        # TypCab construction, so it lives with the other system-wide inputs.
        rated_current_label: QtWidgets.QLabel = QtWidgets.QLabel(self.tr('Rated current'), self.ui.frame_6)
        self.rated_current_spin_box: QtWidgets.QDoubleSpinBox = QtWidgets.QDoubleSpinBox(self.ui.frame_6)
        self.rated_current_spin_box.setDecimals(6)
        self.rated_current_spin_box.setMaximum(1.0e9)
        self.rated_current_spin_box.setSuffix(self.tr(' kA'))
        self.rated_current_spin_box.setValue(self.system.Imax)
        self.ui.horizontalLayout_3.addWidget(rated_current_label)
        self.ui.horizontalLayout_3.addWidget(self.rated_current_spin_box)

        self.catalogue_model: UndergroundCableCatalogueModel = UndergroundCableCatalogueModel(
            cables=catalogue,
            edit_callback=self.compute,
        )
        self.composition_model: UndergroundCableSystemModel = UndergroundCableSystemModel(
            system=self.system,
            edit_callback=self.compute,
        )
        self.ui.wires_tableView.setModel(self.catalogue_model)
        self.ui.tower_tableView.setModel(self.composition_model)
        self.ui.wires_tableView.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.ui.tower_tableView.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )

        self.ui.matrixViewComboBox.addItems((
            self.tr('Primitive series impedance [Ω/km]'),
            self.tr('Reduced series impedance [Ω/km]'),
            self.tr('Sequence series impedance [Ω/km]'),
            self.tr('Primitive shunt admittance [μS/km]'),
            self.tr('Reduced shunt admittance [μS/km]'),
            self.tr('Sequence shunt admittance [μS/km]'),
        ))
        self.ui.main_splitter.setStretchFactor(0, 6)
        self.ui.main_splitter.setStretchFactor(1, 2)

        self.ui.add_to_tower_pushButton.clicked.connect(self.add_cable_to_system)
        self.ui.delete_from_tower_pushButton.clicked.connect(self.delete_cable_from_system)
        self.ui.compute_pushButton.clicked.connect(self.compute_button_clicked)
        self.ui.acceptButton.clicked.connect(self.accept)
        self.ui.name_lineEdit.textChanged.connect(self.name_changed)
        self.ui.matrixViewComboBox.currentIndexChanged.connect(self.show_matrix)
        self.ui.frequency_doubleSpinBox.valueChanged.connect(self.compute)
        self.ui.rho_doubleSpinBox.valueChanged.connect(self.compute)
        self.ui.voltage_doubleSpinBox.valueChanged.connect(self.compute)
        self.rated_current_spin_box.valueChanged.connect(self.compute)

        if self.system.has_physical_data():
            self.compute()
        else:
            self.plot()

    def done(self, result: int) -> None:
        """Dispose plotting resources before closing the dialog.

        :param result: Qt dialog result code.
        :return: None.
        """
        self.ui.plotwidget.dispose()
        QtWidgets.QDialog.done(self, result)

    def show_message(self, text: str, title: str = 'Warning') -> None:
        """Display one informational message.

        :param text: Message text.
        :param title: Message-box title.
        :return: None.
        """
        message: QtWidgets.QMessageBox = QtWidgets.QMessageBox(self)
        message.setIcon(QtWidgets.QMessageBox.Icon.Information)
        message.setText(text)
        message.setWindowTitle(title)
        message.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        message.exec()

    def name_changed(self, text: str) -> None:
        """Apply the edited system name.

        :param text: New name.
        :return: None.
        """
        self.system.name = text

    def add_cable_to_system(self) -> None:
        """Add the selected physical construction to the composition.

        :return: None.
        """
        selected_row: int = self.ui.wires_tableView.currentIndex().row()
        if 0 <= selected_row < len(self.catalogue_model.cables):
            cable: UndergroundCableType = self.catalogue_model.cables[selected_row]
            next_phase: int = self.composition_model.rowCount() + 1
            relation: CableInSystem = CableInSystem(
                cable=cable,
                xpos=0.1 * float(next_phase - 1),
                ypos=1.0,
                phase=next_phase,
            )
            self.composition_model.add(relation=relation)
            self.compute()
        else:
            self.show_message(self.tr('Select a cable construction from the catalogue.'))

    def delete_cable_from_system(self) -> None:
        """Delete the selected cable from the composition.

        :return: None.
        """
        selected_row: int = self.ui.tower_tableView.currentIndex().row()
        if 0 <= selected_row < self.composition_model.rowCount():
            self.composition_model.delete(row=selected_row)
            self.compute()
        else:
            self.show_message(self.tr('Select a cable from the system composition.'))

    def compute(self, unused_value: object | None = None) -> tuple[bool, Logger]:
        """Calculate all cable matrices from the current visible inputs.

        :param unused_value: Optional Qt signal value.
        :return: Calculation state and validation log.
        """
        self.system.freq = self.ui.frequency_doubleSpinBox.value()
        self.system.earth_resistivity = self.ui.rho_doubleSpinBox.value()
        self.system.Vnom = self.ui.voltage_doubleSpinBox.value()
        self.system.Imax = self.rated_current_spin_box.value()
        relation: CableInSystem
        for relation in self.system.cables_in_system.data:
            if relation.cable is not None:
                relation.name = relation.cable.name
            else:
                pass
        self.composition_model.layoutChanged.emit()
        logger: Logger = Logger()
        valid: bool = self.system.check(logger=logger)
        if valid:
            calculated: bool = self.system.compute(logger=logger)
            if calculated:
                self.show_matrix()
            else:
                pass
        else:
            calculated = False
        self.plot()
        return calculated, logger

    def compute_button_clicked(self) -> None:
        """Calculate and show validation messages when inputs are incomplete.

        :return: None.
        """
        calculated: bool
        logger: Logger
        calculated, logger = self.compute()
        if calculated:
            pass
        else:
            log_dialog: LogsDialogue = LogsDialogue(name=self.tr('Cable calculation'), logger=logger)
            log_dialog.exec()

    def _matrix_labels(self, primitive: bool) -> List[str]:
        """Build labels for primitive or reduced phase matrices.

        :param primitive: Include one metallic-sheath label per cable.
        :return: Matrix row and column labels.
        """
        phase_labels: List[str] = list()
        phase: int
        for phase in self.system.z_phases_nabc:
            phase_labels.append(f'Phase {int(phase)}')
        if primitive:
            sheath_labels: List[str] = list()
            for phase in self.system.z_phases_nabc:
                sheath_labels.append(f'Sheath {int(phase)}')
            labels: List[str] = phase_labels + sheath_labels
        else:
            labels = phase_labels
        return labels

    def _sequence_labels(self, matrix: CxMat) -> List[str]:
        """Build sequence labels using the matrix's circuit-block order.

        :param matrix: Complete sequence matrix.
        :return: Sequence labels.
        """
        circuit_count: int = matrix.shape[0] // 3
        labels: List[str] = list()
        circuit_index: int
        sequence_index: int
        for circuit_index in range(circuit_count):
            for sequence_index in range(3):
                labels.append(f'Seq {sequence_index} @ circuit {circuit_index + 1}')
        return labels

    def _set_matrix(self, matrix: CxMat | None, labels: List[str], scale: float = 1.0) -> None:
        """Display one calculated matrix.

        :param matrix: Matrix to display, or ``None`` when unavailable.
        :param labels: Row and column labels.
        :param scale: Unit conversion applied for display.
        :return: None.
        """
        if matrix is not None:
            data_frame: pd.DataFrame = pd.DataFrame(
                data=np.asarray(matrix) * scale,
                columns=labels,
                index=labels,
            )
            self.ui.matrixTableView.setModel(PandasModel(data_frame))
            self.ui.matrixTableView.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        else:
            self.ui.matrixTableView.setModel(None)

    def show_matrix(self, unused_index: int | None = None) -> None:
        """Display the selected primitive, reduced or sequence matrix.

        :param unused_index: Optional Qt signal index.
        :return: None.
        """
        matrix_index: int = self.ui.matrixViewComboBox.currentIndex()
        if matrix_index == 0:
            self._set_matrix(
                matrix=self.system.z_primitive,
                labels=self._matrix_labels(primitive=True),
            )
        elif matrix_index == 1:
            self._set_matrix(
                matrix=self.system.z_nabc,
                labels=self._matrix_labels(primitive=False),
            )
        elif matrix_index == 2:
            sequence_impedance: CxMat | None = self.system.z_seq
            labels: List[str] = (
                self._sequence_labels(matrix=sequence_impedance)
                if sequence_impedance is not None
                else list()
            )
            self._set_matrix(matrix=sequence_impedance, labels=labels)
        elif matrix_index == 3:
            self._set_matrix(
                matrix=self.system.y_primitive,
                labels=self._matrix_labels(primitive=True),
                scale=1.0e6,
            )
        elif matrix_index == 4:
            self._set_matrix(
                matrix=self.system.y_nabc,
                labels=self._matrix_labels(primitive=False),
                scale=1.0e6,
            )
        else:
            sequence_admittance: CxMat | None = self.system.y_seq
            labels = (
                self._sequence_labels(matrix=sequence_admittance)
                if sequence_admittance is not None
                else list()
            )
            self._set_matrix(matrix=sequence_admittance, labels=labels, scale=1.0e6)

    def plot(self) -> None:
        """Redraw the cable positions with burial depth increasing downwards.

        :return: None.
        """
        self.ui.plotwidget.clear()
        figure: Figure = self.ui.plotwidget.get_figure()
        figure.set_facecolor('white')
        axes: Axes = self.ui.plotwidget.get_axis()
        self.system.plot(ax=axes)
        figure.tight_layout()
        self.ui.plotwidget.redraw()
