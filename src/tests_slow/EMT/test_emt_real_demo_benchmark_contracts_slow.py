# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import matplotlib
import pytest


pytestmark = pytest.mark.slow

if os.environ.get("VERAGRID_RUN_EMT_SLOW_BENCHMARKS") != "1":
    pytest.skip(
        "Set VERAGRID_RUN_EMT_SLOW_BENCHMARKS=1 to run slow EMT benchmark contract tests.",
        allow_module_level=True,
    )


matplotlib.use("Agg")

REPO_ROOT = Path(__file__).resolve().parents[3]


from trunk.dynamics_emt.support.benchmark_dependency_stubs import install_optional_dependency_stubs

install_optional_dependency_stubs()

import trunk.dynamics_emt.scripting_emt_event as emt_event_script
import trunk.dynamics_emt.scripting_example_thevequiv_piline_Rload_emt as rload_script
import trunk.dynamics_emt.scripting_example_thevequiv_piline_ZIPload_emt as zipload_script


EXPECTED_SOLVER_ORDER: Tuple[str, ...] = ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED")


@dataclass(frozen=True)
class NormalizedBenchmarkRow:
    solver_key: str
    problem_build_s: float
    solver_init_s: float
    solver_build_s: float
    simulate_s: float
    solver_total_s: float
    loop_s: float
    y_max_abs_diff: float
    dy_max_abs_diff: float
    steps: int
    y_shape: Tuple[int, ...]
    dy_shape: Tuple[int, ...]
    build_stats: Dict[str, float]
    final_residual_inf: float


def _configure_scripts_for_short_regression() -> None:
    rload_script.options.time_step = 5e-5
    rload_script.options.simulation_time = 5e-4
    rload_script.SOLVER_VERBOSE = False
    rload_script.ENABLE_NEWTON_TRACE = False

    zipload_script.options.time_step = 5e-5
    zipload_script.options.simulation_time = 5e-4
    zipload_script.SOLVER_VERBOSE = False
    zipload_script.ENABLE_NEWTON_TRACE = False

    emt_event_script.options.time_step = 1e-3
    emt_event_script.options.simulation_time = 5e-2
    emt_event_script.SOLVER_VERBOSE = False
    emt_event_script.ENABLE_NEWTON_TRACE = False

def _normalize_build_stats(build_stats_any: object) -> Dict[str, float]:
    if isinstance(build_stats_any, dict):
        return {str(key): float(value) for key, value in build_stats_any.items()}

    return dict()


def _normalize_dict_row(raw_row: Dict[str, object]) -> NormalizedBenchmarkRow:
    return NormalizedBenchmarkRow(
        solver_key=str(raw_row["solver"]),
        problem_build_s=float(raw_row["problem_build_s"]),
        solver_init_s=float(raw_row["solver_init_s"]),
        solver_build_s=float(raw_row["solver_build_s"]),
        simulate_s=float(raw_row["simulate_s"]),
        solver_total_s=float(raw_row["solver_total_s"]),
        loop_s=float(raw_row["loop_s"]),
        y_max_abs_diff=float(raw_row["max_abs_diff"]),
        dy_max_abs_diff=float(raw_row["max_abs_diff"]),
        steps=int(raw_row["steps"]),
        y_shape=tuple(int(value) for value in tuple(raw_row["shape"])),
        dy_shape=tuple(int(value) for value in tuple(raw_row["dy_shape"])),
        build_stats=_normalize_build_stats(raw_row["build_stats"]),
        final_residual_inf=math.nan,
    )


def _normalize_zipload_row(raw_row: Any) -> NormalizedBenchmarkRow:
    trace_summary = raw_row.get_trace_summary()
    return NormalizedBenchmarkRow(
        solver_key=str(raw_row.get_solver_key()),
        problem_build_s=float(raw_row.get_problem_build_s()),
        solver_init_s=float(raw_row.get_solver_init_s()),
        solver_build_s=float(raw_row.get_solver_build_s()),
        simulate_s=float(raw_row.get_simulate_s()),
        solver_total_s=float(raw_row.get_solver_total_s()),
        loop_s=float(raw_row.get_loop_s()),
        y_max_abs_diff=float(raw_row.get_y_max_abs_diff()),
        dy_max_abs_diff=float(raw_row.get_dy_max_abs_diff()),
        steps=int(raw_row._steps),
        y_shape=tuple(int(value) for value in raw_row._y_shape),
        dy_shape=tuple(int(value) for value in raw_row._dy_shape),
        build_stats=_normalize_build_stats(raw_row.get_build_stats()),
        final_residual_inf=float(trace_summary.get_final_residual_inf()),
    )


def _normalize_rows(raw_rows: Sequence[object]) -> List[NormalizedBenchmarkRow]:
    normalized_rows: List[NormalizedBenchmarkRow] = list()

    for raw_row in raw_rows:
        if isinstance(raw_row, dict):
            normalized_rows.append(_normalize_dict_row(raw_row))
        else:
            normalized_rows.append(_normalize_zipload_row(raw_row))

    return normalized_rows


@pytest.fixture(scope="module")
def real_demo_standard_benchmark_rows() -> Dict[str, List[NormalizedBenchmarkRow]]:
    _configure_scripts_for_short_regression()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(rload_script, "export_benchmark_results", lambda results, file_stem: None)
        monkeypatch.setattr(zipload_script, "export_benchmark_results", lambda results, file_stem: None)
        monkeypatch.setattr(emt_event_script, "export_benchmark_results", lambda results, file_stem: None)
        return {
            "thevenin_pi_rload": _normalize_rows(rload_script.benchmark_all_solvers()),
            "thevenin_pi_zipload": _normalize_rows(zipload_script.benchmark_all_solvers()),
            "emt_event": _normalize_rows(emt_event_script.benchmark_all_solvers()),
        }


def test_real_demo_benchmarks_expose_the_common_contract(
    real_demo_standard_benchmark_rows: Dict[str, List[NormalizedBenchmarkRow]],
) -> None:
    for case_name, rows in real_demo_standard_benchmark_rows.items():
        assert len(rows) == len(EXPECTED_SOLVER_ORDER), case_name
        assert tuple(row.solver_key for row in rows) == EXPECTED_SOLVER_ORDER, case_name

        reference_steps = rows[0].steps
        reference_y_shape = rows[0].y_shape
        reference_dy_shape = rows[0].dy_shape

        for row in rows:
            assert math.isfinite(row.problem_build_s) and row.problem_build_s > 0.0
            assert math.isfinite(row.solver_init_s) and row.solver_init_s >= 0.0
            assert math.isfinite(row.solver_build_s) and row.solver_build_s >= 0.0
            assert math.isfinite(row.simulate_s) and row.simulate_s > 0.0
            assert math.isfinite(row.solver_total_s) and row.solver_total_s > 0.0
            assert row.steps == reference_steps
            assert row.y_shape == reference_y_shape
            assert row.dy_shape == reference_dy_shape
            assert row.steps > 0
            assert row.y_max_abs_diff >= 0.0
            assert row.dy_max_abs_diff >= 0.0

            if math.isnan(row.loop_s):
                assert math.isnan(row.loop_s)
            else:
                assert math.isfinite(row.loop_s) and row.loop_s > 0.0

            assert len(row.build_stats) > 0


def test_real_demo_benchmarks_keep_cross_backend_differences_bounded(
    real_demo_standard_benchmark_rows: Dict[str, List[NormalizedBenchmarkRow]],
) -> None:
    case_tolerances: Dict[str, Tuple[float, float]] = {
        "thevenin_pi_rload": (3.5e-2, 1.0e-1),
        "emt_event": (6.5e-2, 1.0e-1),
    }
    zip_case_tolerances: Tuple[float, float] = (8.5e-2, 2.0e2)

    for case_name in ("thevenin_pi_rload", "emt_event"):
        y_tol, dy_tol = case_tolerances[case_name]
        rows = real_demo_standard_benchmark_rows[case_name]

        for row in rows[1:]:
            assert row.y_max_abs_diff < y_tol, (case_name, row.solver_key, row.y_max_abs_diff, y_tol)
            assert row.dy_max_abs_diff < dy_tol, (case_name, row.solver_key, row.dy_max_abs_diff, dy_tol)

    for row in real_demo_standard_benchmark_rows["thevenin_pi_zipload"][1:]:
        assert row.y_max_abs_diff < zip_case_tolerances[0]
        assert math.isfinite(row.dy_max_abs_diff)
        assert row.dy_max_abs_diff < zip_case_tolerances[1]
        assert math.isfinite(row.final_residual_inf) or math.isnan(row.final_residual_inf)
