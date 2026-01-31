import numpy as np
import pytest

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    JacobianBackend,
)

# ==============================================================================
# Helpers
# ==============================================================================

def build_buck():
    """
    Simple Buck converter used consistently across all tests.
    """
    i_L = Var("i_L")
    v_C = Var("v_C")

    Vin = Var("Vin_sw")
    R = Var("R")
    L = Var("L")
    C = Var("C")

    block = Block(
        name="Buck",
        state_vars=[i_L, v_C],
        state_eqs=[
            (Vin - v_C) / L,
            (i_L - v_C / R) / C,
        ],
        parameters={
            Vin: Const(0.0),
            R: Const(5.0),
            L: Const(100e-6),
            C: Const(470e-6),
        },
    )

    return block, Vin


def build_params(solver: BlockSolver):
    """
    Builds a physically valid parameter vector:
    [event_params | static_params]
    """
    ev = np.zeros(len(solver._event_parameters))
    static = np.array([p.value for p in solver._parameters_values])
    return np.concatenate((ev, static))


# ==============================================================================
# Tests
# ==============================================================================

def test_jacobian_backend_constructor():
    """
    Solver should accept explicit backend selection.
    """
    block, _ = build_buck()
    t = Var("t")

    solver = BlockSolver(
        block_system=block,
        glob_time=t,
        jacobian_backend=JacobianBackend.Automatic,
    )

    assert solver._jacobian_backend == JacobianBackend.Automatic


def test_residual_symbolic_vs_ad():
    """
    Residuals produced by Symbolic and AD kernels must match.
    """
    block, _ = build_buck()
    t = Var("t")

    solver_sym = BlockSolver(
        block_system=block,
        glob_time=t,
        jacobian_backend=JacobianBackend.Symbolic,
    )

    solver_ad = BlockSolver(
        block_system=block,
        glob_time=t,
        jacobian_backend=JacobianBackend.Automatic,
    )

    method = DynamicIntegrationMethod.Trapezoid.value
    h = 1e-6

    # Force compilation
    solver_sym._build_jit_kernel(method)
    solver_ad._build_jit_ad(method)

    x = np.array([1.0, 2.0])
    dx = np.zeros_like(x)

    params_sym = build_params(solver_sym)
    params_ad  = build_params(solver_ad)

    res_sym = solver_sym.jit_kernels[method](x, params_sym, x, dx, h, x)
    res_ad  = solver_ad.jit_kernels_ad[method](x, params_ad, x, dx, h, x)

    np.testing.assert_allclose(res_sym, res_ad, rtol=1e-9, atol=1e-12)


def test_ad_jacobian_is_finite():
    """
    AD Jacobian must be finite and well-formed.
    """
    block, _ = build_buck()
    t = Var("t")

    solver = BlockSolver(
        block_system=block,
        glob_time=t,
        jacobian_backend=JacobianBackend.Automatic,
    )

    method = DynamicIntegrationMethod.Trapezoid.value
    h = 1e-6

    solver._build_jit_ad(method)

    x = np.array([0.5, 3.0])
    dx = np.zeros_like(x)
    params = build_params(solver)

    J = solver.jit_jacobians_ad[method](
        states=x,
        params=params,
        history=x,
        d_history=dx,
        h=h,
        history2=x,
    )

    assert J.shape == (solver._n_vars, solver._n_vars)
    assert np.all(np.isfinite(J.data))


@pytest.mark.parametrize("backend", ["symbolic", "automatic"])
def test_simulation_runs(backend):
    """
    Minimal EMT simulation must run for both Jacobian backends.
    """
    block, _ = build_buck()
    t = Var("t")

    solver = BlockSolver(
        block_system=block,
        glob_time=t,
        jacobian_backend=(
            JacobianBackend.Symbolic
            if backend == "symbolic"
            else JacobianBackend.Automatic
        ),
    )

    x0 = np.zeros(solver._n_vars)

    t_arr, y_arr = solver.simulate_unified(
        t0=0.0,
        t_end=50e-6,
        h=1e-6,
        x0=x0,
        dx0=None,
        params0=None,
        method=DynamicIntegrationMethod.Trapezoid,
        boundary_update_fn=None,
        verbose=False,
        dense_threshold=50,
    )

    assert t_arr.shape[0] == y_arr.shape[0]
    assert np.all(np.isfinite(y_arr))
