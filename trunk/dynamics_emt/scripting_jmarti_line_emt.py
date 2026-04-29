from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from VeraGridEngine.enumerations import EmtLineTypes
from trunk.dynamics_emt.support.emt_plot_exports import get_plot_results_directory
from trunk.dynamics_emt.support.jmarti_demo_support import build_metrics_report_lines
from trunk.dynamics_emt.support.jmarti_demo_support import JMartiLineComparisonResults
from trunk.dynamics_emt.support.jmarti_demo_support import get_demo_event_time_s
from trunk.dynamics_emt.support.jmarti_demo_support import run_demo_line_case


def run_jmarti_line_comparison(enable_plots: bool = True) -> JMartiLineComparisonResults:
    """
    Run the minimal Pi/Bergeron/J_Marti EMT comparison demo.

    :param enable_plots: Whether to show matplotlib windows.
    :return: Aggregated comparison results.
    """
    pi_case = run_demo_line_case(EmtLineTypes.PI)
    bergeron_case = run_demo_line_case(EmtLineTypes.Bergeron)
    jmarti_case = run_demo_line_case(EmtLineTypes.J_Marti)
    event_time_s: float = get_demo_event_time_s()
    output_dir: Path = get_plot_results_directory("jmarti_line_emt", "symbolic")
    voltage_png_path: Path = output_dir / "jmarti_line_load_bus_voltage_compare.png"
    current_png_path: Path = output_dir / "jmarti_line_current_compare.png"
    voltage_delta_png_path: Path = output_dir / "jmarti_line_voltage_delta_vs_bergeron.png"
    current_delta_png_path: Path = output_dir / "jmarti_line_current_delta_vs_bergeron.png"
    metrics_txt_path: Path = output_dir / "jmarti_line_vs_bergeron_metrics.txt"
    figure_voltage, voltage_axis = plt.subplots(1, 1, figsize=(10, 5))
    figure_current, current_axis = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    figure_voltage_delta, voltage_delta_axis = plt.subplots(1, 1, figsize=(10, 5))
    figure_current_delta, current_delta_axis = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    pi_voltage_delta: np.ndarray = np.asarray(pi_case.load_v_a - bergeron_case.load_v_a, dtype=np.float64)
    jmarti_voltage_delta: np.ndarray = np.asarray(jmarti_case.load_v_a - bergeron_case.load_v_a, dtype=np.float64)
    pi_current_delta: np.ndarray = np.asarray(pi_case.comparison_i_a - bergeron_case.comparison_i_a, dtype=np.float64)
    jmarti_current_delta: np.ndarray = np.asarray(jmarti_case.comparison_i_a - bergeron_case.comparison_i_a, dtype=np.float64)
    pi_load_current_delta: np.ndarray = np.asarray(pi_case.load_i_a - bergeron_case.load_i_a, dtype=np.float64)
    jmarti_load_current_delta: np.ndarray = np.asarray(jmarti_case.load_i_a - bergeron_case.load_i_a, dtype=np.float64)

    voltage_axis.plot(pi_case.time, pi_case.load_v_a, label="Pi", color="tab:blue")
    voltage_axis.plot(bergeron_case.time, bergeron_case.load_v_a, label="Bergeron", color="tab:orange")
    voltage_axis.plot(jmarti_case.time, jmarti_case.load_v_a, label="J_Marti", color="tab:green")
    voltage_axis.grid(True)
    voltage_axis.legend()
    voltage_axis.set_xlabel("Time [s]")
    voltage_axis.set_ylabel("Voltage [pu inst]")
    voltage_axis.set_title("Load-Bus Phase-A Voltage Comparison")
    voltage_axis.axvline(event_time_s, color="black", linestyle="--", linewidth=1.0, label="Source step")
    figure_voltage.tight_layout()
    figure_voltage.savefig(voltage_png_path, dpi=200, bbox_inches="tight")

    current_axis[0].plot(pi_case.time, pi_case.comparison_i_a, label="Pi", color="tab:blue")
    current_axis[0].plot(bergeron_case.time, bergeron_case.comparison_i_a, label="Bergeron", color="tab:orange")
    current_axis[0].plot(jmarti_case.time, jmarti_case.comparison_i_a, label="J_Marti", color="tab:green")
    current_axis[0].grid(True)
    current_axis[0].legend()
    current_axis[0].set_ylabel("Current [pu inst]")
    current_axis[0].set_title("Comparable Phase-A Current Trace")
    current_axis[0].axvline(event_time_s, color="black", linestyle="--", linewidth=1.0)

    current_axis[1].plot(pi_case.time, pi_case.load_i_a, label="Pi", color="tab:blue")
    current_axis[1].plot(bergeron_case.time, bergeron_case.load_i_a, label="Bergeron", color="tab:orange")
    current_axis[1].plot(jmarti_case.time, jmarti_case.load_i_a, label="J_Marti", color="tab:green")
    current_axis[1].grid(True)
    current_axis[1].legend()
    current_axis[1].set_xlabel("Time [s]")
    current_axis[1].set_ylabel("Load i_A [pu inst]")
    current_axis[1].set_title("Load Phase-A Current")
    current_axis[1].axvline(event_time_s, color="black", linestyle="--", linewidth=1.0)
    figure_current.tight_layout()
    figure_current.savefig(current_png_path, dpi=200, bbox_inches="tight")

    voltage_delta_axis.plot(bergeron_case.time, pi_voltage_delta, label="Pi - Bergeron", color="tab:blue")
    voltage_delta_axis.plot(bergeron_case.time, jmarti_voltage_delta, label="J_Marti - Bergeron", color="tab:green")
    voltage_delta_axis.axvline(event_time_s, color="black", linestyle="--", linewidth=1.0)
    voltage_delta_axis.grid(True)
    voltage_delta_axis.legend()
    voltage_delta_axis.set_xlabel("Time [s]")
    voltage_delta_axis.set_ylabel("Delta V_A [pu inst]")
    voltage_delta_axis.set_title("Load-Bus Phase-A Voltage Difference vs Bergeron")
    figure_voltage_delta.tight_layout()
    figure_voltage_delta.savefig(voltage_delta_png_path, dpi=200, bbox_inches="tight")

    current_delta_axis[0].plot(bergeron_case.time, pi_current_delta, label="Pi - Bergeron", color="tab:blue")
    current_delta_axis[0].plot(bergeron_case.time, jmarti_current_delta, label="J_Marti - Bergeron", color="tab:green")
    current_delta_axis[0].axvline(event_time_s, color="black", linestyle="--", linewidth=1.0)
    current_delta_axis[0].grid(True)
    current_delta_axis[0].legend()
    current_delta_axis[0].set_ylabel("Delta i_A [pu inst]")
    current_delta_axis[0].set_title("Comparable Phase-A Current Difference vs Bergeron")

    current_delta_axis[1].plot(bergeron_case.time, pi_load_current_delta, label="Pi - Bergeron", color="tab:blue")
    current_delta_axis[1].plot(bergeron_case.time, jmarti_load_current_delta, label="J_Marti - Bergeron", color="tab:green")
    current_delta_axis[1].axvline(event_time_s, color="black", linestyle="--", linewidth=1.0)
    current_delta_axis[1].grid(True)
    current_delta_axis[1].legend()
    current_delta_axis[1].set_xlabel("Time [s]")
    current_delta_axis[1].set_ylabel("Delta load i_A [pu inst]")
    current_delta_axis[1].set_title("Load Phase-A Current Difference vs Bergeron")
    figure_current_delta.tight_layout()
    figure_current_delta.savefig(current_delta_png_path, dpi=200, bbox_inches="tight")

    results = JMartiLineComparisonResults(
        pi_case=pi_case,
        bergeron_case=bergeron_case,
        jmarti_case=jmarti_case,
        event_time_s=event_time_s,
        voltage_png_path=voltage_png_path,
        current_png_path=current_png_path,
        voltage_delta_png_path=voltage_delta_png_path,
        current_delta_png_path=current_delta_png_path,
        metrics_txt_path=metrics_txt_path,
    )
    metrics_txt_path.write_text("\n".join(build_metrics_report_lines(results)), encoding="utf-8")

    if enable_plots:
        plt.show()
    else:
        plt.close(figure_voltage)
        plt.close(figure_current)
        plt.close(figure_voltage_delta)
        plt.close(figure_current_delta)

    return results


if __name__ == "__main__":
    run_jmarti_line_comparison(enable_plots=True)
