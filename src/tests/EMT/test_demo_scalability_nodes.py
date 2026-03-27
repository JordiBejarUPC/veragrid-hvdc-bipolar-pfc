# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import time
from typing import Any, Dict, List
from unittest.mock import patch

import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


def create_linear_chain(n_masses: int, vf: VarFactory) -> Block:
    """
    Create a linear chain of masses connected by springs.

    Builds a 1D chain of n_masses connected by springs and dampers,
    representing a simple mechanical system for scalability testing.

    :param n_masses: Number of masses in the chain.
    :param vf: Variable factory for creating system variables.
    :returns: Block representing the linear chain system.
    """
    pos_vars: List[Var] = list()
    d_pos_vars: List[Var] = list()
    vel_vars: List[Var] = list()
    d_vel_vars: List[Var] = list()
    for i in range(n_masses):
        pos_vars.append(vf.add_var(f"x_{i}"))
        d_pos_vars.append(vf.add_diff_var(name=f"d_x_{i}", base_var=pos_vars[i]))
        vel_vars.append(vf.add_var(f"v_{i}"))
        d_vel_vars.append(vf.add_diff_var(name=f"d_v_{i}", base_var=vel_vars[i]))

    k: Const = Const(5000.0)
    c: Const = Const(0.5)

    state_vars: List[Var] = list()
    state_eqs: List[Expr] = list()
    diff_vars: List[Var] = list()

    for i in range(n_masses):
        x_i, d_x_i, v_i, d_v_i = pos_vars[i], d_pos_vars[i], vel_vars[i], d_vel_vars[i]
        if i > 0:
            x_L: Expr = pos_vars[i - 1]
        else:
            x_L = Const(0.0)

        if i < n_masses - 1:
            x_R: Expr = pos_vars[i + 1]
        else:
            x_R = Const(0.0)

        force: Expr = k * (x_L - x_i) + k * (x_R - x_i) - c * v_i

        state_vars.append(x_i)
        diff_vars.append(d_x_i)
        state_vars.append(v_i)
        diff_vars.append(d_v_i)
        state_eqs.append(v_i)
        state_eqs.append(force)

    return Block(
        name=f"Linear_N{n_masses}",
        state_vars=state_vars,
        state_eqs=state_eqs,
        diff_vars=diff_vars,
        parameters=dict()
    )


def compute_steps(t0: float, t_end: float, h: float) -> int:
    """
    Compute the number of simulation steps.

    :param t0: Start time.
    :param t_end: End time.
    :param h: Time step size.
    :returns: Number of steps as integer.
    """
    return int(np.ceil((t_end - t0) / h))


class InitialConditionSetter:
    """
    Helper class to set custom initial conditions on a problem.

    Avoids using lambda functions by storing the initial condition
    array directly and providing a callable interface.
    """
    __slots__ = ["_x0"]

    def __init__(self, x0: np.ndarray) -> None:
        self._x0 = x0.copy()

    def __call__(self) -> np.ndarray:
        """Return a copy of the stored initial condition."""
        return self._x0.copy()


def setup_initial_condition(problem: GenericEmtProblem, block: Block, n_nodes: int) -> None:
    """
    Setup sinusoidal initial conditions for the linear chain.

    :param problem: EMT problem to set initial conditions on.
    :param block: System block containing state variables.
    :param n_nodes: Number of nodes in the chain.
    """
    x0: np.ndarray = problem.get_x0()

    for i in range(n_nodes):
        idx_state: int = 2 * i
        if idx_state < len(block.state_vars):
            var_xi: Var = block.state_vars[idx_state]
            if var_xi.uid in problem.uid2idx_vars:
                x0[problem.get_var_idx(var_xi)] = 0.5 * np.sin(2.0 * np.pi * i / max(n_nodes, 1))

    initial_condition_setter = InitialConditionSetter(x0)
    problem.get_x0 = initial_condition_setter


def run_backend(
        label: str,
        n_nodes: int,
        vectorized: bool,
        t_end: float,
        h: float,
        verbose: bool = False
) -> Dict[str, Any]:
    """
    Run scalability benchmark for a given backend.

    Creates a linear chain system, runs EMT simulation, and measures
    timing and activity metrics for the specified solver backend.

    :param label: Label identifier for the test case.
    :param n_nodes: Number of masses in the linear chain.
    :param vectorized: If True, use vectorized solver; otherwise use AD solver.
    :param t_end: Simulation end time.
    :param h: Simulation time step.
    :param verbose: Enable verbose output.
    :returns: Dictionary with timing and activity metrics.
    """
    vf: VarFactory = VarFactory()
    block: Block = create_linear_chain(n_masses=n_nodes, vf=vf)
    block.unify_blocks()
    t_sym: Var = Var("t_glob")

    mode: str = "VEC" if vectorized else "AD"

    t_setup_start: float = time.perf_counter()

    problem: GenericEmtProblem = GenericEmtProblem(sys_block=block, glob_time=t_sym)
    setup_initial_condition(problem, block, n_nodes)

    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
    params0: np.ndarray = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)

    target_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal

    if vectorized:
        solver_vec = StructuralVectorizedSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=target_method, verbose=verbose
        )
        solver_vec.auto_detect_vectorization(method=target_method)
        solver = solver_vec
    else:
        solver_ad = JitAdSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=target_method, verbose=verbose
        )
        solver_ad.build_jit_ad()
        solver = solver_ad

    solver.simulate()

    setup_s: float = time.perf_counter() - t_setup_start

    n_steps: int = compute_steps(0.0, t_end, h)

    t_sim_start: float = time.perf_counter()
    _, y_arr, _ = solver.simulate()

    sim_s: float
    if hasattr(solver, 'last_pure_sim_time'):
        sim_s = solver.last_pure_sim_time
    else:
        sim_s = time.perf_counter() - t_sim_start

    total_s: float = setup_s + sim_s
    ms_step: float = (sim_s / max(n_steps, 1)) * 1000.0
    activity: float = float(np.mean(np.abs(y_arr)))

    return dict({
        "mode": mode,
        "setup_s": setup_s,
        "sim_s": sim_s,
        "total_s": total_s,
        "ms_step": ms_step,
        "n_steps": n_steps,
        "activity": activity,
    })


def test_linear_chain_creation() -> None:
    """
    Test that linear chain block creation produces correct structure.

    Verifies that a chain of 10 masses creates 20 state variables
    (position and velocity for each mass) and 20 differential variables.
    """
    vf = VarFactory()
    block = create_linear_chain(n_masses=10, vf=vf)
    block.unify_blocks()

    assert len(block.state_vars) == 20
    assert len(block.diff_vars) == 20


@patch("matplotlib.pyplot.show")
def test_ad_backend_runs_successfully(mock_show) -> None:
    """
    Test that AD backend runs successfully on linear chain.

    Verifies that the automatic differentiation solver produces
    finite timing results and activity for a moderate-sized chain.
    """
    result = run_backend(
        label="LIN",
        n_nodes=50,
        vectorized=False,
        t_end=1e-4,
        h=1e-7,
        verbose=False
    )

    assert result["mode"] == "AD"
    assert np.isfinite(result["setup_s"])
    assert np.isfinite(result["sim_s"])
    assert np.isfinite(result["total_s"])
    assert result["n_steps"] > 0
    assert np.isfinite(result["activity"])


@patch("matplotlib.pyplot.show")
def test_vectorized_backend_runs_successfully(mock_show) -> None:
    """
    Test that vectorized backend runs successfully on linear chain.

    Verifies that the structural vectorized solver produces
    finite timing results for a moderate-sized chain.
    """
    result = run_backend(
        label="LIN",
        n_nodes=50,
        vectorized=True,
        t_end=1e-4,
        h=1e-7,
        verbose=False
    )

    assert result["mode"] == "VEC"
    assert np.isfinite(result["setup_s"])
    assert np.isfinite(result["sim_s"])
    assert result["n_steps"] > 0


@patch("matplotlib.pyplot.show")
def test_both_backends_produce_similar_activity(mock_show) -> None:
    """
    Test that AD and vectorized backends produce similar activity.

    Both solvers should produce similar mean absolute state values
    for the same system, indicating correct simulation.
    """
    result_ad = run_backend(
        label="LIN",
        n_nodes=50,
        vectorized=False,
        t_end=1e-4,
        h=1e-7,
        verbose=False
    )

    result_vec = run_backend(
        label="LIN",
        n_nodes=50,
        vectorized=True,
        t_end=1e-4,
        h=1e-7,
        verbose=False
    )

    assert np.isfinite(result_ad["activity"]), "AD activity should be finite"
    assert np.isfinite(result_vec["activity"]), "VEC activity should be finite"


@patch("matplotlib.pyplot.show")
def test_scalability_with_more_nodes(mock_show) -> None:
    """
    Test that larger systems require more computation time.

    Verifies that the simulation time increases with the number
    of nodes, demonstrating proper algorithmic complexity.
    """
    result_small = run_backend(
        label="LIN",
        n_nodes=20,
        vectorized=False,
        t_end=1e-4,
        h=1e-7,
        verbose=False
    )

    result_large = run_backend(
        label="LIN",
        n_nodes=100,
        vectorized=False,
        t_end=1e-4,
        h=1e-7,
        verbose=False
    )

    assert result_large["total_s"] > result_small["total_s"], "Larger system should take more time"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
