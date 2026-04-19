# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro, selfix
from VeraGridEngine.enumerations import DeviceType

def get_invert_logic_ip_347_emt_template(vf: VarFactory, name: str = 'Invert Logic _ip__347') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Invert_Logic_ip_Tdrop = vf.add_var('Invert Logic _ip__Tdrop_' + name)
    Invert_Logic_ip_Tpick = vf.add_var('Invert Logic _ip__Tpick_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Invert_Logic_ip_proc_picdro_0 = vf.add_var('Invert Logic _ip__proc_picdro_0_' + name)
    Invert_Logic_ip_proc_selfix_1 = vf.add_var('Invert Logic _ip__proc_selfix_1_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - Invert_Logic_ip_proc_picdro_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Invert Logic _ip'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Invert_Logic_ip_Tpick: vf.add_const(None, name='Tpick'),
        Invert_Logic_ip_Tdrop: vf.add_const(None, name='Tdrop'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Invert_Logic_ip_proc_picdro_0: vf.add_const(0.0, name=''),
        Invert_Logic_ip_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: ((Invert_Logic_ip_proc_selfix_1 * sym.Const(1.0)) + ((sym.Const(1.0) - Invert_Logic_ip_proc_selfix_1) * sym.Const(0.0))),
    }
    templ.block.procedural_logic = [
        picdro((yi < 0.5), Invert_Logic_ip_Tpick, Invert_Logic_ip_Tdrop, output=Invert_Logic_ip_proc_picdro_0),
        selfix((yi < 0.5), output=Invert_Logic_ip_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_invert_logic_ip_347_emt_template(vf=vf, name='Invert Logic _ip__347' if name is None else name)
