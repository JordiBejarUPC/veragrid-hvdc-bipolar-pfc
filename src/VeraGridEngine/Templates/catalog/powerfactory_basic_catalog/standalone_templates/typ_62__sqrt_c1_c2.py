# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_sqrt_c1_c2_62_emt_template(vf: VarFactory, name: str = 'SQRT(C1/C2)__62') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    SQRT_C1_C2_C1 = vf.add_var('SQRT(C1/C2)__C1_' + name)
    SQRT_C1_C2_C2 = vf.add_var('SQRT(C1/C2)__C2_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    SQRT_C1_C2_yo0 = vf.add_var('SQRT(C1/C2)_yo0_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - SQRT_C1_C2_yo0),
        ],
        algebraic_vars=[yo],
        out_vars=[yo],
        name='SQRT(C1/C2)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        SQRT_C1_C2_C1: vf.add_const(None, name='C1'),
        SQRT_C1_C2_C2: vf.add_const(None, name='C2'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        SQRT_C1_C2_yo0: sym.sqrt((SQRT_C1_C2_C1 / SQRT_C1_C2_C2)),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_sqrt_c1_c2_62_emt_template(vf=vf, name='SQRT(C1/C2)__62' if name is None else name)
