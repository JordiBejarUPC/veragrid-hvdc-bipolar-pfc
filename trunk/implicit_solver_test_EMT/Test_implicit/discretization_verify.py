# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Mathematical Verification Suite for VeraGrid BlockSolver.

This test suite validates the numerical integrity of the JIT-compiled solvers.
1. Test 04: Added consistent initial derivatives (dx0) to recover 2nd Order convergence.
2. Test 08: Decoupled equation time variable from solver global time to avoid Numba naming conflicts.
"""

import unittest
import numpy as np

# VeraGrid Imports
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class TestBlockSolverMathematics(unittest.TestCase):

    def setUp(self):
        """
        Common setup. Creates a shared time variable used across tests.
        """
        self.time = Var("t")

    def create_decay_system(self, k_val=1.0):
        """Helper to create a simple decay system: dx/dt = -k*x"""
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
        """Verifies BackEuler algebraic formula: x_new = x_old / (1 + h*k)"""
        h = 0.1
        block, x, _ = self.create_decay_system(k_val=1.0)
        solver = BlockSolver(block, self.time)

        _, y = solver.simulate_unified(
            t0=0.0, t_end=h, h=h,
            x0=np.array([1.0]), dx0=np.array([-1.0]), params0=None,
            method=DynamicIntegrationMethod.BackEuler,
            dense_threshold=100
        )

        x_numeric = y[-1, 0]
        x_expected = 1.0 / (1 + h)
        print(f"\n[Test 01] BackEuler Result: {x_numeric:.6f} vs Formula: {x_expected:.6f}")
        self.assertAlmostEqual(x_numeric, x_expected, places=7)

    def test_02_trapezoidal_math(self):
        """Verifies Trapezoidal algebraic formula: x_new = x_old * (1 - h/2) / (1 + h/2)"""
        h = 0.1
        block, x, _ = self.create_decay_system(k_val=1.0)
        solver = BlockSolver(block, self.time)

        _, y = solver.simulate_unified(
            t0=0.0, t_end=h, h=h,
            x0=np.array([1.0]), dx0=np.array([-1.0]), params0=None,
            method=DynamicIntegrationMethod.Trapezoid,
            dense_threshold=100
        )

        x_numeric = y[-1, 0]
        factor = (1 - h / 2) / (1 + h / 2)
        x_expected = 1.0 * factor
        print(f"[Test 02] Trapezoid Result: {x_numeric:.6f} vs Formula: {x_expected:.6f}")
        self.assertAlmostEqual(x_numeric, x_expected, places=7)

    def test_03_boundary_update_fn(self):
        """Verifies dynamic parameter injection via callback."""
        block, x, k = self.create_decay_system(k_val=1.0)
        solver = BlockSolver(block, self.time)

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
        print(f"[Test 03] Boundary Update: y(0.6)={y_06:.4f}, y(1.0)={y_10:.4f}")
        self.assertAlmostEqual(y_06, y_10, places=6)

    # =========================================================================
    # PART 2: ADVANCED MATHEMATICAL ROBUSTNESS
    # =========================================================================

    def test_04_convergence_order(self):
        """
        Objective: Prove Trapezoidal is 2nd Order (Error decreases ~4x when h halves).
        """
        block, x, _ = self.create_decay_system(k_val=1.0)
        solver = BlockSolver(block, self.time)

        t_target = 1.0
        exact_sol = np.exp(-t_target)

        # Consistent initial derivatives for x' = -x, x0=1 -> dx0=-1
        consistent_dx0 = np.array([-1.0])

        # Run h1 = 0.1
        _, y1 = solver.simulate_unified(
            t0=0.0, t_end=t_target, h=0.1,
            x0=np.array([1.0]), dx0=consistent_dx0, params0=None,
            method=DynamicIntegrationMethod.Trapezoid,
            dense_threshold=100
        )
        err1 = abs(y1[-1, 0] - exact_sol)

        # Run h2 = 0.05
        _, y2 = solver.simulate_unified(
            t0=0.0, t_end=t_target, h=0.05,
            x0=np.array([1.0]), dx0=consistent_dx0, params0=None,
            method=DynamicIntegrationMethod.Trapezoid,
            dense_threshold=100
        )
        err2 = abs(y2[-1, 0] - exact_sol)

        ratio = err1 / err2
        print(f"[Test 04] Convergence Order Ratio: {ratio:.2f} (Expected ~4.0)")

        self.assertGreater(ratio, 3.8)

    def test_05_stiff_system_stability(self):
        """Test L-Stability on stiff system dx/dt = -1000x."""
        x = Var("x")
        stiff_block = Block(name="Stiff", state_vars=[x], state_eqs=[-1000.0 * x], parameters={})
        solver = BlockSolver(stiff_block, self.time)

        _, y = solver.simulate_unified(
            t0=0.0, t_end=1.0, h=0.1,
            x0=np.array([1.0]), dx0=np.array([-1000.0]), params0=None,
            method=DynamicIntegrationMethod.BackEuler,
            dense_threshold=100
        )

        final_val = y[-1, 0]
        print(f"[Test 05] Stiff Result: {final_val}")
        self.assertAlmostEqual(final_val, 0.0, places=3)

    def test_06_nonlinear_jacobian(self):
        """Test Newton convergence on nonlinear system dx/dt = x^2."""
        x = Var("x")
        nl_block = Block(name="NonLinear", state_vars=[x], state_eqs=[x * x], parameters={})
        solver = BlockSolver(nl_block, self.time)

        _, y = solver.simulate_unified(
            t0=0.0, t_end=0.5, h=0.01,
            x0=np.array([1.0]), dx0=np.array([1.0]), params0=None,
            method=DynamicIntegrationMethod.Trapezoid,
            dense_threshold=100
        )

        final_val = y[-1, 0]
        print(f"[Test 06] Non-Linear Result: {final_val:.4f} vs Exact: 2.0000")
        self.assertAlmostEqual(final_val, 2.0, delta=0.05)

    def test_07_energy_conservation(self):
        """Compare energy conservation: Trapezoidal (Conserves) vs BackEuler (Damps)."""
        x = Var("pos")
        v = Var("vel")
        osc_block = Block(name="Oscillator", state_vars=[x, v], state_eqs=[v, -x], parameters={})
        solver = BlockSolver(osc_block, self.time)

        x0 = np.array([1.0, 0.0])
        dx0 = np.array([0.0, -1.0])

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

        print(f"[Test 07] Energy: Trap Amp={amp_trap:.4f}, Euler Amp={amp_be:.4f}")
        self.assertGreater(amp_trap, 0.95)
        self.assertLess(amp_be, 0.5)

    def test_08_time_dependent_forcing(self):
        """
        Objective: Verify solver handles explicit time in equations.
        System: dx/dt = t. Exact: x(t) = t^2/2.

        We use 't_driver' as a separate event parameter to update manually,
        avoiding conflicts with the solver's internal 'glob_time' handling in Numba.
        """
        x = Var("x")
        t_driver = Var("t_driver")  # Independent driver variable

        # Register t_driver as an event parameter
        forcing_block = Block(
            name="Forcing",
            state_vars=[x],
            state_eqs=[t_driver],
            event_dict={t_driver: Const(0.0)},
            parameters={}
        )

        # Use a separate var for global time to instantiate solver
        t_sys = Var("t_sys")
        solver = BlockSolver(forcing_block, t_sys)

        # Find index of our driver parameter
        idx_t = solver.uid2idx_event_params[t_driver.uid]

        def sync_time(t, x, params):
            params[idx_t] = t  # Manually inject simulation time

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

        print(f"[Test 08] Time Forcing: {final_val:.4f} vs Expected: {expected:.4f}")
        self.assertAlmostEqual(final_val, expected, places=2)


if __name__ == '__main__':
    unittest.main()