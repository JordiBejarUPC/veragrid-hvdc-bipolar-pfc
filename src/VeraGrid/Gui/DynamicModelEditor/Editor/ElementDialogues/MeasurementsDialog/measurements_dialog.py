# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.001--.0-
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.general_dialogues import DeviceSelectorDialogue
from VeraGrid.Gui.DynamicModelEditor.Editor.ElementDialogues.MeasurementsDialog.measurements_dialog_ui import (
    Ui_MeasurementsDialog,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.ElementDialogues.MeasurementsDialog.measurement_widgets import (
    MeasurementReferenceList,
)
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.enumerations import BlockType, DeviceType, VarPowerFlowReferenceType


class MeasurementsDialog(QtWidgets.QDialog):
    """Select one bus and configure the interface of one RMS measurement block."""

    __slots__ = (
        "ui",
        "_buses",
        "_measurement_vars_dict",
        "_active_measurement_vars_dict",
        "_selected_bus",
        "_selected_block_type",
        "_input_references",
        "_output_references",
        "_updating_tree",
    )

    def __init__(self,
                 buses: List[Bus],
                 measurement_vars_dict: Dict[str, Dict[BlockType, List[VarPowerFlowReferenceType]]],
                 initial_bus: Bus | None = None,
                 initial_block_type: BlockType | None = None,
                 initial_input_references: Sequence[VarPowerFlowReferenceType] | None = None,
                 initial_output_references: Sequence[VarPowerFlowReferenceType] | None = None,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """Build the measurement configuration dialog.

        :param buses: Buses available to the measurement block.
        :param measurement_vars_dict: Measurement types and references grouped by bus domain.
        :param initial_bus: Bus to preselect when editing an existing block.
        :param initial_block_type: Measurement type to preselect when editing.
        :param initial_input_references: Measurement references already routed as inputs.
        :param initial_output_references: Measurement references already routed as outputs.
        :param parent: Optional owning widget.
        :return: None.
        """
        super().__init__(parent)
        self.ui: Ui_MeasurementsDialog = Ui_MeasurementsDialog()

        self._buses: List[Bus] = list(buses)
        self._measurement_vars_dict: Dict[
            str,
            Dict[BlockType, List[VarPowerFlowReferenceType]],
        ] = dict()
        bus_domain: str
        domain_measurements: Dict[BlockType, List[VarPowerFlowReferenceType]]
        block_type: BlockType
        references: List[VarPowerFlowReferenceType]
        for bus_domain, domain_measurements in measurement_vars_dict.items():
            copied_domain_measurements: Dict[BlockType, List[VarPowerFlowReferenceType]] = dict()
            for block_type, references in domain_measurements.items():
                copied_domain_measurements[block_type] = list(references)
            self._measurement_vars_dict[bus_domain] = copied_domain_measurements
        self._active_measurement_vars_dict: Dict[
            BlockType,
            List[VarPowerFlowReferenceType],
        ] = dict()

        self._selected_bus: Bus | None = None
        self._selected_block_type: BlockType | None = None
        self._input_references: List[VarPowerFlowReferenceType] = list()
        self._output_references: List[VarPowerFlowReferenceType] = list()
        self._updating_tree: bool = False

        self._build_ui()
        self._connect_signals()
        self._refresh_direction_lists()
        self._set_measurement_configuration_enabled(False)
        if initial_bus is not None:
            self.set_selected_bus(initial_bus)
            if initial_block_type is not None:
                self.set_selected_measurement(
                    selected_block_type=initial_block_type,
                    input_references=initial_input_references,
                    output_references=initial_output_references,
                )
            else:
                pass
        else:
            pass

    def _build_ui(self) -> None:
        """Build the bus selector, measurement tree, direction lists, and buttons.

        :return: None.
        """
        self.ui.setupUi(self)
        self.ui.input_list.set_target_direction(0)
        self.ui.output_list.set_target_direction(1)

    def _set_measurement_configuration_enabled(self, enabled: bool) -> None:
        """Enable or shade all controls that depend on the selected bus.

        :param enabled: Whether a concrete bus has been selected.
        :return: None.
        """
        self.ui.measurement_tree.setEnabled(enabled)
        self.ui.input_list.setEnabled(enabled)
        self.ui.output_list.setEnabled(enabled)

    def _populate_measurement_tree(self) -> None:
        """Populate collapsed measurement keys and their checkable references.

        :return: None.
        """
        block_type: BlockType
        references: List[VarPowerFlowReferenceType]
        for block_type, references in self._active_measurement_vars_dict.items():
            parent_item: QtWidgets.QTreeWidgetItem = QtWidgets.QTreeWidgetItem(
                self.ui.measurement_tree,
                list((block_type.name,)),
            )
            parent_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, block_type)
            parent_item.setFlags(
                parent_item.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsSelectable
            )
            parent_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)

            reference: VarPowerFlowReferenceType
            for reference in references:
                child_item: QtWidgets.QTreeWidgetItem = QtWidgets.QTreeWidgetItem(
                    parent_item,
                    list((reference.name,)),
                )
                child_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, reference)
                child_item.setFlags(
                    child_item.flags()
                    | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                    | QtCore.Qt.ItemFlag.ItemIsSelectable
                )
                child_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
            parent_item.setExpanded(False)

    def _connect_signals(self) -> None:
        """Connect tree and drag-and-drop changes to the detached selection state.

        :return: None.
        """
        self.ui.measurement_tree.itemChanged.connect(self.tree_item_changed)
        self.ui.measurement_tree.itemClicked.connect(self.tree_item_clicked)
        self.ui.input_list.moveRequested.connect(self.move_reference)
        self.ui.output_list.moveRequested.connect(self.move_reference)
        self.ui.bus_label.clicked.connect(self.select_bus)
        self.ui.button_box.accepted.connect(self.accept_dialog)
        self.ui.button_box.rejected.connect(self.reject)

    @QtCore.Slot()
    def select_bus(self) -> None:
        """Open the searchable bus selector and apply an accepted selection.

        :return: None.
        """
        devices_by_type: Dict[DeviceType, List[ALL_DEV_TYPES]] = dict()
        bus_devices: List[ALL_DEV_TYPES] = list(self._buses)
        devices_by_type[DeviceType.BusDevice] = bus_devices
        selector: DeviceSelectorDialogue = DeviceSelectorDialogue(
            devices_by_type=devices_by_type,
            allow_none=False,
            parent=self,
        )
        if selector.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            selected_device: object = selector.get_selected_device()
            if isinstance(selected_device, Bus):
                self.set_selected_bus(selected_device)
            else:
                pass
        else:
            pass

    def set_selected_bus(self, selected_bus: Bus) -> None:
        """Select one bus and rebuild its compatible measurement configuration.

        :param selected_bus: Concrete AC or DC bus selected by the user.
        :return: None.
        """
        self._selected_bus = selected_bus
        self.ui.bus_label.setText(selected_bus.name)

        # Changing the physical bus invalidates every selection made for the
        # previous domain, even when both buses happen to share that domain.
        self._updating_tree = True
        self.ui.measurement_tree.clear()
        self._selected_block_type = None
        self._input_references = list()
        self._output_references = list()
        self._active_measurement_vars_dict = dict()

        bus_domain: str
        if selected_bus.is_dc:
            bus_domain = "dc_bus"
        else:
            bus_domain = "a_c_bus"
        domain_measurements: Dict[BlockType, List[VarPowerFlowReferenceType]] | None = (
            self._measurement_vars_dict.get(bus_domain, None)
        )
        if domain_measurements is not None:
            block_type: BlockType
            references: List[VarPowerFlowReferenceType]
            for block_type, references in domain_measurements.items():
                self._active_measurement_vars_dict[block_type] = list(references)
            self._populate_measurement_tree()
        else:
            pass
        self._set_measurement_configuration_enabled(True)

        self._updating_tree = False
        self._refresh_direction_lists()

    def set_selected_measurement(
            self,
            selected_block_type: BlockType,
            input_references: Sequence[VarPowerFlowReferenceType] | None,
            output_references: Sequence[VarPowerFlowReferenceType] | None,
    ) -> None:
        """Select one measurement type and restore its input/output directions.

        :param selected_block_type: Measurement type to select.
        :param input_references: References that must appear in the Inputs list.
        :param output_references: References that must appear in the Outputs list.
        :return: None.
        """
        available_references: List[VarPowerFlowReferenceType] | None = (
            self._active_measurement_vars_dict.get(selected_block_type, None)
        )
        if available_references is None:
            pass
        else:
            self._selected_block_type = selected_block_type
            self._input_references = list()
            self._output_references = list()

            if input_references is not None:
                reference: VarPowerFlowReferenceType
                for reference in input_references:
                    if reference in available_references and reference not in self._input_references:
                        self._input_references.append(reference)
                    else:
                        pass
            else:
                pass

            reference: VarPowerFlowReferenceType
            if output_references is not None:
                for reference in output_references:
                    if (reference in available_references
                            and reference not in self._input_references
                            and reference not in self._output_references):
                        self._output_references.append(reference)
                    else:
                        pass
            else:
                pass

            if len(self._input_references) == 0 and len(self._output_references) == 0:
                self._output_references = list(available_references)
            else:
                pass

            self._updating_tree = True
            selected_item: QtWidgets.QTreeWidgetItem | None = None
            top_index: int
            for top_index in range(self.ui.measurement_tree.topLevelItemCount()):
                parent_item: QtWidgets.QTreeWidgetItem = self.ui.measurement_tree.topLevelItem(top_index)
                block_type_data: object = parent_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if block_type_data is selected_block_type:
                    parent_item.setCheckState(0, QtCore.Qt.CheckState.Checked)
                    parent_item.setExpanded(True)
                    selected_item = parent_item
                    child_index: int
                    for child_index in range(parent_item.childCount()):
                        child_item: QtWidgets.QTreeWidgetItem = parent_item.child(child_index)
                        reference_data: object = child_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                        if (reference_data in self._input_references
                                or reference_data in self._output_references):
                            child_item.setCheckState(0, QtCore.Qt.CheckState.Checked)
                        else:
                            child_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                else:
                    parent_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                    child_index = 0
                    for child_index in range(parent_item.childCount()):
                        parent_item.child(child_index).setCheckState(
                            0,
                            QtCore.Qt.CheckState.Unchecked,
                        )
            self._updating_tree = False

            if selected_item is not None:
                self.ui.measurement_tree.setCurrentItem(selected_item)
            else:
                pass
            self._refresh_direction_lists()

    @QtCore.Slot(QtWidgets.QTreeWidgetItem, int)
    def tree_item_changed(self,
                          item: QtWidgets.QTreeWidgetItem,
                          column: int) -> None:
        """Apply exclusive key selection and individual reference selection.

        :param item: Tree item whose check state changed.
        :param column: Changed tree column.
        :return: None.
        """
        if self._updating_tree or column != 0:
            pass
        elif item.parent() is None:
            self._apply_key_check_change(item)
        else:
            self._apply_reference_check_change(item)

    def _apply_key_check_change(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Select at most one key and select all of its references by default.

        :param item: Changed top-level key item.
        :return: None.
        """
        block_type_data: object = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not isinstance(block_type_data, BlockType):
            pass
        elif item.checkState(0) == QtCore.Qt.CheckState.Checked:
            self._updating_tree = True
            top_index: int
            for top_index in range(self.ui.measurement_tree.topLevelItemCount()):
                candidate_item: QtWidgets.QTreeWidgetItem = self.ui.measurement_tree.topLevelItem(top_index)
                if candidate_item is item:
                    pass
                else:
                    candidate_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                    candidate_child_index: int
                    for candidate_child_index in range(candidate_item.childCount()):
                        candidate_item.child(candidate_child_index).setCheckState(
                            0,
                            QtCore.Qt.CheckState.Unchecked,
                        )
            child_index: int
            for child_index in range(item.childCount()):
                item.child(child_index).setCheckState(0, QtCore.Qt.CheckState.Checked)
            self._updating_tree = False

            self._selected_block_type = block_type_data
            self._input_references = list()
            selected_references: List[VarPowerFlowReferenceType] | None = (
                self._active_measurement_vars_dict.get(block_type_data, None)
            )
            if selected_references is not None:
                self._output_references = list(selected_references)
            else:
                self._output_references = list()
            item.setExpanded(True)
            self._refresh_direction_lists()
        elif self._selected_block_type is block_type_data:
            # Keep the visual tree consistent with the inactive key by clearing
            # every child without processing each generated itemChanged signal.
            self._updating_tree = True
            child_index: int
            for child_index in range(item.childCount()):
                item.child(child_index).setCheckState(
                    0,
                    QtCore.Qt.CheckState.Unchecked,
                )
            self._updating_tree = False

            # Removing the active key invalidates both direction collections.
            self._selected_block_type = None
            self._input_references = list()
            self._output_references = list()
            self._refresh_direction_lists()
        else:
            pass

    def _apply_reference_check_change(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Add checked references to outputs and remove unchecked references.

        :param item: Changed child reference item.
        :return: None.
        """
        parent_item: QtWidgets.QTreeWidgetItem | None = item.parent()
        reference_data: object = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if parent_item is None or not isinstance(reference_data, VarPowerFlowReferenceType):
            pass
        else:
            parent_type_data: object = parent_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if parent_type_data is not self._selected_block_type:
                pass
            elif item.checkState(0) == QtCore.Qt.CheckState.Checked:
                if (reference_data not in self._input_references
                        and reference_data not in self._output_references):
                    self._output_references.append(reference_data)
                else:
                    pass
                self._refresh_direction_lists()
            else:
                if reference_data in self._input_references:
                    self._input_references.remove(reference_data)
                else:
                    pass
                if reference_data in self._output_references:
                    self._output_references.remove(reference_data)
                else:
                    pass
                self._refresh_direction_lists()

    @QtCore.Slot(QtWidgets.QTreeWidgetItem, int)
    def tree_item_clicked(self,
                          item: QtWidgets.QTreeWidgetItem,
                          column: int) -> None:
        """Expand a clicked measurement key so its references become visible.

        :param item: Clicked tree item.
        :param column: Clicked column.
        :return: None.
        """
        if item.parent() is None and column == 0:
            item.setExpanded(True)
        else:
            pass

    @QtCore.Slot(object, int)
    def move_reference(self,
                       reference_data: object,
                       target_direction: int) -> None:
        """Move one selected reference between the input and output collections.

        :param reference_data: Dragged measurement reference.
        :param target_direction: Zero for inputs or one for outputs.
        :return: None.
        """
        if not isinstance(reference_data, VarPowerFlowReferenceType):
            pass
        elif (reference_data not in self._input_references
              and reference_data not in self._output_references):
            pass
        elif target_direction == 0:
            if reference_data in self._output_references:
                self._output_references.remove(reference_data)
            else:
                pass
            if reference_data not in self._input_references:
                self._input_references.append(reference_data)
            else:
                pass
            self._refresh_direction_lists()
        elif target_direction == 1:
            if reference_data in self._input_references:
                self._input_references.remove(reference_data)
            else:
                pass
            if reference_data not in self._output_references:
                self._output_references.append(reference_data)
            else:
                pass
            self._refresh_direction_lists()
        else:
            pass

    def _refresh_direction_lists(self) -> None:
        """Render selected references in the input and output list widgets.

        :return: None.
        """
        self.ui.input_list.clear()
        self.ui.output_list.clear()
        reference: VarPowerFlowReferenceType
        for reference in self._input_references:
            self._add_direction_item(self.ui.input_list, reference)
        for reference in self._output_references:
            self._add_direction_item(self.ui.output_list, reference)

    def _add_direction_item(self,
                            destination_list: MeasurementReferenceList,
                            reference: VarPowerFlowReferenceType) -> None:
        """Insert one draggable typed reference in a direction list.

        :param destination_list: Input or output list receiving the item.
        :param reference: Measurement reference represented by the item.
        :return: None.
        """
        list_item: QtWidgets.QListWidgetItem = QtWidgets.QListWidgetItem(reference.name)
        list_item.setData(QtCore.Qt.ItemDataRole.UserRole, reference)
        list_item.setFlags(
            QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsDragEnabled
        )
        destination_list.addItem(list_item)

    def accept_dialog(self) -> None:
        """Accept the dialog only when a bus and one measurement key are selected.

        :return: None.
        """
        if self._selected_bus is None:
            QtWidgets.QMessageBox.warning(self, "Measurement block", "Select one bus.")
        elif self._selected_block_type is None:
            QtWidgets.QMessageBox.warning(self, "Measurement block", "Select one measurement type.")
        else:
            self.accept()

    def get_user_info(
            self,
    ) -> Tuple[
        Bus,
        BlockType,
        List[VarPowerFlowReferenceType],
        List[VarPowerFlowReferenceType],
    ]:
        """Return the selected bus, block type, and detached reference lists.

        :return: Selected bus, block type, input references, and output references.
        :raises RuntimeError: If queried before a complete selection exists.
        """
        if self._selected_bus is not None and self._selected_block_type is not None:
            return (
                self._selected_bus,
                self._selected_block_type,
                list(self._input_references),
                list(self._output_references),
            )
        else:
            raise RuntimeError("Measurement dialog has no complete selection")
