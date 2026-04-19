# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_switch_sig_1_1_by_sig_fixed_512_emt_template(vf: VarFactory, name: str = 'Switch sig 1->1 by sig (fixed)__512') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Switch_sig_1_1_by_sig_fixed_p = vf.add_var('Switch sig 1->1 by sig (fixed)__p_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Enable = vf.add_var('Enable_' + name)
    Switch_sig_1_1_by_sig_fixed_proc_selfix_0 = vf.add_var('Switch sig 1->1 by sig (fixed)__proc_selfix_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Switch_sig_1_1_by_sig_fixed_proc_selfix_0 * yi) + ((sym.Const(1.0) - Switch_sig_1_1_by_sig_fixed_proc_selfix_0) * Switch_sig_1_1_by_sig_fixed_p))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, Enable],
        out_vars=[yo],
        name='Switch sig 1->1 by sig (fixed)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Switch_sig_1_1_by_sig_fixed_p: vf.add_const(None, name='p'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Switch_sig_1_1_by_sig_fixed_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix(Enable, output=Switch_sig_1_1_by_sig_fixed_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_switch_sig_1_1_by_sig_fixed_512_emt_template(vf=vf, name='Switch sig 1->1 by sig (fixed)__512' if name is None else name)
