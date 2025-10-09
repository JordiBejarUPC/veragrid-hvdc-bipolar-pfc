# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np

from typing import List

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, DynamicVarType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, real, imag, conj, angle, exp, log, abs, UndefinedConst


class LoadRmsTemplate(RmsModelTemplate):

    def __init__(self, name: str = "rms_load_template"):
        super().__init__(name=name)

        self.name = name
        self._device_type: DeviceType = DeviceType.LoadDevice
        self._block: Block = Block()
        self.parameters: List[str] = ['Pl0', 'Ql0']

        self.Vm: Var = Var('')
        self.Va: Var = Var('')

        self.Pl0 = Const(1)
        self.Ql0 = Const(1)

    def build_template_block(self):

        Ql = Var("Ql")
        Pl = Var("Pl")

        self._block = Block(
            algebraic_eqs=[
                Pl - self.Pl0,
                Ql - self.Ql0
            ],
            algebraic_vars=[Pl, Ql],
            init_eqs={},
            init_vars=[],
            parameters=[],
            external_mapping={
                DynamicVarType.P: Pl,
                DynamicVarType.Q: Ql
            }
        )