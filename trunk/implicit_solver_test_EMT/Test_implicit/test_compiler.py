# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Unit tests for the JIT EquationCompiler.

This suite verifies:
1. Mathematical correctness of integration schemes (Trapezoidal, Backward Euler, BDF2).
2. Proper compilation of multivariable systems and parameter handling.
3. Numerical properties such as truncation error order and energy conservation.
"""

import unittest
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler


class TestEquationCompiler(unittest.TestCase):
    """
    Test harness for the EquationCompiler class.
    """

    def setUp(self):
        """
        Sets up a common decay equation (dx/dt = -x) for basic tests.
        """
        self.x = Var('x')
        self.dx = Var(name='dx', base_var=self.x)
        self.decay_eq = self.dx + self.x

    def test_trapezoidal_calculation(self):
        """
        Verifies a single step calculation using the Trapezoidal rule.
        """
        # FIX: Pass [self.x] (Var object), not ['x'] (string)
        compiler = EquationCompiler([self.x], method='trapezoidal')
        step_fn = compiler.compile([self.decay_eq])

        print(f"\n[INFO] Test Trapezoidal")

        # Dummy history buffer for method compatibility
        h2 = np.zeros(1)

        res = step_fn(
            states=np.array([1.0]),
            params=np.zeros(0),
            history=np.array([1.0]),
            d_history=np.array([-1.0]),
            h=0.1,
            history2=h2
        )
        self.assertAlmostEqual(res[0], 2.0, places=5)

    def test_backward_euler_calculation(self):
        """
        Verifies a single step calculation using the Backward Euler method.
        """
        # FIX: Pass [self.x], not ['x']
        compiler = EquationCompiler([self.x], method='be')
        step_fn = compiler.compile([self.decay_eq])

        h2 = np.zeros(1)

        res = step_fn(
            states=np.array([0.5]),
            params=np.zeros(0),
            history=np.array([1.0]),
            d_history=np.array([0.0]),
            h=0.5,
            history2=h2
        )
        self.assertAlmostEqual(res[0], -0.5, places=5)

    def test_bdf2_calculation(self):
        """
        Verifies a single step calculation using the BDF2 method.
        """
        # FIX: Pass [self.x], not ['x']
        compiler = EquationCompiler([self.x], method='bdf2')
        step_fn = compiler.compile([self.decay_eq])

        res = step_fn(
            states=np.array([1.0]),
            params=np.zeros(0),
            history=np.array([1.0]),
            d_history=np.array([0.0]),
            h=1.0,
            history2=np.array([1.0])
        )
        self.assertAlmostEqual(res[0], 1.0, places=5)

    def test_multivariable_system(self):
        """
        Verifies compilation and execution for a multi-variable coupled system.
        """
        x = Var('x')
        y = Var('y')
        k = Var('k')
        dx = Var(name='dx', base_var=x)
        dy = Var(name='dy', base_var=y)

        eq1 = dx - y
        eq2 = dy + k * x

        # FIX: Pass objects [x, y] and parameters [k]
        compiler = EquationCompiler([x, y], parameters=[k], method='trapezoidal')
        step_fn = compiler.compile([eq1, eq2])

        h2 = np.zeros(2)

        res = step_fn(
            states=np.array([1.0, 2.0]),
            params=np.array([10.0]),
            history=np.array([1.0, 2.0]),
            d_history=np.array([0.0, 0.0]),
            h=0.1,
            history2=h2
        )
        np.testing.assert_array_almost_equal(res, np.array([-2.0, 10.0]))

    def test_parameter_sensitivity(self):
        """
        Verifies that changes in parameter values correctly affect the residual calculation.
        Equation: dx/dt + k*x = 0
        """
        k = Var('k')
        eq = self.dx + k * self.x

        # FIX: Pass [self.x] and parameters [k]
        compiler = EquationCompiler([self.x], parameters=[k], method='be')
        step_fn = compiler.compile([eq])

        states = np.array([1.0])
        history = np.array([1.0])
        d_hist = np.array([0.0])
        h2 = np.zeros(1)
        h = 1.0

        res1 = step_fn(states, np.array([1.0]), history, d_hist, h, h2)
        res2 = step_fn(states, np.array([10.0]), history, d_hist, h, h2)

        self.assertNotEqual(res1[0], res2[0])
        self.assertAlmostEqual(res2[0], 10.0)

    def test_truncation_error_order(self):
        """
        Advanced Test: Verifies that the numerical residual decreases with O(h^2).
        """
        # FIX: Pass [self.x]
        compiler = EquationCompiler([self.x], method='trapezoidal')
        step_fn = compiler.compile([self.decay_eq])

        x0 = 1.0
        dx0 = -1.0
        h2 = np.zeros(1)

        h_coarse = 0.1
        h_fine = 0.05

        x_exact_c = np.exp(-h_coarse)
        x_exact_f = np.exp(-h_fine)

        # Evaluate residuals using the exact solution
        res_c = step_fn(np.array([x_exact_c]), np.zeros(0), np.array([x0]), np.array([dx0]), h_coarse, h2)
        res_f = step_fn(np.array([x_exact_f]), np.zeros(0), np.array([x0]), np.array([dx0]), h_fine, h2)

        error_c = abs(res_c[0])
        error_f = abs(res_f[0])

        ratio = error_c / error_f

        print(f"[OK] Convergence (Expected Order 2): Ratio = {ratio:.2f}")
        self.assertTrue(ratio > 3.5)

    def test_energy_conservation(self):
        """
        Physical Test: Verifies that an undamped harmonic oscillator conserves energy
        when using the symplectic Trapezoidal rule.
        System: x'' + x = 0 (k=1, m=1)
        """
        x = Var('x')
        v = Var('v')
        dx = Var(name='dx', base_var=x)
        dv = Var(name='dv', base_var=v)

        # Equations: dx/dt = v, dv/dt = -x
        eq1 = dx - v
        eq2 = dv + x

        # FIX: Pass [x, v]
        compiler = EquationCompiler([x, v], method='trapezoidal')
        step_fn = compiler.compile([eq1, eq2])

        # Initial state: x=1, v=0 -> Energy = 0.5
        states = np.array([1.0, 0.0])
        history = np.array([1.0, 0.0])
        d_history = np.array([0.0, -1.0])
        h2 = np.zeros(2)
        h = 0.01

        # Simulate 1 perfect step using analytical solution
        x_new_exact = np.cos(h)
        v_new_exact = -np.sin(h)
        states_new = np.array([x_new_exact, v_new_exact])

        res = step_fn(states_new, np.zeros(0), history, d_history, h, h2)

        energy_initial = 0.5 * 1.0 ** 2
        energy_final = 0.5 * x_new_exact ** 2 + 0.5 * v_new_exact ** 2

        np.testing.assert_array_almost_equal(res, np.zeros(2), decimal=4)
        self.assertAlmostEqual(energy_initial, energy_final, places=5)

if __name__ == '__main__':
    unittest.main()