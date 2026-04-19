# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_or4_343_emt_template(vf: VarFactory, name: str = 'OR4__343') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    OR4_proc_select_const_0 = vf.add_var('OR4__proc_select_const_0_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yi3 = vf.add_var('yi3_' + name)
    yi4 = vf.add_var('yi4_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((OR4_proc_select_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - OR4_proc_select_const_0) * sym.Const(0.0)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi1, yi2, yi3, yi4],
        out_vars=[yo],
        name='OR4'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        OR4_proc_select_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=OR4_proc_select_const_0, source=(1.0 - ((1.0 - (1.0 - ((1.0 - (1.0 - ((1.0 - yi1) * (1.0 - yi2)))) * (1.0 - yi3)))) * (1.0 - yi4)))),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_or4_343_emt_template(vf=vf, name='OR4__343' if name is None else name)
