import numpy as np

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

# def abc_to_dq(theta, vec):
#     return 2 / 3 * np.array([
#         [np.cos(theta), np.cos(theta - 2 * np.pi / 3), np.cos(theta + 2 * np.pi / 3)],
#         [np.sin(theta), np.sin(theta - 2 * np.pi / 3), np.sin(theta + 2 * np.pi / 3)]
#     ]) @ vec
#
# def dq_to_abc(theta, vec):
#     return np.array([
#         [np.cos(theta), np.sin(theta)],
#         [np.cos(theta - 2 * np.pi / 3), np.sin(theta - 2 * np.pi / 3)],
#         [np.cos(theta + 2 * np.pi / 3), np.sin(theta + 2 * np.pi / 3)]
#     ]) @ vec

# Parameters
fn = 50  # Hz
rload = 3.0# p.u.
# rload = 1 / 0.3833 # p.u.

Ldpp = 0.245
h = 5e-06
r_eq_gen = h / (2 * Ldpp)

rload = rload + r_eq_gen

v = 1.0 # vrms p.u.

La = 0.15  # p.u.
Lmd =  1.55  # p.u.
Lmq =  1.55  # p.u.
Lf = 0.10  # p.u.
Ra = 0.001  # p.u.
Rf = 0.017  # p.u.

L0 = 1.7 # p.u.
R0 = 0.001  # p.u.

D = 2  # p.u.
H = 5  # p.u.
Tm = 1.00  # p.u.

tmax = 10  # s
dt = 1e-5  # s
n_steps = int(tmax / dt)
t = np.linspace(0, tmax, n_steps)

# Init vectors
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
vf = np.zeros_like(t)
psi_d = np.zeros_like(t)
psi_q = np.zeros_like(t)
psi_0 = np.zeros_like(t)
psi_f = np.zeros_like(t)
v_d = np.zeros_like(t)
v_q = np.zeros_like(t)
v_0 = np.zeros_like(t)
w = np.zeros_like(t)
theta = np.zeros_like(t)
Te = np.zeros_like(t)

sf = np.zeros_like(t)

# Rotation matrices

# Initial conditions
w[0] = 1.0
theta[0] = 0.0 #30.4 * 2*np.pi/360#0.0

# Realistic initial guesses based on physical relationships
# Start with field current
vf[0] = 1.0 #0.017
i_f[0] = vf[0] / Rf
sf[0] = 1.0

Vpeak = np.sqrt(2)
v_a[0] = Vpeak * np.cos(0.0)
v_b[0] = Vpeak * np.cos(-2*np.pi/3)
v_c[0] = Vpeak * np.cos(+2*np.pi/3)

# Currents from load: i = v / rload
i_a[0] = v_a[0] / rload
i_b[0] = v_b[0] / rload
i_c[0] = v_c[0] / rload

# For balanced operation, start with q-axis voltage = 0.0 p.u. and d-axis = 1.0
# v_q[0] = 0.0
# v_d[0] = 1.0
# v_0[0] = 0.0  # Balanced system
# dq currents:
# i_q[0] = v_q[0] / rload
# i_d[0] = v_d[0] / rload
# i_0[0] = 0.00  # Balanced system
vdq0_v = abc_to_dq0(theta[0], np.array([v_a[0], v_b[0], v_c[0]]))
vdq0_i = abc_to_dq0(theta[0], np.array([i_a[0], i_b[0], i_c[0]]))

v_d[0], v_q[0], v_0[0] = vdq0_v
i_d[0], i_q[0], i_0[0] = vdq0_i

# Fluxes from inductance relationships
psi_q[0] = (La + Lmd) * i_q[0]
psi_d[0] = (La + Lmd) * i_d[0] + Lmd * i_f[0]
psi_f[0] = Lmd * i_d[0] + (Lmd + Lf) * i_f[0]
psi_0[0] = L0 * i_0[0]


# Electrical torque from flux
Te[0] =-(3/2)*(psi_d[0] * i_q[0] - psi_q[0] * i_d[0])

# Mechanical torque: Tm = Te + D*(w-1), with w=1, so Tm = Te
# Tm[0] = Te[0] + D * (w[0] - 1.0)

# Solve these equations to get the initial values for the missing variables
# double check the Te = (psid * iq - psiq * id) vs calculated with va, ia, etc.
"""
Set of equations:
0 = psi_d - (La + Lmd) * i_d - Lmd * i_f                                                        # 1
0 = psi_f - Lmd * i_d - (Lmd + Lf) * i_f                                                        # 2
0 = psi_q - (La + Lmd) * i_q                                                                    # 3
0 = psi_0 - L0 * i_0                                                                            # 4
0 = v_d - 2 / 3 * (cos(theta) * v_a + cos(theta - 2*pi/3) * v_b + cos(theta + 2*pi/3) * v_c)    # 5
0 = v_q - 2 / 3 * (sin(theta) * v_a + sin(theta - 2*pi/3) * v_b + sin(theta + 2*pi/3) * v_c)    # 6
0 = v_0 - 2 / 3 * (1/2 * v_a + 1/2 * v_b + 1/2 * v_c)                                           # 7
0 = i_a - (cos(theta) * i_d + sin(theta) * i_q + 1 * i_0)                                       # 8
0 = i_b - (cos(theta - 2*pi/3) * i_d + sin(theta - 2*pi/3) * i_q + 1 * i_0)                     # 9
0 = i_c - (cos(theta + 2*pi/3) * i_d + sin(theta + 2*pi/3) * i_q + 1 * i_0)                     # 10
0 = v_a - i_a * rload                                                                           # 11
0 = v_b - i_b * rload                                                                           # 12
0 = v_c - i_c * rload                                                                           # 13
0 = v_d - i_d * Ra - w * psi_q                                                                  # 14
0 = v_q - i_q * Ra + w * psi_d                                                                  # 15
0 = vf - i_f * Rf                                                                               # 16
0 = v_0 - i_0 * R0                                                                              # 17
# 0 = Tm - Te - D * (w - 1)                                                                     # 18
# 0 = Te - (va * ia + vb * ib + vc * ic) / w                                                    # 19
# 0 = Te + (3/2)*(psi_d * i_q - psi_q * i_d)                                                      # 19

x = [psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te] # 19 vars
"""

def f1(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return psi_d - (La + Lmd) * i_d - Lmd * i_f

def f2(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return psi_f - Lmd * i_d - (Lmd + Lf) * i_f

def f3(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return psi_q - (La + Lmd) * i_q

def f4(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return psi_0 - L0 * i_0

def f5(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v_d - 2/3 * (np.cos(theta[0]) * v_a + np.cos(theta[0] - 2*np.pi/3) * v_b + np.cos(theta[0] + 2*np.pi/3) * v_c)

def f6(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v_q - 2/3 * (np.sin(theta[0]) * v_a + np.sin(theta[0] - 2*np.pi/3) * v_b + np.sin(theta[0] + 2*np.pi/3) * v_c)

def f7(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v_0 - 2/3 * (0.5 * v_a + 0.5 * v_b + 0.5 * v_c)

def f8(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return i_a - (np.cos(theta[0]) * i_d + np.sin(theta[0]) * i_q + i_0)

def f9(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return i_b - (np.cos(theta[0] - 2*np.pi/3) * i_d + np.sin(theta[0] - 2*np.pi/3) * i_q + i_0)

def f10(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return i_c - (np.cos(theta[0] + 2*np.pi/3) * i_d + np.sin(theta[0] + 2*np.pi/3) * i_q + i_0)


def f11(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v_a - i_a * rload

def f12(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v_b - i_b * rload

def f13(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v_c - i_c * rload

def f14(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v_d - i_d * Ra - w[0] * psi_q

def f15(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v_q - i_q * Ra + w[0] * psi_d

def f16(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return vf - i_f * Rf

def f17(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v_0 - i_0 * R0

# def f20(x):
#     psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
#     return Tm - Te - D * (w[0] - 1)

# def f21(x):
#     psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
#     return Te - (v_a * i_a + v_b * i_b + v_c * i_c) / w[0]
#     return Te - ( ((v_a * i_a + v_b * i_b + v_c * i_c) / w[0]) -(3/2)*Ra*(i_d*i_d + i_q*i_q)  )

def f18(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return Te + (3/2)*(psi_d * i_q - psi_q * i_d)

def f19(x):
    psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x
    return v - (1/np.sqrt(3))*np.sqrt(v_a*v_a+v_b*v_b+v_c*v_c)

#
#
# def f1(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return psi_d - (La + Lmd) * i_d - Lmd * i_f
#
# def f2(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return psi_f - Lmd * i_d - (Lmd + Lf) * i_f
#
# def f3(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return psi_q - (La + Lmd) * i_q
#
# def f4(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return psi_0 - L0 * i_0
#
# def f5(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return v_d - 2/3 * (np.cos(theta) * v_a + np.cos(theta - 2*np.pi/3) * v_b + np.cos(theta + 2*np.pi/3) * v_c)
#
# def f6(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return v_q - 2/3 * (np.sin(theta) * v_a + np.sin(theta - 2*np.pi/3) * v_b + np.sin(theta + 2*np.pi/3) * v_c)
#
# def f7(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return v_0 - 2/3 * (0.5 * v_a + 0.5 * v_b + 0.5 * v_c)
#
# def f8(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return i_a - (np.cos(theta) * i_d + np.sin(theta) * i_q + i_0)
#
# def f9(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return i_b - (np.cos(theta - 2*np.pi/3) * i_d + np.sin(theta - 2*np.pi/3) * i_q + i_0)
#
# def f10(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return i_c - (np.cos(theta + 2*np.pi/3) * i_d + np.sin(theta + 2*np.pi/3) * i_q + i_0)
#
# # def f11(x):
# #     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
# #     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
# #     return v_a - i_a * rload
# #
# # def f12(x):
# #     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
# #     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
# #     return v_b - i_b * rload
# #
# # def f13(x):
# #     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
# #     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
# #     return v_c - i_c * rload
#
# def f11(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return 1.0 - (v_a * i_a + v_b * i_b + v_c * i_c )
#
# def f12(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return v_a * i_a - v_b * i_b
#
# def f13(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return v_b * i_b - v_c * i_c
#
# def f14(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return v_d - i_d * Ra - w[0] * psi_q
#
# def f15(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return v_q - i_q * Ra + w[0] * psi_d
#
# def f16(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     # return vf - i_f * Rf
#     return sf - i_f * Rf
#
# def f17(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return v_0 - i_0 * R0
#
# def f18(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return Te + (3/2)*(psi_d * i_q - psi_q * i_d)
#
# def f19(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return 3 - (v_a*v_a+v_b*v_b+v_c*v_c)
#
# def f20(x):
#     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
#     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
#     return 0.0 - (1/np.sqrt(3))*((v_a-v_b)*i_c + (v_b-v_c)*i_a + (v_c-v_a)*i_b)
#
# # def f21(x):
# #     # psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te , theta = x
# #     psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
# #     return 1.0 - Pe


    
def build_f(x):
    return np.array([f1(x), f2(x), f3(x), f4(x),
                  f5(x), f6(x), f7(x), f8(x),
                  f9(x), f10(x), f11(x), f12(x),
                  f13(x), f14(x), f15(x), f16(x),
                  f17(x), f18(x), f19(x)])


# NR to find initial values
max_iter = 100
x = np.array([psi_d[0], psi_f[0], psi_q[0], psi_0[0],
                  i_f[0], sf[0], v_a[0], v_b[0], v_c[0],
                  v_d[0], v_q[0], v_0[0],
                  i_a[0], i_b[0], i_c[0],
                  i_d[0], i_q[0], i_0[0], Te[0]])


for i in range(max_iter):
    f = build_f(x)

    # Solve - J Ax = f
    # Build J numerically
    delta = 1e-6
    nx = len(x)
    J = np.zeros((nx, nx), dtype=float)
    for j in range(nx):
        x1 = x.copy()
        x1[j] += delta
        fnew = build_f(x1)
        J[:, j] = (fnew - f) / delta

    Ax = np.linalg.solve(J, -f)
    x += Ax
    err = max(abs(f))
    err_dx = np.max(np.abs(Ax))

print(f'Final x: {x}')
print(f'Final error: {err}')
print(f'Final error dx: {err_dx}')


# psi_d, psi_f, psi_q, psi_0, i_f, sf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te, theta = x
psi_d, psi_f, psi_q, psi_0, i_f, vf, v_a, v_b, v_c, v_d, v_q, v_0, i_a, i_b, i_c, i_d, i_q, i_0, Te = x

Pe = v_a*i_a + v_b*i_b + v_c*i_c
Qe = (1/np.sqrt(3))*((v_a-v_b)*i_c + (v_b-v_c)*i_a + (v_c-v_a)*i_b)
# theta = np.arctan2(v_q, v_d)
print(f'psi_d[0] = {psi_d}')
print(f'psi_q[0] = {psi_q}')
print(f'psi_f[0] = {psi_f}')
print(f'psi_0[0] = {psi_0}')
print(f'i_f[0] = {i_f}')
# print(f'v_f[0] = {sf}')
print(f'v_f[0] = {vf}')
print(f'v_a[0] = {v_a}')
print(f'v_b[0] = {v_b}')
print(f'v_c[0] = {v_c}')
print(f'v_d[0] = {v_d}')
print(f'v_q[0] = {v_q}')
print(f'v_0[0] = {v_0}')
print(f'i_a[0] = {i_a}')
print(f'i_b[0] = {i_b}')
print(f'i_c[0] = {i_c}')
print(f'i_d[0] = {i_d}')
print(f'i_q[0] = {i_q}')
print(f'i_0[0] = {i_0}')
print(f'Te[0] = {Te}')
print(f'Tm[0] = {Te}')
print(f'theta[0] = {theta} ') #rad
print(f'Pe[0] = {Pe} ')
print(f'Qe[0] = {Qe} ')
print(f'Pm[0] = {Te*w[0]} ')

print('-----------------------------------')
print(f'w0 = {1.0}')
print(f'psi_d0 = {psi_d}')
print(f'psi_q0 = {psi_q}')
print(f'psi_f0 = {psi_f}')
print(f'psi_00 = {psi_0}')
print(f'i_f0 = {i_f}')
print(f'v_f00 = {sf*sf}')
print(f'v_a0 = {v_a}')
print(f'v_b0 = {v_b}')
print(f'v_c0 = {v_c}')
print(f'v_d0 = {v_d}')
print(f'v_q0 = {v_q}')
print(f'v_00 = {v_0}')
print(f'i_a0 = {i_a}')
print(f'i_b0 = {i_b}')
print(f'i_c0 = {i_c}')
print(f'i_d0 = {i_d}')
print(f'i_q0 = {i_q}')
print(f'i_00 = {i_0}')
print(f'T_e0 = {Te}')
print(f'T_m0 = {Te}')
print(f'theta0 = {theta} ') #rad
print(f'Pe0 = {Pe} ')
print(f'Qe0 = {Qe} ')
print(f'Pm0 = {Te*w[0]} ')
# print(f'Pm0 = {Tm*w[0]} ')

print('-----------------------------------')
pp = 1.0
# print(f'Te = {((v_a*i_a+v_b*i_b+v_c*i_c)-(3/2)*Ra*(i_d*i_d+i_q*i_q))/w[0]}p.u. (theoretical, from ((v_a*i_a+v_b*i_b+v_c*i_c)-(3/2)*Ra*(i_d*i_d+i_q*i_q))/w[0])')
# print(f'Te = {3/2*(psi_d * i_q - psi_q * i_d)}p.u. (from 3/2*(psi_d * i_q - psi_q * i_d))')

print(f'v_rms = {(1/np.sqrt(3))*np.sqrt(v_a*v_a+v_b*v_b+v_c*v_c)} p.u. (from np.sqrt(v_a*v_a+v_b*v_b+v_c*v_c)/sqrt(3))')
print(f'v_rms = {(1/np.sqrt(2))*np.sqrt(v_q*v_q+v_d*v_d)} p.u. (from (1/np.sqrt(2))*np.sqrt(v_q*v_q+v_d*v_d))')
print(f'i_rms = {(1/np.sqrt(3))*np.sqrt(i_a*i_a+i_b*i_b+i_c*i_c)} p.u. (from np.sqrt(i_a*i_a+i_b*i_b+i_c*i_c)/sqrt(3))')
print(f'i_rms = {(1/np.sqrt(2))*np.sqrt(i_q*i_q+i_d*i_d)} p.u. (from (1/np.sqrt(2))*np.sqrt(i_q*i_q+i_d*i_d))')
# print(f'v = {(1/np.sqrt(3))*np.sqrt(3/2)*np.sqrt(v_d*v_d + v_q*v_q)} p.u. (from vd, vq)')
print(f'delta = {np.arctan2(v_q, v_d)*360/(2*np.pi)} º')
print(f'delta = {np.arctan2(v_q, v_d)} rad')
print(f'Pe = {v_a*i_a + v_b*i_b + v_c*i_c} p.u.')
# print(f'Pe = {(3/2)*(v_d*i_d + v_q*i_q + v_0*i_0)} p.u.')  # exactly the same as before
print(f'Qe = {(1/np.sqrt(3))*((v_a-v_b)*i_c + (v_b-v_c)*i_a + (v_c-v_a)*i_b)} p.u.')
# print(f'Qe = {(3/2)*(v_q*i_d - v_d*i_q)} p.u.')