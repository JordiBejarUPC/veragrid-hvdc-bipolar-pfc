# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Timing utilities for reproducible ANDES--VeraGrid RMS benchmarks."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
import time

import pandas as pd


class BenchmarkTimingRelation(Enum):
    """Describe how one timing sample relates to the normal workflow total."""

    COMPONENT = "component"
    TOTAL = "total"
    EXCLUDED_DIAGNOSTIC = "excluded_diagnostic"


def elapsed_seconds(start_time: float) -> float:
    """Return elapsed wall-clock seconds from a performance-counter sample.

    :param start_time: Value previously returned by ``time.perf_counter``.
    :return: Elapsed seconds.
    """
    return float(time.perf_counter() - start_time)


def finalize_normal_workflow_timings(
    timings: dict[str, float],
    total_start: float,
    normal_component_names: tuple[str, ...],
    diagnostic_names: tuple[str, ...],
) -> None:
    """Complete one timing record with attributable overhead and its true total.

    Diagnostic warm repeats happen during the measured wall-clock interval but
    are not operations performed twice by the normal simulation. Their duration
    is therefore removed before calculating the authoritative workflow total.
    The remaining difference between that total and the explicitly timed normal
    components is retained as overhead instead of silently disappearing.

    :param timings: Mutable phase-to-seconds mapping for one benchmark run.
    :param total_start: Performance-counter sample taken at workflow entry.
    :param normal_component_names: Mutually exclusive normal workflow phases.
    :param diagnostic_names: Warm diagnostic phases excluded from the workflow.
    :return: None.
    """
    diagnostic_seconds: float = float(sum(timings[name] for name in diagnostic_names))
    normal_workflow_seconds: float = elapsed_seconds(total_start) - diagnostic_seconds
    attributed_seconds: float = float(sum(timings[name] for name in normal_component_names))

    # Preserve all normal elapsed time, including small Python-side gaps between
    # the explicit timers, so the displayed components reconcile to the total.
    unattributed_seconds: float = max(0.0, normal_workflow_seconds - attributed_seconds)
    timings["normal_workflow_unattributed_overhead"] = unattributed_seconds
    timings["normal_workflow_total"] = normal_workflow_seconds


def benchmark_timing_metadata(
    phase_name: str,
    engine_label: str,
) -> tuple[BenchmarkTimingRelation, str]:
    """Return the total relationship and precise scope of one timing phase.

    :param phase_name: Stable phase identifier stored in timing artifacts.
    :param engine_label: Simulator name used to specialize unknown phase notes.
    :return: Relationship to the normal workflow total and human-readable scope.
    """
    metadata: dict[str, tuple[BenchmarkTimingRelation, str]] = dict()
    metadata["case_and_model_build"] = (
        BenchmarkTimingRelation.COMPONENT,
        "Load or construct the network, devices, and dynamic model instances.",
    )
    metadata["power_flow"] = (
        BenchmarkTimingRelation.COMPONENT,
        "Solve the steady-state power-flow operating point.",
    )
    metadata["rms_problem_build_initialization_symbolic_to_numeric"] = (
        BenchmarkTimingRelation.COMPONENT,
        "VeraGrid combined stage: build the RMS DAE problem, explicitly initialize dynamic states, "
        "and compile numerical RHS and Jacobian functions.",
    )
    metadata["andes_system_setup"] = (
        BenchmarkTimingRelation.COMPONENT,
        "ANDES system setup: arrays, per-unit data, DAE addresses, sparse patterns, references, and "
        "connectivity; generated numerical calls are normally loaded during case_and_model_build.",
    )
    metadata["dynamic_initialization"] = (
        BenchmarkTimingRelation.COMPONENT,
        "ANDES TDS initialization and initial iterative step; VeraGrid performs its dynamic "
        "initialization inside its combined RMS-problem stage.",
    )
    metadata["benchmark_preprocessing"] = (
        BenchmarkTimingRelation.COMPONENT,
        "ANDES benchmark-only folding of zero-time-constant or unused auxiliary states.",
    )
    metadata["small_signal_total"] = (
        BenchmarkTimingRelation.COMPONENT,
        "Production small-signal calculation, including state matrix, eigensolution, participation "
        "factors, and result assembly.",
    )
    metadata["result_export"] = (
        BenchmarkTimingRelation.COMPONENT,
        "Write the engine numerical result artifacts used by the comparator.",
    )
    metadata["normal_workflow_unattributed_overhead"] = (
        BenchmarkTimingRelation.COMPONENT,
        "Normal-workflow wall time between explicit timers, retained so components reconcile "
        "exactly to the total.",
    )
    metadata["normal_workflow_total"] = (
        BenchmarkTimingRelation.TOTAL,
        "Authoritative network-to-results workflow total; diagnostic warm repeats are subtracted.",
    )
    metadata["diagnostic_state_matrix_warm_repeat"] = (
        BenchmarkTimingRelation.EXCLUDED_DIAGNOSTIC,
        "Warm repeat performed only to profile state-matrix construction separately; excluded from "
        "normal_workflow_total.",
    )
    metadata["diagnostic_eigenanalysis_pf_warm_repeat"] = (
        BenchmarkTimingRelation.EXCLUDED_DIAGNOSTIC,
        "Warm repeat performed only to profile eigensolution and participation factors separately; "
        "excluded from normal_workflow_total.",
    )
    selected_metadata: tuple[BenchmarkTimingRelation, str] | None = metadata.get(phase_name, None)
    if selected_metadata is None:
        relation: BenchmarkTimingRelation = BenchmarkTimingRelation.COMPONENT
        description: str = f"{engine_label} benchmark timing phase."
    else:
        relation, description = selected_metadata
    return relation, description


def save_benchmark_timings(
    output_directory: Path,
    engine_label: str,
    case_label: str,
    timings: dict[str, float],
    state_count: int,
    mode_count: int,
) -> Path:
    """Write timing samples as machine-readable CSV and JSON artifacts.

    :param output_directory: Existing or new benchmark result directory.
    :param engine_label: Simulator name used in filenames and table rows.
    :param case_label: Benchmark case label.
    :param timings: Phase-to-seconds mapping.
    :param state_count: Number of retained physical states.
    :param mode_count: Number of exported eigenvalues.
    :return: Written CSV path.
    """
    output_directory.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = list()
    phase_name: str
    seconds: float
    for phase_name, seconds in timings.items():
        relation: BenchmarkTimingRelation
        description: str
        relation, description = benchmark_timing_metadata(
            phase_name=phase_name,
            engine_label=engine_label,
        )
        row: dict[str, object] = dict()
        row["engine"] = engine_label
        row["case"] = case_label
        row["phase"] = phase_name
        row["seconds"] = float(seconds)
        row["relation_to_normal_workflow_total"] = relation.value
        row["scope"] = description
        row["state_count"] = int(state_count)
        row["mode_count"] = int(mode_count)
        rows.append(row)
    timing_table: pd.DataFrame = pd.DataFrame(rows)
    csv_path: Path = output_directory / f"timings_results_{engine_label}_{case_label}.csv"
    json_path: Path = output_directory / f"timings_results_{engine_label}_{case_label}.json"
    timing_table.to_csv(csv_path, index=False, float_format="%.12g")
    timing_table.to_json(json_path, orient="records", indent=2)
    print("\nSmall-signal benchmark timings:")
    print(
        timing_table.loc[
            :, list(("relation_to_normal_workflow_total", "phase", "seconds"))
        ].to_string(index=False)
    )
    print(f"Timing results written to: {csv_path}")
    return csv_path
