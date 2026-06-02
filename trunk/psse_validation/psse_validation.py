import os
import numpy as np
import pandas as pd
import VeraGridEngine as vg

folder = "data"

for name in [
    # "ACTIVSg2000.RAW",
    # "AU14GenModel.RAW",
    # "ieee9.raw",
    # "IEEE14bus.raw",
    # "IEEE30bus.raw",
    # "NETS-NYPS68Bus.raw",
    # "IEEE118Busv2.raw",
    # "wecc179.raw",
    # "case300.raw",
    "01_A-HP_0-ST_2027_INV_MAX-D_(1).raw",
    "01_A-HP_0-ST_2027_INV_MAX-N_(1).raw",
    "01_A-HP_0-ST_2027_VER_MAX-D_(1).raw",
    "01_A-HP_0-ST_2027_VER_MAX-N_(1).raw",
]:
    # ------------------------------------------------------------------------------------------------------------------
    # Load PSSe
    # ------------------------------------------------------------------------------------------------------------------
    excel_name = os.path.join(folder, name + ".xlsx")
    
    excel_ptr = pd.ExcelFile(excel_name)
    psse_bus_df = pd.read_excel(excel_ptr, "bus")  # , index_col="names")
    psse_lne_df = pd.read_excel(excel_ptr, "branch")
    psse_tr_df = pd.read_excel(excel_ptr, "transformers")
    psse_br_df = pd.concat([psse_lne_df, psse_tr_df])

    Vm_psse = psse_bus_df["Vm"].values
    Va_psse = psse_bus_df["Va(rad)"].values

    # ------------------------------------------------------------------------------------------------------------------
    # Veragrid
    # ------------------------------------------------------------------------------------------------------------------
    grid_name = os.path.join(folder, name)
    grid = vg.open_file(grid_name)

    options = vg.PowerFlowOptions(tolerance=1e-5, retry_with_other_methods=False)
    results = vg.power_flow(grid, options=options)

    vg_bus_df = results.get_bus_df()
    vg_br_df = results.get_branch_df()

    Vm_vg = np.abs(results.voltage)
    Va_vg = np.angle(results.voltage)

    # ------------------------------------------------------------------------------------------------------------------
    # Compare
    # ------------------------------------------------------------------------------------------------------------------

    Vm_ok = np.allclose(Vm_psse, Vm_vg, atol=1e-3)
    Va_ok = np.allclose(Va_psse, Va_vg, atol=1e-3)

    print("*" * 40)
    print(name)
    print("Vm ok", Vm_ok)

    if not Vm_ok:
        # pd.DataFrame({"Vm_veragrid": Vm_vg, "Vm_psse": Vm_psse})
        max_mismatch = np.max(np.abs(Vm_psse - Vm_vg))
        print("\tMax Vm mismatch", max_mismatch)

    print("Va ok", Va_ok)

    if not Va_ok:
        max_mismatch = np.max(np.abs(Va_psse, Va_vg))
        print("\tMax Va mismatch", max_mismatch)
