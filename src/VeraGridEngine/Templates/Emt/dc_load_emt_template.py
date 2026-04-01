# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0



from typing import Dict
import numpy as np

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Var, Expr

"""
EMT DC load template.

The load follows the EMT injection convention used by the rest of the
framework: current and power are positive when entering the bus. A consuming DC
load therefore has negative ``i_dc`` and negative ``p_dc``.
"""

def get_dc_load_emt_template(
    grid: MultiCircuit,
    P_dc: float = 0.0,  # DC power in MW (p.u. after conversion)
    R_dc: float = None,  # Resistance in p.u. (if constant resistance mode)
    name: str = "dc_load_emt_template"
) -> EmtModelTemplate:
    """
    Build an EMT DC load model.

    Two modes are supported:
    1. constant power: ``i_dc = -P_cons / v_dc``
    2. constant resistance: ``i_dc = -v_dc / R_dc``

    Args:
        grid: Multicircuit
        load_name: Name of the load device
        P_dc: DC power in MW (will be converted to p.u.)
        R_dc: Resistance in p.u. (if provided, uses constant R mode)
        name: Name for the model

    Returns:
        EmtModelTemplate with the DC load block
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    templ.block.name = name

    vf: VarFactory = grid.var_factory
    sbase: float = grid.Sbase

    # Positive ``P_dc`` means consumed DC power. The injected bus power is the
    # opposite quantity because loads withdraw power from the bus.
    P_cons_pu = float(P_dc) / sbase

    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowRefferenceType.Vdc)

    i_dc = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowRefferenceType.Idc)
    p_dc = vf.add_var(name=f"p_dc_{name}", reference=VarPowerFlowRefferenceType.P)

    templ.block.in_vars = [v_dc]
    templ.block.algebraic_vars = [i_dc, p_dc]

    alg_eqs = []
    eps = vf.add_const(1e-10)

    if R_dc is not None and R_dc > 0:
        # Constant-resistance load consuming power from the DC bus.
        alg_eqs.append(i_dc + v_dc / R_dc)
        alg_eqs.append(p_dc - v_dc * i_dc)
    else:
        # Constant-power load consuming power from the DC bus.
        alg_eqs.append(i_dc + P_cons_pu / (v_dc + eps))
        alg_eqs.append(p_dc + P_cons_pu)

    templ.block.algebraic_eqs = alg_eqs

    templ.block.out_vars = [i_dc, p_dc]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Vdc: v_dc,
        VarPowerFlowRefferenceType.Idc: i_dc,
        VarPowerFlowRefferenceType.P: p_dc,
    }

    if R_dc is not None and R_dc > 0:
        templ.block.init_eqs = {
            i_dc: -v_dc / R_dc,
            p_dc: -(v_dc * v_dc) / R_dc,
        }
    else:
        templ.block.init_eqs = {
            i_dc: -P_cons_pu / (v_dc + eps),
            p_dc: vf.add_const(-P_cons_pu),
        }

    return templ


def get_dc_load_from_device(
    grid: MultiCircuit,
    load,
    name: str = "dc_load_emt_template"
) -> EmtModelTemplate:
    """
    Build an EMT DC load model from a load device.

    Args:
        grid: Multicircuit
        load: Load device (Generator used as DC load)
        name: Name for the model

    Returns:
        EmtModelTemplate with the DC load block
    """
    P_dc = load.P
    return get_dc_load_emt_template(
        grid=grid,
        P_dc=P_dc,
        name=name
    )
