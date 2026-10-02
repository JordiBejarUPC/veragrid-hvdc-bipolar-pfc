import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType
from VeraGridEngine.enumerations import ResultTypes

input_grid = 'case39_10_he_v2_bis.gridcal.veragrid'
grid = gce.open_file(input_grid)
Ub = 345

bus_1_dc = next(b for b in grid.buses if b.name == "1" and b.is_dc)

# Buscar el bus DC que se llama "2"
bus_2_dc = next(b for b in grid.buses if b.name == "2" and b.is_dc)

# Buscar el bus DC que se llama "4"
bus_4_dc = next(b for b in grid.buses if b.name == "4" and b.is_dc)

# PFC buses
bus_1s = gce.Bus(name = "Bus_1s",
                 Vnom=Ub,
                 is_dc = True,
                 is_grounded = False)
grid.add_bus(bus_1s)

bus_1t = gce.Bus(name = "Bus_1t",
                 Vnom = Ub,
                 is_dc = True,
                 is_grounded = False)
grid.add_bus(bus_1t)


# PFC
grid.add_pfc(gce.PFC(name = "PFC_0",
                     bus_dc_r = bus_1_dc,
                     bus_dc_s = bus_1s,
                     bus_dc_t = bus_1t,
                     control1=PfcControlType.Ps_dc,
                     control1_val=-20))

#Lines
grid.add_dc_line(gce.DcLine(name = "Line_1s_4_1",
                            bus_from=bus_1s,
                            bus_to=bus_4_dc,
                            r = 0.005,
                            rate=100))

grid.add_dc_line(gce.DcLine(name = "Line_1t_2_1",
                            bus_from=bus_1t,
                            bus_to=bus_2_dc,
                            r = 0.005,
                            rate=100))

print("Grid Buses:")
for i, bus in enumerate(grid.buses):
    print(f"  [{i}] {bus.name} - is_dc: {bus.is_dc}, Vnom: {bus.Vnom}")

print("Grid Lines:")
for line in grid.lines:
    print(f"  - {line.name}")

print("Grid DC Lines:")
for line in grid.dc_lines:
    print(f"  - {line.name}")

options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  use_stored_guess=True,
                                  retry_with_other_methods=False)
results = gce.power_flow(grid, options=options_pf)


print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.mdl(result_type=ResultTypes.PfcV1).get_data_frame())
print(results.mdl(result_type=ResultTypes.PfcV2).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())
gce.save_file(grid=grid, filename="old/aaa.veragrid")

