# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_k_1_st_sp_148_emt_template(vf: VarFactory, name: str = 'K/(1+sT) (sp__148') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_1_sT_sp_K = vf.add_var('K/(1+sT) (sp__K_' + name)
    K_1_sT_sp_T = vf.add_var('K/(1+sT) (sp__T_' + name)
    K_1_sT_sp_y_max = vf.add_var('K/(1+sT) (sp__y_max_' + name)
    K_1_sT_sp_y_min = vf.add_var('K/(1+sT) (sp__y_min_' + name)

    # --- State Variables ---
    K_1_sT_sp_x = vf.add_var('K/(1+sT) (sp__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    ylim = vf.add_var('ylim_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_1_sT_sp_x = vf.add_diff_var('d_K/(1+sT) (sp__x_' + name, base_var=K_1_sT_sp_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (((K_1_sT_sp_K * yi) - K_1_sT_sp_x) / K_1_sT_sp_T),
        ],
        state_vars=[K_1_sT_sp_x],
        algebraic_eqs=[
            (yo - (((K_1_sT_sp_y_min * ylim) + ((K_1_sT_sp_x - (K_1_sT_sp_y_min * ylim)) * sym.heaviside((K_1_sT_sp_x - (K_1_sT_sp_y_min * ylim))))) - ((K_1_sT_sp_x - (K_1_sT_sp_y_max * ylim)) * sym.heaviside((K_1_sT_sp_x - (K_1_sT_sp_y_max * ylim)))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, ylim],
        out_vars=[yo],
        name='K/(1+sT) (sp'
    )
    templ.block.diff_vars = [d_K_1_sT_sp_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_1_sT_sp_K: vf.add_const(None, name='K'),
        K_1_sT_sp_T: vf.add_const(None, name='T'),
        K_1_sT_sp_y_max: vf.add_const(None, name='y_max'),
        K_1_sT_sp_y_min: vf.add_const(None, name='y_min'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_1_st_sp_148_emt_template(vf=vf, name='K/(1+sT) (sp__148' if name is None else name)
