# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import gfl_vsc_emt_internal_filter_validation as base_validation
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Utils.procedural_logic import startup_handover
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes


SIM_TIME = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_HARD_PWM_SIM_TIME", "2e-5"))
TIME_STEP = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_HARD_PWM_TIME_STEP", "1e-6"))
HANDOVER_TIME = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_HARD_PWM_HANDOVER_TIME", "1e-4"))
SWITCHING_FREQUENCY = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_HARD_PWM_FSW", "1000.0"))
SOLVER_TYPE = os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_HARD_PWM_SOLVER", "StructuralAD")


def _remove_inverse_park_voltage_source(vsc_mdl: Block) -> None:
    for block in vsc_mdl.get_all_blocks():
        filtered_eqs = []
        for eq in block.algebraic_eqs:
            text = str(eq)
            if text.startswith("(va_v) - ") or text.startswith("(vb_v) - ") or text.startswith("(vc_v) - "):
                continue
            filtered_eqs.append(eq)
        block.algebraic_eqs = filtered_eqs


def install_hard_pwm_bridge(grid, vsc_mdl: Block) -> None:
    vf = grid.var_factory
    theta = base_validation.find_name_in_block("theta", vsc_mdl)
    v_d_c = base_validation.find_name_in_block("v_d_c", vsc_mdl)
    v_q_c = base_validation.find_name_in_block("v_q_c", vsc_mdl)
    v_dc = base_validation.find_name_in_block("Vdc_cap", vsc_mdl)
    va_v = base_validation.find_name_in_block("va_v", vsc_mdl)
    vb_v = base_validation.find_name_in_block("vb_v", vsc_mdl)
    vc_v = base_validation.find_name_in_block("vc_v", vsc_mdl)

    omega_base = vf.add_var("omega_base_hard_pwm_bridge")
    omega_sw = vf.add_var("omega_sw_hard_pwm_bridge")
    carrier_phase = vf.add_var("carrier_phase_hard_pwm_bridge")
    switching_enabled = vf.add_var("switching_enabled_hard_pwm_bridge")
    t_enable = vf.add_var("t_enable_hard_pwm_bridge")
    k_v_conv = vf.add_var("k_v_conv_hard_pwm_bridge")
    m_max = vf.add_var("m_max_hard_pwm_bridge")
    vdc_floor = vf.add_var("vdc_floor_hard_pwm_bridge")

    v_ref_a_raw = vf.add_var("v_ref_a_raw_gfl_hard_pwm_bridge")
    v_ref_b_raw = vf.add_var("v_ref_b_raw_gfl_hard_pwm_bridge")
    v_ref_c_raw = vf.add_var("v_ref_c_raw_gfl_hard_pwm_bridge")
    v_ref_common = vf.add_var("v_ref_common_inj_gfl_hard_pwm_bridge")
    v_ref_a = vf.add_var("v_ref_a_gfl_hard_pwm_bridge")
    v_ref_b = vf.add_var("v_ref_b_gfl_hard_pwm_bridge")
    v_ref_c = vf.add_var("v_ref_c_gfl_hard_pwm_bridge")
    theta_pwm = vf.add_var("theta_pwm_sample_gfl_hard_pwm_bridge")
    v_ref_a_pwm = vf.add_var("v_ref_a_pwm_gfl_hard_pwm_bridge")
    v_ref_b_pwm = vf.add_var("v_ref_b_pwm_gfl_hard_pwm_bridge")
    v_ref_c_pwm = vf.add_var("v_ref_c_pwm_gfl_hard_pwm_bridge")
    m_a_u = vf.add_var("m_a_u_gfl_hard_pwm_bridge")
    m_b_u = vf.add_var("m_b_u_gfl_hard_pwm_bridge")
    m_c_u = vf.add_var("m_c_u_gfl_hard_pwm_bridge")
    m_a = vf.add_var("m_a_gfl_hard_pwm_bridge")
    m_b = vf.add_var("m_b_gfl_hard_pwm_bridge")
    m_c = vf.add_var("m_c_gfl_hard_pwm_bridge")
    carrier = vf.add_var("carrier_pwm_gfl_hard_pwm_bridge")
    gate_a = vf.add_var("gate_a_gfl_hard_pwm_bridge")
    gate_b = vf.add_var("gate_b_gfl_hard_pwm_bridge")
    gate_c = vf.add_var("gate_c_gfl_hard_pwm_bridge")
    v_leg_a = vf.add_var("v_leg_a_gfl_hard_pwm_bridge")
    v_leg_b = vf.add_var("v_leg_b_gfl_hard_pwm_bridge")
    v_leg_c = vf.add_var("v_leg_c_gfl_hard_pwm_bridge")
    v_common_mode = vf.add_var("v_common_mode_gfl_hard_pwm_bridge")
    v_conv_a = vf.add_var("v_conv_a_gfl_hard_pwm_bridge")
    v_conv_b = vf.add_var("v_conv_b_gfl_hard_pwm_bridge")
    v_conv_c = vf.add_var("v_conv_c_gfl_hard_pwm_bridge")
    v_ref_a_avg = vf.add_var("v_ref_a_avg_hard_pwm_bridge")
    v_ref_b_avg = vf.add_var("v_ref_b_avg_hard_pwm_bridge")
    v_ref_c_avg = vf.add_var("v_ref_c_avg_hard_pwm_bridge")

    c_half = Const(0.5)
    c_one = Const(1.0)
    c_two = Const(2.0)
    c_three = Const(3.0)
    eps = Const(1.0e-10)
    sqrt3 = Const(np.sqrt(3.0))
    park_theta = Const(0.0) - theta
    theta_pwm_expr = park_theta - switching_enabled * omega_base * Const(np.pi) / (c_two * omega_sw)
    v_dc_eff = sym.max(v_dc, vdc_floor)
    v_mod_scale = sym.max(k_v_conv * v_dc_eff, eps)
    v_leg_scale = k_v_conv * v_dc_eff
    # This first diagnostic isolates hard symbolic gate logic pre-handover; the carrier is disabled there.
    carrier_expr = Const(0.0)

    raw_a = v_d_c * sym.cos(park_theta) + v_q_c * sym.sin(park_theta)
    raw_b = v_d_c * (-c_half * sym.cos(park_theta) - c_half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-c_half * sym.sin(park_theta) + c_half * sqrt3 * sym.cos(park_theta))
    raw_c = v_d_c * (-c_half * sym.cos(park_theta) + c_half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-c_half * sym.sin(park_theta) - c_half * sqrt3 * sym.cos(park_theta))
    raw_common = c_half * (sym.max(sym.max(raw_a, raw_b), raw_c) + sym.min(sym.min(raw_a, raw_b), raw_c))
    pwm_a_raw = v_d_c * sym.cos(theta_pwm_expr) + v_q_c * sym.sin(theta_pwm_expr)
    pwm_b_raw = v_d_c * (-c_half * sym.cos(theta_pwm_expr) - c_half * sqrt3 * sym.sin(theta_pwm_expr)) + v_q_c * (-c_half * sym.sin(theta_pwm_expr) + c_half * sqrt3 * sym.cos(theta_pwm_expr))
    pwm_c_raw = v_d_c * (-c_half * sym.cos(theta_pwm_expr) + c_half * sqrt3 * sym.sin(theta_pwm_expr)) + v_q_c * (-c_half * sym.sin(theta_pwm_expr) - c_half * sqrt3 * sym.cos(theta_pwm_expr))
    pwm_common = c_half * (sym.max(sym.max(pwm_a_raw, pwm_b_raw), pwm_c_raw) + sym.min(sym.min(pwm_a_raw, pwm_b_raw), pwm_c_raw))
    ref_a = raw_a - raw_common
    ref_b = raw_b - raw_common
    ref_c = raw_c - raw_common
    pwm_a = pwm_a_raw - pwm_common
    pwm_b = pwm_b_raw - pwm_common
    pwm_c = pwm_c_raw - pwm_common
    m_a_u_expr = pwm_a / v_mod_scale
    m_b_u_expr = pwm_b / v_mod_scale
    m_c_u_expr = pwm_c / v_mod_scale
    m_a_expr = sym.hard_sat(m_a_u_expr, -m_max, m_max)
    m_b_expr = sym.hard_sat(m_b_u_expr, -m_max, m_max)
    m_c_expr = sym.hard_sat(m_c_u_expr, -m_max, m_max)
    gate_a_expr = sym.heaviside(m_a - carrier)
    gate_b_expr = sym.heaviside(m_b - carrier)
    gate_c_expr = sym.heaviside(m_c - carrier)
    v_leg_a_expr = (c_two * gate_a - c_one) * v_leg_scale
    v_leg_b_expr = (c_two * gate_b - c_one) * v_leg_scale
    v_leg_c_expr = (c_two * gate_c - c_one) * v_leg_scale
    v_common_mode_expr = (v_leg_a + v_leg_b + v_leg_c) / c_three
    v_conv_a_expr = v_leg_a - v_common_mode
    v_conv_b_expr = v_leg_b - v_common_mode
    v_conv_c_expr = v_leg_c - v_common_mode

    _remove_inverse_park_voltage_source(vsc_mdl)
    vsc_mdl.add(Block(
        algebraic_eqs=[
            v_ref_a_raw - raw_a, v_ref_b_raw - raw_b, v_ref_c_raw - raw_c,
            v_ref_common - raw_common, v_ref_a - ref_a, v_ref_b - ref_b, v_ref_c - ref_c,
            theta_pwm - theta_pwm_expr,
            v_ref_a_pwm - pwm_a, v_ref_b_pwm - pwm_b, v_ref_c_pwm - pwm_c,
            m_a_u - m_a_u_expr, m_b_u - m_b_u_expr, m_c_u - m_c_u_expr,
            m_a - m_a_expr, m_b - m_b_expr, m_c - m_c_expr,
            carrier - carrier_expr,
            gate_a - gate_a_expr, gate_b - gate_b_expr, gate_c - gate_c_expr,
            v_leg_a - v_leg_a_expr, v_leg_b - v_leg_b_expr, v_leg_c - v_leg_c_expr,
            v_common_mode - v_common_mode_expr,
            v_conv_a - v_conv_a_expr, v_conv_b - v_conv_b_expr, v_conv_c - v_conv_c_expr,
            v_ref_a_avg - raw_a, v_ref_b_avg - raw_b, v_ref_c_avg - raw_c,
            va_v - ((c_one - switching_enabled) * v_ref_a_avg + switching_enabled * v_conv_a),
            vb_v - ((c_one - switching_enabled) * v_ref_b_avg + switching_enabled * v_conv_b),
            vc_v - ((c_one - switching_enabled) * v_ref_c_avg + switching_enabled * v_conv_c),
        ],
        algebraic_vars=[
            v_ref_a_raw, v_ref_b_raw, v_ref_c_raw, v_ref_common, v_ref_a, v_ref_b, v_ref_c,
            theta_pwm, v_ref_a_pwm, v_ref_b_pwm, v_ref_c_pwm, m_a_u, m_b_u, m_c_u, m_a, m_b, m_c,
            carrier, gate_a, gate_b, gate_c, v_leg_a, v_leg_b, v_leg_c, v_common_mode, v_conv_a, v_conv_b, v_conv_c,
            v_ref_a_avg, v_ref_b_avg, v_ref_c_avg,
        ],
        event_dict={
            omega_base: vf.add_const(2.0 * np.pi * grid.fBase),
            omega_sw: vf.add_const(2.0 * np.pi * SWITCHING_FREQUENCY),
            carrier_phase: vf.add_const(0.0),
            k_v_conv: vf.add_const(0.5),
            m_max: vf.add_const(0.98),
            vdc_floor: vf.add_const(0.2),
            t_enable: vf.add_const(HANDOVER_TIME),
        },
        mode_dict={switching_enabled: vf.add_const(0.0)},
        procedural_logic=[startup_handover(mode=switching_enabled, t_enable=t_enable, name="hard_pwm_startup_handover")],
        name="gfl_hard_pwm_bridge",
    ))
    vsc_mdl.unify_blocks()


def seed_hard_pwm_bridge(problem: EmtProblemDae, vsc_mdl: Block) -> None:
    def init_value(name: str, default: float = 0.0) -> float:
        var = base_validation.find_name_in_block(name, vsc_mdl)
        if var is None:
            return default
        return float(problem.init_guess.get(var.uid, default))

    theta = init_value("theta")
    v_d_c = init_value("v_d_c")
    v_q_c = init_value("v_q_c")
    v_dc = init_value("Vdc_cap", 1.0)
    k_v_conv = 0.5
    m_max = 0.98
    vdc_floor = 0.2
    v_dc_eff = max(v_dc, vdc_floor)
    v_mod_scale = max(k_v_conv * v_dc_eff, 1.0e-10)
    v_leg_scale = k_v_conv * v_dc_eff

    park_theta = -theta
    raw_refs = (
        v_d_c * np.cos(park_theta) + v_q_c * np.sin(park_theta),
        v_d_c * (-0.5 * np.cos(park_theta) - 0.5 * np.sqrt(3.0) * np.sin(park_theta))
        + v_q_c * (-0.5 * np.sin(park_theta) + 0.5 * np.sqrt(3.0) * np.cos(park_theta)),
        v_d_c * (-0.5 * np.cos(park_theta) + 0.5 * np.sqrt(3.0) * np.sin(park_theta))
        + v_q_c * (-0.5 * np.sin(park_theta) - 0.5 * np.sqrt(3.0) * np.cos(park_theta)),
    )
    common = 0.5 * (max(raw_refs) + min(raw_refs))
    refs = tuple(ref - common for ref in raw_refs)
    m_u = tuple(ref / v_mod_scale for ref in refs)
    m = tuple(float(np.clip(value, -m_max, m_max)) for value in m_u)
    gates = tuple(1.0 if value >= 0.0 else 0.0 for value in m)
    v_legs = tuple((2.0 * gate - 1.0) * v_leg_scale for gate in gates)
    v_common = sum(v_legs) / 3.0
    v_conv = tuple(v_leg - v_common for v_leg in v_legs)

    for phase, raw, ref, m_u_value, m_value, gate, v_leg, v_conv_value in zip(("a", "b", "c"), raw_refs, refs, m_u, m, gates, v_legs, v_conv):
        for name, value in (
            (f"v_ref_{phase}_raw_gfl_hard_pwm_bridge", raw),
            (f"v_ref_{phase}_gfl_hard_pwm_bridge", ref),
            (f"v_ref_{phase}_pwm_gfl_hard_pwm_bridge", ref),
            (f"m_{phase}_u_gfl_hard_pwm_bridge", m_u_value),
            (f"m_{phase}_gfl_hard_pwm_bridge", m_value),
            (f"gate_{phase}_gfl_hard_pwm_bridge", gate),
            (f"v_leg_{phase}_gfl_hard_pwm_bridge", v_leg),
            (f"v_conv_{phase}_gfl_hard_pwm_bridge", v_conv_value),
        ):
            base_validation.set_init_if_exists(problem, vsc_mdl, name, value)
    for name, value in (
        ("v_ref_common_inj_gfl_hard_pwm_bridge", common),
        ("theta_pwm_sample_gfl_hard_pwm_bridge", park_theta),
        ("carrier_pwm_gfl_hard_pwm_bridge", 0.0),
        ("v_common_mode_gfl_hard_pwm_bridge", v_common),
        ("v_ref_a_avg_hard_pwm_bridge", raw_refs[0]),
        ("v_ref_b_avg_hard_pwm_bridge", raw_refs[1]),
        ("v_ref_c_avg_hard_pwm_bridge", raw_refs[2]),
        ("va_v", raw_refs[0]),
        ("vb_v", raw_refs[1]),
        ("vc_v", raw_refs[2]),
    ):
        base_validation.set_init_if_exists(problem, vsc_mdl, name, value)


def main() -> None:
    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = base_validation.build_grid()
    pf_results = base_validation.run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    vsc_mdl, _line23_mdl, _gen_mdl, dc_source_mdl, _vsc_filter_l, _p_ref0, _q_ref0, theta_ref = base_validation.build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3
    )
    install_hard_pwm_bridge(grid, vsc_mdl)
    options = EmtOptions(
        time_step=TIME_STEP,
        simulation_time=SIM_TIME,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        solver_type=EmtSolverTypes[SOLVER_TYPE],
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results)
    base_validation.seed_internal_filter_guess(problem, grid, pf_results, vsc_mdl, dc_source_mdl, line23, bus_dc, bus2, theta_ref)
    seed_hard_pwm_bridge(problem, vsc_mdl)
    print(f"GFL internal-filter hard PWM solver: {SOLVER_TYPE}")
    base_validation.print_problem_structure(problem)
    try:
        t, _y, _dy, well_initialized, converged = base_validation.run_emt(problem=problem, options=options, t_end=options.simulation_time)
    except (np.linalg.LinAlgError, RuntimeError) as exc:
        print(f"GFL internal-filter hard PWM solve failed during Newton iteration: {exc}")
        return
    print(f"GFL internal-filter hard PWM well initialized: {well_initialized}")
    print(f"GFL internal-filter hard PWM converged: {converged}")
    print(f"Solved samples: {len(t)}")


if __name__ == "__main__":
    main()
