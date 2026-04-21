# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro, selfix
from VeraGridEngine.enumerations import DeviceType

def get_and2_ip_345_emt_template(vf: VarFactory, name: str = 'AND2 _ip__345') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    AND2_ip_Tdrop = vf.add_var('AND2 _ip__Tdrop_' + name)
    AND2_ip_Tpick = vf.add_var('AND2 _ip__Tpick_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    AND2_ip_proc_picdro_0 = vf.add_var('AND2 _ip__proc_picdro_0_' + name)
    AND2_ip_proc_selfix_1 = vf.add_var('AND2 _ip__proc_selfix_1_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - AND2_ip_proc_picdro_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi1, yi2],
        out_vars=[yo],
        name='AND2 _ip'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        AND2_ip_Tpick: vf.add_const(None, name='Tpick'),
        AND2_ip_Tdrop: vf.add_const(None, name='Tdrop'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        AND2_ip_proc_picdro_0: vf.add_const(0.0, name=''),
        AND2_ip_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: ((AND2_ip_proc_selfix_1 * sym.Const(1.0)) + ((sym.Const(1.0) - AND2_ip_proc_selfix_1) * sym.Const(0.0))),
    }
    templ.block.procedural_logic = [
        picdro((yi1 * yi2), AND2_ip_Tpick, AND2_ip_Tdrop, output=AND2_ip_proc_picdro_0),
        selfix((yi1 * yi2), output=AND2_ip_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_and2_ip_345_emt_template(vf=vf, name='AND2 _ip__345' if name is None else name)
