# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import cProfile
import json
import pstats
import numpy as np
from pathlib import Path
from time import perf_counter
from typing import Any, cast, Dict, List, Optional, Tuple

import os
import matplotlib.pyplot as plt
from trunk.dynamics_emt.support.emt_plot_exports import (
    extract_three_phase_matrix,
    get_plot_results_directory,
    save_scalar_plot,
    save_two_panel_three_phase_plot,
)
from trunk.dynamics_emt.support.emt_build_report_exports import (
    normalize_initialization_report,
    normalize_problem_build_report,
)

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions

from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block as find_name_in_symbolic_block

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph


from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_3ph_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import (BranchImpedanceMode, DynamicIntegrationMethod, EmtInitializationMethod,
                                         EmtSolverTypes, ShuntConnectionType, SolverType,
                                         VarPowerFlowRefferenceType)

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

profiler = cProfile.Profile()

def find_name_in_block(name: str, block: Block):
    """
    Return one symbolic variable by name from a block tree.

    :param name: Variable name.
    :param block: Root block.
    :return: Matching symbolic variable or None.
    """
    return find_name_in_symbolic_block(name, block)

grid = MultiCircuit(Sbase=2.0, fbase=50.0)

# Buses
vnom = 10 #kV
bus0 = Bus(name="Bus0", Vnom=vnom, is_slack=True)
bus1 = Bus(name="Bus1", Vnom=vnom)

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
line0 = Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)

# physical configuration (Overhead line tower)
tower = OverheadLineType(name="Tower", Vnom=vnom)
wire = Wire(name="Panther 30/7 ACSR",
                diameter=21.0,
                diameter_internal=9.0,
                is_tube=True,
                r=0.1363,
                max_current=1)
tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
tower.compute()

# Aplicar física a la línea
line0.apply_template(tower, grid.Sbase, grid.fBase)

# load
# P=1.0
# Q= 0.999999
# P_ph = P/3
# Q_ph = Q/3
R_ph =100 #ohm
v_ph = vnom / (3**0.5)
P_ph = (v_ph**2) / R_ph # kv*kv/ohm = MW
Q_ph = 0.0
load = Load(name="load",P1= P_ph, P2= P_ph, P3= P_ph, Q1= Q_ph, Q2= Q_ph, Q3= Q_ph)
load.conn = ShuntConnectionType.GroundedStar

# Generators
gen0 = Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=0.001, x1=1.7)
# r1=Ra, x1=xd'

grid.add_line(line0)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_load(bus=bus1, api_obj=load)

for bus in grid.buses:
    get_bus_emt_template(grid, bus)

######################################################################################################
# Build EMT models
######################################################################################################
# generator
gen_mdl = get_generator_thevenin_rl_emt_template(vf=grid.emt_var_factory).block

# line
line_mdl = get_pi_line_emt_template(grid = grid, line = line0).block

# load
load_mdl = get_load_ZIP_3ph_emt_template(vf = grid.emt_var_factory).block

# connection with buses
gen_mdl.connect([gen_mdl.in_vars[0]], [bus0.emt_model.out_vars[0]]) # v_A
gen_mdl.connect([gen_mdl.in_vars[1]], [bus0.emt_model.out_vars[1]]) # v_B
gen_mdl.connect([gen_mdl.in_vars[2]], [bus0.emt_model.out_vars[2]]) # v_C


line_mdl.connect([line_mdl.in_vars[0]], [bus0.emt_model.out_vars[0]]) # line vf_A
line_mdl.connect([line_mdl.in_vars[1]], [bus0.emt_model.out_vars[1]]) # line vf_B
line_mdl.connect([line_mdl.in_vars[2]], [bus0.emt_model.out_vars[2]]) # line vf_C

line_mdl.connect([line_mdl.in_vars[3]], [bus1.emt_model.out_vars[0]]) # line vt_A
line_mdl.connect([line_mdl.in_vars[4]], [bus1.emt_model.out_vars[1]]) # line vt_B
line_mdl.connect([line_mdl.in_vars[5]], [bus1.emt_model.out_vars[2]]) # line vt_C

# u_gov = find_name_in_block("u_gov1", gov1_mdl)

load_mdl.connect([load_mdl.in_vars[0]], [bus1.emt_model.out_vars[0]]) # v_A
load_mdl.connect([load_mdl.in_vars[1]], [bus1.emt_model.out_vars[1]]) # v_B
load_mdl.connect([load_mdl.in_vars[2]], [bus1.emt_model.out_vars[2]]) # v_C

# attach emt models to VeraGrid objects.
# The generator must stay attached as an injection model so the topology
# validator counts its voltage inputs at the slack bus.
line0.emt_model = line_mdl
load.emt_model = load_mdl
gen0.emt_model = gen_mdl

pf_options = PowerFlowOptions(
    solver_type=SolverType.NR,
    retry_with_other_methods=False,
    verbose=0,
    initialize_with_existing_solution=True,
    tolerance=1e-6,
    max_iter=25,
    control_q=False,
    control_taps_modules=True,
    control_taps_phase=True,
    control_remote_voltage=True,
    orthogonalize_controls=True,
    apply_temperature_correction=True,
    branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=False,
    generate_report=False,
)

power_flow = PowerFlowDriver3Ph(grid, pf_options)
power_flow.run()
res = power_flow.results
print("res.m (branch number)= ", res.m)
print("res.n (bus number)= ", res.n)
print("res.n_gen = ", res.n_gen)
print("res.n_load ", res.n_load)
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
print("res.load_names = ", res.load_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage_A = ", res.voltage_A)
print("res.voltage_B = ", res.voltage_B)
print("res.voltage_C = ", res.voltage_C)
print("res.Sbus_A = ", res.Sbus_A)
print("res.Sbus_B = ", res.Sbus_B)
print("res.Sbus_C = ", res.Sbus_C)
print("res.Sf_A = ", res.Sf_A)
print("res.Sf_B = ", res.Sf_B)
print("res.Sf_C = ", res.Sf_C)
print("res.St_A = ", res.St_A)
print("res.St_B = ", res.St_B)
print("res.St_C = ", res.St_C)

print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())


def read_env_flag(env_name: str, default_value: bool) -> bool:
    """
    Read one boolean flag from the environment.

    :param env_name: Environment variable name.
    :param default_value: Default boolean value.
    :return: Parsed boolean flag.
    """
    raw_value: Optional[str] = os.environ.get(env_name, None)

    if raw_value is None:
        return default_value
    else:
        normalized_value: str = raw_value.strip().lower()

        if normalized_value in ("1", "true", "yes", "on"):
            return True
        else:
            return False

# ==============================================================================
# SELECT YOUR SOLVER HERE ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED")
# ==============================================================================
CHOSEN_SOLVER = os.environ.get("VERAGRID_EMT_SOLVER", "COMPILED").strip().upper()
REFERENCE_SOLVER = os.environ.get("VERAGRID_EMT_REFERENCE_SOLVER", "SYMBOLIC").strip().upper()
RUN_ALL_SOLVERS = read_env_flag("VERAGRID_EMT_RUN_ALL_SOLVERS", False)
ENABLE_PLOTS = read_env_flag("VERAGRID_EMT_ENABLE_PLOTS", True)
ENABLE_NEWTON_TRACE = read_env_flag("VERAGRID_EMT_ENABLE_NEWTON_TRACE", False)
SHOW_INIT_GUESS_TABLE = read_env_flag("VERAGRID_EMT_SHOW_INIT_GUESS_TABLE", False)
BENCHMARK_COMPILED_COLD_WARM = read_env_flag("VERAGRID_EMT_BENCHMARK_COMPILED_COLD_WARM", False)
BENCHMARK_ALL_SOLVERS_COLD_WARM = read_env_flag("VERAGRID_EMT_BENCHMARK_ALL_SOLVERS_COLD_WARM", False)
DENSE_THRESHOLD = 0
SOLVER_VERBOSE = read_env_flag("VERAGRID_EMT_SOLVER_VERBOSE", False)
CHOSEN_INIT_METHOD = os.environ.get("VERAGRID_EMT_INIT_METHOD", "AUTO").strip().upper()
PLOT_CASE_NAME = "thevequiv_piline_zipload"

SOLVER_TYPE_MAP = {
    "SYMBOLIC": EmtSolverTypes.Symbolic,
    "AD": EmtSolverTypes.Automatic,
    "VECTORIZED": EmtSolverTypes.StructuralAD,
    "COMPILED": EmtSolverTypes.StructuralCompiled,
}

ALL_SOLVER_KEYS = ["SYMBOLIC", "AD", "VECTORIZED", "COMPILED"]
ALL_INIT_METHOD_KEYS = ["EXPLICIT", "CONSISTENTNEWTON", "PSEUDOTRANSIENT", "AUTO"]

if REFERENCE_SOLVER in ALL_SOLVER_KEYS:
    BENCHMARK_SOLVER_KEYS = [REFERENCE_SOLVER] + [key for key in ALL_SOLVER_KEYS if key != REFERENCE_SOLVER]
else:
    BENCHMARK_SOLVER_KEYS = list(ALL_SOLVER_KEYS)

if CHOSEN_SOLVER not in SOLVER_TYPE_MAP:
    raise ValueError(f"Solver '{CHOSEN_SOLVER}' no reconocido. Usa SYMBOLIC, AD, VECTORIZED o COMPILED.")

if CHOSEN_INIT_METHOD not in ALL_INIT_METHOD_KEYS:
    raise ValueError(f"Initialization method '{CHOSEN_INIT_METHOD}' no reconocido. Usa EXPLICIT, CONSISTENTNEWTON, PSEUDOTRANSIENT o AUTO.")


INIT_METHOD_MAP = {
    "EXPLICIT": EmtInitializationMethod.Explicit,
    "CONSISTENTNEWTON": EmtInitializationMethod.ConsistentNewton,
    "PSEUDOTRANSIENT": EmtInitializationMethod.PseudoTransient,
    "AUTO": EmtInitializationMethod.Auto,
}


def build_emt_options(chosen_solver: str, initialization_method: EmtInitializationMethod) -> EmtOptions:
    """
    Build one EMT option set for this benchmark script.

    :param chosen_solver: Solver key.
    :param initialization_method: Initialization workflow.
    :return: EMT options.
    """
    return EmtOptions(time_step=5e-6,
                      simulation_time=0.06,
                      tolerance=1e-6,
                      solver_type=SOLVER_TYPE_MAP[chosen_solver],
                      integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
                      initialization_method=initialization_method,
                      verbose=0)

options = build_emt_options(CHOSEN_SOLVER, INIT_METHOD_MAP[CHOSEN_INIT_METHOD])


class SolverTraceSummary:
    """
    Compact summary of Newton diagnostics for one solver run.
    """

    __slots__ = (
        '_final_residual_inf',
        '_maximum_residual_inf',
        '_total_newton_iterations',
        '_last_step_newton_iterations',
    )

    def __init__(self,
                 final_residual_inf: float,
                 maximum_residual_inf: float,
                 total_newton_iterations: int,
                 last_step_newton_iterations: int) -> None:
        """
        Build one Newton summary.

        :param final_residual_inf: Final infinity norm of the residual.
        :param maximum_residual_inf: Maximum residual seen during the run.
        :param total_newton_iterations: Total Newton iterations in the run.
        :param last_step_newton_iterations: Newton iterations used by the last time step.
        :return: None.
        """
        self._final_residual_inf: float = float(final_residual_inf)
        self._maximum_residual_inf: float = float(maximum_residual_inf)
        self._total_newton_iterations: int = int(total_newton_iterations)
        self._last_step_newton_iterations: int = int(last_step_newton_iterations)

    def get_final_residual_inf(self) -> float:
        """
        Return the final residual infinity norm.

        :return: Final residual infinity norm.
        """
        return self._final_residual_inf

    def get_maximum_residual_inf(self) -> float:
        """
        Return the maximum residual infinity norm seen during the run.

        :return: Maximum residual infinity norm.
        """
        return self._maximum_residual_inf

    def get_total_newton_iterations(self) -> int:
        """
        Return the total number of Newton iterations.

        :return: Total Newton iterations.
        """
        return self._total_newton_iterations

    def get_last_step_newton_iterations(self) -> int:
        """
        Return the Newton iterations used by the last time step.

        :return: Last-step Newton iterations.
        """
        return self._last_step_newton_iterations


class SolverBenchmarkResult:
    """
    Validation and timing summary for one EMT backend.
    """

    __slots__ = (
        '_solver_key',
        '_problem_build_s',
        '_solver_init_s',
        '_solver_build_s',
        '_simulate_s',
        '_solver_total_s',
        '_loop_s',
        '_y_max_abs_diff',
        '_dy_max_abs_diff',
        '_trace_summary',
        '_build_stats',
        '_steps',
        '_y_shape',
        '_dy_shape',
        '_problem_build_report',
        '_initialization_report',
    )

    def __init__(self,
                 solver_key: str,
                 problem_build_s: float,
                 solver_init_s: float,
                 solver_build_s: float,
                 simulate_s: float,
                 solver_total_s: float,
                 loop_s: float,
                 y_max_abs_diff: float,
                 dy_max_abs_diff: float,
                 trace_summary: SolverTraceSummary,
                 build_stats: Dict[str, float],
                 steps: int,
                 y_shape: tuple[int, ...],
                 dy_shape: tuple[int, ...],
                 problem_build_report: Dict[str, float],
                 initialization_report: Dict[str, object]) -> None:
        """
        Build one benchmark result.

        :param solver_key: Solver identifier.
        :param problem_build_s: Problem build time in seconds.
        :param solver_init_s: Solver initialization time in seconds.
        :param solver_build_s: Backend build time in seconds.
        :param simulate_s: Simulation time in seconds.
        :param solver_total_s: Total solver time in seconds.
        :param loop_s: Integration-loop time in seconds.
        :param y_max_abs_diff: Maximum absolute difference against the reference y.
        :param dy_max_abs_diff: Maximum absolute difference against the reference dy.
        :param trace_summary: Newton diagnostics summary.
        :param build_stats: Backend build statistics.
        :param steps: Number of time steps.
        :param y_shape: Shape of the state trajectory matrix.
        :param dy_shape: Shape of the differential trajectory matrix.
        :return: None.
        """
        self._solver_key: str = solver_key
        self._problem_build_s: float = float(problem_build_s)
        self._solver_init_s: float = float(solver_init_s)
        self._solver_build_s: float = float(solver_build_s)
        self._simulate_s: float = float(simulate_s)
        self._solver_total_s: float = float(solver_total_s)
        self._loop_s: float = float(loop_s)
        self._y_max_abs_diff: float = float(y_max_abs_diff)
        self._dy_max_abs_diff: float = float(dy_max_abs_diff)
        self._trace_summary: SolverTraceSummary = trace_summary
        self._build_stats: Dict[str, float] = dict(build_stats)
        self._steps: int = int(steps)
        self._y_shape: tuple[int, ...] = tuple(y_shape)
        self._dy_shape: tuple[int, ...] = tuple(dy_shape)
        self._problem_build_report: Dict[str, float] = dict(problem_build_report)
        self._initialization_report: Dict[str, object] = dict(initialization_report)

    def get_solver_key(self) -> str:
        """
        Return the solver identifier.

        :return: Solver identifier.
        """
        return self._solver_key

    def get_problem_build_s(self) -> float:
        """
        Return the problem-build time.

        :return: Problem-build time in seconds.
        """
        return self._problem_build_s

    def get_solver_init_s(self) -> float:
        """
        Return the solver initialization time.

        :return: Solver initialization time in seconds.
        """
        return self._solver_init_s

    def get_solver_build_s(self) -> float:
        """
        Return the backend build time.

        :return: Backend build time in seconds.
        """
        return self._solver_build_s

    def get_simulate_s(self) -> float:
        """
        Return the simulation time.

        :return: Simulation time in seconds.
        """
        return self._simulate_s

    def get_solver_total_s(self) -> float:
        """
        Return the total solver time.

        :return: Total solver time in seconds.
        """
        return self._solver_total_s

    def get_loop_s(self) -> float:
        """
        Return the integration-loop time.

        :return: Loop time in seconds.
        """
        return self._loop_s

    def get_y_max_abs_diff(self) -> float:
        """
        Return the maximum y difference against the reference.

        :return: Maximum absolute difference.
        """
        return self._y_max_abs_diff

    def get_dy_max_abs_diff(self) -> float:
        """
        Return the maximum dy difference against the reference.

        :return: Maximum absolute difference.
        """
        return self._dy_max_abs_diff

    def get_trace_summary(self) -> SolverTraceSummary:
        """
        Return the Newton diagnostics summary.

        :return: Newton diagnostics summary.
        """
        return self._trace_summary

    def get_build_stats(self) -> Dict[str, float]:
        """
        Return the backend build statistics.

        :return: Backend build statistics.
        """
        return dict(self._build_stats)

    def get_steps(self) -> int:
        """
        Return the number of accepted time steps.

        :return: Number of accepted time steps.
        :rtype: int
        """
        return self._steps

    def get_y_shape(self) -> tuple[int, ...]:
        """
        Return the state-trajectory shape.

        :return: State-trajectory shape.
        :rtype: tuple[int, ...]
        """
        return tuple(self._y_shape)

    def get_dy_shape(self) -> tuple[int, ...]:
        """
        Return the differential-trajectory shape.

        :return: Differential-trajectory shape.
        :rtype: tuple[int, ...]
        """
        return tuple(self._dy_shape)

    def get_problem_build_report(self) -> Dict[str, float]:
        """
        Return the EMT problem build report.

        :return: EMT problem build report.
        :rtype: Dict[str, float]
        """
        return dict(self._problem_build_report)

    def get_initialization_report(self) -> Dict[str, object]:
        """
        Return the EMT initialization report.

        :return: EMT initialization report.
        :rtype: Dict[str, object]
        """
        return dict(self._initialization_report)


class SolverColdWarmBenchmarkResult:
    """
    Cold/warm timing summary for one EMT backend.
    """

    __slots__ = (
        '_solver_key',
        '_problem_build_s',
        '_solver_init_s',
        '_cold_build_s',
        '_cold_sim_s',
        '_warm_sim_s',
        '_speedup',
        '_y_max_abs_diff',
        '_dy_max_abs_diff',
        '_cold_trace_summary',
        '_warm_trace_summary',
        '_build_stats',
        '_problem_build_report',
        '_initialization_report',
    )

    def __init__(self,
                 solver_key: str,
                 problem_build_s: float,
                 solver_init_s: float,
                 cold_build_s: float,
                 cold_sim_s: float,
                 warm_sim_s: float,
                 speedup: float,
                 y_max_abs_diff: float,
                 dy_max_abs_diff: float,
                 cold_trace_summary: SolverTraceSummary,
                 warm_trace_summary: SolverTraceSummary,
                 build_stats: Dict[str, float],
                 problem_build_report: Dict[str, float],
                 initialization_report: Dict[str, object]) -> None:
        """
        Build one cold/warm benchmark result.

        :param solver_key: Solver identifier.
        :param problem_build_s: Problem build time in seconds.
        :param solver_init_s: Solver initialization time in seconds.
        :param cold_build_s: First backend build time in seconds.
        :param cold_sim_s: First simulation time in seconds.
        :param warm_sim_s: Second simulation time in seconds.
        :param speedup: Cold-to-warm speedup factor.
        :param y_max_abs_diff: Maximum y difference between cold and warm runs.
        :param dy_max_abs_diff: Maximum dy difference between cold and warm runs.
        :param cold_trace_summary: Cold-run Newton summary.
        :param warm_trace_summary: Warm-run Newton summary.
        :param build_stats: Backend build statistics.
        :return: None.
        :rtype: None
        """
        self._solver_key: str = solver_key
        self._problem_build_s: float = float(problem_build_s)
        self._solver_init_s: float = float(solver_init_s)
        self._cold_build_s: float = float(cold_build_s)
        self._cold_sim_s: float = float(cold_sim_s)
        self._warm_sim_s: float = float(warm_sim_s)
        self._speedup: float = float(speedup)
        self._y_max_abs_diff: float = float(y_max_abs_diff)
        self._dy_max_abs_diff: float = float(dy_max_abs_diff)
        self._cold_trace_summary: SolverTraceSummary = cold_trace_summary
        self._warm_trace_summary: SolverTraceSummary = warm_trace_summary
        self._build_stats: Dict[str, float] = dict(build_stats)
        self._problem_build_report: Dict[str, float] = dict(problem_build_report)
        self._initialization_report: Dict[str, object] = dict(initialization_report)

    def get_solver_key(self) -> str:
        """
        Return the solver identifier.

        :return: Solver identifier.
        :rtype: str
        """
        return self._solver_key

    def get_problem_build_s(self) -> float:
        """
        Return the problem-build time.

        :return: Problem-build time.
        :rtype: float
        """
        return self._problem_build_s

    def get_solver_init_s(self) -> float:
        """
        Return the solver initialization time.

        :return: Solver initialization time.
        :rtype: float
        """
        return self._solver_init_s

    def get_cold_build_s(self) -> float:
        """
        Return the first backend-build time.

        :return: First backend-build time.
        :rtype: float
        """
        return self._cold_build_s

    def get_cold_sim_s(self) -> float:
        """
        Return the first simulation time.

        :return: First simulation time.
        :rtype: float
        """
        return self._cold_sim_s

    def get_warm_sim_s(self) -> float:
        """
        Return the second simulation time.

        :return: Second simulation time.
        :rtype: float
        """
        return self._warm_sim_s

    def get_speedup(self) -> float:
        """
        Return the cold-to-warm speedup factor.

        :return: Speedup factor.
        :rtype: float
        """
        return self._speedup

    def get_y_max_abs_diff(self) -> float:
        """
        Return the maximum y difference between cold and warm runs.

        :return: Maximum y difference.
        :rtype: float
        """
        return self._y_max_abs_diff

    def get_dy_max_abs_diff(self) -> float:
        """
        Return the maximum dy difference between cold and warm runs.

        :return: Maximum dy difference.
        :rtype: float
        """
        return self._dy_max_abs_diff

    def get_cold_trace_summary(self) -> SolverTraceSummary:
        """
        Return the cold-run Newton summary.

        :return: Cold-run Newton summary.
        :rtype: SolverTraceSummary
        """
        return self._cold_trace_summary

    def get_warm_trace_summary(self) -> SolverTraceSummary:
        """
        Return the warm-run Newton summary.

        :return: Warm-run Newton summary.
        :rtype: SolverTraceSummary
        """
        return self._warm_trace_summary

    def get_build_stats(self) -> Dict[str, float]:
        """
        Return the backend build statistics.

        :return: Backend build statistics.
        :rtype: Dict[str, float]
        """
        return dict(self._build_stats)

    def get_problem_build_report(self) -> Dict[str, float]:
        """
        Return the EMT problem build report.

        :return: EMT problem build report.
        :rtype: Dict[str, float]
        """
        return dict(self._problem_build_report)

    def get_initialization_report(self) -> Dict[str, object]:
        """
        Return the EMT initialization report.

        :return: EMT initialization report.
        :rtype: Dict[str, object]
        """
        return dict(self._initialization_report)


def create_problem(enable_trace: bool = False) -> EmtProblemDae:
    """
    Build the real EMT problem used by the backend benchmark.

    :param enable_trace: Whether to attach a Newton diagnostics collector.
    :return: Configured EMT problem.
    """
    local_problem: EmtProblemDae = EmtProblemDae(grid=grid,
                                                 options=options,
                                                 pf_results_3Ph=res,
                                                 pf_results=None)

    if enable_trace:
        local_problem.set_newton_trace_collector(NewtonTraceCollector())
    else:
        local_problem = local_problem

    return local_problem


def compute_max_abs_diff(reference_array: Optional[np.ndarray],
                         candidate_array: np.ndarray) -> float:
    """
    Compute the maximum absolute difference against a reference array.

    :param reference_array: Reference array or ``None`` for the first backend.
    :param candidate_array: Candidate array.
    :return: Maximum absolute difference.
    """
    if reference_array is None:
        return 0.0
    else:
        return float(np.max(np.abs(candidate_array - reference_array)))


def summarize_newton_trace(problem: EmtProblemDae) -> SolverTraceSummary:
    """
    Summarize the Newton diagnostics collected during the solver run.

    :param problem: EMT problem holding the optional trace collector.
    :return: Newton diagnostics summary.
    """
    collector = problem.get_newton_trace_collector()

    if collector is not None and len(collector.records) > 0:
        records: List[Dict[str, Any]] = list(collector.records)
        total_newton_iterations: int = len(records)
        last_record: Dict[str, Any] = records[-1]
        final_step_index: int = int(last_record.get('step', -1))
        last_step_newton_iterations: int = 0
        record_index: int = 0
        maximum_residual_inf: float = 0.0

        while record_index < total_newton_iterations:
            current_record: Dict[str, Any] = records[record_index]
            residual_value_any: Any = current_record.get('res_norm_inf', None)

            if residual_value_any is not None:
                residual_value: float = float(residual_value_any)
                maximum_residual_inf = max(maximum_residual_inf, residual_value)
            else:
                maximum_residual_inf = maximum_residual_inf

            if int(current_record.get('step', -2)) == final_step_index:
                last_step_newton_iterations += 1
            else:
                last_step_newton_iterations = last_step_newton_iterations

            record_index += 1

        final_residual_any: Any = last_record.get('res_norm_inf', None)

        if final_residual_any is not None:
            final_residual_inf: float = float(final_residual_any)
        else:
            final_residual_inf = np.nan
    else:
        final_residual_inf = np.nan
        maximum_residual_inf = np.nan
        total_newton_iterations = 0
        last_step_newton_iterations = 0

    return SolverTraceSummary(
        final_residual_inf=final_residual_inf,
        maximum_residual_inf=maximum_residual_inf,
        total_newton_iterations=total_newton_iterations,
        last_step_newton_iterations=last_step_newton_iterations,
    )


def create_solver(solver_key: str, local_problem: EmtProblemDae):
    if solver_key == "SYMBOLIC":
        return JitSymbolicSolver(problem = local_problem,
                                 t0 = 0.0,
                                 t_end = options.simulation_time,
                                 h = options.time_step,
                                 method=options.integration_method,
                                 pred_method=DynamicIntegrationMethod.OdeEuler,
                                 dense_threshold=DENSE_THRESHOLD,
                                 verbose = SOLVER_VERBOSE)

    if solver_key == "AD":
        return JitAdSolver(problem = local_problem,
                           t0 = 0.0,
                           t_end = options.simulation_time,
                           h = options.time_step,
                           method=options.integration_method,
                           pred_method=DynamicIntegrationMethod.OdeEuler,
                           dense_threshold=DENSE_THRESHOLD,
                           verbose = SOLVER_VERBOSE)

    if solver_key == "VECTORIZED":
        return StructuralVectorizedSolver(problem = local_problem,
                                          t0 = 0.0,
                                          t_end = options.simulation_time,
                                          h = options.time_step,
                                          method=options.integration_method,
                                          pred_method=DynamicIntegrationMethod.OdeEuler,
                                          dense_threshold=DENSE_THRESHOLD,
                                          verbose = SOLVER_VERBOSE,
                                          auto_vectorization=False)

    if solver_key == "COMPILED":
        return StructuralCompiledSolver(problem = local_problem,
                                    t0 = 0.0,
                                    t_end = options.simulation_time,
                                    h = options.time_step,
                                    method=options.integration_method,
                                    pred_method=DynamicIntegrationMethod.OdeEuler,
                                    dense_threshold=DENSE_THRESHOLD,
                                    verbose = SOLVER_VERBOSE,
                                    auto_build=False)

    raise ValueError(f"Solver '{solver_key}' no reconocido. Usa SYMBOLIC, AD, VECTORIZED o COMPILED.")


def get_solver_loop_time(solver: Any) -> float:
    """
    Return the integration-loop time when the solver exposes it.

    :param solver: Solver instance.
    :return: Loop time in seconds or NaN.
    """
    if isinstance(solver, (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver)):
        return float(solver.get_last_sim_loop_time())
    else:
        return np.nan


def get_solver_build_stats(solver: Any) -> Dict[str, float]:
    """
    Return backend build statistics when available.

    :param solver: Solver instance.
    :return: Build statistics dictionary.
    """
    if isinstance(solver, (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver)):
        raw_stats_any: Any = solver.get_backend_build_stats()
        out_stats: Dict[str, float] = dict()

        if isinstance(raw_stats_any, dict):
            for key, value in raw_stats_any.items():
                out_stats[str(key)] = float(value)
        else:
            out_stats = out_stats

        return out_stats
    else:
        return dict()


def get_solver_runtime_stats(solver: Any) -> Dict[str, float]:
    """
    Return runtime statistics when the solver exposes them.

    :param solver: Solver instance.
    :return: Runtime statistics dictionary.
    """
    if isinstance(solver, (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver)):
        raw_stats_any: Any = solver.get_last_runtime_stats()
        out_stats: Dict[str, float] = dict()

        if isinstance(raw_stats_any, dict):
            for key, value in raw_stats_any.items():
                out_stats[str(key)] = float(value)
        else:
            out_stats = out_stats

        return out_stats
    else:
        return dict()


def print_solver_runtime_stats(solver: Any, label: str) -> None:
    """
    Print runtime statistics when available.

    :param solver: Solver instance.
    :param label: Text label for the printed block.
    :return: None.
    """
    runtime_stats: Dict[str, float] = get_solver_runtime_stats(solver)

    if len(runtime_stats) > 0:
        print(label)

        for key, value in runtime_stats.items():
            print(f"  {key}: {value:.0f}" if abs(value - round(value)) < 1e-12 else f"  {key}: {value:.6f}")
    else:
        runtime_stats = runtime_stats


def run_single_solver_trajectory(
        solver_key: str,
        enable_trace: bool,
) -> Tuple[EmtProblemDae, Any, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build one solver, execute one simulation and return the raw trajectories.

    :param solver_key: Solver identifier.
    :type solver_key: str
    :param enable_trace: Whether to enable Newton trace collection.
    :type enable_trace: bool
    :return: Tuple ``(problem, solver, t, y, dy)``.
    :rtype: Tuple[EmtProblemDae, Any, np.ndarray, np.ndarray, np.ndarray]
    """
    local_problem: EmtProblemDae = create_problem(enable_trace=enable_trace)
    solver: Any = create_solver(solver_key, local_problem)
    build_solver_backend(solver_key, solver, local_problem)
    boundary_updater: Any = cast(Any, local_problem)
    t_arr: np.ndarray
    y_arr: np.ndarray
    dy_arr: np.ndarray
    t_arr, y_arr, dy_arr = solver.simulate(boundary_updater=boundary_updater)
    return local_problem, solver, t_arr, y_arr, dy_arr


def export_demo_plots(
        problem: EmtProblemDae,
        time_values: np.ndarray,
        y_values: np.ndarray,
        solver_key: str,
        output_root_name: str = "plot_results",
) -> List[Path]:
    """
    Export diagnostic plots for the interactive ZIP-load demo.

    :param problem: EMT problem instance.
    :type problem: EmtProblemDae
    :param time_values: Time vector.
    :type time_values: np.ndarray
    :param y_values: State trajectory.
    :type y_values: np.ndarray
    :param solver_key: Solver identifier.
    :type solver_key: str
    :param output_root_name: Root folder name used for the plot exports.
    :type output_root_name: str
    :return: Generated plot paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_plot_results_directory(PLOT_CASE_NAME, solver_key, output_root_name)
    generated_paths: List[Path] = list()

    bus0_voltages: np.ndarray = extract_three_phase_matrix(problem, y_values, bus0.emt_model.out_vars)
    bus1_voltages: np.ndarray = extract_three_phase_matrix(problem, y_values, bus1.emt_model.out_vars)
    generator_currents: np.ndarray = extract_three_phase_matrix(problem, y_values, gen_mdl.out_vars)
    load_current_triplet: Tuple[Any, Any, Any] = (
        find_name_in_block("i_A_ZIP_Load_EMT_3ph", load_mdl),
        find_name_in_block("i_B_ZIP_Load_EMT_3ph", load_mdl),
        find_name_in_block("i_C_ZIP_Load_EMT_3ph", load_mdl),
    )
    load_currents: np.ndarray = -extract_three_phase_matrix(problem, y_values, load_current_triplet)
    theta_var: Any = find_name_in_block("theta_emt_thevenin_eq_generator_template", gen_mdl)
    theta_values: np.ndarray = y_values[:, problem.get_var_idx(theta_var)]

    voltage_path: Path = output_dir / "bus_voltages.png"
    current_path: Path = output_dir / "source_load_currents.png"
    theta_path: Path = output_dir / "generator_theta.png"

    save_two_panel_three_phase_plot(
        file_path=voltage_path,
        time_values=time_values,
        top_triplet=(bus0_voltages[:, 0], bus0_voltages[:, 1], bus0_voltages[:, 2]),
        top_title="Bus 0 Voltages",
        top_ylabel="Voltage [pu]",
        top_legend_prefix="Bus0",
        bottom_triplet=(bus1_voltages[:, 0], bus1_voltages[:, 1], bus1_voltages[:, 2]),
        bottom_title="Bus 1 Voltages",
        bottom_ylabel="Voltage [pu]",
        bottom_legend_prefix="Bus1",
    )
    generated_paths.append(voltage_path)

    save_two_panel_three_phase_plot(
        file_path=current_path,
        time_values=time_values,
        top_triplet=(generator_currents[:, 0], generator_currents[:, 1], generator_currents[:, 2]),
        top_title="Generator Currents",
        top_ylabel="Current [pu]",
        top_legend_prefix="Gen",
        bottom_triplet=(load_currents[:, 0], load_currents[:, 1], load_currents[:, 2]),
        bottom_title="ZIP Load Currents",
        bottom_ylabel="Current [pu]",
        bottom_legend_prefix="Load",
    )
    generated_paths.append(current_path)

    save_scalar_plot(
        file_path=theta_path,
        time_values=time_values,
        values=theta_values,
        title="Generator Electrical Angle",
        y_label="Theta [rad]",
    )
    generated_paths.append(theta_path)

    return generated_paths


def build_full_parameter_vector(problem: EmtProblemDae,
                                current_time: float,
                                previous_state: np.ndarray) -> np.ndarray:
    """
    Build the full runtime-plus-static parameter vector at one time instant.

    :param problem: EMT problem.
    :param current_time: Current time instant.
    :param previous_state: Previously accepted state vector.
    :return: Full parameter vector.
    """
    runtime_params: np.ndarray = np.asarray(problem.event_params_values.copy(), dtype=np.float64)
    runtime_params = np.asarray(problem.def_event_params_fn(runtime_params, current_time), dtype=np.float64)
    static_values: np.ndarray = np.array([parameter.value for parameter in problem.get_parameters_values()], dtype=np.float64)
    full_params: np.ndarray = np.concatenate((runtime_params, static_values))
    problem.update(current_time, previous_state, full_params)

    if runtime_params.shape[0] > 0:
        runtime_params[:] = full_params[:runtime_params.shape[0]]
    else:
        runtime_params = runtime_params

    return np.asarray(full_params, dtype=np.float64)


def build_final_residual_context(t_arr: np.ndarray,
                                 y_arr: np.ndarray,
                                 dy_arr: np.ndarray) -> tuple[float, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build the final-step residual context from the stored trajectories.

    :param t_arr: Time vector.
    :param y_arr: State trajectory.
    :param dy_arr: Differential trajectory.
    :return: Tuple ``(h_eff, x_curr, x_prev, dx_prev, x_prev2)``.
    """
    h_eff: float = float(t_arr[-1] - t_arr[-2])
    x_curr: np.ndarray = np.asarray(y_arr[-1, :], dtype=np.float64)
    x_prev: np.ndarray = np.asarray(y_arr[-2, :], dtype=np.float64)
    dx_prev: np.ndarray = np.asarray(dy_arr[-2, :], dtype=np.float64)

    if y_arr.shape[0] >= 3:
        x_prev2: np.ndarray = np.asarray(y_arr[-3, :], dtype=np.float64)
    else:
        x_prev2 = np.asarray(y_arr[-2, :], dtype=np.float64)

    return h_eff, x_curr, x_prev, dx_prev, x_prev2


def evaluate_final_residual_inf(solver_key: str,
                                solver: Any,
                                problem: EmtProblemDae,
                                t_arr: np.ndarray,
                                y_arr: np.ndarray,
                                dy_arr: np.ndarray) -> float:
    """
    Evaluate the final implicit residual norm for one backend.

    :param solver_key: Solver identifier.
    :param solver: Solver instance.
    :param problem: EMT problem.
    :param t_arr: Time vector.
    :param y_arr: State trajectory.
    :param dy_arr: Differential trajectory.
    :return: Final residual infinity norm.
    """
    if t_arr.shape[0] >= 2:
        h_eff: float
        x_curr: np.ndarray
        x_prev: np.ndarray
        dx_prev: np.ndarray
        x_prev2: np.ndarray
        h_eff, x_curr, x_prev, dx_prev, x_prev2 = build_final_residual_context(t_arr, y_arr, dy_arr)
        full_params: np.ndarray = build_full_parameter_vector(problem, float(t_arr[-1]), x_prev)
        residual_vector: np.ndarray = np.zeros(problem.get_all_vars_number(), dtype=np.float64)

        # The harness evaluates the same implicit residual relation used by each
        # backend on the final accepted state, so backend mismatches become explicit.
        if solver_key == "SYMBOLIC":
            kernel_list: List[Any] = solver.jit_kernels[options.integration_method]

            for kernel in kernel_list:
                kernel(x_curr, full_params, x_prev, dx_prev, h_eff, residual_vector, x_prev2)
        elif solver_key == "AD":
            kernel_list = solver.jit_kernels_ad[options.integration_method]

            for kernel in kernel_list:
                kernel(x_curr, full_params, x_prev, dx_prev, h_eff, residual_vector, x_prev2)
        elif solver_key == "VECTORIZED":
            solver.fused_residual(x_curr, full_params, x_prev, dx_prev, h_eff, x_prev2, residual_vector)
        elif solver_key == "COMPILED":
            solver._residual_assembler.evaluate(x_curr, full_params, x_prev, dx_prev, h_eff, x_prev2, residual_vector)
        else:
            raise ValueError(f"Solver '{solver_key}' no reconocido. Usa SYMBOLIC, AD, VECTORIZED o COMPILED.")

        return float(np.max(np.abs(residual_vector)))
    else:
        return np.nan


def run_single_solver_benchmark(solver_key: str,
                                reference_y: Optional[np.ndarray],
                                reference_dy: Optional[np.ndarray]) -> tuple[SolverBenchmarkResult, np.ndarray, np.ndarray]:
    """
    Run one backend and compare it against the current reference arrays.

    :param solver_key: Solver identifier.
    :param reference_y: Optional reference state trajectory.
    :param reference_dy: Optional reference differential trajectory.
    :return: Tuple ``(result, y_arr, dy_arr)``.
    """
    t_problem_0: float = perf_counter()
    local_problem: EmtProblemDae = create_problem(enable_trace=True)
    problem_build_s: float = perf_counter() - t_problem_0

    t_solver_0: float = perf_counter()
    solver = create_solver(solver_key, local_problem)
    solver_init_s: float = perf_counter() - t_solver_0

    t_build_0: float = perf_counter()
    build_solver_backend(solver_key, solver, local_problem)
    solver_build_s: float = perf_counter() - t_build_0

    boundary_updater = cast(Any, local_problem)
    t_sim_0: float = perf_counter()
    t_arr: np.ndarray
    y_arr: np.ndarray
    dy_arr: np.ndarray
    t_arr, y_arr, dy_arr = solver.simulate(boundary_updater=boundary_updater)
    simulate_s: float = perf_counter() - t_sim_0
    final_residual_inf: float = evaluate_final_residual_inf(solver_key, solver, local_problem, t_arr, y_arr, dy_arr)
    solver_total_s: float = solver_init_s + solver_build_s + simulate_s
    y_max_abs_diff: float = compute_max_abs_diff(reference_y, y_arr)
    dy_max_abs_diff: float = compute_max_abs_diff(reference_dy, dy_arr)
    trace_summary: SolverTraceSummary = summarize_newton_trace(local_problem)
    trace_summary = SolverTraceSummary(
        final_residual_inf=final_residual_inf,
        maximum_residual_inf=trace_summary.get_maximum_residual_inf(),
        total_newton_iterations=trace_summary.get_total_newton_iterations(),
        last_step_newton_iterations=trace_summary.get_last_step_newton_iterations(),
    )
    build_stats: Dict[str, float] = get_solver_build_stats(solver)
    problem_build_report: Dict[str, float] = normalize_problem_build_report(local_problem)
    initialization_report: Dict[str, object] = normalize_initialization_report(local_problem)
    result: SolverBenchmarkResult = SolverBenchmarkResult(
        solver_key=solver_key,
        problem_build_s=problem_build_s,
        solver_init_s=solver_init_s,
        solver_build_s=solver_build_s,
        simulate_s=simulate_s,
        solver_total_s=solver_total_s,
        loop_s=get_solver_loop_time(solver),
        y_max_abs_diff=y_max_abs_diff,
        dy_max_abs_diff=dy_max_abs_diff,
        trace_summary=trace_summary,
        build_stats=build_stats,
        steps=len(t_arr) - 1,
        y_shape=y_arr.shape,
        dy_shape=dy_arr.shape,
        problem_build_report=problem_build_report,
        initialization_report=initialization_report,
    )

    return result, y_arr, dy_arr


def run_single_solver_cold_warm_benchmark(solver_key: str) -> SolverColdWarmBenchmarkResult:
    """
    Run one backend twice to compare cold and warm execution.

    :param solver_key: Solver identifier.
    :type solver_key: str
    :return: Cold/warm benchmark summary.
    :rtype: SolverColdWarmBenchmarkResult
    """
    t_problem_0: float = perf_counter()
    local_problem: EmtProblemDae = create_problem(enable_trace=False)
    problem_build_s: float = perf_counter() - t_problem_0

    t_solver_0: float = perf_counter()
    solver = create_solver(solver_key, local_problem)
    solver_init_s: float = perf_counter() - t_solver_0

    t_build_0: float = perf_counter()
    build_solver_backend(solver_key, solver, local_problem)
    cold_build_s: float = perf_counter() - t_build_0

    boundary_updater = cast(Any, local_problem)

    # The first simulation captures the post-build cold execution path of the solver.
    local_problem.set_newton_trace_collector(NewtonTraceCollector())
    cold_sim_t0: float = perf_counter()
    cold_t: np.ndarray
    cold_y: np.ndarray
    cold_dy: np.ndarray
    cold_t, cold_y, cold_dy = solver.simulate(boundary_updater=boundary_updater)
    cold_sim_s: float = perf_counter() - cold_sim_t0
    cold_final_residual_inf: float = evaluate_final_residual_inf(solver_key, solver, local_problem, cold_t, cold_y, cold_dy)
    cold_trace_summary_raw: SolverTraceSummary = summarize_newton_trace(local_problem)
    cold_trace_summary: SolverTraceSummary = SolverTraceSummary(
        final_residual_inf=cold_final_residual_inf,
        maximum_residual_inf=cold_trace_summary_raw.get_maximum_residual_inf(),
        total_newton_iterations=cold_trace_summary_raw.get_total_newton_iterations(),
        last_step_newton_iterations=cold_trace_summary_raw.get_last_step_newton_iterations(),
    )

    # The second simulation reuses the same solver instance so cached kernels and
    # factorization-related warm state remain available.
    local_problem.set_newton_trace_collector(NewtonTraceCollector())
    warm_sim_t0: float = perf_counter()
    warm_t: np.ndarray
    warm_y: np.ndarray
    warm_dy: np.ndarray
    warm_t, warm_y, warm_dy = solver.simulate(boundary_updater=boundary_updater)
    warm_sim_s: float = perf_counter() - warm_sim_t0
    warm_final_residual_inf: float = evaluate_final_residual_inf(solver_key, solver, local_problem, warm_t, warm_y, warm_dy)
    warm_trace_summary_raw: SolverTraceSummary = summarize_newton_trace(local_problem)
    warm_trace_summary: SolverTraceSummary = SolverTraceSummary(
        final_residual_inf=warm_final_residual_inf,
        maximum_residual_inf=warm_trace_summary_raw.get_maximum_residual_inf(),
        total_newton_iterations=warm_trace_summary_raw.get_total_newton_iterations(),
        last_step_newton_iterations=warm_trace_summary_raw.get_last_step_newton_iterations(),
    )

    if warm_sim_s > 0.0:
        speedup: float = cold_sim_s / warm_sim_s
    else:
        speedup = np.inf

    return SolverColdWarmBenchmarkResult(
        solver_key=solver_key,
        problem_build_s=problem_build_s,
        solver_init_s=solver_init_s,
        cold_build_s=cold_build_s,
        cold_sim_s=cold_sim_s,
        warm_sim_s=warm_sim_s,
        speedup=speedup,
        y_max_abs_diff=compute_max_abs_diff(cold_y, warm_y),
        dy_max_abs_diff=compute_max_abs_diff(cold_dy, warm_dy),
        cold_trace_summary=cold_trace_summary,
        warm_trace_summary=warm_trace_summary,
        build_stats=get_solver_build_stats(solver),
        problem_build_report=normalize_problem_build_report(local_problem),
        initialization_report=normalize_initialization_report(local_problem),
    )


def get_fastest_total_result(results: List[SolverBenchmarkResult]) -> SolverBenchmarkResult:
    """
    Return the result with the shortest total time.

    :param results: Benchmark results.
    :return: Fastest total-time result.
    """
    best_result: SolverBenchmarkResult = results[0]
    result_index: int = 1

    while result_index < len(results):
        candidate_result: SolverBenchmarkResult = results[result_index]

        if candidate_result.get_solver_total_s() < best_result.get_solver_total_s():
            best_result = candidate_result
        else:
            best_result = best_result

        result_index += 1

    return best_result


def get_fastest_sim_result(results: List[SolverBenchmarkResult]) -> SolverBenchmarkResult:
    """
    Return the result with the shortest simulation time.

    :param results: Benchmark results.
    :return: Fastest simulation-time result.
    """
    best_result: SolverBenchmarkResult = results[0]
    result_index: int = 1

    while result_index < len(results):
        candidate_result: SolverBenchmarkResult = results[result_index]

        if candidate_result.get_simulate_s() < best_result.get_simulate_s():
            best_result = candidate_result
        else:
            best_result = best_result

        result_index += 1

    return best_result


def print_benchmark_table(results: List[SolverBenchmarkResult]) -> None:
    """
    Print the clean backend validation table.

    :param results: Benchmark results.
    :return: None.
    """
    print("\n" + "-" * 200)
    print(
        f"{'Solver':<12}{'Problem[s]':>12}{'Init[s]':>12}{'Build[s]':>12}{'Sim[s]':>12}{'Total[s]':>12}"
        f"{'Loop[s]':>12}{'y MaxDiff':>16}{'dy MaxDiff':>16}{'FinalRes':>14}{'MaxRes':>14}{'Newtons':>12}{'LastStep':>12}"
    )
    print("-" * 200)

    result_index: int = 0

    while result_index < len(results):
        item: SolverBenchmarkResult = results[result_index]
        trace_summary: SolverTraceSummary = item.get_trace_summary()
        print(
            f"{item.get_solver_key():<12}{item.get_problem_build_s():>12.6f}{item.get_solver_init_s():>12.6f}"
            f"{item.get_solver_build_s():>12.6f}{item.get_simulate_s():>12.6f}{item.get_solver_total_s():>12.6f}"
            f"{item.get_loop_s():>12.6f}{item.get_y_max_abs_diff():>16.3e}{item.get_dy_max_abs_diff():>16.3e}"
            f"{trace_summary.get_final_residual_inf():>14.3e}{trace_summary.get_maximum_residual_inf():>14.3e}"
            f"{trace_summary.get_total_newton_iterations():>12d}{trace_summary.get_last_step_newton_iterations():>12d}"
        )
        result_index += 1


def print_compiled_backend_build_stats(results: List[SolverBenchmarkResult]) -> None:
    """
    Print the structural compiled backend statistics when present.

    :param results: Benchmark results.
    :return: None.
    """
    result_index: int = 0

    while result_index < len(results):
        item: SolverBenchmarkResult = results[result_index]

        if item.get_solver_key() == "COMPILED":
            build_stats: Dict[str, float] = item.get_build_stats()

            if len(build_stats) > 0:
                print("\nStructuralCompiled backend build stats")

                for key, value in build_stats.items():
                    print(f"  {key}: {value:.6f}s")
            else:
                build_stats = build_stats

            return
        else:
            result_index = result_index

        result_index += 1


def export_benchmark_results(results: List[SolverBenchmarkResult], file_stem: str) -> None:
    """
    Export benchmark results to structured CSV and JSON files.

    :param results: Benchmark results.
    :type results: List[SolverBenchmarkResult]
    :param file_stem: Output file stem without extension.
    :type file_stem: str
    :return: None.
    :rtype: None
    """
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    result_index: int = 0
    output_dir: Path = Path(__file__).resolve().parent / "benchmark_results"

    # The benchmark exports live next to the EMT demos so the research corpus
    # stays grouped inside trunk/dynamics_emt.
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_lines.append(
        "solver,problem_build_s,solver_init_s,solver_build_s,simulate_s,solver_total_s,loop_s,y_max_abs_diff,dy_max_abs_diff,final_residual_inf,maximum_residual_inf,total_newton_iterations,last_step_newton_iterations,steps,y_shape,dy_shape"
    )

    while result_index < len(results):
        item: SolverBenchmarkResult = results[result_index]
        trace_summary: SolverTraceSummary = item.get_trace_summary()
        y_shape: Tuple[int, ...] = item.get_y_shape()
        dy_shape: Tuple[int, ...] = item.get_dy_shape()

        csv_lines.append(
            f"{item.get_solver_key()},{item.get_problem_build_s():.9f},{item.get_solver_init_s():.9f},"
            f"{item.get_solver_build_s():.9f},{item.get_simulate_s():.9f},{item.get_solver_total_s():.9f},"
            f"{item.get_loop_s():.9f},{item.get_y_max_abs_diff():.9e},{item.get_dy_max_abs_diff():.9e},"
            f"{trace_summary.get_final_residual_inf():.9e},{trace_summary.get_maximum_residual_inf():.9e},"
            f"{trace_summary.get_total_newton_iterations()},{trace_summary.get_last_step_newton_iterations()},"
            f"{item.get_steps()},{y_shape[0]}x{y_shape[1]},{dy_shape[0]}x{dy_shape[1]}"
        )

        json_rows.append(
            dict(
                solver=item.get_solver_key(),
                problem_build_s=item.get_problem_build_s(),
                solver_init_s=item.get_solver_init_s(),
                solver_build_s=item.get_solver_build_s(),
                simulate_s=item.get_simulate_s(),
                solver_total_s=item.get_solver_total_s(),
                loop_s=item.get_loop_s(),
                y_max_abs_diff=item.get_y_max_abs_diff(),
                dy_max_abs_diff=item.get_dy_max_abs_diff(),
                final_residual_inf=trace_summary.get_final_residual_inf(),
                maximum_residual_inf=trace_summary.get_maximum_residual_inf(),
                total_newton_iterations=trace_summary.get_total_newton_iterations(),
                last_step_newton_iterations=trace_summary.get_last_step_newton_iterations(),
                build_stats=item.get_build_stats(),
                problem_build_report=item.get_problem_build_report(),
                initialization_report=item.get_initialization_report(),
                steps=item.get_steps(),
                y_shape=list(y_shape),
                dy_shape=list(dy_shape),
            )
        )
        result_index += 1

    with open(output_dir / f"{file_stem}.csv", "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(output_dir / f"{file_stem}.json", "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)


def export_cold_warm_results(results: Dict[str, float], file_stem: str) -> None:
    """
    Export one cold/warm benchmark summary to JSON.

    :param results: Cold/warm benchmark summary.
    :type results: Dict[str, float]
    :param file_stem: Output file stem without extension.
    :type file_stem: str
    :return: None.
    :rtype: None
    """
    output_dir: Path = Path(__file__).resolve().parent / "benchmark_results"

    # The cold/warm summary belongs to the same benchmark corpus directory.
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / f"{file_stem}.json", "w", encoding="utf-8") as json_file:
        json.dump(results, json_file, indent=2)


def export_all_solvers_cold_warm_results(results: List[SolverColdWarmBenchmarkResult], file_stem: str) -> None:
    """
    Export the four-solver cold/warm benchmark summary to CSV and JSON.

    :param results: Cold/warm benchmark results.
    :type results: List[SolverColdWarmBenchmarkResult]
    :param file_stem: Output file stem without extension.
    :type file_stem: str
    :return: None.
    :rtype: None
    """
    output_dir: Path = Path(__file__).resolve().parent / "benchmark_results"
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    result_index: int = 0

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_lines.append(
        "solver,problem_build_s,solver_init_s,cold_build_s,cold_sim_s,warm_sim_s,speedup,y_max_abs_diff,dy_max_abs_diff,cold_final_residual_inf,warm_final_residual_inf,cold_newton_iterations,warm_newton_iterations"
    )

    while result_index < len(results):
        item: SolverColdWarmBenchmarkResult = results[result_index]
        cold_summary: SolverTraceSummary = item.get_cold_trace_summary()
        warm_summary: SolverTraceSummary = item.get_warm_trace_summary()

        csv_lines.append(
            f"{item.get_solver_key()},{item.get_problem_build_s():.9f},{item.get_solver_init_s():.9f},"
            f"{item.get_cold_build_s():.9f},{item.get_cold_sim_s():.9f},{item.get_warm_sim_s():.9f},"
            f"{item.get_speedup():.9f},{item.get_y_max_abs_diff():.9e},{item.get_dy_max_abs_diff():.9e},"
            f"{cold_summary.get_final_residual_inf():.9e},{warm_summary.get_final_residual_inf():.9e},"
            f"{cold_summary.get_total_newton_iterations()},{warm_summary.get_total_newton_iterations()}"
        )

        json_rows.append(
            dict(
                solver=item.get_solver_key(),
                problem_build_s=item.get_problem_build_s(),
                solver_init_s=item.get_solver_init_s(),
                cold_build_s=item.get_cold_build_s(),
                cold_sim_s=item.get_cold_sim_s(),
                warm_sim_s=item.get_warm_sim_s(),
                speedup=item.get_speedup(),
                y_max_abs_diff=item.get_y_max_abs_diff(),
                dy_max_abs_diff=item.get_dy_max_abs_diff(),
                cold_final_residual_inf=cold_summary.get_final_residual_inf(),
                warm_final_residual_inf=warm_summary.get_final_residual_inf(),
                cold_maximum_residual_inf=cold_summary.get_maximum_residual_inf(),
                warm_maximum_residual_inf=warm_summary.get_maximum_residual_inf(),
                cold_total_newton_iterations=cold_summary.get_total_newton_iterations(),
                warm_total_newton_iterations=warm_summary.get_total_newton_iterations(),
                cold_last_step_newton_iterations=cold_summary.get_last_step_newton_iterations(),
                warm_last_step_newton_iterations=warm_summary.get_last_step_newton_iterations(),
                build_stats=item.get_build_stats(),
                problem_build_report=item.get_problem_build_report(),
                initialization_report=item.get_initialization_report(),
            )
        )
        result_index += 1

    with open(output_dir / f"{file_stem}.csv", "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(output_dir / f"{file_stem}.json", "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)


def build_solver_backend(solver_key: str, solver, local_problem: EmtProblemDae) -> None:
    use_dense_solver = local_problem.get_all_vars_number() <= DENSE_THRESHOLD
    use_sparse = not use_dense_solver

    if solver_key == "SYMBOLIC":
        solver.build_jit_kernel(options.integration_method)
        solver._build_jit_symbolic_hybrid(options.integration_method, use_sparse=use_sparse)

        if options.integration_method == DynamicIntegrationMethod.DaeTrapezoidal:
            solver.build_jit_kernel(DynamicIntegrationMethod.DaeBackEuler)
            solver._build_jit_symbolic_hybrid(DynamicIntegrationMethod.DaeBackEuler, use_sparse=use_sparse)
        return

    if solver_key == "AD":
        solver.build_jit_ad()
        return

    if solver_key == "VECTORIZED":
        solver.auto_detect_vectorization(options.integration_method)
        return

    if solver_key == "COMPILED":
        solver._build_vectorized_backend(options.integration_method)
        return

    raise ValueError(f"Solver '{solver_key}' no reconocido. Usa SYMBOLIC, AD, VECTORIZED o COMPILED.")


def benchmark_all_solvers() -> List[SolverBenchmarkResult]:
    print("\n" + "=" * 110)
    print("EMT SOLVER BENCHMARK (REAL DEMO)")
    print("=" * 110)
    print(f"time_step={options.time_step}, simulation_time={options.simulation_time}, dense_threshold={DENSE_THRESHOLD}")
    print(f"newton_trace={True}, solver_verbose={SOLVER_VERBOSE}")

    results: List[SolverBenchmarkResult] = list()
    reference_y: Optional[np.ndarray] = None
    reference_dy: Optional[np.ndarray] = None

    print(f"reference_solver={BENCHMARK_SOLVER_KEYS[0]}")

    for solver_key in BENCHMARK_SOLVER_KEYS:
        print(f"\n--- Running {solver_key} ---")

        result: SolverBenchmarkResult
        y_arr: np.ndarray
        dy_arr: np.ndarray
        result, y_arr, dy_arr = run_single_solver_benchmark(
            solver_key=solver_key,
            reference_y=reference_y,
            reference_dy=reference_dy,
        )

        if reference_y is None:
            reference_y = y_arr.copy()
            reference_dy = dy_arr.copy()
        else:
            reference_y = reference_y

        results.append(result)

    print_benchmark_table(results)

    fastest_total: SolverBenchmarkResult = get_fastest_total_result(results)
    fastest_sim: SolverBenchmarkResult = get_fastest_sim_result(results)

    print("\nFastest by solver total:", fastest_total.get_solver_key(), f"({fastest_total.get_solver_total_s():.6f}s)")
    print("Fastest by simulate only:", fastest_sim.get_solver_key(), f"({fastest_sim.get_simulate_s():.6f}s)")
    print_compiled_backend_build_stats(results)

    export_benchmark_results(results, "thevequiv_piline_zipload")
    return results


def benchmark_structural_compiled_cold_and_warm() -> None:
    """
    Benchmark ``StructuralCompiled`` in cold-build and warm-reuse modes.

    :return: None.
    """
    print("\n" + "=" * 110)
    print("STRUCTURAL COMPILED COLD/WARM BENCHMARK")
    print("=" * 110)

    local_problem: EmtProblemDae = create_problem(enable_trace=False)

    solver_init_t0: float = perf_counter()
    solver = create_solver("COMPILED", local_problem)
    solver_init_s: float = perf_counter() - solver_init_t0

    build_t0: float = perf_counter()
    build_solver_backend("COMPILED", solver, local_problem)
    cold_build_s: float = perf_counter() - build_t0

    boundary_updater = cast(Any, local_problem)

    cold_sim_t0: float = perf_counter()
    cold_t: np.ndarray
    cold_y: np.ndarray
    cold_dy: np.ndarray
    cold_t, cold_y, cold_dy = solver.simulate(boundary_updater=boundary_updater)
    cold_sim_s: float = perf_counter() - cold_sim_t0
    cold_residual_inf: float = evaluate_final_residual_inf("COMPILED", solver, local_problem, cold_t, cold_y, cold_dy)
    cold_runtime_stats: Dict[str, float] = get_solver_runtime_stats(solver)

    warm_sim_t0: float = perf_counter()
    warm_t: np.ndarray
    warm_y: np.ndarray
    warm_dy: np.ndarray
    warm_t, warm_y, warm_dy = solver.simulate(boundary_updater=boundary_updater)
    warm_sim_s: float = perf_counter() - warm_sim_t0
    warm_residual_inf: float = evaluate_final_residual_inf("COMPILED", solver, local_problem, warm_t, warm_y, warm_dy)
    warm_runtime_stats: Dict[str, float] = get_solver_runtime_stats(solver)

    print(f"solver_init_s = {solver_init_s:.6f}s")
    print(f"cold_build_s  = {cold_build_s:.6f}s")
    print(f"cold_sim_s    = {cold_sim_s:.6f}s")
    print(f"warm_sim_s    = {warm_sim_s:.6f}s")
    print(f"speedup       = {cold_sim_s / warm_sim_s:.3f}x" if warm_sim_s > 0.0 else "speedup       = inf")
    print(f"y_max_abs_diff  = {compute_max_abs_diff(cold_y, warm_y):.3e}")
    print(f"dy_max_abs_diff = {compute_max_abs_diff(cold_dy, warm_dy):.3e}")
    print(f"cold_final_res  = {cold_residual_inf:.3e}")
    print(f"warm_final_res  = {warm_residual_inf:.3e}")

    summary: Dict[str, float] = dict(
        solver_init_s=solver_init_s,
        cold_build_s=cold_build_s,
        cold_sim_s=cold_sim_s,
        warm_sim_s=warm_sim_s,
        speedup=(cold_sim_s / warm_sim_s) if warm_sim_s > 0.0 else np.inf,
        y_max_abs_diff=compute_max_abs_diff(cold_y, warm_y),
        dy_max_abs_diff=compute_max_abs_diff(cold_dy, warm_dy),
        cold_final_residual_inf=cold_residual_inf,
        warm_final_residual_inf=warm_residual_inf,
    )

    if len(cold_runtime_stats) > 0:
        print("Cold runtime stats")
        for key, value in cold_runtime_stats.items():
            print(f"  {key}: {value:.0f}" if abs(value - round(value)) < 1e-12 else f"  {key}: {value:.6f}")
    else:
        cold_runtime_stats = cold_runtime_stats

    if len(warm_runtime_stats) > 0:
        print("Warm runtime stats")
        for key, value in warm_runtime_stats.items():
            print(f"  {key}: {value:.0f}" if abs(value - round(value)) < 1e-12 else f"  {key}: {value:.6f}")
    else:
        warm_runtime_stats = warm_runtime_stats

    export_cold_warm_results(summary, "thevequiv_piline_zipload_compiled_cold_warm")
    raise SystemExit(0)


def benchmark_all_solvers_cold_and_warm() -> List[SolverColdWarmBenchmarkResult]:
    """
    Run cold/warm comparisons for the four EMT backends on the ZIP-load case.

    :return: Cold/warm benchmark results in solver execution order.
    :rtype: List[SolverColdWarmBenchmarkResult]
    """
    print("\n" + "=" * 120)
    print("EMT SOLVER COLD/WARM BENCHMARK (ZIP LOAD CASE)")
    print("=" * 120)
    print(f"time_step={options.time_step}, simulation_time={options.simulation_time}, dense_threshold={DENSE_THRESHOLD}")
    print(f"newton_trace={True}, solver_verbose={SOLVER_VERBOSE}")

    results: List[SolverColdWarmBenchmarkResult] = list()
    solver_index: int = 0

    while solver_index < len(ALL_SOLVER_KEYS):
        solver_key: str = ALL_SOLVER_KEYS[solver_index]
        print(f"\n--- Cold/Warm {solver_key} ---")
        result: SolverColdWarmBenchmarkResult = run_single_solver_cold_warm_benchmark(solver_key)
        results.append(result)
        solver_index += 1

    print("\n" + "-" * 190)
    print(
        f"{'Solver':<12}{'Problem[s]':>12}{'Init[s]':>12}{'Build[s]':>12}{'ColdSim[s]':>14}{'WarmSim[s]':>14}"
        f"{'Speedup':>12}{'y MaxDiff':>16}{'dy MaxDiff':>16}{'ColdRes':>14}{'WarmRes':>14}{'ColdNewt':>12}{'WarmNewt':>12}"
    )
    print("-" * 190)

    solver_index = 0
    while solver_index < len(results):
        result = results[solver_index]
        cold_summary: SolverTraceSummary = result.get_cold_trace_summary()
        warm_summary: SolverTraceSummary = result.get_warm_trace_summary()
        print(
            f"{result.get_solver_key():<12}"
            f"{result.get_problem_build_s():>12.6f}"
            f"{result.get_solver_init_s():>12.6f}"
            f"{result.get_cold_build_s():>12.6f}"
            f"{result.get_cold_sim_s():>14.6f}"
            f"{result.get_warm_sim_s():>14.6f}"
            f"{result.get_speedup():>12.3f}"
            f"{result.get_y_max_abs_diff():>16.3e}"
            f"{result.get_dy_max_abs_diff():>16.3e}"
            f"{cold_summary.get_final_residual_inf():>14.3e}"
            f"{warm_summary.get_final_residual_inf():>14.3e}"
            f"{cold_summary.get_total_newton_iterations():>12d}"
            f"{warm_summary.get_total_newton_iterations():>12d}"
        )
        solver_index += 1

    print("-" * 190)

    export_all_solvers_cold_warm_results(results, "thevequiv_piline_zipload_all_solvers_cold_warm")
    return results


def main() -> None:
    """
    Execute the interactive demo entry point.

    :return: None.
    :rtype: None
    """
    if RUN_ALL_SOLVERS:
        benchmark_all_solvers()
        return
    else:
        pass

    if BENCHMARK_COMPILED_COLD_WARM:
        benchmark_structural_compiled_cold_and_warm()
        return
    else:
        pass

    if BENCHMARK_ALL_SOLVERS_COLD_WARM:
        benchmark_all_solvers_cold_and_warm()
        return
    else:
        pass

    problem = create_problem()

    if SHOW_INIT_GUESS_TABLE:
        df = problem.get_init_guess_table()
        print(f"init_guess_table\n{df}")
    else:
        pass

    print(f"\n======================================")
    print(f"Initializing Solver: {CHOSEN_SOLVER}")
    print(f"======================================\n")

    solver_init_t0 = perf_counter()
    solver = create_solver(CHOSEN_SOLVER, problem)
    solver_init_s = perf_counter() - solver_init_t0

    build_t0 = perf_counter()
    build_solver_backend(CHOSEN_SOLVER, solver, problem)
    solver_build_s = perf_counter() - build_t0

    # ==============================================================================
    # RUN SIMULATION
    # ==============================================================================
    boundary_updater = cast(Any, problem)
    profiler.enable()
    sim_t0 = perf_counter()
    t_arr, y_arr, _dy = solver.simulate(boundary_updater=boundary_updater)
    solver_sim_s = perf_counter() - sim_t0

    print("Single-solver benchmark")
    print(f"  init  = {solver_init_s:.6f}s")
    print(f"  build = {solver_build_s:.6f}s")
    print(f"  sim   = {solver_sim_s:.6f}s")
    print(f"  total = {solver_init_s + solver_build_s + solver_sim_s:.6f}s")

    if isinstance(solver, StructuralCompiledSolver):
        print("StructuralCompiled backend build stats")
        for key, value in solver.get_backend_build_stats().items():
            print(f"  {key}: {value:.6f}s")
    else:
        pass

    print_solver_runtime_stats(solver, "StructuralCompiled runtime stats")

    collector = problem.get_newton_trace_collector()
    if collector:
        print(f"Newton iters : {len(collector.records)}")
        df = collector.to_dataframe()
        df.to_csv("newton_diagnostics_demo.csv", index=False)
        print("Diagnostics written to newton_diagnostics_demo.csv")
    else:
        pass

    # ==============================================================================
    # PROFILING REPORT
    # ==============================================================================
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumtime')
    print("\n" + "=" * 50)
    print("--- PROFILER REPORT (Top 15 slowest functions) ---")
    print("=" * 50)
    stats.print_stats(15)
    print("=" * 50 + "\n")

    if ENABLE_PLOTS:
        plot_paths: List[Path] = export_demo_plots(problem, t_arr, y_arr, CHOSEN_SOLVER)
        print(f"Plots written to {plot_paths[0].parent}")
    else:
        print("Plotting disabled; stopping after solver/profiler report.")


if __name__ == "__main__":
    main()
