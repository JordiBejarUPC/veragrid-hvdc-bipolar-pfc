#!/usr/bin/env python3
"""
Example: Shunt-connected voltage source (ExternalGrid)
This acts as a voltage source in parallel with the bus
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import ExternalGridMode
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

# Create the circuit
circuit = vge.MultiCircuit(name='Shunt Voltage Source Example')

# Create Bus 1: AC bus with shunt voltage source
bus1 = vge.Bus(
    name='Bus 1',
    Vnom=230.0,           # 230 kV
    is_slack=False        # Not slack - ExternalGrid will enforce voltage
)
circuit.add_bus(bus1)

# Create Bus 2: AC bus with load
bus2 = vge.Bus(
    name='Bus 2', 
    Vnom=230.0
)
circuit.add_bus(bus2)

# Connect buses with a line
line = vge.Line(
    name='Line 1-2',
    bus_from=bus1,
    bus_to=bus2,
    r=1.0,      # Ohms
    x=5.0,      # Ohms
    b=0.0,      # Susceptance
    rate=100.0  # MVA
)
circuit.add_line(line)

# Add shunt voltage source at Bus 1 (like a slack bus or ideal voltage source)
# Mode VD = controls both Vm and Va (slack equivalent)
voltage_source = vge.ExternalGrid(
    name='Voltage Source',
    Vm=1.02,                    # Voltage magnitude (pu)
    Va=0.0,                     # Voltage angle (radians)
    P=1.0,                      # Not used in VD mode
    Q=0.0,                      # Not used in VD mode
    mode=ExternalGridMode.VD    # VD mode = voltage source
)
circuit.add_external_grid(bus1, voltage_source)

# Add load at Bus 2
load = vge.Load(
    name='Load',
    P=50.0,     # MW
    Q=20.0      # MVAr
)
circuit.add_load(bus2, load)

print("=" * 60)
print("CIRCUIT WITH SHUNT VOLTAGE SOURCE:")
print("=" * 60)
print(f"Circuit: {circuit.name}")
print(f"\nBuses: {len(circuit.buses)}")
print(f"External Grids (voltage sources): {len(circuit.external_grids)}")
print(f"Loads: {len(circuit.loads)}")
print(f"Lines: {len(circuit.lines)}")

print(f"\nVoltage Source: {voltage_source.name}")
print(f"  - Mode: {voltage_source.mode.value}")
print(f"  - Vm: {voltage_source.Vm} pu")
print(f"  - Va: {voltage_source.Va} rad")

# Run power flow
print("\n" + "=" * 60)
print("RUNNING POWER FLOW...")
print("=" * 60)

pf_options = vge.PowerFlowOptions(
    solver_type=SolverType.NR,
    verbose=False,
    max_iter=100,
    tolerance=1e-6
)

results = vge.power_flow(grid=circuit, options=pf_options)

# Display results
print("\nPOWER FLOW RESULTS:")
print("-" * 60)

if results.converged:
    print("✓ Converged successfully!")
    
    print("\nBus Voltages:")
    for i, bus in enumerate(circuit.buses):
        vm = np.abs(results.voltage[i])
        va = np.angle(results.voltage[i], deg=True)
        print(f"  {bus.name}: V = {vm:.4f} pu, θ = {va:.2f}°")
    
    print("\nPower Injections:")
    for i, bus in enumerate(circuit.buses):
        p = results.Sbus[i].real
        q = results.Sbus[i].imag
        print(f"  {bus.name}: P = {p:.2f} MW, Q = {q:.2f} MVAr")
    
    # Get external grid flow
    print("\nVoltage Source Output:")
    for eg in circuit.external_grids:
        idx = circuit.external_grids.index(eg)
        p = results.Sbus[0].real  # Bus 1 is where external grid is
        q = results.Sbus[0].imag
        print(f"  {eg.name}: P = {p:.2f} MW, Q = {q:.2f} MVAr")
        print(f"    (Supplying power to maintain V = {eg.Vm} pu)")
    
    print("\nLine Flows:")
    for i, line in enumerate(circuit.lines):
        pf = results.Sf[i].real
        qf = results.Sf[i].imag
        pt = results.St[i].real
        qt = results.St[i].imag
        print(f"  {line.name}:")
        print(f"    From Bus: P = {pf:.2f} MW, Q = {qf:.2f} MVAr")
        print(f"    To Bus:   P = {pt:.2f} MW, Q = {qt:.2f} MVAr")
else:
    print("✗ Power flow did not converge")

print("\n" + "=" * 60)
