# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro, selfix
from VeraGridEngine.enumerations import DeviceType

def get_yi_equals_c_ip_35_emt_template(vf: VarFactory, name: str = 'yi equals C _ip__35') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    yi_equals_C_ip_C = vf.add_var('yi equals C _ip__C_' + name)
    yi_equals_C_ip_Tdrop = vf.add_var('yi equals C _ip__Tdrop_' + name)
    yi_equals_C_ip_Tpick = vf.add_var('yi equals C _ip__Tpick_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yi_equals_C_ip_proc_picdro_0 = vf.add_var('yi equals C _ip__proc_picdro_0_' + name)
    yi_equals_C_ip_proc_selfix_1 = vf.add_var('yi equals C _ip__proc_selfix_1_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - yi_equals_C_ip_proc_picdro_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='yi equals C _ip'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        yi_equals_C_ip_C: vf.add_const(None, name='C'),
        yi_equals_C_ip_Tpick: vf.add_const(None, name='Tpick'),
        yi_equals_C_ip_Tdrop: vf.add_const(None, name='Tdrop'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        yi_equals_C_ip_proc_picdro_0: vf.add_const(0.0, name=''),
        yi_equals_C_ip_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: ((yi_equals_C_ip_proc_selfix_1 * sym.Const(1.0)) + ((sym.Const(1.0) - yi_equals_C_ip_proc_selfix_1) * sym.Const(0.0))),
    }
    templ.block.procedural_logic = [
        picdro(sym.Comparison(lhs=yi, op=sym.CmpOp.EQ, rhs=yi_equals_C_ip_C), yi_equals_C_ip_Tpick, yi_equals_C_ip_Tdrop, output=yi_equals_C_ip_proc_picdro_0),
        selfix(sym.Comparison(lhs=yi, op=sym.CmpOp.EQ, rhs=yi_equals_C_ip_C), output=yi_equals_C_ip_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_yi_equals_c_ip_35_emt_template(vf=vf, name='yi equals C _ip__35' if name is None else name)
