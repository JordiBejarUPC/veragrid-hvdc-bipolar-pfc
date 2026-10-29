# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Interactive demo for the hybrid switched EMT converter handover case.

The demo reuses the shared switched-converter support module so that the demo,
the scripting entry point and the automated regressions all rely on the exact
same EMT formulation.
"""

from __future__ import annotations

from pathlib import Path
import sys


def ensure_trunk_import_paths() -> None:
    """
    Add the repository ``src`` tree and the current ``trunk`` directory to ``sys.path``.

    :return: None.
    """
    repo_root: Path = Path(__file__).resolve().parents[3]
    src_root: Path = repo_root / "src"
    trunk_root: Path = repo_root / "trunk"
    repo_root_text: str = str(repo_root)
    src_root_text: str = str(src_root)
    trunk_root_text: str = str(trunk_root)

    # The demo imports both packaged engine modules and shared ``trunk`` support code.
    if src_root_text not in sys.path:
        sys.path.insert(0, src_root_text)
    else:
        pass

    if trunk_root_text not in sys.path:
        sys.path.insert(0, trunk_root_text)
    else:
        pass

    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)
    else:
        pass


ensure_trunk_import_paths()

from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes
from dynamics_emt.support.switched_converter_handover_case import (
    SwitchedConverterHandoverTrace,
    build_emt_options,
    run_switched_converter_handover_case,
)


DEMO_FILTER_R_EQ_PU: float = 0.04
DEMO_FILTER_L_EQ_PU: float = 1.5


def build_demo_emt_options() -> EmtOptions:
    """
    Build the recommended EMT options for the interactive switched-converter demo.

    :return: EMT options instance.
    """
    options: EmtOptions = build_emt_options(
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        time_step=1.0e-5,
        simulation_time=1.2e-3,
        newton_max_iter=20,
    )
    return options


def main() -> SwitchedConverterHandoverTrace:
    """
    Run the interactive switched-converter handover demo.

    :return: Structured switched-converter handover trace.
    """
    trace: SwitchedConverterHandoverTrace = run_switched_converter_handover_case(
        enable_plot_window=False,
        save_plot=True,
        open_saved_plot=True,
        plot_file_name="switched_converter_handover_demo.png",
        emt_options=build_demo_emt_options(),
        r_eq_pu=DEMO_FILTER_R_EQ_PU,
        l_eq_pu=DEMO_FILTER_L_EQ_PU,
    )
    return trace


if __name__ == "__main__":
    main()
