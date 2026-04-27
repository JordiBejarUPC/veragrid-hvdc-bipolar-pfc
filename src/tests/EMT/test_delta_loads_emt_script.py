from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
else:
    pass

from trunk.dynamics_emt.scripting_delta_loads_emt import run_delta_load_cases
from trunk.implicit_solver_test_EMT.Demos.demo_delta_loads_emt import run_demo


def test_delta_load_cases_run_without_plots_and_export_pngs() -> None:
    result = run_delta_load_cases(enable_plots=False)
    exponential = result["exponential"]
    zip_case = result["zip"]

    assert len(exponential["time"]) > 100
    assert len(zip_case["time"]) > 100
    assert Path(exponential["png_path"]).exists()
    assert Path(zip_case["png_path"]).exists()
    assert np.isclose(float(exponential["seed_v_ab"]), float(exponential["bus_v_ab"][0]), atol=1.0e-8)
    assert np.isclose(float(exponential["seed_v_bc"]), float(exponential["bus_v_bc"][0]), atol=1.0e-8)
    assert np.isclose(float(exponential["seed_v_ca"]), float(exponential["bus_v_ca"][0]), atol=1.0e-8)
    assert np.isclose(float(zip_case["seed_v_ab"]), float(zip_case["bus_v_ab"][0]), atol=1.0e-8)
    assert np.isclose(float(zip_case["seed_v_bc"]), float(zip_case["bus_v_bc"][0]), atol=1.0e-8)
    assert np.isclose(float(zip_case["seed_v_ca"]), float(zip_case["bus_v_ca"][0]), atol=1.0e-8)
    assert np.isclose(float(exponential["seed_i_a"]), float(exponential["load_i_a"][0]), atol=1.0e-8)
    assert np.isclose(float(exponential["seed_i_b"]), float(exponential["load_i_b"][0]), atol=1.0e-8)
    assert np.isclose(float(exponential["seed_i_c"]), float(exponential["load_i_c"][0]), atol=1.0e-8)
    assert np.isclose(float(zip_case["seed_i_a"]), float(zip_case["load_i_a"][0]), atol=1.0e-8)
    assert np.isclose(float(zip_case["seed_i_b"]), float(zip_case["load_i_b"][0]), atol=1.0e-8)
    assert np.isclose(float(zip_case["seed_i_c"]), float(zip_case["load_i_c"][0]), atol=1.0e-8)


def test_delta_load_demo_wrapper_runs_without_plots() -> None:
    result = run_demo(enable_plots=False)

    assert len(result["exponential"]["time"]) > 100
    assert len(result["zip"]["time"]) > 100
