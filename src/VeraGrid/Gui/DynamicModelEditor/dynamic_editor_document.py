# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_models import clone_block_for_editing, copy_block_state


class DynamicEditorDocument:
    """
    Represents a single editing document opened in a tab.

    A document owns exactly two block trees:

    * ``original_root_block`` — the authoritative model as it was when the
      document was opened.  Never mutated during editing.
    * ``working_root_block`` — a deep copy of the original that the editors
      modify directly.  All navigation, scene building, and in-place edits
      operate exclusively on this tree.

    The document also provides lifecycle operations:

    * :meth:`commit` — copy the working tree back into the original tree.
    * :meth:`discard` — throw away the working tree and start fresh from
      the original.
    * :meth:`is_dirty` — whether the working tree has unsaved changes.
    """

    def __init__(self, original_root_block: Block) -> None:
        """
        Create a new document from the original (persistent) block tree.

        A single deep copy is made immediately; all subsequent edits
        target the copy.

        :param original_root_block: The authoritative block tree to edit.
        :return: None.
        """
        self._original_root_block: Block = original_root_block
        self._working_root_block: Block = clone_block_for_editing(original_root_block)

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def original_root_block(self) -> Block:
        """Return the original (persistent) block tree."""
        return self._original_root_block

    @property
    def working_root_block(self) -> Block:
        """Return the working (editable) block tree."""
        return self._working_root_block

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """
        Copy the working tree back into the original tree.

        This is the single point where edited state is persisted back
        to the authoritative model.  Call this when the user explicitly
        saves or applies changes.

        :return: None.
        """
        copy_block_state(
            source_block=self._working_root_block,
            target_block=self._original_root_block,
        )

    def discard(self) -> None:
        """
        Discard the current working tree and recreate it from the
        original tree.

        :return: None.
        """
        self._working_root_block = clone_block_for_editing(self._original_root_block)

    def is_dirty(self) -> bool:
        """
        Return whether the working tree has unsaved modifications.

        :return: ``True`` if the document has been modified since the
            last commit.  Currently always returns ``False`` (placeholder).
        """
        return False
