# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math

import numpy as np
from matplotlib import pyplot as plt

import sys
import os

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

fn = Const(50)  # Hz
wb = Const(2 * np.pi * 50) # 2 * np.pi * fn  # rad/s
Rload = Var("Rload")

La = Const(0.15)  # p.u.
Lmd =  Const(0.9)  # p.u.
Lmq =  Const(0.9)  # p.u.
Lf = Const(0.10)  # p.u.
Ra = Const(0.001)  # p.u.
Rf = Const(0.017)  # p.u.
L0 = Const(0.14) # p.u.
R0 = Const(0.001)  # p.u.
D = Const(2)  # p.u.
H = Const(5)  # p.u.


L1d =  Const(1.5) #p.u.
L1q =  Const(1.5) #p.u.
R1d =  Const(1.7) #p.u.
R1q =  Const(1.7) #p.u.

Kp =  Const(2.0) #p.u.

pi = Const(np.pi)

# Build the system
grid = gce.MultiCircuit(Sbase = 160, fbase = 50)
# Bus
v_base = 15/ np.sqrt(3) #kV
bus1 = Bus(name="Bus1", Vnom= v_base)
grid.add_bus(bus1)


# Generator
gen1 = Generator(name="Gen1", P=160, vset=1.0, Sbase = 160, Snom = 160)
grid.add_generator(bus=bus1, api_obj=gen1)

load1 = Load(name="Load1", P=160, Q=0)
grid.add_load(bus=bus1, api_obj=load1)

# event1 = RmsEvent(load1, "Pl0", 2.5, -9.0)

res = gce.power_flow(grid)

print(f"Converged: {res.converged}")

# ----------
# Intialization
# ----------
psi_d0 = -1.3343237871635951
psi_1d0 = -1.3576900283368245
psi_q0 = 0.4671690485234327
psi_1q0 = 0.4004306130200852
psi_f0 = -1.5241219700452913
psi_00 = -2.3513417220457447e-18
i_f0 = -1.6643194170846676
v_f00 = -0.028293430090439352
v_a0 = 0.46732482346458765
v_b0 = -1.3896060228268592
v_c0 = 0.9222811993622715
v_d0 = 0.4673248234645876
v_q0 = 1.3347687100669507
v_00 = -1.6795298014614602e-20
i_a0 = 0.15577494115486257
i_b0 = -0.463202007608953
i_c0 = 0.3074270664540905
i_d0 = 0.15577494115486257
i_q0 = 0.4449229033556502
i_00 = -1.6795298014612465e-17
i_1q0 = 0.0
i_1d0 = 0.0
T_e0 = 0.9996666666666665
Tm0 = 0.9996666666666665
theta0 = 1.2340175418656953
Pe0 = 0.9999999999999999
Qe0 = 3.2049378106392736e-17
Pm0 = 0.9996666666666665

wref = 1.0
Tmref = Const(0.9996666666666665)  # p.u.

# ----------
# Variables
# ----------
t = Var("t")

# generator vars
v_a = Var("v_a") #1
v_b = Var("v_b") #2
v_c = Var("v_c") #3
i_a = Var("i_a") #4
i_b = Var("i_b") #5
i_c = Var("i_c") #6
i_d = Var("i_d") #7
i_q = Var("i_q") #8
i_1d = Var("i_1d") #7
i_1q = Var("i_1q") #8
i_0 = Var("i_0") #9
i_f = Var("i_f") #10
v_f = Var("v_f") #11
psi_d = Var("psi_d") #12
psi_q = Var("psi_q") #13
psi_1d = Var("psi_1d") #12
psi_1q = Var("psi_1q") #13
psi_0 = Var("psi_0") #14
psi_f = Var("psi_f") #15
v_d = Var("v_d") #16
v_q = Var("v_q") #17
v_0 = Var("v_0") #18
w = Var("w") #19
theta = Var("theta") #20
T_e = Var("Te") #21
T_m = Var("Tm") #22
Pe = Var("Pe") #23
Pm = Var("Pm") #23
Qe= Var("Qe") #24


v_f0 = Const(v_f00)
generator_block_1 = Block(
    state_eqs=[
        v_d - Ra * i_d - w * psi_q,
        v_q - Ra * i_q + w * psi_d,
        v_f - Rf * i_f,
        v_0 - R0 * i_0,
        0.0 - R1d * i_1d,
        0.0 - R1q * i_1q,
        wb * w,
        (T_m - T_e - D * (w - 1.0)) / (2 * H),
    ],
    state_vars=[psi_q, psi_d, psi_f, psi_0, psi_1d, psi_1q, theta, w], #6
    algebraic_eqs=[
        psi_d - ((Lmd + La) * i_d + Lmd * i_f + Lmd * i_1d),  #i_d
        psi_f -(Lmd * i_d + (Lmd + Lf) * i_f + Lmd * i_1d), #i_f
        psi_1d -(Lmd * i_d + Lmd * i_f + (Lmd + L1d) * i_1d), #i_1d
        psi_q - ((Lmd + La) * i_q + Lmq * i_1q), #i_q
        psi_1q - (Lmd * i_q + (Lmq + L1q) * i_1q), #i_1q
        psi_0 - L0 * i_0, #i_0

        v_a - i_a * Rload, #v_a
        v_b - i_b * Rload, #v_b
        v_c - i_c * Rload, #v_c
        # v_d - i_d * Rload, #v_d
        # v_q - i_q * Rload, #v_q
        # v_0 - i_0 * Rload, #v_0

        v_d - (2/3) * (v_a * cos(theta) + v_b * cos(theta - 2*pi/3) + v_c * cos(theta + 2*pi/3)), #v_d
        v_q - (2/3) * (v_a * sin(theta) + v_b * sin(theta - 2*pi/3) + v_c * sin(theta + 2*pi/3)), #v_q
        v_0 - (2/3) * (v_a * 0.5 + v_b * 0.5 + v_c * 0.5), #v_0

        i_a - (i_d * cos(theta) + i_q * sin(theta) + i_0), # i_a
        i_b - (i_d * cos(theta - 2*pi/3) + i_q * sin(theta - 2*pi/3) + i_0), # i_b
        i_c - (i_d * cos(theta + 2*pi/3) + i_q * sin(theta + 2*pi/3) + i_0), # i_c

        T_e + (3/2)*(psi_d * i_q - psi_q * i_d), #T_e

        Pe - (i_a * v_a + i_b * v_b + i_c * v_c), #Pe
        Qe - (1/np.sqrt(3))*((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b), #Qe

        T_m - (Tmref + Kp * (wref - w)), #Tm
        v_f - v_f0, #v_f
        Pm - (T_m * w) #Pm

    ],
    algebraic_vars=[i_d, i_f, i_1d, i_q, i_1q, i_0, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, T_e, Pe, Qe, T_m, v_f, Pm], #19
)

generator_block_1.event_dict = {Rload: Const(3.0)}


# ----------------------------------------------------------------------------------------------------------------------
# System
# ----------------------------------------------------------------------------------------------------------------------
sys = Block(
    children=[generator_block_1],
    # in_vars=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = BlockSolver(sys, t)

params_mapping = { }

vars_mapping = {
    v_a: v_a0,
    v_b: v_b0,
    v_c: v_c0,
    i_a: i_a0,
    i_b: i_b0,
    i_c: i_c0,
    i_d: i_d0,
    i_q: i_q0,
    i_1d: i_1d0,
    i_1q: i_1q0,
    i_0: i_00,
    i_f: i_f0,
    v_f: v_f00,
    psi_d: psi_d0,
    psi_q: psi_q0,
    psi_1d: psi_1d0,
    psi_1q: psi_1q0,
    psi_0: psi_00,
    psi_f: psi_f0,
    v_d: v_d0,
    v_q: v_q0,
    v_0: v_00,
    w: wref,
    theta: theta0,
    T_e: T_e0,
    T_m: Tm0,
    Pe: Pe0,
    Qe: Qe0,
    Pm: Pm0,
}

params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector(vars_mapping)

vars_in_order = slv.sort_vars(vars_mapping)

t, y = slv.simulate(
    t0=0.0,
    t_end=3,
    h=5e-6,
    x0=x0,
    params0=params0,
    newton_tol = 1e-12,
    newton_max_iter = 500000000,
    method="implicit_euler"
)

slv.save_simulation_to_csv('simulation_results.csv', t, y, csv_saving = True)


fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, y[:, slv.get_var_idx(v_a)], label='v_a [pu]', color='b')
axs[0].plot(t, y[:, slv.get_var_idx(v_b)], label='v_b [pu]', color='r')
axs[0].plot(t, y[:, slv.get_var_idx(v_c)], label='v_c [pu]', color='g')
axs[0].set_title('Voltages abc')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Voltage [pu]')
axs[0].set_ylim([-3, 3]) #
axs[0].legend(loc='upper right')
axs[0].grid(True)

axs[2].plot(t, y[:, slv.get_var_idx(v_d)], label='v_d [pu]', color='b')
axs[2].plot(t, y[:, slv.get_var_idx(v_q)], label='v_q [pu]', color='r')
axs[2].plot(t, y[:, slv.get_var_idx(v_0)], label='v_0 [pu]', color='g')
axs[2].set_title('Voltages dq0')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('Voltage [pu]')
axs[2].set_ylim([-3, 3]) #
axs[2].legend(loc='upper right')
axs[2].grid(True)

axs[1].plot(t, y[:, slv.get_var_idx(i_a)], label='i_a [pu]', color='b')
axs[1].plot(t, y[:, slv.get_var_idx(i_b)], label='i_b [pu]', color='r')
axs[1].plot(t, y[:, slv.get_var_idx(i_c)], label='i_c [pu]', color='g')
axs[1].set_title('Currents abc')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [pu]')
axs[1].set_ylim([-2, 2])
axs[1].legend(loc='upper right')
axs[1].grid(True)


axs[3].plot(t, y[:, slv.get_var_idx(i_d)], label='i_d [pu]', color='b')
axs[3].plot(t, y[:, slv.get_var_idx(i_q)], label='i_q [pu]', color='r')
axs[3].plot(t, y[:, slv.get_var_idx(i_0)], label='i_0 [pu]', color='g')
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

axs[0].plot(t, y[:, slv.get_var_idx(theta)], label='theta [rad]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Angle [rad]')
axs[0].set_title('Theta')
axs[0].legend(loc='upper right')
axs[0].grid(True)


axs[1].plot(t, y[:, slv.get_var_idx(w)], label='omega [p.u.]', color='b')
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
plt.plot(t, y[:, slv.get_var_idx(T_e)], label='Electrical torque [p.u.]', color='b')
plt.plot(t, y[:, slv.get_var_idx(T_m)], label='Mechanical torque [p.u.]', color='r')
plt.xlabel('Time [s]')
plt.ylabel('Torque [p.u.]')
plt.title("Torques - Synchronous generator model")
plt.legend(loc='upper right')
plt.ylim([-3, 3])
plt.grid(True)
plt.show()

fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, y[:, slv.get_var_idx(psi_f)], label='psi_f [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Field flux [p.u.]')
axs[0].set_title('Field flux psi_f')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)

axs[1].plot(t, y[:, slv.get_var_idx(i_f)], label='i_f [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('Field current i_f')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-2, 2])
axs[1].grid(True)

axs[2].plot(t, y[:, slv.get_var_idx(v_f)], label='v_f [p.u.]', color='b')
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

axs[0].plot(t, y[:, slv.get_var_idx(psi_d)], label='psi_d [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('flux [p.u.]')
axs[0].set_title('flux psi_d')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)


axs[1].plot(t, y[:, slv.get_var_idx(i_d)], label='i_d [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('current i_d')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-2,2])
axs[1].grid(True)

axs[2].plot(t, y[:, slv.get_var_idx(psi_q)], label='psi_q [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('flux [p.u.]')
axs[2].set_title('flux psi_q')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-2, 2])
axs[2].grid(True)

axs[3].plot(t, y[:, slv.get_var_idx(i_q)], label='i_q [p.u.]', color='b')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('Current [p.u.]')
axs[3].set_title('current i_q')
axs[3].legend(loc='upper right')
axs[3].set_ylim([-2, 2])
axs[3].grid(True)

axs[4].plot(t, y[:, slv.get_var_idx(psi_0)], label='psi_0 [p.u.]', color='b')
axs[4].set_xlabel('Time [s]')
axs[4].set_ylabel('flux [p.u.]')
axs[4].set_title('flux psi_0')
axs[4].legend(loc='upper right')
axs[4].set_ylim([-2, 2])
axs[4].grid(True)

axs[5].plot(t, y[:, slv.get_var_idx(i_0)], label='i_0 [p.u.]', color='b')
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

axs[0].plot(t, y[:, slv.get_var_idx(Pe)], label='P_e [p.u.]', color='b')
axs[0].plot(t, y[:, slv.get_var_idx(Pm)], label='P_m [p.u.]', color='r')
# axs[0].plot(t, Pm, label='P_m [p.u.]', color='r')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Active power [p.u.]')
axs[0].set_title('Active power P_e')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-1,5])
axs[0].grid(True)


axs[1].plot(t, y[:, slv.get_var_idx(Qe)], label='Q_e [p.u.]', color='b')
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