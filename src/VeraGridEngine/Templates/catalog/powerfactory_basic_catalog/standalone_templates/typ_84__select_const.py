# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_select_const_84_emt_template(vf: VarFactory, name: str = 'select_const__84') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    select_const_K_false = vf.add_var('select_const__K_false_' + name)
    select_const_K_true = vf.add_var('select_const__K_true_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    condition = vf.add_var('condition_' + name)
    select_const_proc_select_const_0 = vf.add_var('select_const__proc_select_const_0_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((select_const_proc_select_const_0 * select_const_K_true) + ((sym.Const(1.0) - select_const_proc_select_const_0) * select_const_K_false))),
        ],
        algebraic_vars=[yo],
        in_vars=[condition],
        out_vars=[yo],
        name='select_const'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        select_const_K_true: vf.add_const(None, name='K_true'),
        select_const_K_false: vf.add_const(None, name='K_false'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        select_const_proc_select_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=select_const_proc_select_const_0, source=condition),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_select_const_84_emt_template(vf=vf, name='select_const__84' if name is None else name)
