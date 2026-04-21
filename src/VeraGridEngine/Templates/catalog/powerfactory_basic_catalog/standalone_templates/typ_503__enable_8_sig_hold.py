# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_enable_8_sig_hold_503_emt_template(vf: VarFactory, name: str = 'Enable 8 sig _hold__503') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable = vf.add_var('Enable_' + name)
    Enable_8_sig_hold_proc_lastvalue_0 = vf.add_var('Enable 8 sig _hold__proc_lastvalue_0_' + name)
    Enable_8_sig_hold_proc_lastvalue_10 = vf.add_var('Enable 8 sig _hold__proc_lastvalue_10_' + name)
    Enable_8_sig_hold_proc_lastvalue_12 = vf.add_var('Enable 8 sig _hold__proc_lastvalue_12_' + name)
    Enable_8_sig_hold_proc_lastvalue_14 = vf.add_var('Enable 8 sig _hold__proc_lastvalue_14_' + name)
    Enable_8_sig_hold_proc_lastvalue_2 = vf.add_var('Enable 8 sig _hold__proc_lastvalue_2_' + name)
    Enable_8_sig_hold_proc_lastvalue_4 = vf.add_var('Enable 8 sig _hold__proc_lastvalue_4_' + name)
    Enable_8_sig_hold_proc_lastvalue_6 = vf.add_var('Enable 8 sig _hold__proc_lastvalue_6_' + name)
    Enable_8_sig_hold_proc_lastvalue_8 = vf.add_var('Enable 8 sig _hold__proc_lastvalue_8_' + name)
    Enable_8_sig_hold_proc_select_1 = vf.add_var('Enable 8 sig _hold__proc_select_1_' + name)
    Enable_8_sig_hold_proc_select_11 = vf.add_var('Enable 8 sig _hold__proc_select_11_' + name)
    Enable_8_sig_hold_proc_select_13 = vf.add_var('Enable 8 sig _hold__proc_select_13_' + name)
    Enable_8_sig_hold_proc_select_15 = vf.add_var('Enable 8 sig _hold__proc_select_15_' + name)
    Enable_8_sig_hold_proc_select_3 = vf.add_var('Enable 8 sig _hold__proc_select_3_' + name)
    Enable_8_sig_hold_proc_select_5 = vf.add_var('Enable 8 sig _hold__proc_select_5_' + name)
    Enable_8_sig_hold_proc_select_7 = vf.add_var('Enable 8 sig _hold__proc_select_7_' + name)
    Enable_8_sig_hold_proc_select_9 = vf.add_var('Enable 8 sig _hold__proc_select_9_' + name)
    Enable_8_sig_hold_yi1_register = vf.add_var('Enable 8 sig _hold_yi1_register_' + name)
    Enable_8_sig_hold_yi2_register = vf.add_var('Enable 8 sig _hold_yi2_register_' + name)
    Enable_8_sig_hold_yi3_register = vf.add_var('Enable 8 sig _hold_yi3_register_' + name)
    Enable_8_sig_hold_yi4_register = vf.add_var('Enable 8 sig _hold_yi4_register_' + name)
    Enable_8_sig_hold_yi5_register = vf.add_var('Enable 8 sig _hold_yi5_register_' + name)
    Enable_8_sig_hold_yi6_register = vf.add_var('Enable 8 sig _hold_yi6_register_' + name)
    Enable_8_sig_hold_yi7_register = vf.add_var('Enable 8 sig _hold_yi7_register_' + name)
    Enable_8_sig_hold_yi8_register = vf.add_var('Enable 8 sig _hold_yi8_register_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yi3 = vf.add_var('yi3_' + name)
    yi4 = vf.add_var('yi4_' + name)
    yi5 = vf.add_var('yi5_' + name)
    yi6 = vf.add_var('yi6_' + name)
    yi7 = vf.add_var('yi7_' + name)
    yi8 = vf.add_var('yi8_' + name)
    yo1 = vf.add_var('yo1_' + name)
    yo2 = vf.add_var('yo2_' + name)
    yo3 = vf.add_var('yo3_' + name)
    yo4 = vf.add_var('yo4_' + name)
    yo5 = vf.add_var('yo5_' + name)
    yo6 = vf.add_var('yo6_' + name)
    yo7 = vf.add_var('yo7_' + name)
    yo8 = vf.add_var('yo8_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo1 - Enable_8_sig_hold_yi1_register),
            (yo2 - Enable_8_sig_hold_yi2_register),
            (yo3 - Enable_8_sig_hold_yi3_register),
            (yo4 - Enable_8_sig_hold_yi4_register),
            (yo5 - Enable_8_sig_hold_yi5_register),
            (yo6 - Enable_8_sig_hold_yi6_register),
            (yo7 - Enable_8_sig_hold_yi7_register),
            (yo8 - Enable_8_sig_hold_yi8_register),
            (Enable_8_sig_hold_yi1_register - ((Enable_8_sig_hold_proc_select_1 * yi1) + ((sym.Const(1.0) - Enable_8_sig_hold_proc_select_1) * Enable_8_sig_hold_proc_lastvalue_0))),
            (Enable_8_sig_hold_yi2_register - ((Enable_8_sig_hold_proc_select_3 * yi2) + ((sym.Const(1.0) - Enable_8_sig_hold_proc_select_3) * Enable_8_sig_hold_proc_lastvalue_2))),
            (Enable_8_sig_hold_yi3_register - ((Enable_8_sig_hold_proc_select_5 * yi3) + ((sym.Const(1.0) - Enable_8_sig_hold_proc_select_5) * Enable_8_sig_hold_proc_lastvalue_4))),
            (Enable_8_sig_hold_yi4_register - ((Enable_8_sig_hold_proc_select_7 * yi4) + ((sym.Const(1.0) - Enable_8_sig_hold_proc_select_7) * Enable_8_sig_hold_proc_lastvalue_6))),
            (Enable_8_sig_hold_yi5_register - ((Enable_8_sig_hold_proc_select_9 * yi5) + ((sym.Const(1.0) - Enable_8_sig_hold_proc_select_9) * Enable_8_sig_hold_proc_lastvalue_8))),
            (Enable_8_sig_hold_yi6_register - ((Enable_8_sig_hold_proc_select_11 * yi6) + ((sym.Const(1.0) - Enable_8_sig_hold_proc_select_11) * Enable_8_sig_hold_proc_lastvalue_10))),
            (Enable_8_sig_hold_yi7_register - ((Enable_8_sig_hold_proc_select_13 * yi7) + ((sym.Const(1.0) - Enable_8_sig_hold_proc_select_13) * Enable_8_sig_hold_proc_lastvalue_12))),
            (Enable_8_sig_hold_yi8_register - ((Enable_8_sig_hold_proc_select_15 * yi8) + ((sym.Const(1.0) - Enable_8_sig_hold_proc_select_15) * Enable_8_sig_hold_proc_lastvalue_14))),
        ],
        algebraic_vars=[yo1, yo2, yo3, yo4, yo5, yo6, yo7, yo8, Enable_8_sig_hold_yi1_register, Enable_8_sig_hold_yi2_register, Enable_8_sig_hold_yi3_register, Enable_8_sig_hold_yi4_register, Enable_8_sig_hold_yi5_register, Enable_8_sig_hold_yi6_register, Enable_8_sig_hold_yi7_register, Enable_8_sig_hold_yi8_register],
        in_vars=[yi1, yi2, yi3, yi4, yi5, yi6, yi7, yi8, Enable],
        out_vars=[yo1, yo2, yo3, yo4, yo5, yo6, yo7, yo8],
        name='Enable 8 sig _hold'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_8_sig_hold_proc_lastvalue_0: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_select_1: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_lastvalue_2: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_select_3: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_lastvalue_4: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_select_5: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_lastvalue_6: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_select_7: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_lastvalue_8: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_select_9: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_lastvalue_10: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_select_11: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_lastvalue_12: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_select_13: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_lastvalue_14: vf.add_const(0.0, name=''),
        Enable_8_sig_hold_proc_select_15: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Enable_8_sig_hold_yi1_register: yi1,
        Enable_8_sig_hold_yi2_register: yi2,
        Enable_8_sig_hold_yi3_register: yi3,
        Enable_8_sig_hold_yi4_register: yi4,
        Enable_8_sig_hold_yi5_register: yi5,
        Enable_8_sig_hold_yi6_register: yi6,
        Enable_8_sig_hold_yi7_register: yi7,
        Enable_8_sig_hold_yi8_register: yi8,
    }
    templ.block.procedural_logic = [
        lastvalue(Enable_8_sig_hold_yi1_register, output=Enable_8_sig_hold_proc_lastvalue_0),
        sampled_value(output=Enable_8_sig_hold_proc_select_1, source=Enable),
        lastvalue(Enable_8_sig_hold_yi2_register, output=Enable_8_sig_hold_proc_lastvalue_2),
        sampled_value(output=Enable_8_sig_hold_proc_select_3, source=Enable),
        lastvalue(Enable_8_sig_hold_yi3_register, output=Enable_8_sig_hold_proc_lastvalue_4),
        sampled_value(output=Enable_8_sig_hold_proc_select_5, source=Enable),
        lastvalue(Enable_8_sig_hold_yi4_register, output=Enable_8_sig_hold_proc_lastvalue_6),
        sampled_value(output=Enable_8_sig_hold_proc_select_7, source=Enable),
        lastvalue(Enable_8_sig_hold_yi5_register, output=Enable_8_sig_hold_proc_lastvalue_8),
        sampled_value(output=Enable_8_sig_hold_proc_select_9, source=Enable),
        lastvalue(Enable_8_sig_hold_yi6_register, output=Enable_8_sig_hold_proc_lastvalue_10),
        sampled_value(output=Enable_8_sig_hold_proc_select_11, source=Enable),
        lastvalue(Enable_8_sig_hold_yi7_register, output=Enable_8_sig_hold_proc_lastvalue_12),
        sampled_value(output=Enable_8_sig_hold_proc_select_13, source=Enable),
        lastvalue(Enable_8_sig_hold_yi8_register, output=Enable_8_sig_hold_proc_lastvalue_14),
        sampled_value(output=Enable_8_sig_hold_proc_select_15, source=Enable),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_8_sig_hold_503_emt_template(vf=vf, name='Enable 8 sig _hold__503' if name is None else name)
