# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import flipflop
from VeraGridEngine.enumerations import DeviceType

def get_flipflop_68_emt_template(vf: VarFactory, name: str = 'flipflop__68') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    flipflop_proc_flipflop_0 = vf.add_var('flipflop__proc_flipflop_0_' + name)
    rst = vf.add_var('rst_' + name)
    set = vf.add_var('set_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - flipflop_proc_flipflop_0),
        ],
        algebraic_vars=[yo],
        in_vars=[set, rst],
        out_vars=[yo],
        name='flipflop'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        flipflop_proc_flipflop_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        flipflop(set, rst, output=flipflop_proc_flipflop_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_flipflop_68_emt_template(vf=vf, name='flipflop__68' if name is None else name)
