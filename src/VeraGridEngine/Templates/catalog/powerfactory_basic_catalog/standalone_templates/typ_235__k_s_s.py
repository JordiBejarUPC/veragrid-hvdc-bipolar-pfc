# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_k_s_s_235_emt_template(vf: VarFactory, name: str = 'K/s [(s__235') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_s_s_K = vf.add_var('K/s [(s__K_' + name)

    # --- State Variables ---
    K_s_s_x = vf.add_var('K/s [(s__x_' + name)

    # --- Algebraic / Shared Variables ---
    y_max = vf.add_var('y_max_' + name)
    y_min = vf.add_var('y_min_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_s_s_x = vf.add_diff_var('d_K/s [(s__x_' + name, base_var=K_s_s_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (K_s_s_K * yi),
        ],
        state_vars=[K_s_s_x],
        algebraic_eqs=[
            (yo - ((y_min + ((K_s_s_x - y_min) * sym.heaviside((K_s_s_x - y_min)))) - ((K_s_s_x - y_max) * sym.heaviside((K_s_s_x - y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, y_max, y_min],
        out_vars=[yo],
        name='K/s [(s'
    )
    templ.block.diff_vars = [d_K_s_s_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_s_s_K: vf.add_const(None, name='K'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_s_s_235_emt_template(vf=vf, name='K/s [(s__235' if name is None else name)
