# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_sktd_1_st_122_emt_template(vf: VarFactory, name: str = 'sKTd/(1+sT)__122') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    sKTd_1_sT_K = vf.add_var('sKTd/(1+sT)__K_' + name)
    sKTd_1_sT_T = vf.add_var('sKTd/(1+sT)__T_' + name)
    sKTd_1_sT_Td = vf.add_var('sKTd/(1+sT)__Td_' + name)

    # --- State Variables ---
    sKTd_1_sT_x = vf.add_var('sKTd/(1+sT)__x_' + name)

    # --- Algebraic / Shared Variables ---
    sKTd_1_sT_dx = vf.add_var('sKTd/(1+sT)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_sKTd_1_sT_x = vf.add_diff_var('d_sKTd/(1+sT)__x_' + name, base_var=sKTd_1_sT_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            sKTd_1_sT_dx,
        ],
        state_vars=[sKTd_1_sT_x],
        algebraic_eqs=[
            (sKTd_1_sT_dx - ((yi - sKTd_1_sT_x) / sKTd_1_sT_T)),
            (yo - ((sKTd_1_sT_K * sKTd_1_sT_Td) * sKTd_1_sT_dx)),
        ],
        algebraic_vars=[sKTd_1_sT_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='sKTd/(1+sT)'
    )
    templ.block.diff_vars = [d_sKTd_1_sT_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        sKTd_1_sT_K: vf.add_const(None, name='K'),
        sKTd_1_sT_Td: vf.add_const(None, name='Td'),
        sKTd_1_sT_T: vf.add_const(None, name='T'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_sktd_1_st_122_emt_template(vf=vf, name='sKTd/(1+sT)__122' if name is None else name)
