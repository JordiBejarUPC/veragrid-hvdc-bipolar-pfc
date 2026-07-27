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
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes


SIM_TIME = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_AVG_BRIDGE_SIM_TIME", "2e-5"))
TIME_STEP = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_AVG_BRIDGE_TIME_STEP", "1e-6"))
SOLVER_TYPE = os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_AVG_BRIDGE_SOLVER", "StructuralAD")


def _remove_inverse_park_voltage_source(vsc_mdl: Block) -> None:
    for block in vsc_mdl.get_all_blocks():
        filtered_eqs = []
        for eq in block.algebraic_eqs:
            text = str(eq)
            if text.startswith("(va_v) - ") or text.startswith("(vb_v) - ") or text.startswith("(vc_v) - "):
                continue
            filtered_eqs.append(eq)
        block.algebraic_eqs = filtered_eqs


def install_avg_bridge(grid, vsc_mdl: Block) -> None:
    vf = grid.var_factory
    theta = base_validation.find_name_in_block("theta", vsc_mdl)
    v_d_c = base_validation.find_name_in_block("v_d_c", vsc_mdl)
    v_q_c = base_validation.find_name_in_block("v_q_c", vsc_mdl)
    v_dc = base_validation.find_name_in_block("Vdc_cap", vsc_mdl)
    va_v = base_validation.find_name_in_block("va_v", vsc_mdl)
    vb_v = base_validation.find_name_in_block("vb_v", vsc_mdl)
    vc_v = base_validation.find_name_in_block("vc_v", vsc_mdl)

    k_v_conv = vf.add_var("k_v_conv_avg_bridge")
    m_max = vf.add_var("m_max_avg_bridge")
    vdc_floor = vf.add_var("vdc_floor_avg_bridge")
    v_ref_a_raw = vf.add_var("v_ref_a_raw_gfl_avg_bridge")
    v_ref_b_raw = vf.add_var("v_ref_b_raw_gfl_avg_bridge")
    v_ref_c_raw = vf.add_var("v_ref_c_raw_gfl_avg_bridge")
    v_ref_common = vf.add_var("v_ref_common_inj_gfl_avg_bridge")
    v_ref_a = vf.add_var("v_ref_a_gfl_avg_bridge")
    v_ref_b = vf.add_var("v_ref_b_gfl_avg_bridge")
    v_ref_c = vf.add_var("v_ref_c_gfl_avg_bridge")
    m_a_u = vf.add_var("m_a_u_gfl_avg_bridge")
    m_b_u = vf.add_var("m_b_u_gfl_avg_bridge")
    m_c_u = vf.add_var("m_c_u_gfl_avg_bridge")
    m_a = vf.add_var("m_a_gfl_avg_bridge")
    m_b = vf.add_var("m_b_gfl_avg_bridge")
    m_c = vf.add_var("m_c_gfl_avg_bridge")
    v_leg_a = vf.add_var("v_leg_a_gfl_avg_bridge")
    v_leg_b = vf.add_var("v_leg_b_gfl_avg_bridge")
    v_leg_c = vf.add_var("v_leg_c_gfl_avg_bridge")
    v_common_mode = vf.add_var("v_common_mode_gfl_avg_bridge")
    v_conv_a = vf.add_var("v_conv_a_gfl_avg_bridge")
    v_conv_b = vf.add_var("v_conv_b_gfl_avg_bridge")
    v_conv_c = vf.add_var("v_conv_c_gfl_avg_bridge")

    sqrt3 = Const(np.sqrt(3.0))
    eps = Const(1.0e-10)
    third = Const(1.0 / 3.0)
    half = Const(0.5)

    park_theta = Const(0.0) - theta
    raw_a = v_d_c * sym.cos(park_theta) + v_q_c * sym.sin(park_theta)
    raw_b = v_d_c * (-half * sym.cos(park_theta) - half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-half * sym.sin(park_theta) + half * sqrt3 * sym.cos(park_theta))
    raw_c = v_d_c * (-half * sym.cos(park_theta) + half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-half * sym.sin(park_theta) - half * sqrt3 * sym.cos(park_theta))
    common = Const(0.0)
    ref_a = raw_a - common
    ref_b = raw_b - common
    ref_c = raw_c - common
    v_dc_eff = sym.max(v_dc, vdc_floor)
    v_mod_scale = sym.max(k_v_conv * v_dc_eff, eps)
    v_leg_scale = k_v_conv * v_dc_eff
    m_a_u_expr = ref_a / v_mod_scale
    m_b_u_expr = ref_b / v_mod_scale
    m_c_u_expr = ref_c / v_mod_scale
    m_a_expr = sym.hard_sat(m_a_u_expr, -m_max, m_max)
    m_b_expr = sym.hard_sat(m_b_u_expr, -m_max, m_max)
    m_c_expr = sym.hard_sat(m_c_u_expr, -m_max, m_max)
    v_leg_a_expr = m_a * v_leg_scale
    v_leg_b_expr = m_b * v_leg_scale
    v_leg_c_expr = m_c * v_leg_scale
    v_common_mode_expr = third * (v_leg_a + v_leg_b + v_leg_c)
    v_conv_a_expr = v_leg_a - v_common_mode
    v_conv_b_expr = v_leg_b - v_common_mode
    v_conv_c_expr = v_leg_c - v_common_mode

    _remove_inverse_park_voltage_source(vsc_mdl)
    vsc_mdl.add(Block(
        algebraic_eqs=[
            v_ref_a_raw - raw_a,
            v_ref_b_raw - raw_b,
            v_ref_c_raw - raw_c,
            v_ref_common - common,
            v_ref_a - ref_a,
            v_ref_b - ref_b,
            v_ref_c - ref_c,
            m_a_u - m_a_u_expr,
            m_b_u - m_b_u_expr,
            m_c_u - m_c_u_expr,
            m_a - m_a_expr,
            m_b - m_b_expr,
            m_c - m_c_expr,
            v_leg_a - v_leg_a_expr,
            v_leg_b - v_leg_b_expr,
            v_leg_c - v_leg_c_expr,
            v_common_mode - v_common_mode_expr,
            v_conv_a - v_conv_a_expr,
            v_conv_b - v_conv_b_expr,
            v_conv_c - v_conv_c_expr,
            va_v - v_conv_a,
            vb_v - v_conv_b,
            vc_v - v_conv_c,
        ],
        algebraic_vars=[
            v_ref_a_raw, v_ref_b_raw, v_ref_c_raw, v_ref_common,
            v_ref_a, v_ref_b, v_ref_c,
            m_a_u, m_b_u, m_c_u, m_a, m_b, m_c,
            v_leg_a, v_leg_b, v_leg_c, v_common_mode, v_conv_a, v_conv_b, v_conv_c,
        ],
        event_dict={
            k_v_conv: vf.add_const(1.0),
            m_max: vf.add_const(10.0),
            vdc_floor: vf.add_const(0.2),
        },
        name="gfl_avg_bridge",
    ))
    vsc_mdl.unify_blocks()


def seed_avg_bridge(problem: EmtProblemDae, vsc_mdl: Block) -> None:
    def init_value(name: str, default: float = 0.0) -> float:
        var = base_validation.find_name_in_block(name, vsc_mdl)
        if var is None:
            return default
        return float(problem.init_guess.get(var.uid, default))

    theta = init_value("theta")
    v_d_c = init_value("v_d_c")
    v_q_c = init_value("v_q_c")
    v_dc = init_value("Vdc_cap", 1.0)
    k_v_conv = 1.0
    m_max = 10.0
    vdc_floor = 0.2
    v_dc_eff = max(v_dc, vdc_floor)
    v_mod_scale = max(k_v_conv * v_dc_eff, 1.0e-10)
    v_leg_scale = k_v_conv * v_dc_eff

    raw = (
        v_d_c * np.cos(-theta) + v_q_c * np.sin(-theta),
        v_d_c * (-0.5 * np.cos(-theta) - 0.5 * np.sqrt(3.0) * np.sin(-theta))
        + v_q_c * (-0.5 * np.sin(-theta) + 0.5 * np.sqrt(3.0) * np.cos(-theta)),
        v_d_c * (-0.5 * np.cos(-theta) + 0.5 * np.sqrt(3.0) * np.sin(-theta))
        + v_q_c * (-0.5 * np.sin(-theta) - 0.5 * np.sqrt(3.0) * np.cos(-theta)),
    )
    common = 0.0
    refs = tuple(value - common for value in raw)
    m_u = tuple(value / v_mod_scale for value in refs)
    m = tuple(float(np.clip(value, -m_max, m_max)) for value in m_u)
    v_legs = tuple(value * v_leg_scale for value in m)
    v_common = sum(v_legs) / 3.0
    v_conv = tuple(value - v_common for value in v_legs)

    for phase, raw_value, ref_value, m_u_value, m_value, v_leg_value, v_conv_value in zip(("a", "b", "c"), raw, refs, m_u, m, v_legs, v_conv):
        for name, value in (
            (f"v_ref_{phase}_raw_gfl_avg_bridge", raw_value),
            (f"v_ref_{phase}_gfl_avg_bridge", ref_value),
            (f"m_{phase}_u_gfl_avg_bridge", m_u_value),
            (f"m_{phase}_gfl_avg_bridge", m_value),
            (f"v_leg_{phase}_gfl_avg_bridge", v_leg_value),
            (f"v_conv_{phase}_gfl_avg_bridge", v_conv_value),
        ):
            base_validation.set_init_if_exists(problem, vsc_mdl, name, value)
    for name, value in (
        ("v_ref_common_inj_gfl_avg_bridge", common),
        ("v_common_mode_gfl_avg_bridge", v_common),
        ("va_v", v_conv[0]),
        ("vb_v", v_conv[1]),
        ("vc_v", v_conv[2]),
    ):
        base_validation.set_init_if_exists(problem, vsc_mdl, name, value)


def main() -> None:
    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = base_validation.build_grid()
    pf_results = base_validation.run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    vsc_mdl, _line23_mdl, _gen_mdl, dc_source_mdl, _vsc_filter_l, _p_ref0, _q_ref0, theta_ref = base_validation.build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3
    )
    install_avg_bridge(grid, vsc_mdl)
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
    seed_avg_bridge(problem, vsc_mdl)
    print(f"GFL internal-filter averaged bridge solver: {SOLVER_TYPE}")
    base_validation.print_problem_structure(problem)
    try:
        t, y, _dy, well_initialized, converged = base_validation.run_emt(problem=problem, options=options, t_end=options.simulation_time)
    except (np.linalg.LinAlgError, RuntimeError) as exc:
        print(f"GFL internal-filter averaged bridge solve failed during Newton iteration: {exc}")
        return
    print(f"GFL internal-filter averaged bridge well initialized: {well_initialized}")
    print(f"GFL internal-filter averaged bridge converged: {converged}")
    print(f"Solved samples: {len(t)}")
    for name in ("P", "Q", "v_d_c", "v_q_c", "va_v", "vb_v", "vc_v"):
        var = base_validation.find_name_in_block(name, vsc_mdl)
        if var is not None and var.uid in problem._uid2idx_vars:
            trace = y[:, problem.get_var_idx(var)]
            print(f"{name}: t0={trace[0]: .9e}, final={trace[-1]: .9e}")


if __name__ == "__main__":
    main()
