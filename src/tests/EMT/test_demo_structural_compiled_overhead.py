# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import time
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import numpy as np

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


BACKEND_ORDER: Tuple[str, ...] = ("SD", "AD", "VEC", "COMPILED")


def create_linear_chain(n_masses: int, k_value: float = 500.0, c_value: float = 0.5) -> Block:
    """
    Create a linear chain of masses connected by springs and dampers.

    Builds a 1D chain of n_masses connected by springs (k) and
    dampers (c), with fixed boundary conditions at both ends.

    :param n_masses: Number of masses in the chain.
    :param k_value: Spring constant.
    :param c_value: Damping coefficient.
    :returns: Block representing the linear chain system.
    """
    k: Const = Const(k_value)
    c: Const = Const(c_value)

    pos_vars: List[Var] = [Var(f"x_{i}") for i in range(n_masses)]
    vel_vars: List[Var] = [Var(f"v_{i}") for i in range(n_masses)]

    d_pos_vars: List[Var] = [Var(f"d_x_{i}", base_var=pos_vars[i]) for i in range(n_masses)]
    d_vel_vars: List[Var] = [Var(f"d_v_{i}", base_var=vel_vars[i]) for i in range(n_masses)]

    state_vars: List[Var] = list()
    diff_vars: List[Var] = list()
    state_eqs: List[Expr] = list()

    for i in range(n_masses):
        x_i: Var = pos_vars[i]
        v_i: Var = vel_vars[i]
        d_x_i: Var = d_pos_vars[i]
        d_v_i: Var = d_vel_vars[i]

        x_l: Expr = pos_vars[i - 1] if i > 0 else Const(0.0)
        x_r: Expr = pos_vars[i + 1] if i < n_masses - 1 else Const(0.0)

        force: Expr = k * (x_l - x_i) + k * (x_r - x_i) - c * v_i

        state_vars.extend([x_i, v_i])
        diff_vars.extend([d_x_i, d_v_i])
        state_eqs.extend([v_i, force])

    block = Block(
        name=f"LinearChain_{n_masses}",
        state_vars=state_vars,
        state_eqs=state_eqs,
        diff_vars=diff_vars,
        parameters=dict(),
    )
    block.unify_blocks()
    return block


def build_initial_conditions(
    problem: GenericEmtProblem,
    block: Block,
    n_masses: int,
    k_value: float = 500.0,
    c_value: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = problem.get_dx0()
    params0: np.ndarray = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)

    pos0 = np.zeros(n_masses, dtype=np.float64)

    for i in range(n_masses):
        pos0[i] = 0.25 * np.sin(2.0 * np.pi * i / max(n_masses, 1))

    for i in range(n_masses):
        x_var: Var = block.state_vars[2 * i]
        v_var: Var = block.state_vars[2 * i + 1]

        x_idx: int = problem.get_var_idx(x_var)
        v_idx: int = problem.get_var_idx(v_var)

        x_i: float = float(pos0[i])
        v_i: float = 0.0

        x0[x_idx] = x_i
        x0[v_idx] = v_i

        dx0[2 * i] = v_i

        x_l: float = float(pos0[i - 1]) if i > 0 else 0.0
        x_r: float = float(pos0[i + 1]) if i < n_masses - 1 else 0.0
        dx0[2 * i + 1] = k_value * (x_l - x_i) + k_value * (x_r - x_i) - c_value * v_i

    return x0, dx0, params0


def make_solver(
    backend: str,
    problem: GenericEmtProblem,
    t_end: float,
    h: float,
    method: DynamicIntegrationMethod,
) -> Any:
    common_kwargs: Dict[str, Any] = dict(
        problem=problem,
        t0=0.0,
        t_end=t_end,
        h=h,
        method=method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=False,
    )

    if backend == "SD":
        return JitSymbolicSolver(**common_kwargs)
    if backend == "AD":
        return JitAdSolver(**common_kwargs)
    if backend == "VEC":
        return StructuralVectorizedSolver(auto_vectorization=False, **common_kwargs)
    if backend == "COMPILED":
        return StructuralCompiledSolver(auto_build=False, **common_kwargs)

    raise ValueError(f"Unknown backend: {backend}")


def build_backend(solver: Any, backend: str, method: DynamicIntegrationMethod) -> None:
    if backend == "SD":
        solver.build_jit_kernel(method)
        solver._build_jit_symbolic_hybrid(method, use_sparse=True)
    elif backend == "AD":
        solver.build_jit_ad()
    elif backend == "VEC":
        solver.auto_detect_vectorization(method)
    elif backend == "COMPILED":
        solver._build_vectorized_backend(method)
    else:
        raise ValueError(f"Unknown backend: {backend}")


def run_once(
    solver: Any,
    x0: np.ndarray,
    dx0: np.ndarray,
    params0: np.ndarray,
) -> Tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    t0: float = time.perf_counter()
    t_arr, y_arr, dy_arr = solver.simulate(
        x0=x0.copy(),
        dx0=dx0.copy(),
        params0=params0.copy(),
    )
    elapsed: float = time.perf_counter() - t0
    return elapsed, t_arr, y_arr, dy_arr


def measure_backend(
    backend: str,
    n_masses: int,
    t_end: float,
    h: float,
    method: DynamicIntegrationMethod,
    steady_repeats: int = 2,
) -> Dict[str, Any]:
    block: Block = create_linear_chain(n_masses=n_masses)
    problem: GenericEmtProblem = GenericEmtProblem(sys_block=block, glob_time=Var("t_glob"))
    x0, dx0, params0 = build_initial_conditions(problem=problem, block=block, n_masses=n_masses)

    t_setup_start: float = time.perf_counter()
    solver: Any = make_solver(
        backend=backend,
        problem=problem,
        t_end=t_end,
        h=h,
        method=method,
    )
    build_backend(solver=solver, backend=backend, method=method)
    setup_s: float = time.perf_counter() - t_setup_start

    first_run_s, t_arr, y_arr, dy_arr = run_once(
        solver=solver,
        x0=x0,
        dx0=dx0,
        params0=params0,
    )

    steady_times: List[float] = list()
    steady_y: np.ndarray = y_arr
    steady_dy: np.ndarray = dy_arr

    for _ in range(steady_repeats):
        run_s, _, y_tmp, dy_tmp = run_once(
            solver=solver,
            x0=x0,
            dx0=dx0,
            params0=params0,
        )
        steady_times.append(run_s)
        steady_y = y_tmp
        steady_dy = dy_tmp

    steady_run_s: float = float(np.mean(steady_times)) if steady_times else first_run_s
    steps: int = int(np.ceil(t_end / h))

    if not np.all(np.isfinite(steady_y)):
        raise RuntimeError(f"{backend} produced non-finite y values")
    if not np.all(np.isfinite(steady_dy)):
        raise RuntimeError(f"{backend} produced non-finite dy values")

    if hasattr(solver, "get_backend_build_stats"):
        build_stats: Dict[str, float] = solver.get_backend_build_stats()
    else:
        build_stats = dict()

    return {
        "backend": backend,
        "setup_s": setup_s,
        "first_run_s": first_run_s,
        "steady_run_s": steady_run_s,
        "one_shot_s": setup_s + first_run_s,
        "ms_per_step": 1000.0 * steady_run_s / max(steps, 1),
        "steps": steps,
        "t": t_arr,
        "y": steady_y,
        "dy": steady_dy,
        "build_stats": build_stats,
    }


def speedup(reference_s: float, candidate_s: float) -> float:
    if candidate_s <= 0.0:
        return np.inf
    return reference_s / candidate_s


@patch("matplotlib.pyplot.show")
def test_small_linear_chain_all_backends(mock_show) -> None:
    """
    Test all backends on small linear chain system.

    Verifies that all four solver backends (SD, AD, VEC, COMPILED)
    successfully simulate a small mechanical chain and produce finite results.
    """
    n_masses = 20
    h = 2e-5
    t_end = 1e-3
    method = DynamicIntegrationMethod.DaeTrapezoidal

    results = {}
    for backend in BACKEND_ORDER:
        result = measure_backend(
            backend=backend,
            n_masses=n_masses,
            t_end=t_end,
            h=h,
            method=method,
            steady_repeats=2,
        )
        results[backend] = result

        assert np.isfinite(result["setup_s"])
        assert np.isfinite(result["first_run_s"])
        assert np.isfinite(result["steady_run_s"])
        assert np.all(np.isfinite(result["y"]))


@patch("matplotlib.pyplot.show")
def test_large_linear_chain_all_backends(mock_show) -> None:
    """
    Test all backends on large linear chain system.

    Verifies scalability by running all backends on a larger
    80-mass system with finer time step.
    """
    n_masses = 80
    h = 1e-5
    t_end = 5e-3
    method = DynamicIntegrationMethod.DaeTrapezoidal

    results = {}
    for backend in BACKEND_ORDER:
        result = measure_backend(
            backend=backend,
            n_masses=n_masses,
            t_end=t_end,
            h=h,
            method=method,
            steady_repeats=2,
        )
        results[backend] = result

        assert np.isfinite(result["steady_run_s"])
        assert np.all(np.isfinite(result["y"]))


@patch("matplotlib.pyplot.show")
def test_sd_reference_produces_stable_solution(mock_show) -> None:
    """
    Test that SD solver produces stable solution.

    Verifies that the symbolic differentiable solver produces
    bounded, finite solutions without divergence.
    """
    n_masses = 20
    h = 2e-5
    t_end = 1e-3
    method = DynamicIntegrationMethod.DaeTrapezoidal

    result = measure_backend(
        backend="SD",
        n_masses=n_masses,
        t_end=t_end,
        h=h,
        method=method,
    )

    y = result["y"]
    assert np.all(np.isfinite(y))
    assert np.all(np.abs(y) < 1e6)


@patch("matplotlib.pyplot.show")
def test_backends_similar_to_reference(mock_show) -> None:
    """
    Test that all backends produce similar results to SD reference.

    Verifies numerical consistency between SD reference and
    AD, VEC, and COMPILED backends.
    """
    n_masses = 20
    h = 2e-5
    t_end = 1e-3
    method = DynamicIntegrationMethod.DaeTrapezoidal

    reference = measure_backend(
        backend="SD",
        n_masses=n_masses,
        t_end=t_end,
        h=h,
        method=method,
    )

    for backend in ["AD", "VEC", "COMPILED"]:
        result = measure_backend(
            backend=backend,
            n_masses=n_masses,
            t_end=t_end,
            h=h,
            method=method,
        )

        max_err = float(np.max(np.abs(reference["y"] - result["y"])))
        assert max_err < 1e-3, f"{backend} deviates from SD by {max_err}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
