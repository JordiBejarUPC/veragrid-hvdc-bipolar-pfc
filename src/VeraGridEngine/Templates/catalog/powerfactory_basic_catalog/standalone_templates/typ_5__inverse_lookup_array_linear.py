# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_inverse_lookup_array_linear_5_emt_template(vf: VarFactory, name: str = 'Inverse Lookup array (linear)__5') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Inverse_Lookup_array_linear_array_K = vf.add_var('Inverse Lookup array (linear)__array_K_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        in_vars=[yi],
        out_vars=[yo],
        name='Inverse Lookup array (linear)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Inverse_Lookup_array_linear_array_K: vf.add_const(None, name='array_K'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_inverse_lookup_array_linear_5_emt_template(vf=vf, name='Inverse Lookup array (linear)__5' if name is None else name)
