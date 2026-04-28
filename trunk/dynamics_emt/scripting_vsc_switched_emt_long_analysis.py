# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Long-horizon analysis for the hybrid switched EMT converter.

This script is intentionally separate from the short public scripting example.
Its purpose is to help debug whether the residual defect of the switched model is
caused by bridge headroom or by a dq/controller mismatch.
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
    compute_long_horizon_alignment_analysis,
    get_plot_output_path,
    open_plot_file,
    plot_switched_converter_handover,
    print_long_horizon_alignment_analysis,
    print_switched_converter_summary,
    simulate_switched_converter_handover,
)


def build_long_analysis_emt_options() -> EmtOptions:
    """
    Build the EMT options used by the long-horizon switched-converter analysis.

    :return: EMT options instance.
    """
    options: EmtOptions = build_emt_options(
        solver_type=EmtSolverTypes.Symbolic,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        time_step=1.0e-5,
        simulation_time=2.0e-2,
        newton_max_iter=20,
    )
    return options


def main() -> SwitchedConverterHandoverTrace:
    """
    Run the long-horizon switched-converter analysis and print the alignment diagnostics.

    :return: Structured switched-converter handover trace.
    """
    trace: SwitchedConverterHandoverTrace = simulate_switched_converter_handover(
        emt_options=build_long_analysis_emt_options(),
    )
    plot_path: Path = get_plot_output_path(file_name="switched_converter_handover_long_analysis.png")

    print_switched_converter_summary(trace)
    plot_switched_converter_handover(trace=trace, show_plot=False, save_path=plot_path)
    open_plot_file(plot_path)
    print(f"Plot saved to: {plot_path}")
    print_long_horizon_alignment_analysis(
        analysis=compute_long_horizon_alignment_analysis(
            trace=trace,
            frequency_hz=50.0,
            fit_window_s=2.0e-2,
        )
    )
    return trace


if __name__ == "__main__":
    main()
