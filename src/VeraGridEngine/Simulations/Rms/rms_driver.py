# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
import pandas as pd
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.numerical.integration_methods import BackEulerImplicitIntegration
from VeraGridEngine.enumerations import EngineType, SimulationTypes
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

        self.grid = grid

        self.pf_results: PowerFlowResults | None = pf_results

        self.options = options

        self.results = RmsResults(values=np.empty(0),
                                  time_array=pd.DatetimeIndex(pd.to_datetime(np.empty(0))),
                                  stat_vars=list(),
                                  algeb_vars=list(),
                                  uid2idx=dict(),
                                  vars_glob_name2uid=dict(),
                                  devices=[])

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
        self.tic()
        # # Get integration method
        # if self.options.integration_method not in [DynamicIntegrationMethod.BackEuler,
        #                                            DynamicIntegrationMethod.Trapezoid]:
        #     raise ValueError(f"integrator not implemented :( {self.options.integration_method}")
        #
        # # TODO: Check if there is a cleaner way to get all the devices in a list
        # params_mapping: Dict = dict()
        #
        # sim_time, ss, init_guess = initialize_rms(self.grid, self.pf_results, self.options.use_init_values)
        # slv = BlockSolver(ss, sim_time)
        #
        # params0 = slv.build_init_params_vector(params_mapping)
        # x0 = slv.build_init_vars_vector_from_uid(init_guess)
        #
        # dx0 = np.zeros(slv.diff_vars_number)
        #
        # t, y, timings = slv.simulate(
        #     t0=0,
        #     t_end=self.options.simulation_time,
        #     h=self.options.time_step,
        #     x0=x0,
        #     dx0=dx0,
        #     params0=params0,
        #     method=self.options.integration_method,
        #     newton_tol=self.options.tolerance,
        #     newton_max_iter=1000,
        #     followed_vars=None,
        #     initialized=False,
        #     verbose=False,
        # )

        problem = RmsProblemDae(grid=self.grid,
                                options=self.options,
                                pf_results=self.pf_results)

        solver = BackEulerImplicitIntegration(
            problem=problem,
            t0=0,
            t_end=self.options.simulation_time,
            h=self.options.time_step,
            max_iter=self.options.max_iter
        )

        solver.simulate()

        # buses = self.grid.get_buses()
        # branches = self.grid.get_branches()
        # injections = self.grid.get_injection_devices()
        # devices = list(buses) + list(branches) + list(injections)

        self.results = RmsResults(
            values=solver.y,
            time_array=pd.DatetimeIndex(pd.to_datetime(solver.t * 1e9)),
            stat_vars=problem._state_vars,
            algeb_vars=problem._algebraic_vars,
            uid2idx=problem._uid2idx_vars,
            vars_glob_name2uid=problem.v_glob_name2uid,
            devices=problem.get_device_vars_dict()
        )

        self.toc()
