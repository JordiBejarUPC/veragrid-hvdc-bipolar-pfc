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
from typing import Any, Dict, List, Tuple, cast
import pandas as pd

import matplotlib.pyplot as plt
from VeraGrid.trunk.dynamics_emt.support.emt_plot_exports import (
    extract_three_phase_matrix,
    get_plot_results_directory,
    save_scalar_step_plot,
    save_two_panel_three_phase_plot,
)
from VeraGrid.trunk.dynamics_emt.support.emt_build_report_exports import (
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

from VeraGridEngine.Utils.Symbolic.block import Block

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph


from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_3ph_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Devices.Aggregation.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Aggregation import EmtEvent

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import (BranchImpedanceMode, DynamicIntegrationMethod, EmtInitializationMethod,
                                         EmtSolverTypes, ShuntConnectionType, SolverType)

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

profiler = cProfile.Profile()

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

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
gen_mdl = get_generator_thevenin_rl_emt_template(vf = grid.emt_var_factory).block

# line
line_mdl = get_pi_line_emt_template(grid = grid, line = line0).block
# line_mdl = get_pi_line_emt_template(vf= grid.emt_var_factory).block

# load
load_mdl = get_shunt_r_3ph_emt_template(vf = grid.emt_var_factory).block

######################################################################################################
# Add models to devices
######################################################################################################

set_emt_model(device=gen0, model=gen_mdl, var_factory= grid.emt_var_factory)

set_emt_model(device=line0, model=line_mdl, var_factory= grid.emt_var_factory)

set_emt_model(device=load, model=load_mdl, var_factory= grid.emt_var_factory)


######################################################################################################
# Create event
######################################################################################################

R_A = find_name_in_block('R_A_Shunt_R_3ph', load_mdl)
R_B = find_name_in_block('R_B_Shunt_R_3ph', load_mdl)
R_C = find_name_in_block('R_C_Shunt_R_3ph', load_mdl)
events_group = EmtEventsGroup(name="simulation1")
grid.add_emt_events_group(events_group)
event_R_A = EmtEvent(device=load, parameter=R_A, time=0.02, value=3.0, group=events_group)
grid.add_emt_event(event_R_A)
event_R_B = EmtEvent(device=load, parameter=R_B, time=0.02, value=3.0, group=events_group)
grid.add_emt_event(event_R_B)
event_R_C = EmtEvent(device=load, parameter=R_C, time=0.02, value=3.0, group=events_group)
grid.add_emt_event(event_R_C)

event_R_A = EmtEvent(device=load, parameter=R_A, time=0.04, value=6.0, group=events_group)
grid.add_emt_event(event_R_A)
event_R_B = EmtEvent(device=load, parameter=R_B, time=0.04, value=6.0, group=events_group)
grid.add_emt_event(event_R_B)
event_R_C = EmtEvent(device=load, parameter=R_C, time=0.04, value=6.0, group=events_group)
grid.add_emt_event(event_R_C)

rms_events_group_names = np.array(0)


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

# ==============================================================================
# SELECT YOUR SOLVER HERE ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED")
# ==============================================================================
CHOSEN_SOLVER = "VECTORIZED"
RUN_ALL_SOLVERS = False
BENCHMARK_ALL_SOLVERS_COLD_WARM = False
ENABLE_PLOTS = True
ENABLE_NEWTON_TRACE = False
DENSE_THRESHOLD = 0
SOLVER_VERBOSE = True
PLOT_CASE_NAME = "emt_event"

SOLVER_TYPE_MAP = {
    "SYMBOLIC": EmtSolverTypes.Symbolic,
    "AD": EmtSolverTypes.Automatic,
    "VECTORIZED": EmtSolverTypes.StructuralAD,
    "COMPILED": EmtSolverTypes.StructuralCompiled,
}

ALL_SOLVER_KEYS = ["SYMBOLIC", "AD", "VECTORIZED", "COMPILED"]

if CHOSEN_SOLVER not in SOLVER_TYPE_MAP:
    raise ValueError(f"Solver '{CHOSEN_SOLVER}' no reconocido. Usa SYMBOLIC, AD, VECTORIZED o COMPILED.")

options = EmtOptions(time_step = 5e-6,
                     simulation_time =  0.06, # s
                     tolerance = 1e-6,
                     solver_type = SOLVER_TYPE_MAP[CHOSEN_SOLVER],
                     initialization_method = EmtInitializationMethod.Auto,
                     integration_method = DynamicIntegrationMethod.DaeTrapezoidal,
                     verbose = 1)


def create_problem() -> EmtProblemDae:
    local_problem = EmtProblemDae(grid=grid,
                                  options=options,
                                  pf_results_3Ph=res,
                                  pf_results= None)

    if ENABLE_NEWTON_TRACE:
        local_problem.set_newton_trace_collector(NewtonTraceCollector())

    return local_problem


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


def run_single_solver_trajectory(solver_key: str, enable_trace: bool) -> Tuple[EmtProblemDae, Any, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build one solver, execute one simulation and return the raw trajectories.

    :param solver_key: Solver identifier.
    :type solver_key: str
    :param enable_trace: Whether to enable Newton trace collection.
    :type enable_trace: bool
    :return: Tuple ``(problem, solver, t, y, dy)``.
    :rtype: Tuple[EmtProblemDae, Any, np.ndarray, np.ndarray, np.ndarray]
    """
    local_problem: EmtProblemDae = create_problem()

    if enable_trace:
        local_problem.set_newton_trace_collector(NewtonTraceCollector())
    else:
        pass

    solver: Any = create_solver(solver_key, local_problem)
    build_solver_backend(solver_key, solver, local_problem)
    boundary_updater: Any = cast(Any, local_problem)
    t_arr: np.ndarray
    y_arr: np.ndarray
    dy_arr: np.ndarray
    t_arr, y_arr, dy_arr = solver.simulate(boundary_updater=boundary_updater)
    return local_problem, solver, t_arr, y_arr, dy_arr


def build_event_resistance_profile(time_values: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build the three-phase resistance profile used by the event demo.

    :param time_values: Time vector.
    :type time_values: np.ndarray
    :return: Three-phase resistance trajectories.
    :rtype: Tuple[np.ndarray, np.ndarray, np.ndarray]
    """
    r_a: np.ndarray = np.full(time_values.shape, 100.0, dtype=np.float64)
    r_b: np.ndarray = np.full(time_values.shape, 100.0, dtype=np.float64)
    r_c: np.ndarray = np.full(time_values.shape, 100.0, dtype=np.float64)
    first_event_mask: np.ndarray = time_values >= 0.02
    second_event_mask: np.ndarray = time_values >= 0.04

    r_a[first_event_mask] = 3.0
    r_b[first_event_mask] = 3.0
    r_c[first_event_mask] = 3.0
    r_a[second_event_mask] = 6.0
    r_b[second_event_mask] = 6.0
    r_c[second_event_mask] = 6.0
    return r_a, r_b, r_c


def export_demo_plots(
        problem: EmtProblemDae,
        time_values: np.ndarray,
        y_values: np.ndarray,
        solver_key: str,
        output_root_name: str = "plot_results",
) -> List[Path]:
    """
    Export diagnostic plots for the interactive event demo.

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
    load_current_triplet: Tuple[Any, Any, Any] = (
        find_name_in_block("i_A_Shunt_R_3ph", load_mdl),
        find_name_in_block("i_B_Shunt_R_3ph", load_mdl),
        find_name_in_block("i_C_Shunt_R_3ph", load_mdl),
    )
    load_currents: np.ndarray = -extract_three_phase_matrix(problem, y_values, load_current_triplet)
    generator_currents: np.ndarray = extract_three_phase_matrix(problem, y_values, gen_mdl.out_vars)
    resistance_triplet: Tuple[np.ndarray, np.ndarray, np.ndarray] = build_event_resistance_profile(time_values)

    voltage_path: Path = output_dir / "bus_voltages.png"
    current_path: Path = output_dir / "load_currents.png"
    resistance_path: Path = output_dir / "load_resistance_events.png"

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
        top_triplet=(load_currents[:, 0], load_currents[:, 1], load_currents[:, 2]),
        top_title="Load Currents",
        top_ylabel="Current [pu]",
        top_legend_prefix="Load",
        bottom_triplet=(generator_currents[:, 0], generator_currents[:, 1], generator_currents[:, 2]),
        bottom_title="Generator Currents",
        bottom_ylabel="Current [pu]",
        bottom_legend_prefix="Gen",
    )
    generated_paths.append(current_path)

    save_scalar_step_plot(
        file_path=resistance_path,
        time_values=time_values,
        values_triplet=resistance_triplet,
        title="Load Resistance Events",
        y_label="Resistance [pu]",
        legend_prefix="R",
    )
    generated_paths.append(resistance_path)

    return generated_paths


def get_solver_loop_time(solver: Any) -> float:
    """
    Return the integration-loop time when the solver exposes it.

    :param solver: Solver instance.
    :type solver: Any
    :return: Loop time in seconds or NaN.
    :rtype: float
    """
    if isinstance(solver, (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver)):
        return float(solver.get_last_sim_loop_time())
    else:
        return np.nan


def get_solver_build_stats(solver: Any) -> Dict[str, float]:
    """
    Return backend build statistics when available.

    :param solver: Solver instance.
    :type solver: Any
    :return: Backend build statistics.
    :rtype: Dict[str, float]
    """
    if isinstance(solver, (JitSymbolicSolver, JitAdSolver, StructuralVectorizedSolver, StructuralCompiledSolver)):
        raw_stats: Dict[str, float] = solver.get_backend_build_stats()
        out_stats: Dict[str, float] = dict()

        for key, value in raw_stats.items():
            out_stats[str(key)] = float(value)

        return out_stats
    else:
        return dict()


def export_benchmark_results(results: List[Dict[str, object]], file_stem: str) -> None:
    """
    Export benchmark results to structured CSV and JSON files.

    :param results: Benchmark result rows.
    :type results: List[Dict[str, object]]
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
        "solver,problem_build_s,solver_init_s,solver_build_s,simulate_s,solver_total_s,loop_s,max_abs_diff,steps,y_shape,dy_shape"
    )

    while result_index < len(results):
        row: Dict[str, object] = results[result_index]
        y_shape: Tuple[int, ...] = tuple(row["shape"])
        dy_shape: Tuple[int, ...] = tuple(row["dy_shape"])
        build_stats_any: object = row["build_stats"]
        build_stats: Dict[str, float] = dict()

        if isinstance(build_stats_any, dict):
            for key, value in build_stats_any.items():
                build_stats[str(key)] = float(value)
        else:
            build_stats = build_stats

        csv_lines.append(
            f"{row['solver']},{float(row['problem_build_s']):.9f},{float(row['solver_init_s']):.9f},"
            f"{float(row['solver_build_s']):.9f},{float(row['simulate_s']):.9f},{float(row['solver_total_s']):.9f},"
            f"{float(row['loop_s']):.9f},{float(row['max_abs_diff']):.9e},{int(row['steps'])},"
            f"{y_shape[0]}x{y_shape[1]},{dy_shape[0]}x{dy_shape[1]}"
        )

        json_rows.append(
            dict(
                solver=str(row["solver"]),
                problem_build_s=float(row["problem_build_s"]),
                solver_init_s=float(row["solver_init_s"]),
                solver_build_s=float(row["solver_build_s"]),
                simulate_s=float(row["simulate_s"]),
                solver_total_s=float(row["solver_total_s"]),
                loop_s=float(row["loop_s"]),
                max_abs_diff=float(row["max_abs_diff"]),
                build_stats=build_stats,
                problem_build_report=dict(row["problem_build_report"]),
                initialization_report=dict(row["initialization_report"]),
                steps=int(row["steps"]),
                y_shape=list(y_shape),
                dy_shape=list(dy_shape),
            )
        )
        result_index += 1

    with open(output_dir / f"{file_stem}.csv", "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(output_dir / f"{file_stem}.json", "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)


def export_all_solvers_cold_warm_results(results: List[Dict[str, object]], file_stem: str) -> None:
    """
    Export the four-solver cold/warm benchmark summary to CSV and JSON.

    :param results: Cold/warm benchmark rows.
    :type results: List[Dict[str, object]]
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
        "solver,problem_build_s,solver_init_s,cold_build_s,cold_sim_s,warm_sim_s,speedup,max_abs_diff,build_stat_count"
    )

    while result_index < len(results):
        row: Dict[str, object] = results[result_index]
        build_stats_any: object = row["build_stats"]
        build_stats: Dict[str, float] = dict()

        if isinstance(build_stats_any, dict):
            for key, value in build_stats_any.items():
                build_stats[str(key)] = float(value)
        else:
            build_stats = build_stats

        csv_lines.append(
            f"{row['solver']},{float(row['problem_build_s']):.9f},{float(row['solver_init_s']):.9f},"
            f"{float(row['cold_build_s']):.9f},{float(row['cold_sim_s']):.9f},{float(row['warm_sim_s']):.9f},"
            f"{float(row['speedup']):.9f},{float(row['max_abs_diff']):.9e},{len(build_stats)}"
        )
        json_rows.append(
            dict(
                solver=str(row["solver"]),
                problem_build_s=float(row["problem_build_s"]),
                solver_init_s=float(row["solver_init_s"]),
                cold_build_s=float(row["cold_build_s"]),
                cold_sim_s=float(row["cold_sim_s"]),
                warm_sim_s=float(row["warm_sim_s"]),
                speedup=float(row["speedup"]),
                max_abs_diff=float(row["max_abs_diff"]),
                build_stats=build_stats,
                problem_build_report=dict(row["problem_build_report"]),
                initialization_report=dict(row["initialization_report"]),
            )
        )
        result_index += 1

    with open(output_dir / f"{file_stem}.csv", "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(output_dir / f"{file_stem}.json", "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)


def run_single_solver_cold_warm_benchmark(solver_key: str) -> Dict[str, object]:
    """
    Run one backend twice to compare cold and warm execution.

    :param solver_key: Solver identifier.
    :type solver_key: str
    :return: Cold/warm benchmark row.
    :rtype: Dict[str, object]
    """
    t_problem_0: float = perf_counter()
    local_problem: EmtProblemDae = create_problem()
    problem_build_s: float = perf_counter() - t_problem_0

    t_solver_0: float = perf_counter()
    solver = create_solver(solver_key, local_problem)
    solver_init_s: float = perf_counter() - t_solver_0

    t_build_0: float = perf_counter()
    build_solver_backend(solver_key, solver, local_problem)
    cold_build_s: float = perf_counter() - t_build_0

    boundary_updater = cast(Any, local_problem)

    cold_sim_t0: float = perf_counter()
    _cold_t: np.ndarray
    cold_y: np.ndarray
    _cold_dy: np.ndarray
    _cold_t, cold_y, _cold_dy = solver.simulate(boundary_updater=boundary_updater)
    cold_sim_s: float = perf_counter() - cold_sim_t0

    warm_sim_t0: float = perf_counter()
    _warm_t: np.ndarray
    warm_y: np.ndarray
    _warm_dy: np.ndarray
    _warm_t, warm_y, _warm_dy = solver.simulate(boundary_updater=boundary_updater)
    warm_sim_s: float = perf_counter() - warm_sim_t0

    if warm_sim_s > 0.0:
        speedup: float = cold_sim_s / warm_sim_s
    else:
        speedup = np.inf

    return dict(
        solver=solver_key,
        problem_build_s=problem_build_s,
        solver_init_s=solver_init_s,
        cold_build_s=cold_build_s,
        cold_sim_s=cold_sim_s,
        warm_sim_s=warm_sim_s,
        speedup=speedup,
        max_abs_diff=float(np.max(np.abs(cold_y - warm_y))),
        build_stats=get_solver_build_stats(solver),
        problem_build_report=normalize_problem_build_report(local_problem),
        initialization_report=normalize_initialization_report(local_problem),
    )


def run_single_solver_benchmark(solver_key: str, reference_y: np.ndarray | None) -> Dict[str, object]:
    """
    Run one standard benchmark for a single EMT backend.

    :param solver_key: Solver identifier.
    :type solver_key: str
    :param reference_y: Reference state trajectory or ``None`` for the first solver.
    :type reference_y: np.ndarray | None
    :return: Benchmark row with the current trajectory included.
    :rtype: Dict[str, object]
    """
    t_problem_0: float = perf_counter()
    local_problem: EmtProblemDae = create_problem()
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

    if reference_y is None:
        max_abs_diff: float = 0.0
    else:
        max_abs_diff = float(np.max(np.abs(y_arr - reference_y)))

    return dict(
        solver=solver_key,
        problem_build_s=problem_build_s,
        solver_init_s=solver_init_s,
        solver_build_s=solver_build_s,
        simulate_s=simulate_s,
        solver_total_s=solver_init_s + solver_build_s + simulate_s,
        loop_s=get_solver_loop_time(solver),
        max_abs_diff=max_abs_diff,
        build_stats=get_solver_build_stats(solver),
        problem_build_report=normalize_problem_build_report(local_problem),
        initialization_report=normalize_initialization_report(local_problem),
        steps=len(t_arr) - 1,
        shape=y_arr.shape,
        dy_shape=dy_arr.shape,
        y=y_arr,
    )


def benchmark_all_solvers_cold_and_warm() -> List[Dict[str, object]]:
    """
    Run cold/warm comparisons for the four EMT backends on the event case.

    :return: Cold/warm benchmark rows.
    :rtype: List[Dict[str, object]]
    """
    print("\n" + "=" * 120)
    print("EMT SOLVER COLD/WARM BENCHMARK (EVENT CASE)")
    print("=" * 120)
    print(f"time_step={options.time_step}, simulation_time={options.simulation_time}, dense_threshold={DENSE_THRESHOLD}")
    print(f"newton_trace={ENABLE_NEWTON_TRACE}, solver_verbose={SOLVER_VERBOSE}")

    results: List[Dict[str, object]] = list()
    solver_index: int = 0

    while solver_index < len(ALL_SOLVER_KEYS):
        solver_key: str = ALL_SOLVER_KEYS[solver_index]
        print(f"\n--- Cold/Warm {solver_key} ---")
        results.append(run_single_solver_cold_warm_benchmark(solver_key))
        solver_index += 1

    export_all_solvers_cold_warm_results(results, "emt_event_all_solvers_cold_warm")
    return results


def benchmark_all_solvers() -> List[Dict[str, object]]:
    """
    Run the real EMT backend benchmark for all supported solver backends.

    :return: Benchmark result rows in solver execution order.
    :rtype: List[Dict[str, object]]
    """
    print("\n" + "=" * 110)
    print("EMT SOLVER BENCHMARK (REAL DEMO)")
    print("=" * 110)
    print(f"time_step={options.time_step}, simulation_time={options.simulation_time}, dense_threshold={DENSE_THRESHOLD}")
    print(f"newton_trace={ENABLE_NEWTON_TRACE}, solver_verbose={SOLVER_VERBOSE}")

    results: List[Dict[str, object]] = list()
    reference_y = None

    for solver_key in ALL_SOLVER_KEYS:
        print(f"\n--- Running {solver_key} ---")
        result: Dict[str, object] = run_single_solver_benchmark(solver_key, reference_y)

        if reference_y is None:
            reference_y = np.array(result["y"], dtype=np.float64, copy=True)
        else:
            reference_y = reference_y

        result.pop("y")
        results.append(result)

    print("\n" + "-" * 140)
    print(f"{'Solver':<12}{'Problem[s]':>12}{'Init[s]':>12}{'Build[s]':>12}{'Sim[s]':>12}{'Total[s]':>12}{'Loop[s]':>12}{'MaxDiff':>18}")
    print("-" * 140)

    for item in results:
        print(f"{item['solver']:<12}{item['problem_build_s']:>12.6f}{item['solver_init_s']:>12.6f}{item['solver_build_s']:>12.6f}{item['simulate_s']:>12.6f}{item['solver_total_s']:>12.6f}{item['loop_s']:>12.6f}{item['max_abs_diff']:>18.3e}")

    fastest_total = min(results, key=lambda x: x["solver_total_s"])
    fastest_sim = min(results, key=lambda x: x["simulate_s"])

    print("\nFastest by solver total:", fastest_total["solver"], f"({fastest_total['solver_total_s']:.6f}s)")
    print("Fastest by simulate only:", fastest_sim["solver"], f"({fastest_sim['simulate_s']:.6f}s)")

    for item in results:
        if item["solver"] == "COMPILED" and item["build_stats"]:
            print("\nStructuralCompiled backend build stats")
            for key, value in item["build_stats"].items():
                print(f"  {key}: {value:.6f}s")
            break

    export_benchmark_results(results, "emt_event_benchmark")
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

    if BENCHMARK_ALL_SOLVERS_COLD_WARM:
        benchmark_all_solvers_cold_and_warm()
        return
    else:
        pass

    problem = create_problem()

    df = problem.get_init_guess_table()
    print(f"init_guess_table\n{df}")

    print(f"\n======================================")
    print(f"Initializing Solver: {CHOSEN_SOLVER}")
    print(f"======================================\n")

    solver = create_solver(CHOSEN_SOLVER, problem)
    build_solver_backend(CHOSEN_SOLVER, solver, problem)

    # ==============================================================================
    # RUN SIMULATION
    # ==============================================================================
    boundary_updater = cast(Any, problem)
    profiler.enable()
    _t, _y, _dy = solver.simulate(boundary_updater=boundary_updater)

    if isinstance(solver, StructuralCompiledSolver):
        print("StructuralCompiled backend build stats")
        for key, value in solver.get_backend_build_stats().items():
            print(f"  {key}: {value:.6f}s")
    else:
        pass

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
        plot_paths: List[Path] = export_demo_plots(problem, _t, _y, CHOSEN_SOLVER)
        print(f"Plots written to {plot_paths[0].parent}")
    else:
        print("Plotting disabled; stopping after solver/profiler report.")


if __name__ == "__main__":
    main()
