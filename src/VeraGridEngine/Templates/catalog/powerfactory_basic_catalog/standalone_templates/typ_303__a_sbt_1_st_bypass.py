# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_a_sbt_1_st_bypass_303_emt_template(vf: VarFactory, name: str = '(a+sbT)/(1+sT) _bypass__303') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    a_sbT_1_sT_bypass_T = vf.add_var('(a+sbT)/(1+sT) _bypass__T_' + name)
    a_sbT_1_sT_bypass_a = vf.add_var('(a+sbT)/(1+sT) _bypass__a_' + name)
    a_sbT_1_sT_bypass_b = vf.add_var('(a+sbT)/(1+sT) _bypass__b_' + name)

    # --- State Variables ---
    a_sbT_1_sT_bypass_x = vf.add_var('(a+sbT)/(1+sT) _bypass__x_' + name)

    # --- Algebraic / Shared Variables ---
    a_sbT_1_sT_bypass_proc_selfix_0 = vf.add_var('(a+sbT)/(1+sT) _bypass__proc_selfix_0_' + name)
    a_sbT_1_sT_bypass_proc_selfix_1 = vf.add_var('(a+sbT)/(1+sT) _bypass__proc_selfix_1_' + name)
    a_sbT_1_sT_bypass_dx = vf.add_var('(a+sbT)/(1+sT) _bypass_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_a_sbT_1_sT_bypass_x = vf.add_diff_var('d_(a+sbT)/(1+sT) _bypass__x_' + name, base_var=a_sbT_1_sT_bypass_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            a_sbT_1_sT_bypass_dx,
        ],
        state_vars=[a_sbT_1_sT_bypass_x],
        algebraic_eqs=[
            (a_sbT_1_sT_bypass_dx - ((a_sbT_1_sT_bypass_proc_selfix_0 * ((yi - a_sbT_1_sT_bypass_x) / a_sbT_1_sT_bypass_T)) + ((sym.Const(1.0) - a_sbT_1_sT_bypass_proc_selfix_0) * sym.Const(0.0)))),
            (yo - ((a_sbT_1_sT_bypass_proc_selfix_1 * ((a_sbT_1_sT_bypass_a * a_sbT_1_sT_bypass_x) + ((a_sbT_1_sT_bypass_b * a_sbT_1_sT_bypass_T) * a_sbT_1_sT_bypass_dx))) + ((sym.Const(1.0) - a_sbT_1_sT_bypass_proc_selfix_1) * (a_sbT_1_sT_bypass_a * yi)))),
        ],
        algebraic_vars=[a_sbT_1_sT_bypass_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(a+sbT)/(1+sT) _bypass'
    )
    templ.block.diff_vars = [d_a_sbT_1_sT_bypass_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        a_sbT_1_sT_bypass_a: vf.add_const(None, name='a'),
        a_sbT_1_sT_bypass_b: vf.add_const(None, name='b'),
        a_sbT_1_sT_bypass_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        a_sbT_1_sT_bypass_proc_selfix_0: vf.add_const(0.0, name=''),
        a_sbT_1_sT_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((a_sbT_1_sT_bypass_T > 0.0), output=a_sbT_1_sT_bypass_proc_selfix_0),
        selfix((a_sbT_1_sT_bypass_T > 0.0), output=a_sbT_1_sT_bypass_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_a_sbt_1_st_bypass_303_emt_template(vf=vf, name='(a+sbT)/(1+sT) _bypass__303' if name is None else name)
