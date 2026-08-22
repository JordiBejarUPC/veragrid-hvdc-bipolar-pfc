# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from pathlib import Path

import numpy as np

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import (
    BackEulerImplicitIntegration,
)
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    DynamicSimulationMode,
    FileType,
    RmsInitializationMethod,
)


def test_dgs_v1_first_rms_step_is_finite_and_converged() -> None:
    """Run the tracked Nuactis V1 DGS model through one scalar RMS step.

    :return: None.
    """
    fixture_path: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "grids"
        / "DGS"
        / "hvdc_vsc_v1_complete_static_dynamic.dgs"
    )
    file_open: FileOpen = FileOpen(
        file_name=str(fixture_path),
        options=FileOpenOptions(
            file_type=FileType.DGS,
            dgs_use_dynamic_information=True,
            dgs_dynamic_simulation_mode=DynamicSimulationMode.RMS,
        ),
    )
    grid: MultiCircuit | None = file_open.open()
    assert grid is not None
    assert file_open.logger.error_count() == 0

    power_flow_results: PowerFlowResults = gce.power_flow(grid)
    assert power_flow_results.converged
    assert np.all(np.isfinite(power_flow_results.gen_p))

    rms_options: RmsOptions = RmsOptions(
        time_step=0.001,
        simulation_time=0.001,
        tolerance=1.0e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=100,
        verbose=0,
    )
    problem: RmsProblemDae = RmsProblemDae(
        grid=grid,
        options=rms_options,
        pf_results=power_flow_results,
    )
    problem.set_events_group(
        rms_events_group=RmsEventsGroup(name="Nuactis V1 directed step")
    )
    initial_values: np.ndarray = problem.get_x0()
    initial_differentials: np.ndarray = np.zeros(
        problem.get_diff_var_number(),
        dtype=float,
    )
    assert np.all(np.isfinite(initial_values))
    assert np.all(np.isfinite(problem.get_j11(initial_values, initial_differentials, 0.001).data))
    assert np.all(np.isfinite(problem.get_j12(initial_values, initial_differentials, 0.001).data))
    assert np.all(np.isfinite(problem.get_j21(initial_values, initial_differentials, 0.001).data))
    assert np.all(np.isfinite(problem.get_j22(initial_values, initial_differentials, 0.001).data))

    solver: BackEulerImplicitIntegration = BackEulerImplicitIntegration(
        problem=problem,
        t0=0.0,
        t_end=rms_options.simulation_time,
        h=rms_options.time_step,
        max_iter=rms_options.max_iter,
        tolerance=rms_options.tolerance,
    )
    simulation_result: tuple[np.ndarray, np.ndarray, bool, bool] = solver.simulate()
    times: np.ndarray = simulation_result[0]
    values: np.ndarray = simulation_result[1]
    converged: bool = simulation_result[3]

    assert converged
    assert len(times) == 2
    assert np.all(np.isfinite(values))
