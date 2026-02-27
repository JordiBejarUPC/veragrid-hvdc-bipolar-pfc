# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Mathematical Verification Suite for VeraGrid Unified Solvers.

Validates numerical integrity of the JIT-compiled implicit solvers for:
  - JitAdSolver (Sparse AD + Graph Coloring)
  - StructuralVectorizedSolver (Clustered Matrix Kernels)
"""

import unittest
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate

from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod

class GenericEmtProblem(EmtProblemTemplate):
    pass

class TestUnifiedSolverMathematics(unittest.TestCase):

    def setUp(self):
        self.time = Var("t")
        self._solvers_to_test = [JitAdSolver, StructuralVectorizedSolver]

    def make_solver(self, solver_class, block, t_end, h, method: DynamicIntegrationMethod):
        """Helper to construct a BaseProblem and initialize the chosen solver."""
        block.unify_blocks()
        problem = GenericEmtProblem(block, self.time)
        solver = solver_class(problem, t0=0.0, t_end=t_end, h=h, method=method)
        return solver, problem

    def create_decay_system(self, k_val=1.0):
        x, k = Var("x"), Var("k")
        block = Block(
            name="DecayUnit", state_vars=[x], state_eqs=[-k * x], parameters={k: Const(k_val)}
        )
        return block, x, k

    # =========================================================================
    # PART 1: BASIC DISCRETIZATION VERIFICATION
    # =========================================================================

    def test_01_backward_euler_math(self):
        h = 0.1
        block, _, _ = self.create_decay_system(k_val=1.0)

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, block, h, h, DynamicIntegrationMethod.DaeBackEuler)

                # Setup init vectors
                x0 = prob.get_x0()
                x0[0] = 1.0
                dx0 = np.zeros_like(x0)
                dx0[0] = -1.0
                p0 = np.zeros(prob.get_variable_parameter_number())

                _, y = solver.simulate(x0=x0, dx0=dx0, params0=p0)

                x_numeric = y[-1, 0]
                x_expected = 1.0 / (1 + h)
                self.assertAlmostEqual(x_numeric, x_expected, places=7)

    def test_02_Trapezoid_math(self):
        h = 0.1
        block, _, _ = self.create_decay_system(k_val=1.0)

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, block, h, h, DynamicIntegrationMethod.DaeTrapezoidal)

                x0 = prob.get_x0()
                x0[0] = 1.0
                dx0 = np.zeros_like(x0)
                dx0[0] = -1.0
                p0 = np.zeros(prob.get_variable_parameter_number())

                _, y = solver.simulate(x0=x0, dx0=dx0, params0=p0)

                x_numeric = y[-1, 0]
                factor = (1 - h / 2) / (1 + h / 2)
                x_expected = 1.0 * factor
                self.assertAlmostEqual(x_numeric, x_expected, places=7)

    def test_03_boundary_update_fn(self):
        block, _, k = self.create_decay_system(k_val=1.0)

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, block, 1.0, 0.1, DynamicIntegrationMethod.DaeBackEuler)

                idx_k = getattr(solver, 'uid2idx_params', prob.uid2idx_vars).get(k.uid, 0)

                def freeze_parameter(t, x_state, params):
                    if t > 0.5:
                        params[idx_k] = 0.0

                x0 = prob.get_x0()
                x0[0] = 1.0
                dx0 = np.zeros_like(x0)
                dx0[0] = -1.0
                p0 = np.zeros(prob.get_variable_parameter_number())

                _, y = solver.simulate(x0=x0, dx0=dx0, params0=p0, boundary_update_fn=freeze_parameter)

                y_06 = y[6, 0]
                y_10 = y[-1, 0]
                self.assertAlmostEqual(y_06, y_10, places=6)

    # =========================================================================
    # PART 2: ADVANCED MATHEMATICAL ROBUSTNESS
    # =========================================================================

    def test_04_convergence_order(self):
        block, _, _ = self.create_decay_system(k_val=1.0)
        t_target, exact_sol = 1.0, np.exp(-1.0)

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver_c, prob_c = self.make_solver(solver_class, block, t_target, 0.1, DynamicIntegrationMethod.DaeTrapezoidal)
                x0_c, dx0_c = prob_c.get_x0(), np.zeros_like(prob_c.get_x0())
                x0_c[0], dx0_c[0] = 1.0, -1.0
                _, y_c = solver_c.simulate(x0=x0_c, dx0=dx0_c, params0=np.zeros(prob_c.get_variable_parameter_number()))
                err_c = abs(y_c[-1, 0] - exact_sol)

                solver_f, prob_f = self.make_solver(solver_class, block, t_target, 0.05, DynamicIntegrationMethod.DaeTrapezoidal)
                x0_f, dx0_f = prob_f.get_x0(), np.zeros_like(prob_f.get_x0())
                x0_f[0], dx0_f[0] = 1.0, -1.0
                _, y_f = solver_f.simulate(x0=x0_f, dx0=dx0_f, params0=np.zeros(prob_f.get_variable_parameter_number()))
                err_f = abs(y_f[-1, 0] - exact_sol)

                ratio = err_c / err_f
                self.assertGreater(ratio, 3.8)

    def test_05_stiff_system_stability(self):
        x = Var("x")
        stiff_block = Block(name="Stiff", state_vars=[x], state_eqs=[(-1000) * x], parameters={})

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, stiff_block, 1.0, 0.1, DynamicIntegrationMethod.DaeBackEuler)
                x0 = prob.get_x0()
                x0[0] = 1.0
                _, y = solver.simulate(x0=x0, dx0=np.zeros_like(x0),
                                       params0=np.zeros(prob.get_variable_parameter_number()))

                self.assertLess(abs(y[-1, 0]), 1e-2)

    def test_06_nonlinear_jacobian(self):
        x = Var("x")
        nl_block = Block(name="NonLinear", state_vars=[x], state_eqs=[x * x], parameters={})

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, nl_block, 0.5, 0.01, DynamicIntegrationMethod.DaeTrapezoidal)
                x0 = prob.get_x0()
                x0[0] = 1.0
                _, y = solver.simulate(x0=x0, dx0=np.ones_like(x0),
                                       params0=np.zeros(prob.get_variable_parameter_number()))

                self.assertAlmostEqual(y[-1, 0], 2.0, delta=0.05)

    def test_07_energy_conservation(self):
        x, v = Var("pos"), Var("vel")
        osc_block = Block(name="Oscillator", state_vars=[x, v], state_eqs=[v, -x], parameters={})

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver_trap, prob_trap = self.make_solver(solver_class, osc_block, 20.0, 0.1, DynamicIntegrationMethod.DaeTrapezoidal)
                x0, dx0 = prob_trap.get_x0(), np.zeros_like(prob_trap.get_x0())
                x0[0], dx0[1] = 1.0, -1.0  # pos=1, d_vel=-1
                _, y_trap = solver_trap.simulate(x0=x0, dx0=dx0,
                                                 params0=np.zeros(prob_trap.get_variable_parameter_number()))
                amp_trap = np.max(np.abs(y_trap[-20:, 0]))
                self.assertGreater(amp_trap, 0.95)

                solver_be, prob_be = self.make_solver(solver_class, osc_block, 20.0, 0.1, DynamicIntegrationMethod.DaeBackEuler)
                x0, dx0 = prob_be.get_x0(), np.zeros_like(prob_be.get_x0())
                x0[0], dx0[1] = 1.0, -1.0
                _, y_be = solver_be.simulate(x0=x0, dx0=dx0, params0=np.zeros(prob_be.get_variable_parameter_number()))
                amp_be = np.max(np.abs(y_be[-20:, 0]))
                self.assertLess(amp_be, 0.5)

    def test_08_time_dependent_forcing(self):
        x, t_driver = Var("x"), Var("t_driver")
        forcing_block = Block(
            name="Forcing", state_vars=[x], state_eqs=[t_driver],
            event_dict={t_driver: Const(0.0)}, parameters={}
        )

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, forcing_block, 2.0, 0.1, DynamicIntegrationMethod.DaeTrapezoidal)

                idx_t = getattr(solver, 'uid2idx_event_params', {}).get(t_driver.uid, 0)

                def sync_time(t, state, params):
                    params[idx_t] = t

                x0 = prob.get_x0()
                p0 = np.zeros(prob.get_variable_parameter_number())
                _, y = solver.simulate(x0=x0, dx0=np.zeros_like(x0), params0=p0, boundary_update_fn=sync_time)

                expected = (2.0 ** 2) / 2.0
                self.assertAlmostEqual(y[-1, 0], expected, places=2)


if __name__ == '__main__':
    unittest.main()