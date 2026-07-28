#!/usr/bin/env python3
"""Validate the simplified EMT GFM case with a Thevenin slack source."""

from __future__ import annotations

import os
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonDiagnosticsConfig
from VeraGridEngine.enumerations import EmtInitializationMethod, EmtSolverTypes

from emt_gfm_model_validation import (
    apply_gfm_gain_overrides,
    attach_emt_models,
    create_simplified_grid,
    integration_method_from_env,
    print_bus_kcl_residuals,
    print_case_kcl_from_vector,
    print_case_kcl_residuals,
    print_gfm_bus_kcl_derivative,
    run_emt,
    run_power_flow,
    seed_bus_algebraic_predictors,
    seed_gfm_from_power_flow,
    seed_line_current_predictors,
    set_block_event_value,
    trace,
)


TIME_STEP = float(os.environ.get("VERAGRID_GFM_THEVENIN_TIME_STEP", "1e-5"))
SIM_TIME = float(os.environ.get("VERAGRID_GFM_THEVENIN_SIM_TIME", "1e-4"))
VD_G_MAX = float(os.environ.get("VERAGRID_GFM_THEVENIN_MAX_ABS_VD_G", "1e-3"))
P_DRIFT_MAX = float(os.environ.get("VERAGRID_GFM_THEVENIN_MAX_ABS_P_DRIFT", "1e-3"))
Q_DRIFT_MAX = float(os.environ.get("VERAGRID_GFM_THEVENIN_MAX_ABS_Q_DRIFT", "1e-3"))
KDQ_OVERRIDE = os.environ.get("VERAGRID_GFM_THEVENIN_KDQ", "").strip()
V_REF_SCALE = float(os.environ.get("VERAGRID_GFM_THEVENIN_V_REF_SCALE", "1.0"))
V_REF_OFFSET = float(os.environ.get("VERAGRID_GFM_THEVENIN_V_REF_OFFSET", "0.0"))
PLOT_OUTPUT_DIR = os.environ.get(
    "VERAGRID_GFM_THEVENIN_PLOT_DIR",
    os.path.join(os.path.dirname(__file__), "emt_gfm_thevenin_slack_validation_plots"),
)


def save_plot(filename: str) -> None:
    os.makedirs(PLOT_OUTPUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(PLOT_OUTPUT_DIR, filename), dpi=150)
    plt.close()


def plot_validation_results(t: np.ndarray, problem: EmtProblemDae, y: np.ndarray, gfm_block, bus_gfm) -> None:
    t = np.asarray(t, dtype=float)

    p = trace(problem, y, "P", gfm_block)
    q = trace(problem, y, "Q", gfm_block)
    omega = trace(problem, y, "omega", gfm_block)
    vd_g = trace(problem, y, "vd_g", gfm_block)
    vq_g = trace(problem, y, "vq_g", gfm_block)
    id_g = trace(problem, y, "id_g", gfm_block)
    iq_g = trace(problem, y, "iq_g", gfm_block)
    id_c = trace(problem, y, "id_c", gfm_block)
    iq_c = trace(problem, y, "iq_c", gfm_block)
    v_a = trace(problem, y, "v_A", bus_gfm.emt_model)
    v_b = trace(problem, y, "v_B", bus_gfm.emt_model)
    v_c = trace(problem, y, "v_C", bus_gfm.emt_model)

    plt.figure(figsize=(10, 6))
    plt.plot(t, p, label="P")
    plt.plot(t, q, label="Q")
    plt.xlabel("Time (s)")
    plt.ylabel("Power (pu)")
    plt.title("Thevenin Slack GFM Power")
    plt.grid(True)
    plt.legend(loc="best")
    plt.tight_layout()
    save_plot("gfm_power.png")

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(t, vd_g, label="vd_g")
    axes[0].plot(t, vq_g, label="vq_g")
    axes[0].set_ylabel("Grid voltage dq")
    axes[0].grid(True)
    axes[0].legend(loc="best")

    axes[1].plot(t, id_g, label="id_g")
    axes[1].plot(t, iq_g, label="iq_g")
    axes[1].set_ylabel("Grid current dq")
    axes[1].grid(True)
    axes[1].legend(loc="best")

    axes[2].plot(t, id_c, label="id_c")
    axes[2].plot(t, iq_c, label="iq_c")
    axes[2].set_xlabel("Time (s)")
    axes[2].set_ylabel("Converter current dq")
    axes[2].grid(True)
    axes[2].legend(loc="best")
    fig.suptitle("Thevenin Slack GFM dq States")
    fig.tight_layout()
    save_plot("gfm_dq_states.png")

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(t, v_a, label="v_A")
    axes[0].plot(t, v_b, label="v_B")
    axes[0].plot(t, v_c, label="v_C")
    axes[0].set_ylabel("PCC voltage abc")
    axes[0].grid(True)
    axes[0].legend(loc="best")

    axes[1].plot(t, omega, label="omega")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Frequency (pu)")
    axes[1].grid(True)
    axes[1].legend(loc="best")
    fig.suptitle("Thevenin Slack GFM PCC Voltage and Frequency")
    fig.tight_layout()
    save_plot("gfm_voltage_frequency.png")


def bridge_thevenin_gain_overrides_to_common_env() -> None:
    """Allow focused-script env names while reusing the shared GFM seeding logic."""
    mapping = {
        "VERAGRID_GFM_THEVENIN_KP_ICL": "VERAGRID_GFM_EMT_KP_ICL",
        "VERAGRID_GFM_THEVENIN_KI_ICL": "VERAGRID_GFM_EMT_KI_ICL",
        "VERAGRID_GFM_THEVENIN_KDP": "VERAGRID_GFM_EMT_KDP",
        "VERAGRID_GFM_THEVENIN_KDQ": "VERAGRID_GFM_EMT_KDQ",
        "VERAGRID_GFM_THEVENIN_TAU_P": "VERAGRID_GFM_EMT_TAU_P",
        "VERAGRID_GFM_THEVENIN_TAU_Q": "VERAGRID_GFM_EMT_TAU_Q",
    }
    for source_name, target_name in mapping.items():
        value = os.environ.get(source_name, "").strip()
        if value:
            os.environ[target_name] = value


def main() -> None:
    os.environ["VERAGRID_GFM_EMT_SLACK_SOURCE"] = "thevenin"
    bridge_thevenin_gain_overrides_to_common_env()

    grid, devices = create_simplified_grid()
    pf_results = run_power_flow(grid)
    print(f"Power flow converged: {pf_results.converged}")
    print(pf_results.get_bus_df())
    print(pf_results.get_branch_df())
    if not pf_results.converged:
        raise SystemExit(1)

    gfm_block = attach_emt_models(grid, devices, pf_results=pf_results)
    bus_idx = grid.buses.index(devices["bus_gfm"])
    voltage = complex(pf_results.voltage[bus_idx])
    v_ref = float(np.sqrt(2.0) * abs(voltage)) * V_REF_SCALE + V_REF_OFFSET
    set_block_event_value(gfm_block, grid.var_factory, "P_ref", float(np.real(pf_results.Sbus[bus_idx]) / grid.Sbase))
    set_block_event_value(gfm_block, grid.var_factory, "Q_ref", float(np.imag(pf_results.Sbus[bus_idx]) / grid.Sbase))
    set_block_event_value(gfm_block, grid.var_factory, "V_ref", v_ref)
    print(f"Set V_ref: {v_ref:.9e} (scale={V_REF_SCALE:.9e}, offset={V_REF_OFFSET:.9e})")
    apply_gfm_gain_overrides(gfm_block, grid.var_factory)

    options = EmtOptions(
        time_step=TIME_STEP,
        simulation_time=SIM_TIME,
        tolerance=1.0e-6,
        integration_method=integration_method_from_env(),
        solver_type=EmtSolverTypes.StructuralAD,
        initialization_method=EmtInitializationMethod.Explicit,
        init_newton_max_iter=int(os.environ.get("VERAGRID_GFM_THEVENIN_NEWTON_MAX_ITER", "200")),
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results=pf_results)

    seed_gfm_from_power_flow(problem, grid, pf_results, gfm_block, devices["bus_gfm"])
    seed_bus_algebraic_predictors(problem, grid, pf_results)
    seed_line_current_predictors(problem, grid, pf_results, devices)

    print("Seeded native-initialization KCL checks:")
    print_bus_kcl_residuals(problem, grid)
    print_case_kcl_residuals(problem, devices, gfm_block)
    print_gfm_bus_kcl_derivative(problem, devices, gfm_block)

    t, y, _dy, well_initialized, converged = run_emt(problem, options, options.simulation_time)
    print(f"EMT well initialized: {well_initialized}")
    print(f"EMT converged: {converged}")
    print(f"Solved samples: {len(t)}")
    if len(t) > 0:
        print_case_kcl_from_vector(problem, devices, gfm_block, y[0, :], "solution t0")
        print_case_kcl_from_vector(problem, devices, gfm_block, y[-1, :], "solution final")

    p = trace(problem, y, "P", gfm_block)
    q = trace(problem, y, "Q", gfm_block)
    vd_g = trace(problem, y, "vd_g", gfm_block)
    vq_g = trace(problem, y, "vq_g", gfm_block)
    id_g = trace(problem, y, "id_g", gfm_block)
    iq_g = trace(problem, y, "iq_g", gfm_block)

    p_drift = float(np.max(np.abs(p - p[0])))
    q_drift = float(np.max(np.abs(q - q[0])))
    vd_g_max = float(np.max(np.abs(vd_g)))
    print("Validation metrics:")
    print(f"  max_abs(P-P0)={p_drift:.9e} limit={P_DRIFT_MAX:.9e}")
    print(f"  max_abs(Q-Q0)={q_drift:.9e} limit={Q_DRIFT_MAX:.9e}")
    print(f"  max_abs(vd_g)={vd_g_max:.9e} limit={VD_G_MAX:.9e}")
    print(f"  P: t0={p[0]: .9e}, final={p[-1]: .9e}")
    print(f"  Q: t0={q[0]: .9e}, final={q[-1]: .9e}")
    print(f"  vd_g: t0={vd_g[0]: .9e}, final={vd_g[-1]: .9e}")
    print(f"  vq_g: t0={vq_g[0]: .9e}, final={vq_g[-1]: .9e}")
    print(f"  id_g: t0={id_g[0]: .9e}, final={id_g[-1]: .9e}")
    print(f"  iq_g: t0={iq_g[0]: .9e}, final={iq_g[-1]: .9e}")

    plot_validation_results(t, problem, y, gfm_block, devices["bus_gfm"])
    print(f"Plots saved to: {PLOT_OUTPUT_DIR}")

    passed = bool(
        well_initialized
        and converged
        and p_drift <= P_DRIFT_MAX
        and q_drift <= Q_DRIFT_MAX
        and vd_g_max <= VD_G_MAX
    )
    print(f"Validation passed: {passed}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
