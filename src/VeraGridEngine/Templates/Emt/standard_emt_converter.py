# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0



from typing import List
import numpy as np

from VeraGridEngine.enumerations import DeviceType
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, Var, VarPowerFlowRefferenceType
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
import VeraGridEngine.Utils.Symbolic.symbolic as sym

"""
Standard converter template for EMT simulation.

This is an ideal converter model that connects a DC bus with an AC bus,
maintaining power balance: P_ac = P_dc

The converter takes:
- DC side: V_dc (bus DC voltage) as input
- AC side: v_A, v_B, v_C (bus AC instantaneous voltages) as inputs

And provides:
- DC side: I_dc (current flowing into the DC bus)
- AC side: i_A, i_B, i_C (instantaneous three-phase currents)

External mapping for EmtProblemDae:
- v_A, v_B, v_C: AC bus voltages (from bus)
- Vdc: DC bus voltage (from bus)
- i_A, i_B, i_C: AC phase currents (to bus - entering the bus)
- Idc: DC current (to bus - entering the DC bus)

For KCL connection:
- If the DC bus is bus_from: If_dc is looked up
- If the DC bus is bus_to: It_dc is looked up
- AC currents i_A, i_B, i_C are added to the AC bus KCL
"""

def StandardConverterEmtBuild(
    vfactory: VarFactory,
    name: str = "standard_converter_emt",
    P_ref0: float = 0.0
) -> EmtModelTemplate:
    """
    Build a standard ideal converter model for EMT simulation.

    The converter maintains power balance between AC and DC sides:
        P_ac = v_A * i_A + v_B * i_B + v_C * i_C = V_dc * I_dc = P_dc

    Args:
        vfactory: Variable factory for creating symbolic variables
        name: Name for the converter model

    Returns:
        EmtModelTemplate with the converter block
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice

    # =================================================================
    # INPUT VARIABLES (from buses)
    # =================================================================
    # AC side voltages from the AC bus
    v_A = vfactory.add_var(name=f"v_A_{name}", ref=VarPowerFlowRefferenceType.v_A)
    v_B = vfactory.add_var(name=f"v_B_{name}", ref=VarPowerFlowRefferenceType.v_B)
    v_C = vfactory.add_var(name=f"v_C_{name}", ref=VarPowerFlowRefferenceType.v_C)

    # DC side voltage from the DC bus
    v_dc = vfactory.add_var(name=f"v_dc_{name}", ref=VarPowerFlowRefferenceType.Vdc)

    inputs = [v_A, v_B, v_C, v_dc]

    # =================================================================
    # OUTPUT VARIABLES (to buses)
    # =================================================================
    # AC side instantaneous currents (entering the AC bus)
    i_A = vfactory.add_var(name=f"i_A_{name}", ref=VarPowerFlowRefferenceType.i_A)
    i_B = vfactory.add_var(name=f"i_B_{name}", ref=VarPowerFlowRefferenceType.i_B)
    i_C = vfactory.add_var(name=f"i_C_{name}", ref=VarPowerFlowRefferenceType.i_C)

    # DC side current (entering the DC bus)
    # Note: For the KCL, we need If_dc or It_dc depending on which bus is DC
    i_dc = vfactory.add_var(name=f"i_dc_{name}", ref=VarPowerFlowRefferenceType.Idc)

    # =================================================================
    # INTERNAL VARIABLES
    # =================================================================
    # Active power reference (can be controlled externally)
    P_ref = vfactory.add_var(name=f"P_ref_{name}")

    # =================================================================
    # PARAMETERS
    # =================================================================

    event_dict = {
        P_ref: vfactory.add_const(P_ref0),
    }

    # =================================================================
    # ALGEBRAIC EQUATIONS
    # =================================================================
    algebraic_eqs = []

    eps = vfactory.add_const(1e-10)
    v_sq = v_A * v_A + v_B * v_B + v_C * v_C

    algebraic_eqs.append(i_A - P_ref * v_A / (v_sq + eps))
    algebraic_eqs.append(i_B - P_ref * v_B / (v_sq + eps))
    algebraic_eqs.append(i_C - P_ref * v_C / (v_sq + eps))
    algebraic_eqs.append(v_dc * i_dc + P_ref)

    # =================================================================
    # ALGEBRAIC VARIABLES
    # =================================================================
    algebraic_vars = [i_A, i_B, i_C, i_dc]

    # =================================================================
    # INITIALIZATION EQUATIONS
    # =================================================================
    # Use power flow results for initialization
    # The P_ref will be set from power flow initialization
    init_eqs = {}

    # =================================================================
    # BUILD THE BLOCK
    # =================================================================
    converter_block = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        event_dict=event_dict,
        init_eqs=init_eqs,
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc],
    )

    # =================================================================
    # EXTERNAL MAPPING
    # =================================================================
    # This mapping tells EmtProblemDae how to connect the converter
    # to the buses based on the device configuration
    converter_block.external_mapping = {
        VarPowerFlowRefferenceType.v_N: None,
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,

        VarPowerFlowRefferenceType.Vdc: v_dc,

        VarPowerFlowRefferenceType.i_N: None,
        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,

        VarPowerFlowRefferenceType.if_N: None,
        VarPowerFlowRefferenceType.if_A: None,
        VarPowerFlowRefferenceType.if_B: None,
        VarPowerFlowRefferenceType.if_C: None,

        VarPowerFlowRefferenceType.it_N: None,
        VarPowerFlowRefferenceType.it_A: None,
        VarPowerFlowRefferenceType.it_B: None,
        VarPowerFlowRefferenceType.it_C: None,

        VarPowerFlowRefferenceType.Sf_A: None,
        VarPowerFlowRefferenceType.Sf_B: None,
        VarPowerFlowRefferenceType.Sf_C: None,

        VarPowerFlowRefferenceType.St_A: None,
        VarPowerFlowRefferenceType.St_B: None,
        VarPowerFlowRefferenceType.St_C: None,

        VarPowerFlowRefferenceType.d_v_N_f: None,
        VarPowerFlowRefferenceType.d_v_A_f: None,
        VarPowerFlowRefferenceType.d_v_B_f: None,
        VarPowerFlowRefferenceType.d_v_C_f: None,

        VarPowerFlowRefferenceType.d_v_N_t: None,
        VarPowerFlowRefferenceType.d_v_A_t: None,
        VarPowerFlowRefferenceType.d_v_B_t: None,
        VarPowerFlowRefferenceType.d_v_C_t: None,

        # For KCL at DC bus (bus_from)
        VarPowerFlowRefferenceType.Idc: i_dc,

        VarPowerFlowRefferenceType.P: None,
        # VarPowerFlowRefferenceType.P: P_ref,
    }

    converter_block.name = name
    templ.block = converter_block

    return templ


def StandardConverterEmtBuildWithControl(
    vfactory: VarFactory,
    name: str = "standard_converter_ctrl",
    control_mode: str = "P"  # "P" for active power control
) -> EmtModelTemplate:
    """
    Build a standard converter model with basic current control.

    This version adds a simple current control loop that regulates
    the AC currents to achieve the desired power flow.

    Args:
        vfactory: Variable factory
        name: Name for the model
        control_mode: Control mode ("P" for active power)

    Returns:
        EmtModelTemplate with controlled converter
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice

    # =================================================================
    # INPUTS (from buses)
    # =================================================================
    v_A = vfactory.add_var(name=f"v_A_{name}", ref=VarPowerFlowRefferenceType.v_A)
    v_B = vfactory.add_var(name=f"v_B_{name}", ref=VarPowerFlowRefferenceType.v_B)
    v_C = vfactory.add_var(name=f"v_C_{name}", ref=VarPowerFlowRefferenceType.v_C)
    v_dc = vfactory.add_var(name=f"V_dc_{name}", ref=VarPowerFlowRefferenceType.Vdc)

    inputs = [v_A, v_B, v_C, v_dc]

    # =================================================================
    # OUTPUTS (to buses)
    # =================================================================
    i_A = vfactory.add_var(name=f"i_A_{name}", ref=VarPowerFlowRefferenceType.i_A)
    i_B = vfactory.add_var(name=f"i_B_{name}", ref=VarPowerFlowRefferenceType.i_B)
    i_C = vfactory.add_var(name=f"i_C_{name}", ref=VarPowerFlowRefferenceType.i_C)
    i_dc = vfactory.add_var(name=f"Idc_{name}", ref=VarPowerFlowRefferenceType.Idc)

    # =================================================================
    # INTERNAL VARIABLES
    # =================================================================
    P_ref = vfactory.add_var(name=f"P_ref_{name}")
    P_measured = vfactory.add_var(name=f"P_meas_{name}")

    # Current magnitude reference
    I_mag_ref = vfactory.add_var(name=f"I_mag_ref_{name}")
    I_mag = vfactory.add_var(name=f"I_mag_{name}")

    # =================================================================
    # PARAMETERS
    # =================================================================
    event_dict = {
        P_ref: vfactory.add_const(None),
    }

    # =================================================================
    # ALGEBRAIC EQUATIONS
    # =================================================================
    algebraic_eqs = []

    # Instantaneous AC power
    P_ac = v_A * i_A + v_B * i_B + v_C * i_C

    # Power measurement
    algebraic_eqs.append(P_measured - P_ac)

    # DC power balance
    algebraic_eqs.append(v_dc * i_dc - P_ref)

    # Current magnitude from instantaneous currents
    algebraic_eqs.append(I_mag - sym.sqrt(i_A * i_A + i_B * i_B + i_C * i_C + vfactory.add_const(1e-10)))

    # Current magnitude reference from power (simplified: I = P / |V|)
    V_mag = sym.sqrt(v_A * v_A + v_B * v_B + v_C * v_C + vfactory.add_const(1e-10))
    algebraic_eqs.append(I_mag_ref - P_ref / (V_mag + vfactory.add_const(1e-10)))

    # Proportional current injection (simplified control)
    # i_phase = I_mag * v_phase / |V|
    sqrt3_inv = vfactory.add_const(1.0 / np.sqrt(3))
    algebraic_eqs.append(i_A - I_mag_ref * v_A / (V_mag + vfactory.add_const(1e-10)))
    algebraic_eqs.append(i_B - I_mag_ref * v_B / (V_mag + vfactory.add_const(1e-10)))
    algebraic_eqs.append(i_C - I_mag_ref * v_C / (V_mag + vfactory.add_const(1e-10)))

    # =================================================================
    # ALGEBRAIC VARIABLES
    # =================================================================
    algebraic_vars = [P_measured, i_A, i_B, i_C, i_dc, I_mag, I_mag_ref]

    # =================================================================
    # INITIALIZATION
    # =================================================================
    init_eqs = {
        P_measured: P_ref,
        i_A: vfactory.add_const(0.0),
        i_B: vfactory.add_const(0.0),
        i_C: vfactory.add_const(0.0),
        i_dc: vfactory.add_const(0.0),
        I_mag: vfactory.add_const(0.0),
        I_mag_ref: vfactory.add_const(0.0),
    }

    # =================================================================
    # BUILD BLOCK
    # =================================================================
    converter_block = Block(
        algebraic_eqs=algebraic_eqs,
        algebraic_vars=algebraic_vars,
        event_dict=event_dict,
        init_eqs=init_eqs,
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc],
    )

    converter_block.external_mapping = {
        VarPowerFlowRefferenceType.v_A: v_A,
        VarPowerFlowRefferenceType.v_B: v_B,
        VarPowerFlowRefferenceType.v_C: v_C,

        VarPowerFlowRefferenceType.Vdc: v_dc,

        VarPowerFlowRefferenceType.i_A: i_A,
        VarPowerFlowRefferenceType.i_B: i_B,
        VarPowerFlowRefferenceType.i_C: i_C,

        # For KCL at AC bus (bus_to), map i_A/B/C to it_A/B/C
        VarPowerFlowRefferenceType.it_A: i_A,
        VarPowerFlowRefferenceType.it_B: i_B,
        VarPowerFlowRefferenceType.it_C: i_C,

        # For KCL at DC bus (bus_from)
        VarPowerFlowRefferenceType.Idc: i_dc,

        VarPowerFlowRefferenceType.if_N: None,
        VarPowerFlowRefferenceType.it_N: None,
        VarPowerFlowRefferenceType.if_A: None,
        VarPowerFlowRefferenceType.if_B: None,
        VarPowerFlowRefferenceType.if_C: None,

        VarPowerFlowRefferenceType.P: P_ref,
    }

    converter_block.name = name
    templ.block = converter_block

    return templ
