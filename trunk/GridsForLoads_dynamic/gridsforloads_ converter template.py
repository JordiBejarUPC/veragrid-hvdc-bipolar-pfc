# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from codecs import xmlcharrefreplace_errors

import numpy as np
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block, Const
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, DeviceType, ParamPowerFlowReferenceType

def get_trafo_grid_connection_G4L(vf: VarFactory, name: str = "G4L_transformer") -> EmtModelTemplate:

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
    templ.block.event_dict[R_Cf_A] = Const(0.05)
    templ.block.event_dict[R_Cf_B] = Const(0.05)
    templ.block.event_dict[R_Cf_C] = Const(0.05)

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

    # shunt currents, C charge and derivative
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
            q_t_A - Caa * v_t_A,
            q_t_B - Cbb * v_t_B,
            q_t_C - Ccc * v_t_C,
            i_f_A - i_ser_A,
            i_f_B - i_ser_B,
            i_f_C - i_ser_C,
            i_t_A - (-i_ser_A + i_cap_t_A + v_t_A / R_Cf_A),
            i_t_B - (-i_ser_B + i_cap_t_B + v_t_B / R_Cf_B),
            i_t_C - (-i_ser_C + i_cap_t_C + v_t_C / R_Cf_C),
            Pac - (v_t_A*i_t_A + v_t_B*i_t_B + v_t_C*i_t_C),
            Qac - (1 / np.sqrt(3)) * ((v_t_A - v_t_B) * i_t_C +
                                     (v_t_B - v_t_C) * i_t_A +
                                     (v_t_C - v_t_A) * i_t_B),
        ],
        algebraic_vars=[i_cap_t_A, i_cap_t_B, i_cap_t_C, i_f_A, i_f_B, i_f_C, i_t_A, i_t_B, i_t_C, Pac, Qac],
        in_vars=inputs,
        out_vars=[i_f_A, i_f_B, i_f_C, i_t_A, i_t_B, i_t_C, Pac],
        init_eqs={
            i_ser_A: i_f_A,
            i_ser_B: i_f_B,
            i_ser_C: i_f_C,
            q_t_A: Caa * v_t_A,
            q_t_B: Cbb * v_t_B,
            q_t_C: Ccc * v_t_C,
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
    }

    return templ


def get_grid_side_converter_GFL(vf: VarFactory, name: str = "G4L_grid_side_converter") -> EmtModelTemplate:
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

    templ.block.parameters[Raa] = c0
    templ.block.parameters[Rbb] = c0
    templ.block.parameters[Rcc] = c0
    templ.block.parameters[Linv_aa] = c0
    templ.block.parameters[Linv_bb] = c0
    templ.block.parameters[Linv_cc] = c0


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
            Pac - (v_con_A * i_A + v_con_B * i_B + v_con_B * i_C),
            i_dc * v_dc - Pac, #without delay!
        ],
        algebraic_vars=[i_A, i_B, i_C, Pac, i_dc],
        in_vars=inputs,
        out_vars=[i_A, i_B, i_C, i_dc],
        init_eqs={
            i_ser_A: i_A,
            i_ser_B: i_B,
            i_ser_C: i_C,
            Pac: v_con_A * i_A + v_con_B * i_B + v_con_B * i_C,
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
    }

    return templ

def get_load_side_converter_GFL(vf: VarFactory, name: str = "G4L_load_side_converter") -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.LoadDevice
    templ.name = name

    templ.block.name = name

    c0 = vf.add_const(0.0)

    # Reuse the standard EMT branch parameter API slots so the model can be
    # initialized through VeraGrid's existing static-parameter mapping.

    Cdc = vf.add_var(name=f"Cdc_{name}")


    templ.block.event_dict[Cdc] = vf.add_const(max(0.05, 1e-9))

    # DC connection voltages
    v_dc = vf.add_var(name=f"v_dc_{name}", reference=VarPowerFlowReferenceType.Vdc)

    # DC load current
    i_dc_L = vf.add_var(name=f"i_dc_L_{name}")

    inputs = [v_dc, i_dc_L]

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
        ],
        algebraic_vars=[i_cap_dc, i_dc],
        in_vars=inputs,
        out_vars=[i_dc],
        init_eqs={
            q_cap: Cdc * v_dc,
            i_cap_dc: c0,
        },
        diff_init_eqs={
            dq_cap:i_cap_dc,
        },
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.Idc: i_dc,
    }

    return templ

def get_grid_side_converter_control_GFL(vf: VarFactory, name: str = "G4L_grid_side_converter_control") -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name



    return templ

def get_load_side_converter_control_GFL(vf: VarFactory, name: str = "G4L_load_side_converter_control") -> EmtModelTemplate:
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
    # integral state of I
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
            err- (v_dc_ref*v_dc_ref - v_dc*v_dc),
            p_dc -(Kp_E*err + x_e), # PI output
            i_dc_L*v_dc - p_dc, # load control output WITHOUT DELAY!

        ],
        algebraic_vars=[err, p_dc, i_dc_L],
        in_vars=inputs,
        out_vars=[],
        init_eqs={
            i_dc_L: i_dc,
            p_dc: i_dc_L*v_dc,
            err: c0,
            x_e: c0,
        },
        diff_init_eqs={
            dx_e: err,
        },
    )

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vdc: v_dc,
        VarPowerFlowReferenceType.Idc: i_dc,
    }

    return templ

def complete_load_template_G4L(vf: VarFactory, name: str = "G4L_complete_load") -> EmtModelTemplate:

    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    templ.block.name = name

    return templ