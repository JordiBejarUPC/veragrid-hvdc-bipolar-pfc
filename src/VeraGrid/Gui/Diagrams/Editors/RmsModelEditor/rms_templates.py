# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List

import numpy as np

from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, UndefinedConst, cos, sin, real, imag, conj, exp, log, abs
from VeraGridEngine.Utils.Symbolic.block import Block, DynamicVarType

buses = List[Block]
generators = List[Block]
lines = List[Block]
loads = List[Block]

class RmsTemplate:
    def __init__(self, api_object: PhysicalDevice):

        self.api_object = api_object
        self.block= Block()

#
# class Bus(RmsTemplate):
#
#
#
#     Vm = Var("Vm")
#     Va = Var("Va")
#     P = Var("P")
#     Q = Var("Q")
#     bus_block = Block(
#                 algebraic_vars=[Vm, Va],
#                 external_mapping={
#                     DynamicVarType.Vm: Vm,
#                     DynamicVarType.Va: Va,
#                     DynamicVarType.P: P,
#                     DynamicVarType.Q: Q}
#             )
#

