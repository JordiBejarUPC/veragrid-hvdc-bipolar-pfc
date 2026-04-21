# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_switch_sig_1_2_by_par_bool_514_emt_template(vf: VarFactory, name: str = 'Switch sig 1->2 by par (bool)__514') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Switch_sig_1_2_by_par_bool_sw = vf.add_var('Switch sig 1->2 by par (bool)__sw_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Switch_sig_1_2_by_par_bool_proc_selfix_0 = vf.add_var('Switch sig 1->2 by par (bool)__proc_selfix_0_' + name)
    Switch_sig_1_2_by_par_bool_proc_selfix_1 = vf.add_var('Switch sig 1->2 by par (bool)__proc_selfix_1_' + name)
    Switch_sig_1_2_by_par_bool_proc_selfix_2 = vf.add_var('Switch sig 1->2 by par (bool)__proc_selfix_2_' + name)
    Switch_sig_1_2_by_par_bool_proc_selfix_3 = vf.add_var('Switch sig 1->2 by par (bool)__proc_selfix_3_' + name)
    yi = vf.add_var('yi_' + name)
    yo1 = vf.add_var('yo1_' + name)
    yo2 = vf.add_var('yo2_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo1 - ((Switch_sig_1_2_by_par_bool_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Switch_sig_1_2_by_par_bool_proc_selfix_1) * ((Switch_sig_1_2_by_par_bool_proc_selfix_0 * yi) + ((sym.Const(1.0) - Switch_sig_1_2_by_par_bool_proc_selfix_0) * sym.Const(0.0)))))),
            (yo2 - ((Switch_sig_1_2_by_par_bool_proc_selfix_3 * sym.Const(0.0)) + ((sym.Const(1.0) - Switch_sig_1_2_by_par_bool_proc_selfix_3) * ((Switch_sig_1_2_by_par_bool_proc_selfix_2 * yi) + ((sym.Const(1.0) - Switch_sig_1_2_by_par_bool_proc_selfix_2) * sym.Const(0.0)))))),
        ],
        algebraic_vars=[yo1, yo2],
        in_vars=[yi],
        out_vars=[yo1, yo2],
        name='Switch sig 1->2 by par (bool)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Switch_sig_1_2_by_par_bool_sw: vf.add_const(None, name='sw'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Switch_sig_1_2_by_par_bool_proc_selfix_0: vf.add_const(0.0, name=''),
        Switch_sig_1_2_by_par_bool_proc_selfix_1: vf.add_const(0.0, name=''),
        Switch_sig_1_2_by_par_bool_proc_selfix_2: vf.add_const(0.0, name=''),
        Switch_sig_1_2_by_par_bool_proc_selfix_3: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((Switch_sig_1_2_by_par_bool_sw < 1.5), output=Switch_sig_1_2_by_par_bool_proc_selfix_0),
        selfix((Switch_sig_1_2_by_par_bool_sw < 0.5), output=Switch_sig_1_2_by_par_bool_proc_selfix_1),
        selfix((Switch_sig_1_2_by_par_bool_sw < 2.5), output=Switch_sig_1_2_by_par_bool_proc_selfix_2),
        selfix((Switch_sig_1_2_by_par_bool_sw < 1.5), output=Switch_sig_1_2_by_par_bool_proc_selfix_3),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_switch_sig_1_2_by_par_bool_514_emt_template(vf=vf, name='Switch sig 1->2 by par (bool)__514' if name is None else name)
