'''
Con estos gráficos puedes determinar los valores de controlabilidad de los voltajes del PFC.
Se puede observar que cuando V2_pfc es controlada la potencia interna del PFC fluye de la línea controlada
por V2 que es 23 a 13 y eso sucede para valores + de V2_pfc pq es cuando la polaridad de las fuentes el flujo entra por el + de V2_pfc. (absorción de P).
En cambio, si queremos controlar V1 el flujo debe ir de 13 a 23 y por lo tanto se debe cambiar la polaridad establecida en las fuentes de tensión del PFC.
Por lo tanto, V2 deberá coger valores negativos.
Para V2, simulamos de 0,01 (evitar singularidades) hasta 7 kV. Lo que observamos es que a partir de 5.6 la corriente de 23 empieza a ser negativa (lo que implica que tenemos una corriente reversible no deseada).
Para V1, idem pero con valores negativos.
'''


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

values = np.arange(0.01, 7, 0.1)

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
                         control1=PfcControlType.V2_pfc, control1_val=i/Ub))

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

fig, ax = plt.subplots(figsize=(16, 9))
ax.plot(v2_arr, i12_arr, color='red', label='$\mathbf{I_{12}}$')
ax.plot(v2_arr, i13_arr, color='blue', label='$\mathbf{I_{13}}$')
ax.plot(v2_arr, i23_arr, color='green', label='$\mathbf{I_{23}}$')
ax.set_title('V2_pfc vs Currents')
ax.set_xlabel('$V_{2,pfc}$ (kV)')
ax.set_ylabel('$I_{Line}$ (kA)')
ax.grid(True, linestyle=':', alpha=0.6)
ax.legend()
plt.tight_layout()
plt.show()

V1_pfc_list, V2_pfc_list = [], []
p_v1_internal_list, p_v2_internal_list, p_PB_internal_list = [], [], []
I12_list, I13_list, I23_list = [], [], []
P12_list, P13_list, P23_list, P1_list = [], [], [], []
v1_bus_list, v2_bus_list = [], []

values = np.arange(-7, -0.01, 0.1)

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
                         control1=PfcControlType.V1_pfc, control1_val=i/Ub))

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

fig, ax = plt.subplots(figsize=(16, 9))
ax.plot(v1_arr, i12_arr, color='red', label='$\mathbf{I_{12}}$')
ax.plot(v1_arr, i13_arr, color='blue', label='$\mathbf{I_{13}}$')
ax.plot(v1_arr, i23_arr, color='green', label='$\mathbf{I_{23}}$')
ax.set_title('V1_pfc vs Currents')
ax.set_xlabel('$V_{1,pfc}$ (kV)')
ax.set_ylabel('$I_{Line}$ (kA)')
ax.grid(True, linestyle=':', alpha=0.6)
ax.legend()
plt.tight_layout()
plt.show()



