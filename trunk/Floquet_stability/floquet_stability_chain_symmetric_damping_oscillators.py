# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import eigvals, norm
from numpy.linalg import cond



"""
Floquet stability analysis example
==================================

Example system:
---------------
Chain of coupled damped oscillators with periodically varying stiffness.

This system is a natural multi-state generalisation of the classical
2nd-order damped oscillator with periodic stiffness:

    x¨ + d x˙ + (k0 + k1 sin(ω t)) x = 0

Here we consider:
- n oscillators
- nearest-neighbour coupling (spring-like)
- identical damping on all oscillators
- periodic stiffness modulation (parametric excitation)

This type of model appears in:
- structural dynamics
- LC / LCL filter chains
- multi-machine electromechanical models
- linearised EMT systems with periodic operating points

State vector:
-------------
z = [x1, ..., xn, v1, ..., vn]^T
where:
- xi = displacement of oscillator i
- vi = velocity of oscillator i

Total number of states = 2n

Floquet theory is required because the system matrix A(t)
is explicitly time-periodic.
"""

# ----------------------------------------------------------------------
# SYSTEM MATRIX A(t)
# ----------------------------------------------------------------------
def A_chain(t, omega, d, n, k0=2.0, k1=1.0, kc=0.5):
    """
    Time-periodic system matrix A(t).

    Represents a chain of n oscillators with:
    - periodic stiffness modulation
    - viscous damping
    - nearest-neighbour coupling
    """

    k = k0 + k1 * np.sin(omega * t)

    I = np.eye(n)
    Z = np.zeros((n, n))

    K = k * I
    for i in range(n):
        if i > 0:
            K[i, i]     += kc
            K[i, i - 1] -= kc
        if i < n - 1:
            K[i, i]     += kc
            K[i, i + 1] -= kc

    A = np.block([
        [Z,   I],
        [-K, -d * I]
    ])

    return A


# ----------------------------------------------------------------------
# FUNDAMENTAL MATRIX ODE
# ----------------------------------------------------------------------
def fundamental_ode_chain(t, M_flat, omega, d, n):
    """
    Differential equation for the fundamental matrix:

        dM/dt = A(t) M(t)
    """

    dim = 2 * n
    M = M_flat.reshape((dim, dim))

    A_t = A_chain(t, omega, d, n)

    # Diagnostics at selected times
    if abs((t % (np.pi / omega))) < 1e-3:
        print(f"[t = {t:8.4f}] |A(t)|_F = {norm(A_t):.4e}")

    dMdt = A_t @ M
    return dMdt.flatten()


# ----------------------------------------------------------------------
# FLOQUET ANALYSIS
# ----------------------------------------------------------------------
if __name__ == "__main__":

    print("\n==============================")
    print("FLOQUET STABILITY ANALYSIS")
    print("==============================\n")

    # -----------------------------
    # Model parameters
    # -----------------------------
    n = 100
    omega = 2.0
    d = 0.3

    T = 2 * np.pi / omega
    dim = 2 * n

    print(f"Number of oscillators        : {n}")
    print(f"Total number of states       : {dim}")
    print(f"Excitation angular frequency : {omega}")
    print(f"Damping coefficient          : {d}")
    print(f"Period T                     : {T:.6f}\n")

    # -----------------------------
    # Initial condition
    # -----------------------------
    M0 = np.eye(dim).flatten()
    print("Initial fundamental matrix M(0) = I")
    print(f"||M(0)||_F = {norm(np.eye(dim)):.4e}\n")

    # -----------------------------
    # Integrate fundamental matrix
    # -----------------------------
    print("Integrating M˙(t) = A(t) M(t) over one period...\n")

    sol = solve_ivp(
        fundamental_ode_chain,
        t_span=(0.0, T),
        y0=M0,
        args=(omega, d, n),
        method="RK45",
        rtol=1e-8,
        atol=1e-10
    )

    if not sol.success:
        raise RuntimeError("Integration failed")

    print("\nIntegration finished successfully.")
    print(f"Number of internal time steps : {len(sol.t)}\n")

    # -----------------------------
    # Monodromy matrix
    # -----------------------------
    C_M = sol.y[:, -1].reshape((dim, dim))

    print("Monodromy matrix C_M = M(T)")
    print(f"||C_M||_F      = {norm(C_M):.4e}")
    print(f"cond(C_M)      = {cond(C_M):.4e}\n")

    # -----------------------------
    # Floquet multipliers
    # -----------------------------
    mu = eigvals(C_M)

    print("Floquet multipliers μ_i:")
    for i, val in enumerate(mu):
        print(
            f"  μ{i+1:02d} = {val.real:+.6e} "
            f"{val.imag:+.6e}j |μ| = {abs(val):.6e}"
        )

    rho = np.max(np.abs(mu))

    print("\nSpectral radius max |μ| = {:.6e}".format(rho))

    # -----------------------------
    # Stability interpretation
    # -----------------------------
    print("\nStability interpretation:")
    if rho < 1.0:
        print("✔ All |μ| < 1  → asymptotically stable periodic orbit")
    elif np.isclose(rho, 1.0):
        print("⚠ |μ| ≈ 1      → marginally stable (neutral mode present)")
    else:
        print("✘ Some |μ| > 1 → unstable (parametric resonance)")

    print("\nAnalysis complete.")
