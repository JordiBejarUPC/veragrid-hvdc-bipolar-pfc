import json
import unittest
from pathlib import Path
from typing import Dict, List

from VeraGrid.trunk.dynamics_emt.benchmark_dependency_stubs import install_optional_dependency_stubs

install_optional_dependency_stubs()

import VeraGrid.trunk.dynamics_emt.emt_sparse_backend_benchmark_statistics as sparse_backend_stats
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_solver_loader import load_sparse_solver_backend_provider


class TestEmtSparseBackendBenchmarkStatistics(unittest.TestCase):
    """
    Validate repeated sparse backend benchmark statistics exports.
    """

    def test_repeated_sparse_backend_benchmark_exports_when_pardiso_is_available(self) -> None:
        """
        The repeated sparse backend benchmark must export aggregated files when the external backends are available.

        :return: None.
        :rtype: None
        """
        provider = load_sparse_solver_backend_provider("pardiso_pypardiso", "")

        if provider.is_available():
            pass
        else:
            self.skipTest("External Pardiso plugin runtime not installed for this environment")

        exported_paths = sparse_backend_stats.export_default_repeated_sparse_backend_paper_long(repetitions=2)
        path_index: int = 0

        while path_index < len(exported_paths):
            export_path: Path = exported_paths[path_index]
            with self.subTest(file=str(export_path)):
                self.assertTrue(export_path.is_file())
                self.assertGreater(export_path.stat().st_size, 0)
            path_index += 1

        json_path: Path = sparse_backend_stats.get_results_directory() / "emt_sparse_backend_ab_paper_long_repeated.json"

        with open(json_path, "r", encoding="utf-8") as json_file:
            raw_rows_any: object = json.load(json_file)

        self.assertIsInstance(raw_rows_any, list)
        raw_rows: List[Dict[str, object]] = list(raw_rows_any)
        self.assertGreaterEqual(len(raw_rows), 9)

        row_index: int = 0
        while row_index < len(raw_rows):
            row: Dict[str, object] = raw_rows[row_index]
            with self.subTest(case=str(row["case"]), solver_family=str(row["solver_family"]), sparse=str(row["sparse_solver"])):
                self.assertIn(str(row["solver_family"]), ("COMPILED", "VECTORIZED"))
                self.assertIn(str(row["sparse_solver"]), ("SuperLU", "Pardiso", "KLU"))
                self.assertGreaterEqual(float(dict(row["solver_build_s"])["median"]), 0.0)
                self.assertGreaterEqual(float(dict(row["simulate_s"])["median"]), 0.0)
                self.assertGreaterEqual(float(dict(row["solver_total_s"])["median"]), 0.0)
            row_index += 1


if __name__ == "__main__":
    unittest.main()
