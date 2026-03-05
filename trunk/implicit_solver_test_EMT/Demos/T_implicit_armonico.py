# ==============================================================================
# Validation script for the Implicit Solvers using a classic Harmonic Oscillator
# ==============================================================================

import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Any

# VeraGridEngine Imports
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


def integrator(initial_val: Any, vf: VarFactory, name: str) -> Tuple[Var, Block]:
    """
    Creates a state variable and a container block with a placeholder equation.
    """
    var= vf.add_var(name)
    diff_var = vf.add_diff_var(name = f"d_{name}", base_var=var)
    blk: Block = Block(
        name=f"int_{name}",
        state_vars=list([var]),
        diff_vars = list([diff_var]),
        state_eqs=list([Const(0.0)])
    )
    return var, blk


def build_oscillator_system(vf: VarFactory, omega: float = 1.0) -> Tuple[Block, Var, Var]:
    """
    Constructs the State-Space model for a harmonic oscillator.
    """
    x, blk_x = integrator(None, name="x", vf= vf)
    v, blk_v = integrator(None, name="v", vf= vf)

    # Coupling: dx/dt = v, dv/dt = -omega^2 * x
    blk_x.state_eqs[0] = v
    blk_v.state_eqs[0] = Const(-(omega ** 2)) * x

    system: Block = Block(
        name="HarmonicOscillator",
        children=list([blk_x, blk_v])
    )
    return system, x, v


def run_test() -> None:
    """
    Executes the validation routine comparing Trapezoidal and BDF2 methods.
    """
    t0: float = 0.0
    t_end: float = 20.0
    h: float = 0.01
    omega: float = 2.0

    print(f"--- NUMERICAL VALIDATION START ---")
    print(f"System: Harmonic Oscillator (omega={omega})")
    print(f"Interval: [{t0}, {t_end}] s, step h={h} s")

    # 1. Build Block and Unify
    vf = VarFactory()
    sys_block, var_x, var_v = build_oscillator_system(vf=vf, omega = omega)
    sys_block.unify_blocks()
    glob_time = vf.add_var("t_glob")

    # 2. Setup Problem
    problem: GenericEmtProblem = GenericEmtProblem(sys_block, glob_time)

    idx_x: int = problem.get_var_idx(var_x)
    idx_v: int = problem.get_var_idx(var_v)

    custom_x0: np.ndarray = problem.get_x0()
    custom_x0[idx_x] = 1.0
    custom_x0[idx_v] = 0.0

    problem.get_x0 = lambda: custom_x0.copy()

    # --- CASE 1: Trapezoidal Method (A-Stable) ---
    print("\n[1] Running Implicit Solver (Method: Trapezoidal)...")
    solver_trap = JitSymbolicSolver(
        problem=problem, t0=t0, t_end=t_end, h=h,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=True
    )
    t_trap, y_trap_full = solver_trap.simulate()

    # --- CASE 2: BDF2 Method (L-Stable) ---
    print("\n[2] Running Implicit Solver (Method: BDF2)...")
    solver_bdf = JitSymbolicSolver(
        problem=problem, t0=t0, t_end=t_end, h=h,
        method=DynamicIntegrationMethod.DaeBDF2,
        verbose=True
    )
    t_bdf, y_bdf_full = solver_bdf.simulate()

    # --- Analysis ---
    x_trap: np.ndarray = y_trap_full[:, idx_x]
    v_trap: np.ndarray = y_trap_full[:, idx_v]
    x_bdf: np.ndarray = y_bdf_full[:, idx_x]
    v_bdf: np.ndarray = y_bdf_full[:, idx_v]

    # Analytical solution: x(t) = x0 * cos(w*t)
    x_exact: np.ndarray = 1.0 * np.cos(omega * t_trap)

    err_trap: float = float(np.linalg.norm(x_trap - x_exact) / np.sqrt(len(t_trap)))
    err_bdf: float = float(np.linalg.norm(x_bdf - x_exact) / np.sqrt(len(t_bdf)))

    print("\n--- ERROR REPORT (RMS) ---")
    print(f"Trapezoidal: {err_trap:.6e} (A-Stable, Conservation of Energy)")
    print(f"BDF2       : {err_bdf:.6e} (L-Stable, Numerical Damping)")
    print("-" * 30)

    plot_results(t_trap, x_trap, v_trap, x_bdf, v_bdf, x_exact)


def plot_results(t: np.ndarray, x_trap: np.ndarray, v_trap: np.ndarray,
                 x_bdf: np.ndarray, v_bdf: np.ndarray, x_exact: np.ndarray) -> None:
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
    plt.yticks(list())
    plt.axis('equal')
    plt.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    run_test()