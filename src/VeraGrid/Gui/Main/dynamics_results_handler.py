# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Dict, List

from PySide6 import QtCore, QtGui

from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DeviceType


DYNAMICS_VAR_ROLE: int = int(QtCore.Qt.ItemDataRole.UserRole) + 300


def _build_tree_item(text: str) -> QtGui.QStandardItem:
    """
    Build a non-editable tree item.

    :param text: Text to display in the tree node.
    :return: Configured tree item.
    """
    # Every tree node is marked as read-only because the tree is used only as a selector.
    item: QtGui.QStandardItem = QtGui.QStandardItem(text)
    item.setEditable(False)
    return item


def _get_device_type_label(device_tpe: DeviceType) -> str:
    """
    Get the label that represents a device type.

    :param device_tpe: Device type enum value.
    :return: User-facing label for the device type node.
    """
    # The enum value is the stable label already shown in the rest of the application.
    return str(device_tpe.value)


def _get_device_label(device: ALL_DEV_TYPES) -> str:
    """
    Get the label that represents a device instance.

    :param device: Device instance stored in the RMS results tree.
    :return: User-facing label for the device node.
    """
    # Device objects already expose their GUI name through their string representation.
    return str(device)


def _get_var_label(variable: Var) -> str:
    """
    Get the label that represents a simulation variable.

    :param variable: RMS variable object.
    :return: User-facing label for the variable node.
    """
    # The symbolic variable name is the exact identifier used by the simulation results.
    return variable.name


def _append_variables(parent_item: QtGui.QStandardItem, variables: List[Var]) -> None:
    """
    Append variable nodes under a device node.

    :param parent_item: Parent device item.
    :param variables: Variables associated with the device.
    :return: Nothing.
    """
    variable: Var
    for variable in variables:
        # Variable nodes are leaf nodes and carry the actual Var instance for direct retrieval on click.
        variable_item: QtGui.QStandardItem = _build_tree_item(text=_get_var_label(variable=variable))
        variable_item.setData(variable, DYNAMICS_VAR_ROLE)
        parent_item.appendRow(variable_item)


def _append_devices(parent_item: QtGui.QStandardItem,
                    devices_data: Dict[ALL_DEV_TYPES, List[Var]]) -> None:
    """
    Append device nodes under a device-type node.

    :param parent_item: Parent device-type item.
    :param devices_data: Mapping from device instance to its variables.
    :return: Nothing.
    """
    device: ALL_DEV_TYPES
    variables: List[Var]
    for device, variables in devices_data.items():
        # The device node groups the variables that belong to the same physical element.
        device_item: QtGui.QStandardItem = _build_tree_item(text=_get_device_label(device=device))
        parent_item.appendRow(device_item)
        _append_variables(parent_item=device_item, variables=variables)


def build_dynamics_tree_model(
        tree_data: Dict[DeviceType, Dict[ALL_DEV_TYPES, List[Var]]]) -> QtGui.QStandardItemModel:
    """
    Build the tree-view model for RMS dynamics results.

    :param tree_data: Hierarchical RMS results tree grouped by device type and device.
    :return: Tree model ready to be assigned to a QTreeView.
    """
    # The model owns the hierarchical structure that the Qt tree view displays.
    model: QtGui.QStandardItemModel = QtGui.QStandardItemModel()
    model.setHorizontalHeaderLabels(["Dynamics results"])

    # The invisible root is Qt's insertion point for first-level tree nodes.
    root_item: QtGui.QStandardItem = model.invisibleRootItem()

    device_tpe: DeviceType
    devices_data: Dict[ALL_DEV_TYPES, List[Var]]
    for device_tpe, devices_data in tree_data.items():
        # The first level groups all devices by their type so the tree remains navigable.
        device_type_item: QtGui.QStandardItem = _build_tree_item(text=_get_device_type_label(device_tpe=device_tpe))
        root_item.appendRow(device_type_item)
        _append_devices(parent_item=device_type_item, devices_data=devices_data)

    return model


class DynamicsResultsHandler:
    """
    Prepare GUI structures from RMS dynamics results.
    """

    __slots__ = ("results", "tree_data", "tree_model", "group_idx")

    def __init__(self, results: RmsResults):
        """
        Build the handler from RMS results data.

        :param results: RMS results container coming from the simulation engine.
        """
        # The original results object is preserved because later GUI actions may need array access and metadata.
        self.results: RmsResults = results

        self.group_idx = {gr: i for i, gr in enumerate(self.results.rms_events_group_names)}

        # The hierarchical dictionary is the canonical source used to build the tree.
        self.tree_data: Dict[DeviceType, Dict[ALL_DEV_TYPES, List[Var]]] = self.results.get_devices_dict_tree()

        # The tree model is created once and then reused by the view and the click lookup logic.
        self.tree_model: QtGui.QStandardItemModel = build_dynamics_tree_model(tree_data=self.tree_data)

    def get_tree_model(self) -> QtGui.QStandardItemModel:
        """
        Get the tree-view model built from the RMS results tree.

        :return: Tree model ready to be attached to the dynamics tree view.
        """
        # The model instance is reused because the handler owns a fixed snapshot of the results tree.
        return self.tree_model

    def get_var_from_index(self, index: QtCore.QModelIndex) -> Var | None:
        """
        Get the RMS variable associated with a clicked tree index.

        :param index: Qt model index coming from the tree-view click signal.
        :return: Variable stored in the clicked leaf node, or ``None`` for non-variable nodes.
        """
        # Invalid indices do not identify any tree node, so they explicitly produce no variable.
        if index.isValid():
            item: QtGui.QStandardItem | None = self.tree_model.itemFromIndex(index)
            if item is not None:
                item_data: object = item.data(DYNAMICS_VAR_ROLE)
                if isinstance(item_data, Var):
                    return item_data
                else:
                    return None
            else:
                return None
        else:
            return None

    def get_var(self, tree_path: List[str]) -> Var | None:
        """
        Get the RMS variable associated with a tree path.

        :param tree_path: Tree path in the form ``[device_type, device, variable]``.
        :return: Matching variable object, or ``None`` when the path does not point to a variable.
        """
        # Only variable leaves have the full three-level path in the current tree structure.
        if len(tree_path) == 3:
            device_type_label: str = tree_path[0]
            device_label: str = tree_path[1]
            variable_label: str = tree_path[2]

            device_tpe: DeviceType
            devices_data: Dict[ALL_DEV_TYPES, List[Var]]
            for device_tpe, devices_data in self.tree_data.items():
                if _get_device_type_label(device_tpe=device_tpe) == device_type_label:
                    device: ALL_DEV_TYPES
                    variables: List[Var]
                    for device, variables in devices_data.items():
                        if _get_device_label(device=device) == device_label:
                            variable: Var
                            for variable in variables:
                                if _get_var_label(variable=variable) == variable_label:
                                    return variable
                                else:
                                    pass
                            return None
                        else:
                            pass
                    return None
                else:
                    pass

            return None
        else:
            return None

    def plot_var(self, var: Var, group_name: str):
        """
        Plots the given variable for a specified group.

        This function retrieves the group index based on the provided group name
        and uses it to plot the given variable. The operation is performed using
        stored results associated with the instance.

        :param var: The variable to be plotted.
        :type var: Var
        :param group_name: The name of the group for which the variable should be
            plotted.
        :type group_name: str
        """
        gr_idx = self.group_idx[group_name]

        self.results.plot_var(var=var, group_idx=gr_idx)
