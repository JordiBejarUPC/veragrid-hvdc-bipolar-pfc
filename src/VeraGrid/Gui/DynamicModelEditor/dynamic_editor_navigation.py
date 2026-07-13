# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import List

from VeraGridEngine.Utils.Symbolic.block import Block


class DynamicEditorNavigation:
    """
    Domain object that tracks the current position inside a block hierarchy.

    It stores a *root* block and a *current* block and provides
    domain-language operations to navigate between them.  The internal
    representation is kept private so that the API stays clean.
    """

    def __init__(self, root_block: Block) -> None:
        """
        :param root_block: The top-level block that owns this tab.
        :return: None.
        """
        self._root_block: Block = root_block
        self._path: List[Block] = [root_block]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def root_block(self) -> Block:
        """Return the root block of this tab."""
        return self._root_block

    @property
    def current_block(self) -> Block:
        """Return the block currently being edited."""
        return self._path[-1]

    # ------------------------------------------------------------------
    # Navigation operations
    # ------------------------------------------------------------------

    def open_child(self, block: Block) -> None:
        """
        Navigate into a direct child of the current block.

        :param block: A child of :pyattr:`current_block`.
        :return: None.
        """
        self._path.append(block)

    def go_to(self, block: Block) -> None:
        """
        Jump to any block in the current path.

        The target *must* already be in the path (i.e. an ancestor of the
        current block or the current block itself).

        :param block: Target block to navigate to.
        :raises ValueError: If *block* is not part of the current path.
        :return: None.
        """
        for index, ancestor in enumerate(self._path):
            if ancestor.uid == block.uid:
                self._path = self._path[: index + 1]
                return
        raise ValueError(
            f"Block '{block.name}' (uid={block.uid}) is not in the current path."
        )

    def go_to_root(self) -> None:
        """Navigate back to the root block."""
        self._path = [self._root_block]

    def go_to_parent(self) -> None:
        """
        Navigate one level up.

        :raises ValueError: If already at the root.
        :return: None.
        """
        if len(self._path) <= 1:
            raise ValueError("Already at the root block.")
        self._path.pop()

    # ------------------------------------------------------------------
    # Breadcrumb helpers
    # ------------------------------------------------------------------

    def breadcrumb_path(self) -> List[Block]:
        """
        Return the full path from root to the current block.

        The returned list always starts with the root block and ends with
        :pyattr:`current_block`.  It is a *copy* so callers cannot mutate
        the internal state.

        :return: Ordered list of ancestor blocks including root and current.
        """
        return list(self._path)

    def depth(self) -> int:
        """
        Return the current depth (0 = root).

        :return: Number of navigation steps from the root.
        """
        return len(self._path) - 1

    def is_root(self) -> bool:
        """
        Return whether the current block is the root block.

        :return: ``True`` when at root level.
        """
        return len(self._path) == 1
