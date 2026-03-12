# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import sys
import os

import numpy as np
import pandas as pd

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Branches.line import Line
from plot_emt_results import plot_ilines, plot_generators, plot_isource, plot_voltages, plot_v_i
from VeraGridEngine.Templates.Emt.generator_emt_type_template import get_generator_emt_template
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions, DynamicIntegrationMethod
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
import VeraGridEngine.api as gce

import matplotlib.pyplot as plt
import matplotlib as mpl

np.set_printoptions(
    precision=10,  # number of digits
    suppress=False,  # DO NOT suppress scientific notation
    formatter={'float_kind': lambda x: f"{x: .3e}"}
)

# =============================================================================
# 2. CONFIGURACIÓN DEL SISTEMA
# =============================================================================
grid = MultiCircuit()

Sbase = 160  # MVA
# Sbase  = 1000 #MVA
# Vbase = 15/np.sqrt(3) #kV
Vbase = 15  # kV
Zbase = Vbase * Vbase / (Sbase)
Rbase = Zbase.real  # ohm
f = 50  # Hz
# l1 = 1.0 # km
l1 = 100.0  # km -------------

grid.Sbase = Sbase  # *1e6 # MVA

# --- Buses ---
bus1 = Bus(name="Bus1", Vnom=Vbase, is_slack=True)

bus2 = Bus(name="Bus2", Vnom=Vbase)

# Asignar templates simbólicos a los buses
bus1_template = get_bus_emt_template(grid.rms_var_factory)
bus1.emt_model.model = bus1_template.block
bus2_template = get_bus_emt_template(grid.rms_var_factory)
bus2.emt_model.model = bus2_template.block

# --- LÍNEA DE TRANSMISIÓN ---
line0 = Line(name="line 1-2", bus_from=bus1, bus_to=bus2, rate=300, length=l1)

# [CAMBIO IMPORTANTE] Selección del modelo numérico para el driver
# Opciones: 'Bergeron', 'Pi', 'JMarti'
line0.emt_model_type = gce.EmtLineTypes.Bergeron

# Configuración Física (Torre)
tower = gce.OverheadLineType(name="Tower", Vnom=Vbase)
wire = gce.Wire(name="Panther 30/7 ACSR",
                diameter=21.0,
                diameter_internal=9.0,
                is_tube=True,
                r=0.1363,
                max_current=1)
tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
tower.add_wire_relationship(wire=wire, xpos=0, ypos=27.5, phase=2)
tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
tower.compute()

# Aplicar física a la línea
line0.apply_template(tower, grid.Sbase, grid.fBase)

# --- Generador ---
gen1 = Generator(name="Gen1", freq=50, Snom=grid.Sbase)
gen1_template = get_generator_emt_template()
gen1.emt_model.model = gen1_template.block

gen1_mdl = gen1.emt_model.model
bus1_mdl = bus1.emt_model.model
# Conectar puertos
gen1_mdl.connect(gen1_mdl.in_vars, bus1_mdl.out_vars)

# --- load ---
# P = 10

P = 0.004734676015622833 * Sbase  # per a lenght = 1km
load1 = Load(name="load1", P1=P / 3, P2=P / 3, P3=P / 3, Q1=0.0, Q2=0.0, Q3=0.0)
# load1 = Load(name="load1", R= R, P1 =P/3 , P2 =P/3 , P3 =P/3, Q1= 0.0, Q2= 0.0, Q3= 0.0)

# Agregar elementos al grid
grid.add_bus(bus1)
grid.add_bus(bus2)
grid.add_line(line0)
grid.add_generator(bus=bus1, api_obj=gen1)

grid.add_load(bus=bus2, api_obj=load1)
#
print("grid.Sbase = ", grid.Sbase)

# =============================================================================
# 3. POWER FLOW (Inicialización)
# =============================================================================
pf_options = PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=True,
    initialize_with_existing_solution=True,
    tolerance=1e-6,
    max_iter=25,
    control_q=False,
    control_taps_modules=True,
    control_taps_phase=True,
    control_remote_voltage=True,
    orthogonalize_controls=True,
    apply_temperature_correction=True,
    branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=True,
    generate_report=False,
)
power_flow = PowerFlowDriver3Ph(grid, pf_options)
power_flow.run()
res = power_flow.results
print("res.m (branch number)= ", res.m)
print("res.n (bus number)= ", res.n)
print("res.n_gen = ", res.n_gen)
print("res.n_load ", res.n_load)
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
print("res.load_names = ", res.load_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage_A = ", res.voltage_A)
print("res.voltage_B = ", res.voltage_B)
print("res.voltage_C = ", res.voltage_C)
print("res.Sbus_A = ", res.Sbus_A)
print("res.Sbus_B = ", res.Sbus_B)
print("res.Sbus_C = ", res.Sbus_C)
print("res.Sf_A = ", res.Sf_A)
print("res.Sf_B = ", res.Sf_B)
print("res.Sf_C = ", res.Sf_C)
print("res.St_A = ", res.St_A)
print("res.St_B = ", res.St_B)
print("res.St_C = ", res.St_C)
print("res.If_A = ", res.If_A)
print("res.If_B = ", res.If_B)
print("res.If_C = ", res.If_C)
print("res.It_A = ", res.It_A)
print("res.It_B = ", res.It_B)
print("res.It_C = ", res.It_C)

print(f"Converged: {res.converged}")
print(f"res:{res}")

# =============================================================================
# 4. SIMULACIÓN EMT
# =============================================================================
emt_opt = EmtOptions(time_step=5e-06,  # 3.957727297715481e-06,
                     simulation_time=0.005,  # s
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler)

print(f"initial timestep:{emt_opt.time_step}s")
drv = EmtSimulationDriver(grid, emt_opt, res)
t, V, hist, Ilines, hist_lines, Is, x, dx = drv.run()

# print("dx=", dx)
# print(f"hist = {hist}")
# print(f"hist_lines = {hist_lines}")
# print(f"Ilines = {Ilines}")

# =============================================================================
# 5. GUARDAR RESULTADOS
# =============================================================================
t = np.asarray(t).reshape(-1)
time_df = pd.DataFrame({"time_s": t})

# 1) Voltajes
V_cols = []
for bus in grid.get_buses():
    if bus.ph_n: V_cols.append(f"v_n_{bus.name}")
    if bus.ph_a: V_cols.append(f"v_a_{bus.name}")
    if bus.ph_b: V_cols.append(f"v_b_{bus.name}")
    if bus.ph_c: V_cols.append(f"v_c_{bus.name}")
df_V = pd.concat([time_df, pd.DataFrame(V, columns=V_cols)], axis=1)
df_V.to_csv("V_results.csv", index=False)

# 2) Fuentes de Corriente (Is)
Is_cols = []
for bus in grid.get_buses():
    if bus.ph_n:
        Is_cols.append(f"Is_n_{bus.name}")
    if bus.ph_a:
        Is_cols.append(f"Is_a_{bus.name}")
    if bus.ph_b:
        Is_cols.append(f"Is_b_{bus.name}")
    if bus.ph_c:
        Is_cols.append(f"Is_c_{bus.name}")
df_Is = pd.concat([time_df, pd.DataFrame(Is, columns=Is_cols)], axis=1)
df_Is.to_csv("Is_results.csv", index=False)

# 3) Corrientes de Línea (Ilines)
Il_cols = []
for line in grid.get_lines():
    bf = line.bus_from
    if bf.ph_n:
        Il_cols += [f"Ifrom_n_{line.name}", f"Ito_n_{line.name}"]
    if bf.ph_a:
        Il_cols += [f"Ifrom_a_{line.name}", f"Ito_a_{line.name}"]
    if bf.ph_b:
        Il_cols += [f"Ifrom_b_{line.name}", f"Ito_b_{line.name}"]
    if bf.ph_c:
        Il_cols += [f"Ifrom_c_{line.name}", f"Ito_c_{line.name}"]
df_Il = pd.concat([time_df, pd.DataFrame(Ilines, columns=Il_cols)], axis=1)
df_Il.to_csv("I_lines_results.csv", index=False)

# 4) Corrientes Históricas (hist_lines)
hist_cols = []
for line in grid.get_lines():
    bf = line.bus_from
    if bf.ph_n:
        hist_cols += [f"Hfrom_n_{line.name}", f"Hto_n_{line.name}"]
    if bf.ph_a:
        hist_cols += [f"Hfrom_a_{line.name}", f"Hto_a_{line.name}"]
    if bf.ph_b:
        hist_cols += [f"Hfrom_b_{line.name}", f"Hto_b_{line.name}"]
    if bf.ph_c:
        hist_cols += [f"Hfrom_c_{line.name}", f"Hto_c_{line.name}"]
df_hist = pd.concat([time_df, pd.DataFrame(hist_lines, columns=hist_cols)], axis=1)
df_hist.to_csv("hist_lines_results.csv", index=False)

# 5) Variables de Estado (x)
x_cols = []
for gen_idx, gen in enumerate(grid.get_generators(), start=1):
    model = gen.emt_model.model
    var_names = model.state_vars + model.algebraic_vars
    for name in var_names:
        x_cols.append(f"{name}_Gen{gen_idx}")
df_x = pd.concat([time_df, pd.DataFrame(x, columns=x_cols)], axis=1)
df_x.to_csv("x_gen_results.csv", index=False)

# 6) Derivadas (dx)
dx_cols = []
for gen_idx, gen in enumerate(grid.get_generators(), start=1):
    model = gen.emt_model.model
    for name in model.state_vars:
        dx_cols.append(f"d{name}_Gen{gen_idx}")
df_dx = pd.concat([time_df, pd.DataFrame(dx, columns=dx_cols)], axis=1)
df_dx.to_csv("dx_gen_results.csv", index=False)

# =============================================================================
# 6. PLOTS
# =============================================================================
plot_voltages("V_results.csv")
plot_ilines("I_lines_results.csv")
plot_generators("x_gen_results.csv", "dx_gen_results.csv")
plot_isource("Is_results.csv")
plot_v_i("V_results.csv", "x_gen_results.csv")

mpl.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman"],
    "axes.labelsize": 12,
    "font.size": 12,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
})

fig, axs = plt.subplots(2, 3, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, dx[:, 0], label=r"$\dot{\psi}_d\[\mathrm{p.u.}]$", color="b")
axs[0].set_xlabel(r"Time [ms]")
axs[0].set_ylabel(r"$\dot{\psi}_d \[\mathrm{p.u.}]$")
axs[0].set_title(r"Direct-axis flux derivative $\dot{\psi}_d$")
axs[0].legend(loc="upper right")
axs[0].set_ylim([-0.5, 1.0])
axs[0].grid(True)

axs[1].plot(t, dx[:, 2], label=r"$\dot{\psi}_f\[\mathrm{p.u.}]$", color="b")
axs[1].set_xlabel(r"Time [ms]")
axs[1].set_ylabel(r"$\dot{\psi}_f \[\mathrm{p.u.}]$")
axs[1].set_title(r"Field flux derivative $\dot{\psi}_f$")
axs[1].legend(loc="upper right")
axs[1].set_ylim([-0.2, 0.2])
axs[1].grid(True)

axs[2].plot(t, dx[:, 1], label=r"$\dot{\psi}_q\[\mathrm{p.u.}]$", color="b")
axs[2].set_xlabel(r"Time [ms]")
axs[2].set_ylabel(r"$\dot{\psi}_q \[\mathrm{p.u.}]$")
axs[2].set_title(r"Quadrature-axis flux derivative $\dot{\psi}_q$")
axs[2].legend(loc="upper right")
axs[2].set_ylim([-0.5, 1.0])
axs[2].grid(True)

axs[3].plot(t, dx[:, 5], label=r"$\dot{\omega}\[\mathrm{p.u.}]$", color="b")
axs[3].set_xlabel(r"Time [ms]")
axs[3].set_ylabel(r"$\dot{\omega}$ $\[\mathrm{p.u.}]$")
axs[3].set_title(r"Angular frequency derivative $\dot{\omega}$")
axs[3].legend(loc="upper right")
axs[3].set_ylim([-5, 10])
axs[3].grid(True)

axs[4].plot(t, dx[:, 4], label=r"$\dot{\theta}\[\mathrm{rad/s}]$", color="b")
axs[4].set_xlabel(r"Time [ms]")
axs[4].set_ylabel(r"$\dot{\theta} \[\mathrm{rad/s}]$")
axs[4].set_title(r"Rotor angle derivative $\dot{\theta}$")
axs[4].legend(loc="upper right")
axs[4].set_ylim([-5, 320])
axs[4].grid(True)

axs[5].plot(t, dx[:, 6], label=r"$\dot{e}_t\[\mathrm{p.u.}]$", color="b")
axs[5].set_xlabel(r"Time [ms]")
axs[5].set_ylabel(r"PI error derivative $\[\mathrm{p.u.}]$")
axs[5].set_title(r"PI error derivative $\dot{e}_t$")
axs[5].legend(loc="upper right")
axs[5].set_ylim([-5, 10])
axs[5].grid(True)

plt.suptitle(
    r"Synchronous generator model",
    fontsize=14,
    fontweight="bold"
)
plt.tight_layout(rect=(0, 0, 1, 0.96))
plt.show()
