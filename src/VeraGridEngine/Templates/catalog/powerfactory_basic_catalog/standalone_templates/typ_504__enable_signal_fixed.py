# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_enable_signal_fixed_504_emt_template(vf: VarFactory, name: str = 'Enable signal (fixed)__504') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Enable_signal_fixed_Enable = vf.add_var('Enable signal (fixed)__Enable_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable_signal_fixed_proc_selfix_0 = vf.add_var('Enable signal (fixed)__proc_selfix_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Enable_signal_fixed_proc_selfix_0 * yi) + ((sym.Const(1.0) - Enable_signal_fixed_proc_selfix_0) * sym.Const(0.0)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Enable signal (fixed)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Enable_signal_fixed_Enable: vf.add_const(None, name='Enable'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_signal_fixed_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix(Enable_signal_fixed_Enable, output=Enable_signal_fixed_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_signal_fixed_504_emt_template(vf=vf, name='Enable signal (fixed)__504' if name is None else name)
