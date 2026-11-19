import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType
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
    Sbase=Sb)

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
               Vm0=0.001,
               Va0=0.001)
grid.add_bus(bus6)

# Unbalanced #
# bus7 = gce.Bus(name = "Bus7",
#                Vnom=Ub,
#                is_dc=True,
#                Vm0=1,
#                Va0=math.pi)
# grid.add_bus(bus7)

# Symetrical #
bus7 = gce.Bus(name = "Bus7",
               Vnom=Ub,
               is_dc=True,
               Vm0=0.0000000001,
               Va0=0.0000000001)
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
                is_dc=True)
grid.add_bus(bus10)

bus11 = gce.Bus(name = "Bus11",
                Vnom=Ub,
                is_dc=True,
                Va0=math.pi)
grid.add_bus(bus11)

bus12 = gce.Bus(name = "Bus12",
                Vnom=Ub,
                is_dc=True,
                Va0=math.pi)
grid.add_bus(bus12)

#Generators
grid.add_generator(bus1, gce.Generator(name='g1',
                                       vset=1.0))

grid.add_generator(bus8, gce.Generator(name='g8',
                                       vset=1.0))

#DC_lines
grid.add_dc_line(gce.DcLine(name = "dc_line_93",
                            bus_from=bus9,
                            bus_to=bus3,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_103",
                            bus_from=bus10,
                            bus_to=bus3,
                            r=r))

# grid.add_dc_line(gce.DcLine(name = "dc_line_45",
#                             bus_from=bus4,
#                             bus_to=bus5,
#                             r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_115",
                            bus_from=bus11,
                            bus_to=bus5,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_125",
                            bus_from=bus12,
                            bus_to=bus5,
                            r=r))

grid.add_dc_line(gce.DcLine(name = "dc_line_0",
                            bus_from=bus6,
                            bus_to=bus7,
                            r=r))

#PFC
grid.add_pfc(gce.PFC(name="PFC",
                     bus_dc_r=bus2,
                     bus_dc_s=bus9,
                     bus_dc_t=bus10,
                     control1=PfcControlType.Ps_dc,
                     control1_val=50))

grid.add_pfc(gce.PFC(name="PFC",
                     bus_dc_r=bus4,
                     bus_dc_s=bus11,
                     bus_dc_t=bus12,
                     control1=PfcControlType.Ps_dc,
                     control1_val=50))

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
                     control1_val=-100,
                     control2_val=0.0))

options_pf = gce.PowerFlowOptions(verbose=0,
                                  generate_report=True,
                                  retry_with_other_methods=False,
                                  tolerance=1e-6,
                                  use_stored_guess=True)
results = gce.power_flow(grid, options=options_pf)

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

# gce.save_file(grid=grid, filename="BipolarSystem.veragrid")

"""
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

print(results.mdl(result_type=ResultTypes.VscPdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.VscVdc).get_data_frame())

print(results.mdl(result_type=ResultTypes.PfcV1).get_data_frame())
print(results.mdl(result_type=ResultTypes.PfcV2).get_data_frame())

print(results.mdl(result_type=ResultTypes.PfcV1).get_data_frame()*Ub*1000)
print(results.mdl(result_type=ResultTypes.PfcV2).get_data_frame()*Ub*1000)

# 1. Guardamos los DataFrames ORIGINALES en por unidad (p.u.), sin tocar nada
df_I_pu  = results.mdl(result_type=ResultTypes.BranchActiveCurrentFrom).get_data_frame()
df_V1_pu = results.mdl(result_type=ResultTypes.PfcV1).get_data_frame()
df_V2_pu = results.mdl(result_type=ResultTypes.PfcV2).get_data_frame()

# 2. Extraemos los valores crudos en p.u.
i_93_pu  = df_I_pu.loc['dc_line_93'].iloc[0]
i_103_pu = df_I_pu.loc['dc_line_103'].iloc[0]
i_115_pu = df_I_pu.loc['dc_line_115'].iloc[0]
i_125_pu = df_I_pu.loc['dc_line_125'].iloc[0]

v1_pfc_1_pu = df_V1_pu.iloc[0, 0]
print(f"PFC_1 V1:  {v1_pfc_1_pu * Ub * 1000:.30f}")
v2_pfc_1_pu = df_V2_pu.iloc[0, 0]
print(f"PFC_1 V2:  {v2_pfc_1_pu * Ub * 1000:.30f}")
v1_pfc_2_pu = df_V1_pu.iloc[1, 0]
print(f"PFC_2 V1:  {v1_pfc_2_pu * Ub * 1000:.30f}")
v2_pfc_2_pu = df_V2_pu.iloc[1, 0]
print(f"PFC_2 V2:  {v2_pfc_2_pu * Ub * 1000:.30f}")


# 3. Realizamos TODAS las operaciones matemáticas en p.u.
potencia_93_pu  = v1_pfc_1_pu * i_93_pu
potencia_103_pu = v2_pfc_1_pu * i_103_pu
PB_PFC_1_pu     = potencia_93_pu - potencia_103_pu

potencia_115_pu = v1_pfc_2_pu * i_115_pu
potencia_125_pu = v2_pfc_2_pu * i_125_pu
PB_PFC_2_pu     = potencia_115_pu - potencia_125_pu

# 4. Definimos los factores de conversión al final
# Si V_base está en kV e I_base en kA, el producto directo (Ub * Ib) da la potencia en MW.
# Para obtener la potencia en Watts (W): (Ub * 1000) * (Ib * 1000) = Ub * Ib * 1,000,000
base_W  = Ub * Ib * 1000000
base_MW = Ub * Ib  # O usa tu base fija (ej: 100) si estás usando la base del sistema

# 5. Mostramos los resultados escalándolos en el mismo print

print(f"PFC V1 por dc_line_93 (W):  {potencia_93_pu * base_W:.6f}")
print(f"PFC V2 por dc_line_103 (W): {potencia_103_pu * base_W:.6f}")
print(f"PB_PFC_1 (en Watts):        {PB_PFC_1_pu * base_W:.6f} W")
print(f"PB_PFC_1 (en MW):           {PB_PFC_1_pu * base_MW:.12f} MW")

print("-" * 40)

print(f"PFC V1 por dc_line_115 (W):  {potencia_115_pu * base_W:.6f}")
print(f"PFC V2 por dc_line_125 (W): {potencia_125_pu * base_W:.6f}")
print(f"PB_PFC_2 (en Watts):        {PB_PFC_2_pu * base_W:.6f} W")
print(f"PB_PFC_2 (en MW):           {PB_PFC_2_pu * base_MW:.12f} MW")
"""



# df_bus = results.get_bus_df()
# df_branch = results.get_branch_df()
#
# Pt_dc_line_0 = df_branch.loc['dc_line_0', 'Pt']
# Pp_dc_line_23 = df_branch.loc['dc_line_23', 'Pf']
# Pp_dc_line_45 = df_branch.loc['dc_line_45', 'Pf']
# Vm_bus_7 = df_bus.loc['Bus7', 'Vm']
# Vm_bus_2 = df_bus.loc['Bus2', 'Vm']
# Vm_bus_4 = df_bus.loc['Bus4', 'Vm']
#
# # Metallic return current
# I_metallic_return = (Pt_dc_line_0*10e6) / (Vm_bus_7* 10e3 * Ub)
#
# I_positive_pole = (Pp_dc_line_23*10e6) / (Vm_bus_2* 10e3 * Ub)
#
# I_negative_pole = (Pp_dc_line_45*10e6) / (Vm_bus_4* 10e3 * Ub)
#
# print("I_metallic_return:",I_metallic_return)
# print("I_positive_pole:",I_positive_pole)
# print("I_negative_pole:",I_negative_pole)

