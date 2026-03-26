# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path

import pytest

import VeraGridEngine.api as vge
from VeraGridEngine.IO.file_open import FileOpen


GRID_FOLDER = Path(__file__).resolve().parents[1] / "data" / "grids"


def _load_grid(name: str):
    return vge.open_file(str(GRID_FOLDER / name))


def _get_bus_by_name(grid, bus_name: str):
    for bus in grid.buses:
        if bus.name == bus_name:
            return bus
    return None


def _assert_circuits_equal(grid1, grid2) -> None:
    equal, logger = grid1.compare_circuits(
        grid2,
        detailed_profile_comparison=True,
        skip_internals=True,
    )

    if not equal:
        logger.print()

    assert equal


def _assert_same_multiverse(expected, loaded) -> None:
    expected_ids = [node.node_id for node in expected.iter_nodes_depth_first()]
    loaded_ids = [node.node_id for node in loaded.iter_nodes_depth_first()]

    assert loaded_ids == expected_ids
    assert len(loaded.root_nodes) == len(expected.root_nodes)

    for node_id in expected_ids:
        expected_node = expected.get_node(node_id)
        loaded_node = loaded.get_node(node_id)

        expected_parent_id = None if expected_node.parent is None else expected_node.parent.node_id
        loaded_parent_id = None if loaded_node.parent is None else loaded_node.parent.node_id

        assert loaded_parent_id == expected_parent_id
        assert loaded_node.circuit.name == expected_node.circuit.name
        assert len(loaded_node.diagrams) == len(expected_node.diagrams)

        for expected_diagram, loaded_diagram in zip(expected_node.diagrams, loaded_node.diagrams):
            assert loaded_diagram is not expected_diagram
            assert loaded_diagram.name == expected_diagram.name

        _assert_circuits_equal(
            expected.checkout(expected_node),
            loaded.checkout(loaded_node),
        )


def _build_sample_multiverse():
    base_grid = _load_grid("lynn5node.gridcal")
    mv = vge.MultiVerse(base_grid)

    root = mv.root_nodes[0]
    child = mv.create_node(
        data=vge.MultiCircuit(name="child"),
        parent_id=root.node_id,
        position=root.child_count(),
    )
    sibling = mv.create_node(
        data=vge.MultiCircuit(name="sibling"),
        parent_id=root.node_id,
        position=root.child_count(),
    )
    grandchild = mv.create_node(
        data=vge.MultiCircuit(name="grandchild"),
        parent_id=child.node_id,
        position=child.child_count(),
    )

    mv.activate_scenario(child.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=10.0, name="child_only_bus"))

    mv.activate_scenario(grandchild.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=11.0, name="grandchild_only_bus"))

    mv.activate_scenario(sibling.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=12.0, name="sibling_only_bus"))
    mv.commit_current()

    return mv, root, child, sibling, grandchild


def test_multiverse_child_edits_do_not_touch_root() -> None:
    """
    Verify that edits made in a child scenario are isolated from the root scenario.

    The child should keep its added bus after switching away and back, while the root
    should remain equal to the pristine base grid.
    """
    base_grid = _load_grid("lynn5node.gridcal")
    pristine_root = base_grid.copy()

    mv = vge.MultiVerse(base_grid)
    root = mv.root_nodes[0]
    child = mv.create_node(
        data=vge.MultiCircuit(name="child"),
        parent_id=root.node_id,
        position=root.child_count(),
    )

    mv.activate_scenario(child.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=10.0, name="child_only_bus"))

    # Switching away from the child must persist the delta automatically.
    mv.activate_scenario(root.node_id)

    root_grid = mv.checkout(root)
    child_grid = mv.checkout(child)

    assert _get_bus_by_name(root_grid, "child_only_bus") is None
    assert _get_bus_by_name(child_grid, "child_only_bus") is not None
    _assert_circuits_equal(root_grid, pristine_root)
    _assert_circuits_equal(root.circuit, pristine_root)

    reloaded_child_grid = mv.activate_scenario(child.node_id)
    assert _get_bus_by_name(reloaded_child_grid, "child_only_bus") is not None


def test_multiverse_nested_checkout_replays_parent_deltas() -> None:
    """
    Verify that checkout() composes ancestor deltas in order for nested scenarios.

    A grandchild should inherit the child's changes plus its own changes, while the
    child should not include changes introduced only at the grandchild level.
    """
    base_grid = _load_grid("lynn5node.gridcal")
    mv = vge.MultiVerse(base_grid)

    root = mv.root_nodes[0]
    child = mv.create_node(
        data=vge.MultiCircuit(name="child"),
        parent_id=root.node_id,
        position=root.child_count(),
    )
    grandchild = mv.create_node(
        data=vge.MultiCircuit(name="grandchild"),
        parent_id=child.node_id,
        position=child.child_count(),
    )

    mv.activate_scenario(child.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=10.0, name="child_only_bus"))

    # Activating the grandchild commits the child and composes the child changes into the new model.
    mv.activate_scenario(grandchild.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=11.0, name="grandchild_only_bus"))
    mv.commit_current()

    root_grid = mv.checkout(root)
    child_grid = mv.checkout(child)
    grandchild_grid = mv.checkout(grandchild)

    assert _get_bus_by_name(root_grid, "child_only_bus") is None
    assert _get_bus_by_name(root_grid, "grandchild_only_bus") is None
    assert _get_bus_by_name(child_grid, "child_only_bus") is not None
    assert _get_bus_by_name(child_grid, "grandchild_only_bus") is None
    assert _get_bus_by_name(grandchild_grid, "child_only_bus") is not None
    assert _get_bus_by_name(grandchild_grid, "grandchild_only_bus") is not None


def test_multiverse_parse_json_roundtrip() -> None:
    """
    Verify that get_save_data() and parse_json() rebuild the same multiverse in memory.

    This covers tree structure, parent relationships, scenario names, and composed
    circuit equality for every node.
    """
    mv, _, _, _, _ = _build_sample_multiverse()

    metadata, model_data = mv.get_save_data()

    loaded_mv = vge.MultiVerse(current_model=None)
    loaded_mv.parse_json(model_data, metadata)

    _assert_same_multiverse(mv, loaded_mv)


def test_multiverse_save_load_roundtrip(tmp_path: Path) -> None:
    """
    Verify full multiverse persistence through save/load of a .veragrid archive.

    The loaded multiverse should match the original one node-for-node and scenario-for-scenario.
    """
    mv, root, _, _, _ = _build_sample_multiverse()

    # Saving from the root avoids serializing a child delta as the top-level circuit.
    mv.activate_scenario(root.node_id)

    file_name = tmp_path / "multiverse_roundtrip.veragrid"
    vge.save_multiverse(mv=mv, filename=str(file_name))

    loader = FileOpen(str(file_name))
    loader.open()

    assert loader.multiverse is not None
    _assert_same_multiverse(mv, loader.multiverse)


def test_multiverse_move_and_delete_update_tree_registry() -> None:
    """
    Verify that move_node() and delete_node() keep both the tree and node registry coherent.

    This covers reparenting, cycle protection, and recursive registry cleanup on delete.
    """
    mv = vge.MultiVerse(vge.MultiCircuit(name="base"))
    root = mv.root_nodes[0]

    child_a = mv.create_node(
        data=vge.MultiCircuit(name="child_a"),
        parent_id=root.node_id,
        position=root.child_count(),
    )
    child_b = mv.create_node(
        data=vge.MultiCircuit(name="child_b"),
        parent_id=root.node_id,
        position=root.child_count(),
    )
    grandchild = mv.create_node(
        data=vge.MultiCircuit(name="grandchild"),
        parent_id=child_a.node_id,
        position=child_a.child_count(),
    )

    mv.move_node(grandchild.node_id, child_b.node_id, position=0)

    assert grandchild.parent is child_b
    assert child_a.child_count() == 0
    assert child_b.child(0) is grandchild

    with pytest.raises(ValueError):
        mv.move_node(child_b.node_id, grandchild.node_id)

    mv.delete_node(child_b.node_id)

    assert not mv.exists(child_b.node_id)
    assert not mv.exists(grandchild.node_id)
    assert root.child_count() == 1
    assert root.child(0) is child_a


def test_multiverse_merge_children_into_parent_rebases_grandchildren() -> None:
    """
    Verify that merging direct children into a parent preserves rebased descendants.

    Direct children should be removed after their changes are absorbed by the parent,
    while grandchildren should move under the parent and keep the same composed scenario.
    """
    base_grid = _load_grid("lynn5node.gridcal")
    mv = vge.MultiVerse(base_grid)

    root = mv.root_nodes[0]
    child_a = mv.create_node(
        data=vge.MultiCircuit(name="child_a"),
        parent_id=root.node_id,
        position=root.child_count(),
    )
    child_b = mv.create_node(
        data=vge.MultiCircuit(name="child_b"),
        parent_id=root.node_id,
        position=root.child_count(),
    )
    grandchild = mv.create_node(
        data=vge.MultiCircuit(name="grandchild"),
        parent_id=child_a.node_id,
        position=child_a.child_count(),
    )

    mv.activate_scenario(child_a.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=10.0, name="child_a_bus"))

    mv.activate_scenario(child_b.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=11.0, name="child_b_bus"))

    mv.activate_scenario(grandchild.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=12.0, name="grandchild_bus"))
    mv.commit_current()

    expected_parent = mv.checkout(root)
    expected_parent.merge_circuit(child_a.circuit)
    expected_parent.merge_circuit(child_b.circuit)
    expected_grandchild = mv.checkout(grandchild)

    mv.merge_children_into_parent(root.node_id)

    assert root.child_count() == 1
    assert root.child(0) is grandchild
    assert grandchild.parent is root
    assert not mv.exists(child_a.node_id)
    assert not mv.exists(child_b.node_id)

    merged_root = mv.checkout(root)
    merged_grandchild = mv.checkout(grandchild)

    assert _get_bus_by_name(merged_root, "child_a_bus") is not None
    assert _get_bus_by_name(merged_root, "child_b_bus") is not None
    assert _get_bus_by_name(merged_root, "grandchild_bus") is None
    assert _get_bus_by_name(merged_grandchild, "grandchild_bus") is not None

    _assert_circuits_equal(merged_root, expected_parent)
    _assert_circuits_equal(merged_grandchild, expected_grandchild)


def test_multiverse_root_edits_are_persisted_in_place() -> None:
    """
    Verify that edits performed on the root scenario stay in the authoritative root model.

    Root scenarios are not stored as deltas, so switching away and back must not lose
    the changes or require a separate diff commit step.
    """
    base_grid = _load_grid("lynn5node.gridcal")
    mv = vge.MultiVerse(base_grid)

    root = mv.root_nodes[0]
    child = mv.create_node(
        data=vge.MultiCircuit(name="child"),
        parent_id=root.node_id,
        position=root.child_count(),
    )

    root_bus = vge.Bus(Vnom=13.0, name="root_only_bus")
    mv.current_model.add_bus(root_bus)

    mv.activate_scenario(child.node_id)
    mv.activate_scenario(root.node_id)

    root_grid = mv.checkout(root)

    assert _get_bus_by_name(root.circuit, "root_only_bus") is not None
    assert _get_bus_by_name(root_grid, "root_only_bus") is not None
    assert _get_bus_by_name(mv.current_model, "root_only_bus") is not None


def test_multicircuit_copy_deep_copies_diagrams() -> None:
    """
    Verify that MultiCircuit.copy() duplicates stored diagrams instead of sharing them.

    Child scenario activation relies on checkout(), which uses circuit copies. If diagrams are
    shared by reference, edits in one scenario can leak visually into other scenarios.
    """
    original = _load_grid("lynn5node.gridcal")
    original.add_diagram(vge.SchematicDiagram(name="Schematic Copy Test"))
    original.add_diagram(vge.MapDiagram(name="Map Copy Test"))
    original_schematic_index = len(original.diagrams) - 2

    copied = original.copy()

    assert len(copied.diagrams) == len(original.diagrams)

    for original_diagram, copied_diagram in zip(original.diagrams, copied.diagrams):
        assert copied_diagram is not original_diagram
        assert copied_diagram.name == original_diagram.name

    copied.diagrams[original_schematic_index].name = "Modified Diagram Name"
    assert original.diagrams[original_schematic_index].name == "Schematic Copy Test"


def test_multiverse_child_starts_with_copies_of_parent_diagrams() -> None:
    """
    Verify that a newly created child scenario inherits deep-copied diagrams from its parent.

    The child should start with the same diagram content as the parent, but diagram objects
    must not be shared by reference between the two scenarios.
    """
    mv = vge.MultiVerse(_load_grid("lynn5node.gridcal"))
    root = mv.root_nodes[0]
    child = mv.create_node(
        data=vge.MultiCircuit(name="child"),
        parent_id=root.node_id,
        position=root.child_count(),
    )

    assert len(child.diagrams) == len(root.diagrams)

    for root_diagram, child_diagram in zip(root.diagrams, child.diagrams):
        assert child_diagram is not root_diagram
        assert child_diagram.name == root_diagram.name


def test_multiverse_child_diagram_edits_persist_across_switches() -> None:
    """
    Verify that child-specific diagram edits survive commit and scenario switching.

    This covers the workflow where the user activates a child, edits its diagrams, commits,
    switches to the parent, and later comes back to the child.
    """
    mv = vge.MultiVerse(_load_grid("lynn5node.gridcal"))
    root = mv.root_nodes[0]
    child = mv.create_node(
        data=vge.MultiCircuit(name="child"),
        parent_id=root.node_id,
        position=root.child_count(),
    )

    mv.activate_scenario(child.node_id)
    original_root_diagram_name = root.diagrams[0].name
    child_diagram_name = "Child Diagram Edited"
    mv.current_model.diagrams[0].name = child_diagram_name
    mv.commit_current()

    assert child.diagrams[0].name == child_diagram_name
    assert root.diagrams[0].name == original_root_diagram_name

    mv.activate_scenario(root.node_id)
    assert mv.current_model.diagrams[0].name == original_root_diagram_name

    mv.activate_scenario(child.node_id)
    assert mv.current_model.diagrams[0].name == child_diagram_name
    assert child.diagrams[0].name == child_diagram_name


def test_multiverse_reactivated_child_rebinds_branch_bus_references() -> None:
    """
    Verify that reactivating a child scenario rebinds branch endpoint references to the
    buses of the newly composed current model.

    This protects the root -> child -> root -> child workflow used before running a simulation.
    """
    mv = vge.MultiVerse(_load_grid("lynn5node.gridcal"))
    root = mv.root_nodes[0]
    child = mv.create_node(
        data=vge.MultiCircuit(name="child"),
        parent_id=root.node_id,
        position=root.child_count(),
    )

    mv.activate_scenario(child.node_id)

    bus_from = mv.current_model.buses[0]
    bus_to = mv.current_model.buses[1]
    new_line = vge.Line(name="child_line", bus_from=bus_from, bus_to=bus_to)
    mv.current_model.add_line(new_line)
    mv.commit_current()

    mv.activate_scenario(root.node_id)
    child_grid = mv.activate_scenario(child.node_id)

    child_bus_set = set(child_grid.buses)
    restored_line = next(line for line in child_grid.lines if line.name == "child_line")

    assert restored_line.bus_from in child_bus_set
    assert restored_line.bus_to in child_bus_set


def test_multiverse_get_save_data_contains_consistent_metadata() -> None:
    """
    Verify that get_save_data() emits parent/child metadata consistent with the in-memory tree.

    This guards the serialization contract consumed later by parse_json() and the zip loader.
    """
    mv, root, child, sibling, grandchild = _build_sample_multiverse()

    metadata, model_data = mv.get_save_data()

    assert set(metadata.keys()) == {root.node_id, child.node_id, sibling.node_id, grandchild.node_id}
    assert set(model_data.keys()) == {node.circuit.idtag for node in mv.iter_nodes_depth_first()}

    assert metadata[root.node_id]["parent_id"] is None
    assert metadata[root.node_id]["children"] == [child.node_id, sibling.node_id]
    assert metadata[child.node_id]["parent_id"] == root.node_id
    assert metadata[child.node_id]["children"] == [grandchild.node_id]
    assert metadata[sibling.node_id]["parent_id"] == root.node_id
    assert metadata[sibling.node_id]["children"] == []
    assert metadata[grandchild.node_id]["parent_id"] == child.node_id
    assert metadata[grandchild.node_id]["children"] == []


def test_multiverse_parse_json_initializes_active_state() -> None:
    """
    Verify that parse_json() leaves the loaded multiverse in a usable active state.

    After parsing, the first root should be the current node, and the base/current model
    should point to the root's authoritative circuit.
    """
    mv, root, _, _, _ = _build_sample_multiverse()

    metadata, model_data = mv.get_save_data()

    loaded_mv = vge.MultiVerse(current_model=None)
    loaded_mv.parse_json(model_data, metadata)

    assert loaded_mv.current_node is loaded_mv.root_nodes[0]
    assert loaded_mv.current_node.node_id == root.node_id
    assert loaded_mv.current_model is loaded_mv.root_nodes[0].circuit
    assert loaded_mv.base_model is loaded_mv.root_nodes[0].circuit


def test_multiverse_merge_children_into_parent_updates_current_when_child_was_active() -> None:
    """
    Verify that merging children reassigns the active scenario to the parent when needed.

    If the currently active node is one of the removed children, the multiverse should
    keep a valid active node/model pair by switching to the merge target parent.
    """
    mv = vge.MultiVerse(_load_grid("lynn5node.gridcal"))
    root = mv.root_nodes[0]
    child = mv.create_node(
        data=vge.MultiCircuit(name="child"),
        parent_id=root.node_id,
        position=root.child_count(),
    )
    sibling = mv.create_node(
        data=vge.MultiCircuit(name="sibling"),
        parent_id=root.node_id,
        position=root.child_count(),
    )

    mv.activate_scenario(child.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=10.0, name="child_bus"))

    mv.activate_scenario(sibling.node_id)
    mv.current_model.add_bus(vge.Bus(Vnom=11.0, name="sibling_bus"))
    mv.commit_current()

    mv.activate_scenario(child.node_id)
    mv.merge_children_into_parent(root.node_id)

    assert mv.current_node is root
    assert mv.current_model is root.circuit
    assert _get_bus_by_name(mv.current_model, "child_bus") is not None
    assert _get_bus_by_name(mv.current_model, "sibling_bus") is not None


def test_multiverse_merge_children_into_parent_noop_without_children() -> None:
    """
    Verify that merging a leaf scenario is a no-op and does not corrupt active state.

    This covers the degenerate path where the selected node has no direct children to merge.
    """
    mv = vge.MultiVerse(_load_grid("lynn5node.gridcal"))
    root = mv.root_nodes[0]
    leaf = mv.create_node(
        data=vge.MultiCircuit(name="leaf"),
        parent_id=root.node_id,
        position=root.child_count(),
    )

    leaf_model = mv.activate_scenario(leaf.node_id)
    before_leaf = mv.checkout(leaf)

    result = mv.merge_children_into_parent(leaf.node_id)

    assert result is leaf
    assert mv.current_node is leaf
    _assert_circuits_equal(mv.current_model, leaf_model)
    _assert_circuits_equal(mv.checkout(leaf), before_leaf)
