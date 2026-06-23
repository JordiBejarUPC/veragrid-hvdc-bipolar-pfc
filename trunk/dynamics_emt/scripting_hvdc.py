# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys

SCRIPT_DIR: str = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT: str = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_ROOT: str = os.path.join(REPO_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
else:
    pass

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
else:
    pass

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from typing import Optional

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Templates.Emt.converter_emt_template import get_full_pseudo_emt_converter
from VeraGridEngine.Templates.Emt.dc_line_emt_template import get_dc_line_with_power_input_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.block import Block, build_name_to_var_lookup, find_name_in_block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping_rms import converter_control_code
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.Symbolic.block import Var
from VeraGridEngine.enumerations import ConverterControlType, DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, SolverType
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Events.emt_event import EmtEvent

def get_signal(problem: EmtProblemDae, block: Block, variable_name: str, trajectory: np.ndarray) -> np.ndarray:
    """
    Extract one signal from the EMT result matrix.

    :param problem: EMT problem with the variable index map.
    :param block: Root block where the signal is searched.
    :param variable_name: Symbolic variable name.
    :param trajectory: EMT state trajectory matrix.
    :return: Selected signal trajectory.
    """
    variable: Optional[Var] = find_name_in_block(variable_name, block)

    # Missing optional variables are handled with zeros so plotting never breaks
    # the whole study for one absent signal.
    if variable is not None:
        return np.array(trajectory[:, problem.get_var_idx(variable)], copy=True)
    else:
        print(f"Warning: variable '{variable_name}' was not found in block '{block.name}'.")
        return np.zeros(trajectory.shape[0], dtype=np.float64)


def get_piecewise_reference_trace(
    time_s: np.ndarray,
    initial_value: float,
    events: list[tuple[float, float]],
) -> np.ndarray:
    """
    Reconstruct one runtime-parameter trace for plotting.

    EMT event parameters are runtime inputs, not trajectory variables, so they do not
    appear in `trajectory`.
    """
    trace: np.ndarray = np.full(time_s.shape[0], initial_value, dtype=np.float64)

    event_time_s: float
    event_value: float
    for event_time_s, event_value in sorted(events, key=lambda item: item[0]):
        trace[time_s >= event_time_s] = event_value

    return trace


####################################################################################################################
# Build VeraGrid object
####################################################################################################################

sbase_mva: float = 100.0
fbase_hz: float = 50.0
ac_voltage_ll_kv: float = 90.0
dc_voltage_kv: float = 145.0
grid_resistance_ohm: float = 4.8 * 0.669
grid_inductance_h: float = 0.052 * 0.669
coupling_resistance_ohm: float = 3.68 / 10.0
coupling_inductance_h: float = 30.0e-3
inner_loop_tau_s: float = 1.0 / 3100.0

simulation_time_s: float = 0.45
time_step_s: float = 2.0e-5
q_setpoint_1_mvar: float = 0.0
q_setpoint_2_mvar: float = 0.0
transfer_power_mw: float = 40.0
transfer_power_pu: float = transfer_power_mw / sbase_mva
print(f"transfer_power_pu={transfer_power_pu}")
idle_power_pu: float = 1.0e-6
pulse_power_pu: float = transfer_power_pu
# reactive power setpoints
q_setpoint_1_pu: float = q_setpoint_1_mvar / sbase_mva
q_setpoint_2_pu: float = q_setpoint_2_mvar / sbase_mva

tau = 1/3100

grid: gce.MultiCircuit = gce.MultiCircuit(
    name="Point-to-point HVDC EMT example",
    Sbase=sbase_mva,
    fbase=fbase_hz,
)

ac_base_impedance_ohm: float = (ac_voltage_ll_kv * ac_voltage_ll_kv) / sbase_mva
dc_base_impedance_ohm: float = (dc_voltage_kv * dc_voltage_kv) / sbase_mva
omega_base_rad_s: float = 2.0 * np.pi * fbase_hz
dc_base_inductance_h: float = dc_base_impedance_ohm / omega_base_rad_s
dc_base_capacitance_f: float = 1.0 / (omega_base_rad_s * dc_base_impedance_ohm)
grid_r_pu: float = grid_resistance_ohm / ac_base_impedance_ohm
print(f"grid_r_pu = {grid_r_pu}")
grid_x_pu: float = omega_base_rad_s * grid_inductance_h / ac_base_impedance_ohm
print(f"grid_x_pu = {grid_x_pu}")
coupling_r_pu: float = coupling_resistance_ohm / ac_base_impedance_ohm
coupling_x_pu: float = omega_base_rad_s * coupling_inductance_h / ac_base_impedance_ohm
# the dc line impedance is averaged
dc_line_r_pu: float = (0.5 + 0.25 + 0.4) / dc_base_impedance_ohm
dc_line_r1_pu: float = 0.5 / dc_base_impedance_ohm
dc_line_r2_pu: float = 0.25 / dc_base_impedance_ohm
dc_line_r3_pu: float = 0.4 / dc_base_impedance_ohm
dc_line_l1_pu: float = 0.005 / dc_base_inductance_h
dc_line_l2_pu: float = 0.0025 / dc_base_inductance_h
dc_line_l3_pu: float = 0.004 / dc_base_inductance_h
dc_line_capacitor_pu: float = 150.0e-6 / dc_base_capacitance_f
print(f"dc_line_r_pu = {dc_line_r_pu}")

# The averaged pseudo-VSC already includes its own internal AC interface branch.
# Reuse the parameter range validated by the standalone pseudo-converter example
# instead of retuning the inner loop from the external grid-coupling branch.
converter_filter_r_pu: float = 0.03
converter_filter_x_pu: float = 0.12

sample_time = 1/12e3
# current loop PI
current_kp: float = coupling_inductance_h / tau
current_ki: float = coupling_resistance_ohm / tau
print(f"current_kp = {current_kp}")
print(f"current_ki = {current_ki}")
converter_model_sbase_pu: float = 1.0
dc_link_capacitance_pu: float = 0.8
i_max_default_pu: float = 1.3
m_max_default_pu: float = 0.95
tau_meas_default_s: float = 0.01
aw_gain_default: float = 0.1

# The outer Vdc/Q loops act on current references, so they must stay much slower
# than the inner current controller to avoid ill-conditioned EMT initialization.
vdc_kp_vsc1: float = 1.5
vdc_ki_vsc1: float = 12.0
vdc_kp_vsc2: float = 1.5
vdc_ki_vsc2: float = 12.0

q_kp_vsc1: float = 0.8
q_ki_vsc1: float = 20.0
q_kp_vsc2: float = 0.8
q_ki_vsc2: float = 20.0

loss_linear_pu: float = 0.0
loss_quadratic_pu: float = 0.0

####################################################################################################################
# Create buses
####################################################################################################################

bus_grid_1: gce.Bus = gce.Bus(name="Bus_Grid_1", Vnom=ac_voltage_ll_kv, is_slack=True)
bus_dc_1: gce.Bus = gce.Bus(name="Bus_DC_1", Vnom=dc_voltage_kv, is_dc=True)
bus_dc_2: gce.Bus = gce.Bus(name="Bus_DC_2", Vnom=dc_voltage_kv, is_dc=True)
bus_grid_2: gce.Bus = gce.Bus(name="Bus_Grid_2", Vnom=ac_voltage_ll_kv, is_slack=True)

grid.add_bus(bus_grid_1)
grid.add_bus(bus_dc_1)
grid.add_bus(bus_dc_2)
grid.add_bus(bus_grid_2)

####################################################################################################################
# Create devices
####################################################################################################################

# Two Thevenin generators represent the external AC grids seen at each PCC.
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

# Match the stable arrangement from `scripting_hvdc_v2.py`: converter 1 holds
# DC voltage and converter 2 receives the active-power step.
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

# The static DC line stays resistive for power flow, while the EMT RL behavior is
# injected later through a custom symbolic EMT template.
dc_line: gce.DcLine = gce.DcLine(
    name="HVDC_Line",
    bus_from=bus_dc_1,
    bus_to=bus_dc_2,
    r=dc_line_r_pu,
    rate=sbase_mva,
)
grid.add_dc_line(dc_line)

####################################################################################################################
# Build EMT bus shells and device EMT models
####################################################################################################################

# Every branch model later connects to the bus EMT shell voltages, so the bus shells
# must exist before attaching the branch and converter models.
bus: gce.Bus
for bus in grid.buses:
    get_bus_emt_template(grid, bus)

generator_1_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="grid1_thevenin_emt").block
generator_2_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="grid2_thevenin_emt").block
converter_1_mdl: Block = get_full_pseudo_emt_converter(vf=grid.var_factory, name="vsc1_pseudo_emt").block
converter_2_mdl: Block = get_full_pseudo_emt_converter(vf=grid.var_factory, name="vsc2_pseudo_emt").block
dc_line_mdl: Block = get_dc_line_with_power_input_emt_template(vf=grid.var_factory, name="hvdc_line_power_input_emt").block

# Converter 1 is the DC-voltage-regulating terminal in EMT.
converter_1_mdl.set_parameter_in_model(var_name="sbase_vsc1_pseudo_emt", new_value=converter_model_sbase_pu)
converter_1_mdl.set_parameter_in_model(var_name="omega_base_vsc1_pseudo_emt", new_value=omega_base_rad_s)
converter_1_mdl.set_parameter_in_model(var_name="control1_vsc1_pseudo_emt", new_value=converter_control_code(ConverterControlType.Vm_dc))
converter_1_mdl.set_parameter_in_model(var_name="control2_vsc1_pseudo_emt", new_value=converter_control_code(ConverterControlType.Qac))
converter_1_mdl.set_parameter_in_model(var_name="control1_val_vsc1_pseudo_emt", new_value=1.0) # Vdc
converter_1_mdl.set_parameter_in_model(var_name="control2_val_vsc1_pseudo_emt", new_value=q_setpoint_1_pu) # Qac
converter_1_mdl.set_parameter_in_model(var_name="R_eq_vsc1_pseudo_emt", new_value=coupling_resistance_ohm)
converter_1_mdl.set_parameter_in_model(var_name="L_eq_vsc1_pseudo_emt", new_value=coupling_inductance_h)
converter_1_mdl.set_parameter_in_model(var_name="C_dc_vsc1_pseudo_emt", new_value=dc_link_capacitance_pu)
converter_1_mdl.set_parameter_in_model(var_name="R_dc_vsc1_pseudo_emt", new_value=1e6)
converter_1_mdl.set_parameter_in_model(var_name="R_dc_term_vsc1_pseudo_emt", new_value=0.0001)
converter_1_mdl.set_parameter_in_model(var_name="P0_vsc1_pseudo_emt", new_value=idle_power_pu)
converter_1_mdl.set_parameter_in_model(var_name="pll_kp_vsc1_pseudo_emt", new_value=40.0)
converter_1_mdl.set_parameter_in_model(var_name="pll_ki_vsc1_pseudo_emt", new_value=400.0)
converter_1_mdl.set_parameter_in_model(var_name="i_kp_vsc1_pseudo_emt", new_value=current_kp)
converter_1_mdl.set_parameter_in_model(var_name="i_ki_vsc1_pseudo_emt", new_value=current_ki)
converter_1_mdl.set_parameter_in_model(var_name="vdc_kp_vsc1_pseudo_emt", new_value=vdc_kp_vsc1)
converter_1_mdl.set_parameter_in_model(var_name="vdc_ki_vsc1_pseudo_emt", new_value=vdc_ki_vsc1)
converter_1_mdl.set_parameter_in_model(var_name="q_kp_vsc1_pseudo_emt", new_value=q_kp_vsc1)
converter_1_mdl.set_parameter_in_model(var_name="q_ki_vsc1_pseudo_emt", new_value=q_ki_vsc1)
converter_1_mdl.set_parameter_in_model(var_name="i_max_vsc1_pseudo_emt", new_value=i_max_default_pu)
converter_1_mdl.set_parameter_in_model(var_name="m_max_vsc1_pseudo_emt", new_value=m_max_default_pu)
converter_1_mdl.set_parameter_in_model(var_name="P_loss_i1_vsc1_pseudo_emt", new_value=loss_linear_pu)
converter_1_mdl.set_parameter_in_model(var_name="P_loss_i2_vsc1_pseudo_emt", new_value=loss_quadratic_pu)
converter_1_mdl.set_parameter_in_model(var_name="tau_meas_vsc1_pseudo_emt", new_value=tau_meas_default_s)
converter_1_mdl.set_parameter_in_model(var_name="aw_gain_vsc1_pseudo_emt", new_value=aw_gain_default)
converter_1_mdl.set_parameter_in_model(var_name="vdc_floor_vsc1_pseudo_emt", new_value=0.05)
converter_1_mdl.set_parameter_in_model(var_name="Vdc_nom_vsc1_pseudo_emt", new_value=1.0)

# Converter 2 is the active-power-controlled terminal in EMT.
converter_2_mdl.set_parameter_in_model(var_name="sbase_vsc2_pseudo_emt", new_value=converter_model_sbase_pu)
converter_2_mdl.set_parameter_in_model(var_name="omega_base_vsc2_pseudo_emt", new_value=omega_base_rad_s)
converter_2_mdl.set_parameter_in_model(var_name="control1_vsc2_pseudo_emt", new_value=converter_control_code(ConverterControlType.Pdc))
converter_2_mdl.set_parameter_in_model(var_name="control2_vsc2_pseudo_emt", new_value=converter_control_code(ConverterControlType.Qac))
converter_2_mdl.set_parameter_in_model(var_name="control1_val_vsc2_pseudo_emt", new_value=idle_power_pu) # Pdc
converter_2_mdl.set_parameter_in_model(var_name="control2_val_vsc2_pseudo_emt", new_value=q_setpoint_2_pu) # Qac
converter_2_mdl.set_parameter_in_model(var_name="R_eq_vsc2_pseudo_emt", new_value=coupling_resistance_ohm)
converter_2_mdl.set_parameter_in_model(var_name="L_eq_vsc2_pseudo_emt", new_value=coupling_inductance_h)
converter_2_mdl.set_parameter_in_model(var_name="C_dc_vsc2_pseudo_emt", new_value=dc_link_capacitance_pu)
converter_2_mdl.set_parameter_in_model(var_name="R_dc_vsc2_pseudo_emt", new_value=1e6)
converter_2_mdl.set_parameter_in_model(var_name="R_dc_term_vsc2_pseudo_emt", new_value=0.0001)
converter_2_mdl.set_parameter_in_model(var_name="P0_vsc2_pseudo_emt", new_value=idle_power_pu)
converter_2_mdl.set_parameter_in_model(var_name="pll_kp_vsc2_pseudo_emt", new_value=40.0)
converter_2_mdl.set_parameter_in_model(var_name="pll_ki_vsc2_pseudo_emt", new_value=400.0)
converter_2_mdl.set_parameter_in_model(var_name="i_kp_vsc2_pseudo_emt", new_value=current_kp)
converter_2_mdl.set_parameter_in_model(var_name="i_ki_vsc2_pseudo_emt", new_value=current_ki)
converter_2_mdl.set_parameter_in_model(var_name="vdc_kp_vsc2_pseudo_emt", new_value=vdc_kp_vsc2)
converter_2_mdl.set_parameter_in_model(var_name="vdc_ki_vsc2_pseudo_emt", new_value=vdc_ki_vsc2)
converter_2_mdl.set_parameter_in_model(var_name="q_kp_vsc2_pseudo_emt", new_value=q_kp_vsc2)
converter_2_mdl.set_parameter_in_model(var_name="q_ki_vsc2_pseudo_emt", new_value=q_ki_vsc2)
converter_2_mdl.set_parameter_in_model(var_name="i_max_vsc2_pseudo_emt", new_value=i_max_default_pu)
converter_2_mdl.set_parameter_in_model(var_name="m_max_vsc2_pseudo_emt", new_value=m_max_default_pu)
converter_2_mdl.set_parameter_in_model(var_name="P_loss_i1_vsc2_pseudo_emt", new_value=loss_linear_pu)
converter_2_mdl.set_parameter_in_model(var_name="P_loss_i2_vsc2_pseudo_emt", new_value=loss_quadratic_pu)
converter_2_mdl.set_parameter_in_model(var_name="tau_meas_vsc2_pseudo_emt", new_value=tau_meas_default_s)
converter_2_mdl.set_parameter_in_model(var_name="aw_gain_vsc2_pseudo_emt", new_value=aw_gain_default)
converter_2_mdl.set_parameter_in_model(var_name="vdc_floor_vsc2_pseudo_emt", new_value=0.05)
converter_2_mdl.set_parameter_in_model(var_name="Vdc_nom_vsc2_pseudo_emt", new_value=1.0)

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



####################################################################################################################
# Attach EMT models to devices
####################################################################################################################

# The static objects and EMT blocks are attached here so the EMT problem builder can
# traverse one grid object and recover both topology and equations.
set_emt_model(device=generator_1, model=generator_1_mdl, var_factory=grid.var_factory)
set_emt_model(device=generator_2, model=generator_2_mdl, var_factory=grid.var_factory)
set_emt_model(device=converter_1, model=converter_1_mdl, var_factory=grid.var_factory)
set_emt_model(device=converter_2, model=converter_2_mdl, var_factory=grid.var_factory)
set_emt_model(device=dc_line, model=dc_line_mdl, var_factory=grid.var_factory)

####################################################################################################################
# Event
####################################################################################################################

events_group = EmtEventsGroup("simulation1")
grid.add_emt_events_group(events_group)
dc_line_name_lookup = build_name_to_var_lookup(dc_line_mdl)
p_ext_var = dc_line_name_lookup.get("Pext_hvdc_line_power_input_emt")
vsc2_control1_var = build_name_to_var_lookup(converter_2_mdl).get("control1_val_vsc2_pseudo_emt")

if p_ext_var is None:
    raise RuntimeError("Could not resolve event parameter 'Pext_hvdc_line_power_input_emt'.")
if vsc2_control1_var is None:
    raise RuntimeError("Could not resolve event parameter 'control1_val_vsc2_pseudo_emt'.")

p_ext_events: list[tuple[float, float]] = [
    (0.2, idle_power_pu),
    (0.35, idle_power_pu),
]
event_times_and_values_vsc2: list[tuple[float, float]] = [
    (0.2, pulse_power_pu),
    (0.35, idle_power_pu),
]
grid.add_emt_event(EmtEvent(device=dc_line, parameter=p_ext_var, time=p_ext_events[0][0], value=p_ext_events[0][1], group=events_group))
grid.add_emt_event(EmtEvent(device=dc_line, parameter=p_ext_var, time=p_ext_events[1][0], value=p_ext_events[1][1], group=events_group))
grid.add_emt_event(EmtEvent(device=converter_2, parameter=vsc2_control1_var, time=event_times_and_values_vsc2[0][0], value=event_times_and_values_vsc2[0][1], group=events_group))
grid.add_emt_event(EmtEvent(device=converter_2, parameter=vsc2_control1_var, time=event_times_and_values_vsc2[1][0], value=event_times_and_values_vsc2[1][1], group=events_group))

####################################################################################################################
# Balanced AC/DC power flow
####################################################################################################################

# The balanced power flow creates the steady-state point that seeds the EMT initial values.
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

# # No EMT events are applied. Seed converter 1 with the opposite active-power
# # feedforward so the link starts from the intended steady state.
# converter_1_mdl.set_parameter_in_model(var_name="P0_vsc1_pseudo_emt", new_value=-transfer_power_pu)


####################################################################################################################
# EMT problem
####################################################################################################################

# Explicit initialization is used because the EMT study now starts directly from the
# loaded power-flow point and does not need any scheduled reference step.
emt_options: EmtOptions = EmtOptions(
    time_step=time_step_s,
    simulation_time=simulation_time_s,
    tolerance=1e-6,
    solver_type=EmtSolverTypes.StructuralCompiled,
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
else:
    print("The EMT initialization report is not available.")

####################################################################################################################
# EMT solver
####################################################################################################################

# Reuse the compiled pseudo-EMT execution path used by the stable steady-state
# HVDC configuration.
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

time_s: np.ndarray
trajectory: np.ndarray
diff_trajectory: np.ndarray
well_initialized: bool
converged: bool
time_s, trajectory, diff_trajectory, well_initialized, converged = solver.simulate()

if diff_trajectory.shape[0] >= 0:
    pass
else:
    print("Warning: unexpected differential trajectory shape returned by the solver.")

print("=" * 80)
print("EMT SIMULATION REPORT")
print("=" * 80)
print(f"well_initialized = {well_initialized}")
print(f"converged        = {converged}")

if converged is False:
    print("The EMT solver did not converge for the requested horizon.")


####################################################################################################################
# Build signals for plotting
####################################################################################################################

# Runtime event parameters are not part of the state trajectory, so reconstruct the command traces.
power_reference_trace_pu_1: np.ndarray = get_piecewise_reference_trace(
    time_s=time_s,
    initial_value=idle_power_pu,
    events=event_times_and_values_vsc2,
)

v_pcc1_a: np.ndarray = get_signal(problem, bus_grid_1.emt_model, f"v_A_{bus_grid_1.name}_emt_template", trajectory)
v_pcc1_b: np.ndarray = get_signal(problem, bus_grid_1.emt_model, f"v_B_{bus_grid_1.name}_emt_template", trajectory)
v_pcc1_c: np.ndarray = get_signal(problem, bus_grid_1.emt_model, f"v_C_{bus_grid_1.name}_emt_template", trajectory)
v_pcc2_a: np.ndarray = get_signal(problem, bus_grid_2.emt_model, f"v_A_{bus_grid_2.name}_emt_template", trajectory)
v_pcc2_b: np.ndarray = get_signal(problem, bus_grid_2.emt_model, f"v_B_{bus_grid_2.name}_emt_template", trajectory)
v_pcc2_c: np.ndarray = get_signal(problem, bus_grid_2.emt_model, f"v_C_{bus_grid_2.name}_emt_template", trajectory)
i_vsc1_a: np.ndarray = get_signal(problem, converter_1_mdl, "i_A_vsc1_pseudo_emt", trajectory)
i_vsc1_b: np.ndarray = get_signal(problem, converter_1_mdl, "i_B_vsc1_pseudo_emt", trajectory)
i_vsc1_c: np.ndarray = get_signal(problem, converter_1_mdl, "i_C_vsc1_pseudo_emt", trajectory)
i_vsc2_a: np.ndarray = get_signal(problem, converter_2_mdl, "i_A_vsc2_pseudo_emt", trajectory)
i_vsc2_b: np.ndarray = get_signal(problem, converter_2_mdl, "i_B_vsc2_pseudo_emt", trajectory)
i_vsc2_c: np.ndarray = get_signal(problem, converter_2_mdl, "i_C_vsc2_pseudo_emt", trajectory)
v_dc_1: np.ndarray = get_signal(problem, bus_dc_1.emt_model, f"v_DC_{bus_dc_1.name}_emt_template", trajectory)
v_dc_2: np.ndarray = get_signal(problem, bus_dc_2.emt_model, f"v_DC_{bus_dc_2.name}_emt_template", trajectory)
i_line: np.ndarray = get_signal(problem, dc_line_mdl, "i_f_dc_hvdc_line_power_input_emt", trajectory)
p_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "P_vsc1_pseudo_emt", trajectory)
q_vsc1: np.ndarray = get_signal(problem, converter_1_mdl, "Q_vsc1_pseudo_emt", trajectory)
p_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "P_vsc2_pseudo_emt", trajectory)
q_vsc2: np.ndarray = get_signal(problem, converter_2_mdl, "Q_vsc2_pseudo_emt", trajectory)

####################################################################################################################
# Plot results
####################################################################################################################

# The plot layout groups AC terminal quantities, DC corridor quantities and converter powers.
figure, axes = plt.subplots(4, 2, figsize=(16, 14), sharex=True)

axes[0, 0].plot(time_s, v_pcc1_a, label="Va PCC1")
axes[0, 0].plot(time_s, v_pcc1_b, label="Vb PCC1")
axes[0, 0].plot(time_s, v_pcc1_c, label="Vc PCC1")
axes[0, 0].set_ylabel("Voltage [pu]")
axes[0, 0].set_title("Converter 1 AC terminal voltages")
axes[0, 0].grid(True)
axes[0, 0].legend(loc="upper right")

axes[0, 1].plot(time_s, v_pcc2_a, label="Va PCC2")
axes[0, 1].plot(time_s, v_pcc2_b, label="Vb PCC2")
axes[0, 1].plot(time_s, v_pcc2_c, label="Vc PCC2")
axes[0, 1].set_ylabel("Voltage [pu]")
axes[0, 1].set_title("Converter 2 AC terminal voltages")
axes[0, 1].grid(True)
axes[0, 1].legend(loc="upper right")

axes[1, 0].plot(time_s, i_vsc1_a, label="Ia VSC1")
axes[1, 0].plot(time_s, i_vsc1_b, label="Ib VSC1")
axes[1, 0].plot(time_s, i_vsc1_c, label="Ic VSC1")
axes[1, 0].set_ylabel("Current [pu]")
axes[1, 0].set_title("Converter 1 AC currents")
axes[1, 0].grid(True)
axes[1, 0].legend(loc="upper right")

axes[1, 1].plot(time_s, i_vsc2_a, label="Ia VSC2")
axes[1, 1].plot(time_s, i_vsc2_b, label="Ib VSC2")
axes[1, 1].plot(time_s, i_vsc2_c, label="Ic VSC2")
axes[1, 1].set_ylabel("Current [pu]")
axes[1, 1].set_title("Converter 2 AC currents")
axes[1, 1].grid(True)
axes[1, 1].legend(loc="upper right")

axes[2, 0].plot(time_s, v_dc_1, label="Vdc bus 1")
axes[2, 0].plot(time_s, v_dc_2, label="Vdc bus 2")
axes[2, 0].set_ylabel("Voltage [pu]")
axes[2, 0].set_title("DC bus voltages")
axes[2, 0].grid(True)
axes[2, 0].legend(loc="upper right")

axes[2, 1].plot(time_s, i_line, label="HVDC line current")
axes[2, 1].set_ylabel("Current [pu]")
axes[2, 1].set_title("HVDC line current")
axes[2, 1].grid(True)
axes[2, 1].legend(loc="upper right")

axes[3, 0].plot(time_s, power_reference_trace_pu_1, "--", label="P ref VSC1")
axes[3, 0].plot(time_s, p_vsc1, label="P VSC1")
axes[3, 0].plot(time_s, q_vsc1, label="Q VSC1")
axes[3, 0].set_xlabel("Time [s]")
axes[3, 0].set_ylabel("Power [pu]")
axes[3, 0].set_title("Converter 1 active/reactive power")
axes[3, 0].grid(True)
axes[3, 0].legend(loc="upper right")

axes[3, 1].plot(time_s, p_vsc2, label="P VSC2")
axes[3, 1].plot(time_s, q_vsc2, label="Q VSC2")
axes[3, 1].set_xlabel("Time [s]")
axes[3, 1].set_ylabel("Power [pu]")
axes[3, 1].set_title("Converter 2 active/reactive power and VSC1 reference")
axes[3, 1].grid(True)
axes[3, 1].legend(loc="upper right")

figure.tight_layout()
# figure.savefig(os.path.join(SCRIPT_DIR, "scripting_hvdc_results.png"), dpi=150, bbox_inches="tight")
# plt.close(figure)
