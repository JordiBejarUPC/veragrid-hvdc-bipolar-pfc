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


from VeraGridEngine.Templates.Emt.xfmr_emt_template import get_xfmr_emt_template
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.converter_emt_template import get_emt_ideal_converter
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model

from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import EmtInitializationMethod, DynamicIntegrationMethod, EmtSolverTypes, ShuntConnectionType, ConverterControlType, SolverType
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

circuit = gce.MultiCircuit(name='Grid - Generator + Transformer + VSC + DC Load', Sbase=100.0, fbase=50.0)

# =====================================================================
# CREATE BUSES
# =====================================================================
# Bus 1: AC slack bus with generator
bus1_ac = gce.Bus(name='Bus1_AC', Vnom=230.0, is_slack=True)
circuit.add_bus(bus1_ac)

# Bus 2: AC bus connected to transformer and VSC
bus2_ac = gce.Bus(name='Bus2_AC', Vnom=230.0)
circuit.add_bus(bus2_ac)

# =====================================================================
# CREATE DEVICES
# =====================================================================

# Generator at Bus 1 (slack)
gen1 = gce.Generator(
    name='Generator',
    vset=1.0,      # Voltage setpoint (p.u.)
    Snom=100.0,    # Nominal power
    freq=50.0,     # Frequency
    r1=0.001,      # Internal resistance (Ra)
    x1=0.4         # Synchronous reactance (Xd')
)
circuit.add_generator(bus1_ac, gen1)

# Transformer: Bus 1 -> Bus 2
transformer = gce.Transformer2W(
    name='Transformer',
    bus_from=bus1_ac,
    bus_to=bus2_ac,
    rate=100.0,
    r=0.01,        # Resistance (p.u.)
    x=0.1,         # Reactance (p.u.)
    tap_module=1.0,
    tap_phase=0.0,
)
circuit.add_transformer2w(transformer)

# DC load for the PF/DC-link operating point
load = gce.Load(
    name='Load',
    P=50.0,
    Q=0.0,
)
circuit.add_load(bus2_ac, load)

###########################################################################################################################
# BUILD EMT BLOCK
###########################################################################################################################

# =====================================================================
# INITIALIZE BUS EMT MODELS
# =====================================================================
for bus in circuit.buses:
    get_bus_emt_template(grid=circuit, bus=bus)

# =====================================================================
# BUILD DEVICE EMT MODELS
# =====================================================================

# Generator model (Thevenin equivalent)
gen_mdl = get_generator_thevenin_rl_emt_template(vf=circuit.var_factory).block

# Transformer model (series RL with ideal transformer)
trafo_mdl = get_xfmr_emt_template(vf= circuit.var_factory).block

# DC Load model (constant power load)
load_mdl = get_shunt_r_emt_template(vf=circuit.var_factory, phA=True, phB=True, phC=True).block

# =====================================================================
# ASSIGN MODELS TO DEVICES
# =====================================================================

set_emt_model(device=gen1, model=gen_mdl, var_factory=circuit.var_factory)
set_emt_model(device=transformer, model=trafo_mdl, var_factory=circuit.var_factory)
set_emt_model(device=load, model=load_mdl, var_factory=circuit.var_factory)

###########################################################################################################################
# POWER FLOW (for DC initialization)
###########################################################################################################################
#
# pf_options = gce.PowerFlowOptions(
#     solver_type=SolverType.NR,
#     verbose=False,
#     retry_with_other_methods=True,
#     max_iter=100,
#     tolerance=1e-6,
#     control_q=True,
#     control_taps_modules=False,
#     control_taps_phase=False,
#     orthogonalize_controls=False,
# )
#
# pf_results = gce.power_flow(grid=circuit, options=pf_options)
#
# print("="*60)
# print("POWER FLOW RESULTS")
# print("="*60)
# print(f"Converged: {pf_results.converged}")
# if pf_results.converged:
#     print(pf_results.get_bus_df())
#     print(pf_results.get_branch_df())

###########################################################################################################################
# 3ph POWER FLOW (for EMT initialization)
###########################################################################################################################

pf_options_3ph = PowerFlowOptions(
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

power_flow_3ph = PowerFlowDriver3Ph(circuit, pf_options_3ph)
power_flow_3ph.run()
pf_res_3ph = power_flow_3ph.results

print("\n" + "="*60)
print("3-PHASE POWER FLOW RESULTS")
print("="*60)
print(f"Converged: {pf_res_3ph.converged}")
# if pf_res_3ph.converged:
#     print(pf_res_3ph.get_bus_df())
#     print(pf_res_3ph.get_branch_df())
#     print("\nVSC Results:")
#     print(f"  VSC Power (AC side): {pf_res_3ph.St_vsc}")
#     print(f"  VSC Power (DC side): {pf_res_3ph.Pfp_vsc}")

###########################################################################################################################
# EMT SIMULATION SETUP
###########################################################################################################################

# Solver configuration
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

options = EmtOptions(
    time_step=5e-6,
    simulation_time=0.02,  # 20 ms
    tolerance=1e-6,
    solver_type=SOLVER_TYPE_MAP[CHOSEN_SOLVER],
    integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
    initialization_method = EmtInitializationMethod.Explicit,
    verbose=1
)

def create_problem() -> EmtProblemDae:
    local_problem = EmtProblemDae(
        grid=circuit,
        options=options,
        pf_results_3ph=pf_res_3ph,
        pf_results=None
    )
    # local_problem = EmtProblemDae(
    #     grid=circuit,
    #     options=options,
    #     pf_results_3Ph=None,
    #     pf_results=None
    # )

    if ENABLE_NEWTON_TRACE:
        local_problem.set_newton_trace_collector(NewtonTraceCollector())

    return local_problem


def create_solver(solver_key: str, local_problem: EmtProblemDae):
    if solver_key == "SYMBOLIC":
        return JitSymbolicSolver(
            problem=local_problem,
            t0=0.0,
            t_end=options.simulation_time,
            h=options.time_step,
            method=options.integration_method,
            pred_method=DynamicIntegrationMethod.OdeEuler,
            dense_threshold=DENSE_THRESHOLD,
            verbose=SOLVER_VERBOSE
        )

    if solver_key == "AD":
        return JitAdSolver(
            problem=local_problem,
            t0=0.0,
            t_end=options.simulation_time,
            h=options.time_step,
            method=options.integration_method,
            pred_method=DynamicIntegrationMethod.OdeEuler,
            dense_threshold=DENSE_THRESHOLD,
            verbose=SOLVER_VERBOSE
        )

    if solver_key == "VECTORIZED":
        return StructuralVectorizedSolver(
            problem=local_problem,
            t0=0.0,
            t_end=options.simulation_time,
            h=options.time_step,
            method=options.integration_method,
            pred_method=DynamicIntegrationMethod.OdeEuler,
            dense_threshold=DENSE_THRESHOLD,
            verbose=SOLVER_VERBOSE,
            auto_vectorization=False
        )

    if solver_key == "COMPILED":
        return StructuralCompiledSolver(
            problem=local_problem,
            t0=0.0,
            t_end=options.simulation_time,
            h=options.time_step,
            method=options.integration_method,
            pred_method=DynamicIntegrationMethod.OdeEuler,
            dense_threshold=DENSE_THRESHOLD,
            verbose=SOLVER_VERBOSE,
            auto_build=False
        )

    raise ValueError(f"Solver '{solver_key}' not recognized.")


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

    raise ValueError(f"Solver '{solver_key}' not recognized.")


# =====================================================================
# RUN SIMULATION
# =====================================================================
problem = create_problem()

df = problem.get_init_guess_table()
print("\n" + "="*60)
print("INITIAL GUESS TABLE")
print("="*60)
print(df)

print(f"\n{'='*60}")
print(f"Initializing Solver: {CHOSEN_SOLVER}")
print(f"{'='*60}\n")

solver = create_solver(CHOSEN_SOLVER, problem)
build_solver_backend(CHOSEN_SOLVER, solver, problem)

boundary_updater = cast(Any, problem)
t, y, dy, _, _  = solver.simulate(boundary_updater=boundary_updater)

print("StructuralCompiled backend build stats")
for key, value in solver.get_backend_build_stats().items():
    print(f"  {key}: {value:.6f}s")

# =====================================================================
# PROFILING REPORT
# =====================================================================
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

# =====================================================================
# PLOTTING
# =====================================================================
xlim = options.simulation_time
h = options.time_step
steps: int = int(options.simulation_time / h)
tme: np.ndarray = np.linspace(0, options.simulation_time, steps)

# Find voltage variables in buses
v_A_bus1 = find_name_in_block(f"v_A_emt_bus_template", bus1_ac.emt_model)
v_B_bus1 = find_name_in_block(f"v_B_emt_bus_template", bus1_ac.emt_model)
v_C_bus1 = find_name_in_block(f"v_C_emt_bus_template", bus1_ac.emt_model)

v_A_bus2 = find_name_in_block(f"v_A_emt_bus_template", bus2_ac.emt_model)
v_B_bus2 = find_name_in_block(f"v_B_emt_bus_template", bus2_ac.emt_model)
v_C_bus2 = find_name_in_block(f"v_C_emt_bus_template", bus2_ac.emt_model)

v_DC_bus3 = find_name_in_block(f"v_DC_emt_bus_template", bus3_dc.emt_model)

# Generator currents
i_A_gen = find_name_in_block(f"i_A_emt_thevenin_eq_generator_template", gen_mdl)
i_B_gen = find_name_in_block(f"i_B_emt_thevenin_eq_generator_template", gen_mdl)
i_C_gen = find_name_in_block(f"i_C_emt_thevenin_eq_generator_template", gen_mdl)

theta_gen = find_name_in_block("theta_emt_thevenin_eq_generator_template", gen_mdl)

# VSC currents (AC side)
i_A_vsc = find_name_in_block(f"i_A_{vsc.name}", vsc_mdl)
i_B_vsc = find_name_in_block(f"i_B_{vsc.name}", vsc_mdl)
i_C_vsc = find_name_in_block(f"i_C_{vsc.name}", vsc_mdl)

# DC current
i_DC_vsc = find_name_in_block(f"Idc_{vsc.name}", vsc_mdl)

# Plot voltages at AC buses
plt.figure(figsize=(14, 10))

plt.subplot(3, 1, 1)
if v_A_bus1:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(v_A_bus1)], label='Bus1 - Phase A', color='blue')
if v_B_bus1:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(v_B_bus1)], label='Bus1 - Phase B', color='red')
if v_C_bus1:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(v_C_bus1)], label='Bus1 - Phase C', color='green')
plt.title("Bus1 AC - Voltages")
plt.xlabel("Time [s]")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(3, 1, 2)
if v_A_bus2:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(v_A_bus2)], label='Bus2 - Phase A', color='blue')
if v_B_bus2:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(v_B_bus2)], label='Bus2 - Phase B', color='red')
if v_C_bus2:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(v_C_bus2)], label='Bus2 - Phase C', color='green')
plt.title("Bus2 AC - Voltages (VSC side)")
plt.xlabel("Time [s]")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(3, 1, 3)
if v_DC_bus3:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(v_DC_bus3)], label='Bus3 DC Voltage', color='orange')
plt.title("Bus3 DC - Voltage")
plt.xlabel("Time [s]")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.tight_layout()
plt.show()

# Plot generator currents and angle
plt.figure(figsize=(14, 10))

plt.subplot(3, 1, 1)
if i_A_gen:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(i_A_gen)], label='Generator - Phase A', color='blue')
if i_B_gen:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(i_B_gen)], label='Generator - Phase B', color='red')
if i_C_gen:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(i_C_gen)], label='Generator - Phase C', color='green')
plt.title("Generator Currents")
plt.xlabel("Time [s]")
plt.ylabel("Current [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(3, 1, 2)
if theta_gen:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(theta_gen)], label='Theta Generator', color='purple')
plt.title("Generator Electrical Angle")
plt.xlabel("Time [s]")
plt.ylabel("Angle [rad]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(3, 1, 3)
if i_A_vsc:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(i_A_vsc)], label='VSC - Phase A', color='blue')
if i_B_vsc:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(i_B_vsc)], label='VSC - Phase B', color='red')
if i_C_vsc:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(i_C_vsc)], label='VSC - Phase C', color='green')
plt.title("VSC AC Currents")
plt.xlabel("Time [s]")
plt.ylabel("Current [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.tight_layout()
plt.show()

# Plot VSC DC current
plt.figure(figsize=(10, 5))
if i_DC_vsc:
    plt.plot(tme, y[:len(tme), problem.get_var_idx(i_DC_vsc)], label='VSC DC Current', color='orange')
plt.title("VSC DC Current")
plt.xlabel("Time [s]")
plt.ylabel("Current [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)
plt.show()

print("Simulation completed successfully!")
