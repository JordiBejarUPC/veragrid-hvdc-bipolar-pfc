import numpy as np
import matplotlib.pyplot as plt

# ---- Parameters ----
L_ = 1e-6      # H/m
C_ = 1e-11     # F/m
length = 100e3 #m
Rsource = 3  # source impedance (ohm)
print("Gc source = ", 1/Rsource)
Vpeak = 230e3 * np.sqrt(2)
f = 50
omega = 2 * np.pi * f
nbus = 2

# ---- Derived line quantities ----
Zc = np.sqrt(L_ / C_)
v_wave = 1 / np.sqrt(L_ * C_)
tau = length / v_wave
print(f"Zc = {Zc:.2f} Ω, τ = {tau*1e3:.3f} ms")
print("Yc = ", 1/Zc)



Rload = Zc  # matched load (ohm)
print("Gc load = ", 1/Rload)
# Rload = 1e20 # open-circuit
# Rload = 1e-20 # short-circuit

# ---- Simulation setup ----
dt = tau / 50   # 50 points per delay
n_steps = int(15 / f / dt)  # ~6 cycles
t = np.arange(n_steps) * dt
Ndelay = int(round(tau / dt))
print("Ndelay = ", Ndelay)
print("dt = ", dt)

# ---- Source voltage ----
vs = Vpeak * np.sin(omega * t)

# ---- initialize MNA ----
# these change for each time step
G = np.zeros((nbus, nbus))

# add Bergeron's line params: initialize with open circuit
G[0,0] += 1 / Zc
G[1,1] += 1 / Zc


# add voltage source to ground
G[0,0] += 1 / Rsource
#add load to ground
G[1,1] +=  1 / Rload

print("G =", G)
# ---- init ----
# initialize variables
v1 = np.zeros_like(t)
v2 = np.zeros_like(t)
i1 = np.zeros_like(t)
i2 = np.zeros_like(t)
i_hist_1 = np.zeros_like(t)
i_hist_2 = np.zeros_like(t)

for step in range(1, n_steps):
    # update I
    if step - Ndelay >= 0:
        i_hist_1[step] = -v2[step - Ndelay] / Zc - i2[step - Ndelay]
        i_hist_2[step] = -v1[step - Ndelay] / Zc - i1[step - Ndelay]

    Itotal = np.array([[vs[step] / Rsource - i_hist_1[step]],
                       [0.0 - i_hist_2[step]]])
    V = np.linalg.solve(G, Itotal)
    v1[step], v2[step] = V[0,0], V[1,0]

    i1[step] = v1[step]/Zc + i_hist_1[step]
    i2[step] = v2[step]/Zc + i_hist_2[step]
    # i2[step] = 0


fig, axs = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

# --- Subplot 1: Voltages ---
axs[0].plot(t*1e3, vs/1e3, color='green', linewidth=1, label='Source voltage [kV]')
axs[0].plot(t*1e3, v1/1e3, color='blue', linewidth=1, label='Sending-end voltage [kV]')
axs[0].plot(t*1e3, v2/1e3, color='red', linewidth=1, label='Receiving-end voltage [kV]')
axs[0].set_xlabel(r'Time  $[ms]$')
axs[0].set_ylabel(r'Voltage  $[kV]$')
axs[0].set_title("Voltages - Bergeron Line Energization EMT Simulation")
axs[0].legend(loc='upper right')
axs[0].grid(True)

# --- Subplot 2: Currents ---
axs[1].plot(t*1e3, i1, color='blue', linewidth=1, label='Sending-end current [A]')
axs[1].plot(t*1e3, -i2, color='red',linewidth=1, label='Receiving-end current [A]')
axs[1].set_xlabel(r'Time  $[ms]$')
axs[1].set_ylabel(r'Current  $[A]$')
axs[1].set_title("Currents - Bergeron Line Energization EMT Simulation")
axs[1].legend(loc='upper right')
axs[1].grid(True)

plt.tight_layout()
plt.show()

plt.figure(figsize=(10, 6))
plt.plot(t*1e3, i_hist_1, label='i hist 1 [A]', color='b')
plt.plot(t * 1e3, i_hist_2, label='i hist 2 [A]', color='r')
plt.xlabel('Time [ms]')
plt.ylabel('Voltage [kV]')
plt.title("Currents - Bergeron's line EMT simulation")
plt.legend(loc='upper right')
plt.grid(True)
plt.show()

plt.figure(figsize=(10, 6))
plt.plot(t*1e3, vs/ Rsource, label='i source [A]', color='b')
plt.xlabel('Time [ms]')
plt.ylabel('Current [A]')
plt.title("Current source - Bergeron's line EMT simulation")
plt.legend(loc='upper right')
plt.grid(True)
plt.show()




