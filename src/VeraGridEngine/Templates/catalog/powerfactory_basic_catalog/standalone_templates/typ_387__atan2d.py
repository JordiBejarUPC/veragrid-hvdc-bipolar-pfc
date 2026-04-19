# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_atan2d_387_emt_template(vf: VarFactory, name: str = 'ATAN2D__387') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    im = vf.add_var('im_' + name)
    re = vf.add_var('re_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((sym.atan2(im, re) * sym.Const(3.141592653589793)) / sym.Const(180.0))),
        ],
        algebraic_vars=[yo],
        in_vars=[re, im],
        out_vars=[yo],
        name='ATAN2D'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_atan2d_387_emt_template(vf=vf, name='ATAN2D__387' if name is None else name)
