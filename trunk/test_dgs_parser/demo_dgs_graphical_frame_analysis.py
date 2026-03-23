from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import BlkSum
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    build_graphic_node_index,
    extract_root_slot_block_graphical_tree,
    get_blk_sum_signal_specs,
    get_blk_sum_slot_active_mode,
    get_blk_sum_slot_raw_mode,
)


DGS_PATH = r"C:\Users\andre\Documents\DGS_test_type_models.dgs"
SLOTS = ["Synchronization Loop", "Q/Vac droop"]


def print_slot_frame(slot_name: str, circuit: DgsCircuit) -> None:
    """
    Print the full graphical frame reconstruction of one DGS slot.

    :param slot_name: Root slot name.
    :param circuit: Parsed DGS circuit.
    """
    tree = extract_root_slot_block_graphical_tree(
        dgs_path=DGS_PATH,
        slot_name=slot_name,
        root_name="Grid Forming Converter",
    )
    if tree is None:
        raise ValueError(f"Could not resolve graphical frame for '{slot_name}'")

    node_by_id = build_graphic_node_index(circuit)

    print("=" * 120)
    print(f"Graphical Frame: {slot_name}")
    print("=" * 120)
    print(f"Children ({len(tree.view_block.children)}): {[child.name for child in tree.view_block.children]}")
    print(f"Connections ({len(tree.connections)}):")
    for item in tree.connections:
        if item.source_kind == "block_output":
            print(
                f"  {item.consumer_node_id}:{item.consumer_input_name} <- "
                f"{item.source_node_id}:{item.source_output_name}"
            )
        else:
            print(f"  {item.consumer_node_id}:{item.consumer_input_name} <- root:{item.source_root_name}")

    print("\nSum blocks:")
    for node_id in tree.child_node_ids:
        node = node_by_id.get(node_id)
        if not isinstance(node, BlkSum):
            continue
        input_terms, outputs = get_blk_sum_signal_specs(node, circuit)
        rendered_terms: list[str] = list()
        for signal_name, coefficient in input_terms:
            if coefficient >= 0.0:
                rendered_terms.append(f"+ {signal_name}")
            else:
                rendered_terms.append(f"- {signal_name}")
        rhs = " ".join(rendered_terms).lstrip("+ ") if rendered_terms else "0"
        print(f"  {node.loc_name} ({node_id})")
        print(f"    raw modes     : i0={get_blk_sum_slot_raw_mode(node, 0)}, i1={get_blk_sum_slot_raw_mode(node, 1)}, i2={get_blk_sum_slot_raw_mode(node, 2)}, i3={get_blk_sum_slot_raw_mode(node, 3)}")
        print(f"    active modes  : i0={get_blk_sum_slot_active_mode(node, 0)}, i1={get_blk_sum_slot_active_mode(node, 1)}, i2={get_blk_sum_slot_active_mode(node, 2)}, i3={get_blk_sum_slot_active_mode(node, 3)}")
        print(f"    equation : {outputs[0]} = {rhs}")

    print(
        "\nMath note: BlkSum in DGS only carries slot sign/activation flags (iInput0..iInput3 and their :act), "
        "not arbitrary gains. Any multiplier must live in another block such as K/C/PT1, not in BlkSum itself."
    )
    print("")


def main() -> None:
    """
    Run the graphical frame analysis for the configured DGS slots.
    """
    circuit = DgsCircuit()
    circuit.parse_dgs(DGS_PATH)

    for slot_name in SLOTS:
        print_slot_frame(slot_name=slot_name, circuit=circuit)


if __name__ == "__main__":
    main()
