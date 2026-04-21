import unittest

import numpy as np

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.initialization_emt import (
    EmtInitializationStatus,
    run_emt_explicit_initialization,
    run_emt_native_initialization,
)
from VeraGridEngine.enumerations import EmtInitializationMethod
from trunk.implicit_solver_test_EMT.initialization_workflow_support import (
    build_single_state_single_algebraic_problem,
    build_two_bus_real_emt_case,
    build_unresolved_state_problem,
    evaluate_algebraic_residual_inf,
)

class TestEmtInitializationWorkflow(unittest.TestCase):

    def test_consistent_newton_initializes_missing_algebraic_and_dx0(self) -> None:
        problem, context = build_single_state_single_algebraic_problem()
        options = EmtOptions(initialization_method=EmtInitializationMethod.ConsistentNewton)

        run_emt_explicit_initialization(problem)
        report = run_emt_native_initialization(problem, options)

        idx_x = problem.get_var_idx(context.get_x_var())
        idx_y = problem.get_var_idx(context.get_y_var())
        idx_dx = problem.get_diff_var_idx(context.get_dx_var())

        x0 = problem.get_x0()
        dx0 = problem.get_dx0()

        self.assertEqual(report.status, EmtInitializationStatus.RESOLVED)
        self.assertAlmostEqual(x0[idx_x], 2.0, places=9)
        self.assertAlmostEqual(x0[idx_y], 2.0, places=9)
        self.assertAlmostEqual(dx0[idx_dx], 0.0, places=9)

    def test_consistent_newton_uses_state_equilibrium_for_unresolved_states(self) -> None:
        problem, context = build_unresolved_state_problem()
        options = EmtOptions(initialization_method=EmtInitializationMethod.ConsistentNewton)

        report = run_emt_native_initialization(problem, options)

        idx_x = problem.get_var_idx(context.get_x_var())
        idx_y = problem.get_var_idx(context.get_y_var())
        idx_dx = problem.get_diff_var_idx(context.get_dx_var())

        x0 = problem.get_x0()
        dx0 = problem.get_dx0()

        self.assertEqual(report.status, EmtInitializationStatus.RESOLVED)
        self.assertAlmostEqual(x0[idx_x], 3.0, places=9)
        self.assertAlmostEqual(x0[idx_y], 3.0, places=9)
        self.assertAlmostEqual(dx0[idx_dx], 0.0, places=9)

    def test_pseudo_transient_method_converges_on_simple_problem(self) -> None:
        problem, _ = build_unresolved_state_problem()
        options = EmtOptions(
            initialization_method=EmtInitializationMethod.PseudoTransient,
            init_newton_tol=1e-8,
            init_ptc_max_iter=80,
        )

        report = run_emt_native_initialization(problem, options)

        self.assertEqual(report.status, EmtInitializationStatus.RESOLVED)
        self.assertEqual(report.method_used, EmtInitializationMethod.PseudoTransient)
        self.assertLessEqual(report.final_residual_inf, options.init_newton_tol)

    def test_auto_initialization_is_not_worse_than_explicit_on_real_case(self) -> None:
        explicit_problem, _ = build_two_bus_real_emt_case(
            zip_load=True,
            initialization_method=EmtInitializationMethod.Explicit,
        )
        auto_problem, _ = build_two_bus_real_emt_case(
            zip_load=True,
            initialization_method=EmtInitializationMethod.Auto,
        )

        explicit_res = evaluate_algebraic_residual_inf(explicit_problem)
        auto_res = evaluate_algebraic_residual_inf(auto_problem)

        self.assertTrue(np.isfinite(explicit_res))
        self.assertTrue(np.isfinite(auto_res))
        self.assertLessEqual(auto_res, explicit_res + 1.0e-8)
        self.assertIsNotNone(auto_problem.initialization_report)
        assert auto_problem.initialization_report is not None
        self.assertIn(
            auto_problem.initialization_report.status,
            {EmtInitializationStatus.RESOLVED, EmtInitializationStatus.FAILED},
        )


if __name__ == "__main__":
    unittest.main()
