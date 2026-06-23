from __future__ import annotations

import sys

from PySide6 import QtWidgets

from VeraGrid.Gui.DynamicModelEditor.dyn_editor_multiwindow_engine import build_dynamic_editor_entry
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_workspace_window import DynamicEditorWorkspaceWindow
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_workspace_window import get_open_dynamic_editor_workspaces
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_workspace_window import reset_dynamic_editor_workspaces_for_tests
from VeraGridEngine.enumerations import DynamicSimulationMode

import VeraGridEngine.api as gce


def _get_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return QtWidgets.QApplication(sys.argv)
    return app


def _build_load_entry():
    circuit = gce.MultiCircuit(Sbase=100, fbase=50.0)
    bus = gce.Bus(name="Bus 1", Vnom=10.0)
    circuit.add_bus(bus)
    load = gce.Load()
    circuit.add_load(bus=bus, api_obj=load)
    entry = build_dynamic_editor_entry(load, circuit)
    assert entry is not None
    return circuit, load, entry


def test_workspace_reuses_existing_tab_and_remembers_last_mode() -> None:
    _get_app()
    reset_dynamic_editor_workspaces_for_tests()
    circuit, load, _entry = _build_load_entry()
    workspace = DynamicEditorWorkspaceWindow()

    rms_page = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    assert rms_page is not None
    assert workspace.ui.editorTabs.count() == 1

    same_page = workspace.open_dynamic_editor_for(load, circuit)
    assert same_page is rms_page
    assert workspace.ui.editorTabs.count() == 1

    emt_page = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        target_workspace=workspace,
    )
    assert emt_page is not None
    assert emt_page is not rms_page
    assert workspace.ui.editorTabs.count() == 2

    workspace.note_page_activated(emt_page)
    reopened = workspace.open_dynamic_editor_for(load, circuit)
    assert reopened is emt_page

    reset_dynamic_editor_workspaces_for_tests()


def test_tree_is_searchable_and_double_click_opens_rms() -> None:
    _get_app()
    circuit, load, entry = _build_load_entry()
    workspace = DynamicEditorWorkspaceWindow()

    workspace.open_dynamic_editor_for(load, circuit, preferred_mode=DynamicSimulationMode.RMS)
    proxy_model = workspace.ui.treeView.model()
    assert proxy_model is not None

    parent_index = proxy_model.index(0, 0)
    device_index = proxy_model.index(0, 0, parent_index)
    assert device_index.isValid()

    modes = workspace._get_tree_entry_modes(device_index)
    assert DynamicSimulationMode.RMS in modes
    assert DynamicSimulationMode.EMT in modes

    workspace.ui.searchInTreeLineEdit.setText(entry.display_name[:2].lower())
    filtered_index = workspace.ui.treeView.currentIndex()
    assert filtered_index.isValid()
    assert workspace._entry_from_tree_index(filtered_index) is not None

    workspace._on_tree_double_clicked(filtered_index)
    assert workspace.current_page() is not None
    assert workspace.get_current_block_editor() is not None

    reset_dynamic_editor_workspaces_for_tests()


def test_workspace_detaches_and_reattaches_tabs_between_windows() -> None:
    _get_app()
    reset_dynamic_editor_workspaces_for_tests()
    circuit, load, _entry = _build_load_entry()
    workspace = DynamicEditorWorkspaceWindow()

    rms_page = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    assert workspace.current_page() is rms_page
    emt_page = workspace.open_dynamic_editor_for(
        load,
        circuit,
        preferred_mode=DynamicSimulationMode.EMT,
        target_workspace=workspace,
    )

    emt_index = workspace.index_of_page(emt_page)
    workspace._on_tab_drag_started(emt_index)
    workspace._on_tab_detach_requested(workspace.pos())

    assert len(get_open_dynamic_editor_workspaces()) == 2
    detached_workspace = workspace.workspace_for_page(emt_page)
    assert detached_workspace is not None
    assert detached_workspace is not workspace
    assert workspace.ui.editorTabs.count() == 1
    assert detached_workspace.ui.editorTabs.count() == 1

    detached_workspace._on_tab_drag_started(detached_workspace.index_of_page(emt_page))
    workspace._on_tab_reattach_requested(workspace.pos(), -1)

    assert workspace.workspace_for_page(emt_page) is workspace
    assert workspace.ui.editorTabs.count() == 2

    reset_dynamic_editor_workspaces_for_tests()
