# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_kp_ki_s_skd_1_std_p_462_emt_template(vf: VarFactory, name: str = 'Kp+Ki/s+sKd/(1+sTd) [(p__462') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kp_Ki_s_sKd_1_sTd_p_Kd = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__Kd_' + name)
    Kp_Ki_s_sKd_1_sTd_p_Ki = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__Ki_' + name)
    Kp_Ki_s_sKd_1_sTd_p_Kp = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__Kp_' + name)
    Kp_Ki_s_sKd_1_sTd_p_Td = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__Td_' + name)
    Kp_Ki_s_sKd_1_sTd_p_y_max = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__y_max_' + name)
    Kp_Ki_s_sKd_1_sTd_p_y_min = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__y_min_' + name)

    # --- State Variables ---
    Kp_Ki_s_sKd_1_sTd_p_x1 = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__x1_' + name)
    Kp_Ki_s_sKd_1_sTd_p_x2 = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__x2_' + name)

    # --- Algebraic / Shared Variables ---
    Kp_Ki_s_sKd_1_sTd_p_proc_lastvalue_2 = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__proc_lastvalue_2_' + name)
    Kp_Ki_s_sKd_1_sTd_p_proc_select_0 = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__proc_select_0_' + name)
    Kp_Ki_s_sKd_1_sTd_p_proc_select_1 = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__proc_select_1_' + name)
    Kp_Ki_s_sKd_1_sTd_p_proc_select_3 = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p__proc_select_3_' + name)
    Kp_Ki_s_sKd_1_sTd_p_dx2 = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p_dx2_' + name)
    Kp_Ki_s_sKd_1_sTd_p_x1_init = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p_x1_init_' + name)
    Kp_Ki_s_sKd_1_sTd_p_yd = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p_yd_' + name)
    Kp_Ki_s_sKd_1_sTd_p_yis = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p_yis_' + name)
    Kp_Ki_s_sKd_1_sTd_p_yk = vf.add_var('Kp+Ki/s+sKd/(1+sTd) [(p_yk_' + name)
    hold = vf.add_var('hold_' + name)
    rst = vf.add_var('rst_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Kp_Ki_s_sKd_1_sTd_p_x1 = vf.add_diff_var('d_Kp+Ki/s+sKd/(1+sTd) [(p__x1_' + name, base_var=Kp_Ki_s_sKd_1_sTd_p_x1)
    d_Kp_Ki_s_sKd_1_sTd_p_x2 = vf.add_diff_var('d_Kp+Ki/s+sKd/(1+sTd) [(p__x2_' + name, base_var=Kp_Ki_s_sKd_1_sTd_p_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Kp_Ki_s_sKd_1_sTd_p_proc_select_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Kp_Ki_s_sKd_1_sTd_p_proc_select_1) * (yi * Kp_Ki_s_sKd_1_sTd_p_Ki))),
            ((Kp_Ki_s_sKd_1_sTd_p_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Kp_Ki_s_sKd_1_sTd_p_proc_select_0) * Kp_Ki_s_sKd_1_sTd_p_dx2)),
        ],
        state_vars=[Kp_Ki_s_sKd_1_sTd_p_x1, Kp_Ki_s_sKd_1_sTd_p_x2],
        algebraic_eqs=[
            (Kp_Ki_s_sKd_1_sTd_p_yk - (Kp_Ki_s_sKd_1_sTd_p_Kp * yi)),
            (Kp_Ki_s_sKd_1_sTd_p_dx2 - ((yi - Kp_Ki_s_sKd_1_sTd_p_x2) / Kp_Ki_s_sKd_1_sTd_p_Td)),
            (Kp_Ki_s_sKd_1_sTd_p_yd - (Kp_Ki_s_sKd_1_sTd_p_dx2 * Kp_Ki_s_sKd_1_sTd_p_Kd)),
            (Kp_Ki_s_sKd_1_sTd_p_yis - ((Kp_Ki_s_sKd_1_sTd_p_y_min + ((Kp_Ki_s_sKd_1_sTd_p_x1 - Kp_Ki_s_sKd_1_sTd_p_y_min) * sym.heaviside((Kp_Ki_s_sKd_1_sTd_p_x1 - Kp_Ki_s_sKd_1_sTd_p_y_min)))) - ((Kp_Ki_s_sKd_1_sTd_p_x1 - Kp_Ki_s_sKd_1_sTd_p_y_max) * sym.heaviside((Kp_Ki_s_sKd_1_sTd_p_x1 - Kp_Ki_s_sKd_1_sTd_p_y_max))))),
            (yo - ((Kp_Ki_s_sKd_1_sTd_p_proc_select_3 * Kp_Ki_s_sKd_1_sTd_p_proc_lastvalue_2) + ((sym.Const(1.0) - Kp_Ki_s_sKd_1_sTd_p_proc_select_3) * ((Kp_Ki_s_sKd_1_sTd_p_y_min + ((((Kp_Ki_s_sKd_1_sTd_p_yk + Kp_Ki_s_sKd_1_sTd_p_yis) + Kp_Ki_s_sKd_1_sTd_p_yd) - Kp_Ki_s_sKd_1_sTd_p_y_min) * sym.heaviside((((Kp_Ki_s_sKd_1_sTd_p_yk + Kp_Ki_s_sKd_1_sTd_p_yis) + Kp_Ki_s_sKd_1_sTd_p_yd) - Kp_Ki_s_sKd_1_sTd_p_y_min)))) - ((((Kp_Ki_s_sKd_1_sTd_p_yk + Kp_Ki_s_sKd_1_sTd_p_yis) + Kp_Ki_s_sKd_1_sTd_p_yd) - Kp_Ki_s_sKd_1_sTd_p_y_max) * sym.heaviside((((Kp_Ki_s_sKd_1_sTd_p_yk + Kp_Ki_s_sKd_1_sTd_p_yis) + Kp_Ki_s_sKd_1_sTd_p_yd) - Kp_Ki_s_sKd_1_sTd_p_y_max))))))),
        ],
        algebraic_vars=[Kp_Ki_s_sKd_1_sTd_p_yk, Kp_Ki_s_sKd_1_sTd_p_dx2, Kp_Ki_s_sKd_1_sTd_p_yd, Kp_Ki_s_sKd_1_sTd_p_yis, yo],
        in_vars=[yi, hold, rst],
        out_vars=[yo],
        name='Kp+Ki/s+sKd/(1+sTd) [(p'
    )
    templ.block.diff_vars = [d_Kp_Ki_s_sKd_1_sTd_p_x1, d_Kp_Ki_s_sKd_1_sTd_p_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kp_Ki_s_sKd_1_sTd_p_Kp: vf.add_const(None, name='Kp'),
        Kp_Ki_s_sKd_1_sTd_p_Ki: vf.add_const(None, name='Ki'),
        Kp_Ki_s_sKd_1_sTd_p_Kd: vf.add_const(None, name='Kd'),
        Kp_Ki_s_sKd_1_sTd_p_Td: vf.add_const(None, name='Td'),
        Kp_Ki_s_sKd_1_sTd_p_y_max: vf.add_const(None, name='y_max'),
        Kp_Ki_s_sKd_1_sTd_p_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Kp_Ki_s_sKd_1_sTd_p_proc_select_0: vf.add_const(0.0, name=''),
        Kp_Ki_s_sKd_1_sTd_p_proc_select_1: vf.add_const(0.0, name=''),
        Kp_Ki_s_sKd_1_sTd_p_proc_lastvalue_2: vf.add_const(0.0, name=''),
        Kp_Ki_s_sKd_1_sTd_p_proc_select_3: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Kp_Ki_s_sKd_1_sTd_p_x1_init: Kp_Ki_s_sKd_1_sTd_p_x1,
    }
    templ.block.procedural_logic = [
        sampled_value(output=Kp_Ki_s_sKd_1_sTd_p_proc_select_0, source=hold),
        sampled_value(output=Kp_Ki_s_sKd_1_sTd_p_proc_select_1, source=hold),
        lastvalue(yo, output=Kp_Ki_s_sKd_1_sTd_p_proc_lastvalue_2),
        sampled_value(output=Kp_Ki_s_sKd_1_sTd_p_proc_select_3, source=hold),
        reset(Kp_Ki_s_sKd_1_sTd_p_x1, rst, Kp_Ki_s_sKd_1_sTd_p_x1_init),
        reset(Kp_Ki_s_sKd_1_sTd_p_x2, rst, 0.0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kp_ki_s_skd_1_std_p_462_emt_template(vf=vf, name='Kp+Ki/s+sKd/(1+sTd) [(p__462' if name is None else name)
