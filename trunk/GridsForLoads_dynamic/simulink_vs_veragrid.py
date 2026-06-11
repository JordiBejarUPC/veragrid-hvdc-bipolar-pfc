from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
# power reference change in the GFM controller
TEST_NAME: str = "p_ref_step"
SIMULINK_CSV_NAME: str = "simulink_results_G4L_p_ref_step.csv"
VERAGRID_CSV_NAME: str = "veragrid_G4L_p_gfm.csv"
# rocof
# TEST_NAME: str = "rocof"
# SIMULINK_CSV_NAME: str = "simulink_results_G4L_rocof.csv"
# VERAGRID_CSV_NAME: str = "veragrid_G4L_rocof.csv"
# phase jump
# TEST_NAME: str = "phase_jump"
# SIMULINK_CSV_NAME: str = "simulink_results_G4L_phase_jump.csv"
# VERAGRID_CSV_NAME: str = "veragrid_G4L_phase_jump.csv"

# TEST_NAME: str = "vac_step"
# SIMULINK_CSV_NAME: str = "simulink_results_G4L_v_mag_variation.csv"
# VERAGRID_CSV_NAME: str = "veragrid_G4L_vac_step.csv"

# TEST_NAME: str = "vq_step"
# SIMULINK_CSV_NAME: str = "simulink_results_G4L_vq_step.csv"
# VERAGRID_CSV_NAME: str = "veragrid_G4L_vq_step.csv"

class TimeBase(Enum):
    """Time base selection for signal comparison.

    :param value: Internal enum value.
    """

    Simulink = "simulink"
    VeraGrid = "veragrid"
    Custom = "custom"


class SignalSpec:
    """Describe one compared signal.

    :param name: Human readable signal name.
    :param simulink_column: Simulink CSV column name.
    :param veragrid_column: VeraGrid CSV column name.
    :param unit: Plot unit label.
    :param simulink_scale: Simulink multiplicative scale.
    :param veragrid_scale: VeraGrid multiplicative scale.
    :param simulink_offset: Simulink additive offset.
    :param veragrid_offset: VeraGrid additive offset.
    """

    __slots__ = (
        "name",
        "simulink_column",
        "veragrid_column",
        "unit",
        "simulink_scale",
        "veragrid_scale",
        "simulink_offset",
        "veragrid_offset",
    )

    def __init__(
        self,
        name: str,
        simulink_column: str,
        veragrid_column: str,
        unit: str,
        simulink_scale: float = 1.0,
        veragrid_scale: float = 1.0,
        simulink_offset: float = 0.0,
        veragrid_offset: float = 0.0,
    ) -> None:
        """Initialize a signal specification.

        :param name: Human readable signal name.
        :param simulink_column: Simulink CSV column name.
        :param veragrid_column: VeraGrid CSV column name.
        :param unit: Plot unit label.
        :param simulink_scale: Simulink multiplicative scale.
        :param veragrid_scale: VeraGrid multiplicative scale.
        :param simulink_offset: Simulink additive offset.
        :param veragrid_offset: VeraGrid additive offset.
        :return: None.
        """
        self.name = name
        self.simulink_column = simulink_column
        self.veragrid_column = veragrid_column
        self.unit = unit
        self.simulink_scale = simulink_scale
        self.veragrid_scale = veragrid_scale
        self.simulink_offset = simulink_offset
        self.veragrid_offset = veragrid_offset


class PlotGroup:
    """Describe one output figure.

    :param title: Figure title.
    :param file_stem: Output file stem.
    :param signals: Signals included in the figure.
    """

    __slots__ = ("title", "file_stem", "signals")

    def __init__(self, title: str, file_stem: str, signals: list[SignalSpec]) -> None:
        """Initialize a plot group.

        :param title: Figure title.
        :param file_stem: Output file stem.
        :param signals: Signals included in the figure.
        :return: None.
        """
        self.title = title
        self.file_stem = file_stem
        self.signals = signals


class ComparisonResult:
    """Store summary metrics for one signal.

    :param group_name: Plot group title.
    :param signal_name: Signal name.
    :param unit: Signal unit.
    :param points: Number of compared points.
    :param mae: Mean absolute error.
    :param rmse: Root mean square error.
    :param max_abs_error: Maximum absolute error.
    """

    __slots__ = ("group_name", "signal_name", "unit", "points", "mae", "rmse", "max_abs_error")

    def __init__(
        self,
        group_name: str,
        signal_name: str,
        unit: str,
        points: int,
        mae: float,
        rmse: float,
        max_abs_error: float,
    ) -> None:
        """Initialize a comparison result.

        :param group_name: Plot group title.
        :param signal_name: Signal name.
        :param unit: Signal unit.
        :param points: Number of compared points.
        :param mae: Mean absolute error.
        :param rmse: Root mean square error.
        :param max_abs_error: Maximum absolute error.
        :return: None.
        """
        self.group_name = group_name
        self.signal_name = signal_name
        self.unit = unit
        self.points = points
        self.mae = mae
        self.rmse = rmse
        self.max_abs_error = max_abs_error


def create_plot_groups() -> list[PlotGroup]:
    """Create plot groups and editable signal mappings.

    :return: Plot groups for the comparison workflow.
    """
    groups: list[PlotGroup] = list()

    groups.append(
        PlotGroup(
            "AC voltages",
            "ac_voltages",
            list(
                [
                    SignalSpec("Va", "Va", "vA_Bus1_kV", "kV", simulink_scale=1.0 / 1000.0),
                    SignalSpec("Vb", "Vb", "vB_Bus1_kV", "kV", simulink_scale=1.0 / 1000.0),
                    SignalSpec("Vc", "Vc", "vC_Bus1_kV", "kV", simulink_scale=1.0 / 1000.0),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "AC currents",
            "ac_currents",
            list(
                [
                    SignalSpec("Ia", "Ia", "iA_grid_A_sim_sign", "A"),
                    SignalSpec("Ib", "Ib", "iB_grid_A_sim_sign", "A"),
                    SignalSpec("Ic", "Ic", "iC_grid_A_sim_sign", "A"),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "dq voltages",
            "dq_voltages",
            list([SignalSpec("Vd", "Vd", "vd_V", "V"), SignalSpec("Vq", "Vq", "vq_V", "V")]),
        )
    )
    groups.append(
        PlotGroup(
            "q-axis current chain",
            "q_axis_current_chain",
            list(
                [
                    SignalSpec("Iq", "Iq", "iq_va_A_sim_sign", "A"),
                    SignalSpec("Iq limited", "Iq", "iq_lim_A_sim_sign", "A"),
                    SignalSpec("Iq measured", "Iq", "iq_meas_A_sim_sign", "A"),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "d-axis current chain",
            "d_axis_current_chain",
            list(
                [
                    SignalSpec("Id", "Id", "id_va_A_sim_sign", "A"),
                    SignalSpec("Id limited", "Id", "id_lim_A_sim_sign", "A"),
                    SignalSpec("Id measured", "Id", "id_meas_A_sim_sign", "A"),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "active powers",
            "active_powers",
            list(
                [
                    # SignalSpec("Pac bus", "Pac", "Pac_bus_MW_sim_sign", "MW", simulink_scale=1.0 / 1000000.0),
                    SignalSpec("Pac", "Pac", "Pac_MW_sim_sign", "MW", simulink_scale=1.0 / 1000000.0),
                    SignalSpec("Pdc", "Pdc", "pdc_MW_sim_sign", "MW", simulink_scale=-1.0 / 1000000.0),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "DC link",
            "dc_link",
            list(
                [
                    SignalSpec("Vdc", "Vdc", "vdc_V", "V"),
                    SignalSpec("Idc", "Idc_L", "idc_A", "A", simulink_scale=-1.0),
                    # SignalSpec("Idc load", "Idc_L", "idcL_A", "A"),
                    # SignalSpec("Icapdc", "Idc_L", "icapdc_A", "A"),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "virtual admittance errors",
            "virtual_admittance_errors",
            list([SignalSpec("err q", "err_q_VA", "err_q_V", "V"), SignalSpec("err d", "err_d_VA", "err_d_V", "V")]),
        )
    )
    groups.append(
        PlotGroup(
            "virtual admittance internal outputs",
            "virtual_admittance_internal_outputs",
            list(
                [
                    SignalSpec("y1", "VA_y1", "y1_raw_A", "A"),
                    SignalSpec("y2", "VA_y2", "y2_raw_A", "A"),
                    SignalSpec("y3", "VA_y3", "y3_raw_A", "A"),
                    SignalSpec("y4", "VA_y4", "y4_raw_A", "A"),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "virtual admittance reconstructed currents",
            "virtual_admittance_reconstructed_currents",
            list(
                [
                    SignalSpec("Iq reconstructed", "Iq", "iq_va_reconstructed_A_sim_sign", "A"),
                    SignalSpec("Id reconstructed", "Id", "id_va_reconstructed_A_sim_sign", "A"),
                    SignalSpec("Iq actual", "Iq", "iq_va_actual_A_sim_sign", "A"),
                    SignalSpec("Id actual", "Id", "id_va_actual_A_sim_sign", "A"),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "PLL",
            "pll",
            list(
                [
                    SignalSpec("omega pll", "omega_pll", "omega_pll", "rad/s"),
                    # SignalSpec("phase pll", "phase_pll", "phase_pll", "rad"),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "Grid source voltage references",
            "grid_source_voltage_references",
            list(
                [
                    SignalSpec("Vac grid", "Vac_grid", "Vac_grid", "V"),
                    SignalSpec("phase a", "phase_a", "phase_a", "rad"),
                    SignalSpec("phase b", "phase_b", "phase_b", "rad"),
                    SignalSpec("phase c", "phase_c", "phase_c", "rad"),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "Grid source frequency references",
            "grid_source_omega_references",
            list(
                [
                    SignalSpec("omega grid", "omega_grid", "omega_grid", "rad/s"),
                ]
            ),
        )
    )
    groups.append(
        PlotGroup(
            "VA references",
            "va_references",
            list(
                [
                    SignalSpec("Vq ref", "Vq_ref", "Vq_ref", "V"),
                    SignalSpec("Vd ref", "Vd_ref", "Vd_ref", "V"),
                ]
            ),
        )
    )

    return groups


def get_output_folder_name(test_name: str) -> str:
    """Build the output folder name for one comparison run.

    :param test_name: User-selected test name.
    :return: Output folder name.
    """
    sanitized_test_name: str = sanitize_file_name(test_name)
    folder_name: str = f"comparison_plots_{sanitized_test_name}"
    return folder_name


def strip_column_spaces(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with stripped column names.

    :param dataframe: Input dataframe.
    :return: Dataframe with trimmed column names.
    """
    cleaned: pd.DataFrame = dataframe.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    return cleaned


def print_columns(label: str, dataframe: pd.DataFrame) -> None:
    """Print available columns to help mapping edits.

    :param label: Dataset label.
    :param dataframe: Dataframe whose columns are printed.
    :return: None.
    """
    column_names: list[str] = [str(column) for column in dataframe.columns]
    print(f"\n{label} columns ({len(column_names)}):")
    for column_name in column_names:
        print(f"  - {column_name}")


def find_time_column(dataframe: pd.DataFrame, preferred_names: list[str], label: str) -> Optional[str]:
    """Find the first preferred time column present in a dataframe.

    :param dataframe: Input dataframe.
    :param preferred_names: Preferred time column names in priority order.
    :param label: Dataset label.
    :return: Matching time column name, or None.
    """
    selected_name: Optional[str] = None
    for candidate_name in preferred_names:
        if candidate_name in dataframe.columns:
            selected_name = candidate_name
            break
        else:
            pass

    if selected_name is None:
        print(f"No time column found for {label}. Tried: {preferred_names}")
    else:
        print(f"Using {label} time column: {selected_name}")

    return selected_name


def prepare_time_array(dataframe: pd.DataFrame, time_column: str, label: str) -> Optional[np.ndarray]:
    """Extract a sorted numeric time array.

    :param dataframe: Input dataframe.
    :param time_column: Time column name.
    :param label: Dataset label.
    :return: Sorted time array, or None.
    """
    time_series: pd.Series = pd.to_numeric(dataframe[time_column], errors="coerce")
    time_values: np.ndarray = time_series.to_numpy(dtype=float)
    valid_mask: np.ndarray = np.isfinite(time_values)

    if not np.any(valid_mask):
        print(f"No valid numeric time samples found for {label}.")
        return None
    else:
        filtered_time: np.ndarray = time_values[valid_mask]
        sorted_time: np.ndarray = np.sort(filtered_time)

    if sorted_time.size < 2:
        print(f"Not enough time samples found for {label}.")
        return None
    else:
        return sorted_time


def estimate_time_step(time_values: np.ndarray, label: str) -> Optional[float]:
    """Estimate the effective simulation time step from a time vector.

    :param time_values: Sorted simulation time vector.
    :param label: Dataset label used in messages.
    :return: Estimated positive time step, or None.
    """
    time_differences: np.ndarray = np.diff(time_values)
    positive_mask: np.ndarray = time_differences > 0.0

    if not np.any(positive_mask):
        print(f"Could not estimate a positive time step for {label}.")
        return None
    else:
        positive_steps: np.ndarray = time_differences[positive_mask]
        estimated_step: float = float(np.median(positive_steps))
        print(f"Estimated {label} time step: {estimated_step}")
        return estimated_step


def choose_time_base(
    simulink_step: Optional[float],
    veragrid_step: Optional[float],
    preferred_time_base: TimeBase,
) -> TimeBase:
    """Choose the comparison time base from the available time steps.

    :param simulink_step: Estimated Simulink time step.
    :param veragrid_step: Estimated VeraGrid time step.
    :param preferred_time_base: Preferred user time base.
    :return: Selected time base.
    """
    if preferred_time_base == TimeBase.Custom:
        print("Using custom time base selection.")
        return TimeBase.Custom
    else:
        pass

    if simulink_step is None and veragrid_step is None:
        print("Could not estimate either time step. Falling back to Simulink time base.")
        return TimeBase.Simulink
    else:
        pass

    if simulink_step is None:
        print("Simulink time step unavailable. Using VeraGrid time base.")
        return TimeBase.VeraGrid
    else:
        pass

    if veragrid_step is None:
        print("VeraGrid time step unavailable. Using Simulink time base.")
        return TimeBase.Simulink
    else:
        pass

    if preferred_time_base == TimeBase.Simulink:
        if simulink_step <= veragrid_step:
            print("Simulink step is smaller or equal. Using Simulink time base.")
            return TimeBase.Simulink
        else:
            print("VeraGrid step is smaller. Using VeraGrid time base to adapt the coarser simulation.")
            return TimeBase.VeraGrid
    else:
        if veragrid_step <= simulink_step:
            print("VeraGrid step is smaller or equal. Using VeraGrid time base.")
            return TimeBase.VeraGrid
        else:
            print("Simulink step is smaller. Using Simulink time base to adapt the coarser simulation.")
            return TimeBase.Simulink


def build_common_time_vector(
    simulink_time: np.ndarray,
    veragrid_time: np.ndarray,
    time_base: TimeBase,
    custom_time: Optional[np.ndarray],
) -> Optional[np.ndarray]:
    """Build the common interpolation time vector.

    :param simulink_time: Simulink time array.
    :param veragrid_time: VeraGrid time array.
    :param time_base: Selected comparison time base.
    :param custom_time: Optional custom time vector.
    :return: Common time vector, or None.
    """
    overlap_start: float = max(float(simulink_time[0]), float(veragrid_time[0]))
    overlap_end: float = min(float(simulink_time[-1]), float(veragrid_time[-1]))

    if overlap_end <= overlap_start:
        print("The simulation time ranges do not overlap.")
        return None
    else:
        pass

    base_vector: Optional[np.ndarray] = None
    if time_base == TimeBase.Simulink:
        base_vector = simulink_time
    else:
        if time_base == TimeBase.VeraGrid:
            base_vector = veragrid_time
        else:
            if custom_time is None:
                print("Custom time base selected but no custom time vector was provided.")
                base_vector = None
            else:
                base_vector = custom_time

    if base_vector is None:
        return None
    else:
        overlap_mask: np.ndarray = (base_vector >= overlap_start) & (base_vector <= overlap_end)
        common_time: np.ndarray = base_vector[overlap_mask]

    if common_time.size < 2:
        print("Not enough common samples after overlap filtering.")
        return None
    else:
        return common_time


def extract_signal(
    dataframe: pd.DataFrame,
    time_column: str,
    value_column: str,
    scale: float,
    offset: float,
    label: str,
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """Extract sorted numeric time and value arrays for one signal.

    :param dataframe: Source dataframe.
    :param time_column: Time column name.
    :param value_column: Signal column name.
    :param scale: Multiplicative scale.
    :param offset: Additive offset.
    :param label: Signal label used in messages.
    :return: Tuple with time and values, or None.
    """
    if value_column not in dataframe.columns:
        print(f"Missing column for {label}: {value_column}")
        return None
    else:
        pass

    time_values: np.ndarray = pd.to_numeric(dataframe[time_column], errors="coerce").to_numpy(dtype=float)
    raw_values: np.ndarray = pd.to_numeric(dataframe[value_column], errors="coerce").to_numpy(dtype=float)
    valid_mask: np.ndarray = np.isfinite(time_values) & np.isfinite(raw_values)

    if not np.any(valid_mask):
        print(f"No valid numeric samples found for {label}: {value_column}")
        return None
    else:
        filtered_time: np.ndarray = time_values[valid_mask]
        filtered_values: np.ndarray = raw_values[valid_mask] * scale + offset
        order: np.ndarray = np.argsort(filtered_time)
        sorted_time: np.ndarray = filtered_time[order]
        sorted_values: np.ndarray = filtered_values[order]
        unique_time: np.ndarray
        unique_indices: np.ndarray
        unique_time, unique_indices = np.unique(sorted_time, return_index=True)
        unique_values: np.ndarray = sorted_values[unique_indices]

    if unique_time.size < 2:
        print(f"Not enough unique samples found for {label}: {value_column}")
        return None
    else:
        return unique_time, unique_values


def interpolate_signal(source_time: np.ndarray, source_values: np.ndarray, target_time: np.ndarray) -> np.ndarray:
    """Interpolate a signal on the target time vector.

    :param source_time: Source time vector.
    :param source_values: Source signal values.
    :param target_time: Target time vector.
    :return: Interpolated values.
    """
    interpolated_values: np.ndarray = np.interp(target_time, source_time, source_values)
    return interpolated_values


def compute_metrics(group_name: str, signal: SignalSpec, error_values: np.ndarray) -> ComparisonResult:
    """Compute summary metrics for one error signal.

    :param group_name: Plot group title.
    :param signal: Signal specification.
    :param error_values: VeraGrid minus Simulink error values.
    :return: Computed comparison result.
    """
    absolute_error: np.ndarray = np.abs(error_values)
    mae: float = float(np.mean(absolute_error))
    rmse: float = float(np.sqrt(np.mean(np.square(error_values))))
    max_abs_error: float = float(np.max(absolute_error))
    points: int = int(error_values.size)
    result: ComparisonResult = ComparisonResult(group_name, signal.name, signal.unit, points, mae, rmse, max_abs_error)
    return result


def sanitize_file_name(file_name: str) -> str:
    """Convert a text label into a file-safe stem.

    :param file_name: Raw file name text.
    :return: Sanitized file stem.
    """
    characters: list[str] = list()
    for character in file_name.lower():
        if character.isalnum():
            characters.append(character)
        else:
            characters.append("_")
    sanitized: str = "".join(characters).strip("_")
    return sanitized


def save_group_plot(
    output_folder: Path,
    group: PlotGroup,
    common_time: np.ndarray,
    plot_rows: list[tuple[SignalSpec, np.ndarray, np.ndarray, np.ndarray]],
    test_name: str,
) -> None:
    """Save one plot figure for a plot group.

    :param output_folder: Output folder.
    :param group: Plot group definition.
    :param common_time: Common comparison time vector.
    :param plot_rows: Rows of interpolated data.
    :param test_name: User-selected test name used in file naming.
    :return: None.
    """
    if len(plot_rows) == 0:
        print(f"Skipping plot for group '{group.title}' because no mapped signals were available.")
        return
    else:
        figure, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
        upper_axis = axes[0]
        lower_axis = axes[1]

    unit_names: set[str] = set()
    for signal, simulink_values, veragrid_values, error_values in plot_rows:
        upper_axis.plot(common_time, simulink_values, linestyle="--", label=f"Simulink - {signal.name}")
        upper_axis.plot(common_time, veragrid_values, linestyle="-", label=f"VeraGrid - {signal.name}")
        lower_axis.plot(common_time, error_values, linestyle="-", label=f"Error - {signal.name}")
        unit_names.add(signal.unit)

    upper_axis.set_title(group.title)
    if len(unit_names) == 1:
        upper_axis.set_ylabel(next(iter(unit_names)))
    else:
        upper_axis.set_ylabel("Signal")
    lower_axis.set_ylabel("VG - SL")
    lower_axis.set_xlabel("Time [s]")
    upper_axis.grid(True)
    lower_axis.grid(True)
    upper_axis.legend(loc="best")
    lower_axis.legend(loc="best")

    sanitized_test_name: str = sanitize_file_name(test_name)
    output_path: Path = output_folder / f"{sanitize_file_name(group.file_stem)}_{sanitized_test_name}.png"
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    print(f"Saved plot: {output_path}")


def save_summary_csv(output_folder: Path, results: list[ComparisonResult], test_name: str) -> None:
    """Save a CSV summary of computed metrics.

    :param output_folder: Output folder.
    :param results: Comparison results.
    :param test_name: User-selected test name used in file naming.
    :return: None.
    """
    rows: list[dict[str, object]] = list()
    for result in results:
        row: dict[str, object] = dict()
        row["group"] = result.group_name
        row["signal"] = result.signal_name
        row["unit"] = result.unit
        row["points"] = result.points
        row["mae"] = result.mae
        row["rmse"] = result.rmse
        row["max_abs_error"] = result.max_abs_error
        rows.append(row)

    summary_frame: pd.DataFrame = pd.DataFrame(rows)
    sanitized_test_name: str = sanitize_file_name(test_name)
    summary_path: Path = output_folder / f"comparison_summary_{sanitized_test_name}.csv"
    summary_frame.to_csv(summary_path, index=False)
    print(f"Saved summary CSV: {summary_path}")


def run_comparison() -> None:
    """Execute the CSV comparison workflow.

    :return: None.
    """
    script_folder: Path = Path(__file__).resolve().parent
    test_name: str = TEST_NAME
    simulink_csv_path: Path = script_folder / SIMULINK_CSV_NAME
    veragrid_csv_path: Path = script_folder / VERAGRID_CSV_NAME
    output_folder: Path = script_folder / get_output_folder_name(test_name)
    preferred_time_base: TimeBase = TimeBase.Simulink

    if not simulink_csv_path.exists():
        print(f"Missing Simulink CSV: {simulink_csv_path}")
        return
    else:
        pass

    if not veragrid_csv_path.exists():
        print(f"Missing VeraGrid CSV: {veragrid_csv_path}")
        return
    else:
        pass

    print(f"Loading Simulink CSV: {simulink_csv_path}")
    simulink_frame: pd.DataFrame = pd.read_csv(simulink_csv_path)
    print(f"Loading VeraGrid CSV: {veragrid_csv_path}")
    veragrid_frame: pd.DataFrame = pd.read_csv(veragrid_csv_path)

    simulink_frame = strip_column_spaces(simulink_frame)
    veragrid_frame = strip_column_spaces(veragrid_frame)

    print_columns("Simulink", simulink_frame)
    print_columns("VeraGrid", veragrid_frame)

    simulink_time_column: Optional[str] = find_time_column(simulink_frame, ["time", "time_s", "t", "tout"], "Simulink")
    veragrid_time_column: Optional[str] = find_time_column(veragrid_frame, ["time_s", "time", "t", "tout"], "VeraGrid")

    if simulink_time_column is None or veragrid_time_column is None:
        print("Could not resolve both time columns. Stopping safely.")
        return
    else:
        pass

    simulink_time: Optional[np.ndarray] = prepare_time_array(simulink_frame, simulink_time_column, "Simulink")
    veragrid_time: Optional[np.ndarray] = prepare_time_array(veragrid_frame, veragrid_time_column, "VeraGrid")

    if simulink_time is None or veragrid_time is None:
        print("Could not prepare both time vectors. Stopping safely.")
        return
    else:
        pass

    simulink_step: Optional[float] = estimate_time_step(simulink_time, "Simulink")
    veragrid_step: Optional[float] = estimate_time_step(veragrid_time, "VeraGrid")
    selected_time_base: TimeBase = choose_time_base(simulink_step, veragrid_step, preferred_time_base)

    common_time: Optional[np.ndarray] = build_common_time_vector(simulink_time, veragrid_time, selected_time_base, None)
    if common_time is None:
        print("Could not build a common time vector. Stopping safely.")
        return
    else:
        pass

    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"Output folder: {output_folder}")

    plot_groups: list[PlotGroup] = create_plot_groups()
    results: list[ComparisonResult] = list()

    # Process each group by extracting source signals, interpolating to the common
    # time vector, plotting overlays and errors, and collecting metrics.
    for group in plot_groups:
        print(f"\nProcessing group: {group.title}")
        plot_rows: list[tuple[SignalSpec, np.ndarray, np.ndarray, np.ndarray]] = list()

        for signal in group.signals:
            simulink_label: str = f"Simulink {signal.name}"
            veragrid_label: str = f"VeraGrid {signal.name}"
            simulink_pair: Optional[tuple[np.ndarray, np.ndarray]] = extract_signal(
                simulink_frame,
                simulink_time_column,
                signal.simulink_column,
                signal.simulink_scale,
                signal.simulink_offset,
                simulink_label,
            )
            veragrid_pair: Optional[tuple[np.ndarray, np.ndarray]] = extract_signal(
                veragrid_frame,
                veragrid_time_column,
                signal.veragrid_column,
                signal.veragrid_scale,
                signal.veragrid_offset,
                veragrid_label,
            )

            if simulink_pair is None or veragrid_pair is None:
                print(f"Skipping signal due to unavailable data: {signal.name}")
            else:
                simulink_interp: np.ndarray = interpolate_signal(simulink_pair[0], simulink_pair[1], common_time)
                veragrid_interp: np.ndarray = interpolate_signal(veragrid_pair[0], veragrid_pair[1], common_time)
                error_values: np.ndarray = veragrid_interp - simulink_interp
                plot_rows.append((signal, simulink_interp, veragrid_interp, error_values))
                results.append(compute_metrics(group.title, signal, error_values))

        save_group_plot(output_folder, group, common_time, plot_rows, test_name)

    save_summary_csv(output_folder, results, test_name)
    print("Comparison complete.")


if __name__ == "__main__":
    run_comparison()
