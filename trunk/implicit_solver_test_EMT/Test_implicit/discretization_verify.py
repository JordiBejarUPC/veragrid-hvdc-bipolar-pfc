# ==============================================================================
# Mathematical Verification Suite for VeraGrid Unified Solvers
# ==============================================================================

import unittest
import numpy as np
from typing import List, Tuple, Any

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate

from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import BoundaryUpdateWrapper
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


# --- Boundary Condition Wrappers ---
class FreezeParameterWrapper(BoundaryUpdateWrapper):
    __slots__ = ['idx_k', 'threshold']

    def __init__(self, idx_k: int, threshold: float):
        self.idx_k: int = idx_k
        self.threshold: float = threshold

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        if t > self.threshold:
            params[self.idx_k] = 0.0
        else:
            pass


class SyncTimeWrapper(BoundaryUpdateWrapper):
    __slots__ = ['idx_t']

    def __init__(self, idx_t: int):
        self.idx_t: int = idx_t

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        params[self.idx_t] = t


# --- Unit Test Suite ---
def create_decay_system(k_val: float = 1.0) -> Tuple[Block, Var, Var]:
    x: Var = Var("x")
    k: Var = Var("k")
    block: Block = Block(
        name="DecayUnit",
        state_vars=list([x]),
        state_eqs=list([-k * x]),
        parameters=dict({k: Const(k_val)})
    )
    return block, x, k


class TestUnifiedSolverMathematics(unittest.TestCase):

    def setUp(self) -> None:
        self.time: Var = Var("t")
        self._solvers_to_test: List[Any] = list([JitAdSolver, StructuralVectorizedSolver])

    def make_solver(self, solver_class: Any, block: Block, t_end: float, h: float,
                    method: DynamicIntegrationMethod) -> Tuple[Any, GenericEmtProblem]:
        """Helper to construct a BaseProblem and initialize the chosen solver."""
        block.unify_blocks()
        problem: GenericEmtProblem = GenericEmtProblem(block, self.time)
        solver: Any = solver_class(problem, t0=0.0, t_end=t_end, h=h, method=method)
        return solver, problem

    # =========================================================================
    # PART 1: BASIC DISCRETIZATION VERIFICATION
    # =========================================================================

    def test_01_backward_euler_math(self) -> None:
        h: float = 0.1
        block, _, _ = create_decay_system(k_val=1.0)

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, block, h, h, DynamicIntegrationMethod.DaeBackEuler)

                x0: np.ndarray = prob.get_x0()
                x0[0] = 1.0
                dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
                dx0[0] = -1.0
                p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

                _, y, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0)

                x_numeric: float = float(y[-1, 0])
                x_expected: float = 1.0 / (1.0 + h)
                self.assertAlmostEqual(x_numeric, x_expected, places=7)

    def test_02_Trapezoid_math(self) -> None:
        h: float = 0.1
        block, _, _ = create_decay_system(k_val=1.0)

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, block, h, h, DynamicIntegrationMethod.DaeTrapezoidal)

                x0: np.ndarray = prob.get_x0()
                x0[0] = 1.0
                dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
                dx0[0] = -1.0
                p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

                _, y, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0)

                x_numeric: float = float(y[-1, 0])
                factor: float = (1.0 - h / 2.0) / (1.0 + h / 2.0)
                x_expected: float = 1.0 * factor
                self.assertAlmostEqual(x_numeric, x_expected, places=7)

    def test_03_boundary_update_fn(self) -> None:
        block, _, k = create_decay_system(k_val=1.0)

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, block, 1.0, 0.1, DynamicIntegrationMethod.DaeBackEuler)

                # Safe access using the problem as the source of truth
                idx_k: int = prob.uid2idx_params.get(k.uid, 0)

                freeze_updater: FreezeParameterWrapper = FreezeParameterWrapper(idx_k=idx_k, threshold=0.5)

                x0: np.ndarray = prob.get_x0()
                x0[0] = 1.0
                dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
                dx0[0] = -1.0
                p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

                _, y, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0, boundary_updater=freeze_updater)

                y_06: float = float(y[6, 0])
                y_10: float = float(y[-1, 0])
                self.assertAlmostEqual(y_06, y_10, places=6)

    # =========================================================================
    # PART 2: ADVANCED MATHEMATICAL ROBUSTNESS
    # =========================================================================

    def test_04_convergence_order(self) -> None:
        block, _, _ = create_decay_system(k_val=1.0)
        t_target: float = 1.0
        exact_sol: float = float(np.exp(-1.0))

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver_c, prob_c = self.make_solver(solver_class, block, t_target, 0.1,
                                                    DynamicIntegrationMethod.DaeTrapezoidal)
                x0_c: np.ndarray = prob_c.get_x0()
                dx0_c: np.ndarray = np.zeros_like(x0_c, dtype=np.float64)
                x0_c[0] = 1.0
                dx0_c[0] = -1.0
                p0_c: np.ndarray = np.zeros(prob_c.get_variable_parameter_number(), dtype=np.float64)
                _, y_c, _ = solver_c.simulate(x0=x0_c, dx0=dx0_c, params0=p0_c)
                err_c: float = abs(float(y_c[-1, 0]) - exact_sol)

                solver_f, prob_f = self.make_solver(solver_class, block, t_target, 0.05,
                                                    DynamicIntegrationMethod.DaeTrapezoidal)
                x0_f: np.ndarray = prob_f.get_x0()
                dx0_f: np.ndarray = np.zeros_like(x0_f, dtype=np.float64)
                x0_f[0] = 1.0
                dx0_f[0] = -1.0
                p0_f: np.ndarray = np.zeros(prob_f.get_variable_parameter_number(), dtype=np.float64)
                _, y_f, _ = solver_f.simulate(x0=x0_f, dx0=dx0_f, params0=p0_f)
                err_f: float = abs(float(y_f[-1, 0]) - exact_sol)

                ratio: float = err_c / err_f
                self.assertGreater(ratio, 3.8)

    def test_05_stiff_system_stability(self) -> None:
        x: Var = Var("x")
        stiff_block: Block = Block(name="Stiff", state_vars=list([x]), state_eqs=list([(-1000) * x]), parameters=dict())

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, stiff_block, 1.0, 0.1,
                                                DynamicIntegrationMethod.DaeBackEuler)
                x0: np.ndarray = prob.get_x0()
                x0[0] = 1.0
                dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
                p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

                _, y, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0)

                self.assertLess(abs(float(y[-1, 0])), 1e-2)

    def test_06_nonlinear_jacobian(self) -> None:
        x: Var = Var("x")
        nl_block: Block = Block(name="NonLinear", state_vars=list([x]), state_eqs=list([x * x]), parameters=dict())

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, nl_block, 0.5, 0.01,
                                                DynamicIntegrationMethod.DaeTrapezoidal)
                x0: np.ndarray = prob.get_x0()
                x0[0] = 1.0
                dx0: np.ndarray = np.ones_like(x0, dtype=np.float64)
                p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

                _, y, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0)

                self.assertAlmostEqual(float(y[-1, 0]), 2.0, delta=0.05)

    def test_07_energy_conservation(self) -> None:
        vf: VarFactory = VarFactory()
        x: Var = vf.add_var("pos")
        v: Var = vf.add_var("vel")
        dx: Var = vf.add_diff_var(name = "d_pos", base_var=x)
        dv: Var = vf.add_diff_var(name="d_vel", base_var=v)
        osc_block: Block = Block(name="Oscillator", state_vars=list([x, v]), state_eqs=list([v, -x]),diff_vars=list([dx,dv]), parameters=dict())

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                # Trapezoidal
                solver_trap, prob_trap = self.make_solver(solver_class, osc_block, 20.0, 0.1,
                                                          DynamicIntegrationMethod.DaeTrapezoidal)
                x0: np.ndarray = prob_trap.get_x0()
                dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
                x0[0] = 1.0  # pos=1
                dx0[1] = -1.0  # d_vel=-1
                p0: np.ndarray = np.zeros(prob_trap.get_variable_parameter_number(), dtype=np.float64)

                _, y_trap, _ = solver_trap.simulate(x0=x0, dx0=dx0, params0=p0)
                amp_trap: float = float(np.max(np.abs(y_trap[-20:, 0])))
                self.assertGreater(amp_trap, 0.95)

                # Backward Euler
                solver_be, prob_be = self.make_solver(solver_class, osc_block, 20.0, 0.1,
                                                      DynamicIntegrationMethod.DaeBackEuler)
                x0_be: np.ndarray = prob_be.get_x0()
                dx0_be: np.ndarray = np.zeros_like(x0_be, dtype=np.float64)
                x0_be[0] = 1.0
                dx0_be[1] = -1.0
                p0_be: np.ndarray = np.zeros(prob_be.get_variable_parameter_number(), dtype=np.float64)

                _, y_be, _ = solver_be.simulate(x0=x0_be, dx0=dx0_be, params0=p0_be)
                amp_be: float = float(np.max(np.abs(y_be[-20:, 0])))
                self.assertLess(amp_be, 0.5)

    def test_08_time_dependent_forcing(self) -> None:
        x: Var = Var("x")
        t_driver: Var = Var("t_driver")
        forcing_block: Block = Block(
            name="Forcing", state_vars=list([x]), state_eqs=list([t_driver]),
            event_dict=dict({t_driver: Const(0.0)}), parameters=dict()
        )

        for solver_class in self._solvers_to_test:
            with self.subTest(solver=solver_class.__name__):
                solver, prob = self.make_solver(solver_class, forcing_block, 2.0, 0.1,
                                                DynamicIntegrationMethod.DaeTrapezoidal)

                idx_t: int = prob.uid2idx_event_params.get(t_driver.uid, 0)
                sync_updater: SyncTimeWrapper = SyncTimeWrapper(idx_t=idx_t)

                x0: np.ndarray = prob.get_x0()
                dx0: np.ndarray = np.zeros_like(x0, dtype=np.float64)
                p0: np.ndarray = np.zeros(prob.get_variable_parameter_number(), dtype=np.float64)

                _, y, _ = solver.simulate(x0=x0, dx0=dx0, params0=p0, boundary_updater=sync_updater)

                expected: float = (2.0 ** 2) / 2.0
                self.assertAlmostEqual(float(y[-1, 0]), expected, places=2)


if __name__ == '__main__':
    unittest.main()