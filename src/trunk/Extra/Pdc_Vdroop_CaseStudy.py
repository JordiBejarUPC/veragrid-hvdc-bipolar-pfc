import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType
from VeraGridEngine.enumerations import ResultTypes

#Params
Ub = 150
Sb = 100
Rb = (Ub ** 2) / Sb
Ib = Sb / Ub

a = 0.5515/Sb
b = 0.887*(Ib/Sb)
c = 3.77*((Ib**2)/Sb)

Rate =1000 #WF max power generation

r = 0.0224 #ohms/km
d31, d34, d42 = 90, 50, 110 #kms
rlin_31, rlin_34, rlin_42 = (r * d31)/Rb , (r * d34)/Rb, (r * d42)/Rb #p.u.

grid = gce.MultiCircuit(
    name="Pdc_Vdroop_CaseStudy",
    Sbase=Sb
)

#AC buses
bus1_ac = gce.Bus(name = "Bus1_ac_gs1",
                  Vnom = Ub,
                  is_slack=True)
grid.add_bus(bus1_ac)

bus2_ac = gce.Bus(name = "Bus2_ac_gs2",
                  Vnom = Ub,
                  is_slack=True)
grid.add_bus(bus2_ac)

bus3_ac = gce.Bus(name = "Bus3_ac_wf3",
                  Vnom = Ub)
grid.add_bus(bus3_ac)

bus4_ac = gce.Bus(name = "Bus4_ac_wf3",
                  Vnom = Ub)
grid.add_bus(bus4_ac)

#DC buses
bus1_dc = gce.Bus(name = "Bus1_dc",
                  Vnom= Ub,
                  is_dc=True)
grid.add_bus(bus1_dc)

bus2_dc = gce.Bus(name = "Bus2_dc",
                  Vnom= Ub,
                  is_dc=True)
grid.add_bus(bus2_dc)

bus3_dc = gce.Bus(name = "Bus3_dc",
                  Vnom= Ub,
                  is_dc=True)
grid.add_bus(bus3_dc)

bus4_dc = gce.Bus(name = "Bus4_dc",
                  Vnom= Ub,
                  is_dc=True)
grid.add_bus(bus4_dc)

#DC lines
grid.add_dc_line(gce.DcLine(name = "dc_line_31",
                            bus_from=bus3_dc,
                            bus_to=bus1_dc,
                            r=rlin_31))

grid.add_dc_line(gce.DcLine(name = "dc_line_34",
                            bus_from=bus3_dc,
                            bus_to=bus4_dc,
                            r=rlin_34))

grid.add_dc_line(gce.DcLine(name = "dc_line_42",
                            bus_from=bus4_dc,
                            bus_to=bus2_dc,
                            r=rlin_42))

#Generators
#AC Grid Gens
grid.add_generator(bus1_ac, gce.Generator(name='GS1',
                                          vset=1.0))

grid.add_generator(bus2_ac, gce.Generator(name='GS2',
                                          vset=1.0))
#OWF
grid.add_generator(bus3_ac, gce.Generator(name='WF3',
                                          P=102.95))

grid.add_generator(bus4_ac, gce.Generator(name='WF4',
                                          P=102.95))


#VSCs
#On shore VSCs
grid.add_vsc(gce.VSC(name = "VSC_GS_1",
                     bus_from=bus1_dc,
                     bus_to=bus1_ac,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control2=ConverterControlType.Pdc_droop,
                     control1=ConverterControlType.Qac,
                     control1_val=1,
                     control2_val=0.0,
                     control2_droop=1,
                     control2_droop_val=1.0,
                     control2_droop_val_min=0.9,
                     control2_droop_val_max=1.1))

grid.add_vsc(gce.VSC(name = "VSC_GS_2",
                     bus_from=bus2_dc,
                     bus_to=bus2_ac,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control2=ConverterControlType.Pdc_droop,
                     control1=ConverterControlType.Qac,
                     control1_val=1,
                     control2_val=0.0,
                     control2_droop=1,
                     control2_droop_val=-1.0,
                     control2_droop_val_min=-0.9,
                     control2_droop_val_max=-1.1))

#Off-shore VSCs
grid.add_vsc(gce.VSC(name = "VSC_WF_3",
                     bus_from=bus3_dc,
                     bus_to=bus3_ac,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_ac,
                     control2=ConverterControlType.Va_ac,
                     control1_val=1.0,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_WF_4",
                     bus_from=bus4_dc,
                     bus_to=bus4_ac,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_ac,
                     control2=ConverterControlType.Va_ac,
                     control1_val=1.0,
                     control2_val=0.0))

options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  retry_with_other_methods=False)
results = gce.power_flow(grid, options=options_pf)

# gce.save_file(grid=grid, filename="/trunk/old/pfc_BipolarSystem.veragrid")

print('Converged:', results.converged, 'error:', results.error)
print("Iterations:", results.iterations)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())

print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()*Ib*1000)


print(results.mdl(result_type=ResultTypes.VscVdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscIdc).get_data_frame()*Ib*1000)


