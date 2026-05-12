"""Debug sequences_vsc: set fault impedance on buses and retry."""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import FaultType, MethodShortCircuit, SolverType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_options import ShortCircuitOptions
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitDriver
from VeraGridEngine.Devices.Aggregation.short_cirtcuit_event import ShortCircuitEvent

grid = gce.open_file('/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid')

# Set a small fault resistance on all buses (near-bolted fault)
for bus in grid.buses:
    if not bus.is_dc:
        bus.r_fault = 1e-6  # Very small, near zero
        bus.x_fault = 1e-6

# Set min_ac_voltage for testing
for vsc in grid.vsc_devices:
    vsc.min_ac_voltage = 0.85

# Run PF
pf_options = PowerFlowOptions(solver_type=SolverType.NR, retry_with_other_methods=False)
pf_res = gce.power_flow(grid, options=pf_options)
print(f"PF converged, V at Bus 7 = {abs(pf_res.voltage[6]):.4f}")

# SC at Bus 7 with sequences_vsc
fault_bus_idx = 6
grid._short_circuit_events = []
sc_event = ShortCircuitEvent(
    device=grid.buses[fault_bus_idx],
    fault_type=FaultType.LLLG,
    method=MethodShortCircuit.sequences_vsc,
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

print(f"\n=== SC Results (sequences_vsc, fault at Bus 7) ===")
for i, bus in enumerate(grid.buses):
    if i < res_sc.voltage1.shape[0]:
        v = np.abs(res_sc.voltage1[i, 0])
        print(f"  {bus.name:15s}: |V1| = {v:.4f} p.u.")

print(f"\n=== VSC Results ===")
for i, vsc in enumerate(grid.vsc_devices):
    pfp = res_sc.vsc_Pfp[i, 0] if i < res_sc.vsc_Pfp.shape[0] else 0
    st = res_sc.vsc_St[i, 0] if i < res_sc.vsc_St.shape[0] else 0
    load = res_sc.vsc_loading[i, 0] if i < res_sc.vsc_loading.shape[0] else 0
    print(f"  {vsc.name:20s}: Pfp={pfp:+.4f} MW, St={st:.4f}, loading={load*100:.1f}%")
