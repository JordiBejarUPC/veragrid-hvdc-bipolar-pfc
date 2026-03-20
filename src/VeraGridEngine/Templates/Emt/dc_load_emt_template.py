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
EMT DC Load template.

Models a DC load as a constant power load or constant resistance load
connected to a DC bus.

The model provides:
- Idc: current flowing into the DC bus (for KCL)
- Pdc: power consumption (optional, for monitoring)
"""

def get_dc_load_emt_template(
    grid: MultiCircuit,
    load_name: str = "dc_load",
    P_dc: float = 0.0,  # DC power in MW (p.u. after conversion)
    R_dc: float = None,  # Resistance in p.u. (if constant resistance mode)
    name: str = "dc_load_emt_template"
) -> EmtModelTemplate:
    """
    Build an EMT DC load model.

    Two modes:
    1. Constant power: Idc = P_dc / V_dc
    2. Constant resistance: Idc = V_dc / R_dc

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

    vf: VarFactory = grid.emt_var_factory
    sbase: float = grid.Sbase

    c0 = vf.add_const(0.0)

    # Convert power from MW to p.u.
    P_dc_pu = -P_dc / sbase  # p.u. # in the correct sign convention

    v_dc = vf.add_var(name=f"v_dc_{name}", ref=VarPowerFlowRefferenceType.Vdc)

    i_dc = vf.add_var(name=f"i_dc_{name}", ref=VarPowerFlowRefferenceType.Idc)
    p_dc = vf.add_var(name=f"p_dc_{name}", ref=VarPowerFlowRefferenceType.P)

    templ.block.in_vars = [v_dc]
    templ.block.algebraic_vars = [i_dc, p_dc]

    alg_eqs = []

    if R_dc is not None and R_dc > 0:
        # Constant resistance mode: I = V / R
        alg_eqs.append(i_dc + v_dc / R_dc)
        alg_eqs.append(p_dc - v_dc * i_dc)
    else:
        # Constant power mode: I = P / V
        # Add small epsilon to avoid division by zero
        eps = vf.add_const(1e-10)
        alg_eqs.append(i_dc - P_dc_pu / (v_dc + eps))
        alg_eqs.append(p_dc - P_dc_pu)

    templ.block.algebraic_eqs = alg_eqs

    templ.block.out_vars = [i_dc, p_dc]

    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Idc: i_dc,
        VarPowerFlowRefferenceType.P: None,
    }

    eps = vf.add_const(1e-10)
    if R_dc is not None and R_dc > 0:
        templ.block.init_eqs = {
            i_dc: (-v_dc / R_dc),
            p_dc: (v_dc * i_dc),
        }
    else:
        templ.block.init_eqs = {
            i_dc: (P_dc_pu / (v_dc + eps)),
            p_dc: vf.add_const(P_dc_pu),
        }

    return templ


def get_dc_load_from_device(
    grid: MultiCircuit,
    load_device,
    name: str = "dc_load_emt_template"
) -> EmtModelTemplate:
    """
    Build an EMT DC load model from a load device.

    Args:
        grid: Multicircuit
        load_device: Load device (Generator used as DC load)
        name: Name for the model

    Returns:
        EmtModelTemplate with the DC load block
    """
    P_dc = getattr(load_device, 'P', 0.0)
    return get_dc_load_emt_template(
        grid=grid,
        load_name=load_device.name,
        P_dc=P_dc,
        name=f"{load_device.name}_{name}"
    )
