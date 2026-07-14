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
SWITCHING_FREQUENCY = float(os.environ.get("VERAGRID_GFL_EMT_MTI_FSW", "1000.0"))
PREF_EVENT_TIME = float(os.environ.get("VERAGRID_GFL_EMT_MTI_PREF_EVENT_TIME", "0.005"))
PREF_EVENT_DELTA = float(os.environ.get("VERAGRID_GFL_EMT_MTI_PREF_EVENT_DELTA", "0.01"))


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

    _remove_inverse_park_voltage_source(vsc_mdl)
    vsc_mdl.add(bridge)

    sources = [theta, omega_base, v_d_c, v_q_c, v_zero, v_dc, k_v_conv, m_max, vdc_floor, omega_sw, carrier_phase]
    for target, source in zip(bridge.in_vars, sources):
        vsc_mdl.update_model(target, source)

    va_v = find_name_in_block("va_v", vsc_mdl)
    vb_v = find_name_in_block("vb_v", vsc_mdl)
    vc_v = find_name_in_block("vc_v", vsc_mdl)
    v_conv_a = find_name_in_block("v_conv_a_gfl_mti_bridge", bridge)
    v_conv_b = find_name_in_block("v_conv_b_gfl_mti_bridge", bridge)
    v_conv_c = find_name_in_block("v_conv_c_gfl_mti_bridge", bridge)
    vsc_mdl.add(Block(algebraic_eqs=[va_v - v_conv_a, vb_v - v_conv_b, vc_v - v_conv_c], name="mti_bridge_voltage_port"))
    vsc_mdl.add(Block(event_dict={
        omega_base: vf.add_const(2.0 * np.pi * grid.fBase),
        v_zero: vf.add_const(0.0),
        k_v_conv: vf.add_const(0.5),
        m_max: vf.add_const(0.98),
        vdc_floor: vf.add_const(0.2),
        omega_sw: vf.add_const(2.0 * np.pi * SWITCHING_FREQUENCY),
        carrier_phase: vf.add_const(0.0),
    }, name="mti_bridge_runtime_inputs"))
    vsc_mdl.unify_blocks()
    return bridge


def seed_mti_bridge(problem: EmtProblemMTI, vsc_mdl: Block) -> None:
    for name, value in (
        ("carrier_pwm_gfl_mti_bridge", -1.0),
        ("gate_pwm_a_gfl_mti_bridge", 1.0),
        ("gate_pwm_b_gfl_mti_bridge", 1.0),
        ("gate_pwm_c_gfl_mti_bridge", 1.0),
        ("v_zero_mti_bridge", 0.0),
        ("k_v_conv_mti_bridge", 0.5),
        ("m_max_mti_bridge", 0.98),
        ("vdc_floor_mti_bridge", 0.2),
        ("omega_sw_mti_bridge", 2.0 * np.pi * SWITCHING_FREQUENCY),
        ("carrier_phase_mti_bridge", 0.0),
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


def plot_mti_bridge_traces(t: np.ndarray, problem: EmtProblemMTI, y: np.ndarray, vsc_mdl: Block) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    plt.figure(figsize=(10, 5))
    for name in ("gate_pwm_a_gfl_mti_bridge", "gate_pwm_b_gfl_mti_bridge", "gate_pwm_c_gfl_mti_bridge"):
        tr = trace_for_var(problem, y, find_name_in_block(name, vsc_mdl))
        if tr is not None:
            plt.step(t, tr, where="post", label=name)
    plt.xlabel("Time [s]")
    plt.ylabel("Gate")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, "mti_bridge_gates.png"), dpi=150)
    plt.close()


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

    solver = EmtMtiBackEulerSolver(
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        max_iter=options.init_newton_max_iter,
        tolerance=options.tolerance,
    )
    t, y, _dy, well_initialized, converged = solver.simulate()
    print(f"EMT-MTI well initialized: {well_initialized}")
    print(f"EMT-MTI converged: {converged}")
    print(f"Solved samples: {len(t)}")
    print(f"MTI boolean shape: {solver.z.shape}")

    for name in ("P", "Q", "v_d_c", "v_q_c", "carrier_pwm_gfl_mti_bridge"):
        var = find_name_in_block(name, vsc_mdl)
        if var is not None and var.uid in problem._uid2idx_vars:
            trace = y[:, problem.get_var_idx(var)]
            print(f"{name}: t0={trace[0]: .9e}, final={trace[-1]: .9e}")

    plot_mti_bridge_traces(t, problem, y, vsc_mdl)
    plot_traces(t, problem, y, vsc_mdl, bus_dc, bus2, p_ref0)
    print(f"MTI bridge plots saved to: {PLOT_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
