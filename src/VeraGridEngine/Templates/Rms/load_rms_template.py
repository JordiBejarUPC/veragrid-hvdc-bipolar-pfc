# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np

from typing import List

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, Expr, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, real, imag, conj, angle, exp, log, abs, UndefinedConst


class LoadRmsTemplate(RmsModelTemplate):

    def __init__(self, name: str = "rms_load_template"):
        super().__init__(name=name)

        self.tpe: DeviceType = DeviceType.LoadDevice

        self.Vm: Var = Var('')
        self.Va: Var = Var('')

        self.Pl0 = Var("Pl0")
        self.Ql0 = Var("Ql0")

        self.Ql = Var("Ql")
        self.Pl = Var("Pl")

        self._block = Block(
            algebraic_vars=[self.Pl, self.Ql],
            algebraic_eqs=[
                self.Pl - self.Pl0,
                self.Ql - self.Ql0
            ]
        )

        self._block.event_dict = {self.Pl0: Const(1),
                                  self.Ql0: Const(1)}
        self._block.external_mapping={
                VarPowerFlowRefferenceType.P: self.Pl,
                VarPowerFlowRefferenceType.Q: self.Ql
            }
