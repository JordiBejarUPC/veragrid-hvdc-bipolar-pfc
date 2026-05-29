# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List, Dict
import numpy as np
from scipy.sparse import csc_matrix
from VeraGridEngine.basic_structures import BoolVec, IntVec
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from trunk.dynamics_emt.emt_models_and_circuits.emt_transformer import EmtTransformer
from trunk.dynamics_emt.emt_models_and_circuits.emt_line import EmtLine
from trunk.dynamics_emt.emt_models_and_circuits.emt_load import EmtLoad
from trunk.dynamics_emt.emt_models_and_circuits.emt_generator import EmtGenerator
from trunk.dynamics_emt.emt_models_and_circuits.emt_solver_properties import EmtSolverProperties
from VeraGridEngine.enumerations import VarPowerFlowReferenceType


class EmtCircuit:

    def __init__(self,
                 n_bus: int,
                 n_line: int,
                 n_transformer: int,
                 n_gen: int,
                 n_load: int):
        """

        :param n_bus: Number of buses (int)
        :param n_line: Number of lines (int)
        :param n_transformer: Number of transformers (int)
        :param n_gen: Number of generators (int)
        :param n_load: Number of loads (int)
        """
        self.n_bus = n_bus
        self.n_line = n_line
        self.n_transformer = n_transformer
        self.n_gen = n_gen
        self.n_load = n_load
        self.n_br = n_line + n_transformer  # TODO: might not agree with circuit's number of branches

        self.transformer_emt_data: EmtTransformer = EmtTransformer(n_elm=self.n_transformer)
        self.line_emt_data: EmtLine = EmtLine(n_elm=self.n_line)
        self.gen_emt_data: EmtGenerator = EmtGenerator(n_elm=self.n_gen)
        self.load_emt_data: EmtLoad = EmtLoad(n_elm=self.n_load)

        # NOTE: Used only during simulation, no need to add into the var factory
        self.tme: Var = Var("tme")

        self.h: float = 0
        self.n_delay: int = 0

        self.G0: csc_matrix | None = None
        self.binary_bus_mask: BoolVec = np.zeros(4 * self.n_bus, dtype=bool)
        self.branch_lookup: IntVec = np.zeros(4 * self.n_br, dtype=bool)
        self.bus_idx_lookup: IntVec = np.zeros(4 * self.n_bus, dtype=bool)
        self.branch_from_lookup: IntVec = np.zeros(4 * self.n_br, dtype=bool)
        self.branch_to_lookup: IntVec = np.zeros(4 * self.n_br, dtype=bool)

        self._syst_blocks: List[Block | None] = [None] * self.n_bus
        self._init_guesses: List[Dict[int, float]] = [dict()] * self.n_bus
        self._alter_params_mappings: List[Dict[int, Const]] = [dict()] * self.n_bus
        self._uid2idx_alterparams: Dict[int, int] = dict()

        self._emt_vec: List[EmtSolverProperties | None] = [None] * self.n_bus

    def add_guess(self, bus_idx: int, tpe: VarPowerFlowReferenceType, val: float):
        """
        Add init guess
        :param bus_idx:
        :param tpe:
        :param val:
        :return:
        """
        self.add_guess2(
            bus_idx=bus_idx,
            uid=self._syst_blocks[bus_idx].external_mapping[tpe].uid,
            val=val
        )

    def add_guess2(self, bus_idx: int, uid: int, val: float):
        """
        Add init guess
        :param bus_idx:
        :param uid:
        :param val:
        :return:
        """
        self._init_guesses[bus_idx][uid] = val

    def set_bus_block(self, i: int, block: Block):
        """
        Set the block for the bus i
        :param i:
        :param block:
        :return:
        """
        self._syst_blocks[i] = block

    def init_solver(self, i: int):
        """
        Initialize the Solver for the bus i
        :param i:
        :return:
        """

        self._emt_vec[i] = EmtSolverProperties(
            bus_index=i,
            block=self._syst_blocks[i],
            alter_params_mappings=self._alter_params_mappings[i],
            init_guesses=self._init_guesses[i],
            t=self.tme,
        )

    @property
    def emt_vec(self):
        return self._emt_vec

    @property
    def init_guesses(self):
        return self._init_guesses
