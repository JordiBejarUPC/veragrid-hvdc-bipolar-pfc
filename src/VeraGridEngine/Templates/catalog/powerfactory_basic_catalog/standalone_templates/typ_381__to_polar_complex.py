# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_to_polar_complex_381_emt_template(vf: VarFactory, name: str = 'TO POLAR COMPLEX__381') -> EmtModelTemplate:
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
            (mag - sym.sqrt(((re * re) + (im * im)))),
            (phi - sym.atan2(im, re)),
        ],
        algebraic_vars=[mag, phi],
        in_vars=[re, im],
        out_vars=[mag, phi],
        name='TO POLAR COMPLEX'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_to_polar_complex_381_emt_template(vf=vf, name='TO POLAR COMPLEX__381' if name is None else name)
