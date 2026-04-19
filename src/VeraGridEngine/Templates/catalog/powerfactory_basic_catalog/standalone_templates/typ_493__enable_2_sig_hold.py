# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_enable_2_sig_hold_493_emt_template(vf: VarFactory, name: str = 'Enable 2 sig _hold__493') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable = vf.add_var('Enable_' + name)
    Enable_2_sig_hold_proc_lastvalue_0 = vf.add_var('Enable 2 sig _hold__proc_lastvalue_0_' + name)
    Enable_2_sig_hold_proc_lastvalue_2 = vf.add_var('Enable 2 sig _hold__proc_lastvalue_2_' + name)
    Enable_2_sig_hold_proc_select_1 = vf.add_var('Enable 2 sig _hold__proc_select_1_' + name)
    Enable_2_sig_hold_proc_select_3 = vf.add_var('Enable 2 sig _hold__proc_select_3_' + name)
    Enable_2_sig_hold_yi1_register = vf.add_var('Enable 2 sig _hold_yi1_register_' + name)
    Enable_2_sig_hold_yi2_register = vf.add_var('Enable 2 sig _hold_yi2_register_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yo1 = vf.add_var('yo1_' + name)
    yo2 = vf.add_var('yo2_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo1 - Enable_2_sig_hold_yi1_register),
            (yo2 - Enable_2_sig_hold_yi2_register),
            (Enable_2_sig_hold_yi1_register - ((Enable_2_sig_hold_proc_select_1 * yi1) + ((sym.Const(1.0) - Enable_2_sig_hold_proc_select_1) * Enable_2_sig_hold_proc_lastvalue_0))),
            (Enable_2_sig_hold_yi2_register - ((Enable_2_sig_hold_proc_select_3 * yi2) + ((sym.Const(1.0) - Enable_2_sig_hold_proc_select_3) * Enable_2_sig_hold_proc_lastvalue_2))),
        ],
        algebraic_vars=[yo1, yo2, Enable_2_sig_hold_yi1_register, Enable_2_sig_hold_yi2_register],
        in_vars=[yi1, yi2, Enable],
        out_vars=[yo1, yo2],
        name='Enable 2 sig _hold'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_2_sig_hold_proc_lastvalue_0: vf.add_const(0.0, name=''),
        Enable_2_sig_hold_proc_select_1: vf.add_const(0.0, name=''),
        Enable_2_sig_hold_proc_lastvalue_2: vf.add_const(0.0, name=''),
        Enable_2_sig_hold_proc_select_3: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Enable_2_sig_hold_yi1_register: yi1,
        Enable_2_sig_hold_yi2_register: yi2,
    }
    templ.block.procedural_logic = [
        lastvalue(Enable_2_sig_hold_yi1_register, output=Enable_2_sig_hold_proc_lastvalue_0),
        sampled_value(output=Enable_2_sig_hold_proc_select_1, source=Enable),
        lastvalue(Enable_2_sig_hold_yi2_register, output=Enable_2_sig_hold_proc_lastvalue_2),
        sampled_value(output=Enable_2_sig_hold_proc_select_3, source=Enable),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_2_sig_hold_493_emt_template(vf=vf, name='Enable 2 sig _hold__493' if name is None else name)
