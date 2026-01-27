# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd

from matplotlib import pyplot as plt

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, sqrt
from VeraGridEngine.Utils.Symbolic.block import  DiffBlock
from VeraGridEngine.Utils.Symbolic.block_solver import DiffBlockSolver
from VeraGridEngine.Utils.Symbolic.block import Block, Var, DiffVar, Const
import VeraGridEngine.api as gce




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

res = gce.power_flow(grid)

print(f"Converged: {res.converged}")

# ----------
# Intialization
# ----------
# w0 = 1.0
# psi_d0 = -1.229887350550713
# psi_q0 = 0.6971685548303476
# psi_f0 = -1.3696013540893925
# psi_00 = -8.664674504566788e-17
# i_f0 = -1.0484395244679796
# v_f00 = -0.017823471915955656
# v_a0 = 0.6974010218376268
# v_b0 = -1.4141693565707523
# v_c0 = 0.7167683347331255
# v_d0 = 0.6974010218376268
# v_q0 = 1.2302974497006134
# v_00 = -5.09686735562785e-20
# i_a0 = 0.23246700727920894
# i_b0 = -0.4713897855235841
# i_c0 = 0.23892277824437516
# i_d0 = 0.23246700727920896
# i_q0 = 0.4100991499002045
# i_00 = -5.096867355627523e-17
# T_e0 = 0.9996666666666664
# T_m0 = 0.9996666666666664
# # theta0 = 1.0551043059609357
# theta0 = 0.0
# # Pe0 = 0.9999999999999998
# Pe0 = 0.9996666666666664
# Qe0 = 0.0
# Pm0 = 0.9996666666666664

# w0 = 1.0
# psi_d0 = -1.1842763746406721
# psi_q0 = 0.771982229268087
# psi_f0 = -1.3375495187614632
# psi_00 = -3.925011603517386e-17
# i_f0 = -1.0887100650967585
# v_f00 = -0.018508071106644895
# v_a0 = 0.7722782435188278
# v_b0 = -1.4121458156657476
# v_c0 = 0.6398675721469198
# v_d0 = 0.7722782435188278
# v_q0 = 1.1847304818343594
# v_00 = -2.3088303550114134e-20
# i_a0 = 0.2960142507407667
# i_b0 = -0.541275491144681
# i_c0 = 0.2452612404039144
# i_d0 = 0.29601425074076676
# i_q0 = 0.45410719368711
# i_00 = -2.3088303550102268e-17
# T_e0 = 1.1494592433299995
# T_m0 = 1.1494592433299995
# theta0 = 0.0
# Pe0 = 1.1498999999999997
# Qe0 = -8.012344526598184e-18
# Pm0 = 1.1494592433299995

w0 = 1.0
psi_d0 = -1.1842763746406721
psi_q0 = 0.771982229268087
psi_f0 = -1.3375495187614632
psi_00 = -3.925011603517386e-17
i_f0 = -1.0887100650967585
v_f00 = -0.018508071106644895
v_a0 = 0.7722782435188278
v_b0 = -1.4121458156657476
v_c0 = 0.6398675721469198
v_d0 = 0.7722782435188278
v_q0 = 1.1847304818343594
v_00 = -2.3088303550114134e-20
i_a0 = 0.2960142507407667
i_b0 = -0.541275491144681
i_c0 = 0.2452612404039144
i_d0 = 0.29601425074076676
i_q0 = 0.45410719368711
i_00 = -2.3088303550102268e-17
T_e0 = 1.0
T_m0 = 1.0
theta0 = 0.0
Pe0 = 1.0
Qe0 = -8.012344526598184e-18
Pm0 = 1.0


# w0 = 1.0
# psi_d0 = -1.2299371819390006
# psi_q0 = 0.6970807186395105
# psi_f0 = -1.3696367450900728
# psi_00 = -0.4004936625252342
# i_f0 = -1.048397104714715
# v_f00 = 0.00031765044537134294
# v_a0 = 1.4139779386212579
# v_b0 = -0.7073423460716806
# v_c0 = -0.7073423460716806
# v_d0 = 0.6973131176573745
# v_q0 = 1.2303472294205533
# v_00 = -0.00023558450736778483
# i_a0 = 0.23574153756483648
# i_b0 = -0.4712475298340954
# i_c0 = -0.4712475298340954
# i_d0 = 0.23239901786400435
# i_q0 = 0.41004748155265325
# i_00 = -0.23558450736778483
# T_e0 = 0.999500277458717
# T_m0 = 0.999500277458717
# theta0 = 1.0551757383211462
# Pe0 = 1.0
# Qe0 = 0.0
# Pm0 = 0.999500277458717

d_w0 = 0.0
d_theta0 = 1.0
d_psi_d0 = 0.0
d_psi_f0 = 0.0
d_psi_q0 = 0.0
d_psi_00 = 0.0

# ----------
# Variables that will be constants
# ----------
fn = Var("fn")
wb = Var("fn")
H = Var("H")
D = Var("D")
Ra = Var("Ra")
La = Var("La")
Lmd = Var("Lmd")
Lf = Var("Lf")
Rf = Var("Rf")
R0 = Var("R0")
L0 = Var("L0")
wref = Var("wref")
Tmref = Var("Tmref")
Kp = Var("Kp")
Ki = Var("Ki")
Rload = Var("Rload")
v_f0 = Var("v_f0")

Kp_avr = Var("Kp_avr")
Ki_avr = Var("Ki_avr")

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
i_0 = Var("i_0") #9

i_f = Var("i_f") #10
v_f = Var("v_f") #11

psi_d = Var("psi_d") #12
psi_q = Var("psi_q") #13
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
Qe = Var("Qe") #24
Pm = Var("Pm") #24

d_w = DiffVar.get_or_create('d_w', base_var=w)
d_theta = DiffVar.get_or_create('d_theta', base_var=theta)
d_psi_d = DiffVar.get_or_create('d_psid', base_var=psi_d)
d_psi_f = DiffVar.get_or_create('d_psif', base_var=psi_f)
d_psi_q = DiffVar.get_or_create('d_psiq', base_var=psi_q)
d_psi_0 = DiffVar.get_or_create('d_psi0', base_var=psi_0)


et = Var("et")
d_et = DiffVar.get_or_create('d_et', base_var=et)

ev = Var("ev")
d_ev = DiffVar.get_or_create('d_ev', base_var=ev)



generator_block_1 = DiffBlock(
state_eqs=[
        v_d - Ra * i_d - w * psi_q,
        v_q - Ra * i_q + w * psi_d,
        v_f - Rf * i_f,
        v_0 - R0 * i_0,
        wb * w,
        (T_m - T_e - D * (w - 1.0)) / (2 * H),
        wb * (1.0 - w), # d_et
        # 1.0 - (1/sqrt(3)*sqrt(v_d*v_d+v_q*v_q)),
    ],
    state_vars=[psi_d, psi_q, psi_f, psi_0, theta, w, et], #, ev], #6
    algebraic_eqs=[
        psi_d - ((Lmd + La) * i_d + Lmd * i_f),  #i_d
        psi_q - (Lmd + La) * i_q, #i_q
        psi_f -(Lmd * i_d + (Lmd + Lf) * i_f), #i_f
        psi_0 - L0 * i_0, #i_0

        v_a - i_a * Rload, #v_a
        v_b - i_b * Rload, #v_b
        v_c - i_c * Rload, #v_c

        v_d - (2/3) * (v_a * cos(theta) + v_b * cos(theta - 2*pi/3) + v_c * cos(theta + 2*pi/3)), #v_d
        v_q - (2/3) * (v_a * sin(theta) + v_b * sin(theta - 2*pi/3) + v_c * sin(theta + 2*pi/3)), #v_q
        v_0 - (2/3) * (v_a * 0.5 + v_b * 0.5 + v_c * 0.5), #v_0

        i_a - (i_d * cos(theta) + i_q * sin(theta) + i_0), # i_a
        i_b - (i_d * cos(theta - 2*pi/3) + i_q * sin(theta - 2*pi/3) + i_0), # i_b
        i_c - (i_d * cos(theta + 2*pi/3) + i_q * sin(theta + 2*pi/3) + i_0), # i_c

        T_e + (3/2)*(psi_d * i_q - psi_q * i_d), #T_e

        Pe - (i_a * v_a + i_b * v_b + i_c * v_c), #Pe
        Qe - (1/np.sqrt(3))*((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b), #Qe

        # T_m - (Tmref + Kp*(wref - w)), #Tm
        T_m - (T_e + Kp * (wref - w) + Ki * et), #Tm
        v_f - v_f0, #v_f
        # v_f - (v_f0 + Kp_avr * (1.0 - ((1/sqrt(3))*sqrt(v_d*v_d+v_q*v_q)) + Ki_avr * ev)), #v_f
        # Pm - (Pe - (3 / 2) * Ra * (i_d * i_d + i_q * i_q))
        Pm - Pe
    ],
    algebraic_vars=[i_d, i_q, i_f, i_0, v_a, v_b, v_c,
                    v_d, v_q, v_0, i_a, i_b, i_c, T_e, Pe, Qe,
                    T_m, v_f, Pm], #18
)
generator_block_1.diff_vars = [d_psi_d, d_psi_q, d_psi_f, d_psi_0, d_theta, d_w, d_et]#, d_ev]
generator_block_1.event_dict = {fn: Const(50.0),
                           wb: Const(2 * np.pi * 50.0),
                           H: Const(5.0),
                           D: Const(2.0),
                           Ra: Const(0.001),
                           La: Const(0.15),
                           Lmd: Const(1.55),
                           Lf: Const(0.10),
                           Rf: Const(0.017),
                           R0: Const(0.001),
                           L0: Const(0.14),
                           wref: Const(1.0),
                           Tmref: Const(1.0),
                           Kp: Const(2.0),
                           Ki: Const(1.0),
                           Kp_avr: Const(2.0),
                           Ki_avr: Const(1.0),
                           # Rload: Const(3.0),
                           Rload: Const(1/0.3833),
                           # v_f0: Const(-0.017823471915955656)}
                           # v_f0: Const(0.018508071106644895)}
                           v_f0: Const(-0.018508071106644895)}



# ----------------------------------------------------------------------------------------------------------------------
# System
# ----------------------------------------------------------------------------------------------------------------------
sys = Block(
    children=[generator_block_1],
    in_vars=[]
)

# ----------------------------------------------------------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------------------------------------------------------
slv = DiffBlockSolver(sys, t)

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
    i_0: i_00,

    i_f: i_f0,
    v_f: v_f00,

    psi_d: psi_d0,
    psi_q: psi_q0,
    psi_0: psi_00,
    psi_f: psi_f0,

    v_d: v_d0,
    v_q: v_q0,
    v_0: v_00,

    w: w0,
    theta: theta0,

    T_e: T_e0,
    T_m: T_m0,

    Pe: Pe0,
    Qe: Qe0,
    Pm: Pm0,

    et: 0.0,
    #ev: 0.0,

}

diff_mapping = {
    d_w: d_w0,
    d_theta: d_theta0,
    d_psi_d: d_psi_d0,
    d_psi_f: d_psi_f0,
    d_psi_q: d_psi_q0,
    d_psi_0: d_psi_00
}

alter_params0 = np.zeros(0)
params0 = slv.build_init_params_vector(params_mapping)
x0 = slv.build_init_vars_vector(vars_mapping)
dx0 = slv.build_init_diffvars_vector(diff_mapping)

vars_in_order = slv.sort_vars(vars_mapping)

print("Solving...")
t, y, dx, timing = slv.simulate(
    t0=0.0,
    t_end=0.2,
    h=5e-5,
    x0=x0,
    dx0 =dx0,
    params0=params0,
    alter_params0 = alter_params0,
    newton_tol = 1e-12,
    method="implicit_euler"
)

slv.save_simulation_to_csv('simulation_results.csv', t, y, csv_saving = True)

all_vars = slv.diff_vars
var_names = [str(var) + '_VeraGrid' for var in all_vars]

# Create DataFrame with time and variable data
df_simulation_results = pd.DataFrame(data=dx, columns=var_names)
df_simulation_results.insert(0, 'Time [s]', t)
df_simulation_results.to_csv('simulation_derivatives_results.csv', index=False)

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
axs[1].set_ylim([0.5, 1.5])
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
plt.ylim([0.5, 1.5])
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

fig, axs = plt.subplots(2, 3, figsize=(12, 8))
axs = axs.flatten()
axs[0].plot(t, y[:, slv.get_var_idx(psi_f)], label='psi_f [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('f flux  [p.u.]')
axs[0].set_title('f flux psi_f')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-1.4,-1.2])
axs[0].grid(True)


axs[1].plot(t, y[:, slv.get_var_idx(i_f)], label='i_f [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('f current [p.u.]')
axs[1].set_title('f current i_f')
axs[1].legend(loc='upper right')
# axs[1].set_ylim([-2, 2])
axs[1].set_ylim([-1.2, -1])
axs[1].grid(True)

axs[2].plot(t, y[:, slv.get_var_idx(Qe)], label='v_f [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('f voltage [p.u.]')
axs[2].set_title('f voltage v_f')
axs[2].legend(loc='upper right')
# axs[1].set_ylim([-2, 2])
axs[2].set_ylim([-0.2, 0.2])
axs[2].grid(True)


axs[3].plot(t, y[:, slv.get_var_idx(psi_d)], label='psi_d [p.u.]', color='b')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('d flux [p.u.]')
axs[3].set_title('d flux psi_d')
axs[3].legend(loc='upper right')
axs[3].set_ylim([-1.4, -1])
axs[3].grid(True)

axs[4].plot(t, y[:, slv.get_var_idx(i_d)], label='i_d [p.u.]', color='b')
axs[4].set_xlabel('Time [s]')
axs[4].set_ylabel('d current [p.u.]')
axs[4].set_title('d current i_d')
axs[4].legend(loc='upper right')
axs[4].set_ylim([0, 1])
axs[4].grid(True)

axs[5].plot(t, y[:, slv.get_var_idx(v_d)], label='v_d [p.u.]', color='b')
axs[5].set_xlabel('Time [s]')
axs[5].set_ylabel('d voltage [p.u.]')
axs[5].set_title('d voltage v_d')
axs[5].legend(loc='upper right')
axs[5].set_ylim([0.5, 1.5])
axs[5].grid(True)



plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

fig, axs = plt.subplots(2, 3, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, dx[:,0], label='d_psi_d [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('d flux derivate [p.u.]')
axs[0].set_title('d flux derivate d_psi_d')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-0.5,1])
axs[0].grid(True)


axs[1].plot(t, dx[:,2], label='d_psi_f [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('f flux derivate [p.u.]')
axs[1].set_title('f flux derivate d_psi_f')
axs[1].legend(loc='upper right')
# axs[1].set_ylim([-2, 2])
axs[1].set_ylim([-0.2, 0.2])
axs[1].grid(True)

axs[2].plot(t, dx[:,1], label='d_psi_q [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('q flux  derivate[p.u.]')
axs[2].set_title('q flux derivate d_psi_q')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-0.5,1])
axs[2].grid(True)

axs[3].plot(t, dx[:,5], label='d_w [p.u.]', color='b')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('omega derivate[p.u.]')
axs[3].set_title('omega derivate d_w')
axs[3].legend(loc='upper right')
axs[3].set_ylim([-5, 10])
axs[3].grid(True)

axs[4].plot(t, dx[:,4], label='d_theta [p.u.]', color='b')
axs[4].set_xlabel('Time [s]')
axs[4].set_ylabel('theta derivate[p.u.]')
axs[4].set_title('theta derivate d_theta')
axs[4].legend(loc='upper right')
axs[4].set_ylim([-5, 320])
axs[4].grid(True)

axs[5].plot(t, dx[:,6], label='d_et [p.u.]', color='b')
axs[5].set_xlabel('Time [s]')
axs[5].set_ylabel('et derivate[p.u.]')
axs[5].set_title('et derivate d_et')
axs[5].legend(loc='upper right')
axs[5].set_ylim([-5, 10])
axs[5].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

