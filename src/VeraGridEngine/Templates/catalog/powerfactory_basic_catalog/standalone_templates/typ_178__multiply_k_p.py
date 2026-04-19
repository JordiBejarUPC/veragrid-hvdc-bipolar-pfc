# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_multiply_k_p_178_emt_template(vf: VarFactory, name: str = 'Multiply K [p__178') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Multiply_K_p_K = vf.add_var('Multiply K [p__K_' + name)
    Multiply_K_p_y_max = vf.add_var('Multiply K [p__y_max_' + name)
    Multiply_K_p_y_min = vf.add_var('Multiply K [p__y_min_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Multiply_K_p_y_min + (((Multiply_K_p_K * yi) - Multiply_K_p_y_min) * sym.heaviside(((Multiply_K_p_K * yi) - Multiply_K_p_y_min)))) - (((Multiply_K_p_K * yi) - Multiply_K_p_y_max) * sym.heaviside(((Multiply_K_p_K * yi) - Multiply_K_p_y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Multiply K [p'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Multiply_K_p_K: vf.add_const(None, name='K'),
        Multiply_K_p_y_max: vf.add_const(None, name='y_max'),
        Multiply_K_p_y_min: vf.add_const(None, name='y_min'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_multiply_k_p_178_emt_template(vf=vf, name='Multiply K [p__178' if name is None else name)
