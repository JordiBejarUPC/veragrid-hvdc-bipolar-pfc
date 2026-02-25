# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Dict, List

import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.types import INJECTION_DEVICE_TYPES
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.basic_structures import Vec, IntVec, Mat, Vector, BoolVec


class EmtSolverProperties:

    def __init__(self,
                 # bus: dev.Bus,
                 bus_index: int,
                 block: Block,
                 # bus_regions_dict: Dict[dev.Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]],
                 alter_params_mappings: Dict[int, Const],
                 init_guesses: Dict[int, float],
                 t: Var,
                 # steps: int
                 ):
        """
        Container for all EMT symbolic and solver-related properties
        associated with a single bus.
        :param bus : Bus object.
        :param bus_index: Float.
        :param bus_index: Float.
        :param syst_blocks: .
        :param bus_regions_dict: .
        :param alter_params_mappings: .
        :param init_guesses: .
        :param t: .
        :param steps:

        """

        # self.bus = bus
        # self.name = bus.name
        self.index = bus_index

        # Symbolic structure
        self.devices: Dict[DeviceType, List[INJECTION_DEVICE_TYPES]] | None = None
        # Default initialisation (bus without region block)
        self.region_block: Block = block
        self.blocksolver: BlockSolver | None = None
        self.params0: Vec | None = None
        self.alter_params0: Vec | None = None
        self.x0: Vec | None = None
        self.dx0: Vec | None = None
        self.x: Mat | None = None
        self.dx: Mat | None = None

        # self.devices = bus_regions_dict[bus]
        self.region_block = block

        if len(self.region_block.children) >= 2:  # there's a block apart from the bus block

            # Solver
            self.blocksolver = BlockSolver(block_system=self.region_block, glob_time=t)

            # Parameters
            params_mapping = {}
            # self.params0 = self.blocksolver.build_init_params_vector(params_mapping)

            # alter parameters
            # alter_params_mapping = alter_params_mappings[bus]
            self.alter_params0 = (self.blocksolver.build_init_alter_params_vector(alter_params_mappings))

            # Initial states
            self.x0 = self.blocksolver.build_init_vars_vector_from_uid(init_guess)

            # print(f"init guess Bus region {bus_index} = {init_guesses[bus_index]}")

            self.dx0 = np.zeros(self.blocksolver.n_diff)
            # self.dx0[4] = 1.0

    def set_alter_params0(self, alter_params0: Vec):
        """Attach or replace the alter params."""
        self.alter_params0 = alter_params0
