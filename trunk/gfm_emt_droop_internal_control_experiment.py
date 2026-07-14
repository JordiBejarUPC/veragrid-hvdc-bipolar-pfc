#!/usr/bin/env python3
"""Incremental internal-control experiments for the GFM EMT droop example.

The base case is intentionally ``gfm_emt_droop_examples.py``. This script is a
small driver around that file so every controller change can be enabled and
tested one at a time without altering the original droop example.
"""

from __future__ import annotations

import os
from typing import Dict

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import gfm_emt_droop_examples as base


_ORIGINAL_GFM_TEMPLATE = base.get_gfm_emt_template


def _float_env(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


def run_baseline() -> Dict[str, np.ndarray]:
    """Run the unmodified droop-example model."""
    kdp = _float_env("VERAGRID_DROOP_EXPERIMENT_KDP", 0.05)
    kdq = _float_env("VERAGRID_DROOP_EXPERIMENT_KDQ", 0.05)
    use_rl_line = os.environ.get("VERAGRID_DROOP_EXPERIMENT_RL_LINE", "0") == "1"
    return base.run_case(kdp=kdp, kdq=kdq, use_rl_main_line=use_rl_line)


def install_fast_droop_variant() -> None:
    """Make droop states faster, approximating the algebraic droop model.

    ``build_emt_gfm_aggregated_model`` computes ``omega`` and voltage magnitude
    algebraically from filtered P/Q. The droop example uses first-order internal
    VSC states instead. This first incremental variant only reduces those two
    time constants so we can test that change in isolation.
    """
    tau_omega = _float_env("VERAGRID_DROOP_EXPERIMENT_TAU_OMEGA", 0.005)
    tau_v = _float_env("VERAGRID_DROOP_EXPERIMENT_TAU_V", 0.005)

    def get_template_with_fast_droop(vf, name="GFM_VSC"):
        template = _ORIGINAL_GFM_TEMPLATE(vf=vf, name=name)
        for var_name, value in (("tau_omega", tau_omega), ("tau_v", tau_v)):
            var = base._find_name_in_block(var_name, template.block)
            if var is None:
                raise RuntimeError(f"Could not find {var_name} in GFM template")
            template.block.event_dict[var] = vf.add_const(float(value))
        return template

    base.get_gfm_emt_template = get_template_with_fast_droop


def install_filtered_droop_variant() -> None:
    """Add P/Q low-pass states before droop, like the aggregated GFM model."""
    tau_p_value = _float_env("VERAGRID_DROOP_EXPERIMENT_TAU_P", 0.01)
    tau_q_value = _float_env("VERAGRID_DROOP_EXPERIMENT_TAU_Q", 0.01)

    def get_template_with_filtered_droop(vf, name="GFM_VSC"):
        template = _ORIGINAL_GFM_TEMPLATE(vf=vf, name=name)
        block = template.block

        pe = base._find_name_in_block("Pe", block)
        qe = base._find_name_in_block("Qe", block)
        omega = base._find_name_in_block("omega", block)
        epk = base._find_name_in_block("Epk", block)
        kdp = base._find_name_in_block("Kdp", block)
        kdq = base._find_name_in_block("Kdq", block)
        omega_ref = base._find_name_in_block("omega_ref", block)
        p_ref = base._find_name_in_block("P_ref", block)
        q_ref = base._find_name_in_block("Q_ref", block)
        v_ref = base._find_name_in_block("V_ref", block)
        tau_omega = base._find_name_in_block("tau_omega", block)
        tau_v = base._find_name_in_block("tau_v", block)

        required = (pe, qe, omega, epk, kdp, kdq, omega_ref, p_ref, q_ref, v_ref, tau_omega, tau_v)
        if any(var is None for var in required):
            raise RuntimeError("Could not locate all droop variables in GFM template")

        p_lp = vf.add_var(name="y_p_lp")
        q_lp = vf.add_var(name="y_q_lp")
        d_p_lp = vf.add_diff_var(name="d_y_p_lp", base_var=p_lp)
        d_q_lp = vf.add_diff_var(name="d_y_q_lp", base_var=q_lp)
        tau_p = vf.add_var(name="tau_P")
        tau_q = vf.add_var(name="tau_Q")

        block.state_vars.extend([p_lp, q_lp])
        block.diff_vars.extend([d_p_lp, d_q_lp])
        block.state_eqs[4] = ((omega_ref - kdp * (p_lp - p_ref)) - omega) / tau_omega
        block.state_eqs[5] = ((v_ref - kdq * (q_lp - q_ref)) - epk) / tau_v
        block.state_eqs.extend([(pe - p_lp) / tau_p, (qe - q_lp) / tau_q])
        block.event_dict[tau_p] = vf.add_const(float(tau_p_value))
        block.event_dict[tau_q] = vf.add_const(float(tau_q_value))
        block.init_eqs[p_lp] = pe
        block.init_eqs[q_lp] = qe
        block.diff_init_eqs[d_p_lp] = vf.add_const(0.0)
        block.diff_init_eqs[d_q_lp] = vf.add_const(0.0)
        return template

    base.get_gfm_emt_template = get_template_with_filtered_droop


def install_filtered_fast_droop_variant() -> None:
    """Add P/Q filters and speed up omega/Epk droop states."""
    tau_p_value = _float_env("VERAGRID_DROOP_EXPERIMENT_TAU_P", 0.01)
    tau_q_value = _float_env("VERAGRID_DROOP_EXPERIMENT_TAU_Q", 0.01)
    tau_omega_value = _float_env("VERAGRID_DROOP_EXPERIMENT_TAU_OMEGA", 0.005)
    tau_v_value = _float_env("VERAGRID_DROOP_EXPERIMENT_TAU_V", 0.005)

    def get_template_with_filtered_fast_droop(vf, name="GFM_VSC"):
        template = _ORIGINAL_GFM_TEMPLATE(vf=vf, name=name)
        block = template.block

        pe = base._find_name_in_block("Pe", block)
        qe = base._find_name_in_block("Qe", block)
        omega = base._find_name_in_block("omega", block)
        epk = base._find_name_in_block("Epk", block)
        kdp = base._find_name_in_block("Kdp", block)
        kdq = base._find_name_in_block("Kdq", block)
        omega_ref = base._find_name_in_block("omega_ref", block)
        p_ref = base._find_name_in_block("P_ref", block)
        q_ref = base._find_name_in_block("Q_ref", block)
        v_ref = base._find_name_in_block("V_ref", block)
        tau_omega = base._find_name_in_block("tau_omega", block)
        tau_v = base._find_name_in_block("tau_v", block)

        required = (pe, qe, omega, epk, kdp, kdq, omega_ref, p_ref, q_ref, v_ref, tau_omega, tau_v)
        if any(var is None for var in required):
            raise RuntimeError("Could not locate all filtered-fast droop variables in GFM template")

        p_lp = vf.add_var(name="y_p_lp")
        q_lp = vf.add_var(name="y_q_lp")
        d_p_lp = vf.add_diff_var(name="d_y_p_lp", base_var=p_lp)
        d_q_lp = vf.add_diff_var(name="d_y_q_lp", base_var=q_lp)
        tau_p = vf.add_var(name="tau_P")
        tau_q = vf.add_var(name="tau_Q")

        block.state_vars.extend([p_lp, q_lp])
        block.diff_vars.extend([d_p_lp, d_q_lp])
        block.state_eqs[4] = ((omega_ref - kdp * (p_lp - p_ref)) - omega) / tau_omega
        block.state_eqs[5] = ((v_ref - kdq * (q_lp - q_ref)) - epk) / tau_v
        block.state_eqs.extend([(pe - p_lp) / tau_p, (qe - q_lp) / tau_q])
        block.event_dict[tau_p] = vf.add_const(float(tau_p_value))
        block.event_dict[tau_q] = vf.add_const(float(tau_q_value))
        block.event_dict[tau_omega] = vf.add_const(float(tau_omega_value))
        block.event_dict[tau_v] = vf.add_const(float(tau_v_value))
        block.init_eqs[p_lp] = pe
        block.init_eqs[q_lp] = qe
        block.diff_init_eqs[d_p_lp] = vf.add_const(0.0)
        block.diff_init_eqs[d_q_lp] = vf.add_const(0.0)
        return template

    base.get_gfm_emt_template = get_template_with_filtered_fast_droop


def print_summary(label: str, result: Dict[str, np.ndarray]) -> None:
    t = result["t"]
    print(f"\n=== {label} ===")
    print(f"samples={len(t)}, t0={t[0]:.6g}, tf={t[-1]:.6g}")
    for name in ("omega", "Pe", "Qe", "Epk", "i_A"):
        values = result[name]
        print(f"{name}: t0={values[0]: .9e}, final={values[-1]: .9e}")


def plot_result(label: str, result: Dict[str, np.ndarray]) -> None:
    safe_label = label.lower().replace(" ", "_")
    out = os.path.join(base.HERE, f"gfm_internal_control_{safe_label}.png")
    t = result["t"]

    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(t, result["omega"], label="omega")
    axes[0].set_ylabel("omega [pu]")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc="best")

    axes[1].plot(t, result["Pe"], label="Pe")
    axes[1].plot(t, result["Qe"], label="Qe")
    axes[1].set_ylabel("P/Q [pu]")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc="best")

    axes[2].plot(t, result["Epk"], label="Epk")
    axes[2].plot(t, result["i_A"], label="i_A")
    axes[2].set_ylabel("Epk / i_A")
    axes[2].grid(True, alpha=0.3)
    axes[2].legend(loc="best")

    axes[-1].set_xlabel("time [s]")
    for ax in axes:
        ax.axvline(base.EVENT_TIME, color="k", ls=":", lw=0.8, alpha=0.6)
    fig.suptitle(label)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"saved {out}")


def main() -> None:
    # Keep first-step experiments fast by default. These are module-level values
    # in the base script, so override them before calling ``run_case``.
    base.SIM_TIME = _float_env("VERAGRID_DROOP_EXPERIMENT_SIM_TIME", 0.02)
    base.TIME_STEP = _float_env("VERAGRID_DROOP_EXPERIMENT_TIME_STEP", 5.0e-5)
    base.EVENT_TIME = _float_env("VERAGRID_DROOP_EXPERIMENT_EVENT_TIME", 0.01)

    control_variant = os.environ.get("VERAGRID_DROOP_EXPERIMENT_CONTROL", "baseline").strip().lower()
    if control_variant == "baseline":
        label = "baseline droop example"
    elif control_variant == "fast_droop":
        install_fast_droop_variant()
        label = "fast internal droop"
    elif control_variant == "filtered_droop":
        install_filtered_droop_variant()
        label = "filtered internal droop"
    elif control_variant == "filtered_fast_droop":
        install_filtered_fast_droop_variant()
        label = "filtered fast internal droop"
    else:
        raise ValueError(f"Unsupported control variant for this step: {control_variant}")

    result = run_baseline()
    print_summary(label, result)
    plot_result(label, result)


if __name__ == "__main__":
    main()
