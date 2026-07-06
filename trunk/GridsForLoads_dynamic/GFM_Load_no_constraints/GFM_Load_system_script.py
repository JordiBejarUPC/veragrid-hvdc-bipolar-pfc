# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import matplotlib.pyplot as plt
import csv
from pathlib import Path


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
                                         DynamicEventTransitionType, EmtSolverTypes, ShuntConnectionType, SolverType)
from trunk.GridsForLoads_dynamic.gridsforloads_converter_template import (get_trafo_grid_connection_G4L,
                                                                          get_complete_load_template_G4L)
# from trunk.GridsForLoads_dynamic.gridsforloads_converter_template_V2 import (get_trafo_grid_connection_G4L,
#                                                                           get_complete_load_template_G4L)
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


def get_scaled_series(problem: EmtProblemDae, y_arr: np.ndarray, name: str, factor: float, negate: bool = False):
    series = try_get_series(problem, y_arr, name)
    if series is None:
        return None
    return negate_scale_series(series, factor) if negate else scale_series(series, factor)


def plot_horizontal(ax, value: float, label: str, linestyle: str = "--"):
    ax.axhline(value, linestyle=linestyle, label=label)


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


def sanitize_file_name(name: str) -> str:
    sanitized = []
    for char in name:
        if char.isalnum() or char in ("-", "_"):
            sanitized.append(char)
        else:
            sanitized.append("_")
    return "".join(sanitized).strip("_") or "plot"


def get_plot_output_folder(selected_test_name: str) -> Path:
    base_folder = Path(REPO_ROOT) / "trunk" / "GridsForLoads_dynamic" / "generated_plots"
    return base_folder / f"GFM_Load_no_constraints_{sanitize_file_name(selected_test_name)}"


def save_selected_figures(output_folder: Path, figures: list[tuple[str, plt.Figure]]) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)
    for stem, figure in figures:
        figure_path = output_folder / f"{sanitize_file_name(stem)}.png"
        figure.savefig(figure_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot: {figure_path}")


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
TEST_NONE = "none"
TEST_P_GFM = "p_gfm"
TEST_ROCOF = "rocof"
TEST_PHASE_JUMP = "phase_jump"
TEST_VAC_STEP = "vac_step"
TEST_VQ_STEP = "vq_step"
TEST_VD_STEP = "vd_step"

TEST_CSV_SUFFIX = {
    TEST_NONE: "none",
    TEST_P_GFM: "p_gfm",
    TEST_ROCOF: "rocof",
    TEST_PHASE_JUMP: "phase_jump",
    TEST_VAC_STEP: "vac_step",
    TEST_VQ_STEP: "vq_step",
    TEST_VD_STEP: "vd_step",
}

VALID_TESTS = {
    TEST_NONE,
    TEST_P_GFM,
    TEST_ROCOF,
    TEST_PHASE_JUMP,
    TEST_VAC_STEP,
    TEST_VQ_STEP,
    TEST_VD_STEP,
}

# Select a single EMT test here.
selected_test = TEST_P_GFM
# selected_test = TEST_ROCOF
# selected_test = TEST_PHASE_JUMP
# selected_test = TEST_VAC_STEP
# selected_test = TEST_VQ_STEP
# selected_test = TEST_VD_STEP
# selected_test = TEST_NONE

if selected_test not in VALID_TESTS:
    valid_tests_list = ", ".join(sorted(VALID_TESTS))
    raise ValueError(f"Unknown selected_test '{selected_test}'. Valid options: {valid_tests_list}")

print(f"Selected EMT test: {selected_test}")

## Active power reference change (GFM controller)
t_P_GFM = 1.0
d_P_GFM = -0.4

## Deviation of frequency with a Rate-of-Change-of-Frequency (ROCOF)
# The Thevenin source frequency event is applied as an absolute scale target,
# with a ramp from t_omega to t_omega_end.
t_omega = 1.0
t_omega_end = 2.0
rocof_omega = -1 * np.pi * 2

## Phase jump disturbance
# Phase offset applied directly in radians to the Thevenin source.
t_phase = 1.0
d_phase = -10 * np.pi / 180

## Grid voltage magnitude variation
# Simulink applies the grid-voltage magnitude disturbance in volts at the
# source amplitude input. This value is the voltage deviation equivalent to
# -0.01 pu on the phase-peak base used by the EMT source.
t_Vac = 1.0
d_Vac = -269.4438717061496

## AC voltage reference change (q-axis)
# Simulink defines the VA q-axis reference offset and step in volts. The event
# target in VeraGrid is the final absolute p.u. reference, built from the
# initial reference plus this deviation.
t_Vq = 1.0
d_Vq0 = 0.0
d_Vq = -269.4438717061496

## AC voltage reference change (d-axis)
# Simulink defines the VA d-axis reference step in volts. The event target in
# VeraGrid is the final absolute p.u. reference, built from the initial
# reference plus this deviation.
t_Vd = 1.0
d_Vd = -269.4438717061496

# Simulink applies these voltage disturbances in volts. Convert them to the EMT
# internal p.u. voltage base used by the Thevenin source and virtual admittance
# before creating events. VeraGrid event values are absolute targets, not
# increments, so each target is built from the initial value plus the deviation.
VLL_RMS_BASE_V = 33000.0
V_PHASE_PEAK_BASE_V = np.sqrt(2.0 / 3.0) * VLL_RMS_BASE_V
V_Q_REF0_PU = np.sqrt(2.0) + d_Vq0 / V_PHASE_PEAK_BASE_V
V_D_REF0_PU = 0.0
VAC_SCALE0_PU = 1.0
DELTA_VAC_PU = d_Vac / V_PHASE_PEAK_BASE_V
DELTA_VQ_PU = d_Vq / V_PHASE_PEAK_BASE_V
DELTA_VD_PU = d_Vd / V_PHASE_PEAK_BASE_V

events_group = EmtEventsGroup(name="simulation1")
grid.add_emt_events_group(events_group)

P_ref = find_name_in_block('P_ref_G4L_PLL', load_mdl)
omega_ref_scale = find_name_in_block('f_scale_emt_thevenin_eq_generator_template', gen_mdl)
phase_jump_param = find_name_in_block('theta_deviation_param_emt_thevenin_eq_generator_template', gen_mdl)
voltage_scale_param = find_name_in_block('E_scale_emt_thevenin_eq_generator_template', gen_mdl)
v_q_ref = find_name_in_block('v_q_ref_G4L_Virtual_admittance', load_mdl)
v_d_ref = find_name_in_block('v_d_ref_G4L_Virtual_admittance', load_mdl)

events_to_add: list[EmtEvent] = []

if selected_test == TEST_NONE:
    pass
elif selected_test == TEST_P_GFM:
    events_to_add = [
        EmtEvent(device=load, parameter=P_ref, time=t_P_GFM, value=d_P_GFM, group=events_group),
    ]
elif selected_test == TEST_ROCOF:
    if t_omega_end <= t_omega:
        raise ValueError("t_omega_end must be greater than t_omega for the ROCOF test")

    omega_end = omega + rocof_omega * (t_omega_end - t_omega)
    omega_scale_after_ramp = omega_end / omega
    events_to_add = [
        EmtEvent(
            device=gen0,
            parameter=omega_ref_scale,
            time=t_omega,
            end_time=t_omega_end,
            value=omega_scale_after_ramp,
            group=events_group,
            transition_type=DynamicEventTransitionType.Ramp,
        ),
    ]
elif selected_test == TEST_PHASE_JUMP:
    events_to_add = [
        EmtEvent(device=gen0, parameter=phase_jump_param, time=t_phase, value=d_phase, group=events_group),
    ]
elif selected_test == TEST_VAC_STEP:
    voltage_scale_fault = VAC_SCALE0_PU + DELTA_VAC_PU
    events_to_add = [
        EmtEvent(device=gen0, parameter=voltage_scale_param, time=t_Vac, value=voltage_scale_fault, group=events_group),
    ]

elif selected_test == TEST_VQ_STEP:
    events_to_add = [
        EmtEvent(device=load, parameter=v_q_ref, time=t_Vq, value=V_Q_REF0_PU + DELTA_VQ_PU, group=events_group),
    ]
elif selected_test == TEST_VD_STEP:
    events_to_add = [
        EmtEvent(device=load, parameter=v_d_ref, time=t_Vd, value=V_D_REF0_PU + DELTA_VD_PU, group=events_group),
    ]
else:
    raise ValueError(f"Unknown selected_test: {selected_test}")

for event in events_to_add:
    grid.add_emt_event(event)

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
                     solver_type = EmtSolverTypes.Automatic,
                     # initialization_method = EmtInitializationMethod.PseudoTransient,
                     initialization_method = EmtInitializationMethod.Explicit,
                     integration_method = DynamicIntegrationMethod.DaeBackEuler,
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


def wrap_to_pi(angle: np.ndarray | float) -> np.ndarray | float:
    """Wrap angles to ``[-pi, pi]``.

    :param angle: Input angle or angle series in radians.
    :return: Wrapped angle with the same shape.
    """
    return np.arctan2(np.sin(angle), np.cos(angle))

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
    "theta_pll_G4L_PLL",
    "phase_pll_G4L_PLL",
]

init_diagnostics: dict[str, float | None] = {}
print("Initial scalar diagnostics")
for name in init_diagnostic_names:
    value = try_get_init_value(problem, name)
    init_diagnostics[name] = value
    print(f"  {name} = {value}")

theta_pll_init = init_diagnostics.get("theta_pll_G4L_PLL")
phase_pll_init = init_diagnostics.get("phase_pll_G4L_PLL")
if theta_pll_init is not None and phase_pll_init is not None:
    delta_vsm_init = float(wrap_to_pi(float(phase_pll_init) - float(theta_pll_init)))
    init_diagnostics["delta_vsm_init"] = delta_vsm_init
    print(f"  delta_vsm_init = {delta_vsm_init}")

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
print(f"  Imax_sim_A = {Imax_sim_A}")
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


def step_series(t_arr: np.ndarray, time: float, before_value: float, after_value: float):
    return np.where(t_arr < time, before_value, after_value)


def ramp_series(t_arr: np.ndarray, start_time: float, end_time: float, start_value: float, end_value: float):
    if end_time <= start_time:
        return constant_series(start_value, t_arr)

    result = np.full_like(t_arr, fill_value=start_value, dtype=float)
    ramp_mask = (t_arr >= start_time) & (t_arr < end_time)
    result[ramp_mask] = start_value + (end_value - start_value) * (t_arr[ramp_mask] - start_time) / (end_time - start_time)
    result[t_arr >= end_time] = end_value
    return result


def get_series_with_tracking(name: str):
    series = try_get_series(problem, y_arr, name)
    if series is None:
        missing_si_variables.add(name)
    return series


def max_abs_value(series):
    if series is None:
        return None
    return float(np.max(np.abs(series)))


# If the VA model is changed to normalized voltage form, update these reference lines accordingly.
v_q_ref_initial_pu = np.sqrt(2.0)
v_d_ref_initial_pu = 0.0
vac_grid_initial_V = Vac_phase_peak
vac_grid_fault_V = (VAC_SCALE0_PU + DELTA_VAC_PU) * Vac_phase_peak
v_q_ref_initial_V = v_q_ref_initial_pu * V_phase_rms_base
v_q_ref_final_V = (V_Q_REF0_PU + DELTA_VQ_PU) * V_phase_rms_base
v_d_ref_initial_V = v_d_ref_initial_pu * V_phase_rms_base
v_d_ref_final_V = (V_D_REF0_PU + DELTA_VD_PU) * V_phase_rms_base

if selected_test == TEST_VAC_STEP:
    vac_grid_series_V = step_series(t_arr, t_Vac, vac_grid_initial_V, vac_grid_fault_V)
else:
    vac_grid_series_V = np.full_like(t_arr, vac_grid_initial_V, dtype=float)


omega_grid_initial = omega
omega_grid_final = omega + rocof_omega * (t_omega_end - t_omega)
if selected_test == TEST_ROCOF:
    omega_grid_series = ramp_series(t_arr, t_omega, t_omega_end, omega_grid_initial, omega_grid_final)
else:
    omega_grid_series = np.full_like(t_arr, omega_grid_initial, dtype=float)


if selected_test == TEST_PHASE_JUMP:
    phase_jump_series = step_series(t_arr, t_phase, 0.0, d_phase)
else:
    phase_jump_series = np.zeros_like(t_arr, dtype=float)

theta_grid_series = np.cumsum(omega_grid_series) * options.time_step + phase_jump_series
phase_a_grid_series = theta_grid_series
phase_b_grid_series = theta_grid_series - 2.0 * np.pi / 3.0
phase_c_grid_series = theta_grid_series + 2.0 * np.pi / 3.0

if selected_test == TEST_VQ_STEP:
    v_q_ref_series_V = step_series(t_arr, t_Vq, v_q_ref_initial_V, v_q_ref_final_V)
else:
    v_q_ref_series_V = np.full_like(t_arr, v_q_ref_initial_V, dtype=float)

if selected_test == TEST_VD_STEP:
    v_d_ref_series_V = step_series(t_arr, t_Vd, v_d_ref_initial_V, v_d_ref_final_V)
else:
    v_d_ref_series_V = np.full_like(t_arr, v_d_ref_initial_V, dtype=float)

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
plot_if_available(axes_si_overview[2], t_arr, v_q_ref_series_V, "Vq_ref [V]")
plot_if_available(axes_si_overview[2], t_arr, v_d_ref_series_V, "Vd_ref [V]")
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
if selected_test == TEST_P_GFM:
    pref_series_mw = step_series(t_arr, t_P_GFM, P_dc_pu * Sb_va / 1e6, (P_dc_pu + d_P_GFM) * Sb_va / 1e6)
else:
    pref_series_mw = np.full_like(t_arr, P_dc_pu * Sb_va / 1e6, dtype=float)
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
                          Ibase_vg, "y1 [A] sim sign (deprecated for internal comparison)", negate=True)
plot_scaled_with_tracking(axes_si_va[2], t_arr, problem, y_arr, "y2_G4L_Virtual_admittance",
                          Ibase_vg, "y2 [A] sim sign (deprecated for internal comparison)", negate=True)
plot_scaled_with_tracking(axes_si_va[2], t_arr, problem, y_arr, "y3_G4L_Virtual_admittance",
                          Ibase_vg, "y3 [A] sim sign (deprecated for internal comparison)", negate=True, linestyle="--")
plot_scaled_with_tracking(axes_si_va[2], t_arr, problem, y_arr, "y4_G4L_Virtual_admittance",
                          Ibase_vg, "y4 [A] sim sign (deprecated for internal comparison)", negate=True, linestyle="--")
axes_si_va[2].set_title("VA Internal Outputs y1-y4 [A] - Deprecated Mixed-Sign View")
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

y1_pu = get_series_with_tracking("y1_G4L_Virtual_admittance")
y2_pu = get_series_with_tracking("y2_G4L_Virtual_admittance")
y3_pu = get_series_with_tracking("y3_G4L_Virtual_admittance")
y4_pu = get_series_with_tracking("y4_G4L_Virtual_admittance")
err_q_pu = get_series_with_tracking("err_q_G4L_Virtual_admittance")
err_d_pu = get_series_with_tracking("err_d_G4L_Virtual_admittance")
i_q_out_va_pu = get_series_with_tracking("i_q_out_VA_G4L_Virtual_admittance")
i_d_out_va_pu = get_series_with_tracking("i_d_out_VA_G4L_Virtual_admittance")
i_q_lim_pu = get_series_with_tracking("i_q_lim_G4L_current_limiter")
i_d_lim_pu = get_series_with_tracking("i_d_lim_G4L_current_limiter")
i_q_meas_pu = get_series_with_tracking("i_q_G4L_clark_park_transforms_qd")
i_d_meas_pu = get_series_with_tracking("i_d_G4L_clark_park_transforms_qd")

err_q_V = scale_series(err_q_pu, V_phase_rms_base)
err_d_V = scale_series(err_d_pu, V_phase_rms_base)
y1_raw_A = scale_series(y1_pu, Ibase_vg)
y2_raw_A = scale_series(y2_pu, Ibase_vg)
y3_raw_A = scale_series(y3_pu, Ibase_vg)
y4_raw_A = scale_series(y4_pu, Ibase_vg)

print("VA reconstruction consistency checks")
if y1_pu is not None and y2_pu is not None and i_q_out_va_pu is not None:
    iq_recon_pu = y1_pu - y2_pu
    iq_recon_err_pu = iq_recon_pu - i_q_out_va_pu
    print(f"  max_abs(iq_recon_pu - i_q_out_VA) = {max_abs_value(iq_recon_err_pu)}")
    print(f"  max_abs((-iq_recon_pu + i_q_out_VA) * Ibase_vg) = {max_abs_value((-iq_recon_pu + i_q_out_va_pu) * Ibase_vg)}")
else:
    print("  q-axis reconstruction unavailable")
    iq_recon_pu = None

if y3_pu is not None and y4_pu is not None and i_d_out_va_pu is not None:
    id_recon_pu = y3_pu + y4_pu
    id_recon_err_pu = id_recon_pu - i_d_out_va_pu
    print(f"  max_abs(id_recon_pu - i_d_out_VA) = {max_abs_value(id_recon_err_pu)}")
    print(f"  max_abs((-id_recon_pu + i_d_out_VA) * Ibase_vg) = {max_abs_value((-id_recon_pu + i_d_out_va_pu) * Ibase_vg)}")
else:
    print("  d-axis reconstruction unavailable")
    id_recon_pu = None

iq_reconstructed_A_sim_sign = None if (y1_pu is None or y2_pu is None) else (-y1_pu + y2_pu) * Ibase_vg
id_reconstructed_A_sim_sign = None if (y3_pu is None or y4_pu is None) else (-y3_pu - y4_pu) * Ibase_vg
iq_actual_A_sim_sign = negate_scale_series(i_q_out_va_pu, Ibase_vg)
id_actual_A_sim_sign = negate_scale_series(i_d_out_va_pu, Ibase_vg)

fig_si_va_corrected, axes_si_va_corrected = plt.subplots(4, 1, figsize=(15, 14), sharex=True)
plot_if_available(axes_si_va_corrected[0], t_arr, err_q_V,
                  "err_q = Vq_ref - vq [V] (Simulink Scope1 first/upper/yellow)")
plot_if_available(axes_si_va_corrected[0], t_arr, err_d_V,
                  "err_d = Vd_ref - vd [V] (Simulink Scope1 second/lower/blue)")
axes_si_va_corrected[0].set_title("VA Voltage Errors [V] - Scope Order Check")
axes_si_va_corrected[0].set_ylabel("Voltage [V]")
axes_si_va_corrected[0].grid(True)
if axes_si_va_corrected[0].lines:
    axes_si_va_corrected[0].legend(loc="best")

plot_if_available(axes_si_va_corrected[1], t_arr, y1_raw_A, "y1 raw [A]")
plot_if_available(axes_si_va_corrected[1], t_arr, y2_raw_A, "y2 raw [A]")
plot_if_available(axes_si_va_corrected[1], t_arr, y3_raw_A, "y3 raw [A]")
plot_if_available(axes_si_va_corrected[1], t_arr, y4_raw_A, "y4 raw [A]")
axes_si_va_corrected[1].set_title("VA Internal Outputs y1-y4 [A] - Raw Sign, Before Final Output Sign")
axes_si_va_corrected[1].set_ylabel("Current [A]")
axes_si_va_corrected[1].grid(True)
if axes_si_va_corrected[1].lines:
    axes_si_va_corrected[1].legend(loc="best")

plot_if_available(axes_si_va_corrected[2], t_arr, None if y1_raw_A is None else -y1_raw_A,
                  "-y1 contribution to i_q_sim [A]")
plot_if_available(axes_si_va_corrected[2], t_arr, y2_raw_A,
                  "+y2 contribution to i_q_sim [A]")
plot_if_available(axes_si_va_corrected[2], t_arr, iq_reconstructed_A_sim_sign,
                  "reconstructed i_q_sim = -y1 + y2 [A]")
plot_if_available(axes_si_va_corrected[2], t_arr, iq_actual_A_sim_sign,
                  "actual i_q_out_VA sim sign [A]")
axes_si_va_corrected[2].set_title("VA Internal Contributions to Final q-Axis Current [A] - Simulink/load sign")
axes_si_va_corrected[2].set_ylabel("Current [A]")
axes_si_va_corrected[2].grid(True)
if axes_si_va_corrected[2].lines:
    axes_si_va_corrected[2].legend(loc="best")

plot_if_available(axes_si_va_corrected[3], t_arr, None if y3_raw_A is None else -y3_raw_A,
                  "-y3 contribution to i_d_sim [A]")
plot_if_available(axes_si_va_corrected[3], t_arr, None if y4_raw_A is None else -y4_raw_A,
                  "-y4 contribution to i_d_sim [A]")
plot_if_available(axes_si_va_corrected[3], t_arr, id_reconstructed_A_sim_sign,
                  "reconstructed i_d_sim = -y3 - y4 [A]")
plot_if_available(axes_si_va_corrected[3], t_arr, id_actual_A_sim_sign,
                  "actual i_d_out_VA sim sign [A]")
axes_si_va_corrected[3].set_title("VA Internal Contributions to Final d-Axis Current [A] - Simulink/load sign")
axes_si_va_corrected[3].set_ylabel("Current [A]")
axes_si_va_corrected[3].set_xlabel("Time [s]")
axes_si_va_corrected[3].grid(True)
if axes_si_va_corrected[3].lines:
    axes_si_va_corrected[3].legend(loc="best")

fig_si_va_corrected.suptitle("Virtual Admittance Internal Outputs - Correct SI Comparison")

Rv_si = 10.89
Xv_si = 108.9
D_si = Rv_si**2 + Xv_si**2

# These inferred signals are only meaningful in steady-state or slow transients because the transfer functions include dynamics.
err_q_from_y1 = None if y1_raw_A is None else y1_raw_A * D_si / Rv_si
err_q_from_y3 = None if y3_raw_A is None else y3_raw_A * D_si / Xv_si
err_d_from_y2 = None if y2_raw_A is None else y2_raw_A * D_si / Xv_si
err_d_from_y4 = None if y4_raw_A is None else y4_raw_A * D_si / Rv_si

fig_si_va_inferred, axes_si_va_inferred = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
plot_if_available(axes_si_va_inferred[0], t_arr, err_q_V, "err_q direct [V]")
plot_if_available(axes_si_va_inferred[0], t_arr, err_q_from_y1, "err_q from y1 [V]")
plot_if_available(axes_si_va_inferred[0], t_arr, err_q_from_y3, "err_q from y3 [V]")
axes_si_va_inferred[0].set_title("err_q direct vs inferred from y1/y3 [V]")
axes_si_va_inferred[0].set_ylabel("Voltage [V]")
axes_si_va_inferred[0].grid(True)
if axes_si_va_inferred[0].lines:
    axes_si_va_inferred[0].legend(loc="best")

plot_if_available(axes_si_va_inferred[1], t_arr, err_d_V, "err_d direct [V]")
plot_if_available(axes_si_va_inferred[1], t_arr, err_d_from_y2, "err_d from y2 [V]")
plot_if_available(axes_si_va_inferred[1], t_arr, err_d_from_y4, "err_d from y4 [V]")
axes_si_va_inferred[1].set_title("err_d direct vs inferred from y2/y4 [V]")
axes_si_va_inferred[1].set_ylabel("Voltage [V]")
axes_si_va_inferred[1].set_xlabel("Time [s]")
axes_si_va_inferred[1].grid(True)
if axes_si_va_inferred[1].lines:
    axes_si_va_inferred[1].legend(loc="best")

fig_si_va_inferred.suptitle("VA Error Reconstruction from y-components - Steady-State Check")

fig_si_currents_corrected, axes_si_currents_corrected = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
plot_if_available(axes_si_currents_corrected[0], t_arr, iq_actual_A_sim_sign, "i_q_out_VA [A]")
plot_if_available(axes_si_currents_corrected[0], t_arr, negate_scale_series(i_q_lim_pu, Ibase_vg), "i_q_lim [A]")
plot_if_available(axes_si_currents_corrected[0], t_arr, negate_scale_series(i_q_meas_pu, Ibase_vg), "i_q_meas [A]")
plot_horizontal(axes_si_currents_corrected[0], Imax_sim_A, "+Imax_sim_A")
plot_horizontal(axes_si_currents_corrected[0], -Imax_sim_A, "-Imax_sim_A", linestyle=":")
axes_si_currents_corrected[0].set_title("q-axis current chain")
axes_si_currents_corrected[0].set_ylabel("Current [A]")
axes_si_currents_corrected[0].grid(True)
if axes_si_currents_corrected[0].lines:
    axes_si_currents_corrected[0].legend(loc="best")

plot_if_available(axes_si_currents_corrected[1], t_arr, id_actual_A_sim_sign, "i_d_out_VA [A]")
plot_if_available(axes_si_currents_corrected[1], t_arr, negate_scale_series(i_d_lim_pu, Ibase_vg), "i_d_lim [A]")
plot_if_available(axes_si_currents_corrected[1], t_arr, negate_scale_series(i_d_meas_pu, Ibase_vg), "i_d_meas [A]")
plot_horizontal(axes_si_currents_corrected[1], Imax_sim_A, "+Imax_sim_A")
plot_horizontal(axes_si_currents_corrected[1], -Imax_sim_A, "-Imax_sim_A", linestyle=":")
axes_si_currents_corrected[1].set_title("d-axis current chain")
axes_si_currents_corrected[1].set_ylabel("Current [A]")
axes_si_currents_corrected[1].set_xlabel("Time [s]")
axes_si_currents_corrected[1].grid(True)
if axes_si_currents_corrected[1].lines:
    axes_si_currents_corrected[1].legend(loc="best")

fig_si_currents_corrected.suptitle("dq Current Chain [A] - Simulink/load sign")

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

csv_suffix = TEST_CSV_SUFFIX.get(selected_test, selected_test)
csv_path = os.path.join(REPO_ROOT, "trunk", "GridsForLoads_dynamic", f"veragrid_G4L_{csv_suffix}.csv")
plot_output_folder = get_plot_output_folder(csv_suffix)
csv_columns = {"time_s": t_arr}


def add_csv_series(column_name: str, source_name: str, factor: float, negate: bool = False):
    series = try_get_series(problem, y_arr, source_name)
    if series is None:
        missing_si_variables.add(source_name)
        return
    csv_columns[column_name] = negate_scale_series(series, factor) if negate else scale_series(series, factor)


def add_csv_array(column_name: str, series):
    if series is not None:
        csv_columns[column_name] = series


add_csv_series("vA_Bus1_kV", "v_A_Bus1_emt_template", V_phase_rms_base / 1000.0)
add_csv_series("vB_Bus1_kV", "v_B_Bus1_emt_template", V_phase_rms_base / 1000.0)
add_csv_series("vC_Bus1_kV", "v_C_Bus1_emt_template", V_phase_rms_base / 1000.0)
add_csv_series("iA_grid_A_sim_sign", "i_f_A_G4L_grid_side_converter", Ibase_vg, negate=True)
add_csv_series("iB_grid_A_sim_sign", "i_f_B_G4L_grid_side_converter", Ibase_vg, negate=True)
add_csv_series("iC_grid_A_sim_sign", "i_f_C_G4L_grid_side_converter", Ibase_vg, negate=True)
add_csv_series("vq_V", "v_q_G4L_clark_park_transforms_qd", V_phase_rms_base)
add_csv_series("vd_V", "v_d_G4L_clark_park_transforms_qd", V_phase_rms_base)
add_csv_series("iq_va_A_sim_sign", "i_q_out_VA_G4L_Virtual_admittance", Ibase_vg, negate=True)
add_csv_series("id_va_A_sim_sign", "i_d_out_VA_G4L_Virtual_admittance", Ibase_vg, negate=True)
add_csv_series("iq_lim_A_sim_sign", "i_q_lim_G4L_current_limiter", Ibase_vg, negate=True)
add_csv_series("id_lim_A_sim_sign", "i_d_lim_G4L_current_limiter", Ibase_vg, negate=True)
add_csv_series("iq_meas_A_sim_sign", "i_q_G4L_clark_park_transforms_qd", Ibase_vg, negate=True)
add_csv_series("id_meas_A_sim_sign", "i_d_G4L_clark_park_transforms_qd", Ibase_vg, negate=True)
add_csv_series("Pac_bus_MW_sim_sign", "Pac_bus_G4L_grid_side_converter", Sb_va / 1e6, negate=True)
add_csv_series("Pac_MW_sim_sign", "Pac_G4L_grid_side_converter", Sb_va / 1e6, negate=True)
add_csv_series("pdc_MW_sim_sign", "p_dc_G4L_load_side_converter_control", Sb_va / 1e6, negate=True)
add_csv_series("vdc_V", "v_dc_G4L_load_side_converter", Vdc_ref)
add_csv_series("idc_A", "i_dc_G4L_grid_side_converter", Idc_base)
add_csv_series("idcL_A", "i_dc_L_G4L_load_side_converter_control", Idc_base)
add_csv_series("icapdc_A", "i_cap_dc_G4L_load_side_converter", Idc_base)
add_csv_series("omega_pll", "omega_pll_G4L_PLL", 1.0)
add_csv_series("w_pll", "w_pll_G4L_PLL", 1.0)
add_csv_series("theta_pll", "theta_pll_G4L_PLL", 1.0)
add_csv_series("phase_pll", "phase_pll_G4L_PLL", 1.0)
add_csv_array("Vac_grid", vac_grid_series_V)
add_csv_array("phase_a", phase_a_grid_series)
add_csv_array("phase_b", phase_b_grid_series)
add_csv_array("phase_c", phase_c_grid_series)
add_csv_array("omega_grid", omega_grid_series)
add_csv_array("Vq_ref", v_q_ref_series_V)
add_csv_array("Vd_ref", v_d_ref_series_V)
if "phase_pll" in csv_columns and "theta_pll" in csv_columns:
    add_csv_array("delta_vsm", wrap_to_pi(csv_columns["phase_pll"] - csv_columns["theta_pll"]))
if "vd_V" in csv_columns and "vq_V" in csv_columns:
    add_csv_array("delta_from_vdq", np.arctan2(csv_columns["vd_V"], csv_columns["vq_V"]))

add_csv_array("err_q_V", err_q_V)
add_csv_array("err_d_V", err_d_V)
add_csv_array("y1_raw_A", y1_raw_A)
add_csv_array("y2_raw_A", y2_raw_A)
add_csv_array("y3_raw_A", y3_raw_A)
add_csv_array("y4_raw_A", y4_raw_A)
add_csv_array("y1_q_contribution_A_sim_sign", None if y1_raw_A is None else -y1_raw_A)
add_csv_array("y2_q_contribution_A_sim_sign", y2_raw_A)
add_csv_array("y3_d_contribution_A_sim_sign", None if y3_raw_A is None else -y3_raw_A)
add_csv_array("y4_d_contribution_A_sim_sign", None if y4_raw_A is None else -y4_raw_A)
add_csv_array("iq_va_reconstructed_A_sim_sign", iq_reconstructed_A_sim_sign)
add_csv_array("id_va_reconstructed_A_sim_sign", id_reconstructed_A_sim_sign)
add_csv_array("iq_va_actual_A_sim_sign", iq_actual_A_sim_sign)
add_csv_array("id_va_actual_A_sim_sign", id_actual_A_sim_sign)

with open(csv_path, "w", newline="") as csv_file:
    writer = csv.writer(csv_file)
    headers = list(csv_columns.keys())
    writer.writerow(headers)
    for idx in range(len(t_arr)):
        writer.writerow([csv_columns[col][idx] for col in headers])

print(f"SI comparison CSV exported to: {csv_path}")
print("SI comparison missing variables:", sorted(missing_si_variables) if missing_si_variables else "none")
print("Summary:")
print("  - Added corrected raw VA internal output plot.")
print("  - Added contribution-to-final-current plot.")
print("  - Added VA reconstruction consistency checks.")
print("  - Added steady-state inferred-error diagnostics.")
print(f"  - Listed unavailable variables: {sorted(missing_si_variables) if missing_si_variables else 'none'}.")

fig_si_overview.tight_layout()
# fig_si_va.tight_layout()
fig_si_currents.tight_layout()
# fig_si_pll.tight_layout()
# fig_si_va_corrected.tight_layout()
# fig_si_va_inferred.tight_layout()
fig_si_currents_corrected.tight_layout()

figures_to_save = [
    ("01_ac_voltage_current_overview", fig_si_overview),
    ("02_dq_current_chain", fig_si_currents_corrected),
    ("03_power_and_frequency_response", fig_si_pll),
    ("04_virtual_admittance_internal_checks", fig_si_va_corrected),
]
save_selected_figures(plot_output_folder, figures_to_save)
print(f"PNG plots exported to: {plot_output_folder}")
# plt.show()
