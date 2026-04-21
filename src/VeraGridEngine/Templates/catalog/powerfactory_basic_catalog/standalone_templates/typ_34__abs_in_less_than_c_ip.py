# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro, selfix
from VeraGridEngine.enumerations import DeviceType

def get_abs_in_less_than_c_ip_34_emt_template(vf: VarFactory, name: str = 'abs(in) less than C _ip__34') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    abs_in_less_than_C_ip_C = vf.add_var('abs(in) less than C _ip__C_' + name)
    abs_in_less_than_C_ip_Tdrop = vf.add_var('abs(in) less than C _ip__Tdrop_' + name)
    abs_in_less_than_C_ip_Tpick = vf.add_var('abs(in) less than C _ip__Tpick_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    abs_in_less_than_C_ip_proc_picdro_0 = vf.add_var('abs(in) less than C _ip__proc_picdro_0_' + name)
    abs_in_less_than_C_ip_proc_selfix_1 = vf.add_var('abs(in) less than C _ip__proc_selfix_1_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - abs_in_less_than_C_ip_proc_picdro_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='abs(in) less than C _ip'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        abs_in_less_than_C_ip_C: vf.add_const(None, name='C'),
        abs_in_less_than_C_ip_Tpick: vf.add_const(None, name='Tpick'),
        abs_in_less_than_C_ip_Tdrop: vf.add_const(None, name='Tdrop'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        abs_in_less_than_C_ip_proc_picdro_0: vf.add_const(0.0, name=''),
        abs_in_less_than_C_ip_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: ((abs_in_less_than_C_ip_proc_selfix_1 * sym.Const(1.0)) + ((sym.Const(1.0) - abs_in_less_than_C_ip_proc_selfix_1) * sym.Const(0.0))),
    }
    templ.block.procedural_logic = [
        picdro((sym.abs(yi) < abs_in_less_than_C_ip_C), abs_in_less_than_C_ip_Tpick, abs_in_less_than_C_ip_Tdrop, output=abs_in_less_than_C_ip_proc_picdro_0),
        selfix((sym.abs(yi) < abs_in_less_than_C_ip_C), output=abs_in_less_than_C_ip_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_abs_in_less_than_c_ip_34_emt_template(vf=vf, name='abs(in) less than C _ip__34' if name is None else name)
