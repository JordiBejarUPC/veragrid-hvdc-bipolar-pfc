# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import flipflop, sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_yi_less_than_c_eps_46_emt_template(vf: VarFactory, name: str = 'yi less than C _eps__46') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    yi_less_than_C_eps_C = vf.add_var('yi less than C _eps__C_' + name)
    yi_less_than_C_eps_eps = vf.add_var('yi less than C _eps__eps_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yi_less_than_C_eps_proc_flipflop_5 = vf.add_var('yi less than C _eps__proc_flipflop_5_' + name)
    yi_less_than_C_eps_proc_select_0 = vf.add_var('yi less than C _eps__proc_select_0_' + name)
    yi_less_than_C_eps_proc_select_2 = vf.add_var('yi less than C _eps__proc_select_2_' + name)
    yi_less_than_C_eps_proc_select_const_4 = vf.add_var('yi less than C _eps__proc_select_const_4_' + name)
    yi_less_than_C_eps_proc_selfix_1 = vf.add_var('yi less than C _eps__proc_selfix_1_' + name)
    yi_less_than_C_eps_proc_selfix_3 = vf.add_var('yi less than C _eps__proc_selfix_3_' + name)
    yi_less_than_C_eps_proc_selfix_6 = vf.add_var('yi less than C _eps__proc_selfix_6_' + name)
    yi_less_than_C_eps_proc_selfix_const_7 = vf.add_var('yi less than C _eps__proc_selfix_const_7_' + name)
    yi_less_than_C_eps_rst = vf.add_var('yi less than C _eps_rst_' + name)
    yi_less_than_C_eps_set = vf.add_var('yi less than C _eps_set_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yi_less_than_C_eps_set - ((yi_less_than_C_eps_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - yi_less_than_C_eps_proc_selfix_1) * ((yi_less_than_C_eps_proc_select_0 * sym.Const(1.0)) + ((sym.Const(1.0) - yi_less_than_C_eps_proc_select_0) * sym.Const(0.0)))))),
            (yi_less_than_C_eps_rst - ((yi_less_than_C_eps_proc_selfix_3 * sym.Const(0.0)) + ((sym.Const(1.0) - yi_less_than_C_eps_proc_selfix_3) * ((yi_less_than_C_eps_proc_select_2 * sym.Const(1.0)) + ((sym.Const(1.0) - yi_less_than_C_eps_proc_select_2) * sym.Const(0.0)))))),
            (yo - ((yi_less_than_C_eps_proc_selfix_6 * ((yi_less_than_C_eps_proc_select_const_4 * sym.Const(1.0)) + ((sym.Const(1.0) - yi_less_than_C_eps_proc_select_const_4) * sym.Const(0.0)))) + ((sym.Const(1.0) - yi_less_than_C_eps_proc_selfix_6) * yi_less_than_C_eps_proc_flipflop_5))),
        ],
        algebraic_vars=[yi_less_than_C_eps_set, yi_less_than_C_eps_rst, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='yi less than C _eps'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        yi_less_than_C_eps_C: vf.add_const(None, name='C'),
        yi_less_than_C_eps_eps: vf.add_const(None, name='eps'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        yi_less_than_C_eps_proc_select_0: vf.add_const(0.0, name=''),
        yi_less_than_C_eps_proc_selfix_1: vf.add_const(0.0, name=''),
        yi_less_than_C_eps_proc_select_2: vf.add_const(0.0, name=''),
        yi_less_than_C_eps_proc_selfix_3: vf.add_const(0.0, name=''),
        yi_less_than_C_eps_proc_select_const_4: vf.add_const(0.0, name=''),
        yi_less_than_C_eps_proc_flipflop_5: vf.add_const(0.0, name=''),
        yi_less_than_C_eps_proc_selfix_6: vf.add_const(0.0, name=''),
        yi_less_than_C_eps_proc_selfix_const_7: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yi_less_than_C_eps_set: ((yi_less_than_C_eps_proc_selfix_const_7 * sym.Const(1.0)) + ((sym.Const(1.0) - yi_less_than_C_eps_proc_selfix_const_7) * sym.Const(0.0))),
        yi_less_than_C_eps_rst: (sym.Const(1.0) - yi_less_than_C_eps_set),
    }
    templ.block.procedural_logic = [
        sampled_value(output=yi_less_than_C_eps_proc_select_0, source=(sym.heaviside(((yi_less_than_C_eps_C - (yi + yi_less_than_C_eps_eps)) - 1e-06)) * sym.heaviside(((yi_less_than_C_eps_eps - 0.0) - 1e-06)))),
        selfix((yi_less_than_C_eps_eps <= 0.0), output=yi_less_than_C_eps_proc_selfix_1),
        sampled_value(output=yi_less_than_C_eps_proc_select_2, source=(sym.heaviside((((yi - yi_less_than_C_eps_eps) - yi_less_than_C_eps_C) - 1e-06)) * sym.heaviside(((yi_less_than_C_eps_eps - 0.0) - 1e-06)))),
        selfix((yi_less_than_C_eps_eps <= 0.0), output=yi_less_than_C_eps_proc_selfix_3),
        sampled_value(output=yi_less_than_C_eps_proc_select_const_4, source=(sym.heaviside(((yi_less_than_C_eps_C - yi) - 1e-06)) * sym.heaviside(((0.0 - yi_less_than_C_eps_eps) + 1e-06)))),
        flipflop(yi_less_than_C_eps_set, yi_less_than_C_eps_rst, output=yi_less_than_C_eps_proc_flipflop_5),
        selfix((yi_less_than_C_eps_eps <= 0.0), output=yi_less_than_C_eps_proc_selfix_6),
        selfix(((yi + yi_less_than_C_eps_eps) < yi_less_than_C_eps_C), output=yi_less_than_C_eps_proc_selfix_const_7),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_yi_less_than_c_eps_46_emt_template(vf=vf, name='yi less than C _eps__46' if name is None else name)
