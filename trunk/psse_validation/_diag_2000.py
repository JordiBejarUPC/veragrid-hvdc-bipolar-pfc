import os
import numpy as np
import pandas as pd
import VeraGridEngine as vg

folder = "data"
name = "ACTIVSg2000.RAW"

excel_name = os.path.join(folder, name + ".xlsx")
excel_ptr = pd.ExcelFile(excel_name)
psse_bus_df = pd.read_excel(excel_ptr, "bus")
psse_lne_df = pd.read_excel(excel_ptr, "branch")
psse_tr_df = pd.read_excel(excel_ptr, "transformers")

Vm_psse = psse_bus_df["Vm"].values
Va_psse = psse_bus_df["Va(rad)"].values

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

vg_bus_df = results.get_bus_df()

Vm_vg = np.abs(results.voltage)
Va_vg = np.angle(results.voltage)

n = grid.get_bus_number()
ntr = grid.get_transformers3w_number()
n_psse = n - ntr
Vm_vg[Vm_vg == 0] = 1

Vm_vg_cmp = Vm_vg[:n_psse]
Va_vg_cmp = Va_vg[:n_psse]

Vm_diff = np.abs(Vm_psse - Vm_vg_cmp)
Va_diff = np.abs(Va_psse - Va_vg_cmp)

diag = pd.DataFrame({
    'number': psse_bus_df['number'].values,
    'name': psse_bus_df['names'].values,
    'area': psse_bus_df['area'].values if 'area' in psse_bus_df.columns else None,
    'Vm_vg': Vm_vg_cmp,
    'Vm_psse': Vm_psse,
    'Vm_diff': Vm_diff,
    'Va_vg': Va_vg_cmp,
    'Va_psse': Va_psse,
    'Va_diff': Va_diff,
})

print("=== Worst 30 Vm buses ===")
print(diag.sort_values('Vm_diff', ascending=False).head(30).to_string(index=False))

print("\n=== Worst 30 Va buses ===")
print(diag.sort_values('Va_diff', ascending=False).head(30).to_string(index=False))

# Look at the distribution - is it clustered or widespread?
print("\nVm_diff stats:")
print(diag['Vm_diff'].describe())

# Count how many generators exist and how many are at Q limits / PV vs PQ mismatch
gens = grid.get_generators()
print(f"\nTotal generators: {len(gens)}")
n_pv = sum(1 for g in gens if g.is_controlled)
print(f"Controlled (PV) generators: {n_pv}")

# print bus control mode breakdown from results
print("\nbus_types counts (numeric circuit):", )
nc = vg.compile_numerical_circuit_at(grid)
vals, counts = np.unique(nc.bus_data.bus_types, return_counts=True)
for v, c in zip(vals, counts):
    print(f"  type={v}: {c}")
