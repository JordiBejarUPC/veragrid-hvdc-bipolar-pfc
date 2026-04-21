# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_enable_2_sig_494_emt_template(vf: VarFactory, name: str = 'Enable 2 sig__494') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Enable_2_sig_yi1_default = vf.add_var('Enable 2 sig__yi1_default_' + name)
    Enable_2_sig_yi2_default = vf.add_var('Enable 2 sig__yi2_default_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable = vf.add_var('Enable_' + name)
    Enable_2_sig_proc_select_0 = vf.add_var('Enable 2 sig__proc_select_0_' + name)
    Enable_2_sig_proc_select_1 = vf.add_var('Enable 2 sig__proc_select_1_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yo1 = vf.add_var('yo1_' + name)
    yo2 = vf.add_var('yo2_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo1 - ((Enable_2_sig_proc_select_0 * yi1) + ((sym.Const(1.0) - Enable_2_sig_proc_select_0) * Enable_2_sig_yi1_default))),
            (yo2 - ((Enable_2_sig_proc_select_1 * yi2) + ((sym.Const(1.0) - Enable_2_sig_proc_select_1) * Enable_2_sig_yi2_default))),
        ],
        algebraic_vars=[yo1, yo2],
        in_vars=[yi1, yi2, Enable],
        out_vars=[yo1, yo2],
        name='Enable 2 sig'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Enable_2_sig_yi1_default: vf.add_const(None, name='yi1_default'),
        Enable_2_sig_yi2_default: vf.add_const(None, name='yi2_default'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_2_sig_proc_select_0: vf.add_const(0.0, name=''),
        Enable_2_sig_proc_select_1: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Enable_2_sig_proc_select_0, source=Enable),
        sampled_value(output=Enable_2_sig_proc_select_1, source=Enable),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_2_sig_494_emt_template(vf=vf, name='Enable 2 sig__494' if name is None else name)
