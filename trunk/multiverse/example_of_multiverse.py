import VeraGridEngine as vg
from VeraGridEngine.IO.file_open import FileOpen

base_grid = vg.open_file("Lynn 5 Bus pv.gridcal")

mv = vg.MultiVerse(base_grid)

root = mv.root_nodes[0]
child = mv.create_node(
    data=vg.MultiCircuit(name="child"),
    parent_id=root.node_id,
    position=root.child_count(),
)

mv.activate_scenario(child.node_id)

new_bus = vg.Bus(Vnom=10, name="new_bus")
mv.current_model.add_bus(new_bus)
mv.commit_current()

vg.save_multiverse(mv=mv, filename="lynn 5 multiverse.veragrid")

# Load back ------------------------------------------------------
loader = FileOpen("lynn 5 multiverse.veragrid")
loader.open()
loaded_mv = loader.multiverse

loaded_root = loaded_mv.root_nodes[0]
loaded_child = loaded_root.children[0]

root_grid = loaded_mv.checkout(loaded_root)
child_grid = loaded_mv.checkout(loaded_child)

def get_bus_by_name(grid, bus_name):

    for bus in grid.buses:
        if bus.name == bus_name:
            return bus
    return None

assert get_bus_by_name(root_grid, "new_bus") is None
assert get_bus_by_name(child_grid, "new_bus") is not None
assert loaded_child.circuit.name == "child"