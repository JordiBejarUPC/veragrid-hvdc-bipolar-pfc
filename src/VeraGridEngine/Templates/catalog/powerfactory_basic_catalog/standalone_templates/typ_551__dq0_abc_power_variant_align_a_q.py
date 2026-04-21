# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_dq0_abc_power_variant_align_a_q_551_emt_template(vf: VarFactory, name: str = 'dq0->abc (power variant -- align a->q)__551') -> EmtModelTemplate:
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
    dq0_abc_power_variant_align_a_q_twopi_3 = vf.add_var('dq0->abc (power variant -- align a->q)_twopi_3_' + name)
    q = vf.add_var('q_' + name)
    theta = vf.add_var('theta_' + name)
    zero = vf.add_var('zero_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (a - (((sym.sin(theta) * d) + (sym.cos(theta) * q)) + zero)),
            (b - (((sym.sin((theta - dq0_abc_power_variant_align_a_q_twopi_3)) * d) + (sym.cos((theta - dq0_abc_power_variant_align_a_q_twopi_3)) * q)) + zero)),
            (c - (((sym.sin((theta + dq0_abc_power_variant_align_a_q_twopi_3)) * d) + (sym.cos((theta + dq0_abc_power_variant_align_a_q_twopi_3)) * q)) + zero)),
        ],
        algebraic_vars=[a, b, c],
        in_vars=[d, q, zero, theta],
        out_vars=[a, b, c],
        name='dq0->abc (power variant -- align a->q)'
    )
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        dq0_abc_power_variant_align_a_q_twopi_3: (sym.Const(6.283185307179586) / sym.Const(3.0)),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_dq0_abc_power_variant_align_a_q_551_emt_template(vf=vf, name='dq0->abc (power variant -- align a->q)__551' if name is None else name)
