# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_enable_3_sig_496_emt_template(vf: VarFactory, name: str = 'Enable 3 sig__496') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Enable_3_sig_yi1_default = vf.add_var('Enable 3 sig__yi1_default_' + name)
    Enable_3_sig_yi2_default = vf.add_var('Enable 3 sig__yi2_default_' + name)
    Enable_3_sig_yi3_default = vf.add_var('Enable 3 sig__yi3_default_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable = vf.add_var('Enable_' + name)
    Enable_3_sig_proc_select_0 = vf.add_var('Enable 3 sig__proc_select_0_' + name)
    Enable_3_sig_proc_select_1 = vf.add_var('Enable 3 sig__proc_select_1_' + name)
    Enable_3_sig_proc_select_2 = vf.add_var('Enable 3 sig__proc_select_2_' + name)
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
            (yo1 - ((Enable_3_sig_proc_select_0 * yi1) + ((sym.Const(1.0) - Enable_3_sig_proc_select_0) * Enable_3_sig_yi1_default))),
            (yo2 - ((Enable_3_sig_proc_select_1 * yi2) + ((sym.Const(1.0) - Enable_3_sig_proc_select_1) * Enable_3_sig_yi2_default))),
            (yo3 - ((Enable_3_sig_proc_select_2 * yi3) + ((sym.Const(1.0) - Enable_3_sig_proc_select_2) * Enable_3_sig_yi3_default))),
        ],
        algebraic_vars=[yo1, yo2, yo3],
        in_vars=[yi1, yi2, yi3, Enable],
        out_vars=[yo1, yo2, yo3],
        name='Enable 3 sig'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Enable_3_sig_yi1_default: vf.add_const(None, name='yi1_default'),
        Enable_3_sig_yi2_default: vf.add_const(None, name='yi2_default'),
        Enable_3_sig_yi3_default: vf.add_const(None, name='yi3_default'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_3_sig_proc_select_0: vf.add_const(0.0, name=''),
        Enable_3_sig_proc_select_1: vf.add_const(0.0, name=''),
        Enable_3_sig_proc_select_2: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Enable_3_sig_proc_select_0, source=Enable),
        sampled_value(output=Enable_3_sig_proc_select_1, source=Enable),
        sampled_value(output=Enable_3_sig_proc_select_2, source=Enable),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_3_sig_496_emt_template(vf=vf, name='Enable 3 sig__496' if name is None else name)
