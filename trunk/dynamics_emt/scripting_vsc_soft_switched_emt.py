# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Run the standard switched EMT VSC handover grid with a soft-sign PWM bridge.
"""

from __future__ import annotations

from pathlib import Path
import sys


def ensure_trunk_import_paths() -> None:
    """
    Add the repository ``src`` tree and the current ``trunk`` directory to ``sys.path``.

    :return: None.
    """
    repo_root: Path = Path(__file__).resolve().parents[2]
    src_root: Path = repo_root / "src"
    trunk_root: Path = repo_root / "trunk"
    repo_root_text: str = str(repo_root)
    src_root_text: str = str(src_root)
    trunk_root_text: str = str(trunk_root)

    if src_root_text not in sys.path:
        sys.path.insert(0, src_root_text)
    else:
        pass

    if trunk_root_text not in sys.path:
        sys.path.insert(0, trunk_root_text)
    else:
        pass

    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)
    else:
        pass


ensure_trunk_import_paths()

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter
from VeraGridEngine.Templates.Emt.converter_soft_switched_emt_template import get_soft_switched_emt_converter
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes
from dynamics_emt.support.switched_converter_handover_case import (
    SwitchedConverterHandoverTrace,
    build_emt_options,
    get_plot_output_path,
    plot_switched_converter_handover,
    print_switched_converter_summary,
    simulate_switched_converter_handover,
)


SCRIPT_FILTER_R_EQ_PU: float = 0.04
SCRIPT_FILTER_L_EQ_PU: float = 1.5
SCRIPT_OMEGA_SW_HZ: float = 1000.0
SOFT_HEAVISIDE_LAMDA: float = 1.0e-6


def build_script_emt_options() -> EmtOptions:
    """
    Build EMT options for the soft-sign switched VSC scripting case.

    :return: EMT options instance.
    """
    options: EmtOptions = build_emt_options(
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        time_step=1.0e-5,
        simulation_time=1.2e-3,
        newton_max_iter=20,
    )
    return options


def run_soft_switched_vsc_case(
        enable_plots: bool = False,
        save_plot: bool = True,
        emt_options: EmtOptions | None = None,
) -> SwitchedConverterHandoverTrace:
    """
    Run the standard switched EMT grid using the soft-sign PWM converter template.

    :param enable_plots: Display matplotlib figures when ``True``.
    :param save_plot: Save the figure to disk when ``True``.
    :param emt_options: Optional EMT options override.
    :return: Structured switched-converter handover trace.
    """
    resolved_emt_options: EmtOptions = build_script_emt_options() if emt_options is None else emt_options
    trace: SwitchedConverterHandoverTrace = simulate_switched_converter_handover(
        emt_options=resolved_emt_options,
        converter_builder=get_soft_switched_emt_converter,
        r_eq_pu=SCRIPT_FILTER_R_EQ_PU,
        l_eq_pu=SCRIPT_FILTER_L_EQ_PU,
    )
    plot_path: Path | None

    print_switched_converter_summary(trace=trace)

    if save_plot:
        plot_path = get_plot_output_path(file_name="soft_switched_converter_handover_scripting.png")
    else:
        plot_path = None

    plot_switched_converter_handover(trace=trace, show_plot=enable_plots, save_path=plot_path)

    if plot_path is not None:
        print(f"Plot saved to: {plot_path}")
    else:
        pass

    if save_plot:
        carrier_path: Path = get_plot_output_path(file_name="soft_vs_procedural_carrier_compare.png")
        procedural_trace: SwitchedConverterHandoverTrace = simulate_switched_converter_handover(
            emt_options=resolved_emt_options,
            converter_builder=get_switched_emt_converter,
            r_eq_pu=SCRIPT_FILTER_R_EQ_PU,
            l_eq_pu=SCRIPT_FILTER_L_EQ_PU,
        )
        plot_soft_and_procedural_carriers(
            soft_trace=trace,
            procedural_trace=procedural_trace,
            omega_sw_hz=SCRIPT_OMEGA_SW_HZ,
            save_path=carrier_path,
        )
        print(f"Carrier plot saved to: {carrier_path}")
    else:
        pass

    return trace


def compute_effective_carrier_trace(
        time_arr: np.ndarray,
        t_enable_s: float,
        omega_sw_hz: float,
) -> np.ndarray:
    """
    Compute the handover-enabled carrier used by the switched bridge comparison.

    :param time_arr: EMT time vector.
    :param t_enable_s: Startup handover time in seconds.
    :param omega_sw_hz: Carrier frequency in hertz.
    :return: Effective carrier trace.
    """
    omega_sw_rad_per_s: float = 2.0 * np.pi * float(omega_sw_hz)
    carrier_enable_arr: np.ndarray = np.where(time_arr >= float(t_enable_s), 1.0, 0.0)
    carrier_arr: np.ndarray = carrier_enable_arr * np.sin(omega_sw_rad_per_s * time_arr)
    return carrier_arr


def plot_soft_and_procedural_carriers(
        soft_trace: SwitchedConverterHandoverTrace,
        procedural_trace: SwitchedConverterHandoverTrace,
        omega_sw_hz: float,
        save_path: Path,
) -> None:
    """
    Plot the procedural and soft effective carrier traces on the same handover time base.

    :param soft_trace: Soft switched-converter trace.
    :param procedural_trace: Procedural switched-converter trace.
    :param omega_sw_hz: Carrier frequency in hertz.
    :param save_path: PNG output path.
    :return: None.
    """
    procedural_carrier_arr: np.ndarray = compute_effective_carrier_trace(
        time_arr=procedural_trace.t_arr,
        t_enable_s=procedural_trace.t_enable_s,
        omega_sw_hz=omega_sw_hz,
    )
    soft_carrier_arr: np.ndarray = compute_effective_carrier_trace(
        time_arr=soft_trace.t_arr,
        t_enable_s=soft_trace.t_enable_s,
        omega_sw_hz=omega_sw_hz,
    )
    figure: plt.Figure
    axes: np.ndarray
    carrier_axis: plt.Axes
    gate_axis: plt.Axes
    heaviside_axis: plt.Axes
    phase_name: str
    failed_time_s: float
    procedural_argument_arr: np.ndarray
    soft_argument_arr: np.ndarray
    procedural_heaviside_arr: np.ndarray
    soft_heaviside_arr: np.ndarray
    procedural_modulation_by_phase: dict[str, np.ndarray]
    soft_modulation_by_phase: dict[str, np.ndarray]

    procedural_modulation_by_phase = dict([
        ("a", procedural_trace.m_a_u_arr),
        ("b", procedural_trace.m_b_u_arr),
        ("c", procedural_trace.m_c_u_arr),
    ])
    soft_modulation_by_phase = dict([
        ("a", soft_trace.m_a_u_arr),
        ("b", soft_trace.m_b_u_arr),
        ("c", soft_trace.m_c_u_arr),
    ])

    figure, axes = plt.subplots(3, 1, figsize=(11.0, 10.5), sharex=True)
    carrier_axis = axes[0]
    gate_axis = axes[1]
    heaviside_axis = axes[2]

    carrier_axis.plot(procedural_trace.t_arr, procedural_carrier_arr, label="procedural effective carrier", linewidth=1.5)
    carrier_axis.plot(soft_trace.t_arr, soft_carrier_arr, label="soft effective carrier", linestyle="--", linewidth=1.3)
    carrier_axis.axvline(soft_trace.t_enable_s, color="black", linestyle=":", label="handover")
    for failed_time_s in soft_trace.failed_substep_times_s_arr:
        carrier_axis.axvline(float(failed_time_s), color="tab:red", linestyle=":", alpha=0.25)
    carrier_axis.set_title("Procedural versus soft switching carrier and gates")
    carrier_axis.set_ylabel("Carrier [-]")
    carrier_axis.grid(True)
    carrier_axis.legend(loc="best")

    gate_axis.step(procedural_trace.t_arr, procedural_trace.gate_a_arr, where="post", label="procedural gate_a", linewidth=1.0)
    gate_axis.step(procedural_trace.t_arr, procedural_trace.gate_b_arr, where="post", label="procedural gate_b", linewidth=1.0)
    gate_axis.step(procedural_trace.t_arr, procedural_trace.gate_c_arr, where="post", label="procedural gate_c", linewidth=1.0)
    gate_axis.plot(soft_trace.t_arr, soft_trace.gate_a_arr, label="soft gate_a", linestyle="--", linewidth=1.3)
    gate_axis.plot(soft_trace.t_arr, soft_trace.gate_b_arr, label="soft gate_b", linestyle="--", linewidth=1.3)
    gate_axis.plot(soft_trace.t_arr, soft_trace.gate_c_arr, label="soft gate_c", linestyle="--", linewidth=1.3)
    gate_axis.axvline(soft_trace.t_enable_s, color="black", linestyle=":")
    for failed_time_s in soft_trace.failed_substep_times_s_arr:
        gate_axis.axvline(float(failed_time_s), color="tab:red", linestyle=":", alpha=0.25)
    gate_axis.set_ylabel("Gate [-]")
    gate_axis.grid(True)
    gate_axis.legend(loc="best", ncol=2)

    for phase_name in list(["a", "b", "c"]):
        procedural_argument_arr = procedural_carrier_arr - procedural_modulation_by_phase[phase_name]
        soft_argument_arr = soft_carrier_arr - soft_modulation_by_phase[phase_name]
        procedural_heaviside_arr = np.where(procedural_argument_arr >= 0.0, 1.0, 0.0)
        soft_heaviside_arr = 0.5 * (
            1.0 + soft_argument_arr / np.sqrt(soft_argument_arr * soft_argument_arr + SOFT_HEAVISIDE_LAMDA)
        )
        heaviside_axis.plot(
            procedural_trace.t_arr,
            procedural_argument_arr,
            label=f"procedural carrier - m_{phase_name}_u",
            linewidth=0.9,
        )
        heaviside_axis.plot(
            soft_trace.t_arr,
            soft_argument_arr,
            label=f"soft carrier - m_{phase_name}_u",
            linestyle="--",
            linewidth=0.9,
        )
        heaviside_axis.step(
            procedural_trace.t_arr,
            procedural_heaviside_arr,
            where="post",
            label=f"H(carrier - m_{phase_name}_u)",
            linewidth=0.9,
        )
        heaviside_axis.plot(
            soft_trace.t_arr,
            soft_heaviside_arr,
            label=f"soft H(carrier - m_{phase_name}_u)",
            linestyle=":",
            linewidth=1.1,
        )

    heaviside_axis.axvline(soft_trace.t_enable_s, color="black", linestyle=":")
    for failed_time_s in soft_trace.failed_substep_times_s_arr:
        heaviside_axis.axvline(float(failed_time_s), color="tab:red", linestyle=":", alpha=0.25)
    heaviside_axis.set_xlabel("Time [s]")
    heaviside_axis.set_ylabel("Argument / H [-]")
    heaviside_axis.grid(True)
    heaviside_axis.legend(loc="best", ncol=3, fontsize="small")
    figure.tight_layout()
    figure.savefig(save_path, dpi=180)
    plt.close(figure)


def main() -> None:
    """
    Run the soft-sign switched EMT VSC scripting case.

    :return: None.
    """
    run_soft_switched_vsc_case(enable_plots=False, save_plot=True)


if __name__ == "__main__":
    main()
