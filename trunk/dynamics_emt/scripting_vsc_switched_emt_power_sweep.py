# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Active-power sweep for the hybrid switched EMT converter case.

This script is intended for fast control-oriented debugging of the switched
converter. It keeps the short-horizon configuration used by the public scripting
example and reports how the d-axis and q-axis tracking errors evolve with the
requested active-power transfer.
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
    build_emt_options,
    print_switched_converter_power_sweep,
    run_switched_converter_power_sweep,
)


def build_sweep_emt_options() -> EmtOptions:
    """
    Build the EMT options used by the switched-converter active-power sweep.

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


def main() -> None:
    """
    Run the switched-converter active-power sweep.

    :return: None.
    """
    p_transfer_values_mw: list[float] = list([10.0, 15.0, 20.0, 25.0, 30.0])

    # All sweep points reuse the same trusted 30 MW PF seed so that the table isolates converter
    # control/model behaviour instead of mixing in PF convergence artefacts at each operating point.
    rows = run_switched_converter_power_sweep(
        p_transfer_values_mw=p_transfer_values_mw,
        emt_options=build_sweep_emt_options(),
        pf_seed_p_transfer_mw=30.0,
    )
    print_switched_converter_power_sweep(rows=rows)


if __name__ == "__main__":
    main()
