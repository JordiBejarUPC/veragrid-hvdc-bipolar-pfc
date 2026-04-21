# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_k_1_st_bypass_127_emt_template(vf: VarFactory, name: str = '(1-K)/(1+sT) _bypass__127') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_K_1_sT_bypass_K = vf.add_var('(1-K)/(1+sT) _bypass__K_' + name)
    v_1_K_1_sT_bypass_T = vf.add_var('(1-K)/(1+sT) _bypass__T_' + name)

    # --- State Variables ---
    v_1_K_1_sT_bypass_x = vf.add_var('(1-K)/(1+sT) _bypass__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_K_1_sT_bypass_proc_selfix_0 = vf.add_var('(1-K)/(1+sT) _bypass__proc_selfix_0_' + name)
    v_1_K_1_sT_bypass_proc_selfix_1 = vf.add_var('(1-K)/(1+sT) _bypass__proc_selfix_1_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_K_1_sT_bypass_x = vf.add_diff_var('d_(1-K)/(1+sT) _bypass__x_' + name, base_var=v_1_K_1_sT_bypass_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((v_1_K_1_sT_bypass_proc_selfix_0 * ((((sym.Const(1.0) - v_1_K_1_sT_bypass_K) * yi) - v_1_K_1_sT_bypass_x) / v_1_K_1_sT_bypass_T)) + ((sym.Const(1.0) - v_1_K_1_sT_bypass_proc_selfix_0) * sym.Const(0.0))),
        ],
        state_vars=[v_1_K_1_sT_bypass_x],
        algebraic_eqs=[
            (yo - ((v_1_K_1_sT_bypass_proc_selfix_1 * v_1_K_1_sT_bypass_x) + ((sym.Const(1.0) - v_1_K_1_sT_bypass_proc_selfix_1) * ((sym.Const(1.0) - v_1_K_1_sT_bypass_K) * yi)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1-K)/(1+sT) _bypass'
    )
    templ.block.diff_vars = [d_1_K_1_sT_bypass_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_K_1_sT_bypass_K: vf.add_const(None, name='K'),
        v_1_K_1_sT_bypass_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_K_1_sT_bypass_proc_selfix_0: vf.add_const(0.0, name=''),
        v_1_K_1_sT_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((v_1_K_1_sT_bypass_T > 0.0), output=v_1_K_1_sT_bypass_proc_selfix_0),
        selfix((v_1_K_1_sT_bypass_T > 0.0), output=v_1_K_1_sT_bypass_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_k_1_st_bypass_127_emt_template(vf=vf, name='(1-K)/(1+sT) _bypass__127' if name is None else name)
