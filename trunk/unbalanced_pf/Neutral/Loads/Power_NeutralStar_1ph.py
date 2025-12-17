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

bus_634 = gce.Bus(name='Bus634', Vnom=4.16, xpos=200*5, ypos=0)
grid.add_bus(obj=bus_634)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load_634 = gce.Load(P1=0.7,
                    Q1=0.5)
load_634.conn = ShuntConnectionType.NeutralStar
grid.add_load(bus=bus_634, api_obj=load_634)

# ----------------------------------------------------------------------------------------------------------------------
# Line
# ----------------------------------------------------------------------------------------------------------------------
z_nabc = np.array([
    [0.2735 + 1j*0.8143, 0.0173 + 1j*0.0509, 0.0173 + 1j*0.0509, 0.0173 + 1j*0.0509],
    [0.0173 + 1j*0.0509, 0.3465 + 1j*1.0179, 0.1560 + 1j*0.5017, 0.1580 + 1j*0.4236],
    [0.0173 + 1j*0.0509, 0.1560 + 1j*0.5017, 0.3375 + 1j*1.0478, 0.1535 + 1j*0.3849],
    [0.0173 + 1j*0.0509, 0.1580 + 1j*0.4236, 0.1535 + 1j*0.3849, 0.3414 + 1j*1.0348]
], dtype=complex) / 1.60934  # Ω/km

y_nabc = np.array([
    [1j*6.1541, -1j*1.8918, -1j*2.0022, -1j*2.2602],
    [-1j*1.8918, 1j*6.2998, -1j*1.9958, -1j*1.2595],
    [-1j*2.0022, -1j*1.9958, 1j*5.9597, -1j*0.7417],
    [-1j*2.2602, -1j*1.2595, -1j*0.7417, 1j*5.6386]
], dtype=complex) / (10**6) / 1.60934  # S/km

configuration = gce.create_known_abc_overhead_template(name='4 wire line',
                                                       z_nabc=z_nabc,
                                                       ysh_nabc=y_nabc,
                                                       phases=np.array([0, 1, 2, 3]),
                                                       Vnom=4.16,
                                                       frequency=60)
grid.add_overhead_line(configuration)

line = gce.Line(bus_from=bus_632,
                bus_to=bus_634,
                length=2000 * 0.0003048)
line.apply_template(configuration, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line)

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
# print()
# print(res.get_current_3ph_df())

print("\nConverged? ", res.converged)
print("\nIterations: ", res.iterations)

# print()
# print(res.voltage_A)
# print()
# print(res.voltage_B)
# print()
# print(res.voltage_C)

# print("\nSpecified Current Modules:")
# Ispec = np.zeros(1)
# Ispec[0] = abs(0.7 + 0.5j) / (100/3)
# print(Ispec)
#
# print("\nCurrent Modules at VeraGrid:")
# Ivg = np.zeros(1)
# Ivg[0] = abs(res.It_B[0])
# print(Ivg)
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
# engine.Text.Command = r"Redirect C:/Users/alexb/OneDrive/eRoots/OpenDSS_Basics/13bus/Neutral/Current_NeutralStar_1ph_abcn.dss"
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
#         # print(f"  Fase {fase}: {magn/(4160/np.sqrt(3)):.20f}, {angle:.20f}°")
#
# Idss = np.zeros(1, dtype=complex)
#
# #######################################################################################################################
#
# for idx, load in enumerate(["Load.634a"]):
#     circuit.SetActiveElement(load)
#     currents = circuit.ActiveCktElement.CurrentsMagAng
#
#     magn = currents[0]
#     angle = currents[1]
#
#     Idss[idx] = magn * np.exp(1j * np.deg2rad(angle))
#
#     #print(f"{load}: {magn:.2f} A, {angle:.2f}°")
#
# print("\nCurrent Modules at OpenDSS:")
# Idss = Idss / (100*10**6/(np.sqrt(3)*4160))
# print(abs(Idss))