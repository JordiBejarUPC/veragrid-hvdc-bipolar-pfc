# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Compare procedural gates with soft gates built from sampled-and-held modulation values.
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

from VeraGridEngine.Templates.Emt.converter_soft_switched_emt_template import get_soft_switched_emt_converter
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter
from dynamics_emt.scripting_vsc_soft_switched_emt import (
    SCRIPT_FILTER_L_EQ_PU,
    SCRIPT_FILTER_R_EQ_PU,
    SCRIPT_OMEGA_SW_HZ,
    build_script_emt_options,
    compute_effective_carrier_trace,
)
from dynamics_emt.support.switched_converter_handover_case import (
    SwitchedConverterHandoverTrace,
    get_plot_output_path,
    simulate_switched_converter_handover,
)


SOFT_GATE_LAMDA: float = 1.0e-6


def compute_carrier_sample_times(
        t_enable_s: float,
        t_end_s: float,
        omega_sw_hz: float,
) -> np.ndarray:
    """
    Return the PWM sample times used by the sampled-soft offline comparison.

    :param t_enable_s: Startup handover time in seconds.
    :param t_end_s: Final simulation time in seconds.
    :param omega_sw_hz: Carrier frequency in hertz.
    :return: Monotonic sample-time vector.
    """
    omega_sw_rad_per_s: float = 2.0 * np.pi * float(omega_sw_hz)
    first_index: int = int(np.floor((omega_sw_rad_per_s * float(t_enable_s) + 0.5 * np.pi) / np.pi))
    sample_times: list[float] = list([float(t_enable_s)])
    interval_index: int = first_index + 1
    sample_time_s: float = 0.0

    while sample_time_s <= float(t_end_s):
        sample_time_s = (float(interval_index) * np.pi - 0.5 * np.pi) / omega_sw_rad_per_s
        if sample_time_s > float(t_enable_s) and sample_time_s <= float(t_end_s):
            sample_times.append(float(sample_time_s))
        else:
            pass
        interval_index += 1

    return np.array(sample_times, dtype=float)


def compute_held_modulation_trace(
        time_arr: np.ndarray,
        modulation_arr: np.ndarray,
        sample_time_arr: np.ndarray,
) -> np.ndarray:
    """
    Hold one modulation trace from the latest carrier sample time.

    :param time_arr: EMT time vector.
    :param modulation_arr: Continuous modulation trace.
    :param sample_time_arr: Carrier sample times.
    :return: Held modulation trace on ``time_arr``.
    """
    sample_value_arr: np.ndarray = np.interp(sample_time_arr, time_arr, modulation_arr)
    held_arr: np.ndarray = np.zeros_like(time_arr, dtype=float)
    time_index: int
    sample_index: int

    for time_index in range(len(time_arr)):
        sample_index = int(np.searchsorted(sample_time_arr, time_arr[time_index], side="right") - 1)
        if sample_index >= 0:
            held_arr[time_index] = sample_value_arr[sample_index]
        else:
            held_arr[time_index] = 0.0

    return held_arr


def compute_sampled_soft_gate(
        time_arr: np.ndarray,
        t_enable_s: float,
        held_modulation_arr: np.ndarray,
        carrier_arr: np.ndarray,
) -> np.ndarray:
    """
    Compute one soft gate using sampled-and-held modulation and the active carrier.

    :param time_arr: EMT time vector.
    :param t_enable_s: Startup handover time in seconds.
    :param held_modulation_arr: Held modulation trace.
    :param carrier_arr: Effective carrier trace.
    :return: Sampled-soft gate trace.
    """
    carrier_enable_arr: np.ndarray = np.where(time_arr >= float(t_enable_s), 1.0, 0.0)
    comparator_arr: np.ndarray = held_modulation_arr - carrier_arr
    softsign_arr: np.ndarray = comparator_arr / np.sqrt(comparator_arr * comparator_arr + SOFT_GATE_LAMDA)
    gate_arr: np.ndarray = carrier_enable_arr * 0.5 * (1.0 + softsign_arr)
    return gate_arr


def plot_sampled_soft_gate_comparison(
        procedural_trace: SwitchedConverterHandoverTrace,
        soft_trace: SwitchedConverterHandoverTrace,
        save_path: Path,
) -> None:
    """
    Plot procedural gates, current soft gates and sampled-soft gates.

    :param procedural_trace: Procedural switched-converter trace.
    :param soft_trace: Soft switched-converter trace.
    :param save_path: PNG output path.
    :return: None.
    """
    carrier_arr: np.ndarray = compute_effective_carrier_trace(
        time_arr=soft_trace.t_arr,
        t_enable_s=soft_trace.t_enable_s,
        omega_sw_hz=SCRIPT_OMEGA_SW_HZ,
    )
    sample_time_arr: np.ndarray = compute_carrier_sample_times(
        t_enable_s=soft_trace.t_enable_s,
        t_end_s=float(soft_trace.t_arr[-1]),
        omega_sw_hz=SCRIPT_OMEGA_SW_HZ,
    )
    held_m_a_arr: np.ndarray = compute_held_modulation_trace(soft_trace.t_arr, soft_trace.m_a_u_arr, sample_time_arr)
    held_m_b_arr: np.ndarray = compute_held_modulation_trace(soft_trace.t_arr, soft_trace.m_b_u_arr, sample_time_arr)
    held_m_c_arr: np.ndarray = compute_held_modulation_trace(soft_trace.t_arr, soft_trace.m_c_u_arr, sample_time_arr)
    sampled_gate_a_arr: np.ndarray = compute_sampled_soft_gate(soft_trace.t_arr, soft_trace.t_enable_s, held_m_a_arr, carrier_arr)
    sampled_gate_b_arr: np.ndarray = compute_sampled_soft_gate(soft_trace.t_arr, soft_trace.t_enable_s, held_m_b_arr, carrier_arr)
    sampled_gate_c_arr: np.ndarray = compute_sampled_soft_gate(soft_trace.t_arr, soft_trace.t_enable_s, held_m_c_arr, carrier_arr)
    figure: plt.Figure
    axes: np.ndarray
    axis: plt.Axes
    axis_index: int
    phase_names: tuple[str, str, str] = ("a", "b", "c")
    procedural_gate_list: list[np.ndarray] = list([procedural_trace.gate_a_arr, procedural_trace.gate_b_arr, procedural_trace.gate_c_arr])
    soft_gate_list: list[np.ndarray] = list([soft_trace.gate_a_arr, soft_trace.gate_b_arr, soft_trace.gate_c_arr])
    sampled_gate_list: list[np.ndarray] = list([sampled_gate_a_arr, sampled_gate_b_arr, sampled_gate_c_arr])

    figure, axes = plt.subplots(4, 1, figsize=(11.5, 10.0), sharex=True)
    axes[0].plot(soft_trace.t_arr, carrier_arr, label="effective carrier")
    axes[0].scatter(sample_time_arr, np.interp(sample_time_arr, soft_trace.t_arr, carrier_arr), label="m sample times", s=14, color="black")
    axes[0].axvline(soft_trace.t_enable_s, color="black", linestyle=":", label="handover")
    axes[0].set_ylabel("carrier")
    axes[0].grid(True)
    axes[0].legend(loc="best")

    for axis_index in range(3):
        axis = axes[axis_index + 1]
        axis.step(procedural_trace.t_arr, procedural_gate_list[axis_index], where="post", label=f"procedural gate_{phase_names[axis_index]}")
        axis.plot(soft_trace.t_arr, soft_gate_list[axis_index], linestyle="--", label=f"current soft gate_{phase_names[axis_index]}")
        axis.plot(soft_trace.t_arr, sampled_gate_list[axis_index], linestyle=":", label=f"sampled soft gate_{phase_names[axis_index]}")
        axis.axvline(soft_trace.t_enable_s, color="black", linestyle=":")
        axis.set_ylabel(f"gate_{phase_names[axis_index]}")
        axis.grid(True)
        axis.legend(loc="best")

    axes[-1].set_xlabel("Time [s]")
    figure.suptitle("Procedural gates versus sampled-soft gates")
    figure.tight_layout()
    figure.savefig(save_path, dpi=180)
    plt.close(figure)


def main() -> None:
    """
    Run the sampled-soft gate comparison experiment.

    :return: None.
    """
    options = build_script_emt_options()
    options.time_step = 1.0e-6
    options.simulation_time = 6.0e-4
    procedural_trace: SwitchedConverterHandoverTrace = simulate_switched_converter_handover(
        emt_options=options,
        converter_builder=get_switched_emt_converter,
        r_eq_pu=SCRIPT_FILTER_R_EQ_PU,
        l_eq_pu=SCRIPT_FILTER_L_EQ_PU,
    )
    soft_trace: SwitchedConverterHandoverTrace = simulate_switched_converter_handover(
        emt_options=options,
        converter_builder=get_soft_switched_emt_converter,
        r_eq_pu=SCRIPT_FILTER_R_EQ_PU,
        l_eq_pu=SCRIPT_FILTER_L_EQ_PU,
    )
    save_path: Path = get_plot_output_path(file_name="sampled_soft_gate_compare.png")
    plot_sampled_soft_gate_comparison(
        procedural_trace=procedural_trace,
        soft_trace=soft_trace,
        save_path=save_path,
    )
    print(f"Sampled soft gate plot saved to: {save_path}")
    print(f"Procedural converged: {procedural_trace.converged}")
    print(f"Soft converged      : {soft_trace.converged}")


if __name__ == "__main__":
    main()
