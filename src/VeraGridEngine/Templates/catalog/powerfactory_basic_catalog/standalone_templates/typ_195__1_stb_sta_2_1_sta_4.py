# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_stb_sta_2_1_sta_4_195_emt_template(vf: VarFactory, name: str = '(1+sTb)(sTa)^2/(1+sTa)^4__195') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sTb_sTa_2_1_sTa_4_Ta = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4__Ta_' + name)
    v_1_sTb_sTa_2_1_sTa_4_Tb = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4__Tb_' + name)

    # --- State Variables ---
    v_1_sTb_sTa_2_1_sTa_4_x1 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4__x1_' + name)
    v_1_sTb_sTa_2_1_sTa_4_x2 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4__x2_' + name)
    v_1_sTb_sTa_2_1_sTa_4_x3 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4__x3_' + name)
    v_1_sTb_sTa_2_1_sTa_4_x4 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4__x4_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sTb_sTa_2_1_sTa_4_dx1 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4_dx1_' + name)
    v_1_sTb_sTa_2_1_sTa_4_dx2 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4_dx2_' + name)
    v_1_sTb_sTa_2_1_sTa_4_dx3 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4_dx3_' + name)
    v_1_sTb_sTa_2_1_sTa_4_yo1 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4_yo1_' + name)
    v_1_sTb_sTa_2_1_sTa_4_yo2 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4_yo2_' + name)
    v_1_sTb_sTa_2_1_sTa_4_yo3 = vf.add_var('(1+sTb)(sTa)^2/(1+sTa)^4_yo3_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sTb_sTa_2_1_sTa_4_x1 = vf.add_diff_var('d_(1+sTb)(sTa)^2/(1+sTa)^4__x1_' + name, base_var=v_1_sTb_sTa_2_1_sTa_4_x1)
    d_1_sTb_sTa_2_1_sTa_4_x2 = vf.add_diff_var('d_(1+sTb)(sTa)^2/(1+sTa)^4__x2_' + name, base_var=v_1_sTb_sTa_2_1_sTa_4_x2)
    d_1_sTb_sTa_2_1_sTa_4_x3 = vf.add_diff_var('d_(1+sTb)(sTa)^2/(1+sTa)^4__x3_' + name, base_var=v_1_sTb_sTa_2_1_sTa_4_x3)
    d_1_sTb_sTa_2_1_sTa_4_x4 = vf.add_diff_var('d_(1+sTb)(sTa)^2/(1+sTa)^4__x4_' + name, base_var=v_1_sTb_sTa_2_1_sTa_4_x4)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_sTb_sTa_2_1_sTa_4_dx1,
            v_1_sTb_sTa_2_1_sTa_4_dx2,
            v_1_sTb_sTa_2_1_sTa_4_dx3,
            ((v_1_sTb_sTa_2_1_sTa_4_yo3 - v_1_sTb_sTa_2_1_sTa_4_x4) / v_1_sTb_sTa_2_1_sTa_4_Ta),
        ],
        state_vars=[v_1_sTb_sTa_2_1_sTa_4_x1, v_1_sTb_sTa_2_1_sTa_4_x2, v_1_sTb_sTa_2_1_sTa_4_x3, v_1_sTb_sTa_2_1_sTa_4_x4],
        algebraic_eqs=[
            (v_1_sTb_sTa_2_1_sTa_4_dx1 - ((yi - v_1_sTb_sTa_2_1_sTa_4_x1) / v_1_sTb_sTa_2_1_sTa_4_Ta)),
            (v_1_sTb_sTa_2_1_sTa_4_yo1 - (v_1_sTb_sTa_2_1_sTa_4_x1 + (v_1_sTb_sTa_2_1_sTa_4_Tb * v_1_sTb_sTa_2_1_sTa_4_dx1))),
            (v_1_sTb_sTa_2_1_sTa_4_dx2 - ((v_1_sTb_sTa_2_1_sTa_4_yo1 - v_1_sTb_sTa_2_1_sTa_4_x2) / v_1_sTb_sTa_2_1_sTa_4_Ta)),
            (v_1_sTb_sTa_2_1_sTa_4_yo2 - (v_1_sTb_sTa_2_1_sTa_4_Ta * v_1_sTb_sTa_2_1_sTa_4_dx2)),
            (v_1_sTb_sTa_2_1_sTa_4_dx3 - ((v_1_sTb_sTa_2_1_sTa_4_yo2 - v_1_sTb_sTa_2_1_sTa_4_x3) / v_1_sTb_sTa_2_1_sTa_4_Ta)),
            (v_1_sTb_sTa_2_1_sTa_4_yo3 - (v_1_sTb_sTa_2_1_sTa_4_Ta * v_1_sTb_sTa_2_1_sTa_4_dx3)),
            (yo - v_1_sTb_sTa_2_1_sTa_4_x4),
        ],
        algebraic_vars=[v_1_sTb_sTa_2_1_sTa_4_dx1, v_1_sTb_sTa_2_1_sTa_4_yo1, v_1_sTb_sTa_2_1_sTa_4_dx2, v_1_sTb_sTa_2_1_sTa_4_yo2, v_1_sTb_sTa_2_1_sTa_4_dx3, v_1_sTb_sTa_2_1_sTa_4_yo3, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+sTb)(sTa)^2/(1+sTa)^4'
    )
    templ.block.diff_vars = [d_1_sTb_sTa_2_1_sTa_4_x1, d_1_sTb_sTa_2_1_sTa_4_x2, d_1_sTb_sTa_2_1_sTa_4_x3, d_1_sTb_sTa_2_1_sTa_4_x4]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sTb_sTa_2_1_sTa_4_Tb: vf.add_const(None, name='Tb'),
        v_1_sTb_sTa_2_1_sTa_4_Ta: vf.add_const(None, name='Ta'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_stb_sta_2_1_sta_4_195_emt_template(vf=vf, name='(1+sTb)(sTa)^2/(1+sTa)^4__195' if name is None else name)
