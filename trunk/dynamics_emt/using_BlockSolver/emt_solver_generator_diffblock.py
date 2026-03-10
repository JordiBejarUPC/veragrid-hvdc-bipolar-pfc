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
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const
import VeraGridEngine.api as gce

from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver

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
# Pe0 = 0.9999999999999998
Pe0 = 0.0
Qe0 = 0.0
Pm0 = 0.9996666666666664

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
Rload = Var("Rload")
v_f0 = Var("v_f0")

v = Var("v") # the base voltage (rms voltage). we want the rms voltage to be fixed at 1p.u.

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
d_theta = Var.get_or_create('d_theta', base_var=theta)
d_psi_d = Var.get_or_create('d_psid', base_var=psi_d)
d_psi_f = Var.get_or_create('d_psif', base_var=psi_f)
d_psi_q = Var.get_or_create('d_psiq', base_var=psi_q)
d_psi_0 = Var.get_or_create('d_psi0', base_var=psi_0)



generator_block_1 = DiffBlock(
    state_eqs=[
        d_psi_d - (v_d - Ra * i_d - w * psi_q),
        d_psi_q - (v_q - Ra * i_q + w * psi_d),
        d_psi_f - (v_f - Rf * i_f),
        d_psi_0 - (v_0 - R0 * i_0),
        d_theta - (wb * w),
        d_w - ((T_m - T_e - D * (w - 1.0)) / (2 * H)),
    ],
    state_vars=[psi_q, psi_d, psi_f, psi_0, theta, w], #6
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

        T_m - (Tmref + Kp*(w - wref)), #Tm
        v_f - v_f0, #v_f
        Pm - (Pe - (3/2) * Ra * (i_d * i_d + i_q * i_q))
    ],
    algebraic_vars=[i_d, i_q, i_f, i_0, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, T_e, Pe, Qe, T_m, v_f, Pm],
    # init_eqs= {
    #     psi_d: psi_d - (La + Lmd) * i_d - Lmd * i_f,
    #     psi_f: psi_f - Lmd * i_d - (Lmd + Lf) * i_f,
    #     psi_q: psi_q - (La + Lmd) * i_q,
    #     psi_0: psi_0 - L0 * i_0,
    #     v_d: v_d - 2/3 * (cos(theta) * v_a + cos(theta - 2*np.pi/3) * v_b + cos(theta + 2*np.pi/3) * v_c),
    #     v_q: v_q - 2/3 * (sin(theta) * v_a + sin(theta - 2*np.pi/3) * v_b + sin(theta + 2*np.pi/3) * v_c),
    #     v_0: v_0 - 2/3 * (0.5 * v_a + 0.5 * v_b + 0.5 * v_c),
    #     i_a: i_a - (cos(theta) * i_d + sin(theta) * i_q + i_0),
    #     i_b: i_b - (cos(theta- 2*np.pi/3) * i_d + sin(theta - 2*np.pi/3) * i_q + i_0),
    #     i_c: i_c - (cos(theta + 2*np.pi/3) * i_d + sin(theta + 2*np.pi/3) * i_q + i_0),
    #     v_a: v_a - i_a * Rload,
    #     v_b: v_b - i_b * Rload,
    #     v_c: v_c - i_c * Rload,
    #     i_d: v_d - i_d * Ra - w * psi_q,
    #     i_q: v_q - i_q * Ra + w * psi_d,
    #     i_f: v_f - i_f * Rf,
    #     i_0: v_0 - i_0 * R0,
    #     T_e: T_e + (3/2)*(psi_d * i_q - psi_q * i_d),
    #     v_f: v - (1/np.sqrt(3))*sqrt(v_a*v_a+v_b*v_b+v_c*v_c),
    #     Pe: Pe - (i_a * v_a + i_b * v_b + i_c * v_c),
    #     Qe: Qe - (1/np.sqrt(3))*((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b),
    #     T_m: T_m - Tmref,
    #     Pm: Pm - T_e * w,
    # }
    init_eqs= {
            w: Const(1.0),
            # theta: Const(1.0551043059609357),
            theta: Const(0.0),
            T_m: Tmref,

            v_a: Const(0.6974010218376268),
            v_b: Const(-1.4141693565707523),
            v_c: Const(0.7167683347331255),
            # v_a: Const(1.0),
            # v_b:  Const(-0.5),
            # v_c: Const(0.5),


            v_d: 2/3 * (cos(theta) * v_a + cos(theta - 2*np.pi/3) * v_b + cos(theta + 2*np.pi/3) * v_c),
            v_q: 2/3 * (sin(theta) * v_a + sin(theta - 2*np.pi/3) * v_b + sin(theta + 2*np.pi/3) * v_c),
            v_0: 2/3 * (0.5 * v_a + 0.5 * v_b + 0.5 * v_c),
            # v_f: Const(-0.017823471915955656),

            i_a: v_a/Rload,
            i_b: v_b/Rload,
            i_c: v_c/Rload,

            i_d: 2/3 * (cos(theta) * i_a + cos(theta - 2*np.pi/3) * i_b + cos(theta + 2*np.pi/3) * i_c),
            i_q: 2/3 * (sin(theta) * i_a + sin(theta - 2*np.pi/3) * i_b + sin(theta + 2*np.pi/3) * i_c),
            i_0: 2/3 * (0.5 * i_a + 0.5 * i_b + 0.5 * i_c),

            psi_d: (i_q * Ra - v_q) / w,
            i_f: ((La + Lmd) * i_d - psi_d) / Lmd,
            v_f: i_f * Rf,

            # psi_d: (La + Lmd) * i_d - Lmd * i_f,
            psi_f: Lmd * i_d - (Lmd + Lf) * i_f,
            psi_q: (La + Lmd) * i_q,
            psi_0: L0 * i_0,

            # i_d: (v_d - w * psi_q)/Ra,
            # i_q: (v_q + w * psi_d)/Ra,
            # i_f: v_f/Rf,
            # i_0: v_0/R0,

            # i_a: (cos(theta) * i_d + sin(theta) * i_q + i_0),
            # i_b: (cos(theta- 2*np.pi/3) * i_d + sin(theta - 2*np.pi/3) * i_q + i_0),
            # i_c: (cos(theta + 2*np.pi/3) * i_d + sin(theta + 2*np.pi/3) * i_q + i_0),
            T_e: -(3/2)*(psi_d * i_q - psi_q * i_d),
            # v_f: v - (1/np.sqrt(3))*sqrt(v_a*v_a+v_b*v_b+v_c*v_c),

            Pe: (i_a * v_a + i_b * v_b + i_c * v_c),
            Qe: (1/np.sqrt(3))*((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b),
            Pm: T_e * w,
        }
)
generator_block_1.diff_vars = [d_psi_d, d_psi_q, d_psi_f, d_psi_0, d_theta, d_w]
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
                           Rload: Const(3.0),
                           v_f0: Const(-0.017823471915955656),
                           v: Const(1.0)}

gen1.rms_model.model = generator_block_1
# ----------------------------------------------------------------------------------------------------------------------
# Power flow
# ----------------------------------------------------------------------------------------------------------------------
res = gce.power_flow(grid)

print(f"Converged: {res.converged}")

options = RmsOptions(time_step = 5e-5,
                     simulation_time = 0.5,
                     tolerance = 1e-12,
                     integration_method = "implicit euler",
                     use_init_values = True)
drv = RmsSimulationDriver(grid, options, res)
drv.run()
#sim results
y = drv.results.values
t = drv.results.time_array
# stat_vars = drv.results.stat_vars
# algeb_vars = drv.results.algeb_vars
all_vars = drv.results.variable_array



#save results
# all_vars = stat_vars + algeb_vars
var_names = [str(var) + '_VeraGrid' for var in all_vars]
df_simulation_results = pd.DataFrame(data=y, columns=var_names)
df_simulation_results.insert(0, 'Time [s]', t)
df_simulation_results.to_csv('simulation_results.csv', index=False)
print(f"Simulation results saved to: simulation_results.csv")


fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, df_simulation_results['v_aGen1_VeraGrid'], label='v_a [pu]', color='b')
axs[0].plot(t, df_simulation_results['v_bGen1_VeraGrid'], label='v_b [pu]', color='r')
axs[0].plot(t, df_simulation_results['v_cGen1_VeraGrid'], label='v_c [pu]', color='g')
axs[0].set_title('Voltages abc')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Voltage [pu]')
axs[0].set_ylim([-3, 3]) #
axs[0].legend(loc='upper right')
axs[0].grid(True)

axs[2].plot(t, df_simulation_results['v_dGen1_VeraGrid'], label='v_d [pu]', color='b')
axs[2].plot(t, df_simulation_results['v_qGen1_VeraGrid'], label='v_q [pu]', color='r')
axs[2].plot(t, df_simulation_results['v_0Gen1_VeraGrid'], label='v_0 [pu]', color='g')
axs[2].set_title('Voltages dq0')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('Voltage [pu]')
axs[2].set_ylim([-3, 3]) #
axs[2].legend(loc='upper right')
axs[2].grid(True)

axs[1].plot(t, df_simulation_results['i_aGen1_VeraGrid'], label='i_a [pu]', color='b')
axs[1].plot(t, df_simulation_results['i_bGen1_VeraGrid'], label='i_b [pu]', color='r')
axs[1].plot(t, df_simulation_results['i_cGen1_VeraGrid'], label='i_c [pu]', color='g')
axs[1].set_title('Currents abc')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [pu]')
axs[1].set_ylim([-2, 2])
axs[1].legend(loc='upper right')
axs[1].grid(True)


axs[3].plot(t, df_simulation_results['i_dGen1_VeraGrid'], label='i_d [pu]', color='b')
axs[3].plot(t, df_simulation_results['i_qGen1_VeraGrid'], label='i_q [pu]', color='r')
axs[3].plot(t, df_simulation_results['i_0Gen1_VeraGrid'], label='i_0 [pu]', color='g')
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

axs[0].plot(t, df_simulation_results['thetaGen1_VeraGrid'], label='theta [rad]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Angle [rad]')
axs[0].set_title('Theta')
axs[0].legend(loc='upper right')
axs[0].grid(True)


axs[1].plot(t, df_simulation_results['wGen1_VeraGrid'], label='omega [p.u.]', color='b')
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
plt.plot(t, df_simulation_results['TeGen1_VeraGrid'], label='Electrical torque [p.u.]', color='b')
plt.plot(t, df_simulation_results['TmGen1_VeraGrid'], label='Mechanical torque [p.u.]', color='r')
plt.xlabel('Time [s]')
plt.ylabel('Torque [p.u.]')
plt.title("Torques - Synchronous generator model")
plt.legend(loc='upper right')
plt.ylim([-3, 3])
plt.grid(True)
plt.show()

fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, df_simulation_results['psi_fGen1_VeraGrid'], label='psi_f [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Field flux [p.u.]')
axs[0].set_title('Field flux psi_f')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)

axs[1].plot(t, df_simulation_results['i_fGen1_VeraGrid'], label='i_f [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('Field current i_f')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-2, 2])
axs[1].grid(True)

axs[2].plot(t, df_simulation_results['v_fGen1_VeraGrid'], label='v_f [p.u.]', color='b')
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

axs[0].plot(t, df_simulation_results['psi_dGen1_VeraGrid'], label='psi_d [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('flux [p.u.]')
axs[0].set_title('flux psi_d')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)


axs[1].plot(t, df_simulation_results['i_dGen1_VeraGrid'], label='i_d [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('current i_d')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-2,2])
axs[1].grid(True)

axs[2].plot(t, df_simulation_results['psi_qGen1_VeraGrid'], label='psi_q [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('flux [p.u.]')
axs[2].set_title('flux psi_q')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-2, 2])
axs[2].grid(True)

axs[3].plot(t, df_simulation_results['i_dGen1_VeraGrid'], label='i_q [p.u.]', color='b')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('Current [p.u.]')
axs[3].set_title('current i_q')
axs[3].legend(loc='upper right')
axs[3].set_ylim([-2, 2])
axs[3].grid(True)

axs[4].plot(t, df_simulation_results['psi_0Gen1_VeraGrid'], label='psi_0 [p.u.]', color='b')
axs[4].set_xlabel('Time [s]')
axs[4].set_ylabel('flux [p.u.]')
axs[4].set_title('flux psi_0')
axs[4].legend(loc='upper right')
axs[4].set_ylim([-2, 2])
axs[4].grid(True)

axs[5].plot(t, df_simulation_results['i_0Gen1_VeraGrid'], label='i_0 [p.u.]', color='b')
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

axs[0].plot(t, df_simulation_results['PeGen1_VeraGrid'], label='P_e [p.u.]', color='b')
axs[0].plot(t, df_simulation_results['PmGen1_VeraGrid'], label='P_m [p.u.]', color='r')
# axs[0].plot(t, Pm, label='P_m [p.u.]', color='r')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Active power [p.u.]')
axs[0].set_title('Active power P_e')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-1,5])
axs[0].grid(True)


axs[1].plot(t,df_simulation_results['QeGen1_VeraGrid'], label='Q_e [p.u.]', color='b')
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