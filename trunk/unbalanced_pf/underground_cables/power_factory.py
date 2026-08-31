import numpy as np

rho_Al = 2.8264 # Aluminium resistivity [uΩ·cm]
alpha_Al = 0.00403 # Aluminium temperature coefficient at 20 ºC [1/ºC]
rho_Cu = 1.7241 # Copper resistivity [uΩ·cm]
alpha_Cu = 0.00382 # Aluminium temperature coefficient at 20 ºC [1/ºC]

'''
SINGLE CORE CABLE TYPE (TypCab)
'''

# Conductor
material_c = 'Al' # 'Al' or 'Cu' -> materialCond
q_c = 0.0 # Inner diameter of the conducting layer [mm] -> diaTube
r_c = 6.35809 * 2 # Outer diameter of the conducting layer [mm] -> diaCon
C_f_c = 100 # Filling factor of conducting layers [%] -> Cf
if material_c == 'Al':
    rho_c = rho_Al # Resistivity [uΩ·cm]
    alpha_c = alpha_Al # Temperature coefficient at 20 ºC [1/ºC]
elif material_c == 'Cu':
    rho_c = rho_Cu # Resistivity [uΩ·cm]
    alpha_c = alpha_Cu # Temperature coefficient at 20 ºC [1/ºC]
else:
    rho_c = rho_Cu  # Resistivity [uΩ·cm]
    alpha_c = alpha_Cu  # Temperature coefficient at 20 ºC [1/ºC]
    raise Warning('material_c')
R_DC_c = rho_c * 10**3 / (np.pi * ((r_c/2)**2 - (q_c/2)**2) * C_f_c) # DC resistance of the cable [Ω/km]
print('R_DC = ', np.round(R_DC_c,7), 'Ω/km')

# Sheath
material_s = 'Cu' # 'Al' or 'Cu' -> materialCond
q_s = r_c + 7.103906 * 2 # Inner diameter of the conducting layer [mm] -> diaTube
r_s = q_s + 0.159258 * 2 # Outer diameter of the conducting layer [mm] -> diaCon
C_f_s = 99.44012 # Filling factor of conducting layers [%] -> Cf
if material_s == 'Al':
    rho_s = rho_Al # Resistivity [uΩ·cm]
    alpha_s = alpha_Al # Temperature coefficient at 20 ºC [1/ºC]
elif material_s == 'Cu':
    rho_s = rho_Cu # Resistivity [uΩ·cm]
    alpha_s = alpha_Cu # Temperature coefficient at 20 ºC [1/ºC]
else:
    rho_s = rho_Cu  # Resistivity [uΩ·cm]
    alpha_s = alpha_Cu  # Temperature coefficient at 20 ºC [1/ºC]
    raise Warning('material_s')
R_DC_s = rho_s * 10**3 / (np.pi * ((r_s/2)**2 - (q_s/2)**2) * C_f_s) # DC resistance of the cable [Ω/km]
print('R_DC = ', np.round(R_DC_s,7), 'Ω/km')


'''
CABLE SYSTEM TYPE (TypCabsys)
'''
f = 60 # Nominal frequency [Hz] -> frnom
cGearth = 100 # Conductivity of the ground [uS/cm] -> cGearth
x1 = -0.1524 # [m]
x2 = 0.0 # [m]
x3 = 0.1524 # [m]
y1 = 0.6096 # [m]
y2 = 0.6096 # [m]
y3 = 0.6096 # [m]

'''
SERIES IMPEDANCE MATRIX
'''
sigma_g = cGearth * 10**(-4)  # Conductivity of the ground [S/m]
R_ac = np.array([R_DC_c, R_DC_c, R_DC_c, R_DC_s, R_DC_s, R_DC_s]) # Resistance's vector [Ω/km]
gmr_c = np.exp(-1/4) * r_c / 2000 # Geometric mean radius of the conductor [m]
ri_s = q_s * 10**(-3) / 2 # Inner radius of the conducting layer [mm] -> diaTube
ro_s = r_s * 10**(-3) / 2 # Outer radius of the conducting layer [mm] -> diaCon
gmr_s = ro_s * np.exp(
    (3.0 * ri_s**2 - ro_s**2) / (4.0 * (ro_s**2 - ri_s**2))
    - (ri_s**4 / (ro_s**2 - ri_s**2)**2) * np.log(ro_s / ri_s)
) # Geometric mean radius of the sheath [m]
gmr = np.array([gmr_c, gmr_c, gmr_c, gmr_s, gmr_s, gmr_s]) # Geometric mean radius's vector [Ω/km]

d_ab = np.sqrt((x1 - x2)**2 + (y1 - y2)**2)
d_bc = np.sqrt((x2 - x3)**2 + (y2 - y3)**2)
d_ca = np.sqrt((x3 - x1)**2 + (y3 - y1)**2)

d_cs = (ri_s + ro_s) / 2 # Distance between conductor and sheath [m]

d = np.array([
    [1e-20, d_ab, d_ca, d_cs, d_ab, d_ca],
    [d_ab, 1e-20, d_bc, d_ab, d_cs, d_bc],
    [d_ca, d_bc, 1e-20, d_ca, d_bc, d_cs],
    [d_cs, d_ab, d_ca, 1e-20, d_ab, d_ca],
    [d_ab, d_cs, d_bc, d_ab, 1e-20, d_bc],
    [d_ca, d_bc, d_cs, d_ca, d_bc, 1e-20],
]) # Geometrical distances vector [m]

# Self impedance calculation using Carson infinite series [Ω/km]:
Z_self = R_ac + 4 * np.pi * f * 10**(-4) * (np.pi / 4 + 1j * np.log(658.87165 / (gmr * np.sqrt(f * sigma_g))))
print('Z_self =', np.round(Z_self,5))

# Mutual impedance calculation using Carson infinite series [Ω/km]:
Z_mutual = 4 * np.pi * f * 10**(-4) * (np.pi / 4 + 1j * np.log(658.87165 / (d * np.sqrt(f * sigma_g))))
print('Z_mutual =', np.round(Z_mutual,5))

# Total series impedance with concentric wires [Ω/km]:
Z_series = Z_mutual.copy()
np.fill_diagonal(Z_series, Z_self)
print('Z_series =', np.round(Z_series,5))

# Applying Kron reduction to eliminate the explicit representation of the concentric wires [Ω/km]:
phases = 3
Z_cc = Z_series[0:phases, 0:phases]
Z_ww = Z_series[phases:, phases:]
Z_cw = Z_series[0:phases, phases:]
Z_wc = Z_series[phases:, 0:phases]
Z_abc = Z_cc - Z_cw @ np.linalg.inv(Z_ww) @ Z_wc
print('Z_abc =', np.round(Z_abc,5))

# Applying Fortescue transformation to obtain the sequence impedance [Ω/km]:
a = np.exp(1j * 2 * np.pi / 3)
F_abc_to_012 = np.array([
    [1, 1, 1],
    [1, a**2, a],
    [1, a, a**2]
])
F_012_to_abc = 1/3 * np.array([
    [1, 1, 1],
    [1, a, a**2],
    [1, a**2, a]
])
Z_012 = F_012_to_abc @ Z_abc @ F_abc_to_012
print('Z_012 =', np.round(Z_012,5))

'''
SHUNT ADMITTANCE MATRIX
'''
epsilon_insulation = 2.3 # Relative permittivity of the insulation
epsilon_oversheath = 2.5 # Relative permittivity of the oversheath
epsilon_0 = 8.854 * 10**(-12) # Permittivity of the free space [F/m]

r_c = 6.35809 # Conductor radius [mm]
r_insulation = r_c + 7.103906 # Insulation radius [mm]
r_s = r_insulation + 0.159258 # Sheath radius [mm]
r_oversheath = r_s + 1.651 # Oversheath radius [mm]

P_insulation = (1/(2 * np.pi * epsilon_0 * epsilon_insulation)) * np.log(r_insulation/r_c)
P_oversheath = (1/(2 * np.pi * epsilon_0 * epsilon_oversheath)) * np.log(r_oversheath/r_s)

I3 = np.eye(3)

# Ordering: [c1, c2, c3, s1, s2, s3]
P = np.block([
    [(P_insulation + P_oversheath) * I3, P_oversheath * I3],
    [P_oversheath * I3,         P_oversheath * I3],
])

Y_shunt = 1j * 2 * np.pi * f * np.linalg.inv(P)
print('Y_shunt =', np.round(Y_shunt * 1e9, 6))  # μS/km

Y_cc = Y_shunt[:3, :3]
Y_cs = Y_shunt[:3, 3:]
Y_sc = Y_shunt[3:, :3]
Y_ss = Y_shunt[3:, 3:]
Y_abc = Y_cc - Y_cs @ np.linalg.inv(Y_ss) @ Y_sc
print('Y_abc =', np.round(Y_abc * 1e9, 6))  # μS/km

Y_012 = F_012_to_abc @ Y_abc @ F_abc_to_012
print('Y_012 =', np.round(Y_012 * 1e9, 6))  # μS/km