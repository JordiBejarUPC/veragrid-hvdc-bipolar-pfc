# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_inverse_clarke_transform_pow_invariant_535_emt_template(vf: VarFactory, name: str = 'Inverse Clarke transform(pow. invariant)__535') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    a = vf.add_var('a_' + name)
    alpha = vf.add_var('alpha_' + name)
    b = vf.add_var('b_' + name)
    beta = vf.add_var('beta_' + name)
    c = vf.add_var('c_' + name)
    gamma = vf.add_var('gamma_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (a - ((sym.sqrt((sym.Const(2.0) / sym.Const(3.0))) * alpha) + ((sym.Const(1.0) / sym.sqrt(sym.Const(3.0))) * gamma))),
            (b - (((((-sym.Const(1.0)) / sym.sqrt(sym.Const(6.0))) * alpha) + ((sym.Const(1.0) / sym.sqrt(sym.Const(2.0))) * beta)) + ((sym.Const(1.0) / sym.sqrt(sym.Const(3.0))) * gamma))),
            (c - (((((-sym.Const(1.0)) / sym.sqrt(sym.Const(6.0))) * alpha) - ((sym.Const(1.0) / sym.sqrt(sym.Const(2.0))) * beta)) + ((sym.Const(1.0) / sym.sqrt(sym.Const(3.0))) * gamma))),
        ],
        algebraic_vars=[a, b, c],
        in_vars=[alpha, beta, gamma],
        out_vars=[a, b, c],
        name='Inverse Clarke transform(pow. invariant)'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_inverse_clarke_transform_pow_invariant_535_emt_template(vf=vf, name='Inverse Clarke transform(pow. invariant)__535' if name is None else name)
