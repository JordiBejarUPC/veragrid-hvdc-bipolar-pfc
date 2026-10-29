from pathlib import Path
from typing import Any, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np


def get_plot_results_directory(case_name: str, solver_key: str, output_root_name: str = "plot_results") -> Path:
    """
    Return the plot-output directory for one case and solver.

    :param case_name: Case identifier.
    :type case_name: str
    :param solver_key: Solver identifier.
    :type solver_key: str
    :param output_root_name: Root folder name used for the plot exports.
    :type output_root_name: str
    :return: Plot-output directory.
    :rtype: Path
    """
    output_dir: Path = Path(__file__).resolve().parents[1] / output_root_name / case_name / solver_key.lower()
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def save_three_phase_plot(
        file_path: Path,
        time_values: np.ndarray,
        phase_a: np.ndarray,
        phase_b: np.ndarray,
        phase_c: np.ndarray,
        title: str,
        y_label: str,
        legend_prefix: str,
) -> None:
    """
    Save one three-phase line plot.

    :param file_path: Output image path.
    :type file_path: Path
    :param time_values: Time vector.
    :type time_values: np.ndarray
    :param phase_a: Phase-A trajectory.
    :type phase_a: np.ndarray
    :param phase_b: Phase-B trajectory.
    :type phase_b: np.ndarray
    :param phase_c: Phase-C trajectory.
    :type phase_c: np.ndarray
    :param title: Figure title.
    :type title: str
    :param y_label: Y-axis label.
    :type y_label: str
    :param legend_prefix: Legend prefix.
    :type legend_prefix: str
    :return: None.
    :rtype: None
    """
    figure = plt.figure(figsize=(12, 7))
    axis = figure.add_subplot(1, 1, 1)

    # The three phases are plotted together because phase balance and sign errors
    # become obvious immediately when the curves are overlaid.
    axis.plot(time_values, phase_a, label=f"{legend_prefix} A", color="tab:blue")
    axis.plot(time_values, phase_b, label=f"{legend_prefix} B", color="tab:red")
    axis.plot(time_values, phase_c, label=f"{legend_prefix} C", color="tab:green")
    axis.set_title(title)
    axis.set_xlabel("Time [s]")
    axis.set_ylabel(y_label)
    axis.grid(True)
    axis.legend(loc="best")

    figure.tight_layout()
    figure.savefig(file_path, dpi=400)
    plt.close(figure)


def save_two_panel_three_phase_plot(
        file_path: Path,
        time_values: np.ndarray,
        top_triplet: Tuple[np.ndarray, np.ndarray, np.ndarray],
        top_title: str,
        top_ylabel: str,
        top_legend_prefix: str,
        bottom_triplet: Tuple[np.ndarray, np.ndarray, np.ndarray],
        bottom_title: str,
        bottom_ylabel: str,
        bottom_legend_prefix: str,
) -> None:
    """
    Save one two-panel three-phase plot.

    :param file_path: Output image path.
    :type file_path: Path
    :param time_values: Time vector.
    :type time_values: np.ndarray
    :param top_triplet: Top-panel phase triplet.
    :type top_triplet: Tuple[np.ndarray, np.ndarray, np.ndarray]
    :param top_title: Top-panel title.
    :type top_title: str
    :param top_ylabel: Top-panel y label.
    :type top_ylabel: str
    :param top_legend_prefix: Top-panel legend prefix.
    :type top_legend_prefix: str
    :param bottom_triplet: Bottom-panel phase triplet.
    :type bottom_triplet: Tuple[np.ndarray, np.ndarray, np.ndarray]
    :param bottom_title: Bottom-panel title.
    :type bottom_title: str
    :param bottom_ylabel: Bottom-panel y label.
    :type bottom_ylabel: str
    :param bottom_legend_prefix: Bottom-panel legend prefix.
    :type bottom_legend_prefix: str
    :return: None.
    :rtype: None
    """
    figure, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    top_axis = axes[0]
    bottom_axis = axes[1]

    top_axis.plot(time_values, top_triplet[0], label=f"{top_legend_prefix} A", color="tab:blue")
    top_axis.plot(time_values, top_triplet[1], label=f"{top_legend_prefix} B", color="tab:red")
    top_axis.plot(time_values, top_triplet[2], label=f"{top_legend_prefix} C", color="tab:green")
    top_axis.set_title(top_title)
    top_axis.set_ylabel(top_ylabel)
    top_axis.grid(True)
    top_axis.legend(loc="best")

    bottom_axis.plot(time_values, bottom_triplet[0], label=f"{bottom_legend_prefix} A", color="tab:blue")
    bottom_axis.plot(time_values, bottom_triplet[1], label=f"{bottom_legend_prefix} B", color="tab:red")
    bottom_axis.plot(time_values, bottom_triplet[2], label=f"{bottom_legend_prefix} C", color="tab:green")
    bottom_axis.set_title(bottom_title)
    bottom_axis.set_xlabel("Time [s]")
    bottom_axis.set_ylabel(bottom_ylabel)
    bottom_axis.grid(True)
    bottom_axis.legend(loc="best")

    figure.tight_layout()
    figure.savefig(file_path, dpi=400)
    plt.close(figure)


def save_scalar_plot(
        file_path: Path,
        time_values: np.ndarray,
        values: np.ndarray,
        title: str,
        y_label: str,
) -> None:
    """
    Save one scalar time-series plot.

    :param file_path: Output image path.
    :type file_path: Path
    :param time_values: Time vector.
    :type time_values: np.ndarray
    :param values: Scalar trajectory.
    :type values: np.ndarray
    :param title: Figure title.
    :type title: str
    :param y_label: Y-axis label.
    :type y_label: str
    :return: None.
    :rtype: None
    """
    figure = plt.figure(figsize=(12, 5))
    axis = figure.add_subplot(1, 1, 1)
    axis.plot(time_values, values, color="tab:blue")
    axis.set_title(title)
    axis.set_xlabel("Time [s]")
    axis.set_ylabel(y_label)
    axis.grid(True)

    figure.tight_layout()
    figure.savefig(file_path, dpi=400)
    plt.close(figure)


def save_scalar_step_plot(
        file_path: Path,
        time_values: np.ndarray,
        values_triplet: Tuple[np.ndarray, np.ndarray, np.ndarray],
        title: str,
        y_label: str,
        legend_prefix: str,
) -> None:
    """
    Save one stepped three-trace scalar plot.

    :param file_path: Output image path.
    :type file_path: Path
    :param time_values: Time vector.
    :type time_values: np.ndarray
    :param values_triplet: Scalar trajectories.
    :type values_triplet: Tuple[np.ndarray, np.ndarray, np.ndarray]
    :param title: Figure title.
    :type title: str
    :param y_label: Y-axis label.
    :type y_label: str
    :param legend_prefix: Legend prefix.
    :type legend_prefix: str
    :return: None.
    :rtype: None
    """
    figure = plt.figure(figsize=(12, 5))
    axis = figure.add_subplot(1, 1, 1)
    axis.step(time_values, values_triplet[0], where="post", label=f"{legend_prefix} A", color="tab:blue")
    axis.step(time_values, values_triplet[1], where="post", label=f"{legend_prefix} B", color="tab:red")
    axis.step(time_values, values_triplet[2], where="post", label=f"{legend_prefix} C", color="tab:green")
    axis.set_title(title)
    axis.set_xlabel("Time [s]")
    axis.set_ylabel(y_label)
    axis.grid(True)
    axis.legend(loc="best")

    figure.tight_layout()
    figure.savefig(file_path, dpi=400)
    plt.close(figure)


def extract_three_phase_matrix(problem: Any, y_values: np.ndarray, variable_triplet: Sequence[Any]) -> np.ndarray:
    """
    Extract one ``(n_time, 3)`` matrix from three solver variables.

    :param problem: EMT problem with ``get_var_idx``.
    :type problem: Any
    :param y_values: State trajectory.
    :type y_values: np.ndarray
    :param variable_triplet: Three symbolic variables.
    :type variable_triplet: Sequence[Any]
    :return: Extracted three-phase matrix.
    :rtype: np.ndarray
    """
    matrix: np.ndarray = np.zeros((y_values.shape[0], 3), dtype=np.float64)
    phase_index: int = 0

    while phase_index < 3:
        matrix[:, phase_index] = y_values[:, problem.get_var_idx(variable_triplet[phase_index])]
        phase_index += 1

    return matrix
