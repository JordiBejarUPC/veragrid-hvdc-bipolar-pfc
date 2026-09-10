# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Dict, Set

from PySide6 import QtWidgets, QtCore, QtGui

from VeraGrid.Gui.messages import info_msg
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import DynamicEditorEntry
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import get_block_for_entry
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_models import DynamicEventGroupDraft
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_models import DynamicEventsDraftSession

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.enumerations import DynamicSimulationMode


class SwitchSequenceData:
    """
    Typed payload produced by the switch-sequence dialog.
    """

    __slots__ = (
        "parameter",
        "group",
        "times",
        "values",
    )

    def __init__(self,
                 parameter: Var,
                 group: EmtEventsGroup,
                 times: List[float],
                 values: List[float]) -> None:
        """
        Build one switch-sequence payload.

        :param parameter: Mode parameter toggled by the sequence.
        :param group: Target EMT events group.
        :param times: Ordered switching times.
        :param values: Ordered switching values.
        :return: None.
        """
        self.parameter: Var = parameter
        self.group: EmtEventsGroup = group
        self.times: List[float] = times
        self.values: List[float] = values

    def to_dict(self) -> Dict[str, object]:
        """
        Preserve the historical dialog API expected by callers and tests.

        :return: Dictionary view of the payload.
        """
        payload: Dict[str, object] = dict()
        payload["parameter"] = self.parameter
        payload["group"] = self.group
        payload["times"] = list(self.times)
        payload["values"] = list(self.values)
        return payload


def _switch_sequence_pair_sort_key(pair: tuple[float, float]) -> float:
    """
    Return the stable ordering key for one switch-sequence pair.

    :param pair: ``(time, value)`` sequence item.
    :return: Time component used for sorting.
    """
    return float(pair[0])


def build_event_group_status_icon(color: QtGui.QColor) -> QtGui.QIcon:
    """Build a small filled-circle icon for an event-group state action.

    :param color: Circle fill and border color.
    :return: Icon containing the painted status circle.
    """
    icon_size: int = 16
    circle_margin: int = 3
    pixmap: QtGui.QPixmap = QtGui.QPixmap(icon_size, icon_size)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter: QtGui.QPainter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QtGui.QPen(color))
    painter.setBrush(QtGui.QBrush(color))
    painter.drawEllipse(
        circle_margin,
        circle_margin,
        icon_size - 2 * circle_margin,
        icon_size - 2 * circle_margin,
    )
    painter.end()
    return QtGui.QIcon(pixmap)


def create_dynamic_events_group_with_dialog(circuit: MultiCircuit,
                                            mode: DynamicSimulationMode,
                                            parent: QtWidgets.QWidget | None,
                                            missing_group_message: str,
                                            created_group_message_title: str,
                                            created_group_message_body_prefix: str) -> RmsEventsGroup | EmtEventsGroup | None:
    """
    Create one RMS/EMT events group through the shared modal workflow.

    :param circuit: Circuit that owns the canonical event-group collections.
    :param mode: Dynamic simulation family that determines the group type.
    :param parent: Optional parent widget for the modal dialogs.
    :param missing_group_message: Informational text shown before opening the name dialog.
    :param created_group_message_title: Title shown after the group is created.
    :param created_group_message_body_prefix: Prefix used in the created-group confirmation body.
    :return: Created group asset, or ``None`` when the user cancels.
    """
    dialog_title: str

    # The first modal explains why the broader workflow cannot proceed without
    # at least one event-group asset. Reusing this flow keeps event creation
    # semantics identical across the GUI.
    if mode == DynamicSimulationMode.RMS:
        dialog_title = QtCore.QCoreApplication.translate("DynamicEventEditor", "No RMS Events Group")
    else:
        dialog_title = QtCore.QCoreApplication.translate("DynamicEventEditor", "No EMT Events Group")

    if parent is not None:
        QtWidgets.QMessageBox.information(parent, dialog_title, missing_group_message)
    else:
        info_msg(missing_group_message)
        pass

    # The canonical name-entry dialog ensures that every workflow creates the
    # same persisted asset shape and requires the same explicit user choice.
    dialog: DynamicEventsGroupsDialog = DynamicEventsGroupsDialog(parent=parent, mode=mode)
    dialog_result: int = dialog.exec()
    if dialog_result == QtWidgets.QDialog.DialogCode.Accepted:
        group_name: str = dialog.get_name()
        if mode == DynamicSimulationMode.RMS:
            created_group: RmsEventsGroup | EmtEventsGroup = RmsEventsGroup(idtag=None, name=group_name)
            circuit.add_rms_events_group(created_group)
        else:
            created_group = EmtEventsGroup(idtag=None, name=group_name)
            circuit.add_emt_events_group(created_group)

        if parent is not None:
            QtWidgets.QMessageBox.information(
                parent,
                created_group_message_title,
                QtCore.QCoreApplication.translate("DynamicEventEditor", "{prefix}: {group_name}").format(
                    prefix=created_group_message_body_prefix,
                    group_name=group_name,
                )
            )
        else:
            pass
        return created_group
    else:
        return None


def collect_block_runtime_event_parameters(block: Block) -> tuple[List[Var], Set[int]]:
    """
    Collect all runtime event and mode parameters from a block hierarchy.

    :param block: Root symbolic block.
    :return: Ordered parameter list plus the mode-parameter UID set.
    """
    parameters: List[Var] = list()
    mode_parameter_uids: Set[int] = set()
    seen_uids: Set[int] = set()
    block_obj: Block
    parameter: Var

    for block_obj in block.get_all_blocks():
        for parameter in block_obj.event_dict.keys():
            if parameter.uid not in seen_uids:
                seen_uids.add(parameter.uid)
                parameters.append(parameter)
            else:
                pass

        for parameter in block_obj.mode_dict.keys():
            mode_parameter_uids.add(parameter.uid)

            if parameter.uid not in seen_uids:
                seen_uids.add(parameter.uid)
                parameters.append(parameter)
            else:
                pass

    return parameters, mode_parameter_uids


def collect_dynamic_events_page_parameters(
        entry: DynamicEditorEntry,
        mode: DynamicSimulationMode,
) -> tuple[List[Var], Set[int], bool]:
    """Collect the current saved-model parameters used by one events page.

    The persistent model is read every time the events page is activated. This
    ensures that an events page never keeps the detached ``Var`` objects owned
    by a model editor working copy.

    :param entry: Device entry represented by the events page.
    :param mode: RMS or EMT model whose parameters are requested.
    :return: Parameters, mode-parameter UIDs and saved-model empty state.
    """
    block: object = get_block_for_entry(entry=entry, mode=mode)
    if isinstance(block, Block):
        parameters: List[Var]
        mode_parameter_uids: Set[int]
        parameters, mode_parameter_uids = collect_block_runtime_event_parameters(block=block)
        return list(parameters), set(mode_parameter_uids), block.empty()
    else:
        return list(), set(), True


class SwitchSequenceRow:
    """
    Encapsulates one row in the switch sequence helper dialog.
    """

    __slots__ = (
        "__weakref__",
        "table",
        "row",
        "time_spin",
        "state_combo",
    )

    def __init__(self, table: QtWidgets.QTableWidget, row: int) -> None:
        """
        Build one switch-sequence row.

        :param table: Parent table that owns the row widgets.
        :param row: Physical row index inside the table.
        :return: None.
        """
        self.table: QtWidgets.QTableWidget = table
        self.row: int = row

        checkbox: QtWidgets.QTableWidgetItem = QtWidgets.QTableWidgetItem()
        checkbox.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
        checkbox.setCheckState(QtCore.Qt.CheckState.Unchecked)
        table.setItem(row, 0, checkbox)

        self.time_spin = QtWidgets.QDoubleSpinBox()
        self.time_spin.setDecimals(4)
        self.time_spin.setRange(0.0, 1e9)
        self.time_spin.setSingleStep(0.1)
        self.time_spin.setSuffix(" s")
        table.setCellWidget(row, 1, self.time_spin)

        self.state_combo = QtWidgets.QComboBox()
        self.state_combo.addItem(QtCore.QCoreApplication.translate("SwitchSequenceDialog", "Open"), 0.0)
        self.state_combo.addItem(QtCore.QCoreApplication.translate("SwitchSequenceDialog", "Close"), 1.0)
        table.setCellWidget(row, 2, self.state_combo)

    def is_checked(self) -> bool:
        item = self.table.item(self.row, 0)
        return bool(item and item.checkState() == QtCore.Qt.CheckState.Checked)

    def get_data(self) -> tuple[float, float]:
        return float(self.time_spin.value()), float(self.state_combo.currentData())

    def set_data(self, target_time: float, state_value: float) -> None:
        self.time_spin.setValue(float(target_time))
        state_index: int = self.state_combo.findData(float(state_value))
        if state_index >= 0:
            self.state_combo.setCurrentIndex(state_index)
        else:
            pass


class SwitchSequenceDialog(QtWidgets.QDialog):
    """
    Helper dialog that expands one switch opening and reclosing plan into EMT event rows.
    """

    __slots__ = (
        "mode_parameters",
        "events_groups",
        "rows",
        "_data",
        "parameter_combo",
        "group_combo",
        "sequence_table",
        "add_row_btn",
        "remove_row_btn",
    )

    def __init__(self,
                 mode_parameters: List[Var],
                 events_groups: List[EmtEventsGroup],
                 parent: QtWidgets.QWidget | None = None) -> None:
        """
        Build the switch-sequence helper dialog.

        :param mode_parameters: Discrete mode parameters eligible for switching.
        :param events_groups: Available EMT events groups.
        :param parent: Optional parent widget.
        :return: None.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Switch Sequence Wizard"))
        self.setMinimumWidth(520)
        self.mode_parameters: List[Var] = mode_parameters
        self.events_groups: List[EmtEventsGroup] = events_groups
        self.rows: List[SwitchSequenceRow] = list()
        self._data: SwitchSequenceData | None = None

        # Stage 1: build the static form that chooses the discrete parameter
        # and the persisted events group receiving the expanded sequence.
        layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        form_layout: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        self.parameter_combo = QtWidgets.QComboBox()
        parameter: Var
        for parameter in mode_parameters:
            self.parameter_combo.addItem(parameter.name, parameter)
        form_layout.addRow(self.tr("Mode Parameter"), self.parameter_combo)

        self.group_combo = QtWidgets.QComboBox()
        group: EmtEventsGroup
        for group in events_groups:
            self.group_combo.addItem(group.name, group)
        form_layout.addRow(self.tr("Group"), self.group_combo)

        self.sequence_table = QtWidgets.QTableWidget(0, 3)
        self.sequence_table.setHorizontalHeaderLabels(["", self.tr("Time"), self.tr("State")])
        self.sequence_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.sequence_table.horizontalHeader().setStretchLastSection(True)
        self.sequence_table.verticalHeader().setVisible(False)
        self.sequence_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.sequence_table)

        # Stage 2: expose row-level editing controls that let the user build
        # the ordered switching sequence explicitly.
        buttons_layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        self.add_row_btn = QtWidgets.QPushButton(self.tr("Add Sequence Step"))
        self.remove_row_btn = QtWidgets.QPushButton(self.tr("Remove Selected Rows"))
        buttons_layout.addWidget(self.add_row_btn)
        buttons_layout.addWidget(self.remove_row_btn)
        layout.addLayout(buttons_layout)

        # Stage 3: keep confirmation at the bottom so the sequence is validated
        # only after all rows have been normalized and sorted.
        dialog_buttons: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        layout.addWidget(dialog_buttons)

        self.add_row_btn.clicked.connect(self.add_row)
        self.remove_row_btn.clicked.connect(self.remove_checked_rows)
        dialog_buttons.accepted.connect(self.accept_dialog)
        dialog_buttons.rejected.connect(self.reject)

        self.add_row()

    def add_row(self) -> None:
        """
        Append one editable step to the switch sequence.

        :return: None.
        """
        row_index: int = self.sequence_table.rowCount()
        self.sequence_table.insertRow(row_index)
        row: SwitchSequenceRow = SwitchSequenceRow(self.sequence_table, row_index)
        self.rows.append(row)

    def remove_checked_rows(self) -> None:
        """
        Remove every sequence row marked for deletion.

        :return: None.
        """
        rows_to_remove: List[SwitchSequenceRow] = [row for row in self.rows if row.is_checked()]

        if len(rows_to_remove) == 0:
            QtWidgets.QMessageBox.information(self,
                                              self.tr("Switch Sequence"),
                                              self.tr("Please check at least one row to remove."))
        else:
            row: SwitchSequenceRow
            for row in reversed(rows_to_remove):
                self.sequence_table.removeRow(row.row)
                self.rows.remove(row)

            index: int
            reindexed_row: SwitchSequenceRow
            for index, reindexed_row in enumerate(self.rows):
                reindexed_row.row = index

    def accept_dialog(self) -> None:
        """
        Validate the discrete sequence and store it as typed payload.

        :return: None.
        """
        parameter: object = self.parameter_combo.currentData()
        group: object = self.group_combo.currentData()
        times: list[float] = list()
        values: list[float] = list()
        row: SwitchSequenceRow

        if parameter is None or group is None:
            QtWidgets.QMessageBox.warning(self,
                                          self.tr("Switch Sequence"),
                                          self.tr("Select a mode parameter and an events group."))
            return
        else:
            pass

        if not isinstance(parameter, Var) or not isinstance(group, EmtEventsGroup):
            QtWidgets.QMessageBox.warning(self,
                                          self.tr("Switch Sequence"),
                                          self.tr("The selected parameter or group is invalid."))
            return
        else:
            pass

        if len(self.rows) == 0:
            QtWidgets.QMessageBox.warning(self,
                                          self.tr("Switch Sequence"),
                                          self.tr("Add at least one sequence row."))
            return
        else:
            pass

        # Stage 4: read every row before sorting so the dialog preserves the
        # explicit user input and then normalizes it into monotonic time order.
        for row in self.rows:
            target_time, state_value = row.get_data()
            times.append(target_time)
            values.append(state_value)

        sorted_pairs: List[tuple[float, float]] = sorted(zip(times, values), key=_switch_sequence_pair_sort_key)
        sorted_times: List[float] = [float(item[0]) for item in sorted_pairs]
        sorted_values: List[float] = [float(item[1]) for item in sorted_pairs]
        self._data = SwitchSequenceData(parameter=parameter,
                                        group=group,
                                        times=sorted_times,
                                        values=sorted_values)
        self.accept()

    def get_data(self) -> Dict[str, object]:
        """
        Return the historical dictionary view expected by callers and tests.

        :return: Dictionary payload for compatibility.
        """
        if self._data is None:
            return dict()
        else:
            return self._data.to_dict()

    def get_typed_data(self) -> SwitchSequenceData | None:
        """Return the validated switch sequence without dictionary conversion.

        :return: Typed sequence payload, or ``None`` before acceptance.
        """
        return self._data


class DynamicEventsGroupManagerDialog(QtWidgets.QDialog):
    """Manage the event groups belonging to one simulation mode."""

    __slots__ = (
        "session",
        "mode",
        "name_edit",
        "add_button",
        "groups_list",
        "remove_button",
        "activate_button",
        "deactivate_button",
        "close_buttons",
        "_prepared_to_delete",
    )

    GROUP_DATA_ROLE: int = int(QtCore.Qt.ItemDataRole.UserRole)

    def __init__(self,
                 session: DynamicEventsDraftSession,
                 mode: DynamicSimulationMode,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """Build the multi-selection event-group manager.

        :param session: Shared event transaction edited by the dialog.
        :param mode: RMS or EMT group family displayed by the dialog.
        :param parent: Optional parent widget.
        :return: None.
        """
        super().__init__(parent)
        self.session: DynamicEventsDraftSession = session
        self.mode: DynamicSimulationMode = mode
        self._prepared_to_delete: bool = False
        self.setWindowTitle(self.tr("Edit Events Groups"))
        self.setModal(True)
        self.setMinimumSize(480, 360)

        # New groups are created without closing the manager so several groups
        # can be prepared in one editing operation.
        self.name_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(self)
        self.name_edit.setPlaceholderText(self.tr("Enter group name"))
        self.name_edit.setMaximumWidth(260)
        self.add_button: QtWidgets.QPushButton = QtWidgets.QPushButton("+", self)
        self.add_button.setToolTip(self.tr("Add event group"))
        self.add_button.setFixedWidth(34)

        create_layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        create_layout.addWidget(self.name_edit)
        create_layout.addWidget(self.add_button)
        create_layout.addStretch(1)

        # Inactive groups remain enabled and selectable; only their palette is
        # muted so they can be selected and activated again.
        self.groups_list: QtWidgets.QListWidget = QtWidgets.QListWidget(self)
        self.groups_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.groups_list.viewport().installEventFilter(self)

        self.remove_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            self.tr("− Remove"),
            self,
        )
        self.activate_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            build_event_group_status_icon(QtGui.QColor("#2e9f45")),
            self.tr("Activate"),
            self,
        )
        self.deactivate_button: QtWidgets.QPushButton = QtWidgets.QPushButton(
            build_event_group_status_icon(QtGui.QColor("#808080")),
            self.tr("Deactivate"),
            self,
        )

        action_layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        action_layout.addWidget(self.remove_button)
        action_layout.addWidget(self.activate_button)
        action_layout.addWidget(self.deactivate_button)
        action_layout.addStretch(1)

        self.close_buttons: QtWidgets.QDialogButtonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close,
            parent=self,
        )

        main_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(create_layout)
        main_layout.addWidget(self.groups_list)
        main_layout.addLayout(action_layout)
        main_layout.addWidget(self.close_buttons)

        self.add_button.clicked.connect(self.add_group)
        self.name_edit.returnPressed.connect(self.add_group)
        self.remove_button.clicked.connect(self.remove_selected_groups)
        self.activate_button.clicked.connect(self.activate_selected_groups)
        self.deactivate_button.clicked.connect(self.deactivate_selected_groups)
        self.groups_list.itemSelectionChanged.connect(self.update_action_state)
        self.close_buttons.rejected.connect(self.reject)

        self.refresh_groups()

    def prepare_to_delete(self) -> None:
        """Detach viewport callbacks before Qt starts deleting child widgets.

        :return: None.
        """
        if self._prepared_to_delete:
            return
        else:
            self._prepared_to_delete = True

        # The viewport can emit one final event while its QListWidget parent is
        # being destroyed. Removing the filter while both objects are alive
        # prevents that event from dereferencing an already deleted wrapper.
        self.groups_list.viewport().removeEventFilter(self)

    def reject(self) -> None:
        """Close the manager after detaching its viewport event filter.

        :return: None.
        """
        self.prepare_to_delete()
        QtWidgets.QDialog.reject(self)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Prepare the manager for every window-manager close path.

        :param event: Close event delivered by Qt.
        :return: None.
        """
        self.prepare_to_delete()
        QtWidgets.QDialog.closeEvent(self, event)

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Clear group selection when the empty list background is clicked.

        :param watched: Object receiving the intercepted event.
        :param event: Qt event delivered to the watched object.
        :return: Whether the event was consumed.
        """
        if self._prepared_to_delete:
            return QtWidgets.QDialog.eventFilter(self, watched, event)
        else:
            pass

        is_list_mouse_press: bool = (
            watched is self.groups_list.viewport()
            and event.type() == QtCore.QEvent.Type.MouseButtonPress
            and isinstance(event, QtGui.QMouseEvent)
        )
        if is_list_mouse_press and isinstance(event, QtGui.QMouseEvent):
            clicked_index: QtCore.QModelIndex = self.groups_list.indexAt(
                event.position().toPoint()
            )
            if (
                event.button() == QtCore.Qt.MouseButton.LeftButton
                and not clicked_index.isValid()
            ):
                self.groups_list.clearSelection()
                self.groups_list.setCurrentItem(None)
            else:
                pass
        else:
            pass
        return QtWidgets.QDialog.eventFilter(self, watched, event)

    def refresh_groups(self) -> None:
        """Rebuild the visible group list from the current transaction.

        :return: None.
        """
        selected_groups: set[DynamicEventGroupDraft] = set()
        selected_item: QtWidgets.QListWidgetItem
        for selected_item in self.groups_list.selectedItems():
            selected_group: object = selected_item.data(self.GROUP_DATA_ROLE)
            if isinstance(selected_group, DynamicEventGroupDraft):
                selected_groups.add(selected_group)
            else:
                pass

        self.groups_list.clear()
        active_foreground: QtGui.QBrush = self.palette().brush(QtGui.QPalette.ColorRole.Text)
        active_background: QtGui.QBrush = self.palette().brush(QtGui.QPalette.ColorRole.Base)
        inactive_foreground: QtGui.QBrush = QtGui.QBrush(QtGui.QColor("#686868"))
        inactive_background: QtGui.QBrush = QtGui.QBrush(QtGui.QColor("#eeeeee"))
        group: DynamicEventGroupDraft
        for group in self.session.get_groups(self.mode):
            list_item: QtWidgets.QListWidgetItem = QtWidgets.QListWidgetItem(group.name)
            list_item.setData(self.GROUP_DATA_ROLE, group)
            if group.active:
                list_item.setForeground(active_foreground)
                list_item.setBackground(active_background)
            else:
                list_item.setForeground(inactive_foreground)
                list_item.setBackground(inactive_background)
            self.groups_list.addItem(list_item)
            list_item.setSelected(group in selected_groups)

        self.update_action_state()

    @QtCore.Slot(bool)
    def add_group(self, _checked: bool = False) -> None:
        """Add the entered group to the transaction and refresh the list.

        :param _checked: Optional button checked state supplied by Qt.
        :return: None.
        """
        group_name: str = self.name_edit.text().strip()
        created_group: DynamicEventGroupDraft | None = self.session.add_group(
            mode=self.mode,
            name=group_name,
        )
        if created_group is None:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Invalid event group"),
                self.tr("The event group name must be non-empty and unique in this simulation mode."),
            )
        else:
            self.name_edit.clear()
            self.refresh_groups()
            self.select_group(created_group)

    def select_group(self, group: DynamicEventGroupDraft) -> None:
        """Select one visible group after a list rebuild.

        :param group: Group draft to select.
        :return: None.
        """
        row_index: int
        for row_index in range(self.groups_list.count()):
            list_item: QtWidgets.QListWidgetItem = self.groups_list.item(row_index)
            item_group: object = list_item.data(self.GROUP_DATA_ROLE)
            if item_group is group:
                list_item.setSelected(True)
                self.groups_list.setCurrentItem(list_item)
            else:
                pass

    def get_selected_groups(self) -> list[DynamicEventGroupDraft]:
        """Return every valid group represented by a selected list item.

        :return: Selected event-group drafts.
        """
        groups: list[DynamicEventGroupDraft] = list()
        list_item: QtWidgets.QListWidgetItem
        for list_item in self.groups_list.selectedItems():
            group: object = list_item.data(self.GROUP_DATA_ROLE)
            if isinstance(group, DynamicEventGroupDraft):
                groups.append(group)
            else:
                pass
        return groups

    @QtCore.Slot()
    def update_action_state(self) -> None:
        """Enable group actions only while at least one group is selected.

        :return: None.
        """
        has_selection: bool = len(self.groups_list.selectedItems()) > 0
        self.remove_button.setEnabled(has_selection)
        self.activate_button.setEnabled(has_selection)
        self.deactivate_button.setEnabled(has_selection)

    @QtCore.Slot(bool)
    def remove_selected_groups(self, _checked: bool = False) -> None:
        """Mark the selected groups and their events for removal.

        :param _checked: Optional button checked state supplied by Qt.
        :return: None.
        """
        selected_groups: list[DynamicEventGroupDraft] = self.get_selected_groups()
        if len(selected_groups) > 0:
            confirmation: QtWidgets.QMessageBox.StandardButton = QtWidgets.QMessageBox.question(
                self,
                self.tr("Remove event groups"),
                self.tr("Remove the selected event groups and all their events?"),
                QtWidgets.QMessageBox.StandardButton.Yes |
                QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if confirmation == QtWidgets.QMessageBox.StandardButton.Yes:
                group: DynamicEventGroupDraft
                for group in selected_groups:
                    self.session.remove_group(group)
                self.refresh_groups()
            else:
                pass
        else:
            pass

    @QtCore.Slot(bool)
    def activate_selected_groups(self, _checked: bool = False) -> None:
        """Activate every selected event group.

        :param _checked: Optional button checked state supplied by Qt.
        :return: None.
        """
        group: DynamicEventGroupDraft
        for group in self.get_selected_groups():
            self.session.set_group_active(group=group, active=True)
        self.refresh_groups()

    @QtCore.Slot(bool)
    def deactivate_selected_groups(self, _checked: bool = False) -> None:
        """Deactivate every selected event group.

        :param _checked: Optional button checked state supplied by Qt.
        :return: None.
        """
        group: DynamicEventGroupDraft
        for group in self.get_selected_groups():
            self.session.set_group_active(group=group, active=False)
        self.refresh_groups()


class DynamicEventsGroupsDialog(QtWidgets.QDialog):
    """
    Name-entry dialog used to create one RMS or EMT events group.
    """

    __slots__ = (
        "mode",
        "_name",
        "name_label",
        "name_edit",
        "buttons",
    )

    def __init__(self,
                 mode: DynamicSimulationMode,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """
        Build the events-group creation dialog.

        :param mode: Dynamic simulation family that determines the title.
        :param parent: Optional parent widget.
        :return: None.
        """
        super().__init__(parent)

        self.mode = mode
        if self.mode == DynamicSimulationMode.RMS:
            self.setWindowTitle(self.tr("Create RMS Events Group"))
        elif self.mode == DynamicSimulationMode.EMT:
            self.setWindowTitle(self.tr("Create EMT Events Group"))
        self.setModal(True)
        self.setMinimumWidth(300)

        self._name: str | None = None

        # Stage 1: keep the dialog focused on a single explicit choice, the
        # canonical name of the persisted events group asset.
        self.name_label = QtWidgets.QLabel(self.tr("Name:"))
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText(self.tr("Enter group name"))

        # Buttons
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        # Stage 2: build the minimal form that validates the name before the
        # calling workflow mutates the circuit state.
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(self.name_label, self.name_edit)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.buttons)

        # Stage 3: connect both button acceptance and return-press to the same
        # validation path so the workflow stays consistent across input styles.
        self.buttons.accepted.connect(self.accept_dialog)
        self.buttons.rejected.connect(self.reject)
        self.name_edit.returnPressed.connect(self.accept_dialog)

    def accept_dialog(self) -> None:
        """
        Validate the input and store the name.

        :return: None.
        """
        name: str = self.name_edit.text().strip()

        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Invalid name"),
                self.tr("The name cannot be empty.")
            )
            return
        else:
            pass

        self._name = name
        self.accept()

    def get_name(self) -> str:
        """
        Return the validated group name.

        :return: Group name text.
        """
        if self._name is None:
            return ""
        else:
            return self._name
