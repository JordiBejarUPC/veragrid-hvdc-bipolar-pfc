# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_k_s_p_234_emt_template(vf: VarFactory, name: str = 'K/s (p__234') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_s_p_K = vf.add_var('K/s (p__K_' + name)
    K_s_p_y_max = vf.add_var('K/s (p__y_max_' + name)
    K_s_p_y_min = vf.add_var('K/s (p__y_min_' + name)

    # --- State Variables ---
    K_s_p_x = vf.add_var('K/s (p__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_s_p_x = vf.add_diff_var('d_K/s (p__x_' + name, base_var=K_s_p_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (K_s_p_K * yi),
        ],
        state_vars=[K_s_p_x],
        algebraic_eqs=[
            (yo - ((K_s_p_y_min + ((K_s_p_x - K_s_p_y_min) * sym.heaviside((K_s_p_x - K_s_p_y_min)))) - ((K_s_p_x - K_s_p_y_max) * sym.heaviside((K_s_p_x - K_s_p_y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='K/s (p'
    )
    templ.block.diff_vars = [d_K_s_p_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_s_p_K: vf.add_const(None, name='K'),
        K_s_p_y_max: vf.add_const(None, name='y_max'),
        K_s_p_y_min: vf.add_const(None, name='y_min'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_s_p_234_emt_template(vf=vf, name='K/s (p__234' if name is None else name)
