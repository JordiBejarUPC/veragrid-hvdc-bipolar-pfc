"""
Post-fault cascading analysis at 75% renewable penetration.

Same structure as cascading_postfault.py: pre-fault PF, SC at Bus 9, identify
tripped VSCs, then post-fault PF with tripped VSCs at zero power.

VSC P_ac and rates are scaled in-memory so the .veragrid file is not modified.
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
RESULTS_PATH = '/Users/josep/Desktop/VeraGrid/trunk/flexdis/docs/postfault_results_75pct.json'
FAULT_BUS = 7  # Bus 8 (0-indexed); 3/2/1 disconnect spread at 75% penetration
PF_OPTIONS = PowerFlowOptions(solver_type=SolverType.NR, retry_with_other_methods=False)

TARGET_PENETRATION = 0.75
BASELINE_VSC_POWER = {
    "VSC Bus 18": 0.20,
    "VSC Bus 22": 0.15,
    "VSC Bus 25": 0.30,
    "VSC Bus 33": 0.15,
}


def compute_scaled_vsc_power(grid):
    total_load = sum(l.P for l in grid.loads)
    baseline_total = sum(BASELINE_VSC_POWER.values())
    target_total = TARGET_PENETRATION * total_load
    scale = target_total / baseline_total
    return {name: round(p * scale, 4) for name, p in BASELINE_VSC_POWER.items()}, total_load


def configure(grid, min_ac_v, vsc_power, vsc_rate):
    for vsc in grid.vsc_devices:
        vsc.min_ac_voltage = min_ac_v
        vsc.control1_val = -vsc_power[vsc.name]
        vsc.rate = vsc_rate


def run_analysis(min_ac_v, label, vsc_power, vsc_rate):
    print(f"\n{'='*60}")
    print(f"  {label}: min_ac_voltage = {min_ac_v} p.u.")
    print(f"{'='*60}")

    grid = gce.open_file(FILEPATH)
    configure(grid, min_ac_v, vsc_power, vsc_rate)
    pf_res = gce.power_flow(grid, options=PF_OPTIONS)

    healthy_v = {}
    for i, bus in enumerate(grid.buses):
        if not bus.is_dc:
            healthy_v[bus.name] = float(np.abs(pf_res.voltage[i]))
    print(f"  Healthy PF: V range [{min(healthy_v.values()):.4f}, {max(healthy_v.values()):.4f}]")

    grid2 = gce.open_file(FILEPATH)
    configure(grid2, min_ac_v, vsc_power, vsc_rate)
    pf_res2 = gce.power_flow(grid2, options=PF_OPTIONS)
    grid2._short_circuit_events = []
    sc_event = ShortCircuitEvent(
        device=grid2.buses[FAULT_BUS],
        fault_type=FaultType.LLLG,
        method=MethodShortCircuit.sequences_vsc,
        active=True,
        r_fault=1e-6,
        x_fault=1e-6,
    )
    grid2.add_short_circuit_event(sc_event)
    sc_driver = ShortCircuitDriver(grid=grid2, options=ShortCircuitOptions(),
        pf_options=PF_OPTIONS, pf_results=pf_res2, pf_results3ph=None)
    sc_driver.run()
    res_sc = sc_driver.results

    fault_v = {}
    for i, bus in enumerate(grid2.buses):
        if not bus.is_dc:
            fault_v[bus.name] = float(np.abs(res_sc.voltage1[i, 0]))

    tripped_vscs = []
    for vsc in grid2.vsc_devices:
        v_ac = fault_v[vsc.bus_to.name]
        if v_ac < min_ac_v:
            tripped_vscs.append(vsc.name)
            print(f"  VSC {vsc.name} TRIPS: V={v_ac:.4f} < {min_ac_v}")

    surviving = [v.name for v in grid2.vsc_devices if v.name not in tripped_vscs]
    print(f"  Tripped: {len(tripped_vscs)}/4, Surviving: {surviving}")

    grid3 = gce.open_file(FILEPATH)
    configure(grid3, min_ac_v, vsc_power, vsc_rate)
    for vsc in grid3.vsc_devices:
        if vsc.name in tripped_vscs:
            vsc.control1_val = 0.0
            vsc.control2_val = 0.0

    pf_res3 = gce.power_flow(grid3, options=PF_OPTIONS)
    postfault_v = {}
    for i, bus in enumerate(grid3.buses):
        if not bus.is_dc:
            postfault_v[bus.name] = float(np.abs(pf_res3.voltage[i]))
    print(f"  Post-fault PF: V range [{min(postfault_v.values()):.4f}, {max(postfault_v.values()):.4f}]")

    return {
        'label': label,
        'min_ac_v': min_ac_v,
        'healthy': healthy_v,
        'fault': fault_v,
        'postfault': postfault_v,
        'tripped': tripped_vscs,
        'n_tripped': len(tripped_vscs),
    }


def main():
    probe = gce.open_file(FILEPATH)
    vsc_power, total_load = compute_scaled_vsc_power(probe)
    vsc_rate = round(1.5 * max(vsc_power.values()), 2)
    print(f"Total load: {total_load:.4f} MW")
    print(f"Scaled VSC injections: {vsc_power}")
    print(f"Per-VSC rate: {vsc_rate} MVA")

    results = {}
    for min_v, label in [(0.85, 'A'), (0.50, 'B'), (0.10, 'C')]:
        results[label] = run_analysis(min_v, f'Scenario {label}', vsc_power, vsc_rate)

    payload = {
        'penetration': TARGET_PENETRATION,
        'total_load_mw': round(total_load, 4),
        'vsc_power_mw': vsc_power,
        'vsc_rate_mva': vsc_rate,
        'fault_bus': 'Bus 8',
        'A': results['A'],
        'B': results['B'],
        'C': results['C'],
    }
    with open(RESULTS_PATH, 'w') as f:
        json.dump(payload, f, indent=2)
    print(f"\nResults saved to {RESULTS_PATH}")


if __name__ == '__main__':
    main()
