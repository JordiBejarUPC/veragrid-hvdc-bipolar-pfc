import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes
import numpy as np

#Params
Ub = 345
Sb = 100
Rb = (Ub ** 2) / Sb
Ib = Sb / Ub

r = 0.052

# LossA LossB  LossCrec LossCinv
# 0.5515 0.887  5.77    3.77

a = 0.5515/Sb
b = 0.887*(Ib/Sb)
c = 3.77*((Ib**2)/Sb)

grid = gce.MultiCircuit(
    name="Bipolar_system",
    Sbase=Sb
)

bus1 = gce.Bus(name = "Bus1",
               Vnom = Ub,
               is_slack=True)
grid.add_bus(bus1)

bus2 = gce.Bus(name = "Bus2",
               Vnom=Ub,
               is_dc=True)
grid.add_bus(bus2)

bus3 = gce.Bus(name = "Bus3",
               Vnom=Ub,
               is_dc=True)
grid.add_bus(bus3)

bus4 = gce.Bus(name = "Bus4",
               Vnom=Ub,
               is_dc=True,
               Vm0=1.01,
               Va0=3.14)
grid.add_bus(bus4)

bus5 = gce.Bus(name = "Bus5",
               Vnom=Ub,
               is_dc=True,
               Va0=3.14)
grid.add_bus(bus5)

bus6 = gce.Bus(name = "Bus6",
               Vnom=Ub,
               is_dc=True,
               is_grounded=True,
               Vm0=0.000000001,
               Va0=0.01)
grid.add_bus(bus6)

bus7 = gce.Bus(name = "Bus7",
               Vnom=Ub,
               is_dc=True,
               Vm0=0.0001,
               Va0=0.01)
grid.add_bus(bus7)


bus8 = gce.Bus(name = "Bus8",
               Vnom=Ub,
               is_slack=True)
grid.add_bus(bus8)

bus9 = gce.Bus(name = "Bus9",
               Vnom=Ub,
               is_dc=True)
grid.add_bus(bus9)

bus10 = gce.Bus(name = "Bus10",
               Vnom=Ub,
               is_dc=True,
               Vm0=0.0001,
               Va0=0.01)
grid.add_bus(bus10)

bus11 = gce.Bus(name = "Bus11",
                Vnom=Ub,
                is_dc=True,
                Va0=3.14)
grid.add_bus(bus11)

bus12 = gce.Bus(name = "Bus12",
               Vnom=Ub,
               is_dc=True,
               Vm0=0.0001,
               Va0=0.01)
grid.add_bus(bus12)

bus13 = gce.Bus(name = "Bus13",
                Vnom=Ub,
                is_dc=True,
                Va0=3.14)
grid.add_bus(bus13)

bus14 = gce.Bus(name = "Bus14",
                Vnom = Ub)
grid.add_bus(bus14)

#Generators
grid.add_generator(bus1, gce.Generator(name='g1',
                                       vset=1.0))

grid.add_generator(bus8, gce.Generator(name='g8',
                                       vset=1.0))

# grid.add_generator(bus14, gce.Generator(name='g14',
#                                         vset=1.0))

grid.add_load(bus14, gce.Load(name='Pl14',
                              P=40))

#DC_lines
#Line pole +
grid.add_dc_line(gce.DcLine(name = "dc_line_29",
                            bus_from=bus2,
                            bus_to=bus9,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_93",
                            bus_from=bus9,
                            bus_to=bus3,
                            r=r))

#Lines pole -
grid.add_dc_line(gce.DcLine(name = "dc_line_411",
                            bus_from=bus4,
                            bus_to=bus11,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_115",
                            bus_from=bus11,
                            bus_to=bus5,
                            r=r))

#Lines return cable
grid.add_dc_line(gce.DcLine(name = "dc_line_610",
                            bus_from=bus6,
                            bus_to=bus10,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_107",
                            bus_from=bus10,
                            bus_to=bus7,
                            r=r))

#Unbalanced monopolar line
grid.add_dc_line(gce.DcLine(name = "dc_line_1012",
                            bus_from=bus10,
                            bus_to=bus12,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_1113",
                            bus_from=bus11,
                            bus_to=bus13,
                            r=r))

#VSC
grid.add_vsc(gce.VSC(name = "VSC_1",
                     bus_from=bus2,
                     bus_to=bus1,
                     bus_dc_n=bus6,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_dc,
                     control2=ConverterControlType.Qac,
                     control1_val=1,
                     control2_val=0))

grid.add_vsc(gce.VSC(name = "VSC_2",
                     bus_from=bus4,
                     bus_to=bus1,
                     bus_dc_n=bus6,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_dc,
                     control2=ConverterControlType.Qac,
                     control1_val=-1.01,
                     control2_val=0))

grid.add_vsc(gce.VSC(name = "VSC_3",
                     bus_from=bus3,
                     bus_to=bus8,
                     bus_dc_n=bus7,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=19.6,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_4",
                     bus_from=bus5,
                     bus_to=bus8,
                     bus_dc_n=bus7,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=-2.8,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_5",
                     bus_from=bus13,
                     bus_to=bus14,
                     bus_dc_n=bus12,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_ac,
                     control2=ConverterControlType.Va_ac,
                     control1_val=1,
                     control2_val=0))


options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  use_stored_guess=True)
results = gce.power_flow(grid, options=options_pf)

print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())

