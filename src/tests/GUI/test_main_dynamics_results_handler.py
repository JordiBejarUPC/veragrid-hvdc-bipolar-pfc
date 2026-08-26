from typing import Dict, List, Tuple

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

import VeraGrid.Gui.Main.SubClasses.Model.diagrams as diagrams_module
from VeraGrid.Gui.Main.SubClasses.Results.dynamics_results_handler import (
    DynamicResultSeriesKey,
    DynamicPlotCandidate,
    DynamicDeviceEntryCollection,
    DynamicsDeviceTreeModel,
    DynamicsPlotGroup,
    DynamicsPlotGroups,
    DynamicsPlotsTreeModel,
    TreeStateNodeKind,
    TreeStateSnapshot,
    _build_tree_state_key,
    _capture_tree_view_state,
    _restore_tree_view_state,
    build_dynamics_tree_model,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import (
    Colormaps,
    DeviceType,
    DynamicPlotEntryKind,
    PlotSimulationType,
    SimulationTypes,
)


class NamedDevice:
    """
    Minimal device-like object used to label dynamics tree rows.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        """
        Build the named device.

        :param name: Name shown by the dynamics tree.
        :return: Nothing.
        """
        self._name: str = name

    def __str__(self) -> str:
        """
        Get the user-facing device name.

        :return: Device name.
        """
        return self._name


class FakeDropHandler:
    """
    Minimal handler used to test ``DynamicsPlotsTreeModel`` drop routing.
    """

    __slots__ = ("_group_name_role", "_drag_mime_type", "_group_name", "_accepted_var_uid", "_calls")

    def __init__(self, group_name_role: int, drag_mime_type: str, group_name: str, accepted_var_uid: int) -> None:
        """
        Build the fake drop handler.

        :param group_name_role: Qt role that stores plot-group names.
        :param drag_mime_type: Mime type accepted by the plots tree.
        :param group_name: Group name returned for drop targets.
        :param accepted_var_uid: Variable UID accepted by ``add_var_to_group``.
        :return: Nothing.
        """
        self._group_name_role: int = group_name_role
        self._drag_mime_type: str = drag_mime_type
        self._group_name: str = group_name
        self._accepted_var_uid: int = accepted_var_uid
        self._calls: List[Tuple[str, int]] = list()

    def get_group_name_role(self) -> int:
        """
        Get the Qt role used by plot-group items.

        :return: Group-name role.
        """
        return self._group_name_role

    def get_drag_mime_type(self) -> str:
        """
        Get the dynamics drag mime type.

        :return: Drag mime type.
        """
        return self._drag_mime_type

    def get_tree_state_role(self) -> int:
        """
        Get the semantic tree-state role used by the fake handler.

        :return: Tree-state role.
        """
        return self._group_name_role + 1

    def get_group_name_from_drop_index(self, index: QtCore.QModelIndex) -> str | None:
        """
        Resolve a group name for a drop index.

        :param index: Drop target index.
        :return: Configured group name or ``None``.
        """
        if index.isValid():
            return self._group_name
        else:
            return None

    def add_var_to_group(self, group_name: str, var_uid: int) -> bool:
        """
        Record accepted drop calls.

        :param group_name: Target plot group.
        :param var_uid: Dropped variable UID.
        :return: ``True`` when the call matches the configured target.
        """
        accepted: bool = group_name == self._group_name and var_uid == self._accepted_var_uid
        if accepted:
            self._calls.append((group_name, var_uid))
            return True
        else:
            return False

    def add_series_to_group(self, group_name: str, series_key: DynamicResultSeriesKey) -> bool:
        """
        Compatibility shim for current drop handler API.

        :param group_name: Target plot group.
        :param series_key: Dropped series key.
        :return: ``True`` when accepted.
        """
        return self.add_var_to_group(group_name=group_name, var_uid=series_key.get_component_index())

    def get_candidate_from_payload(self, payload: str) -> DynamicPlotCandidate | None:
        """
        Parse one drop payload into a candidate object.

        :param payload: Serialized candidate payload.
        :return: Parsed candidate or ``None``.
        """
        if payload == "":
            return None
        else:
            return DynamicPlotCandidate(
                simulation_type=PlotSimulationType.RMS,
                entry_kind=DynamicPlotEntryKind.VARIABLE,
                event_group_idtag="group-id",
                event_group_name="Group 1",
                device_type=DeviceType.GeneratorDevice,
                device_idtag="device-id",
                device_label="Generator 1",
                bus_label="",
                variable_name="omega",
                result_path_kind="values",
                variable_custom_name="Generator 1 - omega",
                var=Var(name="omega", uid=self._accepted_var_uid),
                parameter=None,
            )

    def add_candidate_to_group(self, group_name: str, candidate: DynamicPlotCandidate) -> bool:
        """
        Compatibility shim for current candidate-drop path.

        :param group_name: Target plot group.
        :param candidate: Candidate dropped into the group.
        :return: ``True`` when accepted.
        """
        return self.add_var_to_group(group_name=group_name, var_uid=candidate.get_var().uid)

    def get_calls(self) -> List[Tuple[str, int]]:
        """
        Get recorded accepted drop calls.

        :return: Accepted calls.
        """
        return list(self._calls)


class FakeRmsColouringUi:
    """
    Typed subset of main-window controls read by diagram colouring.
    """

    __slots__ = (
        "branch_width_based_on_flow_checkBox",
        "min_branch_size_spinBox",
        "max_branch_size_spinBox",
        "min_node_size_spinBox",
        "max_node_size_spinBox",
        "palette_comboBox",
    )

    def __init__(self, palette: Colormaps) -> None:
        """
        Build the exact UI state consumed by ``grid_colour_function``.

        :param palette: Colour map selected in the main window.
        :return: Nothing.
        """
        # Real Qt controls preserve the production API without replacing GUI
        # classes or mutating module-level symbols.
        self.branch_width_based_on_flow_checkBox: QtWidgets.QCheckBox = QtWidgets.QCheckBox()
        self.min_branch_size_spinBox: QtWidgets.QSpinBox = QtWidgets.QSpinBox()
        self.max_branch_size_spinBox: QtWidgets.QSpinBox = QtWidgets.QSpinBox()
        self.min_node_size_spinBox: QtWidgets.QSpinBox = QtWidgets.QSpinBox()
        self.max_node_size_spinBox: QtWidgets.QSpinBox = QtWidgets.QSpinBox()
        self.palette_comboBox: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.palette_comboBox.addItem("RMS fallback palette", palette)


class FakeRmsColouringGui:
    """
    Lightweight receiver for direct ``DiagramsMain`` dispatch testing.
    """

    __slots__ = ("ui", "call_count", "call")

    def __init__(self, ui: FakeRmsColouringUi) -> None:
        """
        Build the receiver with no full main-window initialization.

        :param ui: Typed UI controls read by the production dispatcher.
        :return: Nothing.
        """
        self.ui: FakeRmsColouringUi = ui
        self.call_count: int = 0
        self.call: Tuple[int | None, object, Colormaps, bool, int, int, int, int] | None = None

    def default_colouring(self,
                          t_idx: int | None,
                          diagram_widget: object,
                          cmap: Colormaps,
                          use_flow_based_width: bool = False,
                          min_branch_width: int = 2,
                          max_branch_width: int = 5,
                          min_bus_width: int = 2,
                          max_bus_width: int = 5) -> None:
        """
        Record one fallback colouring call without rendering a diagram.

        :param t_idx: Selected dynamic-results time index.
        :param diagram_widget: Diagram object forwarded by the dispatcher.
        :param cmap: Selected colour map.
        :param use_flow_based_width: Whether branch widths follow power flow.
        :param min_branch_width: Minimum rendered branch width.
        :param max_branch_width: Maximum rendered branch width.
        :param min_bus_width: Minimum rendered bus width.
        :param max_bus_width: Maximum rendered bus width.
        :return: Nothing.
        """
        # One scalar count and one fixed-size record make duplicate dispatches
        # visible without growing a collection during the test.
        self.call_count += 1
        self.call = (
            t_idx,
            diagram_widget,
            cmap,
            use_flow_based_width,
            min_branch_width,
            max_branch_width,
            min_bus_width,
            max_bus_width,
        )


def test_rms_dynamic_grid_colouring_routes_to_default_fallback(
        qt_app: object,
        capsys: pytest.CaptureFixture[str]) -> None:
    """
    Check that RMS results route once through the default diagram colouring.

    :param qt_app: Shared Qt application fixture.
    :param capsys: Pytest fixture used to inspect standard output.
    :return: Nothing.
    """
    del qt_app

    palette: Colormaps = Colormaps.Heatmap
    ui: FakeRmsColouringUi = FakeRmsColouringUi(palette=palette)
    ui.branch_width_based_on_flow_checkBox.setChecked(True)
    ui.min_branch_size_spinBox.setValue(3)
    ui.max_branch_size_spinBox.setValue(9)
    ui.min_node_size_spinBox.setValue(4)
    ui.max_node_size_spinBox.setValue(12)
    gui: FakeRmsColouringGui = FakeRmsColouringGui(ui=ui)
    diagram_widget: object = object()
    time_index: int = 7

    # Invoke the production dispatcher directly so the test covers the exact
    # RMS study-name branch without constructing the complete main window.
    diagrams_module.DiagramsMain.grid_colour_function(
        self=gui,
        diagram_widget=diagram_widget,
        current_study=SimulationTypes.RmsDynamic_run.value,
        t_idx=time_index,
        allow_popups=False,
    )

    routed_call: Tuple[int | None, object, Colormaps, bool, int, int, int, int] | None = gui.call
    captured_output: pytest.CaptureResult[str] = capsys.readouterr()
    expected_call: Tuple[int | None, object, Colormaps, bool, int, int, int, int] = (
        time_index,
        diagram_widget,
        palette,
        True,
        3,
        9,
        4,
        12,
    )

    assert gui.call_count == 1
    assert routed_call == expected_call
    assert "Not implemented" not in captured_output.out


def test_dynamics_plot_group_rejects_duplicate_variables_by_uid() -> None:
    """
    Check that plot groups treat variable UID as the identity key.

    :return: Nothing.
    """
    group: DynamicsPlotGroup = DynamicsPlotGroup(name="Plot A")
    first_var: Var = Var(name="x", uid=10)
    duplicate_uid_var: Var = Var(name="x-copy", uid=10)

    assert group.add_var(variable=first_var) is True
    assert group.add_var(variable=duplicate_uid_var) is False
    assert group.contains_var(variable=duplicate_uid_var) is True
    assert group.remove_var(variable=duplicate_uid_var) is True
    assert group.get_vars() == list()


def test_dynamics_plot_groups_create_rename_and_delete_groups() -> None:
    """
    Check plot-group collection CRUD rules used by the dynamic-results GUI.

    :return: Nothing.
    """
    groups: DynamicsPlotGroups = DynamicsPlotGroups()

    assert groups.create_group(name="  Plot A  ") is True
    assert groups.create_group(name="Plot A") is False
    assert groups.create_group(name="") is False
    assert groups.create_group(name="Plot B") is True
    assert groups.rename_group(old_name="Plot A", new_name="Plot B") is False
    assert groups.rename_group(old_name="Plot A", new_name="Plot C") is True
    assert groups.get_group(name="Plot A") is None
    assert groups.get_group(name="Plot C") is not None
    assert groups.delete_group(name="Plot C") is True
    assert groups.delete_group(name="Plot C") is False


def test_dynamics_tree_model_exports_only_variable_leaf_mime_data(qt_app: object) -> None:
    """
    Check that the dynamics source tree marks only variable leaves as draggable.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    var_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 300
    mime_type: str = "application/x-veragrid-test-dynamics-var"
    state_key_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 302
    variable: Var = Var(name="omega", uid=500)
    variables: List[Var] = list()
    variables.append(variable)

    device: NamedDevice = NamedDevice(name="Generator 1")
    devices_data: Dict[NamedDevice, DynamicDeviceEntryCollection] = dict()
    devices_data[device] = DynamicDeviceEntryCollection(variables=variables, parameters=list())

    tree_data: Dict[DeviceType, Dict[NamedDevice, DynamicDeviceEntryCollection]] = dict()
    tree_data[DeviceType.GeneratorDevice] = devices_data
    series_by_var_uid: Dict[int, List[DynamicPlotCandidate]] = dict()
    series_by_var_uid[variable.uid] = list([
        DynamicPlotCandidate(
            simulation_type=PlotSimulationType.RMS,
            entry_kind=DynamicPlotEntryKind.VARIABLE,
            event_group_idtag="group-id",
            event_group_name="Group 1",
            device_type=DeviceType.GeneratorDevice,
            device_idtag="device-id",
            device_label="Generator 1",
            bus_label="",
            variable_name=variable.name,
            result_path_kind="values",
            variable_custom_name="Generator 1 - omega",
            var=variable,
            parameter=None,
        )
    ])

    model: DynamicsDeviceTreeModel = build_dynamics_tree_model(
        tree_data=tree_data,
        var_role=var_role,
        mime_type=mime_type,
        state_key_role=state_key_role,
        series_by_var_uid=series_by_var_uid,
        candidates_by_parameter_key=dict(),
        has_multiple_sources=False,
    )
    device_type_item: QtGui.QStandardItem = model.item(0, 0)
    device_item: QtGui.QStandardItem = device_type_item.child(0, 0)
    variables_section_item: QtGui.QStandardItem = device_item.child(0, 0)
    variable_item: QtGui.QStandardItem = variables_section_item.child(0, 0)

    device_flags: QtCore.Qt.ItemFlag = model.flags(device_item.index())
    variable_flags: QtCore.Qt.ItemFlag = model.flags(variable_item.index())
    mime_data: QtCore.QMimeData = model.mimeData(indexes=[variable_item.index()])
    device_mime_data: QtCore.QMimeData = model.mimeData(indexes=[device_item.index()])

    assert model.horizontalHeaderItem(0).text() == "Dynamics results"
    assert device_type_item.text() == str(DeviceType.GeneratorDevice.value)
    assert device_item.text() == "Generator 1"
    assert variable_item.text() == "omega"
    assert bool(device_flags & QtCore.Qt.ItemFlag.ItemIsDragEnabled) is False
    assert bool(variable_flags & QtCore.Qt.ItemFlag.ItemIsDragEnabled) is True
    assert mime_data.hasFormat(mime_type) is True
    assert bytes(mime_data.data(mime_type)).decode("utf-8") == series_by_var_uid[variable.uid][0].to_payload()
    assert device_mime_data.hasFormat(mime_type) is False


def test_dynamics_plots_tree_accepts_valid_variable_drop(qt_app: object) -> None:
    """
    Check that the dynamics plots tree routes valid drops to the handler.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    group_name_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 301
    mime_type: str = "application/x-veragrid-test-dynamics-var"
    variable_uid: int = 777
    handler: FakeDropHandler = FakeDropHandler(
        group_name_role=group_name_role,
        drag_mime_type=mime_type,
        group_name="Plot 1",
        accepted_var_uid=variable_uid,
    )
    model: DynamicsPlotsTreeModel = DynamicsPlotsTreeModel(handler=handler)
    group_item: QtGui.QStandardItem = QtGui.QStandardItem("Plot 1")
    child_item: QtGui.QStandardItem = QtGui.QStandardItem("omega")
    group_item.setData("Plot 1", group_name_role)
    model.invisibleRootItem().appendRow(group_item)
    group_item.appendRow(child_item)

    candidate: DynamicPlotCandidate = DynamicPlotCandidate(
        simulation_type=PlotSimulationType.RMS,
        entry_kind=DynamicPlotEntryKind.VARIABLE,
        event_group_idtag="group-id",
        event_group_name="Group 1",
        device_type=DeviceType.GeneratorDevice,
        device_idtag="device-id",
        device_label="Generator 1",
        bus_label="",
        variable_name="omega",
        result_path_kind="values",
        variable_custom_name="Generator 1 - omega",
        var=Var(name="omega", uid=variable_uid),
        parameter=None,
    )
    mime_data: QtCore.QMimeData = QtCore.QMimeData()
    mime_data.setData(mime_type, QtCore.QByteArray(candidate.to_payload().encode("utf-8")))

    group_flags: QtCore.Qt.ItemFlag = model.flags(group_item.index())
    child_flags: QtCore.Qt.ItemFlag = model.flags(child_item.index())
    accepted: bool = model.dropMimeData(
        data=mime_data,
        action=QtCore.Qt.DropAction.CopyAction,
        row=-1,
        column=-1,
        parent=group_item.index(),
    )

    assert bool(group_flags & QtCore.Qt.ItemFlag.ItemIsDropEnabled) is True
    assert bool(child_flags & QtCore.Qt.ItemFlag.ItemIsDropEnabled) is False
    assert accepted is True
    assert handler.get_calls() == [("Plot 1", variable_uid)]


def test_tree_state_helpers_restore_expansion_by_semantic_key(qt_app: object) -> None:
    """
    Check that semantic tree-state restoration survives a model rebuild.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    state_key_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 302
    model: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
    view: QtWidgets.QTreeView = QtWidgets.QTreeView()
    root_item: QtGui.QStandardItem = model.invisibleRootItem()

    group_item: QtGui.QStandardItem = QtGui.QStandardItem("Plot 1")
    group_key: str = _build_tree_state_key(node_kind=TreeStateNodeKind.PLOT_GROUP, parts=["Plot 1"])
    group_item.setData(group_key, state_key_role)
    root_item.appendRow(group_item)

    entry_item: QtGui.QStandardItem = QtGui.QStandardItem("omega")
    entry_key: str = _build_tree_state_key(node_kind=TreeStateNodeKind.PLOT_ENTRY,
                                           parts=["Plot 1", "entry-1"])
    entry_item.setData(entry_key, state_key_role)
    group_item.appendRow(entry_item)

    view.setModel(model)
    view.setExpanded(group_item.index(), True)
    view.setCurrentIndex(entry_item.index())

    snapshot: TreeStateSnapshot = _capture_tree_view_state(view=view, model=model, key_role=state_key_role)

    rebuilt_model: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
    rebuilt_root_item: QtGui.QStandardItem = rebuilt_model.invisibleRootItem()
    rebuilt_group_item: QtGui.QStandardItem = QtGui.QStandardItem("Plot 1")
    rebuilt_group_item.setData(group_key, state_key_role)
    rebuilt_root_item.appendRow(rebuilt_group_item)
    rebuilt_entry_item: QtGui.QStandardItem = QtGui.QStandardItem("omega")
    rebuilt_entry_item.setData(entry_key, state_key_role)
    rebuilt_group_item.appendRow(rebuilt_entry_item)

    view.setModel(rebuilt_model)
    _restore_tree_view_state(view=view, model=rebuilt_model, key_role=state_key_role, snapshot=snapshot)

    assert view.isExpanded(rebuilt_group_item.index()) is True
    assert view.currentIndex() == rebuilt_entry_item.index()
