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

def ExponentialLoadBuild(name: str = "", Pl0 = 1.0, Ql0 =0.1) -> RmsModelTemplate:
    """
     generator with quadratic saturation
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LoadDevice

    inputs = [Var("Vm")]

    #Vars:
    P = Var('P')
    Q = Var('Q')
    
    #Parameters:
    P0 = Var('Pl0')
    Q0 = Var('Ql0')
    V0 = Var('V0')
    a = Var('a')
    b = Var('b')
    
    # ZIP coefficients (classic formulation)
    events_dict = {
        P0: Const(Pl0),
        Q0: Const(Ql0),
        V0: Const(None),
        
        a: Const(5),
        b: Const(5),
    }
    
    init_eqs = {
        V0: inputs[0],
    }
    
    templ.block = Block(
        algebraic_eqs = [
            P - P0*((inputs[0]/V0)**a),
            Q - Q0*((inputs[0]/V0)**b),
        ],
        algebraic_vars=[P,Q],
        event_dict= events_dict,
        init_eqs = init_eqs,
    )

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: P,
        VarPowerFlowRefferenceType.Q: Q,
        VarPowerFlowRefferenceType.Vm: inputs[0],
    }
    
    templ.block.in_vars = inputs

    return templ