import json
import math
import unittest
from pathlib import Path
from typing import Dict, List

import VeraGrid.trunk.dynamics_emt.emt_jit_compiler_microbenchmark as compiler_microbenchmark
import VeraGrid.trunk.dynamics_emt.emt_jit_compiler_microbenchmark_statistics as compiler_microbenchmark_statistics


class TestEmtJitCompilerMicrobenchmark(unittest.TestCase):
    """
    Validate the EMT JIT compiler microbenchmark exports.
    """

    def test_compiler_microbenchmark_exports_for_rload_case(self) -> None:
        """
        The compiler microbenchmark must export valid files and positive timings.

        :return: None.
        :rtype: None
        """
        rows = compiler_microbenchmark.run_compiler_microbenchmark_suite(
            [compiler_microbenchmark.CompilerBenchmarkCase.RLOAD]
        )
        exported_paths = compiler_microbenchmark.export_compiler_microbenchmark(
            rows,
            "emt_jit_compiler_microbenchmark_smoke",
        )
        path_index: int = 0

        while path_index < len(exported_paths):
            export_path: Path = exported_paths[path_index]
            with self.subTest(file=str(export_path)):
                self.assertTrue(export_path.is_file())
                self.assertGreater(export_path.stat().st_size, 0)
            path_index += 1

        json_path: Path = compiler_microbenchmark.get_results_directory() / "emt_jit_compiler_microbenchmark_smoke.json"

        with open(json_path, "r", encoding="utf-8") as json_file:
            raw_rows_any: object = json.load(json_file)

        self.assertIsInstance(raw_rows_any, list)
        raw_rows: List[Dict[str, object]] = list(raw_rows_any)
        self.assertEqual(len(raw_rows), 1)

        row: Dict[str, object] = raw_rows[0]
        self.assertEqual(str(row["case"]), "Rload")
        self.assertGreater(int(row["equation_count"]), 0)
        self.assertGreater(int(row["variable_count"]), 0)
        self.assertGreater(int(row["structural_group_count"]), 0)
        self.assertGreater(float(row["matrix_source_total_s"]), 0.0)
        self.assertGreater(float(row["matrix_njit_total_s"]), 0.0)

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
        metric_index: int = 0

        while metric_index < len(metric_names):
            metric_value: float = float(row[metric_names[metric_index]])
            with self.subTest(metric=metric_names[metric_index]):
                self.assertTrue(math.isfinite(metric_value))
                self.assertGreaterEqual(metric_value, 0.0)
            metric_index += 1

        self.assertLessEqual(float(row["residual_cached_source_cse_on_s"]), float(row["residual_source_cse_on_s"]))
        self.assertLessEqual(float(row["ad_cached_source_cse_on_s"]), float(row["ad_source_cse_on_s"]))
        self.assertLessEqual(float(row["matrix_cached_source_total_s"]), float(row["matrix_source_total_s"]))

    def test_repeated_compiler_microbenchmark_exports_statistics(self) -> None:
        """
        The repeated compiler microbenchmark must export aggregated statistics.

        :return: None.
        :rtype: None
        """
        exported_paths = compiler_microbenchmark_statistics.export_default_repeated_compiler_microbenchmark(repetitions=2)
        path_index: int = 0

        while path_index < len(exported_paths):
            export_path: Path = exported_paths[path_index]
            with self.subTest(file=str(export_path)):
                self.assertTrue(export_path.is_file())
                self.assertGreater(export_path.stat().st_size, 0)
            path_index += 1

        json_path: Path = compiler_microbenchmark.get_results_directory() / "emt_jit_compiler_microbenchmark_repeated.json"

        with open(json_path, "r", encoding="utf-8") as json_file:
            raw_rows_any: object = json.load(json_file)

        self.assertIsInstance(raw_rows_any, list)
        raw_rows: List[Dict[str, object]] = list(raw_rows_any)
        self.assertEqual(len(raw_rows), 4)

        row_index: int = 0
        while row_index < len(raw_rows):
            metrics: Dict[str, Dict[str, float]] = dict(raw_rows[row_index]["metrics"])
            with self.subTest(case=str(raw_rows[row_index]["case"])):
                self.assertGreaterEqual(metrics["residual_source_cse_on_s"]["median"], metrics["residual_cached_source_cse_on_s"]["median"])
                self.assertGreaterEqual(metrics["ad_source_cse_on_s"]["median"], metrics["ad_cached_source_cse_on_s"]["median"])
                self.assertGreaterEqual(metrics["matrix_source_total_s"]["median"], metrics["matrix_cached_source_total_s"]["median"])
            row_index += 1


if __name__ == "__main__":
    unittest.main()
