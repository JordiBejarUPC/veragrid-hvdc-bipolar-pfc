# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Minimal demonstration to validate the correct operation of the symbolic
equation compiler. A simple dynamic system is compiled into a time-stepping
function and executed over multiple steps, with basic plots included only
to verify that the generated code behaves as expected.
"""

import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.symbolic import Var, DiffVar
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler


def solve_step_newton(step_fn, current_x, history, d_history, params, h,
                      tol=1e-6, max_iter=10):
    """
    Minimal Newton–Raphson solver to compute the next state x_next.
    Solves the nonlinear system F(x_next) = 0 at each time step.
    """
    # Initial guess (predictor): x_next = x_prev + h * dx_prev
    x_next = current_x + h * d_history

    # Numerical Jacobian approximation using finite differences.
    # In a real solver, symbolic differentiation would be used.
    perturbation = 1e-5
    n_vars = len(current_x)

    for k in range(max_iter):
        # 1. Evaluate residuals: F(x)
        residuals = step_fn(x_next, params, history, d_history, h)

        # Convergence check
        if np.max(np.abs(residuals)) < tol:
            return x_next

        # 2. Compute numerical Jacobian J
        J = np.zeros((n_vars, n_vars))
        for j in range(n_vars):
            x_pert = x_next.copy()
            x_pert[j] += perturbation
            res_pert = step_fn(x_pert, params, history, d_history, h)
            J[:, j] = (res_pert - residuals) / perturbation

        # 3. Newton update: x_new = x - J^{-1} * F
        try:
            delta = np.linalg.solve(J, residuals)
            x_next -= delta
        except np.linalg.LinAlgError:
            print("Singular Jacobian encountered. Aborting Newton iteration.")
            break

    return x_next


def run_demo():
    print("=== Visual Demo: Harmonic Oscillator ===")

    # 1. Define physics
    # System: M*x'' + C*x' + K*x = 0
    # State variables: [position, velocity]
    pos = Var('pos')
    vel = Var('vel')
    k = Var('k')
    c = Var('c')

    dpos = DiffVar(name='dpos', base_var=pos)
    dvel = DiffVar(name='dvel', base_var=vel)

    # Residual equations
    # 1) dpos/dt - vel = 0
    # 2) dvel/dt + c*vel + k*pos = 0 (assuming mass M = 1)
    eq1 = dpos - vel
    eq2 = dvel + c * vel + k * pos

    # 2. Compile equations (trapezoidal rule for improved stability)
    compiler = EquationCompiler(
        [pos, vel],
        parameters=[k, c],
        method='trapezoidal'
    )
    step_fn = compiler.compile([eq1, eq2])
    print("[OK] Equations successfully compiled.")

    # 3. Simulation setup
    t_end = 100.0
    h = 0.05
    steps = int(t_end / h)
    time = np.linspace(0, t_end, steps)

    # Result arrays
    results = np.zeros((steps, 2))  # [position, velocity]
    energy = np.zeros(steps)

    # Initial conditions: 2 m displacement, zero velocity
    x0 = np.array([2.0, 0.0])

    # Parameters: k = 1.0 (spring), c = 0.1 (light damping)
    p_vals = np.array([1.0, 0.1])

    # Initialise state history
    current_x = x0.copy()
    history = x0.copy()

    # Initial derivative history:
    # dx = v = 0
    # dv = -k*x - c*v = -2
    d_history = np.array([0.0, -2.0])

    print(f"Simulating {steps} time steps...")

    for i in range(steps):
        # Store results
        results[i] = current_x

        # Total energy = kinetic + potential
        energy[i] = (
            0.5 * current_x[1]**2 +
            0.5 * p_vals[0] * current_x[0]**2
        )

        # Compute next step
        next_x = solve_step_newton(
            step_fn, current_x, history, d_history, p_vals, h
        )

        # Update derivative history (trapezoidal reconstruction)
        # dx_new = (2/h)*(x_new - x_old) - dx_old
        d_next = (2.0 / h) * (next_x - history) - d_history

        history = current_x
        d_history = d_next
        current_x = next_x

    # 4. Plot results
    plt.figure(figsize=(12, 8))

    # Plot 1: Time response
    plt.subplot(2, 2, 1)
    plt.plot(time, results[:, 0], label='Position (m)', color='blue')
    plt.plot(time, results[:, 1], label='Velocity (m/s)',
             color='orange', linestyle='--')
    plt.title("Time Response")
    plt.grid(True)
    plt.legend()

    # Plot 2: Phase space
    plt.subplot(2, 2, 2)
    plt.plot(results[:, 0], results[:, 1], color='purple')
    plt.title("Phase Space (Velocity vs Position)")
    plt.xlabel("Position")
    plt.ylabel("Velocity")
    plt.grid(True)

    # Plot 3: Energy evolution
    plt.subplot(2, 1, 2)
    plt.plot(time, energy, color='green', linewidth=2)
    plt.title("Total System Energy (Damped)")
    plt.xlabel("Time (s)")
    plt.ylabel("Energy")
    plt.grid(True)

    plt.tight_layout()
    print("Generating plots...")
    plt.show()


if __name__ == "__main__":
    run_demo()
