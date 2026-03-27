from pathlib import Path
from typing import List

from VeraGrid.trunk.dynamics_emt.emt_solver_process_benchmark import (
    BenchmarkCase,
    BenchmarkMode,
    BenchmarkProfile,
    ProcessBenchmarkRow,
    export_process_cold_suite,
    run_process_cold_suite,
)
from VeraGrid.trunk.dynamics_emt.emt_solver_process_report import export_paper_long_mode_reports
from VeraGrid.trunk.dynamics_emt.emt_solver_process_statistics import (
    export_repeated_raw_samples,
    export_repeated_statistics,
    run_repeated_process_suite,
)


PAPER_LONG_REPETITIONS: int = 3


def export_paper_long_process_cold_summary() -> List[Path]:
    """
    Run and export the long fresh-process benchmark suite intended for paper tables.

    :return: Exported file paths.
    :rtype: List[Path]
    """
    cases: List[BenchmarkCase] = [BenchmarkCase.ZIPLOAD, BenchmarkCase.RLOAD, BenchmarkCase.EVENT]
    rows: List[ProcessBenchmarkRow] = list()
    rows.extend(run_process_cold_suite(BenchmarkProfile.PAPER_LONG, cases, BenchmarkMode.STANDARD))
    rows.extend(run_process_cold_suite(BenchmarkProfile.PAPER_LONG, cases, BenchmarkMode.COLD_WARM))
    exported_paths: List[Path] = export_process_cold_suite(rows, "emt_solver_process_cold_paper_long")
    exported_paths.extend(export_paper_long_mode_reports())

    repeated_samples = run_repeated_process_suite(
        profile=BenchmarkProfile.PAPER_LONG,
        cases=cases,
        modes=[BenchmarkMode.STANDARD, BenchmarkMode.COLD_WARM],
        repetitions=PAPER_LONG_REPETITIONS,
    )
    exported_paths.extend(export_repeated_raw_samples(repeated_samples, "emt_solver_process_cold_paper_long_repeated_samples"))
    exported_paths.extend(export_repeated_statistics(repeated_samples, "emt_solver_paper_long_repeated"))
    return exported_paths


def main() -> None:
    """
    Execute the paper-grade fresh-process benchmark suite.

    :return: None.
    :rtype: None
    """
    export_paper_long_process_cold_summary()


if __name__ == "__main__":
    main()
