# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from PySide6.QtCore import Qt, QPoint, QModelIndex
from PySide6 import QtWidgets

from VeraGrid.Gui.Main.SubClasses.Model.time_events import TimeEventsMain
from VeraGrid.Gui.scenario_tree_model import ScenarioTreeModel
from VeraGrid.Gui import gui_functions as gf
from VeraGrid.Gui.messages import yes_no_question, warning_msg
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.multiverse import MultiVerse, ScenarioNode


class ScenariosMain(TimeEventsMain):
    """
    Scenarios Main
    """

    def __init__(self, parent=None):
        """
        Initialize the Scenarios Main window.

        :param parent: Parent widget
        """

        # create main window
        TimeEventsMain.__init__(self, parent)

        self.scenario_tree_model: ScenarioTreeModel = ScenarioTreeModel(multiverse=self.multiverse)

        self.ui.multiverseTreeView.setModel(self.scenario_tree_model)

        # Disable editing on double-click, only allow editing via the rename menu option
        self.ui.multiverseTreeView.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        # Set context menu policy to CustomContextMenu
        self.ui.multiverseTreeView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Connect context menu signal
        self.ui.multiverseTreeView.customContextMenuRequested.connect(self.show_scenario_tree_context_menu)

        # Connect selection change signal
        self.ui.multiverseTreeView.selectionModel().selectionChanged.connect(self.on_scenario_selection_changed)

        # Connect double-click signal to apply scenario
        self.ui.multiverseTreeView.doubleClicked.connect(self.on_scenario_double_clicked)

        # Show the initially active scenario (root) in the label
        self.ui.activeScenarioLabel.setText(f"Current: {self.multiverse.current_model.name}")

    # ------------------------------------------------------------------
    # Property override: rebuilds MultiVerse and resets the scenario tree
    # whenever a new grid is loaded, replacing the old root entirely.
    # ------------------------------------------------------------------
    @property
    def circuit(self) -> MultiCircuit:
        return self.multiverse.current_model

    @circuit.setter
    def circuit(self, val: MultiCircuit) -> None:
        # Rebuild the entire MultiVerse so the root node's data matches the new grid
        self.multiverse = MultiVerse(current_model=val)

        if hasattr(self, 'scenario_tree_model'):
            self.scenario_tree_model._multiverse = self.multiverse
            self.scenario_tree_model.refresh()
            self.ui.activeScenarioLabel.setText(f"Current: {val.name}")

    def get_selected_scenario_index(self) -> QModelIndex | None:
        """
        Get the currently selected QModelIndex from the tree view.

        :return: QModelIndex if a node is selected, None otherwise
        """
        selection_model = self.ui.multiverseTreeView.selectionModel()
        if selection_model is None:
            return None

        selected_indexes = selection_model.selectedIndexes()
        if len(selected_indexes) > 0:
            return selected_indexes[0]
        else:
            return None

    def get_selected_scenario_node(self) -> ScenarioNode | None:
        """
        Get the currently selected ScenarioNode from the tree view.

        :return: ScenarioNode if a node is selected, None otherwise
        """
        index: QModelIndex | None = self.get_selected_scenario_index()
        if index is not None:
            return self.scenario_tree_model.get_node(index)
        else:
            return None

    def prompt_scenario_name(self, title: str = "Scenario Name", default_name: str = "New Scenario") -> str | None:
        """
        Prompt the user to enter a scenario name using a dialog.

        :param title: Dialog title
        :param default_name: Default name to display in the input field
        :return: Entered name if accepted, None if cancelled
        """
        text: str = ""
        ok: bool = False

        text, ok = QtWidgets.QInputDialog.getText(
            self,
            title,
            "Enter scenario name:",
            QtWidgets.QLineEdit.EchoMode.Normal,
            default_name
        )

        if ok:
            if text.strip() != "":
                return text.strip()
            else:
                warning_msg("Scenario name cannot be empty", title)
                return None
        else:
            return None

    def on_scenario_selection_changed(self) -> None:
        """
        Handle scenario selection changes in the tree view.
        The active scenario label is not changed here — it only reflects the activated scenario.
        """
        pass

    def on_scenario_double_clicked(self, index: QModelIndex) -> None:
        """
        Handle double-click on a scenario node.
        Commits any unsaved edits on the current scenario, then composes and activates
        the selected scenario via the delta chain.

        :param index: The QModelIndex of the double-clicked item
        """
        if not index.isValid():
            return

        node: ScenarioNode | None = self.scenario_tree_model.get_node(index)

        if node is None:
            return

        if node is self.multiverse.current_node:
            self.show_warning_toast(f"'{node.data.name}' is already the active scenario")
            return

        circuit: MultiCircuit = self.multiverse.activate_scenario(node.node_id)

        # Refresh counts: commit_current() may have updated the previous node's delta
        self.scenario_tree_model.refresh_data()

        # Update the UI label
        self.ui.activeScenarioLabel.setText(f"Current: {circuit.name}")

        # Update other UI elements that depend on the circuit
        self.update_date_dependent_combos()
        self.view_objects_data()

        self.show_info_toast(f"Applied scenario '{circuit.name}'")

    def show_scenario_tree_context_menu(self, pos: QPoint) -> None:
        """
        Display context menu for scenario tree operations.

        :param pos: Relative click position
        """
        context_menu: QtWidgets.QMenu = QtWidgets.QMenu(parent=self.ui.multiverseTreeView)

        # Get the selected index to determine which actions to enable
        selected_index: QModelIndex | None = self.get_selected_scenario_index()
        has_selection: bool = selected_index is not None and selected_index.isValid()

        # Add root scenario - always available
        # gf.add_menu_entry(
        #     menu=context_menu,
        #     text="Add root scenario",
        #     icon_path=":/Icons/icons/plus.png",
        #     function_ptr=self.add_root_scenario
        # )

        # Add child scenario - only available if a node is selected
        if has_selection:
            gf.add_menu_entry(
                menu=context_menu,
                text="Add child scenario",
                icon_path=":/Icons/icons/plus.png",
                function_ptr=self.add_child_scenario
            )

            # Separator
            context_menu.addSeparator()

            # Rename scenario - only available if a node is selected
            gf.add_menu_entry(
                menu=context_menu,
                text="Rename scenario",
                icon_path=":/Icons/icons/edit.png",
                function_ptr=self.rename_scenario
            )

            # Set as the current scenario - only available if a node is selected
            gf.add_menu_entry(
                menu=context_menu,
                text="Set as current scenario",
                icon_path=":/Icons/icons/schematic.png",
                function_ptr=self.set_as_current_scenario
            )

            # Separator before delete
            context_menu.addSeparator()

            # Remove scenario - only available if a node is selected
            gf.add_menu_entry(
                menu=context_menu,
                text="Remove scenario",
                icon_path=":/Icons/icons/minus.png",
                function_ptr=self.remove_scenario
            )

            # Convert the global position to the local position of the tree view
            mapped_pos: QPoint = self.ui.multiverseTreeView.viewport().mapToGlobal(pos)
            context_menu.exec(mapped_pos)
        else:
            self.show_warning_toast("Select a scenario...")

    # def add_root_scenario(self) -> None:
    #     """
    #     Add a new root scenario to the multiverse.
    #     Prompts the user for a scenario name and creates a new MultiCircuit.
    #     """
    #     scenario_name: str | None = self.prompt_scenario_name(
    #         title="Add Root Scenario",
    #         default_name=f"Scenario {self.multiverse.roots_number() + 1}"
    #     )
    #
    #     if scenario_name is not None:
    #         # Create a new MultiCircuit as a copy of the current model
    #         new_circuit: MultiCircuit = self.circuit.copy()
    #         new_circuit.name = scenario_name
    #
    #         # Add the root node through the model
    #         node: ScenarioNode = self.scenario_tree_model.append_root(data=new_circuit)
    #
    #         self.show_info_toast(f"Root scenario '{scenario_name}' added")
    #     else:
    #         # User cancelled the operation
    #         pass

    def add_child_scenario(self) -> None:
        """
        Add a child scenario to the selected scenario node.
        The child starts as a copy of the parent's composed circuit (delta chain applied).
        """
        parent_index: QModelIndex | None = self.get_selected_scenario_index()

        if parent_index is None or not parent_index.isValid():
            warning_msg("Please select a parent scenario first", "Add Child Scenario")
            return

        parent_node: ScenarioNode | None = self.scenario_tree_model.get_node(parent_index)

        if parent_node is None:
            warning_msg("Invalid parent scenario selected", "Add Child Scenario")
            return

        # Count existing children for default naming
        child_count: int = parent_node.child_count()
        scenario_name: str | None = self.prompt_scenario_name(
            title="Add Child Scenario",
            default_name=f"{parent_node.data.name} - Child {child_count + 1}"
        )

        if scenario_name is not None:
            # Non-root nodes store a delta, not a full circuit.
            # A brand-new child starts with an empty delta (no changes from parent yet).
            initial_delta: MultiCircuit = MultiCircuit(name=scenario_name)

            # Add the child node through the model
            node: ScenarioNode = self.scenario_tree_model.append_child(
                parent_index=parent_index,
                data=initial_delta
            )

            # Activate the new child immediately
            circuit: MultiCircuit = self.multiverse.activate_scenario(node.node_id)
            self.scenario_tree_model.refresh_data()
            self.ui.activeScenarioLabel.setText(f"Current: {circuit.name}")
            self.update_date_dependent_combos()
            self.view_objects_data()

            # Expand the parent node to show the new child
            self.ui.multiverseTreeView.expand(parent_index)

            self.show_info_toast(f"Child scenario '{scenario_name}' added and activated")
        else:
            # User cancelled the operation
            pass

    def remove_scenario(self) -> None:
        """
        Remove the selected scenario node and its subtree.
        Asks for confirmation before removing.
        """
        selected_index: QModelIndex | None = self.get_selected_scenario_index()

        if selected_index is None or not selected_index.isValid():
            warning_msg("Please select a scenario to remove", "Remove Scenario")
            return

        node: ScenarioNode | None = self.scenario_tree_model.get_node(selected_index)

        if node is None:
            warning_msg("Invalid scenario selected", "Remove Scenario")
            return

        circuit: MultiCircuit = node.data
        child_count: int = node.child_count()

        # Build confirmation message
        message: str = f"Are you sure you want to remove scenario '{circuit.name}'?"
        if child_count > 0:
            message += f"\n\nThis will also remove {child_count} child scenario(s)."

        ok: bool = yes_no_question(message, "Remove Scenario")

        if ok:
            # Remove the node through the model
            success: bool = self.scenario_tree_model.remove_node(selected_index)

            if success:
                self.show_info_toast(f"Scenario '{circuit.name}' removed")
            else:
                warning_msg("Failed to remove scenario", "Remove Scenario")
        else:
            # User cancelled the operation
            pass

    def rename_scenario(self) -> None:
        """
        Rename the selected scenario node.
        Opens the tree view's inline editor for the selected item.
        """
        selected_index: QModelIndex | None = self.get_selected_scenario_index()

        if selected_index is None or not selected_index.isValid():
            warning_msg("Please select a scenario to rename", "Rename Scenario")
            return

        # Use the tree view's built-in editing capability
        self.ui.multiverseTreeView.edit(selected_index)

    def set_as_current_scenario(self) -> None:
        """
        Set the selected scenario as the current working scenario.
        Commits any unsaved edits on the current scenario first, then activates the selected one.
        """
        selected_index: QModelIndex | None = self.get_selected_scenario_index()

        if selected_index is None or not selected_index.isValid():
            warning_msg("Please select a scenario to set as current", "Set Current Scenario")
            return

        node: ScenarioNode | None = self.scenario_tree_model.get_node(selected_index)

        if node is None:
            warning_msg("Invalid scenario selected", "Set Current Scenario")
            return

        if node is self.multiverse.current_node:
            self.show_warning_toast(f"'{node.data.name}' is already the active scenario")
            return

        circuit: MultiCircuit = self.multiverse.activate_scenario(node.node_id)

        # Refresh counts: commit_current() may have updated the previous node's delta
        self.scenario_tree_model.refresh_data()

        # Update the UI label
        self.ui.activeScenarioLabel.setText(f"Current: {circuit.name}")

        # Update other UI elements that depend on the circuit
        self.update_date_dependent_combos()
        self.view_objects_data()

        self.show_info_toast(f"Current scenario set to '{circuit.name}'")