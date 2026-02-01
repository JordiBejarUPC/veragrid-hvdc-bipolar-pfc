# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from PySide6 import QtWidgets
from VeraGrid.Gui.CGMESDialogue.cgmes_export_gui import Ui_CgmesExportDialog
from VeraGrid.Session.session import SimulationSession
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
import VeraGrid.Session.file_handler as filedrv
import VeraGrid.Gui.gui_functions as gf
from VeraGridEngine.enumerations import CGMESVersions
from VeraGridEngine.IO.cim.cgmes.cgmes_export import get_available_cgmes_profiles
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType


class GridExportDialogue(QtWidgets.QDialog):
    """
    GridMergeDialogue
    """

    def __init__(self, grid: MultiCircuit, session: SimulationSession, project_directory: str = ""):
        """
        GridMergeDialogue
        :param grid: MultiCircuit instance
        :param session: SimulationSession instance to query the power flow
        :param project_directory: Set of buses (Bus objects) to reduce
        """
        QtWidgets.QDialog.__init__(self)
        self.ui = Ui_CgmesExportDialog()
        self.ui.setupUi(self)
        self.setWindowTitle('CGMES export')
        self.setModal(True)

        self.grid = grid

        self.sessions_data = session

        self.project_directory = project_directory

        self.current_boundary_set = ""

        self.cgmes_version_dict = {x.value: x for x in [CGMESVersions.v2_4_15,
                                                        CGMESVersions.v3_0_0]}
        self.ui.cgmes_version_comboBox.setModel(gf.get_list_model(list(self.cgmes_version_dict.keys())))

        self.cgmes_profiles_dict = {key: CgmesProfileType(key) for key, val in
                                    get_available_cgmes_profiles(cgmes_version=CGMESVersions.v2_4_15).items()}

        self.ui.cgmes_profiles_listView.setModel(gf.get_list_model(list(self.cgmes_profiles_dict.keys()),
                                                                   checks=True, check_value=True))

        # Buttons
        self.ui.selectCGMESBoundarySetButton.clicked.connect(self.select_cgmes_boundary_set)
        self.ui.exportButton.clicked.connect(self.export)

        # change
        self.ui.cgmes_version_comboBox.currentTextChanged.connect(self.cgmes_version_change)

    def cgmes_version_change(self):
        """
        On GUI cgmes version change, display only the supported profiles
        """
        cgmes_version = self.cgmes_version_dict[self.ui.cgmes_version_comboBox.currentText()]

        self.cgmes_profiles_dict = {key: CgmesProfileType(key) for key, val in
                                    get_available_cgmes_profiles(cgmes_version=cgmes_version).items()}

        self.ui.cgmes_profiles_listView.setModel(gf.get_list_model(list(self.cgmes_profiles_dict.keys()),
                                                                   checks=True, check_value=True))

    def select_cgmes_boundary_set(self):
        """
        Select the current boundary set
        """
        files_types = "Boundary set (*.zip)"

        dialogue = QtWidgets.QFileDialog(None,
                                         caption='Select Boundary set file',
                                         directory=self.project_directory,
                                         filter=files_types)
        if dialogue.exec():
            filenames = dialogue.selectedFiles()
            if len(filenames) > 0:
                self.current_boundary_set = filenames[0]
                self.ui.cgmes_boundary_set_label.setText(self.current_boundary_set)

    def export(self) -> None:
        """
        The elements of the grid will be added with new idtags.
        This is useful in the case you want to compose a new grid from grids that are the same.
        :return:
        """
        cgmes_version = self.cgmes_version_dict[self.ui.cgmes_version_comboBox.currentText()]
        cgmes_profiles_txt = gf.get_checked_values(mdl=self.ui.cgmes_profiles_listView.model())
        cgmes_profiles = [self.cgmes_profiles_dict[e] for e in cgmes_profiles_txt]
        cgmes_one_file_per_profile = self.ui.cgmes_single_profile_per_file_checkBox.isChecked()
        cgmes_map_areas_like_raw = self.ui.cgmes_map_regions_like_raw_checkBox.isChecked()

        options = filedrv.FileSavingOptions(cgmes_boundary_set=self.current_boundary_set,
                                            sessions_data=self.sessions_data.get_save_data(),
                                            dictionary_of_json_files=dict(),
                                            cgmes_version=cgmes_version,
                                            cgmes_profiles=cgmes_profiles,
                                            cgmes_one_file_per_profile=cgmes_one_file_per_profile,
                                            cgmes_map_areas_like_raw=cgmes_map_areas_like_raw)
