# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_b1s_b2ss_1_a1s_a2ss_192_emt_template(vf: VarFactory, name: str = '(1+b1s+b2ss)/(1+a1s+a2ss)__192') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_b1s_b2ss_1_a1s_a2ss_a1 = vf.add_var('(1+b1s+b2ss)/(1+a1s+a2ss)__a1_' + name)
    v_1_b1s_b2ss_1_a1s_a2ss_a2 = vf.add_var('(1+b1s+b2ss)/(1+a1s+a2ss)__a2_' + name)
    v_1_b1s_b2ss_1_a1s_a2ss_b1 = vf.add_var('(1+b1s+b2ss)/(1+a1s+a2ss)__b1_' + name)
    v_1_b1s_b2ss_1_a1s_a2ss_b2 = vf.add_var('(1+b1s+b2ss)/(1+a1s+a2ss)__b2_' + name)

    # --- State Variables ---
    v_1_b1s_b2ss_1_a1s_a2ss_x1 = vf.add_var('(1+b1s+b2ss)/(1+a1s+a2ss)__x1_' + name)
    v_1_b1s_b2ss_1_a1s_a2ss_x2 = vf.add_var('(1+b1s+b2ss)/(1+a1s+a2ss)__x2_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_b1s_b2ss_1_a1s_a2ss_dx1 = vf.add_var('(1+b1s+b2ss)/(1+a1s+a2ss)_dx1_' + name)
    v_1_b1s_b2ss_1_a1s_a2ss_dx2 = vf.add_var('(1+b1s+b2ss)/(1+a1s+a2ss)_dx2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_b1s_b2ss_1_a1s_a2ss_x1 = vf.add_diff_var('d_(1+b1s+b2ss)/(1+a1s+a2ss)__x1_' + name, base_var=v_1_b1s_b2ss_1_a1s_a2ss_x1)
    d_1_b1s_b2ss_1_a1s_a2ss_x2 = vf.add_diff_var('d_(1+b1s+b2ss)/(1+a1s+a2ss)__x2_' + name, base_var=v_1_b1s_b2ss_1_a1s_a2ss_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_b1s_b2ss_1_a1s_a2ss_dx1,
            v_1_b1s_b2ss_1_a1s_a2ss_dx2,
        ],
        state_vars=[v_1_b1s_b2ss_1_a1s_a2ss_x1, v_1_b1s_b2ss_1_a1s_a2ss_x2],
        algebraic_eqs=[
            (v_1_b1s_b2ss_1_a1s_a2ss_dx1 - v_1_b1s_b2ss_1_a1s_a2ss_x2),
            (v_1_b1s_b2ss_1_a1s_a2ss_dx2 - (((yi - v_1_b1s_b2ss_1_a1s_a2ss_x1) - (v_1_b1s_b2ss_1_a1s_a2ss_a1 * v_1_b1s_b2ss_1_a1s_a2ss_x2)) / v_1_b1s_b2ss_1_a1s_a2ss_a2)),
            (yo - ((v_1_b1s_b2ss_1_a1s_a2ss_x1 + (v_1_b1s_b2ss_1_a1s_a2ss_b1 * v_1_b1s_b2ss_1_a1s_a2ss_dx1)) + (v_1_b1s_b2ss_1_a1s_a2ss_b2 * v_1_b1s_b2ss_1_a1s_a2ss_dx2))),
        ],
        algebraic_vars=[v_1_b1s_b2ss_1_a1s_a2ss_dx1, v_1_b1s_b2ss_1_a1s_a2ss_dx2, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+b1s+b2ss)/(1+a1s+a2ss)'
    )
    templ.block.diff_vars = [d_1_b1s_b2ss_1_a1s_a2ss_x1, d_1_b1s_b2ss_1_a1s_a2ss_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_b1s_b2ss_1_a1s_a2ss_a1: vf.add_const(None, name='a1'),
        v_1_b1s_b2ss_1_a1s_a2ss_a2: vf.add_const(None, name='a2'),
        v_1_b1s_b2ss_1_a1s_a2ss_b1: vf.add_const(None, name='b1'),
        v_1_b1s_b2ss_1_a1s_a2ss_b2: vf.add_const(None, name='b2'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_b1s_b2ss_1_a1s_a2ss_192_emt_template(vf=vf, name='(1+b1s+b2ss)/(1+a1s+a2ss)__192' if name is None else name)
