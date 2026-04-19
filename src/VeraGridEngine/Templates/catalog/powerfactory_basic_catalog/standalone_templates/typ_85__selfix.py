# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_selfix_85_emt_template(vf: VarFactory, name: str = 'selfix__85') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    condition = vf.add_var('condition_' + name)
    selfix_proc_selfix_0 = vf.add_var('selfix__proc_selfix_0_' + name)
    y_false = vf.add_var('y_false_' + name)
    y_true = vf.add_var('y_true_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((selfix_proc_selfix_0 * y_true) + ((sym.Const(1.0) - selfix_proc_selfix_0) * y_false))),
        ],
        algebraic_vars=[yo],
        in_vars=[condition, y_true, y_false],
        out_vars=[yo],
        name='selfix'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        selfix_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix(condition, output=selfix_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_selfix_85_emt_template(vf=vf, name='selfix__85' if name is None else name)
