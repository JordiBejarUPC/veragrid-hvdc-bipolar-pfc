import dss
import numpy as np

# Crea el engine
engine = dss.DSS

# Cargar el circuito
engine.Text.Command = "ClearAll"
engine.Text.Command = r"Redirect C:/Users/alexb/OneDrive/eRoots/OpenDSS_Basics/13bus/Neutral/Current_GroundedStar_3ph.dss"
engine.Text.Command = "Solve"

# Acceder al circuito activo
circuit = engine.ActiveCircuit

# Lista de buses
all_buses = circuit.AllBusNames

for bus in all_buses:
    circuit.SetActiveBus(bus)
    voltages = circuit.ActiveBus.VMagAngle  # [V1, ang1, V2, ang2, V3, ang3...]
    U = np.zeros(3)

    # print(f"\nBus {bus}:")
    for i in range(0, len(voltages), 2):
        magn = voltages[i]
        angle = voltages[i+1]
        fase = ["A", "B", "C"][i//2] if i//2 < 3 else f"F{i//2+1}"
        print(f"  Fase {fase}: {magn/(480/np.sqrt(3)):.20f}, {angle:.20f}°")

I = np.zeros(3, dtype=complex)
Ibranch = np.zeros(3, dtype=complex)

#######################################################################################################################

for idx, load in enumerate(["Load.634a", "Load.634b", "Load.634c"]):
    circuit.SetActiveElement(load)
    currents = circuit.ActiveCktElement.CurrentsMagAng

    magn = currents[0]
    angle = currents[1]

    I[idx] = magn * np.exp(1j * np.deg2rad(angle))

    #print(f"{load}: {magn:.2f} A, {angle:.2f}°")

print("\nCurrent OpenDSS:")
I = I / (100*10**6/(np.sqrt(3)*480))
print(abs(I))