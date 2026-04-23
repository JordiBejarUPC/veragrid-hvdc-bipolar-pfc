# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Official scripting entry point for the hybrid switched EMT VSC handover case.

The script is intentionally thin: the actual case construction, simulation,
validation and plotting live in the shared support module so that demos, tests
and scripting all exercise the exact same workflow.
"""

from __future__ import annotations

from pathlib import Path
import sys


def ensure_trunk_import_paths() -> None:
    """
    Add the repository ``src`` tree and the current ``trunk`` directory to ``sys.path``.

    :return: None.
    """
    repo_root: Path = Path(__file__).resolve().parents[2]
    src_root: Path = repo_root / "src"
    trunk_root: Path = repo_root / "trunk"
    repo_root_text: str = str(repo_root)
    src_root_text: str = str(src_root)
    trunk_root_text: str = str(trunk_root)

    # The scripting wrapper imports both packaged engine modules and shared ``trunk`` support code.
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


def build_script_emt_options() -> EmtOptions:
    """
    Build the recommended EMT options for the switched VSC scripting case.

    :return: EMT options instance.
    """
    # The symbolic backend is currently the most reliable cold-start path for a colleague-facing
    # one-shot scripting demo. Other backends can still be exercised by overriding these options.
    options: EmtOptions = build_emt_options(
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        time_step=1.0e-5,
        simulation_time=1.2e-3,
        newton_max_iter=20,
    )
    return options


def run_switched_vsc_case(
        enable_plots: bool = False,
        save_plot: bool = True,
        open_saved_plot: bool = False,
        emt_options: EmtOptions | None = None,
) -> SwitchedConverterHandoverTrace:
    """
    Run the switched EMT VSC scripting case.

    :param enable_plots: Display matplotlib figures when ``True``.
    :param save_plot: Save the figure to disk when ``True``.
    :param open_saved_plot: Open the saved plot with the platform default viewer when ``True``.
    :param emt_options: Optional EMT options override.
    :return: Structured switched-converter handover trace.
    """
    resolved_emt_options: EmtOptions = build_script_emt_options() if emt_options is None else emt_options
    trace: SwitchedConverterHandoverTrace = run_switched_converter_handover_case(
        enable_plot_window=enable_plots,
        save_plot=save_plot,
        open_saved_plot=open_saved_plot,
        plot_file_name="switched_converter_handover_scripting.png",
        emt_options=resolved_emt_options,
    )
    return trace


def main() -> None:
    """
    Run the switched EMT VSC scripting case.

    :return: None.
    """
    run_switched_vsc_case(enable_plots=False, save_plot=True, open_saved_plot=True)


if __name__ == "__main__":
    main()
