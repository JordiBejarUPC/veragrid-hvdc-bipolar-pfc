# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_yi_greater_than_or_equal_c_23_emt_template(vf: VarFactory, name: str = 'yi greater than or equal C__23') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    yi_greater_than_or_equal_C_C = vf.add_var('yi greater than or equal C__C_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yi_greater_than_or_equal_C_proc_select_const_0 = vf.add_var('yi greater than or equal C__proc_select_const_0_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((yi_greater_than_or_equal_C_proc_select_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - yi_greater_than_or_equal_C_proc_select_const_0) * sym.Const(0.0)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='yi greater than or equal C'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        yi_greater_than_or_equal_C_C: vf.add_const(None, name='C'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        yi_greater_than_or_equal_C_proc_select_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=yi_greater_than_or_equal_C_proc_select_const_0, source=(yi >= yi_greater_than_or_equal_C_C)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_yi_greater_than_or_equal_c_23_emt_template(vf=vf, name='yi greater than or equal C__23' if name is None else name)
