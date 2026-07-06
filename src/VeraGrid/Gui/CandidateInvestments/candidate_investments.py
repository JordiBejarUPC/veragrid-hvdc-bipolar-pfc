# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Simulations.InvestmentsEvaluation.CandidateGeneration.candidate_generation_driver import (
    CandidateGenerationDriver,
)
from VeraGridEngine.Simulations.InvestmentsEvaluation.CandidateGeneration.candidate_generation_options import (
    CandidateGenerationOptions,
)
from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget
from VeraGrid.Gui.general_dialogues import LogsDialogue

if TYPE_CHECKING:
    from VeraGrid.Gui.Main.SubClasses.simulations import SimulationsMain


class CandidateInvestmentsWindow(QtWidgets.QDialog):
    """
    Candidate-investment generator window.

    Runs the transmission-expansion candidate-generation pipeline (AC power flow base case ->
    LODF N-1 screening -> PTDF-ranked reinforcements -> shortlist -> AC power-flow verification)
    and lets the user pick which of the ranked candidates to materialise as investments, mirroring
    the ``ProceduralGridWindow`` accept flow.
    """

    def __init__(self, app: SimulationsMain, parent=None):
        """
        :param app: The main application (SimulationsMain).
        :param parent: Optional Qt parent.
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.setWindowTitle('Candidate investment generator')
        self.app = app

        # State of the last successful run. "Add investments" can only run once these are populated.
        self._driver: Optional[CandidateGenerationDriver] = None
        self._candidate_items: List[QtWidgets.QListWidgetItem] = list()

        # ------------------------------------------------------------------------------------------
        # Widgets
        # ------------------------------------------------------------------------------------------
        main_layout = QtWidgets.QVBoxLayout(self)

        # --- options row: number of new-line corridors enumerated per violation ---
        options_layout = QtWidgets.QHBoxLayout()
        options_layout.addWidget(QtWidgets.QLabel("Corridors per violation"))
        self.top_n_spin = QtWidgets.QSpinBox()
        self.top_n_spin.setMinimum(1)
        self.top_n_spin.setMaximum(50)
        self.top_n_spin.setValue(5)
        self.top_n_spin.setToolTip("Number of nearby substation corridors enumerated as new-line "
                                   "candidates for each flagged violation.")
        options_layout.addWidget(self.top_n_spin)
        options_layout.addStretch(1)
        self.run_button = QtWidgets.QPushButton("Run")
        self.run_button.setToolTip("Run the candidate-generation pipeline.")
        self.run_button.clicked.connect(self.run)
        options_layout.addWidget(self.run_button)
        main_layout.addLayout(options_layout)

        # --- base case / N-1 report ---
        main_layout.addWidget(QtWidgets.QLabel("Base case and N-1 screening"))
        self.report_text = QtWidgets.QPlainTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setMaximumHeight(160)
        main_layout.addWidget(self.report_text)

        # --- ranked candidates (checkable) ---
        main_layout.addWidget(QtWidgets.QLabel("Ranked candidate reinforcements"))
        self.candidate_list = QtWidgets.QListWidget()
        main_layout.addWidget(self.candidate_list)

        # --- accept row ---
        accept_layout = QtWidgets.QHBoxLayout()
        accept_layout.addWidget(QtWidgets.QLabel("Investment group name"))
        self.group_name_edit = QtWidgets.QLineEdit()
        self.group_name_edit.setText("Investment " + str(len(self.app.circuit.investments_groups)))
        accept_layout.addWidget(self.group_name_edit)
        self.add_button = QtWidgets.QPushButton("Add selected investments")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self.add_investments)
        accept_layout.addWidget(self.add_button)
        main_layout.addLayout(accept_layout)

        self.setLayout(main_layout)
        self.resize(560, 520)

    # ----------------------------------------------------------------------------------------------
    # Run the pipeline
    # ----------------------------------------------------------------------------------------------
    def run(self) -> None:
        """
        Run the candidate-generation pipeline synchronously and populate the report and the
        ranked candidate list. "Add selected investments" is enabled only when candidates result.
        """
        self.add_button.setEnabled(False)
        self.candidate_list.clear()
        self._candidate_items.clear()
        self.report_text.setPlainText("Running...")
        QtGui.QGuiApplication.processEvents()

        options = CandidateGenerationOptions(top_n_corridors=self.top_n_spin.value())
        pf_options = self.app.get_selected_power_flow_options()

        driver = CandidateGenerationDriver(grid=self.app.circuit,
                                           options=options,
                                           pf_options=pf_options)

        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CursorShape.WaitCursor))
        try:
            driver.run()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self._driver = driver
        results = driver.results

        # Fill the base-case / N-1 report
        self.report_text.setPlainText(results.summary_text())

        # Fill the ranked candidate list with checkable items
        for candidate in results.candidates:
            item = QtWidgets.QListWidgetItem(candidate.label())
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            # Stash the candidate index so we can recover the object on accept.
            item.setData(QtCore.Qt.ItemDataRole.UserRole, candidate)
            self.candidate_list.addItem(item)
            self._candidate_items.append(item)

        self.add_button.setEnabled(len(results.candidates) > 0)

        # Surface any log messages from the run.
        if driver.logger.has_logs():
            LogsDialogue('Candidate investment generator log', driver.logger).exec()

    # ----------------------------------------------------------------------------------------------
    # Materialise the selected candidates as investments
    # ----------------------------------------------------------------------------------------------
    def add_investments(self) -> None:
        """
        Create an ``InvestmentsGroup`` and one ``Investment`` per checked candidate, adding any
        new-line devices to the circuit and drawing them on the currently selected diagram.
        """
        if self._driver is None:
            return

        selected = [item.data(QtCore.Qt.ItemDataRole.UserRole)
                    for item in self._candidate_items
                    if item.checkState() == QtCore.Qt.CheckState.Checked]

        if len(selected) == 0:
            QtWidgets.QMessageBox.information(self, "Candidate investment generator",
                                              "No candidates selected.")
            return

        logger = Logger()
        group = dev.InvestmentsGroup(
            idtag=None,
            name=self.group_name_edit.text(),
            category="single" if len(selected) == 1 else "multiple"
        )
        self.app.circuit.add_investments_group(group)

        new_lines: List[dev.Line] = list()
        for candidate in selected:
            # Each candidate creates its Investment (and any new device) against the circuit.
            new_line = candidate.apply(circuit=self.app.circuit, group=group, logger=logger)
            if new_line is not None:
                new_lines.append(new_line)

        # Draw any newly created lines on the currently selected diagram. New-line candidates
        # connect existing buses, so their endpoints already exist on the diagram.
        self._draw_new_lines(new_lines)

        if logger.has_logs():
            LogsDialogue('Candidate investment generator log', logger).exec()

        self.close()

    def _draw_new_lines(self, new_lines: List[dev.Line]) -> None:
        """
        Draw the given new lines on the currently selected diagram widget, if any.

        :param new_lines: Lines that were added to the circuit.
        """
        if len(new_lines) == 0:
            return

        diagram = self.app.get_selected_diagram_widget()

        if isinstance(diagram, SchematicWidget):
            for line in new_lines:
                if diagram.graphics_manager.query(elm=line) is None:
                    diagram.add_api_line(branch=line)
        elif isinstance(diagram, GridMapWidget):
            for line in new_lines:
                if diagram.graphics_manager.query(elm=line) is None:
                    diagram.add_api_line(api_object=line)
