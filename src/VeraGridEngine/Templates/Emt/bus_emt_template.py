# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Utils.Symbolic.block import Block, VarPowerFlowRefferenceType
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_basic_formulation_3ph import compute_ybus

# depending on the number of phases of the bus a different model must be created.
class BusEmtTemplateABC(EmtModelTemplate):

    def __init__(self,
                 vf: VarFactory,
                 mask: list[bool],
                 name: str = "emt_bus_template"):
        """
        Created the RMS Template of a Bus
        :param vf: VarFactory
        :param mask: list[bool] with true if the phase exist and false if it doesn't in the order [N,A,B,C]
        :param name: Name of the EMT Model
        """

        super().__init__(name=name)

        self.tpe: DeviceType = DeviceType.BusDevice

        self.v_N = vf.add_var("v_N") if mask[0] else None
        self.v_A = vf.add_var("v_A") if mask[1] else None
        self.v_B = vf.add_var("v_B") if mask[2] else None
        self.v_C = vf.add_var("v_C") if mask[3] else None
        self.P = vf.add_var("P")
        self.Q = vf.add_var("Q")

        v_list = [v for v in (self.v_N, self.v_A, self.v_B, self.v_C) if v is not None]
        if not v_list:
            raise ValueError("Bus has no enabled phases")

        self._block = Block(
            alter_params=v_list, # ?
            algebraic_vars=v_list,
            out_vars=v_list
        )

        self._block.external_mapping = {
            VarPowerFlowRefferenceType.v_N: self.v_N,
            VarPowerFlowRefferenceType.v_A: self.v_A,
            VarPowerFlowRefferenceType.v_B: self.v_B,
            VarPowerFlowRefferenceType.v_C: self.v_C,
            VarPowerFlowRefferenceType.P: self.P,
            VarPowerFlowRefferenceType.Q: self.Q
        }

    @property
    def block(self) -> Block:
        """
        block
        :return: Block
        """
        return self._block

def initialize_bus_emt(grid: MultiCircuit,
                       bus: Bus,
                       vf: VarFactory):
    """
    Initialize 3ph bus block
    A bus will have the phases of the branches connected to it
    :param grid: Multicircuit
    :param bus: Bus
    :param vf: VarFactory
    :return:
    """
    mask = [False,False,False,False] # [N, A, B, C]
    for branch in grid.get_branches_iter(add_vsc=True, add_switch= True, add_hvdc=True):
        if bus == branch.bus_from or bus == branch.bus_to:
            mask[0] |= bool(branch.ys.phN)
            mask[1] |= bool(branch.ys.phA)
            mask[2] |= bool(branch.ys.phB)
            mask[3] |= bool(branch.ys.phC)

    # choose template depending on the number of phases
    bus.rms_model.model = BusEmtTemplateABC(vf=vf, mask = mask).block




