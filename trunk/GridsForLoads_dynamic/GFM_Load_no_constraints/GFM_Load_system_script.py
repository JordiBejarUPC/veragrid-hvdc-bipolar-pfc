# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import matplotlib.pyplot as plt


import sys
import os


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from typing import Any, cast

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions

from VeraGridEngine.Utils.Symbolic.block import Block

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref

from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template

from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model

from VeraGridEngine.enumerations import (BranchImpedanceMode, DynamicIntegrationMethod, EmtInitializationMethod,
                                         EmtSolverTypes, ShuntConnectionType, SolverType)
from trunk.GridsForLoads_dynamic.gridsforloads_converter_template import (get_trafo_grid_connection_G4L,
                                                                          get_complete_load_template_G4L)
import VeraGridEngine.api as gce





def get_var_idx(problem: EmtProblemDae, name: str) -> int:
    for var in list(problem.get_state_vars()) + list(problem.get_algebraic_vars()):
        if var.name == name:
            return problem.get_var_idx(var)
    raise KeyError(name)


def try_get_series(problem: EmtProblemDae, y_arr: np.ndarray, name: str):
    try:
        idx = get_var_idx(problem=problem, name=name)
        return y_arr[:, idx]
    except Exception:
        return None


def plot_if_available(ax, t_arr: np.ndarray, series, label: str):
    if series is not None:
        ax.plot(t_arr, series, label=label)
    else:
        print(f"variable:{label} is not in results")


def try_get_init_value(problem: EmtProblemDae, name: str):
    try:
        idx = get_var_idx(problem=problem, name=name)
        x0 = problem.get_x0()
        return x0[idx]
    except Exception:
        return None


def try_get_init_diff_value(problem: EmtProblemDae, name: str):
    try:
        for dv in problem.get_diff_vars():
            if dv.name == name:
                idx = problem.get_diff_var_idx(dv)
                dx0 = problem.get_dx0()
                return dx0[idx]
        return None
    except Exception:
        return None


def print_series_summary(problem: EmtProblemDae, y_arr: np.ndarray, name: str):
    series = try_get_series(problem, y_arr, name)
    if series is None:
        print(f"series_summary:{name} unavailable")
        return

    print(
        f"series_summary:{name} "
        f"start={series[0]:.9f} end={series[-1]:.9f} "
        f"min={np.min(series):.9f} max={np.max(series):.9f} "
        f"mean={np.mean(series):.9f} delta={(series[-1] - series[0]):.9f}"
    )


def print_diff_summary(problem: EmtProblemDae, dy_arr: np.ndarray, name: str):
    try:
        for dv in problem.get_diff_vars():
            if dv.name == name:
                idx = problem.get_diff_var_idx(dv)
                series = dy_arr[:, idx]
                print(
                    f"diff_summary:{name} "
                    f"start={series[0]:.9f} end={series[-1]:.9f} "
                    f"min={np.min(series):.9f} max={np.max(series):.9f} "
                    f"mean={np.mean(series):.9f}"
                )
                return
        print(f"diff_summary:{name} unavailable")
    except Exception:
        print(f"diff_summary:{name} unavailable")

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()) + block.diff_vars:
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


######################################################################################################
# Build grid
######################################################################################################

U       = 33000 / 1000 # V -> kV
Sb      = 2000000 / 1000000 # VA -> MVA
omega   = 2 * np.pi * 50.0

grid = gce.MultiCircuit(Sbase=Sb, fbase=50.0)

# Buses
bus0 = gce.Bus(name="Bus0", Vnom=U, is_slack=True)
bus1 = gce.Bus(name="Bus1", Vnom=U)

grid.add_bus(bus0)
grid.add_bus(bus1)

# Line/transformer equivalent in VeraGrid static units:
# - bus voltage base in kV
# - system base in MVA
# - branch r/x/b in p.u.
R_trf_pu = 0.1 / 10.0
X_trf_pu = 1.0 / 10.0
# The EMT template implements the shunt only on the "to" side, while the
# VeraGrid static line ``b`` is a symmetric pi-line susceptance used for PF
# and EMT initialization. Keep the matching total susceptance here.
# B_sh_pu = 2.0 / 15.0
B_sh_pu = 1.0 / 15.0
line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, r=R_trf_pu, x=X_trf_pu, b=B_sh_pu, rate=Sb)

# load
P_dc_pu = 0.8
R_f_pu = 0.1 / 10.0

# Initial PF-based converter currents in pu.
i_A0 = 0.030786800783117237
i_B0 = 0.31277189836412106
i_C0 = -0.34355869914723824

P_loss_f_pu = R_f_pu * (i_A0*i_A0 + i_B0*i_B0 + i_C0*i_C0)

P_load_pu = P_dc_pu + P_loss_f_pu
# P_target = P_load_pu * 2.0  # MW, because Sb = 2 MVA
P_target = 1.6
load = gce.Load(name="load",P = P_target, P1= P_target/3, P2= P_target/3, P3= P_target/3, Q =0.0, Q1= 0.0, Q2= 0.0, Q3= 0.0)
load.conn = ShuntConnectionType.GroundedStar

# Generator
SCR = 3
RL  = 0.1
R_g_pu = RL / SCR
X_g_pu = 1.0 / SCR
gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq = 50, r1=R_g_pu, x1=X_g_pu)

grid.add_line(line0)
grid.add_generator(bus=bus0, api_obj=gen0)
grid.add_load(bus=bus1, api_obj=load)


for bus in grid.buses:
    get_bus_emt_template(grid, bus)

######################################################################################################
# Build EMT models
######################################################################################################
gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf= grid.var_factory).block

line_mdl = get_trafo_grid_connection_G4L(vf= grid.var_factory).block

load_mdl = get_complete_load_template_G4L(vf= grid.var_factory).block

######################################################################################################
# Add models to devices
######################################################################################################

set_emt_model(device=gen0, model=gen_mdl, var_factory= grid.var_factory)

set_emt_model(device=line0, model=line_mdl, var_factory= grid.var_factory)

set_emt_model(device=load, model=load_mdl, var_factory= grid.var_factory)

######################################################################################################
# PowerFlow
######################################################################################################

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

######################################################################################################
# EMT options and problem
######################################################################################################


options = EmtOptions(time_step = 1e-6,
                     simulation_time =  0.1, # s
                     tolerance = 1e-6,
                     solver_type = EmtSolverTypes.StructuralCompiled,
                     # initialization_method = EmtInitializationMethod.PseudoTransient,
                     initialization_method = EmtInitializationMethod.Explicit,
                     integration_method = DynamicIntegrationMethod.DaeTrapezoidal,
                     verbose = 1)

problem = EmtProblemDae(grid=grid,
                              options=options,
                              pf_results_3ph=None,
                              pf_results=res)

print(problem.initialization_report.method_requested)
print(problem.initialization_report.method_used)
print(problem.initialization_report.status)
print(problem.initialization_report.newton_iterations)
print(problem.initialization_report.pseudo_transient_steps)
print(problem.initialization_report.message)

DENSE_THRESHOLD = 0

df = problem.get_init_guess_table()
print(f"init_guess_table\n{df}")

init_diagnostic_names = [
    "Pac_bus_G4L_grid_side_converter",
    "Pac_G4L_grid_side_converter",
    "p_dc_G4L_load_side_converter_control",
    "i_dc_G4L_grid_side_converter",
    "i_dc_L_G4L_load_side_converter_control",
    "i_cap_dc_G4L_load_side_converter",
    "v_dc_G4L_load_side_converter",
    "i_q_G4L_clark_park_transforms_qd",
    "i_q_out_VA_G4L_Virtual_admittance",
    "i_q_lim_G4L_current_limiter",
]

init_diagnostics: dict[str, float | None] = {}
print("Initial scalar diagnostics")
for name in init_diagnostic_names:
    value = try_get_init_value(problem, name)
    init_diagnostics[name] = value
    print(f"  {name} = {value}")

i_dc_init = init_diagnostics["i_dc_G4L_grid_side_converter"]
i_dc_L_init = init_diagnostics["i_dc_L_G4L_load_side_converter_control"]
i_cap_dc_init = init_diagnostics["i_cap_dc_G4L_load_side_converter"]
if None not in (i_dc_init, i_dc_L_init, i_cap_dc_init):
    dc_current_balance = i_dc_init - i_dc_L_init - i_cap_dc_init
    print(f"  dc_current_balance = {dc_current_balance}")
else:
    print("  dc_current_balance = unavailable")

# RL branch residual diagnostics at t = 0 for the grid-side converter.
omega_base = 2 * np.pi * 50.0
X_f_pu = 1.0 / 10.0
R_f_pu = 0.1 / 10.0
L_f = X_f_pu / omega_base
for ph in ["A", "B", "C"]:
    v_bus = try_get_init_value(problem, f"v_{ph}_Bus1_emt_template")
    v_con = try_get_init_value(problem, f"v_con_{ph}_mode_G4L_current_loop")
    i_ser = try_get_init_value(problem, f"i_ser_{ph}_G4L_grid_side_converter")
    di_ser = try_get_init_diff_value(problem, f"di_ser_{ph}_G4L_grid_side_converter")
    if None not in (v_bus, v_con, i_ser, di_ser):
        residual = v_bus - v_con - R_f_pu * i_ser - L_f * di_ser
        v_con_required = v_bus - R_f_pu * i_ser - L_f * di_ser
        print(f"grid-side RL residual phase {ph}: {residual}")
        print(f"  v_bus={v_bus}, v_con={v_con}, i={i_ser}, di={di_ser}")
        print(f"  v_con_required={v_con_required}, dv_con={(v_con - v_con_required)}")

if options.solver_type == EmtSolverTypes.Automatic:
    solver = StructuralVectorizedSolver(problem=problem,
                                        t0=0.0,
                                        t_end=options.simulation_time,
                                        h=options.time_step,
                                        method=options.integration_method,
                                        pred_method=DynamicIntegrationMethod.OdeEuler,
                                        dense_threshold=DENSE_THRESHOLD,
                                        verbose=True,
                                        auto_vectorization=False)
elif options.solver_type == EmtSolverTypes.StructuralCompiled:
    solver = StructuralCompiledSolver(problem=problem,
                                      t0=0.0,
                                      t_end=options.simulation_time,
                                      h=options.time_step,
                                      method=options.integration_method,
                                      pred_method=DynamicIntegrationMethod.OdeEuler,
                                      dense_threshold=DENSE_THRESHOLD,
                                      verbose=True)
elif options.solver_type == EmtSolverTypes.Symbolic:
    solver = JitSymbolicSolver(problem=problem,
                               t0=0.0,
                               t_end=options.simulation_time,
                               h=options.time_step,
                               method=options.integration_method,
                               pred_method=DynamicIntegrationMethod.OdeEuler,
                               verbose=True)
elif options.solver_type == EmtSolverTypes.StructuralAD:
    solver = JitAdSolver(problem=problem,
                         t0=0.0,
                         t_end=options.simulation_time,
                         h=options.time_step,
                         method=options.integration_method,
                         pred_method=DynamicIntegrationMethod.OdeEuler,
                         verbose=True)
else:
    raise ValueError(f"Unknown options.solver_type '{options.solver_type}'")
boundary_updater = cast(Any, problem)
t_arr: np.ndarray
y_arr: np.ndarray
dy_arr: np.ndarray
t_arr, y_arr, dy_arr, well_initialized , converged= solver.simulate(boundary_updater=boundary_updater)

print(f"EMT well initialized: {well_initialized}")
print(f"EMT converged: {converged}")
if hasattr(solver, "get_last_runtime_stats"):
    print(solver.get_last_runtime_stats())

print("Time-series diagnostics")
for name in [
    "Pac_bus_G4L_grid_side_converter",
    "Pac_G4L_grid_side_converter",
    "p_dc_G4L_load_side_converter_control",
    "i_dc_G4L_grid_side_converter",
    "i_dc_L_G4L_load_side_converter_control",
    "i_cap_dc_G4L_load_side_converter",
    "v_dc_G4L_load_side_converter",
    "i_q_out_VA_G4L_Virtual_admittance",
    "i_q_lim_G4L_current_limiter",
    "i_q_G4L_clark_park_transforms_qd",
    "err_q_G4L_current_loop",
    "i_d_out_VA_G4L_Virtual_admittance",
    "i_d_lim_G4L_current_limiter",
    "i_d_G4L_clark_park_transforms_qd",
    "err_d_G4L_current_loop",
    "err_q_G4L_Virtual_admittance",
    "err_d_G4L_Virtual_admittance",
    "y1_G4L_Virtual_admittance",
    "y2_G4L_Virtual_admittance",
    "y3_G4L_Virtual_admittance",
    "y4_G4L_Virtual_admittance",
    "y_G4L_PLL",
    "omega_pll_G4L_PLL",
    "w_pll_G4L_PLL",
    "phase_pll_G4L_PLL",
]:
    print_series_summary(problem, y_arr, name)

print("Differential-state diagnostics")
for name in [
    "dy_G4L_PLL",
    "dx_e_pll_G4L_PLL",
    "dx1_1_G4L_Virtual_admittance",
    "dx2_1_G4L_Virtual_admittance",
    "dx1_2_G4L_Virtual_admittance",
    "dx2_2_G4L_Virtual_admittance",
    "d_i_q_bias_state_G4L_Virtual_admittance",
    "d_i_d_bias_state_G4L_Virtual_admittance",
    "dv_ffw_q_G4L_current_loop",
    "dv_ffw_d_G4L_current_loop",
    "dx_e_q_G4L_current_loop",
    "dx_e_d_G4L_current_loop",
    "dx_e_G4L_load_side_converter_control",
    "dq_cap_G4L_load_side_converter",
    "di_ser_A_G4L_grid_side_converter",
    "di_ser_B_G4L_grid_side_converter",
    "di_ser_C_G4L_grid_side_converter",
]:
    print_diff_summary(problem, dy_arr, name)


# Core diagnostics for the GFM-load system.
fig, axes = plt.subplots(5, 2, figsize=(14, 15), sharex=True)
axes = axes.ravel()

# 1) PCC voltages and currents
for name in ["v_A_Bus1_emt_template", "v_B_Bus1_emt_template", "v_C_Bus1_emt_template"]:
    plot_if_available(axes[0], t_arr, try_get_series(problem, y_arr, name), name)
axes[0].set_title("Grid-Side AC Voltages")
axes[0].grid(True)
if axes[0].lines:
    axes[0].legend(loc="best")

for name in ["i_f_A_G4L_grid_side_converter", "i_f_B_G4L_grid_side_converter", "i_f_C_G4L_grid_side_converter"]:
    plot_if_available(axes[1], t_arr, try_get_series(problem, y_arr, name), name)
axes[1].set_title("Grid-Side AC Currents")
axes[1].grid(True)
if axes[1].lines:
    axes[1].legend(loc="best")

# 2) DC-link behavior
for name in ["v_dc_G4L_load_side_converter", "i_dc_G4L_grid_side_converter", "i_dc_L_G4L_load_side_converter_control"]:
    plot_if_available(axes[2], t_arr, try_get_series(problem, y_arr, name), name)
axes[2].set_title("DC-Link Variables")
axes[2].grid(True)
if axes[2].lines:
    axes[2].legend(loc="best")

for name in ["Pac_bus_G4L_grid_side_converter", "Pac_G4L_grid_side_converter", "p_dc_G4L_load_side_converter_control"]:
    plot_if_available(axes[3], t_arr, try_get_series(problem, y_arr, name), name)
axes[3].set_title("Converter Power Variables")
axes[3].grid(True)
if axes[3].lines:
    axes[3].legend(loc="best")

# 3) Synchronization variables
for name in ["phase_pll_G4L_PLL", "theta_pll_G4L_PLL"]:
    plot_if_available(axes[4], t_arr, try_get_series(problem, y_arr, name), name)
axes[4].set_title("PLL / VSM Angles")
axes[4].grid(True)
if axes[4].lines:
    axes[4].legend(loc="best")

for name in ["omega_pll_G4L_PLL", "w_pll_G4L_PLL", "y_G4L_PLL"]:
    plot_if_available(axes[5], t_arr, try_get_series(problem, y_arr, name), name)
axes[5].set_title("PLL / VSM Frequencies")
axes[5].grid(True)
if axes[5].lines:
    axes[5].legend(loc="best")

# 4) Controller internals and branch states
for name in ["i_q_lim_G4L_current_limiter", "i_d_lim_G4L_current_limiter", "v_q_G4L_clark_park_transforms_qd", "v_d_G4L_clark_park_transforms_qd"]:
    plot_if_available(axes[6], t_arr, try_get_series(problem, y_arr, name), name)
axes[6].set_title("Current Limits and dq Voltages")
axes[6].grid(True)
if axes[6].lines:
    axes[6].legend(loc="best")

for name in [
    "v_con_A_G4L_current_loop",
    "v_con_B_G4L_current_loop",
    "v_con_C_G4L_current_loop",
]:
    plot_if_available(axes[7], t_arr, try_get_series(problem, y_arr, name), name)
axes[7].set_title("Converter Command Voltages")
axes[7].grid(True)
if axes[7].lines:
    axes[7].legend(loc="best")

fig2, ax2 = plt.subplots(1, 1, figsize=(10, 4), sharex=True)
for name in ["i_cap_t_A_G4L_transformer", "q_t_A_G4L_transformer", "i_ser_A_G4L_transformer"]:
    plot_if_available(ax2, t_arr, try_get_series(problem, y_arr, name), name)
ax2.set_title("Transformer/Filter Branch A")
ax2.grid(True)
if ax2.lines:
    ax2.legend(loc="best")

fig3, axes3 = plt.subplots(1, 2, figsize=(14, 4), sharex=True)
for name in ["i_f_A_G4L_grid_side_converter", "i_f_B_G4L_grid_side_converter", "i_f_C_G4L_grid_side_converter"]:
    plot_if_available(axes3[0], t_arr, try_get_series(problem, y_arr, name), name)
axes3[0].set_title("Converter-Side abc Currents")
axes3[0].grid(True)
if axes3[0].lines:
    axes3[0].legend(loc="best")

for name in ["i_q_G4L_clark_park_transforms_qd", "i_d_G4L_clark_park_transforms_qd"]:
    plot_if_available(axes3[1], t_arr, try_get_series(problem, y_arr, name), name)
axes3[1].set_title("Converter-Side dq Currents")
axes3[1].grid(True)
if axes3[1].lines:
    axes3[1].legend(loc="best")

fig4, axes4 = plt.subplots(1, 2, figsize=(14, 4), sharex=True)
for name in ["v_con_q_G4L_current_loop", "v_con_d_G4L_current_loop"]:
    plot_if_available(axes4[0], t_arr, try_get_series(problem, y_arr, name), name)
axes4[0].set_title("Current-Loop dq Commands")
axes4[0].grid(True)
if axes4[0].lines:
    axes4[0].legend(loc="best")

for name in ["err_q_G4L_current_loop", "err_d_G4L_current_loop", "y_q_G4L_current_loop", "y_d_G4L_current_loop"]:
    plot_if_available(axes4[1], t_arr, try_get_series(problem, y_arr, name), name)
axes4[1].set_title("Current-Loop PI Internals")
axes4[1].grid(True)
if axes4[1].lines:
    axes4[1].legend(loc="best")

fig5, axes5 = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
for name in [
    "i_q_out_VA_G4L_Virtual_admittance",
    "i_d_out_VA_G4L_Virtual_admittance",
    "i_q_bias_state_G4L_Virtual_admittance",
    "i_d_bias_state_G4L_Virtual_admittance",
]:
    plot_if_available(axes5[0], t_arr, try_get_series(problem, y_arr, name), name)
axes5[0].set_title("Virtual Admittance Currents and Bias States")
axes5[0].grid(True)
if axes5[0].lines:
    axes5[0].legend(loc="best")

for name in ["err_q_G4L_Virtual_admittance", "err_d_G4L_Virtual_admittance"]:
    plot_if_available(axes5[1], t_arr, try_get_series(problem, y_arr, name), name)
axes5[1].set_title("Virtual Admittance Voltage Errors")
axes5[1].grid(True)
if axes5[1].lines:
    axes5[1].legend(loc="best")

for name in [
    "y1_G4L_Virtual_admittance",
    "y2_G4L_Virtual_admittance",
    "y3_G4L_Virtual_admittance",
    "y4_G4L_Virtual_admittance",
]:
    plot_if_available(axes5[2], t_arr, try_get_series(problem, y_arr, name), name)
axes5[2].set_title("Virtual Admittance Internal Outputs")
axes5[2].grid(True)
if axes5[2].lines:
    axes5[2].legend(loc="best")

fig6, axes6 = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
for name in [
    "i_dc_G4L_grid_side_converter",
    "i_dc_L_G4L_load_side_converter_control",
    "i_cap_dc_G4L_load_side_converter",
    "v_dc_G4L_load_side_converter",
]:
    plot_if_available(axes6[0], t_arr, try_get_series(problem, y_arr, name), name)
axes6[0].set_title("DC-Link Current Balance")
axes6[0].grid(True)
if axes6[0].lines:
    axes6[0].legend(loc="best")

for name in ["Pac_bus_G4L_grid_side_converter", "Pac_G4L_grid_side_converter", "p_dc_G4L_load_side_converter_control"]:
    plot_if_available(axes6[1], t_arr, try_get_series(problem, y_arr, name), name)
axes6[1].set_title("AC/DC Power Balance")
axes6[1].grid(True)
if axes6[1].lines:
    axes6[1].legend(loc="best")

fig7, axes7 = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
for name in [
    "i_q_out_VA_G4L_Virtual_admittance",
    "i_q_lim_G4L_current_limiter",
    "i_q_G4L_clark_park_transforms_qd",
    "err_q_G4L_current_loop",
]:
    plot_if_available(axes7[0], t_arr, try_get_series(problem, y_arr, name), name)
axes7[0].set_title("q-Axis Current Reference Chain")
axes7[0].grid(True)
if axes7[0].lines:
    axes7[0].legend(loc="best")

for name in [
    "i_d_out_VA_G4L_Virtual_admittance",
    "i_d_lim_G4L_current_limiter",
    "i_d_G4L_clark_park_transforms_qd",
    "err_d_G4L_current_loop",
]:
    plot_if_available(axes7[1], t_arr, try_get_series(problem, y_arr, name), name)
axes7[1].set_title("d-Axis Current Reference Chain")
axes7[1].grid(True)
if axes7[1].lines:
    axes7[1].legend(loc="best")

fig8, ax8 = plt.subplots(1, 1, figsize=(14, 4), sharex=True)
for name in [
    "Pac_bus_G4L_grid_side_converter",
    "y_G4L_PLL",
    "omega_pll_G4L_PLL",
    "w_pll_G4L_PLL",
]:
    plot_if_available(ax8, t_arr, try_get_series(problem, y_arr, name), name)
ax8.axhline(-0.8, color="k", linestyle="--", linewidth=1.0, label="P_ref = -0.8")
ax8.set_title("PLL / VSM Power and Frequency Diagnostics")
ax8.grid(True)
if ax8.lines:
    ax8.legend(loc="best")

for ax in axes:
    ax.set_xlabel("Time [s]")

ax2.set_xlabel("Time [s]")
for ax in axes3:
    ax.set_xlabel("Time [s]")
for ax in axes4:
    ax.set_xlabel("Time [s]")
for ax in axes5:
    ax.set_xlabel("Time [s]")
for ax in axes6:
    ax.set_xlabel("Time [s]")
for ax in axes7:
    ax.set_xlabel("Time [s]")
ax8.set_xlabel("Time [s]")

fig.tight_layout()
fig2.tight_layout()
fig3.tight_layout()
fig4.tight_layout()
fig5.tight_layout()
fig6.tight_layout()
fig7.tight_layout()
fig8.tight_layout()
plt.show()
