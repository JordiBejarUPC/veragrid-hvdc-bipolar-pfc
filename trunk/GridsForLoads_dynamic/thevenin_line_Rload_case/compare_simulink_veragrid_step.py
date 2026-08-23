from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import compare_simulink_veragrid as base_comparison


def get_required_simulink_columns() -> tuple[str, ...]:
    """
    Return the Simulink channels required by the validated model mapping.

    :return: Required Simulink CSV column names.
    :rtype: tuple[str, ...]
    """
    return (
        "time_s", "Vac_grid_pu", "omega_grid_pu",
        "phase_a_pu", "phase_b_pu", "phase_c_pu",
        "Vac_bus0_a_pu", "Vac_bus0_b_pu", "Vac_bus0_c_pu",
        "Iac_bus0_a_pu", "Iac_bus0_b_pu", "Iac_bus0_c_pu",
        "Iac_ser_line_a_pu", "Iac_ser_line_b_pu", "Iac_ser_line_c_pu",
        "Iac_cap_from_line_a_pu", "Iac_cap_from_line_b_pu",
        "Iac_cap_from_line_c_pu",
        "Vac_bus1_a_pu", "Vac_bus1_b_pu", "Vac_bus1_c_pu",
        "Iac_bus1_a_pu", "Iac_bus1_b_pu", "Iac_bus1_c_pu",
        "Iac_cap_to_line_a_pu", "Iac_cap_to_line_b_pu",
        "Iac_cap_to_line_c_pu",
    )


def get_required_veragrid_columns() -> tuple[str, ...]:
    """
    Return the VeraGrid channels required by the validated model mapping.

    :return: Required VeraGrid CSV column names.
    :rtype: tuple[str, ...]
    """
    return (
        "time_s", "theta_gen@Bus 1_pu", "Pe_gen@Bus 1_pu",
        "Qe_gen@Bus 1_pu",
        "e_A_gen@Bus 1_pu", "e_B_gen@Bus 1_pu", "e_C_gen@Bus 1_pu",
        "i_A_gen@Bus 1_pu", "i_B_gen@Bus 1_pu", "i_C_gen@Bus 1_pu",
        "i_A_Load@Bus 0_pu", "i_B_Load@Bus 0_pu",
        "i_C_Load@Bus 0_pu",
        "v_A_Bus 0_pu", "v_B_Bus 0_pu", "v_C_Bus 0_pu",
        "v_A_Bus 1_pu", "v_B_Bus 1_pu", "v_C_Bus 1_pu",
        "q_f_A_Line 1_pu", "q_f_B_Line 1_pu", "q_f_C_Line 1_pu",
        "q_t_A_Line 1_pu", "q_t_B_Line 1_pu", "q_t_C_Line 1_pu",
        "i_cap_f_A_Line 1_pu", "i_cap_f_B_Line 1_pu",
        "i_cap_f_C_Line 1_pu",
        "i_cap_t_A_Line 1_pu", "i_cap_t_B_Line 1_pu",
        "i_cap_t_C_Line 1_pu",
    )


def get_event_windows() -> tuple[tuple[str, str, float, float], ...]:
    """
    Return the steady-state and transient windows used by every plot group.

    Each steady-state interval contains four complete 50 Hz cycles. Event
    intervals start one cycle before their transition and retain enough time
    afterward to expose the electromagnetic response.

    :return: Tuples of key, title, start time and end time.
    :rtype: tuple[tuple[str, str, float, float], ...]
    """
    return (
        ("pre_event", "Before: R = 30 pu", 0.40, 0.48),
        ("first_step", "Step 0.5 s: 30 -> 24 pu", 0.48, 0.62),
        ("middle", "Between steps: R = 24 pu", 0.80, 0.88),
        ("second_step", "Step 1.0 s: 24 -> 30 pu", 0.98, 1.12),
        ("post_event", "After: R = 30 pu", 1.40, 1.48),
    )


def get_sign_label(signal: base_comparison.ComparisonSignal) -> str:
    """
    Build the plotted Simulink label including any polarity correction.

    :param signal: Aligned comparison signal.
    :type signal: base_comparison.ComparisonSignal
    :return: Legend label for the mapped Simulink trace.
    :rtype: str
    """
    if signal.get_simulink_multiplier() < 0.0:
        return "Simulink mapped (sign reversed)"
    else:
        return "Simulink mapped"


def plot_group_overview(
        time_s: np.ndarray,
        group_signals: list[base_comparison.ComparisonSignal],
        first_event_time_s: float,
        second_event_time_s: float,
        output_path: Path) -> None:
    """
    Save one full-duration overview with both resistance events marked.

    :param time_s: Common Simulink/VeraGrid time vector.
    :type time_s: np.ndarray
    :param group_signals: Signals belonging to one physical plot group.
    :type group_signals: list[base_comparison.ComparisonSignal]
    :param first_event_time_s: Time of the 30 to 24 p.u. step.
    :type first_event_time_s: float
    :param second_event_time_s: Time of the 24 to 30 p.u. step.
    :type second_event_time_s: float
    :param output_path: Destination PNG path.
    :type output_path: Path
    :return: None.
    :rtype: None
    """
    signal_count: int = len(group_signals)
    figure: plt.Figure
    axes: np.ndarray
    figure, axes = plt.subplots(
        signal_count,
        1,
        figsize=(15.0, max(3.0 * signal_count, 5.5)),
        squeeze=False,
        sharex=True,
    )
    maximum_points: int = 30000
    stride: int = max(1, int(np.ceil(time_s.size / maximum_points)))
    signal_index: int

    # The overview establishes event timing and the three operating regimes;
    # detailed cycle-level agreement is shown in the companion window figure.
    for signal_index in range(signal_count):
        signal: base_comparison.ComparisonSignal = group_signals[signal_index]
        axis: plt.Axes = axes[signal_index, 0]
        axis.plot(
            time_s[::stride],
            signal.get_veragrid_values()[::stride],
            color="#1f77b4",
            linewidth=1.2,
            label="VeraGrid",
        )
        axis.plot(
            time_s[::stride],
            signal.get_simulink_values()[::stride],
            color="#d62728",
            linewidth=1.0,
            linestyle="--",
            label=get_sign_label(signal=signal),
        )
        axis.axvline(
            first_event_time_s,
            color="#2ca02c",
            linewidth=1.0,
            linestyle=":",
            label="R: 30 -> 24 pu" if signal_index == 0 else None,
        )
        axis.axvline(
            second_event_time_s,
            color="#9467bd",
            linewidth=1.0,
            linestyle=":",
            label="R: 24 -> 30 pu" if signal_index == 0 else None,
        )
        axis.set_ylabel(signal.get_name() + " [" + signal.get_unit() + "]")
        axis.grid(True, alpha=0.3)

        if signal_index == 0:
            axis.legend(loc="best", ncol=2)
        else:
            pass

    axes[signal_count - 1, 0].set_xlabel("Time [s]")
    figure_title: str = (
        "Simulink vs VeraGrid - "
        + output_path.stem.replace("_", " ").title()
    )
    figure.suptitle(figure_title, fontsize=16, fontweight="bold")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.965))
    figure.savefig(output_path, dpi=170, bbox_inches="tight")
    plt.close(figure)


def plot_group_event_windows(
        time_s: np.ndarray,
        group_signals: list[base_comparison.ComparisonSignal],
        windows: tuple[tuple[str, str, float, float], ...],
        first_event_time_s: float,
        second_event_time_s: float,
        output_path: Path) -> None:
    """
    Save aligned before, transition, middle and after zooms for one group.

    :param time_s: Common Simulink/VeraGrid time vector.
    :type time_s: np.ndarray
    :param group_signals: Signals belonging to one physical plot group.
    :type group_signals: list[base_comparison.ComparisonSignal]
    :param windows: Named time windows used as plot columns.
    :type windows: tuple[tuple[str, str, float, float], ...]
    :param first_event_time_s: Time of the resistance reduction.
    :type first_event_time_s: float
    :param second_event_time_s: Time of the resistance restoration.
    :type second_event_time_s: float
    :param output_path: Destination PNG path.
    :type output_path: Path
    :return: None.
    :rtype: None
    """
    signal_count: int = len(group_signals)
    window_count: int = len(windows)
    figure: plt.Figure
    axes: np.ndarray
    figure, axes = plt.subplots(
        signal_count,
        window_count,
        figsize=(5.2 * window_count, max(3.0 * signal_count, 5.5)),
        squeeze=False,
        sharex=False,
    )
    signal_index: int
    window_index: int

    # Each column has a fixed semantic role across all generated quantities,
    # which makes voltage, current and power figures directly comparable.
    for signal_index in range(signal_count):
        signal: base_comparison.ComparisonSignal = group_signals[signal_index]
        for window_index in range(window_count):
            window_key: str = windows[window_index][0]
            window_title: str = windows[window_index][1]
            window_start_s: float = windows[window_index][2]
            window_end_s: float = windows[window_index][3]
            window_mask: np.ndarray = (
                (time_s >= window_start_s) & (time_s <= window_end_s)
            )
            window_indices: np.ndarray = np.flatnonzero(window_mask)
            maximum_window_points: int = 6000
            window_stride: int = max(
                1,
                int(np.ceil(window_indices.size / maximum_window_points)),
            )
            plotted_indices: np.ndarray = window_indices[::window_stride]
            axis: plt.Axes = axes[signal_index, window_index]

            axis.plot(
                time_s[plotted_indices],
                signal.get_veragrid_values()[plotted_indices],
                color="#1f77b4",
                linewidth=1.3,
                label="VeraGrid",
            )
            axis.plot(
                time_s[plotted_indices],
                signal.get_simulink_values()[plotted_indices],
                color="#d62728",
                linewidth=1.0,
                linestyle="--",
                label=get_sign_label(signal=signal),
            )

            if window_key == "first_step":
                axis.axvline(
                    first_event_time_s,
                    color="#2ca02c",
                    linewidth=1.0,
                    linestyle=":",
                )
            else:
                pass
            if window_key == "second_step":
                axis.axvline(
                    second_event_time_s,
                    color="#9467bd",
                    linewidth=1.0,
                    linestyle=":",
                )
            else:
                pass

            axis.grid(True, alpha=0.3)
            axis.set_xlim(window_start_s, window_end_s)

            if signal_index == 0:
                axis.set_title(window_title)
            else:
                pass
            if window_index == 0:
                axis.set_ylabel(
                    signal.get_name() + " [" + signal.get_unit() + "]"
                )
            else:
                pass
            if signal_index == signal_count - 1:
                axis.set_xlabel("Time [s]")
            else:
                pass
            if signal_index == 0 and window_index == 0:
                axis.legend(loc="best")
            else:
                pass

    figure_title: str = (
        "Simulink vs VeraGrid - Event windows - "
        + output_path.stem.replace("_event_windows", "")
        .replace("_", " ")
        .title()
    )
    figure.suptitle(figure_title, fontsize=16, fontweight="bold")
    figure.tight_layout(rect=(0.0, 0.0, 1.0, 0.965))
    figure.savefig(output_path, dpi=170, bbox_inches="tight")
    plt.close(figure)


def write_windowed_summary(
        time_s: np.ndarray,
        signals: list[base_comparison.ComparisonSignal],
        windows: tuple[tuple[str, str, float, float], ...],
        output_path: Path) -> None:
    """
    Write separate numerical error metrics for every event-analysis window.

    :param time_s: Common Simulink/VeraGrid time vector.
    :type time_s: np.ndarray
    :param signals: All aligned physical comparison signals.
    :type signals: list[base_comparison.ComparisonSignal]
    :param windows: Named intervals used for the metrics.
    :type windows: tuple[tuple[str, str, float, float], ...]
    :param output_path: Destination CSV path.
    :type output_path: Path
    :return: None.
    :rtype: None
    """
    rows: list[tuple[str, str, float, float, str, str, str, str, str,
                     float, int, float, float, float, float]] = list()
    window: tuple[str, str, float, float]
    signal: base_comparison.ComparisonSignal

    # Window-specific metrics prevent startup or switching samples from hiding
    # the precision reached in each stationary operating regime.
    for window in windows:
        window_mask: np.ndarray = (
            (time_s >= window[2]) & (time_s <= window[3])
        )
        for signal in signals:
            simulink_values: np.ndarray = signal.get_simulink_values()[window_mask]
            veragrid_values: np.ndarray = signal.get_veragrid_values()[window_mask]
            error: np.ndarray = simulink_values - veragrid_values
            reference_rms: float = float(
                np.sqrt(np.mean(veragrid_values ** 2))
            )
            rmse: float = float(np.sqrt(np.mean(error ** 2)))

            if reference_rms > 1.0e-15:
                normalized_rmse: float = rmse / reference_rms
            else:
                normalized_rmse = float("nan")

            rows.append((
                window[0],
                window[1],
                window[2],
                window[3],
                signal.get_group_name(),
                signal.get_name(),
                signal.get_unit(),
                signal.get_simulink_reference(),
                signal.get_veragrid_reference(),
                signal.get_simulink_multiplier(),
                int(error.size),
                float(np.mean(np.abs(error))),
                rmse,
                normalized_rmse,
                float(np.max(np.abs(error))),
            ))

    columns: tuple[str, ...] = (
        "window_key", "window_title", "window_start_s", "window_end_s",
        "plot_group", "signal", "unit", "simulink_reference",
        "veragrid_reference", "simulink_multiplier_to_veragrid", "points",
        "mae", "rmse", "normalized_rmse", "max_abs_error",
    )
    summary_frame: pd.DataFrame = pd.DataFrame(rows, columns=columns)
    summary_frame.to_csv(output_path, index=False)


def main() -> int:
    """
    Compare the 1.5-second Simulink and VeraGrid two-step trajectories.

    :return: Process exit code, zero when all plots and summaries are written.
    :rtype: int
    """
    first_event_time_s: float = 0.5
    second_event_time_s: float = 1.0
    required_analysis_end_s: float = 1.48
    case_directory: Path = Path(__file__).resolve().parent
    simulink_path: Path = (
        case_directory / "simulink_results_thev_line_Rload_steps_pu.csv"
    )
    veragrid_path: Path = (
        case_directory / "veragrid_results_thev_line_Rload_steps_pu.csv"
    )
    output_directory: Path = case_directory / "comparison_plots_steps"

    if simulink_path.is_file() and veragrid_path.is_file():
        pass
    else:
        print("Missing step-case CSV beside the comparison script.")
        print("Expected Simulink file: " + str(simulink_path))
        print("Expected VeraGrid file: " + str(veragrid_path))
        return 1

    # Load once because derived powers and the many zoom windows reuse every
    # mapped signal on the same common time base.
    simulink_frame: pd.DataFrame = pd.read_csv(simulink_path)
    veragrid_frame: pd.DataFrame = pd.read_csv(veragrid_path)
    valid_simulink: bool = base_comparison.validate_columns(
        simulink_frame,
        get_required_simulink_columns(),
        simulink_path.name,
    )
    valid_veragrid: bool = base_comparison.validate_columns(
        veragrid_frame,
        get_required_veragrid_columns(),
        veragrid_path.name,
    )

    if valid_simulink and valid_veragrid:
        pass
    else:
        return 1

    simulink_time: np.ndarray = simulink_frame["time_s"].to_numpy(dtype=float)
    veragrid_time: np.ndarray = veragrid_frame["time_s"].to_numpy(dtype=float)
    overlap_start_s: float = max(
        float(simulink_time[0]),
        float(veragrid_time[0]),
    )
    overlap_end_s: float = min(
        float(simulink_time[-1]),
        float(veragrid_time[-1]),
    )
    overlap_mask: np.ndarray = (
        (simulink_time >= overlap_start_s) & (simulink_time <= overlap_end_s)
    )
    common_time: np.ndarray = simulink_time[overlap_mask]

    if common_time.size >= 2 and overlap_end_s >= required_analysis_end_s:
        pass
    else:
        print(
            "The overlapping CSV interval must extend through at least "
            + str(required_analysis_end_s)
            + " s."
        )
        return 1

    signals: list[base_comparison.ComparisonSignal] = (
        base_comparison.create_comparison_signals(
            simulink_frame,
            veragrid_frame,
            simulink_time,
            veragrid_time,
            common_time,
        )
    )
    windows: tuple[tuple[str, str, float, float], ...] = get_event_windows()
    output_directory.mkdir(parents=True, exist_ok=True)
    group_names: list[str] = sorted(
        set(signal.get_group_name() for signal in signals)
    )
    group_name: str

    for group_name in group_names:
        group_signals: list[base_comparison.ComparisonSignal] = list()
        signal: base_comparison.ComparisonSignal
        for signal in signals:
            if signal.get_group_name() == group_name:
                group_signals.append(signal)
            else:
                pass

        plot_group_overview(
            time_s=common_time,
            group_signals=group_signals,
            first_event_time_s=first_event_time_s,
            second_event_time_s=second_event_time_s,
            output_path=output_directory / (group_name + "_overview.png"),
        )
        plot_group_event_windows(
            time_s=common_time,
            group_signals=group_signals,
            windows=windows,
            first_event_time_s=first_event_time_s,
            second_event_time_s=second_event_time_s,
            output_path=(
                output_directory / (group_name + "_event_windows.png")
            ),
        )

    base_comparison.write_summary(
        signals,
        output_directory / "comparison_summary_full.csv",
    )
    write_windowed_summary(
        time_s=common_time,
        signals=signals,
        windows=windows,
        output_path=output_directory / "comparison_summary_windows.csv",
    )
    base_comparison.write_unmapped_columns(
        simulink_frame,
        veragrid_frame,
        output_directory / "unmapped_columns.txt",
    )
    print("Step comparison plots written to: " + str(output_directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
