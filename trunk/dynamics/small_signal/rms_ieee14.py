# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path

import pandas as pd

from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.enumerations import RmsInitializationMethod
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
import VeraGridEngine.api as gce

from trunk.dynamics.small_signal.rms_ieee14_small_signal import _build_power_flow_options
from trunk.dynamics.small_signal.rms_ieee14_small_signal import build_ieee14_rms_benchmark_grid


def _get_results_dir() -> Path:
    """Return the VeraGrid RMS results directory.

    :return: Results directory.
    """
    return Path(__file__).resolve().parent / "ieee14_rms_results_VeraGrid"


def run_ieee14_rms() -> None:
    """Run one second of IEEE14 RMS simulation and export CSV results.

    :return: None.
    """
    grid = build_ieee14_rms_benchmark_grid()
    pf_options: PowerFlowOptions = _build_power_flow_options()
    power_flow: PowerFlowDriver = PowerFlowDriver(grid, pf_options)
    power_flow.run()
    pf_results: PowerFlowResults = power_flow.results

    rms_options = RmsOptions(
        time_step=0.001,
        simulation_time=1.0,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=1000,
        verbose=0,
    )
    problem = RmsProblemDae(grid=grid, options=rms_options, pf_results=pf_results)
    solver = BackEulerImplicitIntegration(
        problem=problem,
        t0=0.0,
        t_end=rms_options.simulation_time,
        h=rms_options.time_step,
        max_iter=rms_options.max_iter,
    )
    time_array, values_array, _, _ = solver.simulate()

    state_names = list(problem.get_x_names())
    algebraic_names = list(problem.get_y_names())

    data_dict = dict()
    data_dict["time_s"] = time_array

    state_count = len(state_names)
    state_index = 0
    while state_index < state_count:
        data_dict[str(state_names[state_index])] = values_array[:, state_index]
        state_index += 1

    algebraic_count = len(algebraic_names)
    algebraic_index = 0
    while algebraic_index < algebraic_count:
        data_dict[str(algebraic_names[algebraic_index])] = values_array[:, state_count + algebraic_index]
        algebraic_index += 1

    results_dir = _get_results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(data_dict).to_csv(
        results_dir / "rms_results_VeraGrid_IEEE14.csv",
        index=False,
        float_format="%.10f",
    )


if __name__ == "__main__":
    run_ieee14_rms()
else:
    pass
