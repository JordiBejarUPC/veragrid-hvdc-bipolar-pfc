# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Run the Kundur VeraGrid RMS time-domain benchmark from PyCharm."""

from __future__ import annotations

import time

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
import VeraGridEngine.api as gce

from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkCase
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import RmsBenchmarkConfiguration
from trunk.dynamics.small_signal.rms_dynamic_benchmark_common import run_veragrid_rms_benchmark
from trunk.dynamics.small_signal.rms_kundur_small_signal import build_kundur_rms_benchmark_grid


def build_kundur_power_flow_options() -> PowerFlowOptions:
    """Build the deterministic Kundur Newton power-flow options.

    :return: Power-flow options.
    """
    return PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1.0e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )


def run_kundur_rms(configuration: RmsBenchmarkConfiguration | None = None) -> None:
    """Build, solve and export the Kundur VeraGrid RMS benchmark.

    :param configuration: Optional base or event benchmark settings.
    :return: None.
    """
    workflow_start: float = time.perf_counter()
    build_start: float = time.perf_counter()
    grid: gce.MultiCircuit = build_kundur_rms_benchmark_grid()
    build_seconds: float = time.perf_counter() - build_start
    if configuration is None:
        selected_configuration: RmsBenchmarkConfiguration = RmsBenchmarkConfiguration(
            RmsBenchmarkCase.KUNDUR
        )
    elif configuration.case_tpe is RmsBenchmarkCase.KUNDUR:
        selected_configuration = configuration
    else:
        raise ValueError("Kundur runner received settings for a different case.")
    run_veragrid_rms_benchmark(
        grid=grid,
        power_flow_options=build_kundur_power_flow_options(),
        configuration=selected_configuration,
        case_build_seconds=build_seconds,
        workflow_start=workflow_start,
    )


if __name__ == "__main__":
    run_kundur_rms()
else:
    pass
