# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro, sampled_value
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Templates.Rms.vsc_gfl import pll_transform_rms
from trunk.nu_actis.nuactis_modulator_template import get_nuactis_modulator_rms_template

def get_masterpwm_model_emt_template(vf: VarFactory, name: str = 'MasterPWM_Model', bindings: dict | None = None) -> RmsModelTemplate:
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.VscDevice
    templ.name = name

    # --- In vars ---
    bindings = {} if bindings is None else bindings
    Vmf = bindings.get("Vmf", vf.add_var("Vmf_" + name, VarPowerFlowRefferenceType.Vmf))
    Vaf = bindings.get("Vaf", vf.add_var("Vaf_" + name, VarPowerFlowRefferenceType.Vaf))
    Vmt = bindings.get("Vmt", vf.add_var("Vmt_" + name, VarPowerFlowRefferenceType.Vmt))
    Vat = bindings.get("Vat", vf.add_var("Vat_" + name, VarPowerFlowRefferenceType.Vat))
    uDC = bindings.get("uDC", vf.add_var("Vdc_" + name)) # from the DC bus

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
    id = bindings.get("id", vf.add_var('id_' + name))
    id_lim_cal = vf.add_var('id_lim_cal_' + name)
    id_limit = vf.add_var('id_limit_' + name)
    id_ref = vf.add_var('id_ref_' + name)
    id_ref_lmtd = vf.add_var('id_ref_lmtd_' + name)
    iq = bindings.get("iq", vf.add_var('iq_' + name))
    iq_lim_cal = vf.add_var('iq_lim_cal_' + name)
    iq_limit = vf.add_var('iq_limit_' + name)
    iq_ref = vf.add_var('iq_ref_' + name)
    iq_ref_PI = vf.add_var('iq_ref_PI_' + name)
    iq_ref_lmtd = vf.add_var('iq_ref_lmtd_' + name)
    iq_ref_nonlimited = vf.add_var('iq_ref_nonlimited_' + name)
    min_lim_p = vf.add_var('min_lim_p_' + name)
    min_lim_q = vf.add_var('min_lim_q_' + name)
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
    o3_q = vf.add_var('o3_q_' + name)
    o5_q = vf.add_var('o5_q_' + name)
    yi_q = vf.add_var('yi_q_' + name)
    o10_lim = vf.add_var('o10_lim_' + name)
    o3_lim = vf.add_var('o3_lim_' + name)
    o4_lim = vf.add_var('o4_lim_' + name)
    o6_lim = vf.add_var('o6_lim_' + name)
    o9_lim = vf.add_var('o9_lim_' + name)
    o10_i = vf.add_var('o10_i_' + name)
    o9_i = vf.add_var('o9_i_' + name)
    o5_i = vf.add_var('o5_i_' + name)
    o6_i = vf.add_var('o6_i_' + name)
    yi_i = vf.add_var('yi_i_' + name)
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
            (vd - ((ui * cosphi) - (ur * sinphi))),
            (vq - ((ur * cosphi) + (ui * sinphi))),
        ],
        algebraic_vars=[vd, vq],
        in_vars=[ur, ui, cosphi, sinphi],
        out_vars=[vd, vq],
        name='Vxy_To_dqFrame'
    )
    # --- Initial Equations and Guesses ---
    Vxy_To_dqFrame_0.init_eqs = {
        vd: (((-ur) * sinphi) + (ui * cosphi)),
        vq: ((ur * cosphi) + (ui * sinphi)),
    }

    Outer_ctrl_P_1 = Block(
        state_eqs=[
            (Outer_Ctrl_P_Ki * yi),
        ],
        state_vars=[Outer_Ctrl_P_dx],
        algebraic_eqs=[
            (o3 - Outer_Ctrl_P_P_ctrl_mode),
            (id_ref - ((min_lim_p + ((((Outer_Ctrl_P_Kp * yi) + ((min_lim_p + ((Outer_Ctrl_P_dx - min_lim_p) * sym.heaviside((Outer_Ctrl_P_dx - min_lim_p)))) - ((Outer_Ctrl_P_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_dx - id_limit))))) - min_lim_p) * sym.heaviside((((Outer_Ctrl_P_Kp * yi) + ((min_lim_p + ((Outer_Ctrl_P_dx - min_lim_p) * sym.heaviside((Outer_Ctrl_P_dx - min_lim_p)))) - ((Outer_Ctrl_P_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_dx - id_limit))))) - min_lim_p)))) - ((((Outer_Ctrl_P_Kp * yi) + ((min_lim_p + ((Outer_Ctrl_P_dx - min_lim_p) * sym.heaviside((Outer_Ctrl_P_dx - min_lim_p)))) - ((Outer_Ctrl_P_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_dx - id_limit))))) - id_limit) * sym.heaviside((((Outer_Ctrl_P_Kp * yi) + ((min_lim_p + ((Outer_Ctrl_P_dx - min_lim_p) * sym.heaviside((Outer_Ctrl_P_dx - min_lim_p)))) - ((Outer_Ctrl_P_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_dx - id_limit))))) - id_limit))))),
            (min_lim_p - (-id_limit)),
            (C_id - (-id)),
            (o5 - ((-P_act) + Pdc_ref)),
            (o4 - (uDC - uDC_ref)),
            (yi - ((Outer_Ctrl_P_proc_select_0 * o5) + ((sym.Const(1.0) - Outer_Ctrl_P_proc_select_0) * o4))),
        ],
        algebraic_vars=[o3, id_ref, min_lim_p, C_id, o5, o4, yi],
        in_vars=[id_limit, P_act, uDC, id],
        out_vars=[id_ref],
        name='Outer_ctrl_P'
    )
    Outer_ctrl_P_1.diff_vars = [d_Outer_Ctrl_P_dx]
    # --- Parameter Values ---
    Outer_ctrl_P_1.event_dict = {
        Outer_Ctrl_P_P_ctrl_mode: vf.add_const(value = 0.0, name='P_ctrl_mode'),
        Outer_Ctrl_P_Kp: vf.add_const(value = 0.4, name='Kp'),
        Outer_Ctrl_P_Ki: vf.add_const(value = 8.0, name='Ki'),
        uDC_ref: uDC, # references are parameters of the controller
        Pdc_ref: P_act, # references are parameters of the controller
    }
    # --- Retained Runtime Modes ---
    Outer_ctrl_P_1.mode_dict = {
        Outer_Ctrl_P_proc_select_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    Outer_ctrl_P_1.init_eqs = {
        C_id: (-id),
        Outer_Ctrl_P_dx: C_id,
        id_ref: C_id,
        id_limit: vf.add_const(1.0, name=''),
        min_lim_p: (-id_limit),
        o5: ((-P_act) + Pdc_ref),
        o4: (uDC - uDC_ref),
        yi: ((Outer_Ctrl_P_proc_select_0 * o5) + ((sym.Const(1.0) - Outer_Ctrl_P_proc_select_0) * o4)),
        Pdc_ref: P_act,
        uDC_ref: uDC,
    }
    Outer_ctrl_P_1.procedural_logic = [
        sampled_value(output=Outer_Ctrl_P_proc_select_0, source=o3),
    ]

    Outer_ctrl_Q_2 = Block(
        state_eqs=[
            (Outer_Ctrl_Q_Ki * yi_q),
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
            (iq_ref - iq_ref_nonlimited),
            (iq_ref_PI - ((min_lim_q + ((((Outer_Ctrl_Q_Kp * yi_q) + (((min_lim_q - (Outer_Ctrl_Q_Kp * yi_q)) + ((Outer_Ctrl_Q_dx - (min_lim_q - (Outer_Ctrl_Q_Kp * yi_q))) * sym.heaviside((Outer_Ctrl_Q_dx - (min_lim_q - (Outer_Ctrl_Q_Kp * yi_q)))))) - ((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi_q))) * sym.heaviside((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi_q))))))) - min_lim_q) * sym.heaviside((((Outer_Ctrl_Q_Kp * yi_q) + (((min_lim_q - (Outer_Ctrl_Q_Kp * yi_q)) + ((Outer_Ctrl_Q_dx - (min_lim_q - (Outer_Ctrl_Q_Kp * yi_q))) * sym.heaviside((Outer_Ctrl_Q_dx - (min_lim_q - (Outer_Ctrl_Q_Kp * yi_q)))))) - ((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi_q))) * sym.heaviside((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi_q))))))) - min_lim_q)))) - ((((Outer_Ctrl_Q_Kp * yi_q) + (((min_lim_q - (Outer_Ctrl_Q_Kp * yi_q)) + ((Outer_Ctrl_Q_dx - (min_lim_q - (Outer_Ctrl_Q_Kp * yi_q))) * sym.heaviside((Outer_Ctrl_Q_dx - (min_lim_q - (Outer_Ctrl_Q_Kp * yi_q)))))) - ((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi_q))) * sym.heaviside((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi_q))))))) - iq_limit) * sym.heaviside((((Outer_Ctrl_Q_Kp * yi_q) + (((min_lim_q - (Outer_Ctrl_Q_Kp * yi_q)) + ((Outer_Ctrl_Q_dx - (min_lim_q - (Outer_Ctrl_Q_Kp * yi_q))) * sym.heaviside((Outer_Ctrl_Q_dx - (min_lim_q - (Outer_Ctrl_Q_Kp * yi_q)))))) - ((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi_q))) * sym.heaviside((Outer_Ctrl_Q_dx - (iq_limit - (Outer_Ctrl_Q_Kp * yi_q))))))) - iq_limit))))),
            (min_lim_q - (-iq_limit)),
            (o3_q - Outer_Ctrl_Q_Q_ctrl_mode),
            (C_iq - iq),
            (o2 - (u - Vac_ref)),
            (o5_q - (Q_act - Q_ref)),
            (yi_q - ((Outer_Ctrl_Q_proc_select_3 * o5_q) + ((sym.Const(1.0) - Outer_Ctrl_Q_proc_select_3) * o2))),
        ],
        algebraic_vars=[u_fault, o1q, o3q, o4q, yiq, o5q, iq_ref_nonlimited, iq_ref, iq_ref_PI, min_lim_q, o3_q, C_iq, o2, o5_q, yi_q],
        in_vars=[iq, Q_act, u, iq_limit],
        out_vars=[iq_ref],
        name='Outer_ctrl_Q'
    )
    Outer_ctrl_Q_2.diff_vars = [d_Outer_Ctrl_Q_dx]
    # --- Parameter Values ---
    Outer_ctrl_Q_2.event_dict = {
        Outer_Ctrl_Q_U_fault: vf.add_const(value = 0.0, name='U_fault'),
        Outer_Ctrl_Q_K: vf.add_const(value = 0.0, name='K'),
        Outer_Ctrl_Q_Q_ctrl_mode: vf.add_const(value=0.0, name='Q_ctrl_mode'),
        Outer_Ctrl_Q_Kp: vf.add_const(value = 0.05, name='Kp'),
        Outer_Ctrl_Q_Ki: vf.add_const(value = 2.0, name='Ki'),
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
        C_iq: sym.hard_sat(iq, min_lim_q, iq_limit),
        u_fault: Outer_Ctrl_Q_U_fault,
        o1q: sym.Const(0.0),
        o3q: Outer_Ctrl_Q_U_fault,
        yiq: ((-o3q) + u),
        o4q: (yiq * Outer_Ctrl_Q_K),
        o5q: (o4q + iq_ref_PI),
        iq_ref_nonlimited: ((Outer_Ctrl_Q_proc_select_2 * o5q) + ((sym.Const(1.0) - Outer_Ctrl_Q_proc_select_2) * iq_ref_PI)),
        Outer_Ctrl_Q_dx: C_iq,
        iq_ref: iq_ref_nonlimited,
        iq_ref_PI: C_iq,
        iq_limit: vf.add_const(0.3, name=''),
        min_lim_q: (-iq_limit),
        o3_q: Outer_Ctrl_Q_Q_ctrl_mode,
        o2: (u - Vac_ref),
        o5_q: (Q_act - Q_ref),
        yi_q: ((Outer_Ctrl_Q_proc_select_3 * o5_q) + ((sym.Const(1.0) - Outer_Ctrl_Q_proc_select_3) * o2)),
        Q_ref: Q_act,
        Vac_ref: u,
    }
    Outer_ctrl_Q_2.procedural_logic = [
        picdro((u < u_fault), sym.Const(0.0), sym.Const(0.0), output=Outer_Ctrl_Q_proc_picdro_0),
        sampled_value(output=Outer_Ctrl_Q_proc_select_1, source=(u < u_fault)),
        sampled_value(output=Outer_Ctrl_Q_proc_select_2, source=o1q),
        sampled_value(output=Outer_Ctrl_Q_proc_select_3, source=o3_q),
    ]

    current_limiter_iq_headroom = (
        (((Current_Limiter_C * Current_Limiter_C) - (o2 * o2))
         * sym.heaviside((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) - sym.Const(0.0))))
        + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) - sym.Const(0.0)))))
    )
    current_limiter_iq_limit_raw = sym.sqrt(sym.Const(1e-8) + current_limiter_iq_headroom)

    Current_Limiter_3 = Block(
        algebraic_eqs=[
            (o10_lim - ((current_limiter_iq_limit_raw * sym.heaviside((sym.Const(0.3) - current_limiter_iq_limit_raw))) + (sym.Const(0.3) * (sym.Const(1) - sym.heaviside((sym.Const(0.3) - current_limiter_iq_limit_raw)))))),
            (o4_lim - iq_ref),
            (o11 - sym.sqrt(sym.Const(1e-8) + ((((sym.Const(1.0) * sym.Const(1.0)) - (o5 * o5)) * sym.heaviside((((sym.Const(1.0) * sym.Const(1.0)) - (o5 * o5)) - sym.Const(0.0)))) + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((sym.Const(1.0) * sym.Const(1.0)) - (o5 * o5)) - sym.Const(0.0)))))))),
            (o3_lim - id_ref),
            (o1 - Current_Limiter_proc_picdro_0),
            (o13 - Current_Limiter_C),
            (o14 - sym.Const(1.0)),
            (id_lim_cal - o11),
            (id_ref_lmtd - o3_lim),
            (iq_ref_lmtd - ((Current_Limiter_proc_select_3 * o5) + ((sym.Const(1.0) - Current_Limiter_proc_select_3) * o4_lim))),
            (id_limit - ((Current_Limiter_proc_select_4 * o12) + ((sym.Const(1.0) - Current_Limiter_proc_select_4) * o13))),
            (iq_limit - ((Current_Limiter_proc_select_5 * o14) + ((sym.Const(1.0) - Current_Limiter_proc_select_5) * o15))),
            (Current_Limiter_U_sgnl - o1),
            (o6_lim - Current_Limiter_U_sgnl),
            (o7 - Current_Limiter_U_sgnl),
            (o8 - Current_Limiter_U_sgnl),
            (o9_lim - Current_Limiter_U_sgnl),
            (o12 - id_lim_cal),
            (iq_lim_cal - o10_lim),
            (o15 - iq_lim_cal),
        ],
        algebraic_vars=[o10_lim, o4_lim, o11, o3_lim, o1, o13, o14, id_lim_cal, id_ref_lmtd, iq_ref_lmtd, id_limit, iq_limit, Current_Limiter_U_sgnl, o6_lim, o7, o8, o9_lim, o12, iq_lim_cal, o15],
        in_vars=[id_ref, u, iq_ref],
        out_vars=[id_limit, id_ref_lmtd, iq_ref_lmtd, iq_limit],
        name='Current_Limiter'
    )
    # --- Parameter Values ---
    Current_Limiter_3.event_dict = {
        Current_Limiter_V_fault: vf.add_const(value = 0.0, name='V_fault'),
        Current_Limiter_C: vf.add_const(value = 1.0, name='C'),
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
        Current_Limiter_C: vf.add_const(value=1.0, name='C_init'),
        o1: sym.Const(0.0),
        o3_lim: id_ref,
        o4_lim: iq_ref,
        o13: Current_Limiter_C,
        o14: sym.Const(1.0),
        o10_lim: sym.Const(0.3),
        o11: sym.Const(1.0),
        id_lim_cal: o11,
        iq_lim_cal: o10_lim,
        o12: id_lim_cal,
        o15: iq_lim_cal,
        id_ref_lmtd: o3_lim,
        iq_ref_lmtd: o4_lim,
        id_limit: Current_Limiter_C,
        iq_limit: iq_lim_cal,
        Current_Limiter_U_sgnl: o1,
        o6_lim: Current_Limiter_U_sgnl,
        o7: Current_Limiter_U_sgnl,
        o8: Current_Limiter_U_sgnl,
        o9_lim: Current_Limiter_U_sgnl,
    }
    Current_Limiter_3.procedural_logic = [
        picdro((u < Current_Limiter_V_fault), sym.Const(0.0), sym.Const(0.0), output=Current_Limiter_proc_picdro_0),
        sampled_value(output=Current_Limiter_proc_select_1, source=(u < Current_Limiter_V_fault)),
        sampled_value(output=Current_Limiter_proc_select_2, source=o7),
        sampled_value(output=Current_Limiter_proc_select_3, source=o8),
        sampled_value(output=Current_Limiter_proc_select_4, source=o6_lim),
        sampled_value(output=Current_Limiter_proc_select_5, source=o9_lim),
    ]

    Inner_ctrl_Current_4 = Block(
        state_eqs=[
            (Inner_Control_Ki_d * yi1),
            (Inner_Control_Ki_q * yi_i),
        ],
        state_vars=[Inner_Control_xd, Inner_Control_xq],
        algebraic_eqs=[
            (o5_i - ((Inner_Control_Kp_d * yi1) + Inner_Control_xd)),
            (o6_i - ((Inner_Control_Kp_q * yi_i) + Inner_Control_xq)),
            (Pmd - (((((yi2 * Inner_Control_V_ac_base) / Inner_Control_U_dc_base) * sym.Const(2.0)) * sym.sqrt(sym.Const(2.0))) / sym.sqrt(sym.Const(3.0)))),
            (Pmq - (((((yi3 * Inner_Control_V_ac_base) / Inner_Control_U_dc_base) * sym.Const(2.0)) * sym.sqrt(sym.Const(2.0))) / sym.sqrt(sym.Const(3.0)))),
            (o10_i - ((-id) * Inner_Control_wL)),
            (o9_i - (iq * Inner_Control_wL)),
            (yi2 - (vmd / uDC)),
            (yi3 - (vmq / uDC)),
            (yi1 - (id_ref_lmtd - (-id))),
            (yi_i - (iq_ref_lmtd - iq)),
            (vmd - ((o5_i - o9_i) + vd)),
            (vmq - ((o6_i + vq) + o10_i)),
        ],
        algebraic_vars=[o5_i, o6_i, Pmd, Pmq, o10_i, o9_i, yi2, yi3, yi1, yi_i, vmd, vmq],
        in_vars=[vd, id_ref_lmtd, id, iq, iq_ref_lmtd, vq, uDC],
        out_vars=[Pmd, Pmq],
        name='Inner_ctrl_Current'
    )
    Inner_ctrl_Current_4.diff_vars = [d_Inner_Control_xd, d_Inner_Control_xq]
    # --- Parameter Values ---
    Inner_ctrl_Current_4.event_dict = {
        Inner_Control_Kp_d: vf.add_const(value = 0.8, name='Kp_d'),
        Inner_Control_Ki_d: vf.add_const(value = 8.0, name='Ki_d'),
        Inner_Control_wL: vf.add_const(value = 0.2, name='wL'),
        Inner_Control_Kp_q: vf.add_const(value = 0.8, name='Kp_q'),
        Inner_Control_Ki_q: vf.add_const(value = 8.0, name='Ki_q'),
        Inner_Control_V_ac_base: vf.add_const(value = 525.0, name='V_ac_base'),
        Inner_Control_U_dc_base: vf.add_const(value = 1050.0, name='U_dc_base'),
    }
    # --- Initial Equations and Guesses ---
    Inner_ctrl_Current_4.init_eqs = {
        Inner_Control_xd: (((-vd) + vmd) + (Inner_Control_wL * iq)),
        Inner_Control_xq: (((-vq) + vmq) - (Inner_Control_wL * (-id))),
        vmd: ((((Pmd * uDC) * Inner_Control_U_dc_base) * sym.sqrt(sym.Const(3.0))) / ((sym.Const(2.0) * sym.sqrt(sym.Const(2.0))) * Inner_Control_V_ac_base)),
        vmq: ((((Pmq * uDC) * Inner_Control_U_dc_base) * sym.sqrt(sym.Const(3.0))) / ((sym.Const(2.0) * sym.sqrt(sym.Const(2.0))) * Inner_Control_V_ac_base)),
        yi1: (id_ref_lmtd - (-id)),
        yi_i: (iq_ref_lmtd - iq),
        o10_i: ((-id) * Inner_Control_wL),
        o9_i: (iq * Inner_Control_wL),
        o5_i: ((Inner_Control_Kp_d * yi1) + Inner_Control_xd),
        o6_i: ((Inner_Control_Kp_q * yi_i) + Inner_Control_xq),
        yi2: (vmd / uDC),
        yi3: (vmq / uDC),
    }

    # --------------------------------------
    # MAIN BLOCK
    # --------------------------------------
    # all the algebraic vars in the general template are defined as inputs in the PowerFactory model. However,
    # VeraGrid hasn't got those variables that way. The algebraic equations in the template serve as conversion
    # between the inputs from the VeraGrid devices and inputs (measurements) from the PowerFactory model
    pll_block, pll_outputs = pll_transform_rms(vfactory=vf, Vm=Vmt, Va=Vat, name=f"nuactis_master_pll_{name}")
    theta = pll_outputs[2]

    templ.block = Block(
        children=[pll_block, Vxy_To_dqFrame_0, Outer_ctrl_P_1, Outer_ctrl_Q_2, Current_Limiter_3, Inner_ctrl_Current_4],
        algebraic_vars=[u, ur, ui, cosphi, sinphi, P_act, Q_act],
        algebraic_eqs=[
            u - Vmt,
            ur - Vmt * sym.cos(Vat),
            ui - Vmt * sym.sin(Vat),
            cosphi - sym.cos(theta),
            sinphi - sym.sin(theta),
            P_act + (vq * iq + vd * (-id)),
            Q_act + (vq * (-id) - vd * iq),
        ],
        init_eqs={
            u: Vmt,
            ur: Vmt * sym.cos(Vat),
            ui: Vmt * sym.sin(Vat),
            cosphi: sym.cos(theta),
            sinphi: sym.sin(theta),

        },
        in_vars=[Vmf, Vaf, Vmt, Vat, uDC, id, iq],
        out_vars=[Pmd, Pmq],
        name='MasterPWM_Model'
    )
    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Vmf: Vmf,
        VarPowerFlowRefferenceType.Vaf: Vaf,
        VarPowerFlowRefferenceType.Vmt: Vmt,
        VarPowerFlowRefferenceType.Vat: Vat,
        VarPowerFlowRefferenceType.Vdc: uDC,
    }
    templ.block.internal_vars = {
        "P_act": P_act,
        "Q_act": Q_act,
        "id": id,
        "iq": iq,
        "vd": vd,
        "vq": vq,
        "theta": theta,
        "omega": pll_outputs[3],
        "Pmd": Pmd,
        "Pmq": Pmq,
    }

    # delta: sym.imag(
    #     sym.log((inputs[0] * sym.exp(1j * inputs[1]) + (R1 + 1j * X1) * (
    #         sym.conj((P_g + 1j * Q_g) / (inputs[0] * sym.exp(1j * inputs[1]))))) / (
    #                 sym.abs(inputs[0] * sym.exp(1j * inputs[1]) + (R1 + 1j * X1) * (
    #                     sym.conj((P_g + 1j * Q_g) / (inputs[0] * sym.exp(1j * inputs[1])))))))),
    # omega: omega_ref,
    # v_d: sym.real((inputs[0] * sym.exp(1j * inputs[1])) * sym.exp(-1j * (delta - np.pi / 2))),
    # v_q: sym.imag((inputs[0] * sym.exp(1j * inputs[1])) * sym.exp(-1j * (delta - np.pi / 2))),

    # (vd - ((ur * cosphi) + (ui * sinphi))),
    # (vq - ((ui * cosphi) - (ur * sinphi))),


    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    return get_masterpwm_model_emt_template(vf=vf, name='MasterPWM_Model' if name is None else name)


def build_trafo_master_block(vfactory: VarFactory, name: str = "") -> RmsModelTemplate:
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.VscDevice

    suffix = f"_{name}" if name else ""

    vm_f = vfactory.add_var("Vmf" + suffix)
    va_f = vfactory.add_var("Vaf" + suffix)
    vm_t = vfactory.add_var("Vmt" + suffix)
    va_t = vfactory.add_var("Vat" + suffix)
    vdc = vfactory.add_var("Vdc" + suffix)

    pt_vsc = vfactory.add_var("Pt_vsc_control" + suffix)
    qt_vsc = vfactory.add_var("Qt_vsc_control" + suffix)
    pf_vsc = vfactory.add_var("Pf_vsc_control" + suffix)
    #qf_vsc = vfactory.add_var("Qf_vsc_control" + suffix)
    im_out = vfactory.add_var("Im_vsc_control" + suffix)

    r_traf = vfactory.add_var("R_traf" + suffix)
    l_traf = vfactory.add_var("L_traf" + suffix)
    eps = vfactory.add_var("eps" + suffix)
    v_d_c = vfactory.add_var("v_d_c" + suffix)
    v_q_c = vfactory.add_var("v_q_c" + suffix)

    i_d = vfactory.add_var("id" + suffix)
    i_q = vfactory.add_var("iq" + suffix)
    master_ctrl = get_masterpwm_model_emt_template(
        vf=vfactory,
        name=f"MasterPWM_Model{suffix}",
        bindings={"Vmf": vm_f, "Vaf": va_f, "Vmt": vm_t, "Vat": va_t, "uDC": vdc, "id": i_d, "iq": i_q},
    ).block
    modulator = get_nuactis_modulator_rms_template(vf=vfactory, name=f"NuActis_Modulator{suffix}").block

    internal = master_ctrl.internal_vars
    pmd = internal["Pmd"]
    pmq = internal["Pmq"]
    md = modulator.out_vars[0]
    mq = modulator.out_vars[1]

    pmd_mod = modulator.in_vars[0]
    pmq_mod = modulator.in_vars[1]

    p_act = internal["P_act"]
    q_act = internal["Q_act"]
    v_d = internal["vd"]
    v_q = internal["vq"]
    theta = internal["theta"]
    omega = internal["omega"]

    i_mag = vfactory.add_var("Im_internal" + suffix)
    dt_id = vfactory.add_diff_var("dt_id" + suffix, base_var=i_d)
    dt_iq = vfactory.add_diff_var("dt_iq" + suffix, base_var=i_q)

    modulator.connect([pmd_mod, pmq_mod], [pmd, pmq])

    block = Block(
        algebraic_eqs=[
            p_act + pt_vsc,
            q_act + qt_vsc,
            v_d_c - md,
            v_q_c - mq,
            v_d_c - vm_f * sym.sin(va_f - theta),
            v_q_c - vm_f * sym.cos(va_f - theta),
            v_d_c - (v_d + (r_traf * (-i_d) + l_traf * dt_id - omega * l_traf * i_q)),
            v_q_c - (v_q - (r_traf * i_q + l_traf * dt_iq + omega * l_traf * (-i_d))),
            i_mag - sym.sqrt((i_d * i_d) + (i_q * i_q) + eps),
            pf_vsc + pt_vsc - (r_traf * i_mag * i_mag),
            im_out - i_mag,
        ],
        algebraic_vars=[pt_vsc, qt_vsc, pf_vsc, i_mag, im_out, v_d_c, v_q_c, i_d, i_q],
        diff_vars=[dt_id, dt_iq],
        in_vars=[vm_f, va_f, vm_t, va_t, vdc],
        out_vars=[pf_vsc, pt_vsc, qt_vsc, im_out, md, mq],
        event_dict={
            r_traf: vfactory.add_const(0.005),
            l_traf: vfactory.add_const(0.12),
            eps: vfactory.add_const(1e-10),
        },
        init_eqs={
            p_act: -pt_vsc,
            q_act: -qt_vsc,
            theta: va_t,
            omega: vfactory.add_const(1),
            v_d: vfactory.add_const(0),
            v_q: vm_t,
            i_q: pt_vsc / v_q,
            i_d: (-qt_vsc) / v_q,
            i_mag: sym.sqrt((i_d * i_d) + (i_q * i_q) + eps),
            im_out: i_mag,
            v_d_c: vm_f * sym.sin(va_f - theta),
            v_q_c: vm_f * sym.cos(va_f - theta),
            pmd: v_d_c,
            pmq: v_q_c,
        },
        diff_init_eqs={
            dt_id: sym.Const(0.0),
            dt_iq: sym.Const(0.0),
        },
        children=[master_ctrl, modulator],
        name="trafo_master_block",
    )

    block.external_mapping = {
        VarPowerFlowRefferenceType.Vmf: vm_f,
        VarPowerFlowRefferenceType.Vaf: va_f,
        VarPowerFlowRefferenceType.Vmt: vm_t,
        VarPowerFlowRefferenceType.Vat: va_t,
        VarPowerFlowRefferenceType.Vdc: vdc,
        VarPowerFlowRefferenceType.Pf: pf_vsc,
        VarPowerFlowRefferenceType.Pt: pt_vsc,
        VarPowerFlowRefferenceType.Qt: qt_vsc,
        VarPowerFlowRefferenceType.Im: im_out,
    }

    templ._block = block
    return templ
