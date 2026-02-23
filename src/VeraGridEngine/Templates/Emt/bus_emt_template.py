# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowRefferenceType

class BusEmtTemplate(EmtModelTemplate):

    def __init__(self, vf: VarFactory, name: str = "rms_bus_template"):
        """
        Created the RMS Template of a Bus
        :param vf: VarFactory
        :param name: Name of the RMS Model
        """
        super().__init__(name=name)

        self.tpe: DeviceType = DeviceType.BusDevice

        self.v_A = vf.add_var("v_A")
        self.v_B = vf.add_var("v_B")
        self.v_C = vf.add_var("v_C")
        self.P = vf.add_var("P")
        self.Q = vf.add_var("Q")

        self.block = Block(
            alter_params=[self.v_A, self.v_B, self.v_C],
            algebraic_vars=[self.v_A, self.v_B, self.v_C], #?
            out_vars=[self.v_A, self.v_B, self.v_C]
        )

        self._block.external_mapping = {
            VarPowerFlowRefferenceType.v_A: self.v_A,
            VarPowerFlowRefferenceType.v_B: self.v_B,
            VarPowerFlowRefferenceType.v_C: self.v_C,
            VarPowerFlowRefferenceType.P: self.P,
            VarPowerFlowRefferenceType.Q: self.Q
        }



def initialize_bus_emt(bus: Bus, vf: VarFactory):
    """

    :param bus:
    :param vf:
    :return:
    """
    bus.rms_model.model = BusEmtTemplate(vf=vf).block

