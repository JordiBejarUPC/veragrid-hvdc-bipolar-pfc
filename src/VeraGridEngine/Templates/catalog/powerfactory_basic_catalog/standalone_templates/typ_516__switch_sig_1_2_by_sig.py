# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_switch_sig_1_2_by_sig_516_emt_template(vf: VarFactory, name: str = 'Switch sig 1->2 by sig__516') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Switch_sig_1_2_by_sig_proc_select_2 = vf.add_var('Switch sig 1->2 by sig__proc_select_2_' + name)
    Switch_sig_1_2_by_sig_proc_select_3 = vf.add_var('Switch sig 1->2 by sig__proc_select_3_' + name)
    Switch_sig_1_2_by_sig_proc_selfix_0 = vf.add_var('Switch sig 1->2 by sig__proc_selfix_0_' + name)
    Switch_sig_1_2_by_sig_proc_selfix_1 = vf.add_var('Switch sig 1->2 by sig__proc_selfix_1_' + name)
    sw = vf.add_var('sw_' + name)
    yi = vf.add_var('yi_' + name)
    yo1 = vf.add_var('yo1_' + name)
    yo2 = vf.add_var('yo2_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo1 - ((Switch_sig_1_2_by_sig_proc_select_2 * sym.Const(0.0)) + ((sym.Const(1.0) - Switch_sig_1_2_by_sig_proc_select_2) * yi))),
            (yo2 - ((Switch_sig_1_2_by_sig_proc_select_3 * yi) + ((sym.Const(1.0) - Switch_sig_1_2_by_sig_proc_select_3) * sym.Const(0.0)))),
        ],
        algebraic_vars=[yo1, yo2],
        in_vars=[yi, sw],
        out_vars=[yo1, yo2],
        name='Switch sig 1->2 by sig'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Switch_sig_1_2_by_sig_proc_selfix_0: vf.add_const(0.0, name=''),
        Switch_sig_1_2_by_sig_proc_selfix_1: vf.add_const(0.0, name=''),
        Switch_sig_1_2_by_sig_proc_select_2: vf.add_const(0.0, name=''),
        Switch_sig_1_2_by_sig_proc_select_3: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo1: ((Switch_sig_1_2_by_sig_proc_selfix_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Switch_sig_1_2_by_sig_proc_selfix_0) * yi)),
        yo2: ((Switch_sig_1_2_by_sig_proc_selfix_1 * yi) + ((sym.Const(1.0) - Switch_sig_1_2_by_sig_proc_selfix_1) * sym.Const(0.0))),
    }
    templ.block.procedural_logic = [
        selfix(sw, output=Switch_sig_1_2_by_sig_proc_selfix_0),
        selfix(sw, output=Switch_sig_1_2_by_sig_proc_selfix_1),
        sampled_value(output=Switch_sig_1_2_by_sig_proc_select_2, source=sw),
        sampled_value(output=Switch_sig_1_2_by_sig_proc_select_3, source=sw),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_switch_sig_1_2_by_sig_516_emt_template(vf=vf, name='Switch sig 1->2 by sig__516' if name is None else name)
