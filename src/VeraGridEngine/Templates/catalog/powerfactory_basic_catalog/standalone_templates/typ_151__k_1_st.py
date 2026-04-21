# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_k_1_st_151_emt_template(vf: VarFactory, name: str = 'K/(1+sT)__151') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_1_sT_K = vf.add_var('K/(1+sT)__K_' + name)
    K_1_sT_T = vf.add_var('K/(1+sT)__T_' + name)

    # --- State Variables ---
    K_1_sT_x = vf.add_var('K/(1+sT)__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_1_sT_x = vf.add_diff_var('d_K/(1+sT)__x_' + name, base_var=K_1_sT_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (((K_1_sT_K * yi) - K_1_sT_x) / K_1_sT_T),
        ],
        state_vars=[K_1_sT_x],
        algebraic_eqs=[
            (yo - K_1_sT_x),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='K/(1+sT)'
    )
    templ.block.diff_vars = [d_K_1_sT_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_1_sT_K: vf.add_const(None, name='K'),
        K_1_sT_T: vf.add_const(None, name='T'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_1_st_151_emt_template(vf=vf, name='K/(1+sT)__151' if name is None else name)
