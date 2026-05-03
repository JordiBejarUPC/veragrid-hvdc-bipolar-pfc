from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
else:
    pass

from trunk.dynamics_emt.scripting_xfmr_neutral_emt import run_xfmr_neutral_case
from trunk.implicit_solver_test_EMT.Demos.demo_xfmr_neutral_emt import run_demo


def test_xfmr_neutral_script_runs_without_plots_and_exports_pngs() -> None:
    traces = run_xfmr_neutral_case(enable_plots=False)

    assert len(traces["time"]) > 100
    assert Path(traces["voltage_png_path"]).exists()
    assert Path(traces["current_png_path"]).exists()
    assert float(np.max(np.abs(traces["xfmr_it_n"]))) > 1.0e-4
    assert float(np.max(np.abs(traces["load_i_n"]))) > 1.0e-4
    assert float(np.max(np.abs(traces["xfmr_it_a"]))) > 1.0e-4
    assert float(np.max(np.abs(traces["load_i_a"]))) > 1.0e-4


def test_xfmr_neutral_demo_wrapper_runs_without_plots() -> None:
    traces = run_demo(enable_plots=False)

    assert len(traces["time"]) > 100
    assert float(np.max(np.abs(traces["xfmr_it_n"]))) > 1.0e-4
