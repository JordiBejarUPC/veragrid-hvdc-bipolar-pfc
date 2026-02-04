import numpy as np
from scipy.integrate import solve_ivp
from numpy.linalg import eigvals

# ----- fUNCTION TO ANALYZE: damped oscillator with periodic stiffness -----
def A(t, omega, d):
    k = 2.0 + np.sin(omega * t)
    return np.array([
        [0.0,  1.0],
        [-k,  -d]
    ])

def fundamental_ode(t, M_flat, omega, d):
    M = M_flat.reshape((2, 2))
    dMdt = A(t, omega, d) @ M
    return dMdt.flatten()

# parameters
omega = 2.0
d = 0.3
T = 2 * np.pi / omega


M0 = np.eye(2).flatten()   # M(0) = I

sol = solve_ivp(
    fundamental_ode,
    t_span=(0.0, T),
    y0=M0,
    args=(omega, d),
    method="RK45",        # try "Radau" if stiff
    rtol=1e-9,
    atol=1e-12
)

M_T = sol.y[:, -1].reshape((2, 2))
print("Monodromy matrix C_M:")
print(M_T)

mu = eigvals(M_T)

print("\nFloquet multipliers:")
for i, val in enumerate(mu):
    print(f"μ{i+1} = {val:.6f}, |μ| = {abs(val):.6f}")

rho = np.max(np.abs(mu))

if rho < 1:
    print("\nSystem is asymptotically stable")
elif np.isclose(rho, 1.0):
    print("\nSystem is marginally stable")
else:
    print("\nSystem is unstable")







