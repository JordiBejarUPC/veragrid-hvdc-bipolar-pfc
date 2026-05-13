"""
Generate voltage profile plots for the cascading events presentation.
"""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import FaultType, MethodShortCircuit, SolverType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_options import ShortCircuitOptions
from VeraGridEngine.Simulations.ShortCircuitStudies.short_circuit_driver import ShortCircuitDriver
from VeraGridEngine.Devices.Aggregation.short_cirtcuit_event import ShortCircuitEvent

FILEPATH = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'
OUT = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/docs/figures'

import os
os.makedirs(OUT, exist_ok=True)

# Colors
TEAL = '#04384F'
GREEN = '#41FE9F'
RED = '#E04040'
ORANGE = '#F0A030'
BLUE = '#2080D0'

VSC_BUSES = {18: 'VSC Bus 18\n(0.20 MW)', 22: 'VSC Bus 22\n(0.15 MW)',
             25: 'VSC Bus 25\n(0.30 MW)', 33: 'VSC Bus 33\n(0.15 MW)'}
VSC_BUS_INDICES = [17, 21, 24, 32]  # 0-indexed

FAULT_BUS = 8  # Bus 9 (0-indexed) — A=3, B=2, C=1 disconnections


def load_and_run_pf():
    grid = gce.open_file(FILEPATH)
    pf_options = PowerFlowOptions(solver_type=SolverType.NR, retry_with_other_methods=False)
    pf_res = gce.power_flow(grid, options=pf_options)
    return grid, pf_res, pf_options


def run_sc(min_ac_v, fault_bus_idx):
    """Run SC at a given bus with a given min_ac_voltage."""
    grid = gce.open_file(FILEPATH)
    for bus in grid.buses:
        if not bus.is_dc:
            bus.r_fault = 1e-6
            bus.x_fault = 1e-6
    for vsc in grid.vsc_devices:
        vsc.min_ac_voltage = min_ac_v

    pf_options = PowerFlowOptions(solver_type=SolverType.NR, retry_with_other_methods=False)
    pf_res = gce.power_flow(grid, options=pf_options)

    grid._short_circuit_events = []
    sc_event = ShortCircuitEvent(
        device=grid.buses[fault_bus_idx],
        fault_type=FaultType.LLLG,
        method=MethodShortCircuit.sequences_vsc,
        name=f"Fault",
        active=True,
    )
    grid.add_short_circuit_event(sc_event)

    sc_driver = ShortCircuitDriver(
        grid=grid, options=ShortCircuitOptions(),
        pf_options=pf_options, pf_results=pf_res, pf_results3ph=None,
    )
    sc_driver.run()
    return sc_driver.results, grid


def get_ac_voltages(voltage_array, grid, sc=False):
    """Extract AC bus voltages (indices 0-32)."""
    v = []
    names = []
    for i, bus in enumerate(grid.buses):
        if not bus.is_dc:
            if sc:
                v.append(float(np.abs(voltage_array[i, 0])))
            else:
                v.append(float(np.abs(voltage_array[i])))
            names.append(int(bus.name.replace('Bus ', '')))
    return np.array(names), np.array(v)


# ============================================================
# PLOT 1: Healthy-state voltage profile
# ============================================================
print("Generating healthy-state voltage profile...")
grid, pf_res, pf_options = load_and_run_pf()
bus_nums, pf_v = get_ac_voltages(pf_res.voltage, grid)

fig, ax = plt.subplots(figsize=(12, 5))
ax.bar(bus_nums, pf_v, color=TEAL, alpha=0.85, width=0.7)
for idx in VSC_BUS_INDICES:
    ax.bar(bus_nums[idx], pf_v[idx], color=GREEN, alpha=0.9, width=0.7)

ax.set_xlabel('Bus Number', fontsize=13)
ax.set_ylabel('Voltage Magnitude (p.u.)', fontsize=13)
ax.set_title('Healthy-State Voltage Profile — IEEE 33-Bus Network', fontsize=15, fontweight='bold', color=TEAL)
ax.set_ylim(0.90, 1.01)
ax.set_xticks(bus_nums)
ax.set_xticklabels(bus_nums, fontsize=8)
ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.5)

# Annotate VSC buses
for idx in VSC_BUS_INDICES:
    ax.annotate(f'VSC', (bus_nums[idx], pf_v[idx]),
                textcoords="offset points", xytext=(0, 8),
                ha='center', fontsize=7, color='green', fontweight='bold')

ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(f'{OUT}/voltage_profile_healthy.pdf', dpi=150, bbox_inches='tight')
plt.savefig(f'{OUT}/voltage_profile_healthy.png', dpi=150, bbox_inches='tight')
print(f"  Saved voltage_profile_healthy.pdf")


# ============================================================
# PLOT 2: SC voltage profiles for Bus 9 fault — all 3 scenarios
# ============================================================
print("Running SC at Bus 9 for 3 scenarios...")
scenarios = [
    (0.85, 'A — No LVRT (0.85 p.u.)', RED),
    (0.50, 'B — Moderate (0.50 p.u.)', ORANGE),
    (0.10, 'C — Stringent (0.10 p.u.)', GREEN),
]

sc_data = {}
for min_v, label, color in scenarios:
    res_sc, g = run_sc(min_v, FAULT_BUS)
    bus_nums_sc, v_sc = get_ac_voltages(res_sc.voltage1, g, sc=True)
    sc_data[label] = (bus_nums_sc, v_sc, min_v, color)

# Combined plot
fig, ax = plt.subplots(figsize=(12, 5.5))
x = np.arange(len(bus_nums))
width = 0.25

for i, (label, (bn, v, min_v, color)) in enumerate(sc_data.items()):
    offset = (i - 1) * width
    bars = ax.bar(x + offset, v, width, label=label, color=color, alpha=0.8)
    # Draw threshold line
    ax.axhline(y=min_v, color=color, linestyle='--', linewidth=1.0, alpha=0.6)

# Mark fault bus
ax.annotate('FAULT', (FAULT_BUS, 0), textcoords="offset points", xytext=(0, 5),
            ha='center', fontsize=9, color='white', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='red', alpha=0.8))

# Mark VSC buses
for idx in VSC_BUS_INDICES:
    ax.annotate('VSC', (idx, -0.03), ha='center', fontsize=7, color=TEAL, fontweight='bold')

ax.set_xlabel('Bus Number', fontsize=13)
ax.set_ylabel('Voltage Magnitude (p.u.)', fontsize=13)
ax.set_title('Short Circuit Voltage Profile — Fault at Bus 9', fontsize=15, fontweight='bold', color=TEAL)
ax.set_ylim(-0.08, 1.15)
ax.set_xticks(x)
ax.set_xticklabels(bus_nums, fontsize=8)
ax.legend(fontsize=10, loc='upper right')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(f'{OUT}/sc_voltage_bus9_combined.pdf', dpi=150, bbox_inches='tight')
plt.savefig(f'{OUT}/sc_voltage_bus9_combined.png', dpi=150, bbox_inches='tight')
print(f"  Saved sc_voltage_bus9_combined.pdf")


# ============================================================
# PLOT 3: Individual scenario plots (larger, clearer)
# ============================================================
for label, (bn, v, min_v, color) in sc_data.items():
    scenario_letter = label[0]
    fig, ax = plt.subplots(figsize=(12, 5))

    colors_per_bus = []
    for i in range(len(v)):
        if i == FAULT_BUS:
            colors_per_bus.append('red')
        elif v[i] < min_v:
            colors_per_bus.append(RED)  # Below threshold → disconnects if VSC
        else:
            colors_per_bus.append(TEAL)

    # Highlight VSC buses
    for idx in VSC_BUS_INDICES:
        if v[idx] < min_v:
            colors_per_bus[idx] = RED
        else:
            colors_per_bus[idx] = GREEN

    ax.bar(bn, v, color=colors_per_bus, alpha=0.85, width=0.7)
    ax.axhline(y=min_v, color=color, linestyle='--', linewidth=2.0, alpha=0.8,
               label=f'min_ac_voltage = {min_v} p.u.')

    # Count disconnected VSCs
    disc_count = sum(1 for idx in VSC_BUS_INDICES if v[idx] < min_v)
    disc_buses = [f'Bus {bn[idx]}' for idx in VSC_BUS_INDICES if v[idx] < min_v]
    conn_buses = [f'Bus {bn[idx]}' for idx in VSC_BUS_INDICES if v[idx] >= min_v]

    # Annotate VSC buses
    for idx in VSC_BUS_INDICES:
        v_val = v[idx]
        status = 'DISC' if v_val < min_v else 'OK'
        c = 'red' if v_val < min_v else 'green'
        ax.annotate(f'VSC\n{status}\n({v_val:.2f})', (bn[idx], max(v_val, 0.02)),
                    textcoords="offset points", xytext=(0, 10),
                    ha='center', fontsize=7, color=c, fontweight='bold')

    ax.annotate('FAULT', (bn[FAULT_BUS], 0.01),
                ha='center', fontsize=10, color='white', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='red', alpha=0.9))

    ax.set_xlabel('Bus Number', fontsize=13)
    ax.set_ylabel('Voltage Magnitude (p.u.)', fontsize=13)
    ax.set_title(f'Scenario {label} — Fault at Bus 9 — {disc_count}/4 VSCs disconnect',
                 fontsize=14, fontweight='bold', color=TEAL)
    ax.set_ylim(-0.05, 1.25)
    ax.set_xticks(bn)
    ax.set_xticklabels(bn, fontsize=8)
    ax.legend(fontsize=11, loc='upper right')
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    fname = f'sc_voltage_bus9_scenario_{scenario_letter}'
    plt.savefig(f'{OUT}/{fname}.pdf', dpi=150, bbox_inches='tight')
    plt.savefig(f'{OUT}/{fname}.png', dpi=150, bbox_inches='tight')
    print(f"  Saved {fname}.pdf")


# ============================================================
# PLOT 4: Disconnection heatmap / summary bar chart
# ============================================================
print("Generating disconnection summary chart...")
import json
with open('/Users/Josep/Desktop/VeraGrid/trunk/flexdis/docs/cascading_results.json') as f:
    all_results = json.load(f)

scenario_labels = ['A — No LVRT\n(0.85 p.u.)', 'B — Moderate\n(0.50 p.u.)', 'C — Stringent\n(0.10 p.u.)']
scenario_keys = list(all_results['scenarios'].keys())
colors_bar = [RED, ORANGE, GREEN]

fig, axes = plt.subplots(2, 1, figsize=(10, 9))

# Top: Average disconnections
ax = axes[0]
avgs = [all_results['scenarios'][k]['summary']['avg_vscs_disconnected'] for k in scenario_keys]
bars = ax.bar(scenario_labels, avgs, color=colors_bar, alpha=0.85, width=0.5)
for bar, val in zip(bars, avgs):
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.05,
            f'{val:.2f}', ha='center', va='bottom', fontweight='bold', fontsize=13, color=TEAL)
ax.set_ylabel('Avg. VSCs Disconnected per Fault', fontsize=12)
ax.set_title('Average Cascading Severity', fontsize=14, fontweight='bold', color=TEAL)
ax.set_ylim(0, 3.2)
ax.grid(axis='y', alpha=0.3)

# Bottom: Distribution stacked bar
ax = axes[1]
x_pos = np.arange(3)
bottom = np.zeros(3)
disc_colors = ['#B0B0B0', BLUE, ORANGE, RED, '#800000']
disc_labels = ['0 VSCs', '1 VSC', '2 VSCs', '3 VSCs', '4 VSCs']

for n_disc in range(5):
    vals = []
    for k in scenario_keys:
        dist = all_results['scenarios'][k]['summary']['disconnection_distribution']
        vals.append(dist.get(str(n_disc), 0))
    vals = np.array(vals)
    ax.bar(x_pos, vals, bottom=bottom, color=disc_colors[n_disc],
           label=disc_labels[n_disc], width=0.5, alpha=0.85)
    bottom += vals

ax.set_xticks(x_pos)
ax.set_xticklabels(scenario_labels, fontsize=10)
ax.set_ylabel('Number of Fault Locations', fontsize=12)
ax.set_title('Distribution of VSC Disconnections', fontsize=14, fontweight='bold', color=TEAL)
ax.legend(fontsize=9, loc='upper right')
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig(f'{OUT}/disconnection_summary.pdf', dpi=150, bbox_inches='tight')
plt.savefig(f'{OUT}/disconnection_summary.png', dpi=150, bbox_inches='tight')
print(f"  Saved disconnection_summary.pdf")

print("\nAll plots generated successfully!")
