from __future__ import annotations

import sys

from PySide6 import QtCore, QtWidgets

import VeraGridEngine.api as vge
from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_editor import DynamicEventEditor
from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_editor_support import collect_block_runtime_event_parameters
from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_models import DynamicEventDraft
from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_models import DynamicEventGroupDraft
from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_tree import DynamicEventsPage
from VeraGrid.Session.dynamic_editor_entries import DynamicEditorEntry
from VeraGrid.Session.dynamic_editor_entries import build_dynamic_editor_entry
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.enumerations import DynamicEventTransitionType, DynamicSimulationMode


def get_qt_application() -> QtWidgets.QApplication:
    """Return the shared Qt application used by dynamic-events GUI tests.

    :return: Existing or newly created Qt application.
    """
    application: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if application is None:
        return QtWidgets.QApplication(sys.argv)
    else:
        return application


def build_dynamic_target(
        mode: DynamicSimulationMode,
        empty_model: bool = False,
) -> tuple[vge.MultiCircuit, vge.Load, Var, RmsEventsGroup | EmtEventsGroup]:
    """Build one dynamic-capable load and a mode-specific event group.

    :param mode: RMS or EMT model assigned to the load.
    :param empty_model: Whether the assigned block has no event parameters.
    :return: Circuit, load, symbolic parameter and event group.
    """
    circuit: vge.MultiCircuit = vge.MultiCircuit(name="Dynamic events test")
    bus: vge.Bus = vge.Bus(name="Bus", Vnom=10.0)
    circuit.add_bus(bus)
    load: vge.Load = vge.Load(name="Load")
    circuit.add_load(bus=bus, api_obj=load)
    parameter: Var = VarFactory().add_var("event_parameter")
    if empty_model:
        model: Block = Block()
    else:
        event_values: dict[Var, Const] = dict()
        event_values[parameter] = Const(0.0)
        model = Block(event_dict=event_values)

    if mode == DynamicSimulationMode.RMS:
        group: RmsEventsGroup | EmtEventsGroup = RmsEventsGroup(name="RMS group")
        circuit.add_rms_events_group(group)
        load.rms_model = model
    else:
        group = EmtEventsGroup(name="EMT group")
        circuit.add_emt_events_group(group)
        load.emt_model = model
    return circuit, load, parameter, group


def get_dynamic_entry(device: vge.Load, circuit: vge.MultiCircuit) -> DynamicEditorEntry:
    """Resolve the dynamic-editor entry for one test load.

    :param device: Dynamic-capable load.
    :param circuit: Circuit containing the load.
    :return: Resolved dynamic entry.
    """
    entry: DynamicEditorEntry | None = build_dynamic_editor_entry(device, circuit)
    assert entry is not None
    return entry


def test_selected_device_opens_requested_page_with_tree_collapsed() -> None:
    """A unique selected device must open directly in the requested mode.

    :return: None.
    """
    get_qt_application()
    circuit, load, _parameter, _group = build_dynamic_target(DynamicSimulationMode.RMS)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
        initial_device=load,
    )

    assert len(dialog.pages) == 1
    assert dialog.pages[0].entry.api_object is load
    assert dialog.pages[0].mode == DynamicSimulationMode.RMS
    assert dialog.ui.treeFrame.isHidden()
    dialog.close()


def test_no_selected_device_opens_general_tree() -> None:
    """No selected device must leave the general device tree visible.

    :return: None.
    """
    get_qt_application()
    circuit, _load, _parameter, _group = build_dynamic_target(DynamicSimulationMode.EMT)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.EMT,
    )

    assert len(dialog.pages) == 0
    assert not dialog.ui.treeFrame.isHidden()
    dialog.close()


def test_empty_model_page_keeps_existing_events_visible_and_disables_add() -> None:
    """An empty model page must remain useful for inspecting stale events.

    :return: None.
    """
    get_qt_application()
    circuit, load, parameter, group = build_dynamic_target(
        DynamicSimulationMode.RMS,
        empty_model=True,
    )
    assert isinstance(group, RmsEventsGroup)
    existing_event: vge.RmsEvent = vge.RmsEvent(
        device=load,
        parameter=parameter,
        time=1.0,
        value=2.0,
        group=group,
    )
    circuit.add_rms_event(existing_event)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
        initial_device=load,
    )
    page: DynamicEventsPage = dialog.pages[0]
    group_index: QtCore.QModelIndex = page.tree_model.index(0, 0)

    assert not page.empty_model_message.isHidden()
    assert page.tree_model.rowCount(group_index) == 1
    assert not page.add_event_button.isEnabled()
    dialog.close()


def test_empty_model_message_is_page_specific_and_uses_block_empty_state() -> None:
    """The centered empty-state message must not leak into a non-empty mode tab.

    :return: None.
    """
    get_qt_application()
    circuit, load, _parameter, _group = build_dynamic_target(
        DynamicSimulationMode.RMS,
        empty_model=True,
    )
    emt_group: EmtEventsGroup = EmtEventsGroup(name="EMT group")
    circuit.add_emt_events_group(emt_group)
    load.emt_model = Block(name="Non-empty EMT model without event parameters")
    entry: DynamicEditorEntry = get_dynamic_entry(load, circuit)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
        initial_device=load,
    )
    rms_page: DynamicEventsPage = dialog.pages[0]
    opened_emt_page: DynamicEventsPage | None = dialog.open_entry(entry, DynamicSimulationMode.EMT)
    assert opened_emt_page is not None

    assert not rms_page.empty_model_message.isHidden()
    assert opened_emt_page.empty_model_message.isHidden()
    assert not opened_emt_page.add_event_button.isEnabled()
    dialog.close()


def test_add_event_expands_group_selects_row_and_starts_editing() -> None:
    """Adding an event must reveal it even when its group was collapsed.

    :return: None.
    """
    get_qt_application()
    circuit, load, _parameter, _group = build_dynamic_target(DynamicSimulationMode.RMS)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
        initial_device=load,
    )
    page: DynamicEventsPage = dialog.pages[0]
    group_index: QtCore.QModelIndex = page.tree_model.index(0, 0)
    page.tree_view.collapse(group_index)
    page.tree_view.setCurrentIndex(group_index)
    page.add_event()
    current_index: QtCore.QModelIndex = page.tree_view.currentIndex()
    current_backing: object | None = page.tree_model.backing_object(current_index)

    assert page.tree_view.isExpanded(current_index.parent())
    assert isinstance(current_backing, DynamicEventDraft)
    dialog.close()


def test_page_filters_events_by_device_but_displays_every_group() -> None:
    """Each page must show only its device events under all mode groups.

    :return: None.
    """
    get_qt_application()
    circuit, first_load, parameter, group = build_dynamic_target(DynamicSimulationMode.EMT)
    assert isinstance(group, EmtEventsGroup)
    second_bus: vge.Bus = vge.Bus(name="Second bus", Vnom=10.0)
    circuit.add_bus(second_bus)
    second_load: vge.Load = vge.Load(name="Second load")
    circuit.add_load(bus=second_bus, api_obj=second_load)
    second_load.emt_model = first_load.emt_model
    circuit.add_emt_event(vge.EmtEvent(device=first_load, parameter=parameter, time=1.0, value=1.0, group=group))
    circuit.add_emt_event(vge.EmtEvent(device=second_load, parameter=parameter, time=2.0, value=2.0, group=group))
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        initial_device=first_load,
    )
    page: DynamicEventsPage = dialog.pages[0]
    group_index: QtCore.QModelIndex = page.tree_model.index(0, 0)

    assert page.tree_model.rowCount(group_index) == 1
    event_index: QtCore.QModelIndex = page.tree_model.index(0, 0, group_index)
    event_draft: object | None = page.tree_model.backing_object(event_index)
    assert isinstance(event_draft, DynamicEventDraft)
    assert event_draft.device is first_load
    dialog.close()


def test_dragging_event_to_another_group_moves_draft_and_save_persists_it() -> None:
    """Dropping an event on a group must move it transactionally and preserve its identity.

    :return: None.
    """
    get_qt_application()
    circuit, load, parameter, source_group = build_dynamic_target(DynamicSimulationMode.RMS)
    assert isinstance(source_group, RmsEventsGroup)
    target_group: RmsEventsGroup = RmsEventsGroup(name="RMS target group", active=False)
    circuit.add_rms_events_group(target_group)
    original_event: vge.RmsEvent = vge.RmsEvent(
        device=load,
        parameter=parameter,
        time=1.0,
        value=2.0,
        group=source_group,
    )
    circuit.add_rms_event(original_event)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
        initial_device=load,
    )
    page: DynamicEventsPage = dialog.pages[0]
    group_drafts: list[DynamicEventGroupDraft] = dialog.session.get_groups(DynamicSimulationMode.RMS)
    source_group_draft: DynamicEventGroupDraft = group_drafts[0]
    target_group_draft: DynamicEventGroupDraft = group_drafts[1]
    event_draft: DynamicEventDraft = dialog.session.get_events_for_device(
        load,
        DynamicSimulationMode.RMS,
    )[0]
    event_index: QtCore.QModelIndex = page.tree_model.index_for_backing_object(event_draft)
    target_parameter_index: QtCore.QModelIndex = page.tree_model.index_for_backing_object(target_group_draft)
    target_index: QtCore.QModelIndex = target_parameter_index.siblingAtColumn(
        page.tree_model.COLUMN_VALUE
    )
    event_mime_data: QtCore.QMimeData = page.tree_model.mimeData(list((event_index,)))

    event_flags: QtCore.Qt.ItemFlag = page.tree_model.flags(event_index)
    target_flags: QtCore.Qt.ItemFlag = page.tree_model.flags(target_index)
    accepted: bool = page.tree_model.dropMimeData(
        data=event_mime_data,
        action=QtCore.Qt.DropAction.CopyAction,
        row=-1,
        column=-1,
        parent=target_index,
    )
    moved_index: QtCore.QModelIndex = page.tree_model.index_for_backing_object(event_draft)

    assert bool(event_flags & QtCore.Qt.ItemFlag.ItemIsDragEnabled)
    assert bool(target_flags & QtCore.Qt.ItemFlag.ItemIsDropEnabled)
    assert accepted
    assert event_draft.group is target_group_draft
    assert page.tree_model.rowCount(page.tree_model.index_for_backing_object(source_group_draft)) == 0
    assert page.tree_model.rowCount(moved_index.parent()) == 1
    assert page.tree_model.backing_object(page.tree_view.currentIndex()) is event_draft
    assert page.tree_view.isExpanded(moved_index.parent())
    assert original_event.group is source_group

    dialog.accept_changes()

    assert circuit.rms_events[0] is original_event
    assert original_event.group is target_group
    dialog.close()


def test_event_drop_rejects_invalid_targets_and_close_discards_valid_move() -> None:
    """Only another same-mode group may receive a drop and Close must roll it back.

    :return: None.
    """
    get_qt_application()
    circuit, load, parameter, source_group = build_dynamic_target(DynamicSimulationMode.EMT)
    assert isinstance(source_group, EmtEventsGroup)
    target_group: EmtEventsGroup = EmtEventsGroup(name="EMT target group")
    circuit.add_emt_events_group(target_group)
    foreign_group: RmsEventsGroup = RmsEventsGroup(name="RMS foreign group")
    circuit.add_rms_events_group(foreign_group)
    original_event: vge.EmtEvent = vge.EmtEvent(
        device=load,
        parameter=parameter,
        time=1.0,
        value=2.0,
        group=source_group,
    )
    circuit.add_emt_event(original_event)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        initial_device=load,
    )
    page: DynamicEventsPage = dialog.pages[0]
    event_draft: DynamicEventDraft = dialog.session.get_events_for_device(
        load,
        DynamicSimulationMode.EMT,
    )[0]
    emt_group_drafts: list[DynamicEventGroupDraft] = dialog.session.get_groups(DynamicSimulationMode.EMT)
    rms_group_draft: DynamicEventGroupDraft = dialog.session.get_groups(DynamicSimulationMode.RMS)[0]
    source_group_draft: DynamicEventGroupDraft = emt_group_drafts[0]
    target_group_draft: DynamicEventGroupDraft = emt_group_drafts[1]
    event_index: QtCore.QModelIndex = page.tree_model.index_for_backing_object(event_draft)
    source_index: QtCore.QModelIndex = page.tree_model.index_for_backing_object(source_group_draft)
    target_index: QtCore.QModelIndex = page.tree_model.index_for_backing_object(target_group_draft)
    event_mime_data: QtCore.QMimeData = page.tree_model.mimeData(list((event_index,)))

    same_group_accepted: bool = page.tree_model.canDropMimeData(
        data=event_mime_data,
        action=QtCore.Qt.DropAction.CopyAction,
        row=-1,
        column=-1,
        parent=source_index,
    )
    event_row_accepted: bool = page.tree_model.canDropMimeData(
        data=event_mime_data,
        action=QtCore.Qt.DropAction.CopyAction,
        row=-1,
        column=-1,
        parent=event_index,
    )
    different_mode_accepted: bool = dialog.session.move_event_to_group(event_draft, rms_group_draft)
    valid_move_accepted: bool = page.tree_model.dropMimeData(
        data=event_mime_data,
        action=QtCore.Qt.DropAction.CopyAction,
        row=-1,
        column=-1,
        parent=target_index,
    )

    assert not same_group_accepted
    assert not event_row_accepted
    assert not different_mode_accepted
    assert valid_move_accepted
    assert event_draft.group is target_group_draft
    assert original_event.group is source_group

    dialog.reject()

    assert original_event.group is source_group


def test_group_active_and_rename_are_transactional() -> None:
    """Group activity must toggle repeatedly and remain transactional.

    :return: None.
    """
    get_qt_application()
    circuit, load, _parameter, group = build_dynamic_target(DynamicSimulationMode.RMS)
    assert isinstance(group, RmsEventsGroup)
    cancelled_dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
        initial_device=load,
    )
    cancelled_group: DynamicEventGroupDraft = cancelled_dialog.session.get_groups(
        DynamicSimulationMode.RMS
    )[0]
    cancelled_dialog.session.rename_group(cancelled_group, "Cancelled name")
    cancelled_group_index: QtCore.QModelIndex = cancelled_dialog.pages[0].tree_model.index(0, 0)
    first_uncheck_accepted: bool = cancelled_dialog.pages[0].tree_model.setData(
        cancelled_group_index,
        QtCore.Qt.CheckState.Unchecked,
        QtCore.Qt.ItemDataRole.CheckStateRole,
    )
    first_check_accepted: bool = cancelled_dialog.pages[0].tree_model.setData(
        cancelled_group_index,
        2,
        QtCore.Qt.ItemDataRole.CheckStateRole,
    )
    second_uncheck_accepted: bool = cancelled_dialog.pages[0].tree_model.setData(
        cancelled_group_index,
        0,
        QtCore.Qt.ItemDataRole.CheckStateRole,
    )
    second_check_accepted: bool = cancelled_dialog.pages[0].tree_model.setData(
        cancelled_group_index,
        QtCore.Qt.CheckState.Checked,
        QtCore.Qt.ItemDataRole.CheckStateRole,
    )
    cancelled_dialog.reject()

    assert first_uncheck_accepted
    assert first_check_accepted
    assert second_uncheck_accepted
    assert second_check_accepted
    assert cancelled_group.active
    assert group.name == "RMS group"
    assert group.active

    saved_dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
        initial_device=load,
    )
    saved_group: DynamicEventGroupDraft = saved_dialog.session.get_groups(DynamicSimulationMode.RMS)[0]
    saved_dialog.session.rename_group(saved_group, "Saved name")
    saved_dialog.session.set_group_active(saved_group, False)
    saved_dialog.accept_changes()

    assert group.name == "Saved name"
    assert not group.active
    assert saved_dialog.result() == QtWidgets.QDialog.DialogCode.Rejected
    assert len(saved_dialog.toast_manager.active_toasts) == 1
    toast_label: QtWidgets.QLabel | None = saved_dialog.toast_manager.active_toasts[0].findChild(
        QtWidgets.QLabel
    )
    assert toast_label is not None
    assert toast_label.text() == "Events saved"
    saved_dialog.close()


def test_group_removal_cascades_events_across_devices_on_save() -> None:
    """Removing a global group must remove all its device events on Save.

    :return: None.
    """
    get_qt_application()
    circuit, load, parameter, group = build_dynamic_target(DynamicSimulationMode.EMT)
    assert isinstance(group, EmtEventsGroup)
    circuit.add_emt_event(vge.EmtEvent(device=load, parameter=parameter, time=1.0, value=1.0, group=group))
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        initial_device=load,
    )
    group_draft: DynamicEventGroupDraft = dialog.session.get_groups(DynamicSimulationMode.EMT)[0]
    dialog.session.remove_group(group_draft)
    dialog.accept_changes()

    assert len(circuit.emt_events_groups) == 0
    assert len(circuit.emt_events) == 0
    dialog.close()


def test_align_step_checkbox_accepts_qt_check_state_enum() -> None:
    """Align Step must consume the enum object emitted by PySide6.

    :return: None.
    """
    get_qt_application()
    circuit, load, _parameter, group = build_dynamic_target(DynamicSimulationMode.EMT)
    assert isinstance(group, EmtEventsGroup)
    mode_parameter: Var = VarFactory().add_var("switch_closed_mode_test")
    mode_values: dict[Var, float] = dict()
    mode_values[mode_parameter] = 1.0
    load.emt_model = Block(mode_dict=mode_values)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        initial_device=load,
    )
    page: DynamicEventsPage = dialog.pages[0]
    group_draft: DynamicEventGroupDraft = dialog.session.get_groups(DynamicSimulationMode.EMT)[0]
    event_draft: DynamicEventDraft | None = dialog.session.add_event(
        device=load,
        mode=DynamicSimulationMode.EMT,
        group=group_draft,
        parameters=page.parameters,
        mode_parameter_uids=page.mode_parameter_uids,
    )
    assert event_draft is not None
    event_index: QtCore.QModelIndex = page.tree_model.index_for_backing_object(event_draft)
    align_index: QtCore.QModelIndex = event_index.siblingAtColumn(page.tree_model.COLUMN_ALIGN_STEP)
    edit_accepted: bool = page.tree_model.setData(
        align_index,
        QtCore.Qt.CheckState.Unchecked,
        QtCore.Qt.ItemDataRole.CheckStateRole,
    )

    assert edit_accepted
    assert not event_draft.force_step_alignment
    dialog.close()


def test_tabs_are_unique_per_device_and_mode() -> None:
    """Repeated opens must focus one tab while RMS and EMT remain separate.

    :return: None.
    """
    get_qt_application()
    circuit, load, _parameter, _group = build_dynamic_target(DynamicSimulationMode.RMS)
    emt_group: EmtEventsGroup = EmtEventsGroup(name="EMT group")
    circuit.add_emt_events_group(emt_group)
    load.emt_model = Block()
    entry: DynamicEditorEntry = get_dynamic_entry(load, circuit)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    first_page: DynamicEventsPage | None = dialog.open_entry(entry, DynamicSimulationMode.RMS)
    repeated_page: DynamicEventsPage | None = dialog.open_entry(entry, DynamicSimulationMode.RMS)
    emt_page: DynamicEventsPage | None = dialog.open_entry(entry, DynamicSimulationMode.EMT)

    assert first_page is repeated_page
    assert emt_page is not None
    assert len(dialog.pages) == 2
    assert first_page.switch_sequence_button.isHidden()
    assert not emt_page.switch_sequence_button.isHidden()
    dialog.close()


def test_save_button_and_event_controls_use_new_workspace_contract() -> None:
    """The workspace must expose icon-only Save, Close and Results-style controls.

    :return: None.
    """
    get_qt_application()
    circuit, load, _parameter, _group = build_dynamic_target(DynamicSimulationMode.RMS)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
        initial_device=load,
    )
    save_button: QtWidgets.QPushButton | None = dialog.ui.dialogButtonBox.button(
        QtWidgets.QDialogButtonBox.StandardButton.Ok
    )
    close_button: QtWidgets.QPushButton | None = dialog.ui.dialogButtonBox.button(
        QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )
    page: DynamicEventsPage = dialog.pages[0]

    assert save_button is not None
    assert save_button.text() == ""
    assert save_button.toolTip() == "Save"
    assert not save_button.icon().isNull()
    assert save_button.sizePolicy().horizontalPolicy() == QtWidgets.QSizePolicy.Policy.Fixed
    assert save_button.sizePolicy().verticalPolicy() == QtWidgets.QSizePolicy.Policy.Fixed
    assert close_button is not None
    assert close_button.text() == "Close"
    assert isinstance(page.add_event_button, QtWidgets.QPushButton)
    assert isinstance(page.remove_button, QtWidgets.QPushButton)
    assert page.add_event_button.toolTip() != ""
    assert page.remove_button.toolTip() != ""
    dialog.close()


def test_draft_validation_rejects_overlapping_events() -> None:
    """Prospective validation must reject overlapping target intervals.

    :return: None.
    """
    get_qt_application()
    circuit, load, _parameter, _group = build_dynamic_target(DynamicSimulationMode.RMS)
    dialog: DynamicEventEditor = DynamicEventEditor(
        circuit=circuit,
        preferred_mode=DynamicSimulationMode.RMS,
        initial_device=load,
    )
    group_draft: DynamicEventGroupDraft = dialog.session.get_groups(DynamicSimulationMode.RMS)[0]
    first_event: DynamicEventDraft | None = dialog.session.add_event(
        device=load,
        mode=DynamicSimulationMode.RMS,
        group=group_draft,
        parameters=dialog.pages[0].parameters,
        mode_parameter_uids=set(),
    )
    second_event: DynamicEventDraft | None = dialog.session.add_event(
        device=load,
        mode=DynamicSimulationMode.RMS,
        group=group_draft,
        parameters=dialog.pages[0].parameters,
        mode_parameter_uids=set(),
    )
    assert first_event is not None
    assert second_event is not None
    first_event.time = 1.0
    second_event.time = 1.0
    first_event.transition_type = DynamicEventTransitionType.Step
    second_event.transition_type = DynamicEventTransitionType.Step

    validation_error: str | None = dialog.session.validate()
    assert validation_error is not None
    assert "overlap" in validation_error.lower()
    dialog.close()


def test_collect_block_runtime_event_parameters_includes_child_modes() -> None:
    """Parameter discovery must include discrete modes in child blocks.

    :return: None.
    """
    mode_parameter: Var = VarFactory().add_var("switch_closed_mode_child")
    mode_values: dict[Var, float] = dict()
    mode_values[mode_parameter] = 0.0
    child_block: Block = Block(mode_dict=mode_values)
    root_block: Block = Block(children=list((child_block,)))
    parameters: list[Var]
    mode_uids: set[int]
    parameters, mode_uids = collect_block_runtime_event_parameters(root_block)

    assert parameters == list((mode_parameter,))
    assert mode_uids == set((mode_parameter.uid,))
