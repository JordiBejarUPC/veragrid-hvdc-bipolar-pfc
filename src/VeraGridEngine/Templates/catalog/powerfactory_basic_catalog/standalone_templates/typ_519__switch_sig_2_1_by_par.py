# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_switch_sig_2_1_by_par_519_emt_template(vf: VarFactory, name: str = 'Switch sig 2->1 by par__519') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Switch_sig_2_1_by_par_sw = vf.add_var('Switch sig 2->1 by par__sw_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Switch_sig_2_1_by_par_proc_selfix_0 = vf.add_var('Switch sig 2->1 by par__proc_selfix_0_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Switch_sig_2_1_by_par_proc_selfix_0 * yi2) + ((sym.Const(1.0) - Switch_sig_2_1_by_par_proc_selfix_0) * yi1))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi1, yi2],
        out_vars=[yo],
        name='Switch sig 2->1 by par'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Switch_sig_2_1_by_par_sw: vf.add_const(None, name='sw'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Switch_sig_2_1_by_par_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((Switch_sig_2_1_by_par_sw > 0.0), output=Switch_sig_2_1_by_par_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_switch_sig_2_1_by_par_519_emt_template(vf=vf, name='Switch sig 2->1 by par__519' if name is None else name)
