# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_multiply_1_k_p_173_emt_template(vf: VarFactory, name: str = 'Multiply 1/K [p__173') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Multiply_1_K_p_K = vf.add_var('Multiply 1/K [p__K_' + name)
    Multiply_1_K_p_y_max = vf.add_var('Multiply 1/K [p__y_max_' + name)
    Multiply_1_K_p_y_min = vf.add_var('Multiply 1/K [p__y_min_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Multiply_1_K_p_proc_selfix_1 = vf.add_var('Multiply 1/K [p__proc_selfix_1_' + name)
    Multiply_1_K_p_proc_selfix_const_0 = vf.add_var('Multiply 1/K [p__proc_selfix_const_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Multiply_1_K_p_y_min + ((((Multiply_1_K_p_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Multiply_1_K_p_proc_selfix_1) * (yi / ((Multiply_1_K_p_proc_selfix_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - Multiply_1_K_p_proc_selfix_const_0) * Multiply_1_K_p_K))))) - Multiply_1_K_p_y_min) * sym.heaviside((((Multiply_1_K_p_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Multiply_1_K_p_proc_selfix_1) * (yi / ((Multiply_1_K_p_proc_selfix_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - Multiply_1_K_p_proc_selfix_const_0) * Multiply_1_K_p_K))))) - Multiply_1_K_p_y_min)))) - ((((Multiply_1_K_p_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Multiply_1_K_p_proc_selfix_1) * (yi / ((Multiply_1_K_p_proc_selfix_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - Multiply_1_K_p_proc_selfix_const_0) * Multiply_1_K_p_K))))) - Multiply_1_K_p_y_max) * sym.heaviside((((Multiply_1_K_p_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Multiply_1_K_p_proc_selfix_1) * (yi / ((Multiply_1_K_p_proc_selfix_const_0 * sym.Const(1.0)) + ((sym.Const(1.0) - Multiply_1_K_p_proc_selfix_const_0) * Multiply_1_K_p_K))))) - Multiply_1_K_p_y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Multiply 1/K [p'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Multiply_1_K_p_K: vf.add_const(None, name='K'),
        Multiply_1_K_p_y_max: vf.add_const(None, name='y_max'),
        Multiply_1_K_p_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Multiply_1_K_p_proc_selfix_const_0: vf.add_const(0.0, name=''),
        Multiply_1_K_p_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix(sym.Comparison(lhs=Multiply_1_K_p_K, op=sym.CmpOp.EQ, rhs=0.0), output=Multiply_1_K_p_proc_selfix_const_0),
        selfix(sym.Comparison(lhs=Multiply_1_K_p_K, op=sym.CmpOp.EQ, rhs=0.0), output=Multiply_1_K_p_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_multiply_1_k_p_173_emt_template(vf=vf, name='Multiply 1/K [p__173' if name is None else name)
