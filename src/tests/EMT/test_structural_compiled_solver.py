# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import unittest
from typing import List, Sequence, Tuple

import numba as nb
import numpy as np

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.diagnostic import (
    NewtonDiagnosticsConfig,
    NewtonTraceCollector,
    maybe_apply_backtracking,
    maybe_check_index1,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.Symbolic.jit_compiler import EagerEquationCompiler
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import (
    StructuralCompiledBoundaryUpdateWrapper,
    StructuralCompiledSolver,
)
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


def build_full_params(problem: EmtProblemTemplate) -> np.ndarray:
    ev = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)
    static_vals = np.array([float(p.value) for p in problem.get_parameters_values()], dtype=np.float64)
    return np.concatenate((ev, static_vals))


def build_repeated_decay_block(n_states: int = 4, k_val: float = 2.0) -> Tuple[Block, Var]:
    k: Var = Var("k")
    state_vars: List[Var] = list()
    diff_vars: List[Var] = list()
    state_eqs: List[Expr] = list()

    for i in range(n_states):
        x_i: Var = Var(f"x_{i}")
        dx_i: Var = Var(f"d_x_{i}", base_var=x_i)
        state_vars.append(x_i)
        diff_vars.append(dx_i)
        state_eqs.append(-k * x_i)

    block: Block = Block(
        name="RepeatedDecay",
        state_vars=state_vars,
        state_eqs=state_eqs,
        diff_vars=diff_vars,
        parameters={k: Const(k_val)},
    )
    block.unify_blocks()
    return block, k


def build_zero_dynamics_block() -> Block:
    x: Var = Var("x")
    dx: Var = Var("d_x", base_var=x)

    block: Block = Block(
        name="ZeroDynamics",
        state_vars=[x],
        state_eqs=[Const(0.0)],
        diff_vars=[dx],
        parameters=dict(),
    )
    block.unify_blocks()
    return block


def array_ptr(arr: np.ndarray) -> int:
    return int(arr.__array_interface__["data"][0])


class ForcedEventTracker(StructuralCompiledBoundaryUpdateWrapper):
    __slots__ = ["_forced_times", "_tol", "_cursor", "query_calls", "update_calls"]

    def __init__(self, forced_times: Sequence[float], tol: float = 1e-12) -> None:
        self._forced_times = [float(v) for v in forced_times]
        self._tol = float(tol)
        self._cursor = 0
        self.query_calls: List[Tuple[float, float]] = list()
        self.update_calls: List[float] = list()

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> float | None:
        self.query_calls.append((float(t_prev), float(t_target)))

        idx: int = self._cursor
        while idx < len(self._forced_times):
            event_time: float = self._forced_times[idx]
            if (t_prev + self._tol) < event_time <= (t_target + self._tol):
                return event_time
            idx += 1

        return None

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        _unused = (x, params)
        t_float: float = float(t)
        self.update_calls.append(t_float)

        while self._cursor < len(self._forced_times):
            if self._forced_times[self._cursor] <= t_float + self._tol:
                self._cursor += 1
            else:
                break


class TestStructuralCompiledSolver(unittest.TestCase):

    def test_eager_compiler_smoke_for_residual_ad_and_matrix_kernels(self) -> None:
        x: Var = Var("x")
        dx: Var = Var("d_x", base_var=x)
        k: Var = Var("k")
        eq: Expr = dx + k * x

        compiler = EagerEquationCompiler(
            variables=[x],
            parameters=[k],
            method=DynamicIntegrationMethod.DaeBackEuler,
        )

        states = np.array([2.0], dtype=np.float64)
        params = np.array([3.0], dtype=np.float64)
        history = np.array([1.0], dtype=np.float64)
        d_history = np.zeros(1, dtype=np.float64)
        history2 = history.copy()

        py_res, sig_res = compiler.compile(
            equations=[eq],
            func_name="unit_test_compiled_eager_residual",
            use_cse=True,
            offset=0,
            inplace=True,
        )
        res_fn = nb.njit(sig_res, cache=False, fastmath=True)(py_res)
        residual_out = np.zeros(1, dtype=np.float64)
        res_fn(states, params, history, d_history, 0.5, residual_out, history2)

        self.assertAlmostEqual(float(residual_out[0]), 8.0, places=12)

        py_ad, sig_ad = compiler.compile_ad_kernel(
            equations=[eq],
            func_name="unit_test_compiled_eager_ad",
            use_cse=True,
            active_indices={0},
        )
        ad_fn = nb.njit(sig_ad, cache=False, fastmath=True)(py_ad)
        jvp_out = np.zeros(1, dtype=np.float64)
        seeds = np.zeros(1, dtype=np.float64)
        ad_fn(states, seeds, params, history, d_history, 0.5, jvp_out, history2)

        self.assertAlmostEqual(float(jvp_out[0]), 5.0, places=12)

        py_mat, sig_mat = compiler.compile_matrix_kernel(
            template_eq=eq,
            func_name="unit_test_compiled_eager_matrix",
            template_vars=[x],
        )
        mat_fn = nb.njit(sig_mat, cache=False, fastmath=True)(py_mat)

        grouped_states = np.array([2.0, 4.0], dtype=np.float64)
        grouped_history = np.array([1.0, 3.0], dtype=np.float64)
        grouped_d_history = np.zeros(2, dtype=np.float64)
        grouped_history2 = grouped_history.copy()
        grouped_indices = np.array([[0], [1]], dtype=np.int32)
        grouped_out = np.zeros(2, dtype=np.float64)

        mat_fn(
            grouped_states,
            params,
            grouped_history,
            grouped_d_history,
            0.5,
            grouped_indices,
            grouped_out,
            grouped_history2,
        )

        np.testing.assert_allclose(
            grouped_out,
            np.array([8.0, 14.0], dtype=np.float64),
            rtol=0.0,
            atol=1e-12,
        )

    def test_structural_compiled_backend_builds_and_collapses_repeated_structure(self) -> None:
        block, _ = build_repeated_decay_block(n_states=4, k_val=2.0)
        problem = GenericEmtProblem(block, Var("t_glob"))

        solver = StructuralCompiledSolver(
            problem=problem,
            t0=0.0,
            t_end=1e-3,
            h=1e-4,
            method=DynamicIntegrationMethod.DaeBackEuler,
            dense_threshold=100,
            verbose=False,
            auto_build=True,
        )

        self.assertTrue(solver.is_vectorized_ready())
        self.assertIsNotNone(solver._residual_assembler)
        self.assertIsNotNone(solver._jacobian_evaluator)
        self.assertEqual(len(solver._residual_assembler._kernel_specs), 1)
        self.assertEqual(solver.get_residual_buffer().shape, (4,))
        self.assertGreater(solver.get_jacobian_data_buffer().size, 0)
        self.assertTrue(
            np.shares_memory(
                solver.get_jacobian_data_buffer(),
                solver._jacobian_evaluator.get_data_buffer(),
            )
        )
        self.assertEqual(solver._residual_assembler.get_work_buffer().shape[0], 1)

    def test_structural_compiled_residual_and_jacobian_buffers_are_reused_in_place(self) -> None:
        block, _ = build_repeated_decay_block(n_states=3, k_val=2.0)
        problem = GenericEmtProblem(block, Var("t_glob"))

        solver = StructuralCompiledSolver(
            problem=problem,
            t0=0.0,
            t_end=1e-3,
            h=1e-4,
            method=DynamicIntegrationMethod.DaeBackEuler,
            dense_threshold=100,
            verbose=False,
            auto_build=True,
        )

        full_params = build_full_params(problem)
        x = np.array([1.0, -0.5, 2.0], dtype=np.float64)
        dx = np.zeros_like(x)
        history2 = x.copy()

        residual_ptr_before = array_ptr(solver.get_residual_buffer())
        work_ptr_before = array_ptr(solver._residual_assembler.get_work_buffer())
        jac_data_ptr_before = array_ptr(solver.get_jacobian_data_buffer())

        solver._residual_assembler.evaluate(
            x,
            full_params,
            x,
            dx,
            1e-4,
            history2,
            solver.get_residual_buffer(),
        )
        jacobian_1 = solver._jacobian_evaluator.evaluate(
            x,
            full_params,
            x,
            dx,
            1e-4,
            history2,
        )

        x_2 = np.array([0.75, -0.25, 1.5], dtype=np.float64)
        history2_2 = x_2.copy()

        solver._residual_assembler.evaluate(
            x_2,
            full_params,
            x_2,
            dx,
            1e-4,
            history2_2,
            solver.get_residual_buffer(),
        )
        jacobian_2 = solver._jacobian_evaluator.evaluate(
            x_2,
            full_params,
            x_2,
            dx,
            1e-4,
            history2_2,
        )

        self.assertEqual(array_ptr(solver.get_residual_buffer()), residual_ptr_before)
        self.assertEqual(array_ptr(solver._residual_assembler.get_work_buffer()), work_ptr_before)
        self.assertEqual(array_ptr(solver.get_jacobian_data_buffer()), jac_data_ptr_before)
        self.assertIs(jacobian_1, jacobian_2)
        self.assertTrue(np.all(np.isfinite(solver.get_residual_buffer())))
        self.assertTrue(np.all(np.isfinite(jacobian_2.data)))

    def test_structural_compiled_jacobian_matches_structural_vectorized_backend_and_csc_layout(self) -> None:
        block_fast, _ = build_repeated_decay_block(n_states=4, k_val=2.0)
        block_base, _ = build_repeated_decay_block(n_states=4, k_val=2.0)

        problem_fast = GenericEmtProblem(block_fast, Var("t_fast"))
        problem_base = GenericEmtProblem(block_base, Var("t_base"))

        compiled_solver = StructuralCompiledSolver(
            problem=problem_fast,
            t0=0.0,
            t_end=1e-3,
            h=1e-4,
            method=DynamicIntegrationMethod.DaeBackEuler,
            dense_threshold=100,
            verbose=False,
            auto_build=True,
        )
        base_solver = StructuralVectorizedSolver(
            problem=problem_base,
            t0=0.0,
            t_end=1e-3,
            h=1e-4,
            method=DynamicIntegrationMethod.DaeBackEuler,
            dense_threshold=100,
            verbose=False,
            auto_vectorization=True,
        )

        x = np.array([1.0, -0.5, 2.0, 0.25], dtype=np.float64)
        dx = np.zeros_like(x)
        full_params_fast = build_full_params(problem_fast)
        full_params_base = build_full_params(problem_base)
        history2 = x.copy()

        j_compiled = compiled_solver._jacobian_evaluator.evaluate(
            x,
            full_params_fast,
            x,
            dx,
            1e-4,
            history2,
        )
        j_base = base_solver.vec_jacobian(
            states=x,
            params=full_params_base,
            history=x,
            d_history=dx,
            h=1e-4,
            history2=history2,
        )

        self.assertEqual(j_compiled.shape, j_base.shape)
        self.assertTrue(np.array_equal(j_compiled.indptr, j_base.indptr))
        self.assertTrue(np.array_equal(j_compiled.indices, j_base.indices))
        np.testing.assert_allclose(j_compiled.data, j_base.data, rtol=1e-11, atol=1e-12)

    def test_structural_compiled_simulation_matches_structural_vectorized_solver(self) -> None:
        block_fast, k_fast = build_repeated_decay_block(n_states=3, k_val=1.5)
        block_base, _ = build_repeated_decay_block(n_states=3, k_val=1.5)

        problem_fast = GenericEmtProblem(block_fast, Var("t_fast"))
        problem_base = GenericEmtProblem(block_base, Var("t_base"))

        x0 = np.array([1.0, -0.5, 2.0], dtype=np.float64)
        dx0 = -1.5 * x0
        p0_fast = np.zeros(problem_fast.get_variable_parameter_number(), dtype=np.float64)
        p0_base = np.zeros(problem_base.get_variable_parameter_number(), dtype=np.float64)

        compiled_solver = StructuralCompiledSolver(
            problem=problem_fast,
            t0=0.0,
            t_end=0.2,
            h=0.01,
            method=DynamicIntegrationMethod.DaeTrapezoidal,
            pred_method=DynamicIntegrationMethod.OdeEuler,
            dense_threshold=100,
            verbose=False,
            auto_build=True,
        )
        base_solver = StructuralVectorizedSolver(
            problem=problem_base,
            t0=0.0,
            t_end=0.2,
            h=0.01,
            method=DynamicIntegrationMethod.DaeTrapezoidal,
            pred_method=DynamicIntegrationMethod.OdeEuler,
            dense_threshold=100,
            verbose=False,
            auto_vectorization=True,
        )

        t_compiled, y_compiled, dy_compiled = compiled_solver.simulate(x0=x0, dx0=dx0, params0=p0_fast)
        t_base, y_base, dy_base = base_solver.simulate(x0=x0.copy(), dx0=dx0.copy(), params0=p0_base)

        np.testing.assert_allclose(t_compiled, t_base, rtol=0.0, atol=0.0)
        np.testing.assert_allclose(y_compiled, y_base, rtol=1e-9, atol=1e-10)
        np.testing.assert_allclose(dy_compiled, dy_base, rtol=1e-9, atol=1e-10)
        self.assertGreater(compiled_solver.get_last_sim_loop_time(), 0.0)

    def test_structural_compiled_solver_uses_forced_alignment_and_boundary_updates(self) -> None:
        block = build_zero_dynamics_block()
        problem = GenericEmtProblem(block, Var("t_glob"))

        solver = StructuralCompiledSolver(
            problem=problem,
            t0=0.0,
            t_end=0.2,
            h=0.1,
            method=DynamicIntegrationMethod.DaeBackEuler,
            dense_threshold=100,
            verbose=False,
            auto_build=True,
        )

        updater = ForcedEventTracker(forced_times=[0.05, 0.15])

        x0 = np.array([1.234], dtype=np.float64)
        dx0 = np.array([0.0], dtype=np.float64)
        p0 = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)

        t, y, dy = solver.simulate(
            x0=x0,
            dx0=dx0,
            params0=p0,
            boundary_updater=updater,
        )

        np.testing.assert_allclose(t, np.array([0.0, 0.1, 0.2], dtype=np.float64), rtol=0.0, atol=0.0)
        np.testing.assert_allclose(y[:, 0], np.array([1.234, 1.234, 1.234], dtype=np.float64), rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(dy[:, 0], np.array([0.0, 0.0, 0.0], dtype=np.float64), rtol=0.0, atol=1e-12)

        self.assertGreaterEqual(len(updater.query_calls), 4)
        np.testing.assert_allclose(
            np.array(updater.update_calls, dtype=np.float64),
            np.array([0.0, 0.05, 0.10, 0.15, 0.20], dtype=np.float64),
            rtol=0.0,
            atol=1e-12,
        )

        rounded_updates = [round(v, 8) for v in updater.update_calls]
        self.assertIn(0.05, rounded_updates)
        self.assertIn(0.15, rounded_updates)

    def test_structural_solvers_record_newton_trace_data(self) -> None:
        for solver_class in (StructuralVectorizedSolver, StructuralCompiledSolver):
            with self.subTest(solver=solver_class.__name__):
                block, _ = build_repeated_decay_block(n_states=2, k_val=1.5)
                problem = GenericEmtProblem(block, Var(f"t_{solver_class.__name__}"))
                collector = NewtonTraceCollector()
                problem.set_newton_trace_collector(collector)

                solver = solver_class(
                    problem=problem,
                    t0=0.0,
                    t_end=0.05,
                    h=0.01,
                    method=DynamicIntegrationMethod.DaeTrapezoidal,
                    pred_method=DynamicIntegrationMethod.OdeEuler,
                    dense_threshold=100,
                    verbose=False,
                )

                x0 = np.array([1.0, 0.5], dtype=np.float64)
                dx0 = -1.5 * x0
                p0 = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)

                solver.simulate(x0=x0, dx0=dx0, params0=p0)

                self.assertGreater(len(collector.records), 0)
                self.assertIn("solver", collector.records[0])
                self.assertIn("res_norm_inf", collector.records[0])

    def test_runtime_index1_check_detects_singular_algebraic_block(self) -> None:
        jacobian = np.array(
            [
                [1.0, 0.0],
                [0.0, 0.0],
            ],
            dtype=np.float64,
        )
        config = NewtonDiagnosticsConfig(
            enable_index1_check=True,
            index1_max_block_n=10,
            enable_fallback=False,
            compute_dense_cond=False,
        )

        with self.assertRaises(RuntimeError):
            maybe_check_index1(jacobian, n_state=1, config=config)

    def test_backtracking_helper_reduces_step_when_full_newton_worsens_residual(self) -> None:
        x_iter = np.array([0.0], dtype=np.float64)
        delta = np.array([10.0], dtype=np.float64)
        trial_x = np.zeros(1, dtype=np.float64)
        trial_res = np.zeros(1, dtype=np.float64)
        config = NewtonDiagnosticsConfig(
            enable_backtracking=True,
            backtracking_beta=0.5,
            backtracking_min_alpha=1.0e-3,
            backtracking_max_iter=6,
            enable_fallback=False,
            compute_dense_cond=False,
        )

        def evaluate_residual(candidate_x: np.ndarray, out_res: np.ndarray) -> float:
            out_res[0] = (candidate_x[0] - 1.0) ** 2
            return float(abs(out_res[0]))

        maybe_apply_backtracking(
            x_iter,
            delta,
            res_norm=1.0,
            trial_x=trial_x,
            trial_res=trial_res,
            evaluate_residual=evaluate_residual,
            config=config,
        )

        self.assertLess(abs(x_iter[0] - 1.0), abs(10.0 - 1.0))
        self.assertLess((x_iter[0] - 1.0) ** 2, 1.0)


if __name__ == "__main__":
    unittest.main()
