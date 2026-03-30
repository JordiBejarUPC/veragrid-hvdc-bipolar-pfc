import json
import os
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Sequence

from VeraGrid.trunk.dynamics_emt.benchmarks.emt_solver_process_report import export_regression_short_mode_reports


class BenchmarkCase(Enum):
    """
    EMT benchmark cases supported by the process-cold orchestrator.
    """

    ZIPLOAD = "zipload"
    RLOAD = "rload"
    EVENT = "event"


class BenchmarkProfile(Enum):
    """
    Benchmark profiles supported by the process-cold orchestrator.
    """

    REGRESSION_SHORT = "regression_short"
    PAPER_LONG = "paper_long"


class BenchmarkMode(Enum):
    """
    Benchmark modes supported by the process-cold orchestrator.
    """

    STANDARD = "standard"
    COLD_WARM = "cold_warm"


class ProcessBenchmarkRow:
    """
    One subprocess-isolated EMT benchmark row.
    """

    __slots__ = ["_case_name", "_mode_name", "_payload"]

    def __init__(self, case_name: str, mode_name: str, payload: Dict[str, object]) -> None:
        """
        Build one process benchmark row.

        :param case_name: Benchmark case identifier.
        :type case_name: str
        :param mode_name: Benchmark mode identifier.
        :type mode_name: str
        :param payload: Raw worker payload.
        :type payload: Dict[str, object]
        :return: None.
        :rtype: None
        """
        self._case_name: str = case_name
        self._mode_name: str = mode_name
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
    return Path(__file__).resolve().parents[2]


def get_results_directory() -> Path:
    """
    Return the directory containing benchmark artifacts.

    :return: Benchmark-results directory.
    :rtype: Path
    """
    return Path(__file__).resolve().parent / "benchmark_results"


def build_worker_environment() -> Dict[str, str]:
    """
    Build the subprocess environment with the EMT source tree on ``PYTHONPATH``.

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


def run_worker_subprocess(case_name: BenchmarkCase, profile: BenchmarkProfile, mode: BenchmarkMode, solver_key: str) -> ProcessBenchmarkRow:
    """
    Run one EMT benchmark in a fresh Python process.

    :param case_name: Benchmark case.
    :type case_name: BenchmarkCase
    :param profile: Benchmark profile.
    :type profile: BenchmarkProfile
    :param mode: Benchmark mode.
    :type mode: BenchmarkMode
    :param solver_key: Solver identifier.
    :type solver_key: str
    :return: Process benchmark row.
    :rtype: ProcessBenchmarkRow
    """
    command: List[str] = [
        sys.executable,
        "-m",
        "VeraGrid.trunk.dynamics_emt.benchmarks.emt_solver_process_benchmark_worker",
        "--case",
        case_name.value,
        "--profile",
        profile.value,
        "--mode",
        mode.value,
        "--solver",
        solver_key,
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
    return ProcessBenchmarkRow(case_name.value, mode.value, payload)


def get_solver_keys() -> List[str]:
    """
    Return the solver identifiers in benchmark order.

    :return: Solver identifiers.
    :rtype: List[str]
    """
    return ["SYMBOLIC", "AD", "VECTORIZED", "COMPILED"]


def run_process_cold_suite(profile: BenchmarkProfile, cases: Sequence[BenchmarkCase], mode: BenchmarkMode) -> List[ProcessBenchmarkRow]:
    """
    Run a fresh-process benchmark suite.

    :param profile: Benchmark profile.
    :type profile: BenchmarkProfile
    :param cases: Benchmark cases.
    :type cases: Sequence[BenchmarkCase]
    :param mode: Benchmark mode.
    :type mode: BenchmarkMode
    :return: Process benchmark rows.
    :rtype: List[ProcessBenchmarkRow]
    """
    rows: List[ProcessBenchmarkRow] = list()
    case_index: int = 0

    while case_index < len(cases):
        case_name: BenchmarkCase = cases[case_index]
        solver_keys: List[str] = get_solver_keys()
        solver_index: int = 0

        while solver_index < len(solver_keys):
            rows.append(run_worker_subprocess(case_name, profile, mode, solver_keys[solver_index]))
            solver_index += 1

        case_index += 1

    return rows


def export_process_cold_suite(rows: List[ProcessBenchmarkRow], file_stem: str) -> List[Path]:
    """
    Export a fresh-process benchmark suite to CSV, JSON and Markdown.

    :param rows: Process benchmark rows.
    :type rows: List[ProcessBenchmarkRow]
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
        "case,mode,solver,problem_build_s,solver_init_s,solver_build_s,simulate_s,solver_total_s,loop_s,max_abs_diff,cold_build_s,cold_sim_s,warm_sim_s,speedup"
    )
    markdown_lines.append("| Case | Mode | Solver | Build [s] | Sim [s] | Total [s] | Loop [s] | Cold Build [s] | Cold Sim [s] | Warm Sim [s] | Speedup |")
    markdown_lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(rows):
        row: ProcessBenchmarkRow = rows[row_index]
        payload: Dict[str, object] = row.get_payload()
        solver_key: str = str(payload["solver"])

        if row.get_mode_name() == BenchmarkMode.STANDARD.value:
            solver_build_s: float = float(payload["solver_build_s"])
            simulate_s: float = float(payload["simulate_s"])
            solver_total_s: float = float(payload["solver_total_s"])
            loop_s: float = float(payload["loop_s"])
            max_abs_diff: float = float(payload.get("max_abs_diff", payload.get("y_max_abs_diff", float("nan"))))
            cold_build_s: float = float("nan")
            cold_sim_s: float = float("nan")
            warm_sim_s: float = float("nan")
            speedup: float = float("nan")
        else:
            solver_build_s = float("nan")
            simulate_s = float("nan")
            solver_total_s = float("nan")
            loop_s = float("nan")
            max_abs_diff = float(payload.get("max_abs_diff", payload.get("y_max_abs_diff", float("nan"))))
            cold_build_s = float(payload["cold_build_s"])
            cold_sim_s = float(payload["cold_sim_s"])
            warm_sim_s = float(payload["warm_sim_s"])
            speedup = float(payload["speedup"])

        csv_lines.append(
            f"{row.get_case_name()},{row.get_mode_name()},{solver_key},{float(payload['problem_build_s']):.9f},"
            f"{float(payload['solver_init_s']):.9f},{solver_build_s:.9f},{simulate_s:.9f},{solver_total_s:.9f},"
            f"{loop_s:.9f},{max_abs_diff:.9e},{cold_build_s:.9f},{cold_sim_s:.9f},{warm_sim_s:.9f},{speedup:.9f}"
        )
        json_rows.append(dict(case=row.get_case_name(), mode=row.get_mode_name(), **payload))
        markdown_lines.append(
            f"| {row.get_case_name()} | {row.get_mode_name()} | {solver_key} | {solver_build_s:.6f} | {simulate_s:.6f} | "
            f"{solver_total_s:.6f} | {loop_s:.6f} | {cold_build_s:.6f} | {cold_sim_s:.6f} | {warm_sim_s:.6f} | {speedup:.3f} |"
        )
        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_regression_short_process_cold_summary() -> List[Path]:
    """
    Run and export the short fresh-process benchmark suite.

    :return: Exported file paths.
    :rtype: List[Path]
    """
    cases: List[BenchmarkCase] = [BenchmarkCase.ZIPLOAD, BenchmarkCase.RLOAD, BenchmarkCase.EVENT]
    rows: List[ProcessBenchmarkRow] = list()
    rows.extend(run_process_cold_suite(BenchmarkProfile.REGRESSION_SHORT, cases, BenchmarkMode.STANDARD))
    rows.extend(run_process_cold_suite(BenchmarkProfile.REGRESSION_SHORT, cases, BenchmarkMode.COLD_WARM))
    exported_paths: List[Path] = export_process_cold_suite(rows, "emt_solver_process_cold_regression_short")
    exported_paths.extend(export_regression_short_mode_reports())
    return exported_paths


def main() -> None:
    """
    Execute the short fresh-process benchmark suite.

    :return: None.
    :rtype: None
    """
    export_regression_short_process_cold_summary()


if __name__ == "__main__":
    main()
