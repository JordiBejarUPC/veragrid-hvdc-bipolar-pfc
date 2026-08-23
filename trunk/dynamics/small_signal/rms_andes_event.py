# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Run any ANDES RMS rotor-speed event benchmark directly from PyCharm."""

from __future__ import annotations

from trunk.dynamics.small_signal.rms_andes import run_andes_rms
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkCase
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkConfiguration
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkScenario


def main() -> None:
    """Select and run one ANDES rotor-speed event case with PyCharm Run.

    Change only the uncommented ``selected_case`` line below.

    :return: None.
    """
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.KUNDUR
    selected_case: RmsBenchmarkCase = RmsBenchmarkCase.IEEE14
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.IEEE39
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.NPCC140
    # selected_case: RmsBenchmarkCase = RmsBenchmarkCase.WECC179
    configuration: RmsBenchmarkConfiguration = RmsBenchmarkConfiguration(
        case_tpe=selected_case,
        simulation_time=2.0,
        speed_perturbation_pu=0.0,
        scenario_tpe=RmsBenchmarkScenario.ROTOR_SPEED_STATE_STEP,
        event_time=0.2,
        event_state_step_pu=1.0e-4,
    )
    run_andes_rms(configuration)


if __name__ == "__main__":
    main()
else:
    pass
