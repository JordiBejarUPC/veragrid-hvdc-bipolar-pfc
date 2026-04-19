# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_s_214_emt_template(vf: VarFactory, name: str = '1/s__214') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---
    v_1_s_x = vf.add_var('1/s__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_s_x = vf.add_diff_var('d_1/s__x_' + name, base_var=v_1_s_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            yi,
        ],
        state_vars=[v_1_s_x],
        algebraic_eqs=[
            (yo - v_1_s_x),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='1/s'
    )
    templ.block.diff_vars = [d_1_s_x]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_s_214_emt_template(vf=vf, name='1/s__214' if name is None else name)
