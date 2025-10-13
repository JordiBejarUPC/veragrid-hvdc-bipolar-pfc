# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import List

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, Expr,DynamicVarType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, real, imag, conj, angle, exp, log, abs, UndefinedConst


class BusRmsTemplate(RmsModelTemplate):

    def __init__(self, name: str = "rms_bus_template"):
        super().__init__(name=name)

        self.name = name
        self._device_type: DeviceType = DeviceType.BusDevice

        self.parameters: List[str] = []

        self.event_parameters: List[Var] = list()
        self.event_parameters_eqs: List[Expr] = list()

        Vm = Var("Vm")
        Va = Var("Va")
        P = Var("P")
        Q = Var("Q")

        self.block = Block(
            state_eqs=[],
            state_vars=[],
            algebraic_eqs=[
            ],
            # algebraic_vars=[],
            algebraic_vars=[Vm, Va],

            init_eqs={},
            init_vars=[],
            external_mapping={
                DynamicVarType.Vm: Vm,
                DynamicVarType.Va: Va,
                DynamicVarType.P: P,
                DynamicVarType.Q: Q
            }
        )
