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


SIM_TIME = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_HARD_GATE_SIM_TIME", "2e-5"))
TIME_STEP = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_HARD_GATE_TIME_STEP", "1e-6"))
SOLVER_TYPE = os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_HARD_GATE_SOLVER", "StructuralAD")
COUPLE_GATE_OUTPUT = os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_HARD_GATE_COUPLED", "0") != "0"


def remove_converter_voltage_source(vsc_mdl: Block) -> None:
    """
    Remove the existing converter voltage source equations.

    :param vsc_mdl: VSC symbolic model.
    :return: None.
    """
    for block in vsc_mdl.get_all_blocks():
        block.algebraic_eqs = [
            eq for eq in block.algebraic_eqs
            if not (str(eq).startswith("(va_v) - ") or str(eq).startswith("(vb_v) - ") or str(eq).startswith("(vc_v) - "))
        ]


def install_minimal_hard_gate_bridge(grid, vsc_mdl: Block) -> None:
    """
    Install a minimal hard-gate bridge diagnostic.

    :param grid: Grid containing the shared variable factory.
    :param vsc_mdl: VSC symbolic model.
    :return: None.
    """
    vf = grid.var_factory
    theta = base_validation.find_name_in_block("theta", vsc_mdl)
    v_d_c = base_validation.find_name_in_block("v_d_c", vsc_mdl)
    v_q_c = base_validation.find_name_in_block("v_q_c", vsc_mdl)
    v_dc = base_validation.find_name_in_block("Vdc_cap", vsc_mdl)
    va_v = base_validation.find_name_in_block("va_v", vsc_mdl)
    vb_v = base_validation.find_name_in_block("vb_v", vsc_mdl)
    vc_v = base_validation.find_name_in_block("vc_v", vsc_mdl)

    m_a = vf.add_var("m_a_min_hard_gate_bridge")
    m_b = vf.add_var("m_b_min_hard_gate_bridge")
    m_c = vf.add_var("m_c_min_hard_gate_bridge")
    gate_a = vf.add_var("gate_a_min_hard_gate_bridge")
    gate_b = vf.add_var("gate_b_min_hard_gate_bridge")
    gate_c = vf.add_var("gate_c_min_hard_gate_bridge")
    v_leg_a = vf.add_var("v_leg_a_min_hard_gate_bridge")
    v_leg_b = vf.add_var("v_leg_b_min_hard_gate_bridge")
    v_leg_c = vf.add_var("v_leg_c_min_hard_gate_bridge")
    v_common = vf.add_var("v_common_min_hard_gate_bridge")
    v_gate_a = vf.add_var("v_gate_a_min_hard_gate_bridge")
    v_gate_b = vf.add_var("v_gate_b_min_hard_gate_bridge")
    v_gate_c = vf.add_var("v_gate_c_min_hard_gate_bridge")

    half = Const(0.5)
    one = Const(1.0)
    two = Const(2.0)
    three = Const(3.0)
    eps = Const(1.0e-10)
    sqrt3 = Const(np.sqrt(3.0))
    park_theta = Const(0.0) - theta
    v_scale = sym.max(half * v_dc, eps)
    va_expr = v_d_c * sym.cos(park_theta) + v_q_c * sym.sin(park_theta)
    vb_expr = v_d_c * (-half * sym.cos(park_theta) - half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-half * sym.sin(park_theta) + half * sqrt3 * sym.cos(park_theta))
    vc_expr = v_d_c * (-half * sym.cos(park_theta) + half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-half * sym.sin(park_theta) - half * sqrt3 * sym.cos(park_theta))
    coupled_a = v_gate_a if COUPLE_GATE_OUTPUT else va_expr
    coupled_b = v_gate_b if COUPLE_GATE_OUTPUT else vb_expr
    coupled_c = v_gate_c if COUPLE_GATE_OUTPUT else vc_expr

    remove_converter_voltage_source(vsc_mdl)
    vsc_mdl.add(Block(
        algebraic_eqs=[
            m_a - va_expr / v_scale,
            m_b - vb_expr / v_scale,
            m_c - vc_expr / v_scale,
            gate_a - sym.heaviside(m_a),
            gate_b - sym.heaviside(m_b),
            gate_c - sym.heaviside(m_c),
            v_leg_a - (two * gate_a - one) * v_scale,
            v_leg_b - (two * gate_b - one) * v_scale,
            v_leg_c - (two * gate_c - one) * v_scale,
            v_common - (v_leg_a + v_leg_b + v_leg_c) / three,
            v_gate_a - (v_leg_a - v_common),
            v_gate_b - (v_leg_b - v_common),
            v_gate_c - (v_leg_c - v_common),
            va_v - coupled_a,
            vb_v - coupled_b,
            vc_v - coupled_c,
        ],
        algebraic_vars=[m_a, m_b, m_c, gate_a, gate_b, gate_c, v_leg_a, v_leg_b, v_leg_c, v_common, v_gate_a, v_gate_b, v_gate_c],
        name="gfl_minimal_hard_gate_bridge",
    ))
    vsc_mdl.unify_blocks()


def seed_minimal_hard_gate(problem: EmtProblemDae, vsc_mdl: Block) -> None:
    """
    Seed the minimal hard-gate auxiliary variables.

    :param problem: EMT problem.
    :param vsc_mdl: VSC symbolic model.
    :return: None.
    """
    theta = float(problem.init_guess[base_validation.find_name_in_block("theta", vsc_mdl).uid])
    v_d_c = float(problem.init_guess[base_validation.find_name_in_block("v_d_c", vsc_mdl).uid])
    v_q_c = float(problem.init_guess[base_validation.find_name_in_block("v_q_c", vsc_mdl).uid])
    v_dc = float(problem.init_guess[base_validation.find_name_in_block("Vdc_cap", vsc_mdl).uid])
    park_theta = -theta
    v_scale = max(0.5 * v_dc, 1.0e-10)
    va_value = v_d_c * np.cos(park_theta) + v_q_c * np.sin(park_theta)
    vb_value = v_d_c * (-0.5 * np.cos(park_theta) - 0.5 * np.sqrt(3.0) * np.sin(park_theta)) + v_q_c * (-0.5 * np.sin(park_theta) + 0.5 * np.sqrt(3.0) * np.cos(park_theta))
    vc_value = v_d_c * (-0.5 * np.cos(park_theta) + 0.5 * np.sqrt(3.0) * np.sin(park_theta)) + v_q_c * (-0.5 * np.sin(park_theta) - 0.5 * np.sqrt(3.0) * np.cos(park_theta))
    m_values = (va_value / v_scale, vb_value / v_scale, vc_value / v_scale)
    gate_values = tuple(1.0 if value >= 0.0 else 0.0 for value in m_values)
    leg_values = tuple((2.0 * value - 1.0) * v_scale for value in gate_values)
    common_value = sum(leg_values) / 3.0
    gate_phase_values = tuple(value - common_value for value in leg_values)
    for phase, m_value, gate_value, leg_value, gate_phase_value in zip(("a", "b", "c"), m_values, gate_values, leg_values, gate_phase_values):
        base_validation.set_init_if_exists(problem, vsc_mdl, f"m_{phase}_min_hard_gate_bridge", m_value)
        base_validation.set_init_if_exists(problem, vsc_mdl, f"gate_{phase}_min_hard_gate_bridge", gate_value)
        base_validation.set_init_if_exists(problem, vsc_mdl, f"v_leg_{phase}_min_hard_gate_bridge", leg_value)
        base_validation.set_init_if_exists(problem, vsc_mdl, f"v_gate_{phase}_min_hard_gate_bridge", gate_phase_value)
    base_validation.set_init_if_exists(problem, vsc_mdl, "v_common_min_hard_gate_bridge", common_value)


def main() -> None:
    """
    Run the minimal hard-gate diagnostic.

    :return: None.
    """
    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = base_validation.build_grid()
    pf_results = base_validation.run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    vsc_mdl, _line23_mdl, _gen_mdl, dc_source_mdl, _vsc_filter_l, _p_ref0, _q_ref0, theta_ref = base_validation.build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3
    )
    install_minimal_hard_gate_bridge(grid, vsc_mdl)
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
    seed_minimal_hard_gate(problem, vsc_mdl)
    print(f"GFL internal-filter minimal hard gate solver: {SOLVER_TYPE}")
    print(f"GFL internal-filter minimal hard gate coupled: {COUPLE_GATE_OUTPUT}")
    base_validation.print_problem_structure(problem)
    t, _y, _dy, well_initialized, converged = base_validation.run_emt(problem=problem, options=options, t_end=options.simulation_time)
    print(f"GFL internal-filter minimal hard gate well initialized: {well_initialized}")
    print(f"GFL internal-filter minimal hard gate converged: {converged}")
    print(f"Solved samples: {len(t)}")


if __name__ == "__main__":
    main()
