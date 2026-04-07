# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json
from typing import Dict, List


from trunk.dynamics_emt.support.benchmark_dependency_stubs import install_optional_dependency_stubs

install_optional_dependency_stubs()

from trunk.dynamics_emt.benchmarks import emt_sparse_backend_benchmark as sparse_backend_benchmark
from trunk.dynamics_emt.benchmarks import emt_sparse_backend_benchmark_statistics as sparse_backend_stats


def test_sparse_backend_ab_benchmark_exports() -> None:
    rows = sparse_backend_benchmark.benchmark_sparse_backends(
        sparse_backend_benchmark.SparseBenchmarkProfile.RegressionShort
    )
    # TODO: Andrés, fix this ASAP
    exported_paths = sparse_backend_benchmark.export_sparse_backend_benchmark(
        rows,
        "emt_sparse_backend_ab_src_tests",
    )

    for export_path in exported_paths:
        assert export_path.is_file()
        assert export_path.stat().st_size > 0

    json_path = sparse_backend_benchmark.get_results_directory() / "emt_sparse_backend_ab_src_tests.json"

    with open(json_path, "r", encoding="utf-8") as json_file:
        raw_rows_any: object = json.load(json_file)

    assert isinstance(raw_rows_any, list)
    raw_rows: List[Dict[str, object]] = list(raw_rows_any)
    assert len(raw_rows) >= 6

    for row in raw_rows:
        assert str(row["solver_family"]) in ("COMPILED", "VECTORIZED")
        assert str(row["sparse_solver"]) in ("SuperLU", "Pardiso", "KLU")
        assert float(row["problem_build_s"]) >= 0.0
        assert float(row["simulate_s"]) >= 0.0
        assert float(row["y_max_abs_diff"]) < 1.0e-7
        assert float(row["dy_max_abs_diff"]) < 1.0e-7


def test_repeated_sparse_backend_benchmark_exports_statistics() -> None:
    aggregated_rows = sparse_backend_stats.run_repeated_sparse_backend_benchmark(
        sparse_backend_benchmark.SparseBenchmarkProfile.RegressionShort,
        repetitions=2,
    )
    # TODO: Andrés, fix this ASAP
    exported_paths = sparse_backend_stats.export_repeated_sparse_backend_benchmark(
        aggregated_rows,
        "emt_sparse_backend_ab_repeated_src_tests",
    )

    for export_path in exported_paths:
        assert export_path.is_file()
        assert export_path.stat().st_size > 0

    json_path = sparse_backend_stats.get_results_directory() / "emt_sparse_backend_ab_repeated_src_tests.json"

    with open(json_path, "r", encoding="utf-8") as json_file:
        raw_rows_any: object = json.load(json_file)

    assert isinstance(raw_rows_any, list)
    raw_rows: List[Dict[str, object]] = list(raw_rows_any)
    assert len(raw_rows) >= 6

    for row in raw_rows:
        assert str(row["solver_family"]) in ("COMPILED", "VECTORIZED")
        assert str(row["sparse_solver"]) in ("SuperLU", "Pardiso", "KLU")
        assert float(dict(row["solver_build_s"])["median"]) >= 0.0
        assert float(dict(row["simulate_s"])["median"]) >= 0.0
        assert float(dict(row["solver_total_s"])["median"]) >= 0.0
