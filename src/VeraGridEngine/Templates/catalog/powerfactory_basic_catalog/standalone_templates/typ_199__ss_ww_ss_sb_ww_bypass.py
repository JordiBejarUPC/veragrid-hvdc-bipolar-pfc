# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_ss_ww_ss_sb_ww_bypass_199_emt_template(vf: VarFactory, name: str = '(ss+ww)/(ss+sB+ww) _bypass__199') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    ss_ww_ss_sB_ww_bypass_B = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass__B_' + name)
    ss_ww_ss_sB_ww_bypass_w = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass__w_' + name)

    # --- State Variables ---
    ss_ww_ss_sB_ww_bypass_x1 = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass__x1_' + name)
    ss_ww_ss_sB_ww_bypass_x2 = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass__x2_' + name)

    # --- Algebraic / Shared Variables ---
    ss_ww_ss_sB_ww_bypass_proc_selfix_0 = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass__proc_selfix_0_' + name)
    ss_ww_ss_sB_ww_bypass_proc_selfix_1 = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass__proc_selfix_1_' + name)
    ss_ww_ss_sB_ww_bypass_proc_selfix_2 = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass__proc_selfix_2_' + name)
    ss_ww_ss_sB_ww_bypass_dx1 = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass_dx1_' + name)
    ss_ww_ss_sB_ww_bypass_dx2 = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass_dx2_' + name)
    ss_ww_ss_sB_ww_bypass_triv = vf.add_var('(ss+ww)/(ss+sB+ww) _bypass_triv_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_ss_ww_ss_sB_ww_bypass_x1 = vf.add_diff_var('d_(ss+ww)/(ss+sB+ww) _bypass__x1_' + name, base_var=ss_ww_ss_sB_ww_bypass_x1)
    d_ss_ww_ss_sB_ww_bypass_x2 = vf.add_diff_var('d_(ss+ww)/(ss+sB+ww) _bypass__x2_' + name, base_var=ss_ww_ss_sB_ww_bypass_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ss_ww_ss_sB_ww_bypass_dx1,
            ss_ww_ss_sB_ww_bypass_dx2,
        ],
        state_vars=[ss_ww_ss_sB_ww_bypass_x1, ss_ww_ss_sB_ww_bypass_x2],
        algebraic_eqs=[
            (ss_ww_ss_sB_ww_bypass_dx1 - ((ss_ww_ss_sB_ww_bypass_proc_selfix_0 * sym.Const(0.0)) + ((sym.Const(1.0) - ss_ww_ss_sB_ww_bypass_proc_selfix_0) * ss_ww_ss_sB_ww_bypass_x2))),
            (ss_ww_ss_sB_ww_bypass_dx2 - ((ss_ww_ss_sB_ww_bypass_proc_selfix_1 * sym.Const(0.0)) + ((sym.Const(1.0) - ss_ww_ss_sB_ww_bypass_proc_selfix_1) * ((yi - (ss_ww_ss_sB_ww_bypass_B * ss_ww_ss_sB_ww_bypass_x2)) - ((ss_ww_ss_sB_ww_bypass_w * ss_ww_ss_sB_ww_bypass_w) * ss_ww_ss_sB_ww_bypass_x1))))),
            (yo - ((ss_ww_ss_sB_ww_bypass_proc_selfix_2 * yi) + ((sym.Const(1.0) - ss_ww_ss_sB_ww_bypass_proc_selfix_2) * (ss_ww_ss_sB_ww_bypass_dx2 + ((ss_ww_ss_sB_ww_bypass_x1 * ss_ww_ss_sB_ww_bypass_w) * ss_ww_ss_sB_ww_bypass_w))))),
        ],
        algebraic_vars=[ss_ww_ss_sB_ww_bypass_dx1, ss_ww_ss_sB_ww_bypass_dx2, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(ss+ww)/(ss+sB+ww) _bypass'
    )
    templ.block.diff_vars = [d_ss_ww_ss_sB_ww_bypass_x1, d_ss_ww_ss_sB_ww_bypass_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        ss_ww_ss_sB_ww_bypass_B: vf.add_const(None, name='B'),
        ss_ww_ss_sB_ww_bypass_w: vf.add_const(None, name='w'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        ss_ww_ss_sB_ww_bypass_proc_selfix_0: vf.add_const(0.0, name=''),
        ss_ww_ss_sB_ww_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
        ss_ww_ss_sB_ww_bypass_proc_selfix_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        ss_ww_ss_sB_ww_bypass_triv: (sym.heaviside(((sym.Const(0.0) - sym.abs(ss_ww_ss_sB_ww_bypass_B)) + sym.Const(1e-06))) * sym.heaviside(((sym.Const(0.0) - sym.abs(ss_ww_ss_sB_ww_bypass_w)) + sym.Const(1e-06)))),
    }
    templ.block.procedural_logic = [
        selfix(ss_ww_ss_sB_ww_bypass_triv, output=ss_ww_ss_sB_ww_bypass_proc_selfix_0),
        selfix(ss_ww_ss_sB_ww_bypass_triv, output=ss_ww_ss_sB_ww_bypass_proc_selfix_1),
        selfix(ss_ww_ss_sB_ww_bypass_triv, output=ss_ww_ss_sB_ww_bypass_proc_selfix_2),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_ss_ww_ss_sb_ww_bypass_199_emt_template(vf=vf, name='(ss+ww)/(ss+sB+ww) _bypass__199' if name is None else name)
