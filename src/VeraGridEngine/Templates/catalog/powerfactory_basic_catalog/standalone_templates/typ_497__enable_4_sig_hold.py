# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_enable_4_sig_hold_497_emt_template(vf: VarFactory, name: str = 'Enable 4 sig _hold__497') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable = vf.add_var('Enable_' + name)
    Enable_4_sig_hold_proc_lastvalue_0 = vf.add_var('Enable 4 sig _hold__proc_lastvalue_0_' + name)
    Enable_4_sig_hold_proc_lastvalue_2 = vf.add_var('Enable 4 sig _hold__proc_lastvalue_2_' + name)
    Enable_4_sig_hold_proc_lastvalue_4 = vf.add_var('Enable 4 sig _hold__proc_lastvalue_4_' + name)
    Enable_4_sig_hold_proc_lastvalue_6 = vf.add_var('Enable 4 sig _hold__proc_lastvalue_6_' + name)
    Enable_4_sig_hold_proc_select_1 = vf.add_var('Enable 4 sig _hold__proc_select_1_' + name)
    Enable_4_sig_hold_proc_select_3 = vf.add_var('Enable 4 sig _hold__proc_select_3_' + name)
    Enable_4_sig_hold_proc_select_5 = vf.add_var('Enable 4 sig _hold__proc_select_5_' + name)
    Enable_4_sig_hold_proc_select_7 = vf.add_var('Enable 4 sig _hold__proc_select_7_' + name)
    Enable_4_sig_hold_yi1_register = vf.add_var('Enable 4 sig _hold_yi1_register_' + name)
    Enable_4_sig_hold_yi2_register = vf.add_var('Enable 4 sig _hold_yi2_register_' + name)
    Enable_4_sig_hold_yi3_register = vf.add_var('Enable 4 sig _hold_yi3_register_' + name)
    Enable_4_sig_hold_yi4_register = vf.add_var('Enable 4 sig _hold_yi4_register_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yi3 = vf.add_var('yi3_' + name)
    yi4 = vf.add_var('yi4_' + name)
    yo1 = vf.add_var('yo1_' + name)
    yo2 = vf.add_var('yo2_' + name)
    yo3 = vf.add_var('yo3_' + name)
    yo4 = vf.add_var('yo4_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo1 - Enable_4_sig_hold_yi1_register),
            (yo2 - Enable_4_sig_hold_yi2_register),
            (yo3 - Enable_4_sig_hold_yi3_register),
            (yo4 - Enable_4_sig_hold_yi4_register),
            (Enable_4_sig_hold_yi1_register - ((Enable_4_sig_hold_proc_select_1 * yi1) + ((sym.Const(1.0) - Enable_4_sig_hold_proc_select_1) * Enable_4_sig_hold_proc_lastvalue_0))),
            (Enable_4_sig_hold_yi2_register - ((Enable_4_sig_hold_proc_select_3 * yi2) + ((sym.Const(1.0) - Enable_4_sig_hold_proc_select_3) * Enable_4_sig_hold_proc_lastvalue_2))),
            (Enable_4_sig_hold_yi3_register - ((Enable_4_sig_hold_proc_select_5 * yi3) + ((sym.Const(1.0) - Enable_4_sig_hold_proc_select_5) * Enable_4_sig_hold_proc_lastvalue_4))),
            (Enable_4_sig_hold_yi4_register - ((Enable_4_sig_hold_proc_select_7 * yi4) + ((sym.Const(1.0) - Enable_4_sig_hold_proc_select_7) * Enable_4_sig_hold_proc_lastvalue_6))),
        ],
        algebraic_vars=[yo1, yo2, yo3, yo4, Enable_4_sig_hold_yi1_register, Enable_4_sig_hold_yi2_register, Enable_4_sig_hold_yi3_register, Enable_4_sig_hold_yi4_register],
        in_vars=[yi1, yi2, yi3, yi4, Enable],
        out_vars=[yo1, yo2, yo3, yo4],
        name='Enable 4 sig _hold'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_4_sig_hold_proc_lastvalue_0: vf.add_const(0.0, name=''),
        Enable_4_sig_hold_proc_select_1: vf.add_const(0.0, name=''),
        Enable_4_sig_hold_proc_lastvalue_2: vf.add_const(0.0, name=''),
        Enable_4_sig_hold_proc_select_3: vf.add_const(0.0, name=''),
        Enable_4_sig_hold_proc_lastvalue_4: vf.add_const(0.0, name=''),
        Enable_4_sig_hold_proc_select_5: vf.add_const(0.0, name=''),
        Enable_4_sig_hold_proc_lastvalue_6: vf.add_const(0.0, name=''),
        Enable_4_sig_hold_proc_select_7: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Enable_4_sig_hold_yi1_register: yi1,
        Enable_4_sig_hold_yi2_register: yi2,
        Enable_4_sig_hold_yi3_register: yi3,
        Enable_4_sig_hold_yi4_register: yi4,
    }
    templ.block.procedural_logic = [
        lastvalue(Enable_4_sig_hold_yi1_register, output=Enable_4_sig_hold_proc_lastvalue_0),
        sampled_value(output=Enable_4_sig_hold_proc_select_1, source=Enable),
        lastvalue(Enable_4_sig_hold_yi2_register, output=Enable_4_sig_hold_proc_lastvalue_2),
        sampled_value(output=Enable_4_sig_hold_proc_select_3, source=Enable),
        lastvalue(Enable_4_sig_hold_yi3_register, output=Enable_4_sig_hold_proc_lastvalue_4),
        sampled_value(output=Enable_4_sig_hold_proc_select_5, source=Enable),
        lastvalue(Enable_4_sig_hold_yi4_register, output=Enable_4_sig_hold_proc_lastvalue_6),
        sampled_value(output=Enable_4_sig_hold_proc_select_7, source=Enable),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_4_sig_hold_497_emt_template(vf=vf, name='Enable 4 sig _hold__497' if name is None else name)
