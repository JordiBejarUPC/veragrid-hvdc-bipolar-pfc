# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_enable_5_sig_500_emt_template(vf: VarFactory, name: str = 'Enable 5 sig__500') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Enable_5_sig_yi1_default = vf.add_var('Enable 5 sig__yi1_default_' + name)
    Enable_5_sig_yi2_default = vf.add_var('Enable 5 sig__yi2_default_' + name)
    Enable_5_sig_yi3_default = vf.add_var('Enable 5 sig__yi3_default_' + name)
    Enable_5_sig_yi4_default = vf.add_var('Enable 5 sig__yi4_default_' + name)
    Enable_5_sig_yi5_default = vf.add_var('Enable 5 sig__yi5_default_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable = vf.add_var('Enable_' + name)
    Enable_5_sig_proc_select_0 = vf.add_var('Enable 5 sig__proc_select_0_' + name)
    Enable_5_sig_proc_select_1 = vf.add_var('Enable 5 sig__proc_select_1_' + name)
    Enable_5_sig_proc_select_2 = vf.add_var('Enable 5 sig__proc_select_2_' + name)
    Enable_5_sig_proc_select_3 = vf.add_var('Enable 5 sig__proc_select_3_' + name)
    Enable_5_sig_proc_select_4 = vf.add_var('Enable 5 sig__proc_select_4_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yi3 = vf.add_var('yi3_' + name)
    yi4 = vf.add_var('yi4_' + name)
    yi5 = vf.add_var('yi5_' + name)
    yo1 = vf.add_var('yo1_' + name)
    yo2 = vf.add_var('yo2_' + name)
    yo3 = vf.add_var('yo3_' + name)
    yo4 = vf.add_var('yo4_' + name)
    yo5 = vf.add_var('yo5_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo1 - ((Enable_5_sig_proc_select_0 * yi1) + ((sym.Const(1.0) - Enable_5_sig_proc_select_0) * Enable_5_sig_yi1_default))),
            (yo2 - ((Enable_5_sig_proc_select_1 * yi2) + ((sym.Const(1.0) - Enable_5_sig_proc_select_1) * Enable_5_sig_yi2_default))),
            (yo3 - ((Enable_5_sig_proc_select_2 * yi3) + ((sym.Const(1.0) - Enable_5_sig_proc_select_2) * Enable_5_sig_yi3_default))),
            (yo4 - ((Enable_5_sig_proc_select_3 * yi4) + ((sym.Const(1.0) - Enable_5_sig_proc_select_3) * Enable_5_sig_yi4_default))),
            (yo5 - ((Enable_5_sig_proc_select_4 * yi5) + ((sym.Const(1.0) - Enable_5_sig_proc_select_4) * Enable_5_sig_yi5_default))),
        ],
        algebraic_vars=[yo1, yo2, yo3, yo4, yo5],
        in_vars=[yi1, yi2, yi3, yi4, yi5, Enable],
        out_vars=[yo1, yo2, yo3, yo4, yo5],
        name='Enable 5 sig'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Enable_5_sig_yi1_default: vf.add_const(None, name='yi1_default'),
        Enable_5_sig_yi2_default: vf.add_const(None, name='yi2_default'),
        Enable_5_sig_yi3_default: vf.add_const(None, name='yi3_default'),
        Enable_5_sig_yi4_default: vf.add_const(None, name='yi4_default'),
        Enable_5_sig_yi5_default: vf.add_const(None, name='yi5_default'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_5_sig_proc_select_0: vf.add_const(0.0, name=''),
        Enable_5_sig_proc_select_1: vf.add_const(0.0, name=''),
        Enable_5_sig_proc_select_2: vf.add_const(0.0, name=''),
        Enable_5_sig_proc_select_3: vf.add_const(0.0, name=''),
        Enable_5_sig_proc_select_4: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Enable_5_sig_proc_select_0, source=Enable),
        sampled_value(output=Enable_5_sig_proc_select_1, source=Enable),
        sampled_value(output=Enable_5_sig_proc_select_2, source=Enable),
        sampled_value(output=Enable_5_sig_proc_select_3, source=Enable),
        sampled_value(output=Enable_5_sig_proc_select_4, source=Enable),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_5_sig_500_emt_template(vf=vf, name='Enable 5 sig__500' if name is None else name)
