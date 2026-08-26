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
2.2 CABLE SYSTEM TYPE (TypCabsys)
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
3 Calculation of Electrical Parameters
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

d = np.array([
    [1e-20, d_ab, d_ca],
    [d_ab, 1e-20, d_bc],
    [d_ca, d_bc, 1e-20],
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