# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_enable_3_sig_hold_495_emt_template(vf: VarFactory, name: str = 'Enable 3 sig _hold__495') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable = vf.add_var('Enable_' + name)
    Enable_3_sig_hold_proc_lastvalue_0 = vf.add_var('Enable 3 sig _hold__proc_lastvalue_0_' + name)
    Enable_3_sig_hold_proc_lastvalue_2 = vf.add_var('Enable 3 sig _hold__proc_lastvalue_2_' + name)
    Enable_3_sig_hold_proc_lastvalue_4 = vf.add_var('Enable 3 sig _hold__proc_lastvalue_4_' + name)
    Enable_3_sig_hold_proc_select_1 = vf.add_var('Enable 3 sig _hold__proc_select_1_' + name)
    Enable_3_sig_hold_proc_select_3 = vf.add_var('Enable 3 sig _hold__proc_select_3_' + name)
    Enable_3_sig_hold_proc_select_5 = vf.add_var('Enable 3 sig _hold__proc_select_5_' + name)
    Enable_3_sig_hold_yi1_register = vf.add_var('Enable 3 sig _hold_yi1_register_' + name)
    Enable_3_sig_hold_yi2_register = vf.add_var('Enable 3 sig _hold_yi2_register_' + name)
    Enable_3_sig_hold_yi3_register = vf.add_var('Enable 3 sig _hold_yi3_register_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yi3 = vf.add_var('yi3_' + name)
    yo1 = vf.add_var('yo1_' + name)
    yo2 = vf.add_var('yo2_' + name)
    yo3 = vf.add_var('yo3_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo1 - Enable_3_sig_hold_yi1_register),
            (yo2 - Enable_3_sig_hold_yi2_register),
            (yo3 - Enable_3_sig_hold_yi3_register),
            (Enable_3_sig_hold_yi1_register - ((Enable_3_sig_hold_proc_select_1 * yi1) + ((sym.Const(1.0) - Enable_3_sig_hold_proc_select_1) * Enable_3_sig_hold_proc_lastvalue_0))),
            (Enable_3_sig_hold_yi2_register - ((Enable_3_sig_hold_proc_select_3 * yi2) + ((sym.Const(1.0) - Enable_3_sig_hold_proc_select_3) * Enable_3_sig_hold_proc_lastvalue_2))),
            (Enable_3_sig_hold_yi3_register - ((Enable_3_sig_hold_proc_select_5 * yi3) + ((sym.Const(1.0) - Enable_3_sig_hold_proc_select_5) * Enable_3_sig_hold_proc_lastvalue_4))),
        ],
        algebraic_vars=[yo1, yo2, yo3, Enable_3_sig_hold_yi1_register, Enable_3_sig_hold_yi2_register, Enable_3_sig_hold_yi3_register],
        in_vars=[yi1, yi2, yi3, Enable],
        out_vars=[yo1, yo2, yo3],
        name='Enable 3 sig _hold'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_3_sig_hold_proc_lastvalue_0: vf.add_const(0.0, name=''),
        Enable_3_sig_hold_proc_select_1: vf.add_const(0.0, name=''),
        Enable_3_sig_hold_proc_lastvalue_2: vf.add_const(0.0, name=''),
        Enable_3_sig_hold_proc_select_3: vf.add_const(0.0, name=''),
        Enable_3_sig_hold_proc_lastvalue_4: vf.add_const(0.0, name=''),
        Enable_3_sig_hold_proc_select_5: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Enable_3_sig_hold_yi1_register: yi1,
        Enable_3_sig_hold_yi2_register: yi2,
        Enable_3_sig_hold_yi3_register: yi3,
    }
    templ.block.procedural_logic = [
        lastvalue(Enable_3_sig_hold_yi1_register, output=Enable_3_sig_hold_proc_lastvalue_0),
        sampled_value(output=Enable_3_sig_hold_proc_select_1, source=Enable),
        lastvalue(Enable_3_sig_hold_yi2_register, output=Enable_3_sig_hold_proc_lastvalue_2),
        sampled_value(output=Enable_3_sig_hold_proc_select_3, source=Enable),
        lastvalue(Enable_3_sig_hold_yi3_register, output=Enable_3_sig_hold_proc_lastvalue_4),
        sampled_value(output=Enable_3_sig_hold_proc_select_5, source=Enable),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_3_sig_hold_495_emt_template(vf=vf, name='Enable 3 sig _hold__495' if name is None else name)
