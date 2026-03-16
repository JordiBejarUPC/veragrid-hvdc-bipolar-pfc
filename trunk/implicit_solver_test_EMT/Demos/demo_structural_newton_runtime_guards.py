from __future__ import annotations

import os
import sys
from typing import Any, cast

import numpy as np
from scipy.sparse import csc_matrix


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

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

    block = Block(
        name="DecayBlock",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters={k: Const(k_val)},
    )
    block.unify_blocks()
    return block


def build_scalar_state_block() -> Block:
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
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_inexact_residual"

    def evaluate(self, states, params, history, d_history, h, history2, data_out) -> None:
        _unused = (self._tag, params, history, d_history, h, history2)
        data_out[:] = 0.0
        data_out[0] = states[0] ** 2 - 1.0


class InexactCompiledJacobian:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_inexact_jacobian"

    def evaluate(self, states, params, history, d_history, h, history2) -> csc_matrix:
        _unused = (self._tag, params, history, d_history, h, history2)
        return csc_matrix([[0.2 * states[0]]], dtype=np.float64)

    def get_data_buffer(self) -> np.ndarray:
        _unused = self._tag
        return np.zeros(1, dtype=np.float64)


class SingularCompiledResidualAssembler:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_singular_residual"

    def evaluate(self, states, params, history, d_history, h, history2, data_out) -> None:
        _unused = (self._tag, states, params, history, d_history, h, history2)
        data_out[:] = 0.0
        data_out[0] = 1.0


class SingularCompiledJacobian:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "compiled_singular_jacobian"

    def evaluate(self, states, params, history, d_history, h, history2) -> csc_matrix:
        _unused = (self._tag, states, params, history, d_history, h, history2)
        return csc_matrix(np.array([[1.0, 0.0], [0.0, 1.0e-16]], dtype=np.float64))

    def get_data_buffer(self) -> np.ndarray:
        _unused = self._tag
        return np.zeros(1, dtype=np.float64)


def inexact_vectorized_residual(x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, res_global, x_prev2) -> None:
    _unused = (full_params, x_prev, dx_prev, h, vec_flat_args, x_prev2)
    res_global[:] = 0.0
    res_global[0] = x_iter[0] ** 2 - 1.0


class InexactVectorizedJacobian:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "vectorized_inexact_jacobian"

    def __call__(self, states, params, history, d_history, h, history2=None) -> csc_matrix:
        _unused = (self._tag, params, history, d_history, h, history2)
        return csc_matrix([[0.2 * states[0]]], dtype=np.float64)


def singular_vectorized_residual(x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, res_global, x_prev2) -> None:
    _unused = (x_iter, full_params, x_prev, dx_prev, h, vec_flat_args, x_prev2)
    res_global[:] = 0.0
    res_global[0] = 1.0


class SingularVectorizedJacobian:
    __slots__ = ["_tag"]

    def __init__(self) -> None:
        self._tag = "vectorized_singular_jacobian"

    def __call__(self, states, params, history, d_history, h, history2=None) -> csc_matrix:
        _unused = (self._tag, states, params, history, d_history, h, history2)
        return csc_matrix(np.array([[1.0, 0.0], [0.0, 1.0e-16]], dtype=np.float64))


def print_header(title: str) -> None:
    print("\n" + "=" * 96)
    print(title)
    print("=" * 96)


def run_trace_demo() -> None:
    print_header("Demo 1 - NewtonTraceCollector on structural solvers")

    for solver_name, solver_class in (
        ("StructuralVectorized", StructuralVectorizedSolver),
        ("StructuralCompiled", StructuralCompiledSolver),
    ):
        block = build_decay_block(n_states=2)
        problem = GenericEmtProblem(block, Var(f"t_trace_{solver_name}"))
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

        if solver_class is StructuralVectorizedSolver:
            solver = solver_class(auto_vectorization=True, **common_kwargs)
        else:
            solver = solver_class(auto_build=True, **common_kwargs)

        x0 = np.array([1.0, -0.5], dtype=np.float64)
        dx0 = -1.5 * x0
        solver.simulate(x0=x0, dx0=dx0, params0=np.zeros(0, dtype=np.float64))

        print(f"\n[{solver_name}] collected {len(collector.records)} Newton records")
        if collector.records:
            first = collector.records[0]
            print("  first record:")
            for key in ("t", "step", "newton_iter", "solver", "res_norm_inf", "used_fallback"):
                print(f"    {key}: {first.get(key)}")


def run_backtracking_demo() -> None:
    print_header("Demo 2 - Backtracking improves a difficult Newton solve")

    cfg_bt = NewtonDiagnosticsConfig(
        enable_backtracking=True,
        backtracking_beta=0.5,
        backtracking_min_alpha=1e-3,
        backtracking_max_iter=8,
        compute_dense_cond=False,
        enable_fallback=False,
    )

    for solver_name, solver_class in (
        ("StructuralVectorized", StructuralVectorizedSolver),
        ("StructuralCompiled", StructuralCompiledSolver),
    ):
        problem = GenericEmtProblem(build_scalar_state_block(), Var(f"t_bt_{solver_name}"))

        if solver_class is StructuralVectorizedSolver:
            solver_plain = solver_class(
                problem=problem,
                t0=0.0,
                t_end=0.1,
                h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler,
                dense_threshold=100,
                verbose=False,
                auto_vectorization=False,
                newton_diag_config=NewtonDiagnosticsConfig(enable_backtracking=False),
            )
            solver_plain.vectorized_ready = True
            solver_plain.vec_flat_args = np.zeros(0, dtype=np.float64)
            solver_plain.fused_residual = inexact_vectorized_residual
            solver_plain.vec_jacobian = InexactVectorizedJacobian()

            solver_bt = solver_class(
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
        else:
            solver_plain = solver_class(
                problem=problem,
                t0=0.0,
                t_end=0.1,
                h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler,
                dense_threshold=100,
                verbose=False,
                auto_build=False,
                newton_diag_config=NewtonDiagnosticsConfig(enable_backtracking=False),
            )
            solver_plain._vectorized_ready = True
            solver_plain._residual_assembler = cast(Any, InexactCompiledResidualAssembler())
            solver_plain._jacobian_evaluator = cast(Any, InexactCompiledJacobian())

            solver_bt = solver_class(
                problem=problem,
                t0=0.0,
                t_end=0.1,
                h=0.1,
                method=DynamicIntegrationMethod.DaeBackEuler,
                dense_threshold=100,
                verbose=False,
                auto_build=False,
                newton_diag_config=cfg_bt,
            )
            solver_bt._vectorized_ready = True
            solver_bt._residual_assembler = cast(Any, InexactCompiledResidualAssembler())
            solver_bt._jacobian_evaluator = cast(Any, InexactCompiledJacobian())

        _, y_plain, _ = solver_plain.simulate(
            x0=np.array([0.1], dtype=np.float64),
            dx0=np.array([0.0], dtype=np.float64),
            params0=np.zeros(0, dtype=np.float64),
        )
        _, y_bt, _ = solver_bt.simulate(
            x0=np.array([0.1], dtype=np.float64),
            dx0=np.array([0.0], dtype=np.float64),
            params0=np.zeros(0, dtype=np.float64),
        )

        res_plain = abs(float(y_plain[-1, 0] ** 2 - 1.0))
        res_bt = abs(float(y_bt[-1, 0] ** 2 - 1.0))

        print(f"\n[{solver_name}]")
        print(f"  without backtracking residual: {res_plain:.6e}")
        print(f"  with backtracking residual   : {res_bt:.6e}")
        print(f"  final state without BT       : {y_plain[-1, 0]:.6e}")
        print(f"  final state with BT          : {y_bt[-1, 0]:.6e}")


def run_index1_guard_demo() -> None:
    print_header("Demo 3 - Runtime index-1 guard catches singular algebraic block")

    cfg_idx = NewtonDiagnosticsConfig(
        enable_index1_check=True,
        index1_max_block_n=8,
        compute_dense_cond=False,
        enable_fallback=False,
    )

    for solver_name, solver_class in (
        ("StructuralVectorized", StructuralVectorizedSolver),
        ("StructuralCompiled", StructuralCompiledSolver),
    ):
        problem = GenericEmtProblem(build_singular_dae_block(), Var(f"t_idx_{solver_name}"))

        try:
            if solver_class is StructuralVectorizedSolver:
                solver = solver_class(
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
            else:
                solver = solver_class(
                    problem=problem,
                    t0=0.0,
                    t_end=0.1,
                    h=0.1,
                    method=DynamicIntegrationMethod.DaeBackEuler,
                    dense_threshold=0,
                    verbose=False,
                    auto_build=False,
                    newton_diag_config=cfg_idx,
                )
                solver._vectorized_ready = True
                solver._residual_assembler = cast(Any, SingularCompiledResidualAssembler())
                solver._jacobian_evaluator = cast(Any, SingularCompiledJacobian())

            solver.simulate(
                x0=np.array([0.0, 0.0], dtype=np.float64),
                dx0=np.array([0.0], dtype=np.float64),
                params0=np.zeros(0, dtype=np.float64),
            )
            print(f"[{solver_name}] guard did NOT trigger (unexpected)")
        except RuntimeError as exc:
            print(f"[{solver_name}] expected runtime guard: {exc}")


def main() -> None:
    print_header("Structural Solver Diagnostics Demo")
    print("This demo exercises the new structural-solver runtime guards:")
    print("- NewtonTraceCollector integration")
    print("- optional backtracking line-search")
    print("- optional runtime index-1 validation")

    run_trace_demo()
    run_backtracking_demo()
    run_index1_guard_demo()


if __name__ == "__main__":
    main()
