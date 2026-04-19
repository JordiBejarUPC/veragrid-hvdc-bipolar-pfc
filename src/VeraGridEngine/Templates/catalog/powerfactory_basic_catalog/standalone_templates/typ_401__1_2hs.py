# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_2hs_401_emt_template(vf: VarFactory, name: str = '1/(2Hs)__401') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_2Hs_H = vf.add_var('1/(2Hs)__H_' + name)

    # --- State Variables ---
    v_1_2Hs_x = vf.add_var('1/(2Hs)__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_2Hs_x = vf.add_diff_var('d_1/(2Hs)__x_' + name, base_var=v_1_2Hs_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (yi / (sym.Const(2.0) * v_1_2Hs_H)),
        ],
        state_vars=[v_1_2Hs_x],
        algebraic_eqs=[
            (yo - v_1_2Hs_x),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='1/(2Hs)'
    )
    templ.block.diff_vars = [d_1_2Hs_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_2Hs_H: vf.add_const(None, name='H'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_2hs_401_emt_template(vf=vf, name='1/(2Hs)__401' if name is None else name)
