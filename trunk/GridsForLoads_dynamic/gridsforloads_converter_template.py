# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Utils.Symbolic.symbolic import cos, sin, Expr
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import hard_saturation, sampled_value
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, DeviceType, ParamPowerFlowReferenceType


def get_trafo_grid_connection_G4L(vf: VarFactory, name: str = "G4L_transformer") -> EmtModelTemplate:
    """
    Equivalent transformer where the load is connected.
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name
    templ.block.name = name

    c0 = vf.add_const(0.0)

    # Reuse the standard EMT branch parameter API slots so the model can be
    # initialized through VeraGrid's existing static-parameter mapping.
    Raa = vf.add_var(name=f"Raa_{name}")
    Rbb = vf.add_var(name=f"Rbb_{name}")
    Rcc = vf.add_var(name=f"Rcc_{name}")
    Linv_aa = vf.add_var(name=f"Linv_aa_{name}")
    Linv_bb = vf.add_var(name=f"Linv_bb_{name}")
    Linv_cc = vf.add_var(name=f"Linv_cc_{name}")
    Caa = vf.add_var(name=f"Caa_{name}")
    Cbb = vf.add_var(name=f"Cbb_{name}")
    Ccc = vf.add_var(name=f"Ccc_{name}")
    R_Cf_A = vf.add_var(name=f"R_Cf_A_{name}")
    R_Cf_B = vf.add_var(name=f"R_Cf_B_{name}")
    R_Cf_C = vf.add_var(name=f"R_Cf_C_{name}")
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Raa] = Raa
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Rbb] = Rbb
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Rcc] = Rcc
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Linv_aa] = Linv_aa
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Linv_bb] = Linv_bb
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Linv_cc] = Linv_cc
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Caa] = Caa
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Cbb] = Cbb
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Ccc] = Ccc

    templ.block.parameters[Raa] = c0
    templ.block.parameters[Rbb] = c0
    templ.block.parameters[Rcc] = c0
    templ.block.parameters[Linv_aa] = c0
    templ.block.parameters[Linv_bb] = c0
    templ.block.parameters[Linv_cc] = c0
    templ.block.parameters[Caa] = c0
    templ.block.parameters[Cbb] = c0
    templ.block.parameters[Ccc] = c0

    # MATLAB initialization:
    # R_Cf = 0.05 * U^2 / Sb = 0.05 * Zbase, so in per unit R_Cf_pu = 0.05.
    templ.block.event_dict[R_Cf_A] = vf.add_const(0.05)
    templ.block.event_dict[R_Cf_B] = vf.add_const(0.05)
    templ.block.event_dict[R_Cf_C] = vf.add_const(0.05)

    # grid connection voltages
    v_f_A = vf.add_var(name=f"v_f_A_{name}", reference=VarPowerFlowReferenceType.vf_A)
    v_f_B = vf.add_var(name=f"v_f_B_{name}", reference=VarPowerFlowReferenceType.vf_B)
    v_f_C = vf.add_var(name=f"v_f_C_{name}", reference=VarPowerFlowReferenceType.vf_C)

    # VSC connection voltages
    v_t_A = vf.add_var(name=f"v_t_A_{name}", reference=VarPowerFlowReferenceType.vt_A)
    v_t_B = vf.add_var(name=f"v_t_B_{name}", reference=VarPowerFlowReferenceType.vt_B)
    v_t_C = vf.add_var(name=f"v_t_C_{name}", reference=VarPowerFlowReferenceType.vt_C)

    inputs = [v_f_A, v_f_B, v_f_C, v_t_A, v_t_B, v_t_C]

    # from and to currents
    i_f_A = vf.add_var(name=f"i_f_A_{name}", reference=VarPowerFlowReferenceType.if_A)
    i_f_B = vf.add_var(name=f"i_f_B_{name}", reference=VarPowerFlowReferenceType.if_B)
    i_f_C = vf.add_var(name=f"i_f_C_{name}", reference=VarPowerFlowReferenceType.if_C)
    i_t_A = vf.add_var(name=f"i_t_A_{name}", reference=VarPowerFlowReferenceType.it_A)
    i_t_B = vf.add_var(name=f"i_t_B_{name}", reference=VarPowerFlowReferenceType.it_B)
    i_t_C = vf.add_var(name=f"i_t_C_{name}", reference=VarPowerFlowReferenceType.it_C)

    # series current and derivative
    i_ser_A = vf.add_var(name=f"i_ser_A_{name}")
    i_ser_B = vf.add_var(name=f"i_ser_B_{name}")
    i_ser_C = vf.add_var(name=f"i_ser_C_{name}")
    di_ser_A = vf.add_diff_var(name=f"di_ser_A_{name}", base_var=i_ser_A)
    di_ser_B = vf.add_diff_var(name=f"di_ser_B_{name}", base_var=i_ser_B)
    di_ser_C = vf.add_diff_var(name=f"di_ser_C_{name}", base_var=i_ser_C)

    # shunt series RC branch on the converter side
    i_cap_t_A = vf.add_var(name=f"i_cap_t_A_{name}")
    i_cap_t_B = vf.add_var(name=f"i_cap_t_B_{name}")
    i_cap_t_C = vf.add_var(name=f"i_cap_t_C_{name}")
    q_t_A = vf.add_var(name=f"q_t_A_{name}")
    q_t_B = vf.add_var(name=f"q_t_B_{name}")
    q_t_C = vf.add_var(name=f"q_t_C_{name}")
    dq_t_A = vf.add_diff_var(name=f"dq_t_A_{name}", base_var=q_t_A)
    dq_t_B = vf.add_diff_var(name=f"dq_t_B_{name}", base_var=q_t_B)
    dq_t_C = vf.add_diff_var(name=f"dq_t_C_{name}", base_var=q_t_C)

    # P and Q ac
    Pac = vf.add_var(name=f"Pac_{name}")
    Qac = vf.add_var(name=f"Qac_{name}")

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            Linv_aa * (v_f_A - v_t_A - Raa * i_ser_A),
            Linv_bb * (v_f_B - v_t_B - Rbb * i_ser_B),
            Linv_cc * (v_f_C - v_t_C - Rcc * i_ser_C),
            i_cap_t_A,
            i_cap_t_B,
            i_cap_t_C,
        ],
        state_vars=[i_ser_A, i_ser_B, i_ser_C, q_t_A, q_t_B, q_t_C],
        diff_vars = [di_ser_A, di_ser_B, di_ser_C, dq_t_A, dq_t_B, dq_t_C],

        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            q_t_A - Caa * (v_t_A - R_Cf_A * i_cap_t_A),
            q_t_B - Cbb * (v_t_B - R_Cf_B * i_cap_t_B),
            q_t_C - Ccc * (v_t_C - R_Cf_C * i_cap_t_C),
            i_f_A - i_ser_A,
            i_f_B - i_ser_B,
            i_f_C - i_ser_C,
            i_t_A - (-i_ser_A + i_cap_t_A),
            i_t_B - (-i_ser_B + i_cap_t_B),
            i_t_C - (-i_ser_C + i_cap_t_C),
            Pac - (v_t_A*i_t_A + v_t_B*i_t_B + v_t_C*i_t_C),
            Qac - (1 / np.sqrt(3)) * ((v_t_A - v_t_B) * i_t_C +
                                     (v_t_B - v_t_C) * i_t_A +
                                     (v_t_C - v_t_A) * i_t_B),
        ],
        algebraic_vars=[i_cap_t_A, i_cap_t_B, i_cap_t_C, i_f_A, i_f_B, i_f_C, i_t_A, i_t_B, i_t_C, Pac, Qac],
        in_vars=inputs,
        out_vars=[i_f_A, i_f_B, i_f_C, i_t_A, i_t_B, i_t_C],
        init_eqs={
            i_ser_A: i_f_A,
            i_ser_B: i_f_B,
            i_ser_C: i_f_C,
            q_t_A: Caa * (v_t_A - R_Cf_A * i_cap_t_A),
            q_t_B: Cbb * (v_t_B - R_Cf_B * i_cap_t_B),
            q_t_C: Ccc * (v_t_C - R_Cf_C * i_cap_t_C),
            i_cap_t_A: c0,
            i_cap_t_B: c0,
            i_cap_t_C: c0,
            Pac: v_t_A*i_t_A + v_t_B*i_t_B + v_t_C*i_t_C,
            Qac: (1 / np.sqrt(3)) * ((v_t_A - v_t_B) * i_t_C +
                                     (v_t_B - v_t_C) * i_t_A +
                                     (v_t_C - v_t_A) * i_t_B),
        },
        diff_init_eqs={
            di_ser_A: Linv_aa * (v_f_A - v_t_A - Raa * i_ser_A),
            di_ser_B: Linv_bb * (v_f_B - v_t_B - Rbb * i_ser_B),
            di_ser_C: Linv_cc * (v_f_C - v_t_C - Rcc * i_ser_C),
            dq_t_A: i_cap_t_A,
            dq_t_B: i_cap_t_B,
            dq_t_C: i_cap_t_C,
        },
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.vf_N: None,
        VarPowerFlowReferenceType.vf_A: v_f_A,
        VarPowerFlowReferenceType.vf_B: v_f_B,
        VarPowerFlowReferenceType.vf_C: v_f_C,
        VarPowerFlowReferenceType.vt_N: None,
        VarPowerFlowReferenceType.vt_A: v_t_A,
        VarPowerFlowReferenceType.vt_B: v_t_B,
        VarPowerFlowReferenceType.vt_C: v_t_C,
        VarPowerFlowReferenceType.if_N: None,
        VarPowerFlowReferenceType.if_A: i_f_A,
        VarPowerFlowReferenceType.if_B: i_f_B,
        VarPowerFlowReferenceType.if_C: i_f_C,
        VarPowerFlowReferenceType.it_N: None,
        VarPowerFlowReferenceType.it_A: i_t_A,
        VarPowerFlowReferenceType.it_B: i_t_B,
        VarPowerFlowReferenceType.it_C: i_t_C,
        VarPowerFlowReferenceType.Pt: Pac,
        VarPowerFlowReferenceType.Qt: Qac,
    }

    return templ


def get_grid_side_converter_GFL(vf: VarFactory, name: str = "G4L_grid_side_converter") -> EmtModelTemplate:
    """
    VSC average model

    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    # Reuse the standard EMT branch parameter API slots so the model can be
    # initialized through VeraGrid's existing static-parameter mapping.
    Raa = vf.add_var(name=f"Raa_{name}")
    Rbb = vf.add_var(name=f"Rbb_{name}")
    Rcc = vf.add_var(name=f"Rcc_{name}")
    Linv_aa = vf.add_var(name=f"Linv_aa_{name}")
    Linv_bb = vf.add_var(name=f"Linv_bb_{name}")
    Linv_cc = vf.add_var(name=f"Linv_cc_{name}")

    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Raa] = Raa
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Rbb] = Rbb
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Rcc] = Rcc
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Linv_aa] = Linv_aa
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Linv_bb] = Linv_bb
    templ.block.api_obj_mapping[ParamPowerFlowReferenceType.Linv_cc] = Linv_cc

    U = 33000
    Sb = 2000000
    omega = 2 * np.pi * 50
    Zbase = U * U / Sb
    L_f = Zbase / (10 * omega)
    R_f = (Zbase / 10) * 0.1

    templ.block.parameters[Raa] = R_f
    templ.block.parameters[Rbb] = R_f
    templ.block.parameters[Rcc] = R_f
    templ.block.parameters[Linv_aa] = 1/L_f
    templ.block.parameters[Linv_bb] = 1/L_f
    templ.block.parameters[Linv_cc] = 1/L_f

    # grid connection voltages
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)

    # DC connection voltages
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)

    # AC voltage reference from the controller -> VOLTAGE SOURCE VOLTAGES
    v_con_A = vf.add_var(name=f"v_con_A_{name}")
    v_con_B = vf.add_var(name=f"v_con_B_{name}")
    v_con_C = vf.add_var(name=f"v_con_C_{name}")

    inputs = [v_A, v_B, v_C, v_dc, v_con_A, v_con_B, v_con_C]

    # AC and DC currents
    i_A = vf.add_var(name=f"i_f_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_f_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_f_C_{name}", reference=VarPowerFlowReferenceType.i_C)
    i_dc = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)

    # series current and derivative
    i_ser_A = vf.add_var(name=f"i_ser_A_{name}")
    i_ser_B = vf.add_var(name=f"i_ser_B_{name}")
    i_ser_C = vf.add_var(name=f"i_ser_C_{name}")
    di_ser_A = vf.add_diff_var(name=f"di_ser_A_{name}", base_var=i_ser_A)
    di_ser_B = vf.add_diff_var(name=f"di_ser_B_{name}", base_var=i_ser_B)
    di_ser_C = vf.add_diff_var(name=f"di_ser_C_{name}", base_var=i_ser_C)

    Pac_bus =  vf.add_var(name=f"Pac_bus_{name}")
    Pac = vf.add_var(name=f"Pac_{name}")

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            # AC RL branch + AC voltage source
            Linv_aa * (v_A - v_con_A - Raa * i_ser_A),
            Linv_bb * (v_B - v_con_B - Rbb * i_ser_B),
            Linv_cc * (v_C - v_con_C - Rcc * i_ser_C),
        ],
        state_vars=[i_ser_A, i_ser_B, i_ser_C],
        diff_vars=[di_ser_A, di_ser_B, di_ser_C],

        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            # AC currents
            i_A - i_ser_A,
            i_B - i_ser_B,
            i_C - i_ser_C,

            # DC current injection
            Pac - (v_con_A * i_A + v_con_B * i_B + v_con_C * i_C),
            i_dc * v_dc - Pac, #without delay!
            Pac_bus - (v_A * i_A + v_B * i_B + v_C * i_C),
        ],
        algebraic_vars=[i_A, i_B, i_C, Pac, i_dc, Pac_bus],
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc, Pac_bus],
        init_eqs={
            i_ser_A: i_A,
            i_ser_B: i_B,
            i_ser_C: i_C,
            Pac: v_con_A * i_A + v_con_B * i_B + v_con_C * i_C,
            Pac_bus: v_A * i_A + v_B * i_B + v_C * i_C,
        },
        diff_init_eqs={
            di_ser_A: Linv_aa * (v_A - v_con_A - Raa * i_ser_A),
            di_ser_B: Linv_bb * (v_B - v_con_B - Rbb * i_ser_B),
            di_ser_C: Linv_cc * (v_C - v_con_C - Rcc * i_ser_C),
        },
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
        VarPowerFlowReferenceType.Idc: i_dc,
        VarPowerFlowReferenceType.P: Pac,
    }

    return templ

def get_load_side_converter_GFL(vf: VarFactory, name: str = "G4L_load_side_converter") -> EmtModelTemplate:
    """
    Load side converter: load current source + DC capacitor
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    # Reuse the standard EMT branch parameter API slots so the model can be
    # initialized through VeraGrid's existing static-parameter mapping.

    Sb = 2000000
    Vdc_ref = 1200
    C_DC_expr = Sb * 0.02 * 2 / Vdc_ref * Vdc_ref
    Cdc = vf.add_var(name=f"Cdc_{name}")
    templ.block.event_dict[Cdc] = C_DC_expr

    # DC connection voltages
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)

    # DC load current
    i_dc_L = vf.add_var(name=f"i_dc_L_{name}")

    # i_dc from VSC
    i_dc_vsc = vf.add_var(name=f"i_dc_vsc_{name}")

    inputs = [i_dc_vsc, i_dc_L]

    # DC current
    i_dc = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)

    # cap current and charge
    i_cap_dc = vf.add_var(name=f"i_cap_dc_{name}")
    q_cap = vf.add_var(name=f"q_cap_{name}")
    dq_cap = vf.add_diff_var(name=f"dq_cap_{name}", base_var=q_cap)


    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            i_cap_dc,
        ],
        state_vars=[q_cap],
        diff_vars=[dq_cap],
        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            q_cap - Cdc * v_dc,
            i_dc + i_dc_L - i_cap_dc,
            i_dc_vsc - i_dc, # current balance equation -> as if there was a dc bus!
        ],
        algebraic_vars=[i_cap_dc, i_dc, v_dc],
        in_vars=inputs,
        out_vars=[v_dc],
        init_eqs={
            i_dc: vf.add_const(1.0),
            q_cap: Cdc * v_dc,
            i_cap_dc: c0,
        },
        diff_init_eqs={
            dq_cap:i_cap_dc,
        },
    )

    # the grid has only ac, just one connection!
    # templ.block.external_mapping = {
    #     VarPowerFlowReferenceType.Vdc: v_dc,
    #     VarPowerFlowReferenceType.Idc: i_dc,
    # }

    return templ

def get_load_side_converter_control_GFL(vf: VarFactory, name: str = "G4L_load_side_converter_control") -> EmtModelTemplate:
    """
    Load side converter control (PI)
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    # Vdc reference
    v_dc_ref = vf.add_var(name=f"v_dc_ref_{name}")

    # PI
    Kp_E = vf.add_var(name=f"Kp_E_{name}")
    Ki_E = vf.add_var(name=f"Ki_E_{name}")

    C_DC = 0.05
    chi_E = 0.707
    tau_E = 0.1
    w_E: float = 4 / (chi_E * tau_E)
    Kp_E_expr: float = C_DC * chi_E * w_E
    Ki_E_expr: float = (C_DC/2) * w_E*w_E

    templ.block.event_dict[Kp_E] = vf.add_const(Kp_E_expr)
    templ.block.event_dict[Ki_E] = vf.add_const(Ki_E_expr)

    # DC connection voltages
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)

    # DC load current
    i_dc_L = vf.add_var(name=f"i_dc_L_{name}")

    inputs = [v_dc]

    # DC current and power
    i_dc = vf.add_var(name=f"i_dc_{name}", reference=VarPowerFlowReferenceType.Idc)
    p_dc = vf.add_var(name=f"p_dc_{name}")

    # error
    err = vf.add_var(name=f"err_{name}")
    # integral state of I (PI)
    x_e = vf.add_var(name=f"x_e_{name}")
    dx_e = vf.add_var(name=f"dx_e_{name}", base_var=x_e)

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            Ki_E * err,
        ],
        state_vars=[x_e],
        diff_vars=[dx_e],
        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            err - (v_dc_ref*v_dc_ref - v_dc*v_dc),
            p_dc -(Kp_E*err + x_e), # PI output
            i_dc_L*v_dc - p_dc, # load control output WITHOUT DELAY!
        ],
        algebraic_vars=[err, p_dc, i_dc_L],
        in_vars=inputs,
        out_vars=[i_dc_L],
        init_eqs={
            i_dc: vf.add_const(1.0),
            i_dc_L: i_dc,
            p_dc: i_dc_L*v_dc,
            err: c0,
            x_e: c0,
        },
        diff_init_eqs={
            dx_e: err,
        },
    )

    # templ.block.external_mapping = {
    #     VarPowerFlowReferenceType.Vdc: v_dc,
    #     VarPowerFlowReferenceType.Idc: i_dc,
    #     # VarPowerFlowReferenceType.Pdc: p_dc,
    # }

    return templ

def get_grid_side_converter_control_GFL(vf: VarFactory, name: str = "G4L_grid_side_converter_control") -> EmtModelTemplate:
    """
    This function connects all converter controls:
    - Clark-park transform
    - PLL with VSM
    - Virtual admittance - current limitation - current loop
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name
    templ.block.name = name


    clark_park_transforms_mdl = get_clark_park_transforms_qd_GFL(vf=vf).block
    PLL_mdl = get_PLL_GFL(vf=vf).block
    VA_mdl = get_virtual_admittance_GFL(vf=vf).block
    current_limiter_mdl = get_current_limiter_GFL(vf=vf).block
    current_loop_mdl = get_current_loop_GFL(vf=vf).block

    # IN VARS: v_A, v_B, v_C, i_A, i_B, i_C
    templ.block.in_vars = [clark_park_transforms_mdl.in_vars[0], # v_A
                           clark_park_transforms_mdl.in_vars[1], # v_B
                           clark_park_transforms_mdl.in_vars[2], # v_C
                           clark_park_transforms_mdl.in_vars[3], # i_A
                           clark_park_transforms_mdl.in_vars[4], # i_B
                           clark_park_transforms_mdl.in_vars[5], # i_C
                           PLL_mdl.in_vars[3], # Pac
                           ]
    # OUT VARS:  v_con_A, v_con_B, v_con_C,
    templ.block.out_vars = [current_loop_mdl.out_vars[0], # v_con_A
                            current_loop_mdl.out_vars[1], # v_con_B
                            current_loop_mdl.out_vars[2], # v_con_C
                            ]

    # CONNECT VARIABLES BETWEEN CHILDREN
    # phase_pll
    vf.add_connection(clark_park_transforms_mdl.in_vars[6], PLL_mdl.out_vars[0])
    vf.add_connection(current_loop_mdl.in_vars[4], PLL_mdl.out_vars[0])
    # omega pll
    vf.add_connection(current_loop_mdl.in_vars[5], PLL_mdl.out_vars[1])
    # v_q
    vf.add_connection(VA_mdl.in_vars[0], clark_park_transforms_mdl.out_vars[0])
    vf.add_connection(current_loop_mdl.in_vars[0], clark_park_transforms_mdl.out_vars[0])
    # v_d
    vf.add_connection(VA_mdl.in_vars[1], clark_park_transforms_mdl.out_vars[1])
    vf.add_connection(current_loop_mdl.in_vars[1], clark_park_transforms_mdl.out_vars[1])
    # i_q
    vf.add_connection(current_loop_mdl.in_vars[2], clark_park_transforms_mdl.out_vars[2])
    # i_d
    vf.add_connection(current_loop_mdl.in_vars[3], clark_park_transforms_mdl.out_vars[3])
    # i_q out VA
    vf.add_connection(current_limiter_mdl.in_vars[0], VA_mdl.out_vars[0])
    # i_d out VA
    vf.add_connection(current_limiter_mdl.in_vars[1], VA_mdl.out_vars[1])
    # i_q_lim
    vf.add_connection(current_loop_mdl.in_vars[6], current_limiter_mdl.out_vars[0])
    # i_d_lim
    vf.add_connection(current_loop_mdl.in_vars[7], current_limiter_mdl.out_vars[1])

    # APPEND CHILDREN
    templ.block.children.append(clark_park_transforms_mdl)
    templ.block.children.append(PLL_mdl)
    templ.block.children.append(VA_mdl)
    templ.block.children.append(current_limiter_mdl)
    templ.block.children.append(current_loop_mdl)

    # EXTERNAL MAPPING
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: clark_park_transforms_mdl.in_vars[0],
        VarPowerFlowReferenceType.v_B: clark_park_transforms_mdl.in_vars[1],
        VarPowerFlowReferenceType.v_C: clark_park_transforms_mdl.in_vars[2],
        VarPowerFlowReferenceType.i_A: clark_park_transforms_mdl.in_vars[3],
        VarPowerFlowReferenceType.i_B: clark_park_transforms_mdl.in_vars[4],
        VarPowerFlowReferenceType.i_C: clark_park_transforms_mdl.in_vars[5],
    }

    return templ


def get_clark_park_transforms_qd_GFL(vf: VarFactory, name: str = "G4L_clark_park_transforms_qd") -> EmtModelTemplate:
    """
    clark - park transforms to qd axis
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    # grid connection voltages
    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)

    # AC currents
    i_A = vf.add_var(name=f"i_f_A_{name}", reference=VarPowerFlowReferenceType.i_A)
    i_B = vf.add_var(name=f"i_f_B_{name}", reference=VarPowerFlowReferenceType.i_B)
    i_C = vf.add_var(name=f"i_f_C_{name}", reference=VarPowerFlowReferenceType.i_C)


    # theta pll
    phase_pll = vf.add_var(name=f"phase_pll_{name}")

    inputs = [v_A, v_B, v_C, i_A, i_B, i_C, phase_pll]

    # clark park voltage
    alpha_v = vf.add_var(name=f"alpha_v_{name}")
    beta_v = vf.add_var(name=f"beta_v_{name}")
    v_d = vf.add_var(name=f"v_d_{name}")
    v_q = vf.add_var(name=f"v_q_{name}")
    # clark park current
    alpha_i = vf.add_var(name=f"alpha_i_{name}")
    beta_i = vf.add_var(name=f"beta_i_{name}")
    i_d = vf.add_var(name=f"i_d_{name}")
    i_q = vf.add_var(name=f"i_q_{name}")

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[],
        state_vars=[],
        diff_vars=[],
        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            # voltage clark-park transform
            alpha_v - ((1 / 3) * (2 * v_A - v_B - v_C)),
            beta_v - ((1 / 3) * (-np.sqrt(3) * v_B - np.sqrt(3) * v_C)),
            v_q - (alpha_v * cos(phase_pll) - beta_v * sin(phase_pll)),
            v_d - (alpha_v * sin(phase_pll) + beta_v * cos(phase_pll)),
            # current clark-park transform
            alpha_i - ((1 / 3) * (2 * i_A - i_B - i_C)),
            beta_i - ((1 / 3) * (-np.sqrt(3) * i_B - np.sqrt(3) * i_C)),
            i_q - (alpha_i * cos(phase_pll) - beta_i * sin(phase_pll)),
            i_d - (alpha_i * sin(phase_pll) + beta_i * cos(phase_pll)),
        ],
        algebraic_vars=[alpha_v, beta_v, v_q, v_d,
                        alpha_i, beta_i, i_q, i_d,],
        in_vars=inputs,
        out_vars=[v_q, v_d, i_q, i_d],
        init_eqs={
            alpha_v: c0,
            beta_v: c0,
            alpha_i: c0,
            beta_i: c0,
            v_q: alpha_v * cos(phase_pll) - beta_v * sin(phase_pll),
            v_d: alpha_v * sin(phase_pll) + beta_v * cos(phase_pll),
            i_q: alpha_i * cos(phase_pll) - beta_i * sin(phase_pll),
            i_d: alpha_i * sin(phase_pll) + beta_i * cos(phase_pll),
        },
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
        VarPowerFlowReferenceType.i_A: i_A,
        VarPowerFlowReferenceType.i_B: i_B,
        VarPowerFlowReferenceType.i_C: i_C,
    }

    return templ

def get_PLL_GFL(vf: VarFactory, name: str = "G4L_PLL") -> EmtModelTemplate:
    """
    PLL with VSM
    rate limiter missing!
    """
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    v_A = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_B = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_C = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)

    # ac power
    Pac = vf.add_var(name=f"Pac_{name}")

    P_ref = vf.add_var(name=f"P_ref_{name}")
    templ.block.event_dict[P_ref] = vf.add_const(0.8)

    inputs =[v_A, v_B, v_C, Pac]

    # outputs
    phase_pll = vf.add_var(name=f"phase_pll_{name}")
    omega_pll = vf.add_diff_var(name=f"omega_pll_{name}", base_var = phase_pll)

    # parameters
    Kp_pll = vf.add_var(name=f"Kp_pll_{name}")
    Ki_pll = vf.add_var(name=f"Ki_pll_{name}")
    # synchronization control: Virtual synchronous machine
    k_d = vf.add_var(name=f"k_d_{name}") # damping
    omega_ref = vf.add_var(name=f"omega_ref_{name}")
    H = vf.add_var(name=f"H_{name}")
    Sb = vf.add_var(name=f"Sb_{name}")
    k_p = vf.add_var(name=f"k_p_{name}") # power frequency droop with saturation option

    # pll
    tau_pll = 0.01
    xi_pll = 0.707
    U = 33000
    Vac = U*np.sqrt(2/3)
    Kp_pll_expr = 4*xi_pll*xi_pll/(tau_pll*Vac)
    Ki_pll_expr = Kp_pll_expr / tau_pll
    # VSM
    Sb_expr = 2000000
    omega_expr = 2 * np.pi * 50
    Vdc_ref = 1200
    C_DC = Sb_expr * 0.02 * 2 / Vdc_ref * Vdc_ref
    C_pu = C_DC * Vdc_ref * Vdc_ref / Sb_expr
    Zaparent = 0.5
    chi = 0.8
    kH = (1.935 / 2 / 50) / (1 - (665 * 665 / Vdc_ref * Vdc_ref))
    kP = chi * 2 * np.sqrt(kH * (1 / Zaparent) * omega_expr * 2 / C_pu) / (kH * (1 / Zaparent) * omega_expr)

    H_expr = C_pu / (kH * 4)
    k_d_expr = kP * (C_pu / 2 * (1 / Zaparent) * omega_expr)
    k_p_expr = vf.add_const(20)

    templ.block.event_dict[Kp_pll] = Kp_pll_expr
    templ.block.event_dict[Ki_pll] = Ki_pll_expr
    templ.block.event_dict[k_d] = k_d_expr
    templ.block.event_dict[omega_ref] = omega_expr
    templ.block.event_dict[H] = H_expr
    templ.block.event_dict[Sb] = Sb_expr
    templ.block.event_dict[k_p] = k_p_expr

    # clark transform
    alpha = vf.add_var(name=f"alpha_{name}")
    beta =  vf.add_var(name=f"beta_{name}")

    # park transform
    v_d = vf.add_var(name=f"v_d_{name}")
    v_q = vf.add_var(name=f"v_q_{name}")

    # PLL angle
    theta_pll = vf.add_var(name=f"theta_pll_{name}")
    d_theta_pll = vf.add_var(name=f"d_theta_pll_{name}")
    w_pll = vf.add_var(name=f"w_pll_{name}")

    # integral state of I PLL
    x_e_pll = vf.add_var(name=f"x_e_pll_{name}")
    dx_e_pll = vf.add_var(name=f"dx_e_pll_{name}", base_var=x_e_pll)

    # virtual synchronous machine helper parameters
    x = vf.add_var(name=f"x_{name}")
    y = vf.add_var(name=f"y_{name}")
    dy = vf.add_diff_var(name=f"dy_{name}", base_var=y)

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            Ki_pll * (-v_d),
            w_pll, # WITHOUT DELAY!
            # ------------------------------------------ VSM
            ((1 - y) * k_p - P_ref + Pac / Sb + x) / (2 * H),
            omega_pll,
        ],
        state_vars=[x_e_pll, theta_pll, y, phase_pll],
        diff_vars=[dx_e_pll, d_theta_pll, dy, omega_pll],
        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            alpha - ((1/3) * (2*v_A - v_B - v_C)),
            beta - ((1/3) * (-np.sqrt(3)*v_B - np.sqrt(3)*v_C)),
            v_q -(alpha * cos(theta_pll) - beta * sin(theta_pll)),
            v_d -(alpha * sin(theta_pll) + beta * cos(theta_pll)),
            w_pll - (-v_d * Kp_pll + x_e_pll),
            # ------------------------------------------ VSM
            x - (( w_pll / omega_ref) - y) * k_d

        ],
        algebraic_vars=[alpha, beta, v_q, v_d, w_pll, x],
        in_vars=inputs,
        out_vars=[phase_pll, omega_pll],
        init_eqs={
            x_e_pll: c0,
            theta_pll: c0,
            alpha: (1/3) * (2*v_A - v_B - v_C),
            beta: (1/3) * (-np.sqrt(3)*v_B - np.sqrt(3)*v_C),
            v_q: alpha * cos(theta_pll) - beta * sin(theta_pll),
            v_d: alpha * sin(theta_pll) + beta * cos(theta_pll),
            w_pll: vf.add_const(1.0),
            phase_pll: vf.add_const(-np.pi/2-0.4),

        },
        diff_init_eqs={
            dx_e_pll: c0,
            d_theta_pll: c0,
            omega_pll: vf.add_const(1.0),
        },
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_A,
        VarPowerFlowReferenceType.v_B: v_B,
        VarPowerFlowReferenceType.v_C: v_C,
    }

    return templ

def get_virtual_admittance_GFL(vf: VarFactory, name: str = "G4L_Virtual_admittance") -> EmtModelTemplate:
    """
    Virtual admittance block
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    v_q = vf.add_var(name=f"v_q_{name}")
    v_d = vf.add_var(name=f"v_d_{name}")

    inputs = [v_q, v_d]

    v_q_ref = vf.add_var(name=f"v_q_ref_{name}")
    v_d_ref = vf.add_var(name=f"v_d_ref_{name}")

    # parameters virtual admittance
    Vac = vf.add_var(name=f"Vac_{name}")
    Lv = vf.add_var(name=f"Lv_{name}")
    Rv = vf.add_var(name=f"Rv_{name}")
    omega_ref = vf.add_var(name=f"omega_ref_{name}")

    U = 33000
    Sb = 2000000
    Vac_expr = U * np.sqrt(2 / 3)
    omega_ref_expr = 2 * np.pi * 50
    Zvirtual = 0.2
    R_L = 0.1
    Zbase = U * U / Sb
    Lv_expr = Zvirtual * Zbase / omega_ref_expr
    Rv_expr = Zvirtual * R_L * Zbase

    templ.block.event_dict[Vac] = Vac_expr
    templ.block.event_dict[Lv] = Lv_expr
    templ.block.event_dict[Rv] = Rv_expr
    templ.block.event_dict[omega_ref] = omega_ref_expr

    # outputs
    i_d_out_VA = vf.add_var(name=f"i_d_out_VA_{name}")
    i_q_out_VA = vf.add_var(name=f"i_q_out_VA_{name}")

    # errors
    err_q = vf.add_var(name=f"err_q_{name}")
    err_d =  vf.add_var(name=f"err_d_{name}")

    # transfer function outputs
    y1 = vf.add_var(name=f"y1_{name}")
    y2 = vf.add_var(name=f"y2_{name}")
    y3 = vf.add_var(name=f"y3_{name}")
    y4 = vf.add_var(name=f"y4_{name}")

    # transfer function states
    # TF 1
    x1_1 = vf.add_var(name=f"x1_1_{name}")
    x2_1 = vf.add_var(name=f"x2_1_{name}")
    dx1_1 = vf.add_diff_var(name=f"dx1_1_{name}", base_var=x1_1)
    dx2_1 = vf.add_diff_var(name=f"dx2_1_{name}", base_var=x2_1)
    # TF 2
    x1_2 = vf.add_var(name=f"x1_2_{name}")
    x2_2 = vf.add_var(name=f"x2_2_{name}")
    dx1_2 = vf.add_diff_var(name=f"dx1_2_{name}", base_var=x1_2)
    dx2_2 = vf.add_diff_var(name=f"dx2_2_{name}", base_var=x2_2)
    # TF 3
    x1_3 = vf.add_var(name=f"x1_3_{name}")
    x2_3 = vf.add_var(name=f"x2_3_{name}")
    dx1_3 = vf.add_diff_var(name=f"dx1_3_{name}", base_var=x1_3)
    dx2_3 = vf.add_diff_var(name=f"dx2_3_{name}", base_var=x2_3)
    # TF 4
    x1_4 = vf.add_var(name=f"x1_4_{name}")
    x2_4 = vf.add_var(name=f"x2_4_{name}")
    dx1_4 = vf.add_diff_var(name=f"dx1_4_{name}", base_var=x1_4)
    dx2_4 = vf.add_diff_var(name=f"dx2_4_{name}", base_var=x2_4)


    # denominator coefficients and numerator coefficients
    n1_0 = Lv
    n0_0 = Rv
    n0_1 = Lv * omega_ref
    d2 = Lv * Lv
    d1 = 2 * Lv * Rv
    d0 = Lv * Lv * omega_ref * omega_ref + Rv * Rv

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            # TF 1
            x2_1,
            (err_q - d1 * x2_1 - d0 * x1_1)/d2,
            # TF 2
            x2_2,
            (err_d - d1 * x2_2 - d0 * x1_2) / d2,
            # TF 3
            x2_3,
            (err_q - d1 * x2_3 - d0 * x1_3) / d2,
            # TF 4
            x2_4,
            (err_d - d1 * x2_4 - d0 * x1_4) / d2,
        ],
        state_vars=[x1_1, x2_1, x1_2, x2_2, x1_3, x2_3, x1_4, x2_4],
        diff_vars=[dx1_1, dx2_1, dx1_2, dx2_2, dx1_3, dx2_3, dx1_4, dx2_4],
        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            err_q - (v_q_ref-v_q),
            err_d - (v_d_ref - v_d),
            y1 - (n1_0 * x2_1 + n0_0 * x1_1),
            y2 - (n0_1 * x1_2),
            y3 - (n0_1 * x1_3),
            y4 - (n1_0 * x2_4 + n0_0 * x1_4),
            i_q_out_VA - (-y1 + y2),
            i_d_out_VA - (-y3 - y4),
        ],
        algebraic_vars=[err_q, err_d, y1, y2, y3, y4, i_q_out_VA, i_d_out_VA],
        in_vars=inputs,
        out_vars=[i_q_out_VA, i_d_out_VA],
        init_eqs={
            err_q: c0,
            err_d: c0,
            x1_1: err_q/d0,
            x1_2: err_d/d0,
            x1_3: err_q/d0,
            x1_4: err_d/d0,
            x2_1: c0,
            x2_2: c0,
            x2_3: c0,
            x2_4: c0,
            y1:n0_0*err_q/d0,
            y2: n0_1 * err_d / d0,
            y3: n0_1 * err_q / d0,
            y4: n0_0 * err_d / d0,
            i_q_out_VA: -y1 + y2,
            i_d_out_VA: -y3 - y4,
        },
        diff_init_eqs={
            dx1_1: x2_1,
            dx1_2: x2_2,
            dx1_3: x2_3,
            dx1_4: x2_4,
            dx2_1: (err_q - d1*x2_1 - d0*x1_1)/d2,
            dx2_2: (err_d - d1*x2_2 - d0*x1_2)/d2,
            dx2_3: (err_q - d1*x2_3 - d0*x1_3)/d2,
            dx2_4: (err_d - d1*x2_4 - d0*x1_4)/d2,
        }
    )

    return templ

def get_current_limiter_GFL(vf: VarFactory, name: str = "G4L_current_limiter") -> EmtModelTemplate:
    """
    Current limiter that priorizes i_d

    i_q current limitation:
    if Imax >= abs(i_q):
        i_q_lim = i_q # no limitation.
    else:
        if i_q>=0:
            i_q_lim = Imax
        else:
            i_q_lim = -Imax


    i_d current limitation:
    if np.sqrt(i_q*i_q + i_d*i_d) >= Imax:
        if i_d >=0:
            i_d_lim = np.sqrt(Imax*Imax-i_q_lim*i_q_lim)
        else:
            i_d_lim = - np.sqrt(Imax*Imax-i_q_lim*i_q_lim)
    else:
        i_d_lim = i_d

    """


    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    i_q = vf.add_var(name=f"i_q_{name}")
    i_d = vf.add_var(name=f"i_d_{name}")

    inputs = [i_q, i_d]

    # outputs
    i_d_lim = vf.add_var(name=f"i_d_lim_{name}")
    i_q_lim = vf.add_var(name=f"i_q_lim_{name}")
    i_q_lim_mode = vf.add_var(name=f"i_q_lim_mode_{name}")
    i_d_lim_mode = vf.add_var(name=f"i_d_lim_mode_{name}")

    # parameters current limiter
    Imax = vf.add_var(name=f"Imax_{name}")
    U = 33000
    Sb = 2000000
    Ipeak = (Sb / U) * np.sqrt(2 / 3)
    Imax_expr = 1.1 * Ipeak
    templ.block.event_dict[Imax] = vf.add_const(Imax_expr)

    # First compute the dq current magnitude after the q-axis limiter has been applied.
    # This decides whether the d-axis command must be projected back to the circular limit.
    i_mag_expr: Expr = sym.sqrt(i_q_lim * i_q_lim + i_d * i_d)
    inside_limit_expr: Expr = sym.heaviside(Imax - i_mag_expr)

    # Build the signed d-axis headroom that remains after the limited q-axis current is fixed.
    i_d_sign_expr: Expr = sym.heaviside(i_d) - sym.heaviside(-i_d)
    i_d_cap_expr: Expr = sym.sqrt(sym.max(Imax * Imax - i_q_lim * i_q_lim, c0))

    # Sample the full branch expression procedurally so the DAE only consumes one retained value.
    i_d_lim_expr: Expr = (i_d * inside_limit_expr
                          + i_d_cap_expr * sym.heaviside(sym.abs(i_d)) * i_d_sign_expr * (1 - inside_limit_expr))


    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[],
        state_vars=[],
        diff_vars=[],
        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            i_q_lim - i_q_lim_mode,
            i_d_lim - i_d_lim_mode,
        ],
        algebraic_vars=[i_q_lim, i_d_lim],
        in_vars=inputs,
        out_vars=[i_q_lim, i_d_lim],
        mode_dict={
            i_q_lim_mode: c0,
            i_d_lim_mode: c0,
        },
        init_eqs={
            i_q_lim: sym.hard_sat(i_q, -Imax, Imax),
            i_d_lim: i_d_lim_expr,
        },
        procedural_logic=[
            hard_saturation(
                output=i_q_lim_mode,
                u=i_q,
                u_min=-Imax,
                u_max=Imax,
                name=f"i_q_lim_sat_{name}",
            ),
            sampled_value(
                output=i_d_lim_mode,
                source=i_d_lim_expr,
                name=f"i_d_lim_sample_{name}",
            ),
        ],
    )

    return templ

def get_current_loop_GFL(vf: VarFactory, name: str = "G4L_current_loop") -> EmtModelTemplate:
    """
    Current controller + inverse clark park transforms
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    v_d = vf.add_var(name=f"v_d_{name}")
    v_q = vf.add_var(name=f"v_q_{name}")
    i_d = vf.add_var(name=f"i_d_{name}")
    i_q = vf.add_var(name=f"i_q_{name}")
    phase_pll = vf.add_var(name=f"phase_pll_{name}")
    omega_pll = vf.add_var(name=f"omega_pll_{name}")

    v_con_A = vf.add_var(name=f"v_con_A_{name}")
    v_con_B = vf.add_var(name=f"v_con_B_{name}")
    v_con_C = vf.add_var(name=f"v_con_C_{name}")

    v_con_q = vf.add_var(name=f"v_con_q_{name}")
    v_con_d = vf.add_var(name=f"v_con_d_{name}")

    i_d_lim = vf.add_var(name=f"i_d_lim_{name}")
    i_q_lim = vf.add_var(name=f"i_q_lim_{name}")

    inputs = [v_q, v_d, i_q, i_d, phase_pll, omega_pll, i_q_lim, i_d_lim]

    # feedforward vqd transfer function
    v_ffw_q = vf.add_var(name=f"v_ffw_q_{name}")
    v_ffw_d = vf.add_var(name=f"v_ffw_d_{name}")
    dv_ffw_q = vf.add_diff_var(name=f"dv_ffw_q_{name}", base_var=v_ffw_q)
    dv_ffw_d = vf.add_diff_var(name=f"dv_ffw_d_{name}", base_var=v_ffw_d)
    T_ffw = vf.add_var(name=f"T_ffw_{name}")
    templ.block.event_dict[T_ffw] = vf.add_const(0.0005)

    # PI current loop
    Kp_cc = vf.add_var(name=f"Kp_cc_{name}")
    Ki_cc = vf.add_var(name=f"Ki_cc_{name}")
    L_f = vf.add_var(name=f"L_f_{name}")

    tau_cc = 0.001
    omega_ref_expr = 2 * np.pi * 50
    U = 33000
    Sb = 2000000
    Zbase = U * U / Sb
    L_f_expr = Zbase / (10 * omega_ref_expr)
    R_f = (Zbase / 10) * 0.1
    Kp_cc_expr = L_f_expr / tau_cc
    Ki_cc_expr = R_f / tau_cc

    templ.block.event_dict[Kp_cc] = vf.add_const(Kp_cc_expr)
    templ.block.event_dict[Ki_cc] = vf.add_const(Ki_cc_expr)
    templ.block.event_dict[L_f] = vf.add_const(L_f_expr)
    # error
    err_q = vf.add_var(name=f"err_q_{name}")
    err_d = vf.add_var(name=f"err_d_{name}")
    # integral state of I (PI)
    x_e_q = vf.add_var(name=f"x_e_q_{name}")
    dx_e_q = vf.add_var(name=f"dx_e_q_{name}", base_var=x_e_q)
    x_e_d = vf.add_var(name=f"x_e_d_{name}")
    dx_e_d = vf.add_var(name=f"dx_e_d_{name}", base_var=x_e_d)
    # PI output
    y_q = vf.add_var(name=f"y_q_{name}")
    y_d = vf.add_var(name=f"y_d_{name}")

    # Clark transform
    alpha = vf.add_var(name=f"alpha_{name}")
    beta = vf.add_var(name=f"beta_{name}")

    templ.block = Block(
        # --------------------------------------------------------------------------------------
        # STATE EQUATIONS (seconds + pu)
        # --------------------------------------------------------------------------------------
        state_eqs=[
            # current controller
            (v_q - v_ffw_q) / T_ffw,
            (v_d - v_ffw_d) / T_ffw,
            Ki_cc * err_q,
            Ki_cc * err_d,
        ],
        state_vars=[v_ffw_q, v_ffw_d, x_e_q, x_e_d],
        diff_vars=[dv_ffw_q, dv_ffw_d, dx_e_q, dx_e_d],
        # --------------------------------------------------------------------------------------
        # ALGEBRAIC EQUATIONS
        # --------------------------------------------------------------------------------------
        algebraic_eqs=[
            # current controller
            err_q - (i_q_lim - i_q),
            err_d - (i_d_lim - i_d),
            y_q + (err_q * Kp_cc + x_e_q),
            y_d + (err_d * Kp_cc + x_e_d),
            v_con_q - (v_ffw_q - (omega_pll * L_f * i_d) + y_q),
            v_con_d -(v_ffw_d + (omega_pll * L_f * i_q) + y_d),
            # transform qd to abc
            alpha - (v_con_q * cos(phase_pll) + v_con_d * sin(phase_pll)),
            beta - (-v_con_q * sin(phase_pll) + v_con_d * cos(phase_pll)),
            v_con_A - 0.5 * (2 * alpha),
            v_con_B - 0.5 * (-alpha - np.sqrt(3) * beta),
            v_con_C - 0.5 * (-alpha + np.sqrt(3) * beta),

        ],
        algebraic_vars=[err_q, err_d, y_q, y_d, v_con_q, v_con_d, alpha, beta, v_con_A, v_con_B, v_con_C],
        in_vars=inputs,
        out_vars=[v_con_A, v_con_B, v_con_C],
        init_eqs={
            v_ffw_q: v_q,
            v_ffw_d: v_d,
            x_e_q: c0,
            x_e_d: c0,
            err_q: c0,
            err_d: c0,
            y_q: c0,
            y_d: c0,
            v_con_q: v_q,
            v_con_d: v_d,
            alpha: c0,
            beta: c0,
            v_con_A: c0,
            v_con_B: c0,
            v_con_C: c0,
        },
        diff_init_eqs={
            dv_ffw_q: c0,
            dv_ffw_d: c0,
            dx_e_q: c0,
            dx_e_d: c0,
        }
    )

    templ.block.external_mapping={
        VarPowerFlowReferenceType.v_A: v_con_A,
        VarPowerFlowReferenceType.v_B: v_con_B,
        VarPowerFlowReferenceType.v_C: v_con_C,
    }

    return templ



def get_complete_load_template_G4L(vf: VarFactory, name: str = "G4L_complete_load") -> EmtModelTemplate:
    """
    Complete GFL load composed by:
    - grid side converter
    - load side converter
    - grid side converter control:
        - clark park transforms
        - PLL + VSM
        - Virtual Admittance
        - Current Limitation
        - Current control
    - Load side converter control
    """

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    templ.block.name = name

    grid_side_vsc_mdl = get_grid_side_converter_GFL(vf=vf).block
    load_side_vsc_mdl = get_load_side_converter_GFL(vf=vf).block
    grid_side_ctrl_mdl = get_grid_side_converter_control_GFL(vf=vf).block
    load_side_ctrl_mdl = get_load_side_converter_control_GFL(vf=vf).block

    # IN VARS: v_A, v_B, v_C, Pac
    templ.block.in_vars = [grid_side_vsc_mdl.in_vars[0],  # v_A
                           grid_side_vsc_mdl.in_vars[1],  # v_B
                           grid_side_vsc_mdl.in_vars[2],  # v_C
                           ]

    # OUT VARS: i_A, i_B, i_C
    templ.block.out_vars = [grid_side_vsc_mdl.out_vars[0],  # i_A
                            grid_side_vsc_mdl.out_vars[1],  # i_B
                            grid_side_vsc_mdl.out_vars[2],  # i_C
                            ]

    # CONNECT VARIABLES BETWEEN CHILDREN
    # i dc vsc
    vf.add_connection(load_side_vsc_mdl.in_vars[0], grid_side_vsc_mdl.out_vars[3])
    # vdc
    vf.add_connection(grid_side_vsc_mdl.in_vars[3], load_side_vsc_mdl.out_vars[0])
    vf.add_connection(load_side_ctrl_mdl.in_vars[0], load_side_vsc_mdl.out_vars[0])
    # i_dc_L
    vf.add_connection(load_side_vsc_mdl.in_vars[1], load_side_ctrl_mdl.out_vars[0])
    # v_con_abc
    vf.add_connection(grid_side_vsc_mdl.in_vars[4], grid_side_ctrl_mdl.out_vars[0]) # v_con_A
    vf.add_connection(grid_side_vsc_mdl.in_vars[5], grid_side_ctrl_mdl.out_vars[1])  # v_con_B
    vf.add_connection(grid_side_vsc_mdl.in_vars[6], grid_side_ctrl_mdl.out_vars[2])  # v_con_C
    # i abc
    vf.add_connection(grid_side_ctrl_mdl.in_vars[3], grid_side_vsc_mdl.out_vars[0])  # i_A
    vf.add_connection(grid_side_ctrl_mdl.in_vars[4], grid_side_vsc_mdl.out_vars[1])  # i_B
    vf.add_connection(grid_side_ctrl_mdl.in_vars[5], grid_side_vsc_mdl.out_vars[2])  # i_C
    # Pac_bus
    vf.add_connection(grid_side_ctrl_mdl.in_vars[6], grid_side_vsc_mdl.out_vars[4])

    # APPEND CHILDREN
    templ.block.children.append(grid_side_vsc_mdl)
    templ.block.children.append(load_side_vsc_mdl)
    templ.block.children.append(grid_side_ctrl_mdl)
    templ.block.children.append(load_side_ctrl_mdl)

    # EXTERNAL MAPPING
    templ.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: grid_side_vsc_mdl.in_vars[0],
        VarPowerFlowReferenceType.v_B: grid_side_vsc_mdl.in_vars[1],
        VarPowerFlowReferenceType.v_C: grid_side_vsc_mdl.in_vars[2],
        VarPowerFlowReferenceType.i_A: grid_side_vsc_mdl.out_vars[0],
        VarPowerFlowReferenceType.i_B: grid_side_vsc_mdl.out_vars[1],
        VarPowerFlowReferenceType.i_C: grid_side_vsc_mdl.out_vars[2],
    }


    return templ
