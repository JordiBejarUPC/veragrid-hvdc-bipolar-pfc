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
        control_q=False,
        ignore_single_node_islands=True,
        initialize_angles=True,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        orthogonalize_controls=False,
        apply_temperature_correction=False
    )
    driver = vg.PowerFlowDriver(grid, options=options)
    driver.run()
    results = driver.results

    # Surface engine warnings/errors (e.g. control-aware -> limited-support fallback)
    if len(driver.logger):
        print("\n  --- Power flow log ---")
        driver.logger.print()
        print()

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

        # --------------------------------------------------------------------------------------------------------------
        # Map which PSSe bus numbers are directly connected to a switch or a 3-winding transformer.
        # The PSSe bus number (psse_bus.I) is stored in bus.code by the parser.
        # --------------------------------------------------------------------------------------------------------------
        def _bus_num(bus):
            """Return the PSSe bus number stored in bus.code, or None if not convertible."""
            if bus is None:
                return None
            try:
                return int(bus.code)
            except (TypeError, ValueError):
                return None

        switch_buses = set()
        for sw in grid.get_switches():
            for b in (_bus_num(sw.bus_from), _bus_num(sw.bus_to)):
                if b is not None:
                    switch_buses.add(b)

        tr3w_buses = set()
        for tr in grid.get_transformers3w():
            for b in (_bus_num(tr.bus1), _bus_num(tr.bus2), _bus_num(tr.bus3)):
                if b is not None:
                    tr3w_buses.add(b)

        def _connected_to(bus_number):
            """Classify a bus by what reducible/3W device it touches."""
            num = int(bus_number)
            on_switch = num in switch_buses
            on_tr3w = num in tr3w_buses
            if on_switch and on_tr3w:
                return "switch+tr3w"
            if on_switch:
                return "switch"
            if on_tr3w:
                return "tr3w"
            return "none"

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

            all_bus_numbers = psse_bus_df['number'].values
            connected_to = np.array([_connected_to(b) for b in all_bus_numbers])

            diag = pd.DataFrame({
                'bus_name':               psse_bus_df['names'].values,
                'connected_to':           connected_to,
                f'{label}_vg ({unit})': val_vg,
                f'{label}_psse ({unit})': val_psse,
                f'{label}_diff':          diff,
            })# .sort_values(f'{label}_diff', ascending=False)

            print(f"\n  --- All {label} buses ---")
            print(diag.to_string(index=False))

            # Breakdown of failing buses by the device they are connected to
            counts = pd.Series(connected_to).value_counts()
            print(f"\n {label} buses by connection: "
                  + ", ".join(f"{k}={v}" for k, v in counts.items()))

    else:
        print("*" * 40)
        print(name)
        print("Didn't converge")
