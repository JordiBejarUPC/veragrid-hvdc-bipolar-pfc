"""
Generate plots comparing baseline (21.5%) vs high-penetration (75%) cascading
disconnection results. Reads:
  - docs/cascading_results.json
  - docs/cascading_results_75pct.json
Writes PNG/PDF figures into docs/Figures/Cascading/.
"""
import json
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE_DIR = '/Users/josep/Desktop/VeraGrid/trunk/flexdis'
OUT = f'{BASE_DIR}/docs/Figures/Cascading'
os.makedirs(OUT, exist_ok=True)

with open(f'{BASE_DIR}/docs/cascading_results.json') as f:
    base = json.load(f)
with open(f'{BASE_DIR}/docs/cascading_results_75pct.json') as f:
    high = json.load(f)

TEAL = '#04384F'
GREEN = '#41FE9F'
RED = '#E04040'
ORANGE = '#F0A030'
BLUE = '#2080D0'

LABEL_A = 'A — No LVRT (0.85 p.u.)'
LABEL_B = 'B — Moderate LVRT (0.50 p.u.)'
LABEL_C = 'C — Stringent LVRT (0.10 p.u.)'
SCENS = [LABEL_A, LABEL_B, LABEL_C]
COLORS = {LABEL_A: RED, LABEL_B: ORANGE, LABEL_C: GREEN}


def faults_by_bus(results, scen):
    """Return dict keyed by fault_bus -> fault entry."""
    return {f['fault_bus']: f for f in results['scenarios'][scen]['faults']}


bus_names = [f['fault_bus'] for f in base['scenarios'][LABEL_A]['faults']]
bus_idx = np.arange(len(bus_names))


# ---------------------------------------------------------------------------
# Figure 1: Lost generation per fault, baseline vs 75%, three subplots (A/B/C)
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)

for ax, scen in zip(axes, SCENS):
    base_f = faults_by_bus(base, scen)
    high_f = faults_by_bus(high, scen)
    base_mw = np.array([base_f[b]['lost_generation_mw'] for b in bus_names])
    high_mw = np.array([high_f[b]['lost_generation_mw'] for b in bus_names])

    w = 0.4
    ax.bar(bus_idx - w/2, base_mw, w, label='21.5% penetration (0.80 MW DER)', color=TEAL, alpha=0.85)
    ax.bar(bus_idx + w/2, high_mw, w, label='75% penetration (2.79 MW DER)', color=COLORS[scen], alpha=0.85)
    ax.set_ylabel('Lost DER (MW)', fontsize=10)
    ax.set_title(scen, fontsize=11, fontweight='bold', color=TEAL)
    ax.grid(axis='y', alpha=0.3)
    ax.legend(fontsize=9, loc='upper right')
    ax.set_ylim(0, max(2.9, high_mw.max() * 1.1))

axes[-1].set_xticks(bus_idx)
axes[-1].set_xticklabels([b.replace('Bus ', '') for b in bus_names], fontsize=8)
axes[-1].set_xlabel('Fault bus', fontsize=11)
fig.suptitle('Lost DER generation per fault — baseline vs 75% penetration',
             fontsize=13, fontweight='bold', color=TEAL, y=1.0)
plt.tight_layout()
plt.savefig(f'{OUT}/penetration_lost_mw_per_fault.png', dpi=150, bbox_inches='tight')
plt.savefig(f'{OUT}/penetration_lost_mw_per_fault.pdf', bbox_inches='tight')
print(f'Saved {OUT}/penetration_lost_mw_per_fault.png')


# ---------------------------------------------------------------------------
# Figure 2: Disconnection-count heatmap, side-by-side
# ---------------------------------------------------------------------------
def build_matrix(results):
    m = np.zeros((len(bus_names), 3), dtype=int)
    for j, scen in enumerate(SCENS):
        fmap = faults_by_bus(results, scen)
        for i, b in enumerate(bus_names):
            m[i, j] = fmap[b]['n_disconnected']
    return m


mat_base = build_matrix(base)
mat_high = build_matrix(high)

fig, axes = plt.subplots(1, 2, figsize=(11, 11), sharey=True)
for ax, mat, title in zip(axes,
                          [mat_base, mat_high],
                          ['Baseline — 21.5% penetration', 'High — 75% penetration']):
    im = ax.imshow(mat, aspect='auto', cmap='Reds', vmin=0, vmax=4)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(['A\n0.85', 'B\n0.50', 'C\n0.10'], fontsize=10)
    ax.set_xlabel('LVRT threshold (p.u.)', fontsize=11)
    ax.set_yticks(bus_idx)
    ax.set_yticklabels([b.replace('Bus ', '') for b in bus_names], fontsize=8)
    ax.set_title(title, fontsize=12, fontweight='bold', color=TEAL)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            ax.text(j, i, str(mat[i, j]),
                    ha='center', va='center',
                    color='white' if mat[i, j] >= 2 else 'black',
                    fontsize=8, fontweight='bold')

axes[0].set_ylabel('Fault bus', fontsize=11)
cbar = fig.colorbar(im, ax=axes, shrink=0.7, pad=0.02)
cbar.set_label('# VSCs disconnected (of 4)', fontsize=10)
fig.suptitle('Cascading disconnection matrix — baseline vs 75% penetration',
             fontsize=13, fontweight='bold', color=TEAL)
plt.savefig(f'{OUT}/penetration_disconnect_heatmap.png', dpi=150, bbox_inches='tight')
plt.savefig(f'{OUT}/penetration_disconnect_heatmap.pdf', bbox_inches='tight')
print(f'Saved {OUT}/penetration_disconnect_heatmap.png')


# ---------------------------------------------------------------------------
# Figure 3: Distribution of #disconnected, baseline vs 75%, grouped per scenario
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 5))

categories = [0, 1, 2, 3, 4]
x = np.arange(len(categories))
group_w = 0.13


def get_dist(results, scen):
    d = results['scenarios'][scen]['summary']['disconnection_distribution']
    d = {int(k): v for k, v in d.items()}
    return [d.get(c, 0) for c in categories]


offsets = np.array([-2.5, -1.5, -0.5, 0.5, 1.5, 2.5]) * group_w
series = []
for i, scen in enumerate(SCENS):
    base_dist = get_dist(base, scen)
    high_dist = get_dist(high, scen)
    short_label = scen.split('—')[0].strip()
    b1 = ax.bar(x + offsets[2*i], base_dist, group_w,
                label=f'21.5%  ({short_label})', color=COLORS[scen], alpha=0.4, edgecolor='black', hatch='//')
    b2 = ax.bar(x + offsets[2*i + 1], high_dist, group_w,
                label=f'75%    ({short_label})', color=COLORS[scen], alpha=0.95, edgecolor='black')
    series.extend([b1, b2])

ax.set_xticks(x)
ax.set_xticklabels([f'{c} VSCs\ndisconnected' for c in categories])
ax.set_ylabel('Number of fault buses', fontsize=11)
ax.set_title('Distribution of disconnection counts per fault — baseline vs 75% penetration',
             fontsize=12, fontweight='bold', color=TEAL)
ax.legend(fontsize=8, ncol=3, loc='upper right')
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(f'{OUT}/penetration_distribution.png', dpi=150, bbox_inches='tight')
plt.savefig(f'{OUT}/penetration_distribution.pdf', bbox_inches='tight')
print(f'Saved {OUT}/penetration_distribution.png')


# ---------------------------------------------------------------------------
# Figure 4: Summary metrics bar chart
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

metrics_base = {scen: base['scenarios'][scen]['summary'] for scen in SCENS}
metrics_high = {scen: high['scenarios'][scen]['summary'] for scen in SCENS}

scen_labels = ['A — 0.85', 'B — 0.50', 'C — 0.10']
xs = np.arange(3)
w = 0.35

ax = axes[0]
avg_base = [metrics_base[s]['avg_vscs_disconnected'] for s in SCENS]
avg_high = [metrics_high[s]['avg_vscs_disconnected'] for s in SCENS]
ax.bar(xs - w/2, avg_base, w, label='21.5%', color=TEAL, alpha=0.85)
ax.bar(xs + w/2, avg_high, w, label='75%', color=RED, alpha=0.85)
for i, (b, h) in enumerate(zip(avg_base, avg_high)):
    ax.text(i - w/2, b + 0.05, f'{b:.2f}', ha='center', fontsize=9)
    ax.text(i + w/2, h + 0.05, f'{h:.2f}', ha='center', fontsize=9)
ax.set_xticks(xs)
ax.set_xticklabels(scen_labels)
ax.set_ylabel('Avg # VSCs tripped per fault')
ax.set_title('Average disconnection count', fontsize=11, fontweight='bold', color=TEAL)
ax.set_ylim(0, max(avg_base + avg_high) * 1.2)
ax.legend(fontsize=9)
ax.grid(axis='y', alpha=0.3)

ax = axes[1]
maxlost_base = [metrics_base[s]['max_lost_generation_mw'] for s in SCENS]
maxlost_high = [metrics_high[s]['max_lost_generation_mw'] for s in SCENS]
ax.bar(xs - w/2, maxlost_base, w, label='21.5% (max 0.80 MW)', color=TEAL, alpha=0.85)
ax.bar(xs + w/2, maxlost_high, w, label='75%   (max 2.79 MW)', color=RED, alpha=0.85)
for i, (b, h) in enumerate(zip(maxlost_base, maxlost_high)):
    ax.text(i - w/2, b + 0.05, f'{b:.2f}', ha='center', fontsize=9)
    ax.text(i + w/2, h + 0.05, f'{h:.2f}', ha='center', fontsize=9)
ax.set_xticks(xs)
ax.set_xticklabels(scen_labels)
ax.set_ylabel('Max lost DER (MW)')
ax.set_title('Worst-case lost generation', fontsize=11, fontweight='bold', color=TEAL)
ax.set_ylim(0, max(maxlost_base + maxlost_high) * 1.15)
ax.legend(fontsize=9)
ax.grid(axis='y', alpha=0.3)

fig.suptitle('Headline metrics — penetration uplift impact',
             fontsize=13, fontweight='bold', color=TEAL)
plt.tight_layout()
plt.savefig(f'{OUT}/penetration_summary.png', dpi=150, bbox_inches='tight')
plt.savefig(f'{OUT}/penetration_summary.pdf', bbox_inches='tight')
print(f'Saved {OUT}/penetration_summary.png')

print('\nAll plots generated in', OUT)
