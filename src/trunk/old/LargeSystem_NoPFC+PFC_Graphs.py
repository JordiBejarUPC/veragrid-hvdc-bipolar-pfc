import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ResultTypes
from VeraGridEngine.enumerations import PfcControlType

import matplotlib.pyplot as plt
import pandas as pd

# ==========================================================
# CONFIGURACIÓN GRÁFICA
# ==========================================================
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['font.size'] = 16
plt.rcParams['axes.titlesize'] = 22
plt.rcParams['axes.labelsize'] = 18
plt.rcParams['lines.linewidth'] = 2.5

Ub = 345

# ==========================================================
# CASO BASE
# ==========================================================
input_grid_base = 'case39_10_he_v3.gridcal'

grid_base = gce.open_file(input_grid_base)

options_pf_base = gce.PowerFlowOptions(
    verbose=0,
    generate_report=True,
    retry_with_other_methods=False
)

results_base = gce.power_flow(grid_base, options=options_pf_base)

print('==================================================')
print('BASE CASE')
print('==================================================')
print('Converged:', results_base.converged)
print('Error:', results_base.error)

# ----------------------------------------------------------
# RESULTADOS DE RAMAS
# ----------------------------------------------------------
branch_df_base = results_base.get_branch_df()

# Número de líneas AC y DC
n_ac_base = len(grid_base.lines)
n_dc_base = len(grid_base.dc_lines)

# Separación CORRECTA por posición
ac_base = branch_df_base.iloc[:n_ac_base].copy()
dc_base = branch_df_base.iloc[n_ac_base:n_ac_base + n_dc_base].copy()

# Reasignar nombres correctos
ac_base.index = [line.name for line in grid_base.lines]
dc_base.index = [line.name for line in grid_base.dc_lines]

print('\nAC BASE:')
print(ac_base[['Pf']])

print('\nDC BASE:')
print(dc_base[['Pf']])

# ==========================================================
# CASO CON PFC
# ==========================================================
input_grid_pfc = 'case39_10_he_v2_bis.gridcal.veragrid'

grid_pfc = gce.open_file(input_grid_pfc)

# ----------------------------------------------------------
# BUSCAR BUSES DC
# ----------------------------------------------------------
bus_1_dc = next(b for b in grid_pfc.buses if b.name == "1" and b.is_dc)
bus_2_dc = next(b for b in grid_pfc.buses if b.name == "2" and b.is_dc)
bus_4_dc = next(b for b in grid_pfc.buses if b.name == "4" and b.is_dc)

# ----------------------------------------------------------
# CREAR BUSES PFC
# ----------------------------------------------------------
bus_1s = gce.Bus(
    name="Bus_1s",
    Vnom=Ub,
    is_dc=True,
    is_grounded=False
)

grid_pfc.add_bus(bus_1s)

bus_1t = gce.Bus(
    name="Bus_1t",
    Vnom=Ub,
    is_dc=True,
    is_grounded=False
)

grid_pfc.add_bus(bus_1t)

# ----------------------------------------------------------
# AÑADIR PFC
# ----------------------------------------------------------
grid_pfc.add_pfc(
    gce.PFC(
        name="PFC_0",
        bus_dc_r=bus_1_dc,
        bus_dc_s=bus_1s,
        bus_dc_t=bus_1t,
        control1=PfcControlType.Ps_dc,
        control1_val=-20
    )
)

# ----------------------------------------------------------
# AÑADIR LÍNEAS DC
# ----------------------------------------------------------
grid_pfc.add_dc_line(
    gce.DcLine(
        name="Line_1s_4_1",
        bus_from=bus_1s,
        bus_to=bus_4_dc,
        r=0.005,
        rate=100
    )
)

grid_pfc.add_dc_line(
    gce.DcLine(
        name="Line_1t_2_1",
        bus_from=bus_1t,
        bus_to=bus_2_dc,
        r=0.005,
        rate=100
    )
)

# ----------------------------------------------------------
# POWER FLOW PFC
# ----------------------------------------------------------
options_pf_pfc = gce.PowerFlowOptions(
    verbose=0,
    generate_report=True,
    use_stored_guess=True,
    retry_with_other_methods=False
)

results_pfc = gce.power_flow(grid_pfc, options=options_pf_pfc)

print('\n==================================================')
print('PFC CASE')
print('==================================================')
print('Converged:', results_pfc.converged)
print('Error:', results_pfc.error)

# ----------------------------------------------------------
# RESULTADOS DE RAMAS
# ----------------------------------------------------------
branch_df_pfc = results_pfc.get_branch_df()

# Número de líneas AC y DC
n_ac_pfc = len(grid_pfc.lines)
n_dc_pfc = len(grid_pfc.dc_lines)

# Separación CORRECTA por posición
ac_pfc = branch_df_pfc.iloc[:n_ac_pfc].copy()
dc_pfc = branch_df_pfc.iloc[n_ac_pfc:n_ac_pfc + n_dc_pfc].copy()

# Reasignar nombres correctos
ac_pfc.index = [line.name for line in grid_pfc.lines]
dc_pfc.index = [line.name for line in grid_pfc.dc_lines]

print('\nAC PFC:')
print(ac_pfc[['Pf']])

print('\nDC PFC:')
print(dc_pfc[['Pf']])

# ==========================================================
# COMPROBACIÓN LÍNEA 1_2_1
# ==========================================================
print('\n==================================================')
print('COMPROBACIÓN LÍNEA AC 1_2_1')
print('==================================================')

print('Base case:')
print(ac_base.loc['1_2_1', 'Pf'])

print('PFC case:')
print(ac_pfc.loc['1_2_1', 'Pf'])

# ==========================================================
# GRÁFICO COMPARACIÓN LÍNEAS AC
# ==========================================================
fig_ac, ax_ac = plt.subplots(figsize=(18, 9))

ax_ac.plot(
    range(len(ac_base)),
    ac_base['Pf'],
    'o-',
    label='Base Case'
)

ax_ac.plot(
    range(len(ac_pfc)),
    ac_pfc['Pf'],
    's-',
    label='PFC Case'
)

ax_ac.set_xticks(range(len(ac_base)))
ax_ac.set_xticklabels(ac_base.index, rotation=90)

ax_ac.set_xlabel('Line')
ax_ac.set_ylabel('Active Power Pf (MW)')
ax_ac.set_title('AC Lines')

ax_ac.grid(True, linestyle=':')
ax_ac.legend()

plt.tight_layout()

# ==========================================================
# GRÁFICO COMPARACIÓN LÍNEAS DC
# ==========================================================
fig_dc, ax_dc = plt.subplots(figsize=(18, 9))

ax_dc.plot(
    range(len(dc_base)),
    dc_base['Pf'],
    'o-',
    label='Base Case'
)

ax_dc.plot(
    range(len(dc_pfc)),
    dc_pfc['Pf'],
    's-',
    label='PFC Case'
)

ax_dc.set_xticks(range(len(dc_pfc)))
ax_dc.set_xticklabels(dc_pfc.index, rotation=90)

ax_dc.set_xlabel('Line')
ax_dc.set_ylabel('Active Power Pf (MW)')
ax_dc.set_title('DC lines')

ax_dc.grid(True, linestyle=':')
ax_dc.legend()

plt.tight_layout()

# ==========================================================
# SHOW
# ==========================================================
plt.show()