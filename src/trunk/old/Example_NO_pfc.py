import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes

#Params
Ub = 220
Sb = 100
Rb = (Ub ** 2) / Sb

Rate =1000 #MW
RateCon = 100 #MW

r = 0.010575 #ohms
d12, d13, d23 = 150, 100, 150 #kms
rlin_12, rlin_13, rlin_23 = (r * d12)/Rb , (r * d13)/Rb, (r * d23)/Rb #p.u.

#Input data
v1_slack = 219.9999946211582/Ub
Pg1 = 273.180155868764 #Must be the result of the power flow
Ps_pfc = 173.307664554204 #MW
Pg2 = 208.140452963783
Pl2 = 320
Pl3 = 160
v1_pfc = -0.441312290299503
v2_pfc = 0.761625531934458

Ub = 220
grid = gce.MultiCircuit(
    name="pfc_example_NOPFC",
)



##AC Grid
#AC buses
#Bus 1
bus1_ac = gce.Bus(name = "Bus1_ac",
                  Vnom = Ub,
                  is_slack=True)
grid.add_bus(bus1_ac)
grid.add_generator(bus1_ac, gce.Generator(name='g1',
                                          vset=1.0,
                                          Snom=Rate))
#Bus 2
bus2_ac = gce.Bus(name = "Bus2_ac",
                  Vnom = Ub,
                  is_slack=True)
grid.add_bus(bus2_ac)
grid.add_generator(bus2_ac, gce.Generator(name='g2',
                                          vset=1.0,
                                          Snom=Rate))

grid.add_load(bus2_ac, gce.Load(name='Pl2',
                                P = Pl2,
                                Q = 0))
#Bus 3
bus3_ac = gce.Bus(name = "Bus3_ac",
                  Vnom = Ub)
grid.add_bus(bus3_ac)
grid.add_load(bus3_ac, gce.Load(name='Pl3',
                                P = Pl3,
                                Q = 0))

##DC Grid
#DC buses
bus1_dc = gce.Bus(name = "Bus1_dc",
                  Vnom = Ub,
                  is_dc = True)
grid.add_bus(bus1_dc)

bus2_dc = gce.Bus(name = "Bus2_dc",
                  Vnom = Ub,
                  is_dc = True)
grid.add_bus(bus2_dc)

bus3_dc = gce.Bus(name = "Bus3_dc",
                  Vnom = Ub,
                  is_dc = True)
grid.add_bus(bus3_dc)

#DC lines
grid.add_dc_line(gce.DcLine(name = "dc_line_12",
                       bus_from=bus1_dc,
                       bus_to=bus2_dc,
                       r=rlin_12))
##PFC to be added here
grid.add_dc_line(gce.DcLine(name = "dc_line_13",
                       bus_from=bus1_dc,
                       bus_to=bus3_dc,
                       r=rlin_13))

grid.add_dc_line(gce.DcLine(name = "dc_line_23",
                       bus_from=bus2_dc,
                       bus_to=bus3_dc,
                       r=rlin_23))

#VSC
grid.add_vsc(gce.VSC(name = "VSC_1",
                     bus_from=bus1_dc,
                     bus_to=bus1_ac,
                     alpha1=0.01,
                     alpha2=0.01,
                     alpha3=0.01,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=-100.0,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_2",
                     bus_from=bus2_dc,
                     bus_to=bus2_ac,
                     alpha1=0.01,
                     alpha2=0.01,
                     alpha3=0.01,
                     control1=ConverterControlType.Vm_dc,
                     control2=ConverterControlType.Qac,
                     control1_val=1.0,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_3",
                     bus_from=bus3_dc,
                     bus_to=bus3_ac,
                     alpha1=0.01,
                     alpha2=0.01,
                     alpha3=0.01,
                     control1=ConverterControlType.Vm_ac,
                     control2=ConverterControlType.Va_ac,
                     control1_val=1.0,
                     control2_val=0.0))


#PowerFlow solver

options_pf = gce.PowerFlowOptions(verbose=2,generate_report=True,retry_with_other_methods=False)
results = gce.power_flow(grid, options=options_pf)


print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFrom).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())







