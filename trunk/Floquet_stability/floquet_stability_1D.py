# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0



import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import eig

# ----- fUNCTION TO ANALYZE -----
# dx = (-1 +0.5 * np.sin(w*t)) * x with a(t)= (-1 +0.5 * np.sin(w*t))
def a(t, omega):
    return -1.0 + 0.5 * np.sin(omega * t)

def fundamental_ode(t, M, omega):
    return a(t, omega) * M

# parameters
omega = 2.0 *np.pi * 50         # velocitat angular
T = 2 * np.pi / omega  # període

# solve integral
sol = solve_ivp(
    fundamental_ode,
    t_span=(0.0, T),
    y0=[1.0],          # M(0) = 1
    args=(omega,),
    method="RK45",
    rtol=1e-9,
    atol=1e-12
)
print(sol)

C_M_sc = sol.y[0, -1]    # M(T)
import numpy as np

C_M = np.array([[C_M_sc]])

(eigvals, eigvecs )= eig(C_M)

print("Eigenvalues:", eigvals)

print(f"Monodromia C_M = {C_M_sc:.6f}")
print(f"Multiplicador de Floquet μ = {eigvals}")

mu_analytic = np.exp(-T)
print(f"μ analític = {mu_analytic:.6f}")

#with backward euler
N = 2000
h = T / N

# Backward Euler integration
M = 1.0
t = 0.0

for k in range(N):
    t_next = t + h
    M = M / (1.0 - h * a(t_next, omega))
    t = t_next

C_M_BE = M
print("Backward Euler monodromy:", C_M_BE)










