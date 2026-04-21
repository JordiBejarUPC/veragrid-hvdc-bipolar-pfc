# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_skt_1_st_121_emt_template(vf: VarFactory, name: str = 'sKT/(1+sT)__121') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    sKT_1_sT_K = vf.add_var('sKT/(1+sT)__K_' + name)
    sKT_1_sT_T = vf.add_var('sKT/(1+sT)__T_' + name)

    # --- State Variables ---
    sKT_1_sT_x = vf.add_var('sKT/(1+sT)__x_' + name)

    # --- Algebraic / Shared Variables ---
    sKT_1_sT_dx = vf.add_var('sKT/(1+sT)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_sKT_1_sT_x = vf.add_diff_var('d_sKT/(1+sT)__x_' + name, base_var=sKT_1_sT_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            sKT_1_sT_dx,
        ],
        state_vars=[sKT_1_sT_x],
        algebraic_eqs=[
            (sKT_1_sT_dx - ((yi - sKT_1_sT_x) / sKT_1_sT_T)),
            (yo - ((sKT_1_sT_K * sKT_1_sT_T) * sKT_1_sT_dx)),
        ],
        algebraic_vars=[sKT_1_sT_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='sKT/(1+sT)'
    )
    templ.block.diff_vars = [d_sKT_1_sT_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        sKT_1_sT_K: vf.add_const(None, name='K'),
        sKT_1_sT_T: vf.add_const(None, name='T'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_skt_1_st_121_emt_template(vf=vf, name='sKT/(1+sT)__121' if name is None else name)
