# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_k1_k2_1_st_152_emt_template(vf: VarFactory, name: str = 'K1 + K2/(1+sT)__152') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K1_K2_1_sT_K1 = vf.add_var('K1 + K2/(1+sT)__K1_' + name)
    K1_K2_1_sT_K2 = vf.add_var('K1 + K2/(1+sT)__K2_' + name)
    K1_K2_1_sT_T = vf.add_var('K1 + K2/(1+sT)__T_' + name)

    # --- State Variables ---
    K1_K2_1_sT_x = vf.add_var('K1 + K2/(1+sT)__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K1_K2_1_sT_x = vf.add_diff_var('d_K1 + K2/(1+sT)__x_' + name, base_var=K1_K2_1_sT_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((yi - K1_K2_1_sT_x) / K1_K2_1_sT_T),
        ],
        state_vars=[K1_K2_1_sT_x],
        algebraic_eqs=[
            (yo - ((K1_K2_1_sT_x * K1_K2_1_sT_K2) + (K1_K2_1_sT_K1 * yi))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='K1 + K2/(1+sT)'
    )
    templ.block.diff_vars = [d_K1_K2_1_sT_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K1_K2_1_sT_K1: vf.add_const(None, name='K1'),
        K1_K2_1_sT_K2: vf.add_const(None, name='K2'),
        K1_K2_1_sT_T: vf.add_const(None, name='T'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k1_k2_1_st_152_emt_template(vf=vf, name='K1 + K2/(1+sT)__152' if name is None else name)
