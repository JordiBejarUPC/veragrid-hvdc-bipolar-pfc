# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_dq0_abc_power_invariant_align_a_d_548_emt_template(vf: VarFactory, name: str = 'dq0->abc (power invariant -- align a->d)__548') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    a = vf.add_var('a_' + name)
    b = vf.add_var('b_' + name)
    c = vf.add_var('c_' + name)
    d = vf.add_var('d_' + name)
    dq0_abc_power_invariant_align_a_d_one_sqrt2 = vf.add_var('dq0->abc (power invariant -- align a->d)_one_sqrt2_' + name)
    dq0_abc_power_invariant_align_a_d_sqrt2_3 = vf.add_var('dq0->abc (power invariant -- align a->d)_sqrt2_3_' + name)
    dq0_abc_power_invariant_align_a_d_twopi_3 = vf.add_var('dq0->abc (power invariant -- align a->d)_twopi_3_' + name)
    q = vf.add_var('q_' + name)
    theta = vf.add_var('theta_' + name)
    zero = vf.add_var('zero_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (a - (dq0_abc_power_invariant_align_a_d_sqrt2_3 * (((sym.cos(theta) * d) - (sym.sin(theta) * q)) + (dq0_abc_power_invariant_align_a_d_one_sqrt2 * zero)))),
            (b - (dq0_abc_power_invariant_align_a_d_sqrt2_3 * (((sym.cos((theta - dq0_abc_power_invariant_align_a_d_twopi_3)) * d) - (sym.sin((theta - dq0_abc_power_invariant_align_a_d_twopi_3)) * q)) + (dq0_abc_power_invariant_align_a_d_one_sqrt2 * zero)))),
            (c - (dq0_abc_power_invariant_align_a_d_sqrt2_3 * (((sym.cos((theta + dq0_abc_power_invariant_align_a_d_twopi_3)) * d) - (sym.sin((theta + dq0_abc_power_invariant_align_a_d_twopi_3)) * q)) + (dq0_abc_power_invariant_align_a_d_one_sqrt2 * zero)))),
        ],
        algebraic_vars=[a, b, c],
        in_vars=[d, q, zero, theta],
        out_vars=[a, b, c],
        name='dq0->abc (power invariant -- align a->d)'
    )
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        dq0_abc_power_invariant_align_a_d_sqrt2_3: sym.sqrt((sym.Const(2.0) / sym.Const(3.0))),
        dq0_abc_power_invariant_align_a_d_one_sqrt2: (sym.Const(1.0) / sym.sqrt(sym.Const(2.0))),
        dq0_abc_power_invariant_align_a_d_twopi_3: (sym.Const(6.283185307179586) / sym.Const(3.0)),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_dq0_abc_power_invariant_align_a_d_548_emt_template(vf=vf, name='dq0->abc (power invariant -- align a->d)__548' if name is None else name)
