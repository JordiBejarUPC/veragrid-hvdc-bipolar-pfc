import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType, ResultTypes
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

# =============================================================================
# --- CONFIGURACIÓN GLOBAL PARA PRESENTACIÓN ---
# =============================================================================
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['font.size'] = 18
plt.rcParams['axes.titlesize'] = 24
plt.rcParams['axes.labelsize'] = 20
plt.rcParams['legend.fontsize'] = 16
plt.rcParams['lines.linewidth'] = 3


def apply_pfc_axis_labels(ax):
    ax.set_xlabel('PFC Control Setpoint $P_s$ (MW)')



# =============================================================================
# --- SIMULACIÓN Y RECOLECCIÓN DE DATOS ---
# =============================================================================
values = np.linspace(-0.01, -126, 80)  # Barrido solicitado
Sb = 100
Ub = 345

results_data = []

for val in values:
    grid = gce.open_file('case39_10_he_bis.veragrid')

    # PFC DC Buses
    bus_1s = gce.Bus(name="Bus_1s", Vnom=345, is_dc=True)
    grid.add_bus(bus_1s)
    bus_1t = gce.Bus(name="Bus_1t", Vnom=345, is_dc=True)
    grid.add_bus(bus_1t)

    # Adding the PFC
    grid.add_pfc(gce.PFC(name="PFC_0",
                         bus_dc_r=grid.buses[39],
                         bus_dc_s=bus_1s,
                         bus_dc_t=bus_1t,
                         control1=PfcControlType.Ps_dc,
                         control1_val=val))

    # DC Lines
    grid.add_dc_line(gce.DcLine(name="Line_1s_4_1", bus_from=bus_1s, bus_to=grid.buses[42], r=0.005))
    grid.add_dc_line(gce.DcLine(name="Line_1t_2_1", bus_from=bus_1t, bus_to=grid.buses[40], r=0.005))

    res = gce.power_flow(grid, options=gce.PowerFlowOptions(verbose=0))

    if res.iterations > 0:
        bus_df = res.get_bus_df()
        branch_df = res.get_branch_df()

        v1 = res.mdl(result_type=ResultTypes.PfcV1).get_data_frame().iloc[0, 0] * Ub
        v2 = res.mdl(result_type=ResultTypes.PfcV2).get_data_frame().iloc[0, 0] * Ub
        pb = res.mdl(result_type=ResultTypes.PfcPB).get_data_frame().iloc[0, 0] * Sb

        p14 = branch_df.loc['Line_1s_4_1', 'Pf']
        p12 = branch_df.loc['Line_1t_2_1', 'Pf']
        p24 = branch_df.loc[['2_4_1'], 'Pf'].sum()

        i14 = p14 / (bus_df.loc['Bus_1s', 'Vm'] * Ub)
        i12 = p12 / (bus_df.loc['Bus_1t', 'Vm'] * Ub)
        i24 = p24 / (bus_df.iloc[40]['Vm'] * Ub)

        results_data.append({
            'val': val, 'v1': v1, 'v2': v2, 'pb': pb,
            'p14': p14, 'p12': p12, "p24": p24, 'i14': i14, 'i12': i12, "i24": i24,
            'v_bus_1': bus_df.iloc[39]['Vm'] * Ub,
            'v_bus_s': bus_df.loc['Bus_1s', 'Vm'] * Ub,
            'v_bus_t': bus_df.loc['Bus_1t', 'Vm'] * Ub,
            "v_bus_2": bus_df.iloc[40]['Vm'] * Ub,
            "v_bus_4": bus_df.iloc[42]['Vm'] * Ub,
        })

df = pd.DataFrame(results_data)

# =============================================================================
# Graphs
# =============================================================================

# FIGURE 1: PFC Internal Power Balance vs V2 y V1
fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))
ax1.plot(df['v2'], df['pb'], 'b.-', label='Internal Power Balance')
ax1.set_title('PFC Internal Power Balance vs V2')
ax1.set_xlabel('$V2_{pfc}$ (kV)')
ax1.set_ylabel('$PB_{pfc}$ (MW)')
ax1.grid(True, linestyle=':')
ax1.legend()

ax2.plot(df['v1'], df['pb'], 'b.-', label='Internal Power Balance')
ax2.set_title('PFC Internal Power Balance vs V1')
ax2.set_xlabel('$V1_{pfc}$ (kV)')
ax2.set_ylabel('$PB_{pfc}$ (MW)')
ax2.grid(True, linestyle=':')
ax2.legend()
plt.tight_layout()
plt.show()

# FIGURA 2: PFC Internal Voltages vs Currents (V1 y V2 Dependency)
fig2, (ax3, ax4) = plt.subplots(2, 1, figsize=(16, 12))
ax3.plot(df['v1'], df['i14'], label='$I_{i14}$')
ax3.plot(df['v1'], df['i12'], label='$I_{i12}$')
ax3.plot(df['v1'], df['i24'], label='$I_{i24}$')
ax3.set_title('PFC Internal Voltages vs Currents (V1 Dependency)')
ax3.set_xlabel('$V1_{pfc}$ (kV)')
ax3.set_ylabel('$I_{Line}$ (kA)')
ax3.grid(True, linestyle=':')
ax3.legend()

ax4.plot(df['v2'], df['i14'], label='$I_{i14}$')
ax4.plot(df['v2'], df['i12'], label='$I_{i12}$')
ax4.plot(df['v2'], df['i24'], label='$I_{i24}$')
ax4.set_title('PFC Internal Voltages vs Currents (V2 Dependency)')
ax4.set_xlabel('$V2_{pfc}$ (kV)')
ax4.set_ylabel('$I_{Line}$ (kA)')
ax4.grid(True, linestyle=':')
ax4.legend()
plt.tight_layout()
plt.show()

# FIGURA 3: Combined Currents Graph (vs Control Ps)
fig3, ax_com_i = plt.subplots(figsize=(16, 10))
ax_com_i.plot(df['val'], df['i14'], color='#b82e21', label='$I_{14}$')
ax_com_i.plot(df['val'], df['i12'], color='#448f44', label='$I_{12}$')
ax_com_i.set_title('Currents vs PFC Control Setpoint')
ax_com_i.set_ylabel('$I_{Line}$ (kA)')
apply_pfc_axis_labels(ax_com_i)
ax_com_i.grid(True, linestyle=':')
ax_com_i.legend()
plt.tight_layout()
plt.show()

# FIGURA 4: Contingency (Power Graph) - Áreas de Contingencia
fig4, ax_cont = plt.subplots(figsize=(16, 9))
ax_cont.plot(df['val'], df['p14'], color='#b82e21', label='$\mathbf{P_{14}}$')
ax_cont.plot(df['val'], df['p12'], color='#448f44', label='$\mathbf{P_{12}}$')
ax_cont.plot(df['val'], df['p24'], color='#2c328e', label='$\mathbf{P_{24}}$')
# ax_cont.plot(df['val'], df['p14'] + df['p12'], color='#f5911e', label='$\mathbf{P_{Total}}$')

ax_cont.set_title('Meshed Lines Power Analysis')
ax_cont.set_ylabel('Power (MW)')
apply_pfc_axis_labels(ax_cont)
ax_cont.grid(True, linestyle=':')
ax_cont.legend(loc='lower right', ncol=3)
plt.tight_layout()
plt.show()

# FIGURA 5: Contingency (Power Graph) - Áreas de Contingencia
fig5, ax_cont = plt.subplots(figsize=(16, 9))
ax_cont.plot(df['v1'], df['p14'], color='#b82e21', label='$\mathbf{P_{14}}$')
ax_cont.plot(df['v1'], df['p12'], color='#448f44', label='$\mathbf{P_{12}}$')
ax_cont.plot(df['v1'], df['p24'], color='#2c328e', label='$\mathbf{P_{24}}$')
# ax_cont.plot(df['val'], df['p14'] + df['p12'], color='#f5911e', label='$\mathbf{P_{Total}}$')

ax_cont.set_title('Meshed Lines Power Analysis')
ax_cont.set_ylabel('Power (MW)')
ax_cont.set_xlabel('$V1_{pfc}$ (kV)')
ax_cont.grid(True, linestyle=':')
ax_cont.legend(loc='lower right', ncol=3)
plt.tight_layout()
plt.show()

# FIGURA 6: Contingency (Power Graph) - Áreas de Contingencia
fig6, ax_cont = plt.subplots(figsize=(16, 9))
ax_cont.plot(df['v2'], df['p14'], color='#b82e21', label='$\mathbf{P_{14}}$')
ax_cont.plot(df['v2'], df['p12'], color='#448f44', label='$\mathbf{P_{12}}$')
ax_cont.plot(df['v2'], df['p24'], color='#2c328e', label='$\mathbf{P_{24}}$')
# ax_cont.plot(df['val'], df['p14'] + df['p12'], color='#f5911e', label='$\mathbf{P_{Total}}$')

ax_cont.set_title('Meshed Lines Power Analysis')
ax_cont.set_ylabel('Power (MW)')
ax_cont.set_xlabel('$V1_{pfc}$ (kV)')
ax_cont.grid(True, linestyle=':')
ax_cont.legend(loc='lower right', ncol=3)
plt.tight_layout()
plt.show()

# FIGURA 10: PFC Internal Voltages vs Control Setpoint (El eslabón perdido)
fig10, ax_v_ps = plt.subplots(figsize=(16, 9))
ax_v_ps.plot(df['val'], df['v1'], color='#9b59b6', label='$V1_{pfc}$')
ax_v_ps.plot(df['val'], df['v2'], color='#e67e22', label='$V2_{pfc}$')

ax_v_ps.set_title('PFC Internal Voltages vs Control Setpoint')
ax_v_ps.set_ylabel('Internal Voltage (kV)')
apply_pfc_axis_labels(ax_v_ps) # Usa tu función para el eje X: Ps (MW)
ax_v_ps.grid(True, linestyle=':')
ax_v_ps.legend()
plt.tight_layout()
plt.show()

# FIGURA 7: Bus Voltages Graph
fig7, ax_bus = plt.subplots(figsize=(16, 10))
ax_bus.plot(df['val'], df['v_bus_r'], label='$V_{Bus\_R}$ (Node 39)')
ax_bus.plot(df['val'], df['v_bus_s'], label='$V_{Bus\_14}$')
ax_bus.plot(df['val'], df['v_bus_t'], label='$V_{Bus\_12}$')
ax_bus.set_title('PFC Bus Voltages Analysis')
ax_bus.set_ylabel('$V_{Bus}$ (kV)')
apply_pfc_axis_labels(ax_bus)
ax_bus.grid(True, linestyle=':')
ax_bus.legend()
plt.tight_layout()
plt.show()


# FIGURA 8: Power exchanged by the internal voltage sources
p_internal = np.abs(df['v1'] * df['i14'])  # MW aprox
fig8, ax_pex = plt.subplots(figsize=(16, 10))
ax_pex.plot(df['val'], p_internal, color='blue', label='Internal Power $P$')
ax_pex.set_title('Power Exchanged by Internal Voltage Sources')
ax_pex.set_ylabel('$P$ (MW)')
apply_pfc_axis_labels(ax_pex)
ax_pex.grid(True, linestyle=':')
ax_pex.set_ylim(0, p_internal.max() * 1.1)
plt.tight_layout()
plt.show()

# FIGURA 9: PFC Control Range (V1 vs V2)
fig9, ax_range = plt.subplots(figsize=(16, 10))
ax_range.plot(df['v2'], df['v1'], 'b.-', label='V1-V2 Locus')
ax_range.set_title('PFC Operational Locus: V1 vs V2')
ax_range.set_xlabel('$V2_{pfc}$ (kV)')
ax_range.set_ylabel('$V1_{pfc}$ (kV)')
ax_range.grid(True)
ax_range.legend()
plt.tight_layout()
plt.show()

