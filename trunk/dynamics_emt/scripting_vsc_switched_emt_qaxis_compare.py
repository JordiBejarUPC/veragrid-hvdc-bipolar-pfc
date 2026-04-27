# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Compare switched and pseudo EMT converter internals on the same simple reference case.

The script started as a q-axis comparison, but it also includes a d-axis and
bridge-voltage decomposition because the remaining switched-converter mismatch is
best localized by following both the dq control commands and the realized bridge
voltage in the same run.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


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

import numpy as np
import matplotlib.pyplot as plt

import VeraGridEngine.api as gce
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_solver_factory import build_emt_solver
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.converter_emt_template import get_full_pseudo_emt_converter
from VeraGridEngine.Templates.Emt.converter_switched_emt_template import get_switched_emt_converter
from VeraGridEngine.Templates.Emt.dc_load_emt_template import get_dc_load_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template
from VeraGridEngine.Templates.templates_common_functions import set_emt_model
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.enumerations import ConverterControlType, DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes
from dynamics_emt.support.switched_converter_handover_case import build_power_flow_options, get_plot_output_path


class ConverterCaseArtifacts:
    """
    Runtime bundle returned by one converter comparison run.

    :param problem: EMT problem instance.
    :param model_name: Converter model symbolic name.
    :param time_arr: EMT time vector.
    :param state_traj: EMT trajectory matrix.
    :return: None.
    """

    __slots__ = list(["problem", "model_name", "time_arr", "state_traj"])

    def __init__(
            self,
            problem: EmtProblemDae,
            model_name: str,
            time_arr: np.ndarray,
            state_traj: np.ndarray,
    ) -> None:
        self.problem: EmtProblemDae = problem
        self.model_name: str = model_name
        self.time_arr: np.ndarray = time_arr
        self.state_traj: np.ndarray = state_traj


COMPARISON_FBASE_HZ: float = 50.0
COMPARISON_OMEGA_BASE_RAD_PER_S: float = 2.0 * np.pi * COMPARISON_FBASE_HZ
COMPARISON_R_EQ: float = 0.03
COMPARISON_L_EQ: float = 1.0
COMPARISON_ANALYSIS_START_S: float = 2.0e-4
COMPARISON_DIVERGENCE_THRESHOLD: float = 1.0e-3
TAIL_WINDOW_S: float = 2.0e-3
TAIL_INTERVAL_COUNT: int = 4
QAXIS_SIGN_FLIPPED_TRACE_NAMES: set[str] = {
    "Q",
    "Q_f",
    "i_q_ref",
    "v_q",
    "v_q_pll_f",
    "v_cmd_q_u",
    "v_cmd_q",
}
QAXIS_SIGN_FLIPPED_DIAGNOSTIC_KEYS: set[str] = {
    "mean::Q_f_switched_converter_emt",
    "mean::i_q_ref_switched_converter_emt",
    "mean::i_q",
    "mean::v_q",
    "mean::v_q_pll_f",
    "mean::v_cmd_q_u_switched_converter_emt",
    "mean::v_cmd_q_switched_converter_emt",
    "mean::v_conv_q",
}
QAXIS_SIGN_FLIPPED_INTERVAL_KEYS: set[str] = {
    "v_conv_q_avg",
    "v_ref_hold_q_avg",
    "v_cmd_q_avg",
}


def build_qaxis_signal_mapping() -> list[tuple[str, str, str]]:
    """
    Return the signal-name mapping used by the q-axis temporal comparison.

    :return: Ordered list of tuples ``(display_name, switched_name, pseudo_name)``.
    """
    mappings: list[tuple[str, str, str]] = list([
        ("theta_pll", "theta_pll_switched_converter_emt", "theta_pll_pseudo_converter_emt"),
        ("omega_pll", "omega_pll_switched_converter_emt", "omega_pll_pseudo_converter_emt"),
        ("v_q", "v_q_switched_converter_emt_plant", "v_q_pseudo_converter_emt"),
        ("v_q_pll_f", "v_q_pll_f_switched_converter_emt", "v_q_pseudo_converter_emt"),
        ("Q", "Q_switched_converter_emt", "Q_pseudo_converter_emt"),
        ("Q_f", "Q_f_switched_converter_emt", "Q_f_pseudo_converter_emt"),
        ("i_q_ref", "i_q_ref_switched_converter_emt", "i_q_ref_pseudo_converter_emt"),
        ("v_cmd_q_u", "v_cmd_q_u_switched_converter_emt", "v_cmd_q_u_pseudo_converter_emt"),
        ("v_cmd_q", "v_cmd_q_switched_converter_emt", "v_cmd_q_pseudo_converter_emt"),
    ])
    return mappings


def build_daxis_bridge_trace_names() -> list[str]:
    """
    Return the ordered d-axis and realized-bridge trace names used by the deeper comparison.

    :return: Ordered display-name list.
    """
    trace_names: list[str] = list([
        "i_d_ref",
        "i_d",
        "i_q",
        "v_d",
        "-R*i_d",
        "+omega*L*i_q",
        "-v_pi_d_u",
        "v_cmd_d_u",
        "v_cmd_d",
        "v_lim",
        "v_q_cap",
        "v_conv_d",
        "v_conv_q",
    ])
    return trace_names


def find_name_anywhere_in_block(block: Block, variable_name: str) -> Any:
    """
    Return one symbol by name from a block, including runtime and static parameter stores.

    :param block: Symbolic block to inspect.
    :param variable_name: Requested symbol name.
    :return: Matching symbol or ``None``.
    """
    variable_groups: list[list[Any]] = list([
        block.in_vars,
        block.out_vars,
        block.algebraic_vars,
        block.state_vars,
        block.diff_vars,
        list(block.event_dict.keys()),
        list(block.mode_dict.keys()),
        list(block.parameters.keys()),
    ])
    variable_group: list[Any]
    variable: Any
    child_block: Block
    nested_result: Any

    for variable_group in variable_groups:
        for variable in variable_group:
            if variable.name == variable_name:
                return variable
            else:
                pass

    for child_block in block.children:
        nested_result = find_name_anywhere_in_block(block=child_block, variable_name=variable_name)
        if nested_result is not None:
            return nested_result
        else:
            pass

    return None


def compute_trace_metrics(
        time_arr: np.ndarray,
        switched_arr: np.ndarray,
        pseudo_arr: np.ndarray,
        analysis_start_s: float,
        threshold: float,
) -> dict[str, float]:
    """
    Compute compact temporal-comparison metrics between switched and pseudo traces.

    :param time_arr: Shared time vector.
    :param switched_arr: Switched-trace values.
    :param pseudo_arr: Pseudo-EMT reference values.
    :param analysis_start_s: Start time used by the divergence search.
    :param threshold: Absolute-difference threshold used to detect the first divergence time.
    :return: Dictionary with RMSE, max absolute error and first divergence time.
    """
    analysis_mask: np.ndarray = time_arr >= float(analysis_start_s)
    diff_arr: np.ndarray = switched_arr - pseudo_arr
    first_divergence_time_s: float = float("nan")
    divergence_indices: np.ndarray
    metrics: dict[str, float] = dict()

    if np.any(analysis_mask):
        divergence_indices = np.flatnonzero(np.abs(diff_arr[analysis_mask]) >= float(threshold))
        if len(divergence_indices) > 0:
            first_divergence_time_s = float(time_arr[analysis_mask][int(divergence_indices[0])])
        else:
            pass
    else:
        divergence_indices = np.zeros(0, dtype=int)

    metrics["rmse"] = float(np.sqrt(np.mean(diff_arr[analysis_mask] ** 2))) if np.any(analysis_mask) else float("nan")
    metrics["max_abs"] = float(np.max(np.abs(diff_arr[analysis_mask]))) if np.any(analysis_mask) else float("nan")
    metrics["first_divergence_time_s"] = first_divergence_time_s
    return metrics


def print_trace_metrics(metrics_by_signal: dict[str, dict[str, float]], title: str) -> None:
    """
    Print a compact temporal divergence table for the q-axis block comparison.

    :param metrics_by_signal: Mapping ``signal_name -> metrics``.
    :return: None.
    """
    signal_name: str
    signal_metrics: dict[str, float]

    print("=" * 100)
    print(title)
    print("=" * 100)
    print("signal      | rmse          | max_abs       | first_divergence_s")
    print("-" * 100)

    for signal_name, signal_metrics in metrics_by_signal.items():
        print(
            f"{signal_name:<11} | "
            f"{signal_metrics['rmse']:>13.6e} | "
            f"{signal_metrics['max_abs']:>13.6e} | "
            f"{signal_metrics['first_divergence_time_s']:>18.6e}"
        )


def build_pseudo_convention_trace_view(switched_signals: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """
    Return one sign-adjusted switched trace view in the pseudo converter q-axis convention.

    The switched bridge/filter stack uses one internally consistent q-axis convention
    that is opposite to the idealized pseudo dq branch for several q-channel signals.
    For colleague-facing visual comparison, this helper flips only those q-channel
    traces while leaving the real switched dynamics untouched.

    :param switched_signals: Raw switched traces.
    :return: Sign-adjusted switched traces for visual comparison.
    """
    adjusted_signals: dict[str, np.ndarray] = dict()
    signal_name: str
    signal_arr: np.ndarray

    for signal_name, signal_arr in switched_signals.items():
        if signal_name in QAXIS_SIGN_FLIPPED_TRACE_NAMES:
            adjusted_signals[signal_name] = -np.array(signal_arr, copy=True)
        else:
            adjusted_signals[signal_name] = np.array(signal_arr, copy=True)

    return adjusted_signals


def build_pseudo_convention_diagnostic_view(switched_diag: dict[str, float]) -> dict[str, float]:
    """
    Return one sign-adjusted switched diagnostic view in the pseudo q-axis convention.

    :param switched_diag: Raw switched diagnostics.
    :return: Adjusted diagnostics used only for tables and plots.
    """
    adjusted_diag: dict[str, float] = dict(switched_diag)
    diag_key: str

    for diag_key in QAXIS_SIGN_FLIPPED_DIAGNOSTIC_KEYS:
        if diag_key in adjusted_diag:
            adjusted_diag[diag_key] = -adjusted_diag[diag_key]
        else:
            pass

    return adjusted_diag


def build_pseudo_convention_interval_view(interval_signals: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """
    Return one sign-adjusted interval-averaged switched-voltage view for pseudo comparison.

    :param interval_signals: Raw interval-averaged switched/pseudo signals.
    :return: Adjusted interval signals.
    """
    adjusted_signals: dict[str, np.ndarray] = dict()
    signal_name: str
    signal_arr: np.ndarray

    for signal_name, signal_arr in interval_signals.items():
        if signal_name in QAXIS_SIGN_FLIPPED_INTERVAL_KEYS:
            adjusted_signals[signal_name] = -np.array(signal_arr, copy=True)
        else:
            adjusted_signals[signal_name] = np.array(signal_arr, copy=True)

    return adjusted_signals


def plot_trace_comparison(
        time_arr: np.ndarray,
        switched_signals: dict[str, np.ndarray],
        pseudo_signals: dict[str, np.ndarray],
        save_path: Path,
        plot_title: str,
) -> None:
    """
    Plot the q-axis block-by-block temporal comparison.

    :param time_arr: Shared time vector.
    :param switched_signals: Switched-case traces.
    :param pseudo_signals: Pseudo-EMT reference traces.
    :param save_path: Plot output path.
    :return: None.
    """
    signal_names: list[str] = list(switched_signals.keys())
    figure: plt.Figure
    axes: np.ndarray
    axis: plt.Axes
    signal_name: str
    axis_index: int = 0

    figure, axes = plt.subplots(len(signal_names), 1, figsize=(11.5, 17.0), sharex=True)

    while axis_index < len(signal_names):
        axis = axes[axis_index]
        signal_name = signal_names[axis_index]
        axis.plot(time_arr, switched_signals[signal_name], label=f"switched {signal_name}")
        axis.plot(time_arr, pseudo_signals[signal_name], label=f"pseudo {signal_name}", linestyle="--")
        axis.grid(True)
        axis.legend(loc="best")
        axis.set_ylabel(signal_name)
        axis_index += 1

    axes[0].set_title(plot_title)
    axes[-1].set_xlabel("Time [s]")
    figure.tight_layout()
    figure.savefig(save_path, dpi=180)
    plt.close(figure)


def require_problem_var(problem: EmtProblemDae, variable_name: str) -> Any:
    """
    Return one problem variable by name and assert that it exists.

    :param problem: EMT problem under inspection.
    :param variable_name: Requested variable name.
    :return: Matching symbolic variable.
    """
    variable: Any = find_name_in_block(variable_name, problem.sys_block)
    assert variable is not None
    return variable


def get_signal(problem: EmtProblemDae, state_traj: np.ndarray, variable_name: str) -> np.ndarray:
    """
    Extract one EMT trajectory by symbolic variable name.

    :param problem: EMT problem with indexing information.
    :param state_traj: EMT state trajectory.
    :param variable_name: Requested symbolic variable name.
    :return: Selected trajectory.
    """
    variable: Any = require_problem_var(problem=problem, variable_name=variable_name)
    signal_arr: np.ndarray = np.array(state_traj[:, problem.get_var_idx(variable)], copy=True)
    return signal_arr


def get_problem_parameter_value(problem: EmtProblemDae, variable_name: str) -> float:
    """
    Return one runtime or static parameter value by symbolic name.

    :param problem: EMT problem under inspection.
    :param variable_name: Requested parameter name.
    :return: Numeric parameter value.
    """
    variable: Any = find_name_anywhere_in_block(block=problem.sys_block, variable_name=variable_name)
    assert variable is not None

    if variable.uid in problem.uid2idx_event_params:
        return float(problem.event_params_values[problem.uid2idx_event_params[variable.uid]])
    elif variable.uid in problem.uid2idx_params:
        return float(problem.get_parameters_values()[problem.uid2idx_params[variable.uid]].value)
    else:
        raise KeyError(f"The symbol '{variable_name}' is not stored as a runtime or static parameter")


def sample_trace_at_time(time_arr: np.ndarray, signal_arr: np.ndarray, sample_time_s: float, tolerance_s: float = 1.0e-12) -> float:
    """
    Sample one trace at a requested time, using an exact sample when available.

    :param time_arr: Monotonic time vector.
    :param signal_arr: Trace values.
    :param sample_time_s: Requested sample time.
    :param tolerance_s: Exact-match tolerance.
    :return: Sampled trace value.
    """
    nearest_index: int = int(np.argmin(np.abs(time_arr - float(sample_time_s))))

    if abs(float(time_arr[nearest_index]) - float(sample_time_s)) <= float(tolerance_s):
        return float(signal_arr[nearest_index])
    elif sample_time_s <= float(time_arr[0]):
        return float(signal_arr[0])
    elif sample_time_s >= float(time_arr[-1]):
        return float(signal_arr[-1])
    else:
        return float(np.interp(sample_time_s, time_arr, signal_arr))


def build_interval_trace_segment(
        time_arr: np.ndarray,
        signal_arr: np.ndarray,
        interval_start_s: float,
        interval_end_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return one trace segment over a closed time interval with explicit boundary samples.

    :param time_arr: Monotonic time vector.
    :param signal_arr: Trace values.
    :param interval_start_s: Interval start time.
    :param interval_end_s: Interval end time.
    :return: Tuple ``(segment_time, segment_signal)``.
    """
    interior_mask: np.ndarray = (time_arr > (float(interval_start_s) + 1.0e-12)) & (time_arr < (float(interval_end_s) - 1.0e-12))
    interior_time_arr: np.ndarray = np.array(time_arr[interior_mask], copy=True)
    interior_signal_arr: np.ndarray = np.array(signal_arr[interior_mask], copy=True)
    start_value: float = sample_trace_at_time(time_arr=time_arr, signal_arr=signal_arr, sample_time_s=interval_start_s)
    end_value: float = sample_trace_at_time(time_arr=time_arr, signal_arr=signal_arr, sample_time_s=interval_end_s)
    segment_time_arr: np.ndarray = np.concatenate((np.array([interval_start_s], dtype=float), interior_time_arr, np.array([interval_end_s], dtype=float)))
    segment_signal_arr: np.ndarray = np.concatenate((np.array([start_value], dtype=float), interior_signal_arr, np.array([end_value], dtype=float)))
    return segment_time_arr, segment_signal_arr


def compute_interval_mean(
        time_arr: np.ndarray,
        signal_arr: np.ndarray,
        interval_start_s: float,
        interval_end_s: float,
) -> float:
    """
    Compute one time-weighted trace mean over a closed interval.

    :param time_arr: Monotonic time vector.
    :param signal_arr: Trace values.
    :param interval_start_s: Interval start time.
    :param interval_end_s: Interval end time.
    :return: Time-weighted interval mean.
    """
    segment_time_arr: np.ndarray
    segment_signal_arr: np.ndarray

    segment_time_arr, segment_signal_arr = build_interval_trace_segment(
        time_arr=time_arr,
        signal_arr=signal_arr,
        interval_start_s=interval_start_s,
        interval_end_s=interval_end_s,
    )
    return float(np.trapezoid(segment_signal_arr, segment_time_arr) / (float(interval_end_s) - float(interval_start_s)))


def compute_dq0_from_held_phase_values(
        theta_arr: np.ndarray,
        phase_a_value: float,
        phase_b_value: float,
        phase_c_value: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Reconstruct dq0 traces from one held abc phase vector and a time-varying PLL angle.

    :param theta_arr: PLL angle trace over one interval.
    :param phase_a_value: Held phase-A value.
    :param phase_b_value: Held phase-B value.
    :param phase_c_value: Held phase-C value.
    :return: Tuple ``(d_arr, q_arr, zero_arr)``.
    """
    c13: float = 1.0 / 3.0
    c23: float = 2.0 / 3.0
    theta_b_arr: np.ndarray = theta_arr - (2.0 * np.pi / 3.0)
    theta_c_arr: np.ndarray = theta_arr + (2.0 * np.pi / 3.0)
    d_arr: np.ndarray = c23 * (
        np.sin(theta_arr) * float(phase_a_value)
        + np.sin(theta_b_arr) * float(phase_b_value)
        + np.sin(theta_c_arr) * float(phase_c_value)
    )
    q_arr: np.ndarray = -c23 * (
        np.cos(theta_arr) * float(phase_a_value)
        + np.cos(theta_b_arr) * float(phase_b_value)
        + np.cos(theta_c_arr) * float(phase_c_value)
    )
    zero_arr: np.ndarray = np.full_like(theta_arr, fill_value=c13 * (float(phase_a_value) + float(phase_b_value) + float(phase_c_value)))
    return d_arr, q_arr, zero_arr


def build_full_pwm_intervals(
        omega_sw_rad_per_s: float,
        carrier_phase_rad: float,
        start_time_s: float,
        end_time_s: float,
) -> list[tuple[float, float]]:
    """
    Return the full carrier half-period intervals used by the regular-sampled PWM logic.

    :param omega_sw_rad_per_s: Positive switching angular frequency.
    :param carrier_phase_rad: Carrier phase shift.
    :param start_time_s: First admissible interval start time.
    :param end_time_s: Final admissible interval end time.
    :return: Ordered list of full intervals ``(start_s, end_s)``.
    """
    omega_sw_abs: float = abs(float(omega_sw_rad_per_s))
    half_period_s: float
    interval_index: int
    intervals: list[tuple[float, float]] = list()
    interval_start_s: float
    interval_end_s: float

    if omega_sw_abs <= 1.0e-12:
        return intervals
    else:
        pass

    half_period_s = float(np.pi / omega_sw_abs)
    interval_index = int(np.ceil((omega_sw_abs * float(start_time_s) + float(carrier_phase_rad) + 0.5 * np.pi) / np.pi - 1.0e-12))

    while True:
        interval_start_s = (float(interval_index) * np.pi - float(carrier_phase_rad) - 0.5 * np.pi) / omega_sw_abs
        interval_end_s = interval_start_s + half_period_s

        if interval_end_s > (float(end_time_s) + 1.0e-12):
            break
        else:
            pass

        if interval_start_s >= (float(start_time_s) - 1.0e-12):
            intervals.append((float(interval_start_s), float(interval_end_s)))
        else:
            pass

        interval_index += 1

    return intervals


def build_reference_grid() -> tuple[gce.MultiCircuit, gce.Bus, gce.Bus, gce.Generator, gce.VSC, gce.Load]:
    """
    Build the simple AC/DC topology used by the pseudo and switched comparison.

    :return: Tuple with grid, buses and key devices.
    """
    grid: gce.MultiCircuit = gce.MultiCircuit(
        name="Grid - Thevenin + converter + DC load",
        Sbase=100.0,
        fbase=COMPARISON_FBASE_HZ,
    )
    bus_ac: gce.Bus = gce.Bus(name="Bus_AC", Vnom=230.0, is_slack=True)
    bus_dc: gce.Bus = gce.Bus(name="Bus_DC", Vnom=320.0, is_dc=True)
    generator: gce.Generator = gce.Generator(name="Gen_Thev", vset=1.0, Snom=100.0, freq=50.0, r1=0.001, x1=0.04)
    converter: gce.VSC = gce.VSC(
        name="converter_compare",
        bus_from=bus_dc,
        bus_to=bus_ac,
        rate=grid.Sbase,
        control1=ConverterControlType.Qac,
        control2=ConverterControlType.Vm_dc,
        control1_val=0.0,
        control2_val=1.0,
    )
    dc_load: gce.Load = gce.Load(name="DC_R_Load", P=30.0, Q=0.0)

    grid.add_bus(bus_ac)
    grid.add_bus(bus_dc)
    grid.add_generator(bus_ac, generator)
    grid.add_vsc(converter)
    grid.add_load(bus_dc, dc_load)
    return grid, bus_ac, bus_dc, generator, converter, dc_load


def attach_common_bus_models(grid: gce.MultiCircuit) -> None:
    """
    Attach EMT bus shells to every bus of the comparison grid.

    :param grid: Comparison grid.
    :return: None.
    """
    bus: gce.Bus

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)


def attach_common_device_models(
        grid: gce.MultiCircuit,
        generator: gce.Generator,
        converter: gce.VSC,
        dc_load: gce.Load,
        converter_model: Block,
        dc_load_model_name: str,
) -> tuple[Block, Block, Block]:
    """
    Attach the common Thevenin source, converter and DC-load EMT models.

    :param grid: Comparison grid.
    :param generator: AC Thevenin source.
    :param converter: Converter device.
    :param dc_load: DC load device.
    :param converter_model: Converter EMT model block.
    :param dc_load_model_name: Name used for the DC load EMT model.
    :return: Tuple with generator, converter and DC-load EMT blocks.
    """
    gen_mdl: Block = get_generator_thevenin_rl_emt_template(vf=grid.var_factory).block
    dc_load_mdl: Block = get_dc_load_emt_template(vf=grid.var_factory, name=dc_load_model_name).block

    set_emt_model(device=generator, model=gen_mdl, var_factory=grid.var_factory)
    set_emt_model(device=converter, model=converter_model, var_factory=grid.var_factory)
    set_emt_model(device=dc_load, model=dc_load_mdl, var_factory=grid.var_factory)
    return gen_mdl, converter_model, dc_load_mdl


def apply_common_converter_tuning(converter_model: Block, model_name: str, l_eq_value: float) -> None:
    """
    Apply the same controller tuning to pseudo and switched converter variants.

    :param converter_model: Converter EMT model block.
    :param model_name: Converter symbolic model name.
    :param l_eq_value: Filter inductance value used by the case.
    :return: None.
    """
    parameter_updates: list[tuple[str, float]] = list([
        (f"R_eq_{model_name}", COMPARISON_R_EQ),
        (f"L_eq_{model_name}", l_eq_value),
        (f"pll_kp_{model_name}", 40.0),
        (f"pll_ki_{model_name}", 400.0),
        (f"i_kp_{model_name}", 0.6),
        (f"i_ki_{model_name}", 50.0),
        (f"vdc_kp_{model_name}", 2.0),
        (f"vdc_ki_{model_name}", 30.0),
        (f"q_kp_{model_name}", 1.6),
        (f"q_ki_{model_name}", 60.0),
        (f"i_max_{model_name}", 1.3),
        (f"m_max_{model_name}", 0.95),
        (f"tau_meas_{model_name}", 0.005),
        (f"aw_gain_{model_name}", 0.1),
        (f"vdc_floor_{model_name}", 0.05),
    ])
    parameter_name: str
    parameter_value: float

    for parameter_name, parameter_value in parameter_updates:
        converter_model.set_parameter_in_model(var_name=parameter_name, new_value=parameter_value)


def build_comparison_emt_options() -> EmtOptions:
    """
    Build the EMT options used by the pseudo vs switched q-axis comparison.

    :return: EMT options instance.
    """
    options: EmtOptions = EmtOptions(
        time_step=1.0e-5,
        simulation_time=5.0e-3,
        tolerance=1.0e-6,
        solver_type=EmtSolverTypes.Symbolic,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.Explicit,
        verbose=0,
    )
    options.newton_max_iter = 20
    return options


def build_problem(grid: gce.MultiCircuit, pf_results: PowerFlowResults, options: EmtOptions) -> EmtProblemDae:
    """
    Build one EMT problem from the comparison grid.

    :param grid: Comparison grid.
    :param pf_results: Balanced power-flow seed.
    :param options: EMT options.
    :return: Configured EMT problem.
    """
    problem: EmtProblemDae = EmtProblemDae(grid=grid, options=options, pf_results=pf_results, pf_results_3Ph=None)
    return problem


def run_case(problem: EmtProblemDae, model_name: str) -> ConverterCaseArtifacts:
    """
    Run one EMT problem and return the relevant raw artifacts.

    :param problem: EMT problem to solve.
    :param model_name: Converter symbolic model name.
    :return: Runtime bundle for diagnostics.
    """
    solver: Any = build_emt_solver(
        options=problem.options,
        problem=problem,
        t0=0.0,
        t_end=float(problem.options.simulation_time),
        h=float(problem.options.time_step),
        method=problem.options.integration_method,
    )
    boundary_updater: Any = build_boundary_updater_from_block(problem)
    time_arr: np.ndarray
    state_traj: np.ndarray
    _diff_traj: np.ndarray
    _well_initialized: bool
    _converged: bool
    artifacts: ConverterCaseArtifacts

    time_arr, state_traj, _diff_traj, _well_initialized, _converged = solver.simulate(boundary_updater=boundary_updater)
    artifacts = ConverterCaseArtifacts(problem=problem, model_name=model_name, time_arr=time_arr, state_traj=state_traj)
    return artifacts


def compute_case_tail_means(artifacts: ConverterCaseArtifacts) -> dict[str, float]:
    """
    Compute q-axis diagnostics over the final 2 ms window of one case.

    :param artifacts: Runtime bundle of one converter case.
    :return: Dictionary with tail-window means.
    """
    tail_window_s: float = TAIL_WINDOW_S
    problem: EmtProblemDae = artifacts.problem
    model_name: str = artifacts.model_name
    time_arr: np.ndarray = artifacts.time_arr
    state_traj: np.ndarray = artifacts.state_traj
    tail_mask: np.ndarray = time_arr >= (time_arr[-1] - tail_window_s)
    diagnostics: dict[str, float] = dict()
    variable_name: str
    signal_arr: np.ndarray
    i_d_arr: np.ndarray
    i_q_arr: np.ndarray
    omega_pll_arr: np.ndarray
    v_pi_d_u_arr: np.ndarray
    v_lim_arr: np.ndarray
    v_cmd_d_arr: np.ndarray

    diagnostics["tail_window_s"] = tail_window_s

    for variable_name in list([
        f"i_d_ref_{model_name}",
        f"i_q_ref_{model_name}",
        f"P_f_{model_name}",
        f"Q_f_{model_name}",
        f"v_pi_d_u_{model_name}",
        f"v_pi_q_u_{model_name}",
        f"v_cmd_d_u_{model_name}",
        f"v_cmd_q_u_{model_name}",
        f"v_cmd_d_{model_name}",
        f"v_cmd_q_{model_name}",
        f"v_lim_{model_name}",
        f"v_dc_{model_name}",
        f"omega_pll_{model_name}",
    ]):
        signal_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=variable_name)
        diagnostics[f"mean::{variable_name}"] = float(np.mean(signal_arr[tail_mask]))

    if model_name.startswith("switched"):
        i_d_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"i_d_{model_name}_plant")
        diagnostics["mean::i_d"] = float(np.mean(i_d_arr[tail_mask]))
        i_q_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"i_q_{model_name}_plant")
        diagnostics["mean::i_q"] = float(np.mean(i_q_arr[tail_mask]))
        signal_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_d_{model_name}_plant")
        diagnostics["mean::v_d"] = float(np.mean(signal_arr[tail_mask]))
        signal_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_q_{model_name}_plant")
        diagnostics["mean::v_q"] = float(np.mean(signal_arr[tail_mask]))
        signal_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_q_pll_f_{model_name}")
        diagnostics["mean::v_q_pll_f"] = float(np.mean(signal_arr[tail_mask]))
        signal_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_conv_d_{model_name}")
        diagnostics["mean::v_conv_d"] = float(np.mean(signal_arr[tail_mask]))
        signal_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_conv_q_{model_name}")
        diagnostics["mean::v_conv_q"] = float(np.mean(signal_arr[tail_mask]))
    else:
        i_d_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"i_d_{model_name}")
        diagnostics["mean::i_d"] = float(np.mean(i_d_arr[tail_mask]))
        i_q_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"i_q_{model_name}")
        diagnostics["mean::i_q"] = float(np.mean(i_q_arr[tail_mask]))
        signal_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_d_{model_name}")
        diagnostics["mean::v_d"] = float(np.mean(signal_arr[tail_mask]))
        signal_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_q_{model_name}")
        diagnostics["mean::v_q"] = float(np.mean(signal_arr[tail_mask]))
        diagnostics["mean::v_q_pll_f"] = diagnostics["mean::v_q"]
        diagnostics["mean::v_conv_d"] = diagnostics[f"mean::v_cmd_d_{model_name}"]
        diagnostics["mean::v_conv_q"] = diagnostics[f"mean::v_cmd_q_{model_name}"]

    omega_pll_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"omega_pll_{model_name}")
    v_pi_d_u_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_pi_d_u_{model_name}")
    v_lim_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_lim_{model_name}")
    v_cmd_d_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_cmd_d_{model_name}")
    diagnostics["mean::-R*i_d"] = float(np.mean((-COMPARISON_R_EQ * i_d_arr)[tail_mask]))
    diagnostics["mean::+omega*L*i_q"] = float(np.mean(((omega_pll_arr / COMPARISON_OMEGA_BASE_RAD_PER_S) * COMPARISON_L_EQ * i_q_arr)[tail_mask]))
    diagnostics["mean::-v_pi_d_u"] = float(np.mean((-v_pi_d_u_arr)[tail_mask]))
    diagnostics["mean::v_q_cap"] = float(np.mean(np.sqrt(np.maximum(v_lim_arr * v_lim_arr - v_cmd_d_arr * v_cmd_d_arr, 1.0e-10))[tail_mask]))

    return diagnostics


def print_qaxis_comparison(switched_diag: dict[str, float], pseudo_diag: dict[str, float], title: str) -> None:
    """
    Print the q-axis comparison table between switched and pseudo EMT converters.

    :param switched_diag: Tail-window diagnostics of the switched case.
    :param pseudo_diag: Tail-window diagnostics of the pseudo-EMT case.
    :return: None.
    """
    metric_names: list[tuple[str, str]] = list([
        ("i_d_ref", "mean::i_d_ref_switched_converter_emt"),
        ("i_d", "mean::i_d"),
        ("i_q_ref", "mean::i_q_ref_switched_converter_emt"),
        ("i_q", "mean::i_q"),
        ("v_q_pll_f", "mean::v_q_pll_f"),
        ("P_f", "mean::P_f_switched_converter_emt"),
        ("Q_f", "mean::Q_f_switched_converter_emt"),
        ("v_q", "mean::v_q"),
        ("v_cmd_q_u", "mean::v_cmd_q_u_switched_converter_emt"),
        ("v_cmd_q", "mean::v_cmd_q_switched_converter_emt"),
    ])
    pseudo_metric_names: dict[str, str] = dict([
        ("i_d_ref", "mean::i_d_ref_pseudo_converter_emt"),
        ("i_d", "mean::i_d"),
        ("i_q_ref", "mean::i_q_ref_pseudo_converter_emt"),
        ("i_q", "mean::i_q"),
        ("v_q_pll_f", "mean::v_q_pll_f"),
        ("P_f", "mean::P_f_pseudo_converter_emt"),
        ("Q_f", "mean::Q_f_pseudo_converter_emt"),
        ("v_q", "mean::v_q"),
        ("v_cmd_q_u", "mean::v_cmd_q_u_pseudo_converter_emt"),
        ("v_cmd_q", "mean::v_cmd_q_pseudo_converter_emt"),
    ])
    display_name: str
    switched_key: str
    pseudo_key: str

    print("=" * 100)
    print(title)
    print("=" * 100)
    print("metric      | switched      | pseudo        | delta(sw-pseudo)")
    print("-" * 100)

    for display_name, switched_key in metric_names:
        pseudo_key = pseudo_metric_names[display_name]
        print(
            f"{display_name:<11} | "
            f"{switched_diag[switched_key]:>13.6f} | "
            f"{pseudo_diag[pseudo_key]:>13.6f} | "
            f"{(switched_diag[switched_key] - pseudo_diag[pseudo_key]):>16.6f}"
        )


def print_qaxis_sign_convention_note() -> None:
    """
    Print one compact note explaining the raw vs pseudo-equivalent switched q-axis views.

    :return: None.
    """
    print("=" * 100)
    print("Q-AXIS SIGN-CONVENTION NOTE")
    print("=" * 100)
    print("Raw switched traces keep the physical internal convention used by the abc bridge/filter stack.")
    print("Pseudo-equivalent traces flip only q-channel diagnostics for visual overlay with the pseudo dq model.")
    print("The switched dynamics are unchanged; only the comparison view is re-expressed.")


def print_daxis_comparison(switched_diag: dict[str, float], pseudo_diag: dict[str, float]) -> None:
    """
    Print the d-axis command decomposition and realized-bridge comparison.

    :param switched_diag: Tail-window diagnostics of the switched case.
    :param pseudo_diag: Tail-window diagnostics of the pseudo-EMT case.
    :return: None.
    """
    metric_names: list[tuple[str, str]] = list([
        ("i_d_ref", "mean::i_d_ref_switched_converter_emt"),
        ("i_d", "mean::i_d"),
        ("i_q", "mean::i_q"),
        ("v_d", "mean::v_d"),
        ("-R*i_d", "mean::-R*i_d"),
        ("+omega*L*i_q", "mean::+omega*L*i_q"),
        ("-v_pi_d_u", "mean::-v_pi_d_u"),
        ("v_cmd_d_u", "mean::v_cmd_d_u_switched_converter_emt"),
        ("v_cmd_d", "mean::v_cmd_d_switched_converter_emt"),
        ("v_lim", "mean::v_lim_switched_converter_emt"),
        ("v_q_cap", "mean::v_q_cap"),
        ("v_conv_d", "mean::v_conv_d"),
        ("v_conv_q", "mean::v_conv_q"),
    ])
    pseudo_metric_names: dict[str, str] = dict([
        ("i_d_ref", "mean::i_d_ref_pseudo_converter_emt"),
        ("i_d", "mean::i_d"),
        ("i_q", "mean::i_q"),
        ("v_d", "mean::v_d"),
        ("-R*i_d", "mean::-R*i_d"),
        ("+omega*L*i_q", "mean::+omega*L*i_q"),
        ("-v_pi_d_u", "mean::-v_pi_d_u"),
        ("v_cmd_d_u", "mean::v_cmd_d_u_pseudo_converter_emt"),
        ("v_cmd_d", "mean::v_cmd_d_pseudo_converter_emt"),
        ("v_lim", "mean::v_lim_pseudo_converter_emt"),
        ("v_q_cap", "mean::v_q_cap"),
        ("v_conv_d", "mean::v_conv_d"),
        ("v_conv_q", "mean::v_conv_q"),
    ])
    display_name: str
    switched_key: str
    pseudo_key: str

    print("=" * 100)
    print("D-AXIS / BRIDGE BLOCK-BY-BLOCK COMPARISON")
    print("=" * 100)
    print("metric      | switched      | pseudo        | delta(sw-pseudo)")
    print("-" * 100)

    for display_name, switched_key in metric_names:
        pseudo_key = pseudo_metric_names[display_name]
        print(
            f"{display_name:<11} | "
            f"{switched_diag[switched_key]:>13.6f} | "
            f"{pseudo_diag[pseudo_key]:>13.6f} | "
            f"{(switched_diag[switched_key] - pseudo_diag[pseudo_key]):>16.6f}"
        )


def build_named_signal_traces(artifacts: ConverterCaseArtifacts) -> dict[str, np.ndarray]:
    """
    Return the named q-axis comparison traces for one converter case.

    :param artifacts: Runtime bundle of one converter case.
    :return: Mapping ``display_name -> trace``.
    """
    mappings: list[tuple[str, str, str]] = build_qaxis_signal_mapping()
    traces: dict[str, np.ndarray] = dict()
    display_name: str
    switched_name: str
    pseudo_name: str
    selected_name: str

    for display_name, switched_name, pseudo_name in mappings:
        if artifacts.model_name.startswith("switched"):
            selected_name = switched_name
        else:
            selected_name = pseudo_name
        traces[display_name] = get_signal(
            problem=artifacts.problem,
            state_traj=artifacts.state_traj,
            variable_name=selected_name,
        )

    return traces


def build_daxis_bridge_traces(artifacts: ConverterCaseArtifacts) -> dict[str, np.ndarray]:
    """
    Return the d-axis decomposition and realized-bridge traces for one converter case.

    :param artifacts: Runtime bundle of one converter case.
    :return: Mapping ``display_name -> trace``.
    """
    problem: EmtProblemDae = artifacts.problem
    state_traj: np.ndarray = artifacts.state_traj
    model_name: str = artifacts.model_name
    i_d_name: str
    i_q_name: str
    v_d_name: str
    v_conv_d_name: str
    v_conv_q_name: str
    traces: dict[str, np.ndarray] = dict()
    i_d_arr: np.ndarray
    i_q_arr: np.ndarray
    omega_pll_arr: np.ndarray
    v_pi_d_u_arr: np.ndarray
    v_cmd_d_arr: np.ndarray
    v_lim_arr: np.ndarray

    if model_name.startswith("switched"):
        i_d_name = f"i_d_{model_name}_plant"
        i_q_name = f"i_q_{model_name}_plant"
        v_d_name = f"v_d_{model_name}_plant"
        v_conv_d_name = f"v_conv_d_{model_name}"
        v_conv_q_name = f"v_conv_q_{model_name}"
    else:
        i_d_name = f"i_d_{model_name}"
        i_q_name = f"i_q_{model_name}"
        v_d_name = f"v_d_{model_name}"
        v_conv_d_name = f"v_cmd_d_{model_name}"
        v_conv_q_name = f"v_cmd_q_{model_name}"

    i_d_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=i_d_name)
    i_q_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=i_q_name)
    omega_pll_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"omega_pll_{model_name}")
    v_pi_d_u_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_pi_d_u_{model_name}")
    v_cmd_d_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_cmd_d_{model_name}")
    v_lim_arr = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_lim_{model_name}")

    traces["i_d_ref"] = get_signal(problem=problem, state_traj=state_traj, variable_name=f"i_d_ref_{model_name}")
    traces["i_d"] = i_d_arr
    traces["i_q"] = i_q_arr
    traces["v_d"] = get_signal(problem=problem, state_traj=state_traj, variable_name=v_d_name)
    traces["-R*i_d"] = -COMPARISON_R_EQ * i_d_arr
    traces["+omega*L*i_q"] = (omega_pll_arr / COMPARISON_OMEGA_BASE_RAD_PER_S) * COMPARISON_L_EQ * i_q_arr
    traces["-v_pi_d_u"] = -v_pi_d_u_arr
    traces["v_cmd_d_u"] = get_signal(problem=problem, state_traj=state_traj, variable_name=f"v_cmd_d_u_{model_name}")
    traces["v_cmd_d"] = v_cmd_d_arr
    traces["v_lim"] = v_lim_arr
    traces["v_q_cap"] = np.sqrt(np.maximum(v_lim_arr * v_lim_arr - v_cmd_d_arr * v_cmd_d_arr, 1.0e-10))
    traces["v_conv_d"] = get_signal(problem=problem, state_traj=state_traj, variable_name=v_conv_d_name)
    traces["v_conv_q"] = get_signal(problem=problem, state_traj=state_traj, variable_name=v_conv_q_name)

    return traces


def compute_interval_averaged_bridge_comparison(
        switched_artifacts: ConverterCaseArtifacts,
        pseudo_artifacts: ConverterCaseArtifacts,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, float]]:
    """
    Compare interval-averaged realized bridge dq voltage against held sampled phase references.

    The PWM logic samples modulation values at the accepted left boundary of each carrier
    half-period and then holds the resulting schedule over that full interval. This helper
    reproduces that timing contract so the realized bridge dq bias can be separated from
    pure switching ripple.

    :param switched_artifacts: Switched-converter run artifacts.
    :param pseudo_artifacts: Pseudo-EMT reference run artifacts.
    :return: Tuple ``(interval_mid_arr, interval_signals, metadata)``.
    """
    switched_problem: EmtProblemDae = switched_artifacts.problem
    pseudo_problem: EmtProblemDae = pseudo_artifacts.problem
    switched_time_arr: np.ndarray = switched_artifacts.time_arr
    pseudo_time_arr: np.ndarray = pseudo_artifacts.time_arr
    omega_sw_rad_per_s: float = get_problem_parameter_value(problem=switched_problem, variable_name="omega_sw_switched_converter_emt")
    carrier_phase_rad: float = get_problem_parameter_value(problem=switched_problem, variable_name="carrier_phase_switched_converter_emt")
    t_enable_s: float = get_problem_parameter_value(problem=switched_problem, variable_name="t_enable_sw_switched_converter_emt")
    intervals: list[tuple[float, float]] = build_full_pwm_intervals(
        omega_sw_rad_per_s=omega_sw_rad_per_s,
        carrier_phase_rad=carrier_phase_rad,
        start_time_s=t_enable_s,
        end_time_s=float(switched_time_arr[-1]),
    )
    interval_count: int = len(intervals)
    interval_mid_arr: np.ndarray = np.zeros(interval_count, dtype=float)
    signals: dict[str, np.ndarray] = dict([
        ("v_conv_d_avg", np.zeros(interval_count, dtype=float)),
        ("v_conv_q_avg", np.zeros(interval_count, dtype=float)),
        ("v_ref_hold_d_avg", np.zeros(interval_count, dtype=float)),
        ("v_ref_hold_q_avg", np.zeros(interval_count, dtype=float)),
        ("v_cmd_d_avg", np.zeros(interval_count, dtype=float)),
        ("v_cmd_q_avg", np.zeros(interval_count, dtype=float)),
        ("pseudo_v_cmd_d_avg", np.zeros(interval_count, dtype=float)),
        ("pseudo_v_cmd_q_avg", np.zeros(interval_count, dtype=float)),
    ])
    metadata: dict[str, float] = dict([
        ("omega_sw_rad_per_s", omega_sw_rad_per_s),
        ("carrier_phase_rad", carrier_phase_rad),
        ("t_enable_s", t_enable_s),
        ("half_period_s", float(np.pi / max(abs(omega_sw_rad_per_s), 1.0e-12))),
        ("interval_count", float(interval_count)),
    ])
    theta_pll_arr: np.ndarray = get_signal(problem=switched_problem, state_traj=switched_artifacts.state_traj, variable_name="theta_pll_switched_converter_emt")
    sampled_v_ref_a_name: str
    sampled_v_ref_b_name: str
    sampled_v_ref_c_name: str
    sampled_v_ref_a_name = "v_ref_a_pwm_switched_converter_emt_plant_bridge"
    sampled_v_ref_b_name = "v_ref_b_pwm_switched_converter_emt_plant_bridge"
    sampled_v_ref_c_name = "v_ref_c_pwm_switched_converter_emt_plant_bridge"

    if find_name_anywhere_in_block(switched_problem.sys_block, sampled_v_ref_a_name) is None:
        sampled_v_ref_a_name = "v_ref_a_switched_converter_emt_plant_bridge"
        sampled_v_ref_b_name = "v_ref_b_switched_converter_emt_plant_bridge"
        sampled_v_ref_c_name = "v_ref_c_switched_converter_emt_plant_bridge"
    else:
        pass

    v_ref_a_arr: np.ndarray = get_signal(problem=switched_problem, state_traj=switched_artifacts.state_traj, variable_name=sampled_v_ref_a_name)
    v_ref_b_arr: np.ndarray = get_signal(problem=switched_problem, state_traj=switched_artifacts.state_traj, variable_name=sampled_v_ref_b_name)
    v_ref_c_arr: np.ndarray = get_signal(problem=switched_problem, state_traj=switched_artifacts.state_traj, variable_name=sampled_v_ref_c_name)
    v_conv_d_arr: np.ndarray = get_signal(problem=switched_problem, state_traj=switched_artifacts.state_traj, variable_name="v_conv_d_switched_converter_emt")
    v_conv_q_arr: np.ndarray = get_signal(problem=switched_problem, state_traj=switched_artifacts.state_traj, variable_name="v_conv_q_switched_converter_emt")
    v_cmd_d_arr: np.ndarray = get_signal(problem=switched_problem, state_traj=switched_artifacts.state_traj, variable_name="v_cmd_d_switched_converter_emt")
    v_cmd_q_arr: np.ndarray = get_signal(problem=switched_problem, state_traj=switched_artifacts.state_traj, variable_name="v_cmd_q_switched_converter_emt")
    pseudo_v_cmd_d_arr: np.ndarray = get_signal(problem=pseudo_problem, state_traj=pseudo_artifacts.state_traj, variable_name="v_cmd_d_pseudo_converter_emt")
    pseudo_v_cmd_q_arr: np.ndarray = get_signal(problem=pseudo_problem, state_traj=pseudo_artifacts.state_traj, variable_name="v_cmd_q_pseudo_converter_emt")
    interval_index: int = 0
    interval_start_s: float
    interval_end_s: float
    theta_seg_t_arr: np.ndarray
    theta_seg_arr: np.ndarray
    v_ref_a_hold: float
    v_ref_b_hold: float
    v_ref_c_hold: float
    v_ref_hold_d_seg_arr: np.ndarray
    v_ref_hold_q_seg_arr: np.ndarray
    _unused_zero_seg_arr: np.ndarray

    while interval_index < interval_count:
        interval_start_s, interval_end_s = intervals[interval_index]
        interval_mid_arr[interval_index] = 0.5 * (interval_start_s + interval_end_s)
        signals["v_conv_d_avg"][interval_index] = compute_interval_mean(
            time_arr=switched_time_arr,
            signal_arr=v_conv_d_arr,
            interval_start_s=interval_start_s,
            interval_end_s=interval_end_s,
        )
        signals["v_conv_q_avg"][interval_index] = compute_interval_mean(
            time_arr=switched_time_arr,
            signal_arr=v_conv_q_arr,
            interval_start_s=interval_start_s,
            interval_end_s=interval_end_s,
        )
        signals["v_cmd_d_avg"][interval_index] = compute_interval_mean(
            time_arr=switched_time_arr,
            signal_arr=v_cmd_d_arr,
            interval_start_s=interval_start_s,
            interval_end_s=interval_end_s,
        )
        signals["v_cmd_q_avg"][interval_index] = compute_interval_mean(
            time_arr=switched_time_arr,
            signal_arr=v_cmd_q_arr,
            interval_start_s=interval_start_s,
            interval_end_s=interval_end_s,
        )
        signals["pseudo_v_cmd_d_avg"][interval_index] = compute_interval_mean(
            time_arr=pseudo_time_arr,
            signal_arr=pseudo_v_cmd_d_arr,
            interval_start_s=interval_start_s,
            interval_end_s=interval_end_s,
        )
        signals["pseudo_v_cmd_q_avg"][interval_index] = compute_interval_mean(
            time_arr=pseudo_time_arr,
            signal_arr=pseudo_v_cmd_q_arr,
            interval_start_s=interval_start_s,
            interval_end_s=interval_end_s,
        )

        theta_seg_t_arr, theta_seg_arr = build_interval_trace_segment(
            time_arr=switched_time_arr,
            signal_arr=theta_pll_arr,
            interval_start_s=interval_start_s,
            interval_end_s=interval_end_s,
        )
        v_ref_a_hold = sample_trace_at_time(time_arr=switched_time_arr, signal_arr=v_ref_a_arr, sample_time_s=interval_start_s)
        v_ref_b_hold = sample_trace_at_time(time_arr=switched_time_arr, signal_arr=v_ref_b_arr, sample_time_s=interval_start_s)
        v_ref_c_hold = sample_trace_at_time(time_arr=switched_time_arr, signal_arr=v_ref_c_arr, sample_time_s=interval_start_s)
        v_ref_hold_d_seg_arr, v_ref_hold_q_seg_arr, _unused_zero_seg_arr = compute_dq0_from_held_phase_values(
            theta_arr=theta_seg_arr,
            phase_a_value=v_ref_a_hold,
            phase_b_value=v_ref_b_hold,
            phase_c_value=v_ref_c_hold,
        )
        signals["v_ref_hold_d_avg"][interval_index] = float(np.trapezoid(v_ref_hold_d_seg_arr, theta_seg_t_arr) / (interval_end_s - interval_start_s))
        signals["v_ref_hold_q_avg"][interval_index] = float(np.trapezoid(v_ref_hold_q_seg_arr, theta_seg_t_arr) / (interval_end_s - interval_start_s))
        interval_index += 1

    return interval_mid_arr, signals, metadata


def print_interval_averaged_bridge_comparison(
        interval_mid_arr: np.ndarray,
        interval_signals: dict[str, np.ndarray],
        metadata: dict[str, float],
) -> None:
    """
    Print a compact summary of the interval-averaged bridge-voltage comparison.

    :param interval_mid_arr: Carrier-interval midpoints.
    :param interval_signals: Interval-averaged comparison traces.
    :param metadata: Interval metadata.
    :return: None.
    """
    tail_count: int = min(TAIL_INTERVAL_COUNT, len(interval_mid_arr))
    tail_slice: slice
    component_name: str
    realized_key: str
    held_key: str
    switched_cmd_key: str
    pseudo_cmd_key: str
    q_realized_minus_held: float
    q_held_minus_switched_cmd: float

    print("=" * 100)
    print("PWM INTERVAL-AVERAGED BRIDGE COMPARISON")
    print("=" * 100)
    print(f"omega_sw [rad/s] : {metadata['omega_sw_rad_per_s']: .6f}")
    print(f"half-period [s]  : {metadata['half_period_s']: .6e}")
    print(f"handover [s]     : {metadata['t_enable_s']: .6e}")
    print(f"interval count   : {int(metadata['interval_count'])}")

    if tail_count <= 0:
        print("No full post-handover PWM intervals were available for interval-averaged comparison.")
        return
    else:
        pass

    tail_slice = slice(len(interval_mid_arr) - tail_count, len(interval_mid_arr))
    print(f"tail intervals   : last {tail_count} full carrier half-periods")
    print("-" * 100)
    print("component   | realized_avg  | held_ref_avg  | switched_cmd  | pseudo_cmd    | real-held     | held-swcmd")
    print("-" * 100)

    for component_name, realized_key, held_key, switched_cmd_key, pseudo_cmd_key in list([
        ("d-axis", "v_conv_d_avg", "v_ref_hold_d_avg", "v_cmd_d_avg", "pseudo_v_cmd_d_avg"),
        ("q-axis", "v_conv_q_avg", "v_ref_hold_q_avg", "v_cmd_q_avg", "pseudo_v_cmd_q_avg"),
    ]):
        print(
            f"{component_name:<11} | "
            f"{float(np.mean(interval_signals[realized_key][tail_slice])):>13.6f} | "
            f"{float(np.mean(interval_signals[held_key][tail_slice])):>13.6f} | "
            f"{float(np.mean(interval_signals[switched_cmd_key][tail_slice])):>13.6f} | "
            f"{float(np.mean(interval_signals[pseudo_cmd_key][tail_slice])):>13.6f} | "
            f"{float(np.mean(interval_signals[realized_key][tail_slice] - interval_signals[held_key][tail_slice])):>13.6f} | "
            f"{float(np.mean(interval_signals[held_key][tail_slice] - interval_signals[switched_cmd_key][tail_slice])):>13.6f}"
        )

    q_realized_minus_held = float(np.mean(interval_signals["v_conv_q_avg"][tail_slice] - interval_signals["v_ref_hold_q_avg"][tail_slice]))
    q_held_minus_switched_cmd = float(np.mean(interval_signals["v_ref_hold_q_avg"][tail_slice] - interval_signals["v_cmd_q_avg"][tail_slice]))
    print("-" * 100)

    if abs(q_realized_minus_held) < 0.25 * abs(q_held_minus_switched_cmd):
        print("Interpretation: interval-averaged bridge q-voltage follows the held sampled phase reference much more closely than the dq command")
        print("Interpretation: the dominant residual defect points to PWM timing / zero-order-hold behaviour, not to dq reconstruction")
    else:
        print("Interpretation: interval-averaged bridge q-voltage is still far from the held sampled phase reference")
        print("Interpretation: inspect carrier scheduling and phase-voltage reconstruction before attributing the mismatch to dq hold timing alone")


def plot_interval_averaged_bridge_comparison(
        interval_mid_arr: np.ndarray,
        interval_signals: dict[str, np.ndarray],
        save_path: Path,
        plot_title: str,
) -> None:
    """
    Plot the interval-averaged bridge-voltage comparison.

    :param interval_mid_arr: Carrier-interval midpoints.
    :param interval_signals: Interval-averaged comparison traces.
    :param save_path: Plot output path.
    :param plot_title: Figure title.
    :return: None.
    """
    figure: plt.Figure
    axes: np.ndarray
    axis_d: plt.Axes
    axis_q: plt.Axes

    figure, axes = plt.subplots(2, 1, figsize=(11.5, 7.5), sharex=True)
    axis_d = axes[0]
    axis_q = axes[1]

    axis_d.plot(interval_mid_arr, interval_signals["v_conv_d_avg"], marker="o", label="switched v_conv_d avg")
    axis_d.plot(interval_mid_arr, interval_signals["v_ref_hold_d_avg"], marker="s", label="held phase-ref dq avg", linestyle="--")
    axis_d.plot(interval_mid_arr, interval_signals["v_cmd_d_avg"], marker="^", label="switched v_cmd_d avg", linestyle=":")
    axis_d.plot(interval_mid_arr, interval_signals["pseudo_v_cmd_d_avg"], label="pseudo v_cmd_d avg", linestyle="-.")
    axis_d.grid(True)
    axis_d.legend(loc="best")
    axis_d.set_ylabel("d-axis")
    axis_d.set_title(plot_title)

    axis_q.plot(interval_mid_arr, interval_signals["v_conv_q_avg"], marker="o", label="switched v_conv_q avg")
    axis_q.plot(interval_mid_arr, interval_signals["v_ref_hold_q_avg"], marker="s", label="held phase-ref dq avg", linestyle="--")
    axis_q.plot(interval_mid_arr, interval_signals["v_cmd_q_avg"], marker="^", label="switched v_cmd_q avg", linestyle=":")
    axis_q.plot(interval_mid_arr, interval_signals["pseudo_v_cmd_q_avg"], label="pseudo v_cmd_q avg", linestyle="-.")
    axis_q.grid(True)
    axis_q.legend(loc="best")
    axis_q.set_ylabel("q-axis")
    axis_q.set_xlabel("Time [s]")

    figure.tight_layout()
    figure.savefig(save_path, dpi=180)
    plt.close(figure)


def main() -> None:
    """
    Run the switched vs pseudo q-axis comparison on the matched simple topology.

    :return: None.
    """
    options: EmtOptions = build_comparison_emt_options()
    grid_sw: gce.MultiCircuit
    bus_ac_sw: gce.Bus
    bus_dc_sw: gce.Bus
    generator_sw: gce.Generator
    converter_sw: gce.VSC
    dc_load_sw: gce.Load
    pf_results_sw: PowerFlowResults
    switched_model: Block
    switched_artifacts: ConverterCaseArtifacts
    switched_diag: dict[str, float]
    grid_ps: gce.MultiCircuit
    bus_ac_ps: gce.Bus
    bus_dc_ps: gce.Bus
    generator_ps: gce.Generator
    converter_ps: gce.VSC
    dc_load_ps: gce.Load
    pf_results_ps: PowerFlowResults
    pseudo_model: Block
    pseudo_artifacts: ConverterCaseArtifacts
    pseudo_diag: dict[str, float]
    switched_signals: dict[str, np.ndarray]
    pseudo_signals: dict[str, np.ndarray]
    qaxis_metrics_by_signal: dict[str, dict[str, float]] = dict()
    switched_daxis_signals: dict[str, np.ndarray]
    pseudo_daxis_signals: dict[str, np.ndarray]
    daxis_metrics_by_signal: dict[str, dict[str, float]] = dict()
    interval_mid_arr: np.ndarray
    interval_signals: dict[str, np.ndarray]
    interval_metadata: dict[str, float]
    display_name: str
    pseudo_view_save_path: Path
    interval_pseudo_view_save_path: Path

    grid_sw, bus_ac_sw, bus_dc_sw, generator_sw, converter_sw, dc_load_sw = build_reference_grid()
    attach_common_bus_models(grid_sw)
    pf_results_sw = gce.power_flow(grid=grid_sw, options=build_power_flow_options())
    switched_model = get_switched_emt_converter(vf=grid_sw.var_factory, name="switched_converter_emt").block
    apply_common_converter_tuning(converter_model=switched_model, model_name="switched_converter_emt", l_eq_value=COMPARISON_L_EQ)
    attach_common_device_models(
        grid=grid_sw,
        generator=generator_sw,
        converter=converter_sw,
        dc_load=dc_load_sw,
        converter_model=switched_model,
        dc_load_model_name="dc_load_emt_switched",
    )
    switched_artifacts = run_case(
        problem=build_problem(grid=grid_sw, pf_results=pf_results_sw, options=options),
        model_name="switched_converter_emt",
    )
    switched_diag = compute_case_tail_means(switched_artifacts)

    grid_ps, bus_ac_ps, bus_dc_ps, generator_ps, converter_ps, dc_load_ps = build_reference_grid()
    attach_common_bus_models(grid_ps)
    pf_results_ps = gce.power_flow(grid=grid_ps, options=build_power_flow_options())
    pseudo_model = get_full_pseudo_emt_converter(vf=grid_ps.var_factory, name="pseudo_converter_emt").block
    apply_common_converter_tuning(converter_model=pseudo_model, model_name="pseudo_converter_emt", l_eq_value=COMPARISON_L_EQ)
    attach_common_device_models(
        grid=grid_ps,
        generator=generator_ps,
        converter=converter_ps,
        dc_load=dc_load_ps,
        converter_model=pseudo_model,
        dc_load_model_name="dc_load_emt_pseudo_compare",
    )
    pseudo_artifacts = run_case(
        problem=build_problem(grid=grid_ps, pf_results=pf_results_ps, options=options),
        model_name="pseudo_converter_emt",
    )
    pseudo_diag = compute_case_tail_means(pseudo_artifacts)

    print_qaxis_sign_convention_note()
    print_qaxis_comparison(
        switched_diag=switched_diag,
        pseudo_diag=pseudo_diag,
        title="Q-AXIS BLOCK-BY-BLOCK COMPARISON (RAW SWITCHED CONVENTION)",
    )
    print_qaxis_comparison(
        switched_diag=build_pseudo_convention_diagnostic_view(switched_diag=switched_diag),
        pseudo_diag=pseudo_diag,
        title="Q-AXIS BLOCK-BY-BLOCK COMPARISON (PSEUDO-EQUIVALENT SWITCHED VIEW)",
    )
    print_daxis_comparison(switched_diag=switched_diag, pseudo_diag=pseudo_diag)

    switched_signals = build_named_signal_traces(switched_artifacts)
    pseudo_signals = build_named_signal_traces(pseudo_artifacts)
    switched_signals_pseudo_view = build_pseudo_convention_trace_view(switched_signals=switched_signals)

    for display_name in switched_signals.keys():
        qaxis_metrics_by_signal[display_name] = compute_trace_metrics(
            time_arr=switched_artifacts.time_arr,
            switched_arr=switched_signals[display_name],
            pseudo_arr=pseudo_signals[display_name],
            analysis_start_s=COMPARISON_ANALYSIS_START_S,
            threshold=COMPARISON_DIVERGENCE_THRESHOLD,
        )

    print_trace_metrics(metrics_by_signal=qaxis_metrics_by_signal, title="Q-AXIS TEMPORAL DIVERGENCE")
    qaxis_metrics_by_signal_pseudo_view: dict[str, dict[str, float]] = dict()

    for display_name in switched_signals_pseudo_view.keys():
        qaxis_metrics_by_signal_pseudo_view[display_name] = compute_trace_metrics(
            time_arr=switched_artifacts.time_arr,
            switched_arr=switched_signals_pseudo_view[display_name],
            pseudo_arr=pseudo_signals[display_name],
            analysis_start_s=COMPARISON_ANALYSIS_START_S,
            threshold=COMPARISON_DIVERGENCE_THRESHOLD,
        )

    print_trace_metrics(
        metrics_by_signal=qaxis_metrics_by_signal_pseudo_view,
        title="Q-AXIS TEMPORAL DIVERGENCE (PSEUDO-EQUIVALENT SWITCHED VIEW)",
    )

    pseudo_view_save_path = get_plot_output_path(file_name="switched_converter_qaxis_trace_compare_pseudo_view.png")
    plot_trace_comparison(
        time_arr=switched_artifacts.time_arr,
        switched_signals=switched_signals_pseudo_view,
        pseudo_signals=pseudo_signals,
        save_path=pseudo_view_save_path,
        plot_title="Switched vs pseudo EMT q-axis comparison (pseudo-equivalent switched view)",
    )
    print(f"Plot saved to: {pseudo_view_save_path}")

    switched_daxis_signals = build_daxis_bridge_traces(switched_artifacts)
    pseudo_daxis_signals = build_daxis_bridge_traces(pseudo_artifacts)

    for display_name in build_daxis_bridge_trace_names():
        daxis_metrics_by_signal[display_name] = compute_trace_metrics(
            time_arr=switched_artifacts.time_arr,
            switched_arr=switched_daxis_signals[display_name],
            pseudo_arr=pseudo_daxis_signals[display_name],
            analysis_start_s=COMPARISON_ANALYSIS_START_S,
            threshold=COMPARISON_DIVERGENCE_THRESHOLD,
        )

    print_trace_metrics(metrics_by_signal=daxis_metrics_by_signal, title="D-AXIS / BRIDGE TEMPORAL DIVERGENCE")

    interval_mid_arr, interval_signals, interval_metadata = compute_interval_averaged_bridge_comparison(
        switched_artifacts=switched_artifacts,
        pseudo_artifacts=pseudo_artifacts,
    )
    print_interval_averaged_bridge_comparison(
        interval_mid_arr=interval_mid_arr,
        interval_signals=interval_signals,
        metadata=interval_metadata,
    )
    interval_signals_pseudo_view = build_pseudo_convention_interval_view(interval_signals=interval_signals)
    print_interval_averaged_bridge_comparison(
        interval_mid_arr=interval_mid_arr,
        interval_signals=interval_signals_pseudo_view,
        metadata=interval_metadata,
    )

    interval_pseudo_view_save_path = get_plot_output_path(file_name="switched_converter_bridge_interval_average_compare_pseudo_view.png")
    plot_interval_averaged_bridge_comparison(
        interval_mid_arr=interval_mid_arr,
        interval_signals=interval_signals_pseudo_view,
        save_path=interval_pseudo_view_save_path,
        plot_title="Interval-averaged switched bridge voltage versus held sampled phase reference (pseudo-equivalent switched view)",
    )
    print(f"Plot saved to: {interval_pseudo_view_save_path}")


if __name__ == "__main__":
    main()
