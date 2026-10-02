import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes
import math

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
               is_slack=False)
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
               is_slack=True)
grid.add_bus(bus4)

#Generators
grid.add_generator(bus1, gce.Generator(name='g1',
                                       vset=1.0))

grid.add_generator(bus4, gce.Generator(name='ga',
                                       vset=1))

#DC_lines
grid.add_dc_line(gce.DcLine(name = "dc_line_23",
                            bus_from=bus2,
                            bus_to=bus3,
                            r=r))

#VSC
grid.add_vsc(gce.VSC(name="VSC_1",
                     bus_to=bus1,
                     bus_from=bus2,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Vm_dc,
                     control1_val=1,
                     control2=ConverterControlType.Vm_ac,
                     control2_val=1))

grid.add_vsc(gce.VSC(name = "VSC_3",
                     bus_from=bus3,
                     bus_to=bus4,
                     alpha1=a,
                     alpha2=b,
                     alpha3=c,
                     control1=ConverterControlType.Pdc,
                     control2=ConverterControlType.Qac,
                     control1_val=-100,
                     control2_val=0.0))


options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  use_stored_guess=False,
                                  tolerance=1e-9,
                                  )
results = gce.power_flow(grid, options=options_pf)

print('Converged:', results.converged, 'error:', results.error)
print("Iterations:", results.iterations)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())

print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()*Ib*1000)


print(results.mdl(result_type=ResultTypes.VscVdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscIdc).get_data_frame()*Ib*1000)