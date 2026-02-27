# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Validation script for the Implicit Solvers using a classic Harmonic Oscillator system.

This test validates:
1. The correct assembly of state equations using the Block API.
2. The accuracy of Implicit Integration schemes (Trapezoidal vs BDF2).
3. The integration with the new BaseProblem + JitSymbolicSolver architecture.
"""

import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod

class GenericEmtProblem(EmtProblemTemplate):
    pass

def integrator(initial_val, name: str):
    """
    Creates a state variable and a container block with a placeholder equation.
    Enables the syntax: x, blk = integrator(None, "x")
    """
    var = Var(name)
    # Initialize state_eqs with a Const(0.0) so that index [0] is available for later coupling
    blk = Block(name=f"int_{name}", state_vars=[var], state_eqs=[Const(0.0)])
    return var, blk

def build_oscillator_system(omega=1.0):
    """
    Constructs the State-Space model for a harmonic oscillator.

    Equations:
        dx/dt = v
        dv/dt = -omega^2 * x

    :param omega: Angular frequency of the oscillator.
    :return: Tuple containing (System Block, x variable, v variable).
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
    return system, x, v


def run_test():
    """
    Executes the validation routine comparing Trapezoidal and BDF2 methods
    against the analytical solution.
    """
    t0, t_end, h = 0.0, 20.0, 0.01
    omega = 2.0

    print(f"--- NUMERICAL VALIDATION START ---")
    print(f"System: Harmonic Oscillator (omega={omega})")
    print(f"Interval: [{t0}, {t_end}] s, step h={h} s")

    # 1. Build Block and Unify
    sys_block, var_x, var_v = build_oscillator_system(omega)
    sys_block.unify_blocks()
    glob_time = Var("t_glob")

    # 2. Setup Problem
    problem = GenericEmtProblem(sys_block, glob_time)

    idx_x = problem.get_var_idx(var_x)
    idx_v = problem.get_var_idx(var_v)

    # Extract the original zeros array and inject our values
    custom_x0 = problem.get_x0()
    custom_x0[idx_x] = 1.0
    custom_x0[idx_v] = 0.0

    # Override the problem's method so the JitSymbolicSolver gets our custom array
    problem.get_x0 = lambda: custom_x0.copy()

    # --- CASE 1: Trapezoidal Method (A-Stable) ---
    print("\n[1] Running Implicit Solver (Method: Trapezoidal)...")
    solver_trap = JitSymbolicSolver(
        problem=problem, t0=t0, t_end=t_end, h=h,
        method=DynamicIntegrationMethod.Trapezoid,
        verbose=True
    )
    t_trap, y_trap_full = solver_trap.simulate()

    # --- CASE 2: BDF2 Method (L-Stable) ---
    print("\n[2] Running Implicit Solver (Method: BDF2)...")
    solver_bdf = JitSymbolicSolver(
        problem=problem, t0=t0, t_end=t_end, h=h,
        method=DynamicIntegrationMethod.BDF2,
        verbose=True
    )
    t_bdf, y_bdf_full = solver_bdf.simulate()

    # --- Extract variables for analysis ---
    x_trap = y_trap_full[:, idx_x]
    v_trap = y_trap_full[:, idx_v]

    x_bdf = y_bdf_full[:, idx_x]
    v_bdf = y_bdf_full[:, idx_v]

    # --- Error Analysis ---
    # Analytical solution: x(t) = x0 * cos(w*t)
    x_exact = 1.0 * np.cos(omega * t_trap)

    err_trap = np.linalg.norm(x_trap - x_exact) / np.sqrt(len(t_trap))
    err_bdf = np.linalg.norm(x_bdf - x_exact) / np.sqrt(len(t_bdf))

    print("\n--- ERROR REPORT (RMS) ---")
    print(f"Trapezoidal: {err_trap:.6e} (Should be highly accurate)")
    print(f"BDF2       : {err_bdf:.6e} (Should show numerical damping)")
    print("-" * 30)

    plot_results(t_trap, x_trap, v_trap, x_bdf, v_bdf, x_exact)


def plot_results(t, x_trap, v_trap, x_bdf, v_bdf, x_exact):
    """
    Visualizes the time-domain response and phase space trajectories.
    """
    plt.figure(figsize=(10, 8))

    # Time Domain
    plt.subplot(2, 1, 1)
    plt.plot(t, x_exact, 'k-', linewidth=1.5, alpha=0.3, label='Analytical')
    plt.plot(t, x_trap, 'r--', label='Trapezoidal')
    plt.plot(t, x_bdf, 'b-.', label='BDF2')
    plt.title('Time Response: Position x(t)')
    plt.ylabel('Amplitude [u]')
    plt.legend()
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)

    # Phase Space (Trapezoidal)
    plt.subplot(2, 2, 3)
    plt.plot(x_trap, v_trap, 'r-', linewidth=1, label='Trapezoidal')
    plt.title('Phase Space (Trapezoidal)')
    plt.xlabel('Position x')
    plt.ylabel('Velocity v')
    plt.axis('equal')
    plt.grid(True)

    # Phase Space (BDF2)
    plt.subplot(2, 2, 4)
    plt.plot(x_bdf, v_bdf, 'b-', linewidth=1, label='BDF2')
    plt.title('Phase Space (BDF2)')
    plt.xlabel('Position x')
    plt.yticks([])
    plt.axis('equal')
    plt.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    run_test()