import json
from pathlib import Path
from typing import Dict, List, Tuple


class StandardBenchmarkRow:
    """
    One normalized row from the standard benchmark exports.
    """

    __slots__ = [
        "_case_name",
        "_solver_key",
        "_problem_build_s",
        "_solver_init_s",
        "_solver_build_s",
        "_simulate_s",
        "_solver_total_s",
        "_loop_s",
        "_y_max_abs_diff",
        "_dy_max_abs_diff",
        "_final_residual_inf",
        "_build_stats_count",
    ]

    def __init__(
            self,
            case_name: str,
            solver_key: str,
            problem_build_s: float,
            solver_init_s: float,
            solver_build_s: float,
            simulate_s: float,
            solver_total_s: float,
            loop_s: float,
            y_max_abs_diff: float,
            dy_max_abs_diff: float,
            final_residual_inf: float,
            build_stats_count: int,
    ) -> None:
        """
        Build one normalized standard benchmark row.

        :param case_name: Case identifier.
        :type case_name: str
        :param solver_key: Solver identifier.
        :type solver_key: str
        :param problem_build_s: Problem build time.
        :type problem_build_s: float
        :param solver_init_s: Solver initialization time.
        :type solver_init_s: float
        :param solver_build_s: Backend build time.
        :type solver_build_s: float
        :param simulate_s: Simulation time.
        :type simulate_s: float
        :param solver_total_s: Total solver time.
        :type solver_total_s: float
        :param loop_s: Integration-loop time.
        :type loop_s: float
        :param y_max_abs_diff: Maximum y difference.
        :type y_max_abs_diff: float
        :param dy_max_abs_diff: Maximum dy difference.
        :type dy_max_abs_diff: float
        :param final_residual_inf: Final residual infinity norm.
        :type final_residual_inf: float
        :param build_stats_count: Number of build statistics fields.
        :type build_stats_count: int
        :return: None.
        :rtype: None
        """
        self._case_name: str = case_name
        self._solver_key: str = solver_key
        self._problem_build_s: float = float(problem_build_s)
        self._solver_init_s: float = float(solver_init_s)
        self._solver_build_s: float = float(solver_build_s)
        self._simulate_s: float = float(simulate_s)
        self._solver_total_s: float = float(solver_total_s)
        self._loop_s: float = float(loop_s)
        self._y_max_abs_diff: float = float(y_max_abs_diff)
        self._dy_max_abs_diff: float = float(dy_max_abs_diff)
        self._final_residual_inf: float = float(final_residual_inf)
        self._build_stats_count: int = int(build_stats_count)

    def get_case_name(self) -> str:
        """
        Return the case identifier.

        :return: Case identifier.
        :rtype: str
        """
        return self._case_name

    def get_solver_key(self) -> str:
        """
        Return the solver identifier.

        :return: Solver identifier.
        :rtype: str
        """
        return self._solver_key

    def get_problem_build_s(self) -> float:
        """
        Return the problem-build time.

        :return: Problem-build time.
        :rtype: float
        """
        return self._problem_build_s

    def get_solver_init_s(self) -> float:
        """
        Return the solver initialization time.

        :return: Solver initialization time.
        :rtype: float
        """
        return self._solver_init_s

    def get_solver_build_s(self) -> float:
        """
        Return the backend build time.

        :return: Backend build time.
        :rtype: float
        """
        return self._solver_build_s

    def get_simulate_s(self) -> float:
        """
        Return the simulation time.

        :return: Simulation time.
        :rtype: float
        """
        return self._simulate_s

    def get_solver_total_s(self) -> float:
        """
        Return the total solver time.

        :return: Total solver time.
        :rtype: float
        """
        return self._solver_total_s

    def get_loop_s(self) -> float:
        """
        Return the loop-only time.

        :return: Loop-only time.
        :rtype: float
        """
        return self._loop_s

    def get_y_max_abs_diff(self) -> float:
        """
        Return the maximum y difference.

        :return: Maximum y difference.
        :rtype: float
        """
        return self._y_max_abs_diff

    def get_dy_max_abs_diff(self) -> float:
        """
        Return the maximum dy difference.

        :return: Maximum dy difference.
        :rtype: float
        """
        return self._dy_max_abs_diff

    def get_final_residual_inf(self) -> float:
        """
        Return the final residual infinity norm.

        :return: Final residual infinity norm.
        :rtype: float
        """
        return self._final_residual_inf

    def get_build_stats_count(self) -> int:
        """
        Return the number of build-stat fields.

        :return: Number of build-stat fields.
        :rtype: int
        """
        return self._build_stats_count


class ColdWarmBenchmarkRow:
    """
    One normalized row from the cold/warm benchmark exports.
    """

    __slots__ = [
        "_case_name",
        "_solver_key",
        "_problem_build_s",
        "_solver_init_s",
        "_cold_build_s",
        "_cold_sim_s",
        "_warm_sim_s",
        "_speedup",
        "_y_max_abs_diff",
        "_dy_max_abs_diff",
        "_cold_final_residual_inf",
        "_warm_final_residual_inf",
        "_build_stats_count",
    ]

    def __init__(
            self,
            case_name: str,
            solver_key: str,
            problem_build_s: float,
            solver_init_s: float,
            cold_build_s: float,
            cold_sim_s: float,
            warm_sim_s: float,
            speedup: float,
            y_max_abs_diff: float,
            dy_max_abs_diff: float,
            cold_final_residual_inf: float,
            warm_final_residual_inf: float,
            build_stats_count: int,
    ) -> None:
        """
        Build one normalized cold/warm benchmark row.

        :param case_name: Case identifier.
        :type case_name: str
        :param solver_key: Solver identifier.
        :type solver_key: str
        :param problem_build_s: Problem build time.
        :type problem_build_s: float
        :param solver_init_s: Solver initialization time.
        :type solver_init_s: float
        :param cold_build_s: Cold backend build time.
        :type cold_build_s: float
        :param cold_sim_s: Cold simulation time.
        :type cold_sim_s: float
        :param warm_sim_s: Warm simulation time.
        :type warm_sim_s: float
        :param speedup: Cold-to-warm speedup factor.
        :type speedup: float
        :param y_max_abs_diff: Maximum y difference between cold and warm runs.
        :type y_max_abs_diff: float
        :param dy_max_abs_diff: Maximum dy difference between cold and warm runs.
        :type dy_max_abs_diff: float
        :param cold_final_residual_inf: Cold final residual infinity norm.
        :type cold_final_residual_inf: float
        :param warm_final_residual_inf: Warm final residual infinity norm.
        :type warm_final_residual_inf: float
        :param build_stats_count: Number of build-stat fields.
        :type build_stats_count: int
        :return: None.
        :rtype: None
        """
        self._case_name: str = case_name
        self._solver_key: str = solver_key
        self._problem_build_s: float = float(problem_build_s)
        self._solver_init_s: float = float(solver_init_s)
        self._cold_build_s: float = float(cold_build_s)
        self._cold_sim_s: float = float(cold_sim_s)
        self._warm_sim_s: float = float(warm_sim_s)
        self._speedup: float = float(speedup)
        self._y_max_abs_diff: float = float(y_max_abs_diff)
        self._dy_max_abs_diff: float = float(dy_max_abs_diff)
        self._cold_final_residual_inf: float = float(cold_final_residual_inf)
        self._warm_final_residual_inf: float = float(warm_final_residual_inf)
        self._build_stats_count: int = int(build_stats_count)

    def get_case_name(self) -> str:
        """
        Return the case identifier.

        :return: Case identifier.
        :rtype: str
        """
        return self._case_name

    def get_solver_key(self) -> str:
        """
        Return the solver identifier.

        :return: Solver identifier.
        :rtype: str
        """
        return self._solver_key

    def get_problem_build_s(self) -> float:
        """
        Return the problem-build time.

        :return: Problem-build time.
        :rtype: float
        """
        return self._problem_build_s

    def get_solver_init_s(self) -> float:
        """
        Return the solver initialization time.

        :return: Solver initialization time.
        :rtype: float
        """
        return self._solver_init_s

    def get_cold_build_s(self) -> float:
        """
        Return the cold backend-build time.

        :return: Cold backend-build time.
        :rtype: float
        """
        return self._cold_build_s

    def get_cold_sim_s(self) -> float:
        """
        Return the cold simulation time.

        :return: Cold simulation time.
        :rtype: float
        """
        return self._cold_sim_s

    def get_warm_sim_s(self) -> float:
        """
        Return the warm simulation time.

        :return: Warm simulation time.
        :rtype: float
        """
        return self._warm_sim_s

    def get_speedup(self) -> float:
        """
        Return the cold-to-warm speedup factor.

        :return: Speedup factor.
        :rtype: float
        """
        return self._speedup

    def get_y_max_abs_diff(self) -> float:
        """
        Return the maximum y difference between cold and warm runs.

        :return: Maximum y difference.
        :rtype: float
        """
        return self._y_max_abs_diff

    def get_dy_max_abs_diff(self) -> float:
        """
        Return the maximum dy difference between cold and warm runs.

        :return: Maximum dy difference.
        :rtype: float
        """
        return self._dy_max_abs_diff

    def get_cold_final_residual_inf(self) -> float:
        """
        Return the cold final residual infinity norm.

        :return: Cold final residual infinity norm.
        :rtype: float
        """
        return self._cold_final_residual_inf

    def get_warm_final_residual_inf(self) -> float:
        """
        Return the warm final residual infinity norm.

        :return: Warm final residual infinity norm.
        :rtype: float
        """
        return self._warm_final_residual_inf

    def get_build_stats_count(self) -> int:
        """
        Return the number of build-stat fields.

        :return: Number of build-stat fields.
        :rtype: int
        """
        return self._build_stats_count


class UnifiedBenchmarkRow:
    """
    Unified comparative row joining standard and cold/warm results.
    """

    __slots__ = ["_standard_row", "_cold_warm_row"]

    def __init__(self, standard_row: StandardBenchmarkRow, cold_warm_row: ColdWarmBenchmarkRow | None) -> None:
        """
        Build one unified comparative row.

        :param standard_row: Standard benchmark row.
        :type standard_row: StandardBenchmarkRow
        :param cold_warm_row: Cold/warm benchmark row or ``None``.
        :type cold_warm_row: ColdWarmBenchmarkRow | None
        :return: None.
        :rtype: None
        """
        self._standard_row = standard_row
        self._cold_warm_row = cold_warm_row

    def get_standard_row(self) -> StandardBenchmarkRow:
        """
        Return the standard benchmark row.

        :return: Standard benchmark row.
        :rtype: StandardBenchmarkRow
        """
        return self._standard_row

    def get_cold_warm_row(self) -> ColdWarmBenchmarkRow | None:
        """
        Return the cold/warm benchmark row.

        :return: Cold/warm benchmark row or ``None``.
        :rtype: ColdWarmBenchmarkRow | None
        """
        return self._cold_warm_row


def get_benchmark_results_directory() -> Path:
    """
    Return the directory containing EMT benchmark artifacts.

    :return: Benchmark-results directory.
    :rtype: Path
    """
    return Path(__file__).resolve().parent / "benchmark_results"


def read_json_records(file_path: Path) -> List[Dict[str, object]]:
    """
    Read one JSON benchmark file.

    :param file_path: JSON file path.
    :type file_path: Path
    :return: Raw JSON records.
    :rtype: List[Dict[str, object]]
    """
    with open(file_path, "r", encoding="utf-8") as json_file:
        raw_data: object = json.load(json_file)

    if isinstance(raw_data, list):
        return [dict(item) for item in raw_data]
    else:
        raise TypeError(f"Expected list JSON payload in {file_path}")


def get_build_stats_count(record: Dict[str, object]) -> int:
    """
    Return the number of build-stat fields inside one raw record.

    :param record: Raw JSON record.
    :type record: Dict[str, object]
    :return: Number of build-stat fields.
    :rtype: int
    """
    build_stats_any: object = record.get("build_stats", dict())

    if isinstance(build_stats_any, dict):
        return len(build_stats_any)
    else:
        return 0


def parse_standard_row(case_name: str, record: Dict[str, object]) -> StandardBenchmarkRow:
    """
    Parse one standard benchmark record.

    :param case_name: Case identifier.
    :type case_name: str
    :param record: Raw JSON record.
    :type record: Dict[str, object]
    :return: Parsed standard benchmark row.
    :rtype: StandardBenchmarkRow
    """
    if "y_max_abs_diff" in record:
        y_max_abs_diff: float = float(record["y_max_abs_diff"])
        dy_max_abs_diff: float = float(record["dy_max_abs_diff"])
    else:
        y_max_abs_diff = float(record["max_abs_diff"])
        dy_max_abs_diff = float(record["max_abs_diff"])

    if "final_residual_inf" in record:
        final_residual_inf: float = float(record["final_residual_inf"])
    else:
        final_residual_inf = float("nan")

    return StandardBenchmarkRow(
        case_name=case_name,
        solver_key=str(record["solver"]),
        problem_build_s=float(record["problem_build_s"]),
        solver_init_s=float(record["solver_init_s"]),
        solver_build_s=float(record["solver_build_s"]),
        simulate_s=float(record["simulate_s"]),
        solver_total_s=float(record["solver_total_s"]),
        loop_s=float(record["loop_s"]),
        y_max_abs_diff=y_max_abs_diff,
        dy_max_abs_diff=dy_max_abs_diff,
        final_residual_inf=final_residual_inf,
        build_stats_count=get_build_stats_count(record),
    )


def parse_cold_warm_row(case_name: str, record: Dict[str, object]) -> ColdWarmBenchmarkRow:
    """
    Parse one cold/warm benchmark record.

    :param case_name: Case identifier.
    :type case_name: str
    :param record: Raw JSON record.
    :type record: Dict[str, object]
    :return: Parsed cold/warm benchmark row.
    :rtype: ColdWarmBenchmarkRow
    """
    if "y_max_abs_diff" in record:
        y_max_abs_diff: float = float(record["y_max_abs_diff"])
        dy_max_abs_diff: float = float(record["dy_max_abs_diff"])
    else:
        y_max_abs_diff = float(record["max_abs_diff"])
        dy_max_abs_diff = float(record["max_abs_diff"])

    if "cold_final_residual_inf" in record:
        cold_final_residual_inf: float = float(record["cold_final_residual_inf"])
        warm_final_residual_inf: float = float(record["warm_final_residual_inf"])
    else:
        cold_final_residual_inf = float("nan")
        warm_final_residual_inf = float("nan")

    return ColdWarmBenchmarkRow(
        case_name=case_name,
        solver_key=str(record["solver"]),
        problem_build_s=float(record["problem_build_s"]),
        solver_init_s=float(record["solver_init_s"]),
        cold_build_s=float(record["cold_build_s"]),
        cold_sim_s=float(record["cold_sim_s"]),
        warm_sim_s=float(record["warm_sim_s"]),
        speedup=float(record["speedup"]),
        y_max_abs_diff=y_max_abs_diff,
        dy_max_abs_diff=dy_max_abs_diff,
        cold_final_residual_inf=cold_final_residual_inf,
        warm_final_residual_inf=warm_final_residual_inf,
        build_stats_count=get_build_stats_count(record),
    )


def load_standard_rows() -> List[StandardBenchmarkRow]:
    """
    Load the standard benchmark rows from disk.

    :return: Standard benchmark rows.
    :rtype: List[StandardBenchmarkRow]
    """
    output_dir: Path = get_benchmark_results_directory()
    file_map: Dict[str, str] = dict(
        thevequiv_piline_zipload="thevequiv_piline_zipload.json",
        thevequiv_piline_rload="thevequiv_piline_rload.json",
        emt_event="emt_event_benchmark.json",
        validate_connections_models="validate_connections_emt_models.json",
    )
    rows: List[StandardBenchmarkRow] = list()
    case_names: List[str] = list(file_map.keys())
    case_index: int = 0

    while case_index < len(case_names):
        case_name: str = case_names[case_index]
        file_name: str = file_map[case_name]
        raw_records: List[Dict[str, object]] = read_json_records(output_dir / file_name)
        record_index: int = 0

        while record_index < len(raw_records):
            rows.append(parse_standard_row(case_name, raw_records[record_index]))
            record_index += 1

        case_index += 1

    return rows


def load_cold_warm_rows() -> List[ColdWarmBenchmarkRow]:
    """
    Load the cold/warm benchmark rows from disk.

    :return: Cold/warm benchmark rows.
    :rtype: List[ColdWarmBenchmarkRow]
    """
    output_dir: Path = get_benchmark_results_directory()
    file_map: Dict[str, str] = dict(
        thevequiv_piline_zipload="thevequiv_piline_zipload_all_solvers_cold_warm.json",
        thevequiv_piline_rload="thevequiv_piline_rload_all_solvers_cold_warm.json",
        emt_event="emt_event_all_solvers_cold_warm.json",
    )
    rows: List[ColdWarmBenchmarkRow] = list()
    case_names: List[str] = list(file_map.keys())
    case_index: int = 0

    while case_index < len(case_names):
        case_name: str = case_names[case_index]
        file_name: str = file_map[case_name]
        raw_records: List[Dict[str, object]] = read_json_records(output_dir / file_name)
        record_index: int = 0

        while record_index < len(raw_records):
            rows.append(parse_cold_warm_row(case_name, raw_records[record_index]))
            record_index += 1

        case_index += 1

    return rows


def build_cold_warm_lookup(rows: List[ColdWarmBenchmarkRow]) -> Dict[Tuple[str, str], ColdWarmBenchmarkRow]:
    """
    Build a lookup map for cold/warm rows.

    :param rows: Cold/warm benchmark rows.
    :type rows: List[ColdWarmBenchmarkRow]
    :return: Lookup map keyed by ``(case, solver)``.
    :rtype: Dict[Tuple[str, str], ColdWarmBenchmarkRow]
    """
    lookup: Dict[Tuple[str, str], ColdWarmBenchmarkRow] = dict()
    row_index: int = 0

    while row_index < len(rows):
        row: ColdWarmBenchmarkRow = rows[row_index]
        lookup[(row.get_case_name(), row.get_solver_key())] = row
        row_index += 1

    return lookup


def build_unified_rows() -> List[UnifiedBenchmarkRow]:
    """
    Build the unified comparison rows joining standard and cold/warm results.

    :return: Unified comparison rows.
    :rtype: List[UnifiedBenchmarkRow]
    """
    standard_rows: List[StandardBenchmarkRow] = load_standard_rows()
    cold_warm_lookup: Dict[Tuple[str, str], ColdWarmBenchmarkRow] = build_cold_warm_lookup(load_cold_warm_rows())
    unified_rows: List[UnifiedBenchmarkRow] = list()
    row_index: int = 0

    while row_index < len(standard_rows):
        standard_row: StandardBenchmarkRow = standard_rows[row_index]
        lookup_key: Tuple[str, str] = (standard_row.get_case_name(), standard_row.get_solver_key())
        cold_warm_row: ColdWarmBenchmarkRow | None = cold_warm_lookup.get(lookup_key, None)
        unified_rows.append(UnifiedBenchmarkRow(standard_row, cold_warm_row))
        row_index += 1

    return unified_rows


def build_case_label(case_name: str) -> str:
    """
    Convert one internal case identifier into a presentation label.

    :param case_name: Internal case identifier.
    :type case_name: str
    :return: Presentation label.
    :rtype: str
    """
    label_map: Dict[str, str] = dict(
        thevequiv_piline_zipload="ZIPload",
        thevequiv_piline_rload="Rload",
        emt_event="Event",
        validate_connections_models="ValidateConnections",
    )
    mapped_label: str | None = label_map.get(case_name, None)

    if mapped_label is None:
        return case_name
    else:
        return mapped_label


def export_unified_summary(rows: List[UnifiedBenchmarkRow]) -> List[Path]:
    """
    Export the unified benchmark summary to CSV, JSON and Markdown.

    :param rows: Unified comparison rows.
    :type rows: List[UnifiedBenchmarkRow]
    :return: Exported file paths.
    :rtype: List[Path]
    """
    output_dir: Path = get_benchmark_results_directory()
    csv_path: Path = output_dir / "emt_solver_comparison_summary.csv"
    json_path: Path = output_dir / "emt_solver_comparison_summary.json"
    markdown_path: Path = output_dir / "emt_solver_comparison_summary.md"
    csv_lines: List[str] = list()
    json_rows: List[Dict[str, object]] = list()
    markdown_lines: List[str] = list()
    row_index: int = 0

    csv_lines.append(
        "case,solver,problem_build_s,solver_init_s,solver_build_s,simulate_s,solver_total_s,loop_s,y_max_abs_diff,dy_max_abs_diff,final_residual_inf,build_stats_count,cold_build_s,cold_sim_s,warm_sim_s,speedup,cold_y_max_abs_diff,cold_dy_max_abs_diff,cold_final_residual_inf,warm_final_residual_inf,cold_build_stats_count"
    )

    markdown_lines.append("| Case | Solver | Build [s] | Sim [s] | Total [s] | Loop [s] | Cold Build [s] | Cold Sim [s] | Warm Sim [s] | Speedup | Final Res |")
    markdown_lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    while row_index < len(rows):
        row: UnifiedBenchmarkRow = rows[row_index]
        standard_row: StandardBenchmarkRow = row.get_standard_row()
        cold_warm_row: ColdWarmBenchmarkRow | None = row.get_cold_warm_row()

        if cold_warm_row is None:
            cold_build_s: float = float("nan")
            cold_sim_s: float = float("nan")
            warm_sim_s: float = float("nan")
            speedup: float = float("nan")
            cold_y_max_abs_diff: float = float("nan")
            cold_dy_max_abs_diff: float = float("nan")
            cold_final_residual_inf: float = float("nan")
            warm_final_residual_inf: float = float("nan")
            cold_build_stats_count: int = 0
        else:
            cold_build_s = cold_warm_row.get_cold_build_s()
            cold_sim_s = cold_warm_row.get_cold_sim_s()
            warm_sim_s = cold_warm_row.get_warm_sim_s()
            speedup = cold_warm_row.get_speedup()
            cold_y_max_abs_diff = cold_warm_row.get_y_max_abs_diff()
            cold_dy_max_abs_diff = cold_warm_row.get_dy_max_abs_diff()
            cold_final_residual_inf = cold_warm_row.get_cold_final_residual_inf()
            warm_final_residual_inf = cold_warm_row.get_warm_final_residual_inf()
            cold_build_stats_count = cold_warm_row.get_build_stats_count()

        csv_lines.append(
            f"{build_case_label(standard_row.get_case_name())},{standard_row.get_solver_key()},"
            f"{standard_row.get_problem_build_s():.9f},{standard_row.get_solver_init_s():.9f},"
            f"{standard_row.get_solver_build_s():.9f},{standard_row.get_simulate_s():.9f},"
            f"{standard_row.get_solver_total_s():.9f},{standard_row.get_loop_s():.9f},"
            f"{standard_row.get_y_max_abs_diff():.9e},{standard_row.get_dy_max_abs_diff():.9e},"
            f"{standard_row.get_final_residual_inf():.9e},{standard_row.get_build_stats_count()},"
            f"{cold_build_s:.9f},{cold_sim_s:.9f},{warm_sim_s:.9f},{speedup:.9f},"
            f"{cold_y_max_abs_diff:.9e},{cold_dy_max_abs_diff:.9e},{cold_final_residual_inf:.9e},"
            f"{warm_final_residual_inf:.9e},{cold_build_stats_count}"
        )

        json_rows.append(
            dict(
                case=build_case_label(standard_row.get_case_name()),
                solver=standard_row.get_solver_key(),
                problem_build_s=standard_row.get_problem_build_s(),
                solver_init_s=standard_row.get_solver_init_s(),
                solver_build_s=standard_row.get_solver_build_s(),
                simulate_s=standard_row.get_simulate_s(),
                solver_total_s=standard_row.get_solver_total_s(),
                loop_s=standard_row.get_loop_s(),
                y_max_abs_diff=standard_row.get_y_max_abs_diff(),
                dy_max_abs_diff=standard_row.get_dy_max_abs_diff(),
                final_residual_inf=standard_row.get_final_residual_inf(),
                build_stats_count=standard_row.get_build_stats_count(),
                cold_build_s=cold_build_s,
                cold_sim_s=cold_sim_s,
                warm_sim_s=warm_sim_s,
                speedup=speedup,
                cold_y_max_abs_diff=cold_y_max_abs_diff,
                cold_dy_max_abs_diff=cold_dy_max_abs_diff,
                cold_final_residual_inf=cold_final_residual_inf,
                warm_final_residual_inf=warm_final_residual_inf,
                cold_build_stats_count=cold_build_stats_count,
            )
        )

        markdown_lines.append(
            f"| {build_case_label(standard_row.get_case_name())} | {standard_row.get_solver_key()} | "
            f"{standard_row.get_solver_build_s():.6f} | {standard_row.get_simulate_s():.6f} | "
            f"{standard_row.get_solver_total_s():.6f} | {standard_row.get_loop_s():.6f} | "
            f"{cold_build_s:.6f} | {cold_sim_s:.6f} | {warm_sim_s:.6f} | {speedup:.3f} | "
            f"{standard_row.get_final_residual_inf():.3e} |"
        )

        row_index += 1

    with open(csv_path, "w", encoding="utf-8") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(json_rows, json_file, indent=2)

    with open(markdown_path, "w", encoding="utf-8") as markdown_file:
        markdown_file.write("\n".join(markdown_lines) + "\n")

    return [csv_path, json_path, markdown_path]


def export_solver_comparison_summary() -> List[Path]:
    """
    Build and export the unified EMT solver comparison summary.

    :return: Exported file paths.
    :rtype: List[Path]
    """
    unified_rows: List[UnifiedBenchmarkRow] = build_unified_rows()
    return export_unified_summary(unified_rows)
