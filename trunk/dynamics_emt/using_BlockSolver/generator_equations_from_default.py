# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math

import numpy as np
from matplotlib import pyplot as plt

import sys
import os

from VeraGridEngine.Utils.Symbolic import DiffBlock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver_no_diff import BlockSolver
from VeraGridEngine.Simulations.SmallSignalStability.small_signal_driver import run_small_signal_stability
import VeraGridEngine.api as gce

from VeraGridEngine.Templates.Emt.generator_emt_type_template import Generator_emt_type_EmtTemplate
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Utils.Symbolic.block_solver import DiffBlockSolver, DiffBlock



pi = Const(np.pi)

# Build the system
grid = gce.MultiCircuit(Sbase = 160, fbase = 50)
# Bus
v_base = 15/ np.sqrt(3) #kV
bus1 = Bus(name="Bus1", Vnom= v_base)
grid.add_bus(bus1)

# load1 = Load(name="Load1", P=160, Q=0)
# grid.add_load(bus=bus1, api_obj=load1)

# Generator

gen1 = Generator(name="Gen1", P=160, vset=1.0, Sbase = 160, Snom = 160)
grid.add_generator(bus=bus1, api_obj=gen1)
gen1.initialize_emt(5e-5)
gen_template = gen1.emt_model.model_template

print('gen1.emt_model.model = ', gen1.emt_model.model)
print('gen1.emt_model.model.algebraic_vars = ', gen1.emt_model.model.algebraic_vars)
print('gen1.emt_model.model.algebraic_eqs = ', gen1.emt_model.model.algebraic_eqs)
print("gen_template =", gen_template)
print("gen_template.v_a =", gen_template.v_a)


load1 = Load(name="Load1", P=160, Q=0)
grid.add_load(bus=bus1, api_obj=load1)

# event1 = RmsEvent(load1, "Pl0", 2.5, -9.0)

res = gce.power_flow(grid)

print(f"Converged: {res.converged}")

# ----------
# Intialization
# ----------
w0 = 1.0
psi_d0 = -1.229887350550713
psi_q0 = 0.6971685548303476
psi_f0 = -1.3696013540893925
psi_00 = -8.664674504566788e-17
i_f0 = -1.0484395244679796
v_f00 = -0.017823471915955656
v_a0 = 0.6974010218376268
v_b0 = -1.4141693565707523
v_c0 = 0.7167683347331255
v_d0 = 0.6974010218376268
v_q0 = 1.2302974497006134
v_00 = -5.09686735562785e-20
i_a0 = 0.23246700727920894
i_b0 = -0.4713897855235841
i_c0 = 0.23892277824437516
i_d0 = 0.23246700727920896
i_q0 = 0.4100991499002045
i_00 = -5.096867355627523e-17
T_e0 = 0.9996666666666664
T_m0 = 0.9996666666666664
theta0 = 1.0551043059609357
Pe0 = 0.9999999999999998
Qe0 = 0.0
Pm0 = 0.9996666666666664

wref = 1.0
# Tmref = Const(T_m0)  # p.u.

d_w0 = 0.0
d_theta0 = 1.0
d_psi_d0 = 0.0
d_psi_f0 = 0.0
d_psi_q0 = 0.0
d_psi_00 = 0.0
# d_psi_1d0 = 0.0
# d_psi_1q0 = 0.0


# options = RmsOptions(time_step = 5e-6,
#                      simulation_time = 3,
#                      tolerance = 1e-12,
#                      integration_method = "implicit euler")
# drv = RmsSimulationDriver(grid, options, res)
# drv.run()
# y = drv.results.values
#
# n_steps = int(options.simulation_time / options.time_step)
# t = np.linspace(0, options.simulation_time, n_steps)

# ----------------------------------------------------------------------------------------------------------------------
# System
# ----------------------------------------------------------------------------------------------------------------------
sys = DiffBlock(
    children=[gen1.emt_model.model],
    in_vars=[]
)
t = Var("t")
# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = DiffBlockSolver(sys, t)

params_mapping = { }

vars_mapping = {
    gen_template.v_a: v_a0,
    gen_template.v_b: v_b0,
    gen_template.v_c: v_c0,

    gen_template.i_a: i_a0,
    gen_template.i_b: i_b0,
    gen_template.i_c: i_c0,

    gen_template.i_d: i_d0,
    gen_template.i_q: i_q0,
    gen_template.i_0: i_00,

    gen_template.i_f: i_f0,
    gen_template.v_f: v_f00,

    gen_template.psi_d: psi_d0,
    gen_template.psi_q: psi_q0,
    gen_template.psi_0: psi_00,
    gen_template.psi_f: psi_f0,

    gen_template.v_d: v_d0,
    gen_template.v_q: v_q0,
    gen_template.v_0: v_00,

    gen_template.omega: wref,
    gen_template.theta: theta0
    ,
    gen_template.Te: T_e0,
    gen_template.Tm: T_m0,

    gen_template.Pe: Pe0,
    gen_template.Qe: Qe0,
    gen_template.Pm: Pm0,
}

diff_mapping = {
    gen_template.d_omega: d_w0,
    gen_template.d_theta: d_theta0,
    gen_template.d_psi_d: d_psi_d0,
    gen_template.d_psi_f: d_psi_f0,
    gen_template.d_psi_q: d_psi_q0,
    gen_template.d_psi_0: d_psi_00
}

params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector(vars_mapping)
dx0 = slv.build_init_diffvars_vector(diff_mapping)

vars_in_order = slv.sort_vars(vars_mapping)

print("Solving...")
t, y, dx, timings = slv.simulate(
    t0=0.0,
    t_end=1.2,
    h=5e-5,
    x0=x0,
    dx0 =dx0,
    params0=params0,
    method = "implicit_euler",
    newton_tol = 1e-12)

slv.save_simulation_to_csv('simulation_results.csv', t, y, csv_saving = True)


fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, y[:, slv.get_var_idx(gen_template.v_a)], label='v_a [pu]', color='b')
axs[0].plot(t, y[:, slv.get_var_idx(gen_template.v_b)], label='v_b [pu]', color='r')
axs[0].plot(t, y[:, slv.get_var_idx(gen_template.v_c)], label='v_c [pu]', color='g')
axs[0].set_title('Voltages abc')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Voltage [pu]')
axs[0].set_ylim([-3, 3]) #
axs[0].legend(loc='upper right')
axs[0].grid(True)

axs[2].plot(t, y[:, slv.get_var_idx(gen_template.v_d)], label='v_d [pu]', color='b')
axs[2].plot(t, y[:, slv.get_var_idx(gen_template.v_q)], label='v_q [pu]', color='r')
axs[2].plot(t, y[:, slv.get_var_idx(gen_template.v_0)], label='v_0 [pu]', color='g')
axs[2].set_title('Voltages dq0')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('Voltage [pu]')
axs[2].set_ylim([-3, 3]) #
axs[2].legend(loc='upper right')
axs[2].grid(True)

axs[1].plot(t, y[:, slv.get_var_idx(gen_template.i_a)], label='i_a [pu]', color='b')
axs[1].plot(t, y[:, slv.get_var_idx(gen_template.i_b)], label='i_b [pu]', color='r')
axs[1].plot(t, y[:, slv.get_var_idx(gen_template.i_c)], label='i_c [pu]', color='g')
axs[1].set_title('Currents abc')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [pu]')
axs[1].set_ylim([-2, 2])
axs[1].legend(loc='upper right')
axs[1].grid(True)


axs[3].plot(t, y[:, slv.get_var_idx(gen_template.i_d)], label='i_d [pu]', color='b')
axs[3].plot(t, y[:, slv.get_var_idx(gen_template.i_q)], label='i_q [pu]', color='r')
axs[3].plot(t, y[:, slv.get_var_idx(gen_template.i_0)], label='i_0 [pu]', color='g')
axs[3].set_title('Currents dq0')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('Current [pu]')
axs[3].legend(loc='upper left')
axs[3].set_ylim([-2, 2])
axs[3].grid(True)

plt.suptitle('Synchronous Generator – Voltages and Currents', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

fig, axs = plt.subplots(1, 2, figsize=(12, 8))
axs = axs.flatten()  # per accedir fàcilment a cada subplot com un vector

axs[0].plot(t, y[:, slv.get_var_idx(gen_template.theta)], label='theta [rad]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Angle [rad]')
axs[0].set_title('Theta')
axs[0].legend(loc='upper right')
axs[0].grid(True)


axs[1].plot(t, y[:, slv.get_var_idx(gen_template.omega)], label='omega [p.u.]', color='b')
axs[1].plot(t, np.ones_like(t), label='omega base [p.u.]', color='r')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Speed [p.u.]')
axs[1].set_title('Omega')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-2, 2])
axs[1].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])  # deixa espai per al títol global
plt.show()

plt.figure(figsize=(10, 6))
plt.plot(t, y[:, slv.get_var_idx(gen_template.Te)], label='Electrical torque [p.u.]', color='b')
plt.plot(t, y[:, slv.get_var_idx(gen_template.Tm)], label='Mechanical torque [p.u.]', color='r')
plt.xlabel('Time [s]')
plt.ylabel('Torque [p.u.]')
plt.title("Torques - Synchronous generator model")
plt.legend(loc='upper right')
plt.ylim([-3, 3])
plt.grid(True)
plt.show()

fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, y[:, slv.get_var_idx(gen_template.psi_f)], label='psi_f [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Field flux [p.u.]')
axs[0].set_title('Field flux psi_f')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)

axs[1].plot(t, y[:, slv.get_var_idx(gen_template.i_f)], label='i_f [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('Field current i_f')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-2, 2])
axs[1].grid(True)

axs[2].plot(t, y[:, slv.get_var_idx(gen_template.v_f)], label='v_f [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('Field voltage [p.u.]')
axs[2].set_title('Field voltage v_f')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-2, 2])
axs[2].grid(True)


plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

fig, axs = plt.subplots(3, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, y[:, slv.get_var_idx(gen_template.psi_d)], label='psi_d [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('flux [p.u.]')
axs[0].set_title('flux psi_d')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)


axs[1].plot(t, y[:, slv.get_var_idx(gen_template.i_d)], label='i_d [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('current i_d')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-2,2])
axs[1].grid(True)

axs[2].plot(t, y[:, slv.get_var_idx(gen_template.psi_q)], label='psi_q [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('flux [p.u.]')
axs[2].set_title('flux psi_q')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-2, 2])
axs[2].grid(True)

axs[3].plot(t, y[:, slv.get_var_idx(gen_template.i_q)], label='i_q [p.u.]', color='b')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('Current [p.u.]')
axs[3].set_title('current i_q')
axs[3].legend(loc='upper right')
axs[3].set_ylim([-2, 2])
axs[3].grid(True)

axs[4].plot(t, y[:, slv.get_var_idx(gen_template.psi_0)], label='psi_0 [p.u.]', color='b')
axs[4].set_xlabel('Time [s]')
axs[4].set_ylabel('flux [p.u.]')
axs[4].set_title('flux psi_0')
axs[4].legend(loc='upper right')
axs[4].set_ylim([-2, 2])
axs[4].grid(True)

axs[5].plot(t, y[:, slv.get_var_idx(gen_template.i_0)], label='i_0 [p.u.]', color='b')
axs[5].set_xlabel('Time [s]')
axs[5].set_ylabel('Current [p.u.]')
axs[5].set_title('current i_0')
axs[5].legend(loc='upper right')
axs[5].set_ylim([-2, 2])
axs[5].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

fig, axs = plt.subplots(1, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, y[:, slv.get_var_idx(gen_template.Pe)], label='P_e [p.u.]', color='b')
axs[0].plot(t, y[:, slv.get_var_idx(gen_template.Pm)], label='P_m [p.u.]', color='r')
# axs[0].plot(t, Pm, label='P_m [p.u.]', color='r')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Active power [p.u.]')
axs[0].set_title('Active power P_e')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-1,5])
axs[0].grid(True)


axs[1].plot(t, y[:, slv.get_var_idx(gen_template.Qe)], label='Q_e [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Reactive power [p.u.]')
axs[1].set_title('Reactive power Q_e')
axs[1].legend(loc='upper right')
# axs[1].set_ylim([-2, 2])
axs[1].set_ylim([-1, 5])
axs[1].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()