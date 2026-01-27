# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import matplotlib.pyplot as plt



def abc_to_dq0(theta, vec):
    return 2 / 3 * np.array([
        [np.cos(theta), np.cos(theta - 2 * np.pi / 3), np.cos(theta + 2 * np.pi / 3)],
        [np.sin(theta), np.sin(theta - 2 * np.pi / 3), np.sin(theta + 2 * np.pi / 3)],
        [1/2, 1/2, 1/2]
    ]) @ vec

def dq0_to_abc(theta, vec):
    return np.array([
        [np.cos(theta), np.sin(theta), 1],
        [np.cos(theta - 2 * np.pi / 3), np.sin(theta - 2 * np.pi / 3), 1],
        [np.cos(theta + 2 * np.pi / 3), np.sin(theta + 2 * np.pi / 3), 1]
    ]) @ vec

# simulation parameters
tmax = 10  # s
dt = 5e-6  # s
n_steps = int(tmax / dt)
t = np.linspace(0, tmax, n_steps)

# Generator parameters
fn = 50  # Hz
wb = 2* np.pi * fn

Rload = 3.0  # p.u.
# Rload = 3.2  # p.u.

La = 0.15  # p.u.
# Lmd =  1.55  # p.u.
# Lmq =  1.55  # p.u.
Lmd =  0.9  # p.u.
Lmq =  0.9  # p.u.
Lf = 0.10  # p.u.
Ra = 0.001  # p.u.
Rf = 0.017  # p.u.
L0 = 1.7 # p.u.
R0 = 0.001  # p.u.
Ldpp = 0.185 # p.u.
Lqpp = 0.185 # p.u.

L1d = 1.5 #p.u.
L1q = 1.5 #p.u.
R1d = 1.7 #p.u.
R1q = 1.7 #p.u.

# D = 50 # p.u.
# H = 5  # p.u.
D = 8  # p.u.
H = 4  # p.u.
print("D = ", D)
print("H = ", H)

Tm0 = 1.0  # p.u.
w0 = 1.0 #p.u.

# generator conductance matrix
Geq_d = 1/(Ra + (2*Ldpp)/(wb*dt)) #pu ojo la omega base per transformar dt a pu!!
Geq_q = 1/(Ra + (2*Lqpp)/(wb*dt)) #pu
Geq_0 = 1/(R0 + (2*Lqpp)/(wb*dt)) #pu
Geq_dq0 = np.array([[Geq_d, 0, 0],[0, Geq_q, 0], [0, 0, Geq_0]]) #pu
print("Geq = ", Geq_dq0)

# inductance matrices
L_daxis= np.array([ [La + Lmd, Lmd, Lmd],
                    [Lmd, Lmd + Lf, Lmd],
                    [Lmd, Lmd, Lmd+L1d]])
# L_qaxis  = La + Lmq
L_qaxis  = np.array([ [La + Lmq, Lmq],
                    [Lmq, Lmq + L1q]])
L_0axis  = 1.7
L_d_inv = np.linalg.inv(L_daxis)
L_q_inv = np.linalg.inv(L_qaxis)

# initialize vectors
v_a = np.zeros_like(t)
v_b = np.zeros_like(t)
v_c = np.zeros_like(t)
i_a = np.zeros_like(t)
i_b = np.zeros_like(t)
i_c = np.zeros_like(t)
i_d = np.zeros_like(t)
i_q = np.zeros_like(t)
i_0 = np.zeros_like(t)
i_f = np.zeros_like(t)
v_f = np.zeros_like(t)
psi_d = np.zeros_like(t)
psi_q = np.zeros_like(t)
psi_0 = np.zeros_like(t)
psi_f = np.zeros_like(t)
v_d = np.zeros_like(t)
v_q = np.zeros_like(t)
v_0 = np.zeros_like(t)
w = np.zeros_like(t)
theta = np.zeros_like(t)
delta = np.zeros_like(t)
Te = np.zeros_like(t)
Tm  = np.zeros_like(t)
Pm  = np.zeros_like(t)
Pe  = np.zeros_like(t)
Qe  = np.zeros_like(t)

i_hist_d  = np.zeros_like(t)
i_hist_q  = np.zeros_like(t)
i_hist_0  = np.zeros_like(t)
i_hist_a  = np.zeros_like(t)
i_hist_b  = np.zeros_like(t)
i_hist_c  = np.zeros_like(t)

d_psi_d  = np.zeros_like(t)
d_psi_q  = np.zeros_like(t)
d_psi_f  = np.zeros_like(t)
d_psi_0  = np.zeros_like(t)
d_w = np.zeros_like(t)
d_theta  = np.zeros_like(t)

d_psi_1d = np.zeros_like(t)
d_psi_1q = np.zeros_like(t)
psi_1d = np.zeros_like(t)
psi_1q = np.zeros_like(t)
i_1d = np.zeros_like(t)
i_1q = np.zeros_like(t)

# initialize variables
w[0] = w0
psi_d[0] = -1.3343237871635951
psi_1d[0] = -1.3576900283368245
psi_q[0] = 0.4671690485234327
psi_1q[0] = 0.4004306130200852
psi_f[0] = -1.5241219700452913
psi_0[0] = -2.3513417220457447e-18
i_f[0] = -1.6643194170846676
v_f[0] = -0.028293430090439352
v_a[0] = 0.46732482346458765
v_b[0] = -1.3896060228268592
v_c[0] = 0.9222811993622715
v_d[0] = 0.4673248234645876
v_q[0] = 1.3347687100669507
v_0[0] = -1.6795298014614602e-20
i_a[0] = 0.15577494115486257
i_b[0] = -0.463202007608953
i_c[0] = 0.3074270664540905
i_d[0] = 0.15577494115486257
i_1d[0] = 0.0
i_q[0] = 0.4449229033556502
i_1q[0] = 0.0
i_0[0] = -1.6795298014612465e-17
Te[0] = 0.9996666666666665
Tm[0] = 0.9996666666666665
theta[0] = 1.2340175418656953
Pe[0] = 0.9999999999999999
Qe[0] = 3.2049378106392736e-17
Pm[0] = 0.9996666666666665

delta[0] = theta[0]


d_w0 = (Tm[0] - Te[0] - D * (w[0] - 1.0)) / (2 * H)
print(f"dw/dt at t=0 = {d_w0} --> check steady state initialization")

#controller
# Kp_w = 5
# Kp_p = 5
wref = np.ones_like(t)
Pref = np.ones_like(t)

Tm_min = 0.5
Tm_max = 1.5
Delta_w_max = 0.05  # 5% freq change for full governor stroke
Delta_Tm_range = 0.5 * (Tm_max - Tm_min)
Kp_w = Delta_Tm_range / Delta_w_max

alpha   = 0.3      # 30% of torque range used by power loop
DeltaP_ss = 0.05   # at 0.05 pu power error, we already use that 30%
Delta_Tm_P = alpha * (Tm_max - Tm_min)
Kp_p = Delta_Tm_P / DeltaP_ss
# Kp_p = 1.0

# print("Kp_w = ",Kp_w) #6
# print("Kp_p = ",Kp_p) #3

Kp = 2.0

Kp_w = 2
Kp_p = 0.1
Tmref = Tm[0]  # p.u.


# ---- main loop ----
print("Dynamic simulation starting...")
for step in range(1, n_steps):
    v_f[step] = v_f[0]

    # apply event
    # if step == n_steps // 3: #add event at t/3
    #     Tmref = 0.7498125
    #     # Pref[step] = 1.001
    #     Rload = 4
    # # #     # Tm0 = 1.001
    # #     wref[step] = 1.001
    #     v_f[step] = -0.02761147660444435 # correct vf value from  N-R since no AVR.
    # else:
    #     Tmref = Tm[0]
    #     Rload = 3.0
    #     v_f[step] = v_f[0]

    # Fix/find v_f and Tm to (false AVR and governor)

    # Tm[step] = Tm[0]

    # omega ref controller
    Tm_w = Kp_w * ( wref[step] - w[step - 1] )
    # power ref controller
    # Tm_p = Kp_p * ( Pref[step] - Pm[step - 1] )
    Tm_p = 0.0
    #sum
    Tm[step] = Tmref + Tm_p + Tm_w
    # Tm_raw = Tm0 + Tm_p + Tm_w
    # saturation
    # Tm[step] = np.clip(Tm_raw, Tm_min, Tm_max)

    # Tm[step] = Tm0 + Kp*(wref[step] - w[step - 1])
    # Tm[step] = Tm0 + Kp * (Pref[step] - Pe[step - 1])
    # print('Pref= ', Pref)
    # print('Pe[step - 1]= ', Pe[step - 1])


    # Find dpsi/dt using previous state solution
    d_psi_d[step] = v_d[step - 1] - i_d[step - 1] * Ra - w[step - 1] * psi_q[step - 1]
    d_psi_f[step] = v_f[step - 1] - i_f[step - 1] * Rf
    d_psi_1d[step] = i_1d[step - 1] * R1d
    d_psi_q[step] = v_q[step - 1] - i_q[step - 1] * Ra + w[step - 1] * psi_d[step - 1]
    d_psi_1q[step] = i_1q[step - 1] * R1q
    d_psi_0[step] = v_0[step - 1] - i_0[step - 1] * R0

    # Find new psi using trapezoidal integration
    psi_d[step] = (d_psi_d[step - 1] + d_psi_d[step]) * dt / 2 + psi_d[step - 1]
    psi_f[step] = (d_psi_f[step - 1] + d_psi_f[step]) * dt / 2 + psi_f[step - 1]
    psi_1d[step] = (d_psi_1d[step - 1] + d_psi_1d[step]) * dt / 2 + psi_1d[step - 1]
    psi_q[step] = (d_psi_q[step - 1] + d_psi_q[step]) * dt / 2 + psi_q[step - 1]
    psi_1q[step] = (d_psi_1q[step - 1] + d_psi_1q[step]) * dt / 2 + psi_1q[step - 1]
    psi_0[step] = (d_psi_0[step - 1] + d_psi_0[step]) * dt / 2 + psi_0[step - 1]

    # Find idq0 using the inductance matrices psi = L·i
    psi_df1d = np.array([[psi_d[step]], [psi_f[step]], [psi_1d[step]]])
    i_df1d = L_d_inv @ psi_df1d
    i_d[step] = i_df1d[0, 0]
    i_f[step] = i_df1d[1, 0]
    i_1d[step] = i_df1d[2, 0]
    psi_q1q = np.array([[psi_q[step]],[psi_1q[step]]])
    i_q1q = L_q_inv @ psi_q1q
    i_q[step] = i_q1q[0, 0]
    i_1q[step] = i_q1q[1, 0]
    i_0[step] = psi_0[step] / L_0axis

    # Find new Telec
    # Te[step] = (-(3 / 2) * (psi_d[step] * i_q[step] - psi_q[step] * i_d[step]) + (3/2)*Ra*(i_d[step] * i_d[step] + i_q[step] * i_q[step])/w[step-1])
    Te[step] = -(3 / 2) * (psi_d[step] * i_q[step] - psi_q[step] * i_d[step])
    # Te[step] = (3 / 2) * (psi_d[step] * i_q[step] - psi_q[step] * i_d[step])

    # Find omega and theta from the swing equations

    # find d_w
    d_w[step] = (Tm[step] - Te[step] - D * (w[step-1] - wref[step])) / (2 * H)
    # find w by trapezoidal integration
    w[step] = w[step - 1] + dt * (d_w[step - 1] + d_w[step]) / 2

    # find d_theta
    d_theta[step] = wb * w[step]
    # find theta by trapezoidal integration
    theta[step] = theta[step - 1] + dt * (d_theta[step-1] + d_theta[step]) / 2
    # monitor angle deviation
    delta[step] = theta[step] - wb * t[step]

    #define the mechanical torque
    # Pm[step] = Tm[step] * w[step]

    # find history currents i_hist_dq0
    # i_hist_d[step] = Geq_d * v_d[step - 1]
    # i_hist_q[step] = Geq_q * v_q[step - 1]
    # i_hist_0[step] = Geq_0 * v_0[step - 1]

    # transform idq0, Geq_dq0 and i_hist_dq0 to abc domain
    i_dq0 = np.array([[i_d[step]], [i_q[step]], [i_0[step]]])
    # i_hist_dq0 = np.array([[i_hist_d[step]], [i_hist_q[step]], [i_hist_0[step]]])

    # i_hist_abc = dq0_to_abc(theta[step], i_hist_dq0)
    i_abc = dq0_to_abc(theta[step], i_dq0)

    i_a[step], i_b[step], i_c[step] = i_abc.flatten()
    # i_hist_a[step], i_hist_b[step], i_hist_c[step] = i_hist_abc.flatten()

    # T_inv = np.array([
    #     [np.cos(theta[step]), np.sin(theta[step]), 1],
    #     [np.cos(theta[step] - 2 * np.pi / 3), np.sin(theta[step] - 2 * np.pi / 3), 1],
    #     [np.cos(theta[step] + 2 * np.pi / 3), np.sin(theta[step] + 2 * np.pi / 3), 1]])
    # T = (2 / 3) * np.array([
    #     [np.cos(theta[step]), np.cos(theta[step] - 2 * np.pi / 3), np.cos(theta[step] + 2 * np.pi / 3)],
    #     [np.sin(theta[step]), np.sin(theta[step] - 2 * np.pi / 3), np.sin(theta[step] + 2 * np.pi / 3)],
    #     [0.5, 0.5, 0.5]])
    # Geq_abc = T_inv @ Geq_dq0 @ T

    # Solve network equation
    G = np.zeros((3, 3))
    # G[0, 0] += Geq_abc[0, 0]
    # G[0, 1] += Geq_abc[0, 1]
    # G[0, 2] += Geq_abc[0, 2]
    # G[1, 0] += Geq_abc[1, 0]
    # G[1, 1] += Geq_abc[1, 1]
    # G[1, 2] += Geq_abc[1, 2]
    # G[2, 0] += Geq_abc[2, 0]
    # G[2, 1] += Geq_abc[2, 1]
    # G[2, 2] += Geq_abc[2, 2]
    G[0, 0] += 1 / Rload
    G[1, 1] += 1 / Rload
    G[2, 2] += 1 / Rload

    Is = np.array([[i_a[step]], [i_b[step]], [i_c[step]]])
    # Ihist = np.array([[i_hist_a[step]], [i_hist_b[step]], [i_hist_c[step]]])
    # Itot = Is + Ihist
    Itot = Is
    v_sol = np.linalg.solve(G, Itot)
    v_a[step] = v_sol[0, 0]
    v_b[step] = v_sol[1, 0]
    v_c[step] = v_sol[2, 0]

    # transform vabc to dq0 domain
    v_dq0 = abc_to_dq0(theta[step], v_sol)
    v_d[step], v_q[step], v_0[step] = v_dq0.flatten()

    # calculate Pe and Qe
    Pe[step] = v_a[step] * i_a[step] + v_b[step] * i_b[step] + v_c[step] * i_c[step]
    Qe[step] = (1 / np.sqrt(3)) * (
                (v_a[step] - v_b[step]) * i_c[step] + (v_b[step] - v_c[step]) * i_a[step]
                + (v_c[step] - v_a[step]) * i_b[step])
    Pm[step] = Pe[step] -  (3/2)*Ra*(i_d[step] * i_d[step] + i_q[step] * i_q[step])

print("finished")
# --- plot results ---



# torques: mechanical and electrical
plt.figure(figsize=(10, 6))
plt.plot(t, Pm, label='Pm [p.u.]', color='r')
plt.plot(t, Pe, label='Pe [p.u.]', color='b')
plt.plot(t, Pref, label='Pref [p.u.]', color='g')
plt.xlabel('Time [s]')
plt.ylabel('Power [p.u.]')
plt.title("Powers - Synchronous generator model")
plt.legend(loc='upper right')
plt.ylim([-3, 5])
plt.grid(True)
plt.show()

# voltages and currents abc, dq0
fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, v_a, label='v_a [pu]', color='b')
axs[0].plot(t, v_b, label='v_b [pu]', color='r')
axs[0].plot(t, v_c, label='v_c [pu]', color='g')
axs[0].set_title('Voltages abc')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Voltage [pu]')
axs[0].set_ylim([-3, 3])
axs[0].legend(loc='upper right')
axs[0].grid(True)

axs[2].plot(t, v_d, label='v_d [pu]', color='b')
axs[2].plot(t, v_q, label='v_q [pu]', color='r')
axs[2].plot(t, v_0, label='v_0 [pu]', color='g')
# axs[2].plot(t * 1e3, v_0, label='v_0 [pu]', color='g')
axs[2].set_title('Voltages dq0')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('Voltage [pu]')
axs[2].set_ylim([-3, 3])
axs[2].legend(loc='upper right')
axs[2].grid(True)

axs[1].plot(t, i_a, label='i_a [pu]', color='b')
axs[1].plot(t, i_b, label='i_b [pu]', color='r')
axs[1].plot(t, i_c, label='i_c [pu]', color='g')
axs[1].set_title('Currents abc')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [pu]')
axs[1].set_ylim([-2, 2])
axs[1].legend(loc='upper right')
axs[1].grid(True)

axs[3].plot(t, i_d, label='i_d [pu]', color='b')
axs[3].plot(t, i_q, label='i_q [pu]', color='r')
axs[3].plot(t, i_0, label='i_0 [pu]', color='g')
axs[3].set_title('Currents dq0')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('Current [pu]')
axs[3].legend(loc='upper left')
axs[3].set_ylim([-2, 2])
axs[3].grid(True)

plt.suptitle('Synchronous Generator – Voltages and Currents', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

# theta, delta and omega
fig, axs = plt.subplots(1, 3, figsize=(18, 8))
axs = axs.flatten()  # per accedir fàcilment a cada subplot com un vector

axs[0].plot(t, theta, label='theta [rad]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Angle [rad]')
axs[0].set_title('Theta')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-100, 100])
axs[0].grid(True)

axs[1].plot(t, delta, label='delta [p.u.]', color='r')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('angle [rad]')
axs[1].set_title('Delta')
axs[2].set_ylim([-2, 3])
axs[1].legend(loc='upper right')
axs[1].grid(True)

axs[2].plot(t, wref, label='omega reference [p.u.]', color='r')
axs[2].plot(t, w, label='omega [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('Speed [p.u.]')
axs[2].set_title('Omega')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-2, 3])
axs[2].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])  # deixa espai per al títol global
plt.show()

# torques: mechanical and electrical
plt.figure(figsize=(10, 6))
plt.plot(t, Tm, label='Mechanical torque [p.u.]', color='r')
plt.plot(t, Te, label='Electrical torque [p.u.]', color='b')
plt.xlabel('Time [s]')
plt.ylabel('Torque [p.u.]')
plt.title("Torques - Synchronous generator model")
plt.legend(loc='upper right')
plt.ylim([-3, 5])
plt.grid(True)
plt.show()

# controler error
# fig, axs = plt.subplots(1, 2, figsize=(18, 8))
# axs = axs.flatten()  # per accedir fàcilment a cada subplot com un vector
#
# axs[0].plot(t, e, label='error [rad]', color='b')
# axs[0].set_xlabel('Time [s]')
# axs[0].set_ylabel('error')
# axs[0].set_title('error')
# axs[0].legend(loc='upper right')
# axs[0].set_ylim([-100, 100])
# axs[0].grid(True)
#
# axs[1].plot(t, et, label='et integral [p.u.]', color='r')
# axs[1].set_xlabel('Time [s]')
# axs[1].set_ylabel('int. error')
# axs[1].set_title('int error')
# axs[1].set_ylim([-100, 100])
# axs[1].legend(loc='upper right')
# axs[1].grid(True)
# plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
# plt.tight_layout(rect=[0, 0, 1, 0.96])  # deixa espai per al títol global
# plt.show()
#

# field variables: psi_f, v_f and i_f
fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, psi_f, label='psi_f [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Field flux [p.u.]')
axs[0].set_title('Field flux psi_f')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-4, 5])
axs[0].grid(True)

axs[1].plot(t, i_f, label='i_f [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('Field current i_f')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-6, 6])
axs[1].grid(True)

axs[2].plot(t, v_f, label='v_f [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('Field voltage [p.u.]')
axs[2].set_title('Field voltage v_f')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-5, 5])
axs[2].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

# d and q axis variables
fig, axs = plt.subplots(3, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, psi_d, label='psi_d [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('flux [p.u.]')
axs[0].set_title('flux psi_d')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)

axs[1].plot(t, i_d, label='i_d [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('current i_d')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-5,5])
axs[1].grid(True)

axs[2].plot(t, psi_q, label='psi_q [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('flux [p.u.]')
axs[2].set_title('flux psi_q')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-5, 5])
axs[2].grid(True)

axs[3].plot(t, i_q, label='i_q [p.u.]', color='b')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('Current [p.u.]')
axs[3].set_title('current i_q')
axs[3].legend(loc='upper right')
axs[3].set_ylim([-5, 5])
axs[3].grid(True)

axs[4].plot(t, psi_0, label='psi_0 [p.u.]', color='b')
axs[4].set_xlabel('Time [s]')
axs[4].set_ylabel('flux [p.u.]')
axs[4].set_title('flux psi_0')
axs[4].legend(loc='upper right')
axs[4].set_ylim([-5, 5])
axs[4].grid(True)

axs[5].plot(t, i_0, label='i_0 [p.u.]', color='b')
axs[5].set_xlabel('Time [s]')
axs[5].set_ylabel('Current [p.u.]')
axs[5].set_title('current i_0')
axs[5].legend(loc='upper right')
axs[5].set_ylim([-5, 5])
axs[5].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

fig, axs = plt.subplots(2, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, psi_1d, label='psi_1d [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('flux [p.u.]')
axs[0].set_title('flux psi_1d')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5, 5])
axs[0].grid(True)

axs[1].plot(t, i_1d, label='i_1d [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Current [p.u.]')
axs[1].set_title('current i_1d')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-5,5])
axs[1].grid(True)

axs[2].plot(t, psi_1q, label='psi_1q [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('flux [p.u.]')
axs[2].set_title('flux psi_1q')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-5, 5])
axs[2].grid(True)

axs[3].plot(t, i_1q, label='i_1q [p.u.]', color='b')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('Current [p.u.]')
axs[3].set_title('current i_1q')
axs[3].legend(loc='upper right')
axs[3].set_ylim([-5, 5])
axs[3].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

# derivatives (that must be 0 in steady state)
fig, axs = plt.subplots(3, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, d_psi_d, label='d_psi_d [p.u.]', color='b')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('d flux derivate [p.u.]')
axs[0].set_title('d flux derivate d_psi_d')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5,5])
axs[0].grid(True)

axs[1].plot(t, d_psi_f, label='d_psi_f [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('f flux derivate [p.u.]')
axs[1].set_title('f flux derivate d_psi_f')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-5, 5])
axs[1].grid(True)

axs[2].plot(t, d_psi_q, label='d_psi_q [p.u.]', color='b')
axs[2].set_xlabel('Time [s]')
axs[2].set_ylabel('q flux  derivate[p.u.]')
axs[2].set_title('q flux derivate d_psi_q')
axs[2].legend(loc='upper right')
axs[2].set_ylim([-5 ,5])
axs[2].grid(True)

axs[3].plot(t, d_w, label='d_w [p.u.]', color='b')
axs[3].set_xlabel('Time [s]')
axs[3].set_ylabel('omega derivate[p.u.]')
axs[3].set_title('omega derivate d_w')
axs[3].legend(loc='upper right')
axs[3].set_ylim([-5, 5])
axs[3].grid(True)

axs[4].plot(t, d_psi_1d, label='d_psi_1d [p.u.]', color='b')
axs[4].set_xlabel('Time [s]')
axs[4].set_ylabel('1d flux  derivate[p.u.]')
axs[4].set_title('1d flux derivate d_psi_1d')
axs[4].legend(loc='upper right')
axs[4].set_ylim([-5 ,5])
axs[4].grid(True)

axs[5].plot(t, d_psi_1q, label='d_psi_1q [p.u.]', color='b')
axs[5].set_xlabel('Time [s]')
axs[5].set_ylabel('1q flux derivate[p.u.]')
axs[5].set_title('1q flux derivate d_psi_1q')
axs[5].legend(loc='upper right')
axs[5].set_ylim([-5, 5])
axs[5].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

# Electric and mechanical powers: Pm, Pe and Qe
fig, axs = plt.subplots(1, 2, figsize=(12, 8))
axs = axs.flatten()

axs[0].plot(t, Pe, label='Pe [p.u.]', color='b')
axs[0].plot(t, Pm, label='Pm [p.u.]', color='r')
axs[0].set_xlabel('Time [s]')
axs[0].set_ylabel('Active power [p.u.]')
axs[0].set_title('Active power Pe and Pm')
axs[0].legend(loc='upper right')
axs[0].set_ylim([-5,10])
axs[0].grid(True)

axs[1].plot(t, Qe, label='Q_e [p.u.]', color='b')
axs[1].set_xlabel('Time [s]')
axs[1].set_ylabel('Reactive power [p.u.]')
axs[1].set_title('Reactive power Q_e')
axs[1].legend(loc='upper right')
axs[1].set_ylim([-5, 5])
axs[1].grid(True)

plt.suptitle('Synchronous Generator Model', fontsize=14, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()





