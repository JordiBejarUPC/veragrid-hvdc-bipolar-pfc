"""Debug short circuit to understand voltage results."""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import (
    FaultType, MethodShortCircuit, SolverType
)
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_options import ShortCircuitOptions
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitDriver
from VeraGridEngine.Devices.Aggregation.short_cirtcuit_event import ShortCircuitEvent

grid = gce.open_file('/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid')

# Check bus r_fault values
print("=== Bus fault impedance ===")
for bus in grid.buses[:5]:
    print(f"  {bus.name}: r_fault={bus.r_fault}, x_fault={bus.x_fault}")

# Run PF
pf_options = PowerFlowOptions(solver_type=SolverType.NR, retry_with_other_methods=False)
pf_res = gce.power_flow(grid, options=pf_options)
print(f"\nPF converged, voltage at Bus 7 = {abs(pf_res.voltage[6]):.4f} p.u.")

# Try SC at Bus 7 (mid-network) with sequences method (not sequences_vsc)
fault_bus_idx = 6  # Bus 7
grid._short_circuit_events = []

sc_event = ShortCircuitEvent(
    device=grid.buses[fault_bus_idx],
    fault_type=FaultType.LLLG,
    method=MethodShortCircuit.sequences,
    name="Fault at Bus 7",
    active=True,
)
grid.add_short_circuit_event(sc_event)

sc_driver = ShortCircuitDriver(
    grid=grid,
    options=ShortCircuitOptions(),
    pf_options=pf_options,
    pf_results=pf_res,
    pf_results3ph=None,
)
sc_driver.run()
res_sc = sc_driver.results

print(f"\n=== SC Results (fault at Bus 7, method=sequences) ===")
print(f"voltage1 shape: {res_sc.voltage1.shape}")
print(f"\nBus voltages during fault (positive sequence):")
for i, bus in enumerate(grid.buses):
    if i < res_sc.voltage1.shape[0]:
        v = np.abs(res_sc.voltage1[i, 0])
        print(f"  {bus.name:15s}: |V1| = {v:.4f} p.u.")

# Now try sequences_vsc
print(f"\n\n=== Trying sequences_vsc method ===")
grid._short_circuit_events = []
sc_event2 = ShortCircuitEvent(
    device=grid.buses[fault_bus_idx],
    fault_type=FaultType.LLLG,
    method=MethodShortCircuit.sequences_vsc,
    name="Fault at Bus 7 (vsc)",
    active=True,
)
grid.add_short_circuit_event(sc_event2)

sc_driver2 = ShortCircuitDriver(
    grid=grid,
    options=ShortCircuitOptions(),
    pf_options=pf_options,
    pf_results=pf_res,
    pf_results3ph=None,
)
sc_driver2.run()
res_sc2 = sc_driver2.results

print(f"\nBus voltages during fault (sequences_vsc):")
for i, bus in enumerate(grid.buses):
    if i < res_sc2.voltage1.shape[0]:
        v = np.abs(res_sc2.voltage1[i, 0])
        print(f"  {bus.name:15s}: |V1| = {v:.4f} p.u.")
