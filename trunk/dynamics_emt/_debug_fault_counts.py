from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from VeraGridEngine.enumerations import EmtFaultPlacementSide, FaultType
from trunk.dynamics_emt.scripting_fault_common import (
    FaultCaseConfig,
    _attach_emt_models,
    _build_demo_grid,
    _run_power_flow,
)
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes


grid, _bus_source, _bus_remote, line, source, remote_load = _build_demo_grid()
config = FaultCaseConfig("fault_3ph", "3ph", FaultType.LLL, True, True, True, EmtFaultPlacementSide.FromSide, 0.04, 0.08, 1.0e-3, 1.0e-3)
_source_mdl, line_composite_mdl, _fault_child_mdl, _remote_load_mdl = _attach_emt_models(grid, line, source, remote_load, config)
print("line alg vars", len(line_composite_mdl.algebraic_vars))
print("line alg eqs", len(line_composite_mdl.algebraic_eqs))
print("line state vars", len(line_composite_mdl.state_vars))
print("line state eqs", len(line_composite_mdl.state_eqs))
pf_results = _run_power_flow(grid)
options = EmtOptions(time_step=5.0e-6, simulation_time=0.12, tolerance=1.0e-6, solver_type=EmtSolverTypes.StructuralCompiled, initialization_method=EmtInitializationMethod.Explicit, integration_method=DynamicIntegrationMethod.DaeTrapezoidal, verbose=0)
problem = EmtProblemDae(grid=grid, options=options, pf_results_3ph=None, pf_results=pf_results)
print("sys alg vars", len(problem.get_algebraic_eqs()))
print("sys state vars", len(problem.get_state_eqs()))
print("sys total vars", problem.get_all_vars_number())
print("sys algebraic variable count", problem.get_algebraic_var_number())
print("sys state variable count", problem.get_states_number())
print("sys total equations", len(problem.get_state_eqs()) + len(problem.get_algebraic_eqs()))
