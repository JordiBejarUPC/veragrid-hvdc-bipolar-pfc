import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType
from VeraGridEngine.enumerations import ResultTypes

#Params
Ub = 150 #kV
Sb = 100 #MW
Rb = (Ub ** 2) / Sb #Ohms
Ib = (Sb / Ub)*1000 #A

rlin_12, rlin_13, rlin_23 = 2,3,1 #ohms

Pg1 = 160 #MW
Pg2 = 80 #MW

I_set_amp = 1000
I_set_pu = I_set_amp / Ib

Vr_set_kv = -1.46985
Vr_set_pu = Vr_set_kv / 150

grid = gce.MultiCircuit(
    name="PFC_System",
)

##AC Grid
#AC buses
#Bus 1
bus1_ac = gce.Bus(name = "Bus1_ac",
                  Vnom = Ub,
                  is_slack=True)
grid.add_bus(bus1_ac)
grid.add_generator(bus1_ac, gce.Generator(name='g1',
                                          vset=1.0))
#Bus 2
bus2_ac = gce.Bus(name = "Bus2_ac",
                  Vnom = Ub,
                  is_slack=True)
grid.add_bus(bus2_ac)
grid.add_generator(bus2_ac, gce.Generator(name='g1',
                                          vset=1.0))

#Bus 3
bus3_ac = gce.Bus(name = "Bus3_ac",
                  Vnom = Ub,
                  is_slack=True)
grid.add_bus(bus3_ac)
grid.add_generator(bus3_ac, gce.Generator(name='g3',
                                          vset=1.0))

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

##Adding the PFC
# PFC buses

busR_dc = gce.Bus(name = "busR_dc",
                  Vnom = Ub,
                  is_dc = True)
grid.add_bus(busR_dc)

busS_dc = gce.Bus(name = "busS_dc",
                  Vnom = Ub,
                  is_dc = True)
grid.add_bus(busS_dc)

grid.add_pfc(gce.PFC(name = "PFC_0",
                     bus_dc_q = bus3_dc,
                     bus_dc_r = busR_dc,
                     bus_dc_s = busS_dc,
                     control1 = PfcControlType.Is_pfc,
                     control1_val = I_set_pu))


#DC lines
grid.add_dc_line(gce.DcLine(name = "dc_line_12",
                       bus_from=bus1_dc,
                       bus_to=bus2_dc,
                       r=rlin_12/Rb))
##PFC to be added here
grid.add_dc_line(gce.DcLine(name = "dc_line_13",
                       bus_from=bus1_dc,
                       bus_to=busS_dc,
                       r=rlin_13/Rb))

grid.add_dc_line(gce.DcLine(name = "dc_line_23",
                       bus_from=bus2_dc,
                       bus_to=busR_dc,
                       r=rlin_23/Rb))

#VSC
grid.add_vsc(gce.VSC(name = "VSC_1",
                     bus_from=bus1_dc,
                     bus_to=bus1_ac,
                     alpha1=0.01,
                     alpha2=0.01,
                     alpha3=0.01,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=-Pg1,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_2",
                     bus_from=bus2_dc,
                     bus_to=bus2_ac,
                     alpha1=0.01,
                     alpha2=0.01,
                     alpha3=0.01,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=-Pg2,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_3",
                     bus_from=bus3_dc,
                     bus_to=bus3_ac,
                     alpha1=0.01,
                     alpha2=0.01,
                     alpha3=0.01,
                     control1=ConverterControlType.Vm_dc,
                     control2=ConverterControlType.Qac,
                     control1_val=1.0,
                     control2_val=0.0))


#PowerFlow solver

options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  use_stored_guess=True)
results = gce.power_flow(grid, options=options_pf)


print('Converged:', results.converged, 'error:', results.error)
print("Iterations:",results.iterations)
print("Time (s):", results.elapsed)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())

print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()*Ib)


print(results.mdl(result_type=ResultTypes.VscVdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscIdc).get_data_frame()*Ib)

#PFC results
print(results.mdl(result_type=ResultTypes.PfcVr).get_data_frame()*Ub)
print(results.mdl(result_type=ResultTypes.PfcVs).get_data_frame()*Ub)

print(results.mdl(result_type=ResultTypes.PfcPB).get_data_frame())

print(results.mdl(result_type=ResultTypes.PfcInternalPowerVr_pfc).get_data_frame())

print(results.mdl(result_type=ResultTypes.PfcInternalPowerVs_pfc).get_data_frame())

print(results.mdl(result_type=ResultTypes.PfcCurrentQ).get_data_frame()*Ib)
print(results.mdl(result_type=ResultTypes.PfcCurrentR).get_data_frame()*Ib)
print(results.mdl(result_type=ResultTypes.PfcCurrentS).get_data_frame()*Ib)




