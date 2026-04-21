# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_deadband_96_emt_template(vf: VarFactory, name: str = 'Deadband__96') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Deadband_db = vf.add_var('Deadband__db_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Deadband_proc_select_0 = vf.add_var('Deadband__proc_select_0_' + name)
    Deadband_proc_select_1 = vf.add_var('Deadband__proc_select_1_' + name)
    Deadband_proc_selfix_2 = vf.add_var('Deadband__proc_selfix_2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Deadband_proc_selfix_2 * yi) + ((sym.Const(1.0) - Deadband_proc_selfix_2) * ((Deadband_proc_select_1 * (yi - Deadband_db)) + ((sym.Const(1.0) - Deadband_proc_select_1) * ((Deadband_proc_select_0 * (yi + Deadband_db)) + ((sym.Const(1.0) - Deadband_proc_select_0) * sym.Const(0.0)))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Deadband'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Deadband_db: vf.add_const(None, name='db'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Deadband_proc_select_0: vf.add_const(0.0, name=''),
        Deadband_proc_select_1: vf.add_const(0.0, name=''),
        Deadband_proc_selfix_2: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Deadband_proc_select_0, source=(sym.heaviside((((-Deadband_db) - yi) - 1e-06)) * sym.heaviside(((Deadband_db - 0.0) - 1e-06)))),
        sampled_value(output=Deadband_proc_select_1, source=(sym.heaviside(((yi - Deadband_db) - 1e-06)) * sym.heaviside(((Deadband_db - 0.0) - 1e-06)))),
        selfix((Deadband_db <= 0.0), output=Deadband_proc_selfix_2),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_deadband_96_emt_template(vf=vf, name='Deadband__96' if name is None else name)
