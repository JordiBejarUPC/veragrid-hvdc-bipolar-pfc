"""
Generate voltage profile plots: healthy, during-fault, and post-fault for each scenario.
Fault at Bus 9: Scenario A=3 trips, B=2 trips, C=1 trip.
"""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import numpy as np
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/docs/figures'

# Load results
with open('/Users/Josep/Desktop/VeraGrid/trunk/flexdis/docs/postfault_results.json') as f:
    data = json.load(f)

TEAL = '#04384F'
GREEN = '#41FE9F'
RED = '#E04040'
ORANGE = '#F0A030'
BLUE = '#2080D0'
LIGHTGRAY = '#CCCCCC'

bus_nums = list(range(1, 34))
x = np.arange(33)

VSC_BUSES = {18: 'VSC 18', 22: 'VSC 22', 25: 'VSC 25', 33: 'VSC 33'}
VSC_IDX = [17, 21, 24, 32]  # 0-indexed


def get_v_array(vdict):
    return np.array([vdict[f'Bus {i}'] for i in range(1, 34)])


# ============================================================
# Individual scenario plots: healthy + post-fault + threshold
# ============================================================
scenario_info = {
    'A': {'min_v': 0.85, 'color': RED, 'tripped': data['A']['tripped'],
           'label': 'Scenario A — No LVRT (0.85 p.u.)'},
    'B': {'min_v': 0.50, 'color': ORANGE, 'tripped': data['B']['tripped'],
           'label': 'Scenario B — Moderate LVRT (0.50 p.u.)'},
    'C': {'min_v': 0.10, 'color': GREEN, 'tripped': data['C']['tripped'],
           'label': 'Scenario C — Stringent LVRT (0.10 p.u.)'},
}

for key, info in scenario_info.items():
    healthy = get_v_array(data[key]['healthy'])
    postfault = get_v_array(data[key]['postfault'])
    fault = get_v_array(data[key]['fault'])
    n_tripped = data[key]['n_tripped']
    tripped_names = data[key]['tripped']

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7.5), gridspec_kw={'height_ratios': [1, 1.2]})

    # Top: During-fault voltage profile
    colors_fault = []
    for i in range(33):
        if i == 8:  # Bus 9 = fault bus
            colors_fault.append('red')
        elif fault[i] < info['min_v']:
            colors_fault.append(RED)
        else:
            colors_fault.append(LIGHTGRAY)
    for idx in VSC_IDX:
        if fault[idx] < info['min_v']:
            colors_fault[idx] = RED
        else:
            colors_fault[idx] = GREEN

    ax1.bar(bus_nums, fault, color=colors_fault, alpha=0.85, width=0.7)
    ax1.axhline(y=info['min_v'], color=info['color'], linestyle='--', linewidth=2,
                label=f'Threshold = {info["min_v"]} p.u.')
    ax1.annotate('FAULT', (9, 0.02), ha='center', fontsize=9, color='white', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='red', alpha=0.9))

    for idx in VSC_IDX:
        bn = idx + 1
        status = 'TRIP' if f'VSC Bus {bn}' in tripped_names else 'OK'
        c = 'red' if status == 'TRIP' else 'green'
        ax1.annotate(f'VSC {bn}\n{status}', (bn, max(fault[idx], 0.02)),
                     textcoords="offset points", xytext=(0, 8),
                     ha='center', fontsize=7, color=c, fontweight='bold')

    ax1.set_ylabel('Voltage (p.u.)', fontsize=11)
    ax1.set_title(f'During Fault — {n_tripped}/4 VSCs trip', fontsize=13, fontweight='bold', color=TEAL)
    ax1.set_ylim(-0.05, 1.3)
    ax1.set_xticks(bus_nums)
    ax1.set_xticklabels(bus_nums, fontsize=7)
    ax1.legend(fontsize=10, loc='upper right')
    ax1.grid(axis='y', alpha=0.3)

    # Bottom: Healthy vs Post-fault
    width = 0.35
    ax2.bar(x - width/2, healthy, width, label='Healthy (all VSCs on)', color=TEAL, alpha=0.7)
    ax2.bar(x + width/2, postfault, width, label=f'Post-fault ({n_tripped} VSCs off)',
            color=info['color'], alpha=0.7)

    # Annotate VSC buses
    for idx in VSC_IDX:
        bn = idx + 1
        delta = healthy[idx] - postfault[idx]
        if delta > 0.0005:
            ax2.annotate(f'VSC {bn}\n$\\Delta$={delta:.3f}', (idx + width/2, postfault[idx]),
                         textcoords="offset points", xytext=(0, 8),
                         ha='center', fontsize=7, color=info['color'], fontweight='bold')

    ax2.set_xlabel('Bus Number', fontsize=11)
    ax2.set_ylabel('Voltage (p.u.)', fontsize=11)
    ax2.set_title(f'Post-Fault Steady State — Voltage Drop from Lost DER', fontsize=13, fontweight='bold', color=TEAL)
    ax2.set_ylim(0.90, 1.005)
    ax2.set_xticks(x)
    ax2.set_xticklabels(bus_nums, fontsize=7)
    ax2.legend(fontsize=10, loc='upper right')
    ax2.grid(axis='y', alpha=0.3)

    fig.suptitle(info['label'], fontsize=15, fontweight='bold', color=TEAL, y=0.99)
    plt.tight_layout()
    plt.savefig(f'{OUT}/postfault_scenario_{key}.pdf', dpi=150, bbox_inches='tight')
    plt.savefig(f'{OUT}/postfault_scenario_{key}.png', dpi=150, bbox_inches='tight')
    print(f'Saved postfault_scenario_{key}.pdf')


# ============================================================
# Comparison plot: post-fault voltages for all 3 scenarios
# ============================================================
fig, ax = plt.subplots(figsize=(12, 5))

healthy = get_v_array(data['A']['healthy'])
post_a = get_v_array(data['A']['postfault'])
post_b = get_v_array(data['B']['postfault'])
post_c = get_v_array(data['C']['postfault'])

width = 0.2
ax.bar(x - 1.5*width, healthy, width, label='Healthy (all VSCs)', color=TEAL, alpha=0.6)
ax.bar(x - 0.5*width, post_a, width, label='Post-fault A (3 trips)', color=RED, alpha=0.7)
ax.bar(x + 0.5*width, post_b, width, label='Post-fault B (2 trips)', color=ORANGE, alpha=0.7)
ax.bar(x + 1.5*width, post_c, width, label='Post-fault C (1 trip)', color=GREEN, alpha=0.7)

ax.set_xlabel('Bus Number', fontsize=12)
ax.set_ylabel('Voltage (p.u.)', fontsize=12)
ax.set_title('Post-Fault Voltage Comparison — Fault at Bus 9', fontsize=14, fontweight='bold', color=TEAL)
ax.set_ylim(0.905, 1.005)
ax.set_xticks(x)
ax.set_xticklabels(bus_nums, fontsize=7)
ax.legend(fontsize=9, loc='lower left')
ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig(f'{OUT}/postfault_comparison.pdf', dpi=150, bbox_inches='tight')
plt.savefig(f'{OUT}/postfault_comparison.png', dpi=150, bbox_inches='tight')
print('Saved postfault_comparison.pdf')


# ============================================================
# Keep the healthy + disconnection summary plots from before
# ============================================================
print('\nAll plots generated.')
