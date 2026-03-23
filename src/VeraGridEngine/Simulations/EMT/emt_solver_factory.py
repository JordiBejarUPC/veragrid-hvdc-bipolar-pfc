# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import EmtSolverTypes
from VeraGridEngine.Simulations.driver_template import DummySignal

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonDiagnosticsConfig


EMT_SOLVER_CLASS_MAP = {
    EmtSolverTypes.Symbolic: JitSymbolicSolver,
    EmtSolverTypes.Automatic: JitAdSolver,
    EmtSolverTypes.StructuralAD: StructuralVectorizedSolver,
    EmtSolverTypes.StructuralCompiled: StructuralCompiledSolver,
}


def build_emt_solver(options: EmtOptions,
                     problem: EmtProblemTemplate,
                     t0: float,
                     t_end: float,
                     h: float,
                     method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
                     newton_diag_config: NewtonDiagnosticsConfig | None = None):

    if options.solver_type in EMT_SOLVER_CLASS_MAP:
        solver_cls = EMT_SOLVER_CLASS_MAP[options.solver_type]
    else:
        raise ValueError(f"Unsupported EMT solver type: {options.solver_type}")

    return solver_cls(problem=problem,
                      t0=t0,
                      t_end=t_end,
                      h=h,
                      method=method,
                      newton_diag_config=newton_diag_config)