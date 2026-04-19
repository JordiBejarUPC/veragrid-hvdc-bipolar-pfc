# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_b1s_b2ss_1_a1s_a2ss_bypass_190_emt_template(vf: VarFactory, name: str = '(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__190') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_A1 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__A1_' + name)
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_A2 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__A2_' + name)
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_B1 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__B1_' + name)
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_B2 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__B2_' + name)

    # --- State Variables ---
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_x1 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__x1_' + name)
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_x2 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__x2_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_0 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__proc_selfix_0_' + name)
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_1 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__proc_selfix_1_' + name)
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_2 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__proc_selfix_2_' + name)
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx1 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass_dx1_' + name)
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx2 = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass_dx2_' + name)
    v_1_B1s_B2ss_1_A1s_A2ss_bypass_triv = vf.add_var('(1+B1s+B2ss)/(1+A1s+A2ss) _bypass_triv_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_B1s_B2ss_1_A1s_A2ss_bypass_x1 = vf.add_diff_var('d_(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__x1_' + name, base_var=v_1_B1s_B2ss_1_A1s_A2ss_bypass_x1)
    d_1_B1s_B2ss_1_A1s_A2ss_bypass_x2 = vf.add_diff_var('d_(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__x2_' + name, base_var=v_1_B1s_B2ss_1_A1s_A2ss_bypass_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx1,
            v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx2,
        ],
        state_vars=[v_1_B1s_B2ss_1_A1s_A2ss_bypass_x1, v_1_B1s_B2ss_1_A1s_A2ss_bypass_x2],
        algebraic_eqs=[
            (v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx1 - ((v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_0 * sym.Const(0.0)) + ((sym.Const(1.0) - v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_0) * v_1_B1s_B2ss_1_A1s_A2ss_bypass_x2))),
            (v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx2 - ((v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_1) * (((yi - v_1_B1s_B2ss_1_A1s_A2ss_bypass_x1) - (v_1_B1s_B2ss_1_A1s_A2ss_bypass_A1 * v_1_B1s_B2ss_1_A1s_A2ss_bypass_x2)) / v_1_B1s_B2ss_1_A1s_A2ss_bypass_A2)))),
            (yo - ((v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_2 * yi) + ((sym.Const(1.0) - v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_2) * ((v_1_B1s_B2ss_1_A1s_A2ss_bypass_x1 + (v_1_B1s_B2ss_1_A1s_A2ss_bypass_B1 * v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx1)) + (v_1_B1s_B2ss_1_A1s_A2ss_bypass_B2 * v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx2))))),
        ],
        algebraic_vars=[v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx1, v_1_B1s_B2ss_1_A1s_A2ss_bypass_dx2, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+B1s+B2ss)/(1+A1s+A2ss) _bypass'
    )
    templ.block.diff_vars = [d_1_B1s_B2ss_1_A1s_A2ss_bypass_x1, d_1_B1s_B2ss_1_A1s_A2ss_bypass_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_B1s_B2ss_1_A1s_A2ss_bypass_A1: vf.add_const(None, name='A1'),
        v_1_B1s_B2ss_1_A1s_A2ss_bypass_A2: vf.add_const(None, name='A2'),
        v_1_B1s_B2ss_1_A1s_A2ss_bypass_B1: vf.add_const(None, name='B1'),
        v_1_B1s_B2ss_1_A1s_A2ss_bypass_B2: vf.add_const(None, name='B2'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_0: vf.add_const(0.0, name=''),
        v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
        v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        v_1_B1s_B2ss_1_A1s_A2ss_bypass_triv: (((sym.heaviside(((sym.Const(0.0) - sym.abs(v_1_B1s_B2ss_1_A1s_A2ss_bypass_A1)) + sym.Const(1e-06))) * sym.heaviside(((sym.Const(0.0) - sym.abs(v_1_B1s_B2ss_1_A1s_A2ss_bypass_A2)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - sym.abs(v_1_B1s_B2ss_1_A1s_A2ss_bypass_B1)) + sym.Const(1e-06)))) * sym.heaviside(((sym.Const(0.0) - sym.abs(v_1_B1s_B2ss_1_A1s_A2ss_bypass_B2)) + sym.Const(1e-06)))),
    }
    templ.block.procedural_logic = [
        selfix(v_1_B1s_B2ss_1_A1s_A2ss_bypass_triv, output=v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_0),
        selfix(v_1_B1s_B2ss_1_A1s_A2ss_bypass_triv, output=v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_1),
        selfix(v_1_B1s_B2ss_1_A1s_A2ss_bypass_triv, output=v_1_B1s_B2ss_1_A1s_A2ss_bypass_proc_selfix_2),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_b1s_b2ss_1_a1s_a2ss_bypass_190_emt_template(vf=vf, name='(1+B1s+B2ss)/(1+A1s+A2ss) _bypass__190' if name is None else name)
