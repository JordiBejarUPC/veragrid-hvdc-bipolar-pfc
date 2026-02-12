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
