# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_to_rectangular_complex_382_emt_template(vf: VarFactory, name: str = 'TO RECTANGULAR COMPLEX__382') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    im = vf.add_var('im_' + name)
    mag = vf.add_var('mag_' + name)
    phi = vf.add_var('phi_' + name)
    re = vf.add_var('re_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (re - (mag * sym.cos(phi))),
            (im - (mag * sym.sin(phi))),
        ],
        algebraic_vars=[re, im],
        in_vars=[mag, phi],
        out_vars=[re, im],
        name='TO RECTANGULAR COMPLEX'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_to_rectangular_complex_382_emt_template(vf=vf, name='TO RECTANGULAR COMPLEX__382' if name is None else name)
