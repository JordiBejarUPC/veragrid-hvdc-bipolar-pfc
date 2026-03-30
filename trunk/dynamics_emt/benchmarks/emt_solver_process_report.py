import json
from pathlib import Path
from typing import Dict, List, Tuple


class ProcessReportRow:
    """
    One row loaded from a subprocess benchmark summary.
    """

    __slots__ = ["_case_name", "_mode_name", "_solver_key", "_payload"]

    def __init__(self, case_name: str, mode_name: str, solver_key: str, payload: Dict[str, object]) -> None:
        """
        Build one process-report row.

        :param case_name: Benchmark case identifier.
        :type case_name: str
        :param mode_name: Benchmark mode identifier.
        :type mode_name: str
        :param solver_key: Solver identifier.
        :type solver_key: str
        :param payload: Raw JSON payload.
        :type payload: Dict[str, object]
        :return: None.
        :rtype: None
        """
        self._case_name: str = case_name
        self._mode_name: str = mode_name
        self._solver_key: str = solver_key
        self._payload: Dict[str, object] = dict(payload)

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

    def get_payload(self) -> Dict[str, object]:
        """
        Return the raw payload.

        :return: Raw payload.
        :rtype: Dict[str, object]
        """
        return dict(self._payload)


def get_results_directory() -> Path:
    """
    Return the EMT benchmark-results directory.

    :return: Benchmark-results directory.
    :rtype: Path
    """
    return Path(__file__).resolve().parent / "benchmark_results"


def load_process_rows(file_stem: str) -> List[ProcessReportRow]:
    """
    Load one subprocess benchmark summary.

    :param file_stem: Input file stem without extension.
    :type file_stem: str
    :return: Loaded process-report rows.
    :rtype: List[ProcessReportRow]
    """
    input_path: Path = get_results_directory() / f"{file_stem}.json"

    with open(input_path, "r", encoding="utf-8") as json_file:
        raw_rows_any: object = json.load(json_file)

    if isinstance(raw_rows_any, list):
        raw_rows: List[Dict[str, object]] = [dict(item) for item in raw_rows_any]
    else:
        raise TypeError(f"Expected list JSON payload in {input_path}")

    rows: List[ProcessReportRow] = list()
    row_index: int = 0

    while row_index < len(raw_rows):
        raw_row: Dict[str, object] = raw_rows[row_index]
        rows.append(
            ProcessReportRow(
                case_name=str(raw_row["case"]),
                mode_name=str(raw_row["mode"]),
                solver_key=str(raw_row["solver"]),
                payload=raw_row,
            )
        )
        row_index += 1

    return rows


def build_case_label(case_name: str) -> str:
    """
    Convert one process-case identifier into a presentation label.

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


def filter_rows_by_mode(rows: List[ProcessReportRow], mode_name: str) -> List[ProcessReportRow]:
    """
    Filter process rows by benchmark mode.

    :param rows: Process-report rows.
    :type rows: List[ProcessReportRow]
    :param mode_name: Requested mode identifier.
    :type mode_name: str
    :return: Filtered rows.
    :rtype: List[ProcessReportRow]
    """
    filtered_rows: List[ProcessReportRow] = list()
    row_index: int = 0

    while row_index < len(rows):
        row: ProcessReportRow = rows[row_index]

        if row.get_mode_name() == mode_name:
            filtered_rows.append(row)
        else:
            pass

        row_index += 1

    return filtered_rows


def export_standard_process_report(rows: List[ProcessReportRow], output_prefix: str) -> List[Path]:
    """
    Export the standard process-cold table set.

    :param rows: Standard-mode rows.
    :type rows: List[ProcessReportRow]
    :param output_prefix: Output file prefix.
    :type output_prefix: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_results_directory()
    csv_path: Path = output_dir / f"{output_prefix}_standard_process_cold.csv"
    json_path: Path = output_dir / f"{output_prefix}_standard_process_cold.json"
    markdown_path: Path = output_dir / f"{output_prefix}_standard_process_cold.md"
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    markdown_lines: List[str] = list()
    row_index: int = 0

    csv_lines.append("case,solver,build_s,sim_s,total_s,loop_s,max_abs_diff")
    markdown_lines.append("| Case | Solver | Build [s] | Sim [s] | Total [s] | Loop [s] | Max Diff |")
    markdown_lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(rows):
        row: ProcessReportRow = rows[row_index]
        payload: Dict[str, object] = row.get_payload()
        case_label: str = build_case_label(row.get_case_name())

        if "max_abs_diff" in payload:
            max_abs_diff: float = float(payload["max_abs_diff"])
        else:
            max_abs_diff = float(payload.get("y_max_abs_diff", float("nan")))

        csv_lines.append(
            f"{case_label},{row.get_solver_key()},{float(payload['solver_build_s']):.9f},{float(payload['simulate_s']):.9f},"
            f"{float(payload['solver_total_s']):.9f},{float(payload['loop_s']):.9f},{max_abs_diff:.9e}"
        )
        json_rows.append(
            dict(
                case=case_label,
                solver=row.get_solver_key(),
                build_s=float(payload["solver_build_s"]),
                sim_s=float(payload["simulate_s"]),
                total_s=float(payload["solver_total_s"]),
                loop_s=float(payload["loop_s"]),
                max_abs_diff=max_abs_diff,
            )
        )
        markdown_lines.append(
            f"| {case_label} | {row.get_solver_key()} | {float(payload['solver_build_s']):.6f} | {float(payload['simulate_s']):.6f} | "
            f"{float(payload['solver_total_s']):.6f} | {float(payload['loop_s']):.6f} | {max_abs_diff:.3e} |"
        )
        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_cold_warm_process_report(rows: List[ProcessReportRow], output_prefix: str) -> List[Path]:
    """
    Export the cold/warm process table set.

    :param rows: Cold/warm-mode rows.
    :type rows: List[ProcessReportRow]
    :param output_prefix: Output file prefix.
    :type output_prefix: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_results_directory()
    csv_path: Path = output_dir / f"{output_prefix}_cold_warm_process.csv"
    json_path: Path = output_dir / f"{output_prefix}_cold_warm_process.json"
    markdown_path: Path = output_dir / f"{output_prefix}_cold_warm_process.md"
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    markdown_lines: List[str] = list()
    row_index: int = 0

    csv_lines.append("case,solver,cold_build_s,cold_sim_s,warm_sim_s,speedup,y_max_abs_diff,dy_max_abs_diff")
    markdown_lines.append("| Case | Solver | Cold Build [s] | Cold Sim [s] | Warm Sim [s] | Speedup | y Max Diff | dy Max Diff |")
    markdown_lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(rows):
        row: ProcessReportRow = rows[row_index]
        payload: Dict[str, object] = row.get_payload()
        case_label: str = build_case_label(row.get_case_name())

        if "max_abs_diff" in payload:
            y_max_abs_diff: float = float(payload["max_abs_diff"])
            dy_max_abs_diff: float = float(payload["max_abs_diff"])
        else:
            y_max_abs_diff = float(payload.get("y_max_abs_diff", float("nan")))
            dy_max_abs_diff = float(payload.get("dy_max_abs_diff", float("nan")))

        csv_lines.append(
            f"{case_label},{row.get_solver_key()},{float(payload['cold_build_s']):.9f},{float(payload['cold_sim_s']):.9f},"
            f"{float(payload['warm_sim_s']):.9f},{float(payload['speedup']):.9f},{y_max_abs_diff:.9e},{dy_max_abs_diff:.9e}"
        )
        json_rows.append(
            dict(
                case=case_label,
                solver=row.get_solver_key(),
                cold_build_s=float(payload["cold_build_s"]),
                cold_sim_s=float(payload["cold_sim_s"]),
                warm_sim_s=float(payload["warm_sim_s"]),
                speedup=float(payload["speedup"]),
                y_max_abs_diff=y_max_abs_diff,
                dy_max_abs_diff=dy_max_abs_diff,
            )
        )
        markdown_lines.append(
            f"| {case_label} | {row.get_solver_key()} | {float(payload['cold_build_s']):.6f} | {float(payload['cold_sim_s']):.6f} | "
            f"{float(payload['warm_sim_s']):.6f} | {float(payload['speedup']):.3f} | {y_max_abs_diff:.3e} | {dy_max_abs_diff:.3e} |"
        )
        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_mode_specific_reports(input_file_stem: str, output_prefix: str) -> List[Path]:
    """
    Export separate standard-process-cold and cold-warm-process reports.

    :param input_file_stem: Input process-summary file stem.
    :type input_file_stem: str
    :param output_prefix: Output file prefix.
    :type output_prefix: str
    :return: Exported file paths.
    :rtype: List[Path]
    """
    rows: List[ProcessReportRow] = load_process_rows(input_file_stem)
    exported_paths: List[Path] = list()
    exported_paths.extend(export_standard_process_report(filter_rows_by_mode(rows, "standard"), output_prefix))
    exported_paths.extend(export_cold_warm_process_report(filter_rows_by_mode(rows, "cold_warm"), output_prefix))
    return exported_paths


def export_regression_short_mode_reports() -> List[Path]:
    """
    Export separate reports for the short process-cold benchmark suite.

    :return: Exported file paths.
    :rtype: List[Path]
    """
    return export_mode_specific_reports("emt_solver_process_cold_regression_short", "emt_solver_regression_short")


def export_paper_long_mode_reports() -> List[Path]:
    """
    Export separate reports for the paper-grade process-cold benchmark suite.

    :return: Exported file paths.
    :rtype: List[Path]
    """
    return export_mode_specific_reports("emt_solver_process_cold_paper_long", "emt_solver_paper_long")
