"""
Floquet stability analysis of a HETEROGENEOUS chain of coupled oscillators
=========================================================================

This example generalises the previous homogeneous chain by introducing
heterogeneity in:
- masses
- damping coefficients
- stiffness modulation amplitudes

As a result:
- the system is no longer symmetric
- normal modes are no longer equivalent
- Floquet multipliers have DIFFERENT magnitudes
- a dominant mode naturally appears

This behaviour is representative of realistic EMT / power-system models.
"""

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import eigvals, norm
from numpy.linalg import cond

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import eigvals, norm
from numpy.linalg import cond

# ----------------------------------------------------------------------
# SYSTEM MATRIX A(t) — HETEROGENEOUS CHAIN
# ----------------------------------------------------------------------
def A_chain_heterogeneous(
    t,
    omega,
    n,
    m,
    d,
    k0,
    k1,
    kc
):
    """
    Time-periodic system matrix for a heterogeneous chain of oscillators.

    Mechanical model:
        M q¨ + D q˙ + K(t) q = 0

    with periodically varying stiffness:
        k_i(t) = k0_i + k1_i sin(ω t)

    State vector:
        x = [q; q˙]
    """

    # Periodic stiffness per oscillator
    k_t = k0 + k1 * np.sin(omega * t)

    # Mass-normalised matrices
    Minv = np.diag(1.0 / m)

    Z = np.zeros((n, n))
    I = np.eye(n)

    # Stiffness matrix
    K = np.zeros((n, n))
    for i in range(n):
        K[i, i] += k_t[i]
        if i > 0:
            K[i, i]     += kc
            K[i, i - 1] -= kc
        if i < n - 1:
            K[i, i]     += kc
            K[i, i + 1] -= kc

    # Damping matrix
    D = np.diag(d)

    # First-order state-space form
    A = np.block([
        [Z,            I],
        [-Minv @ K,  -Minv @ D]
    ])

    return A


# ----------------------------------------------------------------------
# FUNDAMENTAL MATRIX ODE
# ----------------------------------------------------------------------
def fundamental_ode_chain(t, M_flat, omega, n, m, d, k0, k1, kc):
    dim = 2 * n
    M = M_flat.reshape((dim, dim))

    A_t = A_chain_heterogeneous(
        t, omega, n, m, d, k0, k1, kc
    )

    dMdt = A_t @ M
    return dMdt.flatten()


# ----------------------------------------------------------------------
# BUILD MEAN (TIME-INVARIANT) STIFFNESS MATRIX K0
# ----------------------------------------------------------------------
def build_K0(k0, kc):
    n = len(k0)
    K = np.zeros((n, n))

    for i in range(n):
        K[i, i] += k0[i]
        if i > 0:
            K[i, i]     += kc
            K[i, i - 1] -= kc
        if i < n - 1:
            K[i, i]     += kc
            K[i, i + 1] -= kc

    return K


# ----------------------------------------------------------------------
# FLOQUET ANALYSIS
# ----------------------------------------------------------------------
if __name__ == "__main__":

    print("\n==============================================")
    print("FLOQUET ANALYSIS — HETEROGENEOUS OSCILLATOR CHAIN")
    print("==============================================\n")

    # -----------------------------
    # Model size
    # -----------------------------
    n = 4
    dim = 2 * n

    # -----------------------------
    # Heterogeneous parameters
    # -----------------------------
    m  = np.array([1.0, 1.2, 0.9, 1.4])
    d  = np.array([0.2, 0.35, 0.25, 0.4])
    k0 = np.array([2.0, 2.5, 1.8, 2.2])
    k1 = np.array([1.5, 1.2, 1.4, 1.1])
    kc = 0.6

    print("Mechanical parameters")
    print("---------------------")
    print("Masses               :", m)
    print("Damping              :", d)
    print("Base stiffness k0    :", k0)
    print("Modulation amplitude :", k1)
    print(f"Coupling stiffness   : {kc}\n")

    # -----------------------------
    # COMPUTE NATURAL FREQUENCIES ω_n
    # -----------------------------
    print("Computing natural frequencies ω_n of the mean system...")

    Mmat = np.diag(m)
    K0 = build_K0(k0, kc)

    eigvals_modal, _ = np.linalg.eig(np.linalg.inv(Mmat) @ K0)
    omega_n = np.sqrt(np.real(eigvals_modal[eigvals_modal > 0]))
    omega_n = np.sort(omega_n)

    for i, w in enumerate(omega_n):
        print(f"  ω_n[{i}] = {w:.6f} rad/s")

    # -----------------------------
    # PARAMETRIC RESONANCE SELECTION
    # -----------------------------
    mode_idx = 0   # choose which mode to excite
    # omega = 2.0 * omega_n[mode_idx]
    omega = 2.0

    T = 2 * np.pi / omega

    print("\nParametric excitation")
    print("---------------------")
    print(f"Selected mode index  : {mode_idx}")
    print(f"ω = 2 ω_n[{mode_idx}] = {omega:.6f} rad/s")
    print(f"Period T             : {T:.6f} s\n")

    # -----------------------------
    # Initial condition
    # -----------------------------
    M0 = np.eye(dim).flatten()
    print("Initial condition: M(0) = I")
    print(f"||M(0)||_F = {norm(np.eye(dim)):.4e}\n")

    # -----------------------------
    # Integrate fundamental matrix
    # -----------------------------
    print("Integrating M˙(t) = A(t) M(t)...\n")

    sol = solve_ivp(
        fundamental_ode_chain,
        t_span=(0.0, T),
        y0=M0,
        args=(omega, n, m, d, k0, k1, kc),
        method="RK45",
        rtol=1e-8,
        atol=1e-10
    )

    if not sol.success:
        raise RuntimeError("Integration failed")

    print("Integration completed.")
    print(f"Number of time steps: {len(sol.t)}\n")

    # -----------------------------
    # Monodromy matrix
    # -----------------------------
    C_M = sol.y[:, -1].reshape((dim, dim))

    print("Monodromy matrix C_M")
    print(f"||C_M||_F = {norm(C_M):.4e}")
    print(f"cond(C_M) = {cond(C_M):.4e}\n")

    # -----------------------------
    # Floquet multipliers
    # -----------------------------
    mu = eigvals(C_M)

    print("Floquet multipliers:")
    for i, val in enumerate(mu):
        print(
            f"  μ{i+1:02d} = {val.real:+.6e} "
            f"{val.imag:+.6e}j |μ| = {abs(val):.6e}"
        )

    rho = np.max(np.abs(mu))

    # -----------------------------
    # Stability verdict
    # -----------------------------
    print("\nStability verdict:")
    if rho < 1.0:
        print("✔ Asymptotically stable (all |μ| < 1)")
    elif np.isclose(rho, 1.0):
        print("⚠ Marginally stable (|μ| ≈ 1)")
    else:
        print("✘ Unstable (|μ| > 1 detected)")

    print("\nAnalysis complete.")


#
# # ----------------------------------------------------------------------
# # SYSTEM MATRIX A(t) — HETEROGENEOUS CHAIN
# # ----------------------------------------------------------------------
# def A_chain_heterogeneous(
#     t,
#     omega,
#     n,
#     m,
#     d,
#     k0,
#     k1,
#     kc
# ):
#     """
#     Time-periodic system matrix for a heterogeneous chain of oscillators.
#
#     Parameters
#     ----------
#     m  : array of masses, shape (n,)
#     d  : array of damping coefficients, shape (n,)
#     k0 : array of base stiffnesses, shape (n,)
#     k1 : array of modulation amplitudes, shape (n,)
#     kc : coupling stiffness (scalar)
#     """
#
#     # Periodic stiffness per oscillator
#     k_t = k0 + k1 * np.sin(omega * t)
#
#     # Mass-normalised matrices
#     Minv = np.diag(1.0 / m)
#
#     Z = np.zeros((n, n))
#     I = np.eye(n)
#
#     # Stiffness matrix with heterogeneous coefficients
#     K = np.zeros((n, n))
#     for i in range(n):
#         K[i, i] += k_t[i]
#         if i > 0:
#             K[i, i]     += kc
#             K[i, i - 1] -= kc
#         if i < n - 1:
#             K[i, i]     += kc
#             K[i, i + 1] -= kc
#
#     # Damping matrix
#     D = np.diag(d)
#
#     # First-order state-space form:
#     #
#     # [ x˙ ] = [   0        I ] [ x ]
#     # [ v˙ ]   [ -M⁻¹K  -M⁻¹D ] [ v ]
#     #
#     A = np.block([
#         [Z,            I],
#         [-Minv @ K,  -Minv @ D]
#     ])
#
#     return A
#
#
# # ----------------------------------------------------------------------
# # FUNDAMENTAL MATRIX ODE
# # ----------------------------------------------------------------------
# def fundamental_ode_chain(t, M_flat, omega, n, m, d, k0, k1, kc):
#     dim = 2 * n
#     M = M_flat.reshape((dim, dim))
#
#     A_t = A_chain_heterogeneous(
#         t, omega, n, m, d, k0, k1, kc
#     )
#
#     dMdt = A_t @ M
#     return dMdt.flatten()
#
#
# # ----------------------------------------------------------------------
# # FLOQUET ANALYSIS
# # ----------------------------------------------------------------------
# if __name__ == "__main__":
#
#     print("\n==============================================")
#     print("FLOQUET ANALYSIS — HETEROGENEOUS OSCILLATOR CHAIN")
#     print("==============================================\n")
#
#     # -----------------------------
#     # Model size
#     # -----------------------------
#     n = 4                 # number of oscillators
#     dim = 2 * n
#
#     # -----------------------------
#     # Heterogeneous parameters
#     # -----------------------------
#     m  = np.array([1.0, 1.2, 0.9, 1.4])       # masses
#     d  = np.array([0.2, 0.35, 0.25, 0.4])     # damping
#     k0 = np.array([2.0, 2.5, 1.8, 2.2])       # base stiffness
#     # k1 = np.array([0.8, 0.4, 0.6, 0.3])       # modulation amplitude
#     k1 = np.array([1.5, 1.2, 1.4, 1.1])        # modulation amplitude
#     kc = 0.6                                  # coupling stiffness
#
#     omega = 2.0
#     T = 2 * np.pi / omega
#
#     print(f"Number of oscillators : {n}")
#     print(f"Total number of states: {dim}")
#     print("Masses               :", m)
#     print("Damping              :", d)
#     print("Base stiffness k0    :", k0)
#     print("Modulation amplitude :", k1)
#     print(f"Coupling stiffness   : {kc}")
#     print(f"Period T             : {T:.6f}\n")
#
#     # -----------------------------
#     # Initial condition
#     # -----------------------------
#     M0 = np.eye(dim).flatten()
#     print("Initial condition: M(0) = I")
#     print(f"||M(0)||_F = {norm(np.eye(dim)):.4e}\n")
#
#     # -----------------------------
#     # Integrate fundamental matrix
#     # -----------------------------
#     print("Integrating M˙(t) = A(t) M(t)...\n")
#
#     sol = solve_ivp(
#         fundamental_ode_chain,
#         t_span=(0.0, T),
#         y0=M0,
#         args=(omega, n, m, d, k0, k1, kc),
#         method="RK45",
#         rtol=1e-8,
#         atol=1e-10
#     )
#
#     if not sol.success:
#         raise RuntimeError("Integration failed")
#
#     print("Integration completed.")
#     print(f"Number of time steps: {len(sol.t)}\n")
#
#     # -----------------------------
#     # Monodromy matrix
#     # -----------------------------
#     C_M = sol.y[:, -1].reshape((dim, dim))
#
#     print("Monodromy matrix C_M")
#     print(f"||C_M||_F = {norm(C_M):.4e}")
#     print(f"cond(C_M) = {cond(C_M):.4e}\n")
#
#     # -----------------------------
#     # Floquet multipliers
#     # -----------------------------
#     mu = eigvals(C_M)
#
#     print("Floquet multipliers:")
#     for i, val in enumerate(mu):
#         print(
#             f"  μ{i+1:02d} = {val.real:+.6e} "
#             f"{val.imag:+.6e}j |μ| = {abs(val):.6e}"
#         )
#
#     rho = np.max(np.abs(mu))
#
#     # -----------------------------
#     # Stability verdict
#     # -----------------------------
#     print("\nStability verdict:")
#     if rho < 1.0:
#         print("✔ Asymptotically stable (all |μ| < 1)")
#     elif np.isclose(rho, 1.0):
#         print("⚠ Marginally stable (|μ| ≈ 1)")
#     else:
#         print("✘ Unstable (|μ| > 1 detected)")
#
#     print("\nAnalysis complete.")
