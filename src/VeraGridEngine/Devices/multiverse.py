# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import json
from typing import List, Dict, Any, Tuple, TYPE_CHECKING
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import SimulationTypes

if TYPE_CHECKING:
    from VeraGridEngine.Simulations.types import DRIVER_OBJECTS


class ScenarioNode:
    __slots__ = (
        "node_id",
        "circuit",
        "parent",
        "children",
        "drivers"
    )

    def __init__(
            self,
            node_id: int,
            data: MultiCircuit,
            parent: ScenarioNode | None = None,
            children: list[ScenarioNode] | None = None
    ) -> None:
        """
        Initializes a ScenarioNode with a unique identifier and its associated circuit data.

        The meaning of *data* depends on the node's position in the tree:

        - **Root node** (``parent is None``): *data* holds the full authoritative
          ``MultiCircuit``.  User edits are applied directly to this object.
        - **Non-root node**: *data* holds the **delta** — a ``MultiCircuit`` produced
          by ``differentiate_circuits()`` that captures only the changes relative to
          the parent's composed circuit.  The full circuit for this node is always
          reconstructed on demand via ``MultiVerse.checkout()`` and kept in
          ``MultiVerse._current_model`` while this node is active.

        :param node_id: A unique identifier for the tree node.
        :param data: Full circuit (root) or delta circuit (non-root).
        :param parent: Parent node, or ``None`` for root nodes.
        """
        self.node_id: int = node_id
        self.circuit: MultiCircuit = data
        self.parent: ScenarioNode | None = parent
        self.children: list[ScenarioNode] = children if children is not None else list()

        self.drivers: Dict[SimulationTypes, DRIVER_OBJECTS] = dict()

    def append_child(self, child: ScenarioNode) -> None:
        """

        :param child:
        :return:
        """
        child.parent = self
        self.children.append(child)

    def insert_child(self, position: int, child: ScenarioNode) -> None:
        """

        :param position:
        :param child:
        :return:
        """
        child.parent = self
        self.children.insert(position, child)

    def remove_child(self, child: ScenarioNode) -> None:
        """

        :param child:
        :return:
        """
        self.children.remove(child)
        child.parent = None

    def remove_child_at(self, position: int) -> ScenarioNode:
        """

        :param position:
        :return:
        """
        child: ScenarioNode = self.children.pop(position)
        child.parent = None
        return child

    def child(self, row: int) -> ScenarioNode:
        """

        :param row:
        :return:
        """
        return self.children[row]

    def child_count(self) -> int:
        """

        :return:
        """
        return len(self.children)

    def row(self) -> int:
        if self.parent is None:
            return 0
        return self.parent.children.index(self)


class MultiVerse:
    __slots__ = (
        "_root_nodes",
        "_nodes_by_id",
        "_next_id",
        "_base_model",
        "_current_model",
        "_current_node",
    )

    def __init__(self, current_model: MultiCircuit | None = None) -> None:
        """
        Initializes an instance of the class with the specified model and necessary
        attributes for processing scenario nodes and model comparison.

        Automatically creates a root scenario node from the current_model.
        If the current_model has an empty name, it is set to "Base Scenario".

        :param current_model: The currently edited and used model. It is used as the currently edited model
        :type current_model: MultiCircuit
        """
        self._root_nodes: List[ScenarioNode] = []
        self._nodes_by_id: Dict[int, ScenarioNode] = {}
        self._next_id: int = 1

        # Model to compare the current model against (kept for backwards compatibility)
        self._base_model: MultiCircuit | None = current_model

        # Currently edited and used model (acts as the place to compose the model of a delta)
        self._current_model: MultiCircuit | None = current_model

        # Currently active scenario node
        self._current_node: ScenarioNode | None = None

        # Set a default name if the current model has an empty name
        if current_model is not None:
            if current_model.name is None or current_model.name.strip() == "":
                current_model.name = "Base Scenario"

            # Create the initial root scenario node from the current model
            root_node = self.create_node(data=current_model, parent_id=None, position=0)
            self._current_node = root_node

    @property
    def base_model(self) -> MultiCircuit:
        return self._base_model

    @base_model.setter
    def base_model(self, val: MultiCircuit):
        if isinstance(val, MultiCircuit):
            self._base_model: MultiCircuit = val
        elif val is None:
            self._base_model = None
        else:
            raise ValueError("Base model must be a MultiCircuit object")

    @property
    def current_model(self) -> MultiCircuit:
        return self._current_model

    @current_model.setter
    def current_model(self, val: MultiCircuit):
        if isinstance(val, MultiCircuit):
            self._current_model: MultiCircuit = val
        else:
            raise ValueError("Current model must be a MultiCircuit object")

    @property
    def current_node(self) -> ScenarioNode:
        return self._current_node

    @property
    def root_nodes(self) -> List[ScenarioNode]:
        return self._root_nodes

    def _generate_id(self) -> int:
        node_id: int = self._next_id
        self._next_id += 1
        return node_id

    @staticmethod
    def checkout(node: ScenarioNode) -> MultiCircuit:
        """
        Reconstruct the full MultiCircuit for *node* by replaying its delta chain from the root.
        Always returns a **fresh copy** — safe to mutate without affecting stored data.

        - Root nodes: returns ``root.data.copy()``.
        - Non-root nodes: walks root → … → node, copies the root circuit, then applies each
          ancestor's delta (``node.data``) in order via ``merge_circuit()``.

        :param node: Target ScenarioNode
        :return: Fully composed MultiCircuit for that node
        """
        if node.parent is None:
            return node.circuit.copy()

        # Collect the path from this node up to (but not including) the root
        chain: list[ScenarioNode] = []
        current: ScenarioNode = node
        while current.parent is not None:
            chain.append(current)
            current = current.parent
        root: ScenarioNode = current
        chain.reverse()  # root-child → … → node

        # Start from a copy of the root's authoritative circuit
        composed: MultiCircuit = root.circuit.copy()

        # Apply each delta going down the chain (node.data IS the delta for non-root nodes)
        for step in chain:
            composed.merge_circuit(new_grid=step.circuit)

        # Preserve the target scenario's name (composed inherits root's name otherwise)
        composed.name = node.circuit.name

        return composed

    def commit_current(self) -> None:
        """
        Persist edits made to the currently active scenario.

        - **Root**: no-op — ``root.data`` is the authoritative circuit and is edited in-place.
        - **Non-root**: computes ``differentiate_circuits(current_model, parent_composed)``
          and stores the result back into ``node.data``, replacing the previous delta.
          The scenario name is preserved on the new delta.
        """
        if self._current_node is None:
            return

        if self._current_node.parent is None:
            # Root: current_model IS root.data, already up to date
            return

        # Preserve the user-facing scenario name before we overwrite node.data
        scenario_name: str = self._current_node.circuit.name

        # Compose parent's full circuit to use as the diff base
        parent_circuit: MultiCircuit = self.checkout(self._current_node.parent)

        # Compute delta: what changed in current_model relative to parent
        _ok, _logger, delta = self._current_model.differentiate_circuits(
            base_grid=parent_circuit,
            force_second_pass=True,  # always detect deletions
        )

        delta.name = scenario_name
        self._current_node.circuit = delta

    def activate_scenario(self, node_id: int) -> MultiCircuit:
        """
        Switch the active scenario to the node identified by *node_id*.

        1. Commits the current node's unsaved edits (non-root only).
        2. Composes the target node's full circuit via ``checkout()``.
        3. Updates ``current_model`` and ``current_node``.

        Root nodes use ``root.data`` directly so in-place edits are reflected immediately.
        Non-root nodes always get a fresh composed copy.

        :param node_id: ID of the node to activate
        :return: The MultiCircuit that is now active
        """
        target: ScenarioNode = self.get_node(node_id)

        self.commit_current()

        if target.parent is None:
            composed: MultiCircuit = target.circuit
        else:
            composed = self.checkout(target)

        self._current_model = composed
        self._current_node = target

        return composed

    def create_node(
            self,
            data: MultiCircuit,
            parent_id: int | None = None,
            position: int | None = None,
    ) -> ScenarioNode:
        """

        :param data:
        :param parent_id:
        :param position:
        :return:
        """
        parent: ScenarioNode | None = None
        if parent_id is not None:
            parent = self.get_node(parent_id)

        node: ScenarioNode = ScenarioNode(
            node_id=self._generate_id(),
            data=data,
            parent=parent,
        )

        if parent is None:
            if position is None:
                self._root_nodes.append(node)
            else:
                self._root_nodes.insert(position, node)
        else:
            if position is None:
                parent.append_child(node)
            else:
                parent.insert_child(position, node)

        self._nodes_by_id[node.node_id] = node
        return node

    def roots_number(self):
        return len(self._root_nodes)

    def get_node(self, node_id: int) -> ScenarioNode:
        """

        :param node_id:
        :return:
        """
        if node_id not in self._nodes_by_id:
            raise KeyError(f"Node with id {node_id} does not exist")
        return self._nodes_by_id[node_id]

    def set_node(self, node_id: int, node: ScenarioNode):
        """

        :param node_id:
        :param node:
        :return:
        """
        self._nodes_by_id[node_id] = node

    def insert_node(self, position: int, node: ScenarioNode):
        """

        :param position:
        :param node:
        :return:
        """
        self._root_nodes.insert(position, node)

    def exists(self, node_id: int) -> bool:
        """

        :param node_id:
        :return:
        """
        return node_id in self._nodes_by_id

    def update_node_data(self, node_id: int, data: MultiCircuit) -> ScenarioNode:
        """

        :param node_id:
        :param data:
        :return:
        """
        node: ScenarioNode = self.get_node(node_id)
        node.circuit = data
        return node

    def delete_node(self, node_id: int) -> ScenarioNode:
        """

        :param node_id:
        :return:
        """
        node: ScenarioNode = self.get_node(node_id)

        if node.parent is None:
            self._root_nodes.remove(node)
        else:
            node.parent.remove_child(node)

        self._delete_from_registry_recursive(node)
        return node

    def _delete_from_registry_recursive(self, node: ScenarioNode) -> None:
        """

        :param node:
        :return:
        """
        for child in node.children:
            self._delete_from_registry_recursive(child)

        node.children.clear()
        if node.node_id in self._nodes_by_id:
            del self._nodes_by_id[node.node_id]

    def move_node(
            self,
            node_id: int,
            new_parent_id: int | None,
            position: int | None = None,
    ) -> ScenarioNode:
        """

        :param node_id:
        :param new_parent_id:
        :param position:
        :return:
        """
        node: ScenarioNode = self.get_node(node_id)

        new_parent: ScenarioNode | None = None
        if new_parent_id is not None:
            new_parent = self.get_node(new_parent_id)

        if new_parent is node:
            raise ValueError("A node cannot be its own parent")

        if self._is_descendant(candidate_parent=node, candidate_child=new_parent):
            raise ValueError("Cannot move a node under one of its descendants")

        if node.parent is None:
            self._root_nodes.remove(node)
        else:
            node.parent.remove_child(node)

        node.parent = new_parent

        if new_parent is None:
            if position is None:
                self._root_nodes.append(node)
            else:
                self._root_nodes.insert(position, node)
        else:
            if position is None:
                new_parent.append_child(node)
            else:
                new_parent.insert_child(position, node)

        return node

    def _is_descendant(self,
                       candidate_parent: ScenarioNode,
                       candidate_child: ScenarioNode | None) -> bool:
        """

        :param candidate_parent:
        :param candidate_child:
        :return:
        """
        current: ScenarioNode | None = candidate_child

        while current is not None:
            if current is candidate_parent:
                return True
            current = current.parent

        return False

    def clear(self) -> None:
        """

        :return:
        """
        self._root_nodes.clear()
        self._nodes_by_id.clear()
        self._next_id = 1

    def iter_nodes_depth_first(self) -> List[ScenarioNode]:
        """

        :return:
        """
        result: List[ScenarioNode] = list()

        for root in self._root_nodes:
            self._collect_subtree_depth_first(root, result)

        return result

    def _collect_subtree_depth_first(self,
                                     node: ScenarioNode,
                                     result: List[ScenarioNode]) -> None:
        """

        :param node:
        :param result:
        :return:
        """
        result.append(node)

        child: ScenarioNode
        for child in node.children:
            self._collect_subtree_depth_first(child, result)

    def get_sorted_node_data(self) -> List[MultiCircuit]:
        """
        Deterministic preorder traversal.
        Good if you only want the MultiCircuit objects in a stable order.
        """
        nodes: List[ScenarioNode] = self.iter_nodes_depth_first()
        return [node.circuit for node in nodes]

    def to_record_list(self) -> List[Dict[str, Any]]:
        """
        Export full tree structure as a flat ordered list.
        This is the correct format for JSON if you want to rebuild the tree later.
        """
        records: List[Dict[str, Any]] = list()

        for node in self.iter_nodes_depth_first():
            parent_id: int | None = None if node.parent is None else node.parent.node_id
            position: int = 0 if node.parent is None else node.row()

            records.append(
                {
                    "node_id": node.node_id,
                    "parent_id": parent_id,
                    "position": position,
                    "idtag": node.circuit.idtag,  # MultiCircuit Idtag
                }
            )

        return records

    def get_save_data(self) -> Tuple[Dict[str, Dict[str, str]], Dict[str, MultiCircuit]]:
        """

        :return:
        """
        multiverse_meta_data = dict()
        multiverse_model_data = dict()

        base_circuit: MultiCircuit = self._root_nodes[0].circuit

        for node in self.iter_nodes_depth_first():
            multiverse_meta_data[node.node_id] = {
                "node_id": node.node_id,
                "circuit_idtag": node.circuit.idtag,
                "parent_id": node.parent.node_id if node.parent is not None else None,
                "children": [chl.node_id for chl in node.children],
            }

            # we want to store all those models that are not the root
            # if node.data != base_circuit:
            multiverse_model_data[node.circuit.idtag] = node.circuit

        return multiverse_meta_data, multiverse_model_data

    def parse_json(self,
                   diffs_dict: Dict[str, MultiCircuit],
                   metadata: Dict[str, Dict[str | int | float]]):
        """
         Parse the json metadata to fill this object
        :param diffs_dict:
        :param metadata: json file name or zip file pointer
        :return:
        """
        self.clear()
        self._base_model = None
        self._current_model = None
        self._current_node = None

        built_nodes: dict[int, ScenarioNode] = dict()
        max_id: int = 0

        # Build nodes from parent links; metadata may be serialized as a dict with string keys.
        pending: Dict[int, Dict[str | int | float]] = {
            int(node_id): record for node_id, record in metadata.items()
        }

        while pending:
            progressed: bool = False

            for metadata_node_id in list(pending.keys()):
                record = pending[metadata_node_id]

                node_id: int = int(record["node_id"])
                circuit_idtag: str = str(record["circuit_idtag"])
                parent_id_raw = record["parent_id"]
                parent_id: int | None = None if parent_id_raw is None else int(parent_id_raw)

                if parent_id is not None and parent_id not in built_nodes:
                    continue

                parent: ScenarioNode | None = None if parent_id is None else built_nodes[parent_id]

                node = ScenarioNode(
                    node_id=node_id,
                    data=diffs_dict[circuit_idtag],
                    parent=parent,
                )

                if parent is None:
                    self._root_nodes.append(node)
                else:
                    parent.append_child(node)

                self.set_node(node_id, node)
                built_nodes[node_id] = node
                del pending[metadata_node_id]
                progressed = True

                if node_id > max_id:
                    max_id = node_id

            if not progressed:
                unresolved = ", ".join(str(node_id) for node_id in pending.keys())
                raise ValueError(f"Could not resolve multiverse metadata parent links for nodes: {unresolved}")

        self._next_id = max_id + 1

        if self._root_nodes:
            self._current_node = self._root_nodes[0]
            self._current_model = self._current_node.circuit
            self._base_model = self._root_nodes[0].circuit
