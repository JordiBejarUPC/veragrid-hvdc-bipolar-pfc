# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_lim_const_76_emt_template(vf: VarFactory, name: str = 'lim_const__76') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    lim_const_y_max = vf.add_var('lim_const__y_max_' + name)
    lim_const_y_min = vf.add_var('lim_const__y_min_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((lim_const_y_min + ((yi - lim_const_y_min) * sym.heaviside((yi - lim_const_y_min)))) - ((yi - lim_const_y_max) * sym.heaviside((yi - lim_const_y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='lim_const'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        lim_const_y_max: vf.add_const(None, name='y_max'),
        lim_const_y_min: vf.add_const(None, name='y_min'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_lim_const_76_emt_template(vf=vf, name='lim_const__76' if name is None else name)
