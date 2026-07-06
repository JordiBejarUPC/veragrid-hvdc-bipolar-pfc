"""
Cascading Disconnection Study on IEEE 33-bus FlexDis Network.

Uses the sequences_vsc short circuit method which properly models:
  - VSC converter dynamics during faults (Fault1/Fault2 control modes)
  - Generator Norton equivalent behind subtransient impedance
  - VSC min_ac_voltage disconnection logic
  - Full AC/DC power flow solution during fault

Three scenarios:
  A: min_ac_voltage = 0.85 p.u. (No LVRT - legacy inverters)
  B: min_ac_voltage = 0.50 p.u. (Moderate LVRT)
  C: min_ac_voltage = 0.10 p.u. (Stringent LVRT - modern grid code)
"""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

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
RESULTS_DIR = '/Users/josep/Desktop/VeraGrid/trunk/flexdis/docs'

# VSC power injections (MW)
VSC_POWER = {
    "VSC Bus 18": 0.20,
    "VSC Bus 22": 0.15,
    "VSC Bus 25": 0.30,
    "VSC Bus 33": 0.15,
}
TOTAL_DER_MW = sum(VSC_POWER.values())  # 0.80 MW


def run_scenario(min_ac_v: float, scenario_label: str) -> dict:
    """Run full SC analysis for a given min_ac_voltage threshold."""
    print(f"\n{'='*70}")
    print(f"  SCENARIO {scenario_label}: min_ac_voltage = {min_ac_v} p.u.")
    print(f"{'='*70}")

    # Load fresh grid for each scenario
    grid = gce.open_file(FILEPATH)

    # Set min_ac_voltage on all VSCs (fault impedance set per-event below)
    for vsc in grid.vsc_devices:
        vsc.min_ac_voltage = min_ac_v

    # Run healthy-state power flow
    pf_options = PowerFlowOptions(solver_type=SolverType.NR, retry_with_other_methods=False)
    pf_res = gce.power_flow(grid, options=pf_options)

    ac_buses = [b for b in grid.buses if not b.is_dc]
    ac_count = len(ac_buses)

    # Map VSC -> AC bus index
    vsc_info = []
    for vsc in grid.vsc_devices:
        ac_idx = grid.buses.index(vsc.bus_to)
        vsc_info.append({
            'name': vsc.name,
            'ac_bus': vsc.bus_to.name,
            'ac_idx': ac_idx,
            'p_mw': VSC_POWER[vsc.name],
        })

    print(f"\n  Healthy state: V range [{min(abs(pf_res.voltage[i]) for i,b in enumerate(grid.buses) if not b.is_dc):.4f}, "
          f"{max(abs(pf_res.voltage[i]) for i,b in enumerate(grid.buses) if not b.is_dc):.4f}] p.u.")

    # Run SC at each AC bus using sequences_vsc
    print(f"  Running {ac_count} short circuit calculations (sequences_vsc)...")

    scenario_results = {
        'scenario_label': scenario_label,
        'min_ac_voltage': min_ac_v,
        'faults': [],
    }

    for fault_bus in ac_buses:
        # Reload grid each time (sequences_vsc modifies VSC controls internally)
        grid = gce.open_file(FILEPATH)
        for vsc in grid.vsc_devices:
            vsc.min_ac_voltage = min_ac_v

        pf_res = gce.power_flow(grid, options=pf_options)

        fault_bus_obj = next(b for b in grid.buses if b.name == fault_bus.name)
        grid._short_circuit_events = []
        sc_event = ShortCircuitEvent(
            device=fault_bus_obj,
            fault_type=FaultType.LLLG,
            method=MethodShortCircuit.sequences_vsc,
            name=f"Fault {fault_bus.name}",
            active=True,
            r_fault=1e-6,
            x_fault=1e-6,
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

        if res_sc is None:
            continue

        # Extract SC voltages at AC buses
        sc_voltages = {}
        for i, bus in enumerate(grid.buses):
            if not bus.is_dc and i < res_sc.voltage1.shape[0]:
                sc_voltages[bus.name] = float(np.abs(res_sc.voltage1[i, 0]))

        # Extract VSC power flows from SC results (sequences_vsc computes these)
        vsc_disconnected = []
        vsc_connected = []
        for vi, vinfo in enumerate(vsc_info):
            v_ac = sc_voltages.get(vinfo['ac_bus'], 1.0)
            # Check actual VSC power output from SC results
            pfp = float(res_sc.vsc_Pfp[vi, 0]) if vi < res_sc.vsc_Pfp.shape[0] else 0
            st = complex(res_sc.vsc_St[vi, 0]) if vi < res_sc.vsc_St.shape[0] else 0

            # VSC is disconnected if its power output dropped to ~0
            is_disconnected = abs(pfp) < 0.001 and v_ac < min_ac_v
            # Also consider it disconnected if AC voltage is below threshold
            if v_ac < min_ac_v:
                is_disconnected = True

            if is_disconnected:
                vsc_disconnected.append({
                    'name': vinfo['name'],
                    'ac_bus': vinfo['ac_bus'],
                    'v_ac': round(v_ac, 4),
                    'p_mw': vinfo['p_mw'],
                    'pfp_sc': round(pfp, 4),
                })
            else:
                vsc_connected.append({
                    'name': vinfo['name'],
                    'v_ac': round(v_ac, 4),
                    'pfp_sc': round(pfp, 4),
                })

        lost_mw = sum(d['p_mw'] for d in vsc_disconnected)

        fault_result = {
            'fault_bus': fault_bus.name,
            'sc_voltages': sc_voltages,
            'min_sc_voltage': round(min(sc_voltages.values()), 4) if sc_voltages else 0.0,
            'n_disconnected': len(vsc_disconnected),
            'disconnected_vscs': vsc_disconnected,
            'connected_vscs': vsc_connected,
            'lost_generation_mw': round(lost_mw, 4),
        }
        scenario_results['faults'].append(fault_result)

    # Print detailed results
    print(f"\n  {'Fault Bus':<10s} {'Vmin':>6s}  {'#Disc':>5s}  {'Lost MW':>8s}  {'Disconnected VSCs'}")
    print(f"  {'-'*70}")
    for f in scenario_results['faults']:
        vsc_list = ", ".join(d['name'].replace('VSC ', '') + f"(V={d['v_ac']:.2f})" for d in f['disconnected_vscs'])
        if not vsc_list:
            vsc_list = "none"
        if f['n_disconnected'] > 0:
            print(f"  {f['fault_bus']:<10s} {f['min_sc_voltage']:>6.3f}  {f['n_disconnected']:>5d}  "
                  f"{f['lost_generation_mw']:>8.3f}  {vsc_list}")

    # Summary
    n_causing = sum(1 for f in scenario_results['faults'] if f['n_disconnected'] > 0)
    max_disc = max((f['n_disconnected'] for f in scenario_results['faults']), default=0)
    max_lost = max((f['lost_generation_mw'] for f in scenario_results['faults']), default=0.0)
    avg_disc = np.mean([f['n_disconnected'] for f in scenario_results['faults']])

    disc_distribution = {}
    for f in scenario_results['faults']:
        k = f['n_disconnected']
        disc_distribution[k] = disc_distribution.get(k, 0) + 1

    scenario_results['summary'] = {
        'n_faults_total': ac_count,
        'n_faults_causing_disconnect': n_causing,
        'max_vscs_disconnected': max_disc,
        'max_lost_generation_mw': round(max_lost, 4),
        'avg_vscs_disconnected': round(float(avg_disc), 2),
        'total_der_mw': TOTAL_DER_MW,
        'disconnection_distribution': disc_distribution,
    }

    print(f"\n  Summary:")
    print(f"    Faults causing >=1 disconnect: {n_causing}/{ac_count} ({100*n_causing/ac_count:.0f}%)")
    print(f"    Max VSCs disconnected: {max_disc}/4")
    print(f"    Avg VSCs disconnected: {avg_disc:.2f}")
    print(f"    Max lost DER: {max_lost:.3f}/{TOTAL_DER_MW:.3f} MW ({100*max_lost/TOTAL_DER_MW:.0f}%)")
    print(f"    Distribution: {dict(sorted(disc_distribution.items()))}")

    return scenario_results


def main():
    scenarios = [
        (0.85, "A — No LVRT (0.85 p.u.)"),
        (0.50, "B — Moderate LVRT (0.50 p.u.)"),
        (0.10, "C — Stringent LVRT (0.10 p.u.)"),
    ]

    all_results = {}
    for min_v, label in scenarios:
        all_results[label] = run_scenario(min_v, label)

    # Cross-scenario comparison
    print(f"\n{'='*70}")
    print(f"  CROSS-SCENARIO COMPARISON")
    print(f"{'='*70}")
    print(f"\n  {'Scenario':<35s} {'Faults':>8s} {'MaxDisc':>8s} {'AvgDisc':>8s} {'MaxLost':>8s} {'%DER':>6s}")
    print(f"  {'-'*75}")
    for label, res in all_results.items():
        s = res['summary']
        pct = 100 * s['max_lost_generation_mw'] / s['total_der_mw']
        print(f"  {label:<35s} {s['n_faults_causing_disconnect']:>4d}/{s['n_faults_total']:<3d}"
              f" {s['max_vscs_disconnected']:>5d}/4  "
              f" {s['avg_vscs_disconnected']:>6.2f}  "
              f" {s['max_lost_generation_mw']:>6.3f}  "
              f" {pct:>5.1f}%")

    # Disconnection matrix
    print(f"\n  Disconnection Matrix (# VSCs tripped per fault)")
    header = f"  {'Fault':<10s}"
    for min_v, _ in scenarios:
        header += f"  {min_v:.2f}"
    print(header)
    print(f"  {'-'*40}")

    fault_names = [f['fault_bus'] for f in all_results[scenarios[0][1]]['faults']]
    for fb in fault_names:
        row = f"  {fb:<10s}"
        for _, label in scenarios:
            fault = next((f for f in all_results[label]['faults'] if f['fault_bus'] == fb), None)
            n = fault['n_disconnected'] if fault else 0
            row += f"  {n:>4d}"
        print(row)

    # Save results
    output = {
        'study': 'Cascading VSC Disconnection - IEEE 33-bus FlexDis',
        'method': 'sequences_vsc (full AC/DC power flow during fault)',
        'date': '2026-03-22',
        'fault_type': 'LLLG (3-phase bolted, Zf=1e-6+j1e-6)',
        'scenarios': {},
    }
    for label, res in all_results.items():
        output['scenarios'][label] = {
            'min_ac_voltage': res['min_ac_voltage'],
            'summary': res['summary'],
            'faults': [{
                'fault_bus': f['fault_bus'],
                'min_sc_voltage': f['min_sc_voltage'],
                'n_disconnected': f['n_disconnected'],
                'lost_generation_mw': f['lost_generation_mw'],
                'disconnected_vscs': f['disconnected_vscs'],
                'connected_vscs': f['connected_vscs'],
            } for f in res['faults']]
        }

    results_path = f"{RESULTS_DIR}/cascading_results.json"
    with open(results_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to {results_path}")


if __name__ == '__main__':
    main()
