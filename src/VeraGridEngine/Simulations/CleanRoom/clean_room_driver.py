# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import SimulationTypes
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.CleanRoom.clean_room import train_aggregate_model


class CleanRoomDriver(DriverTemplate):
    name = 'Clean room'
    tpe = SimulationTypes.CleanRoom_run

    def __init__(self, grid: MultiCircuit):
        """
        Clustering analysis driver constructor
        :param grid: MultiCircuit instance
        """
        DriverTemplate.__init__(self, grid=grid)


    def run(self):
        """
        Run thread
        """
        self.tic()
        self.report_text("Training AI model")
        self.report_progress(0.0)

        self.toc()

