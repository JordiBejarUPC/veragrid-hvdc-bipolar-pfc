import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType
from VeraGridEngine.enumerations import ResultTypes
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

# =============================================================================
# --- CONFIGURACIÓN GLOBAL PARA POWERPOINT (16:9 y Letras Grandes) ---
# =============================================================================
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['font.size'] = 24
plt.rcParams['axes.titlesize'] = 40
plt.rcParams['axes.labelsize'] = 24
plt.rcParams['xtick.labelsize'] = 22
plt.rcParams['ytick.labelsize'] = 22
plt.rcParams['legend.fontsize'] = 20
plt.rcParams['lines.linewidth'] = 3.5


# --- FUNCIÓN AUXILIAR PARA EL EJE X COMBINADO ---
def apply_combined_axis_labels(ax):
    ax.set_xticks([-4, -2, 0, 2, 4, 6])
    ax.set_xlabel('\n\n')
    ax.text(-2, -0.12, r'$V1_{pfc}$', transform=ax.get_xaxis_transform(), ha='center', va='top', clip_on=False)
    ax.text(0, -0.12, r'$(kV)$', transform=ax.get_xaxis_transform(), ha='center', va='top', clip_on=False)
    ax.text(3, -0.12, r'$V2_{pfc}$', transform=ax.get_xaxis_transform(), ha='center', va='top', clip_on=False)


# =============================================================================
# --- PARÁMETROS DE SIMULACIÓN ---
# =============================================================================
Ub = 150
Sb = 100
Rb = (Ub ** 2) / Sb
Ib = Sb / Ub

rlin_12, rlin_13, rlin_23 = 2, 3, 1  # ohms

Pg1 = 160  # MW
Pg2 = 80  # MW

V1_pfc_list, V2_pfc_list = [], []
p_v1_internal_list, p_v2_internal_list, p_PB_internal_list = [], [], []
I12_list, I13_list, I23_list = [], [], []
P12_list, P13_list, P23_list, P1_list = [], [], [], []
v1_bus_list, v2_bus_list = [], []

values = np.arange(0.1, 232.32, 1)

# =============================================================================
# --- BUCLE DE SIMULACIÓN ---
# =============================================================================
for i in values:
    grid = gce.MultiCircuit(name="pfc_validation")

    ## AC Grid buses
    bus1_ac = gce.Bus(name="Bus1_ac", Vnom=Ub, is_slack=True)
    grid.add_bus(bus1_ac)
    grid.add_generator(bus1_ac, gce.Generator(name='g1', vset=1.0))

    bus2_ac = gce.Bus(name="Bus2_ac", Vnom=Ub, is_slack=True)
    grid.add_bus(bus2_ac)
    grid.add_generator(bus2_ac, gce.Generator(name='g2', vset=1.0))

    bus3_ac = gce.Bus(name="Bus3_ac", Vnom=Ub, is_slack=True)
    grid.add_bus(bus3_ac)
    grid.add_generator(bus3_ac, gce.Generator(name='g3', vset=1.0))

    ## DC Grid buses
    bus1_dc = gce.Bus(name="Bus1_dc", Vnom=Ub, is_dc=True)
    grid.add_bus(bus1_dc)
    bus2_dc = gce.Bus(name="Bus2_dc", Vnom=Ub, is_dc=True)
    grid.add_bus(bus2_dc)
    bus3_dc = gce.Bus(name="Bus3_dc", Vnom=Ub, is_dc=True)
    grid.add_bus(bus3_dc)

    ## Adding the PFC
    busS_dc = gce.Bus(name="busS_dc", Vnom=Ub, is_dc=True)
    grid.add_bus(busS_dc)
    busT_dc = gce.Bus(name="busT_dc", Vnom=Ub, is_dc=True)
    grid.add_bus(busT_dc)

    grid.add_pfc(gce.PFC(name="PFC_0", bus_dc_r=bus3_dc, bus_dc_s=busS_dc, bus_dc_t=busT_dc,
                         control1=PfcControlType.Ps_dc, control1_val=i))

    # DC lines
    grid.add_dc_line(gce.DcLine(name="dc_line_12", bus_from=bus1_dc, bus_to=bus2_dc, r=rlin_12 / Rb))
    grid.add_dc_line(gce.DcLine(name="dc_line_13", bus_from=bus1_dc, bus_to=busS_dc, r=rlin_13 / Rb))
    grid.add_dc_line(gce.DcLine(name="dc_line_23", bus_from=bus2_dc, bus_to=busT_dc, r=rlin_23 / Rb))

    # VSC
    grid.add_vsc(gce.VSC(name="VSC_1", bus_from=bus1_dc, bus_to=bus1_ac, alpha1=0.01, alpha2=0.01, alpha3=0.01,
                         control1=ConverterControlType.Pdc, control2=ConverterControlType.Qac, control1_val=-Pg1,
                         control2_val=0.0))
    grid.add_vsc(gce.VSC(name="VSC_2", bus_from=bus2_dc, bus_to=bus2_ac, alpha1=0.01, alpha2=0.01, alpha3=0.01,
                         control1=ConverterControlType.Pdc, control2=ConverterControlType.Qac, control1_val=-Pg2,
                         control2_val=0.0))
    grid.add_vsc(gce.VSC(name="VSC_3", bus_from=bus3_dc, bus_to=bus3_ac, alpha1=0.01, alpha2=0.01, alpha3=0.01,
                         control1=ConverterControlType.Vm_dc, control2=ConverterControlType.Qac, control1_val=1.0,
                         control2_val=0.0))

    options_pf = gce.PowerFlowOptions(verbose=0, generate_report=False, retry_with_other_methods=False)
    results = gce.power_flow(grid, options=options_pf)

    if results.iterations > 0:
        v1_value = results.mdl(result_type=ResultTypes.PfcV1).get_data_frame().iloc[0, 0] * Ub
        v2_value = results.mdl(result_type=ResultTypes.PfcV2).get_data_frame().iloc[0, 0] * Ub
        p_PB_internal_value = results.mdl(result_type=ResultTypes.PfcPB).get_data_frame().iloc[0, 0] * Sb

        bus_df = results.get_bus_df()
        branch_df = results.get_branch_df()

        i12 = (branch_df.loc['dc_line_12', 'Pf'] / Sb) / bus_df.loc['Bus1_dc', 'Vm'] * Ib
        i13 = (branch_df.loc['dc_line_13', 'Pf'] / Sb) / bus_df.loc['Bus1_dc', 'Vm'] * Ib
        i23 = (branch_df.loc['dc_line_23', 'Pf'] / Sb) / bus_df.loc['Bus2_dc', 'Vm'] * Ib

        v1_bus = bus_df.loc['Bus1_dc', 'Vm'] * Ub
        v2_bus = bus_df.loc['Bus2_dc', 'Vm'] * Ub

        P12_list.append(branch_df.loc['dc_line_12', 'Pf'])
        P13_list.append(branch_df.loc['dc_line_13', 'Pf'])
        P23_list.append(branch_df.loc['dc_line_23', 'Pf'])
        P1_list.append(Pg1)

        I12_list.append(i12)
        I13_list.append(i13)
        I23_list.append(i23)

        v1_bus_list.append(v1_bus)
        v2_bus_list.append(v2_bus)

        p_PB_internal_list.append(p_PB_internal_value)
        V1_pfc_list.append(v1_value)
        V2_pfc_list.append(v2_value)
    else:
        V1_pfc_list.append(0)
        V2_pfc_list.append(0)

# Convertir a arrays de numpy para facilitar el indexado y plot
v1_arr = np.array(V1_pfc_list)
v2_arr = np.array(V2_pfc_list)
p_PB_internal_arr = np.array(p_PB_internal_list)
i12_arr = np.array(I12_list)
i13_arr = np.array(I13_list)
i23_arr = np.array(I23_list)
v1_bus_arr = np.array(v1_bus_list)
v2_bus_arr = np.array(v2_bus_list)
p12_arr = np.array(P12_list)
p13_arr = np.array(P13_list)
p23_arr = np.array(P23_list)
p1_arr = np.array(P1_list)

eje_x_com = np.where(values < (max(values) / 2), v1_arr, v2_arr)

# =============================================================================
# FIGURA 1: PFC Internal Power Balance vs V2 y V1
# =============================================================================
fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))

ax1.plot(v2_arr, p_PB_internal_arr, 'b.-', markersize=6, label='Internal Power Balance')
ax1.set_title('PFC Internal Power Balance vs V2')
ax1.set_xlabel('$V2_{pfc}$ (kV)')
ax1.set_ylabel('$PB_{pfc}$ (MW)')
ax1.grid(True, linestyle=':', alpha=0.6)
ax1.legend()

ax2.plot(v1_arr, p_PB_internal_arr, 'b.-', markersize=6, label='Internal Power Balance')
ax2.set_title('PFC Internal Power Balance vs V1')
ax2.set_xlabel('$V1_{pfc}$ (kV)')
ax2.set_ylabel('$PB_{pfc}$ (MW)')
ax2.grid(True, linestyle=':', alpha=0.6)
ax2.legend()

plt.tight_layout()
plt.show()

# =============================================================================
# FIGURA 2: PFC Internal Voltages vs Currents (Dependencias separadas)
# =============================================================================
fig2, (ax3, ax4) = plt.subplots(2, 1, figsize=(16, 12))

ax3.plot(v1_arr, I12_list, label='$I_{12}$')
ax3.plot(v1_arr, I13_list, label='$I_{13}$')
ax3.plot(v1_arr, I23_list, label='$I_{23}$')
ax3.set_title('PFC Internal Voltages vs Currents (V1 Dependency)')
ax3.set_xlabel('$V1_{pfc}$ (kV)')
ax3.set_ylabel('$I_{Line}$ (kA)')
ax3.grid(True, linestyle=':', alpha=0.6)
ax3.legend(loc='center left')

ax4.plot(v2_arr, I12_list, label='$I_{12}$')
ax4.plot(v2_arr, I13_list, label='$I_{13}$')
ax4.plot(v2_arr, I23_list, label='$I_{23}$')
ax4.set_title('PFC Internal Voltages vs Currents (V2 Dependency)')
ax4.set_xlabel('$V2_{pfc}$ (kV)')
ax4.set_ylabel('$I_{Line}$ (kA)')
ax4.grid(True, linestyle=':', alpha=0.6)
ax4.legend(loc='center right')

plt.tight_layout()
plt.show()

# =============================================================================
# FIGURA 3: Combined Currents Graph
# =============================================================================
idx_end = ~np.isnan(i13_arr)
fig3, ax_com_i = plt.subplots(figsize=(16, 12))

ax_com_i.plot(eje_x_com, i13_arr, color='#b82e21', label='$I_{13}$')
ax_com_i.plot(eje_x_com, i23_arr, color='#448f44', label='$I_{23}$')
ax_com_i.plot(eje_x_com, i12_arr, color='#2c328e', label='$I_{12}$')

ax_com_i.axvline(0, color='black', linewidth=1.5)
ax_com_i.set_title('PFC Internal Voltages vs Currents')
ax_com_i.set_ylabel('$I_{Line}$ (kA)')
ax_com_i.grid(True, linestyle=':', alpha=0.6)

apply_combined_axis_labels(ax_com_i)

if any(idx_end):
    ax_com_i.text(eje_x_com[idx_end][-1], i13_arr[idx_end][-1] + 0.05, '$I_{13}$')
    ax_com_i.text(eje_x_com[idx_end][-1], i23_arr[idx_end][-1] + 0.05, '$I_{23}$')
    ax_com_i.text(eje_x_com[idx_end][-1], i12_arr[idx_end][-1] + 0.05, '$I_{12}$')

plt.tight_layout()
plt.show()

# =============================================================================
# FIGURA 4: Contingency (Power Graph) - Áreas de Contingencia
# =============================================================================
fig4, ax_cont = plt.subplots(figsize=(16, 9))

# 1. Sustitución de P1 por la suma de P12, P13 y P23
p_total_arr = p13_arr + p23_arr

ax_cont.plot(eje_x_com, p12_arr, color='#2c328e', label='$\mathbf{P_{12}}$')
ax_cont.plot(eje_x_com, p13_arr, color='#b82e21', label='$\mathbf{P_{13}}$')
ax_cont.plot(eje_x_com, p23_arr, color='#448f44', label='$\mathbf{P_{23}}$')
# Ploteamos la suma total en lugar de P1
ax_cont.plot(eje_x_com, p_total_arr, color='#f5911e', label='$\mathbf{P_{3}}$')

ax_cont.axhline(20, color='black', linestyle='--', linewidth=2, dashes=(4, 4))
ax_cont.axhline(-20, color='black', linestyle='--', linewidth=2, dashes=(4, 4))
ax_cont.axvline(0, color='black', linewidth=1.5)

y_min_fill, y_max_fill = -100, 250
ax_cont.fill_between(eje_x_com, y_min_fill, y_max_fill, where=(np.abs(p12_arr) <= 20), facecolor='#c8c8e6', alpha=0.7,
                     interpolate=True)
ax_cont.fill_between(eje_x_com, y_min_fill, y_max_fill, where=(np.abs(p13_arr) <= 20), facecolor='#f3dcd4', alpha=0.7,
                     interpolate=True)
ax_cont.fill_between(eje_x_com, y_min_fill, y_max_fill, where=(np.abs(p23_arr) <= 20), facecolor='#d2ebd2', alpha=0.7,
                     interpolate=True)

ax_cont.text(0, 0, 'Contingency Area', ha='center', va='center', fontweight='bold',
             bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=6))

ax_cont.set_title('PFC Power Contingency Area Analysis')
ax_cont.set_ylabel('Power (MW)')
x_min, x_max = min(eje_x_com), max(eje_x_com)
ax_cont.set_xlim([x_min, x_max])
ax_cont.set_ylim([-100, 250])
ax_cont.set_yticks([-100, -50, -20, 0, 20, 50, 100, 150, 200, 250])
ax_cont.grid(True, linestyle=':', alpha=0.6)

apply_combined_axis_labels(ax_cont)

# 2. Reubicación de leyendas para evitar solapamiento con el título
legend_lines = ax_cont.legend(loc='lower right', framealpha=1, edgecolor='black', ncol=2)
patch_L12 = mpatches.Patch(color='#c8c8e6', label='$\mathbf{L_{12}}$')
patch_L13 = mpatches.Patch(color='#f3dcd4', label='$\mathbf{L_{13}}$')
patch_L23 = mpatches.Patch(color='#d2ebd2', label='$\mathbf{L_{23}}$')

# Movida a 'lower left' (esquina inferior izquierda) dentro del gráfico
legend_areas = ax_cont.legend(handles=[patch_L12, patch_L13, patch_L23], loc='lower left',
                              ncol=3, framealpha=1, edgecolor='black')
ax_cont.add_artist(legend_lines)

plt.tight_layout()
plt.show()

# =============================================================================
# FIGURA 5: Bus Voltages Graph
# =============================================================================
idx_end_v = ~np.isnan(v1_bus_arr)
fig5, ax_bus = plt.subplots(figsize=(16, 12))

ax_bus.plot(eje_x_com, v1_bus_arr, color='red', label='$V_{1}$')
ax_bus.plot(eje_x_com, v2_bus_arr, color='blue', label='$V_{2}$')

ax_bus.axvline(0, color='black', linewidth=1.5)
ax_bus.set_title('PFC Bus Voltages Analysis')
ax_bus.set_ylabel('$V_{Bus}$ (kV)')
ax_bus.grid(True, linestyle=':', alpha=0.6)

apply_combined_axis_labels(ax_bus)

if any(idx_end_v):
    ax_bus.text(eje_x_com[idx_end_v][-1], v1_bus_arr[idx_end_v][-1] + 0.05, '$V_{1}$')
    ax_bus.text(eje_x_com[idx_end_v][-1], v2_bus_arr[idx_end_v][-1] + 0.05, '$V_{2}$')

plt.tight_layout()
plt.show()

# =============================================================================
# FIGURA 6: Power exchanged by the internal voltage sources
# =============================================================================
p_calc_1 = v1_arr * i13_arr
p_calc_2 = v2_arr * i23_arr
p_total_com = np.where(values < (max(values) / 2), np.abs(p_calc_1), np.abs(p_calc_2))

fig6, ax_pex = plt.subplots(figsize=(16, 12))
ax_pex.plot(eje_x_com, p_total_com, color='blue', label='Internal Power $P$')

ax_pex.axvline(0, color='black', linewidth=1.5)
ax_pex.axhline(0, color='black', linewidth=1.5)

ax_pex.set_title('Power Exchanged by Internal Voltage Sources')
ax_pex.set_ylabel('$P$ (MW)')
ax_pex.grid(True, linestyle=':', alpha=0.6)
ax_pex.set_ylim(0, max(p_total_com) * 1.2)

apply_combined_axis_labels(ax_pex)

plt.tight_layout()
plt.show()

# =============================================================================
# FIGURA 7: PFC Control Range (V1 vs V2)
# =============================================================================
fig7, ax_range = plt.subplots(figsize=(16, 12))
ax_range.plot(v2_arr, v1_arr, 'b.-', markersize=6, label='V1-V2 Curve')
ax_range.set_title('PFC Control Range: V1 vs V2')
ax_range.set_xlabel('$V2_{pfc}$ (kV)')
ax_range.set_ylabel('$V1_{pfc}$ (kV)')
ax_range.grid(True, linestyle='-', alpha=0.6)
ax_range.legend(loc='lower right')

plt.tight_layout()
plt.show()

# =============================================================================
# FIGURA 8: Internal Voltages vs PFC Control Setpoint (Ps)
# =============================================================================
fig8, ax8 = plt.subplots(figsize=(16, 9))

ax8.plot(values, v1_arr, color='#9b59b6', label='$V1_{pfc}$', linewidth=4)
ax8.plot(values, v2_arr, color='#e67e22', label='$V2_{pfc}$', linewidth=4)

ax8.set_title('PFC Internal Voltages vs Control Setpoint')
ax8.set_xlabel('PFC Control Setpoint $P_s$ (MW)')
ax8.set_ylabel('Internal Voltage (kV)')

ax8.grid(True, linestyle=':', alpha=0.6)
ax8.legend(loc='upper left')

plt.tight_layout()
plt.show()

plt.show()