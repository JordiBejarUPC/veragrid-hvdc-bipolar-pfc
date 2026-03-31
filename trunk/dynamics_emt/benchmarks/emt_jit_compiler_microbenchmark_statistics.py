import json
import statistics
from pathlib import Path
from typing import Dict, List

from trunk.dynamics_emt.benchmarks.emt_jit_compiler_microbenchmark import (
    CompilerBenchmarkCase,
    CompilerMicrobenchmarkRow,
    build_case_label,
    get_results_directory,
    run_compiler_microbenchmark_suite,
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


def run_repeated_compiler_microbenchmark(repetitions: int) -> List[Dict[str, object]]:
    """
    Run the compiler microbenchmark repeatedly and aggregate the metrics.

    :param repetitions: Number of repetitions.
    :type repetitions: int
    :return: Aggregated metric rows.
    :rtype: List[Dict[str, object]]
    """
    cases: List[CompilerBenchmarkCase] = [
        CompilerBenchmarkCase.ZIPLOAD,
        CompilerBenchmarkCase.RLOAD,
        CompilerBenchmarkCase.EVENT,
    ]
    grouped_metrics: Dict[str, Dict[str, List[float]]] = dict()
    repeat_index: int = 0

    while repeat_index < repetitions:
        rows: List[CompilerMicrobenchmarkRow] = run_compiler_microbenchmark_suite(cases)
        row_index: int = 0

        while row_index < len(rows):
            payload: Dict[str, object] = rows[row_index].get_payload()
            case_name: str = str(payload["case"])

            if case_name in grouped_metrics:
                metric_map: Dict[str, List[float]] = grouped_metrics[case_name]
            else:
                metric_map = dict()
                grouped_metrics[case_name] = metric_map

            for metric_name, metric_value in payload.items():
                if isinstance(metric_value, (int, float)):
                    if metric_name in metric_map:
                        pass
                    else:
                        metric_map[metric_name] = list()

                    metric_map[metric_name].append(float(metric_value))
                else:
                    pass

            row_index += 1

        repeat_index += 1

    aggregated_rows: List[Dict[str, object]] = list()

    for case_name in sorted(grouped_metrics.keys()):
        metric_map = grouped_metrics[case_name]
        stats_map: Dict[str, Dict[str, float]] = dict()

        for metric_name, values in metric_map.items():
            stats_map[metric_name] = compute_metric_summary(values)

        aggregated_rows.append(dict(case=build_case_label(case_name), metrics=stats_map))

    return aggregated_rows


def export_repeated_compiler_microbenchmark(aggregated_rows: List[Dict[str, object]], file_stem: str) -> List[Path]:
    """
    Export repeated compiler microbenchmark statistics.

    :param aggregated_rows: Aggregated metric rows.
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

    csv_lines.append(
        "case,residual_source_cse_on_median_s,residual_source_cse_on_stdev_s,residual_cached_source_cse_on_median_s,residual_njit_cse_on_median_s,residual_cached_njit_cse_on_median_s,ad_source_cse_on_median_s,ad_cached_source_cse_on_median_s,ad_njit_cse_on_median_s,ad_cached_njit_cse_on_median_s,matrix_source_total_median_s,matrix_cached_source_total_median_s,matrix_njit_total_median_s,matrix_cached_njit_total_median_s"
    )
    markdown_lines.append(
        "| Case | Residual Src Median [s] | Residual Src Cached [s] | Residual JIT Median [s] | Residual JIT Cached [s] | AD Src Median [s] | AD Src Cached [s] | AD JIT Median [s] | AD JIT Cached [s] | Matrix Src Median [s] | Matrix Src Cached [s] | Matrix JIT Median [s] | Matrix JIT Cached [s] |"
    )
    markdown_lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(aggregated_rows):
        row: Dict[str, object] = aggregated_rows[row_index]
        metrics: Dict[str, Dict[str, float]] = dict(row["metrics"])
        case_label: str = str(row["case"])

        csv_lines.append(
            f"{case_label},{metrics['residual_source_cse_on_s']['median']:.9f},{metrics['residual_source_cse_on_s']['stdev']:.9f},"
            f"{metrics['residual_cached_source_cse_on_s']['median']:.9f},{metrics['residual_njit_cse_on_s']['median']:.9f},"
            f"{metrics['residual_cached_njit_cse_on_s']['median']:.9f},{metrics['ad_source_cse_on_s']['median']:.9f},"
            f"{metrics['ad_cached_source_cse_on_s']['median']:.9f},{metrics['ad_njit_cse_on_s']['median']:.9f},"
            f"{metrics['ad_cached_njit_cse_on_s']['median']:.9f},{metrics['matrix_source_total_s']['median']:.9f},"
            f"{metrics['matrix_cached_source_total_s']['median']:.9f},{metrics['matrix_njit_total_s']['median']:.9f},"
            f"{metrics['matrix_cached_njit_total_s']['median']:.9f}"
        )
        markdown_lines.append(
            f"| {case_label} | {metrics['residual_source_cse_on_s']['median']:.6f} | {metrics['residual_cached_source_cse_on_s']['median']:.6f} | "
            f"{metrics['residual_njit_cse_on_s']['median']:.6f} | {metrics['residual_cached_njit_cse_on_s']['median']:.6f} | "
            f"{metrics['ad_source_cse_on_s']['median']:.6f} | {metrics['ad_cached_source_cse_on_s']['median']:.6f} | "
            f"{metrics['ad_njit_cse_on_s']['median']:.6f} | {metrics['ad_cached_njit_cse_on_s']['median']:.6f} | "
            f"{metrics['matrix_source_total_s']['median']:.6f} | {metrics['matrix_cached_source_total_s']['median']:.6f} | "
            f"{metrics['matrix_njit_total_s']['median']:.6f} | {metrics['matrix_cached_njit_total_s']['median']:.6f} |"
        )
        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(aggregated_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_default_repeated_compiler_microbenchmark(repetitions: int = 3) -> List[Path]:
    """
    Run and export the repeated compiler microbenchmark suite.

    :param repetitions: Number of repetitions.
    :type repetitions: int
    :return: Exported file paths.
    :rtype: List[Path]
    """
    aggregated_rows: List[Dict[str, object]] = run_repeated_compiler_microbenchmark(repetitions)
    return export_repeated_compiler_microbenchmark(aggregated_rows, "emt_jit_compiler_microbenchmark_repeated")
