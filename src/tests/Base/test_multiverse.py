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
    mv, _, _, _, _ = _build_sample_multiverse()

    metadata, model_data = mv.get_save_data()

    loaded_mv = vge.MultiVerse(current_model=None)
    loaded_mv.parse_json(model_data, metadata)

    _assert_same_multiverse(mv, loaded_mv)


def test_multiverse_save_load_roundtrip(tmp_path: Path) -> None:
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
