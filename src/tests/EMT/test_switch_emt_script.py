from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
else:
    pass

from trunk.dynamics_emt.scripting_switch_emt import run_switch_emt_case
from trunk.implicit_solver_test_EMT.Demos.demo_switch_emt import run_demo


def test_switch_emt_script_runs_without_plots() -> None:
    traces = run_switch_emt_case(enable_plots=False)

    assert len(traces["time"]) > 100
    assert float(traces["switch_mode"].max()) > 0.5
    assert float(traces["switch_mode"].min()) < 0.5
    transition_count = int(np.count_nonzero(np.abs(np.diff(traces["switch_mode"])) > 0.5))
    assert transition_count >= 4
    assert Path(traces["mode_png_path"]).exists()
    assert Path(traces["response_png_path"]).exists()


def test_switch_emt_implicit_demo_wrapper_runs_without_plots() -> None:
    traces = run_demo(enable_plots=False)

    assert len(traces["time"]) > 100
    assert float(traces["switch_mode"].max()) > 0.5
    assert float(traces["switch_mode"].min()) < 0.5
