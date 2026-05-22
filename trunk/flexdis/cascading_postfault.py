"""
Post-fault cascading analysis.

Approach:
  1. Run healthy PF (baseline)
  2. Run SC at fault bus → get fault voltages
  3. Based on fault voltages + min_ac_voltage, determine which VSCs trip
  4. Disable tripped VSCs → run post-fault PF → get post-fault voltage profile
  5. This shows the actual steady-state impact of the cascading disconnection

This is the realistic sequence: fault occurs → VSCs trip → fault clears →
system reaches a new steady state WITHOUT the tripped VSCs.
"""
import sys
sys.path.insert(0, '/Users/josep/Desktop/VeraGrid/src')

import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import FaultType, MethodShortCircuit, SolverType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_options import ShortCircuitOptions
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitDriver
from VeraGridEngine.Devices.Events.short_cirtcuit_event import ShortCircuitEvent

FILEPATH = '/Users/josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'
FAULT_BUS = 8  # Bus 9
PF_OPTIONS = PowerFlowOptions(solver_type=SolverType.NR, retry_with_other_methods=False)


def run_analysis(min_ac_v, label):
    """Run full pre-fault → SC → post-fault analysis."""
    print(f"\n{'='*60}")
    print(f"  {label}: min_ac_voltage = {min_ac_v} p.u.")
    print(f"{'='*60}")

    # --- 1. Healthy PF ---
    grid = gce.open_file(FILEPATH)
    for vsc in grid.vsc_devices:
        vsc.min_ac_voltage = min_ac_v
    pf_res = gce.power_flow(grid, options=PF_OPTIONS)

    healthy_v = {}
    for i, bus in enumerate(grid.buses):
        if not bus.is_dc:
            healthy_v[bus.name] = float(np.abs(pf_res.voltage[i]))

    print(f"  Healthy PF: V range [{min(healthy_v.values()):.4f}, {max(healthy_v.values()):.4f}]")

    # --- 2. SC at fault bus ---
    grid2 = gce.open_file(FILEPATH)
    for vsc in grid2.vsc_devices:
        vsc.min_ac_voltage = min_ac_v

    pf_res2 = gce.power_flow(grid2, options=PF_OPTIONS)
    grid2._short_circuit_events = []
    sc_event = ShortCircuitEvent(
        device=grid2.buses[FAULT_BUS], fault_type=FaultType.LLLG,
        method=MethodShortCircuit.sequences_vsc, active=True,
        r_fault=1e-6, x_fault=1e-6)
    grid2.add_short_circuit_event(sc_event)

    sc_driver = ShortCircuitDriver(grid=grid2, options=ShortCircuitOptions(),
        pf_options=PF_OPTIONS, pf_results=pf_res2, pf_results3ph=None)
    sc_driver.run()
    res_sc = sc_driver.results

    fault_v = {}
    for i, bus in enumerate(grid2.buses):
        if not bus.is_dc:
            fault_v[bus.name] = float(np.abs(res_sc.voltage1[i, 0]))

    # --- 3. Determine which VSCs trip ---
    tripped_vscs = []
    for vsc in grid2.vsc_devices:
        v_ac = fault_v[vsc.bus_to.name]
        if v_ac < min_ac_v:
            tripped_vscs.append(vsc.name)
            print(f"  VSC {vsc.name} TRIPS: V={v_ac:.4f} < {min_ac_v}")

    surviving = [v.name for v in grid2.vsc_devices if v.name not in tripped_vscs]
    print(f"  Tripped: {len(tripped_vscs)}/4, Surviving: {surviving}")

    # --- 4. Post-fault PF with tripped VSCs at zero power ---
    grid3 = gce.open_file(FILEPATH)
    from VeraGridEngine.enumerations import ConverterControlType
    for vsc in grid3.vsc_devices:
        if vsc.name in tripped_vscs:
            vsc.control1_val = 0.0  # No active power
            vsc.control2_val = 0.0  # No reactive power

    pf_res3 = gce.power_flow(grid3, options=PF_OPTIONS)

    postfault_v = {}
    for i, bus in enumerate(grid3.buses):
        if not bus.is_dc:
            postfault_v[bus.name] = float(np.abs(pf_res3.voltage[i]))

    print(f"  Post-fault PF: V range [{min(postfault_v.values()):.4f}, {max(postfault_v.values()):.4f}]")

    # --- 5. Compute voltage differences ---
    print(f"\n  Bus          Healthy  During-SC  Post-fault  Delta(H-PF)")
    print(f"  {'-'*62}")
    vsc_bus_names = {v.bus_to.name for v in grid2.vsc_devices}
    for bus_name in sorted(healthy_v.keys(), key=lambda x: int(x.replace('Bus ', ''))):
        h = healthy_v[bus_name]
        f = fault_v[bus_name]
        p = postfault_v[bus_name]
        delta = h - p
        marker = ' *' if bus_name in vsc_bus_names else ''
        if abs(delta) > 0.0005 or bus_name in vsc_bus_names:
            print(f"  {bus_name:<12s} {h:.4f}    {f:.4f}     {p:.4f}      {delta:+.4f}{marker}")

    return {
        'label': label,
        'min_ac_v': min_ac_v,
        'healthy': healthy_v,
        'fault': fault_v,
        'postfault': postfault_v,
        'tripped': tripped_vscs,
        'n_tripped': len(tripped_vscs),
    }


# Run all 3 scenarios
results = {}
for min_v, label in [(0.85, 'A'), (0.50, 'B'), (0.10, 'C')]:
    results[label] = run_analysis(min_v, f'Scenario {label}')

# Summary
print(f"\n{'='*60}")
print(f"  POST-FAULT VOLTAGE COMPARISON")
print(f"{'='*60}")
print(f"  Bus          Healthy  Post-A    Post-B    Post-C")
print(f"  {'-'*55}")
bus_names = sorted(results['A']['healthy'].keys(), key=lambda x: int(x.replace('Bus ', '')))
for bn in bus_names:
    h = results['A']['healthy'][bn]
    pa = results['A']['postfault'][bn]
    pb = results['B']['postfault'][bn]
    pc = results['C']['postfault'][bn]
    if abs(pa - pc) > 0.0005:
        print(f"  {bn:<12s} {h:.4f}    {pa:.4f}    {pb:.4f}    {pc:.4f}")

# Save
with open('/Users/josep/Desktop/VeraGrid/trunk/flexdis/docs/postfault_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved.")
