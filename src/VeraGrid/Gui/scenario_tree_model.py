# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.multiverse import MultiVerse, ScenarioNode


class ScenarioTreeModel(QAbstractItemModel):
    __slots__ = (
        "_multiverse",
        "_headers",
    )

    def __init__(self, multiverse: MultiVerse, parent=None) -> None:
        """
        Qt tree model adapter for the MultiVerse hierarchy.

        :param multiverse: Scenario hierarchy container
        :param parent: Optional Qt parent
        """
        super().__init__(parent)
        self._multiverse: MultiVerse = multiverse
        self._headers: List[str] = [
            "Name",
            "Objects",
            "Comment"
        ]

    @property
    def multiverse(self) -> MultiVerse:
        return self._multiverse

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        Number of visible columns in the tree.

        :param parent: Parent model index
        :return: Number of columns
        """
        return len(self._headers)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        Number of rows under a given parent.

        :param parent: Parent model index
        :return: Number of child rows
        """
        if parent.isValid():
            parent_node: ScenarioNode = parent.internalPointer()
            return parent_node.child_count()
        else:
            return len(self._multiverse.root_nodes)

    def index(
            self,
            row: int,
            column: int,
            parent: QModelIndex = QModelIndex(),
    ) -> QModelIndex:
        """
        Create a model index for the given row/column under parent.

        :param row: Row number
        :param column: Column number
        :param parent: Parent model index
        :return: QModelIndex
        """
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if parent.isValid():
            parent_node: ScenarioNode = parent.internalPointer()
            child_node: ScenarioNode = parent_node.child(row)
        else:
            child_node = self._multiverse.root_nodes[row]

        return self.createIndex(row, column, child_node)

    def parent(self, index: QModelIndex) -> QModelIndex:
        """
        Get the Qt parent index of a given node index.

        :param index: Child index
        :return: Parent QModelIndex, or invalid index if root
        """
        if not index.isValid():
            return QModelIndex()

        node: ScenarioNode = index.internalPointer()
        parent_node: ScenarioNode | None = node.parent

        if parent_node is None:
            return QModelIndex()

        grand_parent: ScenarioNode | None = parent_node.parent

        if grand_parent is None:
            row: int = self._multiverse.root_nodes.index(parent_node)
        else:
            row = parent_node.row()

        return self.createIndex(row, 0, parent_node)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Provide the data to the view.

        :param index: Model index
        :param role: Qt item role
        :return: Data value for the requested role
        """
        if not index.isValid():
            return None

        if role not in (Qt.ItemDataRole.DisplayRole,
                        Qt.ItemDataRole.EditRole):
            return None

        node: ScenarioNode = index.internalPointer()
        circuit: MultiCircuit = node.circuit
        column: int = index.column()

        if column == 0:
            return circuit.name
        if column == 1:
            return f"{circuit.get_all_elements_number()}"
        if column == 2:
            return circuit.comments

        return None

    def setData(
            self,
            index: QModelIndex,
            value: Any,
            role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        """
        Edit the underlying MultiCircuit data.

        :param index: Model index
        :param value: New value
        :param role: Qt item role
        :return: True if edited, False otherwise
        """
        if not index.isValid():
            return False

        if role != Qt.ItemDataRole.EditRole:
            return False

        node: ScenarioNode = index.internalPointer()
        circuit: MultiCircuit = node.circuit
        column: int = index.column()

        if column == 0:
            circuit.name = str(value)
        if column == 1:
            return False
        if column == 2:
            circuit.comments = str(value)
        else:
            return False

        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """
        Item capabilities.

        :param index: Model index
        :return: Qt item flags
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return (
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEditable
        )

    def headerData(
            self,
            section: int,
            orientation: Qt.Orientation,
            role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """
        Horizontal header labels.

        :param section: Section number
        :param orientation: Orientation
        :param role: Qt item role
        :return: Header label
        """
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]

        return None

    def get_node(self, index: QModelIndex) -> ScenarioNode | None:
        """
        Convenience accessor.

        :param index: Model index
        :return: ScenarioNode or None if invalid
        """
        if index.isValid():
            return index.internalPointer()
        return None

    def refresh(self) -> None:
        """
        Full model reset after external structural changes.
        """
        self.beginResetModel()
        self.endResetModel()

    def refresh_data(self) -> None:
        """
        Refresh all cell data without resetting the model structure.
        Preserves tree expansion state and selection.
        Emit dataChanged for every node in the tree.
        """
        for node in self._multiverse.iter_nodes_depth_first():
            if node.parent is None:
                row: int = self._multiverse.root_nodes.index(node)
            else:
                row = node.row()
            top_left: QModelIndex = self.createIndex(row, 0, node)
            bottom_right: QModelIndex = self.createIndex(row, len(self._headers) - 1, node)
            self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.DisplayRole])

    # -------------------------------------------------------------------------
    # CRUD wrappers synchronized with Qt model notifications
    # -------------------------------------------------------------------------
    def append_root(self, data: MultiCircuit) -> ScenarioNode:
        """
        Append a new root node.

        :param data: MultiCircuit to store
        :return: Created ScenarioNode
        """
        row: int = len(self._multiverse.root_nodes)
        self.beginInsertRows(QModelIndex(), row, row)
        node: ScenarioNode = self._multiverse.create_node(data=data, parent_id=None, position=row)
        self.endInsertRows()
        return node

    def append_child(self, parent_index: QModelIndex, data: MultiCircuit) -> ScenarioNode:
        """
        Append a child under the given parent index.

        :param parent_index: Parent QModelIndex
        :param data: MultiCircuit to store
        :return: Created ScenarioNode
        """
        if not parent_index.isValid():
            raise ValueError("Parent index must be valid")

        parent_node: ScenarioNode = parent_index.internalPointer()
        row: int = parent_node.child_count()

        self.beginInsertRows(parent_index, row, row)
        node: ScenarioNode = self._multiverse.create_node(
            data=data,
            parent_id=parent_node.node_id,
            position=row,
        )
        self.endInsertRows()
        return node

    def remove_node(self, index: QModelIndex) -> bool:
        """
        Remove one node and its subtree.

        :param index: QModelIndex to remove
        :return: True if removed
        """
        if not index.isValid():
            return False

        node: ScenarioNode = index.internalPointer()
        parent_node: ScenarioNode | None = node.parent

        if parent_node is None:
            parent_index: QModelIndex = QModelIndex()
            row: int = self._multiverse.root_nodes.index(node)
        else:
            parent_index = self.parent(index)
            row = node.row()

        self.beginRemoveRows(parent_index, row, row)
        self._multiverse.delete_node(node.node_id)
        self.endRemoveRows()
        return True

    def move_node_to_parent(
            self,
            index: QModelIndex,
            new_parent_index: QModelIndex | None,
            position: int | None = None,
    ) -> bool:
        """
        Move a node to a new parent.

        This uses a model reset because it is simpler and safer than wiring
        beginMoveRows/endMoveRows for all tree cases.

        :param index: Node to move
        :param new_parent_index: New parent index, or None/invalid for root
        :param position: Insertion position, or append if None
        :return: True if moved
        """
        if not index.isValid():
            return False

        node: ScenarioNode = index.internalPointer()

        new_parent_id: int | None = None
        if new_parent_index is not None and new_parent_index.isValid():
            new_parent_node: ScenarioNode = new_parent_index.internalPointer()
            new_parent_id = new_parent_node.node_id

        self.beginResetModel()
        self._multiverse.move_node(
            node_id=node.node_id,
            new_parent_id=new_parent_id,
            position=position,
        )
        self.endResetModel()
        return True

    def merge_children_into_parent(self, index: QModelIndex) -> bool:
        """
        Merge all direct children of the selected node into that node.

        A model reset is used because the operation can both remove nodes and
        reparent descendants in one step.

        :param index: Parent QModelIndex
        :return: True if the merge was applied
        """
        if not index.isValid():
            return False

        node: ScenarioNode = index.internalPointer()

        self.beginResetModel()
        self._multiverse.merge_children_into_parent(node.node_id)
        self.endResetModel()
        return True
