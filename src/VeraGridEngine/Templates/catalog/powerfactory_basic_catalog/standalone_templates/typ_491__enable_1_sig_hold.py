# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_enable_1_sig_hold_491_emt_template(vf: VarFactory, name: str = 'Enable 1 sig _hold__491') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable = vf.add_var('Enable_' + name)
    Enable_1_sig_hold_proc_lastvalue_0 = vf.add_var('Enable 1 sig _hold__proc_lastvalue_0_' + name)
    Enable_1_sig_hold_proc_select_1 = vf.add_var('Enable 1 sig _hold__proc_select_1_' + name)
    Enable_1_sig_hold_yi_register = vf.add_var('Enable 1 sig _hold_yi_register_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - Enable_1_sig_hold_yi_register),
            (Enable_1_sig_hold_yi_register - ((Enable_1_sig_hold_proc_select_1 * yi) + ((sym.Const(1.0) - Enable_1_sig_hold_proc_select_1) * Enable_1_sig_hold_proc_lastvalue_0))),
        ],
        algebraic_vars=[yo, Enable_1_sig_hold_yi_register],
        in_vars=[yi, Enable],
        out_vars=[yo],
        name='Enable 1 sig _hold'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_1_sig_hold_proc_lastvalue_0: vf.add_const(0.0, name=''),
        Enable_1_sig_hold_proc_select_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Enable_1_sig_hold_yi_register: yi,
    }
    templ.block.procedural_logic = [
        lastvalue(Enable_1_sig_hold_yi_register, output=Enable_1_sig_hold_proc_lastvalue_0),
        sampled_value(output=Enable_1_sig_hold_proc_select_1, source=Enable),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_1_sig_hold_491_emt_template(vf=vf, name='Enable 1 sig _hold__491' if name is None else name)
