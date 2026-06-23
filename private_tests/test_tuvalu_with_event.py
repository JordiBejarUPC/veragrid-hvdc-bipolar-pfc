# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod
import VeraGridEngine.api as gce

def test_simulate_tuvalu():
    """
   This test opens the Tuvalu grid with an event applied and runs a rms simulation
    """

    folder = os.path.join('data', 'grids')
    name = 'funafuti_rms_event.veragrid'
    fname = os.path.join(folder, name)

    # open the Tuvalu grid
    grid = gce.open_file(fname)

    events_group = RmsEventsGroup(name="simulation1")


    # run power flow
    options = gce.PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
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

    res = gce.power_flow(grid, options=options)

    print(f"Converged: {res.converged}")
    print(res.get_bus_df())
    print(res.get_branch_df())

    # run simulation
    options = RmsOptions(time_step=0.001,
                         simulation_time=1,
                         tolerance=1e-6,
                         integration_method=DynamicIntegrationMethod.DaeBackEuler,
                         initialization_method=RmsInitializationMethod.Explicit,
                         use_init_values=False,
                         max_iter=1000,
                         verbose=0)

    problem = RmsProblemDae(grid=grid,
                            options=options,
                            pf_results=res)

    problem.set_events_group(events_group)

    solver = BackEulerImplicitIntegration(
        problem=problem,
        t0=0,
        t_end=options.simulation_time,
        h=options.time_step,
        max_iter=options.max_iter
    )

    t, y, well_initialized, converged = solver.simulate()

    # check results
    assert well_initialized

    assert converged

