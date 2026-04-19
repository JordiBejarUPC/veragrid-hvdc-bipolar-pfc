# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_limit_p_313_emt_template(vf: VarFactory, name: str = 'Limit [p__313') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Limit_p_y_max = vf.add_var('Limit [p__y_max_' + name)
    Limit_p_y_min = vf.add_var('Limit [p__y_min_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Limit_p_proc_selfix_0 = vf.add_var('Limit [p__proc_selfix_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Limit_p_proc_selfix_0 * Limit_p_y_max) + ((sym.Const(1.0) - Limit_p_proc_selfix_0) * ((Limit_p_y_min + ((yi - Limit_p_y_min) * sym.heaviside((yi - Limit_p_y_min)))) - ((yi - Limit_p_y_max) * sym.heaviside((yi - Limit_p_y_max))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Limit [p'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Limit_p_y_max: vf.add_const(None, name='y_max'),
        Limit_p_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Limit_p_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((Limit_p_y_max <= Limit_p_y_min), output=Limit_p_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_limit_p_313_emt_template(vf=vf, name='Limit [p__313' if name is None else name)
