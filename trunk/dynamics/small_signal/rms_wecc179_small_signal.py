# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Build and run the WECC 179-bus VeraGrid RMS small-signal benchmark."""

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

from trunk.dynamics.small_signal.rms_kundur_small_signal import plot_participation_factors
from trunk.dynamics.small_signal.rms_kundur_small_signal import plot_s_domain_eigenvalues
from trunk.dynamics.small_signal.rms_kundur_small_signal import save_small_signal_results_to_csv
from trunk.dynamics.small_signal.rms_large_case_common import assign_standard_network_rms_models
from trunk.dynamics.small_signal.rms_large_case_common import build_large_case_rms_options
from trunk.dynamics.small_signal.rms_large_case_common import finish_benchmark_figures
from trunk.dynamics.small_signal.rms_large_case_common import run_power_flow
from trunk.dynamics.small_signal.wecc179_rms_model_config import get_wecc179_andes_style_state_labels
from trunk.dynamics.small_signal.wecc179_rms_model_config import get_wecc179_generator_rms_template
from trunk.dynamics.small_signal.wecc179_rms_model_config import Wecc179DynamicTables
from trunk.dynamics.small_signal.veragrid_small_signal_benchmark_timing import benchmark_veragrid_isolated_numerical_phases
from trunk.dynamics.small_signal.small_signal_benchmark_timing import elapsed_seconds
from trunk.dynamics.small_signal.small_signal_benchmark_timing import save_benchmark_timings


def _base_grid_path() -> Path:
    """Return the ANDES-distributed WECC RAW network path.

    :return: Absolute RAW path.
    """
    return Path(andes.get_case("wecc/wecc.raw")).resolve()


def _output_grid_path() -> Path:
    """Return the generated RMS-ready VeraGrid path.

    :return: Output grid path.
    """
    return Path(__file__).resolve().parent / "wecc179_rms_sss.veragrid"


def _results_directory() -> Path:
    """Return the standard WECC VeraGrid result directory.

    :return: Result directory.
    """
    return Path(__file__).resolve().parent / "wecc179_small_signal_rms_results_VeraGrid"


def build_wecc179_rms_benchmark_grid() -> gce.MultiCircuit:
    """Import WECC topology and assign every physical RMS device model.

    :return: RMS-ready WECC grid.
    """
    grid: gce.MultiCircuit = gce.open_file(str(_base_grid_path()))
    assign_standard_network_rms_models(grid=grid, prefix="wecc179")
    dynamic_tables: Wecc179DynamicTables = Wecc179DynamicTables()
    generator_index: int
    for generator_index, generator in enumerate(grid.generators):
        set_rms_model(
            device=generator,
            model=get_wecc179_generator_rms_template(
                vfactory=grid.var_factory,
                generator_index=generator_index,
                system_base=float(grid.Sbase),
                tables=dynamic_tables,
            ).block,
            var_factory=grid.var_factory,
        )
    gce.save_file(grid=grid, filename=str(_output_grid_path()))
    return grid


def run_wecc179_small_signal(show_figures: bool = True) -> None:
    """Run WECC power flow and RMS small-signal stability.

    :param show_figures: Display interactive PyCharm figures after exporting.
    :return: None.
    """
    total_start: float = time.perf_counter()
    timings: dict[str, float] = dict()
    model_start: float = time.perf_counter()
    grid: gce.MultiCircuit = build_wecc179_rms_benchmark_grid()
    timings["case_and_model_build"] = elapsed_seconds(model_start)
    power_flow_start: float = time.perf_counter()
    power_flow: PowerFlowDriver = run_power_flow(grid=grid, tolerance=1.0e-9)
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
    timings["symbolic_to_numeric"] = elapsed_seconds(compilation_start)
    small_signal_start: float = time.perf_counter()
    driver.run()
    timings["small_signal_total"] = elapsed_seconds(small_signal_start)
    timings.update(benchmark_veragrid_isolated_numerical_phases(driver))
    results_directory: Path = _results_directory()
    results_directory.mkdir(parents=True, exist_ok=True)
    dynamic_tables: Wecc179DynamicTables = Wecc179DynamicTables()
    export_start: float = time.perf_counter()
    save_small_signal_results_to_csv(
        driver.results,
        power_flow.results,
        results_directory,
        benchmark_state_labels=get_wecc179_andes_style_state_labels(dynamic_tables),
    )
    timings["result_export"] = elapsed_seconds(export_start)
    timings["end_to_end"] = elapsed_seconds(total_start) - (
        timings["state_matrix_isolated_repeat"]
        + timings["eigenanalysis_isolated_repeat"]
    )
    save_benchmark_timings(
        output_directory=results_directory,
        engine_label="VeraGrid",
        case_label="WECC179",
        timings=timings,
        state_count=int(driver.results.state_matrix.shape[0]),
        mode_count=int(driver.results.eigenvalues.size),
    )
    print("\nEigenvalues:")
    print(driver.results.eigenvalues)
    print(f"\nVeraGrid WECC179 results written to: {results_directory}")
    plot_s_domain_eigenvalues(driver.results.eigenvalues)
    plot_participation_factors(driver.results.participation_factors)
    finish_benchmark_figures(show_figures=show_figures)


if __name__ == "__main__":
    run_wecc179_small_signal()
else:
    pass
