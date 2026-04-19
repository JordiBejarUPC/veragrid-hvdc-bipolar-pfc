# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_a0_sa1_ssa2_b0_sb1_ssb2_bypass_197_emt_template(vf: VarFactory, name: str = '(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__197') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_A0 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__A0_' + name)
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_A1 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__A1_' + name)
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_A2 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__A2_' + name)
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_B0 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__B0_' + name)
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_B1 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__B1_' + name)
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_B2 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__B2_' + name)

    # --- State Variables ---
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_x1 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__x1_' + name)
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_x2 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__x2_' + name)

    # --- Algebraic / Shared Variables ---
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_0 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__proc_selfix_0_' + name)
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_1 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__proc_selfix_1_' + name)
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx1 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass_dx1_' + name)
    A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx2 = vf.add_var('(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass_dx2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_A0_sA1_ssA2_B0_sB1_ssB2_bypass_x1 = vf.add_diff_var('d_(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__x1_' + name, base_var=A0_sA1_ssA2_B0_sB1_ssB2_bypass_x1)
    d_A0_sA1_ssA2_B0_sB1_ssB2_bypass_x2 = vf.add_diff_var('d_(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__x2_' + name, base_var=A0_sA1_ssA2_B0_sB1_ssB2_bypass_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx1,
            A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx2,
        ],
        state_vars=[A0_sA1_ssA2_B0_sB1_ssB2_bypass_x1, A0_sA1_ssA2_B0_sB1_ssB2_bypass_x2],
        algebraic_eqs=[
            (A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx1 - ((A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_0 * A0_sA1_ssA2_B0_sB1_ssB2_bypass_x2) + ((sym.Const(1.0) - A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_0) * ((yi - (A0_sA1_ssA2_B0_sB1_ssB2_bypass_B0 * A0_sA1_ssA2_B0_sB1_ssB2_bypass_x1)) / A0_sA1_ssA2_B0_sB1_ssB2_bypass_B1)))),
            (A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx2 - ((A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_1 * (((yi - (A0_sA1_ssA2_B0_sB1_ssB2_bypass_B0 * A0_sA1_ssA2_B0_sB1_ssB2_bypass_x1)) - (A0_sA1_ssA2_B0_sB1_ssB2_bypass_B1 * A0_sA1_ssA2_B0_sB1_ssB2_bypass_x2)) / A0_sA1_ssA2_B0_sB1_ssB2_bypass_B2)) + ((sym.Const(1.0) - A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_1) * sym.Const(0.0)))),
            (yo - (((A0_sA1_ssA2_B0_sB1_ssB2_bypass_A0 * A0_sA1_ssA2_B0_sB1_ssB2_bypass_x1) + (A0_sA1_ssA2_B0_sB1_ssB2_bypass_A1 * A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx1)) + (A0_sA1_ssA2_B0_sB1_ssB2_bypass_A2 * A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx2))),
        ],
        algebraic_vars=[A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx1, A0_sA1_ssA2_B0_sB1_ssB2_bypass_dx2, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass'
    )
    templ.block.diff_vars = [d_A0_sA1_ssA2_B0_sB1_ssB2_bypass_x1, d_A0_sA1_ssA2_B0_sB1_ssB2_bypass_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        A0_sA1_ssA2_B0_sB1_ssB2_bypass_B0: vf.add_const(None, name='B0'),
        A0_sA1_ssA2_B0_sB1_ssB2_bypass_B1: vf.add_const(None, name='B1'),
        A0_sA1_ssA2_B0_sB1_ssB2_bypass_B2: vf.add_const(None, name='B2'),
        A0_sA1_ssA2_B0_sB1_ssB2_bypass_A0: vf.add_const(None, name='A0'),
        A0_sA1_ssA2_B0_sB1_ssB2_bypass_A1: vf.add_const(None, name='A1'),
        A0_sA1_ssA2_B0_sB1_ssB2_bypass_A2: vf.add_const(None, name='A2'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_0: vf.add_const(0.0, name=''),
        A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((A0_sA1_ssA2_B0_sB1_ssB2_bypass_B2 > 0.0), output=A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_0),
        selfix((A0_sA1_ssA2_B0_sB1_ssB2_bypass_B2 > 0.0), output=A0_sA1_ssA2_B0_sB1_ssB2_bypass_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_a0_sa1_ssa2_b0_sb1_ssb2_bypass_197_emt_template(vf=vf, name='(A0+sA1+ssA2)/(B0+sB1+ssB2) _bypass__197' if name is None else name)
