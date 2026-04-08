# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro, sampled_value
from VeraGridEngine.enumerations import ConverterControlType, DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Templates.Rms.vsc_gfl import pll_transform_rms
from trunk.nu_actis.nuactis_modulator_template import get_nuactis_modulator_rms_template

def get_slavepwm_model_emt_template(vf: VarFactory,
                                    name: str = 'SlavePWM_Model',
                                    bindings: dict | None = None,
                                    q_ctrl_mode: float = 1.0) -> tuple[RmsModelTemplate, dict]:
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- In vars ---
    bindings = {} if bindings is None else bindings
    Vmf = bindings.get("Vmf", vf.add_var("Vmf_" + name, VarPowerFlowRefferenceType.Vmf))
    Vaf = bindings.get("Vaf", vf.add_var("Vaf_" + name, VarPowerFlowRefferenceType.Vaf))
    Vmt = bindings.get("Vmt", vf.add_var("Vmt_" + name, VarPowerFlowRefferenceType.Vmt))
    Vat = bindings.get("Vat", vf.add_var("Vat_" + name, VarPowerFlowRefferenceType.Vat))

    # --- Parameters ---
    Current_Limiter_C = vf.add_var('Current_Limiter__C_' + name)
    Current_Limiter_V_fault = vf.add_var('Current_Limiter__V_fault_' + name)
    EPC_Control_Droop_VSC_MainFrame_G_dc = vf.add_var('EPC_Control_Droop_VSC_MainFrame__G_dc_' + name)
    EPC_Control_Droop_VSC_MainFrame_dF_max = vf.add_var('EPC_Control_Droop_VSC_MainFrame__dF_max_' + name)
    EPC_Control_Droop_VSC_MainFrame_dP_max_epc = vf.add_var('EPC_Control_Droop_VSC_MainFrame__dP_max_epc_' + name)
    EPC_Control_Droop_VSC_MainFrame_df_trig = vf.add_var('EPC_Control_Droop_VSC_MainFrame__df_trig_' + name)
    Inner_Control_Ki_d = vf.add_var('Inner_Control__Ki_d_' + name)
    Inner_Control_Ki_q = vf.add_var('Inner_Control__Ki_q_' + name)
    Inner_Control_Kp_d = vf.add_var('Inner_Control__Kp_d_' + name)
    Inner_Control_Kp_q = vf.add_var('Inner_Control__Kp_q_' + name)
    Inner_Control_U_dc_base = vf.add_var('Inner_Control__U_dc_base_' + name)
    Inner_Control_V_ac_base = vf.add_var('Inner_Control__V_ac_base_' + name)
    Inner_Control_wL = vf.add_var('Inner_Control__wL_' + name)
    Outer_Ctrl_P_wEPC_PI_V2_Ki = vf.add_var('Outer_Ctrl_P_wEPC-PI_V2__Ki_' + name)
    Outer_Ctrl_P_wEPC_PI_V2_Kp = vf.add_var('Outer_Ctrl_P_wEPC-PI_V2__Kp_' + name)
    Outer_Ctrl_P_wEPC_PI_V2_P_ctrl_mode = vf.add_var('Outer_Ctrl_P_wEPC-PI_V2__P_ctrl_mode_' + name)
    Outer_Ctrl_Q_K = vf.add_var('Outer_Ctrl_Q__K_' + name)
    Outer_Ctrl_Q_Ki = vf.add_var('Outer_Ctrl_Q__Ki_' + name)
    Outer_Ctrl_Q_Kp = vf.add_var('Outer_Ctrl_Q__Kp_' + name)
    Outer_Ctrl_Q_Q_ctrl_mode = vf.add_var('Outer_Ctrl_Q__Q_ctrl_mode_' + name)
    Outer_Ctrl_Q_U_fault = vf.add_var('Outer_Ctrl_Q__U_fault_' + name)

    # --- State Variables ---
    Inner_Control_xd = vf.add_var('Inner_Control__xd_' + name)
    Inner_Control_xq = vf.add_var('Inner_Control__xq_' + name)
    Outer_Ctrl_P_wEPC_PI_V2_dx = vf.add_var('Outer_Ctrl_P_wEPC-PI_V2__dx_' + name)
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
    EPC_Control_Droop_VSC_MainFrame_proc_select_0 = vf.add_var('EPC_Control_Droop_VSC_MainFrame__proc_select_0_' + name)
    EPC_Control_Droop_VSC_MainFrame_proc_select_1 = vf.add_var('EPC_Control_Droop_VSC_MainFrame__proc_select_1_' + name)
    Outer_Ctrl_P_wEPC_PI_V2_C = vf.add_var('Outer_Ctrl_P_wEPC-PI_V2__C_' + name)
    Outer_Ctrl_P_wEPC_PI_V2_proc_select_0 = vf.add_var('Outer_Ctrl_P_wEPC-PI_V2__proc_select_0_' + name)
    Outer_Ctrl_Q_C = vf.add_var('Outer_Ctrl_Q__C_' + name)
    Outer_Ctrl_Q_proc_picdro_0 = vf.add_var('Outer_Ctrl_Q__proc_picdro_0_' + name)
    Outer_Ctrl_Q_proc_select_1 = vf.add_var('Outer_Ctrl_Q__proc_select_1_' + name)
    Outer_Ctrl_Q_proc_select_2 = vf.add_var('Outer_Ctrl_Q__proc_select_2_' + name)
    Outer_Ctrl_Q_proc_select_3 = vf.add_var('Outer_Ctrl_Q__proc_select_3_' + name)
    P_act = vf.add_var('P_act_' + name)
    P_epc = vf.add_var('P_epc_' + name)
    Pdc_ref = vf.add_var('Pdc_ref_' + name)
    Pmd = vf.add_var('Pmd_' + name)
    Pmq = vf.add_var('Pmq_' + name)
    Q_act = vf.add_var('Q_act_' + name)
    Q_ref = vf.add_var('Q_ref_' + name)
    Vac_ref = vf.add_var('Vac_ref_' + name)
    cosphi = vf.add_var('cosphi_' + name)
    dPepc = vf.add_var('dPepc_' + name)
    df = vf.add_var('df_' + name)
    dfa = vf.add_var('dfa_' + name)
    fe = vf.add_var('fe_' + name)
    gain = vf.add_var('gain_' + name)
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
    uDC = bindings.get("uDC", vf.add_var('uDC_' + name))
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
    d_Outer_Ctrl_P_wEPC_PI_V2_dx = vf.add_diff_var('d_Outer_Ctrl_P_wEPC-PI_V2__dx_' + name, base_var=Outer_Ctrl_P_wEPC_PI_V2_dx)
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
            (Outer_Ctrl_P_wEPC_PI_V2_Ki * yi),
        ],
        state_vars=[Outer_Ctrl_P_wEPC_PI_V2_dx],
        algebraic_eqs=[
            (o3 - Outer_Ctrl_P_wEPC_PI_V2_P_ctrl_mode),
            (id_ref - ((min_lim_p + ((((Outer_Ctrl_P_wEPC_PI_V2_Kp * yi) + ((min_lim_p + ((Outer_Ctrl_P_wEPC_PI_V2_dx - min_lim_p) * sym.heaviside((Outer_Ctrl_P_wEPC_PI_V2_dx - min_lim_p)))) - ((Outer_Ctrl_P_wEPC_PI_V2_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_wEPC_PI_V2_dx - id_limit))))) - min_lim_p) * sym.heaviside((((Outer_Ctrl_P_wEPC_PI_V2_Kp * yi) + ((min_lim_p + ((Outer_Ctrl_P_wEPC_PI_V2_dx - min_lim_p) * sym.heaviside((Outer_Ctrl_P_wEPC_PI_V2_dx - min_lim_p)))) - ((Outer_Ctrl_P_wEPC_PI_V2_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_wEPC_PI_V2_dx - id_limit))))) - min_lim_p)))) - ((((Outer_Ctrl_P_wEPC_PI_V2_Kp * yi) + ((min_lim_p + ((Outer_Ctrl_P_wEPC_PI_V2_dx - min_lim_p) * sym.heaviside((Outer_Ctrl_P_wEPC_PI_V2_dx - min_lim_p)))) - ((Outer_Ctrl_P_wEPC_PI_V2_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_wEPC_PI_V2_dx - id_limit))))) - id_limit) * sym.heaviside((((Outer_Ctrl_P_wEPC_PI_V2_Kp * yi) + ((min_lim_p + ((Outer_Ctrl_P_wEPC_PI_V2_dx - min_lim_p) * sym.heaviside((Outer_Ctrl_P_wEPC_PI_V2_dx - min_lim_p)))) - ((Outer_Ctrl_P_wEPC_PI_V2_dx - id_limit) * sym.heaviside((Outer_Ctrl_P_wEPC_PI_V2_dx - id_limit))))) - id_limit))))),
            (min_lim_p - (-id_limit)),
            (C_id - id),
            (o5 - (((-P_act) + Pdc_ref) + P_epc)),
            (o4 - (uDC - uDC_ref)),
            (yi - ((Outer_Ctrl_P_wEPC_PI_V2_proc_select_0 * o5) + ((sym.Const(1.0) - Outer_Ctrl_P_wEPC_PI_V2_proc_select_0) * o4))),
        ],
        algebraic_vars=[o3, id_ref, min_lim_p, C_id, o5, o4, yi],
        in_vars=[id_limit, P_epc, P_act, Pdc_ref, uDC, uDC_ref, id],
        out_vars=[id_ref],
        name='Outer_ctrl_P'
    )
    Outer_ctrl_P_1.diff_vars = [d_Outer_Ctrl_P_wEPC_PI_V2_dx]
    # --- Parameter Values ---
    Outer_ctrl_P_1.event_dict = {
        Outer_Ctrl_P_wEPC_PI_V2_P_ctrl_mode: vf.add_const(value=0.0, name='P_ctrl_mode'),
        Outer_Ctrl_P_wEPC_PI_V2_Kp: vf.add_const(value=1.3, name='Kp'),
        Outer_Ctrl_P_wEPC_PI_V2_Ki: vf.add_const(value=70.0, name='Ki'),
        uDC_ref: uDC,  # references are parameters of the controller
        Pdc_ref: P_act,  # references are parameters of the controller
    }
    # --- Retained Runtime Modes ---
    Outer_ctrl_P_1.mode_dict = {
        Outer_Ctrl_P_wEPC_PI_V2_proc_select_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    Outer_ctrl_P_1.init_eqs = {
        C_id: id,
        Outer_Ctrl_P_wEPC_PI_V2_dx: C_id,
        id_ref: C_id,
        id_limit: vf.add_const(1.0, name=''),
        min_lim_p: (-id_limit),
        o5: (((-P_act) + Pdc_ref) + P_epc),
        o4: (uDC - uDC_ref),
        yi: ((Outer_Ctrl_P_wEPC_PI_V2_proc_select_0 * o5) + ((sym.Const(1.0) - Outer_Ctrl_P_wEPC_PI_V2_proc_select_0) * o4)),
        Pdc_ref: P_act,
        uDC_ref: uDC,
    }
    Outer_ctrl_P_1.procedural_logic = [
        sampled_value(output=Outer_Ctrl_P_wEPC_PI_V2_proc_select_0, source=o3),
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
        in_vars=[iq, Q_ref, Q_act, Vmt, Vac_ref, iq_limit],
        out_vars=[iq_ref],
        name='Outer_ctrl_Q'
    )
    Outer_ctrl_Q_2.diff_vars = [d_Outer_Ctrl_Q_dx]
    # --- Parameter Values ---
    Outer_ctrl_Q_2.event_dict = {
        Outer_Ctrl_Q_U_fault: vf.add_const(value=0.0, name='U_fault'),
        Outer_Ctrl_Q_K: vf.add_const(value=0.0, name='K'),
        Outer_Ctrl_Q_Q_ctrl_mode: vf.add_const(value=q_ctrl_mode, name='Q_ctrl_mode'),
        Outer_Ctrl_Q_Kp: vf.add_const(value=0.1, name='Kp'),
        Outer_Ctrl_Q_Ki: vf.add_const(value=10.0, name='Ki'),
        Q_ref: Q_act,  # references are parameters of the controller
        Vac_ref: u,  # references are parameters of the controller
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
        iq_ref: iq_ref_nonlimited,
        Outer_Ctrl_Q_dx: C_iq,
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

    Current_Limiter_3 = Block(
        algebraic_eqs=[
            (o10_lim - ((sym.sqrt(((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) * sym.heaviside((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) - sym.Const(0.0)))) + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) - sym.Const(0.0))))))) * sym.heaviside((sym.Const(0.3) - sym.sqrt(((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) * sym.heaviside((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) - sym.Const(0.0)))) + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) - sym.Const(0.0)))))))))) + (sym.Const(0.3) * (sym.Const(1) - sym.heaviside((sym.Const(0.3) - sym.sqrt(((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) * sym.heaviside((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) - sym.Const(0.0)))) + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((Current_Limiter_C * Current_Limiter_C) - (o2 * o2)) - sym.Const(0.0))))))))))))),
            (o4_lim - iq_ref),
            (o11 - sym.sqrt(((((sym.Const(1.0) * sym.Const(1.0)) - (o5 * o5)) * sym.heaviside((((sym.Const(1.0) * sym.Const(1.0)) - (o5 * o5)) - sym.Const(0.0)))) + (sym.Const(0.0) * (sym.Const(1) - sym.heaviside((((sym.Const(1.0) * sym.Const(1.0)) - (o5 * o5)) - sym.Const(0.0)))))))),
            (o3_lim - id_ref),
            (o1 - Current_Limiter_proc_picdro_0),
            (o13 - Current_Limiter_C),
            (o14 - sym.Const(1.0)),
            (id_lim_cal - o11),
            (id_ref_lmtd - ((Current_Limiter_proc_select_2 * o3_lim) + ((sym.Const(1.0) - Current_Limiter_proc_select_2) * o2))),
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
        in_vars=[id_ref, Vmt, iq_ref],
        out_vars=[id_limit, id_ref_lmtd, iq_ref_lmtd, iq_limit],
        name='Current_Limiter'
    )
    # --- Parameter Values ---
    Current_Limiter_3.event_dict = {
        Current_Limiter_V_fault: vf.add_const(value=0.0, name='V_fault'),
        Current_Limiter_C: vf.add_const(value=1.0, name='C'),
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
        id_ref_lmtd: o2,
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
            (o10_i - (id * Inner_Control_wL)),
            (o9_i - (iq * Inner_Control_wL)),
            (yi2 - (vmd / uDC)),
            (yi3 - (vmq / uDC)),
            (yi1 - (id_ref_lmtd - id)),
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
        Inner_Control_Kp_d: vf.add_const(value=1.43, name='Kp_d'),
        Inner_Control_Ki_d: vf.add_const(value=30.0, name='Ki_d'),
        Inner_Control_wL: vf.add_const(value=0.2, name='wL'),
        Inner_Control_Kp_q: vf.add_const(value=1.43, name='Kp_q'),
        Inner_Control_Ki_q: vf.add_const(value=30.0, name='Ki_q'),
        Inner_Control_V_ac_base: vf.add_const(value=520.0, name='V_ac_base'),
        Inner_Control_U_dc_base: vf.add_const(value=1050.0, name='U_dc_base'),
    }
    # --- Initial Equations and Guesses ---
    Inner_ctrl_Current_4.init_eqs = {
        Inner_Control_xd: (((-vd) + vmd) + (Inner_Control_wL * iq)),
        Inner_Control_xq: (((-vq) + vmq) - (Inner_Control_wL * id)),
        vmd: ((((Pmd * uDC) * Inner_Control_U_dc_base) * sym.sqrt(sym.Const(3.0))) / ((sym.Const(2.0) * sym.sqrt(sym.Const(2.0))) * Inner_Control_V_ac_base)),
        vmq: ((((Pmq * uDC) * Inner_Control_U_dc_base) * sym.sqrt(sym.Const(3.0))) / ((sym.Const(2.0) * sym.sqrt(sym.Const(2.0))) * Inner_Control_V_ac_base)),
        yi1: (id_ref_lmtd - id),
        yi_i: (iq_ref_lmtd - iq),
        o10_i: (id * Inner_Control_wL),
        o9_i: (iq * Inner_Control_wL),
        o5_i: ((Inner_Control_Kp_d * yi1) + Inner_Control_xd),
        o6_i: ((Inner_Control_Kp_q * yi_i) + Inner_Control_xq),
        yi2: (vmd / uDC),
        yi3: (vmq / uDC),
    }

    EPC_Block_5 = Block(
        algebraic_eqs=[
            (df - (fe - sym.Const(1.0))),
            (dfa - sym.abs(df)),
            (gain - ((EPC_Control_Droop_VSC_MainFrame_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - EPC_Control_Droop_VSC_MainFrame_proc_select_0) * EPC_Control_Droop_VSC_MainFrame_G_dc))),
            (dPepc - ((EPC_Control_Droop_VSC_MainFrame_proc_select_1 * (gain * (dfa - EPC_Control_Droop_VSC_MainFrame_df_trig))) + ((sym.Const(1.0) - EPC_Control_Droop_VSC_MainFrame_proc_select_1) * ((-gain) * (dfa + EPC_Control_Droop_VSC_MainFrame_df_trig))))),
            (P_epc - (((-EPC_Control_Droop_VSC_MainFrame_dP_max_epc) + ((dPepc - (-EPC_Control_Droop_VSC_MainFrame_dP_max_epc)) * sym.heaviside((dPepc - (-EPC_Control_Droop_VSC_MainFrame_dP_max_epc))))) - ((dPepc - EPC_Control_Droop_VSC_MainFrame_dP_max_epc) * sym.heaviside((dPepc - EPC_Control_Droop_VSC_MainFrame_dP_max_epc))))),
        ],
        algebraic_vars=[df, dfa, gain, dPepc, P_epc],
        # in_vars=[fe], # defined as a parameter
        out_vars=[P_epc],
        name='EPC Block'
    )
    # --- Parameter Values ---
    EPC_Block_5.event_dict = {
        EPC_Control_Droop_VSC_MainFrame_dF_max: vf.add_const(50.0, name='dF_max'),
        EPC_Control_Droop_VSC_MainFrame_G_dc: vf.add_const(0.0, name='G_dc'),
        EPC_Control_Droop_VSC_MainFrame_df_trig: vf.add_const(0.008, name='df_trig'),
        EPC_Control_Droop_VSC_MainFrame_dP_max_epc: vf.add_const(1.0, name='dP_max_epc'),
        fe: vf.add_const(value = 1.0)
    }
    # --- Retained Runtime Modes ---
    EPC_Block_5.mode_dict = {
        EPC_Control_Droop_VSC_MainFrame_proc_select_0: vf.add_const(0.0, name=''),
        EPC_Control_Droop_VSC_MainFrame_proc_select_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    EPC_Block_5.init_eqs = {
        P_epc: vf.add_const(0.0, name=''),
    }
    EPC_Block_5.procedural_logic = [
        sampled_value(output=EPC_Control_Droop_VSC_MainFrame_proc_select_0, source=(dfa < EPC_Control_Droop_VSC_MainFrame_df_trig)),
        sampled_value(output=EPC_Control_Droop_VSC_MainFrame_proc_select_1, source=(df < 0.0)),
    ]

    # --------------------------------------
    # MAIN BLOCK
    # --------------------------------------
    # all the algebraic vars in the general template are defined as inputs in the PowerFactory model. However,
    # VeraGrid hasn't got those variables that way. The algebraic equations in the template serve as conversion
    # between the inputs from the VeraGrid devices and inputs (measurements) from the PowerFactory model
    pll_block, pll_outputs = pll_transform_rms(vfactory=vf, Vm=Vmt, Va=Vat, name=f"nuactis_slave_pll_{name}")
    theta = pll_outputs[2]

    templ.block = Block(
        children=[pll_block, Vxy_To_dqFrame_0, Outer_ctrl_P_1, Outer_ctrl_Q_2, Current_Limiter_3, Inner_ctrl_Current_4, EPC_Block_5],
        algebraic_vars=[u, ur, ui, cosphi, sinphi, P_act, Q_act],
        algebraic_eqs = [
            u - Vmf,
            ur - Vmf * sym.cos(Vaf),
            ui - Vmf * sym.sin(Vaf),
            cosphi - sym.cos(theta),
            sinphi - sym.sin(theta),
            P_act - (vq * iq + vd * id),
            Q_act - (vq * id - vd * iq),
        ],
        init_eqs={
            u: Vmf,
            ur: Vmf * sym.cos(Vaf),
            ui: Vmf * sym.sin(Vaf),
            cosphi: sym.cos(theta),
            sinphi: sym.sin(theta),
            P_act: (vq * iq + vd * id),
            Q_act: (vq * id - vd * iq),
        },
        in_vars=[Vmf, Vaf, Vmt, Vat, uDC, id, iq],
        out_vars=[Pmd, Pmq],
        name='SlavePWM_Model'
    )
    templ.block.external_mapping = {
        VarPowerFlowRefferenceType.Vmf: Vmf,
        VarPowerFlowRefferenceType.Vaf: Vaf,
        VarPowerFlowRefferenceType.Vmt: Vmt,
        VarPowerFlowRefferenceType.Vat: Vat,
        VarPowerFlowRefferenceType.Vdc: uDC,
    }
    internal_vars = {
        "P_act": P_act,
        "Q_act": Q_act,
        "id": id,
        "iq": iq,
        "vd": vd,
        "vq": vq,
        "omega": pll_outputs[3],
        "theta": pll_outputs[2],
        "Pmd": Pmd,
        "Pmq": Pmq,
    }
    templ.block.name = name
    return templ, internal_vars

def get_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    return get_slavepwm_model_emt_template(vf=vf, name='SlavePWM_Model' if name is None else name)


def build_trafo_slave_block(vfactory: VarFactory,
                            name: str = "",
                            q_control_type: ConverterControlType = ConverterControlType.Qac) -> RmsModelTemplate:
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
    qf_vsc = vfactory.add_var("Qf_vsc_control" + suffix)
    qf = vfactory.add_var("Qf" + suffix)
    im_out = vfactory.add_var("Im_vsc_control" + suffix)

    r_traf = vfactory.add_var("R_traf" + suffix)
    l_traf = vfactory.add_var("L_traf" + suffix)
    eps = vfactory.add_var("eps" + suffix)
    v_d_c = vfactory.add_var("v_d_c" + suffix)
    v_q_c = vfactory.add_var("v_q_c" + suffix)

    i_d = vfactory.add_var("id" + suffix)
    i_q = vfactory.add_var("iq" + suffix)
    q_ctrl_mode = 1.0 if str(q_control_type) == str(ConverterControlType.Qac) else 0.0

    slave_ctrl_templ, internal = get_slavepwm_model_emt_template(
        vf=vfactory,
        name=f"SlavePWM_Model{suffix}",
        bindings={"Vmf": vm_f, "Vaf": va_f, "Vmt": vm_t, "Vat": va_t, "uDC": vdc, "id": i_d, "iq": i_q},
        q_ctrl_mode=q_ctrl_mode,
    )
    slave_ctrl = slave_ctrl_templ.block
    modulator = get_nuactis_modulator_rms_template(vf=vfactory, name=f"NuActis_Modulator{suffix}").block

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
    omega = internal["omega"]
    theta = internal["theta"]

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
            v_d_c - v_d + (r_traf * i_d + l_traf * dt_id - omega * l_traf * i_q),
            v_q_c - v_q + (r_traf * i_q + l_traf * dt_iq + omega * l_traf * i_d),
            i_mag - sym.sqrt((i_d * i_d) + (i_q * i_q) + eps),
            pf_vsc + pt_vsc + (r_traf * i_mag * i_mag),
            qf_vsc - qf,
            im_out - i_mag,
        ],
        algebraic_vars=[pt_vsc, qt_vsc, pf_vsc, qf_vsc, i_mag, im_out, v_d_c, v_q_c, i_d, i_q],
        diff_vars=[dt_id, dt_iq],
        in_vars=[vm_f, va_f, vm_t, va_t, vdc],
        out_vars=[pf_vsc, pt_vsc, qt_vsc, im_out, md, mq],
        event_dict={
            r_traf: vfactory.add_const(0.01),
            l_traf: vfactory.add_const(0.05),
            eps: vfactory.add_const(1e-6),
            qf: vfactory.add_const(0.0),
        },
        init_eqs={
            p_act: -pt_vsc,
            q_act: -qt_vsc,
            pf_vsc: -(pt_vsc + (r_traf * i_mag * i_mag)),
            theta: va_t,
            omega: vfactory.add_const(1),
            v_d: vfactory.add_const(0),
            v_q: vm_t,
            i_q: (((-pt_vsc) * v_q) - ((-qt_vsc) * v_d)) / ((v_d * v_d) + (v_q * v_q) + eps),
            i_d: (((-qt_vsc) * v_q) + ((-pt_vsc) * v_d)) / ((v_d * v_d) + (v_q * v_q) + eps),
            pmd: v_d_c,
            pmq: v_q_c,
            i_mag: sym.sqrt((i_d * i_d) + (i_q * i_q) + eps),
            im_out: i_mag,
            v_d_c: vm_f * sym.sin(va_f - theta),
            v_q_c: vm_f * sym.cos(va_f - theta),
        },
        diff_init_eqs={
            dt_id: sym.Const(0.0),
            dt_iq: sym.Const(0.0),
        },
        children=[slave_ctrl, modulator],
        name="trafo_slave_block",
    )

    block.external_mapping = {
        VarPowerFlowRefferenceType.Vmf: vm_f,
        VarPowerFlowRefferenceType.Vaf: va_f,
        VarPowerFlowRefferenceType.Vmt: vm_t,
        VarPowerFlowRefferenceType.Vat: va_t,
        VarPowerFlowRefferenceType.Vdc: vdc,
        VarPowerFlowRefferenceType.Pf: pf_vsc,
        VarPowerFlowRefferenceType.Qf: qf_vsc,
        VarPowerFlowRefferenceType.Pt: pt_vsc,
        VarPowerFlowRefferenceType.Qt: qt_vsc,
        VarPowerFlowRefferenceType.Im: im_out,
    }

    templ._block = block
    return templ


def connect_rms_vsc_to_buses(vsc_model: Block,
                             controlled_bus_model: Block,
                             grid_bus_model: Block,
                             dc_bus_model: Block) -> None:
    """
    Connect an RMS VSC block to controlled AC bus, grid AC bus and DC bus.

    For NUACTIS trafo slave, the controlled bus is always the "from" side
    (Vmf/Vaf), while the grid bus is the "to" side (Vmt/Vat).
    """
    local_vars = []
    remote_vars = []

    ctrl_vm = controlled_bus_model.external_mapping[VarPowerFlowRefferenceType.Vm]
    ctrl_va = controlled_bus_model.external_mapping[VarPowerFlowRefferenceType.Va]
    grid_vm = grid_bus_model.external_mapping[VarPowerFlowRefferenceType.Vm]
    grid_va = grid_bus_model.external_mapping[VarPowerFlowRefferenceType.Va]
    bus_dc_v = dc_bus_model.external_mapping[VarPowerFlowRefferenceType.Vdc]

    from_vm, from_va = ctrl_vm, ctrl_va
    to_vm, to_va = grid_vm, grid_va

    if (VarPowerFlowRefferenceType.Vmf in vsc_model.external_mapping
            and VarPowerFlowRefferenceType.Vaf in vsc_model.external_mapping):
        local_vars.extend([
            vsc_model.external_mapping[VarPowerFlowRefferenceType.Vmf],
            vsc_model.external_mapping[VarPowerFlowRefferenceType.Vaf],
        ])
        remote_vars.extend([from_vm, from_va])

    if (VarPowerFlowRefferenceType.Vmt in vsc_model.external_mapping
            and VarPowerFlowRefferenceType.Vat in vsc_model.external_mapping):
        local_vars.extend([
            vsc_model.external_mapping[VarPowerFlowRefferenceType.Vmt],
            vsc_model.external_mapping[VarPowerFlowRefferenceType.Vat],
        ])
        remote_vars.extend([to_vm, to_va])

    if VarPowerFlowRefferenceType.Vdc in vsc_model.external_mapping:
        local_vars.append(vsc_model.external_mapping[VarPowerFlowRefferenceType.Vdc])
        remote_vars.append(bus_dc_v)

    if not local_vars:
        raise ValueError("No compatible voltage mappings found to connect RMS VSC to buses")

    vsc_model.connect(local_vars, remote_vars)
