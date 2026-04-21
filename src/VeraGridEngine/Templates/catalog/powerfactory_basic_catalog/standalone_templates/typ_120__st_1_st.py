# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_st_1_st_120_emt_template(vf: VarFactory, name: str = '-sT/(1+sT)__120') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    sT_1_sT_T = vf.add_var('-sT/(1+sT)__T_' + name)

    # --- State Variables ---
    sT_1_sT_x = vf.add_var('-sT/(1+sT)__x_' + name)

    # --- Algebraic / Shared Variables ---
    sT_1_sT_dx = vf.add_var('-sT/(1+sT)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_sT_1_sT_x = vf.add_diff_var('d_-sT/(1+sT)__x_' + name, base_var=sT_1_sT_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            sT_1_sT_dx,
        ],
        state_vars=[sT_1_sT_x],
        algebraic_eqs=[
            (sT_1_sT_dx - ((yi - sT_1_sT_x) / sT_1_sT_T)),
            (yo - ((-sT_1_sT_T) * sT_1_sT_dx)),
        ],
        algebraic_vars=[sT_1_sT_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='-sT/(1+sT)'
    )
    templ.block.diff_vars = [d_sT_1_sT_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        sT_1_sT_T: vf.add_const(None, name='T'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_st_1_st_120_emt_template(vf=vf, name='-sT/(1+sT)__120' if name is None else name)
