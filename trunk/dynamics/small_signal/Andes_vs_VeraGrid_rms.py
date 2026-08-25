# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Compare ANDES and VeraGrid RMS time-domain trajectories and timings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from matplotlib import pyplot as plt
import numpy as np
import pandas as pd

from trunk.dynamics.small_signal.Andes_vs_VeraGrid_stability import map_simple_veragrid_labels
from trunk.dynamics.small_signal.Andes_vs_VeraGrid_stability import map_veragrid_labels_to_andes_style
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import case_label
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import engine_results_directory
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkCase
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkScenario


class ErrorMetrics:
    """Aggregate error measures for one trajectory region."""

    __slots__ = ("maximum_absolute", "mean_absolute", "root_mean_square", "normalized_root_mean_square")

    def __init__(
        self: ErrorMetrics,
        reference: np.ndarray,
        candidate: np.ndarray,
    ) -> None:
        """Calculate absolute and scale-normalized trajectory errors.

        :param reference: ANDES reference values.
        :param candidate: VeraGrid candidate values.
        :return: None.
        """
        difference: np.ndarray = np.asarray(candidate, dtype=float) - np.asarray(reference, dtype=float)
        absolute_difference: np.ndarray = np.abs(difference)
        self.maximum_absolute: float = float(np.max(absolute_difference))
        self.mean_absolute: float = float(np.mean(absolute_difference))
        self.root_mean_square: float = float(np.sqrt(np.mean(difference * difference)))
        reference_scale: float = max(float(np.sqrt(np.mean(reference * reference))), 1.0e-15)
        self.normalized_root_mean_square: float = self.root_mean_square / reference_scale


def comparison_directory(
    case_tpe: RmsBenchmarkCase,
    scenario_tpe: RmsBenchmarkScenario = RmsBenchmarkScenario.BASE,
) -> Path:
    """Return the persistent RMS comparison directory for one case.

    :param case_tpe: Selected benchmark case.
    :param scenario_tpe: Base or rotor-speed state-step dynamic scenario.
    :return: Absolute comparison directory.
    """
    script_directory: Path = Path(__file__).resolve().parent
    if scenario_tpe is RmsBenchmarkScenario.BASE:
        scenario_suffix: str = ""
    else:
        scenario_suffix = "_event"
    return script_directory / f"{case_label(case_tpe)}_rms_dynamic{scenario_suffix}_Andes_vs_VeraGrid"


def format_report_float(value: float) -> str:
    """Format one floating-point table value for the text report.

    :param value: Numeric table value.
    :return: Scientific-notation text.
    """
    return f"{value:.6e}"


def load_key_value_table(input_path: Path) -> dict[str, str]:
    """Load one two-column metadata or timing CSV as strings.

    :param input_path: Source CSV file.
    :return: Metric-to-value map.
    """
    frame: pd.DataFrame = pd.read_csv(input_path, dtype=str)
    values: dict[str, str] = dict()
    row_index: int
    for row_index in range(frame.shape[0]):
        values[str(frame.iloc[row_index, 0])] = str(frame.iloc[row_index, 1])
    return values


def validate_numerical_configuration(
    andes_metadata: dict[str, str],
    veragrid_metadata: dict[str, str],
) -> list[str]:
    """Validate solver, fixed-step grid and horizon before comparing results.

    :param andes_metadata: ANDES metadata values.
    :param veragrid_metadata: VeraGrid metadata values.
    :return: Human-readable validation messages.
    """
    messages: list[str] = list()
    exact_keys: tuple[str, ...] = (
        "solver",
        "fixed_step",
        "adaptive_step_reduction",
        "sample_count",
        "perturbed_state",
    )
    if andes_metadata.get("scenario", None) is not None:
        exact_keys = exact_keys + (
            "scenario",
            "event_type",
        )
        if andes_metadata.get("event_type", "base") != RmsBenchmarkScenario.BASE.value:
            exact_keys = exact_keys + ("event_target_state",)
        else:
            pass
    else:
        pass
    exact_key: str
    for exact_key in exact_keys:
        andes_value: str | None = andes_metadata.get(exact_key, None)
        veragrid_value: str | None = veragrid_metadata.get(exact_key, None)
        if andes_value == veragrid_value and andes_value is not None:
            messages.append(f"PASS {exact_key}: {andes_value}")
        else:
            raise ValueError(
                f"Numerical configuration mismatch for {exact_key}: "
                f"ANDES={andes_value}, VeraGrid={veragrid_value}."
            )

    numeric_keys: tuple[str, ...] = (
        "time_step_s",
        "simulation_time_s",
        "integration_tolerance",
        "speed_perturbation_pu",
    )
    if andes_metadata.get("event_type", "base") != RmsBenchmarkScenario.BASE.value:
        numeric_keys = numeric_keys + (
            "event_time_s",
            "event_state_step_pu",
        )
    else:
        pass
    numeric_key: str
    for numeric_key in numeric_keys:
        andes_numeric: float = float(andes_metadata[numeric_key])
        veragrid_numeric: float = float(veragrid_metadata[numeric_key])
        if bool(np.isclose(andes_numeric, veragrid_numeric, rtol=0.0, atol=1.0e-15)):
            messages.append(f"PASS {numeric_key}: {andes_numeric:.12e}")
        else:
            raise ValueError(
                f"Numerical configuration mismatch for {numeric_key}: "
                f"ANDES={andes_numeric:.12e}, VeraGrid={veragrid_numeric:.12e}."
            )
    return messages


def align_state_trajectories(
    andes_frame: pd.DataFrame,
    veragrid_frame: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str], list[str]]:
    """Align timestamps and common physical state columns between both tools.

    :param andes_frame: ANDES state trajectory table.
    :param veragrid_frame: VeraGrid state trajectory table.
    :return: Time, ANDES values, VeraGrid values, matched labels and unmatched labels.
    """
    andes_time: np.ndarray = andes_frame["time_s"].to_numpy(dtype=float)
    veragrid_time: np.ndarray = veragrid_frame["time_s"].to_numpy(dtype=float)
    if andes_time.shape == veragrid_time.shape and bool(
        np.allclose(andes_time, veragrid_time, rtol=0.0, atol=1.0e-12)
    ):
        pass
    else:
        raise ValueError("ANDES and VeraGrid do not use the same stored time grid.")

    andes_labels: list[str] = list(str(label) for label in andes_frame.columns[1:])
    veragrid_labels: list[str] = list(str(label) for label in veragrid_frame.columns[1:])
    converted_labels: list[str] = map_veragrid_labels_to_andes_style(veragrid_labels)
    mapped_labels: list[str] = map_simple_veragrid_labels(converted_labels, andes_labels)
    andes_index_by_label: dict[str, int] = dict()
    andes_index: int
    for andes_index in range(len(andes_labels)):
        andes_index_by_label[andes_labels[andes_index]] = andes_index

    matched_andes_indexes: list[int] = list()
    matched_veragrid_indexes: list[int] = list()
    matched_labels: list[str] = list()
    unmatched_veragrid: list[str] = list()
    veragrid_index: int
    for veragrid_index in range(len(mapped_labels)):
        mapped_label: str = mapped_labels[veragrid_index]
        source_index: int | None = andes_index_by_label.get(mapped_label, None)
        if source_index is None:
            unmatched_veragrid.append(veragrid_labels[veragrid_index])
        else:
            matched_andes_indexes.append(source_index)
            matched_veragrid_indexes.append(veragrid_index)
            matched_labels.append(mapped_label)
    if len(matched_labels) > 0:
        pass
    else:
        raise ValueError("No common physical RMS states could be aligned.")

    matched_label_set: set[str] = set(matched_labels)
    unmatched_andes: list[str] = list()
    andes_label: str
    for andes_label in andes_labels:
        if andes_label in matched_label_set:
            pass
        else:
            unmatched_andes.append(andes_label)

    andes_values: np.ndarray = andes_frame.iloc[:, 1:].to_numpy(dtype=float)[
        :, np.asarray(matched_andes_indexes, dtype=int)
    ]
    veragrid_values: np.ndarray = veragrid_frame.iloc[:, 1:].to_numpy(dtype=float)[
        :, np.asarray(matched_veragrid_indexes, dtype=int)
    ]
    return andes_time, andes_values, veragrid_values, matched_labels, unmatched_andes, unmatched_veragrid


def calculate_segment_rows(
    time_values: np.ndarray,
    andes_values: np.ndarray,
    veragrid_values: np.ndarray,
) -> list[tuple[str, float, float, float, float, float, int]]:
    """Calculate total and four non-overlapping equal-duration error segments.

    :param time_values: Shared timestamps.
    :param andes_values: Aligned ANDES states.
    :param veragrid_values: Aligned VeraGrid states.
    :return: Segment rows with bounds, metrics and sample counts.
    """
    rows: list[tuple[str, float, float, float, float, float, int]] = list()
    total_metrics: ErrorMetrics = ErrorMetrics(andes_values, veragrid_values)
    rows.append((
        "TOTAL",
        float(time_values[0]),
        float(time_values[-1]),
        total_metrics.maximum_absolute,
        total_metrics.mean_absolute,
        total_metrics.root_mean_square,
        int(time_values.size),
    ))

    boundaries: np.ndarray = np.linspace(float(time_values[0]), float(time_values[-1]), 5)
    segment_index: int
    for segment_index in range(4):
        start_time: float = float(boundaries[segment_index])
        end_time: float = float(boundaries[segment_index + 1])
        if segment_index < 3:
            mask: np.ndarray = (time_values >= start_time) & (time_values < end_time)
        else:
            mask = (time_values >= start_time) & (time_values <= end_time)
        segment_metrics: ErrorMetrics = ErrorMetrics(andes_values[mask, :], veragrid_values[mask, :])
        rows.append((
            f"SEGMENT_{segment_index + 1}",
            start_time,
            end_time,
            segment_metrics.maximum_absolute,
            segment_metrics.mean_absolute,
            segment_metrics.root_mean_square,
            int(np.count_nonzero(mask)),
        ))
    return rows


def align_rotor_angle_reference(
    labels: list[str],
    andes_values: np.ndarray,
    veragrid_values: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Remove the single physically arbitrary rotor-angle reference offset.

    :param labels: Common state labels.
    :param andes_values: Aligned ANDES state trajectories.
    :param veragrid_values: Aligned VeraGrid state trajectories.
    :return: Reference-aligned VeraGrid values and applied offset in radians.
    """
    delta_indexes: list[int] = list()
    label_index: int
    for label_index in range(len(labels)):
        if labels[label_index].startswith("delta "):
            delta_indexes.append(label_index)
        else:
            pass
    corrected_values: np.ndarray = np.asarray(veragrid_values, dtype=float).copy()
    if len(delta_indexes) > 0:
        initial_offsets: np.ndarray = (
            corrected_values[0, np.asarray(delta_indexes, dtype=int)]
            - andes_values[0, np.asarray(delta_indexes, dtype=int)]
        )
        angle_offset: float = float(np.median(initial_offsets))
        corrected_values[:, np.asarray(delta_indexes, dtype=int)] -= angle_offset
    else:
        angle_offset = 0.0
    return corrected_values, angle_offset


def calculate_per_state_frame(
    labels: list[str],
    time_values: np.ndarray,
    andes_values: np.ndarray,
    veragrid_values: np.ndarray,
) -> pd.DataFrame:
    """Calculate full-horizon numerical errors for every matched state.

    :param labels: Common state labels.
    :param time_values: Shared time grid.
    :param andes_values: Aligned ANDES states.
    :param veragrid_values: Aligned VeraGrid states.
    :return: Per-state error table sorted by maximum error.
    """
    records: list[dict[str, Any]] = list()
    state_index: int
    for state_index in range(len(labels)):
        metrics: ErrorMetrics = ErrorMetrics(
            andes_values[:, state_index],
            veragrid_values[:, state_index],
        )
        record: dict[str, Any] = dict()
        record["state"] = labels[state_index]
        record["max_abs_error"] = metrics.maximum_absolute
        record["mean_abs_error"] = metrics.mean_absolute
        record["rmse"] = metrics.root_mean_square
        record["normalized_rmse"] = metrics.normalized_root_mean_square
        absolute_error: np.ndarray = np.abs(
            veragrid_values[:, state_index] - andes_values[:, state_index]
        )
        peak_index: int = int(np.argmax(absolute_error))
        record["initial_abs_error"] = float(absolute_error[0])
        record["final_abs_error"] = float(absolute_error[-1])
        record["peak_error_time_s"] = float(time_values[peak_index])
        records.append(record)
    frame: pd.DataFrame = pd.DataFrame(records)
    return frame.sort_values("max_abs_error", ascending=False, ignore_index=True)


def parse_optional_timing(timings: dict[str, str], metric_name: str) -> float | None:
    """Parse one timing value while retaining explicit unavailable phases.

    :param timings: Timing key-value map.
    :param metric_name: Requested timing metric.
    :return: Timing in seconds or ``None`` when not exposed.
    """
    raw_value: str | None = timings.get(metric_name, None)
    if raw_value is None or raw_value.startswith("N/A"):
        value: float | None = None
    else:
        value = float(raw_value)
    return value


def build_timing_comparison(
    andes_timings: dict[str, str],
    veragrid_timings: dict[str, str],
) -> pd.DataFrame:
    """Build a phase-by-phase timing table with faster-tool factors.

    :param andes_timings: ANDES timing values.
    :param veragrid_timings: VeraGrid timing values.
    :return: Comparable timing table.
    """
    phase_specs: tuple[tuple[str, tuple[str, ...], tuple[str, ...], str], ...] = (
        (
            "Case/model build and pre-PF setup",
            ("case_and_model_build_s", "andes_system_setup_s"),
            ("case_and_model_build_s",),
            "ANDES import+setup versus VeraGrid MultiCircuit+RMS model construction",
        ),
        (
            "Cold power flow (excluded)",
            ("power_flow_cold_excluded_s",),
            ("power_flow_cold_excluded_s",),
            "Warm-up diagnostic only; excluded from the analyzed total",
        ),
        (
            "Warm power flow (analyzed)",
            ("power_flow_warm_analyzed_s",),
            ("power_flow_warm_analyzed_s",),
            "Second Newton solve; its solution initializes RMS",
        ),
        (
            "Dynamic initialization and symbolic-to-numeric",
            ("dynamic_initialization_and_symbolic_numeric_s",),
            ("dynamic_initialization_and_symbolic_numeric_s", "solver_setup_s"),
            "DAE initialization plus solver allocation before the first step",
        ),
        (
            "RMS integration",
            ("rms_integration_s",),
            ("rms_integration_s",),
            "All fixed Backward Euler steps over the common horizon",
        ),
        (
            "Analyzed benchmark total",
            ("benchmark_total_analyzed_s",),
            ("benchmark_total_analyzed_s",),
            "Build/setup + warm PF + dynamic initialization + integration",
        ),
    )
    records: list[dict[str, Any]] = list()
    phase_spec: tuple[str, tuple[str, ...], tuple[str, ...], str]
    for phase_spec in phase_specs:
        andes_seconds: float = 0.0
        veragrid_seconds: float = 0.0
        andes_available: bool = True
        veragrid_available: bool = True
        metric_name: str
        for metric_name in phase_spec[1]:
            andes_value: float | None = parse_optional_timing(andes_timings, metric_name)
            if andes_value is None:
                andes_available = False
            else:
                andes_seconds += andes_value
        for metric_name in phase_spec[2]:
            veragrid_value: float | None = parse_optional_timing(veragrid_timings, metric_name)
            if veragrid_value is None:
                veragrid_available = False
            else:
                veragrid_seconds += veragrid_value

        if andes_available and veragrid_available and andes_seconds > 0.0 and veragrid_seconds > 0.0:
            if andes_seconds < veragrid_seconds:
                faster_engine: str = "ANDES"
                speed_factor: float = veragrid_seconds / andes_seconds
            else:
                faster_engine = "VeraGrid"
                speed_factor = andes_seconds / veragrid_seconds
        else:
            faster_engine = "N/A"
            speed_factor = np.nan
        record: dict[str, Any] = dict()
        record["phase"] = phase_spec[0]
        record["what_it_contains"] = phase_spec[3]
        record["andes_s"] = andes_seconds if andes_available else np.nan
        record["veragrid_s"] = veragrid_seconds if veragrid_available else np.nan
        record["faster_engine"] = faster_engine
        record["speed_factor_x"] = speed_factor
        record["included_in_analyzed_total"] = phase_spec[0] not in (
            "Cold power flow (excluded)",
            "Analyzed benchmark total",
        )
        if phase_spec[0] == "Cold power flow (excluded)":
            timing_role: str = "EXCLUDED COMPONENT"
        elif phase_spec[0] == "Analyzed benchmark total":
            timing_role = "ANALYZED TOTAL (sum, not an extra component)"
        else:
            timing_role = "INCLUDED COMPONENT"
        record["timing_role"] = timing_role
        records.append(record)
    return pd.DataFrame(records)


def save_comparison_figures(
    output_directory: Path,
    time_values: np.ndarray,
    andes_values: np.ndarray,
    veragrid_values: np.ndarray,
    segment_frame: pd.DataFrame,
    timing_frame: pd.DataFrame,
    labels: list[str],
    event_time: float | None,
    show_figures: bool,
) -> None:
    """Save trajectory-error and timing figures for human inspection.

    :param output_directory: Comparison result directory.
    :param time_values: Shared timestamps.
    :param andes_values: Aligned ANDES state values.
    :param veragrid_values: Aligned VeraGrid state values.
    :param segment_frame: Total and segment error table.
    :param timing_frame: Phase timing table.
    :param labels: Physical state labels aligned with both trajectories.
    :param event_time: Optional event time drawn on trajectory figures.
    :param show_figures: Display figures after saving them.
    :return: None.
    """
    absolute_error: np.ndarray = np.abs(veragrid_values - andes_values)
    error_envelope: np.ndarray = np.max(absolute_error, axis=1)
    error_rms: np.ndarray = np.sqrt(np.mean(absolute_error * absolute_error, axis=1))
    trajectory_figure: Any
    trajectory_axis: Any
    trajectory_figure, trajectory_axis = plt.subplots(figsize=(10.0, 5.0))
    trajectory_axis.plot(time_values, error_envelope, label="Maximum absolute state error")
    trajectory_axis.plot(time_values, error_rms, label="RMS state error")
    trajectory_axis.set_xlabel("Time [s]")
    trajectory_axis.set_ylabel("Absolute error")
    trajectory_axis.set_title("ANDES versus VeraGrid RMS trajectory error")
    trajectory_axis.grid(True, alpha=0.3)
    trajectory_axis.legend()
    trajectory_figure.tight_layout()
    trajectory_figure.savefig(output_directory / "trajectory_error_over_time.png", dpi=180)

    segment_only: pd.DataFrame = segment_frame.iloc[1:, :]
    segment_figure: Any
    segment_axis: Any
    segment_figure, segment_axis = plt.subplots(figsize=(9.0, 5.0))
    segment_positions: np.ndarray = np.arange(segment_only.shape[0], dtype=float)
    segment_axis.bar(segment_positions - 0.18, segment_only["max_abs_error"], width=0.36, label="Max abs")
    segment_axis.bar(segment_positions + 0.18, segment_only["rmse"], width=0.36, label="RMSE")
    segment_axis.set_xticks(segment_positions, list(segment_only["segment"]))
    segment_axis.set_ylabel("Error")
    segment_axis.set_title("Numerical error by time segment")
    segment_axis.grid(True, axis="y", alpha=0.3)
    segment_axis.legend()
    segment_figure.tight_layout()
    segment_figure.savefig(output_directory / "segment_error_comparison.png", dpi=180)

    timing_plot_frame: pd.DataFrame = timing_frame.dropna(subset=list(("andes_s", "veragrid_s")))
    timing_figure: Any
    timing_axis: Any
    timing_figure, timing_axis = plt.subplots(figsize=(11.0, 6.0))
    timing_positions: np.ndarray = np.arange(timing_plot_frame.shape[0], dtype=float)
    timing_axis.barh(timing_positions - 0.18, timing_plot_frame["andes_s"], height=0.36, label="ANDES")
    timing_axis.barh(timing_positions + 0.18, timing_plot_frame["veragrid_s"], height=0.36, label="VeraGrid")
    timing_axis.set_yticks(timing_positions, list(timing_plot_frame["phase"]))
    timing_axis.set_xscale("log")
    timing_axis.set_xlabel("Wall-clock time [s], logarithmic scale")
    timing_axis.set_title("RMS benchmark timing by phase")
    timing_axis.grid(True, axis="x", alpha=0.3)
    timing_axis.legend()
    timing_figure.tight_layout()
    timing_figure.savefig(output_directory / "timing_comparison.png", dpi=180)

    # The numerical envelope can hide which physical models dominate. Plot the
    # four largest-error states directly so initialization offsets, divergence
    # and post-event response can be distinguished by eye.
    state_error: np.ndarray = np.max(np.abs(veragrid_values - andes_values), axis=0)
    interesting_count: int = min(4, len(labels))
    interesting_indexes: np.ndarray = np.argsort(state_error)[-interesting_count:][::-1]
    state_figure: Any
    state_axes: Any
    state_figure, state_axes = plt.subplots(
        interesting_count,
        1,
        figsize=(11.0, 2.8 * interesting_count),
        sharex=True,
        squeeze=False,
    )
    plot_position: int
    for plot_position in range(interesting_count):
        state_index: int = int(interesting_indexes[plot_position])
        state_axis: Any = state_axes[plot_position, 0]
        state_axis.plot(time_values, andes_values[:, state_index], label="ANDES", linewidth=1.4)
        state_axis.plot(
            time_values,
            veragrid_values[:, state_index],
            label="VeraGrid",
            linewidth=1.1,
            linestyle="--",
        )
        if event_time is not None:
            state_axis.axvline(event_time, color="black", linewidth=0.8, linestyle=":", label="Event")
        else:
            pass
        state_axis.set_ylabel(labels[state_index])
        state_axis.grid(True, alpha=0.3)
        if plot_position == 0:
            state_axis.legend(loc="best")
        else:
            pass
    state_axes[interesting_count - 1, 0].set_xlabel("Time [s]")
    state_figure.suptitle("Representative physical state trajectories")
    state_figure.tight_layout()
    state_figure.savefig(output_directory / "representative_state_trajectories.png", dpi=180)

    if show_figures:
        plt.show()
    else:
        plt.close("all")


def build_text_report(
    case_tpe: RmsBenchmarkCase,
    scenario_tpe: RmsBenchmarkScenario,
    validation_messages: list[str],
    matched_labels: list[str],
    unmatched_andes: list[str],
    unmatched_veragrid: list[str],
    segment_frame: pd.DataFrame,
    per_state_frame: pd.DataFrame,
    timing_frame: pd.DataFrame,
    angle_offset_rad: float,
) -> str:
    """Build the persistent human-readable RMS comparison report.

    :param case_tpe: Compared case.
    :param scenario_tpe: Base or rotor-speed event scenario.
    :param validation_messages: Numerical configuration checks.
    :param matched_labels: Common state labels.
    :param unmatched_andes: ANDES-only states.
    :param unmatched_veragrid: VeraGrid-only states.
    :param segment_frame: Error metrics by horizon segment.
    :param per_state_frame: Error metrics for every common physical state.
    :param timing_frame: Timing comparison by workflow phase.
    :param angle_offset_rad: Common rotor-angle reference removed from VeraGrid.
    :return: Complete report text.
    """
    lines: list[str] = list()
    lines.append(f"RMS DYNAMIC BENCHMARK: {case_label(case_tpe)} [{scenario_tpe.value}]")
    lines.append("=" * 78)
    lines.append("")
    lines.append("NUMERICAL CONFIGURATION VALIDATION")
    lines.extend(validation_messages)
    lines.append("")
    lines.append("POWER-FLOW POLICY")
    lines.append("Both tools run power flow twice. The first cold solve is reported but excluded.")
    lines.append("Only the second warm solution initializes RMS and enters the analyzed total.")
    lines.append("")
    lines.append("STATE ALIGNMENT")
    lines.append(f"Common physical states compared: {len(matched_labels)}")
    lines.append(f"Rotor-angle gauge offset removed from VeraGrid delta states: {angle_offset_rad:.12e} rad")
    lines.append(f"ANDES-only implementation/measurement states: {len(unmatched_andes)}")
    lines.append(f"VeraGrid-only or unmapped states: {len(unmatched_veragrid)}")
    if len(unmatched_andes) > 0:
        lines.append("ANDES-only states: " + ", ".join(unmatched_andes))
    else:
        lines.append("ANDES-only states: none")
    if len(unmatched_veragrid) > 0:
        lines.append("VeraGrid-only/unmapped states: " + ", ".join(unmatched_veragrid))
    else:
        lines.append("VeraGrid-only/unmapped states: none")
    lines.append("")
    lines.append("NUMERICAL RESULTS: TOTAL AND FOUR EQUAL TIME SEGMENTS")
    lines.append(segment_frame.to_string(index=False, float_format=format_report_float))
    lines.append("")
    lines.append("FIVE PHYSICAL STATES WITH THE LARGEST ABSOLUTE DIFFERENCE")
    lines.append(per_state_frame.iloc[:5, :].to_string(index=False, float_format=format_report_float))
    lines.append("")
    lines.append("TIMING COMPARISON BY PHASE")
    lines.append(timing_frame.to_string(index=False, float_format=format_report_float))
    lines.append("")
    lines.append("INTERPRETATION")
    lines.append("The analyzed total includes build/setup, the second warm PF, dynamic initialization,")
    lines.append("solver allocation and RMS integration. It excludes the cold PF and result export.")
    lines.append("Internal RHS/Jacobian/linear-solver timings are exported only for VeraGrid because")
    lines.append("ANDES 2.0 does not expose equivalent phase accumulators without instrumenting its engine.")
    return "\n".join(lines) + "\n"


def compare_rms_case(
    case_tpe: RmsBenchmarkCase,
    show_figures: bool = True,
    scenario_tpe: RmsBenchmarkScenario = RmsBenchmarkScenario.BASE,
) -> None:
    """Compare one already-generated ANDES/VeraGrid RMS result pair.

    :param case_tpe: Benchmark case to compare.
    :param show_figures: Display figures as well as saving them.
    :param scenario_tpe: Base or rotor-speed state-step scenario to compare.
    :return: None.
    """
    andes_directory: Path = engine_results_directory(case_tpe, "Andes", scenario_tpe)
    veragrid_directory: Path = engine_results_directory(case_tpe, "VeraGrid", scenario_tpe)
    output_directory: Path = comparison_directory(case_tpe, scenario_tpe)
    output_directory.mkdir(parents=True, exist_ok=True)

    andes_metadata: dict[str, str] = load_key_value_table(andes_directory / "metadata.csv")
    veragrid_metadata: dict[str, str] = load_key_value_table(veragrid_directory / "metadata.csv")
    validation_messages: list[str] = validate_numerical_configuration(
        andes_metadata=andes_metadata,
        veragrid_metadata=veragrid_metadata,
    )
    andes_frame: pd.DataFrame = pd.read_csv(andes_directory / "state_trajectory.csv")
    veragrid_frame: pd.DataFrame = pd.read_csv(veragrid_directory / "state_trajectory.csv")
    alignment_output: tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str], list[str]] = (
        align_state_trajectories(andes_frame=andes_frame, veragrid_frame=veragrid_frame)
    )
    time_values: np.ndarray = alignment_output[0]
    andes_values: np.ndarray = alignment_output[1]
    veragrid_values: np.ndarray = alignment_output[2]
    matched_labels: list[str] = alignment_output[3]
    unmatched_andes: list[str] = alignment_output[4]
    unmatched_veragrid: list[str] = alignment_output[5]
    angle_offset_rad: float
    veragrid_values, angle_offset_rad = align_rotor_angle_reference(
        labels=matched_labels,
        andes_values=andes_values,
        veragrid_values=veragrid_values,
    )

    segment_rows: list[tuple[str, float, float, float, float, float, int]] = calculate_segment_rows(
        time_values=time_values,
        andes_values=andes_values,
        veragrid_values=veragrid_values,
    )
    segment_frame: pd.DataFrame = pd.DataFrame(
        segment_rows,
        columns=list((
            "segment",
            "start_s",
            "end_s",
            "max_abs_error",
            "mean_abs_error",
            "rmse",
            "sample_count",
        )),
    )
    per_state_frame: pd.DataFrame = calculate_per_state_frame(
        labels=matched_labels,
        time_values=time_values,
        andes_values=andes_values,
        veragrid_values=veragrid_values,
    )
    andes_timings: dict[str, str] = load_key_value_table(andes_directory / "timings.csv")
    veragrid_timings: dict[str, str] = load_key_value_table(veragrid_directory / "timings.csv")
    timing_frame: pd.DataFrame = build_timing_comparison(andes_timings, veragrid_timings)

    segment_frame.to_csv(output_directory / "segment_error_metrics.csv", index=False, float_format="%.12e")
    per_state_frame.to_csv(output_directory / "per_state_error_metrics.csv", index=False, float_format="%.12e")
    timing_frame.to_csv(output_directory / "timing_comparison.csv", index=False, float_format="%.12e")
    report_text: str = build_text_report(
        case_tpe=case_tpe,
        scenario_tpe=scenario_tpe,
        validation_messages=validation_messages,
        matched_labels=matched_labels,
        unmatched_andes=unmatched_andes,
        unmatched_veragrid=unmatched_veragrid,
        segment_frame=segment_frame,
        per_state_frame=per_state_frame,
        timing_frame=timing_frame,
        angle_offset_rad=angle_offset_rad,
    )
    (output_directory / "comparison_report.txt").write_text(report_text, encoding="utf-8")
    print(report_text)
    if scenario_tpe is RmsBenchmarkScenario.ROTOR_SPEED_STATE_STEP:
        event_time: float | None = float(andes_metadata["event_time_s"])
    else:
        event_time = None
    save_comparison_figures(
        output_directory=output_directory,
        time_values=time_values,
        andes_values=andes_values,
        veragrid_values=veragrid_values,
        segment_frame=segment_frame,
        timing_frame=timing_frame,
        labels=matched_labels,
        event_time=event_time,
        show_figures=show_figures,
    )


def main() -> None:
    """Select one case and compare it directly with the PyCharm Run button.

    Change only the uncommented ``selected_case`` line after generating both
    engine result folders.

    :return: None.
    """
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.KUNDUR
    selected_case: RmsBenchmarkCase = RmsBenchmarkCase.IEEE14
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.IEEE39
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.NPCC140
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.WECC179
    compare_rms_case(case_tpe=selected_case, show_figures=True)


if __name__ == "__main__":
    main()
else:
    pass
