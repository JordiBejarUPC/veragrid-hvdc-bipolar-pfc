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

import gfl_vsc_emt_internal_filter_validation as base_validation
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Templates.Emt.bridge_2level_3ph_emt_soft_pwm_template import get_bridge_2level_3ph_emt_soft_pwm_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import startup_handover
from VeraGridEngine.Utils.Symbolic.symbolic import Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes


PLOT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "gfl_vsc_emt_soft_pwm_bridge_validation_plots")
SIM_TIME = float(os.environ.get("VERAGRID_GFL_EMT_SOFT_PWM_SIM_TIME", "0.01"))
TIME_STEP = float(os.environ.get("VERAGRID_GFL_EMT_SOFT_PWM_TIME_STEP", "1e-5"))
SWITCHING_FREQUENCY = float(os.environ.get("VERAGRID_GFL_EMT_SOFT_PWM_FSW", "1000.0"))
SOFT_SIGN_LAMDA = float(os.environ.get("VERAGRID_GFL_EMT_SOFT_PWM_LAMDA", "1e-6"))
HANDOVER_TIME = float(os.environ.get("VERAGRID_GFL_EMT_SOFT_PWM_HANDOVER_TIME", "1e-4"))


def _remove_inverse_park_voltage_source(vsc_mdl: Block) -> None:
    for block in vsc_mdl.get_all_blocks():
        filtered_eqs = []
        for eq in block.algebraic_eqs:
            text = str(eq)
            if text.startswith("(va_v) - ") or text.startswith("(vb_v) - ") or text.startswith("(vc_v) - "):
                continue
            filtered_eqs.append(eq)
        block.algebraic_eqs = filtered_eqs


def install_soft_pwm_bridge(grid, vsc_mdl: Block) -> Block:
    vf = grid.var_factory
    bridge = get_bridge_2level_3ph_emt_soft_pwm_template(
        vf=vf,
        name="gfl_soft_pwm_bridge",
        lamda=SOFT_SIGN_LAMDA,
    ).block

    theta = base_validation.find_name_in_block("theta", vsc_mdl)
    omega_base = vf.add_var("omega_base_soft_pwm_bridge")
    v_d_c = base_validation.find_name_in_block("v_d_c", vsc_mdl)
    v_q_c = base_validation.find_name_in_block("v_q_c", vsc_mdl)
    v_zero = vf.add_var("v_zero_soft_pwm_bridge")
    v_dc = base_validation.find_name_in_block("Vdc_cap", vsc_mdl)
    k_v_conv = vf.add_var("k_v_conv_soft_pwm_bridge")
    m_max = vf.add_var("m_max_soft_pwm_bridge")
    vdc_floor = vf.add_var("vdc_floor_soft_pwm_bridge")
    omega_sw = vf.add_var("omega_sw_soft_pwm_bridge")
    omega_sw_eff = vf.add_var("omega_sw_eff_soft_pwm_bridge")
    carrier_phase = vf.add_var("carrier_phase_soft_pwm_bridge")
    switching_enabled_mode = vf.add_var("switching_enabled_soft_pwm_bridge")
    t_enable_sw = vf.add_var("t_enable_soft_pwm_bridge")
    v_d_bridge = vf.add_var("v_d_bridge_soft_pwm_bridge")
    v_q_bridge = vf.add_var("v_q_bridge_soft_pwm_bridge")
    v_ref_a_avg = vf.add_var("v_ref_a_avg_soft_pwm_bridge")
    v_ref_b_avg = vf.add_var("v_ref_b_avg_soft_pwm_bridge")
    v_ref_c_avg = vf.add_var("v_ref_c_avg_soft_pwm_bridge")

    _remove_inverse_park_voltage_source(vsc_mdl)
    vsc_mdl.add(bridge)

    sources = [theta, omega_base, v_d_bridge, v_q_bridge, v_zero, v_dc, k_v_conv, m_max, vdc_floor, omega_sw, carrier_phase, switching_enabled_mode]
    for target, source in zip(bridge.in_vars, sources):
        vsc_mdl.update_model(target, source)

    va_v = base_validation.find_name_in_block("va_v", vsc_mdl)
    vb_v = base_validation.find_name_in_block("vb_v", vsc_mdl)
    vc_v = base_validation.find_name_in_block("vc_v", vsc_mdl)
    v_conv_a = base_validation.find_name_in_block("v_conv_a_gfl_soft_pwm_bridge", bridge)
    v_conv_b = base_validation.find_name_in_block("v_conv_b_gfl_soft_pwm_bridge", bridge)
    v_conv_c = base_validation.find_name_in_block("v_conv_c_gfl_soft_pwm_bridge", bridge)
    averaged_mode = Const(1.0) - switching_enabled_mode
    theta_b = theta - Const(2.0 * np.pi / 3.0)
    theta_c = theta + Const(2.0 * np.pi / 3.0)
    v_ref_a_avg_expr = v_d_c * sym.sin(theta) - v_q_c * sym.cos(theta)
    v_ref_b_avg_expr = v_d_c * sym.sin(theta_b) - v_q_c * sym.cos(theta_b)
    v_ref_c_avg_expr = v_d_c * sym.sin(theta_c) - v_q_c * sym.cos(theta_c)
    vsc_mdl.add(Block(
        algebraic_eqs=[
            v_d_bridge - v_d_c,
            v_q_bridge - v_q_c,
            v_ref_a_avg - v_ref_a_avg_expr,
            v_ref_b_avg - v_ref_b_avg_expr,
            v_ref_c_avg - v_ref_c_avg_expr,
            va_v - (averaged_mode * v_ref_a_avg + switching_enabled_mode * v_conv_a),
            vb_v - (averaged_mode * v_ref_b_avg + switching_enabled_mode * v_conv_b),
            vc_v - (averaged_mode * v_ref_c_avg + switching_enabled_mode * v_conv_c),
        ],
        algebraic_vars=[v_d_bridge, v_q_bridge, v_ref_a_avg, v_ref_b_avg, v_ref_c_avg],
        init_eqs={
            v_d_bridge: Const(0.0),
            v_q_bridge: Const(0.0),
            v_ref_a_avg: v_ref_a_avg_expr,
            v_ref_b_avg: v_ref_b_avg_expr,
            v_ref_c_avg: v_ref_c_avg_expr,
        },
        event_dict={
            t_enable_sw: vf.add_const(HANDOVER_TIME),
            omega_sw: vf.add_const(2.0 * np.pi * SWITCHING_FREQUENCY),
            omega_sw_eff: switching_enabled_mode * omega_sw,
        },
        mode_dict={switching_enabled_mode: vf.add_const(0.0)},
        procedural_logic=[startup_handover(
            mode=switching_enabled_mode,
            t_enable=t_enable_sw,
            name="soft_pwm_startup_handover",
        )],
        name="soft_pwm_bridge_voltage_handover",
    ))
    vsc_mdl.add(Block(event_dict={
        omega_base: vf.add_const(2.0 * np.pi * grid.fBase),
        v_zero: vf.add_const(0.0),
        k_v_conv: vf.add_const(0.5),
        m_max: vf.add_const(0.98),
        vdc_floor: vf.add_const(0.2),
        carrier_phase: vf.add_const(0.0),
    }, name="soft_pwm_bridge_runtime_inputs"))
    vsc_mdl.unify_blocks()
    return bridge


def seed_soft_pwm_bridge(problem: EmtProblemDae, vsc_mdl: Block) -> None:
    def init_value(name: str, default: float = 0.0) -> float:
        var = base_validation.find_name_in_block(name, vsc_mdl)
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
    theta_pwm = theta
    carrier0 = 0.0
    v_dc_eff = max(v_dc, vdc_floor)
    v_mod_scale = max(k_v_conv * v_dc_eff, 1.0e-10)
    v_leg_scale = k_v_conv * v_dc_eff

    def inverse_dq0(theta_value: float, d_value: float, q_value: float) -> tuple[float, float, float]:
        theta_b = theta_value - 2.0 * np.pi / 3.0
        theta_c = theta_value + 2.0 * np.pi / 3.0
        return (
            d_value * np.sin(theta_value) - q_value * np.cos(theta_value) + v_zero,
            d_value * np.sin(theta_b) - q_value * np.cos(theta_b) + v_zero,
            d_value * np.sin(theta_c) - q_value * np.cos(theta_c) + v_zero,
        )

    avg_refs = inverse_dq0(theta, v_d_c, v_q_c)
    raw_refs = inverse_dq0(theta, v_d_c, v_q_c)
    pwm_refs = inverse_dq0(theta_pwm, v_d_c, v_q_c)
    common_raw = 0.5 * (max(raw_refs) + min(raw_refs))
    common_pwm = 0.5 * (max(pwm_refs) + min(pwm_refs))
    refs = tuple(ref - common_raw for ref in raw_refs)
    pwm_refs = tuple(ref - common_pwm for ref in pwm_refs)
    m_u_values = tuple(ref / v_mod_scale for ref in pwm_refs)
    m_values = tuple(float(np.clip(m_u, -m_max, m_max)) for m_u in m_u_values)
    soft_gate_values = []

    for phase, raw_ref, ref, pwm_ref, m_u_value, m_value in zip(("a", "b", "c"), raw_refs, refs, pwm_refs, m_u_values, m_values):
        for name, value in (
            (f"v_ref_{phase}_raw_gfl_soft_pwm_bridge", raw_ref),
            (f"v_ref_{phase}_gfl_soft_pwm_bridge", ref),
            (f"v_ref_{phase}_pwm_gfl_soft_pwm_bridge", pwm_ref),
            (f"m_{phase}_u_gfl_soft_pwm_bridge", m_u_value),
            (f"m_{phase}_gfl_soft_pwm_bridge", m_value),
        ):
            base_validation.set_init_if_exists(problem, vsc_mdl, name, value)

        x_value = m_value - carrier0
        radicand_value = x_value * x_value + SOFT_SIGN_LAMDA
        denom_value = float(np.sqrt(radicand_value))
        softsign_value = x_value / denom_value
        gate_value = 0.5 * (1.0 + softsign_value)
        soft_gate_values.append(gate_value)

        for name, value in (
            (f"softsign_pwm_{phase}_gfl_soft_pwm_bridge", softsign_value),
            (f"softsign_x_aux_pwm_{phase}_gfl_soft_pwm_bridge", x_value),
            (f"softsign_radicand_pwm_{phase}_gfl_soft_pwm_bridge", radicand_value),
            (f"softsign_denom_a_pwm_{phase}_gfl_soft_pwm_bridge", denom_value),
            (f"softsign_denom_b_pwm_{phase}_gfl_soft_pwm_bridge", denom_value),
            (f"gate_pwm_{phase}_gfl_soft_pwm_bridge", gate_value),
            (f"gate_{phase}_gfl_soft_pwm_bridge", gate_value),
        ):
            base_validation.set_init_if_exists(problem, vsc_mdl, name, value)

    v_leg_a = (2.0 * soft_gate_values[0] - 1.0) * v_leg_scale
    v_leg_b = (2.0 * soft_gate_values[1] - 1.0) * v_leg_scale
    v_leg_c = (2.0 * soft_gate_values[2] - 1.0) * v_leg_scale
    v_common = (v_leg_a + v_leg_b + v_leg_c) / 3.0
    v_conv_a = v_leg_a - v_common
    v_conv_b = v_leg_b - v_common
    v_conv_c = v_leg_c - v_common
    theta_b = theta - 2.0 * np.pi / 3.0
    theta_c = theta + 2.0 * np.pi / 3.0
    v_conv_d = (2.0 / 3.0) * (np.sin(theta) * v_conv_a + np.sin(theta_b) * v_conv_b + np.sin(theta_c) * v_conv_c)
    v_conv_q = -(2.0 / 3.0) * (np.cos(theta) * v_conv_a + np.cos(theta_b) * v_conv_b + np.cos(theta_c) * v_conv_c)
    v_conv_0 = (v_conv_a + v_conv_b + v_conv_c) / 3.0
    i_filter_a = init_value("i_filter_A")
    i_filter_b = init_value("i_filter_B")
    i_filter_c = init_value("i_filter_C")
    p_conv = -(avg_refs[0] * i_filter_a + avg_refs[1] * i_filter_b + avg_refs[2] * i_filter_c) / 3.0

    for name, value in (
        ("v_d_bridge_soft_pwm_bridge", v_d_c),
        ("v_q_bridge_soft_pwm_bridge", v_q_c),
        ("v_ref_a_avg_soft_pwm_bridge", avg_refs[0]),
        ("v_ref_b_avg_soft_pwm_bridge", avg_refs[1]),
        ("v_ref_c_avg_soft_pwm_bridge", avg_refs[2]),
        ("va_v", avg_refs[0]),
        ("vb_v", avg_refs[1]),
        ("vc_v", avg_refs[2]),
        ("P_conv", p_conv),
        ("v_ref_common_inj_gfl_soft_pwm_bridge", common_raw),
        ("theta_pwm_sample_gfl_soft_pwm_bridge", theta_pwm),
        ("v_p_gfl_soft_pwm_bridge", 0.5 * v_dc_eff),
        ("v_n_gfl_soft_pwm_bridge", -0.5 * v_dc_eff),
        ("v_leg_a_gfl_soft_pwm_bridge", v_leg_a),
        ("v_leg_b_gfl_soft_pwm_bridge", v_leg_b),
        ("v_leg_c_gfl_soft_pwm_bridge", v_leg_c),
        ("v_common_mode_gfl_soft_pwm_bridge", v_common),
        ("v_conv_a_gfl_soft_pwm_bridge", v_conv_a),
        ("v_conv_b_gfl_soft_pwm_bridge", v_conv_b),
        ("v_conv_c_gfl_soft_pwm_bridge", v_conv_c),
        ("v_conv_d_gfl_soft_pwm_bridge", v_conv_d),
        ("v_conv_q_gfl_soft_pwm_bridge", v_conv_q),
        ("v_conv_0_gfl_soft_pwm_bridge", v_conv_0),
    ):
        base_validation.set_init_if_exists(problem, vsc_mdl, name, value)

    for name, value in (
        ("v_zero_soft_pwm_bridge", 0.0),
        ("k_v_conv_soft_pwm_bridge", 0.5),
        ("m_max_soft_pwm_bridge", 0.98),
        ("vdc_floor_soft_pwm_bridge", 0.2),
        ("omega_sw_soft_pwm_bridge", 2.0 * np.pi * SWITCHING_FREQUENCY),
        ("omega_sw_eff_soft_pwm_bridge", 0.0),
        ("carrier_phase_soft_pwm_bridge", 0.0),
        ("switching_enabled_soft_pwm_bridge", 0.0),
        ("t_enable_soft_pwm_bridge", HANDOVER_TIME),
    ):
        base_validation.set_init_if_exists(problem, vsc_mdl, name, value)
        base_validation.set_problem_runtime_value(problem, problem.grid.var_factory, vsc_mdl, name, value)


def plot_soft_pwm_bridge_traces(t: np.ndarray, problem: EmtProblemDae, y: np.ndarray, vsc_mdl: Block) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    plt.figure(figsize=(10, 5))
    for name in ("gate_pwm_a_gfl_soft_pwm_bridge", "gate_pwm_b_gfl_soft_pwm_bridge", "gate_pwm_c_gfl_soft_pwm_bridge"):
        tr = base_validation.trace_for_var(problem, y, base_validation.find_name_in_block(name, vsc_mdl))
        if tr is not None:
            plt.plot(t, tr, label=name)
    plt.xlabel("Time [s]")
    plt.ylabel("Soft gate")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "soft_pwm_bridge_gates.png"), dpi=150)
    plt.close()


def main() -> None:
    base_validation.PLOT_OUTPUT_DIR = PLOT_OUTPUT_DIR

    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = base_validation.build_grid()
    pf_results = base_validation.run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")

    vsc_mdl, line23_mdl, gen_mdl, dc_source_mdl, vsc_filter_l, p_ref0, q_ref0, theta_ref = base_validation.build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3
    )
    install_soft_pwm_bridge(grid, vsc_mdl)
    print(f"Soft-sign PWM bridge lamda: {SOFT_SIGN_LAMDA:.9e}")
    print(f"Soft-sign PWM switching frequency: {SWITCHING_FREQUENCY:.9e} Hz")

    options = EmtOptions(
        time_step=TIME_STEP,
        simulation_time=SIM_TIME,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        solver_type=EmtSolverTypes.StructuralAD,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results)
    base_validation.seed_internal_filter_guess(problem, grid, pf_results, vsc_mdl, dc_source_mdl, line23, bus_dc, bus2, theta_ref)
    seed_soft_pwm_bridge(problem, vsc_mdl)
    base_validation.print_problem_structure(problem)

    try:
        x0_run = problem.get_x0().copy()
        dx0_run = problem.get_dx0().copy()
        t, y, dy, well_initialized, converged = base_validation.run_emt(
            problem=problem,
            options=options,
            t_end=options.simulation_time,
        )
    except np.linalg.LinAlgError as exc:
        print(f"Soft-sign PWM EMT solve failed during Newton iteration: {exc}")
        return

    print(f"Soft-sign PWM EMT well initialized: {well_initialized}")
    print(f"Soft-sign PWM EMT converged: {converged}")
    print(f"Solved samples: {len(t)}")
    base_validation.print_initialization_diagnostics(problem, vsc_mdl, t, y, dy, x0_run, dx0_run)

    for name in ("P", "Q", "v_d_c", "v_q_c", "carrier_pwm_gfl_soft_pwm_bridge"):
        var = base_validation.find_name_in_block(name, vsc_mdl)
        if var is not None and var.uid in problem._uid2idx_vars:
            trace = y[:, problem.get_var_idx(var)]
            print(f"{name}: t0={trace[0]: .9e}, final={trace[-1]: .9e}")

    plot_soft_pwm_bridge_traces(t, problem, y, vsc_mdl)
    base_validation.plot_traces(t, problem, y, vsc_mdl, bus_dc, bus2, p_ref0)
    print(f"Soft-sign PWM bridge plots saved to: {PLOT_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
