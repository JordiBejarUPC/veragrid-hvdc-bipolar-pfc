# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Run the Kundur VeraGrid RMS rotor-speed event benchmark from PyCharm."""

from __future__ import annotations

from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkCase
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkConfiguration
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkScenario
from trunk.dynamics.small_signal.rms_kundur import run_kundur_rms


def run_kundur_rms_event() -> None:
    """Run a rotor-speed state step on the first Kundur machine.

    The event occurs at 0.2 s on a fixed 1 ms Backward Euler grid. No initial
    speed offset is applied, so the recorded response is caused by the event.

    :return: None.
    """
    configuration: RmsBenchmarkConfiguration = RmsBenchmarkConfiguration(
        case_tpe=RmsBenchmarkCase.KUNDUR,
        simulation_time=2.0,
        speed_perturbation_pu=0.0,
        scenario_tpe=RmsBenchmarkScenario.ROTOR_SPEED_STATE_STEP,
        event_time=0.2,
        event_state_step_pu=1.0e-4,
    )
    run_kundur_rms(configuration)


if __name__ == "__main__":
    run_kundur_rms_event()
else:
    pass
