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

print("sistema v2")
values = np.arange(-7.9, 0.95, 0.1)
Sb = 100
Ub = 345

results_data = []
val_list=[]
for val in values:
    val_list.append(val)
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
                         control1=PfcControlType.V2_pfc,
                         control1_val=val/Ub))

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

df1 = pd.DataFrame(results_data)


fig1a, ax1a = plt.subplots(figsize=(16, 10))
ax1a.plot(val_list, df1['i14'], color='red', label='i14')
ax1a.plot(val_list, df1['i12'], color='blue', label='i12')
ax1a.plot(val_list, df1['i24'], color='green', label='i24')
ax1a.axhline(0, color='red', linewidth=1.5, linestyle='--')
ax1a.set_title('V2 vs Currents')
ax1a.set_xlabel('V2 (kV)')
ax1a.set_ylabel('Current (kA)')
ax1a.grid(True, linestyle=':')
ax1a.legend()
plt.tight_layout()
plt.show()

fig2a, ax2a = plt.subplots(figsize=(16, 10))
ax2a.plot(val_list, df1['p14'], color='red', label='p14')
ax2a.plot(val_list, df1['p12'], color='blue', label='p12')
ax2a.plot(val_list, df1['p24'], color='green', label='p24')
ax2a.axhline(0, color='red', linewidth=1.5, linestyle='--')
ax2a.set_title('V2 vs Line Powers')
ax2a.set_xlabel('V2 (kV)')
ax2a.set_ylabel('Power (MW)')
ax2a.grid(True, linestyle=':')
ax2a.legend()
plt.tight_layout()
plt.show()

print("sistema v1")
values = np.arange(0.01, 8.1, 0.1)
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
                         control1=PfcControlType.V1_pfc,
                         control1_val=val/Ub))

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

df2 = pd.DataFrame(results_data)


fig1b, ax1b = plt.subplots(figsize=(16, 10))
ax1b.plot(df2['v1'], df2['i14'], color='red', label='i14')
ax1b.plot(df2['v1'], df2['i12'], color='blue', label='i12')
ax1b.plot(df2['v1'], df2['i24'], color='green', label='i24')
ax1b.axhline(0, color='red', linewidth=1.5, linestyle='--')
ax1b.set_title('V1 vs Currents')
ax1b.set_xlabel('V1 (kV)')
ax1b.set_ylabel('Current (kA)')
ax1b.grid(True, linestyle=':')
ax1b.legend()
plt.tight_layout()
plt.show()

fig2b, ax2b = plt.subplots(figsize=(16, 10))
ax2b.plot(df2['v1'], df2['p14'], color='red', label='p14')
ax2b.plot(df2['v1'], df2['p12'], color='blue', label='p12')
ax2b.plot(df2['v1'], df2['p24'], color='green', label='p24')
ax2b.axhline(0, color='red', linewidth=1.5, linestyle='--')
ax2b.set_title('V1 vs Line Powers')
ax2b.set_xlabel('V1 (kV)')
ax2b.set_ylabel('Power (MW)')
ax2b.grid(True, linestyle=':')
ax2b.legend()
plt.tight_layout()
plt.show()

# # =============================================================================
# #Grafic controlabilitat de voltatge
# # =============================================================================
# mask_df1 = df1['i12'] > 0
# v2_set1 = df1.loc[mask_df1, 'v2']
# v1_set1 = df1.loc[mask_df1, 'v1']
#
# mask_df2 = df2['i14'] > 0
# v2_set2 = df2.loc[mask_df2, 'v2']
# v1_set2 = df2.loc[mask_df2, 'v1']
#
# fig_range, ax_range = plt.subplots(figsize=(14, 10))
#
# ax_range.plot(v2_set1, v1_set1, color='blue', linewidth=4, label='V1-V2 Curve')
# ax_range.plot(v2_set2, v1_set2, color='blue', linewidth=4)
#
# ax_range.set_title('PFC Control Range: V1 vs V2', fontsize=32, pad=20)
# ax_range.set_xlabel('$V2_{pfc}$ (kV)', fontsize=24)
# ax_range.set_ylabel('$V1_{pfc}$ (kV)', fontsize=24)
#
# ax_range.axhline(0, color='black', linewidth=0.8, alpha=0.5)
# ax_range.axvline(0, color='black', linewidth=0.8, alpha=0.5)
#
# ax_range.grid(True, which='both', linestyle='-', linewidth=0.5, alpha=0.7)
# ax_range.tick_params(axis='both', which='major', labelsize=18)
#
# ax_range.legend(loc='lower right', fontsize=18)
#
# ax_range.set_xlim(left=min(v2_set1.min(), v2_set2.min()))
# ax_range.set_ylim(bottom=min(v1_set1.min(), v1_set2.min()))
#
# plt.tight_layout()
# plt.show()
#
# # =============================================================================
# # Gráfico de controlabilidad de voltaje (Sin filtros de corriente)
# # =============================================================================
#
# # Para df1 (v2 control), mantenemos o quitamos la máscara según prefieras.
# # Aquí la quitaremos también para ver el locus completo.
# v2_set1 = df1['v2']
# v1_set1 = df1['v1']
#
# # Para df2 (v1 control), eliminamos la máscara mask_df2 como pediste
# v2_set2 = df2['v2']
# v1_set2 = df2['v1']
#
# fig_range, ax_range = plt.subplots(figsize=(14, 10))
#
# # Graficamos ambos conjuntos de datos
# ax_range.plot(v2_set1, v1_set1, color='blue', linewidth=4, label='V1-V2 Locus (Barrido V2)')
# ax_range.plot(v2_set2, v1_set2, color='red', linewidth=2, linestyle='--', label='V1-V2 Locus (Barrido V1)')
#
# ax_range.set_title('PFC Control Range: Full Locus', fontsize=32, pad=20)
# ax_range.set_xlabel('$V2_{pfc}$ (kV)', fontsize=24)
# ax_range.set_ylabel('$V1_{pfc}$ (kV)', fontsize=24)
#
# # Líneas de referencia en los ejes
# ax_range.axhline(0, color='black', linewidth=0.8, alpha=0.5)
# ax_range.axvline(0, color='black', linewidth=0.8, alpha=0.5)
#
# ax_range.grid(True, which='both', linestyle='-', linewidth=0.5, alpha=0.7)
# ax_range.tick_params(axis='both', which='major', labelsize=18)
# ax_range.legend(loc='best', fontsize=18)
#
# plt.tight_layout()
# plt.show()
#
# import seaborn as sns
#
# # Lista para almacenar los flujos de potencia de toda la red
# heatmap_data = []
#
# # =============================================================================
# # BUCLE 1: Barrido V2 (Filtro i12 > 0)
# # =============================================================================
# values_v2 = np.arange(-2, 0.05, 0.1)
#
# for val in values_v2:
#     grid = gce.open_file('case39_10_he_bis.veragrid')
#     # ... (Configuración de buses y PFC igual a tu código) ...
#     bus_1s = gce.Bus(name="Bus_1s", Vnom=345, is_dc=True)
#     grid.add_bus(bus_1s)
#     bus_1t = gce.Bus(name="Bus_1t", Vnom=345, is_dc=True)
#     grid.add_bus(bus_1t)
#
#     grid.add_pfc(gce.PFC(name="PFC_0", bus_dc_r=grid.buses[39], bus_dc_s=bus_1s, bus_dc_t=bus_1t,
#                          control1=PfcControlType.V2_pfc, control1_val=val / Ub))
#
#     grid.add_dc_line(gce.DcLine(name="Line_1s_4_1", bus_from=bus_1s, bus_to=grid.buses[42], r=0.005))
#     grid.add_dc_line(gce.DcLine(name="Line_1t_2_1", bus_from=bus_1t, bus_to=grid.buses[40], r=0.005))
#
#     res = gce.power_flow(grid, options=gce.PowerFlowOptions(verbose=0))
#
#     if res.iterations > 0:
#         branch_df = res.get_branch_df()
#         bus_df = res.get_bus_df()
#
#         # Filtro de corriente i12
#         p12 = branch_df.loc['Line_1t_2_1', 'Pf']
#         i12 = p12 / (bus_df.loc['Bus_1t', 'Vm'] * Ub)
#
#         if i12 > 0:
#             # Capturamos todos los flujos de potencia de la red
#             step_flows = branch_df['Pf'].to_dict()
#             step_flows['v2_set'] = val  # Guardamos el setpoint para el eje X
#             heatmap_data.append(step_flows)
#
# # =============================================================================
# # BUCLE 2: Barrido V1 (Filtro i14 > 0)
# # =============================================================================
# values_v1 = np.arange(-0.01, 5, 0.1)
#
# for val in values_v1:
#     grid = gce.open_file('case39_10_he_bis.veragrid')
#     # ... (Configuración idéntica pero con control V1_pfc) ...
#     bus_1s = gce.Bus(name="Bus_1s", Vnom=345, is_dc=True)
#     grid.add_bus(bus_1s)
#     bus_1t = gce.Bus(name="Bus_1t", Vnom=345, is_dc=True)
#     grid.add_bus(bus_1t)
#
#     grid.add_pfc(gce.PFC(name="PFC_0", bus_dc_r=grid.buses[39], bus_dc_s=bus_1s, bus_dc_t=bus_1t,
#                          control1=PfcControlType.V1_pfc, control1_val=val / Ub))
#
#     grid.add_dc_line(gce.DcLine(name="Line_1s_4_1", bus_from=bus_1s, bus_to=grid.buses[42], r=0.005))
#     grid.add_dc_line(gce.DcLine(name="Line_1t_2_1", bus_from=bus_1t, bus_to=grid.buses[40], r=0.005))
#
#     res = gce.power_flow(grid, options=gce.PowerFlowOptions(verbose=0))
#
#     if res.iterations > 0:
#         branch_df = res.get_branch_df()
#         bus_df = res.get_bus_df()
#
#         # Filtro de corriente i14
#         p14 = branch_df.loc['Line_1s_4_1', 'Pf']
#         i14 = p14 / (bus_df.loc['Bus_1s', 'Vm'] * Ub)
#
#         if i14 > 0:
#             step_flows = branch_df['Pf'].to_dict()
#             step_flows['v1_set'] = val
#             heatmap_data.append(step_flows)
#
# # =============================================================================
# # PROCESAMIENTO Y HEATMAP
# # =============================================================================
# df_total = pd.DataFrame(heatmap_data)
#
# # Calculamos la variación (Delta P) respecto al primer estado estable
# # Eliminamos columnas de control para el cálculo
# df_flows_only = df_total.drop(columns=['v1_set', 'v2_set'], errors='ignore')
# df_delta = df_flows_only.sub(df_flows_only.iloc[0, :], axis=1)
#
# # Filtro de sensibilidad: solo mostramos líneas que cambien más de 0.5 MW
# relevant_lines = df_delta.columns[df_delta.abs().max() > 0.5]
# df_plot = df_delta[relevant_lines].T
#
# plt.figure(figsize=(16, 10))
# sns.heatmap(df_plot, cmap='RdBu_r', center=0, cbar_kws={'label': '$\Delta P$ (MW)'})
# plt.title('Influencia Sistémica del PFC (Solo Corrientes Positivas)')
# plt.ylabel('Líneas de la Red')
# plt.xlabel('Puntos de Barrido (V2 -> V1)')
# plt.show()