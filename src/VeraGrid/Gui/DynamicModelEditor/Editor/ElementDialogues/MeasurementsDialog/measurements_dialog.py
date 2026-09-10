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
        self._refresh_references_from_tree()
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
        """Build the bus selector, measurement tree, and buttons.

        :return: None.
        """
        self.ui.setupUi(self)
        self.ui.measurement_tree.setColumnCount(3)
        self.ui.measurement_tree.setHeaderLabels(list(("Name", "I/O", "Comment")))
        self.ui.measurement_tree.header().setStretchLastSection(False)
        self.ui.measurement_tree.header().setSectionResizeMode(
            0,
            QtWidgets.QHeaderView.ResizeMode.Interactive,
        )
        self.ui.measurement_tree.header().setSectionResizeMode(
            1,
            QtWidgets.QHeaderView.ResizeMode.Interactive,
        )
        self.ui.measurement_tree.header().setSectionResizeMode(
            2,
            QtWidgets.QHeaderView.ResizeMode.Interactive,
        )

    def _set_measurement_configuration_enabled(self, enabled: bool) -> None:
        """Enable or shade all controls that depend on the selected bus.

        :param enabled: Whether a concrete bus has been selected.
        :return: None.
        """
        self.ui.measurement_tree.setEnabled(enabled)

    def _populate_measurement_tree(self) -> None:
        """Populate collapsed measurement keys and I/O reference rows.

        :return: None.
        """
        block_type: BlockType
        references: List[VarPowerFlowReferenceType]
        for block_type, references in self._active_measurement_vars_dict.items():
            parent_item: QtWidgets.QTreeWidgetItem = QtWidgets.QTreeWidgetItem(
                self.ui.measurement_tree,
                list((block_type.name, "", "Measurement type")),
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
                    list((reference.name, "Output", "Checked I/O means input")),
                )
                child_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, reference)
                child_item.setFlags(
                    child_item.flags()
                    | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                    | QtCore.Qt.ItemFlag.ItemIsSelectable
                )
                child_item.setCheckState(1, QtCore.Qt.CheckState.Unchecked)
            parent_item.setExpanded(False)

    def _connect_signals(self) -> None:
        """Connect tree changes to the detached selection state.

        :return: None.
        """
        self.ui.measurement_tree.itemChanged.connect(self.tree_item_changed)
        self.ui.measurement_tree.itemClicked.connect(self.tree_item_clicked)
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
        self._refresh_references_from_tree()

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
                        if reference_data in self._input_references:
                            child_item.setCheckState(1, QtCore.Qt.CheckState.Checked)
                            child_item.setText(1, "Input")
                        else:
                            child_item.setCheckState(1, QtCore.Qt.CheckState.Unchecked)
                            child_item.setText(1, "Output")
                else:
                    parent_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
                    child_index = 0
                    for child_index in range(parent_item.childCount()):
                        parent_item.child(child_index).setCheckState(
                            1,
                            QtCore.Qt.CheckState.Unchecked,
                        )
                        parent_item.child(child_index).setText(1, "Output")
            self._updating_tree = False

            if selected_item is not None:
                self.ui.measurement_tree.setCurrentItem(selected_item)
            else:
                pass
            self._refresh_references_from_tree()

    @QtCore.Slot(QtWidgets.QTreeWidgetItem, int)
    def tree_item_changed(self,
                          item: QtWidgets.QTreeWidgetItem,
                          column: int) -> None:
        """Apply exclusive type selection and child I/O direction changes.

        :param item: Tree item whose check state changed.
        :param column: Changed tree column.
        :return: None.
        """
        if self._updating_tree:
            pass
        elif item.parent() is None and column == 0:
            self._apply_key_check_change(item)
        elif item.parent() is not None and column == 1:
            self._apply_reference_io_change(item)
        else:
            pass

    def _apply_key_check_change(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Select at most one key and refresh its child I/O partition.

        :param item: Changed top-level key item.
        :return: None.
        """
        block_type_data: object = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not isinstance(block_type_data, BlockType):
            pass
        elif item.checkState(0) == QtCore.Qt.CheckState.Checked:
            self._select_measurement_parent_item(item)
            self._refresh_references_from_tree()
        elif self._selected_block_type is block_type_data:
            self._selected_block_type = None
            self._input_references = list()
            self._output_references = list()
        else:
            pass

    def _select_measurement_parent_item(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Mark one parent row as the active measurement type.

        :param item: Parent tree item representing a measurement block type.
        :return: None.
        """
        block_type_data: object = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(block_type_data, BlockType):
            self._updating_tree = True
            top_index: int
            for top_index in range(self.ui.measurement_tree.topLevelItemCount()):
                candidate_item: QtWidgets.QTreeWidgetItem = self.ui.measurement_tree.topLevelItem(top_index)
                if candidate_item is item:
                    candidate_item.setCheckState(0, QtCore.Qt.CheckState.Checked)
                    candidate_item.setExpanded(True)
                else:
                    candidate_item.setCheckState(0, QtCore.Qt.CheckState.Unchecked)
            self._updating_tree = False
            self._selected_block_type = block_type_data
        else:
            pass

    def _apply_reference_io_change(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Switch one child row between input and output.

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
                self._select_measurement_parent_item(parent_item)
                self._refresh_reference_io_text(item)
                self._refresh_references_from_tree()
            else:
                self._refresh_reference_io_text(item)
                self._refresh_references_from_tree()

    @QtCore.Slot(QtWidgets.QTreeWidgetItem, int)
    def tree_item_clicked(self,
                          item: QtWidgets.QTreeWidgetItem,
                          column: int) -> None:
        """Expand a clicked measurement key so its reference rows are visible.

        :param item: Clicked tree item.
        :param column: Clicked column.
        :return: None.
        """
        if item.parent() is None:
            item.setExpanded(True)
        else:
            pass

    def _refresh_reference_io_text(self, item: QtWidgets.QTreeWidgetItem) -> None:
        """Mirror the I/O checkbox state as readable tree text.

        :param item: Child reference row whose direction text changed.
        :return: None.
        """
        if item.checkState(1) == QtCore.Qt.CheckState.Checked:
            direction_text: str = "Input"
        else:
            direction_text = "Output"

        if item.text(1) == direction_text:
            pass
        else:
            was_updating_tree: bool = self._updating_tree
            self._updating_tree = True
            item.setText(1, direction_text)
            self._updating_tree = was_updating_tree

    def _refresh_references_from_tree(self) -> None:
        """Build the input and output reference lists from the active tree row.

        :return: None.
        """
        self._input_references = list()
        self._output_references = list()
        top_index: int
        for top_index in range(self.ui.measurement_tree.topLevelItemCount()):
            parent_item: QtWidgets.QTreeWidgetItem = self.ui.measurement_tree.topLevelItem(top_index)
            parent_type_data: object = parent_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if parent_type_data is self._selected_block_type:
                child_index: int
                for child_index in range(parent_item.childCount()):
                    child_item: QtWidgets.QTreeWidgetItem = parent_item.child(child_index)
                    reference_data: object = child_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                    if isinstance(reference_data, VarPowerFlowReferenceType):
                        self._refresh_reference_io_text(child_item)
                        if child_item.checkState(1) == QtCore.Qt.CheckState.Checked:
                            self._input_references.append(reference_data)
                        else:
                            self._output_references.append(reference_data)
                    else:
                        pass
            else:
                pass

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
