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

from trunk.dynamics_emt.scripting_nonlinear_resistor_emt import NonlinearResistorEmtCaseResults
from trunk.dynamics_emt.scripting_nonlinear_resistor_emt import run_nonlinear_resistor_case
from trunk.implicit_solver_test_EMT.Demos.demo_nonlinear_resistor_emt import run_demo


def test_nonlinear_resistor_script_runs_without_plots_and_exports_pngs() -> None:
    traces: NonlinearResistorEmtCaseResults = run_nonlinear_resistor_case(enable_plots=False)

    assert len(traces.time) > 100
    assert len(traces.curve_voltage) > 100
    assert len(traces.curve_current) > 100
    assert traces.waveform_png_path.exists()
    assert traces.vi_png_path.exists()
    assert float(np.max(np.abs(traces.bus_v_n))) > 1.0e-4
    assert float(np.max(traces.resistor_i_n)) > 1.0e-6
    assert float(np.max(np.abs(traces.line_it_n))) > 1.0e-6
    assert float(np.max(np.abs(traces.source_ground_i_n))) > 1.0e-6
    assert float(traces.max_abs_lookup_error) < 1.0e-10
    assert float(traces.max_abs_load_bus_kcl_error) < 1.0e-5
    assert float(traces.max_abs_source_bus_kcl_error) < 1.0e-5
    assert np.allclose(
        np.asarray(traces.resistor_i_n, dtype=float),
        np.asarray(traces.expected_current, dtype=float),
        atol=1.0e-10,
    )


def test_nonlinear_resistor_demo_wrapper_runs_without_plots() -> None:
    traces: NonlinearResistorEmtCaseResults = run_demo(enable_plots=False)

    assert len(traces.time) > 100
    assert float(traces.max_abs_lookup_error) < 1.0e-10
    assert float(traces.max_abs_load_bus_kcl_error) < 1.0e-5
