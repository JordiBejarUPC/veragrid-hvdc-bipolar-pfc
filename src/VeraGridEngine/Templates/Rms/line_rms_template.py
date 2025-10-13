# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, Expr, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, real, imag, conj, angle, exp, log, abs, UndefinedConst


class LineRmsTemplate(RmsModelTemplate):

    def __init__(self, name: str = "rms_line_template"):
        super().__init__(name=name)

        self.tpe: DeviceType = DeviceType.LineDevice
        self.parameters: List[str] = ['R', 'X', 'B']

        self.event_parameters: List[Var] = list()
        self.event_parameters_eqs: List[Expr] = list()

        self.Vmf: Var = Var('')
        self.Vaf: Var = Var('')
        self.Vmt: Var = Var('')
        self.Vat: Var = Var('')

        # taken from VeraGrid model
        self.R = Const(1)
        self.X = Const(1)
        self.B = Const(1)




    def build_template_block(self):

        Qf = Var("Qf")
        Qt = Var("Qt")
        Pf = Var("Pf")
        Pt = Var("Pt")

        ys = 1.0 / complex(self.R.value, self.X.value)
        g = Const(ys.real)
        b = Const(ys.imag)
        bsh = self.B


        self._block = Block(
            algebraic_eqs=[
                Pf - ((self.Vmf ** 2 * g) - g * self.Vmf * self.Vmt * cos(self.Vaf - self.Vat) + b * self.Vmf * self.Vmt * cos(self.Vaf - self.Vat + np.pi / 2)),
                Qf - (self.Vmf ** 2 * (-bsh / 2 - b) - g * self.Vmf * self.Vmt * sin(self.Vaf - self.Vat) + b * self.Vmf * self.Vmt * sin(
                    self.Vaf - self.Vat + np.pi / 2)),
                Pt - ((self.Vmt ** 2 * g) - g * self.Vmt * self.Vmf * cos(self.Vat - self.Vaf) + b * self.Vmt * self.Vmf * cos(self.Vat - self.Vaf + np.pi / 2)),
                Qt - (self.Vmt ** 2 * (-bsh / 2 - b) - g * self.Vmt * self.Vmf * sin(self.Vat - self.Vaf) + b * self.Vmt * self.Vmf * sin(
                    self.Vat - self.Vaf + np.pi / 2)),
            ],
            algebraic_vars=[Pf, Pt, Qf, Qt],
            init_eqs={},
            init_vars=[],
            parameters=[self.R, self.X, self.B],
            external_mapping={
                VarPowerFlowRefferenceType.Pf: Pf,
                VarPowerFlowRefferenceType.Pt: Pt,
                VarPowerFlowRefferenceType.Qf: Qf,
                VarPowerFlowRefferenceType.Qt: Qt,
            }
        )
