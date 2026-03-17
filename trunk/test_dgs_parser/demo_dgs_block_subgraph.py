from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    dgs_to_root_block,
    extract_root_slot_block_graphical_tree,
    extract_root_slot_block_internal_only,
    extract_root_slot_block_internal_signal_tree,
)

DGS_PATH = r"C:\Users\andre\Documents\DGS_test_type_models.dgs"
BLOCK_NAME = "Synchronization Loop"
LEAF_BLOCK_NAME = "Smart_Admittance"

def summarize_neighbors(subgraph, parsed_blocks, node_ids):
    rows = list()
    for node_id in sorted(node_ids):
        blk = parsed_blocks[node_id]
        upstream_names = sorted(parsed_blocks[src].blkdef.loc_name for src in subgraph.upstream.get(node_id, set()))
        downstream_names = sorted(parsed_blocks[dst].blkdef.loc_name for dst in subgraph.downstream.get(node_id, set()))
        rows.append((node_id, blk.blkdef.loc_name, upstream_names, downstream_names))
    return rows


def main() -> None:
    result = dgs_to_root_block(DGS_PATH)
    subgraph = extract_root_slot_block_internal_signal_tree(
        dgs_path=DGS_PATH,
        slot_name=BLOCK_NAME,
        root_name="Grid Forming Converter",
    )
    if subgraph is None:
        raise ValueError(f"Could not resolve block '{BLOCK_NAME}'")
    else:
        pass

    print("=" * 100)
    print("DGS -> VeraGrid Block demo")
    print("=" * 100)
    print(f"DGS file           : {DGS_PATH}")
    print(f"Root ElmComp       : {result.root_element.loc_name} (typ_id={result.root_element.typ_id})")
    print(f"Root BlkDef        : {result.root_blkdef.blkdef.loc_name} (ID={result.root_blkdef.blkdef.ID})")
    print(f"Selected sub-block : {subgraph.selected_block.blkdef.loc_name} (ID={subgraph.selected_block.blkdef.ID})")
    print(f"Subgraph nodes     : {len(subgraph.node_ids)}")
    print(f"View block name    : {subgraph.view_block.name}")
    print(f"Child blocks       : {len(subgraph.view_block.children)}")
    print(f"Inputs             : {[v.name for v in subgraph.view_block.in_vars]}")
    print(f"Outputs            : {[v.name for v in subgraph.view_block.out_vars]}")

    print("\nSelected block summary")
    print("-" * 100)
    print(f"inputs      : {subgraph.selected_block.blkdef.inputs}")
    print(f"outputs     : {subgraph.selected_block.blkdef.outputs}")
    print(f"states      : {subgraph.selected_block.blkdef.states}")
    print(f"params      : {subgraph.selected_block.blkdef.params}")
    print(f"internals   : {subgraph.selected_block.blkdef.internals[:20]}")
    print(f"eq parsed   : {len(subgraph.selected_block.state_rhs) + len(subgraph.selected_block.algebraic_rhs)}")
    print(f"unsupported : {len(subgraph.selected_block.unsupported_lines)}")

    print("\nDependency neighborhood")
    print("-" * 100)
    for node_id, name, upstream_names, downstream_names in summarize_neighbors(subgraph, result.parsed_blocks, subgraph.node_ids)[:20]:
        print(f"[{node_id:>3}] {name}")
        print(f"      upstream  : {upstream_names[:6]}")
        print(f"      downstream: {downstream_names[:6]}")

    print("\nHierarchy assessment")
    print("-" * 100)
    non_empty_pblk = [ptr for ptr in result.root_element.pblk if ptr]
    non_empty_pelm = [ptr for ptr in result.root_element.pelm if ptr]
    print(f"root ElmComp pblk non-empty entries : {len(non_empty_pblk)}")
    print(f"root ElmComp pelm non-empty entries : {len(non_empty_pelm)}")
    if len(non_empty_pblk) == 0 and len(non_empty_pelm) == 0:
        print(
            "Conclusion: the explicit ElmComp instance hierarchy is not populated in this DGS export.\n"
            "For this file, the Synchronization Loop can still be recovered as a meaningful\n"
            "subgraph using shared-signal dependencies between BlkDef objects, but not as a\n"
            "strict PowerFactory instance tree. To obtain exact nesting from DGS instances,\n"
            "the export would need non-empty pblk/pelm relationships or additional object tables."
        )
    else:
        print(
            "Conclusion: explicit instance links exist in ElmComp and can be used later to\n"
            "refine the hierarchy beyond the current dependency-based reconstruction."
        )

    leaf_subgraph = extract_root_slot_block_internal_only(
        dgs_path=DGS_PATH,
        slot_name=LEAF_BLOCK_NAME,
        root_name="Grid Forming Converter",
    )

    print("\nLeaf block assessment")
    print("-" * 100)
    if leaf_subgraph is None:
        print(f"Could not resolve leaf block '{LEAF_BLOCK_NAME}'")
    else:
        print(f"Selected leaf block : {leaf_subgraph.selected_block.blkdef.loc_name} (ID={leaf_subgraph.selected_block.blkdef.ID})")
        print(f"Leaf node count     : {len(leaf_subgraph.node_ids)}")
        print(f"Leaf children       : {[child.name for child in leaf_subgraph.view_block.children]}")
        print("Conclusion: Smart_Admittance behaves as a pure code-defined block; it does not require internal signal-tree expansion.")

    graphical_tree = extract_root_slot_block_graphical_tree(
        dgs_path=DGS_PATH,
        slot_name=BLOCK_NAME,
        root_name="Grid Forming Converter",
    )

    print("\nGraphical tree assessment")
    print("-" * 100)
    if graphical_tree is None:
        print(f"Could not resolve graphical tree for '{BLOCK_NAME}'")
    else:
        print(f"Selected graphical block : {graphical_tree.selected_block.blkdef.loc_name}")
        print(f"Graphical child count    : {len(graphical_tree.view_block.children)}")
        print(f"Graphical children       : {[child.name for child in graphical_tree.view_block.children]}")
        print(
            "Conclusion: Synchronization Loop can be reconstructed from the exact DGS graphical\n"
            "objects (BlkRef/BlkFrom/BlkGoto/BlkSum/BlkSig), which removes the spurious\n"
            "external blocks that appeared in the earlier dependency-only reconstruction."
        )


if __name__ == "__main__":
    main()
