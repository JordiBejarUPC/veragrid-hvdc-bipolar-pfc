# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import List, Optional, Set, TYPE_CHECKING
import numpy as np
import networkx as nx
from PySide6 import QtWidgets

from VeraGrid.ThirdParty.adjustText import adjust_text
from VeraGrid.Gui.Diagrams.MapWidget.Substation.substation_graphic_item import SubstationGraphicItem
from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import haversine_distance, GridMapWidget
from VeraGridEngine.Devices.Diagrams.map_location import MapLocation
import VeraGridEngine.Devices as dev
from VeraGrid.Gui.ProceduralGrid.procedural_grid_ui import Ui_Dialog
from VeraGrid.Gui.gui_functions import get_list_model, enums_to_model
from VeraGridEngine.enumerations import ProceduralGridMethods
from VeraGridEngine.Topology.Procedural.procedural_grid_engine import ProceduralGridComputationEngine
from VeraGridEngine.basic_structures import Logger
from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import make_diagram_from_buses, SchematicWidget
from VeraGrid.Gui.ProceduralGrid.voltage_warning import VoltageWarningDialog
from VeraGrid.Gui.general_dialogues import LogsDialogue, CheckListDialogue

if TYPE_CHECKING:
    from VeraGrid.Gui.Main.SubClasses.simulations import SimulationsMain
    from VeraGridEngine.Devices.types import ALL_DEV_TYPES
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit


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
        self.app = app

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

        # State of the last successful preview. Accept can only run once these are populated.
        self._engine: Optional[ProceduralGridComputationEngine] = None
        self._expanded_grid: Optional[MultiCircuit] = None
        self._method: Optional[ProceduralGridMethods] = None
        self._logger: Optional[Logger] = None

        # Accept stays disabled until the user has previewed a result
        self.ui.acceptButton.setEnabled(False)

        # Button click
        self.ui.previewButton.clicked.connect(self.preview)
        self.ui.acceptButton.clicked.connect(self.accept_result)
        self.ui.computeCandidatesButton.clicked.connect(self.compute_candidates)

        # Any change to the inputs invalidates the previously previewed result so the user
        # cannot accept a graph that no longer matches the parameters on screen
        self.ui.methodComboBox.currentIndexChanged.connect(self._invalidate_preview)

    def _invalidate_preview(self) -> None:
        """
        Discard the previously computed preview state and disable Accept until the
        user previews again. Called whenever an input that feeds the engine changes.
        """
        self._engine = None
        self._expanded_grid = None
        self._method = None
        self._logger = None
        self.ui.acceptButton.setEnabled(False)

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
            for i in sorted_indices:
                if len(self.candidate_list) >= top_n:
                    break
                candidate = self.all_substations_graphics_in_diagram_list[i]
                if candidate not in self.connection_substations_graphics_list:
                    self.candidate_list.append(candidate)

            # display the candidates list
            self.ui.candidateSubstationListView.setModel(get_list_model(
                [se_graphic.api_object for se_graphic in self.candidate_list]
            ))

        # Recomputed candidates change the engine inputs, so invalidate any prior preview
        self._invalidate_preview()

    def _check_substation_voltages(self, substations):
        """
        Returns offenders and valid voltages.
        Offenders are (substation_name, voltage) pairs for any bus
        whose Vnom does not appear on any branch in the existing grid.
        """
        known_voltages = set()
        for branch in self.app.circuit.get_branches(add_vsc=True, add_hvdc=True, add_switch=True):
            known_voltages.add(branch.bus_from.Vnom)
            known_voltages.add(branch.bus_to.Vnom)

        offenders = []
        for sg in substations:
            for bus in self.app.circuit.get_substation_buses(sg):
                if bus.Vnom not in known_voltages:
                    offenders.append((sg.name, bus.Vnom))

        return offenders, sorted(known_voltages)

    def preview(self) -> None:
        """
        Validate inputs, run the expansion engine and draw the resulting topology
        on the embedded plot. Stores the engine result on the instance so that
        :meth:`accept_result` can apply it without recomputing.

        :return: ``None``.
        """
        # 1. Get the chosen method
        method: ProceduralGridMethods = self.methods_dict[self.ui.methodComboBox.currentText()]

        # 2. Extract the raw API objects from the graphic items
        target_objects = [se.api_object for se in self.connection_substations_graphics_list]
        candidate_objects = [se.api_object for se in self.candidate_list]

        # 3. Validate that all substation voltages exist in the grid
        offenders, valid_voltages = self._check_substation_voltages(target_objects + candidate_objects)
        if offenders:
            dlg = VoltageWarningDialog(offenders=offenders, valid_voltages=valid_voltages, parent=self)
            dlg.setModal(True)
            dlg.exec()
            # Voltage mismatch: do not enable Accept; user must fix inputs first
            self._invalidate_preview()
            return None
        else:
            pass

        # 4. Instantiate the engine and run the selected method
        logger = Logger()
        engine = ProceduralGridComputationEngine(
            grid=self.app.circuit,
            method=method,
            targets=target_objects,
            candidates=candidate_objects,
            logger=logger
        )

        if method == ProceduralGridMethods.SteinerAlone:
            expanded_grid = engine.run_steiner_alone()

        elif method == ProceduralGridMethods.SteinerAndOptimization:
            expanded_grid = engine.run_optimization()

        else:
            raise NotImplementedError(f"Method {method} not implemented")

        # 5. Persist the computed state so that Accept can apply it without recomputing,
        # then draw the topology on the embedded plot and enable Accept
        self._engine = engine
        self._expanded_grid = expanded_grid
        self._method = method
        self._logger = logger

        self._update_summary(engine=engine)
        self._draw_graph(engine=engine)
        self.ui.acceptButton.setEnabled(True)
        return None

    def accept_result(self) -> None:
        """
        Apply the previously previewed result to the application. Does nothing if
        no successful preview is currently held on the instance (Accept should be
        disabled in that case, but we guard against accidental double-clicks).

        :return: ``None``.
        """
        if self._engine is None or self._expanded_grid is None or self._method is None or self._logger is None:
            return None
        else:
            pass

        self._apply_to_app(engine=self._engine,
                           expanded_grid=self._expanded_grid,
                           method=self._method,
                           logger=self._logger)
        return None

    def _update_summary(self, engine: ProceduralGridComputationEngine) -> None:
        """
        Update the summary label above the plot with the count of new buses,
        lines and transformers that the previewed expansion would create.

        :param engine: The engine whose result is being summarised.
        """
        n_new_buses: int = len(engine.get_new_buses())
        n_new_lines: int = len(engine.get_new_lines())
        n_new_transformers: int = len(engine.get_new_transformers())
        self.ui.summaryLabel.setText(
            f'{n_new_buses} new bus(es), {n_new_lines} new line(s) and '
            f'{n_new_transformers} new transformer(s) will be added to the grid.'
        )

    def _draw_graph(self, engine: ProceduralGridComputationEngine) -> None:
        """
        Build a NetworkX graph from the engine result and render it on the
        embedded MatplotlibWidget. Existing buses (targets and candidates) are
        drawn in light blue; newly created buses are drawn in light green.

        :param engine: The engine whose buses and lines are used to build the graph.
        """
        all_buses: List[dev.Bus] = engine.get_buses()
        new_buses: List[dev.Bus] = engine.get_new_buses()
        new_lines: List[dev.Line] = engine.get_new_lines()
        new_transformers: List[dev.Transformer2W] = engine.get_new_transformers()

        # Build a set of new-bus names for O(1) membership checks
        new_bus_names: Set[str] = set()
        for bus in new_buses:
            new_bus_names.add(bus.name)

        G: nx.Graph = nx.Graph()
        pos: dict = dict()
        existing_node_names: List[str] = list()
        new_node_names: List[str] = list()

        # Add all buses as nodes, recording which colour group they belong to
        for bus in all_buses:
            G.add_node(bus.name)
            pos[bus.name] = (bus.longitude, bus.latitude)
            if bus.name in new_bus_names:
                new_node_names.append(bus.name)
            else:
                existing_node_names.append(bus.name)

        # Add new lines as edges
        for line in new_lines:
            G.add_edge(line.bus_from.name, line.bus_to.name)

        # Add new transformers as edges
        for transformer in new_transformers:
            G.add_edge(transformer.bus_from.name, transformer.bus_to.name)

        # Clear the matplotlib canvas before redrawing so successive Preview clicks
        # do not stack graphs on top of each other
        self.ui.plotWidget.clear()
        ax = self.ui.plotWidget.get_axis()

        # Draw existing buses in blue and new buses in green so the user can
        # clearly distinguish what is being added to the grid
        nx.draw_networkx_nodes(G, pos=pos, nodelist=existing_node_names,
                               ax=ax, node_color='lightblue', node_size=300)
        nx.draw_networkx_nodes(G, pos=pos, nodelist=new_node_names,
                               ax=ax, node_color='lightgreen', node_size=300)
        nx.draw_networkx_edges(G, pos=pos, ax=ax)

        # Place labels as Text objects first, then let adjustText reposition
        # them so that overlapping labels (including co-located nodes) are
        # spread apart automatically
        texts: List = list()
        for node, (x, y) in pos.items():
            texts.append(ax.text(x, y, node, fontsize=7))

        adjust_text(texts, ax=ax)

        self.ui.plotWidget.redraw()

    def _apply_to_app(self,
                      engine: ProceduralGridComputationEngine,
                      expanded_grid,
                      method: ProceduralGridMethods,
                      logger: Logger) -> None:
        """
        Apply the confirmed expansion result to the running application: create
        substations for new buses, update all open map widgets, build the schematic
        diagram, display the logger, and prompt for investment group assignment.

        :param engine: The engine whose results are being applied.
        :param expanded_grid: The expanded MultiCircuit returned by the engine.
        :param method: The method that was used (used for diagram naming).
        :param logger: The logger accumulating messages during the run.
        """
        # Create substations for new buses so map lines can reference them
        for bus in engine.get_new_buses():
            if bus.substation is None:
                substation = dev.Substation(
                    name=bus.name,
                    latitude=bus.latitude,
                    longitude=bus.longitude,
                )
                bus.substation = substation
                self.app.circuit.add_substation(substation)
            else:
                pass

        # Draw new elements on all open map widgets
        for map_widget in self.app.diagram_widgets_list:
            if isinstance(map_widget, GridMapWidget):
                for bus in engine.get_new_buses():
                    if map_widget.graphics_manager.query(elm=bus.substation) is None:
                        map_widget.add_api_substation(api_object=bus.substation,
                                                      lat=bus.latitude,
                                                      lon=bus.longitude)
                    else:
                        pass
                for line in engine.get_new_lines():
                    if map_widget.graphics_manager.query(elm=line) is None:
                        map_widget.diagram.set_point(device=line, location=MapLocation())
                        map_widget.add_api_line(api_object=line)
                    else:
                        pass
            else:
                pass

        # Map geographic coordinates to schematic canvas coordinates
        _SCALE: float = 1000.0
        for bus in expanded_grid.buses:
            bus.x = bus.longitude * _SCALE
            bus.y = -bus.latitude * _SCALE

        # Create the schematic diagram from the expanded grid
        expanded_grid_schematic = make_diagram_from_buses(circuit=expanded_grid,
                                                          buses=engine.get_buses(),
                                                          name=f'Diagram {method.value}')

        # Create the schematic widget and add it to the main GUI
        diagram_widget = SchematicWidget(
            gui=self.app,
            diagram=expanded_grid_schematic,
            default_bus_voltage=self.app.ui.defaultBusVoltageSpinBox.value(),
            time_index=self.app.get_diagram_slider_index()
        )

        self.app.add_diagram_widget_and_diagram(diagram_widget=diagram_widget,
                                                diagram=expanded_grid_schematic)
        self.app.set_diagrams_list_view()

        # Show logger if there are any entries
        if logger.has_logs():
            logs_dlg = LogsDialogue('Procedural grid expansion log', logger)
            logs_dlg.exec()
        else:
            pass

        # Ask whether to assign generated objects to an investment group
        new_devices: List[ALL_DEV_TYPES] = (engine.get_new_buses()
                                                 + engine.get_new_lines()
                                                 + engine.get_new_transformers())
        group_name: str = "Investment " + str(len(self.app.circuit.investments_groups))
        names: List[str] = [d.type_name + ": " + d.name for d in new_devices]
        inv_dlg: CheckListDialogue = CheckListDialogue(objects_list=names,
                                                       title="Add investment",
                                                       ask_for_group_name=True,
                                                       group_label="Investment name",
                                                       group_text=group_name)
        inv_dlg.setModal(True)
        inv_dlg.exec()

        if inv_dlg.is_accepted:
            group: dev.InvestmentsGroup = dev.InvestmentsGroup(
                idtag=None,
                name=inv_dlg.get_group_text(),
                category="single" if len(new_devices) == 1 else "multiple"
            )
            self.app.circuit.add_investments_group(group)

            for i in inv_dlg.selected_indices:
                d: ALL_DEV_TYPES = new_devices[i]
                self.app.circuit.add_investment(dev.Investment(device=d,
                                                               code=d.code,
                                                               name=d.type_name + ": " + d.name,
                                                               CAPEX=0.0,
                                                               group=group))

        # Exit
        self.close()
