# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys

import matplotlib
matplotlib.use("Agg")
import numpy as np

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src")
TRUNK_ROOT = os.path.join(REPO_ROOT, "trunk")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if TRUNK_ROOT not in sys.path:
    sys.path.insert(0, TRUNK_ROOT)

from dynamics_emt.scripting_hvdc_vdc_control import run_hvdc_vdc_control_simulation


def main() -> None:
    results = run_hvdc_vdc_control_simulation(simulation_time_s=0.012, time_step_s=1.0e-4, plot=False)
    signals = results["signals"]

    checks = {
        "power_flow_converged": bool(results["pf_results"].converged),
        "emt_well_initialized": bool(results["well_initialized"]),
        "finite_trajectory": bool(np.all(np.isfinite(results["trajectory"]))),
        "finite_vdc_1": bool(np.all(np.isfinite(signals["v_dc_1"]))),
        "finite_pctrl": bool(np.all(np.isfinite(signals["p_ctrl"]))),
        "vdc_reasonable": bool(0.5 < np.min(signals["v_dc_1"]) and np.max(signals["v_dc_1"]) < 1.5),
        "controller_available": bool(signals["p_ctrl"].size > 2),
    }

    print("HVDC Vdc-control EMT validation")
    for name, passed in checks.items():
        print(f"{name}: {passed}")

    if not all(checks.values()):
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        raise RuntimeError(f"HVDC Vdc-control EMT validation failed: {failed}")


if __name__ == "__main__":
    main()
