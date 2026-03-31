# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest


pytestmark = pytest.mark.slow

if os.environ.get("VERAGRID_RUN_EMT_SLOW_BENCHMARKS") != "1":
    pytest.skip(
        "Set VERAGRID_RUN_EMT_SLOW_BENCHMARKS=1 to run slow EMT benchmark regression tests.",
        allow_module_level=True,
    )


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
WORKER_MODULE = "trunk.dynamics_emt.benchmarks.emt_solver_process_benchmark_worker"

CASE_Y_TOLERANCES: Dict[str, float] = {
    "zipload": 8.5e-2,
    "rload": 3.5e-2,
    "event": 6.5e-2,
}
CASE_DY_TOLERANCES: Dict[str, float] = {
    "zipload": 2.0e2,
    "rload": 1.0e-1,
    "event": 1.0e-1,
}


def _build_worker_env() -> Dict[str, str]:
    env = dict(os.environ)
    previous_pythonpath = env.get("PYTHONPATH", "")
    entries = [str(REPO_ROOT), str(SRC_ROOT)]

    if previous_pythonpath:
        entries.append(previous_pythonpath)

    env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def _load_head_json(rel_path: str) -> Any:
    text = subprocess.check_output(
        ["git", "show", f"HEAD:{rel_path.replace(os.sep, '/')}"] ,
        cwd=str(REPO_ROOT),
        text=True,
    )
    return json.loads(text)


def _run_worker(case_name: str, mode_name: str, solver_key: str) -> Dict[str, object]:
    output = subprocess.check_output(
        [
            sys.executable,
            "-m",
            WORKER_MODULE,
            "--case",
            case_name,
            "--profile",
            "regression_short",
            "--mode",
            mode_name,
            "--solver",
            solver_key,
        ],
        cwd=str(REPO_ROOT),
        env=_build_worker_env(),
        text=True,
    )
    return dict(json.loads(output))


def _assert_reasonable_regression(current_value: float, baseline_value: float, factor: float, label: str) -> None:
    assert current_value >= 0.0, f"Expected non-negative {label}, got {current_value}"
    assert baseline_value >= 0.0, f"Expected non-negative baseline {label}, got {baseline_value}"

    if baseline_value <= 1.0e-12:
        return

    assert current_value <= factor * baseline_value, (
        f"{label} regressed beyond envelope: current={current_value:.6e}, "
        f"baseline={baseline_value:.6e}, allowed_factor={factor:.2f}"
    )


def test_regression_short_process_benchmarks_stay_within_numeric_and_timing_envelopes() -> None:
    standard_baseline_rows = _load_head_json(
        "trunk/dynamics_emt/benchmark_results/emt_solver_regression_short_standard_process_cold.json"
    )
    cold_warm_baseline_rows = _load_head_json(
        "trunk/dynamics_emt/benchmark_results/emt_solver_regression_short_cold_warm_process.json"
    )

    standard_baseline = {
        (str(row["case"]).lower(), str(row["solver"])): dict(row)
        for row in standard_baseline_rows
    }
    cold_warm_baseline = {
        (str(row["case"]).lower(), str(row["solver"])): dict(row)
        for row in cold_warm_baseline_rows
    }

    cases = ("zipload", "rload", "event")
    solvers = ("SYMBOLIC", "AD", "VECTORIZED", "COMPILED")

    for case_name in cases:
        for solver_key in solvers:
            standard_row = _run_worker(case_name, "standard", solver_key)
            standard_base = standard_baseline[(case_name, solver_key)]

            max_abs_diff = float(standard_row.get("y_max_abs_diff", standard_row.get("max_abs_diff", 0.0)))
            assert max_abs_diff < CASE_Y_TOLERANCES[case_name]

            if "dy_max_abs_diff" in standard_row:
                assert float(standard_row["dy_max_abs_diff"]) < CASE_DY_TOLERANCES[case_name]

            _assert_reasonable_regression(
                float(standard_row["solver_total_s"]),
                float(standard_base["total_s"]),
                2.5,
                f"standard total {case_name}/{solver_key}",
            )
            _assert_reasonable_regression(
                float(standard_row["simulate_s"]),
                float(standard_base["sim_s"]),
                2.5,
                f"standard simulate {case_name}/{solver_key}",
            )
            _assert_reasonable_regression(
                float(standard_row["solver_build_s"]),
                float(standard_base["build_s"]),
                2.5,
                f"standard build {case_name}/{solver_key}",
            )

            cold_warm_row = _run_worker(case_name, "cold_warm", solver_key)
            cold_warm_base = cold_warm_baseline[(case_name, solver_key)]

            cold_warm_max_abs_diff = float(cold_warm_row.get("y_max_abs_diff", cold_warm_row.get("max_abs_diff", 0.0)))
            assert cold_warm_max_abs_diff < 1.0e-4

            if "dy_max_abs_diff" in cold_warm_row:
                assert float(cold_warm_row["dy_max_abs_diff"]) < 1.0e-4

            _assert_reasonable_regression(
                float(cold_warm_row["cold_sim_s"]),
                float(cold_warm_base["cold_sim_s"]),
                2.5,
                f"cold sim {case_name}/{solver_key}",
            )
            _assert_reasonable_regression(
                float(cold_warm_row["warm_sim_s"]),
                float(cold_warm_base["warm_sim_s"]),
                3.0,
                f"warm sim {case_name}/{solver_key}",
            )
