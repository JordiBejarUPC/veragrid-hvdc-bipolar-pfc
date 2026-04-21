# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_c_49_emt_template(vf: VarFactory, name: str = '-C__49') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    C_C = vf.add_var('-C__C_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - (-C_C)),
        ],
        algebraic_vars=[yo],
        out_vars=[yo],
        name='-C'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        C_C: vf.add_const(None, name='C'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_c_49_emt_template(vf=vf, name='-C__49' if name is None else name)
