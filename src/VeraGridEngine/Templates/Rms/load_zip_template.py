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

def ZIPLoadBuild(name: str = "", Pl0=1.0, Ql0=0.1) -> RmsModelTemplate:
    """
    Builds an RMS model template for a ZIP load.
    
    ZIP load model represents load power consumption as a combination of constant impedance (Z),
    constant current (I), and constant power (P) components. The active and reactive power 
    are calculated as quadratic functions of voltage magnitude.
    
    The power equations are:
        P = P0 * (a1*(V/V0)^2 + a2*(V/V0) + a3)
        Q = Q0 * (a4*(V/V0)^2 + a5*(V/V0) + a6)
    
    Where coefficients must sum to 1.0 for both active (a1+a2+a3) and reactive (a4+a5+a6) power.
    
    Args:
        name (str): Name of the load model
        Pl0 (float): Initial active power at nominal voltage (pu)
        Ql0 (float): Initial reactive power at nominal voltage (pu)
    
    Returns:
        RmsModelTemplate: Configured RMS model template for ZIP load simulation
    
    Raises:
        ValueError: If ZIP coefficients do not sum to 1.0 within tolerance
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    inputs = [Var("Vm_")]

    #Vars:
    P = Var('P')
    Q = Var('Q')

    #Parameters:
    P0 = Var('P0')
    Q0 = Var('Q0')
    V0 = Var('V0')
    a1 = Var('a1')
    a2 = Var('a2')
    a3 = Var('a3')
    a4 = Var('a4')
    a5 = Var('a5')
    a6 = Var('a6')
    
    # ZIP coefficients (classic formulation)
    event_dict = {
        P0: Const(Pl0),
        Q0: Const(Ql0),
        V0: Const(None),

        # Active power ZIP
        a1: Const(0.1),  # Z
        a2: Const(0.1),  # I
        a3: Const(0.8),  # P

        # Reactive power ZIP
        a4: Const(0.1),  # Z
        a5: Const(0.1),  # I
        a6: Const(0.8),  # P
    }

    # --- Validation (fail fast) ---

    P_sum = event_dict[a1].value + event_dict[a2].value + event_dict[a3].value
    Q_sum = event_dict[a4].value + event_dict[a5].value + event_dict[a6].value

    tol = 1e-9

    if abs(P_sum - 1.0) > tol:
        raise ValueError(
            f"Invalid ZIP coefficients for active power: "
            f"a1 + a2 + a3 = {P_sum}, expected 1.0"
        )

    if abs(Q_sum - 1.0) > tol:
        raise ValueError(
            f"Invalid ZIP coefficients for reactive power: "
            f"a4 + a5 + a6 = {Q_sum}, expected 1.0"
        )
    
    init_eqs = {
        V0: inputs[0],
        P: P0,
        Q: Q0,
    }
    templ.block = Block(
        algebraic_eqs = [
            P - P0*(a1*(inputs[0]/V0)**2 + a2*inputs[0]/V0 + a3),
            Q - Q0*(a4*(inputs[0]/V0)**2 + a5*inputs[0]/V0 + a6),
        ],
        algebraic_vars=[P,Q],
        init_eqs = init_eqs,
        event_dict = event_dict,
    )
    
    templ.block.name = 'ZIP Load' 
    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.P: P,
        VarPowerFlowRefferenceType.Q: Q,
        VarPowerFlowRefferenceType.Vm: inputs[0],
    }
    
    templ.block.in_vars = inputs
    
    return templ
    