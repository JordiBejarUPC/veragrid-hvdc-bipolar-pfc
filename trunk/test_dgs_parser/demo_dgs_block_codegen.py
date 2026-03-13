import os
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    export_named_block_subgraph_to_python,
    export_named_block_subgraph_tree_to_python,
)


DGS_PATH = r"C:\Users\andre\Documents\DGS_test_type_models.dgs"
OUT_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_synchronization_loop_template.py")
OUT_TREE_FILE = os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_synchronization_loop_tree.py")


def main() -> None:
    tree_written = export_named_block_subgraph_tree_to_python(
        dgs_path=DGS_PATH,
        output_path=OUT_TREE_FILE,
        block_name="Synchronization Loop",
    )
    template_written = export_named_block_subgraph_to_python(
        dgs_path=DGS_PATH,
        output_path=OUT_TEMPLATE_FILE,
        block_name="Synchronization Loop",
    )

    print("Generated Python block tree module:")
    print(f"  {tree_written}")
    print("Generated Python EMT template module:")
    print(f"  {template_written}")


if __name__ == "__main__":
    main()
