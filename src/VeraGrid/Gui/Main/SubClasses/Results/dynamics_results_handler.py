# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import json
from typing import Dict, List, Sequence, Tuple
import numpy as np
from matplotlib import pyplot as plt
from PySide6 import QtCore, QtGui

from VeraGrid.Gui.Icons.icon_associations import device_type_icons
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DeviceType, StudyResultsType
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGrid.Gui.results_model import ResultsModel


def _build_tree_item(text: str) -> QtGui.QStandardItem:
    """
    Build a non-editable tree item.

    :param text: Text to display in the tree node.
    :return: Configured tree item.
    """
    # Every tree node is marked as read-only because the trees are used as selectors and drop targets.
    item: QtGui.QStandardItem = QtGui.QStandardItem(text)
    item.setEditable(False)
    return item


def _get_device_type_label(device_tpe: DeviceType) -> str:
    """
    Get the label that represents a device type.

    :param device_tpe: Device type enum value.
    :return: User-facing label for the device type node.
    """
    # The enum value is already the canonical label used across the GUI.
    return str(device_tpe.value)


def _get_device_label(device: ALL_DEV_TYPES) -> str:
    """
    Get the label that represents a device instance.

    :param device: Device instance stored in the RMS results tree.
    :return: User-facing label for the device node.
    """
    # Engine devices expose the correct GUI name through their string representation.
    return str(device)


def _get_var_label(variable: Var) -> str:
    """
    Get the label that represents a simulation variable.

    :param variable: RMS variable object.
    :return: User-facing label for the variable node.
    """
    # The symbolic variable name is the exact identifier used by the simulation arrays.
    return variable.name


class DynamicResultSeriesKey:
    """
    Stable identity for one plottable dynamic-result series.
    """

    __slots__ = (
        "_simulation_type",
        "_source_id",
        "_device_type",
        "_device_idtag",
        "_result_path",
        "_variable_index",
        "_component_index",
    )

    def __init__(self,
                 simulation_type: StudyResultsType,
                 source_id: str,
                 device_type: DeviceType,
                 device_idtag: str,
                 result_path: str,
                 variable_index: int,
                 component_index: int) -> None:
        self._simulation_type: StudyResultsType = simulation_type
        self._source_id: str = source_id
        self._device_type: DeviceType = device_type
        self._device_idtag: str = device_idtag
        self._result_path: str = result_path
        self._variable_index: int = variable_index
        self._component_index: int = component_index

    def __hash__(self) -> int:
        return hash((self._simulation_type,
                     self._source_id,
                     self._device_type,
                     self._device_idtag,
                     self._result_path,
                     self._variable_index,
                     self._component_index))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DynamicResultSeriesKey):
            return ((self._simulation_type,
                     self._source_id,
                     self._device_type,
                     self._device_idtag,
                     self._result_path,
                     self._variable_index,
                     self._component_index)
                    == (other._simulation_type,
                        other._source_id,
                        other._device_type,
                        other._device_idtag,
                        other._result_path,
                        other._variable_index,
                        other._component_index))
        else:
            return False

    def to_payload(self) -> str:
        return json.dumps([
            self._simulation_type.value,
            self._source_id,
            self._device_type.value,
            self._device_idtag,
            self._result_path,
            self._variable_index,
            self._component_index,
        ], separators=(",", ":"))

    @classmethod
    def from_payload(cls, payload: str) -> "DynamicResultSeriesKey | None":
        try:
            values = json.loads(payload)
        except json.JSONDecodeError:
            return None

        if isinstance(values, list) and len(values) == 7:
            try:
                return cls(
                    simulation_type=StudyResultsType(values[0]),
                    source_id=str(values[1]),
                    device_type=DeviceType(values[2]),
                    device_idtag=str(values[3]),
                    result_path=str(values[4]),
                    variable_index=int(values[5]),
                    component_index=int(values[6]),
                )
            except (TypeError, ValueError):
                return None
        else:
            return None


class DynamicResultSeries:
    """
    Source-specific dynamic-result series bound to current results arrays.
    """

    __slots__ = (
        "_key",
        "_var",
        "_group_idx",
        "_source_label",
        "_device_label",
        "_variable_label",
    )

    def __init__(self,
                 key: DynamicResultSeriesKey,
                 var: Var,
                 group_idx: int,
                 source_label: str,
                 device_label: str,
                 variable_label: str) -> None:
        self._key: DynamicResultSeriesKey = key
        self._var: Var = var
        self._group_idx: int = group_idx
        self._source_label: str = source_label
        self._device_label: str = device_label
        self._variable_label: str = variable_label

    def get_key(self) -> DynamicResultSeriesKey:
        return self._key

    def get_var(self) -> Var:
        return self._var

    def get_var_uid(self) -> int:
        return self._var.uid

    def get_group_idx(self) -> int:
        return self._group_idx

    def get_source_label(self) -> str:
        return self._source_label

    def get_variable_label(self) -> str:
        return self._variable_label

    def get_tree_leaf_label(self, has_multiple_sources: bool) -> str:
        if has_multiple_sources:
            return self._source_label
        else:
            return self._variable_label

    def get_plot_label(self, has_multiple_sources: bool) -> str:
        if has_multiple_sources:
            return self._device_label + " - " + self._variable_label + " - " + self._source_label
        else:
            return self._variable_label


def _set_item_icon(item: QtGui.QStandardItem, icon_key: str) -> None:
    """
    Set the item icon from the shared device-type icon dictionary.

    :param item: Tree item that should receive the icon.
    :param icon_key: Key used to search in ``device_type_icons``.
    :return: Nothing.
    """
    # The icon mapping is shared with the rest of the GUI so tree categories stay visually consistent.
    icon_path: str | None = device_type_icons.get(icon_key, None)
    if icon_path is not None:
        icon: QtGui.QIcon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(icon_path))
        item.setIcon(icon)
    else:
        pass


class DynamicsPlotGroup:
    """
    Group of variables to be plotted together.
    """

    __slots__ = ("_name", "_vars")

    def __init__(self, name: str):
        """
        Build the plot group.

        :param name: Name shown in the plots tree.
        """
        # The name is the external identifier used by the UI and CRUD operations.
        self._name: str = name

        # The variable list is kept ordered because users expect insertion order to be preserved in the plot tree.
        self._vars: List[DynamicResultSeries | Var] = list()

    def get_name(self) -> str:
        """
        Get the plot-group name.

        :return: Plot-group name.
        """
        return self._name

    def set_name(self, name: str) -> None:
        """
        Set the plot-group name.

        :param name: New group name.
        :return: Nothing.
        """
        self._name = name

    def get_series(self) -> List[DynamicResultSeries | Var]:
        """
        Get the stored plot entries.

        :return: Entries in insertion order.
        """
        return list(self._vars)

    def get_vars(self) -> List[Var]:
        """
        Get the current underlying variables stored in the group.

        :return: Variable list kept for compatibility with older tests and callers.
        """
        variables: List[Var] = list()

        entry: DynamicResultSeries | Var
        for entry in self._vars:
            if isinstance(entry, DynamicResultSeries):
                variables.append(entry.get_var())
            elif isinstance(entry, Var):
                variables.append(entry)
            else:
                pass

        return variables

    def contains_var(self, variable: DynamicResultSeries | Var) -> bool:
        """
        Check whether a series already belongs to the group.

        :param variable: Series to inspect.
        :return: ``True`` when the variable is already present.
        """
        contained: bool = False
        existing_var: DynamicResultSeries | Var
        for existing_var in self._vars:
            if isinstance(existing_var, DynamicResultSeries) and isinstance(variable, DynamicResultSeries):
                if existing_var.get_key() == variable.get_key():
                    contained = True
                else:
                    pass
            elif isinstance(existing_var, Var) and isinstance(variable, Var):
                if existing_var.uid == variable.uid:
                    contained = True
                else:
                    pass
            else:
                pass
        return contained

    def add_var(self, variable: DynamicResultSeries | Var) -> bool:
        """
        Add a variable to the group.

        :param variable: Variable to add.
        :return: ``True`` when the variable was inserted.
        """
        # Duplicate insertions are rejected so drag-and-drop remains idempotent.
        if self.contains_var(variable=variable):
            return False
        else:
            self._vars.append(variable)
            return True

    def remove_var(self, variable: DynamicResultSeries | Var) -> bool:
        """
        Remove a variable from the group.

        :param variable: Variable to remove.
        :return: ``True`` when the variable was present and removed.
        """
        variable_idx: int = -1
        idx: int
        existing_var: DynamicResultSeries | Var
        for idx, existing_var in enumerate(self._vars):
            if isinstance(existing_var, DynamicResultSeries) and isinstance(variable, DynamicResultSeries):
                if existing_var.get_key() == variable.get_key():
                    variable_idx = idx
                else:
                    pass
            elif isinstance(existing_var, Var) and isinstance(variable, Var):
                if existing_var.uid == variable.uid:
                    variable_idx = idx
                else:
                    pass
            else:
                pass

        if variable_idx >= 0:
            del self._vars[variable_idx]
            return True
        else:
            return False


class DynamicsPlotGroups:
    """
    Collection of plot groups with explicit CRUD operations.
    """

    __slots__ = ("_groups",)

    def __init__(self) -> None:
        """
        Build an empty plot-group collection.

        :return: Nothing.
        """
        self._groups: List[DynamicsPlotGroup] = list()

    def get_groups(self) -> List[DynamicsPlotGroup]:
        """
        Get the stored plot groups.

        :return: Copy of the plot-group list.
        """
        return list(self._groups)

    def get_group(self, name: str) -> DynamicsPlotGroup | None:
        """
        Get one plot group by name.

        :param name: Plot-group name.
        :return: Matching plot group or ``None``.
        """
        group: DynamicsPlotGroup
        for group in self._groups:
            if group.get_name() == name:
                return group
            else:
                pass
        return None

    def create_group(self, name: str) -> bool:
        """
        Create a new plot group.

        :param name: Requested group name.
        :return: ``True`` when the group was created.
        """
        clean_name: str = name.strip()
        if clean_name == "":
            return False
        else:
            existing_group: DynamicsPlotGroup | None = self.get_group(name=clean_name)
            if existing_group is None:
                self._groups.append(DynamicsPlotGroup(name=clean_name))
                return True
            else:
                return False

    def delete_group(self, name: str) -> bool:
        """
        Delete a plot group.

        :param name: Group name.
        :return: ``True`` when the group existed and was deleted.
        """
        group_idx: int = -1
        idx: int
        group: DynamicsPlotGroup
        for idx, group in enumerate(self._groups):
            if group.get_name() == name:
                group_idx = idx
            else:
                pass

        if group_idx >= 0:
            del self._groups[group_idx]
            return True
        else:
            return False

    def rename_group(self, old_name: str, new_name: str) -> bool:
        """
        Rename an existing group.

        :param old_name: Current group name.
        :param new_name: Requested group name.
        :return: ``True`` when the rename was applied.
        """
        clean_name: str = new_name.strip()
        if clean_name == "":
            return False
        else:
            target_group: DynamicsPlotGroup | None = self.get_group(name=old_name)
            clashing_group: DynamicsPlotGroup | None = self.get_group(name=clean_name)
            if target_group is not None:
                if clashing_group is None or clean_name == old_name:
                    target_group.set_name(name=clean_name)
                    return True
                else:
                    return False
            else:
                return False


class DynamicsDeviceTreeModel(QtGui.QStandardItemModel):
    """
    Source tree model that exports dragged variables.
    """

    __slots__ = ("_var_role", "_mime_type")

    def __init__(self, var_role: int, mime_type: str):
        """
        Build the source dynamics tree model.

        :param var_role: Qt role that stores the ``Var`` object in leaf nodes.
        :param mime_type: Mime type used during drag-and-drop.
        """
        QtGui.QStandardItemModel.__init__(self)
        self._var_role: int = var_role
        self._mime_type: str = mime_type

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """
        Get the Qt flags for an item.

        :param index: Model index.
        :return: Flags controlling selection and dragging.
        """
        if index.isValid():
            item: QtGui.QStandardItem | None = self.itemFromIndex(index)
            if item is not None:
                item_data: object = item.data(self._var_role)
                if isinstance(item_data, DynamicResultSeries):
                    return (QtCore.Qt.ItemFlag.ItemIsEnabled
                            | QtCore.Qt.ItemFlag.ItemIsSelectable
                            | QtCore.Qt.ItemFlag.ItemIsDragEnabled)
                else:
                    return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
            else:
                return QtCore.Qt.ItemFlag.ItemIsEnabled
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def mimeTypes(self) -> List[str]:
        """
        Get the supported mime types.

        :return: Mime types exported by the model.
        """
        return [self._mime_type]

    def supportedDragActions(self) -> QtCore.Qt.DropAction:
        """
        Get the supported drag actions.

        :return: Copy action.
        """
        return QtCore.Qt.DropAction.CopyAction

    def mimeData(self, indexes: List[QtCore.QModelIndex]) -> QtCore.QMimeData:
        """
        Build mime data from the selected variable item.

        :param indexes: Selected indexes.
        :return: Mime payload containing the dragged series key.
        """
        mime_data: QtCore.QMimeData = QtCore.QMimeData()

        index: QtCore.QModelIndex
        for index in indexes:
            if index.isValid():
                item: QtGui.QStandardItem | None = self.itemFromIndex(index)
                if item is not None:
                    item_data: object = item.data(self._var_role)
                    if isinstance(item_data, DynamicResultSeries):
                        mime_data.setData(self._mime_type,
                                          QtCore.QByteArray(item_data.get_key().to_payload().encode("utf-8")))
                        return mime_data
                    else:
                        pass
                else:
                    pass
            else:
                pass

        return mime_data


class DynamicsPlotsTreeModel(QtGui.QStandardItemModel):
    """
    Target tree model that accepts dropped variables into plot groups.
    """

    __slots__ = ("_handler",)

    def __init__(self, handler: "DynamicsResultsHandler"):
        """
        Build the plots tree model.

        :param handler: Dynamics-results handler that owns the plot-group state.
        """
        QtGui.QStandardItemModel.__init__(self)
        self._handler: DynamicsResultsHandler = handler

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """
        Get the Qt flags for a plots-tree item.

        :param index: Model index.
        :return: Flags controlling selection and drop acceptance.
        """
        if index.isValid():
            item: QtGui.QStandardItem | None = self.itemFromIndex(index)
            if item is not None:
                group_name_data: object = item.data(self._handler.get_group_name_role())
                if isinstance(group_name_data, str):
                    return (QtCore.Qt.ItemFlag.ItemIsEnabled
                            | QtCore.Qt.ItemFlag.ItemIsSelectable
                            | QtCore.Qt.ItemFlag.ItemIsDropEnabled)
                else:
                    return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
            else:
                return QtCore.Qt.ItemFlag.ItemIsEnabled
        else:
            return QtCore.Qt.ItemFlag.ItemIsEnabled

    def mimeTypes(self) -> List[str]:
        """
        Get the supported mime types.

        :return: Mime type accepted by the target model.
        """
        return [self._handler.get_drag_mime_type()]

    def supportedDropActions(self) -> QtCore.Qt.DropAction:
        """
        Get the supported drop actions.

        :return: Copy action.
        """
        return QtCore.Qt.DropAction.CopyAction

    def dropMimeData(self,
                     data: QtCore.QMimeData,
                     action: QtCore.Qt.DropAction,
                     row: int,
                     column: int,
                     parent: QtCore.QModelIndex) -> bool:
        """
        Handle dropping one variable into a plot group.

        :param data: Drag payload.
        :param action: Requested drop action.
        :param row: Drop row.
        :param column: Drop column.
        :param parent: Drop parent index.
        :return: ``True`` when the drop was accepted.
        """
        del row
        del column

        if action == QtCore.Qt.DropAction.IgnoreAction:
            return True
        else:
            if data.hasFormat(self._handler.get_drag_mime_type()):
                payload: bytes = bytes(data.data(self._handler.get_drag_mime_type()))
                payload_text: str = payload.decode("utf-8").strip()
                series_key: DynamicResultSeriesKey | None = DynamicResultSeriesKey.from_payload(payload_text)
                if series_key is not None:
                    group_name: str | None = self._handler.get_group_name_from_drop_index(index=parent)
                    if group_name is not None:
                        return self._handler.add_series_to_group(group_name=group_name, series_key=series_key)
                    else:
                        return False
                else:
                    return False
            else:
                return False


def build_dynamics_tree_model(tree_data: Dict[DeviceType, Dict[ALL_DEV_TYPES, List[Var]]],
                              var_role: int,
                              mime_type: str,
                              series_by_var_uid: Dict[int, List[DynamicResultSeries]],
                              has_multiple_sources: bool) -> DynamicsDeviceTreeModel:
    """
    Build the source tree-view model for RMS/EMT dynamics results.

    :param tree_data: Hierarchical RMS results tree grouped by device type and device.
    :param var_role: Qt item-data role used to store the ``Var`` instance in leaf nodes.
    :param mime_type: Mime type exported when dragging a variable.
    :param series_by_var_uid: Source-specific dynamic series grouped by current variable uid.
    :param has_multiple_sources: ``True`` when multiple result sources must be shown.
    :return: Source tree model ready to be assigned to a QTreeView.
    """
    # The source model owns the full device hierarchy and the drag payload for variable leaves.
    model: DynamicsDeviceTreeModel = DynamicsDeviceTreeModel(var_role=var_role, mime_type=mime_type)
    model.setHorizontalHeaderLabels(["Dynamics results"])

    # The invisible root is Qt's insertion point for first-level tree nodes.
    root_item: QtGui.QStandardItem = model.invisibleRootItem()

    device_tpe: DeviceType
    devices_data: Dict[ALL_DEV_TYPES, List[Var]]
    for device_tpe, devices_data in tree_data.items():
        # The first level groups all devices by their type so the tree remains navigable.
        device_type_item: QtGui.QStandardItem = _build_tree_item(text=_get_device_type_label(device_tpe=device_tpe))
        _set_item_icon(item=device_type_item, icon_key=_get_device_type_label(device_tpe=device_tpe))
        root_item.appendRow(device_type_item)

        device: ALL_DEV_TYPES
        variables: List[Var]
        for device, variables in devices_data.items():
            # The second level groups the variables that belong to one physical device.
            device_item: QtGui.QStandardItem = _build_tree_item(text=_get_device_label(device=device))
            device_type_item.appendRow(device_item)

            variable: Var
            for variable in variables:
                variable_item: QtGui.QStandardItem = _build_tree_item(text=_get_var_label(variable=variable))
                device_item.appendRow(variable_item)

                series_list: List[DynamicResultSeries] = series_by_var_uid.get(variable.uid, list())
                if has_multiple_sources:
                    series: DynamicResultSeries
                    for series in series_list:
                        source_item: QtGui.QStandardItem = _build_tree_item(
                            text=series.get_tree_leaf_label(has_multiple_sources=True)
                        )
                        source_item.setData(series, var_role)
                        variable_item.appendRow(source_item)
                elif len(series_list) > 0:
                    variable_item.setData(series_list[0], var_role)
                else:
                    pass

    return model


class DynamicsResultsHandler:
    """
    Prepare GUI structures from RMS/EMT dynamics results.
    """

    __slots__ = ("results", "tree_data", "tree_model", "proxy_model", "plots_model", "group_idx",
                 "var_role", "group_name_role", "drag_mime_type", "plot_groups", "series_by_key",
                 "series_by_var_uid", "source_labels")

    def __init__(self, results: RmsResults|EmtResults):
        """
        Build the handler from RMS/EMT results data.

        :param results: RMS/EMT results container coming from the simulation engine.
        """
        # The original results object is preserved because later GUI actions need arrays and metadata.
        self.results: RmsResults|EmtResults = results

        # These roles are instance-owned so the handler carries all Qt metadata instead of relying on globals.
        self.var_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 300
        self.group_name_role: int = int(QtCore.Qt.ItemDataRole.UserRole) + 301
        self.drag_mime_type: str = "application/x-veragrid-dynamics-var"

        self.group_idx: Dict[str, int] = dict()
        self.tree_data: Dict[DeviceType, Dict[ALL_DEV_TYPES, List[Var]]] = dict()
        self.tree_model: DynamicsDeviceTreeModel | None = None
        self.series_by_key: Dict[DynamicResultSeriesKey, DynamicResultSeries] = dict()
        self.series_by_var_uid: Dict[int, List[DynamicResultSeries]] = dict()
        self.source_labels: List[str] = list()

        # The proxy model owns the reversible filtering state used by the device tree view.
        self.proxy_model: QtCore.QSortFilterProxyModel = QtCore.QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.tree_model)
        self.proxy_model.setRecursiveFilteringEnabled(True)
        self.proxy_model.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(0)
        if hasattr(self.proxy_model, "setAutoAcceptChildRows"):
            self.proxy_model.setAutoAcceptChildRows(True)
        else:
            pass

        # Plot groups are stored separately from Qt so CRUD operations are explicit and testable.
        self.plot_groups: DynamicsPlotGroups = DynamicsPlotGroups()

        # The plots model is rebuilt from the domain objects after every CRUD operation.
        self.plots_model: DynamicsPlotsTreeModel = DynamicsPlotsTreeModel(handler=self)
        self._refresh_results_state(results=self.results)
        self.rebuild_plots_model()

    def get_group_name_role(self) -> int:
        """
        Get the Qt role used to store plot-group names in the plots tree.

        :return: Item-data role for plot-group names.
        """
        return self.group_name_role

    def get_drag_mime_type(self) -> str:
        """
        Get the mime type used for dynamics-variable drag-and-drop.

        :return: Mime type string.
        """
        return self.drag_mime_type

    def get_view_model(self) -> QtCore.QSortFilterProxyModel:
        """
        Get the proxy model used by the dynamics device tree view.

        :return: Filter proxy model wrapping the source dynamics tree.
        """
        return self.proxy_model

    def get_plots_model(self) -> DynamicsPlotsTreeModel:
        """
        Get the model used by the dynamics plots tree view.

        :return: Plot-groups tree model.
        """
        return self.plots_model

    def set_search_text(self, search_text: str) -> None:
        """
        Update the proxy-model filter with the given search text.

        :param search_text: Text used to filter the device tree nodes.
        :return: Nothing.
        """
        # Escaping the text keeps the search literal and avoids accidental regular-expression semantics.
        escaped_text: str = QtCore.QRegularExpression.escape(search_text.strip())
        regex: QtCore.QRegularExpression = QtCore.QRegularExpression(escaped_text)
        regex.setPatternOptions(QtCore.QRegularExpression.PatternOption.CaseInsensitiveOption)
        self.proxy_model.setFilterRegularExpression(regex)

    def map_to_source(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        """
        Map a view index from the proxy model back to the source device-tree model.

        :param index: Index received from the tree-view signal.
        :return: Source-model index understood by the handler internals.
        """
        return self.proxy_model.mapToSource(index)

    def get_series_from_index(self, index: QtCore.QModelIndex) -> DynamicResultSeries | None:
        """
        Get the source-specific dynamic series associated with a clicked device-tree index.

        :param index: Source-model index coming from the dynamics device tree.
        :return: Series stored in the clicked leaf node, or ``None`` for non-leaf nodes.
        """
        if index.isValid():
            item: QtGui.QStandardItem | None = self.tree_model.itemFromIndex(index)
            if item is not None:
                item_data: object = item.data(self.var_role)
                if isinstance(item_data, DynamicResultSeries):
                    return item_data
                else:
                    return None
            else:
                return None
        else:
            return None

    def get_var_from_index(self, index: QtCore.QModelIndex) -> Var | None:
        """
        Get the current variable associated with a clicked device-tree index.

        :param index: Source-model index coming from the dynamics device tree.
        :return: Current ``Var`` for compatibility with older callers.
        """
        series: DynamicResultSeries | None = self.get_series_from_index(index=index)
        if series is not None:
            return series.get_var()
        else:
            return None

    def get_plot_group_name_from_index(self, index: QtCore.QModelIndex) -> str | None:
        """
        Get the plot-group name represented by a plots-tree index.
        :param index: Index from the plots tree.
        :return: Group name, or ``None`` when the index does not belong to any group.
        """
        if index.isValid():
            item: QtGui.QStandardItem | None = self.plots_model.itemFromIndex(index)
            if item is not None:
                group_name_data: object = item.data(self.group_name_role)
                if isinstance(group_name_data, str):
                    return group_name_data
                else:
                    parent_item: QtGui.QStandardItem | None = item.parent()
                    if parent_item is not None:
                        parent_group_name_data: object = parent_item.data(self.group_name_role)
                        if isinstance(parent_group_name_data, str):
                            return parent_group_name_data
                        else:
                            return None
                    else:
                        return None
            else:
                return None
        else:
            return None

    def get_group_name_from_drop_index(self, index: QtCore.QModelIndex) -> str | None:
        """
        Resolve the plot-group name targeted by a drop operation.

        :param index: Drop target index.
        :return: Group name, or ``None`` when the drop target is invalid.
        """
        return self.get_plot_group_name_from_index(index=index)

    def get_plot_series_from_index(self, index: QtCore.QModelIndex) -> DynamicResultSeries | None:
        """
        Get the series represented by a plots-tree index.

        :param index: Index from the plots tree.
        :return: Series when the index points to a plotted child, otherwise ``None``.
        """
        if index.isValid():
            item: QtGui.QStandardItem | None = self.plots_model.itemFromIndex(index)
            if item is not None:
                item_data: object = item.data(self.var_role)
                if isinstance(item_data, DynamicResultSeries):
                    return item_data
                else:
                    return None
            else:
                return None
        else:
            return None

    def get_plot_var_from_index(self, index: QtCore.QModelIndex) -> Var | None:
        """
        Get the current variable represented by a plots-tree index.

        :param index: Index from the plots tree.
        :return: Current ``Var`` for compatibility with older callers.
        """
        series: DynamicResultSeries | None = self.get_plot_series_from_index(index=index)
        if series is not None:
            return series.get_var()
        else:
            return None

    def rebuild_plots_model(self) -> None:
        """
        Rebuild the plots-tree model from the plot-group domain objects.

        :return: Nothing.
        """
        # The Qt model is treated as a projection of the handler state so every CRUD operation remains explicit.
        self.plots_model.clear()
        self.plots_model.setHorizontalHeaderLabels(["Dynamic plots"])

        root_item: QtGui.QStandardItem = self.plots_model.invisibleRootItem()
        group: DynamicsPlotGroup
        for group in self.plot_groups.get_groups():
            group_item: QtGui.QStandardItem = _build_tree_item(text=group.get_name())
            group_item.setData(group.get_name(), self.group_name_role)
            _set_item_icon(item=group_item, icon_key="Dynamic")
            root_item.appendRow(group_item)

            entry: DynamicResultSeries | Var
            for entry in group.get_series():
                if isinstance(entry, DynamicResultSeries):
                    variable_item: QtGui.QStandardItem = _build_tree_item(
                        text=entry.get_plot_label(has_multiple_sources=self.has_multiple_sources())
                    )
                    variable_item.setData(entry, self.var_role)
                    group_item.appendRow(variable_item)
                elif isinstance(entry, Var):
                    variable_item = _build_tree_item(text=_get_var_label(variable=entry))
                    variable_item.setData(entry, self.var_role)
                    group_item.appendRow(variable_item)
                else:
                    pass

    def _build_next_group_name(self) -> str:
        """
        Build the next default plot-group name.

        :return: New plot-group name that does not clash with existing ones.
        """
        group_number: int = 1
        while self.plot_groups.get_group(name="Plot " + str(group_number)) is not None:
            group_number += 1
        return "Plot " + str(group_number)

    def get_next_group_name(self) -> str:
        """
        Get the next available default plot-group name.

        :return: Suggested group name.
        """
        return self._build_next_group_name()

    def create_plot_group(self, name: str) -> bool:
        """
        Create a plot group and refresh the plots tree.

        :param name: Requested plot-group name.
        :return: ``True`` when the group was created.
        """
        created: bool = self.plot_groups.create_group(name=name)
        if created:
            self.rebuild_plots_model()
            return True
        else:
            return False

    def delete_plot_group(self, group_name: str) -> bool:
        """
        Delete one plot group and refresh the plots tree.

        :param group_name: Plot-group name.
        :return: ``True`` when the group existed and was deleted.
        """
        deleted: bool = self.plot_groups.delete_group(name=group_name)
        if deleted:
            self.rebuild_plots_model()
            return True
        else:
            return False

    def add_var_to_group(self, group_name: str, var_uid: int) -> bool:
        """
        Add one variable to a plot group and refresh the plots tree.

        :param group_name: Target plot-group name.
        :param var_uid: Variable uid kept for compatibility with older callers.
        :return: ``True`` when the variable was inserted.
        """
        series_list: List[DynamicResultSeries] = self.series_by_var_uid.get(var_uid, list())
        if len(series_list) == 1:
            return self.add_series_to_group(group_name=group_name, series_key=series_list[0].get_key())
        else:
            return False

    def add_series_to_group(self, group_name: str, series_key: DynamicResultSeriesKey) -> bool:
        """
        Add one source-specific series to a plot group and refresh the plots tree.

        :param group_name: Target plot-group name.
        :param series_key: Stable identity of the plotted series.
        :return: ``True`` when the series was inserted.
        """
        group: DynamicsPlotGroup | None = self.plot_groups.get_group(name=group_name)
        variable: DynamicResultSeries | None = self.series_by_key.get(series_key, None)
        if group is not None:
            if variable is not None:
                inserted: bool = group.add_var(variable=variable)
                if inserted:
                    self.rebuild_plots_model()
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False

    def remove_var_from_group(self, group_name: str, var_uid: int) -> bool:
        """
        Remove one variable from a plot group and refresh the plots tree.

        :param group_name: Plot-group name.
        :param var_uid: Variable uid.
        :return: ``True`` when the variable was removed.
        """
        series_list: List[DynamicResultSeries] = self.series_by_var_uid.get(var_uid, list())
        if len(series_list) == 1:
            return self.remove_series_from_group(group_name=group_name, series_key=series_list[0].get_key())
        else:
            return False

    def remove_series_from_group(self, group_name: str, series_key: DynamicResultSeriesKey) -> bool:
        """
        Remove one source-specific series from a plot group and refresh the plots tree.

        :param group_name: Plot-group name.
        :param series_key: Stable series identity.
        :return: ``True`` when the series was removed.
        """
        group: DynamicsPlotGroup | None = self.plot_groups.get_group(name=group_name)
        variable: DynamicResultSeries | None = self.series_by_key.get(series_key, None)
        if group is not None:
            if variable is not None:
                removed: bool = group.remove_var(variable=variable)
                if removed:
                    self.rebuild_plots_model()
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False

    def delete_plot_entry_from_index(self, index: QtCore.QModelIndex) -> bool:
        """
        Delete the selected group or variable from the plots tree.

        :param index: Selected plots-tree index.
        :return: ``True`` when something was deleted.
        """
        selected_var: DynamicResultSeries | None = self.get_plot_series_from_index(index=index)
        if selected_var is not None:
            group_name: str | None = self.get_plot_group_name_from_index(index=index)
            if group_name is not None:
                return self.remove_series_from_group(group_name=group_name, series_key=selected_var.get_key())
            else:
                return False
        else:
            group_name = self.get_plot_group_name_from_index(index=index)
            if group_name is not None:
                return self.delete_plot_group(group_name=group_name)
            else:
                return False

    def has_multiple_sources(self) -> bool:
        """
        Check whether the current results object exposes more than one source.

        :return: ``True`` when multiple event-group sources are available.
        """
        return len(self.source_labels) > 1

    def plot_series(self, series: DynamicResultSeries) -> None:
        """
        Plot one source-specific series.

        :param series: Series to plot.
        :return: Nothing.
        """
        figure = plt.figure(figsize=(12, 8))
        axis = figure.add_subplot(111)
        x_values, y_values = self._get_series_plot_data(series=series)
        axis.plot(x_values, y_values, label=series.get_plot_label(has_multiple_sources=self.has_multiple_sources()))
        axis.legend()
        plt.show()

    def plot_var(self, var: Var, group_name: str) -> None:
        """
        Plot one variable for one RMS events group.

        :param var: Variable to plot.
        :param group_name: RMS events group name.
        :return: Nothing.
        """
        gr_idx: int = self.group_idx[group_name]
        self.results.plot_var(var=var, group_idx=gr_idx)

    def plot_group(self, plot_group_name: str, dyn_group_name: str) -> bool:
        """
        Plot all variables stored in one plot group.

        :param plot_group_name: Plot-group name selected by the user.
        :param dyn_group_name: RMS/EMT events group name selected in the combobox.
        :return: ``True`` when the plot group existed and was plotted.
        """
        plot_group: DynamicsPlotGroup | None = self.plot_groups.get_group(name=plot_group_name)
        if plot_group is not None:
            variables: List[DynamicResultSeries | Var] = plot_group.get_series()
            if len(variables) > 0:
                figure = plt.figure(figsize=(12, 8))
                axis = figure.add_subplot(111)

                variable: DynamicResultSeries | Var
                for variable in variables:
                    if isinstance(variable, DynamicResultSeries):
                        x_values, y_values = self._get_series_plot_data(series=variable)
                        label: str = variable.get_plot_label(has_multiple_sources=self.has_multiple_sources())
                    elif isinstance(variable, Var):
                        group_idx: int = self.group_idx[dyn_group_name]
                        x_values = self.results.time_array
                        result_path, values_idx = self._resolve_result_path_and_component_index(variable=variable)
                        if result_path == "values":
                            y_values = self.results.values[:, values_idx, group_idx]
                        elif result_path == "diff_values" and hasattr(self.results, "diff_values"):
                            y_values = self.results.diff_values[:, values_idx, group_idx]
                        else:
                            continue
                        label = variable.name
                    else:
                        continue

                    axis.plot(x_values, y_values, label=label)

                axis.legend()
                axis.set_title(plot_group_name)
                plt.show()
                return True
            else:
                return False
        else:
            return False



    def plot_entry_from_index(self, index: QtCore.QModelIndex, dyn_group_name: str) -> bool:
        """
        Plot the selected plots-tree entry.

        :param index: Selected plots-tree index.
        :param dyn_group_name: Selected RMS/EMT events group name.
        :return: ``True`` when something was plotted.
        """
        selected_var: DynamicResultSeries | None = self.get_plot_series_from_index(index=index)
        if selected_var is not None:
            self.plot_series(series=selected_var)
            return True
        else:
            plot_group_name: str | None = self.get_plot_group_name_from_index(index=index)
            if plot_group_name is not None:
                return self.plot_group(plot_group_name=plot_group_name, dyn_group_name=dyn_group_name)
            else:
                return False


    def get_data_from_plot_index(self, index: QtCore.QModelIndex, dyn_group_name: str) -> ResultsModel | None:
        """

        :param index:
        :param dyn_group_name:
        :return:
        """
        plot_group_name: str | None = self.get_plot_group_name_from_index(index=index)

        if plot_group_name is not None:

            plot_group: DynamicsPlotGroup | None = self.plot_groups.get_group(name=plot_group_name)
            variables: List[DynamicResultSeries | Var] = plot_group.get_series()
            if len(variables) > 0:
                compatible_series: List[DynamicResultSeries] = list()
                variable: DynamicResultSeries | Var
                for variable in variables:
                    if isinstance(variable, DynamicResultSeries):
                        compatible_series.append(variable)
                    else:
                        group_idx: int = self.group_idx[dyn_group_name]
                        series_list: List[DynamicResultSeries] = self.series_by_var_uid.get(variable.uid, list())
                        if len(series_list) == 1 and series_list[0].get_group_idx() == group_idx:
                            compatible_series.append(series_list[0])
                        else:
                            pass

                if len(compatible_series) == 0:
                    return None

                first_time: np.ndarray = np.asarray(self.results.time_array)
                series: DynamicResultSeries
                for series in compatible_series:
                    series_time, _ = self._get_series_plot_data(series=series)
                    if not np.array_equal(np.asarray(series_time), first_time):
                        return None

                data = np.empty((len(first_time), len(compatible_series)), dtype=float)
                columns: List[str] = list()

                for idx, series in enumerate(compatible_series):
                    _, y_values = self._get_series_plot_data(series=series)
                    data[:, idx] = y_values
                    columns.append(series.get_plot_label(has_multiple_sources=self.has_multiple_sources()))

                table = ResultsTable(
                    data=data,
                    index=first_time,
                    columns=np.array(columns, dtype=str),
                    title=plot_group_name,
                    ylabel="",
                    cols_device_type=DeviceType.NoDevice,
                    idx_device_type=DeviceType.NoDevice
                )

                mdl = ResultsModel(table=table)

                return mdl
            else:
                return None
        else:
            return None

    def _get_group_names(self, results: RmsResults | EmtResults) -> Sequence[str]:
        """
        Get the ordered event-group labels for the current results object.
        """
        if type(results) == RmsResults:
            return [str(gr) for gr in results.rms_events_group_names]
        elif type(results) == EmtResults:
            return [str(gr) for gr in results.emt_events_group_names]
        else:
            raise Exception("Unsupported dynamics results type")

    def _build_source_id(self, results: RmsResults | EmtResults, group_idx: int) -> str:
        """
        Build a stable source id for one event-group position.
        """
        return str(results.study_results_type.value) + ":" + str(group_idx)

    def _resolve_result_path_and_component_index(self, variable: Var) -> tuple[str, int]:
        """
        Resolve which result array and column index stores one variable.
        """
        if type(self.results) == RmsResults:
            return "values", self.results.uid2idx[variable.uid]
        elif type(self.results) == EmtResults:
            if variable.uid in self.results.uid2idx_vars:
                return "values", self.results.uid2idx_vars[variable.uid]
            elif variable.uid in self.results.uid2idx_diff:
                return "diff_values", self.results.uid2idx_diff[variable.uid]
            else:
                raise ValueError("Variable with uid " + str(variable.uid) + " not found in EMT results.")
        else:
            raise Exception("Unsupported dynamics results type")

    def _refresh_results_state(self, results: RmsResults | EmtResults) -> None:
        """
        Rebuild source lookup maps and the device tree for the given results object.
        """
        self.results = results
        self.source_labels = list(self._get_group_names(results=self.results))
        self.group_idx = self._build_group_idx(results=self.results)
        self.tree_data = self.results.get_devices_dict_tree()
        self.series_by_key = dict()
        self.series_by_var_uid = dict()

        device_tpe: DeviceType
        devices_data: Dict[ALL_DEV_TYPES, List[Var]]
        for device_tpe, devices_data in self.tree_data.items():
            device: ALL_DEV_TYPES
            variables: List[Var]
            for device, variables in devices_data.items():
                device_label: str = _get_device_label(device=device)
                device_idtag: str = str(device.idtag)

                variable_index: int
                variable: Var
                for variable_index, variable in enumerate(variables):
                    result_path, component_index = self._resolve_result_path_and_component_index(variable=variable)
                    scoped_result_path: str = result_path + ":" + variable.name

                    group_idx: int
                    source_label: str
                    for group_idx, source_label in enumerate(self.source_labels):
                        key: DynamicResultSeriesKey = DynamicResultSeriesKey(
                            simulation_type=self.results.study_results_type,
                            source_id=self._build_source_id(results=self.results, group_idx=group_idx),
                            device_type=device_tpe,
                            device_idtag=device_idtag,
                            result_path=scoped_result_path,
                            variable_index=variable_index,
                            component_index=component_index,
                        )
                        series: DynamicResultSeries = DynamicResultSeries(
                            key=key,
                            var=variable,
                            group_idx=group_idx,
                            source_label=source_label,
                            device_label=device_label,
                            variable_label=_get_var_label(variable=variable),
                        )
                        self.series_by_key[key] = series
                        self.series_by_var_uid.setdefault(variable.uid, list()).append(series)

        self.tree_model = build_dynamics_tree_model(
            tree_data=self.tree_data,
            var_role=self.var_role,
            mime_type=self.drag_mime_type,
            series_by_var_uid=self.series_by_var_uid,
            has_multiple_sources=self.has_multiple_sources(),
        )
        self.proxy_model.setSourceModel(self.tree_model)

    def _get_series_plot_data(self, series: DynamicResultSeries) -> tuple[np.ndarray, np.ndarray]:
        """
        Get x/y arrays for one source-specific plotted series.
        """
        x_values = np.asarray(self.results.time_array)
        key: DynamicResultSeriesKey = series.get_key()
        group_idx: int = series.get_group_idx()

        result_path_prefix: str = key._result_path.split(":", 1)[0]

        if result_path_prefix == "values":
            y_values = np.asarray(self.results.values[:, key._component_index, group_idx])
        elif result_path_prefix == "diff_values" and hasattr(self.results, "diff_values"):
            y_values = np.asarray(self.results.diff_values[:, key._component_index, group_idx])
        else:
            raise ValueError("Unsupported dynamic result path: " + key._result_path)

        return x_values, y_values

    def _build_group_idx(self, results: RmsResults | EmtResults) -> Dict[str, int]:
        """
        Build the event-group-name to index mapping for the given results object.
        """
        return {group_name: i for i, group_name in enumerate(self._get_group_names(results=results))}

    # def _snapshot_plot_groups(self) -> List[tuple[str, List[int]]]:
    #     """
    #     Snapshot current plot groups using variable uid references.
    #
    #     :return: List of tuples (group_name, [var_uid_1, var_uid_2, ...]).
    #     """
    #     snapshot: List[tuple[str, List[int]]] = list()
    #
    #     group: DynamicsPlotGroup
    #     for group in self.plot_groups.get_groups():
    #         var_uids: List[int] = [var.uid for var in group.get_vars()]
    #         snapshot.append((group.get_name(), var_uids))
    #
    #     return snapshot

    def _snapshot_plot_groups(self) -> List[tuple[str, List[DynamicResultSeriesKey | tuple[str, str, str]]]]:
        """
        Snapshot current plot groups using stable series keys.

        Legacy ``Var`` entries are converted best-effort to the old visible signature.

        :return: List of tuples ``(group_name, [series_key_or_legacy_signature, ...])``.
        """
        variable_signature_by_uid: Dict[int, tuple[str, str, str]] = self._build_uid_to_variable_signature_index()
        snapshot: List[tuple[str, List[DynamicResultSeriesKey | tuple[str, str, str]]]] = list()

        group: DynamicsPlotGroup
        for group in self.plot_groups.get_groups():
            var_signatures: List[DynamicResultSeriesKey | tuple[str, str, str]] = list()

            variable: DynamicResultSeries | Var
            for variable in group.get_series():
                if isinstance(variable, DynamicResultSeries):
                    var_signatures.append(variable.get_key())
                elif isinstance(variable, Var):
                    var_signature: tuple[str, str, str] | None = variable_signature_by_uid.get(variable.uid, None)
                    if var_signature is not None:
                        var_signatures.append(var_signature)
                    else:
                        pass
                else:
                    pass

            snapshot.append((group.get_name(), var_signatures))

        return snapshot

    # def _restore_plot_groups_from_snapshot(self, snapshot: List[tuple[str, List[int]]]) -> None:
    #     """
    #     Restore plot groups from a uid snapshot using the current results object.
    #
    #     :param snapshot: Plot-group snapshot created with _snapshot_plot_groups().
    #     :return: Nothing.
    #     """
    #     restored_plot_groups = DynamicsPlotGroups()
    #
    #     group_name: str
    #     var_uids: List[int]
    #     for group_name, var_uids in snapshot:
    #         created: bool = restored_plot_groups.create_group(name=group_name)
    #         if created:
    #             group: DynamicsPlotGroup | None = restored_plot_groups.get_group(name=group_name)
    #             if group is not None:
    #                 var_uid: int
    #                 for var_uid in var_uids:
    #                     variable: Var | None = self.results.get_var(uid=var_uid)
    #                     if variable is not None:
    #                         group.add_var(variable=variable)
    #
    #     self.plot_groups = restored_plot_groups

    def _restore_plot_groups_from_snapshot(self,
                                           snapshot: List[tuple[str, List[DynamicResultSeriesKey | tuple[str, str, str]]]]) -> None:
        """
        Restore plot groups from exact dynamic-result keys.

        Legacy visible signatures are restored only when they map to exactly one
        current source-specific series.

        :param snapshot: Plot-group snapshot created with ``_snapshot_plot_groups()``.
        :return: Nothing.
        """
        restored_plot_groups: DynamicsPlotGroups = DynamicsPlotGroups()
        variable_by_signature: Dict[tuple[str, str, str], List[DynamicResultSeries]] = (
            self._build_variable_signature_to_series_index()
        )

        group_name: str
        var_signatures: List[DynamicResultSeriesKey | tuple[str, str, str]]
        for group_name, var_signatures in snapshot:
            created: bool = restored_plot_groups.create_group(name=group_name)

            if created:
                group: DynamicsPlotGroup | None = restored_plot_groups.get_group(name=group_name)

                if group is not None:
                    var_signature: DynamicResultSeriesKey | tuple[str, str, str]
                    for var_signature in var_signatures:
                        variable: DynamicResultSeries | None
                        if isinstance(var_signature, DynamicResultSeriesKey):
                            variable = self.series_by_key.get(var_signature, None)
                        else:
                            candidate_series: List[DynamicResultSeries] = variable_by_signature.get(var_signature, list())
                            if len(candidate_series) == 1:
                                variable = candidate_series[0]
                            else:
                                variable = None

                        if variable is not None:
                            group.add_var(variable=variable)
                        else:
                            pass
                else:
                    pass
            else:
                pass

        self.plot_groups = restored_plot_groups

    def _build_uid_to_variable_signature_index(self) -> Dict[int, tuple[str, str, str]]:
        """
        Build a lookup table from current variable uid to stable device-variable signature.

        The result tree already stores the relationship between devices and variables.
        This method converts that tree into a lookup that can translate the existing
        plot variables from ``Var.uid`` to ``(device.idtag, device.name, variable.name)``.

        :return: Dictionary mapping ``Var.uid`` to ``(device_idtag, device_name, variable_name)``.
        """
        # The dictionary is used only as a lookup table. This is acceptable here
        # because the algorithm needs direct access from uid to the stable signature.
        signature_by_uid: Dict[int, tuple[str, str, str]] = dict()

        device_tpe: DeviceType
        devices_data: Dict[ALL_DEV_TYPES, List[Var]]
        for device_tpe, devices_data in self.tree_data.items():
            # The device type is not part of the requested matching rule.
            # It is still iterated because the result tree is grouped by device type.
            del device_tpe

            device: ALL_DEV_TYPES
            variables: List[Var]
            for device, variables in devices_data.items():
                # The results tree already exposes device idtag and device name.
                # Storing both keeps the match stable across repeated simulations and
                # also prevents restoring a plot if the device is later renamed.
                device_idtag: str = str(device.idtag)
                device_name: str = str(device.name)

                variable: Var
                for variable in variables:
                    # The stable plot identity requires the same device idtag, the
                    # same device name, and the same variable name in the new results.
                    signature_by_uid[variable.uid] = (device_idtag, device_name, variable.name)

        return signature_by_uid

    def _build_variable_signature_to_series_index(self) -> Dict[tuple[str, str, str], List[DynamicResultSeries]]:
        """
        Build a lookup table from legacy visible signature to current source-specific series.

        :return: Dictionary mapping ``(device_idtag, device_name, variable_name)`` to candidate series.
        """
        variable_by_signature: Dict[tuple[str, str, str], List[DynamicResultSeries]] = dict()

        device_tpe: DeviceType
        devices_data: Dict[ALL_DEV_TYPES, List[Var]]
        for device_tpe, devices_data in self.tree_data.items():
            del device_tpe

            device: ALL_DEV_TYPES
            variables: List[Var]
            for device, variables in devices_data.items():
                device_idtag: str = str(device.idtag)
                device_name: str = str(device.name)

                variable: Var
                for variable in variables:
                    signature: tuple[str, str, str] = (device_idtag, device_name, variable.name)
                    current_entries: List[DynamicResultSeries] = variable_by_signature.get(signature, list())
                    current_entries.extend(self.series_by_var_uid.get(variable.uid, list()))
                    variable_by_signature[signature] = current_entries

        return variable_by_signature

    def update_results(self, results: RmsResults | EmtResults) -> None:
        """
        Replace the underlying results object while preserving dynamic-plot definitions.

        This method assumes that vars, diff_vars and params are compatible with the
        current handler. Compatibility must be checked before calling it.

        :param results: New RMS/EMT results for the same study type.
        :return: Nothing.
        """
        plot_groups_snapshot = self._snapshot_plot_groups()
        self._refresh_results_state(results=results)
        self._restore_plot_groups_from_snapshot(snapshot=plot_groups_snapshot)
        self.rebuild_plots_model()

    def _var_signature(self, var: Var) -> str:
        """
        Build a stable comparison signature for one variable.

        :param var: Variable object.
        :return: Tuple used to compare variables across result objects.
        """
        return str(var.name)

    def _vars_signature(self, variables: List[Var]) -> List[str]:
        """
        Build comparison signatures for a list of variables.

        :param variables: Variable list.
        :return: List of signatures preserving order.
        """
        return [self._var_signature(var=v) for v in variables]
