# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR: str = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_ROOT: str = os.path.join(REPO_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Templates.Emt.converter_emt_template_pq_inverse_test import get_full_pseudo_emt_converter
from VeraGridEngine.Templates.Emt.dc_line_emt_template import get_dc_line_with_power_input_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.block import Block, Var, build_name_to_var_lookup, find_name_in_block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping import converter_control_code
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    SolverType,
    DynamicEventTransitionType,
)


def get_signal(problem: EmtProblemDae, block: Block, variable_name: str, trajectory: np.ndarray) -> np.ndarray:
    variable: Optional[Var] = find_name_in_block(variable_name, block)

    if variable is not None:
        return np.array(trajectory[:, problem.get_var_idx(variable)], copy=True)

    print(f"Warning: variable '{variable_name}' was not found in block '{block.name}'.")
    return np.zeros(trajectory.shape[0], dtype=np.float64)


def get_piecewise_reference_trace(time_s: np.ndarray, initial_value: float, events: list[tuple[float, float]]) -> np.ndarray:
    trace: np.ndarray = np.full(time_s.shape[0], initial_value, dtype=np.float64)

    event_time_s: float
    event_value: float
    for event_time_s, event_value in sorted(events, key=lambda item: item[0]):
        trace[time_s >= event_time_s] = event_value

    return trace


def get_step_window_trace(time_s: np.ndarray, start_s: float, end_s: float, level: float, base_value: float = 0.0) -> np.ndarray:
    trace: np.ndarray = np.full(time_s.shape[0], base_value, dtype=np.float64)
    trace[(time_s >= start_s) & (time_s < end_s)] = level
    return trace


def get_event_reference_trace(
    time_s: np.ndarray,
    initial_value: float,
    events: list[tuple[float, float, Optional[float], DynamicEventTransitionType]],
) -> np.ndarray:
    trace: np.ndarray = np.full(time_s.shape[0], initial_value, dtype=np.float64)
    current_value: float = initial_value

    for event_time_s, event_value, end_time_s, transition_type in sorted(events, key=lambda item: item[0]):
        if transition_type == DynamicEventTransitionType.Step or end_time_s is None:
            trace[time_s >= event_time_s] = event_value
            current_value = event_value
            continue

        ramp_mask = (time_s >= event_time_s) & (time_s < end_time_s)
        if np.any(ramp_mask):
            ramp_fraction = (time_s[ramp_mask] - event_time_s) / max(end_time_s - event_time_s, 1.0e-12)
            trace[ramp_mask] = current_value + ramp_fraction * (event_value - current_value)

        trace[time_s >= end_time_s] = event_value
        current_value = event_value

    return trace


sbase_mva: float = 100.0
fbase_hz: float = 50.0
ac_voltage_ll_kv: float = 90.0
dc_voltage_kv: float = 145.0
grid_resistance_ohm: float = 4.8 * 0.669
grid_inductance_h: float = 0.052 * 0.669
coupling_resistance_ohm: float = 3.68 / 10.0
coupling_inductance_h: float = 30.0e-3

# simulation_time_s: float = 0.5
# simulation_time_s: float = 0.45
simulation_time_s: float = 0.23
time_step_s: float = 2.0e-5
q_setpoint_1_mvar: float = 0.0
q_setpoint_2_mvar: float = 0.0
# transfer_power_mw: float = 100.0
# transfer_power_mw: float = 85.0
# transfer_power_mw: float = 70.0
transfer_power_mw: float = 60.0
transfer_power_pu: float = transfer_power_mw / sbase_mva
# idle_power_pu: float = 0.0
idle_power_pu: float = 1.0e-6

q_setpoint_1_pu: float = q_setpoint_1_mvar / sbase_mva
q_setpoint_2_pu: float = q_setpoint_2_mvar / sbase_mva

tau = 1 / 3100
current_kp: float = coupling_inductance_h / tau
current_ki: float = coupling_resistance_ohm / tau
print(f"current_kp = {current_kp}")
print(f"current_ki = {current_ki}")

converter_model_sbase_pu: float = 1.0
dc_link_capacitance_pu: float = 0.8
vac_control_reference_pu: float = 1.0
q_kp_vsc1: float = 0.8
q_ki_vsc1: float = 20.0
q_kp_vsc2: float = 0.8
q_ki_vsc2: float = 20.0
# loss_linear_pu: float = 1.0e-4
# loss_quadratic_pu: float = 1.0e-4
loss_linear_pu: float = 0.0
loss_quadratic_pu: float = 0.0

# i_max_default_pu: float = 1.3
# m_max_default_pu: float = 0.95
# i_max_default_pu: float = 1.55
# m_max_default_pu: float = 0.98
# i_max_default_pu: float = 1.4
# m_max_default_pu: float = 0.96
i_max_default_pu: float = 1.4
m_max_default_pu: float = 0.97

# vdc_kp_default: float = 4.0
# vdc_ki_default: float = 80.0
# vdc_kp_default: float = 3.0
# vdc_ki_default: float = 45.0
# vdc_kp_default: float = 2.0
# vdc_ki_default: float = 30.0
vdc_kp_default: float = 1.0
vdc_ki_default: float = 10.0

# tau_meas_default_s: float = 0.002
# tau_meas_default_s: float = 0.001
# tau_meas_default_s: float = 0.005
tau_meas_default_s: float = 0.003

# aw_gain_default: float = 0.1
# aw_gain_default: float = 0.5
# aw_gain_default: float = 0.2
# aw_gain_default: float = 0.3
aw_gain_default: float = 0.1

grid: gce.MultiCircuit = gce.MultiCircuit(
    name="Point-to-point HVDC EMT example v3",
    Sbase=sbase_mva,
    fbase=fbase_hz,
)

ac_base_impedance_ohm: float = (ac_voltage_ll_kv * ac_voltage_ll_kv) / sbase_mva
dc_base_impedance_ohm: float = (dc_voltage_kv * dc_voltage_kv) / sbase_mva
print(f"ac_base_impedance_ohm = {ac_base_impedance_ohm}")
print(f"dc_base_impedance_ohm = {dc_base_impedance_ohm}")
omega_base_rad_s: float = 2.0 * np.pi * fbase_hz
dc_base_inductance_h: float = dc_base_impedance_ohm / omega_base_rad_s
dc_base_capacitance_f: float = 1.0 / (omega_base_rad_s * dc_base_impedance_ohm)
print(f"dc_base_inductance_h = {dc_base_inductance_h}")
print(f"dc_base_capacitance_f = {dc_base_capacitance_f}")
grid_r_pu: float = grid_resistance_ohm / ac_base_impedance_ohm
grid_x_pu: float = omega_base_rad_s * grid_inductance_h / ac_base_impedance_ohm
print(f"grid_r_pu = {grid_r_pu}")
print(f"grid_x_pu = {grid_x_pu}")
dc_line_r_pu: float = (0.5 + 0.25 + 0.4) / dc_base_impedance_ohm
print(f"dc_line_r_pu = {dc_line_r_pu}")
dc_line_r1_pu: float = 0.5 / dc_base_impedance_ohm
dc_line_r2_pu: float = 0.25 / dc_base_impedance_ohm
dc_line_r3_pu: float = 0.4 / dc_base_impedance_ohm
dc_line_l1_pu: float = 0.005 / dc_base_inductance_h
dc_line_l2_pu: float = 0.0025 / dc_base_inductance_h
dc_line_l3_pu: float = 0.004 / dc_base_inductance_h
dc_line_capacitor_pu: float = 150.0e-6 / dc_base_capacitance_f
print(f"dc_line_r1_pu = {dc_line_r1_pu}")
print(f"dc_line_r2_pu = {dc_line_r2_pu}")
print(f"dc_line_r3_pu = {dc_line_r3_pu}")
print(f"dc_line_l1_pu = {dc_line_l1_pu}")
print(f"dc_line_l2_pu = {dc_line_l2_pu}")
print(f"dc_line_l3_pu = {dc_line_l3_pu}")
print(f"dc_line_capacitor_pu = {dc_line_capacitor_pu}")


bus_grid_1: gce.Bus = gce.Bus(name="Bus_Grid_1", Vnom=ac_voltage_ll_kv, is_slack=True)
bus_dc_1: gce.Bus = gce.Bus(name="Bus_DC_1", Vnom=dc_voltage_kv, is_dc=True)
bus_dc_2: gce.Bus = gce.Bus(name="Bus_DC_2", Vnom=dc_voltage_kv, is_dc=True)
bus_grid_2: gce.Bus = gce.Bus(name="Bus_Grid_2", Vnom=ac_voltage_ll_kv, is_slack=True)

grid.add_bus(bus_grid_1)
grid.add_bus(bus_dc_1)
grid.add_bus(bus_dc_2)
grid.add_bus(bus_grid_2)

generator_1: gce.Generator = gce.Generator(
    name="Generator_Grid_1",
    vset=1.0,
    Snom=sbase_mva,
    freq=fbase_hz,
    r1=grid_r_pu,
    x1=grid_x_pu,
)
generator_2: gce.Generator = gce.Generator(
    name="Generator_Grid_2",
    vset=1.0,
    Snom=sbase_mva,
    freq=fbase_hz,
    r1=grid_r_pu,
    x1=grid_x_pu,
)
grid.add_generator(bus_grid_1, generator_1)
grid.add_generator(bus_grid_2, generator_2)

converter_1: gce.VSC = gce.VSC(
    name="VSC_1",
    bus_from=bus_dc_1,
    bus_to=bus_grid_1,
    rate=sbase_mva,
    control1=ConverterControlType.Vm_dc,
    control2=ConverterControlType.Qac,
    control1_val=1.0,
    control2_val=q_setpoint_1_pu,
)
converter_2: gce.VSC = gce.VSC(
    name="VSC_2",
    bus_from=bus_dc_2,
    bus_to=bus_grid_2,
    rate=sbase_mva,
    control1=ConverterControlType.Pdc,
    control2=ConverterControlType.Qac,
    control1_val=idle_power_pu,
    control2_val=q_setpoint_2_pu,
)
grid.add_vsc(converter_1)
grid.add_vsc(converter_2)

dc_line: gce.DcLine = gce.DcLine(
    name="HVDC_Line",
    bus_from=bus_dc_1,
    bus_to=bus_dc_2,
    r=dc_line_r_pu,
    rate=sbase_mva,
)
grid.add_dc_line(dc_line)

bus: gce.Bus
for bus in grid.buses:
    get_bus_emt_template(grid, bus)

generator_1_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="grid1_thevenin_emt").block
generator_2_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="grid2_thevenin_emt").block
converter_1_mdl: Block = get_full_pseudo_emt_converter(vf=grid.var_factory, name="vsc1_pseudo_emt").block
converter_2_mdl: Block = get_full_pseudo_emt_converter(vf=grid.var_factory, name="vsc2_pseudo_emt").block
dc_line_mdl: Block = get_dc_line_with_power_input_emt_template(vf=grid.var_factory, name="hvdc_line_power_input_emt").block

for converter_mdl, suffix, control1_type, control1_value, q_setpoint_pu in [
    (converter_1_mdl, "vsc1_pseudo_emt", ConverterControlType.Vm_dc, 1.0, q_setpoint_1_pu),
    (converter_2_mdl, "vsc2_pseudo_emt", ConverterControlType.Pdc, idle_power_pu, q_setpoint_2_pu),
]:
    converter_mdl.set_parameter_in_model(var_name=f"sbase_{suffix}", new_value=converter_model_sbase_pu)
    converter_mdl.set_parameter_in_model(var_name=f"omega_base_{suffix}", new_value=omega_base_rad_s)
    converter_mdl.set_parameter_in_model(var_name=f"control1_{suffix}", new_value=converter_control_code(control1_type))
    converter_mdl.set_parameter_in_model(var_name=f"control2_{suffix}", new_value=converter_control_code(ConverterControlType.Qac))
    converter_mdl.set_parameter_in_model(var_name=f"control1_val_{suffix}", new_value=control1_value)
    converter_mdl.set_parameter_in_model(var_name=f"control2_val_{suffix}", new_value=q_setpoint_pu)
    converter_mdl.set_parameter_in_model(var_name=f"R_eq_{suffix}", new_value=coupling_resistance_ohm)
    converter_mdl.set_parameter_in_model(var_name=f"L_eq_{suffix}", new_value=coupling_inductance_h)
    converter_mdl.set_parameter_in_model(var_name=f"C_dc_{suffix}", new_value=dc_link_capacitance_pu)
    converter_mdl.set_parameter_in_model(var_name=f"R_dc_{suffix}", new_value=1e6)
    converter_mdl.set_parameter_in_model(var_name=f"R_dc_term_{suffix}", new_value=0.0001)
    converter_mdl.set_parameter_in_model(var_name=f"P0_{suffix}", new_value=idle_power_pu)
    converter_mdl.set_parameter_in_model(var_name=f"pll_kp_{suffix}", new_value=40.0)
    converter_mdl.set_parameter_in_model(var_name=f"pll_ki_{suffix}", new_value=400.0)
    converter_mdl.set_parameter_in_model(var_name=f"i_kp_{suffix}", new_value=current_kp)
    converter_mdl.set_parameter_in_model(var_name=f"i_ki_{suffix}", new_value=current_ki)
    converter_mdl.set_parameter_in_model(var_name=f"vdc_kp_{suffix}", new_value=vdc_kp_default)
    converter_mdl.set_parameter_in_model(var_name=f"vdc_ki_{suffix}", new_value=vdc_ki_default)
    converter_mdl.set_parameter_in_model(var_name=f"q_kp_{suffix}", new_value=q_kp_vsc1 if suffix.startswith("vsc1") else q_kp_vsc2)
    converter_mdl.set_parameter_in_model(var_name=f"q_ki_{suffix}", new_value=q_ki_vsc1 if suffix.startswith("vsc1") else q_ki_vsc2)
    converter_mdl.set_parameter_in_model(var_name=f"i_max_{suffix}", new_value=i_max_default_pu)
    converter_mdl.set_parameter_in_model(var_name=f"m_max_{suffix}", new_value=m_max_default_pu)
    converter_mdl.set_parameter_in_model(var_name=f"P_loss_i1_{suffix}", new_value=loss_linear_pu)
    converter_mdl.set_parameter_in_model(var_name=f"P_loss_i2_{suffix}", new_value=loss_quadratic_pu)
    converter_mdl.set_parameter_in_model(var_name=f"tau_meas_{suffix}", new_value=tau_meas_default_s)
    converter_mdl.set_parameter_in_model(var_name=f"aw_gain_{suffix}", new_value=aw_gain_default)
    converter_mdl.set_parameter_in_model(var_name=f"vdc_floor_{suffix}", new_value=0.05)
    converter_mdl.set_parameter_in_model(var_name=f"Vdc_nom_{suffix}", new_value=1.0)

# The DC-line template now owns the physical RL defaults directly in its event dict.
dc_line_mdl.set_parameter_in_model(var_name="R1_hvdc_line_power_input_emt", new_value=dc_line_r1_pu)
dc_line_mdl.set_parameter_in_model(var_name="L1_hvdc_line_power_input_emt", new_value=dc_line_l1_pu)
dc_line_mdl.set_parameter_in_model(var_name="R2_hvdc_line_power_input_emt", new_value=dc_line_r2_pu)
dc_line_mdl.set_parameter_in_model(var_name="L2_hvdc_line_power_input_emt", new_value=dc_line_l2_pu)
dc_line_mdl.set_parameter_in_model(var_name="R3_hvdc_line_power_input_emt", new_value=dc_line_r3_pu)
dc_line_mdl.set_parameter_in_model(var_name="L3_hvdc_line_power_input_emt", new_value=dc_line_l3_pu)
dc_line_mdl.set_parameter_in_model(var_name="C_end_f_hvdc_line_power_input_emt", new_value=dc_line_capacitor_pu)
dc_line_mdl.set_parameter_in_model(var_name="C_mid_1_hvdc_line_power_input_emt", new_value=dc_line_capacitor_pu)
dc_line_mdl.set_parameter_in_model(var_name="C_mid_2_hvdc_line_power_input_emt", new_value=dc_line_capacitor_pu)
dc_line_mdl.set_parameter_in_model(var_name="C_end_t_hvdc_line_power_input_emt", new_value=dc_line_capacitor_pu)
dc_line_mdl.set_parameter_in_model(var_name="Pext_hvdc_line_power_input_emt", new_value=idle_power_pu)

set_emt_model(device=generator_1, model=generator_1_mdl, var_factory=grid.var_factory)
set_emt_model(device=generator_2, model=generator_2_mdl, var_factory=grid.var_factory)
set_emt_model(device=converter_1, model=converter_1_mdl, var_factory=grid.var_factory)
set_emt_model(device=converter_2, model=converter_2_mdl, var_factory=grid.var_factory)
set_emt_model(device=dc_line, model=dc_line_mdl, var_factory=grid.var_factory)

dc_line_name_lookup = build_name_to_var_lookup(dc_line_mdl)
p_ext_var = dc_line_name_lookup.get("Pext_hvdc_line_power_input_emt")

if p_ext_var is None:
    raise RuntimeError("Could not resolve event parameter 'Pext_hvdc_line_power_input_emt'.")

events_group = EmtEventsGroup("simulation1")
grid.add_emt_events_group(events_group)

p_ext_events: list[tuple[float, float]] = [
    (0.09, idle_power_pu),
    (0.17, idle_power_pu),
    (0.2, idle_power_pu),
]

vsc1_reference_events: list[tuple[float, float, Optional[float], DynamicEventTransitionType]] = []

vsc2_reference_events: list[tuple[float, float, Optional[float], DynamicEventTransitionType]] = [
    (0.09, transfer_power_pu, None, DynamicEventTransitionType.Step),
    (0.17, idle_power_pu, 0.2, DynamicEventTransitionType.Ramp),
]

vsc2_control1_var = build_name_to_var_lookup(converter_2_mdl).get("control1_val_vsc2_pseudo_emt")
if vsc2_control1_var is None:
    raise RuntimeError("Could not resolve event parameter 'control1_val_vsc2_pseudo_emt'.")

#  ramp event
grid.add_emt_event(EmtEvent(device=dc_line, parameter=p_ext_var, time=p_ext_events[0][0], value=p_ext_events[0][1], group=events_group))
grid.add_emt_event(EmtEvent(device=dc_line, parameter=p_ext_var, time=p_ext_events[1][0], value=p_ext_events[1][1], group=events_group))
grid.add_emt_event(EmtEvent(device=dc_line, parameter=p_ext_var, time=p_ext_events[2][0], value=p_ext_events[2][1], group=events_group))
for event_time_s, event_value, end_time_s, transition_type in vsc2_reference_events:
    grid.add_emt_event(EmtEvent(
        device=converter_2,
        parameter=vsc2_control1_var,
        time=event_time_s,
        end_time=end_time_s,
        value=event_value,
        group=events_group,
        transition_type=transition_type,
    ))

pf_options: PowerFlowOptions = PowerFlowOptions(
    solver_type=SolverType.NR,
    retry_with_other_methods=True,
    verbose=False,
    tolerance=1e-6,
    max_iter=100,
    control_q=True,
    control_taps_modules=False,
    control_taps_phase=False,
    orthogonalize_controls=False,
)
pf_results: gce.PowerFlowResults = gce.power_flow(grid=grid, options=pf_options)

print("=" * 80)
print("BALANCED AC/DC POWER FLOW RESULTS")
print("=" * 80)
print(f"Converged: {pf_results.converged}")
print(pf_results.get_bus_df())
print(pf_results.get_branch_df())

emt_options: EmtOptions = EmtOptions(
    time_step=time_step_s,
    simulation_time=simulation_time_s,
    tolerance=1e-6,
    solver_type=EmtSolverTypes.StructuralAD,
    initialization_method=EmtInitializationMethod.Explicit,
    integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
    verbose=1,
)

problem: EmtProblemDae = EmtProblemDae(
    grid=grid,
    options=emt_options,
    pf_results_3ph=None,
    pf_results=pf_results,
)
problem.set_events_group(events_group)

print("=" * 80)
print("EMT INITIALIZATION REPORT")
print("=" * 80)
print(f"Finite x0 : {bool(np.all(np.isfinite(problem.get_x0())))}")
print(f"Finite dx0: {bool(np.all(np.isfinite(problem.get_dx0())))}")
if problem.initialization_report is not None:
    print(f"Method    : {problem.initialization_report.method_used.name}")
    print(f"Status    : {problem.initialization_report.status.name}")
    print(f"Residual  : {problem.initialization_report.final_residual_inf:.3e}")

solver: StructuralCompiledSolver = StructuralCompiledSolver(
    problem=problem,
    t0=0.0,
    t_end=simulation_time_s,
    h=time_step_s,
    method=emt_options.integration_method,
    pred_method=DynamicIntegrationMethod.OdeEuler,
    dense_threshold=0,
    verbose=False,
    auto_build=False,
)
solver._build_vectorized_backend(emt_options.integration_method)

time_s, trajectory, diff_trajectory, well_initialized, converged = solver.simulate()

print("=" * 80)
print("EMT SIMULATION REPORT")
print("=" * 80)
print(f"well_initialized = {well_initialized}")
print(f"converged        = {converged}")

p_ext_trace_pu: np.ndarray = get_piecewise_reference_trace(time_s=time_s, initial_value=idle_power_pu, events=p_ext_events)
v_dc_1: np.ndarray = get_signal(problem, bus_dc_1.emt_model, "v_DC", trajectory)
v_dc_2: np.ndarray = get_signal(problem, bus_dc_2.emt_model, "v_DC", trajectory)
i_line_r1: np.ndarray = get_signal(problem, dc_line_mdl, "i_r1_hvdc_line_power_input_emt", trajectory)
i_line_r2: np.ndarray = get_signal(problem, dc_line_mdl, "i_r2_hvdc_line_power_input_emt", trajectory)
i_line_r3: np.ndarray = get_signal(problem, dc_line_mdl, "i_r3_hvdc_line_power_input_emt", trajectory)
i_f_dc: np.ndarray = get_signal(problem, dc_line_mdl, "i_f_dc_hvdc_line_power_input_emt", trajectory)
i_t_dc: np.ndarray = get_signal(problem, dc_line_mdl, "i_t_dc_hvdc_line_power_input_emt", trajectory)
p_f_dc: np.ndarray = get_signal(problem, dc_line_mdl, "p_f_dc_hvdc_line_power_input_emt", trajectory)
p_t_dc: np.ndarray = get_signal(problem, dc_line_mdl, "p_t_dc_hvdc_line_power_input_emt", trajectory)
v_n1: np.ndarray = get_signal(problem, dc_line_mdl, "v_n1_hvdc_line_power_input_emt", trajectory)
v_n2: np.ndarray = get_signal(problem, dc_line_mdl, "v_n2_hvdc_line_power_input_emt", trajectory)
v_pcc1_a: np.ndarray = get_signal(problem, bus_grid_1.emt_model, "v_A", trajectory)
v_pcc2_a: np.ndarray = get_signal(problem, bus_grid_2.emt_model, "v_A", trajectory)
v_pcc1_b: np.ndarray = get_signal(problem, bus_grid_1.emt_model, "v_B", trajectory)
v_pcc2_b: np.ndarray = get_signal(problem, bus_grid_2.emt_model, "v_B", trajectory)
v_pcc1_c: np.ndarray = get_signal(problem, bus_grid_1.emt_model, "v_C", trajectory)
v_pcc2_c: np.ndarray = get_signal(problem, bus_grid_2.emt_model, "v_C", trajectory)
i_vsc1_a: np.ndarray = get_signal(problem, converter_1_mdl, "i_A_vsc1_pseudo_emt", trajectory)
i_vsc1_b: np.ndarray = get_signal(problem, converter_1_mdl, "i_B_vsc1_pseudo_emt", trajectory)
i_vsc1_c: np.ndarray = get_signal(problem, converter_1_mdl, "i_C_vsc1_pseudo_emt", trajectory)
i_vsc2_a: np.ndarray = get_signal(problem, converter_2_mdl, "i_A_vsc2_pseudo_emt", trajectory)
i_vsc2_b: np.ndarray = get_signal(problem, converter_2_mdl, "i_B_vsc2_pseudo_emt", trajectory)
i_vsc2_c: np.ndarray = get_signal(problem, converter_2_mdl, "i_C_vsc2_pseudo_emt", trajectory)
p_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "P_vsc1_pseudo_emt", trajectory)
p_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "P_vsc2_pseudo_emt", trajectory)
q_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "Q_vsc1_pseudo_emt", trajectory)
q_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "Q_vsc2_pseudo_emt", trajectory)
i_dc_conv_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "i_dc_conv_vsc1_pseudo_emt", trajectory)
i_dc_conv_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "i_dc_conv_vsc2_pseudo_emt", trajectory)
i_d_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "i_d_vsc1_pseudo_emt", trajectory)
i_q_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "i_q_vsc1_pseudo_emt", trajectory)
i_d_ref_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "i_d_ref_vsc1_pseudo_emt", trajectory)
i_q_ref_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "i_q_ref_vsc1_pseudo_emt", trajectory)
i_d_ref_u_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "i_d_ref_u_vsc1_pseudo_emt", trajectory)
i_q_ref_u_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "i_q_ref_u_vsc1_pseudo_emt", trajectory)
i_d_ff_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "i_d_ff_vsc1_pseudo_emt", trajectory)
i_q_ff_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "i_q_ff_vsc1_pseudo_emt", trajectory)
p_f_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "P_f_vsc1_pseudo_emt", trajectory)
q_f_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "Q_f_vsc1_pseudo_emt", trajectory)
v_cmd_d_u_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "v_cmd_d_u_vsc1_pseudo_emt", trajectory)
v_cmd_q_u_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "v_cmd_q_u_vsc1_pseudo_emt", trajectory)
v_cmd_d_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "v_cmd_d_vsc1_pseudo_emt", trajectory)
v_cmd_q_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "v_cmd_q_vsc1_pseudo_emt", trajectory)
v_lim_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "v_lim_vsc1_pseudo_emt", trajectory)
k_v_conv_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "k_v_conv_vsc1_pseudo_emt", trajectory)
i_d_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "i_d_vsc2_pseudo_emt", trajectory)
i_q_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "i_q_vsc2_pseudo_emt", trajectory)
i_d_ref_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "i_d_ref_vsc2_pseudo_emt", trajectory)
i_q_ref_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "i_q_ref_vsc2_pseudo_emt", trajectory)
i_d_ref_u_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "i_d_ref_u_vsc2_pseudo_emt", trajectory)
i_q_ref_u_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "i_q_ref_u_vsc2_pseudo_emt", trajectory)
i_d_ff_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "i_d_ff_vsc2_pseudo_emt", trajectory)
i_q_ff_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "i_q_ff_vsc2_pseudo_emt", trajectory)
p_f_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "P_f_vsc2_pseudo_emt", trajectory)
q_f_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "Q_f_vsc2_pseudo_emt", trajectory)
v_cmd_d_u_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "v_cmd_d_u_vsc2_pseudo_emt", trajectory)
v_cmd_q_u_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "v_cmd_q_u_vsc2_pseudo_emt", trajectory)
v_cmd_d_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "v_cmd_d_vsc2_pseudo_emt", trajectory)
v_cmd_q_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "v_cmd_q_vsc2_pseudo_emt", trajectory)
v_lim_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "v_lim_vsc2_pseudo_emt", trajectory)
k_v_conv_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "k_v_conv_vsc2_pseudo_emt", trajectory)
vsc1_pdc_ref_trace_pu: np.ndarray = get_event_reference_trace(
    time_s=time_s,
    initial_value=1.0,
    events=vsc1_reference_events,
)
vsc2_pdc_ref_trace_pu: np.ndarray = get_event_reference_trace(
    time_s=time_s,
    initial_value=idle_power_pu,
    events=vsc2_reference_events,
)
q_vsc1_ref_trace_pu: np.ndarray = np.full(time_s.shape[0], q_setpoint_1_pu, dtype=np.float64)
q_vsc2_ref_trace_pu: np.ndarray = np.full(time_s.shape[0], q_setpoint_2_pu, dtype=np.float64)
line_power_reference_trace_pu: np.ndarray = -vsc2_pdc_ref_trace_pu

figure, axes = plt.subplots(5, 2, figsize=(16, 16), sharex=True)

axes[0, 0].plot(time_s, v_pcc1_a, label="Va PCC1")
axes[0, 0].plot(time_s, v_pcc1_b, label="Vb PCC1")
axes[0, 0].plot(time_s, v_pcc1_c, label="Vc PCC1")
axes[0, 0].set_ylabel("Voltage [pu]")
axes[0, 0].set_title("AC terminal voltages PCC1")
axes[0, 0].grid(True)
axes[0, 0].legend(loc="upper right")

axes[0, 1].plot(time_s, v_pcc2_a, label="Va PCC2")
axes[0, 1].plot(time_s, v_pcc2_b, label="Vb PCC2")
axes[0, 1].plot(time_s, v_pcc2_c, label="Vc PCC2")
axes[0, 1].set_ylabel("Voltage [pu]")
axes[0, 1].set_title("AC terminal voltages PCC2")
axes[0, 1].grid(True)
axes[0, 1].legend(loc="upper right")

axes[1, 0].plot(time_s, i_vsc1_a, label="Ia VSC1")
axes[1, 0].plot(time_s, i_vsc1_b, label="Ib VSC1")
axes[1, 0].plot(time_s, i_vsc1_c, label="Ic VSC1")
axes[1, 0].set_ylabel("Current [pu]")
axes[1, 0].set_title("Converter currents VSC1")
axes[1, 0].grid(True)
axes[1, 0].legend(loc="upper right")

axes[1, 1].plot(time_s, i_vsc2_a, label="Ia VSC2")
axes[1, 1].plot(time_s, i_vsc2_b, label="Ib VSC2")
axes[1, 1].plot(time_s, i_vsc2_c, label="Ic VSC2")
axes[1, 1].set_ylabel("Current [pu]")
axes[1, 1].set_title("Converter currents VSC2")
axes[1, 1].grid(True)
axes[1, 1].legend(loc="upper right")

axes[2, 0].plot(time_s, vsc1_pdc_ref_trace_pu, "--", label="Pdc ref VSC1")
axes[2, 0].plot(time_s, vsc2_pdc_ref_trace_pu, "--", label="Pdc ref VSC2")
axes[2, 0].plot(time_s, p_vsc1, label="P VSC1")
axes[2, 0].plot(time_s, p_vsc2, label="P VSC2")
axes[2, 0].plot(time_s, q_vsc1_ref_trace_pu, ":", label="Q ref VSC1")
axes[2, 0].plot(time_s, q_vsc2_ref_trace_pu, ":", label="Q ref VSC2")
axes[2, 0].plot(time_s, q_vsc1, label="Q VSC1")
axes[2, 0].plot(time_s, q_vsc2, label="Q VSC2")
axes[2, 0].set_ylabel("Power [pu]")
axes[2, 0].set_title("Converter P/Q and commands")
axes[2, 0].grid(True)
axes[2, 0].legend(loc="upper right")

axes[2, 1].plot(time_s, v_dc_1, label="Vdc bus 1")
axes[2, 1].plot(time_s, v_dc_2, label="Vdc bus 2")
axes[2, 1].set_ylabel("Voltage [pu]")
axes[2, 1].set_title("DC bus voltages")
axes[2, 1].grid(True)
axes[2, 1].legend(loc="upper right")

axes[3, 0].plot(time_s, -line_power_reference_trace_pu, "--", label="P line ref")
axes[3, 0].plot(time_s, p_f_dc, label="Pf line")
axes[3, 0].plot(time_s, p_t_dc, label="Pt line")
# axes[3, 0].plot(time_s, p_ext_trace_pu, ":", label="Pext line")
axes[3, 0].set_xlabel("Time [s]")
axes[3, 0].set_ylabel("Power [pu]")
axes[3, 0].set_title("DC line powers and references")
axes[3, 0].grid(True)
axes[3, 0].legend(loc="upper right")

axes[3, 1].plot(time_s, i_f_dc, label="If")
axes[3, 1].plot(time_s, i_t_dc, label="It")
axes[3, 1].plot(time_s, vsc2_pdc_ref_trace_pu / np.maximum(v_dc_2, 1.0e-6), "--", label="Idc ref VSC2")
axes[3, 1].plot(time_s, p_vsc2 / np.maximum(v_dc_2, 1.0e-6), label="Idc eq VSC2")
axes[3, 1].plot(time_s, p_ext_trace_pu / np.maximum(0.5 * (v_n1 + v_n2), 1.0e-6), ":", label="Pext / Vmid")
axes[3, 1].set_xlabel("Time [s]")
axes[3, 1].set_ylabel("Current [pu]")
axes[3, 1].set_title("DC current command and line currents")
axes[3, 1].grid(True)
axes[3, 1].legend(loc="upper right")

# Plot dq currents together with their outer-loop references to verify that the
# inverse P/Q current-reference mapping uses the same convention as the power equations.
axes[4, 0].plot(time_s, i_d_vsc1, label="i_d VSC1")
axes[4, 0].plot(time_s, i_q_vsc1, label="i_q VSC1")
axes[4, 0].plot(time_s, i_d_ref_vsc1, "--", label="i_d_ref VSC1")
axes[4, 0].plot(time_s, i_q_ref_vsc1, "--", label="i_q_ref VSC1")
axes[4, 0].set_xlabel("Time [s]")
axes[4, 0].set_ylabel("Current [pu]")
axes[4, 0].set_title("dq currents and references VSC1")
axes[4, 0].grid(True)
axes[4, 0].legend(loc="upper right")

axes[4, 1].plot(time_s, i_d_vsc2, label="i_d VSC2")
axes[4, 1].plot(time_s, i_q_vsc2, label="i_q VSC2")
axes[4, 1].plot(time_s, i_d_ref_vsc2, "--", label="i_d_ref VSC2")
axes[4, 1].plot(time_s, i_q_ref_vsc2, "--", label="i_q_ref VSC2")
axes[4, 1].set_xlabel("Time [s]")
axes[4, 1].set_ylabel("Current [pu]")
axes[4, 1].set_title("dq currents and references VSC2")
axes[4, 1].grid(True)
axes[4, 1].legend(loc="upper right")

figure.tight_layout()

diag_figure, diag_axes = plt.subplots(5, 2, figsize=(16, 18), sharex=True)

diag_axes[0, 0].plot(time_s, i_d_vsc1, label="i_d")
diag_axes[0, 0].plot(time_s, i_d_ref_u_vsc1, "--", label="i_d_ref_u")
diag_axes[0, 0].plot(time_s, i_d_ref_vsc1, ":", label="i_d_ref")
diag_axes[0, 0].plot(time_s, i_d_ff_vsc1, label="i_d_ff")
diag_axes[0, 0].set_ylabel("Current [pu]")
diag_axes[0, 0].set_title("VSC1 d-axis currents")
diag_axes[0, 0].grid(True)
diag_axes[0, 0].legend(loc="upper right")

diag_axes[0, 1].plot(time_s, i_d_vsc2, label="i_d")
diag_axes[0, 1].plot(time_s, i_d_ref_u_vsc2, "--", label="i_d_ref_u")
diag_axes[0, 1].plot(time_s, i_d_ref_vsc2, ":", label="i_d_ref")
diag_axes[0, 1].plot(time_s, i_d_ff_vsc2, label="i_d_ff")
diag_axes[0, 1].set_ylabel("Current [pu]")
diag_axes[0, 1].set_title("VSC2 d-axis currents")
diag_axes[0, 1].grid(True)
diag_axes[0, 1].legend(loc="upper right")

diag_axes[1, 0].plot(time_s, i_q_vsc1, label="i_q")
diag_axes[1, 0].plot(time_s, i_q_ref_u_vsc1, "--", label="i_q_ref_u")
diag_axes[1, 0].plot(time_s, i_q_ref_vsc1, ":", label="i_q_ref")
diag_axes[1, 0].plot(time_s, i_q_ff_vsc1, label="i_q_ff")
diag_axes[1, 0].set_ylabel("Current [pu]")
diag_axes[1, 0].set_title("VSC1 q-axis currents")
diag_axes[1, 0].grid(True)
diag_axes[1, 0].legend(loc="upper right")

diag_axes[1, 1].plot(time_s, i_q_vsc2, label="i_q")
diag_axes[1, 1].plot(time_s, i_q_ref_u_vsc2, "--", label="i_q_ref_u")
diag_axes[1, 1].plot(time_s, i_q_ref_vsc2, ":", label="i_q_ref")
diag_axes[1, 1].plot(time_s, i_q_ff_vsc2, label="i_q_ff")
diag_axes[1, 1].set_ylabel("Current [pu]")
diag_axes[1, 1].set_title("VSC2 q-axis currents")
diag_axes[1, 1].grid(True)
diag_axes[1, 1].legend(loc="upper right")

diag_axes[2, 0].plot(time_s, p_vsc1, label="P")
diag_axes[2, 0].plot(time_s, p_f_vsc1, "--", label="P_f")
diag_axes[2, 0].plot(time_s, q_vsc1, label="Q")
diag_axes[2, 0].plot(time_s, q_f_vsc1, "--", label="Q_f")
diag_axes[2, 0].plot(time_s, vsc1_pdc_ref_trace_pu, ":", label="control1 ref")
diag_axes[2, 0].set_ylabel("Power [pu]")
diag_axes[2, 0].set_title("VSC1 power channels")
diag_axes[2, 0].grid(True)
diag_axes[2, 0].legend(loc="upper right")

diag_axes[2, 1].plot(time_s, p_vsc2, label="P")
diag_axes[2, 1].plot(time_s, p_f_vsc2, "--", label="P_f")
diag_axes[2, 1].plot(time_s, q_vsc2, label="Q")
diag_axes[2, 1].plot(time_s, q_f_vsc2, "--", label="Q_f")
diag_axes[2, 1].plot(time_s, vsc2_pdc_ref_trace_pu, ":", label="control1 ref")
diag_axes[2, 1].set_ylabel("Power [pu]")
diag_axes[2, 1].set_title("VSC2 power channels")
diag_axes[2, 1].grid(True)
diag_axes[2, 1].legend(loc="upper right")

diag_axes[3, 0].plot(time_s, v_cmd_d_u_vsc1, label="v_cmd_d_u")
diag_axes[3, 0].plot(time_s, v_cmd_d_vsc1, "--", label="v_cmd_d")
diag_axes[3, 0].plot(time_s, v_cmd_q_u_vsc1, label="v_cmd_q_u")
diag_axes[3, 0].plot(time_s, v_cmd_q_vsc1, "--", label="v_cmd_q")
diag_axes[3, 0].plot(time_s, v_lim_vsc1, ":", label="v_lim")
diag_axes[3, 0].plot(time_s, -v_lim_vsc1, ":", color="tab:gray")
diag_axes[3, 0].set_ylabel("Voltage [pu]")
diag_axes[3, 0].set_title("VSC1 inner-loop voltage commands")
diag_axes[3, 0].grid(True)
diag_axes[3, 0].legend(loc="upper right")

diag_axes[3, 1].plot(time_s, v_cmd_d_u_vsc2, label="v_cmd_d_u")
diag_axes[3, 1].plot(time_s, v_cmd_d_vsc2, "--", label="v_cmd_d")
diag_axes[3, 1].plot(time_s, v_cmd_q_u_vsc2, label="v_cmd_q_u")
diag_axes[3, 1].plot(time_s, v_cmd_q_vsc2, "--", label="v_cmd_q")
diag_axes[3, 1].plot(time_s, v_lim_vsc2, ":", label="v_lim")
diag_axes[3, 1].plot(time_s, -v_lim_vsc2, ":", color="tab:gray")
diag_axes[3, 1].set_ylabel("Voltage [pu]")
diag_axes[3, 1].set_title("VSC2 inner-loop voltage commands")
diag_axes[3, 1].grid(True)
diag_axes[3, 1].legend(loc="upper right")

diag_axes[4, 0].plot(time_s, i_dc_conv_vsc1, label="i_dc_conv")
diag_axes[4, 0].plot(time_s, v_dc_1, label="v_dc")
diag_axes[4, 0].plot(time_s, k_v_conv_vsc1, label="k_v_conv")
diag_axes[4, 0].set_xlabel("Time [s]")
diag_axes[4, 0].set_ylabel("Mixed")
diag_axes[4, 0].set_title("VSC1 DC-side diagnostics")
diag_axes[4, 0].grid(True)
diag_axes[4, 0].legend(loc="upper right")

diag_axes[4, 1].plot(time_s, i_dc_conv_vsc2, label="i_dc_conv")
diag_axes[4, 1].plot(time_s, v_dc_2, label="v_dc")
diag_axes[4, 1].plot(time_s, k_v_conv_vsc2, label="k_v_conv")
diag_axes[4, 1].set_xlabel("Time [s]")
diag_axes[4, 1].set_ylabel("Mixed")
diag_axes[4, 1].set_title("VSC2 DC-side diagnostics")
diag_axes[4, 1].grid(True)
diag_axes[4, 1].legend(loc="upper right")

diag_figure.tight_layout()
plt.show()
