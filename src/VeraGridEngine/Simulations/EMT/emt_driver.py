# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from typing import Dict, List
import scipy.sparse as sp

import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.types import INJECTION_DEVICE_TYPES
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.enumerations import EngineType, SimulationTypes
from VeraGridEngine.Simulations.EMT.initialization_emt import initialize_emt
from VeraGridEngine.Simulations.PowerFlow.power_flow_results_3ph import PowerFlowResults3Ph
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.basic_structures import Vec, IntVec, Mat, Vector, BoolVec
from scipy.sparse.linalg import factorized



class EmtSimulationDriver(DriverTemplate):
    name = 'EMT Simulation'
    tpe = SimulationTypes.EmtDynamic_run

    """
    Dynamic wrapper to use with Qt
    """

    def __init__(self, grid: MultiCircuit,
                 options: EmtOptions,
                 pf_results: PowerFlowResults3Ph | None,
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

        self.pf_results: PowerFlowResults3Ph | None = pf_results

        self.options = options

        self.results = EmtResults(values=np.empty(0),
                                  time_array=pd.DatetimeIndex(pd.to_datetime(np.empty(0))),
                                  uid2idx=dict(),
                                  vars_glob_name2uid=dict(),
                                  devices=[])

        self.line_states = {}

    def run(self):
        """
        Main function to initialize and run the system simulation.

        This function sets up logging, starts the dynamic simulation, and
        logs the outcome. It handles and logs any exceptions raised during execution.
        :return:
        """
        # Run the dynamic simulation
        return self.run_time_simulation()

    def run_time_simulation(self):
        """
        Performs the EMTP loop using the MNA.
        :return:
        """
        self.tic()

        nc = compile_numerical_circuit_at(
            circuit=self.grid,
            fill_three_phase=True
        )

        (t, syst_blocks, init_guesses, h, N_delay, G0,
         binary_bus_mask, branch_lookup, bus_idx_lookup,
         alter_params_mappings, uid2idx_alterparams) = initialize_emt(
            grid=self.grid,
            emt_options=self.options,
            pf_results=self.pf_results,
            nc=nc)

        # Inicializar estados internos para líneas
        for branch in self.grid.get_branches_iter():
            if branch.device_type.value == 'Line':
                self.line_states[branch.name] = {
                    'i_prev': None,  # Para modelo Pi
                    'x_states': None  # Para modelo J-Marti
                }

        # simulate
        t, V, hist, Ibranches, hist_branches, Is, x, dx = self.simulate_emt(
            t=t,
            simulation_time=self.options.simulation_time,
            grid=self.grid,
            nc=nc,
            syst_blocks=syst_blocks,
            init_guesses=init_guesses,
            time_step=h,
            N_delay=N_delay,
            G0=G0,
            binary_bus_mask=binary_bus_mask,
            branch_lookup=branch_lookup,
            bus_idx_lookup=bus_idx_lookup,
            alter_params_mappings=alter_params_mappings,
            uid2idx_alterparams=uid2idx_alterparams
        )

        # self.results = EmtResults(values=y,
        #                           time_array=pd.DatetimeIndex(pd.to_datetime(t)),
        #                           uid2idx=slv.uid2idx_vars,
        #                           vars_glob_name2uid=slv.v_glob_name2uid,
        #                           devices = devices)

        self.toc()

        return t, V, hist, Ibranches, hist_branches, Is, x, dx


