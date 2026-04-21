# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_deadband_offset_p_92_emt_template(vf: VarFactory, name: str = 'Deadband offset [p__92') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Deadband_offset_p_db = vf.add_var('Deadband offset [p__db_' + name)
    Deadband_offset_p_y_max = vf.add_var('Deadband offset [p__y_max_' + name)
    Deadband_offset_p_y_min = vf.add_var('Deadband offset [p__y_min_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Deadband_offset_p_proc_select_0 = vf.add_var('Deadband offset [p__proc_select_0_' + name)
    Deadband_offset_p_proc_select_1 = vf.add_var('Deadband offset [p__proc_select_1_' + name)
    Deadband_offset_p_proc_selfix_2 = vf.add_var('Deadband offset [p__proc_selfix_2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Deadband_offset_p_y_min + ((((Deadband_offset_p_proc_selfix_2 * ((Deadband_offset_p_proc_select_1 * ((Deadband_offset_p_proc_select_0 * (yi - Deadband_offset_p_db)) + ((sym.Const(1.0) - Deadband_offset_p_proc_select_0) * (yi + Deadband_offset_p_db)))) + ((sym.Const(1.0) - Deadband_offset_p_proc_select_1) * sym.Const(0.0)))) + ((sym.Const(1.0) - Deadband_offset_p_proc_selfix_2) * yi)) - Deadband_offset_p_y_min) * sym.heaviside((((Deadband_offset_p_proc_selfix_2 * ((Deadband_offset_p_proc_select_1 * ((Deadband_offset_p_proc_select_0 * (yi - Deadband_offset_p_db)) + ((sym.Const(1.0) - Deadband_offset_p_proc_select_0) * (yi + Deadband_offset_p_db)))) + ((sym.Const(1.0) - Deadband_offset_p_proc_select_1) * sym.Const(0.0)))) + ((sym.Const(1.0) - Deadband_offset_p_proc_selfix_2) * yi)) - Deadband_offset_p_y_min)))) - ((((Deadband_offset_p_proc_selfix_2 * ((Deadband_offset_p_proc_select_1 * ((Deadband_offset_p_proc_select_0 * (yi - Deadband_offset_p_db)) + ((sym.Const(1.0) - Deadband_offset_p_proc_select_0) * (yi + Deadband_offset_p_db)))) + ((sym.Const(1.0) - Deadband_offset_p_proc_select_1) * sym.Const(0.0)))) + ((sym.Const(1.0) - Deadband_offset_p_proc_selfix_2) * yi)) - Deadband_offset_p_y_max) * sym.heaviside((((Deadband_offset_p_proc_selfix_2 * ((Deadband_offset_p_proc_select_1 * ((Deadband_offset_p_proc_select_0 * (yi - Deadband_offset_p_db)) + ((sym.Const(1.0) - Deadband_offset_p_proc_select_0) * (yi + Deadband_offset_p_db)))) + ((sym.Const(1.0) - Deadband_offset_p_proc_select_1) * sym.Const(0.0)))) + ((sym.Const(1.0) - Deadband_offset_p_proc_selfix_2) * yi)) - Deadband_offset_p_y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Deadband offset [p'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Deadband_offset_p_db: vf.add_const(None, name='db'),
        Deadband_offset_p_y_max: vf.add_const(None, name='y_max'),
        Deadband_offset_p_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Deadband_offset_p_proc_select_0: vf.add_const(0.0, name=''),
        Deadband_offset_p_proc_select_1: vf.add_const(0.0, name=''),
        Deadband_offset_p_proc_selfix_2: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Deadband_offset_p_proc_select_0, source=(sym.heaviside(((yi - 0.0) - 1e-06)) * sym.heaviside(((Deadband_offset_p_db - 0.0) - 1e-06)))),
        sampled_value(output=Deadband_offset_p_proc_select_1, source=(sym.heaviside(((sym.abs(yi) - Deadband_offset_p_db) + 1e-06)) * sym.heaviside(((Deadband_offset_p_db - 0.0) - 1e-06)))),
        selfix((Deadband_offset_p_db > 0.0), output=Deadband_offset_p_proc_selfix_2),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_deadband_offset_p_92_emt_template(vf=vf, name='Deadband offset [p__92' if name is None else name)
