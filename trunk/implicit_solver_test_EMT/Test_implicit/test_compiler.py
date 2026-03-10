# ==============================================================================
# Module: Structural Compiler Verification Suite
# ==============================================================================

import unittest
import numpy as np
import numba as nb
from typing import List, Callable

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler, MatrixVectorizedCompiler
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class TestStructuralCompiler(unittest.TestCase):
    """
    Test harness for JIT-compiled residual kernels within the SVS framework.
    """

    def setUp(self) -> None:
        """Sets up a canonical decay equation: dx/dt + x = 0."""
        self.x: Var = Var('x')
        self.dx: Var = Var(name='dx', base_var=self.x)
        self.decay_eq: Expr = self.dx + self.x

    # =========================================================================
    # PART 1: SCALAR KERNEL VALIDATION (Legacy Logic)
    # =========================================================================

    def test_trapezoidal_residual_math(self) -> None:
        """
        Verifies the implicit Trapezoidal substitution:
        dx_new = (2/h)*(x - x0) - dx0
        res = dx_new + x
        """
        compiler: EquationCompiler = EquationCompiler(
            list([self.x]),
            method=DynamicIntegrationMethod.DaeTrapezoidal
        )
        step_fn: Callable = compiler.compile(list([self.decay_eq]))

        h: float = 0.1
        h2: np.ndarray = np.zeros(1, dtype=np.float64)

        states: np.ndarray = np.array(list([1.0]), dtype=np.float64)
        params: np.ndarray = np.zeros(0, dtype=np.float64)
        history: np.ndarray = np.array(list([1.0]), dtype=np.float64)
        d_history: np.ndarray = np.array(list([-1.0]), dtype=np.float64)

        res: np.ndarray = step_fn(states, params, history, d_history, h, h2)

        self.assertAlmostEqual(float(res[0]), 2.0, places=7)

    # =========================================================================
    # PART 2: MATRIX VECTORIZED KERNEL VALIDATION (SVS Core)
    # =========================================================================

    def test_matrix_vectorized_clustering_logic(self) -> None:
        """
        Validates the MatrixVectorizedCompiler used in SVS Structural Clustering.
        Ensures a single template can be applied to multiple nodes simultaneously.
        """
        vec_compiler: MatrixVectorizedCompiler = MatrixVectorizedCompiler(
            list([self.x]),
            parameters=list(),
            method=DynamicIntegrationMethod.DaeTrapezoidal
        )
        py_func: Callable = vec_compiler.compile_matrix_kernel(
            self.decay_eq,
            func_name="vec_decay",
            template_vars=list([self.x])
        )
        vec_kernel: Callable = nb.njit(fastmath=True)(py_func)

        indices: np.ndarray = np.array(list([list([0]), list([1]), list([2])]), dtype=np.int32)
        states: np.ndarray = np.array(list([1.0, 1.2, 1.5]), dtype=np.float64)
        params: np.ndarray = np.zeros(0, dtype=np.float64)
        history: np.ndarray = np.array(list([1.0, 1.2, 1.5]), dtype=np.float64)
        d_hist: np.ndarray = np.array(list([-1.0, -1.2, -1.5]), dtype=np.float64)
        h: float = 0.1

        res: np.ndarray = vec_kernel(states, params, history, d_hist, h, indices, history)

        expected: np.ndarray = np.array(list([2.0, 2.4, 3.0]), dtype=np.float64)
        np.testing.assert_allclose(res, expected, rtol=1e-7)

    # =========================================================================
    # PART 3: NUMERICAL CONVERGENCE & PHYSICS
    # =========================================================================

    def test_truncation_error_order(self) -> None:
        """
        Mathematical proof of O(h^2) convergence for the Trapezoidal JIT kernel.
        Residual error should drop by factor of 4 when h is halved.
        """
        compiler: EquationCompiler = EquationCompiler(
            list([self.x]),
            method=DynamicIntegrationMethod.DaeTrapezoidal
        )
        step_fn: Callable = compiler.compile(list([self.decay_eq]))

        x0: float = 1.0
        dx0: float = -1.0
        h2: np.ndarray = np.zeros(1, dtype=np.float64)
        h_c: float = 0.1
        h_f: float = 0.05
        params: np.ndarray = np.zeros(0, dtype=np.float64)

        states_c: np.ndarray = np.array(list([np.exp(-h_c)]), dtype=np.float64)
        hist_c: np.ndarray = np.array(list([x0]), dtype=np.float64)
        d_hist_c: np.ndarray = np.array(list([dx0]), dtype=np.float64)
        res_c: np.ndarray = step_fn(states_c, params, hist_c, d_hist_c, h_c, h2)

        states_f: np.ndarray = np.array(list([np.exp(-h_f)]), dtype=np.float64)
        hist_f: np.ndarray = np.array(list([x0]), dtype=np.float64)
        d_hist_f: np.ndarray = np.array(list([dx0]), dtype=np.float64)
        res_f: np.ndarray = step_fn(states_f, params, hist_f, d_hist_f, h_f, h2)

        ratio: float = float(abs(res_c[0]) / abs(res_f[0]))
        print(f"\n[MATH] Empirical Convergence Ratio: {ratio:.2f} (Expected ~4.0)")
        self.assertGreater(ratio, 3.8)

    def test_oscillator_energy_conservation(self) -> None:
        """
        Physical verification: Trapezoidal rule must conserve energy in a Hamiltonian system.
        System: x'' + x = 0 (Undamped Oscillator).
        """
        pos: Var = Var('pos')
        vel: Var = Var('vel')
        d_pos: Var = Var(name='d_pos', base_var=pos)
        d_vel: Var = Var(name='d_vel', base_var=vel)

        eqs: List[Expr] = list([d_pos - vel, d_vel + pos])
        compiler: EquationCompiler = EquationCompiler(
            list([pos, vel]),
            method=DynamicIntegrationMethod.DaeTrapezoidal
        )
        kernel: Callable = compiler.compile(eqs)

        h: float = 0.01
        h2: np.ndarray = np.zeros(2, dtype=np.float64)
        hist: np.ndarray = np.array(list([1.0, 0.0]), dtype=np.float64)
        d_hist: np.ndarray = np.array(list([0.0, -1.0]), dtype=np.float64)
        params: np.ndarray = np.zeros(0, dtype=np.float64)

        states_new: np.ndarray = np.array(list([np.cos(h), -np.sin(h)]), dtype=np.float64)
        res: np.ndarray = kernel(states_new, params, hist, d_hist, h, h2)

        np.testing.assert_allclose(res, np.zeros(2, dtype=np.float64), atol=1e-4)

        e_init: float = 0.5 * (1.0 ** 2 + 0.0 ** 2)
        e_final: float = 0.5 * (float(states_new[0]) ** 2 + float(states_new[1]) ** 2)
        self.assertAlmostEqual(e_init, e_final, places=6)


if __name__ == '__main__':
    unittest.main()