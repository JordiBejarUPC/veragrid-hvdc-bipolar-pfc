# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Run the NPCC 140-bus VeraGrid RMS time-domain benchmark from PyCharm."""

from __future__ import annotations

import time

import VeraGridEngine.api as gce

from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkCase
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkConfiguration
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import run_veragrid_rms_benchmark
from trunk.dynamics.small_signal.rms_large_case_common import build_large_case_power_flow_options
from trunk.dynamics.small_signal.rms_npcc140_small_signal import build_npcc140_rms_benchmark_grid
from trunk.dynamics.small_signal.npcc140_rms_model_config import get_npcc140_andes_style_state_labels
from trunk.dynamics.small_signal.npcc140_rms_model_config import Npcc140DynamicTables


def run_npcc140_rms(configuration: RmsBenchmarkConfiguration | None = None) -> None:
    """Build, solve and export the NPCC140 VeraGrid RMS benchmark.

    :param configuration: Optional base or event benchmark settings.
    :return: None.
    """
    workflow_start: float = time.perf_counter()
    build_start: float = time.perf_counter()
    grid: gce.MultiCircuit = build_npcc140_rms_benchmark_grid()
    build_seconds: float = time.perf_counter() - build_start
    if configuration is None:
        selected_configuration: RmsBenchmarkConfiguration = RmsBenchmarkConfiguration(
            RmsBenchmarkCase.NPCC140
        )
    elif configuration.case_tpe is RmsBenchmarkCase.NPCC140:
        selected_configuration = configuration
    else:
        raise ValueError("NPCC140 runner received settings for a different case.")
    dynamic_tables: Npcc140DynamicTables = Npcc140DynamicTables()
    run_veragrid_rms_benchmark(
        grid=grid,
        power_flow_options=build_large_case_power_flow_options(tolerance=1.0e-10),
        configuration=selected_configuration,
        case_build_seconds=build_seconds,
        workflow_start=workflow_start,
        canonical_state_labels=get_npcc140_andes_style_state_labels(dynamic_tables),
    )


if __name__ == "__main__":
    run_npcc140_rms()
else:
    pass
