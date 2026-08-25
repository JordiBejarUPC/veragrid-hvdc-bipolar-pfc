# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_mti import EmtProblemMTI
from VeraGridEngine.Simulations.EMT.solvers.emt_mti_back_euler_solver import EmtMtiBackEulerSolver
from VeraGridEngine.Templates.Emt.bridge_2level_3ph_emt_mti_template import get_bridge_2level_3ph_emt_mti_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import piecewise
from VeraGridEngine.Utils.procedural_logic import startup_handover
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes

from gfl_vsc_emt_internal_filter_validation import (
    VERAGRID_GFL_EMT_TIME_STEP,
    add_bus_zero_sequence_reference,
    build_emt_models,
    build_grid,
    find_name_in_block,
    plot_traces,
    print_problem_structure,
    run_power_flow,
    seed_internal_filter_guess,
    set_event_value_in_block,
    set_init_if_exists,
    set_problem_runtime_value,
    trace_for_var,
)


PLOT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "gfl_vsc_emt_mti_bridge_validation_plots")
SIM_TIME = float(os.environ.get("VERAGRID_GFL_EMT_MTI_SIM_TIME", "0.01"))
TIME_STEP = float(os.environ.get("VERAGRID_GFL_EMT_MTI_TIME_STEP", "1e-5"))
SIM_TIME_INCREMENT = float(os.environ.get("VERAGRID_GFL_EMT_MTI_SIM_TIME_INCREMENT", "0.001"))
SWITCHING_FREQUENCY = float(os.environ.get("VERAGRID_GFL_EMT_MTI_FSW", "1000.0"))
HANDOVER_TIME = float(os.environ.get("VERAGRID_GFL_EMT_MTI_HANDOVER_TIME", "1e-4"))
PREF_EVENT_TIME = float(os.environ.get("VERAGRID_GFL_EMT_MTI_PREF_EVENT_TIME", "0.005"))
PREF_EVENT_DELTA = float(os.environ.get("VERAGRID_GFL_EMT_MTI_PREF_EVENT_DELTA", "0.01"))
PLOT_RESULTS = os.environ.get("VERAGRID_GFL_EMT_MTI_PLOTS", "1").strip() in ("1", "true", "True", "yes", "on")


def _remove_inverse_park_voltage_source(vsc_mdl: Block) -> None:
    for block in vsc_mdl.get_all_blocks():
        filtered_eqs = []
        for eq in block.algebraic_eqs:
            text = str(eq)
            if text.startswith("(va_v) - ") or text.startswith("(vb_v) - ") or text.startswith("(vc_v) - "):
                continue
            filtered_eqs.append(eq)
        block.algebraic_eqs = filtered_eqs


def install_mti_bridge(grid, vsc_mdl: Block) -> Block:
    vf = grid.var_factory
    bridge = get_bridge_2level_3ph_emt_mti_template(vf=vf, name="gfl_mti_bridge").block

    theta = find_name_in_block("theta", vsc_mdl)
    omega_base = vf.add_var("omega_base_mti_bridge")
    v_d_c = find_name_in_block("v_d_c", vsc_mdl)
    v_q_c = find_name_in_block("v_q_c", vsc_mdl)
    v_zero = vf.add_var("v_zero_mti_bridge")
    v_dc = find_name_in_block("Vdc_cap", vsc_mdl)
    k_v_conv = vf.add_var("k_v_conv_mti_bridge")
    m_max = vf.add_var("m_max_mti_bridge")
    vdc_floor = vf.add_var("vdc_floor_mti_bridge")
    omega_sw = vf.add_var("omega_sw_mti_bridge")
    carrier_phase = vf.add_var("carrier_phase_mti_bridge")
    switching_enabled_mode = vf.add_var("switching_enabled_mode_mti_bridge")
    t_enable_sw = vf.add_var("t_enable_sw_mti_bridge")
    switching_enabled_trace = vf.add_var("switching_enabled_trace_mti_bridge")
    omega_sw_eff_trace = vf.add_var("omega_sw_eff_trace_mti_bridge")

    _remove_inverse_park_voltage_source(vsc_mdl)
    vsc_mdl.add(bridge)

    sources = [
        theta,
        omega_base,
        v_d_c,
        v_q_c,
        v_zero,
        v_dc,
        k_v_conv,
        m_max,
        vdc_floor,
        omega_sw,
        carrier_phase,
    ]
    vsc_mdl.update_model_bulk(dict(zip(bridge.in_vars, sources)))

    va_v = find_name_in_block("va_v", vsc_mdl)
    vb_v = find_name_in_block("vb_v", vsc_mdl)
    vc_v = find_name_in_block("vc_v", vsc_mdl)
    v_ref_a = find_name_in_block("v_ref_a_gfl_mti_bridge", bridge)
    v_ref_b = find_name_in_block("v_ref_b_gfl_mti_bridge", bridge)
    v_ref_c = find_name_in_block("v_ref_c_gfl_mti_bridge", bridge)
    v_conv_a = find_name_in_block("v_conv_a_gfl_mti_bridge", bridge)
    v_conv_b = find_name_in_block("v_conv_b_gfl_mti_bridge", bridge)
    v_conv_c = find_name_in_block("v_conv_c_gfl_mti_bridge", bridge)
    averaged_mode = vf.add_const(1.0) - switching_enabled_mode
    vsc_mdl.add(Block(algebraic_eqs=[
        va_v - (averaged_mode * v_ref_a + switching_enabled_mode * v_conv_a),
        vb_v - (averaged_mode * v_ref_b + switching_enabled_mode * v_conv_b),
        vc_v - (averaged_mode * v_ref_c + switching_enabled_mode * v_conv_c),
        switching_enabled_trace - switching_enabled_mode,
        omega_sw_eff_trace - switching_enabled_mode * omega_sw,
    ], algebraic_vars=[
        switching_enabled_trace,
        omega_sw_eff_trace,
    ], name="mti_bridge_voltage_port"))
    vsc_mdl.add(Block(event_dict={
        omega_base: vf.add_const(2.0 * np.pi * grid.fBase),
        v_zero: vf.add_const(0.0),
        k_v_conv: vf.add_const(0.5),
        m_max: vf.add_const(0.98),
        vdc_floor: vf.add_const(0.2),
        omega_sw: vf.add_const(2.0 * np.pi * SWITCHING_FREQUENCY),
        carrier_phase: vf.add_const(0.0),
        t_enable_sw: vf.add_const(HANDOVER_TIME),
    }, mode_dict={
        switching_enabled_mode: vf.add_const(0.0),
    }, procedural_logic=[
        startup_handover(
            mode=switching_enabled_mode,
            t_enable=t_enable_sw,
            name="mti_bridge_startup_handover",
        )
    ], name="mti_bridge_runtime_inputs"))
    vsc_mdl.unify_blocks()
    return bridge


def seed_mti_bridge(problem: EmtProblemMTI, vsc_mdl: Block) -> None:
    def init_value(name: str, default: float = 0.0) -> float:
        var = find_name_in_block(name, vsc_mdl)
        if var is None:
            return default
        return float(problem.init_guess.get(var.uid, default))

    theta = init_value("theta")
    v_d_c = init_value("v_d_c")
    v_q_c = init_value("v_q_c")
    v_zero = 0.0
    v_dc = init_value("Vdc_cap", 1.0)
    k_v_conv = 0.5
    m_max = 0.98
    vdc_floor = 0.2
    omega_base = 2.0 * np.pi * problem.grid.fBase
    omega_sw = 2.0 * np.pi * SWITCHING_FREQUENCY
    carrier0 = 0.0
    b_carrier_rise = 1.0
    v_dc_eff = max(v_dc, vdc_floor)
    v_mod_scale = max(k_v_conv * v_dc_eff, 1.0e-10)
    v_leg_scale = k_v_conv * v_dc_eff
    theta_pwm = theta + omega_base * np.pi / (2.0 * omega_sw)

    def inverse_dq0(theta_value: float, d_value: float, q_value: float) -> tuple[float, float, float]:
        theta_b = theta_value - 2.0 * np.pi / 3.0
        theta_c = theta_value + 2.0 * np.pi / 3.0
        return (
            d_value * np.sin(theta_value) - q_value * np.cos(theta_value) + v_zero,
            d_value * np.sin(theta_b) - q_value * np.cos(theta_b) + v_zero,
            d_value * np.sin(theta_c) - q_value * np.cos(theta_c) + v_zero,
        )

    refs_raw = inverse_dq0(theta, v_d_c, v_q_c)
    refs_pwm_raw = inverse_dq0(theta_pwm, v_d_c, v_q_c)
    common_inj = 0.5 * (max(refs_raw) + min(refs_raw))
    common_inj_pwm = 0.5 * (max(refs_pwm_raw) + min(refs_pwm_raw))
    refs = tuple(ref - common_inj for ref in refs_raw)
    refs_pwm = tuple(ref - common_inj_pwm for ref in refs_pwm_raw)
    m_u_values = tuple(ref / v_mod_scale for ref in refs_pwm)
    m_values = tuple(float(np.clip(m_u, -m_max, m_max)) for m_u in m_u_values)
    gate_values = tuple(1.0 if (m_value - carrier0) >= 0.0 else 0.0 for m_value in m_values)

    v_leg_a = (2.0 * gate_values[0] - 1.0) * v_leg_scale
    v_leg_b = (2.0 * gate_values[1] - 1.0) * v_leg_scale
    v_leg_c = (2.0 * gate_values[2] - 1.0) * v_leg_scale
    v_common = (v_leg_a + v_leg_b + v_leg_c) / 3.0
    v_conv_a = v_leg_a - v_common
    v_conv_b = v_leg_b - v_common
    v_conv_c = v_leg_c - v_common
    theta_b = theta - 2.0 * np.pi / 3.0
    theta_c = theta + 2.0 * np.pi / 3.0
    v_conv_d = (2.0 / 3.0) * (np.sin(theta) * v_conv_a + np.sin(theta_b) * v_conv_b + np.sin(theta_c) * v_conv_c)
    v_conv_q = -(2.0 / 3.0) * (np.cos(theta) * v_conv_a + np.cos(theta_b) * v_conv_b + np.cos(theta_c) * v_conv_c)
    v_conv_0 = (v_conv_a + v_conv_b + v_conv_c) / 3.0

    for name, value in (
        ("v_ref_a_raw_gfl_mti_bridge", refs_raw[0]),
        ("v_ref_b_raw_gfl_mti_bridge", refs_raw[1]),
        ("v_ref_c_raw_gfl_mti_bridge", refs_raw[2]),
        ("v_ref_common_inj_gfl_mti_bridge", common_inj),
        ("v_ref_a_gfl_mti_bridge", refs[0]),
        ("v_ref_b_gfl_mti_bridge", refs[1]),
        ("v_ref_c_gfl_mti_bridge", refs[2]),
        ("theta_pwm_sample_gfl_mti_bridge", theta_pwm),
        ("v_ref_a_pwm_gfl_mti_bridge", refs_pwm[0]),
        ("v_ref_b_pwm_gfl_mti_bridge", refs_pwm[1]),
        ("v_ref_c_pwm_gfl_mti_bridge", refs_pwm[2]),
        ("m_a_u_gfl_mti_bridge", m_u_values[0]),
        ("m_b_u_gfl_mti_bridge", m_u_values[1]),
        ("m_c_u_gfl_mti_bridge", m_u_values[2]),
        ("m_a_gfl_mti_bridge", m_values[0]),
        ("m_b_gfl_mti_bridge", m_values[1]),
        ("m_c_gfl_mti_bridge", m_values[2]),
        ("carrier_pwm_gfl_mti_bridge", carrier0),
        ("gate_pwm_a_gfl_mti_bridge", gate_values[0]),
        ("gate_pwm_b_gfl_mti_bridge", gate_values[1]),
        ("gate_pwm_c_gfl_mti_bridge", gate_values[2]),
        ("v_p_gfl_mti_bridge", 0.5 * v_dc_eff),
        ("v_n_gfl_mti_bridge", -0.5 * v_dc_eff),
        ("v_leg_a_gfl_mti_bridge", v_leg_a),
        ("v_leg_b_gfl_mti_bridge", v_leg_b),
        ("v_leg_c_gfl_mti_bridge", v_leg_c),
        ("v_common_mode_gfl_mti_bridge", v_common),
        ("v_conv_a_gfl_mti_bridge", v_conv_a),
        ("v_conv_b_gfl_mti_bridge", v_conv_b),
        ("v_conv_c_gfl_mti_bridge", v_conv_c),
        ("v_conv_d_gfl_mti_bridge", v_conv_d),
        ("v_conv_q_gfl_mti_bridge", v_conv_q),
        ("v_conv_0_gfl_mti_bridge", v_conv_0),
        ("gate_a_gfl_mti_bridge", gate_values[0]),
        ("gate_b_gfl_mti_bridge", gate_values[1]),
        ("gate_c_gfl_mti_bridge", gate_values[2]),
    ):
        set_init_if_exists(problem, vsc_mdl, name, value)

    for name, value in (
        ("b_pwm_a_gfl_mti_bridge", gate_values[0]),
        ("b_pwm_b_gfl_mti_bridge", gate_values[1]),
        ("b_pwm_c_gfl_mti_bridge", gate_values[2]),
        ("b_carrier_rise_pwm_gfl_mti_bridge", b_carrier_rise),
        ("v_zero_mti_bridge", v_zero),
        ("k_v_conv_mti_bridge", k_v_conv),
        ("m_max_mti_bridge", m_max),
        ("vdc_floor_mti_bridge", vdc_floor),
        ("omega_sw_mti_bridge", omega_sw),
        ("carrier_phase_mti_bridge", 0.0),
        ("switching_enabled_mode_mti_bridge", 0.0 if HANDOVER_TIME > 0.0 else 1.0),
        ("t_enable_sw_mti_bridge", HANDOVER_TIME),
    ):
        set_init_if_exists(problem, vsc_mdl, name, value)
        set_problem_runtime_value(problem, problem.grid.var_factory, vsc_mdl, name, value)
    carrier = find_name_in_block("carrier_pwm_gfl_mti_bridge", vsc_mdl)
    if carrier is not None and carrier.diff_var is not None:
        problem.diff_init_guess[carrier.diff_var.uid] = 4.0 * SWITCHING_FREQUENCY


def apply_pref_step_event(problem: EmtProblemMTI, vsc_mdl: Block, p_ref0: float) -> None:
    p_ref = find_name_in_block("P_ref", vsc_mdl)
    if p_ref is None or p_ref.uid not in problem._uid2idx_event_params:
        return

    idx = int(problem._uid2idx_event_params[p_ref.uid])
    event_expr = piecewise(
        time_var=problem.glob_time,
        t_events=np.asarray([PREF_EVENT_TIME], dtype=np.float64),
        new_values=np.asarray([p_ref0 + PREF_EVENT_DELTA], dtype=np.float64),
        default_value=problem.grid.var_factory.add_const(float(p_ref0)),
    )
    problem._event_parameters_eqs[idx] = event_expr
    if idx < len(problem._runtime_all_eqs_source):
        problem._runtime_all_eqs_source[idx] = event_expr
    if idx < len(problem._runtime_continuous_eqs):
        problem._runtime_continuous_eqs[idx] = event_expr
    problem._event_params_values[idx] = float(p_ref0)
    print(
        f"P_ref step event: t={PREF_EVENT_TIME:.6e}s "
        f"from {p_ref0:.9e} to {p_ref0 + PREF_EVENT_DELTA:.9e}"
    )


def _plot_named_step_traces(
    t: np.ndarray,
    problem: EmtProblemMTI,
    y: np.ndarray,
    vsc_mdl: Block,
    names: tuple[str, ...],
    ylabel: str,
    filename: str,
) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    plt.figure(figsize=(10, 5))
    for name in names:
        tr = trace_for_var(problem, y, find_name_in_block(name, vsc_mdl))
        if tr is not None:
            plt.step(t, tr, where="post", label=name)
    plt.xlabel("Time [s]")
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, filename), dpi=150)
    plt.close()


def plot_mti_bridge_traces(t: np.ndarray, problem: EmtProblemMTI, y: np.ndarray, vsc_mdl: Block, z: np.ndarray) -> None:
    if len(t) == 0:
        return

    _plot_named_step_traces(
        t=t,
        problem=problem,
        y=y,
        vsc_mdl=vsc_mdl,
        names=("gate_pwm_a_gfl_mti_bridge", "gate_pwm_b_gfl_mti_bridge", "gate_pwm_c_gfl_mti_bridge"),
        ylabel="Gate",
        filename="mti_bridge_gates.png",
    )
    _plot_named_step_traces(
        t=t,
        problem=problem,
        y=y,
        vsc_mdl=vsc_mdl,
        names=("gate_a_gfl_mti_bridge", "gate_b_gfl_mti_bridge", "gate_c_gfl_mti_bridge"),
        ylabel="Gate output",
        filename="mti_bridge_gate_outputs.png",
    )
    _plot_named_step_traces(
        t=t,
        problem=problem,
        y=y,
        vsc_mdl=vsc_mdl,
        names=("switching_enabled_trace_mti_bridge", "omega_sw_eff_trace_mti_bridge"),
        ylabel="Handover mode / omega_sw_eff",
        filename="mti_bridge_startup_handover.png",
    )

    plt.figure(figsize=(10, 5))
    for name in ("carrier_pwm_gfl_mti_bridge", "m_a_gfl_mti_bridge", "m_b_gfl_mti_bridge", "m_c_gfl_mti_bridge"):
        tr = trace_for_var(problem, y, find_name_in_block(name, vsc_mdl))
        if tr is not None:
            plt.plot(t, tr, label=name)
    plt.xlabel("Time [s]")
    plt.ylabel("Carrier / modulation")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "mti_bridge_pwm_comparator.png"), dpi=150)
    plt.close()

    if z.size > 0:
        plt.figure(figsize=(10, 5))
        for idx, var in enumerate(problem.get_mti_boolean_parameters()):
            if idx < z.shape[1]:
                plt.step(t, z[:, idx], where="post", label=var.name)
        plt.xlabel("Time [s]")
        plt.ylabel("MTI boolean")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "mti_bridge_boolean_modes.png"), dpi=150)
        plt.close()


def seed_problem_from_state(problem: EmtProblemMTI, x: np.ndarray) -> None:
    for var in problem.state_and_algebraic_vars():
        idx = problem._uid2idx_vars.get(var.uid, None)
        if idx is not None:
            problem.init_guess[var.uid] = float(x[idx])


def run_mti_solver_incrementally(
    problem: EmtProblemMTI,
    options: EmtOptions,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool, np.ndarray]:
    target_time = float(options.simulation_time)
    h = float(options.time_step)
    chunk_time = max(h, float(SIM_TIME_INCREMENT))
    t0 = 0.0
    t_parts: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []
    dy_parts: list[np.ndarray] = []
    z_parts: list[np.ndarray] = []
    well_initialized_all = True
    converged_all = True

    while t0 < target_time - 1e-15:
        t_end = min(target_time, t0 + chunk_time)
        print(f"EMT-MTI chunk: {t0:.6e}s -> {t_end:.6e}s")
        solver = EmtMtiBackEulerSolver(
            problem=problem,
            t0=t0,
            t_end=t_end,
            h=h,
            max_iter=options.init_newton_max_iter,
            tolerance=options.tolerance,
        )
        t_chunk, y_chunk, dy_chunk, well_initialized, converged = solver.simulate()
        if len(t_chunk) == 0:
            converged_all = False
            break

        start = 0 if not t_parts else 1
        if start < len(t_chunk):
            t_parts.append(t_chunk[start:])
            y_parts.append(y_chunk[start:, :])
            dy_parts.append(dy_chunk[start:, :])
            z_parts.append(solver.z[start:, :])

        well_initialized_all = bool(well_initialized_all and well_initialized)
        converged_all = bool(converged_all and converged)
        seed_problem_from_state(problem, y_chunk[-1, :])
        if solver.z.size > 0 and solver.z.shape[0] > 0:
            problem.set_mti_boolean_state(solver.z[-1, :])
        try:
            problem.update_variable_params(t=float(t_chunk[-1]), x_snapshot=y_chunk[-1, :])
        except TypeError:
            problem.update_variable_params(float(t_chunk[-1]))
        except Exception:
            pass

        if not converged or t_chunk[-1] <= t0 + 1e-15:
            converged_all = False
            break
        t0 = float(t_chunk[-1])

    if not t_parts:
        empty_y = np.zeros((0, problem.get_all_vars_number()), dtype=float)
        empty_dy = np.zeros((0, problem.get_all_vars_number()), dtype=float)
        return np.zeros(0, dtype=float), empty_y, empty_dy, well_initialized_all, False, np.zeros((0, 0), dtype=float)

    t = np.concatenate(t_parts)
    y = np.vstack(y_parts)
    dy = np.vstack(dy_parts)
    z = np.vstack(z_parts) if z_parts else np.zeros((len(t), 0), dtype=float)
    return t, y, dy, well_initialized_all, converged_all, z


def run_mti_solver_direct(
    problem: EmtProblemMTI,
    options: EmtOptions,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool, np.ndarray]:
    solver = EmtMtiBackEulerSolver(
        problem=problem,
        t0=0.0,
        t_end=float(options.simulation_time),
        h=float(options.time_step),
        max_iter=options.init_newton_max_iter,
        tolerance=options.tolerance,
    )
    t, y, dy, well_initialized, converged = solver.simulate()
    z = solver.z if getattr(solver, "z", None) is not None else np.zeros((len(t), 0), dtype=float)
    return t, y, dy, well_initialized, converged, z


def main() -> None:
    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = build_grid()
    pf_results = run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")

    vsc_mdl, line23_mdl, gen_mdl, dc_source_mdl, vsc_filter_l, p_ref0, q_ref0, theta_ref = build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3
    )
    install_mti_bridge(grid, vsc_mdl)

    options = EmtOptions(
        time_step=TIME_STEP,
        simulation_time=SIM_TIME,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        solver_type=EmtSolverTypes.StructuralAD,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )
    problem = EmtProblemMTI(grid=grid, options=options, pf_results=pf_results)
    seed_internal_filter_guess(problem, grid, pf_results, vsc_mdl, dc_source_mdl, line23, bus_dc, bus2, theta_ref)
    apply_pref_step_event(problem, vsc_mdl, p_ref0)
    seed_mti_bridge(problem, vsc_mdl)
    print_problem_structure(problem)

    t, y, _dy, well_initialized, converged, z = run_mti_solver_direct(problem, options)
    print(f"EMT-MTI well initialized: {well_initialized}")
    print(f"EMT-MTI converged: {converged}")
    print(f"Solved samples: {len(t)}")
    print(f"MTI boolean shape: {z.shape}")

    for name in (
        "P",
        "Q",
        "v_d_c",
        "v_q_c",
        "carrier_pwm_gfl_mti_bridge",
        "switching_enabled_trace_mti_bridge",
        "omega_sw_eff_trace_mti_bridge",
    ):
        var = find_name_in_block(name, vsc_mdl)
        if var is not None and var.uid in problem._uid2idx_vars:
            trace = y[:, problem.get_var_idx(var)]
            print(f"{name}: t0={trace[0]: .9e}, final={trace[-1]: .9e}")

    if PLOT_RESULTS:
        plot_mti_bridge_traces(t, problem, y, vsc_mdl, z)
        if len(t) > 0:
            plot_traces(t, problem, y, vsc_mdl, bus_dc, bus2, p_ref0)
        print(f"MTI bridge plots saved to: {PLOT_OUTPUT_DIR}")
    else:
        print("MTI bridge plotting skipped (VERAGRID_GFL_EMT_MTI_PLOTS=0)")


if __name__ == "__main__":
    main()
