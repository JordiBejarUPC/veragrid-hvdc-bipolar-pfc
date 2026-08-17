# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Compare one ANDES/VeraGrid RMS rotor-speed event from PyCharm."""

from __future__ import annotations

from trunk.dynamics.small_signal.Andes_vs_VeraGrid_rms import compare_rms_case
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkCase
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkScenario


def main() -> None:
    """Select and compare one already-generated rotor-speed event case.

    Change only the uncommented ``selected_case`` line below.

    :return: None.
    """
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.KUNDUR
    selected_case: RmsBenchmarkCase = RmsBenchmarkCase.IEEE14
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.IEEE39
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.NPCC140
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.WECC179
    compare_rms_case(
        case_tpe=selected_case,
        show_figures=True,
        scenario_tpe=RmsBenchmarkScenario.ROTOR_SPEED_STATE_STEP,
    )


if __name__ == "__main__":
    main()
else:
    pass
