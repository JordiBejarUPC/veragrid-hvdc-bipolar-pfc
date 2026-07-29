# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np


def ensure_repo_import_paths() -> None:
    """
    Add the repository source and trunk paths for direct script execution.

    :return: None.
    """
    repo_root: Path = Path(__file__).resolve().parents[2]
    src_root: Path = repo_root / "src"
    trunk_root: Path = repo_root / "trunk"
    path_text: str

    for path_text in (str(src_root), str(trunk_root), str(repo_root), str(Path(__file__).resolve().parent)):
        if path_text not in sys.path:
            sys.path.insert(0, path_text)
        else:
            pass


ensure_repo_import_paths()

import VeraGridEngine.api as gce
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter

from scripting_vsc_switched_emt_qaxis_compare import (
    COMPARISON_DIVERGENCE_THRESHOLD,
    COMPARISON_L_EQ,
    ConverterCaseArtifacts,
    apply_common_converter_tuning,
    attach_common_bus_models,
    attach_common_device_models,
    build_comparison_emt_options,
    build_daxis_bridge_traces,
    build_daxis_bridge_trace_names,
    build_named_signal_traces,
    build_problem,
    build_power_flow_options,
    build_qaxis_signal_mapping,
    build_reference_grid,
    compute_trace_metrics,
    get_plot_output_path,
    print_trace_metrics,
    run_case,
)


SOFT_SIGN_LAMDA = 1.0e-6


def get_soft_switched_emt_converter(vf: object, name: str) -> None:
    """
    Reject the removed soft-switched production-converter path explicitly.

    :param vf: Shared EMT variable factory.
    :param name: Symbolic model name.
    :return: None.
    """
    raise RuntimeError(
        "soft switched full-converter comparison is disabled because the production converter templates were restored"
    )


def find_problem_var_by_prefix(artifacts_or_problem, prefix: str):
    problem = getattr(artifacts_or_problem, "problem", artifacts_or_problem)
    for var in problem.sys_block.get_all_vars():
        if getattr(var, "name", "").startswith(prefix):
            return var
    return None


def set_init_if_present(problem, prefix: str, value: float) -> None:
    var = find_problem_var_by_prefix(problem, prefix)
    if var is not None:
        problem.init_guess[var.uid] = float(value)


def get_init_by_prefix(problem, prefix: str, default: float = 0.0) -> float:
    var = find_problem_var_by_prefix(problem, prefix)
    if var is None:
        return default
    return float(problem.init_guess.get(var.uid, default))


def seed_soft_bridge_auxiliaries(problem) -> None:
    carrier = get_init_by_prefix(problem, "carrier_pwm_switched_converter_emt_plant_bridge", 0.0)
    for phase in ("a", "b", "c"):
        m_value = get_init_by_prefix(problem, f"m_{phase}_switched_converter_emt_plant_bridge", 0.0)
        x_value = m_value - carrier
        radicand = x_value * x_value + SOFT_SIGN_LAMDA
        denom = float(np.sqrt(radicand))
        softsign = x_value / denom
        gate = 0.5 * (1.0 + softsign)
        set_init_if_present(problem, f"softsign_x_aux_pwm_{phase}_switched_converter_emt_plant_bridge", x_value)
        set_init_if_present(problem, f"softsign_radicand_pwm_{phase}_switched_converter_emt_plant_bridge", radicand)
        set_init_if_present(problem, f"softsign_denom_a_pwm_{phase}_switched_converter_emt_plant_bridge", denom)
        set_init_if_present(problem, f"softsign_denom_b_pwm_{phase}_switched_converter_emt_plant_bridge", denom)
        set_init_if_present(problem, f"softsign_pwm_{phase}_switched_converter_emt_plant_bridge", softsign)
        set_init_if_present(problem, f"gate_pwm_{phase}_switched_converter_emt_plant_bridge", gate)
        set_init_if_present(problem, f"gate_{phase}_switched_converter_emt_plant_bridge", gate)


def run_switched_case(use_soft_bridge: bool) -> ConverterCaseArtifacts:
    grid, _bus_ac, _bus_dc, generator, converter, dc_load = build_reference_grid()
    attach_common_bus_models(grid)
    pf_results = gce.power_flow(grid=grid, options=build_power_flow_options())
    if use_soft_bridge:
        converter_model = get_soft_switched_emt_converter(vf=grid.var_factory, name="switched_converter_emt").block
    else:
        converter_model = get_switched_emt_converter(vf=grid.var_factory, name="switched_converter_emt").block
    apply_common_converter_tuning(converter_model=converter_model, model_name="switched_converter_emt", l_eq_value=COMPARISON_L_EQ)
    attach_common_device_models(
        grid=grid,
        generator=generator,
        converter=converter,
        dc_load=dc_load,
        converter_model=converter_model,
        dc_load_model_name="dc_load_emt_switched",
    )
    problem = build_problem(
        grid=grid,
        pf_results=pf_results,
        options=build_comparison_emt_options(time_step=1.0e-5, simulation_time=5.0e-3),
    )
    if use_soft_bridge:
        seed_soft_bridge_auxiliaries(problem)
    return run_case(problem=problem, model_name="switched_converter_emt")


def plot_soft_vs_procedural(
        time_arr: np.ndarray,
        procedural_signals: dict[str, np.ndarray],
        soft_signals: dict[str, np.ndarray],
        save_path: Path,
) -> None:
    names = [display_name for display_name, _switched_name, _pseudo_name in build_qaxis_signal_mapping()]
    fig, axes = plt.subplots(len(names), 1, figsize=(11, 2.0 * len(names)), sharex=True)
    for axis, name in zip(np.atleast_1d(axes), names):
        axis.plot(time_arr, procedural_signals[name], label="procedural", linewidth=1.1)
        axis.plot(time_arr, soft_signals[name], label="soft", linewidth=1.1, linestyle="--")
        axis.set_ylabel(name)
        axis.grid(True)
        axis.legend(loc="best")
    axes[-1].set_xlabel("Time [s]")
    fig.suptitle("Soft-sign bridge vs procedural switched converter")
    fig.tight_layout()
    fig.savefig(save_path, dpi=180)
    plt.close(fig)


def main() -> None:
    procedural_artifacts = run_switched_case(use_soft_bridge=False)
    try:
        soft_artifacts = run_switched_case(use_soft_bridge=True)
    except RuntimeError as exc:
        print(f"Soft switched comparison skipped: {exc}")
        return

    procedural_signals = build_named_signal_traces(procedural_artifacts)
    soft_signals = build_named_signal_traces(soft_artifacts)
    qaxis_metrics = {
        name: compute_trace_metrics(
            time_arr=procedural_artifacts.time_arr,
            switched_arr=soft_signals[name],
            pseudo_arr=procedural_signals[name],
            analysis_start_s=0.0,
            threshold=COMPARISON_DIVERGENCE_THRESHOLD,
        )
        for name in procedural_signals.keys()
    }
    print_trace_metrics(metrics_by_signal=qaxis_metrics, title="SOFT VS PROCEDURAL Q-AXIS TRACE DIFFERENCE")

    procedural_daxis_signals = build_daxis_bridge_traces(procedural_artifacts)
    soft_daxis_signals = build_daxis_bridge_traces(soft_artifacts)
    daxis_metrics = {
        name: compute_trace_metrics(
            time_arr=procedural_artifacts.time_arr,
            switched_arr=soft_daxis_signals[name],
            pseudo_arr=procedural_daxis_signals[name],
            analysis_start_s=0.0,
            threshold=COMPARISON_DIVERGENCE_THRESHOLD,
        )
        for name in build_daxis_bridge_trace_names()
    }
    print_trace_metrics(metrics_by_signal=daxis_metrics, title="SOFT VS PROCEDURAL D-AXIS / BRIDGE TRACE DIFFERENCE")

    save_path = get_plot_output_path(file_name="soft_vs_procedural_switched_qaxis_trace_compare.png")
    plot_soft_vs_procedural(
        time_arr=procedural_artifacts.time_arr,
        procedural_signals=procedural_signals,
        soft_signals=soft_signals,
        save_path=save_path,
    )
    print(f"Plot saved to: {save_path}")


if __name__ == "__main__":
    main()
