# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import flipflop, sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_yi1_greater_than_yi2_eps_47_emt_template(vf: VarFactory, name: str = 'yi1 greater than yi2 _eps__47') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    yi1_greater_than_yi2_eps_eps = vf.add_var('yi1 greater than yi2 _eps__eps_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi1 = vf.add_var('yi1_' + name)
    yi1_greater_than_yi2_eps_proc_flipflop_5 = vf.add_var('yi1 greater than yi2 _eps__proc_flipflop_5_' + name)
    yi1_greater_than_yi2_eps_proc_select_const_0 = vf.add_var('yi1 greater than yi2 _eps__proc_select_const_0_' + name)
    yi1_greater_than_yi2_eps_proc_select_const_2 = vf.add_var('yi1 greater than yi2 _eps__proc_select_const_2_' + name)
    yi1_greater_than_yi2_eps_proc_select_const_4 = vf.add_var('yi1 greater than yi2 _eps__proc_select_const_4_' + name)
    yi1_greater_than_yi2_eps_proc_selfix_1 = vf.add_var('yi1 greater than yi2 _eps__proc_selfix_1_' + name)
    yi1_greater_than_yi2_eps_proc_selfix_3 = vf.add_var('yi1 greater than yi2 _eps__proc_selfix_3_' + name)
    yi1_greater_than_yi2_eps_proc_selfix_6 = vf.add_var('yi1 greater than yi2 _eps__proc_selfix_6_' + name)
    yi1_greater_than_yi2_eps_proc_selfix_const_7 = vf.add_var('yi1 greater than yi2 _eps__proc_selfix_const_7_' + name)
    yi1_greater_than_yi2_eps_rst = vf.add_var('yi1 greater than yi2 _eps_rst_' + name)
    yi1_greater_than_yi2_eps_set = vf.add_var('yi1 greater than yi2 _eps_set_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yi1_greater_than_yi2_eps_set - ((yi1_greater_than_yi2_eps_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - yi1_greater_than_yi2_eps_proc_selfix_1) * ((yi1_greater_than_yi2_eps_proc_select_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - yi1_greater_than_yi2_eps_proc_select_const_0) * sym.Const(0.0)))))),
            (yi1_greater_than_yi2_eps_rst - ((yi1_greater_than_yi2_eps_proc_selfix_3 * sym.Const(0.0)) + ((sym.Const(1.0) - yi1_greater_than_yi2_eps_proc_selfix_3) * ((yi1_greater_than_yi2_eps_proc_select_const_2 * sym.Const(1.0)) + ((sym.Const(1.0) - yi1_greater_than_yi2_eps_proc_select_const_2) * sym.Const(0.0)))))),
            (yo - ((yi1_greater_than_yi2_eps_proc_selfix_6 * ((yi1_greater_than_yi2_eps_proc_select_const_4 * sym.Const(1.0)) + ((sym.Const(1.0) - yi1_greater_than_yi2_eps_proc_select_const_4) * sym.Const(0.0)))) + ((sym.Const(1.0) - yi1_greater_than_yi2_eps_proc_selfix_6) * yi1_greater_than_yi2_eps_proc_flipflop_5))),
        ],
        algebraic_vars=[yi1_greater_than_yi2_eps_set, yi1_greater_than_yi2_eps_rst, yo],
        in_vars=[yi1, yi2],
        out_vars=[yo],
        name='yi1 greater than yi2 _eps'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        yi1_greater_than_yi2_eps_eps: vf.add_const(None, name='eps'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        yi1_greater_than_yi2_eps_proc_select_const_0: vf.add_const(0.0, name=''),
        yi1_greater_than_yi2_eps_proc_selfix_1: vf.add_const(0.0, name=''),
        yi1_greater_than_yi2_eps_proc_select_const_2: vf.add_const(0.0, name=''),
        yi1_greater_than_yi2_eps_proc_selfix_3: vf.add_const(0.0, name=''),
        yi1_greater_than_yi2_eps_proc_select_const_4: vf.add_const(0.0, name=''),
        yi1_greater_than_yi2_eps_proc_flipflop_5: vf.add_const(0.0, name=''),
        yi1_greater_than_yi2_eps_proc_selfix_6: vf.add_const(0.0, name=''),
        yi1_greater_than_yi2_eps_proc_selfix_const_7: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yi1_greater_than_yi2_eps_set: ((yi1_greater_than_yi2_eps_proc_selfix_const_7 * sym.Const(1.0)) + ((sym.Const(1.0) - yi1_greater_than_yi2_eps_proc_selfix_const_7) * sym.Const(0.0))),
        yi1_greater_than_yi2_eps_rst: (sym.Const(1.0) - yi1_greater_than_yi2_eps_set),
    }
    templ.block.procedural_logic = [
        sampled_value(output=yi1_greater_than_yi2_eps_proc_select_const_0, source=(sym.heaviside((((yi1 - yi1_greater_than_yi2_eps_eps) - yi2) - 1e-06)) * sym.heaviside(((yi1_greater_than_yi2_eps_eps - 0.0) - 1e-06)))),
        selfix((yi1_greater_than_yi2_eps_eps <= 0.0), output=yi1_greater_than_yi2_eps_proc_selfix_1),
        sampled_value(output=yi1_greater_than_yi2_eps_proc_select_const_2, source=(sym.heaviside(((yi2 - (yi1 + yi1_greater_than_yi2_eps_eps)) - 1e-06)) * sym.heaviside(((yi1_greater_than_yi2_eps_eps - 0.0) - 1e-06)))),
        selfix((yi1_greater_than_yi2_eps_eps <= 0.0), output=yi1_greater_than_yi2_eps_proc_selfix_3),
        sampled_value(output=yi1_greater_than_yi2_eps_proc_select_const_4, source=(sym.heaviside(((yi1 - yi2) - 1e-06)) * sym.heaviside(((0.0 - yi1_greater_than_yi2_eps_eps) + 1e-06)))),
        flipflop(yi1_greater_than_yi2_eps_set, yi1_greater_than_yi2_eps_rst, output=yi1_greater_than_yi2_eps_proc_flipflop_5),
        selfix((yi1_greater_than_yi2_eps_eps <= 0.0), output=yi1_greater_than_yi2_eps_proc_selfix_6),
        selfix(((yi1 - yi1_greater_than_yi2_eps_eps) > yi2), output=yi1_greater_than_yi2_eps_proc_selfix_const_7),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_yi1_greater_than_yi2_eps_47_emt_template(vf=vf, name='yi1 greater than yi2 _eps__47' if name is None else name)
