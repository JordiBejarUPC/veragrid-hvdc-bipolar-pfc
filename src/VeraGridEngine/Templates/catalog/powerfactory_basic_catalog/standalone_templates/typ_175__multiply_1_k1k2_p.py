# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_multiply_1_k1k2_p_175_emt_template(vf: VarFactory, name: str = 'Multiply 1/K1K2 [p__175') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Multiply_1_K1K2_p_K1 = vf.add_var('Multiply 1/K1K2 [p__K1_' + name)
    Multiply_1_K1K2_p_K2 = vf.add_var('Multiply 1/K1K2 [p__K2_' + name)
    Multiply_1_K1K2_p_y_max = vf.add_var('Multiply 1/K1K2 [p__y_max_' + name)
    Multiply_1_K1K2_p_y_min = vf.add_var('Multiply 1/K1K2 [p__y_min_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Multiply_1_K1K2_p_y_min + (((yi / (Multiply_1_K1K2_p_K1 * Multiply_1_K1K2_p_K2)) - Multiply_1_K1K2_p_y_min) * sym.heaviside(((yi / (Multiply_1_K1K2_p_K1 * Multiply_1_K1K2_p_K2)) - Multiply_1_K1K2_p_y_min)))) - (((yi / (Multiply_1_K1K2_p_K1 * Multiply_1_K1K2_p_K2)) - Multiply_1_K1K2_p_y_max) * sym.heaviside(((yi / (Multiply_1_K1K2_p_K1 * Multiply_1_K1K2_p_K2)) - Multiply_1_K1K2_p_y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Multiply 1/K1K2 [p'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Multiply_1_K1K2_p_K1: vf.add_const(None, name='K1'),
        Multiply_1_K1K2_p_K2: vf.add_const(None, name='K2'),
        Multiply_1_K1K2_p_y_max: vf.add_const(None, name='y_max'),
        Multiply_1_K1K2_p_y_min: vf.add_const(None, name='y_min'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_multiply_1_k1k2_p_175_emt_template(vf=vf, name='Multiply 1/K1K2 [p__175' if name is None else name)
