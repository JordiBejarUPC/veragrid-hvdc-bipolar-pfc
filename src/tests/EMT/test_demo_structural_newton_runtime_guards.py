# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Any, cast
from unittest.mock import patch

import numpy as np
from scipy.sparse import csc_matrix

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonDiagnosticsConfig, NewtonTraceCollector
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


def build_decay_block(n_states: int = 2, k_val: float = 1.5) -> Block:
    """
    Build a simple decay block for testing Newton convergence.

    Creates a system of independent first-order decay equations
    for testing structural solver diagnostics.

    :param n_states: Number of decay state variables.
    :param k_val: Decay rate constant.
    :returns: Block representing the decay system.
    """
    k = Var("k")
    state_vars = []
    diff_vars = []
    state_eqs = []

    for i in range(n_states):
        x_i = Var(f"x_{i}")
        dx_i = Var(f"d_x_{i}", base_var=x_i)
        state_vars.append(x_i)
        diff_vars.append(dx_i)
        state_eqs.append(-k * x_i)

    parameters = dict()
    parameters[k] = Const(k_val)

    block = Block(
        name="DecayBlock",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters=parameters,
    )
    block.unify_blocks()
    return block


def build_scalar_state_block() -> Block:
    """
    Build a scalar state block for testing.

    Creates a minimal single-state system for testing
    structural solver backtracking and diagnostics.

    :returns: Block representing the scalar state system.
    """
    x = Var("x")
    dx = Var("d_x", base_var=x)
    block = Block(
        name="ScalarState",
        state_vars=[x],
        diff_vars=[dx],
        state_eqs=[Const(0.0)],
        parameters=dict(),
    )
    block.unify_blocks()
    return block


def build_singular_dae_block() -> Block:
    """
    Build a singular DAE block for index testing.

    Creates a minimal differential-algebraic equation system
    with singularity for testing index checking diagnostics.

    :returns: Block representing the singular DAE system.
    """
    x = Var("x")
    y = Var("y")
    dx = Var("d_x", base_var=x)
    block = Block(
        name="SingularDae",
        state_vars=[x],
        algebraic_vars=[y],
        diff_vars=[dx],
        state_eqs=[Const(0.0)],
        algebraic_eqs=[Const(0.0)],
        parameters=dict(),
    )
    block.unify_blocks()
    return block


class InexactCompiledResidualAssembler:
    """
    Inexact residual assembler for compiled structural solver testing.

    Provides a residual function that intentionally produces inaccurate
    results for testing Newton diagnostics and fallback mechanisms.

    :ivar _tag: Internal tag identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_inexact_residual"

    def evaluate(self, states, params, history, d_history, h, history2, data_out) -> None:
        """
        Compute inexact residual for testing.

        :param states: Current state vector.
        :param params: Parameter vector.
        :param history: History states.
        :param d_history: History derivatives.
        :param h: Time step.
        :param history2: Secondary history.
        :param data_out: Output residual vector.
        """
        _unused = (self._tag, params, history, d_history, h, history2)
        data_out[:] = 0.0
        data_out[0] = states[0] ** 2 - 1.0


class InexactCompiledJacobian:
    """
    Inexact Jacobian assembler for compiled structural solver testing.

    Provides an intentionally inaccurate Jacobian for testing
    Newton solver diagnostics.

    :ivar _tag: Internal tag identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_inexact_jacobian"

    def evaluate(self, states, params, history, d_history, h, history2) -> csc_matrix:
        """
        Compute inexact Jacobian matrix.

        :returns: Sparse Jacobian matrix.
        """
        _unused = (self._tag, params, history, d_history, h, history2)
        return csc_matrix([[0.2 * states[0]]], dtype=np.float64)

    def get_data_buffer(self) -> np.ndarray:
        """Return data buffer for Jacobian values."""
        _unused = self._tag
        return np.zeros(1, dtype=np.float64)


class SingularCompiledResidualAssembler:
    """
    Singular residual assembler for compiled structural solver testing.

    Produces a singular residual for testing index checking
    and singularity handling.

    :ivar _tag: Internal tag identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_singular_residual"

    def evaluate(self, states, params, history, d_history, h, history2, data_out) -> None:
        """
        Compute singular residual for testing.

        :param states: Current state vector.
        :param params: Parameter vector.
        :param history: History states.
        :param d_history: History derivatives.
        :param h: Time step.
        :param history2: Secondary history.
        :param data_out: Output residual vector.
        """
        _unused = (self._tag, states, params, history, d_history, h, history2)
        data_out[:] = 0.0
        data_out[0] = 1.0


class SingularCompiledJacobian:
    """
    Singular Jacobian assembler for compiled structural solver testing.

    Provides a near-singular Jacobian for testing singularity
    detection and handling.

    :ivar _tag: Internal tag identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_singular_jacobian"

    def evaluate(self, states, params, history, d_history, h, history2) -> csc_matrix:
        """
        Compute near-singular Jacobian matrix.

        :returns: Sparse near-singular Jacobian matrix.
        """
        _unused = (self._tag, states, params, history, d_history, h, history2)
        return csc_matrix(np.array([[1.0, 0.0], [0.0, 1.0e-16]], dtype=np.float64))

    def get_data_buffer(self) -> np.ndarray:
        """Return data buffer for Jacobian values."""
        _unused = self._tag
        return np.zeros(1, dtype=np.float64)


def inexact_vectorized_residual(x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, res_global, x_prev2) -> None:
    """
    Vectorized inexact residual function for testing.

    :param x_iter: Current iteration state.
    :param full_params: Full parameter vector.
    :param x_prev: Previous state.
    :param dx_prev: Previous derivative.
    :param h: Time step.
    :param vec_flat_args: Flattened vector arguments.
    :param res_global: Global residual output.
    :param x_prev2: Second previous state.
    """
    _unused = (full_params, x_prev, dx_prev, h, vec_flat_args, x_prev2)
    res_global[:] = 0.0
    res_global[0] = x_iter[0] ** 2 - 1.0


class InexactVectorizedJacobian:
    """
    Inexact Jacobian for vectorized structural solver testing.

    Provides an intentionally inaccurate Jacobian for testing
    vectorized Newton diagnostics.

    :ivar _tag: Internal tag identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "vectorized_inexact_jacobian"

    def __call__(self, states, params, history, d_history, h, history2=None) -> csc_matrix:
        """
        Compute inexact Jacobian.

        :returns: Sparse Jacobian matrix.
        """
        _unused = (self._tag, params, history, d_history, h, history2)
        return csc_matrix([[0.2 * states[0]]], dtype=np.float64)


def singular_vectorized_residual(x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, res_global, x_prev2) -> None:
    """
    Vectorized singular residual function for testing.

    :param x_iter: Current iteration state.
    :param full_params: Full parameter vector.
    :param x_prev: Previous state.
    :param dx_prev: Previous derivative.
    :param h: Time step.
    :param vec_flat_args: Flattened vector arguments.
    :param res_global: Global residual output.
    :param x_prev2: Second previous state.
    """
    _unused = (x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, x_prev2)
    res_global[:] = 0.0
    res_global[0] = 1.0


class SingularVectorizedJacobian:
    """
    Near-singular Jacobian for vectorized structural solver testing.

    Provides a near-singular Jacobian for testing singularity
    handling in vectorized solvers.

    :ivar _tag: Internal tag identifier.
    """
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "vectorized_singular_jacobian"

    def __call__(self, states, params, history, d_history, h, history2=None) -> csc_matrix:
        """
        Compute near-singular Jacobian.

        :returns: Sparse near-singular Jacobian matrix.
        """
        _unused = (self._tag, states, params, history, d_history, h, history2)
        return csc_matrix(np.array([[1.0, 0.0], [0.0, 1.0e-16]], dtype=np.float64))


def test_trace_demo_structural_vectorized() -> None:
    """
    Test Newton trace collection with vectorized structural solver.

    Verifies that the Newton trace collector properly records
    iteration information during simulation.
    """
    block = build_decay_block(n_states=2)
    problem = GenericEmtProblem(block, Var(f"t_trace_StructuralVectorized"))
    collector = NewtonTraceCollector()
    problem.set_newton_trace_collector(collector)

    common_kwargs = dict(
        problem=problem,
        t0=0.0,
        t_end=0.05,
        h=0.01,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=100,
        verbose=False,
    )

    solver = StructuralVectorizedSolver(auto_vectorization=True, **common_kwargs)

    x0 = np.array([1.0, -0.5], dtype=np.float64)
    dx0 = -1.5 * x0
    solver.simulate(x0=x0, dx0=dx0, params0=np.zeros(0, dtype=np.float64))

    assert len(collector.records) > 0


def test_trace_demo_structural_compiled() -> None:
    """
    Test Newton trace collection with compiled structural solver.

    Verifies that the Newton trace collector properly records
    iteration information in the compiled solver.
    """
    block = build_decay_block(n_states=2)
    problem = GenericEmtProblem(block, Var(f"t_trace_StructuralCompiled"))
    collector = NewtonTraceCollector()
    problem.set_newton_trace_collector(collector)

    common_kwargs = dict(
        problem=problem,
        t0=0.0,
        t_end=0.05,
        h=0.01,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=100,
        verbose=False,
    )

    solver = StructuralCompiledSolver(auto_build=True, **common_kwargs)

    x0 = np.array([1.0, -0.5], dtype=np.float64)
    dx0 = -1.5 * x0
    solver.simulate(x0=x0, dx0=dx0, params0=np.zeros(0, dtype=np.float64))

    assert len(collector.records) > 0


def test_backtracking_demo_structural_vectorized() -> None:
    """
    Test backtracking mechanism with inexact Jacobian.

    Verifies that the backtracking Newton diagnostics properly
    handle inexact Jacobian information.
    """
    cfg_bt = NewtonDiagnosticsConfig(
        enable_backtracking=True,
        backtracking_beta=0.5,
        backtracking_min_alpha=1e-3,
        backtracking_max_iter=8,
        compute_dense_cond=False,
        enable_fallback=False,
    )

    problem = GenericEmtProblem(build_scalar_state_block(), Var(f"t_bt_VEC"))

    solver_bt = StructuralVectorizedSolver(
        problem=problem,
        t0=0.0,
        t_end=0.1,
        h=0.1,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=100,
        verbose=False,
        auto_vectorization=False,
        newton_diag_config=cfg_bt,
    )
    solver_bt.vectorized_ready = True
    solver_bt.vec_flat_args = np.zeros(0, dtype=np.float64)
    solver_bt.fused_residual = inexact_vectorized_residual
    solver_bt.vec_jacobian = InexactVectorizedJacobian()

    _, y_bt, _ = solver_bt.simulate(
        x0=np.array([0.1], dtype=np.float64),
        dx0=np.array([0.0], dtype=np.float64),
        params0=np.zeros(0, dtype=np.float64),
    )

    res_bt = abs(float(y_bt[-1, 0] ** 2 - 1.0))

    assert np.isfinite(res_bt)


def test_index1_guard_structural_vectorized() -> None:
    """
    Test index-1 DAE guard with singular system.

    Verifies that the structural solver properly detects and raises
    an error for singular DAE systems that violate index-1 constraints.
    """
    cfg_idx = NewtonDiagnosticsConfig(
        enable_index1_check=True,
        index1_max_block_n=8,
        compute_dense_cond=False,
        enable_fallback=False,
    )

    problem = GenericEmtProblem(build_singular_dae_block(), Var(f"t_idx_VEC"))

    solver = StructuralVectorizedSolver(
        problem=problem,
        t0=0.0,
        t_end=0.1,
        h=0.1,
        method=DynamicIntegrationMethod.DaeBackEuler,
        dense_threshold=0,
        verbose=False,
        auto_vectorization=False,
        newton_diag_config=cfg_idx,
    )
    solver.vectorized_ready = True
    solver.vec_flat_args = np.zeros(0, dtype=np.float64)
    solver.fused_residual = singular_vectorized_residual
    solver.vec_jacobian = SingularVectorizedJacobian()

    try:
        solver.simulate(
            x0=np.array([0.0, 0.0], dtype=np.float64),
            dx0=np.array([0.0], dtype=np.float64),
            params0=np.zeros(0, dtype=np.float64),
        )
        assert False, "Expected RuntimeError to be raised"
    except RuntimeError:
        pass


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
