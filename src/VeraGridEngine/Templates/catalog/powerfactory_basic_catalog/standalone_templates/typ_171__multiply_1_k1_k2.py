# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_multiply_1_k1_k2_171_emt_template(vf: VarFactory, name: str = 'Multiply (1-K1-K2)__171') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Multiply_1_K1_K2_K1 = vf.add_var('Multiply (1-K1-K2)__K1_' + name)
    Multiply_1_K1_K2_K2 = vf.add_var('Multiply (1-K1-K2)__K2_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - (((sym.Const(1.0) - Multiply_1_K1_K2_K1) - Multiply_1_K1_K2_K2) * yi)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Multiply (1-K1-K2)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Multiply_1_K1_K2_K1: vf.add_const(None, name='K1'),
        Multiply_1_K1_K2_K2: vf.add_const(None, name='K2'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_multiply_1_k1_k2_171_emt_template(vf=vf, name='Multiply (1-K1-K2)__171' if name is None else name)
