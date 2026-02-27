# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Simulations.options_template import OptionsTemplate


class RmsOptions(OptionsTemplate):
    """
    Rms simulation options
    """

    def __init__(self,
                 time_step: float = 0.001,
                 simulation_time: float = 5,
                 tolerance: float = 1e-6,
                 integration_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeBackEuler,
                 initialization_method: RmsInitializationMethod = RmsInitializationMethod.Explicit,
                 use_init_values: bool = False,
                 max_iter: int = 1000,
                 verbose: int = 0):
        """
        RmsOptions
        :param time_step: time step of the simulations (s)
        :param simulation_time: simulation time (s)
        :param max_iter: max number of iterations
        :param tolerance: Integration tolerance
        :param integration_method: Integration method (default Trapezoid)
        """

        OptionsTemplate.__init__(self, name='RmsSimulationOptions')

        self.integration_method: DynamicIntegrationMethod = integration_method
        self.initialization_method: RmsInitializationMethod = initialization_method
        self.time_step: float = time_step
        self.simulation_time: float = simulation_time
        self.tolerance: float = tolerance
        self.use_init_values: bool = use_init_values
        self.max_iter: int = max_iter
        self.verbose = verbose

        self.register(key="integration_method", tpe=DynamicIntegrationMethod)
        self.register(key="initialization_method", tpe=RmsInitializationMethod)
        self.register(key="time_step", tpe=float)
        self.register(key="simulation_time", tpe=float)
        self.register(key="tolerance", tpe=float)
        self.register(key="use_init_values", tpe=bool)
        self.register(key="max_iter", tpe=int)
