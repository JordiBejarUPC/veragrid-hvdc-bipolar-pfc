# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import delay
from VeraGridEngine.enumerations import DeviceType

def get_delay_67_emt_template(vf: VarFactory, name: str = 'delay__67') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    delay_T = vf.add_var('delay__T_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    delay_proc_delay_0 = vf.add_var('delay__proc_delay_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - delay_proc_delay_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='delay'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        delay_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        delay_proc_delay_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        delay(yi, delay_T, output=delay_proc_delay_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_delay_67_emt_template(vf=vf, name='delay__67' if name is None else name)
