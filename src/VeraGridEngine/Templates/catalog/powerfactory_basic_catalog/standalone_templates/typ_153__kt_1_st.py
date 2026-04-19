# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_kt_1_st_153_emt_template(vf: VarFactory, name: str = 'KT/(1+sT)__153') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    KT_1_sT_K = vf.add_var('KT/(1+sT)__K_' + name)
    KT_1_sT_T = vf.add_var('KT/(1+sT)__T_' + name)

    # --- State Variables ---
    KT_1_sT_x = vf.add_var('KT/(1+sT)__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_KT_1_sT_x = vf.add_diff_var('d_KT/(1+sT)__x_' + name, base_var=KT_1_sT_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((((KT_1_sT_K * KT_1_sT_T) * yi) - KT_1_sT_x) / KT_1_sT_T),
        ],
        state_vars=[KT_1_sT_x],
        algebraic_eqs=[
            (yo - KT_1_sT_x),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='KT/(1+sT)'
    )
    templ.block.diff_vars = [d_KT_1_sT_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        KT_1_sT_K: vf.add_const(None, name='K'),
        KT_1_sT_T: vf.add_const(None, name='T'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kt_1_st_153_emt_template(vf=vf, name='KT/(1+sT)__153' if name is None else name)
