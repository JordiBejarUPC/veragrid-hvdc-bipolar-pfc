# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_limit_s_321_emt_template(vf: VarFactory, name: str = 'Limit [s__321') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    y_max = vf.add_var('y_max_' + name)
    y_min = vf.add_var('y_min_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((y_min + ((yi - y_min) * sym.heaviside((yi - y_min)))) - ((yi - y_max) * sym.heaviside((yi - y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, y_max, y_min],
        out_vars=[yo],
        name='Limit [s'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_limit_s_321_emt_template(vf=vf, name='Limit [s__321' if name is None else name)
