from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Dict, List, Tuple

from trunk.dynamics_emt.benchmarks.emt_sparse_backend_benchmark import (
    SparseBackendBenchmarkResult,
    SparseBenchmarkProfile,
    benchmark_sparse_backends,
    get_results_directory,
)


def compute_metric_summary(values: List[float]) -> Dict[str, float]:
    """
    Compute count, mean, median and population standard deviation.

    :param values: Metric samples.
    :type values: List[float]
    :return: Metric summary.
    :rtype: Dict[str, float]
    """
    if len(values) == 0:
        return dict(count=0.0, mean=float("nan"), median=float("nan"), stdev=float("nan"))
    else:
        pass

    if len(values) == 1:
        stdev_value: float = 0.0
    else:
        stdev_value = float(statistics.pstdev(values))

    return dict(
        count=float(len(values)),
        mean=float(statistics.fmean(values)),
        median=float(statistics.median(values)),
        stdev=stdev_value,
    )


def run_repeated_sparse_backend_benchmark(profile: SparseBenchmarkProfile, repetitions: int) -> List[Dict[str, object]]:
    """
    Run the sparse backend benchmark repeatedly and aggregate by case/solver/sparse backend.

    :param profile: Benchmark profile.
    :type profile: SparseBenchmarkProfile
    :param repetitions: Number of repetitions.
    :type repetitions: int
    :return: Aggregated metric rows.
    :rtype: List[Dict[str, object]]
    """
    grouped_values: Dict[Tuple[str, str, str], Dict[str, List[float]]] = dict()
    repeat_index: int = 0

    while repeat_index < repetitions:
        rows: List[SparseBackendBenchmarkResult] = benchmark_sparse_backends(profile)
        row_index: int = 0

        while row_index < len(rows):
            payload: Dict[str, object] = rows[row_index].get_payload()
            grouping_key: Tuple[str, str, str] = (
                str(payload["case"]),
                str(payload["solver_family"]),
                str(payload["sparse_solver"]),
            )

            if grouping_key in grouped_values:
                metric_map: Dict[str, List[float]] = grouped_values[grouping_key]
            else:
                metric_map = dict()
                grouped_values[grouping_key] = metric_map

            for metric_name in ["solver_build_s", "simulate_s", "solver_total_s", "loop_s"]:
                if metric_name in metric_map:
                    pass
                else:
                    metric_map[metric_name] = list()

                metric_map[metric_name].append(float(payload[metric_name]))

            row_index += 1

        repeat_index += 1

    aggregated_rows: List[Dict[str, object]] = list()

    for grouping_key in sorted(grouped_values.keys()):
        metric_map = grouped_values[grouping_key]
        aggregated_rows.append(
            dict(
                case=grouping_key[0],
                solver_family=grouping_key[1],
                sparse_solver=grouping_key[2],
                solver_build_s=compute_metric_summary(metric_map["solver_build_s"]),
                simulate_s=compute_metric_summary(metric_map["simulate_s"]),
                solver_total_s=compute_metric_summary(metric_map["solver_total_s"]),
                loop_s=compute_metric_summary(metric_map["loop_s"]),
            )
        )

    return aggregated_rows


def export_repeated_sparse_backend_benchmark(aggregated_rows: List[Dict[str, object]], file_stem: str) -> List[Path]:
    """
    Export the repeated sparse backend benchmark summary.

    :param aggregated_rows: Aggregated benchmark rows.
    :type aggregated_rows: List[Dict[str, object]]
    :param file_stem: Output file stem without extension.
    :type file_stem: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_results_directory()
    csv_path: Path = output_dir / f"{file_stem}.csv"
    json_path: Path = output_dir / f"{file_stem}.json"
    markdown_path: Path = output_dir / f"{file_stem}.md"
    csv_lines: List[str] = list()
    markdown_lines: List[str] = list()
    row_index: int = 0

    csv_lines.append("case,solver_family,sparse_solver,build_median_s,build_stdev_s,sim_median_s,sim_stdev_s,total_median_s,loop_median_s")
    markdown_lines.append("| Case | Solver Family | Sparse Solver | Build Median [s] | Build Stdev [s] | Sim Median [s] | Sim Stdev [s] | Total Median [s] | Loop Median [s] |")
    markdown_lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(aggregated_rows):
        row: Dict[str, object] = aggregated_rows[row_index]
        build_stats: Dict[str, float] = dict(row["solver_build_s"])
        sim_stats: Dict[str, float] = dict(row["simulate_s"])
        total_stats: Dict[str, float] = dict(row["solver_total_s"])
        loop_stats: Dict[str, float] = dict(row["loop_s"])

        csv_lines.append(
            f"{row['case']},{row['solver_family']},{row['sparse_solver']},"
            f"{build_stats['median']:.9f},{build_stats['stdev']:.9f},"
            f"{sim_stats['median']:.9f},{sim_stats['stdev']:.9f},"
            f"{total_stats['median']:.9f},{loop_stats['median']:.9f}"
        )
        markdown_lines.append(
            f"| {row['case']} | {row['solver_family']} | {row['sparse_solver']} | {build_stats['median']:.6f} | {build_stats['stdev']:.6f} | "
            f"{sim_stats['median']:.6f} | {sim_stats['stdev']:.6f} | {total_stats['median']:.6f} | {loop_stats['median']:.6f} |"
        )
        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(aggregated_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_default_repeated_sparse_backend_paper_long(repetitions: int = 3) -> List[Path]:
    """
    Run and export the repeated paper-long sparse backend benchmark.

    :param repetitions: Number of repetitions.
    :type repetitions: int
    :return: Exported file paths.
    :rtype: List[Path]
    """
    aggregated_rows: List[Dict[str, object]] = run_repeated_sparse_backend_benchmark(
        SparseBenchmarkProfile.PaperLong,
        repetitions,
    )
    return export_repeated_sparse_backend_benchmark(aggregated_rows, "emt_sparse_backend_ab_paper_long_repeated")
