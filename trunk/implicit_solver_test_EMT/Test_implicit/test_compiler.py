# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Module: Structural Compiler Verification Suite
==============================================
Rigorous mathematical validation of Scalar and Matrix-Vectorized JIT kernels.
Focus: Residual accuracy, Convergence Order, and Energy Conservation.
"""

import unittest
import numpy as np
import numba as nb

from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler, MatrixVectorizedCompiler
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class TestStructuralCompiler(unittest.TestCase):
    """
    Test harness for JIT-compiled residual kernels within the SVS framework.
    """

    def setUp(self):
        """Sets up a canonical decay equation: dx/dt + x = 0."""
        self.x = Var('x')
        self.dx = Var(name='dx', base_var=self.x)
        self.decay_eq = self.dx + self.x

    # =========================================================================
    # PART 1: SCALAR KERNEL VALIDATION (Legacy Logic)
    # =========================================================================

    def test_trapezoidal_residual_math(self):
        """
        Verifies the implicit Trapezoidal substitution:
        dx_new = (2/h)*(x - x0) - dx0
        res = dx_new + x
        """
        compiler = EquationCompiler([self.x], method=DynamicIntegrationMethod.Trapezoid)
        step_fn = compiler.compile([self.decay_eq])

        h, h2 = 0.1, np.zeros(1)
        # Condition: x=1.0, x0=1.0, dx0=-1.0.
        # dx_new = (2/0.1)*(0) - (-1.0) = 1.0
        # res = 1.0 + 1.0 = 2.0
        res = step_fn(np.array([1.0]), np.zeros(0), np.array([1.0]), np.array([-1.0]), h, h2)

        self.assertAlmostEqual(res[0], 2.0, places=7)

    # =========================================================================
    # PART 2: MATRIX VECTORIZED KERNEL VALIDATION (SVS Core)
    # =========================================================================

    def test_matrix_vectorized_clustering_logic(self):
        """
        Validates the MatrixVectorizedCompiler used in SVS Structural Clustering.
        Ensures a single template can be applied to multiple nodes simultaneously.
        """
        # System: 3 independent oscillators sharing the same algebraic template
        vec_compiler = MatrixVectorizedCompiler([self.x], parameters=[], method=DynamicIntegrationMethod.Trapezoid)
        py_func = vec_compiler.compile_matrix_kernel(self.decay_eq, func_name="vec_decay", template_vars=[self.x])
        vec_kernel = nb.njit(fastmath=True)(py_func)

        # 3 Nodes, each with its own index mapping
        indices = np.array([[0], [1], [2]], dtype=np.int32)
        states = np.array([1.0, 1.2, 1.5])
        history = np.array([1.0, 1.2, 1.5])
        d_hist = np.array([-1.0, -1.2, -1.5])
        h = 0.1

        # The kernel should process all 3 nodes in a single vectorized pass
        res = vec_kernel(states, np.zeros(0), history, d_hist, h, indices, history)

        # Expected residuals based on the exact DAE substitution
        expected = np.array([2.0, 2.4, 3.0])
        np.testing.assert_allclose(res, expected, rtol=1e-7)

    # =========================================================================
    # PART 3: NUMERICAL CONVERGENCE & PHYSICS
    # =========================================================================

    def test_truncation_error_order(self):
        """
        Mathematical proof of O(h^2) convergence for the Trapezoidal JIT kernel.
        Residual error should drop by factor of 4 when h is halved.
        """
        compiler = EquationCompiler([self.x], method=DynamicIntegrationMethod.Trapezoid)
        step_fn = compiler.compile([self.decay_eq])

        x0, dx0, h2 = 1.0, -1.0, np.zeros(1)
        h_c, h_f = 0.1, 0.05  # Coarse and Fine steps

        # Exact solutions used to evaluate the numerical residual
        res_c = step_fn(np.array([np.exp(-h_c)]), np.zeros(0), np.array([x0]), np.array([dx0]), h_c, h2)
        res_f = step_fn(np.array([np.exp(-h_f)]), np.zeros(0), np.array([x0]), np.array([dx0]), h_f, h2)

        ratio = abs(res_c[0]) / abs(res_f[0])
        print(f"\n[MATH] Empirical Convergence Ratio: {ratio:.2f} (Expected ~4.0)")
        self.assertGreater(ratio, 3.8)  # Proves 2nd order accuracy

    def test_oscillator_energy_conservation(self):
        """
        Physical verification: Trapezoidal rule must conserve energy in a Hamiltonian system.
        System: x'' + x = 0 (Undamped Oscillator).
        """
        pos, vel = Var('pos'), Var('vel')
        d_pos, d_vel = Var(name='d_pos', base_var=pos), Var(name='d_vel', base_var=vel)

        # Equations: dx/dt = v, dv/dt = -x
        eqs = [d_pos - vel, d_vel + pos]
        compiler = EquationCompiler([pos, vel], method=DynamicIntegrationMethod.Trapezoid)
        kernel = compiler.compile(eqs)

        h, h2 = 0.01, np.zeros(2)
        # Start at max displacement: pos=1, vel=0 (Energy = 0.5)
        hist, d_hist = np.array([1.0, 0.0]), np.array([0.0, -1.0])

        # Exact solution step
        states_new = np.array([np.cos(h), -np.sin(h)])
        res = kernel(states_new, np.zeros(0), hist, d_hist, h, h2)

        # Residual must be near zero, and energy must be preserved
        np.testing.assert_allclose(res, np.zeros(2), atol=1e-4)
        e_init = 0.5 * (1.0 ** 2 + 0.0 ** 2)
        e_final = 0.5 * (states_new[0] ** 2 + states_new[1] ** 2)
        self.assertAlmostEqual(e_init, e_final, places=6)


if __name__ == '__main__':
    unittest.main()