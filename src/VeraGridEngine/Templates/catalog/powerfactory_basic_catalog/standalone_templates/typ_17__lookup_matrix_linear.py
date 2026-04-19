# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_lookup_matrix_linear_17_emt_template(vf: VarFactory, name: str = 'Lookup matrix (linear)__17') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Lookup_matrix_linear_matrix_K = vf.add_var('Lookup matrix (linear)__matrix_K_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        in_vars=[yi1, yi2],
        out_vars=[yo],
        name='Lookup matrix (linear)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Lookup_matrix_linear_matrix_K: vf.add_const(None, name='matrix_K'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_lookup_matrix_linear_17_emt_template(vf=vf, name='Lookup matrix (linear)__17' if name is None else name)
