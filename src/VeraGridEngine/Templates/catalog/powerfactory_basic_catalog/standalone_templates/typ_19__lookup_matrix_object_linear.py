# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_lookup_matrix_object_linear_19_emt_template(vf: VarFactory, name: str = 'Lookup matrix object (linear)__19') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Lookup_matrix_object_linear_omatrix_K = vf.add_var('Lookup matrix object (linear)__omatrix_K_' + name)

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
        name='Lookup matrix object (linear)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Lookup_matrix_object_linear_omatrix_K: vf.add_const(None, name='omatrix_K'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_lookup_matrix_object_linear_19_emt_template(vf=vf, name='Lookup matrix object (linear)__19' if name is None else name)
