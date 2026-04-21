# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_k_1_stb_1_sta_304_emt_template(vf: VarFactory, name: str = 'K(1+sTb)/(1+sTa)__304') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_1_sTb_1_sTa_K = vf.add_var('K(1+sTb)/(1+sTa)__K_' + name)
    K_1_sTb_1_sTa_Ta = vf.add_var('K(1+sTb)/(1+sTa)__Ta_' + name)
    K_1_sTb_1_sTa_Tb = vf.add_var('K(1+sTb)/(1+sTa)__Tb_' + name)

    # --- State Variables ---
    K_1_sTb_1_sTa_x = vf.add_var('K(1+sTb)/(1+sTa)__x_' + name)

    # --- Algebraic / Shared Variables ---
    K_1_sTb_1_sTa_dx = vf.add_var('K(1+sTb)/(1+sTa)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_1_sTb_1_sTa_x = vf.add_diff_var('d_K(1+sTb)/(1+sTa)__x_' + name, base_var=K_1_sTb_1_sTa_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            K_1_sTb_1_sTa_dx,
        ],
        state_vars=[K_1_sTb_1_sTa_x],
        algebraic_eqs=[
            (K_1_sTb_1_sTa_dx - (((K_1_sTb_1_sTa_K * yi) - K_1_sTb_1_sTa_x) / K_1_sTb_1_sTa_Ta)),
            (yo - (K_1_sTb_1_sTa_x + (K_1_sTb_1_sTa_Tb * K_1_sTb_1_sTa_dx))),
        ],
        algebraic_vars=[K_1_sTb_1_sTa_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='K(1+sTb)/(1+sTa)'
    )
    templ.block.diff_vars = [d_K_1_sTb_1_sTa_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_1_sTb_1_sTa_K: vf.add_const(None, name='K'),
        K_1_sTb_1_sTa_Tb: vf.add_const(None, name='Tb'),
        K_1_sTb_1_sTa_Ta: vf.add_const(None, name='Ta'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_1_stb_1_sta_304_emt_template(vf=vf, name='K(1+sTb)/(1+sTa)__304' if name is None else name)
