import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes
import math
import numpy as np

#Params
Ub = 345 #kV
Sb = 100 #MW
Rb = (Ub ** 2) / Sb #Ohms
Ib = (Sb / Ub) #A

a = 0.5515/Sb
b = 0.887*(Ib/Sb)
c = 3.77*((Ib**2)/Sb)

r = 0.052


grid = gce.MultiCircuit(
    name="Bipolar_system",
    Sbase=Sb
)

bus1 = gce.Bus(name = "Bus1",
               Vnom = Ub,
               is_slack=True)
grid.add_bus(bus1)

#DC buses
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
               Va0=math.pi)
grid.add_bus(bus4)

bus5 = gce.Bus(name = "Bus5",
               Vnom=Ub,
               is_dc=True,
               Va0=math.pi)
grid.add_bus(bus5)

bus6 = gce.Bus(name = "Bus6",
               Vnom=Ub,
               is_dc=True,
               is_grounded=True,
               Vm0=0.01,
               Va0=0.01)
grid.add_bus(bus6)

bus7 = gce.Bus(name = "Bus7",
               Vnom=Ub,
               is_dc=True,
               Vm0=1,
               Va0=math.pi)
grid.add_bus(bus7)

bus8 = gce.Bus(name = "Bus8",
               Vnom=Ub,
               is_slack=True)
grid.add_bus(bus8)

#Generators
grid.add_generator(bus1, gce.Generator(name='g1',
                                       vset=1.0))

grid.add_generator(bus8, gce.Generator(name='g8',
                                       vset=1))


#DC_lines
grid.add_dc_line(gce.DcLine(name = "dc_line_23",
                            bus_from=bus2,
                            bus_to=bus3,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_45",
                            bus_from=bus4,
                            bus_to=bus5,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_0",
                            bus_from=bus6,
                            bus_to=bus7,
                            r=r))


#VSC
grid.add_vsc(gce.VSC(name="VSC_1",
                     bus_to=bus1,
                     bus_from=bus2,
                     bus_dc_n=bus6,
                     rate = 30,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_dc,
                     control1_val=1.1,
                     control2=ConverterControlType.Qac,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name="VSC_2",
                     bus_to=bus1,
                     bus_from=bus4,
                     bus_dc_n=bus6,
                     rate = 30,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_dc,
                     control1_val=-1.1,
                     control2=ConverterControlType.Qac,
                     control2_val=0.0))

grid.add_vsc(gce.VSC(name = "VSC_3",
                     bus_from=bus3,
                     bus_to=bus8,
                     bus_dc_n=bus7,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=-100,
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
                     control1_val=-0.9*100,
                     control2_val=0.0))

options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  tolerance=1e-6,
                                  use_stored_guess=True)
results = gce.power_flow(grid, options=options_pf)

# gce.save_file(grid=grid, filename="BipolarSystem.veragrid")


print('Converged:', results.converged, 'error:', results.error)
print(results.iterations)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())

print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame())
print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()*Ib*1000)

print(results.mdl(result_type=ResultTypes.VscIf).get_data_frame()*Ib*1000)

print(results.mdl(result_type=ResultTypes.VscV).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())

df_bus = results.get_bus_df()
df_branch = results.get_branch_df()

Pt_dc_line_0 = df_branch.loc['dc_line_0', 'Pt']
Pp_dc_line_23 = df_branch.loc['dc_line_23', 'Pf']
Pp_dc_line_45 = df_branch.loc['dc_line_45', 'Pf']
Vm_bus_7 = df_bus.loc['Bus7', 'Vm']
Vm_bus_2 = df_bus.loc['Bus2', 'Vm']
Vm_bus_4 = df_bus.loc['Bus4', 'Vm']

# Metallic return current
I_metallic_return = (Pt_dc_line_0*10e6) / (Vm_bus_7* 10e3 * Ub)

I_positive_pole = (Pp_dc_line_23*10e6) / (Vm_bus_2* 10e3 * Ub)

I_negative_pole = (Pp_dc_line_45*10e6) / (Vm_bus_4* 10e3 * Ub)

print("I_metallic_return:",I_metallic_return)
print("I_positive_pole:",I_positive_pole)
print("I_negative_pole:",I_negative_pole)