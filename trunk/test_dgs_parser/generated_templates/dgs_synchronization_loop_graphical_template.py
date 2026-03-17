# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\DGS_test_type_models.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset
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
    DP_full = vf.add_var('DP_full_' + name)
    Dw = vf.add_var('Dw_' + name)
    Dw_1 = vf.add_var('Dw_' + name)
    Limit_ss_x = vf.add_var('Limit_ss__x_' + name)
    PI_with_hold_and_reset_proc_lastvalue_0 = vf.add_var('PI with hold and reset__proc_lastvalue_0_' + name)
    P_capab_high = vf.add_var('P_capab_high_' + name)
    P_capab_low = vf.add_var('P_capab_low_' + name)
    Pmeas = vf.add_var('Pmeas_' + name)
    Pref_sat1 = vf.add_var('Pref_sat1_' + name)
    Pset = vf.add_var('Pset_' + name)
    SIN_yi = vf.add_var('SIN__[yi]_' + name)
    cosdelta = vf.add_var('cosdelta_' + name)
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
    wref = vf.add_var('wref_' + name)
    wset = vf.add_var('wset_' + name)
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
            ((sym.Const(1.0) / (sym.Const(2.0) * v_1_2Hs_H)) * DP_full),
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
            yi,
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
            yi_1,
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
            yi_2,
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
            (y_out - ((sym.heaviside((flag_overload_1 - sym.Const(0.5))) * sym.Const(0.0)) + ((sym.Const(1.0) - sym.heaviside((flag_overload_1 - sym.Const(0.5)))) * u_in))),
        ],
        algebraic_vars=[y_out],
        in_vars=[flag_overload_1, u_in],
        out_vars=[y_out],
        name='Freeze_Gate'
    )

    Freeze_Gate_8 = Block(
        algebraic_eqs=[
            (y_out_1 - ((sym.heaviside((flag_overload_2 - sym.Const(0.5))) * sym.Const(0.0)) + ((sym.Const(1.0) - sym.heaviside((flag_overload_2 - sym.Const(0.5)))) * u_in_1))),
        ],
        algebraic_vars=[y_out_1],
        in_vars=[flag_overload_2, u_in_1],
        out_vars=[y_out_1],
        name='Freeze_Gate'
    )

    From_9 = Block(
        name='From'
    )

    From_1_10 = Block(
        name='From(1)'
    )

    From_12_11 = Block(
        name='From(12)'
    )

    From_13_12 = Block(
        name='From(13)'
    )

    From_18_13 = Block(
        name='From(18)'
    )

    From_19_14 = Block(
        name='From(19)'
    )

    From_2_15 = Block(
        name='From(2)'
    )

    From_20_16 = Block(
        name='From(20)'
    )

    From_3_17 = Block(
        name='From(3)'
    )

    From_31_18 = Block(
        name='From(31)'
    )

    From_38_19 = Block(
        name='From(38)'
    )

    From_39_20 = Block(
        name='From(39)'
    )

    From_4_21 = Block(
        name='From(4)'
    )

    From_4_22 = Block(
        name='From(4)'
    )

    From_5_23 = Block(
        name='From(5)'
    )

    From_6_24 = Block(
        name='From(6)'
    )

    From_66_25 = Block(
        name='From(66)'
    )

    From_7_26 = Block(
        name='From(7)'
    )

    From_8_27 = Block(
        name='From(8)'
    )

    From_9_28 = Block(
        name='From(9)'
    )

    Goto_29 = Block(
        name='Goto'
    )

    Goto_14_30 = Block(
        name='Goto(14)'
    )

    Goto_20_31 = Block(
        name='Goto(20)'
    )

    Goto_21_32 = Block(
        name='Goto(21)'
    )

    Goto_22_33 = Block(
        name='Goto(22)'
    )

    Goto_24_34 = Block(
        name='Goto(24)'
    )

    Goto_3_35 = Block(
        name='Goto(3)'
    )

    Goto_4_36 = Block(
        name='Goto(4)'
    )

    Goto_5_37 = Block(
        name='Goto(5)'
    )

    Goto_54_38 = Block(
        name='Goto(54)'
    )

    Goto_6_39 = Block(
        name='Goto(6)'
    )

    Goto_6_40 = Block(
        name='Goto(6)'
    )

    Goto_7_41 = Block(
        name='Goto(7)'
    )

    Goto_8_42 = Block(
        name='Goto(8)'
    )

    Goto_9_43 = Block(
        name='Goto(9)'
    )

    K_44 = Block(
        algebraic_eqs=[
            (yo_6 - (Multiply_K_K * yi_4)),
        ],
        algebraic_vars=[yo_6],
        in_vars=[yi_4],
        out_vars=[yo_6],
        name='K'
    )
    # --- Parameter Values ---
    K_44.event_dict = {
        Multiply_K_K: vf.add_const(None, name='K'),
    }

    Limit_ss_45 = Block(
        algebraic_eqs=[
            (yo_7 - Limit_ss_x),
        ],
        algebraic_vars=[yo_7],
        in_vars=[yi_5],
        out_vars=[yo_7],
        name='Limit_ss'
    )
    # --- Parameter Values ---
    Limit_ss_45.event_dict = {
        Limit_ss_Tau: vf.add_const(None, name='Tau'),
    }

    PI_with_hold_and_reset_46 = Block(
        state_eqs=[
            ((hold * sym.Const(0.0)) + ((sym.Const(1.0) - hold) * ((PI_with_hold_and_reset_GFOR_QREG_Kp / PI_with_hold_and_reset_GFOR_QREG_Ti) * yi_6))),
        ],
        state_vars=[PI_with_hold_and_reset_x],
        algebraic_eqs=[
            (yo_8 - ((hold * PI_with_hold_and_reset_proc_lastvalue_0) + ((sym.Const(1.0) - hold) * ((y_min_PI + ((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi_6) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_min_PI) * sym.heaviside((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi_6) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_min_PI)))) - ((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi_6) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_max_PI) * sym.heaviside((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi_6) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_max_PI))))))),
        ],
        algebraic_vars=[yo_8],
        in_vars=[yi_6, hold, rst, y_max_PI, y_min_PI, x_init],
        out_vars=[yo_8],
        name='PI with hold and reset'
    )
    PI_with_hold_and_reset_46.diff_vars = [d_PI_with_hold_and_reset_x]
    # --- Parameter Values ---
    PI_with_hold_and_reset_46.event_dict = {
        PI_with_hold_and_reset_GFOR_QREG_Kp: vf.add_const(None, name='GFOR_QREG_Kp'),
        PI_with_hold_and_reset_GFOR_QREG_Ti: vf.add_const(None, name='GFOR_QREG_Ti'),
    }
    # --- Retained Runtime Modes ---
    PI_with_hold_and_reset_46.mode_dict = {
        PI_with_hold_and_reset_proc_lastvalue_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    PI_with_hold_and_reset_46.init_eqs = {
        PI_with_hold_and_reset_x: x_init,
    }
    PI_with_hold_and_reset_46.procedural_logic = [
        lastvalue(yo_8, output=PI_with_hold_and_reset_proc_lastvalue_0),
        reset(PI_with_hold_and_reset_x, rst, x_init),
    ]

    PT1_47 = Block(
        state_eqs=[
            ((yi_7 - PT1_x) / PT1_T),
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
    PT1_47.diff_vars = [d_PT1_x]
    # --- Parameter Values ---
    PT1_47.event_dict = {
        PT1_K: vf.add_const(None, name='K'),
        PT1_T: vf.add_const(None, name='T'),
    }

    SIN_48 = Block(
        algebraic_eqs=[
            (yo_10 - sym.sin(SIN_yi)),
        ],
        algebraic_vars=[yo_10],
        in_vars=[yi_8],
        out_vars=[yo_10],
        name='SIN'
    )

    Summation_Point_49 = Block(
        name='Summation Point'
    )

    Summation_Point_2_50 = Block(
        name='Summation Point(2)'
    )

    Summation_Point_4_51 = Block(
        name='Summation Point(4)'
    )

    Summation_Point_6_52 = Block(
        name='Summation Point(6)'
    )

    angle_integrator_53 = Block(
        state_eqs=[
            (Dw_1 * w_r),
        ],
        state_vars=[angle_integrator_x],
        algebraic_eqs=[
            (w_r - (sym.Const(6.283185307179586) * f1)),
            (delta - angle_integrator_x),
        ],
        algebraic_vars=[w_r, delta],
        in_vars=[Dw_1, f1],
        out_vars=[delta],
        name='angle integrator'
    )
    angle_integrator_53.diff_vars = [d_angle_integrator_x]

    fn_to_wn_54 = Block(
        algebraic_eqs=[
            (yo_11 - ((sym.Const(2.0) * sym.Const(3.141592653589793)) * yi_9)),
        ],
        algebraic_vars=[yo_11],
        in_vars=[yi_9],
        out_vars=[yo_11],
        name='fn_to_wn'
    )

    templ.block = Block(
        children=[v_1_0, v_1_2Hs_1, v_1_s_2, v_1_s_3, v_1_s_4, C_5, COS_6, Freeze_Gate_7, Freeze_Gate_8, From_9, From_1_10, From_12_11, From_13_12, From_18_13, From_19_14, From_2_15, From_20_16, From_3_17, From_31_18, From_38_19, From_39_20, From_4_21, From_4_22, From_5_23, From_6_24, From_66_25, From_7_26, From_8_27, From_9_28, Goto_29, Goto_14_30, Goto_20_31, Goto_21_32, Goto_22_33, Goto_24_34, Goto_3_35, Goto_4_36, Goto_5_37, Goto_54_38, Goto_6_39, Goto_6_40, Goto_7_41, Goto_8_42, Goto_9_43, K_44, Limit_ss_45, PI_with_hold_and_reset_46, PT1_47, SIN_48, Summation_Point_49, Summation_Point_2_50, Summation_Point_4_51, Summation_Point_6_52, angle_integrator_53, fn_to_wn_54],
        in_vars=[wset, wref, P_capab_high, P_capab_low, Pset, Pmeas, flag_overload],
        out_vars=[w, cosdelta, sindelta, Pref_sat1],
        name='Synchronization Loop'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_synchronization_loop_emt_template(vf=vf, name='Synchronization Loop' if name is None else name)
