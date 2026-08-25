import numpy as np

phases = 3 # Number of phases
f = 60 # Power system frequency [Hz]
sigma_g = 1/100 # Conductivity of the ground [S/m]

r_ext_c = 56 / 2 * 10**(-3) # Conductor's external radius [m]
r_ext_one_strand = 2.03 / 2 * 10**(-3) # Concentric wire's external radius [m]
n = 78 # Number of strands in the concentric wire
r_ext = 114.2 / 2 * 10**(-3) # External radius after the concentric wires [m]

R_ac_a = 0.015842 # Phase a conductor resistance at the power frequency [Ω/km]
R_ac_b = 0.015749 # Phase b conductor resistance at the power frequency [Ω/km]
R_ac_c = 0.015749 # Phase c conductor resistance at the power frequency [Ω/km]

R_ac_w_a = 0.08759 # Concentric wire's resistance of phase a [Ω/km]
R_ac_w_b = 0.0867 # Concentric wire's resistance of phase b [Ω/km]
R_ac_w_c = 0.0867 # Concentric wire's resistance of phase c [Ω/km]

d_ab = 0.425 # Distance between phases a and b [m]
d_ca = 0.425 # Distance between phases c and a [m]
d_bc = d_ab + d_ca # Distance between phases b and c [m]

R = r_ext - r_ext_one_strand # Radius of the concentric wire [m]

R_ac = np.array([R_ac_a, R_ac_b, R_ac_c, R_ac_w_a, R_ac_w_b, R_ac_w_c]) # Resistance's vector [Ω/km]

gmr_c = np.exp(-1/4) * r_ext_c # Geometric mean radius of the conductor [m]
gmr_one_strand = np.exp(-1/4) * r_ext_one_strand # Geometric mean radius of one strand [m]
gmr_w = (gmr_one_strand * n * R**(n-1))**(1/n) # Geometric mean radius of concentric wires [m]
gmr = np.array([gmr_c, gmr_c, gmr_c, gmr_w, gmr_w, gmr_w]) # Geometric mean radius's vector [Ω/km]

d = np.array([
    [1e-20, d_ab, d_ca, R, d_ab, d_ca],
    [d_ab, 1e-20, d_bc, d_ab, R, d_bc],
    [d_ca, d_bc, 1e-20, d_ca, d_bc, R],
    [R, d_ab, d_ca, 1e-20, d_ab, d_ca],
    [d_ab, R, d_bc, d_ab, 1e-20, d_bc],
    [d_ca, d_bc, R, d_ca, d_bc, 1e-20],
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

# Three sections of equal length: only the concentric strands are transposed
permutations = (
    [0, 1, 2, 3, 4, 5],
    [0, 1, 2, 4, 5, 3],
    [0, 1, 2, 5, 3, 4],
)

Z_bond = sum(
    Z_series[np.ix_(p, p)]
    for p in permutations
) / len(permutations)

# Applying Kron reduction to eliminate the explicit representation of the concentric wires [Ω/km]:
Z_cc = Z_bond[0:phases, 0:phases]
Z_ww = Z_bond[phases:, phases:]
Z_cw = Z_bond[0:phases, phases:]
Z_wc = Z_bond[phases:, 0:phases]
Z_abc = Z_cc - Z_cw @ np.linalg.inv(Z_ww) @ Z_wc
print('Z_abc =', np.round(Z_abc,5))