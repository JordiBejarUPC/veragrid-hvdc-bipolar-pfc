# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np
import math

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import (Block, Var, DiffVar, Const, VarPowerFlowRefferenceType, tf_to_diffblock,
                                                 tf_to_diffblock_with_output, tf_to_diffblock_with_antiwindup)
import VeraGridEngine.Utils.Symbolic.symbolic as sym

def DCVoltageSource(Vdc, name: str = "") -> RmsModelTemplate:
    """
    Builds an RMS model template for a DC voltage source with capacitive filtering.
    
    Models a DC voltage source (e.g., photovoltaic array, battery) connected through
    a DC-link capacitor and series resistance. The model captures the DC-side dynamics
    and power injection into the AC grid.
    
    The circuit consists of:
    - DC voltage source (Vpv) with internal resistance (Rpv)
    - DC-link capacitor (C) for energy storage and ripple filtering
    - DC current (Idc) and power (Pdc) output to the converter
    
    The differential-algebraic equations governing the system:
        - Algebraic: Pdc = Idc * Vdc (power balance)
        - Algebraic: Vpv = Vpv0 (source voltage)
        - Differential: C*dVdc/dt + Idc = (Vpv - Vdc)/Rpv (capacitor dynamics)
    
    Args:
        Vdc: DC voltage variable (pu)
        name (str): Name of the DC voltage source model
    
    Returns:
        RmsModelTemplate: Configured RMS model template for DC voltage source simulation
    """
    templ = RmsModelTemplate()

    #Vars:
    Idc = Var('Idc')
    Pdc = Var('Pdc')
    Vpv = Var('Vpv')
    dVdcdt = DiffVar('dVdcdt', base_var = Vdc)

    #Parameters
    C = Var('C')
    Rpv = Var('Rpv')
    Vpv0 = Var('Vpv0')

    event_dict = {
        C:Const(0.01),
        Rpv: Const(0.001),
        Vpv0:Const(None),
    }
    dc_block = Block(
        algebraic_eqs=[
            Pdc - Idc*Vdc,
            Vpv - Vpv0,
            dVdcdt*C + Idc - (Vpv -Vdc)/Rpv
        ],
        algebraic_vars=[Idc, Pdc, Vpv],
        diff_vars = [dVdcdt],
        event_dict= event_dict,
        out_vars  = [Pdc, Idc],
        init_eqs  = {
            Idc: Pdc/Vdc,
            Vpv: Rpv*Idc + Vdc,
            Vpv0: Rpv*Idc + Vdc,
        },
        external_mapping={
            VarPowerFlowRefferenceType.P: Pdc,
            VarPowerFlowRefferenceType.Idc: Idc,
            VarPowerFlowRefferenceType.Vdc: Vdc,
        },
    )
    templ.block = dc_block

    return templ
