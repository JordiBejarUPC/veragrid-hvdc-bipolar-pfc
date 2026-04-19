# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_abc_dq0_power_invariant_align_a_q_545_emt_template(vf: VarFactory, name: str = 'abc->dq0 (power invariant -- align a->q)__545') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    a = vf.add_var('a_' + name)
    abc_dq0_power_invariant_align_a_q_one_sqrt2 = vf.add_var('abc->dq0 (power invariant -- align a->q)_one_sqrt2_' + name)
    abc_dq0_power_invariant_align_a_q_sqrt2_3 = vf.add_var('abc->dq0 (power invariant -- align a->q)_sqrt2_3_' + name)
    abc_dq0_power_invariant_align_a_q_twopi_3 = vf.add_var('abc->dq0 (power invariant -- align a->q)_twopi_3_' + name)
    b = vf.add_var('b_' + name)
    c = vf.add_var('c_' + name)
    d = vf.add_var('d_' + name)
    q = vf.add_var('q_' + name)
    theta = vf.add_var('theta_' + name)
    zero = vf.add_var('zero_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (d - (abc_dq0_power_invariant_align_a_q_sqrt2_3 * (((sym.sin(theta) * a) + (sym.sin((theta - abc_dq0_power_invariant_align_a_q_twopi_3)) * b)) + (sym.sin((theta + abc_dq0_power_invariant_align_a_q_twopi_3)) * c)))),
            (q - (abc_dq0_power_invariant_align_a_q_sqrt2_3 * (((sym.cos(theta) * a) + (sym.cos((theta - abc_dq0_power_invariant_align_a_q_twopi_3)) * b)) + (sym.cos((theta + abc_dq0_power_invariant_align_a_q_twopi_3)) * c)))),
            (zero - (abc_dq0_power_invariant_align_a_q_sqrt2_3 * (((abc_dq0_power_invariant_align_a_q_one_sqrt2 * a) + (abc_dq0_power_invariant_align_a_q_one_sqrt2 * b)) + (abc_dq0_power_invariant_align_a_q_one_sqrt2 * c)))),
        ],
        algebraic_vars=[d, q, zero],
        in_vars=[a, b, c, theta],
        out_vars=[d, q, zero],
        name='abc->dq0 (power invariant -- align a->q)'
    )
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        abc_dq0_power_invariant_align_a_q_sqrt2_3: sym.sqrt((sym.Const(2.0) / sym.Const(3.0))),
        abc_dq0_power_invariant_align_a_q_one_sqrt2: (sym.Const(1.0) / sym.sqrt(sym.Const(2.0))),
        abc_dq0_power_invariant_align_a_q_twopi_3: (sym.Const(6.283185307179586) / sym.Const(3.0)),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_abc_dq0_power_invariant_align_a_q_545_emt_template(vf=vf, name='abc->dq0 (power invariant -- align a->q)__545' if name is None else name)
