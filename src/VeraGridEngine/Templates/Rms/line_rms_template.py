# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np
from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Var, Const, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin


def get_line_rms_template(name = "Line rms template") -> RmsModelTemplate:
    """
    Get the RMS template model of the Line
    :return: RmsModelTemplate
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name

    inputs: List[Var] = [Var("Vmf_" + name),
                         Var("Vaf_" + name),
                         Var("Vmt_" + name),
                         Var("Vat_" + name)]



    Qf = Var("Qf")
    Qt = Var("Qt")
    Pf = Var("Pf")
    Pt = Var("Pt")

    g = Var("g")
    b = Var("b")
    bsh = Var("bsh")

    templ.block.event_dict[g] = Const(0.0)
    templ.block.event_dict[b] = Const(0.0)
    templ.block.event_dict[bsh] = Const(0.0)

    templ.block.algebraic_vars = [Pf, Pt, Qf, Qt]

    pi2 = np.pi / 2
    templ.block.algebraic_eqs = [
        Pf - ((inputs[0] ** 2 * g) - g * inputs[0] * inputs[2] * cos(inputs[1] - inputs[3]) + b * inputs[0] * inputs[2] * cos(inputs[1] - inputs[3] + pi2)),
        Qf - (inputs[0] ** 2 * (-bsh / 2 - b) - g * inputs[0] * inputs[2] * sin(inputs[1] - inputs[3]) + b * inputs[0] * inputs[2] * sin(inputs[1] - inputs[3] + pi2)),
        Pt - ((inputs[2] ** 2 * g) - g * inputs[2] * inputs[0] * cos(inputs[3] - inputs[1]) + b * inputs[2] * inputs[0] * cos(inputs[3] - inputs[1] + pi2)),
        Qt - (inputs[2] ** 2 * (-bsh / 2 - b) - g * inputs[2] * inputs[0] * sin(inputs[3] - inputs[1]) + b * inputs[2] * inputs[0] * sin(inputs[3] - inputs[1] + pi2)),
    ]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Vaf: inputs[1],
        VarPowerFlowRefferenceType.Vat: inputs[3],
        VarPowerFlowRefferenceType.Vmf: inputs[0],
        VarPowerFlowRefferenceType.Vmt: inputs[2],
        VarPowerFlowRefferenceType.Pf: Pf,
        VarPowerFlowRefferenceType.Pt: Pt,
        VarPowerFlowRefferenceType.Qf: Qf,
        VarPowerFlowRefferenceType.Qt: Qt,
    }
    templ.block.in_vars = inputs

    return templ
