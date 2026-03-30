# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import cProfile
import pstats
import numpy as np
from time import perf_counter
from typing import Any, cast

import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import matplotlib.pyplot as plt

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions

from VeraGridEngine.Utils.Symbolic.block import Block

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver


from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_3ph_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes, ShuntConnectionType, EmtInitializationMethod
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################

profiler = cProfile.Profile()
profiler.enable()

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res

grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

# Buses
vnom = 10 #kV
bus0 = gce.Bus(name="Bus0", Vnom=vnom, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=vnom)

grid.add_bus(bus0)
grid.add_bus(bus1)

# Lines
line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)


# physical configuration (Overhead line tower)
tower = gce.OverheadLineType(name="Tower", Vnom=vnom)
wire = gce.Wire(name="Panther 30/7 ACSR",
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
load = gce.Load(name="load", P= 3.0*P_ph, Q = 3.0*Q_ph, P1= P_ph, P2= P_ph, P3= P_ph, Q1= Q_ph, Q2= Q_ph, Q3= Q_ph)
load.conn = ShuntConnectionType.GroundedStar

# Generators
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=0.001, x1=1.7)
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
gen_mdl = get_generator_thevenin_rl_emt_template(vf= grid.emt_var_factory).block

# line
line_mdl = get_pi_line_emt_template(grid = grid, line = line0).block
# line_mdl = get_pi_line_emt_template(vf= grid.emt_var_factory).block

# load
load_mdl = get_shunt_r_3ph_emt_template(vf = grid.emt_var_factory).block

load_mdl.set_parameter_in_model(var_name="Vnom_Shunt_R_3ph", new_value=1.0)

######################################################################################################
# Add models to devices
######################################################################################################

set_emt_model(device=gen0, model=gen_mdl, var_factory= grid.emt_var_factory)

set_emt_model(device=line0, model=line_mdl, var_factory= grid.emt_var_factory)

set_emt_model(device=load, model=load_mdl, var_factory= grid.emt_var_factory)

#
# # connection with buses
# gen_mdl.connect([gen_mdl.in_vars[0]], [bus0.emt_model.out_vars[0]]) # v_A
# gen_mdl.connect([gen_mdl.in_vars[1]], [bus0.emt_model.out_vars[1]]) # v_B
# gen_mdl.connect([gen_mdl.in_vars[2]], [bus0.emt_model.out_vars[2]]) # v_C
#
#
# line_mdl.connect([line_mdl.in_vars[0]], [bus0.emt_model.out_vars[0]]) # line vf_A
# line_mdl.connect([line_mdl.in_vars[1]], [bus0.emt_model.out_vars[1]]) # line vf_B
# line_mdl.connect([line_mdl.in_vars[2]], [bus0.emt_model.out_vars[2]]) # line vf_C
#
# line_mdl.connect([line_mdl.in_vars[3]], [bus1.emt_model.out_vars[0]]) # line vt_A
# line_mdl.connect([line_mdl.in_vars[4]], [bus1.emt_model.out_vars[1]]) # line vt_B
# line_mdl.connect([line_mdl.in_vars[5]], [bus1.emt_model.out_vars[2]]) # line vt_C
#
# # u_gov = find_name_in_block("u_gov1", gov1_mdl)
#
# load_mdl.connect([load_mdl.in_vars[0]], [bus1.emt_model.out_vars[0]]) # v_A
# load_mdl.connect([load_mdl.in_vars[1]], [bus1.emt_model.out_vars[1]]) # v_B
# load_mdl.connect([load_mdl.in_vars[2]], [bus1.emt_model.out_vars[2]]) # v_C
#
# # external mapping
# # big_gen1 = Block(children=[gen_mdl])
# #
# # big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: gen_mdl.out_vars[0]})
# # big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: gen_mdl.out_vars[1]})
#
# # attach emt models to Veragrid objects
# line0.emt_model= line_mdl
# load.emt_model= load_mdl
# gen0.emt_model= gen_mdl
# # gen0.emt_model= big_gen1

# gce.save_file(grid=grid, filename="grid_save_event.veragrid")

pf_options = PowerFlowOptions(
    solver_type=gce.SolverType.NR,
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
    branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=False,
    generate_report=False,
)
# Balanced powerflow
power_flow = PowerFlowDriver(grid, pf_options)
power_flow.run()
res = power_flow.results
print("Balanced power flow results")
print("res.bus_names = ", res.bus_names)
print("res.branch_names = ", res.branch_names)
print("res.bus_types = ", res.bus_types)
print("res.voltage_A = ", res.voltage)
print("res.Sbus_A = ", res.Sbus)
print("res.Sf_A = ", res.Sf)
print("res.St_A = ", res.St)

print(f"Converged: {res.converged}")
print(res.get_bus_df())
print(res.get_branch_df())

# 3ph powerflow

power_flow = PowerFlowDriver3Ph(grid, pf_options)
power_flow.run()
res3h = power_flow.results
print("3Ph power flow results")
print("res3h.m (branch number)= ", res3h.m)
print("res3h.n (bus number)= ", res3h.n)
print("res3h.n_gen = ", res3h.n_gen)
print("res3h.n_load ", res3h.n_load)
print("res3h.bus_names = ", res3h.bus_names)
print("res3h.branch_names = ", res3h.branch_names)
print("res3h.load_names = ", res3h.load_names)
print("res3h.bus_types = ", res3h.bus_types)
print("res3h.voltage_A = ", res3h.voltage_A)
print("res3h.voltage_B = ", res3h.voltage_B)
print("res3h.voltage_C = ", res3h.voltage_C)
print("res3h.Sbus_A = ", res3h.Sbus_A)
print("res3h.Sbus_B = ", res3h.Sbus_B)
print("res3h.Sbus_C = ", res3h.Sbus_C)
print("res3h.Sf_A = ", res3h.Sf_A)
print("res3h.Sf_B = ", res3h.Sf_B)
print("res3h.Sf_C = ", res3h.Sf_C)
print("res3h.St_A = ", res3h.St_A)
print("res3h.St_B = ", res3h.St_B)
print("res3h.St_C = ", res3h.St_C)

print(f"Converged: {res3h.converged}")
print(res3h.get_bus_df())
print(res3h.get_branch_df())

# ==============================================================================
# SELECT YOUR SOLVER HERE ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED")
# ==============================================================================
CHOSEN_SOLVER = "SYMBOLIC"
RUN_ALL_SOLVERS = False
ENABLE_PLOTS = True
ENABLE_NEWTON_TRACE = False
DENSE_THRESHOLD = 0
SOLVER_VERBOSE = True

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
                     simulation_time =  0.01, # s
                     tolerance = 1e-6,
                     solver_type = SOLVER_TYPE_MAP[CHOSEN_SOLVER],
                     initialization_method = EmtInitializationMethod.Auto,
                     integration_method = DynamicIntegrationMethod.DaeTrapezoidal,
                     verbose = 1)


def create_problem() -> EmtProblemDae:
    # local_problem = EmtProblemDae(grid=grid,
    #                               options=options,
    #                               pf_results_3Ph=res3h,
    #                               pf_results= res)
    local_problem = EmtProblemDae(grid=grid,
                                  options=options,
                                  pf_results_3Ph=None,
                                  pf_results=res)

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


def benchmark_all_solvers() -> None:
    print("\n" + "=" * 110)
    print("EMT SOLVER BENCHMARK (REAL DEMO)")
    print("=" * 110)
    print(f"time_step={options.time_step}, simulation_time={options.simulation_time}, dense_threshold={DENSE_THRESHOLD}")
    print(f"newton_trace={ENABLE_NEWTON_TRACE}, solver_verbose={SOLVER_VERBOSE}")

    results = list()
    reference_y = None

    for solver_key in ALL_SOLVER_KEYS:
        print(f"\n--- Running {solver_key} ---")

        t_problem_0 = perf_counter()
        local_problem = create_problem()
        problem_build_s = perf_counter() - t_problem_0

        t_solver_0 = perf_counter()
        solver = create_solver(solver_key, local_problem)
        solver_init_s = perf_counter() - t_solver_0

        t_build_0 = perf_counter()
        build_solver_backend(solver_key, solver, local_problem)
        solver_build_s = perf_counter() - t_build_0

        boundary_updater = cast(Any, local_problem)
        t_sim_0 = perf_counter()
        t_arr, y_arr, dy_arr = solver.simulate(boundary_updater=boundary_updater)
        simulate_s = perf_counter() - t_sim_0

        if reference_y is None:
            max_abs_diff = 0.0
            reference_y = y_arr.copy()
        else:
            max_abs_diff = float(np.max(np.abs(y_arr - reference_y)))

        loop_time = getattr(solver, "_last_sim_loop_time", np.nan)
        build_stats_fn = getattr(solver, "get_backend_build_stats", None)

        results.append({
            "solver": solver_key,
            "problem_build_s": problem_build_s,
            "solver_init_s": solver_init_s,
            "solver_build_s": solver_build_s,
            "simulate_s": simulate_s,
            "solver_total_s": solver_init_s + solver_build_s + simulate_s,
            "loop_s": float(loop_time) if loop_time == loop_time else np.nan,
            "max_abs_diff": max_abs_diff,
            "build_stats": build_stats_fn() if callable(build_stats_fn) else dict(),
            "steps": len(t_arr) - 1,
            "shape": y_arr.shape,
            "dy_shape": dy_arr.shape,
        })

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

    raise SystemExit(0)


if RUN_ALL_SOLVERS:
    benchmark_all_solvers()

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
t, y, dy = solver.simulate(boundary_updater=boundary_updater)

if hasattr(solver, "get_backend_build_stats"):
    print("StructuralCompiled backend build stats")
    for key, value in solver.get_backend_build_stats().items():
        print(f"  {key}: {value:.6f}s")


collector = problem.get_newton_trace_collector()
if collector:
    print(f"Newton iters : {len(collector.records)}")
    df = collector.to_dataframe()
    df.to_csv("newton_diagnostics_demo.csv", index=False)
    print("Diagnostics written to newton_diagnostics_demo.csv")

# ==============================================================================
# PROFILING REPORT
# ==============================================================================
profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumtime')
print("\n" + "="*50)
print("--- PROFILER REPORT (Top 15 slowest functions) ---")
print("="*50)
stats.print_stats(15)
print("="*50 + "\n")

if not ENABLE_PLOTS:
    print("Plotting disabled; stopping after solver/profiler report.")
    raise SystemExit(0)

# ==============================================================================
# PLOTTING
# ==============================================================================
xlim = options.simulation_time

t_end = options.simulation_time
h = options.time_step
steps: int = int(t_end / h)
tme: np.ndarray = np.linspace(0, t_end, steps)

#
v_A_0 = find_name_in_block("v_A_Bus0_emt_template", bus0.emt_model)
v_B_0 = find_name_in_block("v_B_Bus0_emt_template", bus0.emt_model)
v_C_0 = find_name_in_block("v_C_Bus0_emt_template", bus0.emt_model)
v_A_0_plt = y[:, problem.get_var_idx(v_A_0)]
v_B_0_plt = y[:, problem.get_var_idx(v_B_0)]
v_C_0_plt = y[:, problem.get_var_idx(v_C_0)]

v_A_1 = find_name_in_block("v_A_Bus1_emt_template", bus1.emt_model)
v_B_1 = find_name_in_block("v_B_Bus1_emt_template", bus1.emt_model)
v_C_1 = find_name_in_block("v_C_Bus1_emt_template", bus1.emt_model)
v_A_1_plt = y[:, problem.get_var_idx(v_A_1)]
v_B_1_plt = y[:, problem.get_var_idx(v_B_1)]
v_C_1_plt = y[:, problem.get_var_idx(v_C_1)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 1, 1)
plt.plot(tme, v_A_0_plt[:len(tme)], label='Voltage phase A bus 0', color='blue')
plt.plot(tme, v_B_0_plt[:len(tme)], label='Voltage phase B bus 0', color='red')
plt.plot(tme, v_C_0_plt[:len(tme)], label='Voltage phase C bus 0', color='green')
plt.title("Voltage bus 0")
plt.xlabel("Time")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 1, 2)
plt.plot(tme, v_A_1_plt[:len(tme)], label='Voltage phase A bus 1', color='blue')
plt.plot(tme, v_B_1_plt[:len(tme)], label='Voltage phase B bus 1', color='red')
plt.plot(tme, v_C_1_plt[:len(tme)], label='Voltage phase C bus 1', color='green')
plt.title("Voltage bus 1")
plt.xlabel("Time")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()

theta = find_name_in_block("theta_emt_thevenin_eq_generator_template", gen_mdl)
theta_plt = y[:, problem.get_var_idx(theta)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 1, 1)
plt.plot(tme, theta_plt[:len(tme)], label='Theta generator [rad]', color='blue')
plt.title("Theta generator")
plt.xlabel("Time")
plt.ylabel("Theta generator")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()

i_A_gen = find_name_in_block("i_A_emt_thevenin_eq_generator_template", gen_mdl)
i_B_gen = find_name_in_block("i_B_emt_thevenin_eq_generator_template", gen_mdl)
i_C_gen = find_name_in_block("i_C_emt_thevenin_eq_generator_template", gen_mdl)
i_A_gen_plt = y[:, problem.get_var_idx(i_A_gen)]
i_B_gen_plt = y[:, problem.get_var_idx(i_B_gen)]
i_C_gen_plt = y[:, problem.get_var_idx(i_C_gen)]

i_A_load = find_name_in_block("i_A_Shunt_R_3ph", load_mdl)
i_B_load = find_name_in_block("i_B_Shunt_R_3ph", load_mdl)
i_C_load = find_name_in_block("i_C_Shunt_R_3ph", load_mdl)
i_A_load_plt = y[:, problem.get_var_idx(i_A_load)]
i_B_load_plt = y[:, problem.get_var_idx(i_B_load)]
i_C_load_plt = y[:, problem.get_var_idx(i_C_load)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 2, 1)
plt.plot(tme, i_A_gen_plt[:len(tme)], label='Current phase A from generator', color='blue')
plt.plot(tme, i_B_gen_plt[:len(tme)], label='Current phase B from generator', color='red')
plt.plot(tme, i_C_gen_plt[:len(tme)], label='Current phase C from generator', color='green')
plt.title("Current generator")
plt.xlabel("Time")
plt.ylabel("Current generator")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 2)
# SIGNS IN LOAD ARE FLIPPED. FOR SIGN CONVENTION CURRENTS LEAVE INJECTIONS SO IN THE CASE OF THE LOAD
# THAT MEANS THE CURRENTS ARE NEGATIVE
plt.plot(tme, -i_A_load_plt[:len(tme)], label='Current phase A from load', color='blue')
plt.plot(tme, -i_B_load_plt[:len(tme)], label='Current phase B from load', color='red')
plt.plot(tme, -i_C_load_plt[:len(tme)], label='Current phase C from load', color='green')
plt.title("Current load")
plt.xlabel("Time")
plt.ylabel("Current load")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()


i_f_A_line = find_name_in_block("if_Pi_0", line0.emt_model)
i_f_B_line = find_name_in_block("if_Pi_1", line0.emt_model)
i_f_C_line = find_name_in_block("if_Pi_2", line0.emt_model)
i_f_A_line_plt = y[:, problem.get_var_idx(i_f_A_line)]
i_f_B_line_plt = y[:, problem.get_var_idx(i_f_B_line)]
i_f_C_line_plt = y[:, problem.get_var_idx(i_f_C_line)]

i_t_A_line = find_name_in_block("it_Pi_0", line0.emt_model)
i_t_B_line = find_name_in_block("it_Pi_1", line0.emt_model)
i_t_C_line = find_name_in_block("it_Pi_2", line0.emt_model)
i_t_A_line_plt = y[:, problem.get_var_idx(i_t_A_line)]
i_t_B_line_plt = y[:, problem.get_var_idx(i_t_B_line)]
i_t_C_line_plt = y[:, problem.get_var_idx(i_t_C_line)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 2, 1)
plt.plot(tme, i_A_gen_plt[:len(tme)], label='Current phase A from generator', color='blue')
plt.plot(tme, i_B_gen_plt[:len(tme)], label='Current phase B from generator', color='red')
plt.plot(tme, i_C_gen_plt[:len(tme)], label='Current phase C from generator', color='green')
plt.title("Current generator")
plt.xlabel("Time")
plt.ylabel("Current generator")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 2)
# SIGNS IN LOAD ARE FLIPPED. FOR SIGN CONVENTION CURRENTS LEAVE INJECTIONS SO IN THE CASE OF THE LOAD
# THAT MEANS THE CURRENTS ARE NEGATIVE
plt.plot(tme, -i_A_load_plt[:len(tme)], label='Current phase A from load', color='blue')
plt.plot(tme, -i_B_load_plt[:len(tme)], label='Current phase B from load', color='red')
plt.plot(tme, -i_C_load_plt[:len(tme)], label='Current phase C from load', color='green')
plt.title("Current load")
plt.xlabel("Time")
plt.ylabel("Current load")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 3)
plt.plot(tme, i_f_A_line_plt[:len(tme)], label='Current FROM phase A from line', color='blue')
plt.plot(tme, i_f_B_line_plt[:len(tme)], label='Current FROM phase B from line', color='red')
plt.plot(tme, i_f_C_line_plt[:len(tme)], label='Current FROM phase C from line', color='green')
plt.title("Current from line")
plt.xlabel("Time")
plt.ylabel("Current from")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 4)
# SIGNS IN LOAD ARE FLIPPED. FOR SIGN CONVENTION CURRENTS LEAVE INJECTIONS SO IN THE CASE OF THE LOAD
# THAT MEANS THE CURRENTS ARE NEGATIVE
plt.plot(tme, -i_t_A_line_plt[:len(tme)], label='Current TO phase A from line', color='blue')
plt.plot(tme, -i_t_B_line_plt[:len(tme)], label='Current TO phase B from line', color='red')
plt.plot(tme, -i_t_C_line_plt[:len(tme)], label='Current TO phase C from line', color='green')
plt.title("Current to line")
plt.xlabel("Time")
plt.ylabel("Current to")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()

i_ser_A = find_name_in_block("i_ser_Pi_0", line0.emt_model)
i_ser_B = find_name_in_block("i_ser_Pi_1", line0.emt_model)
i_ser_C = find_name_in_block("i_ser_Pi_2", line0.emt_model)
i_ser_A_plt = y[:, problem.get_var_idx(i_ser_A)]
i_ser_B_plt = y[:, problem.get_var_idx(i_ser_B)]
i_ser_C_plt = y[:, problem.get_var_idx(i_ser_C)]

i_f_cap_A = find_name_in_block("i_cap_f_Pi_0", line0.emt_model)
i_f_cap_B = find_name_in_block("i_cap_f_Pi_1", line0.emt_model)
i_f_cap_C = find_name_in_block("i_cap_f_Pi_2", line0.emt_model)
i_f_cap_A_plt = y[:, problem.get_var_idx(i_f_cap_A)]
i_f_cap_B_plt = y[:, problem.get_var_idx(i_f_cap_B)]
i_f_cap_C_plt = y[:, problem.get_var_idx(i_f_cap_C)]

i_t_cap_A = find_name_in_block("i_cap_t_Pi_0", line0.emt_model)
i_t_cap_B = find_name_in_block("i_cap_t_Pi_1", line0.emt_model)
i_t_cap_C = find_name_in_block("i_cap_t_Pi_2", line0.emt_model)
i_t_cap_A_plt = y[:, problem.get_var_idx(i_t_cap_A)]
i_t_cap_B_plt = y[:, problem.get_var_idx(i_t_cap_B)]
i_t_cap_C_plt = y[:, problem.get_var_idx(i_t_cap_C)]

plt.figure(figsize=(12, 8))

plt.subplot(2, 2, 1)
plt.plot(tme, i_ser_A_plt[:len(tme)], label='Phase A series current line', color='blue')
plt.plot(tme, i_ser_B_plt[:len(tme)], label='Phase B series current line', color='red')
plt.plot(tme, i_ser_C_plt[:len(tme)], label='Phase C series current line', color='green')
plt.title("Series current in line")
plt.xlabel("Time")
plt.ylabel("Current")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 3)
plt.plot(tme, i_f_cap_A_plt[:len(tme)], label='Shunt current at from line phase A', color='blue')
plt.plot(tme, i_f_cap_B_plt[:len(tme)], label='Shunt current at from line phase B', color='red')
plt.plot(tme, i_f_cap_C_plt[:len(tme)], label='Shunt current at from line phase C', color='green')
plt.title("From shunt currents in line")
plt.xlabel("Time")
plt.ylabel("Current")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.subplot(2, 2, 4)
plt.plot(tme, i_t_cap_A_plt[:len(tme)], label='Shunt current at to line phase A', color='blue')
plt.plot(tme, i_t_cap_B_plt[:len(tme)], label='Shunt current at to line phase B', color='red')
plt.plot(tme, i_t_cap_C_plt[:len(tme)], label='Shunt current at to line phase C', color='green')
plt.title("To shunt currents in line")
plt.xlabel("Time")
plt.ylabel("Current")
plt.legend(loc='upper left')
plt.grid(True)
plt.legend()

plt.tight_layout()
print("Generating plots...")
plt.show()