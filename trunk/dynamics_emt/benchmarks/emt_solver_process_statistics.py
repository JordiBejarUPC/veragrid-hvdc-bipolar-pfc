import json
import statistics
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from VeraGrid.trunk.dynamics_emt.benchmarks.emt_solver_process_benchmark import (
    BenchmarkCase,
    BenchmarkMode,
    BenchmarkProfile,
    ProcessBenchmarkRow,
    run_process_cold_suite,
)


class RepeatedProcessSample:
    """
    One raw subprocess benchmark sample with an explicit repetition index.
    """

    __slots__ = ["_repeat_index", "_row"]

    def __init__(self, repeat_index: int, row: ProcessBenchmarkRow) -> None:
        """
        Build one repeated subprocess sample.

        :param repeat_index: Repetition index.
        :type repeat_index: int
        :param row: Process benchmark row.
        :type row: ProcessBenchmarkRow
        :return: None.
        :rtype: None
        """
        self._repeat_index: int = int(repeat_index)
        self._row: ProcessBenchmarkRow = row

    def get_repeat_index(self) -> int:
        """
        Return the repetition index.

        :return: Repetition index.
        :rtype: int
        """
        return self._repeat_index

    def get_row(self) -> ProcessBenchmarkRow:
        """
        Return the underlying process benchmark row.

        :return: Process benchmark row.
        :rtype: ProcessBenchmarkRow
        """
        return self._row


class AggregatedProcessMetricRow:
    """
    Aggregated subprocess statistics for one ``(case, mode, solver)`` tuple.
    """

    __slots__ = ["_case_name", "_mode_name", "_solver_key", "_metric_stats"]

    def __init__(self, case_name: str, mode_name: str, solver_key: str, metric_stats: Dict[str, Dict[str, float]]) -> None:
        """
        Build one aggregated subprocess metric row.

        :param case_name: Benchmark case identifier.
        :type case_name: str
        :param mode_name: Benchmark mode identifier.
        :type mode_name: str
        :param solver_key: Solver identifier.
        :type solver_key: str
        :param metric_stats: Metric summary dictionary.
        :type metric_stats: Dict[str, Dict[str, float]]
        :return: None.
        :rtype: None
        """
        self._case_name: str = case_name
        self._mode_name: str = mode_name
        self._solver_key: str = solver_key
        self._metric_stats: Dict[str, Dict[str, float]] = dict(metric_stats)

    def get_case_name(self) -> str:
        """
        Return the benchmark case identifier.

        :return: Benchmark case identifier.
        :rtype: str
        """
        return self._case_name

    def get_mode_name(self) -> str:
        """
        Return the benchmark mode identifier.

        :return: Benchmark mode identifier.
        :rtype: str
        """
        return self._mode_name

    def get_solver_key(self) -> str:
        """
        Return the solver identifier.

        :return: Solver identifier.
        :rtype: str
        """
        return self._solver_key

    def get_metric_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Return the aggregated metric statistics.

        :return: Aggregated metric statistics.
        :rtype: Dict[str, Dict[str, float]]
        """
        return dict(self._metric_stats)


def get_results_directory() -> Path:
    """
    Return the EMT benchmark-results directory.

    :return: Benchmark-results directory.
    :rtype: Path
    """
    return Path(__file__).resolve().parent / "benchmark_results"


def build_case_label(case_name: str) -> str:
    """
    Convert one internal case identifier into a presentation label.

    :param case_name: Internal case identifier.
    :type case_name: str
    :return: Presentation label.
    :rtype: str
    """
    label_map: Dict[str, str] = dict(
        zipload="ZIPload",
        rload="Rload",
        event="Event",
    )
    mapped_label: str | None = label_map.get(case_name, None)

    if mapped_label is None:
        return case_name
    else:
        return mapped_label


def build_solver_keys() -> List[str]:
    """
    Return the solver identifiers in benchmark order.

    :return: Solver identifiers.
    :rtype: List[str]
    """
    return ["SYMBOLIC", "AD", "VECTORIZED", "COMPILED"]


def build_metric_name_list(mode_name: BenchmarkMode) -> List[str]:
    """
    Return the metric list for one benchmark mode.

    :param mode_name: Benchmark mode.
    :type mode_name: BenchmarkMode
    :return: Metric names.
    :rtype: List[str]
    """
    if mode_name == BenchmarkMode.STANDARD:
        return ["problem_build_s", "solver_init_s", "solver_build_s", "simulate_s", "solver_total_s", "loop_s"]
    else:
        return ["problem_build_s", "solver_init_s", "cold_build_s", "cold_sim_s", "warm_sim_s", "speedup"]


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


def run_repeated_process_suite(
        profile: BenchmarkProfile,
        cases: Sequence[BenchmarkCase],
        modes: Sequence[BenchmarkMode],
        repetitions: int,
) -> List[RepeatedProcessSample]:
    """
    Run a repeated subprocess benchmark suite.

    :param profile: Benchmark profile.
    :type profile: BenchmarkProfile
    :param cases: Benchmark cases.
    :type cases: Sequence[BenchmarkCase]
    :param modes: Benchmark modes.
    :type modes: Sequence[BenchmarkMode]
    :param repetitions: Number of repetitions.
    :type repetitions: int
    :return: Repeated subprocess samples.
    :rtype: List[RepeatedProcessSample]
    """
    samples: List[RepeatedProcessSample] = list()
    repeat_index: int = 0

    while repeat_index < repetitions:
        mode_index: int = 0

        while mode_index < len(modes):
            rows: List[ProcessBenchmarkRow] = run_process_cold_suite(profile, cases, modes[mode_index])
            row_index: int = 0

            while row_index < len(rows):
                samples.append(RepeatedProcessSample(repeat_index=repeat_index, row=rows[row_index]))
                row_index += 1

            mode_index += 1

        repeat_index += 1

    return samples


def export_repeated_raw_samples(samples: List[RepeatedProcessSample], file_stem: str) -> List[Path]:
    """
    Export the raw repeated subprocess samples.

    :param samples: Repeated subprocess samples.
    :type samples: List[RepeatedProcessSample]
    :param file_stem: Output file stem without extension.
    :type file_stem: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_results_directory()
    csv_path: Path = output_dir / f"{file_stem}.csv"
    json_path: Path = output_dir / f"{file_stem}.json"
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    sample_index: int = 0

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_lines.append("repeat,case,mode,solver,payload_json")

    while sample_index < len(samples):
        sample: RepeatedProcessSample = samples[sample_index]
        row: ProcessBenchmarkRow = sample.get_row()
        payload: Dict[str, object] = row.get_payload()
        payload_json: str = json.dumps(payload, separators=(",", ":"))

        escaped_payload_json: str = payload_json.replace('"', '""')
        csv_lines.append(
            f"{sample.get_repeat_index()},{row.get_case_name()},{row.get_mode_name()},{row.get_payload()['solver']},\"{escaped_payload_json}\""
        )
        json_rows.append(
            dict(
                repeat=sample.get_repeat_index(),
                case=row.get_case_name(),
                mode=row.get_mode_name(),
                solver=str(payload["solver"]),
                payload=payload,
            )
        )
        sample_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    return [csv_path, json_path]


def aggregate_repeated_samples(samples: List[RepeatedProcessSample]) -> List[AggregatedProcessMetricRow]:
    """
    Aggregate repeated subprocess samples into metric summaries.

    :param samples: Repeated subprocess samples.
    :type samples: List[RepeatedProcessSample]
    :return: Aggregated metric rows.
    :rtype: List[AggregatedProcessMetricRow]
    """
    grouped_values: Dict[Tuple[str, str, str], Dict[str, List[float]]] = dict()
    sample_index: int = 0

    while sample_index < len(samples):
        sample: RepeatedProcessSample = samples[sample_index]
        row: ProcessBenchmarkRow = sample.get_row()
        payload: Dict[str, object] = row.get_payload()
        grouping_key: Tuple[str, str, str] = (row.get_case_name(), row.get_mode_name(), str(payload["solver"]))
        metric_names: List[str] = build_metric_name_list(BenchmarkMode(row.get_mode_name()))
        metric_index: int = 0

        if grouping_key in grouped_values:
            metric_values: Dict[str, List[float]] = grouped_values[grouping_key]
        else:
            metric_values = dict()
            grouped_values[grouping_key] = metric_values

        while metric_index < len(metric_names):
            metric_name: str = metric_names[metric_index]

            if metric_name in metric_values:
                pass
            else:
                metric_values[metric_name] = list()

            metric_values[metric_name].append(float(payload[metric_name]))
            metric_index += 1

        sample_index += 1

    sorted_keys: List[Tuple[str, str, str]] = sorted(grouped_values.keys())
    rows: List[AggregatedProcessMetricRow] = list()
    key_index: int = 0

    while key_index < len(sorted_keys):
        grouping_key = sorted_keys[key_index]
        metric_values = grouped_values[grouping_key]
        metric_stats: Dict[str, Dict[str, float]] = dict()

        for metric_name, values in metric_values.items():
            metric_stats[metric_name] = compute_metric_summary(values)

        rows.append(
            AggregatedProcessMetricRow(
                case_name=grouping_key[0],
                mode_name=grouping_key[1],
                solver_key=grouping_key[2],
                metric_stats=metric_stats,
            )
        )
        key_index += 1

    return rows


def filter_aggregated_rows(rows: List[AggregatedProcessMetricRow], mode_name: str) -> List[AggregatedProcessMetricRow]:
    """
    Filter aggregated metric rows by benchmark mode.

    :param rows: Aggregated metric rows.
    :type rows: List[AggregatedProcessMetricRow]
    :param mode_name: Requested mode identifier.
    :type mode_name: str
    :return: Filtered rows.
    :rtype: List[AggregatedProcessMetricRow]
    """
    filtered_rows: List[AggregatedProcessMetricRow] = list()
    row_index: int = 0

    while row_index < len(rows):
        row: AggregatedProcessMetricRow = rows[row_index]

        if row.get_mode_name() == mode_name:
            filtered_rows.append(row)
        else:
            pass

        row_index += 1

    return filtered_rows


def export_aggregated_standard_report(rows: List[AggregatedProcessMetricRow], output_prefix: str) -> List[Path]:
    """
    Export the aggregated standard-process-cold report.

    :param rows: Aggregated standard rows.
    :type rows: List[AggregatedProcessMetricRow]
    :param output_prefix: Output file prefix.
    :type output_prefix: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_results_directory()
    csv_path: Path = output_dir / f"{output_prefix}_standard_process_cold_stats.csv"
    json_path: Path = output_dir / f"{output_prefix}_standard_process_cold_stats.json"
    markdown_path: Path = output_dir / f"{output_prefix}_standard_process_cold_stats.md"
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    markdown_lines: List[str] = list()
    row_index: int = 0

    csv_lines.append("case,solver,build_median_s,build_mean_s,build_stdev_s,sim_median_s,sim_mean_s,sim_stdev_s,total_median_s,loop_median_s")
    markdown_lines.append("| Case | Solver | Build Median [s] | Build Stdev [s] | Sim Median [s] | Sim Stdev [s] | Total Median [s] | Loop Median [s] |")
    markdown_lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(rows):
        row: AggregatedProcessMetricRow = rows[row_index]
        stats_map: Dict[str, Dict[str, float]] = row.get_metric_stats()
        case_label: str = build_case_label(row.get_case_name())

        csv_lines.append(
            f"{case_label},{row.get_solver_key()},"
            f"{stats_map['solver_build_s']['median']:.9f},{stats_map['solver_build_s']['mean']:.9f},{stats_map['solver_build_s']['stdev']:.9f},"
            f"{stats_map['simulate_s']['median']:.9f},{stats_map['simulate_s']['mean']:.9f},{stats_map['simulate_s']['stdev']:.9f},"
            f"{stats_map['solver_total_s']['median']:.9f},{stats_map['loop_s']['median']:.9f}"
        )
        json_rows.append(
            dict(
                case=case_label,
                solver=row.get_solver_key(),
                solver_build_s=stats_map['solver_build_s'],
                simulate_s=stats_map['simulate_s'],
                solver_total_s=stats_map['solver_total_s'],
                loop_s=stats_map['loop_s'],
            )
        )
        markdown_lines.append(
            f"| {case_label} | {row.get_solver_key()} | {stats_map['solver_build_s']['median']:.6f} | {stats_map['solver_build_s']['stdev']:.6f} | "
            f"{stats_map['simulate_s']['median']:.6f} | {stats_map['simulate_s']['stdev']:.6f} | {stats_map['solver_total_s']['median']:.6f} | {stats_map['loop_s']['median']:.6f} |"
        )
        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_aggregated_cold_warm_report(rows: List[AggregatedProcessMetricRow], output_prefix: str) -> List[Path]:
    """
    Export the aggregated cold/warm-process report.

    :param rows: Aggregated cold/warm rows.
    :type rows: List[AggregatedProcessMetricRow]
    :param output_prefix: Output file prefix.
    :type output_prefix: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_results_directory()
    csv_path: Path = output_dir / f"{output_prefix}_cold_warm_process_stats.csv"
    json_path: Path = output_dir / f"{output_prefix}_cold_warm_process_stats.json"
    markdown_path: Path = output_dir / f"{output_prefix}_cold_warm_process_stats.md"
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    markdown_lines: List[str] = list()
    row_index: int = 0

    csv_lines.append("case,solver,cold_build_median_s,cold_build_stdev_s,cold_sim_median_s,cold_sim_stdev_s,warm_sim_median_s,warm_sim_stdev_s,speedup_median,speedup_stdev")
    markdown_lines.append("| Case | Solver | Cold Build Median [s] | Cold Build Stdev [s] | Cold Sim Median [s] | Warm Sim Median [s] | Speedup Median | Speedup Stdev |")
    markdown_lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(rows):
        row: AggregatedProcessMetricRow = rows[row_index]
        stats_map: Dict[str, Dict[str, float]] = row.get_metric_stats()
        case_label: str = build_case_label(row.get_case_name())

        csv_lines.append(
            f"{case_label},{row.get_solver_key()},"
            f"{stats_map['cold_build_s']['median']:.9f},{stats_map['cold_build_s']['stdev']:.9f},"
            f"{stats_map['cold_sim_s']['median']:.9f},{stats_map['cold_sim_s']['stdev']:.9f},"
            f"{stats_map['warm_sim_s']['median']:.9f},{stats_map['warm_sim_s']['stdev']:.9f},"
            f"{stats_map['speedup']['median']:.9f},{stats_map['speedup']['stdev']:.9f}"
        )
        json_rows.append(
            dict(
                case=case_label,
                solver=row.get_solver_key(),
                cold_build_s=stats_map['cold_build_s'],
                cold_sim_s=stats_map['cold_sim_s'],
                warm_sim_s=stats_map['warm_sim_s'],
                speedup=stats_map['speedup'],
            )
        )
        markdown_lines.append(
            f"| {case_label} | {row.get_solver_key()} | {stats_map['cold_build_s']['median']:.6f} | {stats_map['cold_build_s']['stdev']:.6f} | "
            f"{stats_map['cold_sim_s']['median']:.6f} | {stats_map['warm_sim_s']['median']:.6f} | {stats_map['speedup']['median']:.3f} | {stats_map['speedup']['stdev']:.3f} |"
        )
        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_compiled_component_report(samples: List[RepeatedProcessSample], output_prefix: str) -> List[Path]:
    """
    Export a component breakdown of ``COMPILED`` cold-build statistics.

    :param samples: Repeated subprocess samples.
    :type samples: List[RepeatedProcessSample]
    :param output_prefix: Output file prefix.
    :type output_prefix: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_results_directory()
    csv_path: Path = output_dir / f"{output_prefix}_compiled_build_components.csv"
    json_path: Path = output_dir / f"{output_prefix}_compiled_build_components.json"
    markdown_path: Path = output_dir / f"{output_prefix}_compiled_build_components.md"
    component_map: Dict[str, Dict[str, List[float]]] = dict()
    component_names: List[str] = [
        "grouping_s",
        "vec_kernel_compile_s",
        "jacobian_evaluator_s",
        "helper_warmup_s",
        "residual_warmup_s",
        "jacobian_warmup_s",
        "warmup_s",
        "full_warmup_enabled",
        "total_s",
    ]
    sample_index: int = 0

    while sample_index < len(samples):
        sample: RepeatedProcessSample = samples[sample_index]
        row: ProcessBenchmarkRow = sample.get_row()
        payload: Dict[str, object] = row.get_payload()

        if row.get_mode_name() == BenchmarkMode.STANDARD.value and str(payload["solver"]) == "COMPILED":
            case_name: str = row.get_case_name()

            if case_name in component_map:
                metric_values: Dict[str, List[float]] = component_map[case_name]
            else:
                metric_values = dict()
                component_map[case_name] = metric_values

            build_stats_any: object = payload.get("build_stats", dict())

            if isinstance(build_stats_any, dict):
                for component_name in component_names:
                    if component_name in metric_values:
                        pass
                    else:
                        metric_values[component_name] = list()

                    metric_values[component_name].append(float(build_stats_any.get(component_name, 0.0)))
            else:
                pass
        else:
            pass

        sample_index += 1

    sorted_case_names: List[str] = sorted(component_map.keys())
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    markdown_lines: List[str] = list()
    case_index: int = 0

    csv_lines.append(
        "case,grouping_median_s,vec_compile_median_s,jacobian_median_s,helper_warmup_median_s,residual_warmup_median_s,jacobian_warmup_median_s,warmup_median_s,full_warmup_enabled_median,total_median_s"
    )
    markdown_lines.append(
        "| Case | Grouping Median [s] | Vec Compile Median [s] | Jacobian Median [s] | Helper Warmup [s] | Residual Warmup [s] | Jacobian Warmup [s] | Warmup Median [s] | Full Warmup Flag | Total Median [s] |"
    )
    markdown_lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    while case_index < len(sorted_case_names):
        case_name: str = sorted_case_names[case_index]
        metric_values = component_map[case_name]
        metric_stats: Dict[str, Dict[str, float]] = dict()

        for component_name in component_names:
            metric_stats[component_name] = compute_metric_summary(metric_values[component_name])

        csv_lines.append(
            f"{build_case_label(case_name)},{metric_stats['grouping_s']['median']:.9f},{metric_stats['vec_kernel_compile_s']['median']:.9f},"
            f"{metric_stats['jacobian_evaluator_s']['median']:.9f},{metric_stats['helper_warmup_s']['median']:.9f},"
            f"{metric_stats['residual_warmup_s']['median']:.9f},{metric_stats['jacobian_warmup_s']['median']:.9f},"
            f"{metric_stats['warmup_s']['median']:.9f},{metric_stats['full_warmup_enabled']['median']:.9f},{metric_stats['total_s']['median']:.9f}"
        )
        json_rows.append(
            dict(
                case=build_case_label(case_name),
                grouping_s=metric_stats['grouping_s'],
                vec_kernel_compile_s=metric_stats['vec_kernel_compile_s'],
                jacobian_evaluator_s=metric_stats['jacobian_evaluator_s'],
                helper_warmup_s=metric_stats['helper_warmup_s'],
                residual_warmup_s=metric_stats['residual_warmup_s'],
                jacobian_warmup_s=metric_stats['jacobian_warmup_s'],
                warmup_s=metric_stats['warmup_s'],
                full_warmup_enabled=metric_stats['full_warmup_enabled'],
                total_s=metric_stats['total_s'],
            )
        )
        markdown_lines.append(
            f"| {build_case_label(case_name)} | {metric_stats['grouping_s']['median']:.6f} | {metric_stats['vec_kernel_compile_s']['median']:.6f} | "
            f"{metric_stats['jacobian_evaluator_s']['median']:.6f} | {metric_stats['helper_warmup_s']['median']:.6f} | "
            f"{metric_stats['residual_warmup_s']['median']:.6f} | {metric_stats['jacobian_warmup_s']['median']:.6f} | "
            f"{metric_stats['warmup_s']['median']:.6f} | {metric_stats['full_warmup_enabled']['median']:.3f} | {metric_stats['total_s']['median']:.6f} |"
        )
        case_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_repeated_statistics(samples: List[RepeatedProcessSample], output_prefix: str) -> List[Path]:
    """
    Export aggregated repeated subprocess statistics.

    :param samples: Repeated subprocess samples.
    :type samples: List[RepeatedProcessSample]
    :param output_prefix: Output file prefix.
    :type output_prefix: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    aggregated_rows: List[AggregatedProcessMetricRow] = aggregate_repeated_samples(samples)
    exported_paths: List[Path] = list()
    exported_paths.extend(export_aggregated_standard_report(filter_aggregated_rows(aggregated_rows, "standard"), output_prefix))
    exported_paths.extend(export_aggregated_cold_warm_report(filter_aggregated_rows(aggregated_rows, "cold_warm"), output_prefix))
    exported_paths.extend(export_compiled_component_report(samples, output_prefix))
    return exported_paths
