from __future__ import annotations

import csv
import math
import timeit
from pathlib import Path
from typing import List, Tuple

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.Simulations.OPF.Formulations.ac_opf_problem import NonlinearOPFResults
from VeraGridEngine.Simulations.OPF.ac_opf_worker import run_nonlinear_opf
from VeraGridEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.enumerations import AcOpfMode, SolverType


class BaselineEntry:
    """
    One AC baseline row parsed from the PGLIB markdown file.
    """
    __slots__ = (
        "group_name",
        "case_name",
        "nodes",
        "edges",
        "ac_objective",
        "ac_time_seconds",
    )

    def __init__(self,
                 group_name: str,
                 case_name: str,
                 nodes: int,
                 edges: int,
                 ac_objective: float,
                 ac_time_seconds: float) -> None:
        """
        Build one baseline entry.

        :param group_name: Benchmark group name such as ``TYP``, ``API`` or ``SAD``.
        :param case_name: PGLIB case stem without file extension.
        :param nodes: Number of buses from the baseline table.
        :param edges: Number of edges from the baseline table.
        :param ac_objective: Baseline AC objective value.
        :param ac_time_seconds: Baseline AC solve time in seconds.
        """
        self.group_name: str = group_name
        self.case_name: str = case_name
        self.nodes: int = nodes
        self.edges: int = edges
        self.ac_objective: float = ac_objective
        self.ac_time_seconds: float = ac_time_seconds


class BenchmarkRow:
    """
    One VeraGrid ACOPF benchmark result row.
    """
    __slots__ = (
        "group_name",
        "case_name",
        "file_path",
        "nodes",
        "edges",
        "baseline_ac_objective",
        "baseline_ac_time_seconds",
        "veragrid_ac_objective",
        "objective_gap_percent",
        "runtime_seconds",
        "iterations",
        "converged",
        "pf_init_used",
        "solver_error",
        "status",
    )

    def __init__(self) -> None:
        """
        Build one empty benchmark row so fields can be filled explicitly step by step.
        """
        self.group_name: str = ""
        self.case_name: str = ""
        self.file_path: str = ""
        self.nodes: int = 0
        self.edges: int = 0
        self.baseline_ac_objective: float = math.nan
        self.baseline_ac_time_seconds: float = math.nan
        self.veragrid_ac_objective: float = math.nan
        self.objective_gap_percent: float = math.nan
        self.runtime_seconds: float = math.nan
        self.iterations: int = 0
        self.converged: bool = False
        self.pf_init_used: bool = False
        self.solver_error: float = math.nan
        self.status: str = ""


class BenchmarkConfig:
    """
    Explicit benchmark configuration for the standalone ACOPF benchmark script.
    """
    __slots__ = (
        "ips_tolerance",
        "ips_iterations",
        "verbose",
        "output_path",
    )

    def __init__(self,
                 ips_tolerance: float,
                 ips_iterations: int,
                 verbose: int,
                 output_path: Path) -> None:
        """
        Build one immutable-like benchmark configuration object.

        :param ips_tolerance: IPS convergence tolerance.
        :param ips_iterations: Maximum IPS iterations.
        :param verbose: VeraGrid ACOPF verbosity.
        :param output_path: CSV file destination path.
        """
        self.ips_tolerance: float = ips_tolerance
        self.ips_iterations: int = ips_iterations
        self.verbose: int = verbose
        self.output_path: Path = output_path


def split_markdown_row(line: str) -> List[str]:
    """
    Split one markdown table row into stripped cell values.

    :param line: Markdown table row.
    :return: Cell values without the leading and trailing pipe characters.
    """
    parts_raw: List[str] = line.strip().split("|")
    parts: List[str] = list()
    for part in parts_raw[1:-1]:
        parts.append(part.strip())
    return parts


def parse_baseline_time(value: str) -> float:
    """
    Parse one baseline time cell from ``BASELINE.md``.

    :param value: Markdown cell content.
    :return: Solve time in seconds, using ``0.5`` for ``<1`` and ``inf`` for ``inf.``.
    """
    parsed_value: float

    if value == "<1":
        parsed_value = 0.5
    else:
        if value.lower().startswith("inf"):
            parsed_value = math.inf
        else:
            parsed_value = float(value)

    return parsed_value


def parse_baseline_float(value: str) -> float:
    """
    Parse one baseline numeric cell.

    :param value: Markdown cell content.
    :return: Parsed float, including ``inf`` values.
    """
    parsed_value: float

    if value.lower().startswith("inf"):
        parsed_value = math.inf
    else:
        parsed_value = float(value)

    return parsed_value


def parse_baseline_group_name(line: str) -> str:
    """
    Translate one section heading from the baseline markdown into the compact group code.

    :param line: Section heading line from the markdown file.
    :return: ``TYP``, ``API`` or ``SAD``.
    """
    group_name: str

    if "(TYP)" in line:
        group_name = "TYP"
    else:
        if "(API)" in line:
            group_name = "API"
        else:
            if "(SAD)" in line:
                group_name = "SAD"
            else:
                group_name = ""

    return group_name


def parse_baseline_file(baseline_path: Path) -> List[BaselineEntry]:
    """
    Parse the PGLIB baseline markdown and extract the AC objective/time rows.

    :param baseline_path: Path to ``BASELINE.md``.
    :return: Parsed baseline entries in file order.
    """
    entries: List[BaselineEntry] = list()
    active_group_name: str = ""

    with baseline_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line: str = raw_line.strip()

            if line.startswith("## "):
                parsed_group_name: str = parse_baseline_group_name(line)
                if parsed_group_name != "":
                    active_group_name = parsed_group_name
                else:
                    pass
            else:
                if line.startswith("| pglib_opf_case"):
                    cells: List[str] = split_markdown_row(line)
                    entry: BaselineEntry = BaselineEntry(
                        group_name=active_group_name,
                        case_name=cells[0],
                        nodes=int(cells[1]),
                        edges=int(cells[2]),
                        ac_objective=parse_baseline_float(cells[4]),
                        ac_time_seconds=parse_baseline_time(cells[8]),
                    )
                    entries.append(entry)
                else:
                    pass

    return entries


def build_baseline_lookup(entries: List[BaselineEntry]) -> dict[str, BaselineEntry]:
    """
    Build a lookup by case stem for quick baseline comparison.

    :param entries: Parsed baseline entries.
    :return: Lookup keyed by PGLIB case stem.
    """
    lookup: dict[str, BaselineEntry] = dict()

    for entry in entries:
        lookup[entry.case_name] = entry

    return lookup


def collect_case_files(pglib_root: Path) -> List[Path]:
    """
    Collect all benchmark case files that should be run by VeraGrid.

    :param pglib_root: Root directory of the PGLIB OPF benchmark archive.
    :return: Sorted list of ``.matpower`` case files.
    """
    case_files: List[Path] = list()

    for case_path in sorted(pglib_root.rglob("*.matpower")):
        # The baseline markdown only reports the top-level TYP set plus the API and SAD subsets.
        # Restricting the file list to these directories keeps the VeraGrid run aligned with PGLIB.
        if case_path.parent == pglib_root:
            case_files.append(case_path)
        else:
            if case_path.parent.name == "api" or case_path.parent.name == "sad":
                case_files.append(case_path)
            else:
                pass

    return case_files


def detect_case_group(case_path: Path, pglib_root: Path) -> str:
    """
    Detect the benchmark group from the case file location.

    :param case_path: Full path to one benchmark file.
    :param pglib_root: Root directory of the PGLIB OPF benchmark archive.
    :return: ``TYP``, ``API``, ``SAD`` or ``""`` when the file is outside the supported groups.
    """
    group_name: str

    if case_path.parent == pglib_root:
        group_name = "TYP"
    else:
        if case_path.parent.name == "api":
            group_name = "API"
        else:
            if case_path.parent.name == "sad":
                group_name = "SAD"
            else:
                group_name = ""

    return group_name


def compute_total_ac_objective(results: NonlinearOPFResults) -> float:
    """
    Compute the total AC objective from the nonlinear OPF result payload.

    :param results: VeraGrid nonlinear ACOPF results.
    :return: Total active-power generation cost.
    """
    total_cost: float = float(results.Pcost.sum())
    return total_cost


def compute_objective_gap_percent(veragrid_ac_objective: float, baseline_ac_objective: float) -> float:
    """
    Compute the relative gap between VeraGrid and the PGLIB AC baseline objective.

    :param veragrid_ac_objective: VeraGrid AC objective value.
    :param baseline_ac_objective: PGLIB baseline AC objective value.
    :return: Relative gap in percent.
    """
    gap_percent: float

    if math.isfinite(baseline_ac_objective) and baseline_ac_objective != 0.0:
        gap_percent = 100.0 * (veragrid_ac_objective - baseline_ac_objective) / baseline_ac_objective
    else:
        gap_percent = math.nan

    return gap_percent


def build_opf_options_with_pf_init(grid: MultiCircuit,
                                   ips_tolerance: float,
                                   ips_iterations: int,
                                   verbose: int) -> Tuple[OptimalPowerFlowOptions, bool]:
    """
    Build ACOPF options and, when possible, seed them with a converged power-flow point.

    :param grid: Loaded benchmark grid.
    :param ips_tolerance: IPS convergence tolerance.
    :param ips_iterations: Maximum IPS iterations.
    :param verbose: Solver verbosity level.
    :return: ``(opf_options, pf_init_used)``.
    """
    # First solve a plain PF because ACOPF is substantially more stable when it starts from a
    # physically consistent voltage profile instead of the flat or parser-provided default point.
    pf_options: PowerFlowOptions = PowerFlowOptions(control_q=False)
    pf_driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=pf_options)
    pf_driver.run()

    opf_options: OptimalPowerFlowOptions = OptimalPowerFlowOptions(
        ips_method=SolverType.NR,
        ips_tolerance=ips_tolerance,
        ips_iterations=ips_iterations,
        acopf_mode=AcOpfMode.ACOPFstd,
        verbose=verbose,
    )

    pf_init_used: bool = False

    # A converged PF point is the cheapest robust seed for the nonlinear OPF.
    if pf_driver.results is not None and pf_driver.results.converged:
        opf_options.ips_init_with_pf = True
        opf_options.acopf_v0 = pf_driver.results.voltage
        opf_options.acopf_S0 = pf_driver.results.Sbus
        pf_init_used = True
    else:
        opf_options.ips_init_with_pf = False
        pf_init_used = False

    return opf_options, pf_init_used


def benchmark_case(case_path: Path,
                   pglib_root: Path,
                   baseline_lookup: dict[str, BaselineEntry],
                   ips_tolerance: float,
                   ips_iterations: int,
                   verbose: int) -> BenchmarkRow:
    """
    Run VeraGrid ACOPF on one benchmark case and compare it against the baseline row.

    :param case_path: Full path to the ``.matpower`` case file.
    :param pglib_root: Root directory of the PGLIB archive.
    :param baseline_lookup: Baseline lookup by case stem.
    :param ips_tolerance: IPS convergence tolerance.
    :param ips_iterations: Maximum IPS iterations.
    :param verbose: Solver verbosity level.
    :return: Filled benchmark row.
    """
    row: BenchmarkRow = BenchmarkRow()
    row.case_name = case_path.stem
    row.file_path = str(case_path)
    row.group_name = detect_case_group(case_path=case_path, pglib_root=pglib_root)

    # Copy the baseline metadata first so the row stays informative even if VeraGrid later fails.
    baseline_entry: BaselineEntry | None = baseline_lookup.get(row.case_name, None)
    if baseline_entry is not None:
        row.baseline_ac_objective = baseline_entry.ac_objective
        row.baseline_ac_time_seconds = baseline_entry.ac_time_seconds
        row.nodes = baseline_entry.nodes
        row.edges = baseline_entry.edges
    else:
        pass

    start_time: float = timeit.default_timer()

    # Unsupported directories are not a hard error for the batch runner. Mark the row explicitly
    # and leave the rest of the run intact so one bad path does not destroy the whole benchmark.
    if row.group_name == "":
        row.status = "skipped:unknown_group"
    else:
        file_open_driver: FileOpen = FileOpen(file_name=str(case_path))
        try:
            # Load the Matpower case and refresh the topology counts from the parsed network so the
            # CSV reflects what VeraGrid actually solved, not only what the markdown baseline says.
            grid: MultiCircuit = file_open_driver.open()
            row.nodes = grid.get_bus_number()
            row.edges = grid.get_branch_number(add_vsc=False, add_hvdc=False, add_switch=True)

            opf_options, pf_init_used = build_opf_options_with_pf_init(
                grid=grid,
                ips_tolerance=ips_tolerance,
                ips_iterations=ips_iterations,
                verbose=verbose,
            )
            row.pf_init_used = pf_init_used

            # Run ACOPF with the same case file used by the baseline and extract the quantities that
            # matter for the comparison: objective value, convergence state, iterations and error.
            results: NonlinearOPFResults = run_nonlinear_opf(grid=grid, opf_options=opf_options)

            row.veragrid_ac_objective = compute_total_ac_objective(results=results)
            row.objective_gap_percent = compute_objective_gap_percent(
                veragrid_ac_objective=row.veragrid_ac_objective,
                baseline_ac_objective=row.baseline_ac_objective,
            )
            row.iterations = results.iterations
            row.converged = results.converged
            row.solver_error = results.error

            if results.converged:
                row.status = "ok"
            else:
                row.status = "not_converged"
        except (RuntimeError, ValueError, TypeError, ArithmeticError, OSError) as exc:
            row.status = f"failed:{exc.__class__.__name__}"
        else:
            pass

    row.runtime_seconds = timeit.default_timer() - start_time
    return row


def write_csv_results(rows: List[BenchmarkRow], output_path: Path) -> None:
    """
    Write the benchmark comparison table to CSV.

    :param rows: Benchmark rows in output order.
    :param output_path: CSV file destination.
    """
    # The CSV is the durable artifact for later analysis, so every solved or failed row is written.
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "group",
            "case_name",
            "file_path",
            "nodes",
            "edges",
            "baseline_ac_objective",
            "baseline_ac_time_seconds",
            "veragrid_ac_objective",
            "objective_gap_percent",
            "runtime_seconds",
            "iterations",
            "converged",
            "pf_init_used",
            "solver_error",
            "status",
        ])

        for row in rows:
            writer.writerow([
                row.group_name,
                row.case_name,
                row.file_path,
                row.nodes,
                row.edges,
                row.baseline_ac_objective,
                row.baseline_ac_time_seconds,
                row.veragrid_ac_objective,
                row.objective_gap_percent,
                row.runtime_seconds,
                row.iterations,
                row.converged,
                row.pf_init_used,
                row.solver_error,
                row.status,
            ])


def print_summary(rows: List[BenchmarkRow]) -> None:
    """
    Print a compact benchmark summary for quick terminal inspection.

    :param rows: Benchmark rows in output order.
    """
    total_cases: int = len(rows)
    converged_cases: int = 0
    failed_cases: int = 0

    for row in rows:
        # The summary intentionally groups hard failures and non-convergence together because both
        # outcomes mean the benchmark row did not produce a valid ACOPF optimum for comparison.
        if row.status == "ok":
            converged_cases += 1
        else:
            failed_cases += 1

    print(f"Cases: {total_cases}")
    print(f"Converged: {converged_cases}")
    print(f"Failed or not converged: {failed_cases}")


def build_benchmark_config(repo_root: Path) -> BenchmarkConfig:
    """
    Build the explicit configuration used by this standalone benchmark script.

    :param repo_root: Repository root path.
    :return: Benchmark configuration.
    """
    # Keep configuration centralized so the script stays importable and does not depend on CLI args.
    output_path: Path = repo_root / "benchmarks" / "nonlinear_opf" / "pglib_opf_veragrid_acopf_benchmark.csv"
    config: BenchmarkConfig = BenchmarkConfig(
        ips_tolerance=1e-6,
        ips_iterations=300,
        verbose=0,
        output_path=output_path,
    )
    return config


def main() -> None:
    """
    Execute the full PGLIB ACOPF benchmark run and write the CSV comparison table.

    :return: ``None``.
    """
    script_path: Path = Path(__file__).resolve()
    repo_root: Path = script_path.parents[2]
    config: BenchmarkConfig = build_benchmark_config(repo_root=repo_root)
    benchmark_root: Path = script_path.parent / "pglib-opf"
    baseline_path: Path = benchmark_root / "BASELINE.md"
    output_path: Path = config.output_path.resolve()

    baseline_entries: List[BaselineEntry] = parse_baseline_file(baseline_path=baseline_path)
    baseline_lookup: dict[str, BaselineEntry] = build_baseline_lookup(entries=baseline_entries)
    case_files: List[Path] = collect_case_files(pglib_root=benchmark_root)
    benchmark_rows: List[BenchmarkRow] = list()

    # Run the same file set used by the PGLIB baseline tables: TYP, API and SAD.
    for case_path in case_files:
        row: BenchmarkRow = benchmark_case(
            case_path=case_path,
            pglib_root=benchmark_root,
            baseline_lookup=baseline_lookup,
            ips_tolerance=config.ips_tolerance,
            ips_iterations=config.ips_iterations,
            verbose=config.verbose,
        )
        benchmark_rows.append(row)
        print(
            f"{row.case_name}: status={row.status}, converged={row.converged}, "
            f"objective={row.veragrid_ac_objective}, gap_pct={row.objective_gap_percent}, "
            f"time={row.runtime_seconds:.3f}s"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv_results(rows=benchmark_rows, output_path=output_path)
    print_summary(rows=benchmark_rows)
    print(f"CSV written to {output_path}")
    return None


if __name__ == "__main__":
    main()
else:
    pass
