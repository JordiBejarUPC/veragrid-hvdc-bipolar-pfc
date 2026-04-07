import json
import unittest
from pathlib import Path
from typing import Dict, List

from VeraGrid.trunk.dynamics_emt.support.benchmark_dependency_stubs import install_optional_dependency_stubs

install_optional_dependency_stubs()

import VeraGrid.trunk.dynamics_emt.benchmarks.emt_sparse_backend_benchmark as sparse_backend_benchmark
from VeraGridEngine.Utils.NumericalMethods.emt_sparse_solver_loader import load_sparse_solver_backend_provider


class TestEmtSparseBackendBenchmark(unittest.TestCase):
    """
    Validate the EMT sparse backend A/B benchmark exports.
    """

    def test_sparse_backend_ab_benchmark_exports_when_pardiso_is_available(self) -> None:
        """
        The sparse backend A/B benchmark must export valid files when the Pardiso plugin is available.

        :return: None.
        :rtype: None
        """
        provider = load_sparse_solver_backend_provider("pardiso_pypardiso", "")

        if provider.is_available():
            pass
        else:
            self.skipTest("External Pardiso plugin runtime not installed for this environment")

        # TODO: Andrés, fix this ASAP
        rows = sparse_backend_benchmark.benchmark_sparse_backends(
            sparse_backend_benchmark.SparseBenchmarkProfile.RegressionShort
        )
        self.assertGreater(len(rows), 0)

        output_dir: Path = sparse_backend_benchmark.get_results_directory()
        expected_files: List[Path] = list()
        expected_files.append(output_dir / "emt_sparse_backend_ab.csv")
        expected_files.append(output_dir / "emt_sparse_backend_ab.json")
        expected_files.append(output_dir / "emt_sparse_backend_ab.md")
        path_index: int = 0

        while path_index < len(expected_files):
            expected_path: Path = expected_files[path_index]
            with self.subTest(file=str(expected_path)):
                self.assertTrue(expected_path.is_file())
                self.assertGreater(expected_path.stat().st_size, 0)
            path_index += 1

        with open(output_dir / "emt_sparse_backend_ab.json", "r", encoding="utf-8") as json_file:
            raw_rows_any: object = json.load(json_file)

        self.assertIsInstance(raw_rows_any, list)
        raw_rows: List[Dict[str, object]] = list(raw_rows_any)
        self.assertGreaterEqual(len(raw_rows), 6)

        row_index: int = 0
        while row_index < len(raw_rows):
            row: Dict[str, object] = raw_rows[row_index]
            with self.subTest(case=str(row["case"]), solver_family=str(row["solver_family"]), sparse=str(row["sparse_solver"])):
                self.assertIn(str(row["solver_family"]), ("COMPILED", "VECTORIZED"))
                self.assertIn(str(row["sparse_solver"]), ("SuperLU", "Pardiso", "KLU"))
                self.assertGreaterEqual(float(row["problem_build_s"]), 0.0)
                self.assertGreaterEqual(float(row["simulate_s"]), 0.0)
                self.assertLess(float(row["y_max_abs_diff"]), 1.0e-7)
                self.assertLess(float(row["dy_max_abs_diff"]), 1.0e-7)
            row_index += 1


if __name__ == "__main__":
    unittest.main()
