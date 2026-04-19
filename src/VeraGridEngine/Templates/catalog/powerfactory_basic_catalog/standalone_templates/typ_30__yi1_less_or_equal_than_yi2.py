# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_yi1_less_or_equal_than_yi2_30_emt_template(vf: VarFactory, name: str = 'yi1 less or equal than yi2__30') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi1 = vf.add_var('yi1_' + name)
    yi1_less_or_equal_than_yi2_proc_select_const_0 = vf.add_var('yi1 less or equal than yi2__proc_select_const_0_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((yi1_less_or_equal_than_yi2_proc_select_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - yi1_less_or_equal_than_yi2_proc_select_const_0) * sym.Const(0.0)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi1, yi2],
        out_vars=[yo],
        name='yi1 less or equal than yi2'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        yi1_less_or_equal_than_yi2_proc_select_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=yi1_less_or_equal_than_yi2_proc_select_const_0, source=(yi1 <= yi2)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_yi1_less_or_equal_than_yi2_30_emt_template(vf=vf, name='yi1 less or equal than yi2__30' if name is None else name)
