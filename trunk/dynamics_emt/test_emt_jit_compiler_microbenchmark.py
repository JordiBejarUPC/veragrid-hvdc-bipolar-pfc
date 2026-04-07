# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json
import math
from typing import Dict, List


from trunk.dynamics_emt.benchmarks import emt_jit_compiler_microbenchmark as compiler_microbenchmark
from trunk.dynamics_emt.benchmarks import emt_jit_compiler_microbenchmark_statistics as compiler_microbenchmark_statistics


def test_compiler_microbenchmark_exports_for_rload_case() -> None:
    rows = compiler_microbenchmark.run_compiler_microbenchmark_suite(
        [compiler_microbenchmark.CompilerBenchmarkCase.RLOAD]
    )
    # TODO: Andrés, fix this ASAP
    exported_paths = compiler_microbenchmark.export_compiler_microbenchmark(
        rows,
        "emt_jit_compiler_microbenchmark_smoke_src_tests",
    )

    for export_path in exported_paths:
        assert export_path.is_file()
        assert export_path.stat().st_size > 0

    json_path = (
        compiler_microbenchmark.get_results_directory()
        / "emt_jit_compiler_microbenchmark_smoke_src_tests.json"
    )

    with open(json_path, "r", encoding="utf-8") as json_file:
        raw_rows_any: object = json.load(json_file)

    assert isinstance(raw_rows_any, list)
    raw_rows: List[Dict[str, object]] = list(raw_rows_any)
    assert len(raw_rows) == 1

    row = raw_rows[0]
    assert str(row["case"]) == "Rload"
    assert int(row["equation_count"]) > 0
    assert int(row["variable_count"]) > 0
    assert int(row["structural_group_count"]) > 0
    assert float(row["matrix_source_total_s"]) > 0.0
    assert float(row["matrix_njit_total_s"]) > 0.0

    metric_names: List[str] = [
        "residual_source_cse_on_s",
        "residual_njit_cse_on_s",
        "residual_cached_source_cse_on_s",
        "residual_cached_njit_cse_on_s",
        "residual_source_cse_off_s",
        "residual_njit_cse_off_s",
        "residual_cached_source_cse_off_s",
        "residual_cached_njit_cse_off_s",
        "ad_source_cse_on_s",
        "ad_njit_cse_on_s",
        "ad_cached_source_cse_on_s",
        "ad_cached_njit_cse_on_s",
        "ad_source_cse_off_s",
        "ad_njit_cse_off_s",
        "ad_cached_source_cse_off_s",
        "ad_cached_njit_cse_off_s",
        "matrix_cached_source_total_s",
        "matrix_cached_njit_total_s",
    ]

    for metric_name in metric_names:
        metric_value = float(row[metric_name])
        assert math.isfinite(metric_value)
        assert metric_value >= 0.0

    assert float(row["residual_cached_source_cse_on_s"]) <= float(row["residual_source_cse_on_s"])
    assert float(row["ad_cached_source_cse_on_s"]) <= float(row["ad_source_cse_on_s"])
    assert float(row["matrix_cached_source_total_s"]) <= float(row["matrix_source_total_s"])


def test_repeated_compiler_microbenchmark_exports_statistics() -> None:
    aggregated_rows = compiler_microbenchmark_statistics.run_repeated_compiler_microbenchmark(repetitions=2)
    # TODO: Andrés, fix this ASAP
    exported_paths = compiler_microbenchmark_statistics.export_repeated_compiler_microbenchmark(
        aggregated_rows,
        "emt_jit_compiler_microbenchmark_repeated_src_tests",
    )

    for export_path in exported_paths:
        assert export_path.is_file()
        assert export_path.stat().st_size > 0

    json_path = (
        compiler_microbenchmark.get_results_directory()
        / "emt_jit_compiler_microbenchmark_repeated_src_tests.json"
    )

    with open(json_path, "r", encoding="utf-8") as json_file:
        raw_rows_any: object = json.load(json_file)

    assert isinstance(raw_rows_any, list)
    raw_rows: List[Dict[str, object]] = list(raw_rows_any)
    assert len(raw_rows) == 3

    for row in raw_rows:
        metrics: Dict[str, Dict[str, float]] = dict(row["metrics"])
        assert metrics["residual_source_cse_on_s"]["median"] >= metrics["residual_cached_source_cse_on_s"]["median"]
        assert metrics["ad_source_cse_on_s"]["median"] >= metrics["ad_cached_source_cse_on_s"]["median"]
        assert metrics["matrix_source_total_s"]["median"] >= metrics["matrix_cached_source_total_s"]["median"]
