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

def DynamicTapLoadBuild(name: str = "", Pl0=1.0, Ql0=0.1) -> RmsModelTemplate:
    """
    Builds an RMS model template for a dynamic tap-changing load with PI voltage control.

    This load model represents a load equipped with an on-load tap changer (OLTC) or similar
    voltage regulation device. A PI controller adjusts the effective voltage ratio (m) to
    maintain the load voltage within desired bounds.

    The model includes:
    - State equation for tap position/ratio (m) controlled by PI regulator
    - Algebraic equations for active and reactive power with exponential voltage dependency
    - Power equations: P = P0*(V/m)^alpha_p, Q = Q0*(V/m)^alpha_q

    The PI controller adjusts m based on voltage deviation from reference:
        dm/dt = -Kd*m + Ki*(V/m - 1 + Kd/Ki*V0)

    Args:
        name (str): Name of the load model
        Pl0 (float): Initial active power at nominal voltage (pu)
        Ql0 (float): Initial reactive power at nominal voltage (pu)

    Returns:
        RmsModelTemplate: Configured RMS model template for dynamic tap load simulation
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    inputs = [Var("Vm_")]

    #Vars:
    m = Var('m')
    P = Var('P')
    Q = Var('Q')

    #Parameters:
    P0 = Var('Pl0')
    Q0 = Var('Ql0')
    V0 = Var('V0')
    Kd = Var('Kd')
    Ki = Var('Ki')
    alpha_p = Var('alpha_p')
    alpha_q = Var('alpha_q')
    m_max = Var('m_max')
    m_min = Var('m_min')
    
    # ZIP coefficients (classic formulation)
    event_dict = {
        P0: Const(Pl0),
        Q0: Const(Ql0),
        V0: Const(None),

        # Exponential Parameters
        alpha_p: Const(1.2),  
        alpha_q: Const(1.2),

        #PI parameters
        Kd: Const(0.1),
        Ki: Const(0.1),
    }  
    
    init_eqs = {
        V0: inputs[0],
        m: V0,
        P: P0,
        Q: Q0,
    }
    templ.block = Block(
        state_eqs=[
            -Kd*m + Ki(inputs[0]/m - Const(1) + Kd/Ki*V0)
        ],
        state_vars= [m],
        algebraic_eqs = [
            P - P0*(inputs[0]/m)**alpha_p,
            Q - Q0*(inputs[0]/m)**alpha_q,
        ],
        algebraic_vars=[P,Q],
        init_eqs = init_eqs,
        event_dict = event_dict,
    )
    
    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: P,
        VarPowerFlowRefferenceType.Q: Q,
        VarPowerFlowRefferenceType.Vm: inputs[0],
    }
    
    templ.block.in_vars = inputs
    
    return templ
    