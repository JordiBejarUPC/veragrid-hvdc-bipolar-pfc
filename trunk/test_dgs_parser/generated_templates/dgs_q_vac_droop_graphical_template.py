# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\DGS_test_type_models.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block, find_name_in_block
from VeraGridEngine.Utils.procedural_logic import flipflop, lastvalue, reset, sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_q_vac_droop_emt_template(vf: VarFactory, name: str = 'Q/Vac droop') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_1_sT_bypass_T = vf.add_var('1/(1+sT) _bypass__T_' + name)
    v_1_1_sT_bypass_T_1 = vf.add_var('1/(1+sT) _bypass__T_' + name)
    C_C = vf.add_var('C__C_' + name)
    C_C_1 = vf.add_var('C__C_' + name)
    Multiply_K_K = vf.add_var('Multiply K__K_' + name)
    Multiply_K_K_1 = vf.add_var('Multiply K__K_' + name)
    PI_with_hold_and_reset_GFOR_QREG_Kp = vf.add_var('PI with hold and reset__GFOR_QREG_Kp_' + name)
    PI_with_hold_and_reset_GFOR_QREG_Ti = vf.add_var('PI with hold and reset__GFOR_QREG_Ti_' + name)
    TDS_Pos_Vmax = vf.add_var('TDS Pos__Vmax_' + name)
    TDS_Pos_Vmin = vf.add_var('TDS Pos__Vmin_' + name)

    # --- State Variables ---
    v_1_1_sT_bypass_x = vf.add_var('1/(1+sT) _bypass__x_' + name)
    v_1_1_sT_bypass_x_1 = vf.add_var('1/(1+sT) _bypass__x_' + name)
    v_1_s_x = vf.add_var('1/s__x_' + name)
    v_1_s_x_1 = vf.add_var('1/s__x_' + name)
    v_1_s_x_2 = vf.add_var('1/s__x_' + name)
    v_1_s_x_3 = vf.add_var('1/s__x_' + name)
    PI_with_hold_and_reset_x = vf.add_var('PI with hold and reset__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_1_sT_bypass_proc_selfix_0 = vf.add_var('1/(1+sT) _bypass__proc_selfix_0_' + name)
    v_1_1_sT_bypass_proc_selfix_0_1 = vf.add_var('1/(1+sT) _bypass__proc_selfix_0_' + name)
    v_1_1_sT_bypass_proc_selfix_1 = vf.add_var('1/(1+sT) _bypass__proc_selfix_1_' + name)
    v_1_1_sT_bypass_proc_selfix_1_1 = vf.add_var('1/(1+sT) _bypass__proc_selfix_1_' + name)
    DV = vf.add_var('DV_' + name)
    FRT1_flag = vf.add_var('FRT1_flag_' + name)
    Freeze_Gate_proc_select_0 = vf.add_var('Freeze_Gate__proc_select_0_' + name)
    Freeze_Gate_proc_select_0_1 = vf.add_var('Freeze_Gate__proc_select_0_' + name)
    PI_with_hold_and_reset_proc_lastvalue_1 = vf.add_var('PI with hold and reset__proc_lastvalue_1_' + name)
    PI_with_hold_and_reset_proc_select_0 = vf.add_var('PI with hold and reset__proc_select_0_' + name)
    PI_with_hold_and_reset_proc_select_2 = vf.add_var('PI with hold and reset__proc_select_2_' + name)
    Pvsc = vf.add_var('Pvsc_' + name)
    Q_Vac_droop_denom_v = vf.add_var('Q/Vac droop__denom_v_' + name)
    Q_Vac_droop_e_int_imag = vf.add_var('Q/Vac droop__e_int_imag_' + name)
    Q_Vac_droop_e_int_real = vf.add_var('Q/Vac droop__e_int_real_' + name)
    Q_Vac_droop_e_mag_final = vf.add_var('Q/Vac droop__e_mag_final_' + name)
    Q_Vac_droop_i_imag = vf.add_var('Q/Vac droop__i_imag_' + name)
    Q_Vac_droop_i_real = vf.add_var('Q/Vac droop__i_real_' + name)
    Q_Vac_droop_v_imag = vf.add_var('Q/Vac droop__v_imag_' + name)
    Q_Vac_droop_v_real = vf.add_var('Q/Vac droop__v_real_' + name)
    Q_Vac_droop_val_cos = vf.add_var('Q/Vac droop__val_cos_' + name)
    Q_Vac_droop_val_sin = vf.add_var('Q/Vac droop__val_sin_' + name)
    Q_capab_high = vf.add_var('Q_capab_high_' + name)
    Q_capab_low = vf.add_var('Q_capab_low_' + name)
    Qref = vf.add_var('Qref_' + name)
    Qref_1 = vf.add_var('Qref_' + name)
    Qref_out = vf.add_var('Qref_out_' + name)
    Qref_sat = vf.add_var('Qref_sat_' + name)
    Qref_sat1 = vf.add_var('Qref_sat1_' + name)
    Qvsc = vf.add_var('Qvsc_' + name)
    Qvsc_f = vf.add_var('Qvsc_f_' + name)
    SIN_yi = vf.add_var('SIN__[yi]_' + name)
    TDS_Pos_proc_flipflop_2 = vf.add_var('TDS Pos__proc_flipflop_2_' + name)
    TDS_Pos_proc_select_const_0 = vf.add_var('TDS Pos__proc_select_const_0_' + name)
    TDS_Pos_proc_select_const_1 = vf.add_var('TDS Pos__proc_select_const_1_' + name)
    V1vsc = vf.add_var('V1vsc_' + name)
    Vf = vf.add_var('Vf_' + name)
    Vref = vf.add_var('Vref_' + name)
    Vref_1 = vf.add_var('Vref_' + name)
    ed = vf.add_var('ed_' + name)
    eq = vf.add_var('eq_' + name)
    flag_overload = vf.add_var('flag_overload_' + name)
    flag_overload_1 = vf.add_var('flag_overload_' + name)
    flag_overload_2 = vf.add_var('flag_overload_' + name)
    hold = vf.add_var('hold_' + name)
    o2 = vf.add_var('o2_' + name)
    o5 = vf.add_var('o5_' + name)
    o6 = vf.add_var('o6_' + name)
    o6_1 = vf.add_var('o6_' + name)
    o7 = vf.add_var('o7_' + name)
    o7_1 = vf.add_var('o7_' + name)
    phase_jump = vf.add_var('phase_jump_' + name)
    r = vf.add_var('r_' + name)
    rst = vf.add_var('rst_' + name)
    rv_init = vf.add_var('rv_init_' + name)
    s = vf.add_var('s_' + name)
    u = vf.add_var('u_' + name)
    u_in = vf.add_var('u_in_' + name)
    u_in_1 = vf.add_var('u_in_' + name)
    val_angle_E = vf.add_var('val_angle_E_' + name)
    x_init = vf.add_var('x_init_' + name)
    xv_init = vf.add_var('xv_init_' + name)
    y = vf.add_var('y_' + name)
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
    yi_10 = vf.add_var('yi_' + name)
    yi_11 = vf.add_var('yi_' + name)
    yi_12 = vf.add_var('yi_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi1_1 = vf.add_var('yi1_' + name)
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
    yo_12 = vf.add_var('yo_' + name)
    yo_13 = vf.add_var('yo_' + name)
    yo_14 = vf.add_var('yo_' + name)
    yo_15 = vf.add_var('yo_' + name)
    yo_16 = vf.add_var('yo_' + name)
    yo_17 = vf.add_var('yo_' + name)
    yo_18 = vf.add_var('yo_' + name)
    yo_19 = vf.add_var('yo_' + name)
    yo_20 = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_1_sT_bypass_x = vf.add_diff_var('d_1/(1+sT) _bypass__x_' + name, base_var=v_1_1_sT_bypass_x)
    d_1_1_sT_bypass_x_1 = vf.add_diff_var('d_1/(1+sT) _bypass__x_' + name, base_var=v_1_1_sT_bypass_x_1)
    d_1_s_x = vf.add_diff_var('d_1/s__x_' + name, base_var=v_1_s_x)
    d_1_s_x_1 = vf.add_diff_var('d_1/s__x_' + name, base_var=v_1_s_x_1)
    d_1_s_x_2 = vf.add_diff_var('d_1/s__x_' + name, base_var=v_1_s_x_2)
    d_1_s_x_3 = vf.add_diff_var('d_1/s__x_' + name, base_var=v_1_s_x_3)
    d_PI_with_hold_and_reset_x = vf.add_diff_var('d_PI with hold and reset__x_' + name, base_var=PI_with_hold_and_reset_x)

    # --- Block Assembly ---
    v_0_0 = Block(
        algebraic_eqs=[
            (yo - sym.Const(0.0)),
        ],
        algebraic_vars=[yo],
        out_vars=[yo],
        name='0'
    )

    v_0_1 = Block(
        algebraic_eqs=[
            (yo_1 - sym.Const(0.0)),
        ],
        algebraic_vars=[yo_1],
        out_vars=[yo_1],
        name='0'
    )

    v_0_2 = Block(
        algebraic_eqs=[
            (yo_2 - sym.Const(0.0)),
        ],
        algebraic_vars=[yo_2],
        out_vars=[yo_2],
        name='0'
    )

    v_1_3 = Block(
        algebraic_eqs=[
            (yo_3 - yi),
        ],
        algebraic_vars=[yo_3],
        in_vars=[yi],
        out_vars=[yo_3],
        name='1'
    )

    v_1_4 = Block(
        algebraic_eqs=[
            (yo_4 - sym.Const(1.0)),
        ],
        algebraic_vars=[yo_4],
        out_vars=[yo_4],
        name='1'
    )

    v_1_5 = Block(
        algebraic_eqs=[
            (yo_5 - yi_1),
        ],
        algebraic_vars=[yo_5],
        in_vars=[yi_1],
        out_vars=[yo_5],
        name='1'
    )

    v_1_6 = Block(
        algebraic_eqs=[
            (yo_6 - sym.Const(1.0)),
        ],
        algebraic_vars=[yo_6],
        out_vars=[yo_6],
        name='1'
    )

    v_1_1_sT_7 = Block(
        state_eqs=[
            ((v_1_1_sT_bypass_proc_selfix_0 * ((yi_2 - v_1_1_sT_bypass_x) / v_1_1_sT_bypass_T)) + ((sym.Const(1.0) - v_1_1_sT_bypass_proc_selfix_0) * sym.Const(0.0))),
        ],
        state_vars=[v_1_1_sT_bypass_x],
        algebraic_eqs=[
            (yo_7 - ((v_1_1_sT_bypass_proc_selfix_1 * v_1_1_sT_bypass_x) + ((sym.Const(1.0) - v_1_1_sT_bypass_proc_selfix_1) * yi_2))),
        ],
        algebraic_vars=[yo_7],
        in_vars=[yi_2],
        out_vars=[yo_7],
        name='1/(1+sT)'
    )
    v_1_1_sT_7.diff_vars = [d_1_1_sT_bypass_x]
    # --- Parameter Values ---
    v_1_1_sT_7.event_dict = {
        v_1_1_sT_bypass_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    v_1_1_sT_7.mode_dict = {
        v_1_1_sT_bypass_proc_selfix_0: vf.add_const(0.0, name=''),
        v_1_1_sT_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    v_1_1_sT_7.procedural_logic = [
        selfix((v_1_1_sT_bypass_T > 0.0), output=v_1_1_sT_bypass_proc_selfix_0),
        selfix((v_1_1_sT_bypass_T > 0.0), output=v_1_1_sT_bypass_proc_selfix_1),
    ]

    v_1_1_sT_8 = Block(
        state_eqs=[
            ((v_1_1_sT_bypass_proc_selfix_0_1 * ((yi_3 - v_1_1_sT_bypass_x_1) / v_1_1_sT_bypass_T_1)) + ((sym.Const(1.0) - v_1_1_sT_bypass_proc_selfix_0_1) * sym.Const(0.0))),
        ],
        state_vars=[v_1_1_sT_bypass_x_1],
        algebraic_eqs=[
            (yo_8 - ((v_1_1_sT_bypass_proc_selfix_1_1 * v_1_1_sT_bypass_x_1) + ((sym.Const(1.0) - v_1_1_sT_bypass_proc_selfix_1_1) * yi_3))),
        ],
        algebraic_vars=[yo_8],
        in_vars=[yi_3],
        out_vars=[yo_8],
        name='1/(1+sT)'
    )
    v_1_1_sT_8.diff_vars = [d_1_1_sT_bypass_x_1]
    # --- Parameter Values ---
    v_1_1_sT_8.event_dict = {
        v_1_1_sT_bypass_T_1: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    v_1_1_sT_8.mode_dict = {
        v_1_1_sT_bypass_proc_selfix_0_1: vf.add_const(0.0, name=''),
        v_1_1_sT_bypass_proc_selfix_1_1: vf.add_const(0.0, name=''),
    }
    v_1_1_sT_8.procedural_logic = [
        selfix((v_1_1_sT_bypass_T_1 > 0.0), output=v_1_1_sT_bypass_proc_selfix_0_1),
        selfix((v_1_1_sT_bypass_T_1 > 0.0), output=v_1_1_sT_bypass_proc_selfix_1_1),
    ]

    v_1_s_9 = Block(
        state_eqs=[
            yi_4,
        ],
        state_vars=[v_1_s_x],
        algebraic_eqs=[
            (yo_9 - v_1_s_x),
        ],
        algebraic_vars=[yo_9],
        in_vars=[yi_4],
        out_vars=[yo_9],
        name='1/s'
    )
    v_1_s_9.diff_vars = [d_1_s_x]

    v_1_s_10 = Block(
        state_eqs=[
            yi_5,
        ],
        state_vars=[v_1_s_x_1],
        algebraic_eqs=[
            (yo_10 - v_1_s_x_1),
        ],
        algebraic_vars=[yo_10],
        in_vars=[yi_5],
        out_vars=[yo_10],
        name='1/s'
    )
    v_1_s_10.diff_vars = [d_1_s_x_1]

    v_1_s_11 = Block(
        state_eqs=[
            yi_6,
        ],
        state_vars=[v_1_s_x_2],
        algebraic_eqs=[
            (yo_11 - v_1_s_x_2),
        ],
        algebraic_vars=[yo_11],
        in_vars=[yi_6],
        out_vars=[yo_11],
        name='1/s'
    )
    v_1_s_11.diff_vars = [d_1_s_x_2]

    v_1_s_12 = Block(
        state_eqs=[
            yi_7,
        ],
        state_vars=[v_1_s_x_3],
        algebraic_eqs=[
            (yo_12 - v_1_s_x_3),
        ],
        algebraic_vars=[yo_12],
        in_vars=[yi_7],
        out_vars=[yo_12],
        name='1/s'
    )
    v_1_s_12.diff_vars = [d_1_s_x_3]

    v_2PI_13 = Block(
        algebraic_eqs=[
            (yo_13 - sym.Const(6.283185307179586)),
        ],
        algebraic_vars=[yo_13],
        out_vars=[yo_13],
        name='2PI'
    )

    C_14 = Block(
        algebraic_eqs=[
            (yo_14 - C_C),
        ],
        algebraic_vars=[yo_14],
        out_vars=[yo_14],
        name='C'
    )
    # --- Parameter Values ---
    C_14.event_dict = {
        C_C: vf.add_const(None, name='C'),
    }

    C_15 = Block(
        algebraic_eqs=[
            (yo_15 - C_C_1),
        ],
        algebraic_vars=[yo_15],
        out_vars=[yo_15],
        name='C'
    )
    # --- Parameter Values ---
    C_15.event_dict = {
        C_C_1: vf.add_const(None, name='C'),
    }

    Freeze_Gate_16 = Block(
        algebraic_eqs=[
            (y_out - ((Freeze_Gate_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Freeze_Gate_proc_select_0) * u_in))),
        ],
        algebraic_vars=[y_out],
        in_vars=[flag_overload_1, u_in],
        out_vars=[y_out],
        name='Freeze_Gate'
    )
    # --- Retained Runtime Modes ---
    Freeze_Gate_16.mode_dict = {
        Freeze_Gate_proc_select_0: vf.add_const(0.0, name=''),
    }
    Freeze_Gate_16.procedural_logic = [
        sampled_value(output=Freeze_Gate_proc_select_0, source=(flag_overload > 0.5)),
    ]

    Freeze_Gate_17 = Block(
        algebraic_eqs=[
            (y_out_1 - ((Freeze_Gate_proc_select_0_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Freeze_Gate_proc_select_0_1) * u_in_1))),
        ],
        algebraic_vars=[y_out_1],
        in_vars=[flag_overload_2, u_in_1],
        out_vars=[y_out_1],
        name='Freeze_Gate'
    )
    # --- Retained Runtime Modes ---
    Freeze_Gate_17.mode_dict = {
        Freeze_Gate_proc_select_0_1: vf.add_const(0.0, name=''),
    }
    Freeze_Gate_17.procedural_logic = [
        sampled_value(output=Freeze_Gate_proc_select_0_1, source=(flag_overload > 0.5)),
    ]

    K_18 = Block(
        algebraic_eqs=[
            (yo_16 - (Multiply_K_K * yi_8)),
        ],
        algebraic_vars=[yo_16],
        in_vars=[yi_8],
        out_vars=[yo_16],
        name='K'
    )
    # --- Parameter Values ---
    K_18.event_dict = {
        Multiply_K_K: vf.add_const(None, name='K'),
    }

    K_19 = Block(
        algebraic_eqs=[
            (yo_17 - (Multiply_K_K_1 * yi_9)),
        ],
        algebraic_vars=[yo_17],
        in_vars=[yi_9],
        out_vars=[yo_17],
        name='K'
    )
    # --- Parameter Values ---
    K_19.event_dict = {
        Multiply_K_K_1: vf.add_const(None, name='K'),
    }

    Limit_20 = Block(
        in_vars=[yi_10],
        out_vars=[yo_18],
        name='Limit'
    )

    PI_with_hold_and_reset_21 = Block(
        state_eqs=[
            ((PI_with_hold_and_reset_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - PI_with_hold_and_reset_proc_select_0) * ((PI_with_hold_and_reset_GFOR_QREG_Kp / PI_with_hold_and_reset_GFOR_QREG_Ti) * yi_11))),
        ],
        state_vars=[PI_with_hold_and_reset_x],
        algebraic_eqs=[
            (yo_19 - ((PI_with_hold_and_reset_proc_select_2 * PI_with_hold_and_reset_proc_lastvalue_1) + ((sym.Const(1.0) - PI_with_hold_and_reset_proc_select_2) * ((y_min_PI + ((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi_11) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_min_PI) * sym.heaviside((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi_11) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_min_PI)))) - ((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi_11) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_max_PI) * sym.heaviside((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi_11) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_max_PI))))))),
        ],
        algebraic_vars=[yo_19],
        in_vars=[yi_11, hold, rst, y_max_PI, y_min_PI, x_init],
        out_vars=[yo_19],
        name='PI with hold and reset'
    )
    PI_with_hold_and_reset_21.diff_vars = [d_PI_with_hold_and_reset_x]
    # --- Parameter Values ---
    PI_with_hold_and_reset_21.event_dict = {
        PI_with_hold_and_reset_GFOR_QREG_Kp: vf.add_const(None, name='GFOR_QREG_Kp'),
        PI_with_hold_and_reset_GFOR_QREG_Ti: vf.add_const(None, name='GFOR_QREG_Ti'),
    }
    # --- Retained Runtime Modes ---
    PI_with_hold_and_reset_21.mode_dict = {
        PI_with_hold_and_reset_proc_select_0: vf.add_const(0.0, name=''),
        PI_with_hold_and_reset_proc_lastvalue_1: vf.add_const(0.0, name=''),
        PI_with_hold_and_reset_proc_select_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    PI_with_hold_and_reset_21.init_eqs = {
        PI_with_hold_and_reset_x: x_init,
    }
    PI_with_hold_and_reset_21.procedural_logic = [
        sampled_value(output=PI_with_hold_and_reset_proc_select_0, source=FRT1_flag),
        lastvalue(yo_19, output=PI_with_hold_and_reset_proc_lastvalue_1),
        sampled_value(output=PI_with_hold_and_reset_proc_select_2, source=FRT1_flag),
        reset(PI_with_hold_and_reset_x, rst, x_init),
    ]

    SIN_22 = Block(
        algebraic_eqs=[
            (yo_20 - sym.sin(SIN_yi)),
        ],
        algebraic_vars=[yo_20],
        in_vars=[yi_12],
        out_vars=[yo_20],
        name='SIN'
    )

    Summation_Point_23 = Block(
        algebraic_eqs=[
            (DV - ((sym.Const(0.0) + (sym.Const(1.0) * Vref)) + (sym.Const(-1.0) * Vf))),
        ],
        algebraic_vars=[DV],
        in_vars=[Vref_1, Vf],
        out_vars=[DV],
        name='Summation Point'
    )

    Summation_Point_24 = Block(
        algebraic_eqs=[
            (yi1 - ((sym.Const(0.0) + (sym.Const(1.0) * o7_1)) + (sym.Const(1.0) * phase_jump))),
        ],
        algebraic_vars=[yi1],
        in_vars=[o7, phase_jump],
        out_vars=[yi1],
        name='Summation Point'
    )

    Summation_Point_1_25 = Block(
        algebraic_eqs=[
            (o2 - ((sym.Const(0.0) + (sym.Const(1.0) * Qref_sat)) + (sym.Const(-1.0) * Qvsc_f))),
        ],
        algebraic_vars=[o2],
        in_vars=[Qref_sat, Qvsc_f],
        out_vars=[o2],
        name='Summation Point(1)'
    )

    Summation_Point_2_26 = Block(
        algebraic_eqs=[
            (yi1_1 - ((sym.Const(0.0) + (sym.Const(1.0) * Qref)) + (sym.Const(1.0) * o6))),
        ],
        algebraic_vars=[yi1_1],
        in_vars=[Qref_1, o6],
        out_vars=[yi1_1],
        name='Summation Point(2)'
    )

    Summation_Point_3_27 = Block(
        algebraic_eqs=[
            (o7_1 - ((sym.Const(0.0) + (sym.Const(1.0) * o5)) + (sym.Const(1.0) * o6_1))),
        ],
        algebraic_vars=[o7_1],
        in_vars=[o5, o6_1],
        out_vars=[o7_1],
        name='Summation Point(3)'
    )

    TDS_Pos_28 = Block(
        algebraic_eqs=[
            (s - ((TDS_Pos_proc_select_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - TDS_Pos_proc_select_const_0) * sym.Const(0.0)))),
            (r - ((TDS_Pos_proc_select_const_1 * sym.Const(1.0)) + ((sym.Const(1.0) - TDS_Pos_proc_select_const_1) * sym.Const(0.0)))),
            (y - TDS_Pos_proc_flipflop_2),
        ],
        algebraic_vars=[s, r, y],
        in_vars=[u],
        out_vars=[y],
        name='TDS Pos'
    )
    # --- Parameter Values ---
    TDS_Pos_28.event_dict = {
        TDS_Pos_Vmin: vf.add_const(None, name='Vmin'),
        TDS_Pos_Vmax: vf.add_const(None, name='Vmax'),
    }
    # --- Retained Runtime Modes ---
    TDS_Pos_28.mode_dict = {
        TDS_Pos_proc_select_const_0: vf.add_const(0.0, name=''),
        TDS_Pos_proc_select_const_1: vf.add_const(0.0, name=''),
        TDS_Pos_proc_flipflop_2: vf.add_const(0.0, name=''),
    }
    TDS_Pos_28.procedural_logic = [
        sampled_value(output=TDS_Pos_proc_select_const_0, source=(u <= TDS_Pos_Vmin)),
        sampled_value(output=TDS_Pos_proc_select_const_1, source=(u > TDS_Pos_Vmax)),
        flipflop(s, r, output=TDS_Pos_proc_flipflop_2),
    ]

    # --- Graphical Connections (resolved from From/To) ---
    Freeze_Gate_16.connect([Freeze_Gate_16.in_vars[0]], [flag_overload])
    Freeze_Gate_17.connect([Freeze_Gate_17.in_vars[0]], [flag_overload])
    PI_with_hold_and_reset_21.connect([PI_with_hold_and_reset_21.in_vars[1]], [FRT1_flag])
    Summation_Point_23.connect([Summation_Point_23.in_vars[0]], [Vref])
    Summation_Point_24.connect([Summation_Point_24.in_vars[0]], [Summation_Point_3_27.out_vars[0]])
    Summation_Point_1_25.connect([Summation_Point_1_25.in_vars[0]], [Qref_sat1])
    Summation_Point_2_26.connect([Summation_Point_2_26.in_vars[0]], [Qref])

    templ.block = Block(
        children=[v_0_0, v_0_1, v_0_2, v_1_3, v_1_4, v_1_5, v_1_6, v_1_1_sT_7, v_1_1_sT_8, v_1_s_9, v_1_s_10, v_1_s_11, v_1_s_12, v_2PI_13, C_14, C_15, Freeze_Gate_16, Freeze_Gate_17, K_18, K_19, Limit_20, PI_with_hold_and_reset_21, SIN_22, Summation_Point_23, Summation_Point_24, Summation_Point_1_25, Summation_Point_2_26, Summation_Point_3_27, TDS_Pos_28],
        in_vars=[Q_capab_high, Vref, V1vsc, Qref, Qvsc, Q_capab_low, FRT1_flag, Pvsc, val_angle_E, flag_overload, xv_init, rv_init],
        out_vars=[Qref_out, ed, eq, Qref_sat1],
        name='Q/Vac droop'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_q_vac_droop_emt_template(vf=vf, name='Q/Vac droop' if name is None else name)
