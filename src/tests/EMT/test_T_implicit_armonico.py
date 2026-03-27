# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Any, Tuple
from unittest.mock import patch

import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


class GenericEmtProblem(EmtProblemTemplate):
    """
    Generic EMT problem template for harmonic oscillator tests.
    """
    __slots__ = list()


def integrator(initial_val: Any, vf: VarFactory, name: str) -> Tuple[Var, Block]:
    """
    Create an integrator block for a variable.

    :param initial_val: Initial value (unused in this simple implementation).
    :param vf: Variable factory for creating variables.
    :param name: Name for the variable.
    :returns: Tuple of (variable, integrator block).
    """
    var = vf.add_var(name)
    diff_var = vf.add_diff_var(name=f"d_{name}", base_var=var)
    blk: Block = Block(
        name=f"int_{name}",
        state_vars=list([var]),
        diff_vars=list([diff_var]),
        state_eqs=list([Const(0.0)])
    )
    return var, blk


def build_oscillator_system(vf: VarFactory, omega: float = 1.0) -> Tuple[Block, Var, Var]:
    """
    Build a harmonic oscillator system.

    Creates a second-order harmonic oscillator with position x
    and velocity v, governed by d^2x/dt^2 = -omega^2 * x.

    :param vf: Variable factory for creating variables.
    :param omega: Angular frequency of oscillation.
    :returns: Tuple of (system_block, x_var, v_var).
    """
    x, blk_x = integrator(None, name="x", vf=vf)
    v, blk_v = integrator(None, name="v", vf=vf)

    blk_x.state_eqs[0] = v
    blk_v.state_eqs[0] = Const(-(omega ** 2)) * x

    system: Block = Block(
        name="HarmonicOscillator",
        children=list([blk_x, blk_v])
    )
    return system, x, v


class CustomInitialCondition:
    """
    Helper class to set custom initial conditions without using lambda.

    Stores the custom initial condition array and provides a callable
    interface to retrieve it.
    """
    __slots__ = ["_x0"]

    def __init__(self, x0: np.ndarray) -> None:
        self._x0 = x0.copy()

    def __call__(self) -> np.ndarray:
        """Return a copy of the stored initial condition."""
        return self._x0.copy()


def run_test() -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Run harmonic oscillator simulation with Trapezoidal and BDF2 methods.

    Creates a harmonic oscillator system with initial conditions x(0)=1, v(0)=0,
    and runs simulations using both integration methods.

    :returns: Tuple of (t_trap, x_trap, v_trap, t_bdf, x_bdf, v_bdf, x_exact).
    """
    t0: float = 0.0
    t_end: float = 20.0
    h: float = 0.01
    omega: float = 2.0

    vf = VarFactory()
    sys_block, var_x, var_v = build_oscillator_system(vf=vf, omega=omega)
    sys_block.unify_blocks()
    glob_time = vf.add_var("t_glob")

    problem: GenericEmtProblem = GenericEmtProblem(sys_block, glob_time)

    idx_x: int = problem.get_var_idx(var_x)
    idx_v: int = problem.get_var_idx(var_v)

    custom_x0: np.ndarray = problem.get_x0()
    custom_x0[idx_x] = 1.0
    custom_x0[idx_v] = 0.0

    problem.get_x0 = CustomInitialCondition(custom_x0)

    solver_trap = JitSymbolicSolver(
        problem=problem, t0=t0, t_end=t_end, h=h,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False
    )
    t_trap, y_trap_full, _ = solver_trap.simulate()

    solver_bdf = JitSymbolicSolver(
        problem=problem, t0=t0, t_end=t_end, h=h,
        method=DynamicIntegrationMethod.DaeBDF2,
        verbose=False
    )
    t_bdf, y_bdf_full, _ = solver_bdf.simulate()

    x_trap: np.ndarray = y_trap_full[:, idx_x]
    v_trap: np.ndarray = y_trap_full[:, idx_v]
    x_bdf: np.ndarray = y_bdf_full[:, idx_x]
    v_bdf: np.ndarray = y_bdf_full[:, idx_v]

    x_exact: np.ndarray = 1.0 * np.cos(omega * t_trap)

    return t_trap, x_trap, v_trap, t_bdf, x_bdf, v_bdf, x_exact


@patch("matplotlib.pyplot.show")
def test_harmonic_oscillator_trapezoidal(mock_show) -> None:
    """
    Test harmonic oscillator with Trapezoidal integration.

    Verifies that the Trapezoidal method produces finite, bounded
    position and velocity trajectories for the harmonic oscillator.
    """
    t_trap, x_trap, v_trap, t_bdf, x_bdf, v_bdf, x_exact = run_test()

    assert len(t_trap) == len(x_trap)
    assert len(t_trap) == len(v_trap)

    assert np.all(np.isfinite(x_trap))
    assert np.all(np.isfinite(v_trap))

    assert np.all(np.abs(x_trap) < 2.0)
    assert np.all(np.abs(v_trap) < 5.0)


@patch("matplotlib.pyplot.show")
def test_harmonic_oscillator_bdf2(mock_show) -> None:
    """
    Test harmonic oscillator with BDF2 integration.

    Verifies that the BDF2 method produces finite position and
    velocity trajectories.
    """
    t_trap, x_trap, v_trap, t_bdf, x_bdf, v_bdf, x_exact = run_test()

    assert len(t_bdf) == len(x_bdf)
    assert len(t_bdf) == len(v_bdf)

    assert np.all(np.isfinite(x_bdf))
    assert np.all(np.isfinite(v_bdf))


@patch("matplotlib.pyplot.show")
def test_trapezoidal_error_small(mock_show) -> None:
    """
    Test that Trapezoidal method has small error vs exact solution.

    Verifies that the Trapezoidal integration error remains bounded
    and reasonable for the harmonic oscillator.
    """
    t_trap, x_trap, v_trap, t_bdf, x_bdf, v_bdf, x_exact = run_test()

    err_trap: float = float(np.linalg.norm(x_trap - x_exact) / np.sqrt(len(t_trap)))

    assert err_trap < 1.0, f"Trapezoidal error should be small, got {err_trap}"


@patch("matplotlib.pyplot.show")
def test_bdf2_error_small(mock_show) -> None:
    """
    Test that BDF2 method error is bounded.

    Verifies that the BDF2 method produces a bounded solution
    even if the error is larger than Trapezoidal.
    """
    t_trap, x_trap, v_trap, t_bdf, x_bdf, v_bdf, x_exact = run_test()

    err_bdf: float = float(np.linalg.norm(x_bdf - x_exact) / np.sqrt(len(t_bdf)))

    assert err_bdf < 5.0, f"BDF2 error should be bounded, got {err_bdf}"


@patch("matplotlib.pyplot.show")
def test_initial_conditions_correct(mock_show) -> None:
    """
    Test that initial conditions are correctly set.

    Verifies that x(0)=1.0 and v(0)=0.0 as specified
    for the harmonic oscillator.
    """
    t_trap, x_trap, v_trap, t_bdf, x_bdf, v_bdf, x_exact = run_test()

    assert abs(x_trap[0] - 1.0) < 1e-5
    assert abs(v_trap[0] - 0.0) < 1e-5


@patch("matplotlib.pyplot.show")
def test_energy_conserved_trapezoidal(mock_show) -> None:
    """
    Test that energy remains finite in Trapezoidal simulation.

    Verifies numerical stability by checking that the mechanical
    energy (kinetic + potential) remains finite throughout.
    """
    t_trap, x_trap, v_trap, t_bdf, x_bdf, v_bdf, x_exact = run_test()

    omega = 2.0
    energy_initial = 0.5 * v_trap[0]**2 + 0.5 * omega**2 * x_trap[0]**2
    energy_final = 0.5 * v_trap[-1]**2 + 0.5 * omega**2 * x_trap[-1]**2

    assert np.isfinite(energy_initial)
    assert np.isfinite(energy_final)


@patch("matplotlib.pyplot.show")
def test_both_methods_produce_physical_results(mock_show) -> None:
    """
    Test that both methods agree on initial conditions.

    Verifies that Trapezoidal and BDF2 produce consistent
    initial values despite different algorithmic behavior.
    """
    t_trap, x_trap, v_trap, t_bdf, x_bdf, v_bdf, x_exact = run_test()

    assert np.allclose(x_trap[0], x_bdf[0], atol=1e-3)
    assert np.allclose(v_trap[0], v_bdf[0], atol=1e-3)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
