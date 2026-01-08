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


def get_load_rms_template(name = "Load rms template") -> RmsModelTemplate:
    """
    Get the RMS template model of the Load
    :return: RmsModelTemplate
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    inputs: List[Var] = [Var("Vm_" + name),
                         Var("Va_" + name)
                         ]

    Pl0 = Var("Pl0")
    Ql0 = Var("Ql0")

    Ql = Var("Ql")
    Pl = Var("Pl")

    templ.block.event_dict[Pl0] = Const(-0.0999999)
    templ.block.event_dict[Ql0] = Const(-0.00999999)

    templ.block.algebraic_vars = [Pl, Ql]

    templ.block.algebraic_eqs = [
                Pl - Pl0,
                Ql - Ql0]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Va: inputs[0],
        VarPowerFlowRefferenceType.Vm: inputs[1],
        VarPowerFlowRefferenceType.P: Pl,
        VarPowerFlowRefferenceType.Q: Ql
    }

    templ.block.in_vars = inputs

    return templ