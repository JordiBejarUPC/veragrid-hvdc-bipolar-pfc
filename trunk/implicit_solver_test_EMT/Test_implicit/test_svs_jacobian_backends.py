import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.base_problem import BaseProblem
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver

# ==============================================================================
# Helpers
# ==============================================================================

def build_buck():
    """Simple Buck converter for testing."""
    i_L, v_C = Var("i_L"), Var("v_C")
    Vin, R, L, C = Var("Vin_sw"), Var("R"), Var("L"), Var("C")

    block = Block(
        name="Buck",
        state_vars=[i_L, v_C],
        state_eqs=[(Vin - v_C) / L, (i_L - v_C / R) / C],
        parameters={Vin: Const(0.0), R: Const(5.0), L: Const(100e-6), C: Const(470e-6)}
    )
    block.unify_blocks()
    return block

def get_full_params(solver):
    """
    Builds the FULL parameter vector [variable_params | static_params].
    This prevents division by zero in Jacobian kernels.
    """
    ev_params = np.zeros(len(solver._event_parameters))
    static_params = np.array([p.value for p in solver._parameters_values])
    return np.concatenate((ev_params, static_params))


# ==============================================================================
# Tests for StructuralVectorizedSolver
# ==============================================================================

def test_svs_clustering_and_jacobian():
    """
    Validates that SVS performs clustering and produces a well-formed Sparse Jacobian.
    """
    block = build_buck()
    t_sys = Var("t_sys")
    problem = BaseProblem(block, t_sys)

    solver = StructuralVectorizedSolver(
        problem, t0=0.0, t_end=1e-3, h=1e-6, integration_method="trapezoidal"
    )

    x = problem.get_x0()
    dx = np.zeros_like(x)

    p_full = get_full_params(solver)

    # Verify clustering detection
    assert hasattr(solver, 'vec_kernels')
    assert len(solver.vec_kernels) > 0

    J = solver.vec_jacobian(states=x, params=p_full, history=x, d_history=dx, h=1e-6)

    assert J.shape == (len(x), len(x))
    assert np.all(np.isfinite(J.data)), f"Jacobian contains non-finite values: {J.data}"


def test_svs_simulation_consistency():
    """
    Ensures SVS simulation runs without divergence in a standard EMT case.
    """
    block = build_buck()
    t_sys = Var("t_sys")
    problem = BaseProblem(block, t_sys)
    x0 = problem.get_x0()
    p0 = np.zeros(problem.get_variable_parameter_number())

    solver = StructuralVectorizedSolver(
        problem, t0=0.0, t_end=50e-6, h=1e-6, integration_method="trapezoidal"
    )

    t_arr, y_arr = solver.simulate(x0=x0, params0=p0)

    assert len(t_arr) == y_arr.shape[0]
    assert np.all(np.isfinite(y_arr))