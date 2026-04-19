# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import delay, selfix
from VeraGridEngine.enumerations import DeviceType

def get_e_st_bypass_102_emt_template(vf: VarFactory, name: str = 'e^-sT _bypass__102') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    e_sT_bypass_T = vf.add_var('e^-sT _bypass__T_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    e_sT_bypass_proc_delay_0 = vf.add_var('e^-sT _bypass__proc_delay_0_' + name)
    e_sT_bypass_proc_selfix_1 = vf.add_var('e^-sT _bypass__proc_selfix_1_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((e_sT_bypass_proc_selfix_1 * e_sT_bypass_proc_delay_0) + ((sym.Const(1.0) - e_sT_bypass_proc_selfix_1) * yi))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='e^-sT _bypass'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        e_sT_bypass_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        e_sT_bypass_proc_delay_0: vf.add_const(0.0, name=''),
        e_sT_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        delay(yi, e_sT_bypass_T, output=e_sT_bypass_proc_delay_0),
        selfix((e_sT_bypass_T > 0.0), output=e_sT_bypass_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_e_st_bypass_102_emt_template(vf=vf, name='e^-sT _bypass__102' if name is None else name)
