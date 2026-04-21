# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_switch_par_2_1_by_sig_511_emt_template(vf: VarFactory, name: str = 'Switch par 2->1 by sig__511') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Switch_par_2_1_by_sig_K1 = vf.add_var('Switch par 2->1 by sig__K1_' + name)
    Switch_par_2_1_by_sig_K2 = vf.add_var('Switch par 2->1 by sig__K2_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Switch_par_2_1_by_sig_proc_select_const_0 = vf.add_var('Switch par 2->1 by sig__proc_select_const_0_' + name)
    sw = vf.add_var('sw_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Switch_par_2_1_by_sig_proc_select_const_0 * Switch_par_2_1_by_sig_K2) + ((sym.Const(1.0) - Switch_par_2_1_by_sig_proc_select_const_0) * Switch_par_2_1_by_sig_K1))),
        ],
        algebraic_vars=[yo],
        in_vars=[sw],
        out_vars=[yo],
        name='Switch par 2->1 by sig'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Switch_par_2_1_by_sig_K1: vf.add_const(None, name='K1'),
        Switch_par_2_1_by_sig_K2: vf.add_const(None, name='K2'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Switch_par_2_1_by_sig_proc_select_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Switch_par_2_1_by_sig_proc_select_const_0, source=(sw > 0.0)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_switch_par_2_1_by_sig_511_emt_template(vf=vf, name='Switch par 2->1 by sig__511' if name is None else name)
