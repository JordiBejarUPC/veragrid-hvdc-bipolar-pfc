from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
else:
    pass

from trunk.dynamics_emt.scripting_neutral_ground_shunt_emt import run_neutral_ground_shunt_cases
from trunk.implicit_solver_test_EMT.Demos.demo_neutral_ground_shunt_emt import run_demo


def test_neutral_ground_shunt_script_runs_and_separates_the_three_cases() -> None:
    result = run_neutral_ground_shunt_cases(enable_plots=False)
    cases = result["cases"]
    y_floating = cases["y_floating"]
    yg_solid = cases["yg_solid"]
    yn_grounding_link = cases["yn_grounding_link"]

    assert len(y_floating["time"]) > 100
    assert Path(result["png_path"]).exists()

    assert float(y_floating["steady_abs_load_i_a"]) < float(yg_solid["steady_abs_load_i_a"]) * 0.1
    assert float(y_floating["steady_abs_load_i_n"]) < float(yg_solid["steady_abs_load_i_n"]) * 0.1
    assert float(yg_solid["steady_abs_load_i_a"]) > 1.0e-3
    assert float(yg_solid["steady_abs_load_i_n"]) > 1.0e-4
    assert float(yn_grounding_link["steady_abs_load_i_a"]) > 1.0e-3
    assert float(yn_grounding_link["steady_abs_load_i_n"]) > 1.0e-4

    steady_index = max(1, len(yg_solid["time"]) // 2)
    assert np.allclose(
        yg_solid["load_i_a"][steady_index:],
        yn_grounding_link["load_i_a"][steady_index:],
        rtol=1.0e-2,
        atol=1.0e-3,
    )
    grounding_mean = float(np.mean(yn_grounding_link["grounding_i_n"][steady_index:]))
    load_neutral_mean = float(np.mean(yn_grounding_link["load_i_n"][steady_index:]))
    assert abs(grounding_mean) > 1.0e-3
    assert grounding_mean * load_neutral_mean < 0.0


def test_neutral_ground_shunt_demo_wrapper_runs_without_plots() -> None:
    result = run_demo(enable_plots=False)
    cases = result["cases"]

    assert len(cases["yg_solid"]["time"]) > 100
    assert float(cases["yg_solid"]["steady_abs_load_i_a"]) > 1.0e-3
