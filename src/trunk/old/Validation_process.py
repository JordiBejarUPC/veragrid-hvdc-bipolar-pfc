import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType
from VeraGridEngine.enumerations import ResultTypes

#Params
Ub = 150
Sb = 100
Rb = (Ub ** 2) / Sb

rlin_12, rlin_13, rlin_23 = 2,3,1 #ohms

Pg1 = 160 #MW
Pg2 = 80 #MW

grid = gce.MultiCircuit(
    name="Validation_grid"
)
#Buses and generators
bus1 = gce.Bus(name = "Bus1",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus1)

grid.add_generator(bus1, gce.Generator(name='g1',
                                       P = Pg1,
                                       power_factor=1,
                                       is_controlled=False))

bus2 = gce.Bus(name = "Bus2",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus2)

grid.add_generator(bus2, gce.Generator(name='g2',
                                       P = Pg2,
                                       power_factor=1,
                                       is_controlled=False))

bus3 = gce.Bus(name = "Bus3",
               Vnom = Ub,
               is_dc = True,
               is_slack = True)
grid.add_bus(bus3)
grid.add_generator(bus3, gce.Generator(name='g3',
                                       vset=1.0))

# PFC buses
bus_r = gce.Bus(name = "Bus_r",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus_r)

bus_s = gce.Bus(name = "Bus_s",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus_s)

bus_t = gce.Bus(name = "Bus_t",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus_t)

# PFC
grid.add_pfc(gce.PFC(name = "PFC_0",
                     bus_dc_r = bus_r,
                     bus_dc_s = bus_s,
                     bus_dc_t = bus_t,
                     control1=PfcControlType.Ps_dc,
                     control1_val=220))

#Lines
grid.add_dc_line(gce.DcLine(name = "Line_12",
                            bus_from=bus1,
                            bus_to=bus2,
                            r = rlin_12/Rb))

grid.add_dc_line(gce.DcLine(name = "Line_13",
                            bus_from=bus1,
                            bus_to=bus_t,
                            r = rlin_13/Rb))

grid.add_dc_line(gce.DcLine(name = "Line_23",
                            bus_from=bus2,
                            bus_to=bus_s,
                            r = rlin_23/Rb))

grid.add_dc_line(gce.DcLine(name = "Line_r3",
                            bus_from=bus_r,
                            bus_to=bus3,
                            r = rlin_12/Rb))

options_pf = gce.PowerFlowOptions(verbose=0, generate_report=True, retry_with_other_methods=False)
results = gce.power_flow(grid, options=options_pf)


print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.mdl(result_type=ResultTypes.PfcV1).get_data_frame())
print(results.mdl(result_type=ResultTypes.PfcV2).get_data_frame())
