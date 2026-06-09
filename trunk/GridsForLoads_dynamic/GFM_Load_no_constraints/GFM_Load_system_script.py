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

from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.emt_event import EmtEvent





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


def scale_series(series, factor):
    if series is None:
        return None
    return series * factor


def negate_scale_series(series, factor):
    if series is None:
        return None
    return -series * factor


def constant_series(value, t_arr):
    return np.full_like(t_arr, fill_value=value, dtype=float)


def plot_scaled_if_available(ax, t_arr: np.ndarray, problem: EmtProblemDae, y_arr: np.ndarray,
                             name: str, factor: float, label: str, negate: bool = False):
    series = try_get_series(problem, y_arr, name)
    if series is None:
        print(f"variable:{name} is not in results")
        return False

    scaled = negate_scale_series(series, factor) if negate else scale_series(series, factor)
    ax.plot(t_arr, scaled, label=label)
    return True


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
# EVENT
######################################################################################################
P_ref = find_name_in_block('P_ref_G4L_PLL', load_mdl)
events_group = EmtEventsGroup(name="simulation1")
grid.add_emt_events_group(events_group)
event_Pref = EmtEvent(device=load, parameter=P_ref, time=1, value=-0.4, group=events_group)
grid.add_emt_event(event_Pref)
emt_events_group_names = np.array(0)
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
                     simulation_time =  2, # s
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


# Compact diagnostics focused on virtual admittance tuning.
fig_overview, axes_overview = plt.subplots(3, 2, figsize=(14, 11), sharex=True)
axes_overview = axes_overview.ravel()

for name in ["v_A_Bus1_emt_template", "v_B_Bus1_emt_template", "v_C_Bus1_emt_template"]:
    plot_if_available(axes_overview[0], t_arr, try_get_series(problem, y_arr, name), name)
axes_overview[0].set_title("Grid-Side AC Voltages")
axes_overview[0].grid(True)
if axes_overview[0].lines:
    axes_overview[0].legend(loc="best")

for name in ["i_f_A_G4L_grid_side_converter", "i_f_B_G4L_grid_side_converter", "i_f_C_G4L_grid_side_converter"]:
    plot_if_available(axes_overview[1], t_arr, try_get_series(problem, y_arr, name), name)
axes_overview[1].set_title("Grid-Side AC Currents")
axes_overview[1].grid(True)
if axes_overview[1].lines:
    axes_overview[1].legend(loc="best")

for name in ["v_dc_G4L_load_side_converter", "i_dc_G4L_grid_side_converter", "i_dc_L_G4L_load_side_converter_control"]:
    plot_if_available(axes_overview[2], t_arr, try_get_series(problem, y_arr, name), name)
axes_overview[2].set_title("DC-Link Variables")
axes_overview[2].grid(True)
if axes_overview[2].lines:
    axes_overview[2].legend(loc="best")

for name in ["Pac_bus_G4L_grid_side_converter", "Pac_G4L_grid_side_converter", "p_dc_G4L_load_side_converter_control"]:
    plot_if_available(axes_overview[3], t_arr, try_get_series(problem, y_arr, name), name)
axes_overview[3].set_title("Power Variables")
axes_overview[3].grid(True)
if axes_overview[3].lines:
    axes_overview[3].legend(loc="best")

for name in ["omega_pll_G4L_PLL", "w_pll_G4L_PLL", "y_G4L_PLL"]:
    plot_if_available(axes_overview[4], t_arr, try_get_series(problem, y_arr, name), name)
axes_overview[4].set_title("PLL / VSM Frequencies")
axes_overview[4].grid(True)
if axes_overview[4].lines:
    axes_overview[4].legend(loc="best")

for name in ["v_con_q_G4L_current_loop", "v_con_d_G4L_current_loop"]:
    plot_if_available(axes_overview[5], t_arr, try_get_series(problem, y_arr, name), name)
axes_overview[5].set_title("Current-Loop dq Commands")
axes_overview[5].grid(True)
if axes_overview[5].lines:
    axes_overview[5].legend(loc="best")

fig_va, axes_va = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
for name in [
    "i_q_out_VA_G4L_Virtual_admittance",
    "i_d_out_VA_G4L_Virtual_admittance",
    "i_q_bias_state_G4L_Virtual_admittance",
    "i_d_bias_state_G4L_Virtual_admittance",
]:
    plot_if_available(axes_va[0], t_arr, try_get_series(problem, y_arr, name), name)
axes_va[0].set_title("Virtual Admittance Outputs and Bias States")
axes_va[0].grid(True)
if axes_va[0].lines:
    axes_va[0].legend(loc="best")

for name in ["err_q_G4L_Virtual_admittance", "err_d_G4L_Virtual_admittance"]:
    plot_if_available(axes_va[1], t_arr, try_get_series(problem, y_arr, name), name)
axes_va[1].set_title("Virtual Admittance Errors")
axes_va[1].grid(True)
if axes_va[1].lines:
    axes_va[1].legend(loc="best")

for name in [
    "y1_G4L_Virtual_admittance",
    "y2_G4L_Virtual_admittance",
    "y3_G4L_Virtual_admittance",
    "y4_G4L_Virtual_admittance",
]:
    plot_if_available(axes_va[2], t_arr, try_get_series(problem, y_arr, name), name)
axes_va[2].set_title("Virtual Admittance Internal Outputs y1-y4")
axes_va[2].grid(True)
if axes_va[2].lines:
    axes_va[2].legend(loc="best")

fig_currents, axes_currents = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
for name in [
    "i_q_out_VA_G4L_Virtual_admittance",
    "i_q_lim_G4L_current_limiter",
    "i_q_G4L_clark_park_transforms_qd",
    "err_q_G4L_current_loop",
]:
    plot_if_available(axes_currents[0], t_arr, try_get_series(problem, y_arr, name), name)
axes_currents[0].set_title("q-Axis Comparison")
axes_currents[0].grid(True)
if axes_currents[0].lines:
    axes_currents[0].legend(loc="best")

for name in [
    "i_d_out_VA_G4L_Virtual_admittance",
    "i_d_lim_G4L_current_limiter",
    "i_d_G4L_clark_park_transforms_qd",
    "err_d_G4L_current_loop",
]:
    plot_if_available(axes_currents[1], t_arr, try_get_series(problem, y_arr, name), name)
axes_currents[1].set_title("d-Axis Comparison")
axes_currents[1].grid(True)
if axes_currents[1].lines:
    axes_currents[1].legend(loc="best")

for ax in axes_overview:
    ax.set_xlabel("Time [s]")
for ax in axes_va:
    ax.set_xlabel("Time [s]")
for ax in axes_currents:
    ax.set_xlabel("Time [s]")

fig_overview.tight_layout()
fig_va.tight_layout()
fig_currents.tight_layout()

U_LL = 33000.0
Sb_va = 2_000_000.0
Vdc_ref = 1200.0
V_phase_rms_base = U_LL / np.sqrt(3.0)
Vac_phase_peak = U_LL * np.sqrt(2.0 / 3.0)
Ibase_vg = Sb_va / V_phase_rms_base
Ipeak_sim = (Sb_va / U_LL) * np.sqrt(2.0 / 3.0)
Idc_base = Sb_va / Vdc_ref
Imax_sim_A = 1.1 * Ipeak_sim

print("SI comparison base values")
print(f"  V_phase_rms_base = {V_phase_rms_base}")
print(f"  Vac_phase_peak = {Vac_phase_peak}")
print(f"  Ibase_vg = {Ibase_vg}")
print(f"  Ipeak_sim = {Ipeak_sim}")
print(f"  Idc_base = {Idc_base}")
print(f"  Ibase_vg / Ipeak_sim = {Ibase_vg / Ipeak_sim}")

missing_si_variables: set[str] = set()


def plot_scaled_with_tracking(ax, t_arr: np.ndarray, problem: EmtProblemDae, y_arr: np.ndarray,
                              name: str, factor: float, label: str, negate: bool = False,
                              linestyle: str = "-"):
    before_count = len(ax.lines)
    plotted = plot_scaled_if_available(ax, t_arr, problem, y_arr, name, factor, label, negate=negate)
    if not plotted:
        missing_si_variables.add(name)
        return False
    if len(ax.lines) > before_count:
        ax.lines[-1].set_linestyle(linestyle)
    return True


def add_constant_line(ax, t_arr: np.ndarray, value: float, label: str, linestyle: str = "--"):
    ax.plot(t_arr, constant_series(value, t_arr), linestyle=linestyle, label=label)


# If the VA model is changed to normalized voltage form, update these reference lines accordingly.
v_q_ref_SI = np.sqrt(2.0) * V_phase_rms_base
v_d_ref_SI = 0.0

# If VA is changed to normalized voltage form err = 1 - v/sqrt(2), use Vac_phase_peak instead.

fig_si_overview, axes_si_overview = plt.subplots(3, 2, figsize=(16, 12), sharex=True)
axes_si_overview = axes_si_overview.ravel()

plot_scaled_with_tracking(axes_si_overview[0], t_arr, problem, y_arr, "v_A_Bus1_emt_template",
                          V_phase_rms_base / 1000.0, "v_A_Bus1 [kV]")
plot_scaled_with_tracking(axes_si_overview[0], t_arr, problem, y_arr, "v_B_Bus1_emt_template",
                          V_phase_rms_base / 1000.0, "v_B_Bus1 [kV]")
plot_scaled_with_tracking(axes_si_overview[0], t_arr, problem, y_arr, "v_C_Bus1_emt_template",
                          V_phase_rms_base / 1000.0, "v_C_Bus1 [kV]")
axes_si_overview[0].set_title("Grid-Side AC Voltages [kV phase-to-neutral instantaneous]")
axes_si_overview[0].set_ylabel("Voltage [kV]")
axes_si_overview[0].grid(True)
if axes_si_overview[0].lines:
    axes_si_overview[0].legend(loc="best")

plot_scaled_with_tracking(axes_si_overview[1], t_arr, problem, y_arr, "i_f_A_G4L_grid_side_converter",
                          Ibase_vg, "i_f_A [A] sim sign", negate=True)
plot_scaled_with_tracking(axes_si_overview[1], t_arr, problem, y_arr, "i_f_B_G4L_grid_side_converter",
                          Ibase_vg, "i_f_B [A] sim sign", negate=True)
plot_scaled_with_tracking(axes_si_overview[1], t_arr, problem, y_arr, "i_f_C_G4L_grid_side_converter",
                          Ibase_vg, "i_f_C [A] sim sign", negate=True)
axes_si_overview[1].set_title("Grid-Side AC Currents [A] - Simulink/load sign")
axes_si_overview[1].set_ylabel("Current [A]")
axes_si_overview[1].grid(True)
if axes_si_overview[1].lines:
    axes_si_overview[1].legend(loc="best")

plot_scaled_with_tracking(axes_si_overview[2], t_arr, problem, y_arr, "v_q_G4L_clark_park_transforms_qd",
                          V_phase_rms_base, "v_q [V]")
plot_scaled_with_tracking(axes_si_overview[2], t_arr, problem, y_arr, "v_d_G4L_clark_park_transforms_qd",
                          V_phase_rms_base, "v_d [V]")
add_constant_line(axes_si_overview[2], t_arr, v_q_ref_SI, "Vq_ref [V]", linestyle="--")
add_constant_line(axes_si_overview[2], t_arr, v_d_ref_SI, "Vd_ref [V]", linestyle=":")
axes_si_overview[2].set_title("VA/Input dq Voltages [V]")
axes_si_overview[2].set_ylabel("Voltage [V]")
axes_si_overview[2].grid(True)
if axes_si_overview[2].lines:
    axes_si_overview[2].legend(loc="best")

plot_scaled_with_tracking(axes_si_overview[3], t_arr, problem, y_arr, "i_q_out_VA_G4L_Virtual_admittance",
                          Ibase_vg, "i_q_out_VA [A]", negate=True, linestyle="-")
plot_scaled_with_tracking(axes_si_overview[3], t_arr, problem, y_arr, "i_q_lim_G4L_current_limiter",
                          Ibase_vg, "i_q_lim [A]", negate=True, linestyle="-")
plot_scaled_with_tracking(axes_si_overview[3], t_arr, problem, y_arr, "i_q_G4L_clark_park_transforms_qd",
                          Ibase_vg, "i_q_meas [A]", negate=True, linestyle="-")
plot_scaled_with_tracking(axes_si_overview[3], t_arr, problem, y_arr, "i_d_out_VA_G4L_Virtual_admittance",
                          Ibase_vg, "i_d_out_VA [A]", negate=True, linestyle="--")
plot_scaled_with_tracking(axes_si_overview[3], t_arr, problem, y_arr, "i_d_lim_G4L_current_limiter",
                          Ibase_vg, "i_d_lim [A]", negate=True, linestyle="--")
plot_scaled_with_tracking(axes_si_overview[3], t_arr, problem, y_arr, "i_d_G4L_clark_park_transforms_qd",
                          Ibase_vg, "i_d_meas [A]", negate=True, linestyle="--")
axes_si_overview[3].set_title("dq Currents [A] - Simulink/load sign")
axes_si_overview[3].set_ylabel("Current [A]")
axes_si_overview[3].grid(True)
if axes_si_overview[3].lines:
    axes_si_overview[3].legend(loc="best")

plot_scaled_with_tracking(axes_si_overview[4], t_arr, problem, y_arr, "Pac_bus_G4L_grid_side_converter",
                          Sb_va / 1e6, "Pac_bus [MW]", negate=True)
plot_scaled_with_tracking(axes_si_overview[4], t_arr, problem, y_arr, "Pac_G4L_grid_side_converter",
                          Sb_va / 1e6, "Pac [MW]", negate=True)
plot_scaled_with_tracking(axes_si_overview[4], t_arr, problem, y_arr, "p_dc_G4L_load_side_converter_control",
                          Sb_va / 1e6, "p_dc [MW]", negate=True)
pref_series_mw = np.where(t_arr < 1.0, 0.8 * Sb_va / 1e6, 0.4 * Sb_va / 1e6)
axes_si_overview[4].plot(t_arr, pref_series_mw, linestyle="--", label="P_ref [MW]")
axes_si_overview[4].set_title("Active Powers [MW] - Simulink/load sign")
axes_si_overview[4].set_ylabel("Power [MW]")
axes_si_overview[4].grid(True)
if axes_si_overview[4].lines:
    axes_si_overview[4].legend(loc="best")

ax_dc_v = axes_si_overview[5]
ax_dc_i = ax_dc_v.twinx()
plot_scaled_with_tracking(ax_dc_v, t_arr, problem, y_arr, "v_dc_G4L_load_side_converter",
                          Vdc_ref, "v_dc [V]")
plot_scaled_with_tracking(ax_dc_i, t_arr, problem, y_arr, "i_dc_G4L_grid_side_converter",
                          Idc_base, "i_dc [A]")
plot_scaled_with_tracking(ax_dc_i, t_arr, problem, y_arr, "i_dc_L_G4L_load_side_converter_control",
                          Idc_base, "i_dc_L [A]")
plot_scaled_with_tracking(ax_dc_i, t_arr, problem, y_arr, "i_cap_dc_G4L_load_side_converter",
                          Idc_base, "i_cap_dc [A]")
ax_dc_v.set_title("DC-Link Variables [V, A]")
ax_dc_v.set_ylabel("Voltage [V]")
ax_dc_i.set_ylabel("Current [A]")
ax_dc_v.grid(True)
dc_lines = ax_dc_v.lines + ax_dc_i.lines
if dc_lines:
    dc_labels = [line.get_label() for line in dc_lines]
    ax_dc_v.legend(dc_lines, dc_labels, loc="best")

fig_si_va, axes_si_va = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
plot_scaled_with_tracking(axes_si_va[0], t_arr, problem, y_arr, "i_q_out_VA_G4L_Virtual_admittance",
                          Ibase_vg, "i_q_out_VA [A]", negate=True)
plot_scaled_with_tracking(axes_si_va[0], t_arr, problem, y_arr, "i_d_out_VA_G4L_Virtual_admittance",
                          Ibase_vg, "i_d_out_VA [A]", negate=True, linestyle="--")
axes_si_va[0].set_title("VA Output Currents [A] - Simulink/load sign")
axes_si_va[0].set_ylabel("Current [A]")
axes_si_va[0].grid(True)
if axes_si_va[0].lines:
    axes_si_va[0].legend(loc="best")

plot_scaled_with_tracking(axes_si_va[1], t_arr, problem, y_arr, "err_q_G4L_Virtual_admittance",
                          V_phase_rms_base, "err_q [V]")
plot_scaled_with_tracking(axes_si_va[1], t_arr, problem, y_arr, "err_d_G4L_Virtual_admittance",
                          V_phase_rms_base, "err_d [V]", linestyle="--")
axes_si_va[1].set_title("VA Voltage Errors [V]")
axes_si_va[1].set_ylabel("Error [V]")
axes_si_va[1].grid(True)
if axes_si_va[1].lines:
    axes_si_va[1].legend(loc="best")

plot_scaled_with_tracking(axes_si_va[2], t_arr, problem, y_arr, "y1_G4L_Virtual_admittance",
                          Ibase_vg, "y1 [A] sim sign", negate=True)
plot_scaled_with_tracking(axes_si_va[2], t_arr, problem, y_arr, "y2_G4L_Virtual_admittance",
                          Ibase_vg, "y2 [A] sim sign", negate=True)
plot_scaled_with_tracking(axes_si_va[2], t_arr, problem, y_arr, "y3_G4L_Virtual_admittance",
                          Ibase_vg, "y3 [A] sim sign", negate=True, linestyle="--")
plot_scaled_with_tracking(axes_si_va[2], t_arr, problem, y_arr, "y4_G4L_Virtual_admittance",
                          Ibase_vg, "y4 [A] sim sign", negate=True, linestyle="--")
axes_si_va[2].set_title("VA Internal Outputs y1-y4 [A] - Simulink/load sign")
axes_si_va[2].set_ylabel("Output [A]")
axes_si_va[2].grid(True)
if axes_si_va[2].lines:
    axes_si_va[2].legend(loc="best")

fig_si_currents, axes_si_currents = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
plot_scaled_with_tracking(axes_si_currents[0], t_arr, problem, y_arr, "i_q_out_VA_G4L_Virtual_admittance",
                          Ibase_vg, "i_q_out_VA [A]", negate=True)
plot_scaled_with_tracking(axes_si_currents[0], t_arr, problem, y_arr, "i_q_lim_G4L_current_limiter",
                          Ibase_vg, "i_q_lim [A]", negate=True)
plot_scaled_with_tracking(axes_si_currents[0], t_arr, problem, y_arr, "i_q_G4L_clark_park_transforms_qd",
                          Ibase_vg, "i_q_meas [A]", negate=True)
add_constant_line(axes_si_currents[0], t_arr, Imax_sim_A, "+Imax_sim_A", linestyle="--")
add_constant_line(axes_si_currents[0], t_arr, -Imax_sim_A, "-Imax_sim_A", linestyle=":")
axes_si_currents[0].set_title("q-Axis Current Chain [A]")
axes_si_currents[0].set_ylabel("Current [A]")
axes_si_currents[0].grid(True)
if axes_si_currents[0].lines:
    axes_si_currents[0].legend(loc="best")

plot_scaled_with_tracking(axes_si_currents[1], t_arr, problem, y_arr, "i_d_out_VA_G4L_Virtual_admittance",
                          Ibase_vg, "i_d_out_VA [A]", negate=True)
plot_scaled_with_tracking(axes_si_currents[1], t_arr, problem, y_arr, "i_d_lim_G4L_current_limiter",
                          Ibase_vg, "i_d_lim [A]", negate=True)
plot_scaled_with_tracking(axes_si_currents[1], t_arr, problem, y_arr, "i_d_G4L_clark_park_transforms_qd",
                          Ibase_vg, "i_d_meas [A]", negate=True)
add_constant_line(axes_si_currents[1], t_arr, Imax_sim_A, "+Imax_sim_A", linestyle="--")
add_constant_line(axes_si_currents[1], t_arr, -Imax_sim_A, "-Imax_sim_A", linestyle=":")
axes_si_currents[1].set_title("d-Axis Current Chain [A]")
axes_si_currents[1].set_ylabel("Current [A]")
axes_si_currents[1].grid(True)
if axes_si_currents[1].lines:
    axes_si_currents[1].legend(loc="best")

fig_si_pll, axes_si_pll = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
plot_scaled_with_tracking(axes_si_pll[0], t_arr, problem, y_arr, "Pac_bus_G4L_grid_side_converter",
                          Sb_va / 1e6, "Pac_bus [MW]", negate=True)
axes_si_pll[0].plot(t_arr, pref_series_mw, linestyle="--", label="P_ref event [MW] @ t=1 s")
axes_si_pll[0].set_title("PCC Power vs Reference [MW] - Simulink/load sign")
axes_si_pll[0].set_ylabel("Power [MW]")
axes_si_pll[0].grid(True)
if axes_si_pll[0].lines:
    axes_si_pll[0].legend(loc="best")

plot_scaled_with_tracking(axes_si_pll[1], t_arr, problem, y_arr, "omega_pll_G4L_PLL",
                          1.0, "omega_pll [rad/s]")
plot_scaled_with_tracking(axes_si_pll[1], t_arr, problem, y_arr, "w_pll_G4L_PLL",
                          1.0, "w_pll [rad/s]", linestyle="--")
axes_si_pll[1].set_title("PLL/VSM Frequencies [rad/s, Hz]")
axes_si_pll[1].set_ylabel("Angular frequency [rad/s]")
axes_si_pll[1].grid(True)
if axes_si_pll[1].lines:
    axes_si_pll[1].legend(loc="best")

omega_pll_series = try_get_series(problem, y_arr, "omega_pll_G4L_PLL")
w_pll_series = try_get_series(problem, y_arr, "w_pll_G4L_PLL")
if omega_pll_series is not None or w_pll_series is not None:
    ax_freq_hz = axes_si_pll[1].twinx()
    if omega_pll_series is not None:
        ax_freq_hz.plot(t_arr, omega_pll_series / (2.0 * np.pi), color=axes_si_pll[1].lines[0].get_color(),
                        alpha=0.35, linestyle=":", label="omega_pll [Hz]")
    if w_pll_series is not None:
        color_idx = 1 if omega_pll_series is not None and len(axes_si_pll[1].lines) > 1 else 0
        ax_freq_hz.plot(t_arr, w_pll_series / (2.0 * np.pi),
                        color=axes_si_pll[1].lines[color_idx].get_color(), alpha=0.35, linestyle="-.",
                        label="w_pll [Hz]")
    ax_freq_hz.set_ylabel("Frequency [Hz]")
    pll_lines = axes_si_pll[1].lines + ax_freq_hz.lines
    pll_labels = [line.get_label() for line in pll_lines]
    axes_si_pll[1].legend(pll_lines, pll_labels, loc="best")

for ax in axes_si_overview[:5]:
    ax.set_xlabel("Time [s]")
ax_dc_v.set_xlabel("Time [s]")
for ax in axes_si_va:
    ax.set_xlabel("Time [s]")
for ax in axes_si_currents:
    ax.set_xlabel("Time [s]")
for ax in axes_si_pll:
    ax.set_xlabel("Time [s]")

# csv_path = os.path.join(os.path.dirname(__file__), "veragrid_si_comparison_timeseries.csv")
# csv_columns = {"time_s": t_arr}
#
#
# def add_csv_series(column_name: str, source_name: str, factor: float, negate: bool = False):
#     series = try_get_series(problem, y_arr, source_name)
#     if series is None:
#         missing_si_variables.add(source_name)
#         return
#     csv_columns[column_name] = negate_scale_series(series, factor) if negate else scale_series(series, factor)
#
#
# add_csv_series("vA_Bus1_kV", "v_A_Bus1_emt_template", V_phase_rms_base / 1000.0)
# add_csv_series("vB_Bus1_kV", "v_B_Bus1_emt_template", V_phase_rms_base / 1000.0)
# add_csv_series("vC_Bus1_kV", "v_C_Bus1_emt_template", V_phase_rms_base / 1000.0)
# add_csv_series("iA_grid_A_sim_sign", "i_f_A_G4L_grid_side_converter", Ibase_vg, negate=True)
# add_csv_series("iB_grid_A_sim_sign", "i_f_B_G4L_grid_side_converter", Ibase_vg, negate=True)
# add_csv_series("iC_grid_A_sim_sign", "i_f_C_G4L_grid_side_converter", Ibase_vg, negate=True)
# add_csv_series("vq_V", "v_q_G4L_clark_park_transforms_qd", V_phase_rms_base)
# add_csv_series("vd_V", "v_d_G4L_clark_park_transforms_qd", V_phase_rms_base)
# add_csv_series("iq_va_A_sim_sign", "i_q_out_VA_G4L_Virtual_admittance", Ibase_vg, negate=True)
# add_csv_series("id_va_A_sim_sign", "i_d_out_VA_G4L_Virtual_admittance", Ibase_vg, negate=True)
# add_csv_series("iq_lim_A_sim_sign", "i_q_lim_G4L_current_limiter", Ibase_vg, negate=True)
# add_csv_series("id_lim_A_sim_sign", "i_d_lim_G4L_current_limiter", Ibase_vg, negate=True)
# add_csv_series("iq_meas_A_sim_sign", "i_q_G4L_clark_park_transforms_qd", Ibase_vg, negate=True)
# add_csv_series("id_meas_A_sim_sign", "i_d_G4L_clark_park_transforms_qd", Ibase_vg, negate=True)
# add_csv_series("Pac_bus_MW_sim_sign", "Pac_bus_G4L_grid_side_converter", Sb_va / 1e6, negate=True)
# add_csv_series("Pac_MW_sim_sign", "Pac_G4L_grid_side_converter", Sb_va / 1e6, negate=True)
# add_csv_series("pdc_MW_sim_sign", "p_dc_G4L_load_side_converter_control", Sb_va / 1e6, negate=True)
# add_csv_series("vdc_V", "v_dc_G4L_load_side_converter", Vdc_ref)
# add_csv_series("idc_A", "i_dc_G4L_grid_side_converter", Idc_base)
# add_csv_series("idcL_A", "i_dc_L_G4L_load_side_converter_control", Idc_base)
# add_csv_series("icapdc_A", "i_cap_dc_G4L_load_side_converter", Idc_base)
#
# with open(csv_path, "w", newline="") as csv_file:
#     writer = csv.writer(csv_file)
#     headers = list(csv_columns.keys())
#     writer.writerow(headers)
#     for idx in range(len(t_arr)):
#         writer.writerow([csv_columns[col][idx] for col in headers])

# print(f"SI comparison CSV exported to: {csv_path}")
print("SI comparison missing variables:", sorted(missing_si_variables) if missing_si_variables else "none")

fig_si_overview.tight_layout()
fig_si_va.tight_layout()
fig_si_currents.tight_layout()
fig_si_pll.tight_layout()
plt.show()
