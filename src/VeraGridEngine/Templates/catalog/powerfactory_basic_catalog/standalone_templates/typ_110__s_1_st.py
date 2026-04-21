# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_s_1_st_110_emt_template(vf: VarFactory, name: str = 's/(1+sT)__110') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    s_1_sT_T = vf.add_var('s/(1+sT)__T_' + name)

    # --- State Variables ---
    s_1_sT_x = vf.add_var('s/(1+sT)__x_' + name)

    # --- Algebraic / Shared Variables ---
    s_1_sT_dx = vf.add_var('s/(1+sT)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_s_1_sT_x = vf.add_diff_var('d_s/(1+sT)__x_' + name, base_var=s_1_sT_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            s_1_sT_dx,
        ],
        state_vars=[s_1_sT_x],
        algebraic_eqs=[
            (s_1_sT_dx - ((yi - s_1_sT_x) / s_1_sT_T)),
            (yo - s_1_sT_dx),
        ],
        algebraic_vars=[s_1_sT_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='s/(1+sT)'
    )
    templ.block.diff_vars = [d_s_1_sT_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        s_1_sT_T: vf.add_const(None, name='T'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_s_1_st_110_emt_template(vf=vf, name='s/(1+sT)__110' if name is None else name)
