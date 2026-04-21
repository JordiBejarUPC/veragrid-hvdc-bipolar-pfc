# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json
import statistics
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from trunk.dynamics_emt.benchmarks.emt_solver_process_benchmark import (
    BenchmarkCase,
    BenchmarkMode,
    BenchmarkProfile,
    get_repo_root,
    run_worker_subprocess,
)

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
TIMING_REPETITIONS = 3
OUTPUT_DIR: Path = Path(__file__).resolve().parent / "Benchmark_waveform_degradation"


def _load_head_json(rel_path: str) -> Any:
    repo_root = get_repo_root()
    normalized_rel_path = rel_path.replace("\\", "/")
    text = subprocess.check_output(
        ["git", "show", f"HEAD:{normalized_rel_path}"],
        cwd=str(repo_root),
        text=True,
    )
    return json.loads(text)


def _run_worker(case_name: str, mode_name: str, solver_key: str) -> Dict[str, object]:
    payload = run_worker_subprocess(
        BenchmarkCase(case_name),
        BenchmarkProfile.REGRESSION_SHORT,
        BenchmarkMode(mode_name),
        solver_key,
    )
    return payload.get_payload()


def _assert_reasonable_regression(current_value: float, baseline_value: float, factor: float, label: str) -> None:
    assert current_value >= 0.0, f"Expected non-negative {label}, got {current_value}"
    assert baseline_value >= 0.0, f"Expected non-negative baseline {label}, got {baseline_value}"

    if baseline_value <= 1.0e-12:
        return

    assert current_value <= factor * baseline_value, (
        f"{label} regressed beyond envelope: current={current_value:.6e}, "
        f"baseline={baseline_value:.6e}, allowed_factor={factor:.2f}"
    )


def _median_float(rows: List[Dict[str, object]], key: str) -> float:
    return float(statistics.median(float(row[key]) for row in rows if key in row))


def _summarize_repeated_worker_rows(case_name: str, mode_name: str, solver_key: str) -> Dict[str, object]:
    repeated_rows: List[Dict[str, object]] = [
        _run_worker(case_name, mode_name, solver_key)
        for _ in range(TIMING_REPETITIONS)
    ]
    summary_row: Dict[str, object] = dict(repeated_rows[0])

    summary_row["timing_repetitions"] = TIMING_REPETITIONS
    summary_row["y_max_abs_diff"] = max(float(row.get("y_max_abs_diff", row.get("max_abs_diff", 0.0))) for row in repeated_rows)
    summary_row["dy_max_abs_diff"] = max(float(row.get("dy_max_abs_diff", 0.0)) for row in repeated_rows)

    if mode_name == "standard":
        summary_row["solver_total_s"] = _median_float(repeated_rows, "solver_total_s")
        summary_row["simulate_s"] = _median_float(repeated_rows, "simulate_s")
        summary_row["solver_build_s"] = _median_float(repeated_rows, "solver_build_s")
    else:
        summary_row["cold_sim_s"] = _median_float(repeated_rows, "cold_sim_s")
        summary_row["warm_sim_s"] = _median_float(repeated_rows, "warm_sim_s")

    return summary_row


def export_waveform_degradation_process_results(rows: List[Dict[str, object]]) -> List[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "benchmark_waveform_degradation_process_regression.json"
    csv_path = OUTPUT_DIR / "benchmark_waveform_degradation_process_regression.csv"
    md_path = OUTPUT_DIR / "benchmark_waveform_degradation_process_regression.md"

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(rows, json_file, indent=2)

    csv_lines: List[str] = [
        "case,mode,solver,timing_repetitions,y_max_abs_diff,dy_max_abs_diff,baseline_total_s,current_total_s,baseline_sim_s,current_sim_s,baseline_build_s,current_build_s,baseline_cold_sim_s,current_cold_sim_s,baseline_warm_sim_s,current_warm_sim_s"
    ]
    markdown_lines: List[str] = [
        "| Case | Mode | Solver | Reps | Y diff | dY diff | Base total [s] | Current total [s] | Base sim [s] | Current sim [s] | Base build [s] | Current build [s] | Base cold sim [s] | Current cold sim [s] | Base warm sim [s] | Current warm sim [s] |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for row in rows:
        csv_lines.append(
            f"{row['case']},{row['mode']},{row['solver']},{int(row['timing_repetitions'])},{float(row['y_max_abs_diff']):.12e},{float(row['dy_max_abs_diff']):.12e},"
            f"{float(row['baseline_total_s']):.12e},{float(row['current_total_s']):.12e},{float(row['baseline_sim_s']):.12e},"
            f"{float(row['current_sim_s']):.12e},{float(row['baseline_build_s']):.12e},{float(row['current_build_s']):.12e},"
            f"{float(row['baseline_cold_sim_s']):.12e},{float(row['current_cold_sim_s']):.12e},{float(row['baseline_warm_sim_s']):.12e},"
            f"{float(row['current_warm_sim_s']):.12e}"
        )
        markdown_lines.append(
            f"| {row['case']} | {row['mode']} | {row['solver']} | {int(row['timing_repetitions'])} | {float(row['y_max_abs_diff']):.3e} | {float(row['dy_max_abs_diff']):.3e} | "
            f"{float(row['baseline_total_s']):.6f} | {float(row['current_total_s']):.6f} | {float(row['baseline_sim_s']):.6f} | "
            f"{float(row['current_sim_s']):.6f} | {float(row['baseline_build_s']):.6f} | {float(row['current_build_s']):.6f} | "
            f"{float(row['baseline_cold_sim_s']):.6f} | {float(row['current_cold_sim_s']):.6f} | {float(row['baseline_warm_sim_s']):.6f} | "
            f"{float(row['current_warm_sim_s']):.6f} |"
        )

    with open(csv_path, "w", encoding="utf-8", newline="") as csv_file:
        csv_file.write("\n".join(csv_lines) + "\n")
    with open(md_path, "w", encoding="utf-8") as md_file:
        md_file.write("\n".join(markdown_lines) + "\n")

    return [json_path, csv_path, md_path]


def run_regression_short_process_benchmark_demo() -> List[Dict[str, object]]:
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
    exported_rows: List[Dict[str, object]] = list()

    for case_name in cases:
        for solver_key in solvers:
            standard_row = _summarize_repeated_worker_rows(case_name, "standard", solver_key)
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

            exported_rows.append(
                {
                    "case": case_name,
                    "mode": "standard",
                    "solver": solver_key,
                    "timing_repetitions": int(standard_row["timing_repetitions"]),
                    "y_max_abs_diff": max_abs_diff,
                    "dy_max_abs_diff": float(standard_row.get("dy_max_abs_diff", 0.0)),
                    "baseline_total_s": float(standard_base["total_s"]),
                    "current_total_s": float(standard_row["solver_total_s"]),
                    "baseline_sim_s": float(standard_base["sim_s"]),
                    "current_sim_s": float(standard_row["simulate_s"]),
                    "baseline_build_s": float(standard_base["build_s"]),
                    "current_build_s": float(standard_row["solver_build_s"]),
                    "baseline_cold_sim_s": 0.0,
                    "current_cold_sim_s": 0.0,
                    "baseline_warm_sim_s": 0.0,
                    "current_warm_sim_s": 0.0,
                }
            )

            cold_warm_row = _summarize_repeated_worker_rows(case_name, "cold_warm", solver_key)
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

            exported_rows.append(
                {
                    "case": case_name,
                    "mode": "cold_warm",
                    "solver": solver_key,
                    "timing_repetitions": int(cold_warm_row["timing_repetitions"]),
                    "y_max_abs_diff": cold_warm_max_abs_diff,
                    "dy_max_abs_diff": float(cold_warm_row.get("dy_max_abs_diff", 0.0)),
                    "baseline_total_s": 0.0,
                    "current_total_s": 0.0,
                    "baseline_sim_s": 0.0,
                    "current_sim_s": 0.0,
                    "baseline_build_s": 0.0,
                    "current_build_s": 0.0,
                    "baseline_cold_sim_s": float(cold_warm_base["cold_sim_s"]),
                    "current_cold_sim_s": float(cold_warm_row["cold_sim_s"]),
                    "baseline_warm_sim_s": float(cold_warm_base["warm_sim_s"]),
                    "current_warm_sim_s": float(cold_warm_row["warm_sim_s"]),
                }
            )

    exported_paths = export_waveform_degradation_process_results(exported_rows)
    print("Exported process regression demo artifacts:")
    for export_path in exported_paths:
        print(f"- {export_path}")

    return exported_rows


if __name__ == "__main__":
    run_regression_short_process_benchmark_demo()
