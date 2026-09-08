# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_support import DynamicEventsGroupsDialog
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_support import collect_dynamic_events_page_parameters
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_support import SwitchSequenceData
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_support import SwitchSequenceDialog
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_page_ui import Ui_DynamicEventsPage
from VeraGrid.Gui.DynamicModelEditor.Events.dynamic_events_models import (
    DynamicEventDraft,
    DynamicEventGroupDraft,
    DynamicEventsDraftSession,
)
from VeraGrid.Gui.DynamicModelEditor.Workspace.dynamic_editor_entries import DynamicEditorEntry
from VeraGrid.Gui.toast_widget import ToastManager
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicSimulationMode


def resolve_qt_checked_state(value: object) -> bool | None:
    """Normalize a Qt checkbox payload to a two-state boolean.

    PySide6 may deliver ``CheckStateRole`` values either as ``Qt.CheckState``
    members or as the corresponding integer stored in the Qt model variant.
    Partial and invalid states are rejected because dynamic-event controls are
    deliberately two-state checkboxes.

    :param value: Check-state payload received by ``setData``.
    :return: Checked boolean, or ``None`` when the payload is unsupported.
    """
    check_state: QtCore.Qt.CheckState
    if isinstance(value, QtCore.Qt.CheckState):
        check_state = value
    elif isinstance(value, int):
        if 0 <= value <= 2:
            check_state = QtCore.Qt.CheckState(value)
        else:
            return None
    else:
        return None

    if check_state == QtCore.Qt.CheckState.Checked:
        return True
    elif check_state == QtCore.Qt.CheckState.Unchecked:
        return False
    else:
        return None


class InvalidDynamicEventsNode:
    """Typed marker for events whose persisted group reference is unresolved."""

    __slots__ = ()


class DynamicEventsTreeModel(QtGui.QStandardItemModel):
    """Hierarchical editable view of groups and events for one device and mode."""

    event_moved = QtCore.Signal(object)

    __slots__ = (
        "session",
        "device",
        "mode",
        "parameters",
        "mode_parameter_uids",
        "invalid_node",
    )

    COLUMN_PARAMETER: int = 0
    COLUMN_TIME: int = 1
    COLUMN_VALUE: int = 2
    COLUMN_TRANSITION: int = 3
    COLUMN_END_TIME: int = 4
    COLUMN_ALIGN_STEP: int = 5
    EVENT_DRAFT_MIME_TYPE: str = "application/x-veragrid-dynamic-event-draft"

    def __init__(self,
                 session: DynamicEventsDraftSession,
                 device: EditableDevice,
                 mode: DynamicSimulationMode,
                 parameters: list[Var],
                 mode_parameter_uids: set[int],
                 parent: QtCore.QObject | None = None) -> None:
        """Build a device-scoped event tree over the shared transaction.

        :param session: Shared dynamic-events transaction.
        :param device: Device displayed by this page.
        :param mode: RMS or EMT family displayed by this page.
        :param parameters: Runtime parameters available in the current model.
        :param mode_parameter_uids: Parameters representing discrete modes.
        :param parent: Optional Qt owner.
        :return: None.
        """
        QtGui.QStandardItemModel.__init__(self, parent)
        self.session: DynamicEventsDraftSession = session
        self.device: EditableDevice = device
        self.mode: DynamicSimulationMode = mode
        self.parameters: list[Var] = list(parameters)
        self.mode_parameter_uids: set[int] = set(mode_parameter_uids)
        self.invalid_node: InvalidDynamicEventsNode = InvalidDynamicEventsNode()
        self.setHorizontalHeaderLabels(
            list((
                self.tr("Parameter"),
                self.tr("Time"),
                self.tr("New Value"),
                self.tr("Transition"),
                self.tr("End Time"),
                self.tr("Align Step"),
            ))
        )
        self.session.changed.connect(self.rebuild)
        self.session.group_changed.connect(self.refresh_group)
        self.rebuild()

    @QtCore.Slot()
    def rebuild(self) -> None:
        """Rebuild group branches and device-filtered event children.

        :return: None.
        """
        row_count: int = self.rowCount()
        if row_count > 0:
            self.removeRows(0, row_count)
        else:
            pass

        group: DynamicEventGroupDraft
        for group in self.session.get_groups(self.mode):
            group_items: list[QtGui.QStandardItem] = self._build_group_row(group)
            self.appendRow(group_items)
            group_parent: QtGui.QStandardItem = group_items[self.COLUMN_PARAMETER]
            event: DynamicEventDraft
            for event in self.session.get_group_events(group, self.device):
                group_parent.appendRow(self._build_event_row(event))

        invalid_events: list[DynamicEventDraft] = list()
        device_event: DynamicEventDraft
        for device_event in self.session.get_events_for_device(self.device, self.mode):
            if device_event.group is None:
                invalid_events.append(device_event)
            else:
                pass
        if len(invalid_events) > 0:
            invalid_items: list[QtGui.QStandardItem] = self._build_invalid_group_row()
            self.appendRow(invalid_items)
            invalid_parent: QtGui.QStandardItem = invalid_items[self.COLUMN_PARAMETER]
            for device_event in invalid_events:
                invalid_parent.appendRow(self._build_event_row(device_event))
        else:
            pass

    def replace_parameters(self,
                           parameters: list[Var],
                           mode_parameter_uids: set[int],
                           rebuild: bool) -> None:
        """Replace saved-model parameter references used by this tree.

        :param parameters: Current event parameters from the saved model.
        :param mode_parameter_uids: Current discrete-mode parameter UIDs.
        :param rebuild: Whether the visible tree must rebuild immediately.
        :return: None.
        """
        self.parameters = list(parameters)
        self.mode_parameter_uids = set(mode_parameter_uids)
        if rebuild:
            self.rebuild()
        else:
            pass

    @QtCore.Slot(object)
    def refresh_group(self, backing_object: object) -> None:
        """Refresh a renamed or reactivated group without rebuilding the tree.

        :param backing_object: Group draft emitted by the shared session.
        :return: None.
        """
        if not isinstance(backing_object, DynamicEventGroupDraft):
            return
        else:
            group_index: QtCore.QModelIndex = self.index_for_backing_object(backing_object)
        if group_index.isValid():
            QtGui.QStandardItemModel.setData(
                self,
                group_index,
                backing_object.name,
                QtCore.Qt.ItemDataRole.DisplayRole,
            )
            if backing_object.active:
                check_state: QtCore.Qt.CheckState = QtCore.Qt.CheckState.Checked
            else:
                check_state = QtCore.Qt.CheckState.Unchecked
            QtGui.QStandardItemModel.setData(
                self,
                group_index,
                check_state,
                QtCore.Qt.ItemDataRole.CheckStateRole,
            )
        else:
            pass

    def _build_group_row(self, group: DynamicEventGroupDraft) -> list[QtGui.QStandardItem]:
        """Build one checkable editable group branch.

        :param group: Group transaction record represented by the row.
        :return: Complete six-column item row.
        """
        items: list[QtGui.QStandardItem] = list()
        column_index: int
        for column_index in range(self.columnCount()):
            item: QtGui.QStandardItem = QtGui.QStandardItem()
            item.setEditable(False)
            item.setData(group, QtCore.Qt.ItemDataRole.UserRole)
            items.append(item)
        name_item: QtGui.QStandardItem = items[self.COLUMN_PARAMETER]
        name_item.setText(group.name)
        name_item.setEditable(True)
        name_item.setCheckable(True)
        if group.active:
            name_item.setCheckState(QtCore.Qt.CheckState.Checked)
        else:
            name_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        return items

    def _build_invalid_group_row(self) -> list[QtGui.QStandardItem]:
        """Build the diagnostic branch that keeps unresolved events visible.

        :return: Complete six-column diagnostic row.
        """
        items: list[QtGui.QStandardItem] = list()
        column_index: int
        for column_index in range(self.columnCount()):
            item: QtGui.QStandardItem = QtGui.QStandardItem()
            item.setEditable(False)
            item.setData(self.invalid_node, QtCore.Qt.ItemDataRole.UserRole)
            items.append(item)
        items[self.COLUMN_PARAMETER].setText(self.tr("Invalid / Ungrouped Events"))
        items[self.COLUMN_PARAMETER].setToolTip(
            self.tr("These persisted events do not reference a valid events group and can only be removed.")
        )
        return items

    def _build_event_row(self, event: DynamicEventDraft) -> list[QtGui.QStandardItem]:
        """Build one event child row from the transaction values.

        :param event: Event transaction record represented by the row.
        :return: Complete six-column item row.
        """
        items: list[QtGui.QStandardItem] = list()
        column_index: int
        for column_index in range(self.columnCount()):
            item: QtGui.QStandardItem = QtGui.QStandardItem()
            item.setData(event, QtCore.Qt.ItemDataRole.UserRole)
            items.append(item)

        if event.parameter is None:
            parameter_text: str = self.tr("Invalid parameter")
        else:
            parameter_text = event.parameter.name
        items[self.COLUMN_PARAMETER].setText(parameter_text)
        items[self.COLUMN_TIME].setText(f"{event.time:.4f} s")
        items[self.COLUMN_VALUE].setText(f"{event.value:.6f}")
        items[self.COLUMN_TRANSITION].setText(event.transition_type.name)
        if event.transition_type == DynamicEventTransitionType.Ramp and event.end_time is not None:
            items[self.COLUMN_END_TIME].setText(f"{event.end_time:.4f} s")
        else:
            items[self.COLUMN_END_TIME].setText("")

        align_item: QtGui.QStandardItem = items[self.COLUMN_ALIGN_STEP]
        if self._event_uses_mode_parameter(event):
            align_item.setCheckable(True)
            if event.force_step_alignment:
                align_item.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                align_item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        else:
            align_item.setCheckable(False)
        return items

    def backing_object(self, index: QtCore.QModelIndex) -> object | None:
        """Return the group, event or diagnostic object represented by a row.

        :param index: Any cell index in the requested row.
        :return: Backing transaction object, diagnostic marker or ``None``.
        """
        if not index.isValid():
            return None
        else:
            return QtGui.QStandardItemModel.data(
                self,
                index.siblingAtColumn(self.COLUMN_PARAMETER),
                QtCore.Qt.ItemDataRole.UserRole,
            )

    def index_for_backing_object(self, backing_object: object) -> QtCore.QModelIndex:
        """Locate the parameter-column index representing one draft object.

        :param backing_object: Group or event draft to locate by identity.
        :return: Matching tree index, or an invalid index when absent.
        """
        return self._find_backing_object_index(backing_object, QtCore.QModelIndex())

    def _find_backing_object_index(
            self,
            backing_object: object,
            parent: QtCore.QModelIndex,
    ) -> QtCore.QModelIndex:
        """Recursively locate one draft below a tree parent.

        :param backing_object: Draft object sought by identity.
        :param parent: Parent index whose children are inspected.
        :return: Matching parameter-column index, or an invalid index.
        """
        row_count: int = self.rowCount(parent)
        row_index: int
        for row_index in range(row_count):
            candidate_index: QtCore.QModelIndex = self.index(row_index, self.COLUMN_PARAMETER, parent)
            candidate_backing: object | None = self.backing_object(candidate_index)
            if candidate_backing is backing_object:
                return candidate_index
            else:
                child_result: QtCore.QModelIndex = self._find_backing_object_index(
                    backing_object,
                    candidate_index,
                )
            if child_result.isValid():
                return child_result
            else:
                pass
        return QtCore.QModelIndex()

    def _parameter_is_available(self, parameter: Var | None) -> bool:
        """Return whether a symbolic parameter still belongs to the current model.

        :param parameter: Parameter referenced by an event.
        :return: Whether the exact symbolic object is available for editing.
        """
        if parameter is None:
            return False
        else:
            pass
        available_parameter: Var
        for available_parameter in self.parameters:
            if available_parameter is parameter:
                return True
            else:
                pass
        return False

    def _event_uses_mode_parameter(self, event: DynamicEventDraft) -> bool:
        """Return whether an event targets a discrete mode parameter.

        :param event: Event draft to inspect.
        :return: Whether step alignment is applicable.
        """
        return event.parameter is not None and event.parameter.uid in self.mode_parameter_uids

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """Expose edits supported by group and event rows.

        :param index: Tree cell queried by Qt.
        :return: Item flags for selection, editing or check-state changes.
        """
        backing: object | None = self.backing_object(index)
        base_flags: QtCore.Qt.ItemFlag = (
            QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        )
        if isinstance(backing, DynamicEventGroupDraft):
            base_flags |= QtCore.Qt.ItemFlag.ItemIsDropEnabled
            if index.column() == self.COLUMN_PARAMETER:
                return base_flags | QtCore.Qt.ItemFlag.ItemIsEditable | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            else:
                return base_flags
        elif isinstance(backing, DynamicEventDraft):
            if backing.group is not None and not backing.group.is_removed:
                base_flags |= QtCore.Qt.ItemFlag.ItemIsDragEnabled
            else:
                pass
            editable: bool = self._parameter_is_available(backing.parameter) and backing.group is not None
            if not editable:
                return base_flags
            elif index.column() == self.COLUMN_ALIGN_STEP:
                if self._event_uses_mode_parameter(backing):
                    return base_flags | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                else:
                    return base_flags
            elif index.column() == self.COLUMN_END_TIME:
                if backing.transition_type == DynamicEventTransitionType.Ramp:
                    return base_flags | QtCore.Qt.ItemFlag.ItemIsEditable
                else:
                    return base_flags
            else:
                return base_flags | QtCore.Qt.ItemFlag.ItemIsEditable
        else:
            return base_flags

    def mimeTypes(self) -> list[str]:
        """Return the private MIME format used for event-row drags.

        :return: Supported internal event-draft MIME type.
        """
        return list((self.EVENT_DRAFT_MIME_TYPE,))

    def supportedDragActions(self) -> QtCore.Qt.DropAction:
        """Expose the safe transport action used by event drags.

        The model performs the semantic move through the draft session. Using
        Qt's copy transport prevents the item view from independently removing
        a source row after the session has already rebuilt the projection.

        :return: Copy transport action.
        """
        return QtCore.Qt.DropAction.CopyAction

    def supportedDropActions(self) -> QtCore.Qt.DropAction:
        """Expose the safe transport action accepted by group rows.

        :return: Copy transport action.
        """
        return QtCore.Qt.DropAction.CopyAction

    def mimeData(self, indexes: list[QtCore.QModelIndex]) -> QtCore.QMimeData:
        """Encode the single event draft represented by a selected row.

        The payload contains process-local identities for both the shared
        session and event draft. The receiver resolves those identities back
        through its own session instead of trusting serialized event fields.

        :param indexes: Selected indexes supplied by the tree view.
        :return: MIME data containing a valid payload only for one event row.
        """
        mime_data: QtCore.QMimeData = QtCore.QMimeData()
        dragged_event: DynamicEventDraft | None = None
        index: QtCore.QModelIndex
        for index in indexes:
            backing: object | None = self.backing_object(index)
            if isinstance(backing, DynamicEventDraft) and backing.group is not None:
                if dragged_event is None or dragged_event is backing:
                    dragged_event = backing
                else:
                    # Although the view currently has single-row selection,
                    # reject ambiguous payloads if that policy ever changes.
                    return mime_data
            else:
                pass

        if dragged_event is not None and not dragged_event.is_removed:
            payload_text: str = f"{id(self.session)}:{id(dragged_event)}"
            payload_bytes: QtCore.QByteArray = QtCore.QByteArray(payload_text.encode("ascii"))
            mime_data.setData(self.EVENT_DRAFT_MIME_TYPE, payload_bytes)
        else:
            pass
        return mime_data

    def _event_from_mime_data(self, data: QtCore.QMimeData) -> DynamicEventDraft | None:
        """Resolve an internal drag payload to a live event draft.

        :param data: MIME data received by a candidate drop target.
        :return: Matching live event draft from this session, or ``None``.
        """
        if not data.hasFormat(self.EVENT_DRAFT_MIME_TYPE):
            return None
        else:
            payload_text: str = bytes(data.data(self.EVENT_DRAFT_MIME_TYPE)).decode(
                "ascii",
                errors="replace",
            ).strip()
        payload_parts: list[str] = payload_text.split(":")
        if len(payload_parts) != 2 or not payload_parts[0].isdigit() or not payload_parts[1].isdigit():
            return None
        else:
            payload_session_identity: int = int(payload_parts[0])
            payload_event_identity: int = int(payload_parts[1])
        if payload_session_identity != id(self.session):
            return None
        else:
            pass

        candidate_event: DynamicEventDraft
        for candidate_event in self.session.event_drafts:
            event_is_usable: bool = (
                id(candidate_event) == payload_event_identity
                and not candidate_event.is_removed
                and candidate_event.mode == self.mode
                and candidate_event.device is self.device
                and candidate_event.group is not None
                and not candidate_event.group.is_removed
            )
            if event_is_usable:
                return candidate_event
            else:
                pass
        return None

    def _drop_target_group(
            self,
            row: int,
            column: int,
            parent: QtCore.QModelIndex,
    ) -> DynamicEventGroupDraft | None:
        """Resolve a drop made directly on one compatible group row.

        :param row: Proposed insertion row supplied by Qt.
        :param column: Proposed insertion column supplied by Qt.
        :param parent: Index underneath the drop indicator.
        :return: Compatible destination group, or ``None`` for other targets.
        """
        if row >= 0 or column >= 0:
            return None
        else:
            backing: object | None = self.backing_object(parent)
        if (
            isinstance(backing, DynamicEventGroupDraft)
            and not backing.is_removed
            and backing.mode == self.mode
        ):
            return backing
        else:
            return None

    def canDropMimeData(self,
                        data: QtCore.QMimeData,
                        action: QtCore.Qt.DropAction,
                        row: int,
                        column: int,
                        parent: QtCore.QModelIndex) -> bool:
        """Return whether an event can be moved onto the indicated group row.

        :param data: Event drag payload.
        :param action: Transport action proposed by Qt.
        :param row: Proposed insertion row.
        :param column: Proposed insertion column.
        :param parent: Candidate group index.
        :return: Whether the drop represents a valid group reassignment.
        """
        if action == QtCore.Qt.DropAction.IgnoreAction:
            return True
        elif action != QtCore.Qt.DropAction.CopyAction:
            return False
        else:
            dragged_event: DynamicEventDraft | None = self._event_from_mime_data(data)
            target_group: DynamicEventGroupDraft | None = self._drop_target_group(row, column, parent)
        return dragged_event is not None and target_group is not None and dragged_event.group is not target_group

    def dropMimeData(self,
                     data: QtCore.QMimeData,
                     action: QtCore.Qt.DropAction,
                     row: int,
                     column: int,
                     parent: QtCore.QModelIndex) -> bool:
        """Move one dragged event to the group represented by the drop row.

        :param data: Event drag payload.
        :param action: Transport action proposed by Qt.
        :param row: Proposed insertion row.
        :param column: Proposed insertion column.
        :param parent: Destination group index.
        :return: Whether the transaction accepted and applied the move.
        """
        if action == QtCore.Qt.DropAction.IgnoreAction:
            return True
        elif not self.canDropMimeData(data, action, row, column, parent):
            return False
        else:
            dragged_event: DynamicEventDraft | None = self._event_from_mime_data(data)
            target_group: DynamicEventGroupDraft | None = self._drop_target_group(row, column, parent)
        if dragged_event is not None and target_group is not None:
            moved: bool = self.session.move_event_to_group(dragged_event, target_group)
            if moved:
                self.event_moved.emit(dragged_event)
            else:
                pass
            return moved
        else:
            return False

    def setData(self,
                index: QtCore.QModelIndex,
                value: object,
                role: int = QtCore.Qt.ItemDataRole.EditRole) -> bool:
        """Apply one inline edit to the shared transaction record.

        :param index: Edited group or event cell.
        :param value: Typed value supplied by the delegate.
        :param role: Qt edit or check-state role.
        :return: Whether the transaction accepted the edit.
        """
        backing: object | None = self.backing_object(index)
        if isinstance(backing, DynamicEventGroupDraft):
            if index.column() == self.COLUMN_PARAMETER and role == QtCore.Qt.ItemDataRole.EditRole:
                return self.session.rename_group(backing, str(value))
            elif index.column() == self.COLUMN_PARAMETER and role == QtCore.Qt.ItemDataRole.CheckStateRole:
                group_is_active: bool | None = resolve_qt_checked_state(value)
                if group_is_active is not None:
                    self.session.set_group_active(backing, group_is_active)
                    return True
                else:
                    return False
            else:
                return False
        elif isinstance(backing, DynamicEventDraft):
            accepted: bool = self._set_event_data(backing, index.column(), value, role)
            if accepted:
                self._refresh_event_row(index, backing)
                self.session.mark_changed(rebuild=False)
            else:
                pass
            return accepted
        else:
            return False

    def _refresh_event_row(self,
                           index: QtCore.QModelIndex,
                           event: DynamicEventDraft) -> None:
        """Refresh one edited event row without rebuilding the whole tree.

        Event values are device-page-local, so an inline edit does not require
        a structural broadcast to other tabs. Keeping the existing model
        indexes alive prevents editors and selection from disappearing while a
        cell is being committed.

        :param index: Any index in the edited event row.
        :param event: Event draft containing the accepted values.
        :return: None.
        """
        parameter_index: QtCore.QModelIndex = index.siblingAtColumn(self.COLUMN_PARAMETER)
        time_index: QtCore.QModelIndex = index.siblingAtColumn(self.COLUMN_TIME)
        value_index: QtCore.QModelIndex = index.siblingAtColumn(self.COLUMN_VALUE)
        transition_index: QtCore.QModelIndex = index.siblingAtColumn(self.COLUMN_TRANSITION)
        end_time_index: QtCore.QModelIndex = index.siblingAtColumn(self.COLUMN_END_TIME)
        align_index: QtCore.QModelIndex = index.siblingAtColumn(self.COLUMN_ALIGN_STEP)
        if event.parameter is None:
            parameter_text: str = self.tr("Invalid parameter")
        else:
            parameter_text = event.parameter.name
        QtGui.QStandardItemModel.setData(
            self,
            parameter_index,
            parameter_text,
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        QtGui.QStandardItemModel.setData(
            self,
            time_index,
            f"{event.time:.4f} s",
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        QtGui.QStandardItemModel.setData(
            self,
            value_index,
            f"{event.value:.6f}",
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        QtGui.QStandardItemModel.setData(
            self,
            transition_index,
            event.transition_type.name,
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        if event.transition_type == DynamicEventTransitionType.Ramp and event.end_time is not None:
            end_time_text: str = f"{event.end_time:.4f} s"
        else:
            end_time_text = ""
        QtGui.QStandardItemModel.setData(
            self,
            end_time_index,
            end_time_text,
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        if self._event_uses_mode_parameter(event):
            if event.force_step_alignment:
                check_state: QtCore.Qt.CheckState = QtCore.Qt.CheckState.Checked
            else:
                check_state = QtCore.Qt.CheckState.Unchecked
            QtGui.QStandardItemModel.setData(
                self,
                align_index,
                check_state,
                QtCore.Qt.ItemDataRole.CheckStateRole,
            )
        else:
            QtGui.QStandardItemModel.setData(
                self,
                align_index,
                None,
                QtCore.Qt.ItemDataRole.CheckStateRole,
            )

    def _set_event_data(self,
                        event: DynamicEventDraft,
                        column: int,
                        value: object,
                        role: int) -> bool:
        """Apply one typed event-cell value to its transaction record.

        :param event: Event draft being edited.
        :param column: Logical event column.
        :param value: Delegate value.
        :param role: Qt edit or check-state role.
        :return: Whether the value type and column are valid.
        """
        if column == self.COLUMN_PARAMETER and role == QtCore.Qt.ItemDataRole.EditRole:
            if isinstance(value, Var):
                event.parameter = value
                event.force_step_alignment = value.uid in self.mode_parameter_uids
                return True
            else:
                return False
        elif column == self.COLUMN_TIME and role == QtCore.Qt.ItemDataRole.EditRole:
            if isinstance(value, (float, int)):
                event.time = float(value)
                return True
            else:
                return False
        elif column == self.COLUMN_VALUE and role == QtCore.Qt.ItemDataRole.EditRole:
            if isinstance(value, (float, int)):
                event.value = float(value)
                return True
            else:
                return False
        elif column == self.COLUMN_TRANSITION and role == QtCore.Qt.ItemDataRole.EditRole:
            if isinstance(value, DynamicEventTransitionType):
                event.transition_type = value
                if value == DynamicEventTransitionType.Ramp and event.end_time is None:
                    event.end_time = event.time
                elif value == DynamicEventTransitionType.Step:
                    event.end_time = None
                else:
                    pass
                return True
            else:
                return False
        elif column == self.COLUMN_END_TIME and role == QtCore.Qt.ItemDataRole.EditRole:
            if isinstance(value, (float, int)):
                event.end_time = float(value)
                return True
            else:
                return False
        elif column == self.COLUMN_ALIGN_STEP and role == QtCore.Qt.ItemDataRole.CheckStateRole:
            if self._event_uses_mode_parameter(event):
                force_step_alignment: bool | None = resolve_qt_checked_state(value)
                if force_step_alignment is not None:
                    event.force_step_alignment = force_step_alignment
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False


class DynamicEventsItemDelegate(QtWidgets.QStyledItemDelegate):
    """Provide typed editors for dynamic-event tree cells."""

    __slots__ = ()

    def createEditor(self,
                     parent: QtWidgets.QWidget,
                     option: QtWidgets.QStyleOptionViewItem,
                     index: QtCore.QModelIndex) -> QtWidgets.QWidget | None:
        """Create the editor appropriate for one group or event cell.

        :param parent: Delegate editor parent.
        :param option: Native style options.
        :param index: Edited tree cell.
        :return: Typed editor widget, or ``None`` for check-state cells.
        """
        del option
        model: QtCore.QAbstractItemModel | None = index.model()
        if not isinstance(model, DynamicEventsTreeModel):
            return None
        else:
            backing: object | None = model.backing_object(index)
        if isinstance(backing, DynamicEventGroupDraft):
            return QtWidgets.QLineEdit(parent)
        elif not isinstance(backing, DynamicEventDraft):
            return None
        elif index.column() == model.COLUMN_PARAMETER:
            combo: QtWidgets.QComboBox = QtWidgets.QComboBox(parent)
            parameter: Var
            for parameter in model.parameters:
                combo.addItem(parameter.name, parameter)
            return combo
        elif index.column() in (model.COLUMN_TIME, model.COLUMN_END_TIME):
            time_spin: QtWidgets.QDoubleSpinBox = QtWidgets.QDoubleSpinBox(parent)
            time_spin.setDecimals(4)
            time_spin.setRange(0.0, 1.0e9)
            time_spin.setSingleStep(0.1)
            time_spin.setSuffix(" s")
            return time_spin
        elif index.column() == model.COLUMN_VALUE:
            value_spin: QtWidgets.QDoubleSpinBox = QtWidgets.QDoubleSpinBox(parent)
            value_spin.setDecimals(6)
            value_spin.setRange(-1.0e9, 1.0e9)
            value_spin.setSingleStep(0.01)
            return value_spin
        elif index.column() == model.COLUMN_TRANSITION:
            transition_combo: QtWidgets.QComboBox = QtWidgets.QComboBox(parent)
            transition_combo.addItem(self.tr("Step"), DynamicEventTransitionType.Step)
            transition_combo.addItem(self.tr("Ramp"), DynamicEventTransitionType.Ramp)
            return transition_combo
        else:
            return None

    def setEditorData(self,
                      editor: QtWidgets.QWidget,
                      index: QtCore.QModelIndex) -> None:
        """Populate a typed editor from the selected transaction value.

        :param editor: Editor created for the cell.
        :param index: Edited tree cell.
        :return: None.
        """
        model: QtCore.QAbstractItemModel | None = index.model()
        if not isinstance(model, DynamicEventsTreeModel):
            return
        else:
            backing: object | None = model.backing_object(index)
        if isinstance(backing, DynamicEventGroupDraft) and isinstance(editor, QtWidgets.QLineEdit):
            editor.setText(backing.name)
        elif isinstance(backing, DynamicEventDraft):
            self._set_event_editor_data(editor, index.column(), backing)
        else:
            pass

    def _set_event_editor_data(self,
                               editor: QtWidgets.QWidget,
                               column: int,
                               event: DynamicEventDraft) -> None:
        """Populate one event editor from its typed draft value.

        :param editor: Event-cell editor.
        :param column: Logical event column.
        :param event: Event draft being edited.
        :return: None.
        """
        if column == DynamicEventsTreeModel.COLUMN_PARAMETER and isinstance(editor, QtWidgets.QComboBox):
            parameter_index: int = editor.findData(event.parameter)
            editor.setCurrentIndex(parameter_index)
        elif column == DynamicEventsTreeModel.COLUMN_TIME and isinstance(editor, QtWidgets.QDoubleSpinBox):
            editor.setValue(event.time)
        elif column == DynamicEventsTreeModel.COLUMN_VALUE and isinstance(editor, QtWidgets.QDoubleSpinBox):
            editor.setValue(event.value)
        elif column == DynamicEventsTreeModel.COLUMN_TRANSITION and isinstance(editor, QtWidgets.QComboBox):
            transition_index: int = editor.findData(event.transition_type)
            editor.setCurrentIndex(transition_index)
        elif column == DynamicEventsTreeModel.COLUMN_END_TIME and isinstance(editor, QtWidgets.QDoubleSpinBox):
            if event.end_time is not None:
                editor.setValue(event.end_time)
            else:
                editor.setValue(event.time)
        else:
            pass

    def setModelData(self,
                     editor: QtWidgets.QWidget,
                     model: QtCore.QAbstractItemModel,
                     index: QtCore.QModelIndex) -> None:
        """Commit one typed editor value to the transaction model.

        :param editor: Editor containing the user value.
        :param model: Dynamic events tree model.
        :param index: Edited tree cell.
        :return: None.
        """
        if not isinstance(model, DynamicEventsTreeModel):
            return
        else:
            backing: object | None = model.backing_object(index)
        if isinstance(backing, DynamicEventGroupDraft) and isinstance(editor, QtWidgets.QLineEdit):
            model.setData(index, editor.text(), QtCore.Qt.ItemDataRole.EditRole)
        elif isinstance(backing, DynamicEventDraft):
            if isinstance(editor, QtWidgets.QComboBox):
                model.setData(index, editor.currentData(), QtCore.Qt.ItemDataRole.EditRole)
            elif isinstance(editor, QtWidgets.QDoubleSpinBox):
                model.setData(index, editor.value(), QtCore.Qt.ItemDataRole.EditRole)
            else:
                pass
        else:
            pass


class DynamicEventsPage(QtWidgets.QWidget):
    """One tab page displaying every event for a device and simulation mode."""

    dirtyStateChanged = QtCore.Signal(bool)

    __slots__ = (
        "session",
        "entry",
        "device",
        "mode",
        "parameters",
        "mode_parameter_uids",
        "model_is_empty",
        "ui",
        "empty_model_message",
        "tree_model",
        "tree_view",
        "switch_sequence_action",
        "add_event_action",
        "remove_action",
        "new_group_action",
        "save_button",
        "toast_manager",
        "_prepared_to_delete",
    )

    def __init__(self,
                 session: DynamicEventsDraftSession,
                 entry: DynamicEditorEntry,
                 device: EditableDevice,
                 mode: DynamicSimulationMode,
                 parameters: list[Var],
                 mode_parameter_uids: set[int],
                 model_is_empty: bool,
                 parent: QtWidgets.QWidget | None = None) -> None:
        """Build one device/mode event editor page.

        :param session: Shared dynamic-events transaction.
        :param entry: Device represented by the page.
        :param device: Concrete network device targeted by the page events.
        :param mode: RMS or EMT family represented by the page.
        :param parameters: Runtime parameters available in the current model.
        :param mode_parameter_uids: Parameters representing discrete modes.
        :param model_is_empty: Whether the underlying symbolic block is structurally empty.
        :param parent: Optional owning widget.
        :return: None.
        """
        QtWidgets.QWidget.__init__(self, parent)
        self.session: DynamicEventsDraftSession = session
        self.entry: DynamicEditorEntry = entry
        self.device: EditableDevice = device
        self.mode: DynamicSimulationMode = mode
        self.parameters: list[Var] = list(parameters)
        self.mode_parameter_uids: set[int] = set(mode_parameter_uids)
        self.model_is_empty: bool = bool(model_is_empty)
        self._prepared_to_delete: bool = False
        self.toast_manager: ToastManager = ToastManager(parent=self, position_top=False)
        self.ui: Ui_DynamicEventsPage = Ui_DynamicEventsPage()
        self.ui.setupUi(self)

        # Keep explicit typed aliases for the page behavior while the generated
        # UI object remains the declarative owner of widget construction.
        self.empty_model_message: QtWidgets.QLabel = self.ui.emptyModelMessage
        self.tree_view: QtWidgets.QTreeView = self.ui.eventsTreeView
        self.switch_sequence_action: QtGui.QAction = self.ui.actionSwitchSequence
        self.add_event_action: QtGui.QAction = self.ui.actionAddEvent
        self.remove_action: QtGui.QAction = self.ui.actionRemove
        self.new_group_action: QtGui.QAction = self.ui.actionNewGroup
        self.save_button: QtWidgets.QPushButton = self.ui.saveButton

        # The empty-state label overlays the tree without intercepting input,
        # so existing rows remain interactive while the message is visible.
        self.empty_model_message.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.empty_model_message.setVisible(self.model_is_empty)
        self.empty_model_message.raise_()
        self.switch_sequence_action.setVisible(self.mode == DynamicSimulationMode.EMT)

        self.tree_model: DynamicEventsTreeModel = DynamicEventsTreeModel(
            session=session,
            device=self.device,
            mode=mode,
            parameters=self.parameters,
            mode_parameter_uids=self.mode_parameter_uids,
            parent=self,
        )
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setItemDelegate(DynamicEventsItemDelegate(self.tree_view))
        # The tree is a projection of the transaction, so drops are routed to
        # the model instead of letting QTreeView rearrange QStandardItems.
        self.tree_view.setDragEnabled(True)
        self.tree_view.setAcceptDrops(True)
        self.tree_view.viewport().setAcceptDrops(True)
        self.tree_view.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DragDrop)
        self.tree_view.setDropIndicatorShown(True)
        self.tree_view.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)
        self.tree_view.setDragDropOverwriteMode(False)
        self.tree_view.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked
            | QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.tree_view.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        header: QtWidgets.QHeaderView = self.tree_view.header()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.resizeSection(DynamicEventsTreeModel.COLUMN_PARAMETER, 190)
        header.resizeSection(DynamicEventsTreeModel.COLUMN_TIME, 105)
        header.resizeSection(DynamicEventsTreeModel.COLUMN_VALUE, 110)
        header.resizeSection(DynamicEventsTreeModel.COLUMN_TRANSITION, 105)
        header.resizeSection(DynamicEventsTreeModel.COLUMN_END_TIME, 105)

        self.add_event_action.triggered.connect(self.add_event)
        self.remove_action.triggered.connect(self.remove_selection)
        self.new_group_action.triggered.connect(self.create_event_group)
        self.save_button.clicked.connect(self.save_changes)
        self.switch_sequence_action.triggered.connect(self.open_switch_sequence)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        self.tree_model.modelReset.connect(self.tree_view.expandAll)
        self.tree_model.event_moved.connect(self._show_moved_event)
        selection_model: QtCore.QItemSelectionModel | None = self.tree_view.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(self.update_actions)
        else:
            pass
        self.session.dirty_state_changed.connect(self._on_dirty_state_changed)
        self.tree_view.expandAll()
        self.update_actions()

    def get_dynamic_editor_entry(self) -> DynamicEditorEntry:
        """Return the device entry represented by this workspace page.

        :return: Dynamic device entry associated with the events page.
        """
        return self.entry

    def get_dynamic_editor_mode(self) -> DynamicSimulationMode:
        """Return the simulation mode represented by this workspace page.

        :return: RMS or EMT mode.
        """
        return self.mode

    def get_dynamic_editor_display_title(self) -> str:
        """Build the disambiguated title displayed on the workspace tab.

        :return: Device, mode and events content title.
        """
        return f"{self.entry.display_name} [{self.mode.name} events]"

    @property
    def has_unapplied_changes(self) -> bool:
        """Return the dirty state of the shared event transaction.

        :return: ``True`` when any event page has unsaved changes.
        """
        return self.session.has_unapplied_changes

    def can_close_editor(self, parent: QtWidgets.QWidget | None = None) -> bool:
        """Allow the workspace session to coordinate shared-event close guards.

        :param parent: Unused compatibility parent supplied by the workspace.
        :return: Always ``True`` because the shared session performs the guard.
        """
        del parent
        return True

    def prepare_to_delete(self) -> None:
        """Disconnect the page from its shared transaction before deletion.

        :return: None.
        """
        if self._prepared_to_delete:
            return
        else:
            self._prepared_to_delete = True
        try:
            self.session.dirty_state_changed.disconnect(self._on_dirty_state_changed)
        except (RuntimeError, TypeError):
            pass
        try:
            self.session.changed.disconnect(self.tree_model.rebuild)
        except (RuntimeError, TypeError):
            pass
        try:
            self.session.group_changed.disconnect(self.tree_model.refresh_group)
        except (RuntimeError, TypeError):
            pass

    def set_dark_mode(self) -> None:
        """Refresh the events page after the application selects its dark palette.

        :return: None.
        """
        self.tree_view.viewport().update()

    def set_light_mode(self) -> None:
        """Refresh the events page after the application selects its light palette.

        :return: None.
        """
        self.tree_view.viewport().update()

    @QtCore.Slot(bool)
    def _on_dirty_state_changed(self, dirty: bool) -> None:
        """Forward shared transaction changes to workspace tab-title handling.

        :param dirty: New shared transaction dirty state.
        :return: None.
        """
        self.dirtyStateChanged.emit(dirty)

    def refresh_from_saved_model(self) -> int:
        """Regenerate this page from the latest saved RMS or EMT model.

        Existing event drafts are rebound by variable UID. Events whose target
        parameter no longer exists are removed from the shared transaction.

        :return: Number of obsolete events removed by reconciliation.
        """
        parameters: list[Var]
        mode_parameter_uids: set[int]
        model_is_empty: bool
        parameters, mode_parameter_uids, model_is_empty = collect_dynamic_events_page_parameters(
            entry=self.entry,
            mode=self.mode,
        )
        self.parameters = list(parameters)
        self.mode_parameter_uids = set(mode_parameter_uids)
        self.model_is_empty = model_is_empty
        self.empty_model_message.setVisible(self.model_is_empty)
        self.tree_model.replace_parameters(
            parameters=self.parameters,
            mode_parameter_uids=self.mode_parameter_uids,
            rebuild=False,
        )
        removed_count: int = self.session.reconcile_device_parameters(
            device=self.device,
            mode=self.mode,
            parameters=self.parameters,
        )
        # Reconciliation is device-local, so rebuild this projection after
        # updating both its parameter catalogue and its matching event drafts.
        self.tree_model.rebuild()
        self.update_actions()
        return removed_count

    @QtCore.Slot(bool)
    def create_event_group(self, _checked: bool = False) -> None:
        """Ask for and create one draft event group for this page mode.

        :param _checked: QAction checked state supplied by Qt.
        :return: None.
        """
        group_dialog: DynamicEventsGroupsDialog = DynamicEventsGroupsDialog(
            mode=self.mode,
            parent=self,
        )
        if group_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            created_group: DynamicEventGroupDraft | None = self.session.add_group(
                mode=self.mode,
                name=group_dialog.get_name(),
            )
            if created_group is None:
                QtWidgets.QMessageBox.warning(
                    self,
                    self.tr("Invalid event group"),
                    self.tr("The event group name must be non-empty and unique in this simulation mode."),
                )
            else:
                pass
        else:
            pass

    @QtCore.Slot()
    def save_changes(self) -> None:
        """Validate and persist the complete shared event transaction.

        :return: None.
        """
        validation_error: str | None = self.session.validate()
        if validation_error is not None:
            QtWidgets.QMessageBox.warning(self, self.tr("Invalid dynamic events"), validation_error)
        else:
            self.session.commit()
            self.toast_manager.show_info_toast(self.tr("Events saved"))

    @QtCore.Slot(object)
    def _show_moved_event(self, backing_object: object) -> None:
        """Reveal an event after a successful drag-and-drop reassignment.

        The session rebuild completes synchronously before the model emits
        ``event_moved``, so the fresh destination index is already available.

        :param backing_object: Event draft emitted by the tree model.
        :return: None.
        """
        if isinstance(backing_object, DynamicEventDraft):
            self._reveal_event(backing_object, start_editing=False)
        else:
            pass

    def has_runtime_parameters(self) -> bool:
        """Return whether the current dynamic model can receive a new event.

        :return: Whether at least one event or mode parameter is available.
        """
        return len(self.parameters) > 0

    def _selected_backing_object(self) -> object | None:
        """Return the transaction object represented by the selected row.

        :return: Selected group, event, diagnostic node or ``None``.
        """
        return self.tree_model.backing_object(self.tree_view.currentIndex())

    @QtCore.Slot()
    def update_actions(self) -> None:
        """Refresh action availability and contextual guidance.

        Add and remove remain clickable without a selection so their handlers
        can explain what the user must select through a non-blocking toast.

        :return: None.
        """
        selected: object | None = self._selected_backing_object()
        self.add_event_action.setEnabled(True)
        self.remove_action.setEnabled(True)

        mode_parameters: list[Var] = self._get_switch_mode_parameters()
        can_open_switch_sequence: bool = (
            self.mode == DynamicSimulationMode.EMT
            and isinstance(selected, DynamicEventGroupDraft)
            and len(mode_parameters) > 0
        )
        self.switch_sequence_action.setEnabled(can_open_switch_sequence)
        if self.has_runtime_parameters():
            self.add_event_action.setToolTip(self.tr("Add an event to the selected event group"))
        else:
            self.add_event_action.setToolTip(
                self.tr("No events can be added because the dynamic model has no event parameters.")
            )

    @QtCore.Slot(bool)
    def add_event(self, _checked: bool = False) -> None:
        """Add one event under the selected group.

        :param _checked: QAction checked state supplied by Qt.
        :return: None.
        """
        selected: object | None = self._selected_backing_object()
        if isinstance(selected, DynamicEventGroupDraft):
            created_event: DynamicEventDraft | None = self.session.add_event(
                device=self.device,
                mode=self.mode,
                group=selected,
                parameters=self.parameters,
                mode_parameter_uids=self.mode_parameter_uids,
            )
            if created_event is None:
                QtWidgets.QMessageBox.information(
                    self,
                    self.tr("Empty dynamic model"),
                    self.tr("Events cannot be added because this dynamic model has no event parameters."),
                )
            else:
                # ``add_event`` rebuilds the page model synchronously through
                # the shared session. Resolve the fresh index, expand its group
                # and start parameter editing so the new event is immediately
                # visible even when the branch was previously collapsed.
                self._reveal_event(created_event, start_editing=True)
        else:
            self.toast_manager.show_warning_toast(
                self.tr("Select the event group where you want to add the event.")
            )

    def _reveal_event(self,
                      event: DynamicEventDraft,
                      start_editing: bool) -> None:
        """Expand, select and optionally edit one event after a model rebuild.

        :param event: Event draft that must become visible.
        :param start_editing: Whether to open its Parameter editor immediately.
        :return: None.
        """
        event_index: QtCore.QModelIndex = self.tree_model.index_for_backing_object(event)
        if event_index.isValid():
            parent_index: QtCore.QModelIndex = event_index.parent()
            self.tree_view.expand(parent_index)
            self.tree_view.setCurrentIndex(event_index)
            self.tree_view.scrollTo(event_index)
            if start_editing:
                self.tree_view.edit(event_index)
            else:
                pass
        else:
            pass

    @QtCore.Slot(bool)
    def remove_selection(self, _checked: bool = False) -> None:
        """Remove the selected event or global event group after confirmation.

        :param _checked: QAction checked state supplied by Qt.
        :return: None.
        """
        selected: object | None = self._selected_backing_object()
        if isinstance(selected, DynamicEventDraft):
            self._confirm_remove_event(selected)
        elif isinstance(selected, DynamicEventGroupDraft):
            self._confirm_remove_group(selected)
        else:
            self.toast_manager.show_warning_toast(
                self.tr("Select the event or event group you want to remove.")
            )

    def _confirm_remove_event(self, event: DynamicEventDraft) -> None:
        """Confirm and remove one selected event.

        :param event: Event transaction record selected for removal.
        :return: None.
        """
        if event.parameter is None:
            parameter_name: str = self.tr("Invalid parameter")
        else:
            parameter_name = event.parameter.name
        result: QtWidgets.QMessageBox.StandardButton = QtWidgets.QMessageBox.question(
            self,
            self.tr("Remove event"),
            self.tr("Are you sure you want to remove the event for '{parameter}' at {time:.4f} s?").format(
                parameter=parameter_name,
                time=event.time,
            ),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if result == QtWidgets.QMessageBox.StandardButton.Yes:
            self.session.remove_event(event)
        else:
            pass

    def _confirm_remove_group(self, group: DynamicEventGroupDraft) -> None:
        """Confirm removal of one global group and all its events.

        :param group: Global group transaction record selected for removal.
        :return: None.
        """
        event_count: int = len(self.session.get_group_events(group))
        device_count: int = self.session.count_group_devices(group)
        result: QtWidgets.QMessageBox.StandardButton = QtWidgets.QMessageBox.question(
            self,
            self.tr("Remove events group"),
            self.tr(
                "Are you sure you want to remove group '{group}'? "
                "This will remove {events} events from {devices} devices."
            ).format(group=group.name, events=event_count, devices=device_count),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if result == QtWidgets.QMessageBox.StandardButton.Yes:
            self.session.remove_group(group)
        else:
            pass

    @QtCore.Slot(QtCore.QPoint)
    def show_context_menu(self, position: QtCore.QPoint) -> None:
        """Show actions appropriate for the clicked group or event row.

        :param position: Tree viewport position requested by Qt.
        :return: None.
        """
        index: QtCore.QModelIndex = self.tree_view.indexAt(position)
        if not index.isValid():
            return
        else:
            self.tree_view.setCurrentIndex(index)
        selected: object | None = self.tree_model.backing_object(index)
        menu: QtWidgets.QMenu = QtWidgets.QMenu(self.tree_view)
        rename_action: QtGui.QAction | None = None
        switch_action: QtGui.QAction | None = None
        if isinstance(selected, DynamicEventGroupDraft):
            rename_action = menu.addAction(self.tr("Rename"))
            if self.mode == DynamicSimulationMode.EMT and len(self._get_switch_mode_parameters()) > 0:
                switch_action = menu.addAction(self.tr("Switch Sequence Wizard"))
            else:
                pass
        else:
            pass
        if isinstance(selected, (DynamicEventGroupDraft, DynamicEventDraft)):
            remove_action: QtGui.QAction | None = menu.addAction(self.tr("Remove"))
        else:
            remove_action = None
        chosen_action: QtGui.QAction | None = menu.exec(self.tree_view.viewport().mapToGlobal(position))
        if rename_action is not None and chosen_action is rename_action:
            self.tree_view.edit(index.siblingAtColumn(DynamicEventsTreeModel.COLUMN_PARAMETER))
        elif switch_action is not None and chosen_action is switch_action:
            self.open_switch_sequence()
        elif remove_action is not None and chosen_action is remove_action:
            self.remove_selection()
        else:
            pass

    def _get_switch_mode_parameters(self) -> list[Var]:
        """Return EMT switch-state mode parameters available in this page.

        :return: Ordered switch mode parameter list.
        """
        mode_parameters: list[Var] = list()
        parameter: Var
        for parameter in self.parameters:
            if parameter.uid in self.mode_parameter_uids and parameter.name.startswith("switch_closed_mode_"):
                mode_parameters.append(parameter)
            else:
                pass
        return mode_parameters

    @QtCore.Slot(bool)
    def open_switch_sequence(self, _checked: bool = False) -> None:
        """Create EMT switch events under the selected transaction group.

        :param _checked: QAction checked state supplied by Qt.
        :return: None.
        """
        selected: object | None = self._selected_backing_object()
        mode_parameters: list[Var] = self._get_switch_mode_parameters()
        if not isinstance(selected, DynamicEventGroupDraft) or len(mode_parameters) == 0:
            return
        else:
            proxy_group: EmtEventsGroup = EmtEventsGroup(name=selected.name, active=selected.active)
        dialog: SwitchSequenceDialog = SwitchSequenceDialog(
            mode_parameters=mode_parameters,
            events_groups=list((proxy_group,)),
            parent=self,
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            sequence_data: SwitchSequenceData | None = dialog.get_typed_data()
            if sequence_data is not None:
                last_created_event: DynamicEventDraft | None = None
                sequence_index: int
                for sequence_index in range(min(len(sequence_data.times), len(sequence_data.values))):
                    event: DynamicEventDraft | None = self.session.add_event(
                        device=self.device,
                        mode=self.mode,
                        group=selected,
                        parameters=self.parameters,
                        mode_parameter_uids=self.mode_parameter_uids,
                    )
                    if event is not None:
                        event.parameter = sequence_data.parameter
                        event.time = float(sequence_data.times[sequence_index])
                        event.value = float(sequence_data.values[sequence_index])
                        event.transition_type = DynamicEventTransitionType.Step
                        event.end_time = None
                        event.force_step_alignment = True
                        last_created_event = event
                    else:
                        pass
                self.session.changed.emit()
                if last_created_event is not None:
                    self._reveal_event(last_created_event, start_editing=False)
                else:
                    pass
            else:
                pass
        else:
            pass
