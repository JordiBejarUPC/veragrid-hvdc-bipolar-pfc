import VeraGridEngine as vg

base_grid = vg.open_file("Lynn 5 Bus pv.gridcal")

mv = vg.MultiVerse(base_grid)


parent_node = mv.root_nodes[0]
child_node = mv.create_node(
    data=vg.MultiCircuit(name="child"),
    parent_id=parent_node.node_id,
    position=parent_node.child_count()
)
mv.activate_scenario(child_node.node_id)

# add new stuff
new_bus = vg.Bus(Vnom=10, name="new_bus")
mv.current_node.circuit.add_bus(new_bus)

# save
vg.save_multiverse(mv=mv, filename="lynn 5 multiverse.veragrid")
