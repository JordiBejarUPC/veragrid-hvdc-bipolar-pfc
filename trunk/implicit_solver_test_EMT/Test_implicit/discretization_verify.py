# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Mathematical Verification Suite for VeraGrid BlockSolver.

Validates numerical integrity of the JIT-compiled implicit solvers for:
  - Symbolic Jacobian backend
  - Automatic Jacobian backend (Sparse AD + Graph Coloring)
"""

import unittest
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod, JacobianBackend


class TestBlockSolverMathematics(unittest.TestCase):

    def setUp(self):
        self.time = Var("t")
        self._jacobian_backends = [JacobianBackend.Symbolic, JacobianBackend.Automatic]

    def make_solver(self, block, jac_backend: JacobianBackend):
        return BlockSolver(
            block_system=block,
            glob_time=self.time,
            jacobian_backend=jac_backend,
        )

    def create_decay_system(self, k_val=1.0):
        x = Var("x")
        k = Var("k")
        block = Block(
            name="DecayUnit",
            state_vars=[x],
            state_eqs=[-k * x],
            parameters={k: Const(k_val)}
        )
        return block, x, k

    # =========================================================================
    # PART 1: BASIC DISCRETIZATION VERIFICATION
    # =========================================================================

    def test_01_backward_euler_math(self):
        h = 0.1
        block, _, _ = self.create_decay_system(k_val=1.0)

        for jb in self._jacobian_backends:
            with self.subTest(jacobian_backend=str(jb)):
                solver = self.make_solver(block, jb)

                _, y = solver.simulate_unified(
                    t0=0.0, t_end=h, h=h,
                    x0=np.array([1.0]), dx0=np.array([-1.0]), params0=None,
                    method=DynamicIntegrationMethod.BackEuler,
                    dense_threshold=100
                )

                x_numeric = y[-1, 0]
                x_expected = 1.0 / (1 + h)
                self.assertAlmostEqual(x_numeric, x_expected, places=7)

    def test_02_trapezoidal_math(self):
        h = 0.1
        block, _, _ = self.create_decay_system(k_val=1.0)

        for jb in self._jacobian_backends:
            with self.subTest(jacobian_backend=str(jb)):
                solver = self.make_solver(block, jb)

                _, y = solver.simulate_unified(
                    t0=0.0, t_end=h, h=h,
                    x0=np.array([1.0]), dx0=np.array([-1.0]), params0=None,
                    method=DynamicIntegrationMethod.Trapezoid,
                    dense_threshold=100
                )

                x_numeric = y[-1, 0]
                factor = (1 - h / 2) / (1 + h / 2)
                x_expected = 1.0 * factor
                self.assertAlmostEqual(x_numeric, x_expected, places=7)

    def test_03_boundary_update_fn(self):
        block, _, k = self.create_decay_system(k_val=1.0)

        for jb in self._jacobian_backends:
            with self.subTest(jacobian_backend=str(jb)):
                solver = self.make_solver(block, jb)

                offset_events = len(solver._event_parameters)
                idx_k = offset_events + solver.uid2idx_params[k.uid]

                def freeze_parameter(t, x_state, params):
                    if t > 0.5:
                        params[idx_k] = 0.0  # Freeze decay

                _, y = solver.simulate_unified(
                    t0=0.0, t_end=1.0, h=0.1,
                    x0=np.array([1.0]), dx0=np.array([-1.0]), params0=None,
                    method=DynamicIntegrationMethod.BackEuler,
                    boundary_update_fn=freeze_parameter,
                    dense_threshold=100
                )

                y_06 = y[6, 0]
                y_10 = y[-1, 0]
                self.assertAlmostEqual(y_06, y_10, places=6)

    # =========================================================================
    # PART 2: ADVANCED MATHEMATICAL ROBUSTNESS
    # =========================================================================

    def test_04_convergence_order(self):
        block, _, _ = self.create_decay_system(k_val=1.0)

        t_target = 1.0
        exact_sol = np.exp(-t_target)
        consistent_dx0 = np.array([-1.0])

        for jb in self._jacobian_backends:
            with self.subTest(jacobian_backend=str(jb)):
                solver = self.make_solver(block, jb)

                _, y1 = solver.simulate_unified(
                    t0=0.0, t_end=t_target, h=0.1,
                    x0=np.array([1.0]), dx0=consistent_dx0, params0=None,
                    method=DynamicIntegrationMethod.Trapezoid,
                    dense_threshold=100
                )
                err1 = abs(y1[-1, 0] - exact_sol)

                _, y2 = solver.simulate_unified(
                    t0=0.0, t_end=t_target, h=0.05,
                    x0=np.array([1.0]), dx0=consistent_dx0, params0=None,
                    method=DynamicIntegrationMethod.Trapezoid,
                    dense_threshold=100
                )
                err2 = abs(y2[-1, 0] - exact_sol)

                ratio = err1 / err2
                self.assertGreater(ratio, 3.8)

    def test_05_stiff_system_stability(self):
        x = Var("x")
        stiff_block = Block(
            name="Stiff",
            state_vars=[x],
            state_eqs=[(-1000) * x],
            parameters={}
        )

        for jb in self._jacobian_backends:
            with self.subTest(jacobian_backend=str(jb)):
                solver = self.make_solver(stiff_block, jb)

                _, y = solver.simulate_unified(
                    t0=0.0, t_end=1.0, h=0.1,
                    x0=np.array([1.0]),
                    dx0=None,
                    params0=None,
                    method=DynamicIntegrationMethod.BackEuler,
                    dense_threshold=100
                )

                final_val = y[-1, 0]
                self.assertLess(abs(final_val), 1e-2)

    def test_06_nonlinear_jacobian(self):
        x = Var("x")
        nl_block = Block(name="NonLinear", state_vars=[x], state_eqs=[x * x], parameters={})

        for jb in self._jacobian_backends:
            with self.subTest(jacobian_backend=str(jb)):
                solver = self.make_solver(nl_block, jb)

                _, y = solver.simulate_unified(
                    t0=0.0, t_end=0.5, h=0.01,
                    x0=np.array([1.0]), dx0=np.array([1.0]), params0=None,
                    method=DynamicIntegrationMethod.Trapezoid,
                    dense_threshold=100
                )

                final_val = y[-1, 0]
                self.assertAlmostEqual(final_val, 2.0, delta=0.05)

    def test_07_energy_conservation(self):
        x = Var("pos")
        v = Var("vel")
        osc_block = Block(name="Oscillator", state_vars=[x, v], state_eqs=[v, -x], parameters={})

        x0 = np.array([1.0, 0.0])
        dx0 = np.array([0.0, -1.0])

        for jb in self._jacobian_backends:
            with self.subTest(jacobian_backend=str(jb)):
                solver = self.make_solver(osc_block, jb)

                _, y_trap = solver.simulate_unified(
                    t0=0.0, t_end=20.0, h=0.1, x0=x0, dx0=dx0, params0=None,
                    method=DynamicIntegrationMethod.Trapezoid, dense_threshold=100
                )
                _, y_be = solver.simulate_unified(
                    t0=0.0, t_end=20.0, h=0.1, x0=x0, dx0=dx0, params0=None,
                    method=DynamicIntegrationMethod.BackEuler, dense_threshold=100
                )

                amp_trap = np.max(np.abs(y_trap[-20:, 0]))
                amp_be = np.max(np.abs(y_be[-20:, 0]))

                self.assertGreater(amp_trap, 0.95)
                self.assertLess(amp_be, 0.5)

    def test_08_time_dependent_forcing(self):
        x = Var("x")
        t_driver = Var("t_driver")

        forcing_block = Block(
            name="Forcing",
            state_vars=[x],
            state_eqs=[t_driver],
            event_dict={t_driver: Const(0.0)},
            parameters={}
        )

        t_sys = Var("t_sys")

        for jb in self._jacobian_backends:
            with self.subTest(jacobian_backend=str(jb)):
                solver = BlockSolver(forcing_block, t_sys, jacobian_backend=jb)

                idx_t = solver.uid2idx_event_params[t_driver.uid]

                def sync_time(t, x, params):
                    params[idx_t] = t

                t_end = 2.0
                _, y = solver.simulate_unified(
                    t0=0.0, t_end=t_end, h=0.1,
                    x0=np.array([0.0]), dx0=np.array([0.0]), params0=None,
                    method=DynamicIntegrationMethod.Trapezoid,
                    boundary_update_fn=sync_time,
                    dense_threshold=100
                )

                final_val = y[-1, 0]
                expected = (t_end ** 2) / 2.0
                self.assertAlmostEqual(final_val, expected, places=2)


if __name__ == '__main__':
    unittest.main()
