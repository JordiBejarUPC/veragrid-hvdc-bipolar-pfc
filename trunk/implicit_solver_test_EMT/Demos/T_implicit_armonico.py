# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Validation script for the Implicit BlockSolver using a classic Harmonic Oscillator system.

This test validates:
1. The correct assembly of state equations using the Block API.
2. The accuracy of Implicit Integration schemes (Trapezoidal vs BDF2).
3. The convergence of the Newton-Raphson solver for linear oscillatory systems.
"""

import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.Symbolic.block import Block, integrator
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod

def build_oscillator_system(omega=1.0):
    """
    Constructs the State-Space model for a harmonic oscillator.

    Equations:
        dx/dt = v
        dv/dt = -omega^2 * x

    :param omega: Angular frequency of the oscillator.
    :return: Block containing the system equations.
    """
    x, blk_x = integrator(None, name="x")
    v, blk_v = integrator(None, name="v")

    # Coupling
    blk_x.state_eqs[0] = v
    blk_v.state_eqs[0] = Const(-(omega ** 2)) * x

    system = Block(
        name="HarmonicOscillator",
        children=[blk_x, blk_v]
    )
    return system


def run_test():
    """
    Executes the validation routine comparing Trapezoidal and BDF2 methods
    against the analytical solution.
    """
    t0, t_end, h = 0.0, 20.0, 0.01
    omega = 2.0

    # Initial conditions: x(0)=1, v(0)=0
    x0 = np.array([1.0, 0.0], dtype=np.float64)
    dx0 = np.zeros_like(x0)

    print(f"--- NUMERICAL VALIDATION START ---")
    print(f"System: Harmonic Oscillator (omega={omega})")
    print(f"Interval: [{t0}, {t_end}] s, step h={h} s")

    glob_time = Var("t_glob")

    sys = build_oscillator_system(omega)
    solver = BlockSolver(sys, glob_time)

    params0 = np.array([])

    # --- CASE 1: Trapezoidal Method (A-Stable) ---
    print("\n[1] Running Implicit Solver (Method: Trapezoidal)...")

    t_trap, y_trap = solver.simulate_unified(
        t0, t_end, h, x0, dx0, params0,
        method=DynamicIntegrationMethod.Trapezoid,
        verbose=True,
        dense_threshold=100
    )

    # --- CASE 2: BDF2 Method (L-Stable) ---
    print("\n[2] Running Implicit Solver (Method: BDF2)...")

    t_bdf, y_bdf = solver.simulate_unified(
        t0, t_end, h, x0, dx0, params0,
        method=DynamicIntegrationMethod.BDF2,
        verbose=True,
        dense_threshold=100
    )

    # --- Error Analysis ---
    # Analytical solution: x(t) = x0 * cos(w*t)
    x_exact = x0[0] * np.cos(omega * t_trap)

    err_trap = np.linalg.norm(y_trap[:, 0] - x_exact) / np.sqrt(len(t_trap))
    err_bdf = np.linalg.norm(y_bdf[:, 0] - x_exact) / np.sqrt(len(t_bdf))

    print("\n--- ERROR REPORT (RMS) ---")
    print(f"Trapezoidal: {err_trap:.6e}")
    print(f"BDF2       : {err_bdf:.6e}")
    print("-" * 30)

    plot_results(t_trap, y_trap, y_bdf, x_exact)


def plot_results(t, y_trap, y_bdf, x_exact):
    """
    Visualizes the time-domain response and phase space trajectories.
    """
    plt.figure(figsize=(10, 8))

    # Time Domain
    plt.subplot(2, 1, 1)
    plt.plot(t, x_exact, 'k-', linewidth=1.5, alpha=0.3, label='Analytical')
    plt.plot(t, y_trap[:, 0], 'r--', label='Trapezoidal')
    plt.plot(t, y_bdf[:, 0], 'b-.', label='BDF2')
    plt.title('Time Response: Position x(t)')
    plt.ylabel('Amplitude [u]')
    plt.legend()
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)

    # Phase Space (Trapezoidal)
    plt.subplot(2, 2, 3)
    plt.plot(y_trap[:, 0], y_trap[:, 1], 'r-', linewidth=1, label='Trapezoidal')
    plt.title('Phase Space (Trapezoidal)')
    plt.xlabel('Position x')
    plt.ylabel('Velocity v')
    plt.axis('equal')
    plt.grid(True)

    # Phase Space (BDF2)
    plt.subplot(2, 2, 4)
    plt.plot(y_bdf[:, 0], y_bdf[:, 1], 'b-', linewidth=1, label='BDF2')
    plt.title('Phase Space (BDF2)')
    plt.xlabel('Position x')
    plt.yticks([])
    plt.axis('equal')
    plt.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    run_test()