# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_deadband_offset_bypass_93_emt_template(vf: VarFactory, name: str = 'Deadband offset _bypass__93') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Deadband_offset_bypass_db = vf.add_var('Deadband offset _bypass__db_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Deadband_offset_bypass_proc_select_0 = vf.add_var('Deadband offset _bypass__proc_select_0_' + name)
    Deadband_offset_bypass_proc_select_1 = vf.add_var('Deadband offset _bypass__proc_select_1_' + name)
    Deadband_offset_bypass_proc_selfix_2 = vf.add_var('Deadband offset _bypass__proc_selfix_2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Deadband_offset_bypass_proc_selfix_2 * ((Deadband_offset_bypass_proc_select_1 * ((Deadband_offset_bypass_proc_select_0 * (yi - Deadband_offset_bypass_db)) + ((sym.Const(1.0) - Deadband_offset_bypass_proc_select_0) * (yi + Deadband_offset_bypass_db)))) + ((sym.Const(1.0) - Deadband_offset_bypass_proc_select_1) * sym.Const(0.0)))) + ((sym.Const(1.0) - Deadband_offset_bypass_proc_selfix_2) * yi))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Deadband offset _bypass'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Deadband_offset_bypass_db: vf.add_const(None, name='db'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Deadband_offset_bypass_proc_select_0: vf.add_const(0.0, name=''),
        Deadband_offset_bypass_proc_select_1: vf.add_const(0.0, name=''),
        Deadband_offset_bypass_proc_selfix_2: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Deadband_offset_bypass_proc_select_0, source=(sym.heaviside(((yi - 0.0) - 1e-06)) * sym.heaviside(((Deadband_offset_bypass_db - 0.0) - 1e-06)))),
        sampled_value(output=Deadband_offset_bypass_proc_select_1, source=(sym.heaviside(((sym.abs(yi) - Deadband_offset_bypass_db) + 1e-06)) * sym.heaviside(((Deadband_offset_bypass_db - 0.0) - 1e-06)))),
        selfix((Deadband_offset_bypass_db > 0.0), output=Deadband_offset_bypass_proc_selfix_2),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_deadband_offset_bypass_93_emt_template(vf=vf, name='Deadband offset _bypass__93' if name is None else name)
