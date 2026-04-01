import os

from VeraGridEngine.IO.dgs.dgs_to_blocks import export_root_elmcomp_template_to_python


def main() -> None:
    """
    Regenerate the NUACTIS root EMT templates directly from the DGS file.

    :return: None.
    """
    # The demo writes the generated files into the parser sandbox so it does not touch shared working files.
    base_dir: str = os.path.dirname(__file__)
    output_dir: str = os.path.join(base_dir, "generated_templates")
    dgs_path: str = r"C:\Users\andre\Documents\NUACTIS_models.dgs"

    # Each root ElmComp becomes one exported EMT template module.
    master_output_path: str = os.path.join(output_dir, "dgs_nuactis_master_pwm_template.py")
    slave_output_path: str = os.path.join(output_dir, "dgs_nuactis_slave_pwm_template.py")

    master_written_path = export_root_elmcomp_template_to_python(
        dgs_path=dgs_path,
        output_path=master_output_path,
        root_name="MasterPWM_Model",
    )
    slave_written_path = export_root_elmcomp_template_to_python(
        dgs_path=dgs_path,
        output_path=slave_output_path,
        root_name="SlavePWM_Model",
    )

    print("Generated NUACTIS root EMT templates:")
    print(f"  {master_written_path}")
    print(f"  {slave_written_path}")


if __name__ == "__main__":
    main()
