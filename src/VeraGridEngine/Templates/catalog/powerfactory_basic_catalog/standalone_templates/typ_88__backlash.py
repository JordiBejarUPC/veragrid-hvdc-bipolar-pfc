# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_backlash_88_emt_template(vf: VarFactory, name: str = 'Backlash__88') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Backlash_db = vf.add_var('Backlash__db_' + name)

    # --- State Variables ---
    Backlash_x = vf.add_var('Backlash__x_' + name)

    # --- Algebraic / Shared Variables ---
    Backlash_proc_select_0 = vf.add_var('Backlash__proc_select_0_' + name)
    Backlash_proc_select_1 = vf.add_var('Backlash__proc_select_1_' + name)
    Backlash_proc_selfix_2 = vf.add_var('Backlash__proc_selfix_2_' + name)
    Backlash_d = vf.add_var('Backlash_d_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Backlash_x = vf.add_diff_var('d_Backlash__x_' + name, base_var=Backlash_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (Backlash_d / sym.Const(0.01)),
        ],
        state_vars=[Backlash_x],
        algebraic_eqs=[
            (Backlash_d - ((Backlash_proc_selfix_2 * sym.Const(0.0)) + ((sym.Const(1.0) - Backlash_proc_selfix_2) * ((Backlash_proc_select_1 * ((yi - Backlash_x) - Backlash_db)) + ((sym.Const(1.0) - Backlash_proc_select_1) * ((Backlash_proc_select_0 * ((yi - Backlash_x) + Backlash_db)) + ((sym.Const(1.0) - Backlash_proc_select_0) * sym.Const(0.0)))))))),
            (yo - Backlash_x),
        ],
        algebraic_vars=[Backlash_d, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Backlash'
    )
    templ.block.diff_vars = [d_Backlash_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Backlash_db: vf.add_const(None, name='db'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Backlash_proc_select_0: vf.add_const(0.0, name=''),
        Backlash_proc_select_1: vf.add_const(0.0, name=''),
        Backlash_proc_selfix_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Backlash_x: yo,
    }
    templ.block.procedural_logic = [
        sampled_value(output=Backlash_proc_select_0, source=(sym.heaviside((((-Backlash_db) - (yi - Backlash_x)) + 1e-06)) * sym.heaviside(((Backlash_db - 0.0) - 1e-06)))),
        sampled_value(output=Backlash_proc_select_1, source=(sym.heaviside((((yi - Backlash_x) - Backlash_db) + 1e-06)) * sym.heaviside(((Backlash_db - 0.0) - 1e-06)))),
        selfix((Backlash_db <= 0.0), output=Backlash_proc_selfix_2),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_backlash_88_emt_template(vf=vf, name='Backlash__88' if name is None else name)
