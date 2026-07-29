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
    Add repository ``src`` and ``trunk`` directories to ``sys.path`` for direct script execution.

    :return: None.
    """
    repo_root: Path = Path(__file__).resolve().parents[2]
    src_root_text: str = str(repo_root / "src")
    trunk_root_text: str = str(repo_root / "trunk")

    if src_root_text not in sys.path:
        sys.path.insert(0, src_root_text)
    else:
        pass

    if trunk_root_text not in sys.path:
        sys.path.insert(0, trunk_root_text)
    else:
        pass


ensure_repo_import_paths()

from dynamics_emt.scripting_vsc_soft_switched_emt import (
    SCRIPT_FILTER_L_EQ_PU,
    SCRIPT_FILTER_R_EQ_PU,
    SCRIPT_OMEGA_SW_HZ,
    build_script_emt_options,
    compute_effective_carrier_trace,
    get_plot_output_path,
)
from dynamics_emt.support.switched_converter_handover_case import (
    SwitchedConverterHandoverTrace,
    print_switched_converter_summary,
    simulate_switched_converter_handover,
)
from VeraGridEngine.Templates.Emt.converter_soft_switched_emt_template import get_soft_switched_emt_converter
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter


def compute_sampled_modulation_trace(
        time_arr: np.ndarray,
        modulation_arr: np.ndarray,
        t_enable_s: float,
        omega_sw_hz: float,
) -> np.ndarray:
    """
    Build a sampled-and-held modulation trace using procedural PWM half-period sampling.

    :param time_arr: Accepted EMT time vector.
    :param modulation_arr: Continuous modulation trace to sample.
    :param t_enable_s: Time at which switching is enabled.
    :param omega_sw_hz: PWM carrier frequency in hertz.
    :return: Sampled-and-held modulation trace on ``time_arr``.
    """
    sampled_arr: np.ndarray = np.zeros_like(modulation_arr, dtype=float)
    omega_sw_rad_per_s: float = 2.0 * np.pi * float(omega_sw_hz)
    half_period_s: float = np.pi / omega_sw_rad_per_s
    current_sample_value: float = 0.0
    next_sample_time_s: float = float(t_enable_s)
    time_index: int = 0
    sample_index: int

    # The procedural PWM rebuilds its schedule from the accepted state at the first enabled instant and
    # then at every carrier half-period boundary, holding that sampled modulation during the interval.
    while time_index < int(time_arr.size):
        current_time_s: float = float(time_arr[time_index])
        if current_time_s + 1.0e-12 < float(t_enable_s):
            sampled_arr[time_index] = 0.0
        else:
            while current_time_s + 1.0e-12 >= next_sample_time_s:
                sample_index = int(np.searchsorted(time_arr, next_sample_time_s, side="left"))
                if sample_index >= int(time_arr.size):
                    sample_index = int(time_arr.size) - 1
                else:
                    pass
                current_sample_value = float(modulation_arr[sample_index])
                next_sample_time_s += half_period_s
            sampled_arr[time_index] = current_sample_value
        time_index += 1

    return sampled_arr


def plot_sampled_modulation_comparison(
        soft_trace: SwitchedConverterHandoverTrace,
        procedural_trace: SwitchedConverterHandoverTrace,
        omega_sw_hz: float,
        save_path: Path,
) -> None:
    """
    Plot continuous and sampled modulation comparator arguments against the procedural run.

    :param soft_trace: Soft/direct-Heaviside switched converter trace.
    :param procedural_trace: Procedural switched converter trace.
    :param omega_sw_hz: PWM carrier frequency in hertz.
    :param save_path: Output PNG path.
    :return: None.
    """
    soft_carrier_arr: np.ndarray = compute_effective_carrier_trace(
        time_arr=soft_trace.t_arr,
        t_enable_s=soft_trace.t_enable_s,
        omega_sw_hz=omega_sw_hz,
    )
    procedural_carrier_arr: np.ndarray = compute_effective_carrier_trace(
        time_arr=procedural_trace.t_arr,
        t_enable_s=procedural_trace.t_enable_s,
        omega_sw_hz=omega_sw_hz,
    )
    soft_modulation_by_phase: dict[str, np.ndarray] = dict([
        ("a", soft_trace.m_a_u_arr),
        ("b", soft_trace.m_b_u_arr),
        ("c", soft_trace.m_c_u_arr),
    ])
    procedural_modulation_by_phase: dict[str, np.ndarray] = dict([
        ("a", procedural_trace.m_a_u_arr),
        ("b", procedural_trace.m_b_u_arr),
        ("c", procedural_trace.m_c_u_arr),
    ])
    figure: plt.Figure
    axes: np.ndarray
    carrier_axis: plt.Axes
    argument_axis: plt.Axes
    gate_axis: plt.Axes
    phase_name: str

    figure, axes = plt.subplots(3, 1, figsize=(12.0, 10.5), sharex=True)
    carrier_axis = axes[0]
    argument_axis = axes[1]
    gate_axis = axes[2]

    carrier_axis.plot(procedural_trace.t_arr, procedural_carrier_arr, label="procedural carrier", linewidth=1.2)
    carrier_axis.plot(soft_trace.t_arr, soft_carrier_arr, label="soft carrier", linestyle="--", linewidth=1.2)
    carrier_axis.axvline(soft_trace.t_enable_s, color="black", linestyle=":", label="handover")
    carrier_axis.set_title("Soft/procedural carrier comparison with sampled modulation")
    carrier_axis.set_ylabel("Carrier [-]")
    carrier_axis.grid(True)
    carrier_axis.legend(loc="best")

    for phase_name in list(["a", "b", "c"]):
        sampled_soft_modulation_arr: np.ndarray = compute_sampled_modulation_trace(
            time_arr=soft_trace.t_arr,
            modulation_arr=soft_modulation_by_phase[phase_name],
            t_enable_s=soft_trace.t_enable_s,
            omega_sw_hz=omega_sw_hz,
        )
        sampled_procedural_modulation_arr: np.ndarray = compute_sampled_modulation_trace(
            time_arr=procedural_trace.t_arr,
            modulation_arr=procedural_modulation_by_phase[phase_name],
            t_enable_s=procedural_trace.t_enable_s,
            omega_sw_hz=omega_sw_hz,
        )
        argument_axis.plot(
            soft_trace.t_arr,
            soft_carrier_arr - soft_modulation_by_phase[phase_name],
            linestyle=":",
            linewidth=0.8,
            label=f"soft raw carrier - m_{phase_name}",
        )
        argument_axis.step(
            soft_trace.t_arr,
            soft_carrier_arr - sampled_soft_modulation_arr,
            where="post",
            linewidth=1.1,
            label=f"soft sampled carrier - m_{phase_name}",
        )
        argument_axis.step(
            procedural_trace.t_arr,
            procedural_carrier_arr - sampled_procedural_modulation_arr,
            where="post",
            linestyle="--",
            linewidth=0.9,
            label=f"procedural sampled carrier - m_{phase_name}",
        )

    argument_axis.axvline(soft_trace.t_enable_s, color="black", linestyle=":")
    argument_axis.set_ylabel("carrier - sampled m [-]")
    argument_axis.grid(True)
    argument_axis.legend(loc="best", ncol=3, fontsize="small")

    gate_axis.step(procedural_trace.t_arr, procedural_trace.gate_a_arr, where="post", label="procedural gate_a", linewidth=1.0)
    gate_axis.step(procedural_trace.t_arr, procedural_trace.gate_b_arr, where="post", label="procedural gate_b", linewidth=1.0)
    gate_axis.step(procedural_trace.t_arr, procedural_trace.gate_c_arr, where="post", label="procedural gate_c", linewidth=1.0)
    gate_axis.plot(soft_trace.t_arr, soft_trace.gate_a_arr, label="soft gate_a", linestyle="--", linewidth=1.0)
    gate_axis.plot(soft_trace.t_arr, soft_trace.gate_b_arr, label="soft gate_b", linestyle="--", linewidth=1.0)
    gate_axis.plot(soft_trace.t_arr, soft_trace.gate_c_arr, label="soft gate_c", linestyle="--", linewidth=1.0)
    gate_axis.axvline(soft_trace.t_enable_s, color="black", linestyle=":")
    gate_axis.set_xlabel("Time [s]")
    gate_axis.set_ylabel("Gate [-]")
    gate_axis.grid(True)
    gate_axis.legend(loc="best", ncol=3)

    figure.tight_layout()
    figure.savefig(save_path, dpi=180)
    plt.close(figure)


def main() -> None:
    """
    Run the 2 ms soft/procedural comparison with sampled modulation diagnostics.

    :return: None.
    """
    options = build_script_emt_options()
    options.simulation_time = 2.0e-3

    soft_trace: SwitchedConverterHandoverTrace = simulate_switched_converter_handover(
        emt_options=options,
        converter_builder=get_soft_switched_emt_converter,
        r_eq_pu=SCRIPT_FILTER_R_EQ_PU,
        l_eq_pu=SCRIPT_FILTER_L_EQ_PU,
    )
    print("SOFT")
    print_switched_converter_summary(trace=soft_trace)

    procedural_trace: SwitchedConverterHandoverTrace = simulate_switched_converter_handover(
        emt_options=options,
        converter_builder=get_switched_emt_converter,
        r_eq_pu=SCRIPT_FILTER_R_EQ_PU,
        l_eq_pu=SCRIPT_FILTER_L_EQ_PU,
    )
    print("PROCEDURAL")
    print_switched_converter_summary(trace=procedural_trace)

    sampled_plot_path: Path = get_plot_output_path(file_name="soft_vs_procedural_sampled_m_compare_0p002s.png")
    plot_sampled_modulation_comparison(
        soft_trace=soft_trace,
        procedural_trace=procedural_trace,
        omega_sw_hz=SCRIPT_OMEGA_SW_HZ,
        save_path=sampled_plot_path,
    )
    print(f"Sampled modulation plot saved to: {sampled_plot_path}")


if __name__ == "__main__":
    main()
