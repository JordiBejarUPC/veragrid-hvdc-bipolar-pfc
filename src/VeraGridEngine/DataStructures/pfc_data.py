# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import numpy as np
from VeraGridEngine.DataStructures.branch_parent_data import BranchParentData
from VeraGridEngine.enumerations import PfcControlType
from VeraGridEngine.basic_structures import Vec, IntVec, ObjVec, Logger

class PfcData(BranchParentData):
    """
    PfcData class provides a structured model for managing data related to
    Power Flow Controller (PFC) in power grid simulations.
    """

    def __init__(self, nelm: int, nbus: int):
        """
        Branch data arrays
        :param nelm: number of elements
        :param nbus: number of buses
        """
        BranchParentData.__init__(self, nelm=nelm, nbus=nbus)

        self.Q_dc = np.zeros(self.nelm, dtype=int)
        self.R_dc = np.zeros(self.nelm, dtype=int)
        self.S_dc = np.zeros(self.nelm, dtype=int)

        self.control1_int: IntVec = np.zeros(self.nelm, dtype=int)
        self.fault_control_int: IntVec = np.zeros(self.nelm, dtype=int)

        self.control1_val: Vec = np.ones(self.nelm, dtype=float)
        self.control1_bus_idx: IntVec = np.full(nelm, -1, dtype=int)
        self.control1_branch_idx: IntVec = np.full(nelm, -1, dtype=int)

        self.control1_val: Vec = np.ones(self.nelm, dtype=float)

        self.control1_bus_idx: IntVec = np.full(nelm, -1, dtype=int)
        self.control1_branch_idx: IntVec = np.full(nelm, -1, dtype=int)



    def slice(self, elm_idx: IntVec, bus_idx: IntVec, bus_map: IntVec, logger: Logger | None) -> "PfcData":
        """
        Slice branch data by given indices
        :param elm_idx: array of branch indices
        :param bus_idx: array of bus indices
        :param bus_map: map from bus index to branch index
        :param logger: Logger
        :return: new BranchData instance
        """

        data, bus_map = super().slice(elm_idx, bus_idx, bus_map, logger)
        data: PfcData = data
        data.__class__ = PfcData

        data.Q_dc = self.Q_dc[elm_idx]
        data.R_dc = self.R_dc[elm_idx]
        data.S_dc = self.S_dc[elm_idx]

        data.control1_int = self.control1_int[elm_idx]

        data.control1_val = self.control1_val[elm_idx]

        data.control1_bus_idx = self.control1_bus_idx[elm_idx]

        # TODO: think about how to re-map this stuff
        data.control1_branch_idx = self.control1_branch_idx[elm_idx]

        for k in range(data.nelm):
            if data.control1_bus_idx[k] > -1:
                data.control1_bus_idx[k] = bus_map[data.control1_bus_idx[k]]

                if data.control1_bus_idx[k] == -1:
                    if logger is not None:
                        logger.add_error(f"Branch {k}, {self.names[k]} control1 bus is unreachable",
                                         value=data.control1_bus_idx[k])
        return data

    def copy(self) -> "PfcData":
        """
        Get a deep copy of this object
        :return: new BranchData instance
        """
        data: PfcData = super().copy()
        data.__class__ = PfcData

        data.Q_dc = self.Q_dc.copy()
        data.R_dc = self.R_dc.copy()
        data.S_dc = self.S_dc.copy()

        data.dc = self.dc.copy()

        data.control1_int = self.control1_int.copy()

        data.control1_val = self.control1_val.copy()

        data.control1_bus_idx = self.control1_bus_idx.copy()
        data.control1_branch_idx = self.control1_branch_idx.copy()

        return data

    def __len__(self) -> int:
        """
        Get vsc count
        :return:
        """
        return self.nelm
