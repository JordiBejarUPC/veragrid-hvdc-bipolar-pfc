# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_ROOT = os.path.join(REPO_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from VeraGridEngine.enumerations import EmtFaultPlacementSide, FaultType
from trunk.dynamics_emt.scripting_fault_common import FaultCaseConfig, run_fault_case


def main() -> None:
    """Run the legacy balanced-fault demo as a three-phase fault case."""
    run_fault_case(
        FaultCaseConfig(
            case_name="balanced_fault",
            case_title="Balanced Three-Phase Fault",
            fault_type=FaultType.LLL,
            phA=True,
            phB=True,
            phC=True,
            placement_side=EmtFaultPlacementSide.FromSide,
            fault_time_s=0.04,
            clear_time_s=0.08,
            fault_resistance=1.0e-3,
            ground_resistance=1.0e-3,
        )
    )


if __name__ == "__main__":
    main()
