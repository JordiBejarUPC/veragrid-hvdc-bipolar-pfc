# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Run the IEEE 39-bus VeraGrid RMS time-domain benchmark from PyCharm."""

from __future__ import annotations

import time

import VeraGridEngine.api as gce

from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkCase
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkConfiguration
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import run_veragrid_rms_benchmark
from trunk.dynamics.small_signal.rms_ieee39_small_signal import _build_power_flow_options
from trunk.dynamics.small_signal.rms_ieee39_small_signal import build_ieee39_rms_benchmark_grid


def get_ieee39_andes_style_state_labels() -> list[str]:
    """Return IEEE39 physical state labels in VeraGrid compiled order.

    :return: ANDES-style labels aligned with the 130 VeraGrid states.
    """
    labels: list[str] = list()
    generator_ordinal: int
    for generator_ordinal in range(1, 11):
        state_name: str
        for state_name in ("delta", "omega", "e1q", "e1d", "e2d", "e2q"):
            labels.append(f"{state_name} GENROU {generator_ordinal}")
        labels.append(f"LAG_y TGOV1N TGOV1 {generator_ordinal}")
        labels.append(f"LL_x TGOV1N TGOV1 {generator_ordinal}")
        for state_name in ("vp", "LA_y", "W_x"):
            labels.append(f"{state_name} IEEEX1 {generator_ordinal}")
        labels.append(f"LL2_x IEEEST {generator_ordinal}")
        labels.append(f"WO_x IEEEST {generator_ordinal}")
    return labels


def run_ieee39_rms(configuration: RmsBenchmarkConfiguration | None = None) -> None:
    """Build, solve and export the IEEE39 VeraGrid RMS benchmark.

    :param configuration: Optional base or event benchmark settings.
    :return: None.
    """
    workflow_start: float = time.perf_counter()
    build_start: float = time.perf_counter()
    grid: gce.MultiCircuit = build_ieee39_rms_benchmark_grid()
    build_seconds: float = time.perf_counter() - build_start
    if configuration is None:
        selected_configuration: RmsBenchmarkConfiguration = RmsBenchmarkConfiguration(
            RmsBenchmarkCase.IEEE39
        )
    elif configuration.case_tpe is RmsBenchmarkCase.IEEE39:
        selected_configuration = configuration
    else:
        raise ValueError("IEEE39 runner received settings for a different case.")
    run_veragrid_rms_benchmark(
        grid=grid,
        power_flow_options=_build_power_flow_options(),
        configuration=selected_configuration,
        case_build_seconds=build_seconds,
        workflow_start=workflow_start,
        canonical_state_labels=get_ieee39_andes_style_state_labels(),
    )


if __name__ == "__main__":
    run_ieee39_rms()
else:
    pass
