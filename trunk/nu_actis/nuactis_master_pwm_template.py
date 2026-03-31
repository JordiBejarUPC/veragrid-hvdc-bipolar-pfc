# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro, sampled_value
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType

def get_masterpwm_model_emt_template(vf: VarFactory, name: str = 'MasterPWM_Model') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name

    # --- In vars ---
    Vm = vf.add_var("Vm_" + name)
    Va = vf.add_var("Va_" + name)
    uDC = vf.add_var("Vdc_" + name)

    # --- Parameters ---
    Current_Limiter_C = vf.add_var('Current_Limiter__C_' + name)
    Current_Limiter_V_fault = vf.add_var('Current_Limiter__V_fault_' + name)
    Inner_Control_Ki_d = vf.add_var('Inner_Control__Ki_d_' + name)
    Inner_Control_Ki_q = vf.add_var('Inner_Control__Ki_q_' + name)
    Inner_Control_Kp_d = vf.add_var('Inner_Control__Kp_d_' + name)
    Inner_Control_Kp_q = vf.add_var('Inner_Control__Kp_q_' + name)
    Inner_Control_U_dc_base = vf.add_var('Inner_Control__U_dc_base_' + name)
    Inner_Control_V_ac_base = vf.add_var('Inner_Control__V_ac_base_' + name)
    Inner_Control_wL = vf.add_var('Inner_Control__wL_' + name)
    Outer_Ctrl_P_Ki = vf.add_var('Outer_Ctrl_P__Ki_' + name)
    Outer_Ctrl_P_Kp = vf.add_var('Outer_Ctrl_P__Kp_' + name)
    Outer_Ctrl_P_P_ctrl_mode = vf.add_var('Outer_Ctrl_P__P_ctrl_mode_' + name)
    Outer_Ctrl_Q_K = vf.add_var('Outer_Ctrl_Q__K_' + name)
    Outer_Ctrl_Q_Ki = vf.add_var('Outer_Ctrl_Q__Ki_' + name)
    Outer_Ctrl_Q_Kp = vf.add_var('Outer_Ctrl_Q__Kp_' + name)
    Outer_Ctrl_Q_Q_ctrl_mode = vf.add_var('Outer_Ctrl_Q__Q_ctrl_mode_' + name)
    Outer_Ctrl_Q_U_fault = vf.add_var('Outer_Ctrl_Q__U_fault_' + name)

    # --- State Variables ---
    Inner_Control_xd = vf.add_var('Inner_Control__xd_' + name)
    Inner_Control_xq = vf.add_var('Inner_Control__xq_' + name)
    Outer_Ctrl_P_dx = vf.add_var('Outer_Ctrl_P__dx_' + name)
    Outer_Ctrl_Q_dx = vf.add_var('Outer_Ctrl_Q__dx_' + name)

    # --- Algebraic / Shared Variables ---
    C_id = vf.add_var('C_id_' + name)
    C_iq = vf.add_var('C_iq_' + name)
    Current_Limiter_U_sgnl = vf.add_var('Current_Limiter__U_sgnl_' + name)
    Current_Limiter_proc_picdro_0 = vf.add_var('Current_Limiter__proc_picdro_0_' + name)
    Current_Limiter_proc_select_1 = vf.add_var('Current_Limiter__proc_select_1_' + name)
    Current_Limiter_proc_select_2 = vf.add_var('Current_Limiter__proc_select_2_' + name)
    Current_Limiter_proc_select_3 = vf.add_var('Current_Limiter__proc_select_3_' + name)
    Current_Limiter_proc_select_4 = vf.add_var('Current_Limiter__proc_select_4_' + name)
    Current_Limiter_proc_select_5 = vf.add_var('Current_Limiter__proc_select_5_' + name)
    Outer_Ctrl_P_C = vf.add_var('Outer_Ctrl_P__C_' + name)
    Outer_Ctrl_P_proc_select_0 = vf.add_var('Outer_Ctrl_P__proc_select_0_' + name)
    Outer_Ctrl_Q_C = vf.add_var('Outer_Ctrl_Q__C_' + name)
    Outer_Ctrl_Q_proc_picdro_0 = vf.add_var('Outer_Ctrl_Q__proc_picdro_0_' + name)
    Outer_Ctrl_Q_proc_select_1 = vf.add_var('Outer_Ctrl_Q__proc_select_1_' + name)
    Outer_Ctrl_Q_proc_select_2 = vf.add_var('Outer_Ctrl_Q__proc_select_2_' + name)
    Outer_Ctrl_Q_proc_select_3 = vf.add_var('Outer_Ctrl_Q__proc_select_3_' + name)
    P_act = vf.add_var('P_act_' + name) #◙
    Pdc_ref = vf.add_var('Pdc_ref_' + name)
    Pmd = vf.add_var('Pmd_' + name)
    Pmq = vf.add_var('Pmq_' + name)
    Q_act = vf.add_var('Q_act_' + name)
    Q_ref = vf.add_var('Q_ref_' + name)
    Vac_ref = vf.add_var('Vac_ref_' + name)
    cosphi = vf.add_var('cosphi_' + name)
    i_mag_1 = vf.add_var('i_mag_1_' + name)
    i_mag_3 = vf.add_var('i_mag_3_' + name)
    id = vf.add_var('id_' + name)
    id_lim_cal = vf.add_var('id_lim_cal_' + name)
    id_limit = vf.add_var('id_limit_' + name)
    id_ref = vf.add_var('id_ref_' + name)
    id_ref_lmtd = vf.add_var('id_ref_lmtd_' + name)
    iq = vf.add_var('iq_' + name)
    iq_lim_cal = vf.add_var('iq_lim_cal_' + name)
    iq_limit = vf.add_var('iq_limit_' + name)
    iq_ref = vf.add_var('iq_ref_' + name)
    iq_ref_PI = vf.add_var('iq_ref_PI_' + name)
    iq_ref_lmtd = vf.add_var('iq_ref_lmtd_' + name)
    iq_ref_nonlimited = vf.add_var('iq_ref_nonlimited_' + name)
    min_lim = vf.add_var('min_lim_' + name)
    o1 = vf.add_var('o1_' + name)
    o10 = vf.add_var('o10_' + name)
    o11 = vf.add_var('o11_' + name)
    o12 = vf.add_var('o12_' + name)
    o13 = vf.add_var('o13_' + name)
    o14 = vf.add_var('o14_' + name)
    o15 = vf.add_var('o15_' + name)
    o1q = vf.add_var('o1q_' + name)
    o2 = vf.add_var('o2_' + name)
    o3 = vf.add_var('o3_' + name)
    o3q = vf.add_var('o3q_' + name)
    o4 = vf.add_var('o4_' + name)
    o4q = vf.add_var('o4q_' + name)
    o5 = vf.add_var('o5_' + name)
    o5q = vf.add_var('o5q_' + name)
    o6 = vf.add_var('o6_' + name)
    o7 = vf.add_var('o7_' + name)
    o8 = vf.add_var('o8_' + name)
    o9 = vf.add_var('o9_' + name)
    sinphi = vf.add_var('sinphi_' + name)
    u = vf.add_var('u_' + name)
    uDC_ref = vf.add_var('uDC_ref_' + name)
    u_fault = vf.add_var('u_fault_' + name)
    ui = vf.add_var('ui_' + name)
    ur = vf.add_var('ur_' + name)
    vd = vf.add_var('vd_' + name)
    vmd = vf.add_var('vmd_' + name)
    vmq = vf.add_var('vmq_' + name)
    vq = vf.add_var('vq_' + name)
    yi = vf.add_var('yi_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yi3 = vf.add_var('yi3_' + name)
    yiq = vf.add_var('yiq_' + name)

    # --- Derivative Variables ---
    d_Inner_Control_xd = vf.add_diff_var('d_Inner_Control__xd_' + name, base_var=Inner_Control_xd)
    d_Inner_Control_xq = vf.add_diff_var('d_Inner_Control__xq_' + name, base_var=Inner_Control_xq)
    d_Outer_Ctrl_P_dx = vf.add_diff_var('d_Outer_Ctrl_P__dx_' + name, base_var=Outer_Ctrl_P_dx)
    d_Outer_Ctrl_Q_dx = vf.add_diff_var('d_Outer_Ctrl_Q__dx_' + name, base_var=Outer_Ctrl_Q_dx)

    # --- Block Assembly ---
    Vxy_To_dqFrame_0 = Block(
        algebraic_eqs=[
            (vd - ((ur * cosphi) + (ui * sinphi))),
            (vq - ((ui * cosphi) - (ur * sinphi))),
        ],
        algebraic_vars=[vd, vq],
        in_vars=[ur, ui, cosphi, sinphi],
        out_vars=[vd, vq],
        name='Vxy_To_dqFrame'
    )
    # --- Initial Equations and Guesses ---
    Vxy_To_dqFrame_0.init_eqs = {
        vd: ((ur * cosphi) + (ui * sinphi)),
        vq: (((-ur) * sinphi) + (ui * cosphi)),
    }

    Outer_ctrl_P_1 = Block(
        state_eqs=[
            (Outer_Ctrl_P_Ki * yi),
        ],
        state_vars=[Outer_Ctrl_P_dx],
        algebraic_eqs=[
            (o3 - Outer_Ctrl_P_P_ctrl_mode),
            (id_ref - ((min_lim + ((((Outer_Ctrl_P_Kp * yi) + ((min_lim + ((Outer_Ctrl_P_dx - min_lim) * sym.heaviside((Outer_Ctrl_P_dx - min_lim)))) - ((Outer_Ctrl_P_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_dx - id_limit))))) - min_lim) * sym.heaviside((((Outer_Ctrl_P_Kp * yi) + ((min_lim + ((Outer_Ctrl_P_dx - min_lim) * sym.heaviside((Outer_Ctrl_P_dx - min_lim)))) - ((Outer_Ctrl_P_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_dx - id_limit))))) - min_lim)))) - ((((Outer_Ctrl_P_Kp * yi) + ((min_lim + ((Outer_Ctrl_P_dx - min_lim) * sym.heaviside((Outer_Ctrl_P_dx - min_lim)))) - ((Outer_Ctrl_P_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_dx - id_limit))))) - id_limit) * sym.heaviside((((Outer_Ctrl_P_Kp * yi) + ((min_lim + ((Outer_Ctrl_P_dx - min_lim) * sym.heaviside((Outer_Ctrl_P_dx - min_lim)))) - ((Outer_Ctrl_P_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_dx - id_limit))))) - id_limit))))),
            (min_lim - (-id_limit)),
            (C_id - id),
            (o5 - ((-P_act) + Pdc_ref)),
            (o4 - (uDC - uDC_ref)),
            (yi - ((Outer_Ctrl_P_proc_select_0 * o5) + ((sym.Const(1.0) - Outer_Ctrl_P_proc_select_0) * o4))),
        ],
        algebraic_vars=[o3, id_ref, min_lim, C_id, o5, o4, yi],
        in_vars=[id_limit, P_act, uDC, id],
        out_vars=[id_ref],
        name='Outer_ctrl_P'
    )
    Outer_ctrl_P_1.diff_vars = [d_Outer_Ctrl_P_dx]
    # --- Parameter Values ---
    Outer_ctrl_P_1.event_dict = {
        Outer_Ctrl_P_P_ctrl_mode: vf.add_const(None, name='P_ctrl_mode'),
        Outer_Ctrl_P_Kp: vf.add_const(None, name='Kp'),
        Outer_Ctrl_P_Ki: vf.add_const(None, name='Ki'),
        uDC_ref: uDC, # references are parameters of the controller
        Pdc_ref: P_act, # references are parameters of the controller
    }
    # --- Retained Runtime Modes ---
    Outer_ctrl_P_1.mode_dict = {
        Outer_Ctrl_P_proc_select_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    Outer_ctrl_P_1.init_eqs = {
        Outer_Ctrl_P_C: id,
        Outer_Ctrl_P_dx: C_id,
        id_ref: C_id,
        id_limit: vf.add_const(1.0, name=''),
        min_lim: (-id_limit),
        # Pdc_ref: P_act,
        # uDC_ref: uDC,
    }
    Outer_ctrl_P_1.procedural_logic = [
        sampled_value(output=Outer_Ctrl_P_proc_select_0, source=o3),
    ]

    Outer_ctrl_Q_2 = Block(
        state_eqs=[
            (Outer_Ctrl_Q_Ki * yi),
        ],
        state_vars=[Outer_Ctrl_Q_dx],
        algebraic_eqs=[
            (u_fault - Outer_Ctrl_Q_U_fault),
            (o1q - Outer_Ctrl_Q_proc_picdro_0),
            (o3q - Outer_Ctrl_Q_U_fault),
            (o4q - (yiq * Outer_Ctrl_Q_K)),
            (yiq - ((-o3q) + u)),
            (o5q - (o4q + iq_ref_PI)),
            (iq_ref_nonlimited - ((Outer_Ctrl_Q_proc_select_2 * o5q) + ((sym.Const(1.0) - Outer_Ctrl_Q_proc_select_2) * iq_ref_PI))),
            (iq_ref_PI - ((min_lim + ((((Outer_Ctrl_Q_Kp * yi) + (((min_lim - (Outer_Ctrl_Q_Kp * yi)) + ((Outer_Ctrl_Q_dx - (min_lim - (Outer_Ctrl_Q_Kp * yi))) * sym.heaviside((Outer_Ctrl_Q_dx - (min_lim - (Outer_Ctrl_Q_Kp * yi)))))) - ((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi))) * sym.heaviside((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi))))))) - min_lim) * sym.heaviside((((Outer_Ctrl_Q_Kp * yi) + (((min_lim - (Outer_Ctrl_Q_Kp * yi)) + ((Outer_Ctrl_Q_dx - (min_lim - (Outer_Ctrl_Q_Kp * yi))) * sym.heaviside((Outer_Ctrl_Q_dx - (min_lim - (Outer_Ctrl_Q_Kp * yi)))))) - ((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi))) * sym.heaviside((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi))))))) - min_lim)))) - ((((Outer_Ctrl_Q_Kp * yi) + (((min_lim - (Outer_Ctrl_Q_Kp * yi)) + ((Outer_Ctrl_Q_dx - (min_lim - (Outer_Ctrl_Q_Kp * yi))) * sym.heaviside((Outer_Ctrl_Q_dx - (min_lim - (Outer_Ctrl_Q_Kp * yi)))))) - ((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi))) * sym.heaviside((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi))))))) - iq_limit) * sym.heaviside((((Outer_Ctrl_Q_Kp * yi) + (((min_lim - (Outer_Ctrl_Q_Kp * yi)) + ((Outer_Ctrl_Q_dx - (min_lim - (Outer_Ctrl_Q_Kp * yi))) * sym.heaviside((Outer_Ctrl_Q_dx - (min_lim - (Outer_Ctrl_Q_Kp * yi)))))) - ((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi))) * sym.heaviside((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi))))))) - iq_limit))))),
            (min_lim - (-iq_limit)),
            (o3 - Outer_Ctrl_Q_Q_ctrl_mode),
            (C_iq - iq),
            (o2 - (u - Vac_ref)),
            (o5 - (Q_act - Q_ref)),
            (yi - ((Outer_Ctrl_Q_proc_select_3 * o5) + ((sym.Const(1.0) - Outer_Ctrl_Q_proc_select_3) * o2))),
        ],
        algebraic_vars=[u_fault, o1q, o3q, o4q, yiq, o5q, iq_ref_nonlimited, iq_ref_PI, min_lim, o3, C_iq, o2, o5, yi],
        in_vars=[iq, Q_act, u, iq_limit],
        out_vars=[iq_ref],
        name='Outer_ctrl_Q'
    )
    Outer_ctrl_Q_2.diff_vars = [d_Outer_Ctrl_Q_dx]
    # --- Parameter Values ---
    Outer_ctrl_Q_2.event_dict = {
        Outer_Ctrl_Q_U_fault: vf.add_const(value = 0.0, name='U_fault'),
        Outer_Ctrl_Q_K: vf.add_const(value = 0.0, name='K'),
        Outer_Ctrl_Q_Q_ctrl_mode: vf.add_const(None, name='Q_ctrl_mode'),
        Outer_Ctrl_Q_Kp: vf.add_const(value = 0.1, name='Kp'),
        Outer_Ctrl_Q_Ki: vf.add_const(value = 10.0, name='Ki'),
        Q_ref: Q_act, # references are parameters of the controller
        Vac_ref: u, # references are parameters of the controller
    }
    # --- Retained Runtime Modes ---
    Outer_ctrl_Q_2.mode_dict = {
        Outer_Ctrl_Q_proc_picdro_0: vf.add_const(0.0, name=''),
        Outer_Ctrl_Q_proc_select_1: vf.add_const(0.0, name=''),
        Outer_Ctrl_Q_proc_select_2: vf.add_const(0.0, name=''),
        Outer_Ctrl_Q_proc_select_3: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    Outer_ctrl_Q_2.init_eqs = {
        o1q: ((Outer_Ctrl_Q_proc_select_1 * sym.Const(1.0)) + ((sym.Const(1.0) - Outer_Ctrl_Q_proc_select_1) * sym.Const(0.0))),
        Outer_Ctrl_Q_C: iq,
        Outer_Ctrl_Q_dx: C_iq,
        iq_ref: C_iq,
        iq_limit: vf.add_const(1.0, name=''),
        min_lim: (-iq_limit),
        # Q_ref: Q_act,
        # Vac_ref: u,
    }
    Outer_ctrl_Q_2.procedural_logic = [
        picdro((u < u_fault), 0.0, 0.0, output=Outer_Ctrl_Q_proc_picdro_0),
        sampled_value(output=Outer_Ctrl_Q_proc_select_1, source=(u < u_fault)),
        sampled_value(output=Outer_Ctrl_Q_proc_select_2, source=o1q),
        sampled_value(output=Outer_Ctrl_Q_proc_select_3, source=o3),
    ]

    Current_Limiter_3 = Block(
        algebraic_eqs=[
            (o10 - ((sym.sqrt(((((i_mag_1 * i_mag_1) - (o2 * o2)) * sym.heaviside((((i_mag_1 * i_mag_1) - (o2 * o2)) - sym.Const(0.0)))) + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((i_mag_1 * i_mag_1) - (o2 * o2)) - sym.Const(0.0))))))) * sym.heaviside((sym.Const(0.3) - sym.sqrt(((((i_mag_1 * i_mag_1) - (o2 * o2)) * sym.heaviside((((i_mag_1 * i_mag_1) - (o2 * o2)) - sym.Const(0.0)))) + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((i_mag_1 * i_mag_1) - (o2 * o2)) - sym.Const(0.0)))))))))) + (sym.Const(0.3) * (sym.Const(1) - sym.heaviside((sym.Const(0.3) - sym.sqrt(((((i_mag_1 * i_mag_1) - (o2 * o2)) * sym.heaviside((((i_mag_1 * i_mag_1) - (o2 * o2)) - sym.Const(0.0)))) + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((i_mag_1 * i_mag_1) - (o2 * o2)) - sym.Const(0.0))))))))))))),
            (o4 - iq_ref),
            (o11 - sym.sqrt(((((i_mag_3 * i_mag_3) - (o5 * o5)) * sym.heaviside((((i_mag_3 * i_mag_3) - (o5 * o5)) - sym.Const(0.0)))) + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((i_mag_3 * i_mag_3) - (o5 * o5)) - sym.Const(0.0)))))))),
            (o3 - id_ref),
            (o1 - Current_Limiter_proc_picdro_0),
            (o13 - Current_Limiter_C),
            (o14 - sym.Const(1.0)),
            (id_lim_cal - o11),
            (id_ref_lmtd - ((Current_Limiter_proc_select_2 * o3) + ((sym.Const(1.0) - Current_Limiter_proc_select_2) * o2))),
            (iq_ref_lmtd - ((Current_Limiter_proc_select_3 * o5) + ((sym.Const(1.0) - Current_Limiter_proc_select_3) * o4))),
            (id_limit - ((Current_Limiter_proc_select_4 * o12) + ((sym.Const(1.0) - Current_Limiter_proc_select_4) * o13))),
            (iq_limit - ((Current_Limiter_proc_select_5 * o14) + ((sym.Const(1.0) - Current_Limiter_proc_select_5) * o15))),
            (Current_Limiter_U_sgnl - o1),
            (o6 - Current_Limiter_U_sgnl),
            (o7 - Current_Limiter_U_sgnl),
            (o8 - Current_Limiter_U_sgnl),
            (o9 - Current_Limiter_U_sgnl),
            (o12 - id_lim_cal),
            (iq_lim_cal - o10),
            (o15 - iq_lim_cal),
        ],
        algebraic_vars=[o10, o4, o11, o3, o1, o13, o14, id_lim_cal, id_ref_lmtd, iq_ref_lmtd, id_limit, iq_limit, Current_Limiter_U_sgnl, o6, o7, o8, o9, o12, iq_lim_cal, o15],
        in_vars=[id_ref, u, iq_ref],
        out_vars=[id_limit, id_ref_lmtd, iq_ref_lmtd, iq_limit],
        name='Current_Limiter'
    )
    # --- Parameter Values ---
    Current_Limiter_3.event_dict = {
        Current_Limiter_V_fault: vf.add_const(None, name='V_fault'),
        Current_Limiter_C: vf.add_const(None, name='C'),
    }
    # --- Retained Runtime Modes ---
    Current_Limiter_3.mode_dict = {
        Current_Limiter_proc_picdro_0: vf.add_const(0.0, name=''),
        Current_Limiter_proc_select_1: vf.add_const(0.0, name=''),
        Current_Limiter_proc_select_2: vf.add_const(0.0, name=''),
        Current_Limiter_proc_select_3: vf.add_const(0.0, name=''),
        Current_Limiter_proc_select_4: vf.add_const(0.0, name=''),
        Current_Limiter_proc_select_5: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    Current_Limiter_3.init_eqs = {
        o1: ((Current_Limiter_proc_select_1 * sym.Const(1.0)) + ((sym.Const(1.0) - Current_Limiter_proc_select_1) * sym.Const(0.0))),
        id_ref_lmtd: id_ref,
        iq_ref_lmtd: iq_ref,
        id_limit: Current_Limiter_C,
        iq_limit: iq_lim_cal,
    }
    Current_Limiter_3.procedural_logic = [
        picdro((u < Current_Limiter_V_fault), 0.0, 0.0, output=Current_Limiter_proc_picdro_0),
        sampled_value(output=Current_Limiter_proc_select_1, source=(u < Current_Limiter_V_fault)),
        sampled_value(output=Current_Limiter_proc_select_2, source=o7),
        sampled_value(output=Current_Limiter_proc_select_3, source=o8),
        sampled_value(output=Current_Limiter_proc_select_4, source=o6),
        sampled_value(output=Current_Limiter_proc_select_5, source=o9),
    ]

    Inner_ctrl_Current_4 = Block(
        state_eqs=[
            (Inner_Control_Ki_d * yi1),
            (Inner_Control_Ki_q * yi),
        ],
        state_vars=[Inner_Control_xd, Inner_Control_xq],
        algebraic_eqs=[
            (o5 - ((Inner_Control_Kp_d * yi1) + Inner_Control_xd)),
            (o6 - ((Inner_Control_Kp_q * yi) + Inner_Control_xq)),
            (Pmd - (((((yi2 * Inner_Control_V_ac_base) / Inner_Control_U_dc_base) * sym.Const(2.0)) * sym.sqrt(sym.Const(2.0))) / sym.sqrt(sym.Const(3.0)))),
            (Pmq - (((((yi3 * Inner_Control_V_ac_base) / Inner_Control_U_dc_base) * sym.Const(2.0)) * sym.sqrt(sym.Const(2.0))) / sym.sqrt(sym.Const(3.0)))),
            (o10 - (id * Inner_Control_wL)),
            (o9 - (iq * Inner_Control_wL)),
            (yi2 - (vmd / uDC)),
            (yi3 - (vmq / uDC)),
            (yi1 - (id_ref_lmtd - id)),
            (yi - (iq_ref_lmtd - iq)),
            (vmd - ((o5 - o9) + vd)),
            (vmq - ((o6 + vq) + o10)),
        ],
        algebraic_vars=[o5, o6, Pmd, Pmq, o10, o9, yi2, yi3, yi1, yi, vmd, vmq],
        in_vars=[vd, id_ref_lmtd, id, iq, iq_ref_lmtd, vq, uDC],
        out_vars=[Pmd, Pmq],
        name='Inner_ctrl_Current'
    )
    Inner_ctrl_Current_4.diff_vars = [d_Inner_Control_xd, d_Inner_Control_xq]
    # --- Parameter Values ---
    Inner_ctrl_Current_4.event_dict = {
        Inner_Control_Kp_d: vf.add_const(None, name='Kp_d'),
        Inner_Control_Ki_d: vf.add_const(None, name='Ki_d'),
        Inner_Control_wL: vf.add_const(None, name='wL'),
        Inner_Control_Kp_q: vf.add_const(None, name='Kp_q'),
        Inner_Control_Ki_q: vf.add_const(None, name='Ki_q'),
        Inner_Control_V_ac_base: vf.add_const(None, name='V_ac_base'),
        Inner_Control_U_dc_base: vf.add_const(None, name='U_dc_base'),
    }
    # --- Initial Equations and Guesses ---
    Inner_ctrl_Current_4.init_eqs = {
        Inner_Control_xd: (((-vd) + vmd) + (Inner_Control_wL * iq)),
        Inner_Control_xq: (((-vq) + vmq) - (Inner_Control_wL * id)),
        vmd: ((((Pmd * uDC) * Inner_Control_U_dc_base) * sym.sqrt(sym.Const(3.0))) / ((sym.Const(2.0) * sym.sqrt(sym.Const(2.0))) * Inner_Control_V_ac_base)),
        vmq: ((((Pmq * uDC) * Inner_Control_U_dc_base) * sym.sqrt(sym.Const(3.0))) / ((sym.Const(2.0) * sym.sqrt(sym.Const(2.0))) * Inner_Control_V_ac_base)),
        id_ref_lmtd: id,
        iq_ref_lmtd: iq,
    }

    # --------------------------------------
    # MAIN BLOCK
    # --------------------------------------

    templ.block = Block(
        children=[Vxy_To_dqFrame_0, Outer_ctrl_P_1, Outer_ctrl_Q_2, Current_Limiter_3, Inner_ctrl_Current_4],
        algebraic_vars=[u, ur, ui, cosphi, sinphi, id, iq],
        algebraic_eqs=[
            # Voltage -> u: phasor, ur: real part, ui: imaginary part
            u - Vm * sym.exp(1j * Va),
            ur - sym.real(u),
            ui - sym.imag(u),
            # PLL -> cosphi : cos(Va), sinphi: sin(Va)
            cosphi - sym.cos(Va),
            sinphi - sym.sin(Va),
            # Actual power of the grid -> P_act: , Q_act:
            # P_act - ,
            # Q_act - ,

        ],
        in_vars = [Vm, Va, uDC, # from the buses variables
                   ],
        # in_vars=[ P_act, uDC, id, iq, Q_act, u],
        out_vars=[Pmd, Pmq],
        name='MasterPWM_Model'
    )
    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Vm: Vm,
        VarPowerFlowRefferenceType.Va: Va,
    }

    # delta: sym.imag(
    #     sym.log((inputs[0] * sym.exp(1j * inputs[1]) + (R1 + 1j * X1) * (
    #         sym.conj((P_g + 1j * Q_g) / (inputs[0] * sym.exp(1j * inputs[1]))))) / (
    #                 sym.abs(inputs[0] * sym.exp(1j * inputs[1]) + (R1 + 1j * X1) * (
    #                     sym.conj((P_g + 1j * Q_g) / (inputs[0] * sym.exp(1j * inputs[1])))))))),
    # omega: omega_ref,
    # v_d: sym.real((inputs[0] * sym.exp(1j * inputs[1])) * sym.exp(-1j * (delta - np.pi / 2))),
    # v_q: sym.imag((inputs[0] * sym.exp(1j * inputs[1])) * sym.exp(-1j * (delta - np.pi / 2))),


    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_masterpwm_model_emt_template(vf=vf, name='MasterPWM_Model' if name is None else name)
