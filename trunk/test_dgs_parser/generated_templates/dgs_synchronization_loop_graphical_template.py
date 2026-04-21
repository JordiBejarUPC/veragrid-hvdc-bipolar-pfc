# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\DGS_test_type_models.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_synchronization_loop_emt_template(vf: VarFactory, name: str = 'Synchronization Loop') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_2Hs_H = vf.add_var('1/2Hs__H_' + name)
    C_C = vf.add_var('C__C_' + name)
    Limit_ss_Tau = vf.add_var('Limit_ss__Tau_' + name)
    Multiply_K_K = vf.add_var('Multiply K__K_' + name)
    PI_with_hold_and_reset_GFOR_QREG_Kp = vf.add_var('PI with hold and reset__GFOR_QREG_Kp_' + name)
    PI_with_hold_and_reset_GFOR_QREG_Ti = vf.add_var('PI with hold and reset__GFOR_QREG_Ti_' + name)
    PT1_K = vf.add_var('PT1__K_' + name)
    PT1_T = vf.add_var('PT1__T_' + name)

    # --- State Variables ---
    v_1_2Hs_xw = vf.add_var('1/2Hs__xw_' + name)
    v_1_s_x = vf.add_var('1/s__x_' + name)
    v_1_s_x_1 = vf.add_var('1/s__x_' + name)
    v_1_s_x_2 = vf.add_var('1/s__x_' + name)
    PI_with_hold_and_reset_x = vf.add_var('PI with hold and reset__x_' + name)
    PT1_x = vf.add_var('PT1__x_' + name)
    angle_integrator_x = vf.add_var('angle integrator__x_' + name)

    # --- Algebraic / Shared Variables ---
    COS_yi = vf.add_var('COS__[yi]_' + name)
    DP = vf.add_var('DP_' + name)
    DP2 = vf.add_var('DP2_' + name)
    DP_full = vf.add_var('DP_full_' + name)
    DP_full_1 = vf.add_var('DP_full_' + name)
    Dw = vf.add_var('Dw_' + name)
    Dw_1 = vf.add_var('Dw_' + name)
    Dw_2 = vf.add_var('Dw_' + name)
    Freeze_Gate_proc_select_0 = vf.add_var('Freeze_Gate__proc_select_0_' + name)
    Freeze_Gate_proc_select_0_1 = vf.add_var('Freeze_Gate__proc_select_0_' + name)
    Limit_ss_x = vf.add_var('Limit_ss__x_' + name)
    PI_with_hold_and_reset_proc_lastvalue_1 = vf.add_var('PI with hold and reset__proc_lastvalue_1_' + name)
    PI_with_hold_and_reset_proc_select_0 = vf.add_var('PI with hold and reset__proc_select_0_' + name)
    PI_with_hold_and_reset_proc_select_2 = vf.add_var('PI with hold and reset__proc_select_2_' + name)
    P_capab_high = vf.add_var('P_capab_high_' + name)
    P_capab_low = vf.add_var('P_capab_low_' + name)
    Pmeas = vf.add_var('Pmeas_' + name)
    Pref_sat = vf.add_var('Pref_sat_' + name)
    Pref_sat1 = vf.add_var('Pref_sat1_' + name)
    Pset = vf.add_var('Pset_' + name)
    Pvsc_fil = vf.add_var('Pvsc_fil_' + name)
    SIN_yi = vf.add_var('SIN__[yi]_' + name)
    W_base = vf.add_var('W_base_' + name)
    cosdelta = vf.add_var('cosdelta_' + name)
    damping2 = vf.add_var('damping2_' + name)
    delta = vf.add_var('delta_' + name)
    f1 = vf.add_var('f1_' + name)
    flag_overload = vf.add_var('flag_overload_' + name)
    flag_overload_1 = vf.add_var('flag_overload_' + name)
    flag_overload_2 = vf.add_var('flag_overload_' + name)
    hold = vf.add_var('hold_' + name)
    rst = vf.add_var('rst_' + name)
    sindelta = vf.add_var('sindelta_' + name)
    u_in = vf.add_var('u_in_' + name)
    u_in_1 = vf.add_var('u_in_' + name)
    w = vf.add_var('w_' + name)
    w_r = vf.add_var('w_r_' + name)
    wdiff = vf.add_var('wdiff_' + name)
    wref = vf.add_var('wref_' + name)
    wref_1 = vf.add_var('wref_' + name)
    wset = vf.add_var('wset_' + name)
    wset_1 = vf.add_var('wset_' + name)
    x_init = vf.add_var('x_init_' + name)
    y_max_PI = vf.add_var('y_max_PI_' + name)
    y_min_PI = vf.add_var('y_min_PI_' + name)
    y_out = vf.add_var('y_out_' + name)
    y_out_1 = vf.add_var('y_out_' + name)
    yi = vf.add_var('yi_' + name)
    yi_1 = vf.add_var('yi_' + name)
    yi_2 = vf.add_var('yi_' + name)
    yi_3 = vf.add_var('yi_' + name)
    yi_4 = vf.add_var('yi_' + name)
    yi_5 = vf.add_var('yi_' + name)
    yi_6 = vf.add_var('yi_' + name)
    yi_7 = vf.add_var('yi_' + name)
    yi_8 = vf.add_var('yi_' + name)
    yi_9 = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)
    yo_1 = vf.add_var('yo_' + name)
    yo_2 = vf.add_var('yo_' + name)
    yo_3 = vf.add_var('yo_' + name)
    yo_4 = vf.add_var('yo_' + name)
    yo_5 = vf.add_var('yo_' + name)
    yo_6 = vf.add_var('yo_' + name)
    yo_7 = vf.add_var('yo_' + name)
    yo_8 = vf.add_var('yo_' + name)
    yo_9 = vf.add_var('yo_' + name)
    yo_10 = vf.add_var('yo_' + name)
    yo_11 = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_2Hs_xw = vf.add_diff_var('d_1/2Hs__xw_' + name, base_var=v_1_2Hs_xw)
    d_1_s_x = vf.add_diff_var('d_1/s__x_' + name, base_var=v_1_s_x)
    d_1_s_x_1 = vf.add_diff_var('d_1/s__x_' + name, base_var=v_1_s_x_1)
    d_1_s_x_2 = vf.add_diff_var('d_1/s__x_' + name, base_var=v_1_s_x_2)
    d_PI_with_hold_and_reset_x = vf.add_diff_var('d_PI with hold and reset__x_' + name, base_var=PI_with_hold_and_reset_x)
    d_PT1_x = vf.add_diff_var('d_PT1__x_' + name, base_var=PT1_x)
    d_angle_integrator_x = vf.add_diff_var('d_angle integrator__x_' + name, base_var=angle_integrator_x)

    # --- Block Assembly ---
    v_1_0 = Block(
        algebraic_eqs=[
            (yo - sym.Const(1.0)),
        ],
        algebraic_vars=[yo],
        out_vars=[yo],
        name='1'
    )

    v_1_2Hs_1 = Block(
        state_eqs=[
            ((sym.Const(1.0) / (sym.Const(2.0) * v_1_2Hs_H)) * DP_full_1),
        ],
        state_vars=[v_1_2Hs_xw],
        algebraic_eqs=[
            (Dw - v_1_2Hs_xw),
        ],
        algebraic_vars=[Dw],
        in_vars=[DP_full],
        out_vars=[Dw],
        name='1/2Hs'
    )
    v_1_2Hs_1.diff_vars = [d_1_2Hs_xw]
    # --- Parameter Values ---
    v_1_2Hs_1.event_dict = {
        v_1_2Hs_H: vf.add_const(None, name='H'),
    }

    v_1_s_2 = Block(
        state_eqs=[
            Dw,
        ],
        state_vars=[v_1_s_x],
        algebraic_eqs=[
            (yo_1 - v_1_s_x),
        ],
        algebraic_vars=[yo_1],
        in_vars=[yi],
        out_vars=[yo_1],
        name='1/s'
    )
    v_1_s_2.diff_vars = [d_1_s_x]

    v_1_s_3 = Block(
        state_eqs=[
            Dw,
        ],
        state_vars=[v_1_s_x_1],
        algebraic_eqs=[
            (yo_2 - v_1_s_x_1),
        ],
        algebraic_vars=[yo_2],
        in_vars=[yi_1],
        out_vars=[yo_2],
        name='1/s'
    )
    v_1_s_3.diff_vars = [d_1_s_x_1]

    v_1_s_4 = Block(
        state_eqs=[
            Dw,
        ],
        state_vars=[v_1_s_x_2],
        algebraic_eqs=[
            (yo_3 - v_1_s_x_2),
        ],
        algebraic_vars=[yo_3],
        in_vars=[yi_2],
        out_vars=[yo_3],
        name='1/s'
    )
    v_1_s_4.diff_vars = [d_1_s_x_2]

    C_5 = Block(
        algebraic_eqs=[
            (yo_4 - C_C),
        ],
        algebraic_vars=[yo_4],
        out_vars=[yo_4],
        name='C'
    )
    # --- Parameter Values ---
    C_5.event_dict = {
        C_C: vf.add_const(None, name='C'),
    }

    COS_6 = Block(
        algebraic_eqs=[
            (yo_5 - sym.cos(COS_yi)),
        ],
        algebraic_vars=[yo_5],
        in_vars=[yi_3],
        out_vars=[yo_5],
        name='COS'
    )

    Freeze_Gate_7 = Block(
        algebraic_eqs=[
            (y_out - ((Freeze_Gate_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Freeze_Gate_proc_select_0) * DP_full_1))),
        ],
        algebraic_vars=[y_out],
        in_vars=[flag_overload_1, u_in],
        out_vars=[y_out],
        name='Freeze_Gate'
    )
    # --- Retained Runtime Modes ---
    Freeze_Gate_7.mode_dict = {
        Freeze_Gate_proc_select_0: vf.add_const(0.0, name=''),
    }
    Freeze_Gate_7.procedural_logic = [
        sampled_value(output=Freeze_Gate_proc_select_0, source=(flag_overload > 0.5)),
    ]

    Freeze_Gate_8 = Block(
        algebraic_eqs=[
            (y_out_1 - ((Freeze_Gate_proc_select_0_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Freeze_Gate_proc_select_0_1) * DP_full_1))),
        ],
        algebraic_vars=[y_out_1],
        in_vars=[flag_overload_2, u_in_1],
        out_vars=[y_out_1],
        name='Freeze_Gate'
    )
    # --- Retained Runtime Modes ---
    Freeze_Gate_8.mode_dict = {
        Freeze_Gate_proc_select_0_1: vf.add_const(0.0, name=''),
    }
    Freeze_Gate_8.procedural_logic = [
        sampled_value(output=Freeze_Gate_proc_select_0_1, source=(flag_overload > 0.5)),
    ]

    K_9 = Block(
        algebraic_eqs=[
            (yo_6 - (Multiply_K_K * Dw)),
        ],
        algebraic_vars=[yo_6],
        in_vars=[yi_4],
        out_vars=[yo_6],
        name='K'
    )
    # --- Parameter Values ---
    K_9.event_dict = {
        Multiply_K_K: vf.add_const(None, name='K'),
    }

    Limit_ss_10 = Block(
        algebraic_eqs=[
            (yo_7 - Limit_ss_x),
        ],
        algebraic_vars=[yo_7],
        in_vars=[yi_5],
        out_vars=[yo_7],
        name='Limit_ss'
    )
    # --- Parameter Values ---
    Limit_ss_10.event_dict = {
        Limit_ss_Tau: vf.add_const(None, name='Tau'),
    }

    PI_with_hold_and_reset_11 = Block(
        state_eqs=[
            ((PI_with_hold_and_reset_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - PI_with_hold_and_reset_proc_select_0) * ((PI_with_hold_and_reset_GFOR_QREG_Kp / PI_with_hold_and_reset_GFOR_QREG_Ti) * Dw))),
        ],
        state_vars=[PI_with_hold_and_reset_x],
        algebraic_eqs=[
            (yo_8 - ((PI_with_hold_and_reset_proc_select_2 * PI_with_hold_and_reset_proc_lastvalue_1) + ((sym.Const(1.0) - PI_with_hold_and_reset_proc_select_2) * ((y_min_PI + ((((PI_with_hold_and_reset_GFOR_QREG_Kp * Dw) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_min_PI) * sym.heaviside((((PI_with_hold_and_reset_GFOR_QREG_Kp * Dw) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_min_PI)))) - ((((PI_with_hold_and_reset_GFOR_QREG_Kp * Dw) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_max_PI) * sym.heaviside((((PI_with_hold_and_reset_GFOR_QREG_Kp * Dw) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_max_PI))))))),
        ],
        algebraic_vars=[yo_8],
        in_vars=[yi_6, hold, rst, y_max_PI, y_min_PI, x_init],
        out_vars=[yo_8],
        name='PI with hold and reset'
    )
    PI_with_hold_and_reset_11.diff_vars = [d_PI_with_hold_and_reset_x]
    # --- Parameter Values ---
    PI_with_hold_and_reset_11.event_dict = {
        PI_with_hold_and_reset_GFOR_QREG_Kp: vf.add_const(None, name='GFOR_QREG_Kp'),
        PI_with_hold_and_reset_GFOR_QREG_Ti: vf.add_const(None, name='GFOR_QREG_Ti'),
    }
    # --- Retained Runtime Modes ---
    PI_with_hold_and_reset_11.mode_dict = {
        PI_with_hold_and_reset_proc_select_0: vf.add_const(0.0, name=''),
        PI_with_hold_and_reset_proc_lastvalue_1: vf.add_const(0.0, name=''),
        PI_with_hold_and_reset_proc_select_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    PI_with_hold_and_reset_11.init_eqs = {
        PI_with_hold_and_reset_x: x_init,
    }
    PI_with_hold_and_reset_11.procedural_logic = [
        sampled_value(output=PI_with_hold_and_reset_proc_select_0, source=hold),
        lastvalue(yo_8, output=PI_with_hold_and_reset_proc_lastvalue_1),
        sampled_value(output=PI_with_hold_and_reset_proc_select_2, source=hold),
        reset(PI_with_hold_and_reset_x, rst, x_init),
    ]

    PT1_12 = Block(
        state_eqs=[
            ((Dw - PT1_x) / PT1_T),
        ],
        state_vars=[PT1_x],
        algebraic_eqs=[
            (yo_9 - (PT1_K * PT1_x)),
        ],
        algebraic_vars=[yo_9],
        in_vars=[yi_7],
        out_vars=[yo_9],
        name='PT1'
    )
    PT1_12.diff_vars = [d_PT1_x]
    # --- Parameter Values ---
    PT1_12.event_dict = {
        PT1_K: vf.add_const(None, name='K'),
        PT1_T: vf.add_const(None, name='T'),
    }

    SIN_13 = Block(
        algebraic_eqs=[
            (yo_10 - sym.sin(SIN_yi)),
        ],
        algebraic_vars=[yo_10],
        in_vars=[yi_8],
        out_vars=[yo_10],
        name='SIN'
    )

    Summation_Point_14 = Block(
        algebraic_eqs=[
            (w - ((sym.Const(0.0) + (sym.Const(1.0) * W_base)) + (sym.Const(1.0) * Dw))),
        ],
        algebraic_vars=[w],
        in_vars=[W_base, Dw_1],
        out_vars=[w],
        name='Summation Point'
    )

    Summation_Point_2_15 = Block(
        algebraic_eqs=[
            (DP_full_1 - ((sym.Const(0.0) + (sym.Const(-1.0) * damping2)) + (sym.Const(1.0) * DP))),
        ],
        algebraic_vars=[DP_full_1],
        in_vars=[damping2, DP2],
        out_vars=[DP_full_1],
        name='Summation Point(2)'
    )

    Summation_Point_4_16 = Block(
        algebraic_eqs=[
            (wdiff - ((sym.Const(0.0) + (sym.Const(-1.0) * wref)) + (sym.Const(1.0) * wset))),
        ],
        algebraic_vars=[wdiff],
        in_vars=[wref_1, wset_1],
        out_vars=[wdiff],
        name='Summation Point(4)'
    )

    Summation_Point_6_17 = Block(
        algebraic_eqs=[
            (DP - ((sym.Const(0.0) + (sym.Const(-1.0) * Pvsc_fil)) + (sym.Const(1.0) * Pref_sat))),
        ],
        algebraic_vars=[DP],
        in_vars=[Pvsc_fil, Pref_sat],
        out_vars=[DP],
        name='Summation Point(6)'
    )

    angle_integrator_18 = Block(
        state_eqs=[
            (Dw * w_r),
        ],
        state_vars=[angle_integrator_x],
        algebraic_eqs=[
            (w_r - (sym.Const(6.283185307179586) * f1)),
            (delta - angle_integrator_x),
        ],
        algebraic_vars=[w_r, delta],
        in_vars=[Dw_2, f1],
        out_vars=[delta],
        name='angle integrator'
    )
    angle_integrator_18.diff_vars = [d_angle_integrator_x]

    fn_to_wn_19 = Block(
        algebraic_eqs=[
            (yo_11 - ((sym.Const(2.0) * sym.Const(3.141592653589793)) * Dw)),
        ],
        algebraic_vars=[yo_11],
        in_vars=[yi_9],
        out_vars=[yo_11],
        name='fn_to_wn'
    )

    # --- Graphical Connections (resolved from From/To) ---
    v_1_2Hs_1.connect([v_1_2Hs_1.in_vars[0]], [Summation_Point_2_15.out_vars[0]])
    v_1_s_2.connect([v_1_s_2.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    v_1_s_3.connect([v_1_s_3.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    v_1_s_4.connect([v_1_s_4.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    COS_6.connect([COS_6.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    Freeze_Gate_7.connect([Freeze_Gate_7.in_vars[0]], [flag_overload])
    Freeze_Gate_7.connect([Freeze_Gate_7.in_vars[1]], [Summation_Point_2_15.out_vars[0]])
    Freeze_Gate_8.connect([Freeze_Gate_8.in_vars[0]], [flag_overload])
    Freeze_Gate_8.connect([Freeze_Gate_8.in_vars[1]], [Summation_Point_2_15.out_vars[0]])
    K_9.connect([K_9.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    Limit_ss_10.connect([Limit_ss_10.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    PI_with_hold_and_reset_11.connect([PI_with_hold_and_reset_11.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    PT1_12.connect([PT1_12.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    SIN_13.connect([SIN_13.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    Summation_Point_14.connect([Summation_Point_14.in_vars[1]], [v_1_2Hs_1.out_vars[0]])
    Summation_Point_2_15.connect([Summation_Point_2_15.in_vars[1]], [Summation_Point_6_17.out_vars[0]])
    Summation_Point_4_16.connect([Summation_Point_4_16.in_vars[0]], [wref])
    Summation_Point_4_16.connect([Summation_Point_4_16.in_vars[1]], [wset])
    Summation_Point_6_17.connect([Summation_Point_6_17.in_vars[1]], [Pref_sat1])
    angle_integrator_18.connect([angle_integrator_18.in_vars[0]], [v_1_2Hs_1.out_vars[0]])
    fn_to_wn_19.connect([fn_to_wn_19.in_vars[0]], [v_1_2Hs_1.out_vars[0]])

    templ.block = Block(
        children=[v_1_0, v_1_2Hs_1, v_1_s_2, v_1_s_3, v_1_s_4, C_5, COS_6, Freeze_Gate_7, Freeze_Gate_8, K_9, Limit_ss_10, PI_with_hold_and_reset_11, PT1_12, SIN_13, Summation_Point_14, Summation_Point_2_15, Summation_Point_4_16, Summation_Point_6_17, angle_integrator_18, fn_to_wn_19],
        in_vars=[wset, wref, P_capab_high, P_capab_low, Pset, Pmeas, flag_overload],
        out_vars=[w, cosdelta, sindelta, Pref_sat1],
        name='Synchronization Loop'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_synchronization_loop_emt_template(vf=vf, name='Synchronization Loop' if name is None else name)
