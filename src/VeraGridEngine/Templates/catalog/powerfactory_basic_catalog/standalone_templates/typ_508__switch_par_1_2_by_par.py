# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_switch_par_1_2_by_par_508_emt_template(vf: VarFactory, name: str = 'Switch par 1->2 by par__508') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Switch_par_1_2_by_par_K = vf.add_var('Switch par 1->2 by par__K_' + name)
    Switch_par_1_2_by_par_sw = vf.add_var('Switch par 1->2 by par__sw_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Switch_par_1_2_by_par_proc_selfix_const_0 = vf.add_var('Switch par 1->2 by par__proc_selfix_const_0_' + name)
    Switch_par_1_2_by_par_proc_selfix_const_1 = vf.add_var('Switch par 1->2 by par__proc_selfix_const_1_' + name)
    Switch_par_1_2_by_par_proc_selfix_const_2 = vf.add_var('Switch par 1->2 by par__proc_selfix_const_2_' + name)
    Switch_par_1_2_by_par_proc_selfix_const_3 = vf.add_var('Switch par 1->2 by par__proc_selfix_const_3_' + name)
    yo1 = vf.add_var('yo1_' + name)
    yo2 = vf.add_var('yo2_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo1 - ((Switch_par_1_2_by_par_proc_selfix_const_2 * sym.Const(0.0)) + ((sym.Const(1.0) - Switch_par_1_2_by_par_proc_selfix_const_2) * Switch_par_1_2_by_par_K))),
            (yo2 - ((Switch_par_1_2_by_par_proc_selfix_const_3 * Switch_par_1_2_by_par_K) + ((sym.Const(1.0) - Switch_par_1_2_by_par_proc_selfix_const_3) * sym.Const(0.0)))),
        ],
        algebraic_vars=[yo1, yo2],
        out_vars=[yo1, yo2],
        name='Switch par 1->2 by par'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Switch_par_1_2_by_par_sw: vf.add_const(None, name='sw'),
        Switch_par_1_2_by_par_K: vf.add_const(None, name='K'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Switch_par_1_2_by_par_proc_selfix_const_0: vf.add_const(0.0, name=''),
        Switch_par_1_2_by_par_proc_selfix_const_1: vf.add_const(0.0, name=''),
        Switch_par_1_2_by_par_proc_selfix_const_2: vf.add_const(0.0, name=''),
        Switch_par_1_2_by_par_proc_selfix_const_3: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo1: ((Switch_par_1_2_by_par_proc_selfix_const_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Switch_par_1_2_by_par_proc_selfix_const_0) * Switch_par_1_2_by_par_K)),
        yo2: ((Switch_par_1_2_by_par_proc_selfix_const_1 * Switch_par_1_2_by_par_K) + ((sym.Const(1.0) - Switch_par_1_2_by_par_proc_selfix_const_1) * sym.Const(0.0))),
    }
    templ.block.procedural_logic = [
        selfix(Switch_par_1_2_by_par_sw, output=Switch_par_1_2_by_par_proc_selfix_const_0),
        selfix(Switch_par_1_2_by_par_sw, output=Switch_par_1_2_by_par_proc_selfix_const_1),
        selfix(Switch_par_1_2_by_par_sw, output=Switch_par_1_2_by_par_proc_selfix_const_2),
        selfix(Switch_par_1_2_by_par_sw, output=Switch_par_1_2_by_par_proc_selfix_const_3),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_switch_par_1_2_by_par_508_emt_template(vf=vf, name='Switch par 1->2 by par__508' if name is None else name)
