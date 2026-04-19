# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_st3_1_st1_sst1t2_bypass_193_emt_template(vf: VarFactory, name: str = '(1+sT3)/(1+sT1+ssT1T2) _bypass__193') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sT3_1_sT1_ssT1T2_bypass_T1 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass__T1_' + name)
    v_1_sT3_1_sT1_ssT1T2_bypass_T2 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass__T2_' + name)
    v_1_sT3_1_sT1_ssT1T2_bypass_T3 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass__T3_' + name)

    # --- State Variables ---
    v_1_sT3_1_sT1_ssT1T2_bypass_x1 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass__x1_' + name)
    v_1_sT3_1_sT1_ssT1T2_bypass_x2 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass__x2_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_0 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass__proc_selfix_0_' + name)
    v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_1 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass__proc_selfix_1_' + name)
    v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_2 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass__proc_selfix_2_' + name)
    v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_3 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass__proc_selfix_3_' + name)
    v_1_sT3_1_sT1_ssT1T2_bypass_dx1 = vf.add_var('(1+sT3)/(1+sT1+ssT1T2) _bypass_dx1_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sT3_1_sT1_ssT1T2_bypass_x1 = vf.add_diff_var('d_(1+sT3)/(1+sT1+ssT1T2) _bypass__x1_' + name, base_var=v_1_sT3_1_sT1_ssT1T2_bypass_x1)
    d_1_sT3_1_sT1_ssT1T2_bypass_x2 = vf.add_diff_var('d_(1+sT3)/(1+sT1+ssT1T2) _bypass__x2_' + name, base_var=v_1_sT3_1_sT1_ssT1T2_bypass_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_sT3_1_sT1_ssT1T2_bypass_dx1,
            ((v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_2 * (((yi - v_1_sT3_1_sT1_ssT1T2_bypass_x1) - (v_1_sT3_1_sT1_ssT1T2_bypass_x2 * v_1_sT3_1_sT1_ssT1T2_bypass_T1)) / (v_1_sT3_1_sT1_ssT1T2_bypass_T1 * v_1_sT3_1_sT1_ssT1T2_bypass_T2))) + ((sym.Const(1.0) - v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_2) * sym.Const(0.0))),
        ],
        state_vars=[v_1_sT3_1_sT1_ssT1T2_bypass_x1, v_1_sT3_1_sT1_ssT1T2_bypass_x2],
        algebraic_eqs=[
            (v_1_sT3_1_sT1_ssT1T2_bypass_dx1 - ((v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_1 * v_1_sT3_1_sT1_ssT1T2_bypass_x2) + ((sym.Const(1.0) - v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_1) * ((v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_0 * ((yi - v_1_sT3_1_sT1_ssT1T2_bypass_x1) / v_1_sT3_1_sT1_ssT1T2_bypass_T1)) + ((sym.Const(1.0) - v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_0) * sym.Const(0.0)))))),
            (yo - ((v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_3 * (v_1_sT3_1_sT1_ssT1T2_bypass_x1 + (v_1_sT3_1_sT1_ssT1T2_bypass_T3 * v_1_sT3_1_sT1_ssT1T2_bypass_dx1))) + ((sym.Const(1.0) - v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_3) * yi))),
        ],
        algebraic_vars=[v_1_sT3_1_sT1_ssT1T2_bypass_dx1, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+sT3)/(1+sT1+ssT1T2) _bypass'
    )
    templ.block.diff_vars = [d_1_sT3_1_sT1_ssT1T2_bypass_x1, d_1_sT3_1_sT1_ssT1T2_bypass_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sT3_1_sT1_ssT1T2_bypass_T1: vf.add_const(None, name='T1'),
        v_1_sT3_1_sT1_ssT1T2_bypass_T2: vf.add_const(None, name='T2'),
        v_1_sT3_1_sT1_ssT1T2_bypass_T3: vf.add_const(None, name='T3'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_0: vf.add_const(0.0, name=''),
        v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
        v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_2: vf.add_const(0.0, name=''),
        v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_3: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((v_1_sT3_1_sT1_ssT1T2_bypass_T1 > 0.0), output=v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_0),
        selfix((v_1_sT3_1_sT1_ssT1T2_bypass_T2 > 0.0), output=v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_1),
        selfix((v_1_sT3_1_sT1_ssT1T2_bypass_T2 > 0.0), output=v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_2),
        selfix((1.0 - ((1.0 - sym.heaviside(((v_1_sT3_1_sT1_ssT1T2_bypass_T1 - 0.0) - 1e-06))) * (1.0 - sym.heaviside(((v_1_sT3_1_sT1_ssT1T2_bypass_T2 - 0.0) - 1e-06))))), output=v_1_sT3_1_sT1_ssT1T2_bypass_proc_selfix_3),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_st3_1_st1_sst1t2_bypass_193_emt_template(vf=vf, name='(1+sT3)/(1+sT1+ssT1T2) _bypass__193' if name is None else name)
