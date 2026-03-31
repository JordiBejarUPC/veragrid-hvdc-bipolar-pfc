import json
import os
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Sequence


class CompilerBenchmarkCase(Enum):
    """
    EMT benchmark cases supported by the compiler microbenchmark orchestrator.
    """

    ZIPLOAD = "zipload"
    RLOAD = "rload"
    EVENT = "event"
    VALIDATE = "validate"


class CompilerMicrobenchmarkRow:
    """
    One subprocess-isolated compiler microbenchmark row.
    """

    __slots__ = ["_case_name", "_payload"]

    def __init__(self, case_name: str, payload: Dict[str, object]) -> None:
        """
        Build one compiler microbenchmark row.

        :param case_name: Benchmark case identifier.
        :type case_name: str
        :param payload: Raw worker payload.
        :type payload: Dict[str, object]
        :return: None.
        :rtype: None
        """
        self._case_name: str = case_name
        self._payload: Dict[str, object] = dict(payload)

    def get_case_name(self) -> str:
        """
        Return the benchmark case identifier.

        :return: Benchmark case identifier.
        :rtype: str
        """
        return self._case_name

    def get_payload(self) -> Dict[str, object]:
        """
        Return the raw worker payload.

        :return: Raw worker payload.
        :rtype: Dict[str, object]
        """
        return dict(self._payload)


def get_repo_root() -> Path:
    """
    Return the repository root directory.

    :return: Repository root directory.
    :rtype: Path
    """
    return Path(__file__).resolve().parents[3]


def get_results_directory() -> Path:
    """
    Return the directory containing benchmark artifacts.

    :return: Benchmark-results directory.
    :rtype: Path
    """
    return Path(__file__).resolve().parents[1] / "benchmark_results"


def build_worker_environment() -> Dict[str, str]:
    """
    Build the subprocess environment with the project roots on ``PYTHONPATH``.

    :return: Worker environment.
    :rtype: Dict[str, str]
    """
    repo_root: Path = get_repo_root()
    repo_parent: Path = repo_root.parent
    src_root: Path = repo_root / "src"
    env: Dict[str, str] = dict(os.environ)
    previous_pythonpath: str | None = env.get("PYTHONPATH", None)
    required_entries: List[str] = [str(repo_parent), str(src_root)]

    if previous_pythonpath is None or len(previous_pythonpath) == 0:
        env["PYTHONPATH"] = os.pathsep.join(required_entries)
    else:
        env["PYTHONPATH"] = os.pathsep.join(required_entries) + os.pathsep + previous_pythonpath

    return env


def run_worker_subprocess(case_name: CompilerBenchmarkCase) -> CompilerMicrobenchmarkRow:
    """
    Run one compiler microbenchmark in a fresh Python process.

    :param case_name: Benchmark case.
    :type case_name: CompilerBenchmarkCase
    :return: Compiler microbenchmark row.
    :rtype: CompilerMicrobenchmarkRow
    """
    command: List[str] = [
        sys.executable,
        "-m",
        "trunk.dynamics_emt.benchmarks.emt_jit_compiler_microbenchmark_worker",
        "--case",
        case_name.value,
    ]
    completed_process: subprocess.CompletedProcess[str] = subprocess.run(
        command,
        cwd=str(get_repo_root()),
        env=build_worker_environment(),
        check=True,
        capture_output=True,
        text=True,
    )
    payload: Dict[str, object] = dict(json.loads(completed_process.stdout))
    return CompilerMicrobenchmarkRow(case_name.value, payload)


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
        validate="ValidateConnections",
    )
    mapped_label: str | None = label_map.get(case_name, None)

    if mapped_label is None:
        return case_name
    else:
        return mapped_label


def run_compiler_microbenchmark_suite(cases: Sequence[CompilerBenchmarkCase]) -> List[CompilerMicrobenchmarkRow]:
    """
    Run the compiler microbenchmark suite.

    :param cases: Benchmark cases.
    :type cases: Sequence[CompilerBenchmarkCase]
    :return: Compiler microbenchmark rows.
    :rtype: List[CompilerMicrobenchmarkRow]
    """
    rows: List[CompilerMicrobenchmarkRow] = list()
    case_index: int = 0

    while case_index < len(cases):
        rows.append(run_worker_subprocess(cases[case_index]))
        case_index += 1

    return rows


def export_compiler_microbenchmark(rows: List[CompilerMicrobenchmarkRow], file_stem: str) -> List[Path]:
    """
    Export the compiler microbenchmark summary to CSV, JSON and Markdown.

    :param rows: Compiler microbenchmark rows.
    :type rows: List[CompilerMicrobenchmarkRow]
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
    json_rows: List[Dict[str, object]] = list()
    markdown_lines: List[str] = list()
    row_index: int = 0

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_lines.append(
        "case,equations,variables,parameters,groups,residual_source_cse_on_s,residual_njit_cse_on_s,residual_cached_source_cse_on_s,residual_cached_njit_cse_on_s,residual_source_cse_off_s,residual_njit_cse_off_s,residual_cached_source_cse_off_s,residual_cached_njit_cse_off_s,ad_source_cse_on_s,ad_njit_cse_on_s,ad_cached_source_cse_on_s,ad_cached_njit_cse_on_s,ad_source_cse_off_s,ad_njit_cse_off_s,ad_cached_source_cse_off_s,ad_cached_njit_cse_off_s,matrix_source_total_s,matrix_njit_total_s,matrix_cached_source_total_s,matrix_cached_njit_total_s,average_group_rows"
    )
    markdown_lines.append(
        "| Case | Eq | Vars | Groups | Residual Src On [s] | Residual JIT On [s] | Residual Src On Cached [s] | Residual JIT On Cached [s] | AD Src On [s] | AD JIT On [s] | AD Src On Cached [s] | AD JIT On Cached [s] | Matrix Src [s] | Matrix JIT [s] | Matrix Src Cached [s] | Matrix JIT Cached [s] | Avg Group Rows |"
    )
    markdown_lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(rows):
        row: CompilerMicrobenchmarkRow = rows[row_index]
        payload: Dict[str, object] = row.get_payload()
        case_label: str = build_case_label(row.get_case_name())

        csv_lines.append(
            f"{case_label},{int(payload['equation_count'])},{int(payload['variable_count'])},{int(payload['parameter_count'])},{int(payload['structural_group_count'])},"
            f"{float(payload['residual_source_cse_on_s']):.9f},{float(payload['residual_njit_cse_on_s']):.9f},"
            f"{float(payload['residual_cached_source_cse_on_s']):.9f},{float(payload['residual_cached_njit_cse_on_s']):.9f},"
            f"{float(payload['residual_source_cse_off_s']):.9f},{float(payload['residual_njit_cse_off_s']):.9f},"
            f"{float(payload['residual_cached_source_cse_off_s']):.9f},{float(payload['residual_cached_njit_cse_off_s']):.9f},"
            f"{float(payload['ad_source_cse_on_s']):.9f},{float(payload['ad_njit_cse_on_s']):.9f},"
            f"{float(payload['ad_cached_source_cse_on_s']):.9f},{float(payload['ad_cached_njit_cse_on_s']):.9f},"
            f"{float(payload['ad_source_cse_off_s']):.9f},{float(payload['ad_njit_cse_off_s']):.9f},"
            f"{float(payload['ad_cached_source_cse_off_s']):.9f},{float(payload['ad_cached_njit_cse_off_s']):.9f},"
            f"{float(payload['matrix_source_total_s']):.9f},{float(payload['matrix_njit_total_s']):.9f},"
            f"{float(payload['matrix_cached_source_total_s']):.9f},{float(payload['matrix_cached_njit_total_s']):.9f},{float(payload['average_group_rows']):.6f}"
        )
        json_row: Dict[str, object] = dict(payload)
        json_row["case"] = case_label
        json_rows.append(json_row)
        markdown_lines.append(
            f"| {case_label} | {int(payload['equation_count'])} | {int(payload['variable_count'])} | {int(payload['structural_group_count'])} | "
            f"{float(payload['residual_source_cse_on_s']):.6f} | {float(payload['residual_njit_cse_on_s']):.6f} | "
            f"{float(payload['residual_cached_source_cse_on_s']):.6f} | {float(payload['residual_cached_njit_cse_on_s']):.6f} | "
            f"{float(payload['ad_source_cse_on_s']):.6f} | {float(payload['ad_njit_cse_on_s']):.6f} | "
            f"{float(payload['ad_cached_source_cse_on_s']):.6f} | {float(payload['ad_cached_njit_cse_on_s']):.6f} | "
            f"{float(payload['matrix_source_total_s']):.6f} | {float(payload['matrix_njit_total_s']):.6f} | "
            f"{float(payload['matrix_cached_source_total_s']):.6f} | {float(payload['matrix_cached_njit_total_s']):.6f} | {float(payload['average_group_rows']):.3f} |"
        )
        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_default_compiler_microbenchmark() -> List[Path]:
    """
    Run and export the default compiler microbenchmark suite.

    :return: Exported file paths.
    :rtype: List[Path]
    """
    cases: List[CompilerBenchmarkCase] = [
        CompilerBenchmarkCase.ZIPLOAD,
        CompilerBenchmarkCase.RLOAD,
        CompilerBenchmarkCase.EVENT,
        CompilerBenchmarkCase.VALIDATE,
    ]
    rows: List[CompilerMicrobenchmarkRow] = run_compiler_microbenchmark_suite(cases)
    return export_compiler_microbenchmark(rows, "emt_jit_compiler_microbenchmark")


def main() -> None:
    """
    Execute the default compiler microbenchmark suite.

    :return: None.
    :rtype: None
    """
    export_default_compiler_microbenchmark()


if __name__ == "__main__":
    main()
