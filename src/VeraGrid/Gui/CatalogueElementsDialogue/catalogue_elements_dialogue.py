# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict, List

from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem

from VeraGrid.Gui.CatalogueElementsDialogue.catalogue_elements_gui import Ui_CatalogueElementsDialog
from VeraGrid.Gui.CatalogueElementsDialogue.catalogue_actions import CatalogueAction, CatalogueActionKind
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGrid.templates import (get_transformer_catalogue, get_cables_catalogue,
                                get_wires_catalogue, get_sequence_lines_catalogue)
import VeraGridEngine.Templates as tem


class CatalogueElementsSelectionDialogue(QtWidgets.QDialog):
    """
    CatalogueElementsSelectionDialogue

    This dialog presents a tree of catalogue elements grouped by category.
    Each leaf item corresponds to a concrete template object that can be added to a circuit.
    """

    __slots__ = (
        'ui',
        '_model',
        '_circuit',
        '_catalogue_categories',
        '_signals_blocked',
        '_added_count',
    )

    _COL_NAME: int = 0
    _COL_VOLTAGE: int = 1
    _COL_POWER: int = 2

    _ROLE_OBJ: int = int(Qt.ItemDataRole.UserRole) + 1
    _ROLE_KIND: int = int(Qt.ItemDataRole.UserRole) + 2
    _ROLE_IS_CATEGORY: int = int(Qt.ItemDataRole.UserRole) + 3

    def __init__(self, parent: QtWidgets.QWidget | None, circuit: MultiCircuit):
        """
        Constructor.

        :param parent: Parent widget.
        :param circuit: Target circuit.
        """
        QtWidgets.QDialog.__init__(self, parent)

        self._circuit: MultiCircuit = circuit
        self._catalogue_categories: Dict[str, List[CatalogueAction]] = self.build_catalogue_categories()

        # Internal re-entrancy guard for itemChanged propagation.
        self._signals_blocked: bool = False
        self._added_count: int = 0

        # Build UI and model.
        self.ui = Ui_CatalogueElementsDialog()
        self.ui.setupUi(self)

        self._model = QStandardItemModel()
        self._model.setHorizontalHeaderLabels(['Element', 'Voltage', 'Power'])

        self.ui.treeView.setModel(self._model)
        self.ui.treeView.setHeaderHidden(False)
        self.ui.treeView.setItemsExpandable(True)
        self.ui.treeView.setRootIsDecorated(True)
        self.ui.treeView.setAlternatingRowColors(True)
        self.ui.treeView.setUniformRowHeights(True)

        # Wire up signals.
        self._model.itemChanged.connect(self.on_item_changed)
        self.ui.selectAllButton.clicked.connect(self.select_all)
        self.ui.selectNoneButton.clicked.connect(self.select_none)
        self.ui.buttonBox.accepted.connect(self.on_accept)
        self.ui.buttonBox.rejected.connect(self.reject)

        # Populate.
        self.populate_from_dict()
        # self.ui.treeView.expandAll()
        self.ui.treeView.resizeColumnToContents(self._COL_NAME)

    @property
    def added_count(self) -> int:
        """
        Get the number of actions executed when the dialog was accepted.

        :return: int
        """
        return self._added_count

    def get_selected_elements(self) -> Dict[str, List[CatalogueAction]]:
        """
        Get selected leaf objects grouped by their category.

        :return: Dictionary ``{category_name: [objects...]}``.
        """
        selected: Dict[str, List[CatalogueAction]] = dict()

        # Walk the model top-level categories and pick checked leaves.
        root = self._model.invisibleRootItem()
        for i in range(root.rowCount()):
            category_item = root.child(i, self._COL_NAME)

            if category_item is None:
                # Explicit else per project coding rules.
                pass
            else:
                category_name = str(category_item.text())
                selected_objects: List[CatalogueAction] = list()

                # Iterate children (leaf items).
                for j in range(category_item.rowCount()):
                    leaf_item = category_item.child(j, self._COL_NAME)

                    if leaf_item is None:
                        pass
                    elif leaf_item.checkState() == Qt.CheckState.Checked:
                        action = leaf_item.data(self._ROLE_OBJ)
                        if isinstance(action, CatalogueAction):
                            selected_objects.append(action)
                        else:
                            pass
                    else:
                        pass

                if len(selected_objects) > 0:
                    selected[category_name] = selected_objects
                else:
                    pass

        return selected

    # ------------------------------------------------------------------------------------------------------------------
    # UI actions
    # ------------------------------------------------------------------------------------------------------------------
    def select_all(self) -> None:
        """
        Mark all leaf items as selected.

        :return: None
        """
        self.set_all_check_state(Qt.CheckState.Checked)

    def select_none(self) -> None:
        """
        Mark all leaf items as unselected.

        :return: None
        """
        self.set_all_check_state(Qt.CheckState.Unchecked)

    def on_accept(self) -> None:
        """
        Execute the selected catalogue actions and close the dialog.

        :return: None
        """
        selected: Dict[str, List[CatalogueAction]] = self.get_selected_elements()
        existing_keys: Dict[str, bool] = self.get_existing_keys()
        added_count: int = 0

        for category_name, actions_list in selected.items():
            for action in actions_list:
                action_key: str = f"{category_name}|{action.unique_key}"
                if action_key in existing_keys:
                    pass
                else:
                    action.execute(circuit=self._circuit)
                    existing_keys[action_key] = True
                    added_count += 1

        self._added_count = added_count
        self.accept()

    # ------------------------------------------------------------------------------------------------------------------
    # Model building
    # ------------------------------------------------------------------------------------------------------------------
    def populate_from_dict(self) -> None:
        """
        Populate the tree from ``self._catalogue_categories``.

        :return: None
        """
        # Clear any previous content.
        self._model.removeRows(0, self._model.rowCount())

        # Add one root node per category.
        for category_name, objects_list in self._catalogue_categories.items():
            self.append_category(category_name=category_name, objects_list=objects_list)

    def build_catalogue_categories(self) -> Dict[str, List[CatalogueAction]]:
        """
        Build the tree payload using lightweight actions.

        :return: Dictionary mapping category names to action lists.
        """
        categories: Dict[str, List[CatalogueAction]] = dict()

        transformer_actions: List[CatalogueAction] = list()
        for obj in get_transformer_catalogue():
            transformer_actions.append(CatalogueAction(kind=CatalogueActionKind.AddTransformerType,
                                                       args=(obj,),
                                                       name=str(obj.name),
                                                       voltage_text=f"{float(obj.HV):.3g}/{float(obj.LV):.3g} kV",
                                                       power_text=f"{float(obj.Sn):.3g} MVA",
                                                       unique_key=f"{obj.name}|{obj.HV}|{obj.LV}|{obj.Sn}"))
        categories['Transformer types'] = transformer_actions

        cable_actions: List[CatalogueAction] = list()
        for obj in get_cables_catalogue():
            cable_actions.append(CatalogueAction(kind=CatalogueActionKind.AddUndergroundLineType,
                                                 args=(obj,),
                                                 name=str(obj.name),
                                                 voltage_text=f"{float(obj.Vnom):.3g} kV",
                                                 power_text=f"{self.compute_mva_from_v_i(v_kv=float(obj.Vnom), i_ka=float(obj.Imax)):.3g} MVA",
                                                 unique_key=f"{obj.name}|{obj.Vnom}|{obj.Imax}"))
        categories['Underground line types'] = cable_actions

        wire_actions: List[CatalogueAction] = list()
        for obj in get_wires_catalogue():
            wire_actions.append(CatalogueAction(kind=CatalogueActionKind.AddWire,
                                                args=(obj,),
                                                name=str(obj.name),
                                                voltage_text='',
                                                power_text='',
                                                unique_key=str(obj.name)))
        categories['Wire types'] = wire_actions

        sequence_actions: List[CatalogueAction] = list()
        for obj in get_sequence_lines_catalogue():
            sequence_actions.append(CatalogueAction(kind=CatalogueActionKind.AddSequenceLineType,
                                                    args=(obj,),
                                                    name=str(obj.name),
                                                    voltage_text=f"{float(obj.Vnom):.3g} kV",
                                                    power_text=f"{self.compute_mva_from_v_i(v_kv=float(obj.Vnom), i_ka=float(obj.Imax)):.3g} MVA",
                                                    unique_key=f"{obj.name}|{obj.Vnom}|{obj.Imax}"))
        categories['Sequence line types'] = sequence_actions

        categories['RMS model templates'] = self.build_rms_actions()
        categories['EMT model templates'] = self.build_emt_actions()

        return categories

    def build_rms_actions(self) -> List[CatalogueAction]:
        """
        Build the RMS template action list.

        :return: List[CatalogueAction]
        """
        actions: List[CatalogueAction] = list()

        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='complete_generator',
                voltage_text='',
                power_text='',
                unique_key='rms:get_complete_generator_template_rms',
                function_ptr=tem.get_complete_generator_template_rms
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='genqec',
                voltage_text='',
                power_text='',
                unique_key='rms:get_genqec_rms',
                function_ptr=tem.get_genqec_rms
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='governor',
                voltage_text='',
                power_text='',
                unique_key='rms:get_governor_rms',
                function_ptr=tem.get_governor_rms
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='stabilizer',
                voltage_text='',
                power_text='',
                unique_key='rms:get_stabilizer_rms',
                function_ptr=tem.get_stabilizer_rms
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='exciter',
                voltage_text='',
                power_text='',
                unique_key='rms:get_exciter_rms',
                function_ptr=tem.get_exciter_rms
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='genrow',
                voltage_text='',
                power_text='',
                unique_key='rms:get_genrow_rms_template',
                function_ptr=tem.get_genrow_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='line',
                voltage_text='',
                power_text='',
                unique_key='rms:get_line_rms_template',
                function_ptr=tem.get_line_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='dc_line',
                voltage_text='',
                power_text='',
                unique_key='rms:get_dc_line_rms_template',
                function_ptr=tem.get_dc_line_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='load',
                voltage_text='',
                power_text='',
                unique_key='rms:get_load_rms_template',
                function_ptr=tem.get_load_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='line_phasor',
                voltage_text='',
                power_text='',
                unique_key='rms:get_line_phasor_rms_template',
                function_ptr=tem.get_line_phasor_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='load_phasor_current',
                voltage_text='',
                power_text='',
                unique_key='rms:get_load_phasor_current_rms_template',
                function_ptr=tem.get_load_phasor_current_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='complete_generator_template_phasor',
                voltage_text='',
                power_text='',
                unique_key='rms:get_complete_generator_template_phasor',
                function_ptr=tem.get_complete_generator_template_phasor
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='transformer2w',
                voltage_text='',
                power_text='',
                unique_key='rms:get_transformer2w_rms',
                function_ptr=tem.get_transformer2w_rms
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='shunt',
                voltage_text='',
                power_text='',
                unique_key='rms:get_shunt_template',
                function_ptr=tem.get_shunt_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='genqec_phasor',
                voltage_text='',
                power_text='',
                unique_key='rms:get_genqec_phasor',
                function_ptr=tem.get_genqec_phasor
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pvd1',
                voltage_text='',
                power_text='',
                unique_key='rms:get_pvd1_rms_template',
                function_ptr=tem.get_pvd1_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pvd1_complete',
                voltage_text='',
                power_text='',
                unique_key='rms:get_pvd1_complete_rms_template',
                function_ptr=tem.get_pvd1_complete_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pvd1_dc_mppt',
                voltage_text='',
                power_text='',
                unique_key='rms:get_pvd1_dc_mppt_rms_template',
                function_ptr=tem.get_pvd1_dc_mppt_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pvd1_dc_link_mppt',
                voltage_text='',
                power_text='',
                unique_key='rms:get_pvd1_dc_link_mppt_rms_template',
                function_ptr=tem.get_pvd1_dc_link_mppt_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pvd1_dc_link_bess',
                voltage_text='',
                power_text='',
                unique_key='rms:get_pvd1_dc_link_bess_rms_template',
                function_ptr=tem.get_pvd1_dc_link_bess_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='esd1',
                voltage_text='',
                power_text='',
                unique_key='rms:get_esd1_rms_template',
                function_ptr=tem.get_esd1_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='voltage_source',
                voltage_text='',
                power_text='',
                unique_key='rms:VoltageSourceBuild',
                function_ptr=tem.VoltageSourceBuild
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='vsc',
                voltage_text='',
                power_text='',
                unique_key='rms:build_vsc_rms',
                function_ptr=tem.build_vsc_rms
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pll_transform',
                voltage_text='',
                power_text='',
                unique_key='rms:get_pll_transform_rms',
                function_ptr=tem.get_pll_transform_rms
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pi_current_controller',
                voltage_text='',
                power_text='',
                unique_key='rms:get_pi_current_controller',
                function_ptr=tem.get_pi_current_controller
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pi_power_controller',
                voltage_text='',
                power_text='',
                unique_key='rms:get_pi_power_controller',
                function_ptr=tem.get_pi_power_controller
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='gfl_converter',
                voltage_text='',
                power_text='',
                unique_key='rms:get_gfl_converter_rms',
                function_ptr=tem.get_gfl_converter_rms
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='empty',
                voltage_text='',
                power_text='',
                unique_key='rms:get_empty_rms_template',
                function_ptr=tem.get_empty_rms_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ac1a',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ac1a_template',
                function_ptr=tem.build_ac1a_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ac1c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ac1c_template',
                function_ptr=tem.build_ac1c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ac6a',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ac6a_template',
                function_ptr=tem.build_ac6a_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ac6c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ac6c_template',
                function_ptr=tem.build_ac6c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ac7b',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ac7b_template',
                function_ptr=tem.build_ac7b_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ac7c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ac7c_template',
                function_ptr=tem.build_ac7c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ac8b',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ac8b_template',
                function_ptr=tem.build_ac8b_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ac8c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ac8c_template',
                function_ptr=tem.build_ac8c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='bbsex1',
                voltage_text='',
                power_text='',
                unique_key='rms:build_bbsex1_template',
                function_ptr=tem.build_bbsex1_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='besscbcurrentsourcenoplantcontrol',
                voltage_text='',
                power_text='',
                unique_key='rms:build_besscbcurrentsourcenoplantcontrol_template',
                function_ptr=tem.build_besscbcurrentsourcenoplantcontrol_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='dc1a',
                voltage_text='',
                power_text='',
                unique_key='rms:build_dc1a_template',
                function_ptr=tem.build_dc1a_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='dc1c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_dc1c_template',
                function_ptr=tem.build_dc1c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='exac1',
                voltage_text='',
                power_text='',
                unique_key='rms:build_exac1_template',
                function_ptr=tem.build_exac1_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='govhydro4',
                voltage_text='',
                power_text='',
                unique_key='rms:build_govhydro4_template',
                function_ptr=tem.build_govhydro4_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='govsteam1',
                voltage_text='',
                power_text='',
                unique_key='rms:build_govsteam1_template',
                function_ptr=tem.build_govsteam1_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='govsteameu',
                voltage_text='',
                power_text='',
                unique_key='rms:build_govsteameu_template',
                function_ptr=tem.build_govsteameu_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ieeeg1',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ieeeg1_template',
                function_ptr=tem.build_ieeeg1_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ieeeg2',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ieeeg2_template',
                function_ptr=tem.build_ieeeg2_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ieeet1',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ieeet1_template',
                function_ptr=tem.build_ieeet1_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ieeex2',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ieeex2_template',
                function_ptr=tem.build_ieeex2_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ieex2a',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ieex2a_template',
                function_ptr=tem.build_ieex2a_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='maxex2',
                voltage_text='',
                power_text='',
                unique_key='rms:build_maxex2_template',
                function_ptr=tem.build_maxex2_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='oel2c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_oel2c_template',
                function_ptr=tem.build_oel2c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='oel3c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_oel3c_template',
                function_ptr=tem.build_oel3c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='oel4c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_oel4c_template',
                function_ptr=tem.build_oel4c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='oel5c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_oel5c_template',
                function_ptr=tem.build_oel5c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pss1aomega',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pss1aomega_template',
                function_ptr=tem.build_pss1aomega_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pss1apgen',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pss1apgen_template',
                function_ptr=tem.build_pss1apgen_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pss2a',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pss2a_template',
                function_ptr=tem.build_pss2a_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pss2b',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pss2b_template',
                function_ptr=tem.build_pss2b_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pss2c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pss2c_template',
                function_ptr=tem.build_pss2c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pss3b',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pss3b_template',
                function_ptr=tem.build_pss3b_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pss3c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pss3c_template',
                function_ptr=tem.build_pss3c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pss6c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pss6c_template',
                function_ptr=tem.build_pss6c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='psskundur',
                voltage_text='',
                power_text='',
                unique_key='rms:build_psskundur_template',
                function_ptr=tem.build_psskundur_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pvcurrentsourcebnoplantcontrol',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pvcurrentsourcebnoplantcontrol_template',
                function_ptr=tem.build_pvcurrentsourcebnoplantcontrol_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pvvoltagesourceanoplantcontrol',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pvvoltagesourceanoplantcontrol_template',
                function_ptr=tem.build_pvvoltagesourceanoplantcontrol_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='pvvoltagesourcebnoplantcontrol',
                voltage_text='',
                power_text='',
                unique_key='rms:build_pvvoltagesourcebnoplantcontrol_template',
                function_ptr=tem.build_pvvoltagesourcebnoplantcontrol_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='reecb',
                voltage_text='',
                power_text='',
                unique_key='rms:build_reecb_template',
                function_ptr=tem.build_reecb_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='reecc',
                voltage_text='',
                power_text='',
                unique_key='rms:build_reecc_template',
                function_ptr=tem.build_reecc_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='regcbcs',
                voltage_text='',
                power_text='',
                unique_key='rms:build_regcbcs_template',
                function_ptr=tem.build_regcbcs_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='repca',
                voltage_text='',
                power_text='',
                unique_key='rms:build_repca_template',
                function_ptr=tem.build_repca_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='scl1c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_scl1c_template',
                function_ptr=tem.build_scl1c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='scl2c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_scl2c_template',
                function_ptr=tem.build_scl2c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='scrx',
                voltage_text='',
                power_text='',
                unique_key='rms:build_scrx_template',
                function_ptr=tem.build_scrx_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='sexs',
                voltage_text='',
                power_text='',
                unique_key='rms:build_sexs_template',
                function_ptr=tem.build_sexs_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st1a',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st1a_template',
                function_ptr=tem.build_st1a_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st1c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st1c_template',
                function_ptr=tem.build_st1c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st4b',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st4b_template',
                function_ptr=tem.build_st4b_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st4c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st4c_template',
                function_ptr=tem.build_st4c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st5b',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st5b_template',
                function_ptr=tem.build_st5b_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st5c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st5c_template',
                function_ptr=tem.build_st5c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st6b',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st6b_template',
                function_ptr=tem.build_st6b_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st6c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st6c_template',
                function_ptr=tem.build_st6c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st7b',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st7b_template',
                function_ptr=tem.build_st7b_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st7c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st7c_template',
                function_ptr=tem.build_st7c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='st9c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_st9c_template',
                function_ptr=tem.build_st9c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='tgov3',
                voltage_text='',
                power_text='',
                unique_key='rms:build_tgov3_template',
                function_ptr=tem.build_tgov3_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='uel1',
                voltage_text='',
                power_text='',
                unique_key='rms:build_uel1_template',
                function_ptr=tem.build_uel1_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='uel2c',
                voltage_text='',
                power_text='',
                unique_key='rms:build_uel2c_template',
                function_ptr=tem.build_uel2c_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='vrkundur',
                voltage_text='',
                power_text='',
                unique_key='rms:build_vrkundur_template',
                function_ptr=tem.build_vrkundur_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='wpp4bcurrentsource2020',
                voltage_text='',
                power_text='',
                unique_key='rms:build_wpp4bcurrentsource2020_template',
                function_ptr=tem.build_wpp4bcurrentsource2020_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='wt4acurrentsource',
                voltage_text='',
                power_text='',
                unique_key='rms:build_wt4acurrentsource_template',
                function_ptr=tem.build_wt4acurrentsource_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='wt4acurrentsource2020',
                voltage_text='',
                power_text='',
                unique_key='rms:build_wt4acurrentsource2020_template',
                function_ptr=tem.build_wt4acurrentsource2020_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='wt4bcurrentsource2020',
                voltage_text='',
                power_text='',
                unique_key='rms:build_wt4bcurrentsource2020_template',
                function_ptr=tem.build_wt4bcurrentsource2020_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='wt4bcurrentsource',
                voltage_text='',
                power_text='',
                unique_key='rms:build_wt4bcurrentsource_template',
                function_ptr=tem.build_wt4bcurrentsource_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='wt4injector',
                voltage_text='',
                power_text='',
                unique_key='rms:build_wt4injector_template',
                function_ptr=tem.build_wt4injector_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='wtg4acurrentsource',
                voltage_text='',
                power_text='',
                unique_key='rms:build_wtg4acurrentsource_template',
                function_ptr=tem.build_wtg4acurrentsource_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='wtg4bcurrentsource',
                voltage_text='',
                power_text='',
                unique_key='rms:build_wtg4bcurrentsource_template',
                function_ptr=tem.build_wtg4bcurrentsource_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ieeevc_1981',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ieeevc_1981_template',
                function_ptr=tem.build_ieeevc_1981_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='esdc2a',
                voltage_text='',
                power_text='',
                unique_key='rms:build_esdc2a_template',
                function_ptr=tem.build_esdc2a_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='frqtpa',
                voltage_text='',
                power_text='',
                unique_key='rms:build_frqtpa_template',
                function_ptr=tem.build_frqtpa_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='vtgtpa',
                voltage_text='',
                power_text='',
                unique_key='rms:build_vtgtpa_template',
                function_ptr=tem.build_vtgtpa_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='cimtr1',
                voltage_text='',
                power_text='',
                unique_key='rms:build_cimtr1_template',
                function_ptr=tem.build_cimtr1_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='cimw',
                voltage_text='',
                power_text='',
                unique_key='rms:build_cimw_template',
                function_ptr=tem.build_cimw_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='gensal',
                voltage_text='',
                power_text='',
                unique_key='rms:build_gensal_template',
                function_ptr=tem.build_gensal_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='genrou',
                voltage_text='',
                power_text='',
                unique_key='rms:build_genrou_template',
                function_ptr=tem.build_genrou_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ggov1',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ggov1_template',
                function_ptr=tem.build_ggov1_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='hygov',
                voltage_text='',
                power_text='',
                unique_key='rms:build_hygov_template',
                function_ptr=tem.build_hygov_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='ieel',
                voltage_text='',
                power_text='',
                unique_key='rms:build_ieel_template',
                function_ptr=tem.build_ieel_template
            )
        )
        actions.append(
            CatalogueAction(
                kind=CatalogueActionKind.AddRmsTemplate,
                args=(self._circuit.var_factory,),
                name='tgov1',
                voltage_text='',
                power_text='',
                unique_key='rms:build_tgov1_template',
                function_ptr=tem.build_tgov1_template
            )
        )
        return actions
    def build_emt_actions(self) -> List[CatalogueAction]:
        """
        Build the EMT template action list.

        :return: List[CatalogueAction]
        """
        actions: List[CatalogueAction] = list()
        # actions.append(CatalogueAction(
        #     kind=CatalogueActionKind.AddEmtTemplate,
        #     args=(self._circuit.var_factory,),
        #     name='Simple generator',
        #     voltage_text='', power_text='',
        #     unique_key='emt:get_simple_generator_emt_template',
        #     function_ptr=tem.get_simple_generator_emt_template)
        # )
        # actions.append(CatalogueAction(
        #     kind=CatalogueActionKind.AddEmtTemplate,
        #     args=(self._circuit.var_factory,),
        #     name='Sauer Pai generator',
        #     voltage_text='', power_text='',
        #     unique_key='emt:get_generator_sauer_pai_type_emt_template',
        #     function_ptr=tem.get_generator_sauer_pai_type_emt_template)
        # )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='Complete generator',
            voltage_text='', power_text='',
            unique_key='emt:get_complete_generator_template_emt',
            function_ptr=tem.get_complete_generator_template_emt)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='Thevenin generator',
            voltage_text='', power_text='',
            unique_key='emt:get_generator_thevenin_rl_emt_template_with_ref',
            function_ptr=tem.get_generator_thevenin_rl_emt_template_with_ref)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='Ideal converter',
            voltage_text='', power_text='',
            unique_key='emt:get_emt_ideal_converter',
            function_ptr=tem.get_emt_ideal_converter)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='Full pseudo converter',
            voltage_text='', power_text='',
            unique_key='emt:get_full_pseudo_emt_converter',
            function_ptr=tem.get_full_pseudo_emt_converter)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='Switched converter',
            voltage_text='', power_text='',
            unique_key='emt:get_switched_emt_converter',
            function_ptr=tem.get_switched_emt_converter)
        )
        # actions.append(CatalogueAction(
        #     kind=CatalogueActionKind.AddEmtTemplate,
        #     args=(self._circuit.var_factory,),
        #     name='Bridge 2-level 3ph',
        #     voltage_text='', power_text='',
        #     unique_key='emt:get_bridge_2level_3ph_emt_template',
        #     function_ptr=tem.get_bridge_2level_3ph_emt_template)
        # )
        # actions.append(CatalogueAction(
        #     kind=CatalogueActionKind.AddEmtTemplate,
        #     args=(self._circuit.var_factory,),
        #     name='Bridge filter 2-level 3ph',
        #     voltage_text='', power_text='',
        #     unique_key='emt:get_bridge_filter_2level_3ph_emt_template',
        #     function_ptr=tem.get_bridge_filter_2level_3ph_emt_template)
        # )
        # actions.append(CatalogueAction(
        #     kind=CatalogueActionKind.AddEmtTemplate,
        #     args=(self._circuit.var_factory,),
        #     name='Bridge filter control 2-level 3ph',
        #     voltage_text='', power_text='',
        #     unique_key='emt:get_bridge_filter_control_2level_3ph_emt_template',
        #     function_ptr=tem.get_bridge_filter_control_2level_3ph_emt_template)
        # )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='DC load',
            voltage_text='', power_text='',
            unique_key='emt:get_dc_load_emt_template',
            function_ptr=tem.get_dc_load_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='DC line',
            voltage_text='', power_text='',
            unique_key='emt:get_dc_line_emt_template',
            function_ptr=tem.get_dc_line_with_power_input_emt_template)
        )
        # actions.append(CatalogueAction(
        #     kind=CatalogueActionKind.AddEmtTemplate,
        #     args=(self._circuit.var_factory,),
        #     name='DC line',
        #     voltage_text='', power_text='',
        #     unique_key='emt:get_dc_line_emt_template',
        #     function_ptr=tem.get_dc_line_emt_template)
        # )

        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='Transformer',
            voltage_text='', power_text='',
            unique_key='emt:get_transformer_emt_template',
            function_ptr=tem.get_transformer_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='XFMR',
            voltage_text='', power_text='',
            unique_key='emt:get_xfmr_emt_template',
            function_ptr=tem.get_xfmr_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory, True, True, True),
            name='Shunt C (ABC)',
            voltage_text='', power_text='',
            unique_key='emt:get_shunt_c_emt_template:abc',
            function_ptr=tem.get_shunt_c_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory, True, True, True),
            name='Shunt L (ABC)',
            voltage_text='', power_text='',
            unique_key='emt:get_shunt_l_emt_template:abc',
            function_ptr=tem.get_shunt_l_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory, True, True, True),
            name='Shunt R (ABC)',
            voltage_text='', power_text='',
            unique_key='emt:get_shunt_r_emt_template:abc',
            function_ptr=tem.get_shunt_r_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory, True, True, True),
            name='Exponential load (ABC)',
            voltage_text='', power_text='',
            unique_key='emt:get_exponential_load_emt:abc',
            function_ptr=tem.get_exponential_load_emt)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory, True, True, True),
            name='ZIP load (ABC)',
            voltage_text='', power_text='',
            unique_key='emt:get_load_ZIP_emt_template:abc',
            function_ptr=tem.get_load_ZIP_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory, False, True, True, True),
            name='PI line (ABC)',
            voltage_text='', power_text='',
            unique_key='emt:get_pi_line_emt_template:abc',
            function_ptr=tem.get_pi_line_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory, False, True, True, True),
            name='Bergeron line (ABC)',
            voltage_text='', power_text='',
            unique_key='emt:get_bergeron_line_emt_template:abc',
            function_ptr=tem.get_bergeron_line_emt_template)
        )

        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='Single cage induction motor',
            voltage_text='', power_text='',
            unique_key='emt:get_induction_motor_single_cage_emt_template:abc',
            function_ptr=tem.get_induction_motor_single_cage_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='Double cage induction motor',
            voltage_text='', power_text='',
            unique_key='emt:get_induction_motor_double_cage_emt_template:abc',
            function_ptr=tem.get_induction_motor_double_cage_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='BESS',
            voltage_text='', power_text='',
            unique_key='emt:get_bess_avm_grid_following_emt_template:abc',
            function_ptr=tem.get_bess_avm_grid_following_emt_template)
        )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='PV plant grid following',
            voltage_text='', power_text='',
            unique_key='emt:get_pv_avm_grid_following_emt_template:abc',
            function_ptr=tem.get_pv_avm_grid_following_emt_template)
        )
        # actions.append(CatalogueAction(
        #     kind=CatalogueActionKind.AddEmtTemplate,
        #     args=(self._circuit.var_factory,),
        #     name='PV plant boost grid following',
        #     voltage_text='', power_text='',
        #     unique_key='emt:get_pv_avm_boost_grid_following_emt_template:abc',
        #     function_ptr=tem.get_pv_avm_boost_grid_following_emt_template)
        # )
        actions.append(CatalogueAction(
            kind=CatalogueActionKind.AddEmtTemplate,
            args=(self._circuit.var_factory,),
            name='VSC Grid-Forming (GFM)',
            voltage_text='', power_text='',
            unique_key='emt:get_gfm_emt_template',
            function_ptr=tem.get_gfm_emt_template)
        )
        # actions.append(CatalogueAction(kind=CatalogueActionKind.AddEmtTemplate,
        #                                args=(self._circuit.var_factory,),
        #                                name='Empty template',
        #                                voltage_text='',
        #                                power_text='',
        #                                unique_key='emt:get_empty_emt_template',
        #                                function_ptr=tem.get_empty_emt_template)
        #                )
        return actions

    def get_existing_keys(self) -> Dict[str, bool]:
        """
        Build the current circuit key set used to avoid duplicate imports.

        :return: Dictionary used as a set.
        """
        existing_keys: Dict[str, bool] = dict()

        for tpe in self._circuit.transformer_types:
            existing_keys[f"Transformer types|{tpe.name}|{tpe.HV}|{tpe.LV}|{tpe.Sn}"] = True
        for tpe in self._circuit.underground_cable_types:
            existing_keys[f"Underground line types|{tpe.name}|{tpe.Vnom}|{tpe.Imax}"] = True
        for tpe in self._circuit.wire_types:
            existing_keys[f"Wire types|{tpe.name}"] = True
        for tpe in self._circuit.sequence_line_types:
            existing_keys[f"Sequence line types|{tpe.name}|{tpe.Vnom}|{tpe.Imax}"] = True
        for tpe in self._circuit.rms_models:
            existing_keys[f"RMS model templates|{tpe.name}"] = True
        for tpe in self._circuit.emt_models:
            existing_keys[f"EMT model templates|{tpe.name}"] = True

        return existing_keys

    def compute_mva_from_v_i(self, v_kv: float, i_ka: float) -> float:
        """
        Compute the 3-phase apparent power rating from nominal voltage and current.

        :param v_kv: Voltage in kV.
        :param i_ka: Current in kA.
        :return: MVA value.
        """
        return float(v_kv) * float(i_ka) * 1.73205080757

    def append_category(self, category_name: str, objects_list: List[CatalogueAction]) -> None:
        """
        Append a category row and its children.

        :param category_name: Category caption.
        :param objects_list: List of template objects in that category.
        :return: None
        """
        # Category row: checkable + tri-state.
        cat_name_item = QStandardItem(str(category_name))
        cat_voltage_item = QStandardItem('')
        cat_power_item = QStandardItem('')

        cat_name_item.setEditable(False)
        cat_voltage_item.setEditable(False)
        cat_power_item.setEditable(False)

        cat_name_item.setCheckable(True)
        # In PySide6, QStandardItem exposes tri-state via auto/user tristate flags.
        cat_name_item.setAutoTristate(True)
        cat_name_item.setUserTristate(True)
        cat_name_item.setCheckState(Qt.CheckState.Unchecked)
        cat_name_item.setData(True, self._ROLE_IS_CATEGORY)

        self._model.appendRow([cat_name_item, cat_voltage_item, cat_power_item])

        # Child rows.
        for obj in objects_list:
            row_items = self.create_leaf_row(action=obj)
            cat_name_item.appendRow(row_items)

    def create_leaf_row(self, action: CatalogueAction) -> List[QStandardItem]:
        """
        Create the 3-column row representing a concrete template object.

        :param action: CatalogueAction.
        :return: List of 3 ``QStandardItem``.
        """
        name_item = QStandardItem(action.name)
        voltage_item = QStandardItem(action.voltage_text)
        power_item = QStandardItem(action.power_text)

        # Make leaf selectable and checkable.
        name_item.setEditable(False)
        voltage_item.setEditable(False)
        power_item.setEditable(False)

        name_item.setCheckable(True)
        name_item.setCheckState(Qt.CheckState.Unchecked)

        # Store the raw object and its kind for later consumption.
        name_item.setData(action, self._ROLE_OBJ)
        name_item.setData(int(action.kind.value), self._ROLE_KIND)
        name_item.setData(False, self._ROLE_IS_CATEGORY)

        # Keep numeric columns aligned.
        voltage_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        power_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return [name_item, voltage_item, power_item]

    # ------------------------------------------------------------------------------------------------------------------
    # Checkbox propagation
    # ------------------------------------------------------------------------------------------------------------------
    def on_item_changed(self, item: QStandardItem) -> None:
        """
        Handle checkbox state propagation:

        1. If a category item is toggled, apply its state to its children.
        2. If a leaf item is toggled, update its parent category tri-state.

        :param item: Changed item.
        :return: None
        """
        # Re-entrancy protection: we update other items programmatically in this handler.
        if self._signals_blocked:
            return
        else:
            pass

        # Only react to changes in the first column, where checkboxes live.
        if item.index().column() != self._COL_NAME:
            return
        else:
            pass

        self._signals_blocked = True
        try:
            is_category = bool(item.data(self._ROLE_IS_CATEGORY))

            if is_category:
                self.propagate_category_state(category_item=item)
            else:
                self.update_parent_state_from_children(leaf_item=item)
        finally:
            self._signals_blocked = False

    def propagate_category_state(self, category_item: QStandardItem) -> None:
        """
        Apply a category checkbox state to all its children.

        :param category_item: Category item.
        :return: None
        """
        desired = category_item.checkState()

        # Only propagate explicit checked/unchecked; ignore PartiallyChecked direct user assignments.
        if desired == Qt.CheckState.PartiallyChecked:
            return
        else:
            pass

        for i in range(category_item.rowCount()):
            child = category_item.child(i, self._COL_NAME)
            if child is None:
                pass
            else:
                child.setCheckState(desired)

    def update_parent_state_from_children(self, leaf_item: QStandardItem) -> None:
        """
        Update parent category tri-state from the states of all children.

        :param leaf_item: Leaf item that changed.
        :return: None
        """
        parent_item = leaf_item.parent()

        if parent_item is None:
            # Leaf without parent should not happen in our tree.
            return
        else:
            pass

        checked_count = 0
        unchecked_count = 0

        for i in range(parent_item.rowCount()):
            child = parent_item.child(i, self._COL_NAME)
            if child is None:
                pass
            elif child.checkState() == Qt.CheckState.Checked:
                checked_count += 1
            elif child.checkState() == Qt.CheckState.Unchecked:
                unchecked_count += 1
            else:
                # PartiallyChecked should not happen on leaves, but handle explicitly.
                pass

        # Decide parent state.
        if checked_count == parent_item.rowCount():
            parent_item.setCheckState(Qt.CheckState.Checked)
        elif unchecked_count == parent_item.rowCount():
            parent_item.setCheckState(Qt.CheckState.Unchecked)
        else:
            parent_item.setCheckState(Qt.CheckState.PartiallyChecked)

    def set_all_check_state(self, state: Qt.CheckState) -> None:
        """
        Set all leaf checkboxes to a given state.

        :param state: Desired state (Checked/Unchecked).
        :return: None
        """
        self._signals_blocked = True
        try:
            root = self._model.invisibleRootItem()
            for i in range(root.rowCount()):
                category_item = root.child(i, self._COL_NAME)
                if category_item is None:
                    pass
                else:
                    for j in range(category_item.rowCount()):
                        child = category_item.child(j, self._COL_NAME)
                        if child is None:
                            pass
                        else:
                            child.setCheckState(state)

                    category_item.setCheckState(state)
        finally:
            self._signals_blocked = False
