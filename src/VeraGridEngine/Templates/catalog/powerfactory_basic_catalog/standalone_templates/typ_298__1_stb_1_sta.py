# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_stb_1_sta_298_emt_template(vf: VarFactory, name: str = '(1+sTb)/(1+sTa)__298') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sTb_1_sTa_Ta = vf.add_var('(1+sTb)/(1+sTa)__Ta_' + name)
    v_1_sTb_1_sTa_Tb = vf.add_var('(1+sTb)/(1+sTa)__Tb_' + name)

    # --- State Variables ---
    v_1_sTb_1_sTa_x = vf.add_var('(1+sTb)/(1+sTa)__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sTb_1_sTa_dx = vf.add_var('(1+sTb)/(1+sTa)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sTb_1_sTa_x = vf.add_diff_var('d_(1+sTb)/(1+sTa)__x_' + name, base_var=v_1_sTb_1_sTa_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_sTb_1_sTa_dx,
        ],
        state_vars=[v_1_sTb_1_sTa_x],
        algebraic_eqs=[
            (v_1_sTb_1_sTa_dx - ((yi - v_1_sTb_1_sTa_x) / v_1_sTb_1_sTa_Ta)),
            (yo - (v_1_sTb_1_sTa_x + (v_1_sTb_1_sTa_Tb * v_1_sTb_1_sTa_dx))),
        ],
        algebraic_vars=[v_1_sTb_1_sTa_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+sTb)/(1+sTa)'
    )
    templ.block.diff_vars = [d_1_sTb_1_sTa_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sTb_1_sTa_Tb: vf.add_const(None, name='Tb'),
        v_1_sTb_1_sTa_Ta: vf.add_const(None, name='Ta'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_stb_1_sta_298_emt_template(vf=vf, name='(1+sTb)/(1+sTa)__298' if name is None else name)
