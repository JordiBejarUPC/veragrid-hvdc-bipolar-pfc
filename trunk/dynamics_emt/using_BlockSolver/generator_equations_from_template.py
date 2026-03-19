# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from matplotlib import pyplot as plt
import pandas as pd

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Utils.Symbolic.symbolic import Const
import VeraGridEngine.api as gce
from VeraGridEngine.Templates.Emt.simple_generator_emt_template import get_simple_generator_emt_template
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver

pi = Const(np.pi)

# Build the system
grid = gce.MultiCircuit(Sbase = 160, fbase = 50)
# Bus
v_base = 15/ np.sqrt(3) #kV
bus1 = Bus(name="Bus1", Vnom= v_base)
grid.add_bus(bus1)

gen1 = Generator(name="Gen1", P=160, vset=1.0, Sbase = 160, Snom = 160)
gen1_template = get_simple_generator_emt_template()
gen1.emt_model = gen1_template.block

grid.add_generator(bus=bus1, api_obj=gen1)

load1 = Load(name="Load1", P=1, Q=0,
             Pl0 = 1, Ql0 = 0)
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
# theta0 = 1.0551043059609357
# Pe0 = 0.9999999999999998
# Qe0 = 0.0
# Pm0 = 0.9996666666666664
#
# wref = 1.0
#
# d_w0 = 0.0
# d_theta0 = 1.0
# d_psi_d0 = 0.0
# d_psi_f0 = 0.0
# d_psi_q0 = 0.0
# d_psi_00 = 0.0
#
options = RmsOptions(time_step = 5e-6,
                     simulation_time = 3,
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

axs[0].plot(t, df_simulation_results['v_a_VeraGrid'], label='v_a [pu]', color='b')
axs[0].plot(t, df_simulation_results['v_b_VeraGrid'], label='v_b [pu]', color='r')
axs[0].plot(t, df_simulation_results['v_c_VeraGrid'], label='v_c [pu]', color='g')
axs[0].set_title('Voltages abc')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Voltage [pu]')
axs[0].set_ylim([-3, 3]) #
axs[0].legend(loc='upper right')
axs[0].grid(True)

axs[2].plot(t, df_simulation_results['v_d_VeraGrid'], label='v_d [pu]', color='b')
axs[2].plot(t, df_simulation_results['v_q_VeraGrid'], label='v_q [pu]', color='r')
axs[2].plot(t, df_simulation_results['v_0_VeraGrid'], label='v_0 [pu]', color='g')
axs[2].set_title('Voltages dq0')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('Voltage [pu]')
axs[2].set_ylim([-3, 3]) #
axs[2].legend(loc='upper right')
axs[2].grid(True)

axs[1].plot(t, df_simulation_results['i_a_VeraGrid'], label='i_a [pu]', color='b')
axs[1].plot(t, df_simulation_results['i_b_VeraGrid'], label='i_b [pu]', color='r')
axs[1].plot(t, df_simulation_results['i_c_VeraGrid'], label='i_c [pu]', color='g')
axs[1].set_title('Currents abc')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [pu]')
axs[1].set_ylim([-2, 2])
axs[1].legend(loc='upper right')
axs[1].grid(True)


axs[3].plot(t, df_simulation_results['i_d_VeraGrid'], label='i_d [pu]', color='b')
axs[3].plot(t, df_simulation_results['i_q_VeraGrid'], label='i_q [pu]', color='r')
axs[3].plot(t, df_simulation_results['i_0_VeraGrid'], label='i_0 [pu]', color='g')
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

axs[0].plot(t, df_simulation_results['theta_VeraGrid'], label='theta [rad]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Angle [rad]')
axs[0].set_title('Theta')
axs[0].legend(loc='upper right')
axs[0].grid(True)


axs[1].plot(t, df_simulation_results['omega_VeraGrid'], label='omega [p.u.]', color='b')
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
plt.plot(t, df_simulation_results['Te_VeraGrid'], label='Electrical torque [p.u.]', color='b')
plt.plot(t, df_simulation_results['Tm_VeraGrid'], label='Mechanical torque [p.u.]', color='r')
plt.xlabel('Time [s]')
plt.ylabel('Torque [p.u.]')
plt.title("Torques - Synchronous generator model")
plt.legend(loc='upper right')
plt.ylim([-3, 3])
plt.grid(True)
plt.show()

fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, df_simulation_results['psi_f_VeraGrid'], label='psi_f [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Field flux [p.u.]')
axs[0].set_title('Field flux psi_f')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)

axs[1].plot(t, df_simulation_results['i_f_VeraGrid'], label='i_f [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('Field current i_f')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-2, 2])
axs[1].grid(True)

axs[2].plot(t, df_simulation_results['v_f_VeraGrid'], label='v_f [p.u.]', color='b')
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

axs[0].plot(t, df_simulation_results['psi_d_VeraGrid'], label='psi_d [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('flux [p.u.]')
axs[0].set_title('flux psi_d')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)


axs[1].plot(t, df_simulation_results['i_d_VeraGrid'], label='i_d [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('current i_d')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-2,2])
axs[1].grid(True)

axs[2].plot(t, df_simulation_results['psi_q_VeraGrid'], label='psi_q [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('flux [p.u.]')
axs[2].set_title('flux psi_q')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-2, 2])
axs[2].grid(True)

axs[3].plot(t, df_simulation_results['i_d_VeraGrid'], label='i_q [p.u.]', color='b')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('Current [p.u.]')
axs[3].set_title('current i_q')
axs[3].legend(loc='upper right')
axs[3].set_ylim([-2, 2])
axs[3].grid(True)

axs[4].plot(t, df_simulation_results['psi_0_VeraGrid'], label='psi_0 [p.u.]', color='b')
axs[4].set_xlabel('Time [s]')
axs[4].set_ylabel('flux [p.u.]')
axs[4].set_title('flux psi_0')
axs[4].legend(loc='upper right')
axs[4].set_ylim([-2, 2])
axs[4].grid(True)

axs[5].plot(t, df_simulation_results['i_0_VeraGrid'], label='i_0 [p.u.]', color='b')
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

axs[0].plot(t, df_simulation_results['Pe_VeraGrid'], label='P_e [p.u.]', color='b')
axs[0].plot(t, df_simulation_results['Pm_VeraGrid'], label='P_m [p.u.]', color='r')
# axs[0].plot(t, Pm, label='P_m [p.u.]', color='r')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Active power [p.u.]')
axs[0].set_title('Active power P_e')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-1,5])
axs[0].grid(True)


axs[1].plot(t,df_simulation_results['Qe_VeraGrid'], label='Q_e [p.u.]', color='b')
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