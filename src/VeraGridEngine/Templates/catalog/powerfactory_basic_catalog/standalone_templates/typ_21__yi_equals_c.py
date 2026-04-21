# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_yi_equals_c_21_emt_template(vf: VarFactory, name: str = 'yi equals C__21') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    yi_equals_C_C = vf.add_var('yi equals C__C_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yi_equals_C_proc_select_const_0 = vf.add_var('yi equals C__proc_select_const_0_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((yi_equals_C_proc_select_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - yi_equals_C_proc_select_const_0) * sym.Const(0.0)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='yi equals C'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        yi_equals_C_C: vf.add_const(None, name='C'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        yi_equals_C_proc_select_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=yi_equals_C_proc_select_const_0, source=sym.Comparison(lhs=yi, op=sym.CmpOp.EQ, rhs=yi_equals_C_C)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_yi_equals_c_21_emt_template(vf=vf, name='yi equals C__21' if name is None else name)
