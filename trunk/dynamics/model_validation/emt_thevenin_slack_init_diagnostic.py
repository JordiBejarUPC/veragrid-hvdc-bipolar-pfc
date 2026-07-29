#!/usr/bin/env python3
"""Diagnose Thevenin slack initialization in the simplified GFM EMT case."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import VeraGridEngine.api as vge
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes

from emt_gfm_model import find_name_in_block
from emt_gfm_model_validation import (
    attach_emt_models,
    create_simplified_grid,
    print_bus_kcl_residuals,
    print_case_kcl_residuals,
    print_global_state_residuals,
    run_emt,
    run_power_flow,
    seed_bus_algebraic_predictors,
    seed_gfm_from_power_flow,
    seed_line_current_predictors,
    trace,
    uid_bindings_from_problem,
)


def working_model(problem: EmtProblemDae, device):
    models = getattr(problem, "_working_emt_models", {})
    return models.get(str(device.idtag), device.emt_model)


def x_value(problem: EmtProblemDae, block, name: str) -> float:
    var = find_name_in_block(name, block)
    if var is None or var.uid not in problem._uid2idx_vars:
        return float("nan")
    return float(problem.get_x0()[problem.get_var_idx(var)])


def x_value_matching(problem: EmtProblemDae, block, prefix: str, phase: str) -> float:
    for var in list(block.state_vars) + list(block.algebraic_vars) + list(block.out_vars):
        if var.name.startswith(prefix) and var.name.endswith(f"_{phase}") and var.uid in problem._uid2idx_vars:
            return float(problem.get_x0()[problem.get_var_idx(var)])
    return float("nan")


def event_value(problem: EmtProblemDae, block, name: str) -> float:
    var = find_name_in_block(name, block)
    uid2idx = getattr(problem, "_uid2idx_event_params", getattr(problem, "uid2idx_event_params", {}))
    if var is None or var.uid not in uid2idx:
        return float("nan")
    return float(problem._event_params_values[uid2idx[var.uid]])


def set_x_value(problem: EmtProblemDae, block, name: str, value: float) -> None:
    var = find_name_in_block(name, block)
    if var is not None and var.uid in problem._uid2idx_vars:
        problem.init_guess[var.uid] = float(value)


def set_event_value(problem: EmtProblemDae, block, name: str, value: float) -> None:
    var = find_name_in_block(name, block)
    uid2idx = getattr(problem, "_uid2idx_event_params", getattr(problem, "uid2idx_event_params", {}))
    if var is not None and var.uid in uid2idx:
        idx = uid2idx[var.uid]
        problem._event_params_values[idx] = float(value)
        if hasattr(problem, "event_params_values"):
            problem.event_params_values[idx] = float(value)


def diff_value(problem: EmtProblemDae, block, name: str) -> float:
    var = find_name_in_block(name, block)
    if var is None or var.diff_var is None:
        return float("nan")
    return float(problem.diff_init_guess.get(var.diff_var.uid, 0.0))


def phasor_from_abc(phase_a: complex, phase_b: complex, phase_c: complex) -> complex:
    a = np.exp(1j * 2.0 * np.pi / 3.0)
    return complex((phase_a + a * phase_b + a * a * phase_c) / 3.0)


def print_thevenin_reference_report(problem: EmtProblemDae, grid: vge.MultiCircuit, devices: dict) -> None:
    source = working_model(problem, devices["gen_slack"])
    line = working_model(problem, devices["line13"])
    bus = working_model(problem, devices["bus_slack"])

    phi_v = event_value(problem, source, "phi_v")
    phi = event_value(problem, source, "phi")
    vpk = event_value(problem, source, "Vpk")
    ipk = event_value(problem, source, "Ipk")
    r_s = event_value(problem, source, "R_s")
    x_s = event_value(problem, source, "X_s")
    if not np.isfinite(r_s):
        r_s = float(devices["gen_slack"].R1)
    if not np.isfinite(x_s):
        x_s = float(devices["gen_slack"].X1)

    theta = x_value(problem, source, "theta")
    e_a = x_value(problem, source, "e_A")
    e_b = x_value(problem, source, "e_B")
    e_c = x_value(problem, source, "e_C")
    i_a = x_value(problem, source, "i_A")
    i_b = x_value(problem, source, "i_B")
    i_c = x_value(problem, source, "i_C")
    v_a = x_value(problem, bus, "v_A")
    v_b = x_value(problem, bus, "v_B")
    v_c = x_value(problem, bus, "v_C")

    e_re = vpk + r_s * ipk * np.cos(phi) - x_s * ipk * np.sin(phi)
    e_im = r_s * ipk * np.sin(phi) + x_s * ipk * np.cos(phi)
    theta_expected = phi_v + np.arctan2(e_im, e_re)
    epk_expected = float(np.hypot(e_re, e_im))

    print("Thevenin slack PF/event references:")
    print(f"  phi_v={phi_v:.9e}, phi={phi:.9e}, Vpk={vpk:.9e}, Ipk={ipk:.9e}")
    print(f"  R_s={r_s:.9e}, X_s={x_s:.9e}")
    print("Thevenin initialized internal source:")
    print(f"  theta={theta:.9e}, theta_expected={theta_expected:.9e}, diff={theta - theta_expected:.3e}")
    print(f"  Epk_expected={epk_expected:.9e}")
    print(f"  e_A={e_a:.9e}, e_B={e_b:.9e}, e_C={e_c:.9e}")
    print("Thevenin terminal samples:")
    print(f"  v_A={v_a:.9e}, v_B={v_b:.9e}, v_C={v_c:.9e}")
    print(f"  i_A={i_a:.9e}, i_B={i_b:.9e}, i_C={i_c:.9e}")
    print(f"  d_i_A={diff_value(problem, source, 'i_A'):.9e}, d_i_B={diff_value(problem, source, 'i_B'):.9e}, d_i_C={diff_value(problem, source, 'i_C'):.9e}")

    v1 = phasor_from_abc(v_a, v_b, v_c)
    i1 = phasor_from_abc(i_a, i_b, i_c)
    e1 = v1 + complex(r_s, x_s) * i1
    print("Positive-sequence reconstruction from initialized abc:")
    print(f"  |V1|pk={np.sqrt(2.0) * abs(v1):.9e}, angle(V1)={np.angle(v1):.9e}")
    print(f"  |I1|pk={np.sqrt(2.0) * abs(i1):.9e}, angle(I1)-angle(V1)={np.angle(i1) - np.angle(v1):.9e}")
    print(f"  |E1|pk={np.sqrt(2.0) * abs(e1):.9e}, angle(E1)={np.angle(e1):.9e}")

    print("Slack source versus Line13 terminal current:")
    for phase in ("A", "B", "C"):
        source_i = x_value(problem, source, f"i_{phase}")
        line_it = x_value_matching(problem, line, "it_", phase)
        print(
            f"  phase {phase}: source_i={source_i:.9e}, "
            f"line_it={line_it:.9e}, source_i-line_it={source_i - line_it:.9e}"
        )


def print_thevenin_state_residuals(problem: EmtProblemDae, devices: dict) -> None:
    source = working_model(problem, devices["gen_slack"])
    bindings = uid_bindings_from_problem(problem)
    for parameter, value in zip(problem.get_constant_parameters(), problem.get_parameters_values()):
        bindings[parameter.uid] = float(value.value)

    print("Thevenin slack state residuals at seeded x0:")
    for state_var, diff_var, eq in zip(source.state_vars, source.diff_vars, source.state_eqs):
        rhs = float(eq.eval_uid(bindings))
        d_init = float(problem.diff_init_guess.get(diff_var.uid, 0.0))
        print(f"  {state_var.name}: rhs={rhs:.9e}, d_init={d_init:.9e}, residual={rhs - d_init:.9e}")


def reseed_thevenin_from_line_current(problem: EmtProblemDae, grid: vge.MultiCircuit, devices: dict) -> None:
    source = working_model(problem, devices["gen_slack"])
    line = working_model(problem, devices["line13"])

    phi_v = event_value(problem, source, "phi_v")
    phi = event_value(problem, source, "phi")
    vpk = event_value(problem, source, "Vpk")
    ipk = event_value(problem, source, "Ipk")
    r_s = float(devices["gen_slack"].R1)
    x_s = float(devices["gen_slack"].X1)
    omega_base = 2.0 * np.pi * grid.fBase

    line_currents = {
        phase: x_value_matching(problem, line, "it_", phase)
        for phase in ("A", "B", "C")
    }
    source_current_a = x_value(problem, source, "i_A")
    line_current_a = line_currents["A"]
    current_scale = line_current_a / source_current_a if abs(source_current_a) > 1.0e-12 else 1.0
    ipk = float(ipk * current_scale)

    e_re = vpk + r_s * ipk * np.cos(phi) - x_s * ipk * np.sin(phi)
    e_im = r_s * ipk * np.sin(phi) + x_s * ipk * np.cos(phi)
    theta = float(phi_v + np.arctan2(e_im, e_re))
    epk = float(np.hypot(e_re, e_im))
    e_values = {
        "A": epk * np.sin(theta),
        "B": epk * np.sin(theta - 2.0 * np.pi / 3.0),
        "C": epk * np.sin(theta + 2.0 * np.pi / 3.0),
    }

    set_event_value(problem, source, "Ipk", ipk)
    set_x_value(problem, source, "theta", theta)
    for phase in ("A", "B", "C"):
        set_x_value(problem, source, f"i_{phase}", line_currents[phase])
        set_x_value(problem, source, f"e_{phase}", e_values[phase])
        state_var = find_name_in_block(f"i_{phase}", source)
        if state_var is not None and state_var.diff_var is not None:
            v_phase = x_value(problem, working_model(problem, devices["bus_slack"]), f"v_{phase}")
            rhs = omega_base * (e_values[phase] - r_s * line_currents[phase] - v_phase) / x_s
            problem.diff_init_guess[state_var.diff_var.uid] = float(rhs)

    theta_var = find_name_in_block("theta", source)
    if theta_var is not None and theta_var.diff_var is not None:
        problem.diff_init_guess[theta_var.diff_var.uid] = omega_base

    print(f"Applied line-current-consistent Thevenin reseed: Ipk scale={current_scale:.9e}")


def main() -> None:
    os.environ["VERAGRID_GFM_EMT_SLACK_SOURCE"] = "thevenin"

    grid, devices = create_simplified_grid()
    pf_results = run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    print(pf_results.get_bus_df())
    print(pf_results.get_branch_df())

    gfm_block = attach_emt_models(grid, devices, pf_results=pf_results)
    options = EmtOptions(
        time_step=float(os.environ.get("VERAGRID_GFM_EMT_TIME_STEP", "1e-5")),
        simulation_time=float(os.environ.get("VERAGRID_GFM_EMT_SIM_TIME", "1e-5")),
        tolerance=1.0e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        solver_type=EmtSolverTypes.StructuralAD,
        initialization_method=EmtInitializationMethod.Explicit,
        init_newton_max_iter=200,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results)

    seed_gfm_from_power_flow(problem, grid, pf_results, gfm_block, devices["bus_gfm"])
    seed_bus_algebraic_predictors(problem, grid, pf_results)
    seed_line_current_predictors(problem, grid, pf_results, devices)

    print_thevenin_reference_report(problem, grid, devices)
    print_thevenin_state_residuals(problem, devices)
    print_global_state_residuals(problem)
    print_bus_kcl_residuals(problem, grid)
    print_case_kcl_residuals(problem, devices, gfm_block)

    print("\nAfter line-current-consistent slack reseed:")
    reseed_thevenin_from_line_current(problem, grid, devices)
    print_thevenin_reference_report(problem, grid, devices)
    print_thevenin_state_residuals(problem, devices)
    print_global_state_residuals(problem)
    print_bus_kcl_residuals(problem, grid)
    print_case_kcl_residuals(problem, devices, gfm_block)

    print("Running one-step EMT check after reseed")
    t, y, _dy, well_initialized, converged = run_emt(problem, options, options.simulation_time)
    print(f"  EMT well initialized: {well_initialized}")
    print(f"  EMT converged: {converged}")
    if len(t) > 0:
        for name in ("P", "Q", "vd_g", "vq_g", "id_g", "iq_g"):
            values = trace(problem, y, name, gfm_block)
            print(f"  {name}: t0={values[0]: .9e}, final={values[-1]: .9e}")


if __name__ == "__main__":
    main()
