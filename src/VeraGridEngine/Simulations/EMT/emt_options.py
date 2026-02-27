# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Simulations.options_template import OptionsTemplate
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes


class EmtOptions(OptionsTemplate):
    """
    Rms simulation options
    """

    def __init__(self,
                 time_step: float = 0.0001,
                 simulation_time: float = 5,
                 tolerance: float = 1e-6,
                 solver: EmtSolverTypes = EmtSolverTypes.StructuralAD,
                 integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
                 verbose: int = 0):
        """
        EmtOptions
        :param time_step: time step of the simulations (s)
        :param simulation_time: simulation time (s)
        :param tolerance: Integration tolerance
        :param verbose: Verbosity level
        """

        OptionsTemplate.__init__(self, name='EmtSimulationOptions')

        self.time_step: float = time_step
        self.simulation_time: float = simulation_time
        self.tolerance: float = tolerance
        self.solver: EmtSolverTypes = solver
        self.integration_method: DynamicIntegrationMethod = integration_method
        self.verbose = verbose

        self.register(key="time_step", tpe=float)
        self.register(key="simulation_time", tpe=float)
        self.register(key="tolerance", tpe=float)
        self.register(key="solver", tpe=EmtSolverTypes)
        self.register(key="integration_method", tpe=DynamicIntegrationMethod)
        self.register(key="verbose", tpe=int)

