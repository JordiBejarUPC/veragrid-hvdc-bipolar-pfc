# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_clarke_transform_power_invariant_533_emt_template(vf: VarFactory, name: str = 'Clarke transform (power invariant)__533') -> EmtModelTemplate:
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
            (alpha - (((sym.sqrt((sym.Const(2.0) / sym.Const(3.0))) * a) - ((sym.Const(1.0) / sym.sqrt(sym.Const(6.0))) * b)) - ((sym.Const(1.0) / sym.sqrt(sym.Const(6.0))) * c))),
            (beta - (((sym.Const(1.0) / sym.sqrt(sym.Const(2.0))) * b) - (sym.sqrt(sym.Const(2.0)) * c))),
            (gamma - ((((sym.Const(1.0) / sym.sqrt(sym.Const(3.0))) * a) + ((sym.Const(1.0) / sym.sqrt(sym.Const(3.0))) * b)) + ((sym.Const(1.0) / sym.sqrt(sym.Const(3.0))) * c))),
        ],
        algebraic_vars=[alpha, beta, gamma],
        in_vars=[a, b, c],
        out_vars=[alpha, beta, gamma],
        name='Clarke transform (power invariant)'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_clarke_transform_power_invariant_533_emt_template(vf=vf, name='Clarke transform (power invariant)__533' if name is None else name)
