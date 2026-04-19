# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_butterworth_2nd_order_rst_hold_160_emt_template(vf: VarFactory, name: str = 'Butterworth 2nd order _rst_hold__160') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Butterworth_2nd_order_rst_hold_wc = vf.add_var('Butterworth 2nd order _rst_hold__wc_' + name)

    # --- State Variables ---
    Butterworth_2nd_order_rst_hold_x1 = vf.add_var('Butterworth 2nd order _rst_hold__x1_' + name)
    Butterworth_2nd_order_rst_hold_x2 = vf.add_var('Butterworth 2nd order _rst_hold__x2_' + name)

    # --- Algebraic / Shared Variables ---
    Butterworth_2nd_order_rst_hold_proc_lastvalue_2 = vf.add_var('Butterworth 2nd order _rst_hold__proc_lastvalue_2_' + name)
    Butterworth_2nd_order_rst_hold_proc_select_0 = vf.add_var('Butterworth 2nd order _rst_hold__proc_select_0_' + name)
    Butterworth_2nd_order_rst_hold_proc_select_1 = vf.add_var('Butterworth 2nd order _rst_hold__proc_select_1_' + name)
    Butterworth_2nd_order_rst_hold_proc_select_3 = vf.add_var('Butterworth 2nd order _rst_hold__proc_select_3_' + name)
    Butterworth_2nd_order_rst_hold_wc_2 = vf.add_var('Butterworth 2nd order _rst_hold_wc_2_' + name)
    Butterworth_2nd_order_rst_hold_x1_init = vf.add_var('Butterworth 2nd order _rst_hold_x1_init_' + name)
    hold = vf.add_var('hold_' + name)
    rst = vf.add_var('rst_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Butterworth_2nd_order_rst_hold_x1 = vf.add_diff_var('d_Butterworth 2nd order _rst_hold__x1_' + name, base_var=Butterworth_2nd_order_rst_hold_x1)
    d_Butterworth_2nd_order_rst_hold_x2 = vf.add_diff_var('d_Butterworth 2nd order _rst_hold__x2_' + name, base_var=Butterworth_2nd_order_rst_hold_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Butterworth_2nd_order_rst_hold_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Butterworth_2nd_order_rst_hold_proc_select_0) * Butterworth_2nd_order_rst_hold_x2)),
            ((Butterworth_2nd_order_rst_hold_proc_select_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Butterworth_2nd_order_rst_hold_proc_select_1) * ((((-Butterworth_2nd_order_rst_hold_wc_2) * Butterworth_2nd_order_rst_hold_x1) - ((sym.Const(1.414) * Butterworth_2nd_order_rst_hold_wc) * Butterworth_2nd_order_rst_hold_x2)) + yi))),
        ],
        state_vars=[Butterworth_2nd_order_rst_hold_x1, Butterworth_2nd_order_rst_hold_x2],
        algebraic_eqs=[
            (yo - ((Butterworth_2nd_order_rst_hold_proc_select_3 * Butterworth_2nd_order_rst_hold_proc_lastvalue_2) + ((sym.Const(1.0) - Butterworth_2nd_order_rst_hold_proc_select_3) * (Butterworth_2nd_order_rst_hold_wc_2 * Butterworth_2nd_order_rst_hold_x1)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, hold, rst],
        out_vars=[yo],
        name='Butterworth 2nd order _rst_hold'
    )
    templ.block.diff_vars = [d_Butterworth_2nd_order_rst_hold_x1, d_Butterworth_2nd_order_rst_hold_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Butterworth_2nd_order_rst_hold_wc: vf.add_const(None, name='wc'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Butterworth_2nd_order_rst_hold_proc_select_0: vf.add_const(0.0, name=''),
        Butterworth_2nd_order_rst_hold_proc_select_1: vf.add_const(0.0, name=''),
        Butterworth_2nd_order_rst_hold_proc_lastvalue_2: vf.add_const(0.0, name=''),
        Butterworth_2nd_order_rst_hold_proc_select_3: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Butterworth_2nd_order_rst_hold_wc_2: (Butterworth_2nd_order_rst_hold_wc * Butterworth_2nd_order_rst_hold_wc),
        Butterworth_2nd_order_rst_hold_x1: (yi / Butterworth_2nd_order_rst_hold_wc_2),
        Butterworth_2nd_order_rst_hold_x2: vf.add_const(0.0, name=''),
        Butterworth_2nd_order_rst_hold_x1_init: Butterworth_2nd_order_rst_hold_x1,
    }
    templ.block.procedural_logic = [
        sampled_value(output=Butterworth_2nd_order_rst_hold_proc_select_0, source=hold),
        sampled_value(output=Butterworth_2nd_order_rst_hold_proc_select_1, source=hold),
        lastvalue(yo, output=Butterworth_2nd_order_rst_hold_proc_lastvalue_2),
        sampled_value(output=Butterworth_2nd_order_rst_hold_proc_select_3, source=hold),
        reset(Butterworth_2nd_order_rst_hold_x1, rst, Butterworth_2nd_order_rst_hold_x1_init),
        reset(Butterworth_2nd_order_rst_hold_x2, rst, 0.0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_butterworth_2nd_order_rst_hold_160_emt_template(vf=vf, name='Butterworth 2nd order _rst_hold__160' if name is None else name)
