# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import cProfile
import os
import pstats
import sys
from time import perf_counter
from typing import Any, cast

import numpy as np
import matplotlib
matplotlib.use("QtAgg")   # prova primer aquest a Windows/PyCharm
import matplotlib.pyplot as plt


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from VeraGridEngine.Utils.Symbolic.block import Block, Var
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.Emt.transformer_emt_template import get_transformer_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.enumerations import (
    BranchImpedanceMode,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    ShuntConnectionType,
    SolverType,
)
import VeraGridEngine.api as gce


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

    return None


def get_series(problem: EmtProblemDae, y: np.ndarray, variable: Var) -> np.ndarray:
    return y[:, problem.get_var_idx(variable)]


def abc_active_power(v_a: np.ndarray, v_b: np.ndarray, v_c: np.ndarray,
                     i_a: np.ndarray, i_b: np.ndarray, i_c: np.ndarray) -> np.ndarray:
    return (v_a * i_a) + (v_b * i_b) + (v_c * i_c)


def abc_reactive_power(v_a: np.ndarray, v_b: np.ndarray, v_c: np.ndarray,
                       i_a: np.ndarray, i_b: np.ndarray, i_c: np.ndarray) -> np.ndarray:
    return ((v_a - v_b) * i_c + (v_b - v_c) * i_a + (v_c - v_a) * i_b) / np.sqrt(3.0)


def waveform_rms(signal: np.ndarray) -> float:
    return float(np.sqrt(np.mean(signal * signal)))


def window_mean(signal: np.ndarray, window_slice: slice) -> float:
    return float(np.mean(signal[window_slice]))


circuit = gce.MultiCircuit(name='Grid - Source + Simplified EMT Transformer + R Load', Sbase=100.0, fbase=50.0)

# =====================================================================
# CREATE BUSES
# =====================================================================
bus1_ac = gce.Bus(name='Bus1_AC', Vnom=230.0, is_slack=True)
bus2_ac = gce.Bus(name='Bus2_AC', Vnom=230.0)

circuit.add_bus(bus1_ac)
circuit.add_bus(bus2_ac)

# =====================================================================
# CREATE DEVICES
# =====================================================================
gen1 = gce.Generator(
    name='Generator',
    vset=1.0,
    Snom=100.0,
    freq=50.0,
    r1=0.002,
    x1=0.25,
)
circuit.add_generator(bus1_ac, gen1)

transformer = gce.Transformer2W(
    name='Transformer',
    bus_from=bus1_ac,
    bus_to=bus2_ac,
    rate=100.0,
    r=0.005,
    x=0.06,
    g=0.0005,
    b=0.02,
    tap_module=1.0,
    tap_phase=0.0,
)
circuit.add_transformer2w(transformer)

load_total_mw = 20.0
load_phase_mw = load_total_mw / 3.0
load = gce.Load(
    name='Load',
    P=load_total_mw,
    Q=0.0,
    P1=load_phase_mw,
    P2=load_phase_mw,
    P3=load_phase_mw,
    Q1=0.0,
    Q2=0.0,
    Q3=0.0,
)
load.conn = ShuntConnectionType.GroundedStar
circuit.add_load(bus2_ac, load)

# =====================================================================
# BUILD EMT BLOCKS
# =====================================================================
for bus in circuit.buses:
    get_bus_emt_template(grid=circuit, bus=bus)

gen_mdl = get_generator_thevenin_rl_emt_template(vf=circuit.var_factory).block
trafo_mdl = get_transformer_emt_template(vf=circuit.var_factory, name=transformer.name).block
load_mdl = get_shunt_r_emt_template(vf=circuit.var_factory, phA=True, phB=True, phC=True, name=load.name).block

set_emt_model(device=gen1, model=gen_mdl, var_factory=circuit.var_factory)
set_emt_model(device=transformer, model=trafo_mdl, var_factory=circuit.var_factory)
set_emt_model(device=load, model=load_mdl, var_factory=circuit.var_factory)

# =====================================================================
# POWER FLOW
# =====================================================================
pf_options = PowerFlowOptions(
    solver_type=SolverType.NR,
    verbose=False,
    retry_with_other_methods=False,
    max_iter=50,
    tolerance=1e-6,
    control_q=False,
    control_taps_modules=False,
    control_taps_phase=False,
    orthogonalize_controls=False,
)

pf_results = gce.power_flow(grid=circuit, options=pf_options)

print("=" * 60)
print("POWER FLOW RESULTS")
print("=" * 60)
print(f"Converged: {pf_results.converged}")
if pf_results.converged:
    print(pf_results.get_bus_df())
    print(pf_results.get_branch_df())

# =====================================================================
# 3-PHASE POWER FLOW
# =====================================================================
pf_options_3ph = PowerFlowOptions(
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

power_flow_3ph = PowerFlowDriver3Ph(circuit, pf_options_3ph)
power_flow_3ph.run()
pf_res_3ph = power_flow_3ph.results

print("\n" + "=" * 60)
print("3-PHASE POWER FLOW RESULTS")
print("=" * 60)
print(f"Converged: {pf_res_3ph.converged}")
if pf_res_3ph.converged:
    print(pf_res_3ph.get_bus_df())
    print(pf_res_3ph.get_branch_df())

# =====================================================================
# EMT SIMULATION SETUP ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED")
# =====================================================================
CHOSEN_SOLVER = "SYMBOLIC"
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
    simulation_time=0.08,
    tolerance=1e-6,
    solver_type=SOLVER_TYPE_MAP[CHOSEN_SOLVER],
    integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
    initialization_method=EmtInitializationMethod.PseudoTransient,
    verbose=1,
)


def create_problem() -> EmtProblemDae:
    local_problem = EmtProblemDae(
        grid=circuit,
        options=options,
        pf_results_3ph=pf_res_3ph,
        pf_results=pf_results,
    )

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
            verbose=SOLVER_VERBOSE,
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
            verbose=SOLVER_VERBOSE,
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
            auto_vectorization=False,
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
            auto_build=False,
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
print("\n" + "=" * 60)
print("INITIAL GUESS TABLE")
print("=" * 60)
print(df)

print(f"\n{'=' * 60}")
print(f"Initializing Solver: {CHOSEN_SOLVER}")
print(f"{'=' * 60}\n")

solver = create_solver(CHOSEN_SOLVER, problem)
build_solver_backend(CHOSEN_SOLVER, solver, problem)

boundary_updater = cast(Any, problem)
simulation_t0 = perf_counter()
t, y, dy, _, _ = solver.simulate(boundary_updater=boundary_updater)
simulation_elapsed_s = perf_counter() - simulation_t0

print(f"Simulation runtime: {simulation_elapsed_s:.3f} s")
print("StructuralCompiled backend build stats")
for key, value in solver.get_backend_build_stats().items():
    print(f"  {key}: {value:.6f}s")

profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumtime')
print("\n" + "=" * 50)
print("--- PROFILER REPORT (Top 15 slowest functions) ---")
print("=" * 50)
stats.print_stats(15)
print("=" * 50 + "\n")

# =====================================================================
# RESULT EXTRACTION
# =====================================================================
tme = np.asarray(t)

v_A_bus1 = find_name_in_block("v_A_Bus1_AC_emt_template", bus1_ac.emt_model)
v_B_bus1 = find_name_in_block("v_B_Bus1_AC_emt_template", bus1_ac.emt_model)
v_C_bus1 = find_name_in_block("v_C_Bus1_AC_emt_template", bus1_ac.emt_model)

v_A_bus2 = find_name_in_block("v_A_Bus2_AC_emt_template", bus2_ac.emt_model)
v_B_bus2 = find_name_in_block("v_B_Bus2_AC_emt_template", bus2_ac.emt_model)
v_C_bus2 = find_name_in_block("v_C_Bus2_AC_emt_template", bus2_ac.emt_model)

i_A_gen = find_name_in_block("i_A_emt_thevenin_eq_generator_template", gen_mdl)
i_B_gen = find_name_in_block("i_B_emt_thevenin_eq_generator_template", gen_mdl)
i_C_gen = find_name_in_block("i_C_emt_thevenin_eq_generator_template", gen_mdl)

if_A_trafo = find_name_in_block(f"if_{transformer.name}_A", trafo_mdl)
if_B_trafo = find_name_in_block(f"if_{transformer.name}_B", trafo_mdl)
if_C_trafo = find_name_in_block(f"if_{transformer.name}_C", trafo_mdl)
it_A_trafo = find_name_in_block(f"it_{transformer.name}_A", trafo_mdl)
it_B_trafo = find_name_in_block(f"it_{transformer.name}_B", trafo_mdl)
it_C_trafo = find_name_in_block(f"it_{transformer.name}_C", trafo_mdl)

i_f_A_trafo = find_name_in_block(f"i_f_A_{transformer.name}", trafo_mdl)
i_f_B_trafo = find_name_in_block(f"i_f_B_{transformer.name}", trafo_mdl)
i_f_C_trafo = find_name_in_block(f"i_f_C_{transformer.name}", trafo_mdl)

i_A_load = find_name_in_block(f"i_A_{load_mdl.name}", load_mdl)
i_B_load = find_name_in_block(f"i_B_{load_mdl.name}", load_mdl)
i_C_load = find_name_in_block(f"i_C_{load_mdl.name}", load_mdl)

required_vars = [
    v_A_bus1, v_B_bus1, v_C_bus1,
    v_A_bus2, v_B_bus2, v_C_bus2,
    i_A_gen, i_B_gen, i_C_gen,
    if_A_trafo, if_B_trafo, if_C_trafo,
    it_A_trafo, it_B_trafo, it_C_trafo,
    i_f_A_trafo, i_f_B_trafo, i_f_C_trafo,
    i_A_load, i_B_load, i_C_load,
]

if any(var is None for var in required_vars):
    raise RuntimeError("Could not locate one or more EMT variables needed for the transformer diagnostics.")

v1_a = get_series(problem, y, v_A_bus1)
v1_b = get_series(problem, y, v_B_bus1)
v1_c = get_series(problem, y, v_C_bus1)

v2_a = get_series(problem, y, v_A_bus2)
v2_b = get_series(problem, y, v_B_bus2)
v2_c = get_series(problem, y, v_C_bus2)

i_gen_a = get_series(problem, y, i_A_gen)
i_gen_b = get_series(problem, y, i_B_gen)
i_gen_c = get_series(problem, y, i_C_gen)

i_tf_if_a = get_series(problem, y, if_A_trafo)
i_tf_if_b = get_series(problem, y, if_B_trafo)
i_tf_if_c = get_series(problem, y, if_C_trafo)
i_tf_it_a = get_series(problem, y, it_A_trafo)
i_tf_it_b = get_series(problem, y, it_B_trafo)
i_tf_it_c = get_series(problem, y, it_C_trafo)

i_tf_winding_a = get_series(problem, y, i_f_A_trafo)
i_tf_winding_b = get_series(problem, y, i_f_B_trafo)
i_tf_winding_c = get_series(problem, y, i_f_C_trafo)

i_load_a = get_series(problem, y, i_A_load)
i_load_b = get_series(problem, y, i_B_load)
i_load_c = get_series(problem, y, i_C_load)

# Positive values below are aligned with power transfer from bus 1 to bus 2.
i_tf_primary_into_a = i_tf_if_a
i_tf_primary_into_b = i_tf_if_b
i_tf_primary_into_c = i_tf_if_c
i_tf_secondary_out_a = -i_tf_it_a
i_tf_secondary_out_b = -i_tf_it_b
i_tf_secondary_out_c = -i_tf_it_c
i_mag_a = i_tf_if_a - i_tf_winding_a
i_mag_b = i_tf_if_b - i_tf_winding_b
i_mag_c = i_tf_if_c - i_tf_winding_c

p_source = abc_active_power(v1_a, v1_b, v1_c, i_gen_a, i_gen_b, i_gen_c)
q_source = abc_reactive_power(v1_a, v1_b, v1_c, i_gen_a, i_gen_b, i_gen_c)

p_tf_primary = abc_active_power(v1_a, v1_b, v1_c, i_tf_if_a, i_tf_if_b, i_tf_if_c)
q_tf_primary = abc_reactive_power(v1_a, v1_b, v1_c, i_tf_if_a, i_tf_if_b, i_tf_if_c)

p_tf_secondary = -abc_active_power(v2_a, v2_b, v2_c, i_tf_it_a, i_tf_it_b, i_tf_it_c)
q_tf_secondary = -abc_reactive_power(v2_a, v2_b, v2_c, i_tf_it_a, i_tf_it_b, i_tf_it_c)

p_load = -abc_active_power(v2_a, v2_b, v2_c, i_load_a, i_load_b, i_load_c)
q_load = -abc_reactive_power(v2_a, v2_b, v2_c, i_load_a, i_load_b, i_load_c)

p_source_loss = p_source - p_tf_primary
p_transformer_loss = p_tf_primary - p_tf_secondary
p_load_mismatch = p_tf_secondary - p_load
p_total_mismatch = p_source - p_load

q_source_loss = q_source - q_tf_primary
q_transformer_drop = q_tf_primary - q_tf_secondary
q_load_mismatch = q_tf_secondary - q_load

steady_window_samples = max(int(round(0.02 / options.time_step)), 1)
steady_slice = slice(max(len(tme) - steady_window_samples, 0), len(tme))

turns_ratio = float(transformer.tap_module)
s_base_mva = float(circuit.Sbase)
primary_v_phase_rms_pu = np.mean([
    waveform_rms(v1_a[steady_slice]),
    waveform_rms(v1_b[steady_slice]),
    waveform_rms(v1_c[steady_slice]),
])
secondary_v_phase_rms_pu = np.mean([
    waveform_rms(v2_a[steady_slice]),
    waveform_rms(v2_b[steady_slice]),
    waveform_rms(v2_c[steady_slice]),
])
primary_i_rms_pu = np.mean([
    waveform_rms(i_tf_primary_into_a[steady_slice]),
    waveform_rms(i_tf_primary_into_b[steady_slice]),
    waveform_rms(i_tf_primary_into_c[steady_slice]),
])
secondary_i_rms_pu = np.mean([
    waveform_rms(i_tf_secondary_out_a[steady_slice]),
    waveform_rms(i_tf_secondary_out_b[steady_slice]),
    waveform_rms(i_tf_secondary_out_c[steady_slice]),
])

bus1_v_phase_base_kv = float(bus1_ac.Vnom) / np.sqrt(3.0)
bus2_v_phase_base_kv = float(bus2_ac.Vnom) / np.sqrt(3.0)
bus1_i_base_ka = float(circuit.Sbase) / (np.sqrt(3.0) * float(bus1_ac.Vnom))
bus2_i_base_ka = float(circuit.Sbase) / (np.sqrt(3.0) * float(bus2_ac.Vnom))

primary_v_phase_rms_kv = primary_v_phase_rms_pu * bus1_v_phase_base_kv
secondary_v_phase_rms_kv = secondary_v_phase_rms_pu * bus2_v_phase_base_kv
primary_i_rms_ka = primary_i_rms_pu * bus1_i_base_ka
secondary_i_rms_ka = secondary_i_rms_pu * bus2_i_base_ka

referred_current_error_a = i_tf_primary_into_a - i_tf_secondary_out_a
referred_voltage_error_a = v1_a - (turns_ratio * v2_a)

print("=" * 60)
print("STEADY-STATE SUMMARY (final 20 ms window)")
print("=" * 60)
print(f"Turns ratio used n = {turns_ratio:.6f}")
print(f"Primary phase RMS voltage:   {primary_v_phase_rms_pu:.6f} pu, {primary_v_phase_rms_kv:.3f} kV")
print(f"Secondary phase RMS voltage: {secondary_v_phase_rms_pu:.6f} pu, {secondary_v_phase_rms_kv:.3f} kV")
print(f"Primary phase RMS current:   {primary_i_rms_pu:.6f} pu, {primary_i_rms_ka:.6f} kA")
print(f"Secondary phase RMS current: {secondary_i_rms_pu:.6f} pu, {secondary_i_rms_ka:.6f} kA")
print(f"Primary active power:        {window_mean(p_tf_primary, steady_slice):.6f} pu, {window_mean(p_tf_primary, steady_slice) * s_base_mva:.3f} MW")
print(f"Primary reactive power:      {window_mean(q_tf_primary, steady_slice):.6f} pu, {window_mean(q_tf_primary, steady_slice) * s_base_mva:.3f} MVAr")
print(f"Secondary active power:      {window_mean(p_tf_secondary, steady_slice):.6f} pu, {window_mean(p_tf_secondary, steady_slice) * s_base_mva:.3f} MW")
print(f"Secondary reactive power:    {window_mean(q_tf_secondary, steady_slice):.6f} pu, {window_mean(q_tf_secondary, steady_slice) * s_base_mva:.3f} MVAr")
print(f"Load active power:           {window_mean(p_load, steady_slice):.6f} pu, {window_mean(p_load, steady_slice) * s_base_mva:.3f} MW")
print(f"Load reactive power:         {window_mean(q_load, steady_slice):.6f} pu, {window_mean(q_load, steady_slice) * s_base_mva:.3f} MVAr")
print(f"Source active power:         {window_mean(p_source, steady_slice):.6f} pu, {window_mean(p_source, steady_slice) * s_base_mva:.3f} MW")
print(f"Estimated source losses:     {window_mean(p_source_loss, steady_slice):.6f} pu, {window_mean(p_source_loss, steady_slice) * s_base_mva:.3f} MW")
print(f"Estimated transformer losses:{window_mean(p_transformer_loss, steady_slice):.6f} pu, {window_mean(p_transformer_loss, steady_slice) * s_base_mva:.3f} MW")
print(f"Secondary/load mismatch:     {window_mean(p_load_mismatch, steady_slice):.6f} pu, {window_mean(p_load_mismatch, steady_slice) * s_base_mva:.3f} MW")
print(f"Total source-load mismatch:  {window_mean(p_total_mismatch, steady_slice):.6f} pu, {window_mean(p_total_mismatch, steady_slice) * s_base_mva:.3f} MW")
print(f"Terminal current diff A:     {waveform_rms(referred_current_error_a[steady_slice]):.6e} pu RMS")
print(f"Referred voltage error A:    {waveform_rms(referred_voltage_error_a[steady_slice]):.6e} pu RMS")

if not ENABLE_PLOTS:
    print("Plotting disabled; stopping after summary.")
    raise SystemExit(0)

plot_dir = os.path.join(os.path.dirname(__file__), "plots")
os.makedirs(plot_dir, exist_ok=True)

fig = plt.figure(figsize=(14, 10))
plt.subplot(2, 1, 1)
plt.plot(tme, v1_a, label='Bus1 - Phase A', color='blue')
plt.plot(tme, v1_b, label='Bus1 - Phase B', color='red')
plt.plot(tme, v1_c, label='Bus1 - Phase C', color='green')
plt.title("Bus1 AC - Phase Voltages")
plt.xlabel("Time [s]")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(2, 1, 2)
plt.plot(tme, v2_a, label='Bus2 - Phase A', color='blue')
plt.plot(tme, v2_b, label='Bus2 - Phase B', color='red')
plt.plot(tme, v2_c, label='Bus2 - Phase C', color='green')
plt.title("Bus2 AC - Phase Voltages")
plt.xlabel("Time [s]")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)
plt.tight_layout()
fig.savefig(os.path.join(plot_dir, 'trafo_emt_bus_voltages.png'), dpi=150)
plt.show()
plt.close(fig)

fig = plt.figure(figsize=(14, 10))
plt.subplot(2, 1, 1)
plt.plot(tme, i_tf_primary_into_a, label='Primary into trafo - A', color='blue')
plt.plot(tme, i_tf_primary_into_b, label='Primary into trafo - B', color='red')
plt.plot(tme, i_tf_primary_into_c, label='Primary into trafo - C', color='green')
plt.title("Transformer Primary Currents")
plt.xlabel("Time [s]")
plt.ylabel("Current [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(2, 1, 2)
plt.plot(tme, i_tf_secondary_out_a, label='Secondary out of trafo - A', color='blue')
plt.plot(tme, i_tf_secondary_out_b, label='Secondary out of trafo - B', color='red')
plt.plot(tme, i_tf_secondary_out_c, label='Secondary out of trafo - C', color='green')
plt.title("Transformer Secondary Currents")
plt.xlabel("Time [s]")
plt.ylabel("Current [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)
plt.tight_layout()
fig.savefig(os.path.join(plot_dir, 'trafo_emt_transformer_currents.png'), dpi=150)
plt.show()
plt.close(fig)

fig = plt.figure(figsize=(14, 10))
plt.subplot(3, 1, 1)
plt.plot(tme, v1_a, label='Primary voltage A', color='black')
plt.plot(tme, (turns_ratio * v2_a), label='Secondary referred voltage A', color='tab:orange')
plt.title("Referred Voltage Comparison - Phase A")
plt.xlabel("Time [s]")
plt.ylabel("Voltage [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(3, 1, 2)
plt.plot(tme, referred_voltage_error_a, label='Primary minus referred secondary voltage A', color='purple')
plt.title("Referred Voltage Error - Phase A")
plt.xlabel("Time [s]")
plt.ylabel("Error [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(3, 1, 3)
plt.plot(tme, i_mag_a, label='Magnetizing/core-loss current A', color='teal')
plt.plot(tme, i_mag_b, label='Magnetizing/core-loss current B', color='tab:pink')
plt.plot(tme, i_mag_c, label='Magnetizing/core-loss current C', color='tab:gray')
plt.title("Primary Shunt Branch Current Estimate")
plt.xlabel("Time [s]")
plt.ylabel("Current [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)
plt.tight_layout()
fig.savefig(os.path.join(plot_dir, 'trafo_emt_referred_current_and_magnetizing.png'), dpi=150)
plt.show()
plt.close(fig)

fig = plt.figure(figsize=(14, 10))
plt.subplot(2, 1, 1)
plt.plot(tme, p_source, label='Source injected P', color='black')
plt.plot(tme, p_tf_primary, label='Transformer primary absorbed P', color='blue')
plt.plot(tme, p_tf_secondary, label='Transformer secondary delivered P', color='green')
plt.plot(tme, p_load, label='Load absorbed P', color='red')
plt.title("Active Power Diagnostics")
plt.xlabel("Time [s]")
plt.ylabel("Power [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(2, 1, 2)
plt.plot(tme, q_source, label='Source injected Q', color='black')
plt.plot(tme, q_tf_primary, label='Transformer primary absorbed Q', color='blue')
plt.plot(tme, q_tf_secondary, label='Transformer secondary delivered Q', color='green')
plt.plot(tme, q_load, label='Load absorbed Q', color='red')
plt.title("Reactive Power Diagnostics")
plt.xlabel("Time [s]")
plt.ylabel("Power [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)
plt.tight_layout()
fig.savefig(os.path.join(plot_dir, 'trafo_emt_power_diagnostics.png'), dpi=150)
plt.show()
plt.close(fig)

fig = plt.figure(figsize=(14, 10))
plt.subplot(2, 1, 1)
plt.plot(tme, p_source_loss, label='Source internal losses estimate', color='black')
plt.plot(tme, p_transformer_loss, label='Transformer losses estimate', color='blue')
plt.plot(tme, p_load_mismatch, label='Secondary-load mismatch', color='red')
plt.plot(tme, p_total_mismatch, label='Source-load total mismatch', color='green')
plt.title("Active Power Balance Residuals")
plt.xlabel("Time [s]")
plt.ylabel("Power [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)

plt.subplot(2, 1, 2)
plt.plot(tme, q_source_loss, label='Source Q gap', color='black')
plt.plot(tme, q_transformer_drop, label='Transformer Q drop', color='blue')
plt.plot(tme, q_load_mismatch, label='Secondary-load Q mismatch', color='red')
plt.title("Reactive Power Balance Residuals")
plt.xlabel("Time [s]")
plt.ylabel("Power [p.u.]")
plt.legend(loc='upper right')
plt.grid(True)
plt.tight_layout()
fig.savefig(os.path.join(plot_dir, 'trafo_emt_power_balance.png'), dpi=150)
plt.show()
plt.close(fig)

print(f"Plots saved under: {plot_dir}")
print("Simulation completed successfully!")
