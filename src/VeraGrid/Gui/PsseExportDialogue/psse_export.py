# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Set
from PySide6 import QtWidgets
from PySide6.QtGui import QClipboard
import numpy as np
from VeraGrid.Gui.GridReduce.grid_reduce_gui import Ui_ReduceDialog
from VeraGrid.Gui.general_dialogues import LogsDialogue
from VeraGrid.Gui.messages import yes_no_question, warning_msg
from VeraGrid.Gui.gui_functions import get_list_model, enums_to_model
from VeraGrid.Session.session import SimulationSession
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Topology.GridReduction.di_shi_grid_reduction import di_shi_reduction
from VeraGridEngine.Topology.GridReduction.ptdf_grid_reduction import ptdf_reduction, ptdf_reduction_projected
from VeraGridEngine.Topology.GridReduction.ward_equivalents import ward_standard_reduction
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import GridReductionMethod, BusReductionMethod


class PsseExportDialogue(QtWidgets.QDialog):
    """
    GridMergeDialogue
    """

    def __init__(self, grid: MultiCircuit, session: SimulationSession):
        """
        GridMergeDialogue
        :param grid: MultiCircuit instance
        :param session: SimulationSession instance to query the power flow
        """
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_ReduceDialog()
        self.ui.setupUi(self)
        self.setWindowTitle('PSS/e export')
        self.setModal(True)

        self.logger = Logger()
        self.logs_dialogue: LogsDialogue | None = None

        self.ui.raw_export_version_comboBox.addItems(["33", "35"])

        self.ui.exportButton.clicked.connect(self.export)

    def export(self):
        raw_version = self.ui.raw_export_version_comboBox.currentText()

        options = filedrv.FileSavingOptions(cgmes_boundary_set=self.current_boundary_set,
                                            sessions_data=sessions_data,
                                            dictionary_of_json_files=json_files)
