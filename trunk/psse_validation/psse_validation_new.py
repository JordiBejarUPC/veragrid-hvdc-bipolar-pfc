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
    # "01_A-HP_0-ST_2027_INV_MAX-N_(1).raw",
    # "01_A-HP_0-ST_2027_VER_MAX-D_(1).raw",
    # "01_A-HP_0-ST_2027_VER_MAX-N_(1).raw",
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
    # VeraGrid
    # ------------------------------------------------------------------------------------------------------------------
    grid_name = os.path.join(folder, name)
    grid = vg.open_file(grid_name, options=vg.FileOpenOptions(file_type=vg.FileType.PSSE_raw))

    options = vg.PowerFlowOptions(
        tolerance=1e-5,
        solver_type=vg.SolverType.NR,
        retry_with_other_methods=False,
        initialize_angles=True,
        ignore_single_node_islands=True,
        control_q=True,
        # verbose = 2 # delete line once singular jacobian problem solved
    )
    results = vg.power_flow(grid, options=options)

    vg_bus_df = results.get_bus_df()
    vg_br_df = results.get_branch_df()

    Vm_vg = np.abs(results.voltage)
    Va_vg = np.angle(results.voltage)

    # ------------------------------------------------------------------------------------------------------------------
    # Compare
    # ------------------------------------------------------------------------------------------------------------------
    if results.converged:
        ntr = grid.get_transformers3w_number()
        n = grid.get_bus_number()
        n_psse = n - ntr
        Vm_vg[Vm_vg == 0] = 1  # PSS/e garbage where disconnected nodes keep voltage = 1

        Vm_vg_cmp = Vm_vg[:n_psse]
        Va_vg_cmp = Va_vg[:n_psse]
        vg_bus_df_cmp = vg_bus_df.iloc[:n_psse]
    

        Vm_diff = np.abs(Vm_psse - Vm_vg_cmp)
        Va_diff = np.abs(Va_psse - Va_vg_cmp)
        Vm_ok = (Vm_diff <= 1e-3).all()
        Va_ok = (Va_diff <= 1e-3).all()

        print("*" * 40)
        print(name)
        print(f"Vm ok: {Vm_ok}  |  max diff: {Vm_diff.max():.2e}  |  buses > 1e-3: {(Vm_diff > 1e-3).sum()}/{n_psse}")
        print(f"Va ok: {Va_ok}  |  max diff: {Va_diff.max():.2e}  |  buses > 1e-3: {(Va_diff > 1e-3).sum()}/{n_psse}")

        for label, diff, val_psse, val_vg, unit in [
            ("Vm", Vm_diff, Vm_psse, Vm_vg_cmp, "pu"),
            ("Va", Va_diff, Va_psse, Va_vg_cmp, "rad"),
        ]:
            bad_mask = diff > 1e-3
            if not bad_mask.any():
                continue

            diag = pd.DataFrame({
                'bus_number':             psse_bus_df['number'].values[bad_mask],
                'bus_name':               psse_bus_df['names'].values[bad_mask],
                f'{label}_psse ({unit})': val_psse[bad_mask],
                f'{label}_vg ({unit})':   val_vg[bad_mask],
                f'{label}_diff':          diff[bad_mask],
                'P_vg (MW)':              vg_bus_df_cmp['P'].values[bad_mask],
                'Q_vg (MVAr)':            vg_bus_df_cmp['Q'].values[bad_mask],
            }).sort_values(f'{label}_diff', ascending=False)

            print(f"\n  --- Failing {label} buses ---")
            print(diag.to_string(index=False))

            # Branch flows adjacent to the worst-mismatch bus
            worst_bus_num = int(diag.iloc[0]['bus_number'])
            adj_psse = psse_br_df[(psse_br_df['f'] == worst_bus_num) | (psse_br_df['t'] == worst_bus_num)]
            if not adj_psse.empty:
                print(f"\n  PSSE branch flows adjacent to worst bus {worst_bus_num}:")
                print(adj_psse[['names', 'f', 't', 'Pf', 'Qf', 'Pt', 'Qt']].to_string(index=False))
                adj_vg = vg_br_df[vg_br_df.index.isin(adj_psse['names'])]
                if not adj_vg.empty:
                    print(f"\n  VG branch flows adjacent to worst bus {worst_bus_num}:")
                    print(adj_vg[['Pf', 'Qf', 'Pt', 'Qt']].to_string())
    else:
        print("*" * 40)
        print(name)
        print("Didn't converge")
