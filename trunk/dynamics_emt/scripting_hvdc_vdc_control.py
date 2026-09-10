# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys
from typing import Any, Optional

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Dynamic.static_parameter_mapping import converter_control_code
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Templates.Emt.converter_emt_template import get_full_pseudo_emt_converter
from VeraGridEngine.Templates.Emt.dc_line_vdc_control_emt_template import get_dc_line_with_vdc_control_emt_template
from VeraGridEngine.Templates.Emt.dc_line_emt_template import get_dc_line_with_power_input_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.block import Block, Var, build_name_to_var_lookup, find_name_in_block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DynamicEventTransitionType,
    DynamicIntegrationMethod,
    EmtInitializationMethod,
    EmtSolverTypes,
    SolverType,
)


def get_signal(problem: EmtProblemDae, block: Block, variable_name: str, trajectory: np.ndarray) -> np.ndarray:
    variable: Optional[Var] = find_name_in_block(variable_name, block)
    if variable is not None:
        return np.array(trajectory[:, problem.get_var_idx(variable)], copy=True)

    print(f"Warning: variable '{variable_name}' was not found in block '{block.name}'.")
    return np.zeros(trajectory.shape[0], dtype=np.float64)


def get_event_reference_trace(
        time_s: np.ndarray,
        initial_value: float,
        events: list[tuple[float, float, Optional[float], DynamicEventTransitionType]],
) -> np.ndarray:
    trace = np.full(time_s.shape[0], initial_value, dtype=np.float64)
    current_value = initial_value

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


def run_hvdc_vdc_control_simulation(
        simulation_time_s: float = 0.12,
        time_step_s: float = 2.0e-5,
        solver_type: EmtSolverTypes = EmtSolverTypes.StructuralCompiled,
        integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
        enable_vdc_reference_event: bool = True,
        use_line_vdc_control: bool = True,
        power_event_time_s: float = 0.04,
        vdc_event_time_s: float = 0.08,
        transfer_power_pu: float = 0.20,
        vdc_event_value_pu: float = 1.02,
        plot: bool = True,
        save_grid_filename: Optional[str] = os.path.join(SCRIPT_DIR, "hvdc_vdc_control.veragrid"),
) -> dict[str, Any]:
    sbase_mva = 100.0
    fbase_hz = 50.0
    ac_voltage_ll_kv = 90.0
    dc_voltage_kv = 145.0
    grid_resistance_ohm = 4.8 * 0.669
    grid_inductance_h = 0.052 * 0.669
    coupling_resistance_ohm = 3.68 / 10.0
    coupling_inductance_h = 30.0e-3
    idle_power_pu = 1.0e-6

    q_setpoint_1_pu = 0.0
    q_setpoint_2_pu = 0.0
    tau = 1.0 / 3100.0
    # The pseudo-converter current plant is written on electrical-angle time,
    # i.e. di/dt = omega_base/L * (...).  Include that omega_base factor when
    # placing the PI pole at 1/tau; omitting it makes the loop ~314 times too
    # aggressive at 50 Hz.
    omega_base_rad_s = 2.0 * np.pi * fbase_hz
    current_kp = coupling_inductance_h / (omega_base_rad_s * tau)
    current_ki = coupling_resistance_ohm / (omega_base_rad_s * tau)

    grid = gce.MultiCircuit(name="Point-to-point HVDC EMT Vdc-control example", Sbase=sbase_mva, fbase=fbase_hz)

    ac_base_impedance_ohm = (ac_voltage_ll_kv * ac_voltage_ll_kv) / sbase_mva
    dc_base_impedance_ohm = (dc_voltage_kv * dc_voltage_kv) / sbase_mva
    dc_base_inductance_h = dc_base_impedance_ohm / omega_base_rad_s
    dc_base_capacitance_f = 1.0 / (omega_base_rad_s * dc_base_impedance_ohm)

    grid_r_pu = grid_resistance_ohm / ac_base_impedance_ohm
    grid_x_pu = omega_base_rad_s * grid_inductance_h / ac_base_impedance_ohm
    dc_line_r_pu = (0.5 + 0.25 + 0.4) / dc_base_impedance_ohm
    dc_line_r1_pu = 0.5 / dc_base_impedance_ohm
    dc_line_r2_pu = 0.25 / dc_base_impedance_ohm
    dc_line_r3_pu = 0.4 / dc_base_impedance_ohm
    dc_line_l1_pu = 0.005 / dc_base_inductance_h
    dc_line_l2_pu = 0.0025 / dc_base_inductance_h
    dc_line_l3_pu = 0.004 / dc_base_inductance_h
    dc_line_capacitor_pu = 150.0e-6 / dc_base_capacitance_f

    bus_grid_1 = gce.Bus(name="Bus_Grid_1", Vnom=ac_voltage_ll_kv, is_slack=True)
    bus_dc_1 = gce.Bus(name="Bus_DC_1", Vnom=dc_voltage_kv, is_dc=True)
    bus_dc_2 = gce.Bus(name="Bus_DC_2", Vnom=dc_voltage_kv, is_dc=True)
    bus_grid_2 = gce.Bus(name="Bus_Grid_2", Vnom=ac_voltage_ll_kv, is_slack=True)
    for bus in (bus_grid_1, bus_dc_1, bus_dc_2, bus_grid_2):
        grid.add_bus(bus)

    generator_1 = gce.Generator(name="Generator_Grid_1", vset=1.0, Snom=sbase_mva, freq=fbase_hz, r1=grid_r_pu, x1=grid_x_pu)
    generator_2 = gce.Generator(name="Generator_Grid_2", vset=1.0, Snom=sbase_mva, freq=fbase_hz, r1=grid_r_pu, x1=grid_x_pu)
    grid.add_generator(bus_grid_1, generator_1)
    grid.add_generator(bus_grid_2, generator_2)

    converter_1 = gce.VSC(
        name="VSC_1",
        bus_from=bus_dc_1,
        bus_to=bus_grid_1,
        rate=sbase_mva,
        control1=ConverterControlType.Vm_dc,
        control2=ConverterControlType.Qac,
        control1_val=1.0,
        control2_val=q_setpoint_1_pu,
    )
    converter_2 = gce.VSC(
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

    dc_line = gce.DcLine(name="HVDC_Line", bus_from=bus_dc_1, bus_to=bus_dc_2, r=dc_line_r_pu, rate=sbase_mva)
    grid.add_dc_line(dc_line)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    generator_1_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="grid1_thevenin_emt").block
    generator_2_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory, name="grid2_thevenin_emt").block
    converter_1_mdl = get_full_pseudo_emt_converter(vf=grid.var_factory, name="vsc1_pseudo_emt").block
    converter_2_mdl = get_full_pseudo_emt_converter(vf=grid.var_factory, name="vsc2_pseudo_emt").block
    if use_line_vdc_control:
        dc_line_mdl = get_dc_line_with_vdc_control_emt_template(
            vf=grid.var_factory,
            name="hvdc_line_vdc_control_emt",
        ).block
    else:
        dc_line_mdl = get_dc_line_with_power_input_emt_template(
            vf=grid.var_factory,
            name="hvdc_line_passive_emt",
        ).block
        dc_line_mdl.set_parameter_in_model("Pext", 0.0)

    for converter_mdl, suffix, control1_type, control1_value, q_setpoint_pu in [
        (converter_1_mdl, "vsc1_pseudo_emt", ConverterControlType.Vm_dc, 1.0, q_setpoint_1_pu),
        (converter_2_mdl, "vsc2_pseudo_emt", ConverterControlType.Pdc, idle_power_pu, q_setpoint_2_pu),
    ]:
        converter_mdl.set_parameter_in_model("sbase", 1.0)
        converter_mdl.set_parameter_in_model("omega_base", omega_base_rad_s)
        converter_mdl.set_parameter_in_model("control1", converter_control_code(control1_type))
        converter_mdl.set_parameter_in_model("control2", converter_control_code(ConverterControlType.Qac))
        converter_mdl.set_parameter_in_model("control1_val", control1_value)
        converter_mdl.set_parameter_in_model("control2_val", q_setpoint_pu)
        converter_mdl.set_parameter_in_model("R_eq", coupling_resistance_ohm)
        converter_mdl.set_parameter_in_model("L_eq", coupling_inductance_h)
        converter_mdl.set_parameter_in_model("C_dc", 0.8)
        converter_mdl.set_parameter_in_model("R_dc", 1.0e6)
        converter_mdl.set_parameter_in_model("R_dc_term", 1.0e-4)
        converter_mdl.set_parameter_in_model("P0", idle_power_pu)
        converter_mdl.set_parameter_in_model("pll_kp", 40.0)
        converter_mdl.set_parameter_in_model("pll_ki", 400.0)
        converter_mdl.set_parameter_in_model("i_kp", current_kp)
        converter_mdl.set_parameter_in_model("i_ki", current_ki)
        converter_mdl.set_parameter_in_model("vdc_kp", 1.0)
        converter_mdl.set_parameter_in_model("vdc_ki", 10.0)
        converter_mdl.set_parameter_in_model("q_kp", 0.8)
        converter_mdl.set_parameter_in_model("q_ki", 20.0)
        converter_mdl.set_parameter_in_model("i_max", 1.4)
        converter_mdl.set_parameter_in_model("m_max", 0.97)
        converter_mdl.set_parameter_in_model("P_loss_i1", 0.0)
        converter_mdl.set_parameter_in_model("P_loss_i2", 0.0)
        converter_mdl.set_parameter_in_model("tau_meas", 0.003)
        converter_mdl.set_parameter_in_model("aw_gain", 0.1)
        converter_mdl.set_parameter_in_model("vdc_floor", 0.05)
        converter_mdl.set_parameter_in_model("Vdc_nom", 1.0)

    for name, value in [
        ("R1", dc_line_r1_pu),
        ("L1", dc_line_l1_pu),
        ("R2", dc_line_r2_pu),
        ("L2", dc_line_l2_pu),
        ("R3", dc_line_r3_pu),
        ("L3", dc_line_l3_pu),
        ("C_end_f", dc_line_capacitor_pu),
        ("C_mid_1", dc_line_capacitor_pu),
        ("C_mid_2", dc_line_capacitor_pu),
        ("C_end_t", dc_line_capacitor_pu),
        ("P0", idle_power_pu),
        ("Vdc_ref", 1.0),
        ("Kp_vdc", -0.8),
        ("Ki_vdc", -8.0),
    ]:
        dc_line_mdl.set_parameter_in_model(var_name=name, new_value=value)

    set_emt_model(generator_1, generator_1_mdl, grid.var_factory)
    set_emt_model(generator_2, generator_2_mdl, grid.var_factory)
    set_emt_model(converter_1, converter_1_mdl, grid.var_factory)
    set_emt_model(converter_2, converter_2_mdl, grid.var_factory)
    set_emt_model(dc_line, dc_line_mdl, grid.var_factory)

    events_group = EmtEventsGroup("vdc_control")
    grid.add_emt_events_group(events_group)

    vsc2_reference_events = [(power_event_time_s, transfer_power_pu, None, DynamicEventTransitionType.Step)]
    vdc_reference_events = [(vdc_event_time_s, vdc_event_value_pu, None, DynamicEventTransitionType.Step)] if enable_vdc_reference_event else []

    vsc2_control1_var = build_name_to_var_lookup(converter_2_mdl).get("control1_val")
    vdc_control_device = dc_line if use_line_vdc_control else converter_1
    vdc_ref_var = build_name_to_var_lookup(
        dc_line_mdl if use_line_vdc_control else converter_1_mdl
    ).get("Vdc_ref" if use_line_vdc_control else "control1_val")
    if vsc2_control1_var is None or vdc_ref_var is None:
        raise RuntimeError("Could not resolve EMT event parameters for the HVDC Vdc-control case.")

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

    for event_time_s, event_value, end_time_s, transition_type in vdc_reference_events:
        grid.add_emt_event(EmtEvent(
            device=vdc_control_device,
            parameter=vdc_ref_var,
            time=event_time_s,
            end_time=end_time_s,
            value=event_value,
            group=events_group,
            transition_type=transition_type,
        ))

    if save_grid_filename is not None:
        gce.save_file(grid=grid, filename=save_grid_filename)
    else:
        pass

    pf_options = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=False,
        tolerance=1.0e-6,
        max_iter=30,
        control_q=True,
        control_taps_modules=False,
        control_taps_phase=False,
        orthogonalize_controls=False,
    )
    pf_results = gce.power_flow(grid=grid, options=pf_options)

    emt_options = EmtOptions(
        time_step=time_step_s,
        simulation_time=simulation_time_s,
        tolerance=1.0e-6,
        solver_type=solver_type,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=integration_method,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=emt_options, pf_results_3ph=None, pf_results=pf_results)
    problem.set_events_group(events_group)

    solver = build_emt_solver(
        options=emt_options,
        problem=problem,
        t0=0.0,
        t_end=simulation_time_s,
        h=time_step_s,
        method=integration_method,
    )
    time_s, trajectory, diff_trajectory, well_initialized, converged = solver.simulate()

    signals = {
        "v_dc_1": get_signal(problem, bus_dc_1.emt_model, "v_DC", trajectory),
        "v_dc_2": get_signal(problem, bus_dc_2.emt_model, "v_DC", trajectory),
        "v_grid_1_a": get_signal(problem, bus_grid_1.emt_model, "v_A", trajectory),
        "v_grid_1_b": get_signal(problem, bus_grid_1.emt_model, "v_B", trajectory),
        "v_grid_1_c": get_signal(problem, bus_grid_1.emt_model, "v_C", trajectory),
        "v_grid_2_a": get_signal(problem, bus_grid_2.emt_model, "v_A", trajectory),
        "v_grid_2_b": get_signal(problem, bus_grid_2.emt_model, "v_B", trajectory),
        "v_grid_2_c": get_signal(problem, bus_grid_2.emt_model, "v_C", trajectory),
        "p_ctrl": get_signal(problem, dc_line_mdl, "Pctrl", trajectory),
        "p_f_dc": get_signal(problem, dc_line_mdl, "p_f_dc", trajectory),
        "p_t_dc": get_signal(problem, dc_line_mdl, "p_t_dc", trajectory),
        "p_vsc2": get_signal(problem, converter_2_mdl, "P", trajectory),
        "p_ref_vsc2": get_signal(problem, converter_2_mdl, "P_ref", trajectory),
        "vdc_ref_vsc1": get_signal(problem, converter_1_mdl, "Vdc_ref", trajectory),
        "i_d_ref_vsc1": get_signal(problem, converter_1_mdl, "i_d_ref", trajectory),
        "i_d_ref_vsc2": get_signal(problem, converter_2_mdl, "i_d_ref", trajectory),
        "i_f_dc": get_signal(problem, dc_line_mdl, "i_f_dc", trajectory),
        "i_t_dc": get_signal(problem, dc_line_mdl, "i_t_dc", trajectory),
        "vdc_ref": get_event_reference_trace(time_s, 1.0, vdc_reference_events),
        "pdc_ref_vsc2": get_event_reference_trace(time_s, idle_power_pu, vsc2_reference_events),
    }

    if plot:
        figure, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
        axes[0].plot(time_s, signals["vdc_ref"], "--", label="Vdc ref")
        axes[0].plot(time_s, signals["v_dc_1"], label="Vdc bus 1")
        axes[0].plot(time_s, signals["v_dc_2"], label="Vdc bus 2")
        axes[0].set_ylabel("Voltage [pu]")
        axes[0].grid(True)
        axes[0].legend(loc="best")

        axes[1].plot(time_s, signals["pdc_ref_vsc2"], "--", label="VSC2 Pdc ref")
        axes[1].plot(time_s, signals["p_vsc2"], label="P VSC2")
        axes[1].plot(time_s, signals["p_ctrl"], label="Line PI Pctrl")
        axes[1].set_ylabel("Power [pu]")
        axes[1].grid(True)
        axes[1].legend(loc="best")

        axes[2].plot(time_s, signals["i_f_dc"], label="If dc")
        axes[2].plot(time_s, signals["i_t_dc"], label="It dc")
        axes[2].set_xlabel("Time [s]")
        axes[2].set_ylabel("Current [pu]")
        axes[2].grid(True)
        axes[2].legend(loc="best")
        figure.tight_layout()

        output_dir = os.path.join(SCRIPT_DIR, "hvdc_vdc_control_plots")
        os.makedirs(output_dir, exist_ok=True)
        figure.savefig(os.path.join(output_dir, "hvdc_vdc_control.png"), dpi=150)
        plt.close(figure)

        ac_figure, ac_axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
        ac_axes[0].plot(time_s, signals["v_grid_1_a"], label="Va Grid 1")
        ac_axes[0].plot(time_s, signals["v_grid_1_b"], label="Vb Grid 1")
        ac_axes[0].plot(time_s, signals["v_grid_1_c"], label="Vc Grid 1")
        ac_axes[0].set_ylabel("Voltage [pu]")
        ac_axes[0].set_title("AC bus voltages Grid 1")
        ac_axes[0].grid(True)
        ac_axes[0].legend(loc="best")

        ac_axes[1].plot(time_s, signals["v_grid_2_a"], label="Va Grid 2")
        ac_axes[1].plot(time_s, signals["v_grid_2_b"], label="Vb Grid 2")
        ac_axes[1].plot(time_s, signals["v_grid_2_c"], label="Vc Grid 2")
        ac_axes[1].set_xlabel("Time [s]")
        ac_axes[1].set_ylabel("Voltage [pu]")
        ac_axes[1].set_title("AC bus voltages Grid 2")
        ac_axes[1].grid(True)
        ac_axes[1].legend(loc="best")
        ac_figure.tight_layout()
        ac_figure.savefig(os.path.join(output_dir, "hvdc_ac_bus_voltages.png"), dpi=150)
        plt.close(ac_figure)

    return {
        "grid": grid,
        "pf_results": pf_results,
        "problem": problem,
        "time": time_s,
        "trajectory": trajectory,
        "diff_trajectory": diff_trajectory,
        "well_initialized": well_initialized,
        "converged": converged,
        "signals": signals,
        "save_grid_filename": save_grid_filename,
    }


if __name__ == "__main__":
    results = run_hvdc_vdc_control_simulation(plot=True)
    print(f"well_initialized = {results['well_initialized']}")
    print(f"converged        = {results['converged']}")
    print(f"finite trajectory = {bool(np.all(np.isfinite(results['trajectory'])))}")
