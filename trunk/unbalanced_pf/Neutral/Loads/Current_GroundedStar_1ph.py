from sympy import factor

import VeraGridEngine.api as gce
from VeraGridEngine import WindingType, ShuntConnectionType, SolverType
import numpy as np
import pandas as pd

logger = gce.Logger()
grid = gce.MultiCircuit()
grid.fBase = 60

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_632 = gce.Bus(name='Bus632', Vnom=4.16, xpos=0, ypos=0)
bus_632.is_slack = True
grid.add_bus(obj=bus_632)
gen = gce.Generator(vset = 1.0)
grid.add_generator(bus = bus_632, api_obj = gen)

bus_634 = gce.Bus(name='Bus634', Vnom=0.48, xpos=200*5, ypos=0)
grid.add_bus(obj=bus_634)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load_634 = gce.Load(Ir1=0.7,
                    Ii1=0.5)
load_634.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_634, api_obj=load_634)

# ----------------------------------------------------------------------------------------------------------------------
# Transformer
# ----------------------------------------------------------------------------------------------------------------------
XFM_1 = gce.Transformer2W(name='XFM-1',
                          bus_from=bus_632,
                          bus_to=bus_634,
                          HV=4.16,
                          LV=0.48,
                          nominal_power=0.5,
                          rate=0.5,
                          r=1.1*2,
                          x=2*2)
XFM_1.conn_f = WindingType.GroundedStar
XFM_1.conn_t = WindingType.GroundedStar
grid.add_transformer2w(XFM_1)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = gce.power_flow3ph(grid=grid, options=gce.PowerFlowOptions(solver_type=SolverType.NR,
                                                             retry_with_other_methods=False))

# ----------------------------------------------------------------------------------------------------------------------
# Show the results
# ----------------------------------------------------------------------------------------------------------------------
pd.set_option("display.float_format", "{:.5f}".format)

print()
print(res.get_voltage_3ph_df())

print("\nConverged? ", res.converged)
print("\nIterations: ", res.iterations)

# print()
# print(res.voltage_A)
# print()
# print(res.voltage_B)
# print()
# print(res.voltage_C)

#
# print("\nSpecified Current Modules:")
# Ispec = np.zeros(3)
# Ispec[0] = abs(0.7 + 0.5j) / (100/3)
# Ispec[1] = abs(0.0 + 0.0j) / (100/3)
# Ispec[2] = abs(0.0 + 0.0j) / (100/3)
# print(Ispec)
#
# I_vg = np.zeros(3)
# I_vg[0] = abs(res.It_A[0])
# I_vg[1] = abs(res.It_B[0])
# I_vg[2] = abs(res.It_C[0])
#
# print("\nCurrent Modules at VeraGrid:")
# print(I_vg)
#
# # ---------------------------------------------------------------------------------------------------------------------
# # OpenDSS
# # ---------------------------------------------------------------------------------------------------------------------
# import dss
# import numpy as np
#
# # Crea el engine
# engine = dss.DSS
#
# # Cargar el circuito
# engine.Text.Command = "ClearAll"
# engine.Text.Command = r"Redirect C:/Users/alexb/OneDrive/eRoots/OpenDSS_Basics/13bus/Neutral/Current_GroundedStar_1ph.dss"
# engine.Text.Command = "Solve"
#
# # Acceder al circuito activo
# circuit = engine.ActiveCircuit
#
# # Lista de buses
# all_buses = circuit.AllBusNames
#
# for bus in all_buses:
#     circuit.SetActiveBus(bus)
#     voltages = circuit.ActiveBus.VMagAngle  # [V1, ang1, V2, ang2, V3, ang3...]
#     U = np.zeros(3)
#
#     # print(f"\nBus {bus}:")
#     for i in range(0, len(voltages), 2):
#         magn = voltages[i]
#         angle = voltages[i+1]
#         fase = ["A", "B", "C"][i//2] if i//2 < 3 else f"F{i//2+1}"
#         # print(f"  Fase {fase}: {magn/(480/np.sqrt(3)):.20f}, {angle:.20f}°")
#
# I_dss = np.zeros(3, dtype=complex)
# Ibranch = np.zeros(3, dtype=complex)
#
# #######################################################################################################################
#
# for idx, load in enumerate(["Load.634a", "Load.634b", "Load.634c"]):
#     circuit.SetActiveElement(load)
#     currents = circuit.ActiveCktElement.CurrentsMagAng
#
#     magn = currents[0]
#     angle = currents[1]
#
#     I_dss[idx] = magn * np.exp(1j * np.deg2rad(angle))
#
#     #print(f"{load}: {magn:.2f} A, {angle:.2f}°")
#
# print("\nCurrent Modules at OpenDSS:")
# I_dss = I_dss / (100*10**6/(np.sqrt(3)*480))
# print(abs(I_dss))
#
# print()
#
# print('Uvg =', abs(res.voltage_A[1]))
# print('Iratio =', abs(I_vg[0]/I_dss[0]))