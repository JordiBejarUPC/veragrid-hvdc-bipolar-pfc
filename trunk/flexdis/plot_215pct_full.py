"""
Render the full figure set for the 21.5% baseline cascading report.

Mirrors plot_75pct_full.py with the 21.5% fixtures:
  - voltage_profile_healthy_215pct.pdf
  - disconnection_summary_215pct.pdf
  - sc_voltage_bus9_combined_215pct.pdf
  - sc_voltage_bus9_scenario_{A,B,C}_215pct.pdf
  - postfault_comparison_215pct.pdf
  - postfault_scenario_{A,B,C}_215pct.pdf
"""
import json
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = '/Users/josep/Desktop/VeraGrid/trunk/flexdis'
OUT = f'{BASE}/docs/Figures/Cascading'
os.makedirs(OUT, exist_ok=True)

with open(f'{BASE}/docs/cascading_results.json') as f:
    cascading = json.load(f)
with open(f'{BASE}/docs/postfault_results.json') as f:
    pf = json.load(f)

TEAL = '#04384F'
GREEN = '#41FE9F'
RED = '#E04040'
ORANGE = '#F0A030'
LIGHTGRAY = '#CCCCCC'

LABEL_A = 'A — No LVRT (0.85 p.u.)'
LABEL_B = 'B — Moderate LVRT (0.50 p.u.)'
LABEL_C = 'C — Stringent LVRT (0.10 p.u.)'
SCENS = [LABEL_A, LABEL_B, LABEL_C]
SHORT = {'A': LABEL_A, 'B': LABEL_B, 'C': LABEL_C}
SCEN_COLOR = {'A': RED, 'B': ORANGE, 'C': GREEN}
SCEN_VMIN = {'A': 0.85, 'B': 0.50, 'C': 0.10}

bus_nums = list(range(1, 34))
x = np.arange(33)
VSC_BUS_NUMS = [18, 22, 25, 33]
VSC_IDX = [n - 1 for n in VSC_BUS_NUMS]
FAULT_BUS_LABEL = 'Bus 9'
FAULT_BUS_IDX = int(FAULT_BUS_LABEL.replace('Bus ', '')) - 1
PENETRATION_PCT = '21.5'


def vec(vdict):
    return np.array([vdict[f'Bus {i}'] for i in range(1, 34)])


# ---------------------------------------------------------------------------
# Figure 1: Healthy voltage profile
# ---------------------------------------------------------------------------
healthy = vec(pf['A']['healthy'])
fig, ax = plt.subplots(figsize=(12, 4.5))
colors = [GREEN if i in VSC_IDX else TEAL for i in range(33)]
ax.bar(bus_nums, healthy, color=colors, alpha=0.85, width=0.7)
for idx in VSC_IDX:
    bn = idx + 1
    ax.annotate(f'VSC {bn}', (bn, healthy[idx]),
                textcoords="offset points", xytext=(0, 6),
                ha='center', fontsize=8, color='green', fontweight='bold')
ax.axhline(y=1.0, color='gray', linestyle=':', linewidth=1, alpha=0.6)
ax.set_xlabel('Bus number', fontsize=11)
ax.set_ylabel('Voltage (p.u.)', fontsize=11)
ax.set_title(f'Healthy-state voltage profile, {PENETRATION_PCT}\\% renewable penetration',
             fontsize=12, fontweight='bold', color=TEAL)
ax.set_ylim(0.90, 1.02)
ax.set_xticks(bus_nums)
ax.set_xticklabels(bus_nums, fontsize=7)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(f'{OUT}/voltage_profile_healthy_215pct.pdf', bbox_inches='tight')
plt.savefig(f'{OUT}/voltage_profile_healthy_215pct.png', dpi=150, bbox_inches='tight')
print('Saved voltage_profile_healthy_215pct')


# ---------------------------------------------------------------------------
# Figure 2: Disconnection summary (avg bars + distribution histogram)
# ---------------------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), gridspec_kw={'height_ratios': [1, 1.3]})

avg = [cascading['scenarios'][s]['summary']['avg_vscs_disconnected'] for s in SCENS]
scen_short = ['A: 0.85', 'B: 0.50', 'C: 0.10']
bar_colors = [RED, ORANGE, GREEN]
ax1.bar(scen_short, avg, color=bar_colors, alpha=0.85)
for i, v in enumerate(avg):
    ax1.text(i, v + 0.05, f'{v:.2f}', ha='center', fontsize=10, fontweight='bold')
ax1.set_ylabel('Avg \\# VSCs disconnected per fault', fontsize=10)
ax1.set_title('Average cascading severity by LVRT threshold',
              fontsize=11, fontweight='bold', color=TEAL)
ax1.set_ylim(0, max(avg) * 1.25)
ax1.grid(axis='y', alpha=0.3)

categories = [0, 1, 2, 3, 4]
xpos = np.arange(len(categories))
w = 0.25
for j, s in enumerate(['A', 'B', 'C']):
    dist = cascading['scenarios'][SHORT[s]]['summary']['disconnection_distribution']
    dist = {int(k): v for k, v in dist.items()}
    counts = [dist.get(c, 0) for c in categories]
    ax2.bar(xpos + (j - 1) * w, counts, w,
            label=scen_short[j], color=bar_colors[j], alpha=0.85)
    for i, c in enumerate(counts):
        if c > 0:
            ax2.text(xpos[i] + (j - 1) * w, c + 0.4, str(c),
                     ha='center', fontsize=8)
ax2.set_xticks(xpos)
ax2.set_xticklabels([f'{c}' for c in categories])
ax2.set_xlabel('Number of VSCs disconnected per fault', fontsize=10)
ax2.set_ylabel('Number of fault locations (of 33)', fontsize=10)
ax2.set_title('Distribution of cascading severity across fault locations',
              fontsize=11, fontweight='bold', color=TEAL)
ax2.legend(fontsize=9)
ax2.grid(axis='y', alpha=0.3)

fig.suptitle(f'Cascading disconnection summary, {PENETRATION_PCT}\\% penetration',
             fontsize=13, fontweight='bold', color=TEAL, y=1.0)
plt.tight_layout()
plt.savefig(f'{OUT}/disconnection_summary_215pct.pdf', bbox_inches='tight')
plt.savefig(f'{OUT}/disconnection_summary_215pct.png', dpi=150, bbox_inches='tight')
print('Saved disconnection_summary_215pct')


# ---------------------------------------------------------------------------
# Figure 3: Combined SC voltage profile at Bus 9 across the three scenarios
# ---------------------------------------------------------------------------
fault_A = vec(pf['A']['fault'])
fault_B = vec(pf['B']['fault'])
fault_C = vec(pf['C']['fault'])

fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(bus_nums, fault_A, 'o-', color=RED, alpha=0.85, label='Scenario A fault profile')
ax.plot(bus_nums, fault_B, 's-', color=ORANGE, alpha=0.85, label='Scenario B fault profile')
ax.plot(bus_nums, fault_C, 'd-', color=GREEN, alpha=0.85, label='Scenario C fault profile')
for s, color in [('A', RED), ('B', ORANGE), ('C', GREEN)]:
    ax.axhline(y=SCEN_VMIN[s], color=color, linestyle='--', linewidth=1.2, alpha=0.7,
               label=f'Threshold {s} = {SCEN_VMIN[s]} p.u.')
for idx in VSC_IDX:
    bn = idx + 1
    ax.axvline(x=bn, color='gray', linestyle=':', alpha=0.3)
    ax.annotate(f'VSC {bn}', (bn, 1.02), ha='center', fontsize=8, color=TEAL, fontweight='bold')
ax.annotate(f'FAULT', (FAULT_BUS_IDX + 1, 0.04), ha='center', fontsize=8, color='white',
            fontweight='bold', bbox=dict(boxstyle='round,pad=0.2', facecolor='red', alpha=0.9))
ax.set_xlabel('Bus number', fontsize=11)
ax.set_ylabel('Voltage (p.u.)', fontsize=11)
ax.set_title(f'During-fault voltage profile, 3-phase fault at {FAULT_BUS_LABEL} ({PENETRATION_PCT}\\% penetration)',
             fontsize=12, fontweight='bold', color=TEAL)
ax.set_ylim(-0.05, 1.15)
ax.set_xticks(bus_nums)
ax.set_xticklabels(bus_nums, fontsize=7)
ax.legend(fontsize=8, loc='upper right', ncol=2)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(f'{OUT}/sc_voltage_bus9_combined_215pct.pdf', bbox_inches='tight')
plt.savefig(f'{OUT}/sc_voltage_bus9_combined_215pct.png', dpi=150, bbox_inches='tight')
print('Saved sc_voltage_bus9_combined_215pct')


# ---------------------------------------------------------------------------
# Figures 4-6: Per-scenario fault profiles at Bus 9
# ---------------------------------------------------------------------------
scenario_info = {
    'A': {'min_v': 0.85, 'color': RED, 'label': 'Scenario A, No LVRT (0.85 p.u.)'},
    'B': {'min_v': 0.50, 'color': ORANGE, 'label': 'Scenario B, Moderate LVRT (0.50 p.u.)'},
    'C': {'min_v': 0.10, 'color': GREEN, 'label': 'Scenario C, Stringent LVRT (0.10 p.u.)'},
}

for s, info in scenario_info.items():
    fault = vec(pf[s]['fault'])
    n_tripped = pf[s]['n_tripped']
    tripped_names = pf[s]['tripped']

    fig, ax = plt.subplots(figsize=(12, 5))
    colors_fault = []
    for i in range(33):
        if i == FAULT_BUS_IDX:
            colors_fault.append('red')
        elif fault[i] < info['min_v']:
            colors_fault.append(RED)
        else:
            colors_fault.append(LIGHTGRAY)
    for idx in VSC_IDX:
        bn = idx + 1
        if f'VSC Bus {bn}' in tripped_names:
            colors_fault[idx] = RED
        else:
            colors_fault[idx] = GREEN

    ax.bar(bus_nums, fault, color=colors_fault, alpha=0.85, width=0.7)
    ax.axhline(y=info['min_v'], color=info['color'], linestyle='--', linewidth=2,
               label=f'Threshold = {info["min_v"]} p.u.')
    ax.annotate('FAULT', (FAULT_BUS_IDX + 1, 0.04), ha='center', fontsize=9,
                color='white', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='red', alpha=0.9))
    for idx in VSC_IDX:
        bn = idx + 1
        status = 'TRIP' if f'VSC Bus {bn}' in tripped_names else 'OK'
        c = 'red' if status == 'TRIP' else 'green'
        ax.annotate(f'VSC {bn}\n{status}\nV={fault[idx]:.2f}',
                    (bn, max(fault[idx], 0.02)),
                    textcoords="offset points", xytext=(0, 8),
                    ha='center', fontsize=7, color=c, fontweight='bold')
    ax.set_xlabel('Bus number', fontsize=11)
    ax.set_ylabel('Voltage (p.u.)', fontsize=11)
    ax.set_title(f'{info["label"]}, fault at {FAULT_BUS_LABEL}: {n_tripped}/4 VSCs disconnect',
                 fontsize=12, fontweight='bold', color=TEAL)
    ax.set_ylim(-0.05, 1.25)
    ax.set_xticks(bus_nums)
    ax.set_xticklabels(bus_nums, fontsize=7)
    ax.legend(fontsize=10, loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(f'{OUT}/sc_voltage_bus9_scenario_{s}_215pct.pdf', bbox_inches='tight')
    plt.savefig(f'{OUT}/sc_voltage_bus9_scenario_{s}_215pct.png', dpi=150, bbox_inches='tight')
    print(f'Saved sc_voltage_bus9_scenario_{s}_215pct')


# ---------------------------------------------------------------------------
# Figure 7: Post-fault comparison across all three scenarios
# ---------------------------------------------------------------------------
post_a = vec(pf['A']['postfault'])
post_b = vec(pf['B']['postfault'])
post_c = vec(pf['C']['postfault'])

fig, ax = plt.subplots(figsize=(12, 5))
width = 0.2
ax.bar(x - 1.5 * width, healthy, width, label='Healthy (all VSCs)', color=TEAL, alpha=0.6)
ax.bar(x - 0.5 * width, post_a, width,
       label=f'Post-fault A ({pf["A"]["n_tripped"]} trips)', color=RED, alpha=0.7)
ax.bar(x + 0.5 * width, post_b, width,
       label=f'Post-fault B ({pf["B"]["n_tripped"]} trips)', color=ORANGE, alpha=0.7)
ax.bar(x + 1.5 * width, post_c, width,
       label=f'Post-fault C ({pf["C"]["n_tripped"]} trip)', color=GREEN, alpha=0.7)
ax.set_xlabel('Bus number', fontsize=11)
ax.set_ylabel('Voltage (p.u.)', fontsize=11)
ax.set_title(f'Post-fault voltage comparison, fault at {FAULT_BUS_LABEL} ({PENETRATION_PCT}\\% penetration)',
             fontsize=12, fontweight='bold', color=TEAL)
ymin = min(post_a.min(), post_b.min(), post_c.min(), healthy.min()) - 0.005
ax.set_ylim(ymin, 1.01)
ax.set_xticks(x)
ax.set_xticklabels(bus_nums, fontsize=7)
ax.legend(fontsize=9, loc='lower left')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(f'{OUT}/postfault_comparison_215pct.pdf', bbox_inches='tight')
plt.savefig(f'{OUT}/postfault_comparison_215pct.png', dpi=150, bbox_inches='tight')
print('Saved postfault_comparison_215pct')


# ---------------------------------------------------------------------------
# Figures 8-10: Per-scenario postfault analysis (during-fault + steady-state)
# ---------------------------------------------------------------------------
for s, info in scenario_info.items():
    fault = vec(pf[s]['fault'])
    postfault = vec(pf[s]['postfault'])
    n_tripped = pf[s]['n_tripped']
    tripped_names = pf[s]['tripped']

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7.5),
                                    gridspec_kw={'height_ratios': [1, 1.2]})

    colors_fault = []
    for i in range(33):
        if i == FAULT_BUS_IDX:
            colors_fault.append('red')
        elif fault[i] < info['min_v']:
            colors_fault.append(RED)
        else:
            colors_fault.append(LIGHTGRAY)
    for idx in VSC_IDX:
        bn = idx + 1
        if f'VSC Bus {bn}' in tripped_names:
            colors_fault[idx] = RED
        else:
            colors_fault[idx] = GREEN
    ax1.bar(bus_nums, fault, color=colors_fault, alpha=0.85, width=0.7)
    ax1.axhline(y=info['min_v'], color=info['color'], linestyle='--', linewidth=2,
                label=f'Threshold = {info["min_v"]} p.u.')
    ax1.annotate('FAULT', (FAULT_BUS_IDX + 1, 0.02), ha='center', fontsize=9,
                 color='white', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='red', alpha=0.9))
    for idx in VSC_IDX:
        bn = idx + 1
        status = 'TRIP' if f'VSC Bus {bn}' in tripped_names else 'OK'
        c = 'red' if status == 'TRIP' else 'green'
        ax1.annotate(f'VSC {bn}\n{status}', (bn, max(fault[idx], 0.02)),
                     textcoords="offset points", xytext=(0, 8),
                     ha='center', fontsize=7, color=c, fontweight='bold')
    ax1.set_ylabel('Voltage (p.u.)', fontsize=11)
    ax1.set_title(f'During fault, {n_tripped}/4 VSCs trip',
                  fontsize=13, fontweight='bold', color=TEAL)
    ax1.set_ylim(-0.05, 1.3)
    ax1.set_xticks(bus_nums)
    ax1.set_xticklabels(bus_nums, fontsize=7)
    ax1.legend(fontsize=10, loc='upper right')
    ax1.grid(axis='y', alpha=0.3)

    w2 = 0.35
    ax2.bar(x - w2 / 2, healthy, w2, label='Healthy (all VSCs on)', color=TEAL, alpha=0.7)
    ax2.bar(x + w2 / 2, postfault, w2,
            label=f'Post-fault ({n_tripped} VSCs off)', color=info['color'], alpha=0.7)
    for idx in VSC_IDX:
        bn = idx + 1
        delta = healthy[idx] - postfault[idx]
        if delta > 0.0005:
            ax2.annotate(f'VSC {bn}\n$\\Delta$={delta:.3f}',
                         (idx + w2 / 2, postfault[idx]),
                         textcoords="offset points", xytext=(0, 8),
                         ha='center', fontsize=7, color=info['color'], fontweight='bold')
    ax2.set_xlabel('Bus number', fontsize=11)
    ax2.set_ylabel('Voltage (p.u.)', fontsize=11)
    ax2.set_title('Post-fault steady state, voltage drop from lost DER',
                  fontsize=13, fontweight='bold', color=TEAL)
    ymin = min(postfault.min(), healthy.min()) - 0.005
    ax2.set_ylim(ymin, 1.01)
    ax2.set_xticks(x)
    ax2.set_xticklabels(bus_nums, fontsize=7)
    ax2.legend(fontsize=10, loc='upper right')
    ax2.grid(axis='y', alpha=0.3)

    fig.suptitle(info['label'], fontsize=15, fontweight='bold', color=TEAL, y=0.99)
    plt.tight_layout()
    plt.savefig(f'{OUT}/postfault_scenario_{s}_215pct.pdf', bbox_inches='tight')
    plt.savefig(f'{OUT}/postfault_scenario_{s}_215pct.png', dpi=150, bbox_inches='tight')
    print(f'Saved postfault_scenario_{s}_215pct')


# ---------------------------------------------------------------------------
# Compute VSC vulnerability stats (for the tex tables)
# ---------------------------------------------------------------------------
print(f"\n=== VSC VULNERABILITY ({PENETRATION_PCT}%, # faults where VSC trips, out of 33) ===")
for s_short, s_label in [('A', LABEL_A), ('B', LABEL_B), ('C', LABEL_C)]:
    counts = {f'VSC Bus {n}': 0 for n in VSC_BUS_NUMS}
    for fault in cascading['scenarios'][s_label]['faults']:
        for v in fault['disconnected_vscs']:
            counts[v['name']] = counts.get(v['name'], 0) + 1
    print(f"  Scenario {s_short}: {counts}")

print('\nAll plots in', OUT)
