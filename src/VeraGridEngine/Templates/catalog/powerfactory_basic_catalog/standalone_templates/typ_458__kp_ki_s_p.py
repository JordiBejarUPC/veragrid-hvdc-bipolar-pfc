# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_kp_ki_s_p_458_emt_template(vf: VarFactory, name: str = 'Kp+Ki/s [(p__458') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kp_Ki_s_p_Ki = vf.add_var('Kp+Ki/s [(p__Ki_' + name)
    Kp_Ki_s_p_Kp = vf.add_var('Kp+Ki/s [(p__Kp_' + name)
    Kp_Ki_s_p_y_max = vf.add_var('Kp+Ki/s [(p__y_max_' + name)
    Kp_Ki_s_p_y_min = vf.add_var('Kp+Ki/s [(p__y_min_' + name)

    # --- State Variables ---
    Kp_Ki_s_p_x = vf.add_var('Kp+Ki/s [(p__x_' + name)

    # --- Algebraic / Shared Variables ---
    Kp_Ki_s_p_proc_lastvalue_1 = vf.add_var('Kp+Ki/s [(p__proc_lastvalue_1_' + name)
    Kp_Ki_s_p_proc_select_0 = vf.add_var('Kp+Ki/s [(p__proc_select_0_' + name)
    Kp_Ki_s_p_proc_select_2 = vf.add_var('Kp+Ki/s [(p__proc_select_2_' + name)
    Kp_Ki_s_p_x_init = vf.add_var('Kp+Ki/s [(p_x_init_' + name)
    hold = vf.add_var('hold_' + name)
    rst = vf.add_var('rst_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Kp_Ki_s_p_x = vf.add_diff_var('d_Kp+Ki/s [(p__x_' + name, base_var=Kp_Ki_s_p_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Kp_Ki_s_p_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Kp_Ki_s_p_proc_select_0) * (Kp_Ki_s_p_Ki * yi))),
        ],
        state_vars=[Kp_Ki_s_p_x],
        algebraic_eqs=[
            (yo - ((Kp_Ki_s_p_proc_select_2 * Kp_Ki_s_p_proc_lastvalue_1) + ((sym.Const(1.0) - Kp_Ki_s_p_proc_select_2) * ((Kp_Ki_s_p_y_min + ((((Kp_Ki_s_p_Kp * yi) + ((Kp_Ki_s_p_y_min + ((Kp_Ki_s_p_x - Kp_Ki_s_p_y_min) * sym.heaviside((Kp_Ki_s_p_x - Kp_Ki_s_p_y_min)))) - ((Kp_Ki_s_p_x - Kp_Ki_s_p_y_max) * sym.heaviside((Kp_Ki_s_p_x - Kp_Ki_s_p_y_max))))) - Kp_Ki_s_p_y_min) * sym.heaviside((((Kp_Ki_s_p_Kp * yi) + ((Kp_Ki_s_p_y_min + ((Kp_Ki_s_p_x - Kp_Ki_s_p_y_min) * sym.heaviside((Kp_Ki_s_p_x - Kp_Ki_s_p_y_min)))) - ((Kp_Ki_s_p_x - Kp_Ki_s_p_y_max) * sym.heaviside((Kp_Ki_s_p_x - Kp_Ki_s_p_y_max))))) - Kp_Ki_s_p_y_min)))) - ((((Kp_Ki_s_p_Kp * yi) + ((Kp_Ki_s_p_y_min + ((Kp_Ki_s_p_x - Kp_Ki_s_p_y_min) * sym.heaviside((Kp_Ki_s_p_x - Kp_Ki_s_p_y_min)))) - ((Kp_Ki_s_p_x - Kp_Ki_s_p_y_max) * sym.heaviside((Kp_Ki_s_p_x - Kp_Ki_s_p_y_max))))) - Kp_Ki_s_p_y_max) * sym.heaviside((((Kp_Ki_s_p_Kp * yi) + ((Kp_Ki_s_p_y_min + ((Kp_Ki_s_p_x - Kp_Ki_s_p_y_min) * sym.heaviside((Kp_Ki_s_p_x - Kp_Ki_s_p_y_min)))) - ((Kp_Ki_s_p_x - Kp_Ki_s_p_y_max) * sym.heaviside((Kp_Ki_s_p_x - Kp_Ki_s_p_y_max))))) - Kp_Ki_s_p_y_max))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, hold, rst],
        out_vars=[yo],
        name='Kp+Ki/s [(p'
    )
    templ.block.diff_vars = [d_Kp_Ki_s_p_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kp_Ki_s_p_Kp: vf.add_const(None, name='Kp'),
        Kp_Ki_s_p_Ki: vf.add_const(None, name='Ki'),
        Kp_Ki_s_p_y_max: vf.add_const(None, name='y_max'),
        Kp_Ki_s_p_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Kp_Ki_s_p_proc_select_0: vf.add_const(0.0, name=''),
        Kp_Ki_s_p_proc_lastvalue_1: vf.add_const(0.0, name=''),
        Kp_Ki_s_p_proc_select_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Kp_Ki_s_p_x_init: Kp_Ki_s_p_x,
    }
    templ.block.procedural_logic = [
        sampled_value(output=Kp_Ki_s_p_proc_select_0, source=hold),
        lastvalue(yo, output=Kp_Ki_s_p_proc_lastvalue_1),
        sampled_value(output=Kp_Ki_s_p_proc_select_2, source=hold),
        reset(Kp_Ki_s_p_x, rst, Kp_Ki_s_p_x_init),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kp_ki_s_p_458_emt_template(vf=vf, name='Kp+Ki/s [(p__458' if name is None else name)
