import os
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    export_named_block_subgraph_to_python,
    export_named_block_subgraph_tree_to_python,
    export_root_slot_block_graphical_template_to_python,
    export_root_slot_block_graphical_tree_to_python,
)


DGS_PATH = r"C:\Users\andre\Documents\DGS_test_type_models.dgs"
OUT_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_synchronization_loop_template.py")
OUT_TREE_FILE = os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_synchronization_loop_tree.py")
SMART_OUT_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_smart_admittance_template.py")
SMART_OUT_TREE_FILE = os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_smart_admittance_tree.py")
PI_HOLD_OUT_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_pi_with_hold_and_reset_template.py")
PROTECTION_OUT_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_protection_template.py")


def main() -> None:
    tree_written = export_named_block_subgraph_tree_to_python(
        dgs_path=DGS_PATH,
        output_path=OUT_TREE_FILE,
        block_name="Synchronization Loop",
    )
    graphical_tree_written = export_root_slot_block_graphical_tree_to_python(
        dgs_path=DGS_PATH,
        output_path=os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_synchronization_loop_graphical_tree.py"),
        slot_name="Synchronization Loop",
    )
    graphical_template_written = export_root_slot_block_graphical_template_to_python(
        dgs_path=DGS_PATH,
        output_path=os.path.join(os.path.dirname(__file__), "generated_templates", "dgs_synchronization_loop_graphical_template.py"),
        slot_name="Synchronization Loop",
    )
    template_written = export_named_block_subgraph_to_python(
        dgs_path=DGS_PATH,
        output_path=OUT_TEMPLATE_FILE,
        block_name="Synchronization Loop",
    )
    smart_tree_written = export_named_block_subgraph_tree_to_python(
        dgs_path=DGS_PATH,
        output_path=SMART_OUT_TREE_FILE,
        block_name="Smart_Admittance",
    )
    smart_template_written = export_named_block_subgraph_to_python(
        dgs_path=DGS_PATH,
        output_path=SMART_OUT_TEMPLATE_FILE,
        block_name="Smart_Admittance",
    )
    pi_hold_template_written = export_named_block_subgraph_to_python(
        dgs_path=DGS_PATH,
        output_path=PI_HOLD_OUT_TEMPLATE_FILE,
        block_name="PI with hold and reset",
    )
    protection_template_written = export_named_block_subgraph_to_python(
        dgs_path=DGS_PATH,
        output_path=PROTECTION_OUT_TEMPLATE_FILE,
        block_name="Protection",
    )

    print("Generated functional block tree module:")
    print(f"  {tree_written}")
    print("Generated Python graphical block tree module:")
    print(f"  {graphical_tree_written}")
    print("Generated Python graphical EMT template module:")
    print(f"  {graphical_template_written}")
    print("Generated Python EMT template module:")
    print(f"  {template_written}")
    print("Generated Smart_Admittance block tree module:")
    print(f"  {smart_tree_written}")
    print("Generated Smart_Admittance EMT template module:")
    print(f"  {smart_template_written}")
    print("Generated PI with hold/reset EMT template module:")
    print(f"  {pi_hold_template_written}")
    print("Generated Protection EMT template module:")
    print(f"  {protection_template_written}")


if __name__ == "__main__":
    main()
