from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def _ensure_repo_root_on_path() -> None:
    """
    Ensure the repository root is importable during direct pytest execution.

    :return: None.
    """
    repo_root: Path = Path(__file__).resolve().parents[3]

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    else:
        pass


_ensure_repo_root_on_path()

from trunk.dynamics_emt.scripting_jmarti_line_emt import run_jmarti_line_comparison
from trunk.dynamics_emt.support.jmarti_demo_support import JMartiLineComparisonResults
from trunk.dynamics_emt.support.jmarti_demo_support import is_jmarti_demo_internal_acceptance_passed
from trunk.implicit_solver_test_EMT.Demos.demo_jmarti_line_emt import run_demo


def test_jmarti_line_comparison_script_runs_without_plots_and_exports_pngs() -> None:
    results: JMartiLineComparisonResults = run_jmarti_line_comparison(enable_plots=False)

    assert len(results.pi_case.time) > 50
    assert len(results.bergeron_case.time) > 50
    assert len(results.jmarti_case.time) > 50
    assert results.voltage_png_path.exists()
    assert results.current_png_path.exists()
    assert results.voltage_delta_png_path.exists()
    assert results.current_delta_png_path.exists()
    assert results.metrics_txt_path.exists()
    assert np.isfinite(results.pi_case.load_v_a).all()
    assert np.isfinite(results.bergeron_case.load_v_a).all()
    assert np.isfinite(results.jmarti_case.load_v_a).all()
    assert np.isfinite(results.pi_case.comparison_i_a).all()
    assert np.isfinite(results.bergeron_case.comparison_i_a).all()
    assert np.isfinite(results.jmarti_case.comparison_i_a).all()
    assert results.event_time_s > 0.0
    assert results.pi_case.history_runtime_name == ""
    assert results.bergeron_case.history_runtime_name == "BergeronHistoryRuntime"
    assert results.jmarti_case.history_runtime_name == "JMartiHistoryRuntime"
    assert "JMARTI vs Bergeron comparison report" in results.metrics_txt_path.read_text(encoding="utf-8")
    assert "Internal acceptance passed: True" in results.metrics_txt_path.read_text(encoding="utf-8")
    assert is_jmarti_demo_internal_acceptance_passed(results)


def test_jmarti_line_demo_wrapper_runs_without_plots() -> None:
    results: JMartiLineComparisonResults = run_demo(enable_plots=False)

    assert len(results.jmarti_case.time) > 1
    assert np.isfinite(results.jmarti_case.comparison_i_a).all()
