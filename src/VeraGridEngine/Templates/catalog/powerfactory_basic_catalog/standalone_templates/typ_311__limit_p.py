# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import flipflop, sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_limit_p_311_emt_template(vf: VarFactory, name: str = 'Limit [p__311') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Limit_p_eps = vf.add_var('Limit [p__eps_' + name)
    Limit_p_y_min = vf.add_var('Limit [p__y_min_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Limit_p_proc_flipflop_4 = vf.add_var('Limit [p__proc_flipflop_4_' + name)
    Limit_p_proc_select_6 = vf.add_var('Limit [p__proc_select_6_' + name)
    Limit_p_proc_select_const_0 = vf.add_var('Limit [p__proc_select_const_0_' + name)
    Limit_p_proc_select_const_2 = vf.add_var('Limit [p__proc_select_const_2_' + name)
    Limit_p_proc_selfix_1 = vf.add_var('Limit [p__proc_selfix_1_' + name)
    Limit_p_proc_selfix_3 = vf.add_var('Limit [p__proc_selfix_3_' + name)
    Limit_p_proc_selfix_5 = vf.add_var('Limit [p__proc_selfix_5_' + name)
    Limit_p_proc_selfix_7 = vf.add_var('Limit [p__proc_selfix_7_' + name)
    Limit_p_proc_selfix_8 = vf.add_var('Limit [p__proc_selfix_8_' + name)
    Limit_p_proc_selfix_9 = vf.add_var('Limit [p__proc_selfix_9_' + name)
    Limit_p_rstmin = vf.add_var('Limit [p_rstmin_' + name)
    Limit_p_setmin = vf.add_var('Limit [p_setmin_' + name)
    Limit_p_yo_min = vf.add_var('Limit [p_yo_min_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Limit_p_setmin - ((Limit_p_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Limit_p_proc_selfix_1) * ((Limit_p_proc_select_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - Limit_p_proc_select_const_0) * sym.Const(0.0)))))),
            (Limit_p_rstmin - ((Limit_p_proc_selfix_3 * sym.Const(0.0)) + ((sym.Const(1.0) - Limit_p_proc_selfix_3) * ((Limit_p_proc_select_const_2 * sym.Const(1.0)) + ((sym.Const(1.0) - Limit_p_proc_select_const_2) * sym.Const(0.0)))))),
            (Limit_p_yo_min - ((Limit_p_proc_selfix_5 * sym.Const(0.0)) + ((sym.Const(1.0) - Limit_p_proc_selfix_5) * Limit_p_proc_flipflop_4))),
            (yo - ((Limit_p_proc_selfix_7 * ((yi * sym.heaviside((yi - Limit_p_y_min))) + (Limit_p_y_min * (sym.Const(1) - sym.heaviside((yi - Limit_p_y_min)))))) + ((sym.Const(1.0) - Limit_p_proc_selfix_7) * ((Limit_p_proc_select_6 * Limit_p_y_min) + ((sym.Const(1.0) - Limit_p_proc_select_6) * yi))))),
        ],
        algebraic_vars=[Limit_p_setmin, Limit_p_rstmin, Limit_p_yo_min, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Limit [p'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Limit_p_eps: vf.add_const(None, name='eps'),
        Limit_p_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Limit_p_proc_select_const_0: vf.add_const(0.0, name=''),
        Limit_p_proc_selfix_1: vf.add_const(0.0, name=''),
        Limit_p_proc_select_const_2: vf.add_const(0.0, name=''),
        Limit_p_proc_selfix_3: vf.add_const(0.0, name=''),
        Limit_p_proc_flipflop_4: vf.add_const(0.0, name=''),
        Limit_p_proc_selfix_5: vf.add_const(0.0, name=''),
        Limit_p_proc_select_6: vf.add_const(0.0, name=''),
        Limit_p_proc_selfix_7: vf.add_const(0.0, name=''),
        Limit_p_proc_selfix_8: vf.add_const(0.0, name=''),
        Limit_p_proc_selfix_9: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Limit_p_setmin: ((Limit_p_proc_selfix_8 * sym.heaviside(((Limit_p_y_min - yi) - sym.Const(1e-06)))) + ((sym.Const(1.0) - Limit_p_proc_selfix_8) * sym.heaviside(((Limit_p_y_min - (yi - Limit_p_eps)) - sym.Const(1e-06))))),
        Limit_p_rstmin: ((Limit_p_proc_selfix_9 * sym.heaviside(((yi - Limit_p_y_min) - sym.Const(1e-06)))) + ((sym.Const(1.0) - Limit_p_proc_selfix_9) * sym.heaviside((((yi + Limit_p_eps) - Limit_p_y_min) - sym.Const(1e-06))))),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Limit_p_proc_select_const_0, source=(sym.heaviside(((Limit_p_y_min - (yi - Limit_p_eps)) - 1e-06)) * sym.heaviside(((Limit_p_eps - 0.0) - 1e-06)))),
        selfix((Limit_p_eps <= 0.0), output=Limit_p_proc_selfix_1),
        sampled_value(output=Limit_p_proc_select_const_2, source=(sym.heaviside((((yi + Limit_p_eps) - Limit_p_y_min) - 1e-06)) * sym.heaviside(((Limit_p_eps - 0.0) - 1e-06)))),
        selfix((Limit_p_eps <= 0.0), output=Limit_p_proc_selfix_3),
        flipflop(Limit_p_setmin, Limit_p_rstmin, output=Limit_p_proc_flipflop_4),
        selfix((Limit_p_eps <= 0.0), output=Limit_p_proc_selfix_5),
        sampled_value(output=Limit_p_proc_select_6, source=(sym.heaviside(((Limit_p_yo_min - 0.5) - 1e-06)) * sym.heaviside(((Limit_p_eps - 0.0) - 1e-06)))),
        selfix((Limit_p_eps <= 0.0), output=Limit_p_proc_selfix_7),
        selfix((sym.heaviside(((Limit_p_y_min - (yi - Limit_p_eps)) - 1e-06)) * sym.heaviside((((yi + Limit_p_eps) - Limit_p_y_min) - 1e-06))), output=Limit_p_proc_selfix_8),
        selfix((sym.heaviside(((Limit_p_y_min - (yi - Limit_p_eps)) - 1e-06)) * sym.heaviside((((yi + Limit_p_eps) - Limit_p_y_min) - 1e-06))), output=Limit_p_proc_selfix_9),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_limit_p_311_emt_template(vf=vf, name='Limit [p__311' if name is None else name)
