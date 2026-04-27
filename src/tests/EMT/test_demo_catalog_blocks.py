from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
else:
    pass

from trunk.implicit_solver_test_EMT.Demos.demo_lookup_table_catalog_block import run_lookup_table_catalog_demo
from trunk.implicit_solver_test_EMT.Demos.demo_triangle_pulse_source_catalog_block import run_triangle_pulse_source_demo


def test_lookup_table_catalog_demo_runs_and_shapes_signal() -> None:
    traces = run_lookup_table_catalog_demo(enable_plots=False)

    assert len(traces["time"]) > 100
    assert float(np.min(traces["yo_triangle_source_demo"])) >= -1.0e-9
    assert float(np.max(traces["yo_triangle_source_demo"])) <= 1.0 + 1.0e-9
    assert float(np.max(traces["yo_lookup_spline_demo"])) > 0.9
    assert float(np.max(traces["x_lookup_demo"])) > 0.1


def test_triangle_pulse_source_demo_runs_and_produces_pulses() -> None:
    traces = run_triangle_pulse_source_demo(enable_plots=False)

    assert len(traces["time"]) > 100
    assert float(np.min(traces["yo_triangle_source_demo"])) >= -1.0e-9
    assert float(np.max(traces["yo_triangle_source_demo"])) <= 1.0 + 1.0e-9
    assert float(np.max(traces["yo_pulse_from_triangle_demo"])) > 0.5
    assert float(np.min(traces["yo_pulse_from_triangle_demo"])) < 0.1
