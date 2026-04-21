# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_sqrt3_64_emt_template(vf: VarFactory, name: str = 'SQRT3__64') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    SQRT3_yo0 = vf.add_var('SQRT3_yo0_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - SQRT3_yo0),
        ],
        algebraic_vars=[yo],
        out_vars=[yo],
        name='SQRT3'
    )
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        SQRT3_yo0: sym.sqrt(sym.Const(3.0)),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_sqrt3_64_emt_template(vf=vf, name='SQRT3__64' if name is None else name)
