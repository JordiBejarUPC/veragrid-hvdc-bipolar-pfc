# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_div_complex_377_emt_template(vf: VarFactory, name: str = 'DIV COMPLEX__377') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    DIV_COMPLEX_var1 = vf.add_var('DIV COMPLEX_var1_' + name)
    im = vf.add_var('im_' + name)
    im1 = vf.add_var('im1_' + name)
    im2 = vf.add_var('im2_' + name)
    re = vf.add_var('re_' + name)
    re1 = vf.add_var('re1_' + name)
    re2 = vf.add_var('re2_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (re - (((re1 * re2) + (im1 * im2)) / DIV_COMPLEX_var1)),
            (im - (((im1 * re2) - (re1 * im2)) / DIV_COMPLEX_var1)),
            (DIV_COMPLEX_var1 - ((re2 * re2) + (im2 * im2))),
        ],
        algebraic_vars=[re, im, DIV_COMPLEX_var1],
        in_vars=[re1, im1, re2, im2],
        out_vars=[re, im],
        name='DIV COMPLEX'
    )
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        DIV_COMPLEX_var1: ((re2 * re2) + (im2 * im2)),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_div_complex_377_emt_template(vf=vf, name='DIV COMPLEX__377' if name is None else name)
