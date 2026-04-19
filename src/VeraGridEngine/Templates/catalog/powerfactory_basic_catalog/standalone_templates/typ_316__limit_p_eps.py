# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import flipflop, sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_limit_p_eps_316_emt_template(vf: VarFactory, name: str = 'Limit [p] _eps__316') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Limit_p_eps_eps = vf.add_var('Limit [p] _eps__eps_' + name)
    Limit_p_eps_y_lim = vf.add_var('Limit [p] _eps__y_lim_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Limit_p_eps_proc_flipflop_10 = vf.add_var('Limit [p] _eps__proc_flipflop_10_' + name)
    Limit_p_eps_proc_flipflop_8 = vf.add_var('Limit [p] _eps__proc_flipflop_8_' + name)
    Limit_p_eps_proc_select_12 = vf.add_var('Limit [p] _eps__proc_select_12_' + name)
    Limit_p_eps_proc_select_13 = vf.add_var('Limit [p] _eps__proc_select_13_' + name)
    Limit_p_eps_proc_select_const_0 = vf.add_var('Limit [p] _eps__proc_select_const_0_' + name)
    Limit_p_eps_proc_select_const_2 = vf.add_var('Limit [p] _eps__proc_select_const_2_' + name)
    Limit_p_eps_proc_select_const_4 = vf.add_var('Limit [p] _eps__proc_select_const_4_' + name)
    Limit_p_eps_proc_select_const_6 = vf.add_var('Limit [p] _eps__proc_select_const_6_' + name)
    Limit_p_eps_proc_selfix_1 = vf.add_var('Limit [p] _eps__proc_selfix_1_' + name)
    Limit_p_eps_proc_selfix_11 = vf.add_var('Limit [p] _eps__proc_selfix_11_' + name)
    Limit_p_eps_proc_selfix_14 = vf.add_var('Limit [p] _eps__proc_selfix_14_' + name)
    Limit_p_eps_proc_selfix_15 = vf.add_var('Limit [p] _eps__proc_selfix_15_' + name)
    Limit_p_eps_proc_selfix_16 = vf.add_var('Limit [p] _eps__proc_selfix_16_' + name)
    Limit_p_eps_proc_selfix_17 = vf.add_var('Limit [p] _eps__proc_selfix_17_' + name)
    Limit_p_eps_proc_selfix_18 = vf.add_var('Limit [p] _eps__proc_selfix_18_' + name)
    Limit_p_eps_proc_selfix_3 = vf.add_var('Limit [p] _eps__proc_selfix_3_' + name)
    Limit_p_eps_proc_selfix_5 = vf.add_var('Limit [p] _eps__proc_selfix_5_' + name)
    Limit_p_eps_proc_selfix_7 = vf.add_var('Limit [p] _eps__proc_selfix_7_' + name)
    Limit_p_eps_proc_selfix_9 = vf.add_var('Limit [p] _eps__proc_selfix_9_' + name)
    Limit_p_eps_rstmax = vf.add_var('Limit [p] _eps_rstmax_' + name)
    Limit_p_eps_rstmin = vf.add_var('Limit [p] _eps_rstmin_' + name)
    Limit_p_eps_setmax = vf.add_var('Limit [p] _eps_setmax_' + name)
    Limit_p_eps_setmin = vf.add_var('Limit [p] _eps_setmin_' + name)
    Limit_p_eps_yo_max = vf.add_var('Limit [p] _eps_yo_max_' + name)
    Limit_p_eps_yo_min = vf.add_var('Limit [p] _eps_yo_min_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Limit_p_eps_setmin - ((Limit_p_eps_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_1) * ((Limit_p_eps_proc_select_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_select_const_0) * sym.Const(0.0)))))),
            (Limit_p_eps_rstmin - ((Limit_p_eps_proc_selfix_3 * sym.Const(0.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_3) * ((Limit_p_eps_proc_select_const_2 * sym.Const(1.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_select_const_2) * sym.Const(0.0)))))),
            (Limit_p_eps_setmax - ((Limit_p_eps_proc_selfix_5 * sym.Const(0.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_5) * ((Limit_p_eps_proc_select_const_4 * sym.Const(1.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_select_const_4) * sym.Const(0.0)))))),
            (Limit_p_eps_rstmax - ((Limit_p_eps_proc_selfix_7 * sym.Const(0.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_7) * ((Limit_p_eps_proc_select_const_6 * sym.Const(1.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_select_const_6) * sym.Const(0.0)))))),
            (Limit_p_eps_yo_min - ((Limit_p_eps_proc_selfix_9 * sym.Const(0.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_9) * Limit_p_eps_proc_flipflop_8))),
            (Limit_p_eps_yo_max - ((Limit_p_eps_proc_selfix_11 * sym.Const(0.0)) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_11) * Limit_p_eps_proc_flipflop_10))),
            (yo - ((Limit_p_eps_proc_selfix_14 * (((-Limit_p_eps_y_lim) + ((yi - (-Limit_p_eps_y_lim)) * sym.heaviside((yi - (-Limit_p_eps_y_lim))))) - ((yi - Limit_p_eps_y_lim) * sym.heaviside((yi - Limit_p_eps_y_lim))))) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_14) * ((Limit_p_eps_proc_select_13 * (-Limit_p_eps_y_lim)) + ((sym.Const(1.0) - Limit_p_eps_proc_select_13) * ((Limit_p_eps_proc_select_12 * Limit_p_eps_y_lim) + ((sym.Const(1.0) - Limit_p_eps_proc_select_12) * yi))))))),
        ],
        algebraic_vars=[Limit_p_eps_setmin, Limit_p_eps_rstmin, Limit_p_eps_setmax, Limit_p_eps_rstmax, Limit_p_eps_yo_min, Limit_p_eps_yo_max, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Limit [p] _eps'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Limit_p_eps_eps: vf.add_const(None, name='eps'),
        Limit_p_eps_y_lim: vf.add_const(None, name='y_lim'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Limit_p_eps_proc_select_const_0: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_1: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_select_const_2: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_3: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_select_const_4: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_5: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_select_const_6: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_7: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_flipflop_8: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_9: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_flipflop_10: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_11: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_select_12: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_select_13: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_14: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_15: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_16: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_17: vf.add_const(0.0, name=''),
        Limit_p_eps_proc_selfix_18: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Limit_p_eps_setmin: ((Limit_p_eps_proc_selfix_15 * sym.heaviside((((-Limit_p_eps_y_lim) - yi) - sym.Const(1e-06)))) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_15) * sym.heaviside((((-Limit_p_eps_y_lim) - (yi - Limit_p_eps_eps)) - sym.Const(1e-06))))),
        Limit_p_eps_rstmin: ((Limit_p_eps_proc_selfix_16 * sym.heaviside(((yi - (-Limit_p_eps_y_lim)) - sym.Const(1e-06)))) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_16) * sym.heaviside((((yi + Limit_p_eps_eps) - (-Limit_p_eps_y_lim)) - sym.Const(1e-06))))),
        Limit_p_eps_setmax: ((Limit_p_eps_proc_selfix_17 * sym.heaviside(((yi - Limit_p_eps_y_lim) - sym.Const(1e-06)))) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_17) * sym.heaviside((((yi + Limit_p_eps_eps) - Limit_p_eps_y_lim) - sym.Const(1e-06))))),
        Limit_p_eps_rstmax: ((Limit_p_eps_proc_selfix_18 * sym.heaviside(((Limit_p_eps_y_lim - yi) - sym.Const(1e-06)))) + ((sym.Const(1.0) - Limit_p_eps_proc_selfix_18) * sym.heaviside(((Limit_p_eps_y_lim - (yi - Limit_p_eps_eps)) - sym.Const(1e-06))))),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Limit_p_eps_proc_select_const_0, source=(sym.heaviside((((-Limit_p_eps_y_lim) - (yi - Limit_p_eps_eps)) - 1e-06)) * sym.heaviside(((Limit_p_eps_eps - 0.0) - 1e-06)))),
        selfix((Limit_p_eps_eps <= 0.0), output=Limit_p_eps_proc_selfix_1),
        sampled_value(output=Limit_p_eps_proc_select_const_2, source=(sym.heaviside((((yi + Limit_p_eps_eps) - (-Limit_p_eps_y_lim)) - 1e-06)) * sym.heaviside(((Limit_p_eps_eps - 0.0) - 1e-06)))),
        selfix((Limit_p_eps_eps <= 0.0), output=Limit_p_eps_proc_selfix_3),
        sampled_value(output=Limit_p_eps_proc_select_const_4, source=(sym.heaviside((((yi + Limit_p_eps_eps) - Limit_p_eps_y_lim) - 1e-06)) * sym.heaviside(((Limit_p_eps_eps - 0.0) - 1e-06)))),
        selfix((Limit_p_eps_eps <= 0.0), output=Limit_p_eps_proc_selfix_5),
        sampled_value(output=Limit_p_eps_proc_select_const_6, source=(sym.heaviside(((Limit_p_eps_y_lim - (yi - Limit_p_eps_eps)) - 1e-06)) * sym.heaviside(((Limit_p_eps_eps - 0.0) - 1e-06)))),
        selfix((Limit_p_eps_eps <= 0.0), output=Limit_p_eps_proc_selfix_7),
        flipflop(Limit_p_eps_setmin, Limit_p_eps_rstmin, output=Limit_p_eps_proc_flipflop_8),
        selfix((Limit_p_eps_eps <= 0.0), output=Limit_p_eps_proc_selfix_9),
        flipflop(Limit_p_eps_setmax, Limit_p_eps_rstmax, output=Limit_p_eps_proc_flipflop_10),
        selfix((Limit_p_eps_eps <= 0.0), output=Limit_p_eps_proc_selfix_11),
        sampled_value(output=Limit_p_eps_proc_select_12, source=(sym.heaviside(((Limit_p_eps_yo_max - 0.5) - 1e-06)) * sym.heaviside(((Limit_p_eps_eps - 0.0) - 1e-06)))),
        sampled_value(output=Limit_p_eps_proc_select_13, source=(sym.heaviside(((Limit_p_eps_yo_min - 0.5) - 1e-06)) * sym.heaviside(((Limit_p_eps_eps - 0.0) - 1e-06)))),
        selfix((Limit_p_eps_eps <= 0.0), output=Limit_p_eps_proc_selfix_14),
        selfix((sym.heaviside((((-Limit_p_eps_y_lim) - (yi - Limit_p_eps_eps)) - 1e-06)) * sym.heaviside((((yi + Limit_p_eps_eps) - (-Limit_p_eps_y_lim)) - 1e-06))), output=Limit_p_eps_proc_selfix_15),
        selfix((sym.heaviside((((-Limit_p_eps_y_lim) - (yi - Limit_p_eps_eps)) - 1e-06)) * sym.heaviside((((yi + Limit_p_eps_eps) - (-Limit_p_eps_y_lim)) - 1e-06))), output=Limit_p_eps_proc_selfix_16),
        selfix((sym.heaviside((((yi + Limit_p_eps_eps) - Limit_p_eps_y_lim) - 1e-06)) * sym.heaviside(((Limit_p_eps_y_lim - (yi - Limit_p_eps_eps)) - 1e-06))), output=Limit_p_eps_proc_selfix_17),
        selfix((sym.heaviside((((yi + Limit_p_eps_eps) - Limit_p_eps_y_lim) - 1e-06)) * sym.heaviside(((Limit_p_eps_y_lim - (yi - Limit_p_eps_eps)) - 1e-06))), output=Limit_p_eps_proc_selfix_18),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_limit_p_eps_316_emt_template(vf=vf, name='Limit [p] _eps__316' if name is None else name)
