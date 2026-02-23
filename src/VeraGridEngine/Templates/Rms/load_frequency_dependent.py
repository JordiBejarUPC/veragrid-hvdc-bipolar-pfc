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

def FrequencyLoadBuild(name: str = "", Pl0=1.0, Ql0=0.1) -> RmsModelTemplate:
    """
     generator with quadratic saturation
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    inputs = [Var("Vm_"), Var('Va_')]

    #Vars:
    m = Var('m')
    P = Var('P')
    Q = Var('Q')
    Va = inputs[1]

    #Parameters:
    P0 = Var('Pl0')
    Q0 = Var('Ql0')
    V0 = Var('V0')
    Kd = Var('Kd')
    Ki = Var('Ki')
    alpha_p = Var('alpha_p')
    alpha_q = Var('alpha_q')
    beta_p = Var('beta_p')
    beta_q = Var('beta_q')
    Tf = Var('Tf')
    theta0 = Var('theta0')
    
    block1, d_omega = tf_to_diffblock(
        num = [0, Const(1)],
        den = [Const(1), Tf],
        x= (Va - theta0),
        name = "frequency_measure"

    )
    # ZIP coefficients (classic formulation)
    event_dict = {
        P0: Const(Pl0),
        Q0: Const(Ql0),
        V0: Const(None),

        # Exponential Parameters
        alpha_p: Const(1.2),  
        alpha_q: Const(1.2),
        beta_p: Const(1.2),
        beta_q: Const(1.2),

        Tf : Const(0.1),
        theta0: Const(None),
    }  
    
    init_eqs = {
        V0: inputs[0],
        theta0: inputs[1],
        P: P0,
        Q: Q0,
    }
    templ.block = Block(
        algebraic_eqs = [
            P - P0*(inputs[0])**alpha_p*(Const(1) + d_omega)**beta_p,
            Q - Q0*(inputs[0])**alpha_q*(Const(1) + d_omega)**beta_q,
        ],
        algebraic_vars=[P,Q],
        init_eqs = init_eqs,
        event_dict = event_dict,
        children = [block1,]
    )
    
    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: P,
        VarPowerFlowRefferenceType.Q: Q,
        VarPowerFlowRefferenceType.Vm: inputs[0],
    }
    
    templ.block.in_vars = inputs
    
    return templ
    