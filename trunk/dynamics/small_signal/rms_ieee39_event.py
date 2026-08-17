# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Run the IEEE39 VeraGrid RMS rotor-speed event benchmark from PyCharm."""

from __future__ import annotations

from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkCase
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkConfiguration
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkScenario
from trunk.dynamics.small_signal.rms_ieee39 import run_ieee39_rms


def run_ieee39_rms_event() -> None:
    """Run a rotor-speed state step on the first IEEE39 machine.

    :return: None.
    """
    configuration: RmsBenchmarkConfiguration = RmsBenchmarkConfiguration(
        case_tpe=RmsBenchmarkCase.IEEE39,
        simulation_time=2.0,
        speed_perturbation_pu=0.0,
        scenario_tpe=RmsBenchmarkScenario.ROTOR_SPEED_STATE_STEP,
        event_time=0.2,
        event_state_step_pu=1.0e-4,
    )
    run_ieee39_rms(configuration)


if __name__ == "__main__":
    run_ieee39_rms_event()
else:
    pass
