# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_conj_complex_376_emt_template(vf: VarFactory, name: str = 'CONJ COMPLEX__376') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    im = vf.add_var('im_' + name)
    im1 = vf.add_var('im1_' + name)
    re = vf.add_var('re_' + name)
    re1 = vf.add_var('re1_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (re - re1),
            (im - (-im1)),
        ],
        algebraic_vars=[re, im],
        in_vars=[re1, im1],
        out_vars=[re, im],
        name='CONJ COMPLEX'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_conj_complex_376_emt_template(vf=vf, name='CONJ COMPLEX__376' if name is None else name)
