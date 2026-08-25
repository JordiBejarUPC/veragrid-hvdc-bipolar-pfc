# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import sys

import numpy as np
import matplotlib.pyplot as plt

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


SIM_TIME = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_SOFT_GATE_SIM_TIME", "2e-5"))
TIME_STEP = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_SOFT_GATE_TIME_STEP", "1e-6"))
SOFT_LAMDA = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_SOFT_GATE_LAMDA", "1e-4"))
HANDOVER_TIME = float(os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_SOFT_GATE_HANDOVER_TIME", "1e-4"))
SOLVER_TYPE = os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_SOFT_GATE_SOLVER", "StructuralAD")
COUPLE_GATE_OUTPUT = os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_SOFT_GATE_COUPLED", "0") != "0"
USE_HANDOVER = os.environ.get("VERAGRID_GFL_INTERNAL_FILTER_MIN_SOFT_GATE_HANDOVER", "0") != "0"
PLOT_DIR = os.environ.get(
    "VERAGRID_GFL_INTERNAL_FILTER_MIN_SOFT_GATE_PLOT_DIR",
    os.path.join(os.path.dirname(__file__), "gfl_vsc_emt_internal_filter_minimal_soft_gate_plots"),
)


def remove_converter_voltage_source(vsc_mdl: Block) -> None:
    """
    Remove converter voltage equations.

    :param vsc_mdl: VSC symbolic model.
    :return: None.
    """
    for block in vsc_mdl.get_all_blocks():
        block.algebraic_eqs = [
            eq for eq in block.algebraic_eqs
            if not (str(eq).startswith("(va_v) - ") or str(eq).startswith("(vb_v) - ") or str(eq).startswith("(vc_v) - "))
        ]


def install_minimal_soft_gate_bridge(grid, vsc_mdl: Block) -> None:
    """
    Install a minimal direct soft-gate bridge diagnostic.

    :param grid: Grid containing the variable factory.
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

    m_a = vf.add_var("m_a_min_soft_gate_bridge")
    m_b = vf.add_var("m_b_min_soft_gate_bridge")
    m_c = vf.add_var("m_c_min_soft_gate_bridge")
    gate_a = vf.add_var("gate_a_min_soft_gate_bridge")
    gate_b = vf.add_var("gate_b_min_soft_gate_bridge")
    gate_c = vf.add_var("gate_c_min_soft_gate_bridge")
    switching_enabled = vf.add_var("switching_enabled_min_soft_gate_bridge")
    t_enable = vf.add_var("t_enable_min_soft_gate_bridge")
    v_leg_a = vf.add_var("v_leg_a_min_soft_gate_bridge")
    v_leg_b = vf.add_var("v_leg_b_min_soft_gate_bridge")
    v_leg_c = vf.add_var("v_leg_c_min_soft_gate_bridge")
    v_common = vf.add_var("v_common_min_soft_gate_bridge")
    v_gate_a = vf.add_var("v_gate_a_min_soft_gate_bridge")
    v_gate_b = vf.add_var("v_gate_b_min_soft_gate_bridge")
    v_gate_c = vf.add_var("v_gate_c_min_soft_gate_bridge")

    half = Const(0.5)
    one = Const(1.0)
    two = Const(2.0)
    three = Const(3.0)
    eps = Const(1.0e-10)
    lamda = Const(SOFT_LAMDA)
    sqrt3 = Const(np.sqrt(3.0))
    park_theta = Const(0.0) - theta
    v_scale = sym.max(half * v_dc, eps)
    va_expr = v_d_c * sym.cos(park_theta) + v_q_c * sym.sin(park_theta)
    vb_expr = v_d_c * (-half * sym.cos(park_theta) - half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-half * sym.sin(park_theta) + half * sqrt3 * sym.cos(park_theta))
    vc_expr = v_d_c * (-half * sym.cos(park_theta) + half * sqrt3 * sym.sin(park_theta)) + v_q_c * (-half * sym.sin(park_theta) - half * sqrt3 * sym.cos(park_theta))
    gate_a_expr = half * (one + m_a / sym.sqrt(m_a * m_a + lamda))
    gate_b_expr = half * (one + m_b / sym.sqrt(m_b * m_b + lamda))
    gate_c_expr = half * (one + m_c / sym.sqrt(m_c * m_c + lamda))
    handover_mode = switching_enabled if USE_HANDOVER else one
    coupled_a = (one - handover_mode) * va_expr + handover_mode * v_gate_a if COUPLE_GATE_OUTPUT else va_expr
    coupled_b = (one - handover_mode) * vb_expr + handover_mode * v_gate_b if COUPLE_GATE_OUTPUT else vb_expr
    coupled_c = (one - handover_mode) * vc_expr + handover_mode * v_gate_c if COUPLE_GATE_OUTPUT else vc_expr

    remove_converter_voltage_source(vsc_mdl)
    vsc_mdl.add(Block(
        algebraic_eqs=[
            m_a - va_expr / v_scale,
            m_b - vb_expr / v_scale,
            m_c - vc_expr / v_scale,
            gate_a - gate_a_expr,
            gate_b - gate_b_expr,
            gate_c - gate_c_expr,
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
        event_dict={t_enable: vf.add_const(HANDOVER_TIME)},
        mode_dict={switching_enabled: vf.add_const(0.0)},
        procedural_logic=[startup_handover(mode=switching_enabled, t_enable=t_enable, name="minimal_soft_gate_startup_handover")],
        name="gfl_minimal_soft_gate_bridge",
    ))
    vsc_mdl.unify_blocks()


def seed_minimal_soft_gate(problem: EmtProblemDae, vsc_mdl: Block) -> None:
    """
    Seed minimal soft-gate variables.

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
    gate_values = tuple(0.5 * (1.0 + value / np.sqrt(value * value + SOFT_LAMDA)) for value in m_values)
    leg_values = tuple((2.0 * value - 1.0) * v_scale for value in gate_values)
    common_value = sum(leg_values) / 3.0
    gate_phase_values = tuple(value - common_value for value in leg_values)
    for phase, m_value, gate_value, leg_value, gate_phase_value in zip(("a", "b", "c"), m_values, gate_values, leg_values, gate_phase_values):
        base_validation.set_init_if_exists(problem, vsc_mdl, f"m_{phase}_min_soft_gate_bridge", m_value)
        base_validation.set_init_if_exists(problem, vsc_mdl, f"gate_{phase}_min_soft_gate_bridge", gate_value)
        base_validation.set_init_if_exists(problem, vsc_mdl, f"v_leg_{phase}_min_soft_gate_bridge", leg_value)
        base_validation.set_init_if_exists(problem, vsc_mdl, f"v_gate_{phase}_min_soft_gate_bridge", gate_phase_value)
    base_validation.set_init_if_exists(problem, vsc_mdl, "v_common_min_soft_gate_bridge", common_value)


def trace_or_none(problem: EmtProblemDae, y: np.ndarray, vsc_mdl: Block, name: str) -> np.ndarray | None:
    """
    Return a variable trace if it exists in the EMT problem.

    :param problem: EMT problem.
    :param y: State and algebraic solution matrix.
    :param vsc_mdl: VSC symbolic model.
    :param name: Variable name.
    :return: Variable trace or None.
    """
    var = base_validation.find_name_in_block(name, vsc_mdl)
    if var is None:
        trace = None
    elif var.uid not in problem._uid2idx_vars:
        trace = None
    else:
        trace = y[:, problem.get_var_idx(var)]
    return trace


def print_trace_summary(problem: EmtProblemDae, y: np.ndarray, vsc_mdl: Block, names: tuple[str, ...]) -> None:
    """
    Print start and final values for selected traces.

    :param problem: EMT problem.
    :param y: State and algebraic solution matrix.
    :param vsc_mdl: VSC symbolic model.
    :param names: Variable names to print.
    :return: None.
    """
    for name in names:
        trace = trace_or_none(problem, y, vsc_mdl, name)
        if trace is None:
            print(f"{name}: <missing>")
        else:
            print(f"{name}: t0={trace[0]: .9e}, final={trace[-1]: .9e}")


def save_plots(problem: EmtProblemDae, t: np.ndarray, y: np.ndarray, vsc_mdl: Block) -> None:
    """
    Save minimal soft-gate diagnostic plots.

    :param problem: EMT problem.
    :param t: Time vector.
    :param y: State and algebraic solution matrix.
    :param vsc_mdl: VSC symbolic model.
    :return: None.
    """
    os.makedirs(PLOT_DIR, exist_ok=True)
    groups: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("power", ("P", "Q")),
        ("converter_voltage", ("va_v", "vb_v", "vc_v")),
        ("dq_voltage", ("v_d_c", "v_q_c")),
        ("soft_gates", ("gate_a_min_soft_gate_bridge", "gate_b_min_soft_gate_bridge", "gate_c_min_soft_gate_bridge")),
        ("soft_modulation", ("m_a_min_soft_gate_bridge", "m_b_min_soft_gate_bridge", "m_c_min_soft_gate_bridge")),
        ("soft_gate_voltage", ("v_gate_a_min_soft_gate_bridge", "v_gate_b_min_soft_gate_bridge", "v_gate_c_min_soft_gate_bridge")),
    )
    for plot_name, names in groups:
        fig, ax = plt.subplots(figsize=(10.0, 5.0))
        plotted = False
        for name in names:
            trace = trace_or_none(problem, y, vsc_mdl, name)
            if trace is None:
                pass
            else:
                ax.plot(t, trace, label=name)
                plotted = True
        if plotted:
            ax.set_xlabel("time [s]")
            if USE_HANDOVER:
                ax.axvline(HANDOVER_TIME, color="black", linestyle="--", linewidth=1.0, label="handover")
            else:
                pass
            ax.grid(True)
            ax.legend(loc="best")
            fig.tight_layout()
            fig.savefig(os.path.join(PLOT_DIR, f"{plot_name}.png"), dpi=140)
        else:
            pass
        plt.close(fig)


def main() -> None:
    """
    Run the minimal soft-gate diagnostic.

    :return: None.
    """
    grid, bus_dc, bus2, bus3, line23, vsc1, gen1, dc_source = base_validation.build_grid()
    pf_results = base_validation.run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    vsc_mdl, _line23_mdl, _gen_mdl, dc_source_mdl, _vsc_filter_l, _p_ref0, _q_ref0, theta_ref = base_validation.build_emt_models(
        grid, line23, vsc1, gen1, dc_source, pf_results, bus_dc, bus2, bus3
    )
    install_minimal_soft_gate_bridge(grid, vsc_mdl)
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
    seed_minimal_soft_gate(problem, vsc_mdl)
    print(f"GFL internal-filter minimal soft gate solver: {SOLVER_TYPE}")
    print(f"GFL internal-filter minimal soft gate coupled: {COUPLE_GATE_OUTPUT}")
    print(f"GFL internal-filter minimal soft gate handover enabled: {USE_HANDOVER}")
    print(f"GFL internal-filter minimal soft gate handover time: {HANDOVER_TIME:.9e} s")
    print(f"GFL internal-filter minimal soft gate lambda: {SOFT_LAMDA:.9e}")
    base_validation.print_problem_structure(problem)
    t, y, _dy, well_initialized, converged = base_validation.run_emt(problem=problem, options=options, t_end=options.simulation_time)
    print(f"GFL internal-filter minimal soft gate well initialized: {well_initialized}")
    print(f"GFL internal-filter minimal soft gate converged: {converged}")
    print(f"Solved samples: {len(t)}")
    print_trace_summary(
        problem,
        y,
        vsc_mdl,
        ("P", "Q", "v_d_c", "v_q_c", "va_v", "vb_v", "vc_v", "gate_a_min_soft_gate_bridge", "gate_b_min_soft_gate_bridge", "gate_c_min_soft_gate_bridge"),
    )
    save_plots(problem, t, y, vsc_mdl)
    print(f"Plots saved to: {PLOT_DIR}")


if __name__ == "__main__":
    main()
