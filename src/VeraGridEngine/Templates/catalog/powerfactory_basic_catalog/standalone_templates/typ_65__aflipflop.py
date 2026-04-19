# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import aflipflop
from VeraGridEngine.enumerations import DeviceType

def get_aflipflop_65_emt_template(vf: VarFactory, name: str = 'aflipflop__65') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    aflipflop_proc_aflipflop_0 = vf.add_var('aflipflop__proc_aflipflop_0_' + name)
    rst = vf.add_var('rst_' + name)
    set = vf.add_var('set_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - aflipflop_proc_aflipflop_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, set, rst],
        out_vars=[yo],
        name='aflipflop'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        aflipflop_proc_aflipflop_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        aflipflop(yi, set, rst, output=aflipflop_proc_aflipflop_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_aflipflop_65_emt_template(vf=vf, name='aflipflop__65' if name is None else name)
