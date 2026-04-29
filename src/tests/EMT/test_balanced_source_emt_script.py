# SPDX-License-Identifier: MPL-2.0

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

from trunk.dynamics_emt.scripting_balanced_source_emt import run_balanced_source_emt_demos
from trunk.implicit_solver_test_EMT.Demos.demo_balanced_source_emt import run_demo


def test_balanced_source_emt_script_runs_without_plots_and_exports_case_pngs() -> None:
    results = run_balanced_source_emt_demos(enable_plots=False)

    assert set(results.keys()) == {
        "balanced_3ph_current_source",
        "balanced_3ph_voltage_source",
        "controlled_balanced_3ph_current_source",
        "controlled_balanced_3ph_voltage_source",
    }

    for case_result in results.values():
        assert len(case_result.time) > 10
        assert np.isfinite(case_result.amplitude_reference).all()
        assert np.isfinite(case_result.amplitude_command).all()
        assert np.isfinite(case_result.bus_voltage_a).all()
        assert np.isfinite(case_result.bus_voltage_b).all()
        assert np.isfinite(case_result.bus_voltage_c).all()
        assert np.isfinite(case_result.source_current_a).all()
        assert np.isfinite(case_result.source_current_b).all()
        assert np.isfinite(case_result.source_current_c).all()
        assert Path(case_result.png_path).exists()


def test_balanced_source_emt_demo_wrapper_runs_without_plots() -> None:
    results = run_demo(enable_plots=False)

    assert "controlled_balanced_3ph_voltage_source" in results
    assert len(results["controlled_balanced_3ph_voltage_source"].time) > 10
