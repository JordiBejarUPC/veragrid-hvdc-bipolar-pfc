# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np
import math

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (Block, Var, Const, VarPowerFlowRefferenceType, tf_to_diffblock,
                                                 tf_to_diffblock_with_output, tf_to_diffblock_with_antiwindup)
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def ShuntLoadBuild(name: str = "") -> RmsModelTemplate:
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.ShuntDevice
    res_block = Block()
    pi = math.pi
    #Inputs:
    inputs = [Var('Vm'), Var('Va')]
    Vm = inputs[0]
    Va = inputs[1]
    #Variables:
    P = Var('P')
    Q = Var('Q')
    g = Var('g')
    b = Var('b')

    events_dict = {
        g: Const(0.0),
        b: Const(0.4),
    }
    
    res_block = Block(
        algebraic_eqs=[
            P+g*Vm**2,
            Q-b*Vm**2,
        ],
        algebraic_vars=[P, Q],
        init_eqs={
            P: Const(0.0),
            Q: Const(0.1),
        }
    )


    res_block.event_dict = events_dict
    res_block.external_mapping = {
        VarPowerFlowRefferenceType.Vm: inputs[0],
        VarPowerFlowRefferenceType.Va: inputs[1],
        VarPowerFlowRefferenceType.P: P,
        VarPowerFlowRefferenceType.Q: Q,
    }
    res_block.in_vars = inputs

    
    templ.block = res_block
    return templ