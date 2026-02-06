# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Simulations.options_template import OptionsTemplate


class SmallSignalStabilityOptions(OptionsTemplate):
    """
    Rms simulation options
    """

    def __init__(self,  ss_assessment_time: float = 5,):
        """
        RmsOptions
        todo: add EMT vs RMS!
        :param time_step: time step of the simulations (s)
        :param ss_assessment_time: stability assessment time (s)
        :param tolerance: Integration tolerance
        :param integration_method: Integration method (default Trapezoid)
        """

        OptionsTemplate.__init__(self, name='RmsSimulationOptions')
        self.ss_assessment_time: float = ss_assessment_time

        self.register(key="ss_assessment_time", tpe=float)
