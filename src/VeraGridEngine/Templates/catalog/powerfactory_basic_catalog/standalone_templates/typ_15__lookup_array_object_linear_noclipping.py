# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_lookup_array_object_linear_noclipping_15_emt_template(vf: VarFactory, name: str = 'Lookup array object (linear_noclipping)__15') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Lookup_array_object_linear_noclipping_oarray_K = vf.add_var('Lookup array object (linear_noclipping)__oarray_K_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        in_vars=[yi],
        out_vars=[yo],
        name='Lookup array object (linear_noclipping)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Lookup_array_object_linear_noclipping_oarray_K: vf.add_const(None, name='oarray_K'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_lookup_array_object_linear_noclipping_15_emt_template(vf=vf, name='Lookup array object (linear_noclipping)__15' if name is None else name)
