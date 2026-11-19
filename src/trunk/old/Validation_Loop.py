import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType
from VeraGridEngine.enumerations import ResultTypes
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

# --- CONFIGURACIÓN GLOBAL DE GRÁFICOS ---
# 1. Definir la familia de la fuente (puede ser 'sans-serif', 'serif', 'monospace', etc.)
plt.rcParams['font.family'] = 'sans-serif'

# 2. Especificar la fuente exacta que quieres usar (ej. 'Arial', 'Tahoma', 'Times New Roman')
plt.rcParams['font.sans-serif'] = ['Calibril']

# (Opcional) Cambiar también el tamaño general de las letras para no tener que usar 'fontsize=12' en cada línea
plt.rcParams['font.size'] = 20
plt.rcParams['axes.titlesize'] = 20
plt.rcParams['axes.labelsize'] = 20
plt.rcParams['legend.fontsize'] = 20

#Params
Ub = 150
Sb = 100
Rb = (Ub ** 2) / Sb
Ib = Sb/Ub

rlin_12, rlin_13, rlin_23 = 2,3,1 #ohms

Pg1 = 160 #MW
Pg2 = 80 #MW

V1_pfc_list = []
V2_pfc_list = []
p_v1_internal_list = []
p_v2_internal_list = []
p_PB_internal_list = []

I12_list = []
I13_list = []
I23_list = []

P12_list = []
P13_list = []
P23_list = []
P1_list = []

v1_bus_list = []
v2_bus_list = []


values = np.arange(0.1,232.32,1)
c=0
nc=0

for i in values:
    grid = gce.MultiCircuit(
        name="pfc_validation",
    )

    ##AC Grid
    # AC buses
    # Bus 1
    bus1_ac = gce.Bus(name="Bus1_ac",
                      Vnom=Ub,
                      is_slack=True)
    grid.add_bus(bus1_ac)
    grid.add_generator(bus1_ac, gce.Generator(name='g1',
                                              vset=1.0))
    # Bus 2
    bus2_ac = gce.Bus(name="Bus2_ac",
                      Vnom=Ub,
                      is_slack=True)
    grid.add_bus(bus2_ac)
    grid.add_generator(bus2_ac, gce.Generator(name='g1',
                                              vset=1.0))

    # Bus 3
    bus3_ac = gce.Bus(name="Bus3_ac",
                      Vnom=Ub,
                      is_slack=True)
    grid.add_bus(bus3_ac)
    grid.add_generator(bus3_ac, gce.Generator(name='g3',
                                              vset=1.0))

    ##DC Grid
    # DC buses
    bus1_dc = gce.Bus(name="Bus1_dc",
                      Vnom=Ub,
                      is_dc=True)
    grid.add_bus(bus1_dc)

    bus2_dc = gce.Bus(name="Bus2_dc",
                      Vnom=Ub,
                      is_dc=True)
    grid.add_bus(bus2_dc)

    bus3_dc = gce.Bus(name="Bus3_dc",
                      Vnom=Ub,
                      is_dc=True)
    grid.add_bus(bus3_dc)

    ##Adding the PFC
    # PFC buses
    # busR_dc = gce.Bus(name = "busR_dc",
    #                   Vnom = Ub,
    #                   is_dc = True)
    # grid.add_bus(busR_dc)

    busS_dc = gce.Bus(name="busS_dc",
                      Vnom=Ub,
                      is_dc=True)
    grid.add_bus(busS_dc)

    busT_dc = gce.Bus(name="busT_dc",
                      Vnom=Ub,
                      is_dc=True)
    grid.add_bus(busT_dc)

    grid.add_pfc(gce.PFC(name="PFC_0",
                         bus_dc_r=bus3_dc,
                         bus_dc_s=busS_dc,
                         bus_dc_t=busT_dc,
                         control1=PfcControlType.Ps_dc,
                         control1_val=i))

    # DC lines
    grid.add_dc_line(gce.DcLine(name="dc_line_12",
                                bus_from=bus1_dc,
                                bus_to=bus2_dc,
                                r=rlin_12 / Rb))
    ##PFC to be added here
    grid.add_dc_line(gce.DcLine(name="dc_line_13",
                                bus_from=bus1_dc,
                                bus_to=busS_dc,
                                r=rlin_13 / Rb))

    grid.add_dc_line(gce.DcLine(name="dc_line_23",
                                bus_from=bus2_dc,
                                bus_to=busT_dc,
                                r=rlin_23 / Rb))

    # VSC
    grid.add_vsc(gce.VSC(name="VSC_1",
                         bus_from=bus1_dc,
                         bus_to=bus1_ac,
                         alpha1=0.01,
                         alpha2=0.01,
                         alpha3=0.01,
                         control1=ConverterControlType.Pdc,
                         control2=ConverterControlType.Qac,
                         control1_val=-Pg1,
                         control2_val=0.0))

    grid.add_vsc(gce.VSC(name="VSC_2",
                         bus_from=bus2_dc,
                         bus_to=bus2_ac,
                         alpha1=0.01,
                         alpha2=0.01,
                         alpha3=0.01,
                         control1=ConverterControlType.Pdc,
                         control2=ConverterControlType.Qac,
                         control1_val=-Pg2,
                         control2_val=0.0))

    grid.add_vsc(gce.VSC(name="VSC_3",
                         bus_from=bus3_dc,
                         bus_to=bus3_ac,
                         alpha1=0.01,
                         alpha2=0.01,
                         alpha3=0.01,
                         control1=ConverterControlType.Vm_dc,
                         control2=ConverterControlType.Qac,
                         control1_val=1.0,
                         control2_val=0.0))

    options_pf = gce.PowerFlowOptions(verbose=0, generate_report=False, retry_with_other_methods=False)
    results = gce.power_flow(grid, options=options_pf)
    if results.iterations > 0:
        v1_value = results.mdl(result_type=ResultTypes.PfcV1).get_data_frame().iloc[0, 0]*Ub
        v2_value = results.mdl(result_type=ResultTypes.PfcV2).get_data_frame().iloc[0, 0]*Ub
        p_v1_internal_value = results.mdl(result_type=ResultTypes.PfcInternalPowerV1_pfc).get_data_frame().iloc[0, 0]*Sb
        p_v2_internal_value = results.mdl(result_type=ResultTypes.PfcInternalPowerV2_pfc).get_data_frame().iloc[0, 0]*Sb
        p_PB_internal_value = results.mdl(result_type=ResultTypes.PfcPB).get_data_frame().iloc[0, 0]*Sb

        bus_df = results.get_bus_df()
        branch_df = results.get_branch_df()

        # I = (Pf / Sb) / Vm * Ib
        i12 = (branch_df.loc['dc_line_12', 'Pf'] / Sb) / bus_df.loc['Bus1_dc', 'Vm'] * Ib
        i13 = (branch_df.loc['dc_line_13', 'Pf'] / Sb) / bus_df.loc['Bus1_dc', 'Vm'] * Ib
        i23 = (branch_df.loc['dc_line_23', 'Pf'] / Sb) / bus_df.loc['Bus2_dc', 'Vm'] * Ib

        v1_bus = bus_df.loc['Bus1_dc', 'Vm'] * Ub
        v2_bus = bus_df.loc['Bus2_dc', 'Vm'] * Ub

        p12 = branch_df.loc['dc_line_12', 'Pf']
        p13 = branch_df.loc['dc_line_13', 'Pf']
        p23 = branch_df.loc['dc_line_23', 'Pf']

        P12_list.append(p12)
        P13_list.append(p13)
        P23_list.append(p23)
        P1_list.append(Pg1)

        I12_list.append(i12)
        I13_list.append(i13)
        I23_list.append(i23)


        v1_bus_list.append(v1_bus)
        v2_bus_list.append(v2_bus)

        p_v1_internal_list.append(p_v1_internal_value)
        p_v2_internal_list.append(p_v2_internal_value)
        p_PB_internal_list.append(p_PB_internal_value)
        V1_pfc_list.append(v1_value)
        V2_pfc_list.append(v2_value)
        c = c +1
    else:
        V1_pfc_list.append(0)
        V2_pfc_list.append(0)
        nc = nc +1

print(c)
print(nc)
# print(values[1500])
print(V1_pfc_list)
print(V2_pfc_list)

# --- Gráficos ---
# Convertir listas a arrays de numpy para facilitar el plot
v1_arr = np.array(V1_pfc_list)
v2_arr = np.array(V2_pfc_list)
p_v1_arr = np.array(p_v1_internal_list)
p_v2_arr = np.array(p_v2_internal_list)
p_PB_internal_arr = np.array(p_PB_internal_list)
i12_arr = np.array(I12_list)
i13_arr = np.array(I13_list)
i23_arr = np.array(I23_list)
v1_bus_arr = np.array(v1_bus_list)
v2_bus_arr = np.array(v2_bus_list)
p12_arr = np.array(P12_list)
p13_arr = np.array(P13_list)
p23_arr = np.array(P23_list)

print(max(v1_arr), max(v2_arr))

# Crear una figura con 2 subplots
fig, ((ax2), (ax3)) = plt.subplots(2, 1, figsize=(14, 10))
fig, ((ax4) ,(ax1)) = plt.subplots(2, 1, figsize=(14, 10))



# Graph 1: V1 X, V2 Y
ax1.plot(v2_arr, p_PB_internal_arr, 'b.-', label='PFC internal Power Balance')
ax1.set_title('PFC internal Power Balance: V (X) vs P (y))')
ax1.set_xlabel('V2_pfc [kV]')
ax1.set_ylabel('PB_pfc [MW]')
ax1.grid(True)
ax1.legend()

# Gráfico 2: V1 eje X, I eje YS
ax2.plot(v1_arr, I12_list, label='I_line_12')
ax2.plot(v1_arr, I13_list, label='I_line_13')
ax2.plot(v1_arr, I23_list, label='I_line_23')
ax2.set_title('PFC internal voltages: V1 (X) vs I12, I13, I23 (y))')
ax2.set_xlabel('V1_pfc [kV]')
ax2.set_ylabel('I [kA]')
ax2.grid(True)
ax2.legend()

# Gráfico 2: V2 eje X, I eje YS
ax3.plot(v2_arr, I12_list, label='I_line_12')
ax3.plot(v2_arr, I13_list, label='I_line_13')
ax3.plot(v2_arr, I23_list, label='I_line_23')
ax3.set_title('PFC internal voltages: V2 (X) vs I12, I13, I23 (y))')
ax3.set_xlabel('V2_pfc [kV]')
ax3.set_ylabel('I [kA]')
ax3.grid(True)
ax3.legend()

# Gráfico 2: V2 eje X, V1 eje YS
ax4.plot(v1_arr, p_PB_internal_arr, 'b.-', label='PFC internal Power Balance')
ax4.set_title('PFC internal Power Balance: V (X) vs P (y))')
ax4.set_xlabel('V1_pfc [kV]')
ax4.set_ylabel('PB_pfc [MW]')
ax4.grid(True)
ax4.legend()

plt.tight_layout()
plt.show()

# fig_i, (ax_i1, ax_i2) = plt.subplots(1, 2, figsize=(15, 6))
#
# # Corrientes vs V1_pfc
# ax_i1.plot(v1_arr, I12_list, label='I_line_12')
# ax_i1.plot(v1_arr, I13_list, label='I_line_13')
# ax_i1.plot(v1_arr, I23_list, label='I_line_23')
# ax_i1.set_title('Intensidades de línea vs V1_pfc')
# ax_i1.set_xlabel('V1_pfc [kV]')
# ax_i1.set_ylabel('Corriente [kA]')
# ax_i1.legend()
# ax_i1.grid(True)
#
# # Corrientes vs V2_pfc
# ax_i2.plot(v2_arr, I12_list, label='I_line_12')
# ax_i2.plot(v2_arr, I13_list, label='I_line_13')
# ax_i2.plot(v2_arr, I23_list, label='I_line_23')
# ax_i2.set_title('Intensidades de línea vs V2_pfc')
# ax_i2.set_xlabel('V2_pfc [kV]')
# ax_i2.set_ylabel('Corriente [kA]')
# ax_i2.legend()
# ax_i2.grid(True)
#
# plt.tight_layout()
# plt.show()

#Currents Graph
eje_x_com = np.where(values < (max(values)/2), v1_arr, v2_arr)
idx_end = ~np.isnan(i13_arr)
plt.figure(figsize=(9, 6))
plt.plot(eje_x_com, i13_arr, color='blue', linewidth=2.5, label='$I_{13}$')
plt.plot(eje_x_com, i23_arr, color='lime', linewidth=2.5, label='$I_{23}$')
plt.plot(eje_x_com, i12_arr, color='red', linewidth=2.5, label='$I_{12}$')

plt.axvline(0, color='black', linewidth=1)
plt.xlabel('$V1_pfc$              (kV)             $V2_pfc$')
plt.ylabel('$I_{Line} (kA)$')
plt.grid(True, linestyle=':', alpha=0.6)

if any(idx_end):
    plt.text(eje_x_com[idx_end][-1], i13_arr[idx_end][-1] + 0.05, '$I_{13}$')
    plt.text(eje_x_com[idx_end][-1], i23_arr[idx_end][-1] + 0.05, '$I_{23}$')
    plt.text(eje_x_com[idx_end][-1], i12_arr[idx_end][-1] - 0.15, '$I_{12}$')

plt.tight_layout()
plt.show()

# --- Power Graph (Contingencies) ---

# Asegurar que P1 es un array
p1_arr = np.array(P1_list)

# Crear el eje X combinado de voltajes
eje_x_com = np.where(values < (max(values)/2), v1_arr, v2_arr)

fig, ax = plt.subplots(figsize=(10, 6))

# 1. Ploteando las líneas de potencia contra el eje combinado
ax.plot(eje_x_com, p12_arr, color='#2c328e', linewidth=2.5, label='$\mathbf{P_{12}}$')
ax.plot(eje_x_com, p13_arr, color='#b82e21', linewidth=2.5, label='$\mathbf{P_{13}}$')
ax.plot(eje_x_com, p23_arr, color='#448f44', linewidth=2.5, label='$\mathbf{P_{23}}$')
ax.plot(eje_x_com, p1_arr, color='#f5911e', linewidth=2.5, label='$\mathbf{P_1}$')

# 2. Líneas de referencia (+/- 20 MW)
ax.axhline(20, color='black', linestyle='--', linewidth=1.5, dashes=(4, 4))
ax.axhline(-20, color='black', linestyle='--', linewidth=1.5, dashes=(4, 4))
ax.axvline(0, color='black', linewidth=1)

# 3. Áreas sombreadas DINÁMICAS (Donde cada línea no supera los 20 MW)
# interpolate=True hace que el color llegue exactamente al punto de corte matemático
y_min_fill, y_max_fill = -200, 300

# L12 (Azul claro para la línea azul P12)
ax.fill_between(eje_x_com, y_min_fill, y_max_fill, where=(np.abs(p12_arr) <= 20),
                facecolor='#c8c8e6', alpha=0.7, interpolate=True)

# L13 (Rojo claro para la línea roja P13)
ax.fill_between(eje_x_com, y_min_fill, y_max_fill, where=(np.abs(p13_arr) <= 20),
                facecolor='#f3dcd4', alpha=0.7, interpolate=True)

# L23 (Verde claro para la línea verde P23)
ax.fill_between(eje_x_com, y_min_fill, y_max_fill, where=(np.abs(p23_arr) <= 20),
                facecolor='#d2ebd2', alpha=0.7, interpolate=True)

# Texto de "Contingency area"
ax.text(0, 0, 'Contingency area', ha='center', va='center',
        fontweight='bold', bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=3))

# 4. Configuración de ejes
x_min, x_max = min(eje_x_com), max(eje_x_com)
ax.set_xlabel('$V1_{pfc}$              (kV)             $V2_{pfc}$')
ax.set_ylabel('Power [MW]')
ax.set_xlim([x_min, x_max])
ax.set_ylim([-100, 250])
ax.grid(True, linestyle=':', alpha=0.6)

# 5. Leyendas
# Leyenda de líneas abajo a la derecha
legend_lines = ax.legend(loc='lower right', framealpha=1, edgecolor='black', ncol=2)

# Crear parches con los mismos colores para la leyenda de áreas
patch_L12 = mpatches.Patch(color='#c8c8e6', label='$\mathbf{L_{12}}$')
patch_L13 = mpatches.Patch(color='#f3dcd4', label='$\mathbf{L_{13}}$')
patch_L23 = mpatches.Patch(color='#d2ebd2', label='$\mathbf{L_{23}}$')

# Leyenda superior (Áreas seguras)
legend_areas = ax.legend(handles=[patch_L12, patch_L13, patch_L23],
                         loc='upper center', bbox_to_anchor=(0.5, 1.1),
                         ncol=3, framealpha=1, edgecolor='black')

ax.add_artist(legend_lines)

plt.tight_layout()
plt.show()

#Voltage Graph
eje_x_com = np.where(values < (max(values)/2), v1_arr, v2_arr)
idx_end = ~np.isnan(v1_bus_arr)
plt.figure(figsize=(9, 6))
plt.plot(eje_x_com, v1_bus_arr, color='red', linewidth=2.5, label='$V_{1}$')
plt.plot(eje_x_com, v2_bus_arr, color='blue', linewidth=2.5, label='$V_{2}$')

plt.axvline(0, color='black', linewidth=1)
plt.xlabel('$V1_pfc$           (kV)           $V2_pfc$')
plt.ylabel('$V_{Bus} (kV)$')
plt.grid(True, linestyle=':', alpha=0.6)

if any(idx_end):
    plt.text(eje_x_com[idx_end][-1], v1_bus_arr[idx_end][-1] + 0.05, '$V_{1}$')
    plt.text(eje_x_com[idx_end][-1], v2_bus_arr[idx_end][-1] + 0.05, '$V_{2}$')

plt.tight_layout()
plt.show()




# # --- GRÁFICO FINAL: Potencias Internas (P1, P2, Pbp) ---
#
# idx_valid = ~np.isnan(p_v1_arr)
#
# plt.figure(figsize=(9, 6))
#
# plt.plot(eje_x_com, p_v1_arr, color='blue', linewidth=2.5, label='$P_{1}$')
# plt.plot(eje_x_com, p_v2_arr, color='green', linewidth=2.5, label='$P_{2}$')
# plt.plot(eje_x_com, p_PB_internal_arr, color='red', linewidth=2.5, label='$P_{bp}$')
#
# plt.axvline(0, color='black', linewidth=1.2)
# plt.axhline(0, color='black', linewidth=1.2)
#
# plt.xlabel('$V_{1pfc}$           (kV)           $V_{2pfc}$', fontsize=12)
# plt.ylabel('Potencia Interna (MW)', fontsize=12)
# plt.grid(True, linestyle=':', alpha=0.6)
# plt.legend(loc='best')
#
# if any(idx_valid):
#     plt.text(eje_x_com[idx_valid][-1], p_v1_arr[idx_valid][-1] + 0.2, '$P_{1}$', color='blue', fontsize=12)
#     plt.text(eje_x_com[idx_valid][-1], p_v2_arr[idx_valid][-1] - 0.5, '$P_{2}$', color='green', fontsize=12)
#     plt.text(eje_x_com[idx_valid][-1], p_PB_internal_arr[idx_valid][-1] + 0.2, '$P_{bp}$', color='red', fontsize=12)
#
# plt.tight_layout()
# plt.show()


#Graph internal powers
v1_pfc_arr = np.array(V1_pfc_list)
v2_pfc_arr = np.array(V2_pfc_list)
i13_arr = np.array(I13_list)
i23_arr = np.array(I23_list)

p_calc_1 = v1_pfc_arr * i13_arr
p_calc_2 = v2_pfc_arr * i23_arr

fig, (ax_p1, ax_p2) = plt.subplots(1, 2, figsize=(15, 6))

ax_p1.plot(v1_pfc_arr, p_calc_1, color='blue', linewidth=2, label='$V_{1pfc} \cdot I_{13}$')
ax_p1.set_title('Internal power Voltage source 1 vs $V_{1pfc}$')
ax_p1.set_xlabel('$V_{1pfc}$ [kV]')
ax_p1.set_ylabel('Potencia [MW]')
ax_p1.grid(True, linestyle=':', alpha=0.6)
ax_p1.legend()

ax_p2.plot(v2_pfc_arr, p_calc_2, color='green', linewidth=2, label='$V_{2pfc} \cdot I_{23}$')
ax_p2.set_title('Internal power Voltage source 2 vs $V_{2pfc}$')
ax_p2.set_xlabel('$V_{2pfc}$ [kV]')
ax_p2.set_ylabel('Potencia [MW]')
ax_p2.grid(True, linestyle=':', alpha=0.6)
ax_p2.legend()

plt.tight_layout()
plt.show()


# --- Graph with unic axis ---

p_calc_1 = v1_pfc_arr * i13_arr
p_calc_2 = v2_pfc_arr * i23_arr

eje_x_com = np.where(values < (max(values)/2), v1_pfc_arr, v2_pfc_arr)

p_total_com = np.where(values < (max(values)/2), np.abs(p_calc_1), np.abs(p_calc_2))

plt.figure(figsize=(9, 6))

plt.plot(eje_x_com, p_total_com, color='blue', linewidth=2.5, label='Internal Power $P$')

plt.axvline(0, color='black', linewidth=1.2)
plt.axhline(0, color='black', linewidth=1.2)

plt.xlabel('V1_pfc                   (kV)            V2_pfc')
plt.ylabel('$P$ (MW)')
ax.set_ylim([0, 10])
plt.title('Power exchanged by the internal voltage sources')
plt.grid(True, linestyle=':', alpha=0.6)

plt.ylim(0, max(p_total_com) * 1.2)

plt.tight_layout()
plt.show()


#Voltage control range
plt.figure(figsize=(9, 6))

plt.plot(v2_arr, v1_arr, 'b.-', label='V1-V2 Curve')
plt.title('PFC control range: V1 (X) vs V2 (y))')
plt.xlabel('V2_pfc [kV]')
plt.ylabel('V1_pfc [kV]')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()





# print('Converged:', results.converged, 'error:', results.error)
# print(results.get_bus_df())
# print(results.get_branch_df())
# print(results.mdl(result_type=ResultTypes.VscLosses).get_data_frame())
# print(results.mdl(result_type=ResultTypes.VscPowerFrom).get_data_frame())
# print(results.mdl(result_type=ResultTypes.VscPowerTo).get_data_frame())