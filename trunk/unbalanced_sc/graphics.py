import pandas as pd
import matplotlib.pyplot as plt

# -------------------------------------------------------------------------------------------
#   Figura 1    -   Rf = 0,5
# -------------------------------------------------------------------------------------------

# PowerFactory (dynamic) importation Rf = 0,5
df_Rf05 = pd.read_csv('voltage_bus_ac_Rf05.csv')
df_Rf05 = df_Rf05[df_Rf05[df_Rf05.columns[0]] >= 0]
t_Rf05 = df_Rf05.iloc[:, 0]
u_Rf05 = df_Rf05.iloc[:, 1]

# VeraGrid (steady-state) definition Rf = 0,5
t_switch = 0.1
u1 = 1.00010284
u2_Rf05 = 0.611188
t_ref_Rf05 = [t_Rf05.min(), t_switch, t_switch, t_Rf05.max()]
u_ref_Rf05 = [u1,        u1,       u2_Rf05,       u2_Rf05]

# Plot  Rf = 0,5
plt.figure(figsize=(6.5, 3.8))
plt.plot(t_Rf05, u_Rf05, linestyle='-', label='PowerFactory (dynamic)')
plt.plot(t_ref_Rf05, u_ref_Rf05, linestyle='--', label='VeraGrid (steady-state)')
plt.xlabel('Time [s]')
plt.ylabel('Voltage [pu]')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

print('\nError Rf = 0,5 ->', abs(u_Rf05.iloc[-1] - u2_Rf05) / u_Rf05.iloc[-1] * 100, '%')

# -------------------------------------------------------------------------------------------
#   Figura 2    -   Rf = 1
# -------------------------------------------------------------------------------------------

# PowerFactory (dynamic) importation Rf = 1
df_Rf1 = pd.read_csv('voltage_bus_ac_Rf1.csv')
df_Rf1 = df_Rf1[df_Rf1[df_Rf1.columns[0]] >= 0]
t_Rf1 = df_Rf1.iloc[:, 0]
u_Rf1 = df_Rf1.iloc[:, 1]

# VeraGrid (steady-state) definition Rf = 1
t_switch = 0.1
u1 = 1.00010284
u2_Rf1 = 0.822714
t_ref_Rf1 = [t_Rf1.min(), t_switch, t_switch, t_Rf1.max()]
u_ref_Rf1 = [u1,        u1,       u2_Rf1,       u2_Rf1]

# Plot  Rf = 1
plt.figure(figsize=(6.5, 3.8))
plt.plot(t_Rf1, u_Rf1, linestyle='-', label='PowerFactory (dynamic)')
plt.plot(t_ref_Rf1, u_ref_Rf1, linestyle='--', label='VeraGrid (steady-state)')
plt.xlabel('Time [s]')
plt.ylabel('Voltage [pu]')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

print('\nError Rf = 1 ->', abs(u_Rf1.iloc[-1] - u2_Rf1) / u_Rf1.iloc[-1] * 100, '%')

# -------------------------------------------------------------------------------------------
#   Figura 3    -   Rf = 5
# -------------------------------------------------------------------------------------------

# PowerFactory (dynamic) importation Rf = 5
df_Rf5 = pd.read_csv('voltage_bus_ac_Rf5.csv')
df_Rf5 = df_Rf5[df_Rf5[df_Rf5.columns[0]] >= 0]
t_Rf5 = df_Rf5.iloc[:, 0]
u_Rf5 = df_Rf5.iloc[:, 1]

# VeraGrid (steady-state) definition Rf = 5
t_switch = 0.1
u1 = 1.00010284
u2_Rf5 = 0.981747
t_ref_Rf5 = [t_Rf5.min(), t_switch, t_switch, t_Rf5.max()]
u_ref_Rf5 = [u1,        u1,       u2_Rf5,       u2_Rf5]

# Plot  Rf = 5
plt.figure(figsize=(6.5, 3.8))
plt.plot(t_Rf5, u_Rf5, linestyle='-', label='PowerFactory (dynamic)')
plt.plot(t_ref_Rf5, u_ref_Rf5, linestyle='--', label='VeraGrid (steady-state)')
plt.xlabel('Time [s]')
plt.ylabel('Voltage [pu]')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

print('\nError Rf = 5 ->', abs(u_Rf5.iloc[-1] - u2_Rf5) / u_Rf5.iloc[-1] * 100, '%')