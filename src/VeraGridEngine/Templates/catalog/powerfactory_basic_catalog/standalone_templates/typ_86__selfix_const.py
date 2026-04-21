# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_selfix_const_86_emt_template(vf: VarFactory, name: str = 'selfix_const__86') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    selfix_const_K_false = vf.add_var('selfix_const__K_false_' + name)
    selfix_const_K_true = vf.add_var('selfix_const__K_true_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    condition = vf.add_var('condition_' + name)
    selfix_const_proc_selfix_const_0 = vf.add_var('selfix_const__proc_selfix_const_0_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((selfix_const_proc_selfix_const_0 * selfix_const_K_true) + ((sym.Const(1.0) - selfix_const_proc_selfix_const_0) * selfix_const_K_false))),
        ],
        algebraic_vars=[yo],
        in_vars=[condition],
        out_vars=[yo],
        name='selfix_const'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        selfix_const_K_true: vf.add_const(None, name='K_true'),
        selfix_const_K_false: vf.add_const(None, name='K_false'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        selfix_const_proc_selfix_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix(condition, output=selfix_const_proc_selfix_const_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_selfix_const_86_emt_template(vf=vf, name='selfix_const__86' if name is None else name)
