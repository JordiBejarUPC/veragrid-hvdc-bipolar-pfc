# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro, selfix
from VeraGridEngine.enumerations import DeviceType

def get_not_ip_348_emt_template(vf: VarFactory, name: str = 'NOT _ip__348') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    NOT_ip_Tdrop = vf.add_var('NOT _ip__Tdrop_' + name)
    NOT_ip_Tpick = vf.add_var('NOT _ip__Tpick_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    NOT_ip_proc_picdro_0 = vf.add_var('NOT _ip__proc_picdro_0_' + name)
    NOT_ip_proc_selfix_1 = vf.add_var('NOT _ip__proc_selfix_1_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - NOT_ip_proc_picdro_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi1],
        out_vars=[yo],
        name='NOT _ip'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        NOT_ip_Tpick: vf.add_const(None, name='Tpick'),
        NOT_ip_Tdrop: vf.add_const(None, name='Tdrop'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        NOT_ip_proc_picdro_0: vf.add_const(0.0, name=''),
        NOT_ip_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: ((NOT_ip_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - NOT_ip_proc_selfix_1) * sym.Const(1.0))),
    }
    templ.block.procedural_logic = [
        picdro((1.0 - yi1), NOT_ip_Tpick, NOT_ip_Tdrop, output=NOT_ip_proc_picdro_0),
        selfix(sym.Comparison(lhs=yi1, op=sym.CmpOp.EQ, rhs=1.0), output=NOT_ip_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_not_ip_348_emt_template(vf=vf, name='NOT _ip__348' if name is None else name)
