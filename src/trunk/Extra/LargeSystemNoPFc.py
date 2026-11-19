import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ResultTypes

input_grid = 'case39_10_he_v3.gridcal'
grid = gce.open_file(input_grid)
print("Grid Buses:")
for i, bus in enumerate(grid.buses):
    print(f"  [{i}] {bus.name} - is_dc: {bus.is_dc}, Vnom: {bus.Vnom}")


print("AC Grid Lines:")
for line in grid.lines:
    print(f" {line.name}")

print("DC Grid Lines:")
for line in grid.dc_lines:
    print(f" {line.name}")

options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  retry_with_other_methods=False)
results = gce.power_flow(grid, options=options_pf)


print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())