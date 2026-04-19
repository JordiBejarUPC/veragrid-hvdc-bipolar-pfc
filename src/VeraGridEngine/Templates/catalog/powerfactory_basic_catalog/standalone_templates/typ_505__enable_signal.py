# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_enable_signal_505_emt_template(vf: VarFactory, name: str = 'Enable signal__505') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Enable_signal_Enable = vf.add_var('Enable signal__Enable_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable_signal_proc_select_0 = vf.add_var('Enable signal__proc_select_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Enable_signal_proc_select_0 * yi) + ((sym.Const(1.0) - Enable_signal_proc_select_0) * sym.Const(0.0)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Enable signal'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Enable_signal_Enable: vf.add_const(None, name='Enable'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Enable_signal_proc_select_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Enable_signal_proc_select_0, source=Enable_signal_Enable),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_enable_signal_505_emt_template(vf=vf, name='Enable signal__505' if name is None else name)
