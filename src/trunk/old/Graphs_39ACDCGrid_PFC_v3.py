import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType, ResultTypes
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# =============================================================================
# --- CONFIGURACIÓN GLOBAL PARA PRESENTACIÓN ---
# =============================================================================
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['font.size'] = 18
plt.rcParams['axes.titlesize'] = 24
plt.rcParams['axes.labelsize'] = 20
plt.rcParams['lines.linewidth'] = 3

Sb = 100
Ub = 345

results_data_1 = []
results_data_2 = []

ac_lines_names = []
dc_lines_names = []

# =============================================================================
# BUCLE 1: Barrido V2
# =============================================================================
values_v2 = np.arange(-2, 0.05, 0.1)

for val in values_v2:
    grid = gce.open_file('case39_10_he_bis.veragrid')

    # PFC DC Buses
    bus_1s = gce.Bus(name="Bus_1s", Vnom=345, is_dc=True)
    grid.add_bus(bus_1s)
    bus_1t = gce.Bus(name="Bus_1t", Vnom=345, is_dc=True)
    grid.add_bus(bus_1t)

    # Adding the PFC
    grid.add_pfc(gce.PFC(name="PFC_0", bus_dc_r=grid.buses[39], bus_dc_s=bus_1s, bus_dc_t=bus_1t,
                         control1=PfcControlType.V2_pfc, control1_val=val/Ub))

    # DC Lines
    grid.add_dc_line(gce.DcLine(name="Line_1s_4_1", bus_from=bus_1s, bus_to=grid.buses[42], r=0.005))
    grid.add_dc_line(gce.DcLine(name="Line_1t_2_1", bus_from=bus_1t, bus_to=grid.buses[40], r=0.005))

    res = gce.power_flow(grid, options=gce.PowerFlowOptions(verbose=0))

    if res.iterations > 0:
        if not ac_lines_names:
            ac_lines_names = [line.name for line in grid.lines]
            dc_lines_names = [line.name for line in grid.dc_lines]

        bus_df = res.get_bus_df()
        branch_df = res.get_branch_df()

        v1 = res.mdl(result_type=ResultTypes.PfcV1).get_data_frame().iloc[0, 0] * Ub
        v2 = res.mdl(result_type=ResultTypes.PfcV2).get_data_frame().iloc[0, 0] * Ub

        p14 = branch_df.loc['Line_1s_4_1', 'Pf']
        p12 = branch_df.loc['Line_1t_2_1', 'Pf']
        i14 = p14 / (bus_df.loc['Bus_1s', 'Vm'] * Ub)
        i12 = p12 / (bus_df.loc['Bus_1t', 'Vm'] * Ub)

        row_data = branch_df['Pf'].to_dict()
        row_data.update({'v1': v1, 'v2': v2, 'i14': i14, 'i12': i12, 'val': val})
        results_data_1.append(row_data)

df1 = pd.DataFrame(results_data_1)


# =============================================================================
# BUCLE 2: Barrido V1
# =============================================================================
values_v1 = np.arange(-0.01, 5, 0.1)

for val in values_v1:
    grid = gce.open_file('case39_10_he_bis.veragrid')

    # PFC DC Buses
    bus_1s = gce.Bus(name="Bus_1s", Vnom=345, is_dc=True)
    grid.add_bus(bus_1s)
    bus_1t = gce.Bus(name="Bus_1t", Vnom=345, is_dc=True)
    grid.add_bus(bus_1t)

    # Adding the PFC
    grid.add_pfc(gce.PFC(name="PFC_0", bus_dc_r=grid.buses[39], bus_dc_s=bus_1s, bus_dc_t=bus_1t,
                         control1=PfcControlType.V1_pfc, control1_val=val/Ub))

    # DC Lines
    grid.add_dc_line(gce.DcLine(name="Line_1s_4_1", bus_from=bus_1s, bus_to=grid.buses[42], r=0.005))
    grid.add_dc_line(gce.DcLine(name="Line_1t_2_1", bus_from=bus_1t, bus_to=grid.buses[40], r=0.005))

    res = gce.power_flow(grid, options=gce.PowerFlowOptions(verbose=0))

    if res.iterations > 0:
        bus_df = res.get_bus_df()
        branch_df = res.get_branch_df()

        v1 = res.mdl(result_type=ResultTypes.PfcV1).get_data_frame().iloc[0, 0] * Ub
        v2 = res.mdl(result_type=ResultTypes.PfcV2).get_data_frame().iloc[0, 0] * Ub

        p14 = branch_df.loc['Line_1s_4_1', 'Pf']
        p12 = branch_df.loc['Line_1t_2_1', 'Pf']
        i14 = p14 / (bus_df.loc['Bus_1s', 'Vm'] * Ub)
        i12 = p12 / (bus_df.loc['Bus_1t', 'Vm'] * Ub)

        row_data = branch_df['Pf'].to_dict()
        row_data.update({'v1': v1, 'v2': v2, 'i14': i14, 'i12': i12, 'val': val})
        results_data_2.append(row_data)

df2 = pd.DataFrame(results_data_2)

# =============================================================================
# APLICACIÓN DE MÁSCARAS (CORRIENTES CONTROLADAS POSITIVAS)
# =============================================================================
df1_valid = df1[df1['i12'] > 0].copy()
df2_valid = df2[df2['i14'] > 0].copy()


# =============================================================================
# LOS 4 GRÁFICOS: Controlabilidad vs TODAS las Potencias (DC y AC)
# =============================================================================

# 1. Control V1 vs Potencias Líneas DC
fig_v1_dc, ax_v1_dc = plt.subplots(figsize=(16, 10))
for line in dc_lines_names:
    if line in df2_valid.columns:
        ax_v1_dc.plot(df2_valid['v1'], df2_valid[line], label=line)
ax_v1_dc.set_title('Control V1 vs Todas las Potencias DC ($i_{14} > 0$)')
ax_v1_dc.set_xlabel('$V1_{pfc}$ (kV)')
ax_v1_dc.set_ylabel('Potencia (MW)')
ax_v1_dc.axhline(0, color='black', linewidth=1.5, linestyle='--')
ax_v1_dc.grid(True, linestyle=':')
# mode="expand" fuerza a la leyenda a ocupar todo el ancho del bbox definido
ax_v1_dc.legend(loc='upper center', bbox_to_anchor=(0.0, -0.25, 1.0, 0.1), mode="expand",
                ncol=4, fontsize=14, fancybox=True, shadow=True, borderaxespad=0.)
plt.subplots_adjust(bottom=0.25)
plt.show()

# 2. Control V2 vs Potencias Líneas DC
fig_v2_dc, ax_v2_dc = plt.subplots(figsize=(16, 10))
for line in dc_lines_names:
    if line in df1_valid.columns:
        ax_v2_dc.plot(df1_valid['v2'], df1_valid[line], label=line)
ax_v2_dc.set_title('Control V2 vs Todas las Potencias DC ($i_{12} > 0$)')
ax_v2_dc.set_xlabel('$V2_{pfc}$ (kV)')
ax_v2_dc.set_ylabel('Potencia (MW)')
ax_v2_dc.axhline(0, color='black', linewidth=1.5, linestyle='--')
ax_v2_dc.grid(True, linestyle=':')
ax_v2_dc.legend(loc='upper center', bbox_to_anchor=(0.0, -0.25, 1.0, 0.1), mode="expand",
                ncol=4, fontsize=14, fancybox=True, shadow=True, borderaxespad=0.)
plt.subplots_adjust(bottom=0.25)
plt.show()

# 3. Control V1 vs Potencias Líneas AC
fig_v1_ac, ax_v1_ac = plt.subplots(figsize=(18, 12))
for line in ac_lines_names:
    if line in df2_valid.columns:
        ax_v1_ac.plot(df2_valid['v1'], df2_valid[line], label=line)
ax_v1_ac.set_title('Control V1 vs Todas las Potencias AC ($i_{14} > 0$)')
ax_v1_ac.set_xlabel('$V1_{pfc}$ (kV)')
ax_v1_ac.set_ylabel('Potencia (MW)')
ax_v1_ac.axhline(0, color='black', linewidth=1.5, linestyle='--')
ax_v1_ac.grid(True, linestyle=':')
# Usamos ncol=6 o más para las líneas AC para que quede bien distribuido a lo ancho
ax_v1_ac.legend(loc='upper center', bbox_to_anchor=(0.0, -0.3, 1.0, 0.1), mode="expand",
                ncol=6, fontsize=12, fancybox=True, shadow=True, borderaxespad=0.)
plt.subplots_adjust(bottom=0.35)
plt.show()

# 4. Control V2 vs Potencias Líneas AC
fig_v2_ac, ax_v2_ac = plt.subplots(figsize=(18, 12))
for line in ac_lines_names:
    if line in df1_valid.columns:
        ax_v2_ac.plot(df1_valid['v2'], df1_valid[line], label=line)
ax_v2_ac.set_title('Control V2 vs Todas las Potencias AC ($i_{12} > 0$)')
ax_v2_ac.set_xlabel('$V2_{pfc}$ (kV)')
ax_v2_ac.set_ylabel('Potencia (MW)')
ax_v2_ac.axhline(0, color='black', linewidth=1.5, linestyle='--')
ax_v2_ac.grid(True, linestyle=':')
ax_v2_ac.legend(loc='upper center', bbox_to_anchor=(0.0, -0.3, 1.0, 0.1), mode="expand",
                ncol=6, fontsize=12, fancybox=True, shadow=True, borderaxespad=0.)
plt.subplots_adjust(bottom=0.35)
plt.show()