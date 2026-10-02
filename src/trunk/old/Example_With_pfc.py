import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType
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
Pl1 = 320
Pl2 = 160
v1_pfc = 0.5
v2_pfc = 0.761625531934458

Ub = 220
grid = gce.MultiCircuit(
    name="pfc_example_with_PFC",
)



##AC Grid
#AC buses
#Bus 0
bus01 = gce.Bus(name = "Bus01",
                Vnom = Ub,
                is_slack=True)
grid.add_bus(bus01)
grid.add_generator(bus01, gce.Generator(name='g0',
                                        vset=1.0,
                                        Snom=Rate))

bus0 = gce.Bus(name = "Bus0",
               Vnom = Ub)
grid.add_bus(bus0)

#Bus 1
bus1 = gce.Bus(name = "Bus1",
               Vnom = Ub,
               is_slack=True)
grid.add_bus(bus1)
grid.add_generator(bus1, gce.Generator(name='g1',
                                       vset=1.0,
                                       Snom=Rate))

grid.add_load(bus1, gce.Load(name='Pl1',
                             P = Pl1,
                             Q = 0))
#Bus 2
bus2 = gce.Bus(name = "Bus2",
               Vnom = Ub)
grid.add_bus(bus2)
grid.add_load(bus2, gce.Load(name='Pl2',
                             P = Pl2,
                             Q = 0))

##DC Grid
#DC buses
bus3 = gce.Bus(name = "Bus3",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus3)

bus4 = gce.Bus(name = "Bus4",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus4)

bus5 = gce.Bus(name = "Bus5",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus5)

# bus6 = gce.Bus(name = "Bus6",
#                Vnom = Ub,
#                is_dc = True)
# grid.add_bus(bus6)

bus7 = gce.Bus(name = "Bus7",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus7)

bus8 = gce.Bus(name = "Bus8",
               Vnom = Ub,
               is_dc = True)
grid.add_bus(bus8)

grid.add_line(gce.Line(name = "Line_01",
                       bus_from=bus01,
                       bus_to=bus0,
                       r = rlin_12))

grid.add_pfc(gce.PFC(name = "PFC_0",
                     bus_dc_r = bus3,
                     bus_dc_s = bus7,
                     bus_dc_t = bus8,
                     control1=PfcControlType.V1_pfc,
                     control1_val=0.001431))


grid.add_dc_line(gce.DcLine(name = "dc_line_74",
                       bus_from=bus7,
                       bus_to=bus4,
                       r=rlin_13))

grid.add_dc_line(gce.DcLine(name = "dc_line_45",
                       bus_from=bus4,
                       bus_to=bus5,
                       r=rlin_13))

grid.add_dc_line(gce.DcLine(name = "dc_line_85",
                       bus_from=bus8,
                       bus_to=bus5,
                       r=rlin_23))

#VSC
grid.add_vsc(gce.VSC(name = "VSC_0",
                     bus_from=bus3,
                     bus_to=bus0,
                     alpha1=0.01,
                     alpha2=0.01,
                     alpha3=0.01,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=-100,
                     control2_val=0))

grid.add_vsc(gce.VSC(name = "VSC_1",
                     bus_from=bus4,
                     bus_to=bus1,
                     alpha1=0.01,
                     alpha2=0.01,
                     alpha3=0.01,
                     control1=ConverterControlType.Vm_dc,
                     control2=ConverterControlType.Qac,
                     control1_val=1.0,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_2",
                     bus_from=bus5,
                     bus_to=bus2,
                     alpha1=0.01,
                     alpha2=0.01,
                     alpha3=0.01,
                     control1=ConverterControlType.Vm_ac,
                     control2=ConverterControlType.Va_ac,
                     control1_val=1.0,
                     control2_val=0.0))


# #PowerFlow solver

options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  use_stored_guess=True,
                                  retry_with_other_methods=False)
results = gce.power_flow(grid, options=options_pf)


# print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())
print(results.mdl(result_type=ResultTypes.PfcV1).get_data_frame())
print(results.mdl(result_type=ResultTypes.PfcV2).get_data_frame())







