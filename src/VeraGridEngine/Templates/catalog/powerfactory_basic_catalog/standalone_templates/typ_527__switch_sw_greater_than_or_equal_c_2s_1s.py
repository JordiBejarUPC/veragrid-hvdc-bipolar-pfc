# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_switch_sw_greater_than_or_equal_c_2s_1s_527_emt_template(vf: VarFactory, name: str = 'Switch sw greater than or equal C 2s->1s__527') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Switch_sw_greater_than_or_equal_C_2s_1s_C = vf.add_var('Switch sw greater than or equal C 2s->1s__C_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Switch_sw_greater_than_or_equal_C_2s_1s_proc_select_0 = vf.add_var('Switch sw greater than or equal C 2s->1s__proc_select_0_' + name)
    sw = vf.add_var('sw_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Switch_sw_greater_than_or_equal_C_2s_1s_proc_select_0 * yi1) + ((sym.Const(1.0) - Switch_sw_greater_than_or_equal_C_2s_1s_proc_select_0) * yi2))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi1, sw, yi2],
        out_vars=[yo],
        name='Switch sw greater than or equal C 2s->1s'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Switch_sw_greater_than_or_equal_C_2s_1s_C: vf.add_const(None, name='C'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Switch_sw_greater_than_or_equal_C_2s_1s_proc_select_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Switch_sw_greater_than_or_equal_C_2s_1s_proc_select_0, source=(sw >= Switch_sw_greater_than_or_equal_C_2s_1s_C)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_switch_sw_greater_than_or_equal_c_2s_1s_527_emt_template(vf=vf, name='Switch sw greater than or equal C 2s->1s__527' if name is None else name)
