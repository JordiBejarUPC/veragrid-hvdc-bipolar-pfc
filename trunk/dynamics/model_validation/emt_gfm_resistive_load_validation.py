#!/usr/bin/env python3
"""Validate an EMT GFM source feeding a balanced resistive load."""

from __future__ import annotations

import os
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import VeraGridEngine.api as vge
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import EmtInitializationMethod, EmtSolverTypes

from emt_gfm_model import build_emt_gfm_model, find_name_in_block
from emt_gfm_model_validation import (
    apply_gfm_gain_overrides,
    integration_method_from_env,
    print_bus_kcl_residuals,
    print_gfm_algebraic_residuals,
    print_gfm_state_residuals,
    print_global_state_residuals,
    run_emt,
    run_emt_with_p_ref_step,
    run_power_flow,
    seed_bus_algebraic_predictors,
    seed_gfm_from_power_flow,
    seed_line_current_predictors,
    set_runtime_param_in_vector,
    set_block_event_value,
    trace,
)


TIME_STEP = float(os.environ.get("VERAGRID_GFM_RLOAD_TIME_STEP", "1e-5"))
SIM_TIME = float(os.environ.get("VERAGRID_GFM_RLOAD_SIM_TIME", "0.1"))
LOAD_P_MW = float(os.environ.get("VERAGRID_GFM_RLOAD_P_MW", "4.0"))
LINE_R = float(os.environ.get("VERAGRID_GFM_RLOAD_LINE_R", "0.01"))
LINE_X = float(os.environ.get("VERAGRID_GFM_RLOAD_LINE_X", "0.001"))
V_REF_SCALE = float(os.environ.get("VERAGRID_GFM_RLOAD_V_REF_SCALE", "1.0"))
V_REF_OFFSET = float(os.environ.get("VERAGRID_GFM_RLOAD_V_REF_OFFSET", "0.0"))
EMT_LOAD_POWER_SCALE = float(os.environ.get("VERAGRID_GFM_RLOAD_EMT_LOAD_POWER_SCALE", "3.0"))
EVENT_KIND = os.environ.get("VERAGRID_GFM_RLOAD_EVENT", "p_ref").strip().lower()
P_REF_STEP = os.environ.get("VERAGRID_GFM_RLOAD_P_REF_STEP", "0.01").strip()
P_REF_STEP_TIME = float(os.environ.get("VERAGRID_GFM_RLOAD_P_REF_STEP_TIME", "0.01"))
R_STEP_SCALE = os.environ.get("VERAGRID_GFM_RLOAD_R_STEP_SCALE", "1.1").strip()
R_STEP_TIME = float(os.environ.get("VERAGRID_GFM_RLOAD_R_STEP_TIME", "0.01"))
DISABLE_PREDICTOR_DERIVATIVES = os.environ.get("VERAGRID_GFM_RLOAD_DISABLE_PREDICTOR_DERIVATIVES", "0").strip().lower() in {"1", "true", "yes", "on"}
PRESERVE_PF_ANGLE = os.environ.get("VERAGRID_GFM_RLOAD_PRESERVE_PF_ANGLE", "0").strip().lower() in {"1", "true", "yes", "on"}
PLOT_OUTPUT_DIR = os.environ.get(
    "VERAGRID_GFM_RLOAD_PLOT_DIR",
    os.path.join(os.path.dirname(__file__), "emt_gfm_resistive_load_validation_plots"),
)


def bridge_rload_gain_overrides_to_common_env() -> None:
    mapping = {
        "VERAGRID_GFM_RLOAD_KP_ICL": "VERAGRID_GFM_EMT_KP_ICL",
        "VERAGRID_GFM_RLOAD_KI_ICL": "VERAGRID_GFM_EMT_KI_ICL",
        "VERAGRID_GFM_RLOAD_KDP": "VERAGRID_GFM_EMT_KDP",
        "VERAGRID_GFM_RLOAD_KDQ": "VERAGRID_GFM_EMT_KDQ",
        "VERAGRID_GFM_RLOAD_TAU_P": "VERAGRID_GFM_EMT_TAU_P",
        "VERAGRID_GFM_RLOAD_TAU_Q": "VERAGRID_GFM_EMT_TAU_Q",
        "VERAGRID_GFM_RLOAD_MAX_NEWTON_STEP": "VERAGRID_GFM_EMT_MAX_NEWTON_STEP",
        "VERAGRID_GFM_RLOAD_COMPUTE_DENSE_COND": "VERAGRID_GFM_EMT_COMPUTE_DENSE_COND",
    }
    for source_name, target_name in mapping.items():
        value = os.environ.get(source_name, "").strip()
        if value:
            os.environ[target_name] = value

    os.environ.setdefault("VERAGRID_GFM_EMT_MAX_NEWTON_STEP", "10")
    os.environ.setdefault("VERAGRID_GFM_EMT_COMPUTE_DENSE_COND", "0")


def create_resistive_load_grid() -> tuple[vge.MultiCircuit, dict]:
    grid = vge.MultiCircuit(name="EMT GFM resistive load validation", Sbase=100.0, fbase=50.0)

    bus_gfm = vge.Bus(name="GFM Bus", Vnom=230.0, is_slack=True)
    bus_load = vge.Bus(name="R Load Bus", Vnom=230.0)
    grid.add_bus(bus_gfm)
    grid.add_bus(bus_load)

    gen_gfm = vge.Generator(name="GFM Generator", P=LOAD_P_MW, vset=0.98, Snom=grid.Sbase, freq=50.0)
    load = vge.Load(name="Balanced R Load", P=LOAD_P_MW, Q=0.0)
    line13 = vge.Line(
        name="Line13",
        bus_from=bus_gfm,
        bus_to=bus_load,
        rate=100.0,
        r=LINE_R,
        x=LINE_X,
        b=0.0,
    )

    grid.add_generator(bus=bus_gfm, api_obj=gen_gfm)
    grid.add_load(bus=bus_load, api_obj=load)
    grid.add_line(line13)
    grid.apply_all_branch_types()

    return grid, {
        "bus_gfm": bus_gfm,
        "bus_load": bus_load,
        "gen_gfm": gen_gfm,
        "load": load,
        "line13": line13,
    }


def attach_emt_models(grid: vge.MultiCircuit, devices: dict):
    for bus in grid.buses:
        get_bus_emt_template(grid=grid, bus=bus)

    gfm_block = build_emt_gfm_model(vf=grid.var_factory, name="GFM_rload")
    set_emt_model(devices["gen_gfm"], gfm_block, grid.var_factory)

    line_block = get_pi_line_emt_template(vf=grid.var_factory, name="Line13").block
    set_emt_model(devices["line13"], line_block, grid.var_factory)

    load_block = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True, name="Balanced_R_Shunt_EMT").block
    set_emt_model(devices["load"], load_block, grid.var_factory)
    return gfm_block


def value_from_vector(problem: EmtProblemDae, vector: np.ndarray, block, name: str) -> float:
    var = find_name_in_block(name, block)
    if var is None or var.uid not in problem._uid2idx_vars:
        return 0.0
    return float(vector[problem.get_var_idx(var)])


def preserve_gfm_angle_seed(problem: EmtProblemDae, grid: vge.MultiCircuit, pf_results, gfm_block, bus_gfm) -> None:
    """Keep the oscillator angle exactly aligned with the PF bus voltage at t=0."""
    bus_idx = grid.buses.index(bus_gfm)
    voltage = complex(pf_results.voltage[bus_idx])
    theta0 = float(np.pi - np.angle(voltage))
    theta_var = find_name_in_block("theta", gfm_block)
    if theta_var is not None and theta_var.uid in problem._uid2idx_vars:
        problem.init_guess[theta_var.uid] = theta0
    if theta_var is not None and theta_var.diff_var is not None:
        problem.diff_init_guess[theta_var.diff_var.uid] = -2.0 * np.pi * grid.fBase


def print_case_kcl(problem: EmtProblemDae, devices: dict, gfm_block, vector: np.ndarray, label: str) -> None:
    working_models = getattr(problem, "_working_emt_models", {})

    def model(device):
        return working_models.get(str(device.idtag), device.emt_model)

    print(f"Device-current KCL at {label}:")
    for phase in ("A", "B", "C"):
        line_if = value_from_vector(problem, vector, model(devices["line13"]), f"if_Line13_{phase}")
        line_it = value_from_vector(problem, vector, model(devices["line13"]), f"it_Line13_{phase}")
        gfm_i = value_from_vector(problem, vector, gfm_block, f"i_{phase}")
        load_i = value_from_vector(problem, vector, model(devices["load"]), f"i_{phase}")
        print(
            f"  phase {phase}: gfm_bus={-line_if + gfm_i:.9e}, "
            f"load_bus={-line_it + load_i:.9e}"
        )


def print_raw_x0_report(problem: EmtProblemDae, gfm_block, bus_gfm) -> None:
    x0 = problem.get_x0()

    def get(block, name: str) -> float:
        return value_from_vector(problem, x0, block, name)

    theta = get(gfm_block, "theta")
    v_a = get(bus_gfm.emt_model, "v_A")
    v_b = get(bus_gfm.emt_model, "v_B")
    v_c = get(bus_gfm.emt_model, "v_C")
    c = float(np.cos(theta))
    s = float(np.sin(theta))
    vd_reconstructed = (2.0 * c * v_a + (-c - np.sqrt(3.0) * s) * v_b + (-c + np.sqrt(3.0) * s) * v_c) / 3.0
    vq_reconstructed = (2.0 * s * v_a + (-s + np.sqrt(3.0) * c) * v_b + (-s - np.sqrt(3.0) * c) * v_c) / 3.0

    print("Raw x0 GFM report before run_emt:")
    for name in ("theta", "P", "Q", "vd_g", "vq_g", "id_g", "iq_g", "omega"):
        print(f"  {name}={get(gfm_block, name): .9e}")
    print(f"  bus v_A={v_a: .9e}, v_B={v_b: .9e}, v_C={v_c: .9e}")
    print(f"  reconstructed vd={vd_reconstructed: .9e}, vq={vq_reconstructed: .9e}")


def save_plot(filename: str) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, filename), dpi=150)
    plt.close()


def event_param_value(problem: EmtProblemDae, block, name: str, params: np.ndarray | None = None) -> float:
    var = find_name_in_block(name, block)
    if var is None:
        raise ValueError(f"Could not find runtime parameter {name}")
    uid2idx = getattr(problem, "_uid2idx_event_params", getattr(problem, "uid2idx_event_params", {}))
    idx = uid2idx.get(var.uid, None)
    if idx is None:
        raise ValueError(f"{name} is not an EMT runtime parameter")
    values = problem.event_params_values if params is None else params
    return float(values[idx])


def run_emt_with_r_step(problem: EmtProblemDae, options: EmtOptions, load_block, step_time: float, scale: float):
    step_time = max(0.0, min(float(step_time), float(options.simulation_time)))
    print(f"Running EMT simulation with load R step: t={step_time:.6g} s, scale={scale:.9e}")
    t1, y1, dy1, well1, conv1 = run_emt(problem, options, step_time)
    params = problem.event_params_values.copy()

    for phase in ("A", "B", "C"):
        name = f"R_{phase}"
        before = event_param_value(problem, load_block, name, params=params)
        after = before * float(scale)
        set_runtime_param_in_vector(problem, load_block, name, params, after)
        print(f"{name} step applied: {before:.9e} -> {after:.9e}")

    x0 = np.asarray(y1[-1, :], dtype=float)
    dx0 = np.asarray(dy1[-1, :], dtype=float)
    t2, y2, dy2, well2, conv2 = run_emt(problem, options, options.simulation_time - step_time, x0=x0, dx0=dx0, params0=params)

    if t2.size > 1:
        t = np.concatenate([t1, step_time + t2[1:]])
        y = np.vstack([y1, y2[1:, :]])
        dy = np.vstack([dy1, dy2[1:, :]])
    else:
        t, y, dy = t1, y1, dy1
    return t, y, dy, bool(well1 and well2), bool(conv1 and conv2)


def plot_results(t: np.ndarray, problem: EmtProblemDae, y: np.ndarray, gfm_block, bus_gfm, bus_load) -> None:
    p = trace(problem, y, "P", gfm_block)
    q = trace(problem, y, "Q", gfm_block)
    vd_g = trace(problem, y, "vd_g", gfm_block)
    vq_g = trace(problem, y, "vq_g", gfm_block)
    id_g = trace(problem, y, "id_g", gfm_block)
    iq_g = trace(problem, y, "iq_g", gfm_block)
    omega = trace(problem, y, "omega", gfm_block)
    v_g_a = trace(problem, y, "v_A", bus_gfm.emt_model)
    v_g_b = trace(problem, y, "v_B", bus_gfm.emt_model)
    v_g_c = trace(problem, y, "v_C", bus_gfm.emt_model)
    v_l_a = trace(problem, y, "v_A", bus_load.emt_model)
    v_l_b = trace(problem, y, "v_B", bus_load.emt_model)
    v_l_c = trace(problem, y, "v_C", bus_load.emt_model)

    plt.figure(figsize=(10, 6))
    plt.plot(t, p, label="P")
    plt.plot(t, q, label="Q")
    plt.xlabel("Time (s)")
    plt.ylabel("Power (pu)")
    plt.title("GFM Feeding Balanced R Load")
    plt.grid(True)
    plt.legend(loc="best")
    plt.tight_layout()
    save_plot("gfm_power.png")

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(t, vd_g, label="vd_g")
    axes[0].plot(t, vq_g, label="vq_g")
    axes[0].set_ylabel("Voltage dq")
    axes[0].grid(True)
    axes[0].legend(loc="best")
    axes[1].plot(t, id_g, label="id_g")
    axes[1].plot(t, iq_g, label="iq_g")
    axes[1].set_ylabel("Current dq")
    axes[1].grid(True)
    axes[1].legend(loc="best")
    axes[2].plot(t, omega, label="omega")
    axes[2].set_xlabel("Time (s)")
    axes[2].set_ylabel("Frequency (pu)")
    axes[2].grid(True)
    axes[2].legend(loc="best")
    fig.tight_layout()
    save_plot("gfm_dq_frequency.png")

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(t, v_g_a, label="GFM v_A")
    axes[0].plot(t, v_g_b, label="GFM v_B")
    axes[0].plot(t, v_g_c, label="GFM v_C")
    axes[0].set_ylabel("GFM bus voltage")
    axes[0].grid(True)
    axes[0].legend(loc="best")
    axes[1].plot(t, v_l_a, label="Load v_A")
    axes[1].plot(t, v_l_b, label="Load v_B")
    axes[1].plot(t, v_l_c, label="Load v_C")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Load bus voltage")
    axes[1].grid(True)
    axes[1].legend(loc="best")
    fig.tight_layout()
    save_plot("bus_voltages.png")


def main() -> None:
    bridge_rload_gain_overrides_to_common_env()

    grid, devices = create_resistive_load_grid()
    pf_results = run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    print(pf_results.get_bus_df())
    print(pf_results.get_branch_df())
    if not pf_results.converged:
        raise SystemExit(1)

    # Keep the PF case unchanged while matching the EMT shunt's three-phase
    # current basis to the line-terminal KCL basis.
    devices["load"].P *= EMT_LOAD_POWER_SCALE
    devices["load"].Q *= EMT_LOAD_POWER_SCALE
    print(f"Scaled EMT load powers by {EMT_LOAD_POWER_SCALE:.9e} after PF")

    gfm_block = attach_emt_models(grid, devices)
    bus_idx = grid.buses.index(devices["bus_gfm"])
    load_bus_idx = grid.buses.index(devices["bus_load"])
    voltage = complex(pf_results.voltage[bus_idx])
    load_voltage = complex(pf_results.voltage[load_bus_idx])
    p_ref = float(np.real(pf_results.Sbus[bus_idx]) / grid.Sbase)
    q_ref = float(np.imag(pf_results.Sbus[bus_idx]) / grid.Sbase)
    v_ref = float(np.sqrt(2.0) * abs(voltage)) * V_REF_SCALE + V_REF_OFFSET
    set_block_event_value(gfm_block, grid.var_factory, "P_ref", p_ref)
    set_block_event_value(gfm_block, grid.var_factory, "Q_ref", q_ref)
    set_block_event_value(gfm_block, grid.var_factory, "V_ref", v_ref)
    set_block_event_value(devices["load"].emt_model, grid.var_factory, "Vnom", abs(load_voltage))
    print(f"Set refs: P_ref={p_ref:.9e}, Q_ref={q_ref:.9e}, V_ref={v_ref:.9e}")
    apply_gfm_gain_overrides(gfm_block, grid.var_factory)
    
    options = EmtOptions(
        time_step=TIME_STEP,
        simulation_time=SIM_TIME,
        tolerance=1.0e-6,
        integration_method=integration_method_from_env(),
        solver_type=EmtSolverTypes.StructuralAD,
        initialization_method=EmtInitializationMethod.Explicit,
        init_newton_max_iter=int(os.environ.get("VERAGRID_GFM_RLOAD_NEWTON_MAX_ITER", "200")),
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results)
    seed_gfm_from_power_flow(problem, grid, pf_results, gfm_block, devices["bus_gfm"])
    if PRESERVE_PF_ANGLE:
        preserve_gfm_angle_seed(problem, grid, pf_results, gfm_block, devices["bus_gfm"])
    seed_bus_algebraic_predictors(problem, grid, pf_results)
    seed_line_current_predictors(problem, grid, pf_results, devices)
    if DISABLE_PREDICTOR_DERIVATIVES:
        problem.algebraic_predictor_derivatives = {}
        print("Disabled algebraic predictor derivatives")

    print_gfm_algebraic_residuals(problem, gfm_block)
    print_gfm_state_residuals(problem, gfm_block)
    print_global_state_residuals(problem)
    print_bus_kcl_residuals(problem, grid)
    print_raw_x0_report(problem, gfm_block, devices["bus_gfm"])

    if EVENT_KIND in {"r", "load_r", "resistance"} and R_STEP_SCALE:
        t, y, _dy, well_initialized, converged = run_emt_with_r_step(
            problem=problem,
            options=options,
            load_block=devices["load"].emt_model,
            step_time=R_STEP_TIME,
            scale=float(R_STEP_SCALE),
        )
    elif P_REF_STEP:
        t, y, _dy, well_initialized, converged = run_emt_with_p_ref_step(
            problem=problem,
            options=options,
            gfm_block=gfm_block,
            step_time=P_REF_STEP_TIME,
            step_delta=float(P_REF_STEP),
        )
    else:
        t, y, _dy, well_initialized, converged = run_emt(problem, options, options.simulation_time)
    print(f"EMT well initialized: {well_initialized}")
    print(f"EMT converged: {converged}")
    print(f"Solved samples: {len(t)}")
    print_case_kcl(problem, devices, gfm_block, y[0, :], "solution t0")
    print_case_kcl(problem, devices, gfm_block, y[-1, :], "solution final")

    p = trace(problem, y, "P", gfm_block)
    q = trace(problem, y, "Q", gfm_block)
    vd_g = trace(problem, y, "vd_g", gfm_block)
    vq_g = trace(problem, y, "vq_g", gfm_block)
    id_g = trace(problem, y, "id_g", gfm_block)
    iq_g = trace(problem, y, "iq_g", gfm_block)
    omega = trace(problem, y, "omega", gfm_block)
    print("Final metrics:")
    for name, values in (("P", p), ("Q", q), ("vd_g", vd_g), ("vq_g", vq_g), ("id_g", id_g), ("iq_g", iq_g), ("omega", omega)):
        print(f"  {name}: t0={values[0]: .9e}, final={values[-1]: .9e}, max_abs={np.max(np.abs(values)):.9e}")

    theta = trace(problem, y, "theta", gfm_block)
    v_a0 = trace(problem, y, "v_A", devices["bus_gfm"].emt_model)[0]
    v_b0 = trace(problem, y, "v_B", devices["bus_gfm"].emt_model)[0]
    v_c0 = trace(problem, y, "v_C", devices["bus_gfm"].emt_model)[0]
    c0 = float(np.cos(theta[0]))
    s0 = float(np.sin(theta[0]))
    vd_reconstructed = (2.0 * c0 * v_a0 + (-c0 - np.sqrt(3.0) * s0) * v_b0 + (-c0 + np.sqrt(3.0) * s0) * v_c0) / 3.0
    vq_reconstructed = (2.0 * s0 * v_a0 + (-s0 + np.sqrt(3.0) * c0) * v_b0 + (-s0 - np.sqrt(3.0) * c0) * v_c0) / 3.0
    print("Initial Park check at solution t0:")
    print(f"  theta={theta[0]: .9e}, v_A={v_a0: .9e}, v_B={v_b0: .9e}, v_C={v_c0: .9e}")
    print(f"  vd_reconstructed={vd_reconstructed: .9e}, vq_reconstructed={vq_reconstructed: .9e}")

    plot_results(t, problem, y, gfm_block, devices["bus_gfm"], devices["bus_load"])
    print(f"Plots saved to: {PLOT_OUTPUT_DIR}")
    if not (well_initialized and converged):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
