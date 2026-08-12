# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Timing utilities for reproducible ANDES--VeraGrid RMS benchmarks."""

from __future__ import annotations

from pathlib import Path
import time

import pandas as pd


def elapsed_seconds(start_time: float) -> float:
    """Return elapsed wall-clock seconds from a performance-counter sample.

    :param start_time: Value previously returned by ``time.perf_counter``.
    :return: Elapsed seconds.
    """
    return float(time.perf_counter() - start_time)


def save_benchmark_timings(
    output_directory: Path,
    engine_label: str,
    case_label: str,
    timings: dict[str, float],
    state_count: int,
    mode_count: int,
) -> Path:
    """Write timing samples as machine-readable CSV and JSON artifacts.

    :param output_directory: Existing or new benchmark result directory.
    :param engine_label: Simulator name used in filenames and table rows.
    :param case_label: Benchmark case label.
    :param timings: Phase-to-seconds mapping.
    :param state_count: Number of retained physical states.
    :param mode_count: Number of exported eigenvalues.
    :return: Written CSV path.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = list()
    phase_name: str
    seconds: float
    for phase_name, seconds in timings.items():
        row: dict[str, object] = dict()
        row["engine"] = engine_label
        row["case"] = case_label
        row["phase"] = phase_name
        row["seconds"] = float(seconds)
        row["state_count"] = int(state_count)
        row["mode_count"] = int(mode_count)
        rows.append(row)
    timing_table: pd.DataFrame = pd.DataFrame(rows)
    csv_path: Path = output_directory / f"timings_results_{engine_label}_{case_label}.csv"
    json_path: Path = output_directory / f"timings_results_{engine_label}_{case_label}.json"
    timing_table.to_csv(csv_path, index=False, float_format="%.12g")
    timing_table.to_json(json_path, orient="records", indent=2)
    print("\nSmall-signal benchmark timings:")
    print(timing_table.loc[:, list(("phase", "seconds"))].to_string(index=False))
    print(f"Timing results written to: {csv_path}")
    return csv_path
