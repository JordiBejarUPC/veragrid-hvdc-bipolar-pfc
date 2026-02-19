# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
import pandas as pd

import cProfile
import pstats

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.enumerations import EngineType, SimulationTypes, DynamicIntegrationMethod
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults


class RmsSimulationDriver(DriverTemplate):
    name = 'Rms Simulation'
    tpe = SimulationTypes.RmsDynamic_run

    """
    Dynamic wrapper to use with Qt
    """

    def __init__(self, grid: MultiCircuit,
                 options: RmsOptions,
                 pf_results: PowerFlowResults | None,
                 engine: EngineType = EngineType.VeraGrid):
        """
        DynamicDriver class constructor
        :param grid: MultiCircuit instance
        :param options: RmsOptions instance (optional)
        :param pf_results: PowerFlowResults
        :param engine: EngineType (i.e., EngineType.VeraGrid) (optional)
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        self.integartion_methods_dict = {DynamicIntegrationMethod.BackEuler: BackEulerImplicitIntegration}

        self.grid = grid

        self.pf_results: PowerFlowResults | None = pf_results

        self.options = options

        self.results = RmsResults(well_initialized = True,
                                  converged = True,
                                  values=np.empty(0),
                                  time_array=pd.DatetimeIndex(pd.to_datetime(np.empty(0))),
                                  variables=list(),
                                  uid2idx=dict(),
                                  vars_glob_name2uid=dict(),
                                  devices_vars_info=dict())

    def run(self):
        """
        Main function to initialize and run the system simulation.

        This function sets up logging, starts the dynamic simulation, and
        logs the outcome. It handles and logs any exceptions raised during execution.
        :return:
        """
        # Run the dynamic simulation
        self.run_time_simulation()

    def run_time_simulation(self):
        """
        Performs the numerical integration using the chosen method.
        :return:
        """
        res = self.pf_results

        print(f"Converged: {res.converged}")
        print(res.get_bus_df())
        print(res.get_branch_df())

        profiler = cProfile.Profile()
        profiler.enable()

        problem = RmsProblemDae(grid=self.grid,
                                options=self.options,
                                pf_results=self.pf_results)



        solver = self.integartion_methods_dict[self.options.integration_method](
            problem=problem,
            t0=0,
            t_end=self.options.simulation_time,
            h=self.options.time_step,
            max_iter=self.options.max_iter
        )

        t, y, well_initialized, converged = solver.simulate()

        profiler.disable()

        stats = pstats.Stats(profiler).sort_stats('cumtime')
        stats.print_stats(10)

        self.results = RmsResults(
            well_initialized=well_initialized,
            converged=converged,
            values=solver.y,
            time_array=pd.DatetimeIndex(pd.to_datetime(solver.t * 1e9)),
            variables=problem.state_and_algebraic_vars,
            uid2idx=problem.uid2idx_vars,
            vars_glob_name2uid=problem.vars_glob_name2uid,
            devices_vars_info=problem.get_device_vars_dict()
        )


