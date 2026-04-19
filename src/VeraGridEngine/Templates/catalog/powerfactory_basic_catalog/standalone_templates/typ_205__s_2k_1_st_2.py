# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_s_2k_1_st_2_205_emt_template(vf: VarFactory, name: str = 's^2K/(1+sT)^2__205') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    s_2K_1_sT_2_K = vf.add_var('s^2K/(1+sT)^2__K_' + name)
    s_2K_1_sT_2_T = vf.add_var('s^2K/(1+sT)^2__T_' + name)

    # --- State Variables ---
    s_2K_1_sT_2_x1 = vf.add_var('s^2K/(1+sT)^2__x1_' + name)
    s_2K_1_sT_2_x2 = vf.add_var('s^2K/(1+sT)^2__x2_' + name)

    # --- Algebraic / Shared Variables ---
    s_2K_1_sT_2_dx1 = vf.add_var('s^2K/(1+sT)^2_dx1_' + name)
    s_2K_1_sT_2_dx2 = vf.add_var('s^2K/(1+sT)^2_dx2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_s_2K_1_sT_2_x1 = vf.add_diff_var('d_s^2K/(1+sT)^2__x1_' + name, base_var=s_2K_1_sT_2_x1)
    d_s_2K_1_sT_2_x2 = vf.add_diff_var('d_s^2K/(1+sT)^2__x2_' + name, base_var=s_2K_1_sT_2_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            s_2K_1_sT_2_dx1,
            s_2K_1_sT_2_dx2,
        ],
        state_vars=[s_2K_1_sT_2_x1, s_2K_1_sT_2_x2],
        algebraic_eqs=[
            (s_2K_1_sT_2_dx1 - (((s_2K_1_sT_2_K * yi) - s_2K_1_sT_2_x1) / s_2K_1_sT_2_T)),
            (s_2K_1_sT_2_dx2 - ((s_2K_1_sT_2_dx1 - s_2K_1_sT_2_x2) / s_2K_1_sT_2_T)),
            (yo - s_2K_1_sT_2_dx2),
        ],
        algebraic_vars=[s_2K_1_sT_2_dx1, s_2K_1_sT_2_dx2, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='s^2K/(1+sT)^2'
    )
    templ.block.diff_vars = [d_s_2K_1_sT_2_x1, d_s_2K_1_sT_2_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        s_2K_1_sT_2_K: vf.add_const(None, name='K'),
        s_2K_1_sT_2_T: vf.add_const(None, name='T'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_s_2k_1_st_2_205_emt_template(vf=vf, name='s^2K/(1+sT)^2__205' if name is None else name)
