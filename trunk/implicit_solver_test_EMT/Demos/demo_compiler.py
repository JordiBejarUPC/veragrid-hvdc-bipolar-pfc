# ==============================================================================
# DEMO COMPILER
# ==============================================================================

import numpy as np
import matplotlib.pyplot as plt
from typing import Callable, List

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler
from VeraGridEngine.enumerations import DynamicIntegrationMethod


def solve_step_newton(step_fn: Callable, current_x: np.ndarray, history: np.ndarray,
                      d_history: np.ndarray, params: np.ndarray, h: float,
                      tol: float = 1e-6, max_iter: int = 10) -> np.ndarray:
    """
    Minimal Newton–Raphson solver to compute the next state x_next.
    """
    # Initial guess (predictor): x_next = x_prev + h * dx_prev
    x_next: np.ndarray = current_x + h * d_history
    perturbation: float = 1e-5
    n_vars: int = len(current_x)

    for _ in range(max_iter):
        # 1. Evaluate residuals: F(x)
        residuals: np.ndarray = step_fn(x_next, params, history, d_history, h)

        # Convergence check
        if float(np.max(np.abs(residuals))) < tol:
            return x_next
        else:
            pass

        # 2. Compute numerical Jacobian J
        J: np.ndarray = np.zeros((n_vars, n_vars), dtype=np.float64)
        for j in range(n_vars):
            x_pert: np.ndarray = x_next.copy()
            x_pert[j] += perturbation
            res_pert: np.ndarray = step_fn(x_pert, params, history, d_history, h)
            J[:, j] = (res_pert - residuals) / perturbation

        # 3. Newton update: x_new = x - J^{-1} * F
        det_j: float = float(np.linalg.det(J))
        if abs(det_j) < 1e-12:
            print("Singular Jacobian encountered. Aborting Newton iteration.")
            break
        else:
            delta: np.ndarray = np.linalg.solve(J, residuals)
            x_next -= delta

    return x_next


def run_demo() -> None:
    print("=== Visual Demo: Harmonic Oscillator ===")

    # 1. Define physics
    pos: Var = Var('pos')
    vel: Var = Var('vel')
    k: Var = Var('k')
    c: Var = Var('c')

    dpos: Var = Var(name='dpos', base_var=pos)
    dvel: Var = Var(name='dvel', base_var=vel)

    eq1: Expr = dpos - vel
    eq2: Expr = dvel + c * vel + k * pos

    variables: List[Var] = list([pos, vel])
    parameters: List[Var] = list([k, c])
    equations: List[Expr] = list([eq1, eq2])

    # 2. Compile equations
    compiler = EquationCompiler(
        variables,
        parameters=parameters,
        method=DynamicIntegrationMethod.DaeTrapezoidal
    )
    step_fn: Callable = compiler.compile(equations)
    print("[OK] Equations successfully compiled.")

    # 3. Simulation setup
    t_end: float = 100.0
    h: float = 0.05
    steps: int = int(t_end / h)
    time: np.ndarray = np.linspace(0, t_end, steps)

    results: np.ndarray = np.zeros((steps, 2), dtype=np.float64)
    energy: np.ndarray = np.zeros(steps, dtype=np.float64)

    x0: np.ndarray = np.array([2.0, 0.0], dtype=np.float64)
    p_vals: np.ndarray = np.array([1.0, 0.1], dtype=np.float64)

    current_x: np.ndarray = x0.copy()
    history: np.ndarray = x0.copy()
    d_history: np.ndarray = np.array([0.0, -2.0], dtype=np.float64)

    print(f"Simulating {steps} time steps...")

    for i in range(steps):
        results[i] = current_x

        energy[i] = (
            0.5 * current_x[1]**2 +
            0.5 * p_vals[0] * current_x[0]**2
        )

        next_x: np.ndarray = solve_step_newton(
            step_fn, current_x, history, d_history, p_vals, h
        )

        d_next: np.ndarray = (2.0 / h) * (next_x - history) - d_history

        history = current_x
        d_history = d_next
        current_x = next_x

    # 4. Plot results
    plt.figure(figsize=(12, 8))

    plt.subplot(2, 2, 1)
    plt.plot(time, results[:, 0], label='Position (m)', color='blue')
    plt.plot(time, results[:, 1], label='Velocity (m/s)', color='orange', linestyle='--')
    plt.title("Time Response")
    plt.grid(True)
    plt.legend()

    plt.subplot(2, 2, 2)
    plt.plot(results[:, 0], results[:, 1], color='purple')
    plt.title("Phase Space (Velocity vs Position)")
    plt.xlabel("Position")
    plt.ylabel("Velocity")
    plt.grid(True)

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