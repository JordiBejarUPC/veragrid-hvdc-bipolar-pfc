# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import sys
from typing import List, TYPE_CHECKING
import numpy as np
from PySide6 import QtWidgets

from VeraGrid.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import haversine_distance
from VeraGrid.Gui.ProceduralGrid.procedural_grid_ui import Ui_Dialog
from VeraGrid.Gui.gui_functions import get_list_model, enums_to_model
from VeraGridEngine.enumerations import ProceduralGridMethods
from VeraGridEngine.Topology.Procedural.procedural_grid_engine import Graph
#from VeraGridEngine.Devices.multi_circuit import MultiCircuit

if TYPE_CHECKING:
    from VeraGrid.Gui.Main.SubClasses.simulations import SimulationsMain


class ProceduralGridWindow(QtWidgets.QDialog):
    """
    SystemScaler GUI
    """

    def __init__(self, app: SimulationsMain, parent=None):
        """

        :param parent:
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle('Procedural grid expansion')

        # Setup combobox
        self.methods_dict, methods_mdl = enums_to_model(
            [ProceduralGridMethods.SteinerAlone,
             ProceduralGridMethods.SteinerAndOptimization]
        )
        self.ui.methodComboBox.setModel(methods_mdl)
        self.ui.methodComboBox.setCurrentIndex(0)

        # setup candidates

        # setup connection substations
        self.connection_substations_graphics_list: List[SubstationGraphicItem] = list()
        self.candidate_list: List[SubstationGraphicItem] = list()
        self.all_substations_graphics_in_diagram_list: List[SubstationGraphicItem] = list()
        for se_idx, se_api_object, se_graphic in app.get_current_diagram_substations():

            self.all_substations_graphics_in_diagram_list.append(se_graphic)

            if se_graphic.isSelected():
                self.connection_substations_graphics_list.append(se_graphic)

        self.ui.targetSubstationListView.setModel(get_list_model(
            [se_graphic.api_object for se_graphic in self.connection_substations_graphics_list]
        ))

        # Button click
        self.ui.computeButton.clicked.connect(self.compute)
        self.ui.computeCandidatesButton.clicked.connect(self.compute_candidates)

    def compute_candidates(self):
        """

        :return:
        """
        n_number = len(self.connection_substations_graphics_list)
        mc_number = len(self.all_substations_graphics_in_diagram_list)
        top_n = self.ui.topClosestSpinBox.value()

        distances = np.zeros((mc_number, n_number))

        for j, se_graphic_target in enumerate(self.connection_substations_graphics_list):
            for i, se_graphic_candidate in enumerate(self.all_substations_graphics_in_diagram_list):

                distances[i, j] = haversine_distance(
                    lat1=se_graphic_candidate.lat,
                    lon1=se_graphic_candidate.lon,
                    lat2=se_graphic_target.lat,
                    lon2=se_graphic_target.lon
                )

        if distances.shape[0] > 0:

            distances2 = np.min(distances, axis=1)
            sorted_indices = np.argsort(distances2, axis=0)

            self.candidate_list.clear()
            for i in sorted_indices[:top_n]:
                self.candidate_list.append(self.all_substations_graphics_in_diagram_list[i])

            # display the candidates list
            self.ui.candidateSubstationListView.setModel(get_list_model(
                [se_graphic.api_object for se_graphic in self.candidate_list]
            ))

    def compute(self):
        """
        Computation
        :return:
        """
        method: ProceduralGridMethods = self.methods_dict[self.ui.methodComboBox.currentText()]

        if method == ProceduralGridMethods.SteinerAlone:
            # 1. Fetch coordinates
            coord_M = np.array([[sg.lat, sg.lon] for sg in self.candidate_list])
            coord_N = np.array([[sg.lat, sg.lon] for sg in self.connection_substations_graphics_list])
            # TODO: Get the voltages you inputed in the substations.
            #  The idea is to get the electrical element form the graphic element and then use get_substaiton_buses()
            # print(MultiCircuit.get_substation_buses(self.candidate_list[0].api_object))
            Vnom_kV_M = None
            Vnom_kV_N = None

            # 2A. Run VSA: Create an initial radial topology with a Steiner tree approach
            network = Graph(coord_M, coord_N, max_iteration=15000)
            raw_vector, history = network.run_vsa()
            raw_steiner_pts = network.decode_solution(raw_vector)

            # 2B. Prune redundant nodes
            final_steiner_pts = network.prune_redundant_nodes(raw_steiner_pts)

            # 2C. Get edges of the final network
            coords_final_network = np.vstack((network.all_coords, final_steiner_pts))
            _, final_mst = network.get_mst_cost(coords_final_network)
            edges = network.generate_edges(final_mst)

            # 2E. Assign voltages to Steiner Points
            closest_voltage = []
            for i in range(len(final_steiner_pts)):
                steiner_coord = final_steiner_pts[i]
                dists_to_M = np.linalg.norm(coord_M - steiner_coord, axis=1)
                dists_to_N = np.linalg.norm(coord_N - steiner_coord, axis=1)
                min_dist_M = np.min(dists_to_M)
                min_dist_N = np.min(dists_to_N)
                if min_dist_M < min_dist_N:
                    closest_bus_idx = np.argmin(dists_to_M)
                    closest_voltage.append(Vnom_kV_M[closest_bus_idx])
                else:
                    closest_bus_idx = np.argmin(dists_to_N)
                    closest_voltage.append(Vnom_kV_N[closest_bus_idx])

            # 3. Convert to VeraGrid object
            # TODO: Convert to VeraGrid object

            # 4. Display in the diagram
            # TODO: Display in the diagram

        # elif method == ProceduralGridMethods.SteinerAndOptimization:
            # TODO: Implement steiner tree + optimization
