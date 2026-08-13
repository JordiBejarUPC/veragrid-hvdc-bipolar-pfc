# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Build and run the NPCC 140-bus VeraGrid RMS small-signal benchmark."""

from __future__ import annotations

from pathlib import Path
import time

import andes

from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_driver import SmallSignalStabilityRmsDriver
from VeraGridEngine.Simulations.SmallSignalStabilityRms.small_signal_options import RmsSmallSignalStabilityOptions
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
import VeraGridEngine.api as gce

from trunk.dynamics.small_signal.npcc140_rms_model_config import get_npcc140_generator_rms_template
from trunk.dynamics.small_signal.npcc140_rms_model_config import get_npcc140_andes_style_state_labels
from trunk.dynamics.small_signal.npcc140_rms_model_config import Npcc140DynamicTables
from trunk.dynamics.small_signal.rms_kundur_small_signal import plot_participation_factors
from trunk.dynamics.small_signal.rms_kundur_small_signal import plot_s_domain_eigenvalues
from trunk.dynamics.small_signal.rms_kundur_small_signal import save_small_signal_results_to_csv
from trunk.dynamics.small_signal.rms_large_case_common import assign_standard_network_rms_models
from trunk.dynamics.small_signal.rms_large_case_common import build_large_case_rms_options
from trunk.dynamics.small_signal.rms_large_case_common import finish_benchmark_figures
from trunk.dynamics.small_signal.rms_large_case_common import run_power_flow
from trunk.dynamics.small_signal.veragrid_small_signal_benchmark_timing import benchmark_veragrid_isolated_numerical_phases
from trunk.dynamics.small_signal.small_signal_benchmark_timing import elapsed_seconds
from trunk.dynamics.small_signal.small_signal_benchmark_timing import finalize_normal_workflow_timings
from trunk.dynamics.small_signal.small_signal_benchmark_timing import save_benchmark_timings


def _base_grid_path() -> Path:
    """Return the ANDES-distributed NPCC RAW network path.

    :return: Absolute RAW path.
    """
    return Path(andes.get_case("npcc/npcc.raw")).resolve()


def _results_directory() -> Path:
    """Return the standard NPCC VeraGrid result directory.

    :return: Result directory.
    """
    return Path(__file__).resolve().parent / "npcc140_small_signal_rms_results_VeraGrid"


def _remove_raw_line_virtual_taps(grid: gce.MultiCircuit) -> None:
    """Match the ANDES NPCC branch convention for nominal-voltage aliases.

    Several NPCC RAW line endpoints use 220 kV and 230 kV labels while the
    ANDES ``Line`` records retain ``tap=1``. VeraGrid correctly interprets a
    nominal-voltage mismatch as an implicit virtual tap for a general RAW case,
    but that is not the convention of this benchmark. Buses joined by ordinary
    lines are therefore assigned one component nominal voltage; transformer
    winding ratings are then aligned with their oriented endpoint buses so every
    implicit virtual tap is exactly one, matching the ANDES admittance matrix.

    :param grid: Imported NPCC RAW grid.
    :return: None.
    """
    bus_index_by_idtag: dict[str, int] = dict()
    bus_index: int
    for bus_index, bus in enumerate(grid.buses):
        bus_index_by_idtag[bus.idtag] = bus_index
    component_ids: list[int] = list(range(len(grid.buses)))
    for line in grid.lines:
        from_index: int = bus_index_by_idtag[line.bus_from.idtag]
        to_index: int = bus_index_by_idtag[line.bus_to.idtag]
        from_component: int = component_ids[from_index]
        to_component: int = component_ids[to_index]
        if from_component == to_component:
            pass
        else:
            retained_component: int = min(from_component, to_component)
            replaced_component: int = max(from_component, to_component)
            replacement_index: int
            for replacement_index in range(len(component_ids)):
                if component_ids[replacement_index] == replaced_component:
                    component_ids[replacement_index] = retained_component
                else:
                    pass
    component_nominal_voltage: dict[int, float] = dict()
    for bus_index, bus in enumerate(grid.buses):
        component_index: int = component_ids[bus_index]
        current_voltage: float = component_nominal_voltage.get(component_index, 0.0)
        component_nominal_voltage[component_index] = max(current_voltage, float(bus.Vnom))
    for bus_index, bus in enumerate(grid.buses):
        bus.Vnom = component_nominal_voltage[component_ids[bus_index]]
    for transformer in grid.transformers2w:
        # ``HV`` and ``LV`` are the oriented winding ratings consumed by the RMS
        # template. Their names do not imply that the RAW from side is always
        # the higher-voltage side.
        transformer.HV = float(transformer.bus_from.Vnom)
        transformer.LV = float(transformer.bus_to.Vnom)


def _match_andes_branch_regularization(grid: gce.MultiCircuit) -> None:
    """Apply the explicit ANDES ``r+1e-8`` and ``x+1e-8`` convention.

    :param grid: NPCC benchmark grid.
    :return: None.
    """
    for line in grid.lines:
        line.R = float(line.R) + 1.0e-8
        line.X = float(line.X) + 1.0e-8
    for transformer in grid.transformers2w:
        transformer.R = float(transformer.R) + 1.0e-8
        transformer.X = float(transformer.X) + 1.0e-8


def _match_andes_parallel_generator_reactive_allocation(
    grid: gce.MultiCircuit,
) -> None:
    """Match the RAW reactive-power split of co-located generators.

    ANDES retains the RAW generator reactive-power proportions when multiple
    voltage-controlling generators share one bus. VeraGrid allocates the bus
    reactive requirement using each generator's available range. The NPCC RAW
    file uses unequal placeholder limits for otherwise equivalent units, so the
    default allocation changes their individual dynamic operating points even
    though the aggregate bus power flow is identical. Symmetric ranges weighted
    by active power recover the RAW proportions used by this benchmark.

    :param grid: Imported NPCC RAW grid.
    :return: None.
    """
    generator_count_by_bus: dict[str, int] = dict()
    for generator in grid.generators:
        bus_idtag: str = generator.bus.idtag
        generator_count: int | None = generator_count_by_bus.get(bus_idtag, None)
        if generator_count is None:
            generator_count_by_bus[bus_idtag] = 1
        else:
            generator_count_by_bus[bus_idtag] = generator_count + 1
    for generator in grid.generators:
        if generator_count_by_bus[generator.bus.idtag] > 1:
            reactive_weight: float = max(abs(float(generator.P)), 1.0e-6)
            generator.Qmin = -reactive_weight
            generator.Qmax = reactive_weight
        else:
            pass


def build_npcc140_rms_benchmark_grid() -> gce.MultiCircuit:
    """Import NPCC topology and assign every physical RMS device model.

    :return: RMS-ready NPCC grid.
    """
    grid: gce.MultiCircuit = gce.open_file(str(_base_grid_path()))
    _remove_raw_line_virtual_taps(grid)
    _match_andes_branch_regularization(grid)
    _match_andes_parallel_generator_reactive_allocation(grid)
    assign_standard_network_rms_models(grid=grid, prefix="npcc140")
    dynamic_tables: Npcc140DynamicTables = Npcc140DynamicTables()
    generator_index: int
    for generator_index, generator in enumerate(grid.generators):
        set_rms_model(
            device=generator,
            model=get_npcc140_generator_rms_template(
                vfactory=grid.var_factory,
                generator_index=generator_index,
                system_base=float(grid.Sbase),
                tables=dynamic_tables,
            ).block,
            var_factory=grid.var_factory,
        )
    return grid


def run_npcc140_small_signal(show_figures: bool = True) -> None:
    """Run NPCC power flow and RMS small-signal stability.

    :param show_figures: Display interactive PyCharm figures after exporting.
    :return: None.
    """
    total_start: float = time.perf_counter()
    timings: dict[str, float] = dict()
    model_start: float = time.perf_counter()
    grid: gce.MultiCircuit = build_npcc140_rms_benchmark_grid()
    timings["case_and_model_build"] = elapsed_seconds(model_start)
    power_flow_start: float = time.perf_counter()
    power_flow: PowerFlowDriver = run_power_flow(grid=grid, tolerance=1.0e-10)
    timings["power_flow"] = elapsed_seconds(power_flow_start)
    rms_options: RmsOptions = build_large_case_rms_options()
    small_signal_options: RmsSmallSignalStabilityOptions = RmsSmallSignalStabilityOptions(
        ss_assessment_time=0.0
    )
    compilation_start: float = time.perf_counter()
    driver: SmallSignalStabilityRmsDriver = SmallSignalStabilityRmsDriver(
        grid=grid,
        rms_options=rms_options,
        sss_options=small_signal_options,
        pf_results=power_flow.results,
    )
    timings["rms_problem_build_initialization_symbolic_to_numeric"] = elapsed_seconds(compilation_start)
    small_signal_start: float = time.perf_counter()
    driver.run()
    timings["small_signal_total"] = elapsed_seconds(small_signal_start)
    timings.update(benchmark_veragrid_isolated_numerical_phases(driver))
    results_directory: Path = _results_directory()
    results_directory.mkdir(parents=True, exist_ok=True)
    export_start: float = time.perf_counter()
    save_small_signal_results_to_csv(
        driver.results,
        power_flow.results,
        results_directory,
        benchmark_state_labels=get_npcc140_andes_style_state_labels(
            Npcc140DynamicTables()
        ),
    )
    timings["result_export"] = elapsed_seconds(export_start)
    normal_component_names: tuple[str, ...] = (
        "case_and_model_build",
        "power_flow",
        "rms_problem_build_initialization_symbolic_to_numeric",
        "small_signal_total",
        "result_export",
    )
    diagnostic_names: tuple[str, ...] = (
        "diagnostic_state_matrix_warm_repeat",
        "diagnostic_eigenanalysis_pf_warm_repeat",
    )
    finalize_normal_workflow_timings(
        timings=timings,
        total_start=total_start,
        normal_component_names=normal_component_names,
        diagnostic_names=diagnostic_names,
    )
    save_benchmark_timings(
        output_directory=results_directory,
        engine_label="VeraGrid",
        case_label="NPCC140",
        timings=timings,
        state_count=int(driver.results.state_matrix.shape[0]),
        mode_count=int(driver.results.eigenvalues.size),
    )
    print("\nEigenvalues:")
    print(driver.results.eigenvalues)
    print(f"\nVeraGrid NPCC140 results written to: {results_directory}")
    plot_s_domain_eigenvalues(driver.results.eigenvalues)
    plot_participation_factors(driver.results.participation_factors)
    finish_benchmark_figures(show_figures=show_figures)


if __name__ == "__main__":
    run_npcc140_small_signal()
else:
    pass
