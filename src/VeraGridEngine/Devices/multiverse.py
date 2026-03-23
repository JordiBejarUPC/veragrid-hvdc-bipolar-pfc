# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import json
from typing import List, Dict, Any
from VeraGridEngine.Devices.multi_circuit import MultiCircuit


class ScenarioNode:
    __slots__ = (
        "node_id",
        "data",
        "parent",
        "children",
    )

    def __init__(
            self,
            node_id: int,
            data: MultiCircuit,
            parent: ScenarioNode | None = None,
    ) -> None:
        """
        Initializes a TreeNode object with a unique identifier, associated data, an optional
        reference to its parent node, and initializes an empty list for its child nodes.

        :param node_id: A unique identifier for the tree node.
        :param data: An instance of MultiCircuit class, representing the associated data for this tree node.
        :param parent: An optional TreeNode instance, referencing the parent of this tree node. Defaults to None.
        """
        self.node_id: int = node_id
        self.data: MultiCircuit = data
        self.parent: ScenarioNode | None = parent
        self.children: list[ScenarioNode] = []

    def append_child(self, child: ScenarioNode) -> None:
        child.parent = self
        self.children.append(child)

    def insert_child(self, position: int, child: ScenarioNode) -> None:
        child.parent = self
        self.children.insert(position, child)

    def remove_child(self, child: ScenarioNode) -> None:
        self.children.remove(child)
        child.parent = None

    def remove_child_at(self, position: int) -> ScenarioNode:
        child: ScenarioNode = self.children.pop(position)
        child.parent = None
        return child

    def child(self, row: int) -> ScenarioNode:
        return self.children[row]

    def child_count(self) -> int:
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
        "_current_model"
    )
    def __init__(self, current_model: MultiCircuit) -> None:
        """
        Initializes an instance of the class with the specified model and necessary
        attributes for processing scenario nodes and model comparison.

        :param current_model: The currently edited and used model. It is used as the currently edited model
        :type current_model: MultiCircuit
        """
        self._root_nodes: List[ScenarioNode] = []
        self._nodes_by_id: Dict[int, ScenarioNode] = {}
        self._next_id: int = 1

        # Model to compare the current model against
        self._base_model: MultiCircuit | None = current_model

        # Currently edited and used model
        self._current_model: MultiCircuit = current_model

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
    def root_nodes(self) -> List[ScenarioNode]:
        return self._root_nodes

    def _generate_id(self) -> int:
        node_id: int = self._next_id
        self._next_id += 1
        return node_id

    def create_node(
            self,
            data: MultiCircuit,
            parent_id: int | None = None,
            position: int | None = None,
    ) -> ScenarioNode:
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
        if node_id not in self._nodes_by_id:
            raise KeyError(f"Node with id {node_id} does not exist")
        return self._nodes_by_id[node_id]

    def set_node(self, node_id: int, node: ScenarioNode):
        self._nodes_by_id[node_id] = node

    def insert_node(self, position: int, node: ScenarioNode):
        self._root_nodes.insert(position, node)

    def exists(self, node_id: int) -> bool:
        return node_id in self._nodes_by_id

    def update_node_data(self, node_id: int, data: MultiCircuit) -> ScenarioNode:
        node: ScenarioNode = self.get_node(node_id)
        node.data = data
        return node

    def delete_node(self, node_id: int) -> ScenarioNode:
        node: ScenarioNode = self.get_node(node_id)

        if node.parent is None:
            self._root_nodes.remove(node)
        else:
            node.parent.remove_child(node)

        self._delete_from_registry_recursive(node)
        return node

    def _delete_from_registry_recursive(self, node: ScenarioNode) -> None:
        child: ScenarioNode
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

    def _is_descendant(
            self,
            candidate_parent: ScenarioNode,
            candidate_child: ScenarioNode | None,
    ) -> bool:
        current: ScenarioNode | None = candidate_child

        while current is not None:
            if current is candidate_parent:
                return True
            current = current.parent

        return False

    def clear(self) -> None:
        self._root_nodes.clear()
        self._nodes_by_id.clear()
        self._next_id = 1

    def iter_nodes_depth_first(self) -> list[ScenarioNode]:
        result: list[ScenarioNode] = []
        root: ScenarioNode

        for root in self._root_nodes:
            self._collect_subtree_depth_first(root, result)

        return result

    def _collect_subtree_depth_first(
            self,
            node: ScenarioNode,
            result: list[ScenarioNode],
    ) -> None:
        result.append(node)

        child: ScenarioNode
        for child in node.children:
            self._collect_subtree_depth_first(child, result)

    def get_sorted_node_data(self) -> list[MultiCircuit]:
        """
        Deterministic preorder traversal.
        Good if you only want the MultiCircuit objects in a stable order.
        """
        nodes: list[ScenarioNode] = self.iter_nodes_depth_first()
        return [node.data for node in nodes]

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
                    "idtag": node.data.idtag,  # MultiCircuit Idtag
                }
            )

        return records

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_record_list(), indent=indent)


def from_json(base_circuit: MultiCircuit,
              diffs_dict: Dict[str, MultiCircuit],
              f_name) -> MultiVerse:
    """
    
    :param base_circuit: 
    :param diffs_dict: 
    :param f_name: json file name or zip file pointer 
    :return: 
    """
    handler: MultiVerse = MultiVerse(base_circuit)
    built_nodes: dict[int, ScenarioNode] = {}
    max_id: int = 0

    # Read the json data
    with open(f_name, "r") as f:
        records: List[Dict[str, Any]] = json.load(f)

    for record in records:

        # get the record values
        node_id: int = int(record["node_id"])
        parent_id_raw: Any = record["parent_id"]
        parent_id: int | None = None if parent_id_raw is None else int(parent_id_raw)
        position: int = int(record["position"])
        idtag: str = str(record["idtag"])

        parent: ScenarioNode | None = None
        if parent_id is not None:
            if parent_id not in built_nodes:
                raise ValueError(
                    f"Parent id {parent_id} was not found before child {node_id}"
                )
            parent = built_nodes[parent_id]

        node: ScenarioNode = ScenarioNode(
            node_id=node_id,
            data=diffs_dict[idtag],
            parent=parent,
        )

        if parent is None:
            if 0 < position < handler.roots_number():
                handler.insert_node(position, node)
            else:
                raise ValueError(f"Invalid root position {position} for node {node_id}")

        else:
            if 0 < position < len(parent.children):
                parent.children.insert(position, node)
            else:
                raise ValueError(f"Invalid child position {position} for node {node_id}")

        handler.set_node(node_id, node)
        built_nodes[node_id] = node

        if node_id > max_id:
            max_id = node_id

    handler._next_id = max_id + 1
    return handler
