# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import pandas as pd

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGrid.trunk.dynamics_emt.support.plot_emt_results import plot_ilines, plot_generators, plot_isource, plot_voltages, plot_v_i
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver

from matplotlib import pyplot as plt
import matplotlib as mpl

import VeraGridEngine.api as gce
np.set_printoptions(
            precision=10,  # number of digits
            suppress=False,  # DO NOT suppress scientific notation
            formatter={'float_kind': lambda x: f"{x: .3e}"}
        )

#-------------------------------------------
# This circuit is composed of a synchronous generator connected to a three-phase load in the same bus.
# Therefore, the initialization using the power-flow result doesn't work (the power-flow has no sense)
# In initialization lines between 404 and 430 must be uncommented (horrible but it works)
#-------------------------------------------


grid = MultiCircuit()

Sbase  =160 #VA
# Vbase = 15/np.sqrt(3)
Vbase = 15 #kV line to line voltage
Zbase = Vbase*Vbase/(Sbase*1e3) # kV*kV / kVA = ohm
Rbase = Zbase.real # ohm
f = 50 # Hz


grid.Sbase = Sbase #*1e6 # MVA

bus1 = Bus(name="Bus1", Vnom=Vbase, is_slack= True)
bus1.ph_n = False
bus1.ph_a = True
bus1.ph_b = True
bus1.ph_c = True

bus1_template = get_bus_emt_template(grid.var_factory)
bus1.emt_model = bus1_template.block

gen1 = Generator(name="Gen1",freq = 50, Snom=grid.Sbase)
gen1_template = get_simple_generator_emt_template()
gen1.emt_model = gen1_template.block

gen1_mdl = gen1.emt_model
bus1_mdl = bus1.emt_model
grid.var_factory.add_connections(gen1_mdl.in_vars, bus1_mdl.out_vars)

# load
P = 160.0
# Rload = 1 / 0.3833
Rload = 3.0
load1 = Load(name="load1", P1 =P/3 , P2 =P/3 , P3 =P/3, Q1= 0.0, Q2= 0.0, Q3= 0.0) # R in p.u.2.75

grid.add_bus(bus1)
grid.add_generator(bus=bus1, api_obj=gen1)

grid.add_load(bus=bus1, api_obj=load1)

print("grid.Sbase = ", grid.Sbase)

pf_options = PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=0,
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
    initialize_angles=False,
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

print(f"Converged: {res.converged}")
print(f"res:{res}")

emt_opt = EmtOptions(time_step = 5e-6,
                     simulation_time =  0.01, #5e-6*10, # s
                     tolerance = 1e-6,
                     integration_method = "implicit_euler")

print(f"initial timestep:{emt_opt.time_step}s")
drv = EmtSimulationDriver(grid, emt_opt, res)
t, V, hist, Ilines, hist_lines, Is, x, dx = drv.run()

t = np.asarray(t).reshape(-1)
time_df = pd.DataFrame({"time_s": t})

# ============================================================
# 1) V -> V_results.csv
# ============================================================
V_cols = []
for bus in grid.get_buses():

    if bus.ph_n: V_cols.append(f"v_n_{bus.name}")
    if bus.ph_a: V_cols.append(f"v_a_{bus.name}")
    if bus.ph_b: V_cols.append(f"v_b_{bus.name}")
    if bus.ph_c: V_cols.append(f"v_c_{bus.name}")

df_V = pd.concat([time_df, pd.DataFrame(V, columns=V_cols)], axis=1)
df_V.to_csv("V_results.csv", index=False)

# ============================================================
# 2) Is -> Is_results.csv
# ============================================================
Is_cols = []
for bus in grid.get_buses():

    if bus.ph_n: Is_cols.append(f"Is_n_{bus.name}")
    if bus.ph_a: Is_cols.append(f"Is_a_{bus.name}")
    if bus.ph_b: Is_cols.append(f"Is_b_{bus.name}")
    if bus.ph_c: Is_cols.append(f"Is_c_{bus.name}")

df_Is = pd.concat([time_df, pd.DataFrame(Is, columns=Is_cols)], axis=1)
df_Is.to_csv("Is_results.csv", index=False)

# ============================================================
# 3) Ilines -> Ilines_results.csv
# ============================================================
Il_cols = []

for line in grid.get_lines():

    bf = line.bus_from
    bt = line.bus_to

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

# ============================================================
# 4) x -> x_gen_results.csv
# ============================================================
x_cols = []
offset = 0

for gen_idx, gen in enumerate(grid.get_generators(), start=1):

    model = gen.emt_model
    state_vars     = model.state_vars        # list of names
    algebraic_vars = model.algebraic_vars    # list of names

    var_names = state_vars + algebraic_vars  # in correct order

    # assign names with Gen index
    for name in var_names:
        x_cols.append(f"{name}_Gen{gen_idx}")

df_x = pd.concat([time_df, pd.DataFrame(x, columns=x_cols)], axis=1)
df_x.to_csv("x_gen_results.csv", index=False)


# ============================================================
# 5) dx -> dx_gen_results.csv (ONLY state vars)
# ============================================================
dx_cols = []

offset = 0
for gen_idx, gen in enumerate(grid.get_generators(), start=1):

    model = gen.emt_model
    state_vars = model.state_vars  # only variables with derivative

    for name in state_vars:
        dx_cols.append(f"d{name}_Gen{gen_idx}")

df_dx = pd.concat([time_df, pd.DataFrame(dx, columns=dx_cols)], axis=1)
df_dx.to_csv("dx_gen_results.csv", index=False)

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

plot_voltages("V_results.csv")
# plot_ilines("I_lines_results.csv")
plot_generators("x_gen_results.csv","dx_gen_results.csv" )
plot_isource("Is_results.csv")
plot_v_i("V_results.csv", "x_gen_results.csv")

fig, axs = plt.subplots(2, 3, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, x[:,3], label=r"$\psi_f\;[\mathrm{p.u.}]$", color="b")
axs[0].set_xlabel(r"$t\;[\mathrm{s}]$")
axs[0].set_ylabel(r" $\psi~[\mathrm{p.u.}]$")
axs[0].set_title(r"Field flux $\psi_f$")
axs[0].legend(loc="upper right")
axs[0].set_ylim([-1.4, -1.2])
axs[0].grid(True)

axs[1].plot(t, x[:,9], label=r"$i_f\;[\mathrm{p.u.}]$", color="b")
axs[1].set_xlabel(r"Time [ms]")
axs[1].set_ylabel(r"Current $\;[\mathrm{p.u.}]$")
axs[1].set_title(r"Field current $i_f$ ")
axs[1].legend(loc="upper right")
axs[1].set_ylim([-1.2, -1.0])
axs[1].grid(True)

axs[2].plot(t, x[:,21], label=r"$v_f\;[\mathrm{p.u.}]$", color="b")
axs[2].set_xlabel(r"Time [ms]")
axs[2].set_ylabel(r"Voltage $\;[\mathrm{p.u.}]$")
axs[2].set_title(r"Field voltage $v_f$")
axs[2].legend(loc="upper right")
axs[2].set_ylim([-0.2, 0.2])
axs[2].grid(True)

axs[3].plot(t, x[:,0], label=r"$\psi_d\;[\mathrm{p.u.}]$", color="b")
axs[3].set_xlabel(r"Time [ms]")
axs[3].set_ylabel(r"$\psi~\;[\mathrm{p.u.}]$")
axs[3].set_title(r"Direct-axis flux $psi_d$")
axs[3].legend(loc="upper right")
axs[3].set_ylim([-1.4, -1.0])
axs[3].grid(True)

axs[4].plot(t, x[:,7], label=r"$i_d\;[\mathrm{p.u.}]$", color="b")
axs[4].set_xlabel(r"Time [ms]")
axs[4].set_ylabel(r"Current $\;[\mathrm{p.u.}]$")
axs[4].set_title(r"Direct-axis current $i_d$")
axs[4].legend(loc="upper right")
axs[4].set_ylim([0.0, 1.0])
axs[4].grid(True)

axs[5].plot(t, x[:,11], label=r"$v_d\;[\mathrm{p.u.}]$", color="b")
axs[5].set_xlabel(r"Time [ms]")
axs[5].set_ylabel(r"Voltage $\;[\mathrm{p.u.}]$")
axs[5].set_title(r"Direct-axis voltage $v_d$")
axs[5].legend(loc="upper right")
axs[5].set_ylim([0.5, 1.5])
axs[5].grid(True)

plt.suptitle(
    r"Synchronous generator model",
    fontsize=14,
    fontweight="bold"
)
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()


fig, axs = plt.subplots(2, 3, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, dx[:,0], label=r"$\dot{\psi}_d\;[\mathrm{p.u.}]$", color="b")
axs[0].set_xlabel(r"Time [ms]")
axs[0].set_ylabel(r"$\dot{\psi}_d \;[\mathrm{p.u.}]$")
axs[0].set_title(r"Direct-axis flux derivative $\dot{\psi}_d$")
axs[0].legend(loc="upper right")
axs[0].set_ylim([-0.5, 1.0])
axs[0].grid(True)

axs[1].plot(t, dx[:,2], label=r"$\dot{\psi}_f\;[\mathrm{p.u.}]$", color="b")
axs[1].set_xlabel(r"Time [ms]")
axs[1].set_ylabel(r"$\dot{\psi}_f \;[\mathrm{p.u.}]$")
axs[1].set_title(r"Field flux derivative $\dot{\psi}_f$")
axs[1].legend(loc="upper right")
axs[1].set_ylim([-0.2, 0.2])
axs[1].grid(True)

axs[2].plot(t, dx[:,1], label=r"$\dot{\psi}_q\;[\mathrm{p.u.}]$", color="b")
axs[2].set_xlabel(r"Time [ms]")
axs[2].set_ylabel(r"$\dot{\psi}_q \;[\mathrm{p.u.}]$")
axs[2].set_title(r"Quadrature-axis flux derivative $\dot{\psi}_q$")
axs[2].legend(loc="upper right")
axs[2].set_ylim([-0.5, 1.0])
axs[2].grid(True)

axs[3].plot(t, dx[:,5], label=r"$\dot{\omega}\;[\mathrm{p.u.}]$", color="b")
axs[3].set_xlabel(r"Time [ms]")
axs[3].set_ylabel(r"$\dot{\omega}$ $\;[\mathrm{p.u.}]$")
axs[3].set_title(r"Angular frequency derivative $\dot{\omega}$")
axs[3].legend(loc="upper right")
axs[3].set_ylim([-5, 10])
axs[3].grid(True)

axs[4].plot(t, dx[:,4], label=r"$\dot{\theta}\;[\mathrm{rad/s}]$", color="b")
axs[4].set_xlabel(r"Time [ms]")
axs[4].set_ylabel(r"$\dot{\theta} \;[\mathrm{rad/s}]$")
axs[4].set_title(r"Rotor angle derivative $\dot{\theta}$")
axs[4].legend(loc="upper right")
axs[4].set_ylim([-5, 320])
axs[4].grid(True)

axs[5].plot(t, dx[:,6], label=r"$\dot{e}_t\;[\mathrm{p.u.}]$", color="b")
axs[5].set_xlabel(r"Time [ms]")
axs[5].set_ylabel(r"PI error derivative $\;[\mathrm{p.u.}]$")
axs[5].set_title(r"PI error derivative $\dot{e}_t$")
axs[5].legend(loc="upper right")
axs[5].set_ylim([-5, 10])
axs[5].grid(True)

plt.suptitle(
    r"Synchronous generator model",
    fontsize=14,
    fontweight="bold"
)
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()


# fig, axs = plt.subplots(2, 3, figsize=(12, 8))
# axs = axs.flatten()
# axs[0].plot(t, x[:,3], label='psi_f [p.u.]', color='b')
# axs[0].set_xlabel('Time [s]')
# axs[0].set_ylabel('Electromagnetic flux  [p.u.]')
# axs[0].set_title('Field flux ')
# axs[0].legend(loc='upper right')
# axs[0].set_ylim([-1.4,-1.2])
# axs[0].grid(True)
#
# axs[1].plot(t, x[:,9], label='i_f [p.u.]', color='b')
# axs[1].set_xlabel('Time [s]')
# axs[1].set_ylabel('Current [p.u.]')
# axs[1].set_title('Field current')
# axs[1].legend(loc='upper right')
# axs[1].set_ylim([-1.2, -1])
# axs[1].grid(True)
#
# axs[2].plot(t, x[:,21], label='v_f [p.u.]', color='b')
# axs[2].set_xlabel('Time [s]')
# axs[2].set_ylabel('Voltage [p.u.]')
# axs[2].set_title('Field voltage')
# axs[2].legend(loc='upper right')
# # axs[1].set_ylim([-2, 2])
# axs[2].set_ylim([-0.2, 0.2])
# axs[2].grid(True)
#
#
# axs[3].plot(t, x[:,0], label='psi_d [p.u.]', color='b')
# axs[3].set_xlabel('Time [s]')
# axs[3].set_ylabel('Flux [p.u.]')
# axs[3].set_title('Direct axis flux')
# axs[3].legend(loc='upper right')
# axs[3].set_ylim([-1.4, -1])
# axs[3].grid(True)
#
# axs[4].plot(t, x[:,7], label='i_d [p.u.]', color='b')
# axs[4].set_xlabel('Time [s]')
# axs[4].set_ylabel('Current [p.u.]')
# axs[4].set_title('Direct axis current')
# axs[4].legend(loc='upper right')
# axs[4].set_ylim([0, 1])
# axs[4].grid(True)
#
# axs[5].plot(t, x[:,11], label='v_d [p.u.]', color='b')
# axs[5].set_xlabel('Time [s]')
# axs[5].set_ylabel('Voltage [p.u.]')
# axs[5].set_title('Direct axis voltage')
# axs[5].legend(loc='upper right')
# axs[5].set_ylim([0.5, 1.5])
# axs[5].grid(True)
#
#
#
# plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
# plt.tight_layout(rect=[0, 0, 1, 0.96])
# plt.show()
#
#
#
# fig, axs = plt.subplots(2, 3, figsize=(12, 8))
# axs = axs.flatten()
#
# axs[0].plot(t, dx[:,0], label='d_psi_d [p.u.]', color='b')
# axs[0].set_xlabel('Time [s]')
# axs[0].set_ylabel('Flux derivative [p.u.]')
# axs[0].set_title('Direct axis flux derivative')
# axs[0].legend(loc='upper right')
# axs[0].set_ylim([-0.5,1])
# axs[0].grid(True)
#
#
# axs[1].plot(t, dx[:,2], label='d_psi_f [p.u.]', color='b')
# axs[1].set_xlabel('Time [s]')
# axs[1].set_ylabel('Flux derivative [p.u.]')
# axs[1].set_title('Field flux derivative')
# axs[1].legend(loc='upper right')
# # axs[1].set_ylim([-2, 2])
# axs[1].set_ylim([-0.2, 0.2])
# axs[1].grid(True)
#
# axs[2].plot(t, dx[:,1], label='d_psi_q [p.u.]', color='b')
# axs[2].set_xlabel('Time [s]')
# axs[2].set_ylabel('Flux  derivative[p.u.]')
# axs[2].set_title('Quadrature axis flux derivative')
# axs[2].legend(loc='upper right')
# axs[2].set_ylim([-0.5,1])
# axs[2].grid(True)
#
# axs[3].plot(t, dx[:,5], label='d_w [p.u.]', color='b')
# axs[3].set_xlabel('Time [s]')
# axs[3].set_ylabel('Angular frequency derivative[p.u.]')
# axs[3].set_title('Angular frequency derivative d_w')
# axs[3].legend(loc='upper right')
# axs[3].set_ylim([-5, 10])
# axs[3].grid(True)
#
# axs[4].plot(t, dx[:,4], label='d_theta [p.u.]', color='b')
# axs[4].set_xlabel('Time [s]')
# axs[4].set_ylabel('Rotor angle derivative[rad/s]')
# axs[4].set_title('Rotor angle derivative d_theta')
# axs[4].legend(loc='upper right')
# axs[4].set_ylim([-5, 320])
# axs[4].grid(True)
#
# axs[5].plot(t, dx[:,6], label='d_et [p.u.]', color='b')
# axs[5].set_xlabel('Time [s]')
# axs[5].set_ylabel('PI error derivative[p.u.]')
# axs[5].set_title('et derivative d_t')
# axs[5].legend(loc='upper right')
# axs[5].set_ylim([-5, 10])
# axs[5].grid(True)
#
# plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
# plt.tight_layout(rect=[0, 0, 1, 0.96])
# plt.show()



















# two phase
# line0.x = [-12.65, 12.65] # Phase conductor x-axis coordinates [m]
# line0.y = [27.5, 27.5] # Phase conductor heights [m]
# line0.R_ac = [0.1363, 0.1363]  # Phase conductor AC resistances [Ohm/km]
# line0.radius = [0.0105, 0.0105] # Phase conductor radi [m]
# line0.inner_radius = [0.0045, 0.0045] # Phase conductor inner tube radii [m]
# line0.rho_e = 100 # Earth resistivity [Ohm.m]

# one phase
# line0.x = [-12.65] # Phase conductor x-axis coordinates [m]
# line0.y = [27.5] # Phase conductor heights [m]
# line0.R_ac = [0.1363]  # Phase conductor AC resistances [Ohm/km]
# line0.radius = [0.0105] # Phase conductor radi [m]
# line0.inner_radius = [0.0045] # Phase conductor inner tube radii [m]
# line0.rho_e = 100 # Earth resistivity [Ohm.m]

# one phase with neutral
# line0.x = [-12.65, 0] # Phase conductor x-axis coordinates [m]
# line0.y = [27.5,  20] # Phase conductor heights [m]
# line0.R_ac = [0.1363,  0.1363]  # Phase conductor AC resistances [Ohm/km]
# line0.radius = [0.0105,  0.0105] # Phase conductor radi [m]
# line0.inner_radius = [0.0045, 0.0045] # Phase conductor inner tube radii [m]
# line0.rho_e = 100 # Earth resistivity [Ohm.m]

# three phase with neutral
# line0.x = [-12.65, 0, 12.65, 0] # Phase conductor x-axis coordinates [m]
# line0.y = [27.5, 27.5, 27.5, 20] # Phase conductor heights [m]
# line0.R_ac = [0.1363, 0.1363, 0.1363, 0.1363]  # Phase conductor AC resistances [Ohm/km]
# line0.radius = [0.0105, 0.0105, 0.0105, 0.0105] # Phase conductor radi [m]
# line0.inner_radius = [0.0045, 0.0045, 0.0045, 0.0045] # Phase conductor inner tube radii [m]
# line0.rho_e = 100 # Earth resistivity [Ohm.m]



