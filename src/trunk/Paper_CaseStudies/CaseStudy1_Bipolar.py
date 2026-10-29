"""
Case Study 1: Bipolar System
- This script sets up and runs a power flow analysis for a bipolar HVDC system.
- To run this case study, ensure that the VeraGridEngine library is installed and accessible in your Python environment.
- For simulating different scenarios, you can modify the parameters such as Vdc, Pdc_vsc3, and Pdc_vsc4 in the script. (by default a balanced scenario is set)
"""

import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.enumerations import ResultTypes
import math
import pandas as pd

#Params
Ub = 525 #kV
Sb = 100 #MW
Rb = (Ub ** 2) / Sb #Ohms
Ib = (Sb / Ub) #kA

a = 0.5515/Sb
b = 0.887*(Ib/Sb)
c = 3.77*((Ib**2)/Sb)

dcr_20 = 1.7241e-8 #ohm*m
A = 2.5e-3 #m
r_ohm_km =  (dcr_20/A)*1000 # ohm/km (Extracted from https://cse.cigre.org/cse-n032/enhanced-real-time-multi-terminal-hvdc-power-system-benchmark-models-with-performance-evaluation-strategies.pdf?tx_site_pdfdownload%5BaccessToken%5D=dummyToken&tx_site_pdfdownload%5Baction%5D=download&tx_site_pdfdownload%5Bcontroller%5D=Pdf&tx_site_pdfdownload%5BpdfProject%5D=11954&cHash=1af3d0cbb45897c40b04a67731cbd063)
r_ohm = r_ohm_km*100 # ohm for a 100km line
r = (r_ohm/Rb) #p.u. for a 100km line
print(r_ohm_km)
print(r_ohm)

#VSC Control Parameters
Vdc = 1.1 #p.u.
Pdc_vsc3 = -1000 #MW
Pdc_vsc4 = -1000 #MW


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
               Vm0=0.000000001,
               Va0=0.000000001)
grid.add_bus(bus4)

bus5 = gce.Bus(name = "Bus5",
               Vnom=Ub,
               is_dc=True,
               Vm0=0.000000001,
               Va0=0.000000001)
grid.add_bus(bus5)

bus6 = gce.Bus(name = "Bus6",
               Vnom=Ub,
               is_dc=True,
               is_grounded=True,
               Vm0=1.0,
               Va0=math.pi)
grid.add_bus(bus6)

bus7 = gce.Bus(name = "Bus7",
               Vnom=Ub,
               is_dc=True,
               Vm0=1.0,
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
                     control1_val=Vdc,
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
                     control1_val=-Vdc,
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
                     control1_val=Pdc_vsc3,
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
                     control1_val=Pdc_vsc4,
                     control2_val=0.0))

options_pf = gce.PowerFlowOptions(verbose=1,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  tolerance=1e-8,
                                  use_stored_guess=False)
results = gce.power_flow(grid, options=options_pf)

#gce.save_file(grid=grid, filename="old/BipolarSystem_Times.veragrid")

print('Converged:', results.converged, 'error:', results.error)
print("Iterations:",results.iterations)
print("Time (s):", results.elapsed)
print(results.get_bus_df())
print(results.get_branch_df())
print(results.St_vsc)
print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromNegative).get_data_frame())
print(results.mdl(result_type=ResultTypes.VscPowerFromPositive).get_data_frame())

print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame())
print(results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()*Ib*1000)

print(results.mdl(result_type=ResultTypes.VscVdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscIdc).get_data_frame()*Ib*1000)