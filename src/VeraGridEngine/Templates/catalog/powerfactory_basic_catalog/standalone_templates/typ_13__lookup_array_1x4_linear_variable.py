# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_lookup_array_1x4_linear_variable_13_emt_template(vf: VarFactory, name: str = 'Lookup array 1x4 (linear_variable)__13') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Lookup_array_1x4_linear_variable_vClip = vf.add_var('Lookup array 1x4 (linear_variable)__vClip_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Lookup_array_1x4_linear_variable_proc_select_10 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_select_10_' + name)
    Lookup_array_1x4_linear_variable_proc_select_11 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_select_11_' + name)
    Lookup_array_1x4_linear_variable_proc_select_2 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_select_2_' + name)
    Lookup_array_1x4_linear_variable_proc_select_3 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_select_3_' + name)
    Lookup_array_1x4_linear_variable_proc_select_4 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_select_4_' + name)
    Lookup_array_1x4_linear_variable_proc_select_5 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_select_5_' + name)
    Lookup_array_1x4_linear_variable_proc_select_8 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_select_8_' + name)
    Lookup_array_1x4_linear_variable_proc_select_9 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_select_9_' + name)
    Lookup_array_1x4_linear_variable_proc_selfix_0 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_selfix_0_' + name)
    Lookup_array_1x4_linear_variable_proc_selfix_1 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_selfix_1_' + name)
    Lookup_array_1x4_linear_variable_proc_selfix_6 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_selfix_6_' + name)
    Lookup_array_1x4_linear_variable_proc_selfix_7 = vf.add_var('Lookup array 1x4 (linear_variable)__proc_selfix_7_' + name)
    Lookup_array_1x4_linear_variable_m = vf.add_var('Lookup array 1x4 (linear_variable)_m_' + name)
    Lookup_array_1x4_linear_variable_m1 = vf.add_var('Lookup array 1x4 (linear_variable)_m1_' + name)
    Lookup_array_1x4_linear_variable_m2 = vf.add_var('Lookup array 1x4 (linear_variable)_m2_' + name)
    Lookup_array_1x4_linear_variable_m3 = vf.add_var('Lookup array 1x4 (linear_variable)_m3_' + name)
    Lookup_array_1x4_linear_variable_n = vf.add_var('Lookup array 1x4 (linear_variable)_n_' + name)
    arr_x1 = vf.add_var('arr_x1_' + name)
    arr_x2 = vf.add_var('arr_x2_' + name)
    arr_x3 = vf.add_var('arr_x3_' + name)
    arr_x4 = vf.add_var('arr_x4_' + name)
    arr_y1 = vf.add_var('arr_y1_' + name)
    arr_y2 = vf.add_var('arr_y2_' + name)
    arr_y3 = vf.add_var('arr_y3_' + name)
    arr_y4 = vf.add_var('arr_y4_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Lookup_array_1x4_linear_variable_m1 - ((arr_y2 - arr_y1) / (arr_x2 - arr_x1))),
            (Lookup_array_1x4_linear_variable_m2 - ((arr_y3 - arr_y2) / (arr_x3 - arr_x2))),
            (Lookup_array_1x4_linear_variable_m3 - ((arr_y4 - arr_y3) / (arr_x4 - arr_x3))),
            (Lookup_array_1x4_linear_variable_m - ((Lookup_array_1x4_linear_variable_proc_select_5 * ((Lookup_array_1x4_linear_variable_proc_selfix_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_selfix_0) * Lookup_array_1x4_linear_variable_m1))) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_select_5) * ((Lookup_array_1x4_linear_variable_proc_select_4 * Lookup_array_1x4_linear_variable_m1) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_select_4) * ((Lookup_array_1x4_linear_variable_proc_select_3 * Lookup_array_1x4_linear_variable_m2) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_select_3) * ((Lookup_array_1x4_linear_variable_proc_select_2 * Lookup_array_1x4_linear_variable_m3) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_select_2) * ((Lookup_array_1x4_linear_variable_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_selfix_1) * Lookup_array_1x4_linear_variable_m3))))))))))),
            (Lookup_array_1x4_linear_variable_n - ((Lookup_array_1x4_linear_variable_proc_select_11 * ((Lookup_array_1x4_linear_variable_proc_selfix_6 * arr_y1) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_selfix_6) * (arr_y2 - (Lookup_array_1x4_linear_variable_m * arr_x2))))) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_select_11) * ((Lookup_array_1x4_linear_variable_proc_select_10 * (arr_y2 - (Lookup_array_1x4_linear_variable_m * arr_x2))) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_select_10) * ((Lookup_array_1x4_linear_variable_proc_select_9 * (arr_y3 - (Lookup_array_1x4_linear_variable_m * arr_x3))) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_select_9) * ((Lookup_array_1x4_linear_variable_proc_select_8 * (arr_y4 - (Lookup_array_1x4_linear_variable_m * arr_x4))) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_select_8) * ((Lookup_array_1x4_linear_variable_proc_selfix_7 * arr_y4) + ((sym.Const(1.0) - Lookup_array_1x4_linear_variable_proc_selfix_7) * (arr_y4 - (Lookup_array_1x4_linear_variable_m * arr_x4))))))))))))),
            (yo - ((Lookup_array_1x4_linear_variable_m * yi) + Lookup_array_1x4_linear_variable_n)),
        ],
        algebraic_vars=[Lookup_array_1x4_linear_variable_m1, Lookup_array_1x4_linear_variable_m2, Lookup_array_1x4_linear_variable_m3, Lookup_array_1x4_linear_variable_m, Lookup_array_1x4_linear_variable_n, yo],
        in_vars=[yi, arr_x1, arr_x2, arr_x3, arr_x4, arr_y1, arr_y2, arr_y3, arr_y4],
        out_vars=[yo],
        name='Lookup array 1x4 (linear_variable)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Lookup_array_1x4_linear_variable_vClip: vf.add_const(None, name='vClip'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Lookup_array_1x4_linear_variable_proc_selfix_0: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_selfix_1: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_select_2: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_select_3: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_select_4: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_select_5: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_selfix_6: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_selfix_7: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_select_8: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_select_9: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_select_10: vf.add_const(0.0, name=''),
        Lookup_array_1x4_linear_variable_proc_select_11: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Lookup_array_1x4_linear_variable_m1: ((arr_y2 - arr_y1) / (arr_x2 - arr_x1)),
        Lookup_array_1x4_linear_variable_m2: ((arr_y3 - arr_y2) / (arr_x3 - arr_x2)),
        Lookup_array_1x4_linear_variable_m3: ((arr_y4 - arr_y3) / (arr_x4 - arr_x3)),
    }
    templ.block.procedural_logic = [
        selfix(Lookup_array_1x4_linear_variable_vClip, output=Lookup_array_1x4_linear_variable_proc_selfix_0),
        selfix(Lookup_array_1x4_linear_variable_vClip, output=Lookup_array_1x4_linear_variable_proc_selfix_1),
        sampled_value(output=Lookup_array_1x4_linear_variable_proc_select_2, source=(yi < arr_x4)),
        sampled_value(output=Lookup_array_1x4_linear_variable_proc_select_3, source=(yi < arr_x3)),
        sampled_value(output=Lookup_array_1x4_linear_variable_proc_select_4, source=(yi < arr_x2)),
        sampled_value(output=Lookup_array_1x4_linear_variable_proc_select_5, source=(yi < arr_x1)),
        selfix(Lookup_array_1x4_linear_variable_vClip, output=Lookup_array_1x4_linear_variable_proc_selfix_6),
        selfix(Lookup_array_1x4_linear_variable_vClip, output=Lookup_array_1x4_linear_variable_proc_selfix_7),
        sampled_value(output=Lookup_array_1x4_linear_variable_proc_select_8, source=(yi < arr_x4)),
        sampled_value(output=Lookup_array_1x4_linear_variable_proc_select_9, source=(yi < arr_x3)),
        sampled_value(output=Lookup_array_1x4_linear_variable_proc_select_10, source=(yi < arr_x2)),
        sampled_value(output=Lookup_array_1x4_linear_variable_proc_select_11, source=(yi < arr_x1)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_lookup_array_1x4_linear_variable_13_emt_template(vf=vf, name='Lookup array 1x4 (linear_variable)__13' if name is None else name)
