"""
Run the best current NR parity test for ACTIVSg2000.

The current best-performing path on this case is the reduced balanced-subspace
artifact, not the full-query order-2 subset correction. This script therefore
tests the reduced artifact against Newton-Raphson and exits non-zero on parity
failure.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from mdhelm import create_mdhelm_inputs
from mdhelm import VeraGridQueryCaseData
from mdhelm import load_multicircuit_from_file
from mdhelm_pv_activsg2000_local_artifact import MDHEMReducedSubspacePVArtifact
from mdhelm_pv_activsg2000_local_artifact import ReducedSubspaceMetrics
from mdhelm_pv_activsg2000_local_artifact import ReducedSubspaceScenario
from mdhelm_pv_activsg2000_local_artifact import build_reduced_subspace_artifact_from_case
from mdhelm_pv_activsg2000_local_artifact import create_coordinate_scenarios
from mdhelm_pv_activsg2000_local_artifact import create_nr_seed_results
from mdhelm_pv_activsg2000_local_artifact import evaluate_coordinate_scenario
from mdhelm_pv_activsg2000_local_artifact import load_reduced_subspace_artifact
from mdhelm_pv_activsg2000_local_artifact import save_reduced_subspace_artifact
from mdhelm_pv_case14_fire_test import DeviceBusMapping
from mdhelm_pv_case14_fire_test import build_device_bus_mapping

if TYPE_CHECKING:
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit


def resolve_case_path() -> Path:
    """
    Resolve the local ACTIVSg2000 MATPOWER case path.

    Returns
    -------
    pathlib.Path
        Existing MATPOWER case path.
    """
    case_path: Path = Path(__file__).resolve().with_name("case_ACTIVSg2000.matpower")

    if case_path.exists():
        return case_path
    else:
        raise FileNotFoundError(f"Missing MATPOWER case file: {case_path}")


def resolve_artifact_path() -> Path:
    """
    Resolve the reduced artifact cache path.

    Returns
    -------
    pathlib.Path
        Reduced artifact path.
    """
    return Path(__file__).resolve().with_name("mdhelm_pv_activsg2000_local_artifact.npz")


def resolve_report_path() -> Path:
    """
    Resolve the parity markdown report path.

    Returns
    -------
    pathlib.Path
        Markdown report path.
    """
    return Path(__file__).resolve().with_name("case_ACTIVSg2000_parity_test_report.md")


def resolve_plot_path() -> Path:
    """
    Resolve the parity graphic path.

    Returns
    -------
    pathlib.Path
        PNG plot path.
    """
    return Path(__file__).resolve().with_name("case_ACTIVSg2000_parity_test_plot.png")


def resolve_table_path() -> Path:
    """
    Resolve the parity CSV table path.

    Returns
    -------
    pathlib.Path
        CSV table path.
    """
    return Path(__file__).resolve().with_name("case_ACTIVSg2000_parity_test_table.csv")


def calculate_passed_count(metrics_list: list[ReducedSubspaceMetrics]) -> int:
    """
    Count the passed scenarios.

    Parameters
    ----------
    metrics_list:
        Scenario metrics.

    Returns
    -------
    int
        Number of passed scenarios.
    """
    passed_count: int = 0
    metrics: ReducedSubspaceMetrics

    for metrics in metrics_list:
        if metrics.passed:
            passed_count = passed_count + 1
        else:
            passed_count = passed_count

    return passed_count


def calculate_worst_metric(metrics_list: list[ReducedSubspaceMetrics], metric_name: str) -> float:
    """
    Calculate the worst value of one metrics field.

    Parameters
    ----------
    metrics_list:
        Scenario metrics.
    metric_name:
        Supported metric field name.

    Returns
    -------
    float
        Worst metric value.
    """
    worst_value: float = 0.0
    metrics: ReducedSubspaceMetrics

    for metrics in metrics_list:
        value: float

        if metric_name == "injection_write_error":
            value = metrics.injection_write_error
        else:
            if metric_name == "nr_error":
                value = metrics.nr_error
            else:
                if metric_name == "artifact_error":
                    value = metrics.artifact_error
                else:
                    if metric_name == "max_voltage_diff":
                        value = metrics.max_voltage_diff
                    else:
                        if metric_name == "max_flow_diff_mva":
                            value = metrics.max_flow_diff_mva
                        else:
                            if metric_name == "max_loading_diff":
                                value = metrics.max_loading_diff
                            else:
                                raise ValueError(f"Unsupported metric field: {metric_name}")

        if value > worst_value:
            worst_value = value
        else:
            worst_value = worst_value

    return worst_value


def calculate_percentile_metric(
    metrics_list: list[ReducedSubspaceMetrics],
    metric_name: str,
    percentile: float,
) -> float:
    """
    Calculate one percentile of a metrics field.

    Parameters
    ----------
    metrics_list:
        Scenario metrics.
    metric_name:
        Supported metric field name.
    percentile:
        Requested percentile in ``[0, 100]``.

    Returns
    -------
    float
        Percentile value.
    """
    values: list[float] = list()
    metrics: ReducedSubspaceMetrics

    for metrics in metrics_list:
        value: float

        if metric_name == "artifact_error":
            value = metrics.artifact_error
        else:
            if metric_name == "max_voltage_diff":
                value = metrics.max_voltage_diff
            else:
                if metric_name == "max_flow_diff_mva":
                    value = metrics.max_flow_diff_mva
                else:
                    if metric_name == "max_loading_diff":
                        value = metrics.max_loading_diff
                    else:
                        raise ValueError(f"Unsupported metric field: {metric_name}")

        values.append(value)

    if len(values) > 0:
        return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))
    else:
        raise ValueError("metrics_list must not be empty")


def write_metrics_table(
    table_path: Path,
    scenarios: list[ReducedSubspaceScenario],
    metrics_list: list[ReducedSubspaceMetrics],
) -> None:
    """
    Write the full parity table as CSV.

    Parameters
    ----------
    table_path:
        Output CSV path.
    scenarios:
        Scenario list.
    metrics_list:
        Scenario metrics.

    Returns
    -------
    None
        The CSV file is written to disk.
    """
    with table_path.open("w", encoding="utf-8", newline="") as file_pointer:
        writer: csv.writer = csv.writer(file_pointer)
        writer.writerow(
            (
                "scenario",
                "active_delta_sum",
                "reactive_delta_sum",
                "passed",
                "nr_converged",
                "artifact_converged",
                "injection_write_error",
                "nr_error",
                "artifact_error",
                "max_voltage_diff",
                "max_flow_diff_mva",
                "max_loading_diff",
            )
        )
        scenario_index: int

        for scenario_index in range(len(scenarios)):
            scenario: ReducedSubspaceScenario = scenarios[scenario_index]
            metrics: ReducedSubspaceMetrics = metrics_list[scenario_index]
            writer.writerow(
                (
                    scenario.name,
                    f"{scenario.active_delta_sum:.16e}",
                    f"{scenario.reactive_delta_sum:.16e}",
                    str(metrics.passed),
                    str(metrics.nr_converged),
                    str(metrics.artifact_converged),
                    f"{metrics.injection_write_error:.16e}",
                    f"{metrics.nr_error:.16e}",
                    f"{metrics.artifact_error:.16e}",
                    f"{metrics.max_voltage_diff:.16e}",
                    f"{metrics.max_flow_diff_mva:.16e}",
                    f"{metrics.max_loading_diff:.16e}",
                )
            )


def create_parity_plot(plot_path: Path, metrics_list: list[ReducedSubspaceMetrics]) -> None:
    """
    Create the parity summary graphic.

    Parameters
    ----------
    plot_path:
        Output PNG path.
    metrics_list:
        Scenario metrics.

    Returns
    -------
    None
        The PNG file is written to disk.
    """
    artifact_error: np.ndarray = np.asarray(
        [metrics.artifact_error for metrics in metrics_list],
        dtype=np.float64,
    )
    voltage_error: np.ndarray = np.asarray(
        [metrics.max_voltage_diff for metrics in metrics_list],
        dtype=np.float64,
    )
    flow_error: np.ndarray = np.asarray(
        [metrics.max_flow_diff_mva for metrics in metrics_list],
        dtype=np.float64,
    )
    loading_error: np.ndarray = np.asarray(
        [metrics.max_loading_diff for metrics in metrics_list],
        dtype=np.float64,
    )
    scenario_index: np.ndarray = np.arange(artifact_error.size, dtype=np.int64)
    passed_mask: np.ndarray = np.asarray([metrics.passed for metrics in metrics_list], dtype=bool)
    minimum_positive_value: float = 1.0e-16
    artifact_error = np.maximum(artifact_error, minimum_positive_value)
    voltage_error = np.maximum(voltage_error, minimum_positive_value)
    flow_error = np.maximum(flow_error, minimum_positive_value)
    loading_error = np.maximum(loading_error, minimum_positive_value)
    figure: plt.Figure
    axes: np.ndarray
    figure, axes = plt.subplots(2, 2, figsize=(13.0, 9.0), constrained_layout=True)

    # The top row shows the metric spread across the scenario batch so the user
    # can see both drift and outliers instead of only one worst-case scalar.
    axes[0, 0].plot(scenario_index, voltage_error, color="#0b6e4f", linewidth=1.4)
    axes[0, 0].set_title("Voltage Error by Scenario")
    axes[0, 0].set_xlabel("Scenario index")
    axes[0, 0].set_ylabel("max |dV| p.u.")
    axes[0, 0].grid(True, alpha=0.25)

    axes[0, 1].plot(scenario_index, flow_error, color="#a23b72", linewidth=1.4)
    axes[0, 1].set_title("Branch Flow Error by Scenario")
    axes[0, 1].set_xlabel("Scenario index")
    axes[0, 1].set_ylabel("max |dSf| MVA")
    axes[0, 1].grid(True, alpha=0.25)

    # The bottom-left panel summarizes the error distributions on log scales so
    # the tail behavior is readable even when the base case error is tiny.
    axes[1, 0].hist(voltage_error, bins=20, alpha=0.70, color="#0b6e4f", label="Voltage")
    axes[1, 0].hist(flow_error, bins=20, alpha=0.55, color="#a23b72", label="Flow")
    axes[1, 0].set_title("Error Distribution")
    axes[1, 0].set_xlabel("Error magnitude")
    axes[1, 0].set_ylabel("Count")
    axes[1, 0].set_xscale("log")
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.25)

    # The bottom-right panel ties pass/fail to mismatch and loading error.
    axes[1, 1].scatter(
        artifact_error[passed_mask],
        loading_error[passed_mask],
        color="#0b6e4f",
        label="Passed",
        s=18,
        alpha=0.75,
    )
    axes[1, 1].scatter(
        artifact_error[np.logical_not(passed_mask)],
        loading_error[np.logical_not(passed_mask)],
        color="#a23b72",
        label="Failed",
        s=22,
        alpha=0.85,
    )
    axes[1, 1].set_title("Mismatch vs Loading Error")
    axes[1, 1].set_xlabel("Artifact mismatch norm")
    axes[1, 1].set_ylabel("max loading diff")
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_yscale("log")
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.25)

    figure.savefig(plot_path, dpi=160)
    plt.close(figure)


def build_parity_report(
    case_path: Path,
    artifact_path: Path,
    plot_path: Path,
    table_path: Path,
    n_dimensions: int,
    max_order: int,
    coordinate_radius: float,
    germ_error: float,
    scenarios: list[ReducedSubspaceScenario],
    metrics_list: list[ReducedSubspaceMetrics],
) -> str:
    """
    Build the parity markdown report.

    Parameters
    ----------
    case_path:
        MATPOWER case path.
    artifact_path:
        Reduced artifact path.
    plot_path:
        Parity graphic path.
    table_path:
        Parity CSV table path.
    n_dimensions:
        Reduced coordinate count.
    max_order:
        Maximum polynomial order.
    coordinate_radius:
        Scenario coordinate radius.
    germ_error:
        Builder germ error.
    scenarios:
        Scenario list.
    metrics_list:
        Scenario metrics.

    Returns
    -------
    str
        Markdown report text.
    """
    passed_count: int = calculate_passed_count(metrics_list=metrics_list)
    worst_write_error: float = calculate_worst_metric(metrics_list=metrics_list, metric_name="injection_write_error")
    worst_nr_error: float = calculate_worst_metric(metrics_list=metrics_list, metric_name="nr_error")
    worst_artifact_error: float = calculate_worst_metric(metrics_list=metrics_list, metric_name="artifact_error")
    worst_voltage_diff: float = calculate_worst_metric(metrics_list=metrics_list, metric_name="max_voltage_diff")
    worst_flow_diff_mva: float = calculate_worst_metric(metrics_list=metrics_list, metric_name="max_flow_diff_mva")
    worst_loading_diff: float = calculate_worst_metric(metrics_list=metrics_list, metric_name="max_loading_diff")
    p95_voltage_diff: float = calculate_percentile_metric(
        metrics_list=metrics_list,
        metric_name="max_voltage_diff",
        percentile=95.0,
    )
    p95_flow_diff_mva: float = calculate_percentile_metric(
        metrics_list=metrics_list,
        metric_name="max_flow_diff_mva",
        percentile=95.0,
    )
    p95_loading_diff: float = calculate_percentile_metric(
        metrics_list=metrics_list,
        metric_name="max_loading_diff",
        percentile=95.0,
    )
    lines: list[str] = list()
    lines.append("# ACTIVSg2000 NR parity test")
    lines.append("")
    lines.append(f"- Timestamp: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- Case: `{case_path}`")
    lines.append(f"- Artifact: `{artifact_path}`")
    lines.append(f"- Graphic: `{plot_path}`")
    lines.append(f"- Table: `{table_path}`")
    lines.append("- Model: `reduced balanced-subspace MDHEM artifact`")
    lines.append("- NR role: `seed + external parity reference only`")
    lines.append(f"- Reduced dimensions: `{n_dimensions}`")
    lines.append(f"- Maximum order: `{max_order}`")
    lines.append(f"- Coordinate radius: `{coordinate_radius:.4f}`")
    lines.append(f"- Germ error: `{germ_error:.6e}`")
    lines.append(f"- Passed scenarios: `{passed_count}/{len(metrics_list)}`")
    lines.append(f"- Worst write error: `{worst_write_error:.6e}` p.u.")
    lines.append(f"- Worst NR error: `{worst_nr_error:.6e}`")
    lines.append(f"- Worst artifact error: `{worst_artifact_error:.6e}`")
    lines.append(f"- Worst voltage diff: `{worst_voltage_diff:.6e}` p.u.")
    lines.append(f"- Worst branch flow diff: `{worst_flow_diff_mva:.6e}` MVA")
    lines.append(f"- Worst loading diff: `{worst_loading_diff:.6e}`")
    lines.append(f"- P95 voltage diff: `{p95_voltage_diff:.6e}` p.u.")
    lines.append(f"- P95 branch flow diff: `{p95_flow_diff_mva:.6e}` MVA")
    lines.append(f"- P95 loading diff: `{p95_loading_diff:.6e}`")
    lines.append("")
    lines.append("## Graphic")
    lines.append("")
    lines.append(f"![ACTIVSg2000 parity plot]({plot_path.name})")
    lines.append("")
    lines.append("## Scenario metrics")
    lines.append("")
    lines.append("| Scenario | dP sum | dQ sum | Passed | NR converged | Artifact converged | Artifact err | Voltage diff | Flow diff MVA | Loading diff |")
    lines.append("| --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |")
    scenario_index: int

    for scenario_index in range(len(scenarios)):
        scenario: ReducedSubspaceScenario = scenarios[scenario_index]
        metrics: ReducedSubspaceMetrics = metrics_list[scenario_index]
        lines.append(
            "| "
            f"{scenario.name} | "
            f"{scenario.active_delta_sum:+.6e} | "
            f"{scenario.reactive_delta_sum:+.6e} | "
            f"{metrics.passed} | "
            f"{metrics.nr_converged} | "
            f"{metrics.artifact_converged} | "
            f"{metrics.artifact_error:.6e} | "
            f"{metrics.max_voltage_diff:.6e} | "
            f"{metrics.max_flow_diff_mva:.6e} | "
            f"{metrics.max_loading_diff:.6e} |"
        )

    lines.append("")
    return "\n".join(lines)


def run_activsg2000_parity_test() -> None:
    """
    Run the ACTIVSg2000 NR parity test.

    Returns
    -------
    None
        The report is printed, written to disk and the process exits non-zero
        when parity fails.
    """
    case_path: Path = resolve_case_path()
    artifact_path: Path = resolve_artifact_path()
    report_path: Path = resolve_report_path()
    plot_path: Path = resolve_plot_path()
    table_path: Path = resolve_table_path()
    max_order: int = 4
    n_dimensions: int = 6
    basis_seed: int = 2000
    scenario_seed: int = 2001
    scenario_count: int = 100
    artifact_tolerance: float = 1.0e-6
    voltage_threshold: float = 1.0e-3
    branch_flow_threshold_mva: float = 1.0
    loading_threshold: float = 2.0e-3
    injection_write_threshold: float = 2.0e-6
    rebuild_artifact: bool = False
    base_grid: "MultiCircuit" = load_multicircuit_from_file(matpower_path=case_path)
    case_data: VeraGridQueryCaseData
    artifact: MDHEMReducedSubspacePVArtifact
    germ_error: float

    if artifact_path.exists() and rebuild_artifact is False:
        case_data = create_mdhelm_inputs(grid=base_grid)
        artifact = load_reduced_subspace_artifact(path=artifact_path)
        germ_error = 0.0
    else:
        nr_seed_results = create_nr_seed_results(grid=base_grid)
        case_data, artifact, germ_error = build_reduced_subspace_artifact_from_case(
            grid=base_grid,
            max_order=max_order,
            n_dimensions=n_dimensions,
            random_seed=basis_seed,
            germ_seed_results=nr_seed_results,
        )
        save_reduced_subspace_artifact(path=artifact_path, artifact=artifact)

    mapping: DeviceBusMapping = build_device_bus_mapping(grid=base_grid, case_data=case_data)
    coordinate_radius: float = artifact.get_recommended_coordinate_radius()
    scenarios: list[ReducedSubspaceScenario] = create_coordinate_scenarios(
        artifact=artifact,
        case_data=case_data,
        mapping=mapping,
        scenario_count=scenario_count,
        random_seed=scenario_seed,
        coordinate_radius=coordinate_radius,
    )
    metrics_list: list[ReducedSubspaceMetrics] = list()
    scenario: ReducedSubspaceScenario

    for scenario in scenarios:
        metrics_list.append(
            evaluate_coordinate_scenario(
                base_grid=base_grid,
                case_data=case_data,
                mapping=mapping,
                artifact=artifact,
                scenario=scenario,
                artifact_tolerance=artifact_tolerance,
                voltage_threshold=voltage_threshold,
                branch_flow_threshold_mva=branch_flow_threshold_mva,
                loading_threshold=loading_threshold,
                injection_write_threshold=injection_write_threshold,
            )
        )

    write_metrics_table(
        table_path=table_path,
        scenarios=scenarios,
        metrics_list=metrics_list,
    )
    create_parity_plot(plot_path=plot_path, metrics_list=metrics_list)
    report_text: str = build_parity_report(
        case_path=case_path,
        artifact_path=artifact_path,
        plot_path=plot_path,
        table_path=table_path,
        n_dimensions=n_dimensions,
        max_order=max_order,
        coordinate_radius=coordinate_radius,
        germ_error=germ_error,
        scenarios=scenarios,
        metrics_list=metrics_list,
    )
    report_path.write_text(report_text, encoding="utf-8")
    print(report_text)
    print(f"\nSaved report to {report_path}")
    print(f"Saved plot to {plot_path}")
    print(f"Saved table to {table_path}")

    if calculate_passed_count(metrics_list=metrics_list) == len(metrics_list):
        pass
    else:
        raise SystemExit(1)


if __name__ == "__main__":
    run_activsg2000_parity_test()
