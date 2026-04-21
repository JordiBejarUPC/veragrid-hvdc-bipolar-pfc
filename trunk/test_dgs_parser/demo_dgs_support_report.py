from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    build_blkdef_statement_support_report,
    dgs_to_root_block,
    extract_root_slot_block_internal_only,
    summarize_blkdef_support_report,
)


DGS_PATH = r"C:\Users\andre\Documents\DGS_test_type_models.dgs"


def print_report(block_name: str) -> None:
    subgraph = extract_root_slot_block_internal_only(
        dgs_path=DGS_PATH,
        slot_name=block_name,
        root_name="Grid Forming Converter",
    )
    if subgraph is None:
        print(f"Block '{block_name}' not found")
        return

    parsed = subgraph.selected_block.blkdef
    report = build_blkdef_statement_support_report(parsed)
    summary = summarize_blkdef_support_report(report)

    print("=" * 100)
    print(f"Support report for: {parsed.loc_name} (BlkDef ID={parsed.ID})")
    print("=" * 100)
    print(f"inputs    : {parsed.inputs}")
    print(f"outputs   : {parsed.outputs}")
    print(f"states    : {parsed.states}")
    print(f"params    : {parsed.params}")
    print(f"internals : {len(parsed.internals)}")
    print("\nSummary")
    print("-" * 100)
    for key in ["supported", "unsupported", "ignored", "state", "algebraic", "inc", "inc0"]:
        print(f"  {key:<12}: {summary.get(key, 0)}")

    print("\nDetailed lines")
    print("-" * 100)
    for entry in report:
        print(f"[{entry.index:03d}] {entry.status:<11} kind={entry.kind:<10} lhs={repr(entry.lhs):<25} :: {entry.statement}")
        if entry.status != "supported":
            print(f"      detail: {entry.detail}")


def main() -> None:
    dgs_to_root_block(DGS_PATH)
    print_report("Synchronization Loop")
    print()
    print_report("Smart_Admittance")


if __name__ == "__main__":
    main()
