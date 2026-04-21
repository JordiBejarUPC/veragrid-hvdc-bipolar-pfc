# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_k_1_st_bypass_150_emt_template(vf: VarFactory, name: str = 'K/(1+sT) _bypass__150') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_1_sT_bypass_K = vf.add_var('K/(1+sT) _bypass__K_' + name)
    K_1_sT_bypass_T = vf.add_var('K/(1+sT) _bypass__T_' + name)

    # --- State Variables ---
    K_1_sT_bypass_x = vf.add_var('K/(1+sT) _bypass__x_' + name)

    # --- Algebraic / Shared Variables ---
    K_1_sT_bypass_proc_selfix_0 = vf.add_var('K/(1+sT) _bypass__proc_selfix_0_' + name)
    K_1_sT_bypass_proc_selfix_1 = vf.add_var('K/(1+sT) _bypass__proc_selfix_1_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_1_sT_bypass_x = vf.add_diff_var('d_K/(1+sT) _bypass__x_' + name, base_var=K_1_sT_bypass_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((K_1_sT_bypass_proc_selfix_0 * (((K_1_sT_bypass_K * yi) - K_1_sT_bypass_x) / K_1_sT_bypass_T)) + ((sym.Const(1.0) - K_1_sT_bypass_proc_selfix_0) * sym.Const(0.0))),
        ],
        state_vars=[K_1_sT_bypass_x],
        algebraic_eqs=[
            (yo - ((K_1_sT_bypass_proc_selfix_1 * K_1_sT_bypass_x) + ((sym.Const(1.0) - K_1_sT_bypass_proc_selfix_1) * (K_1_sT_bypass_K * yi)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='K/(1+sT) _bypass'
    )
    templ.block.diff_vars = [d_K_1_sT_bypass_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_1_sT_bypass_K: vf.add_const(None, name='K'),
        K_1_sT_bypass_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        K_1_sT_bypass_proc_selfix_0: vf.add_const(0.0, name=''),
        K_1_sT_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((K_1_sT_bypass_T > 0.0), output=K_1_sT_bypass_proc_selfix_0),
        selfix((K_1_sT_bypass_T > 0.0), output=K_1_sT_bypass_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_1_st_bypass_150_emt_template(vf=vf, name='K/(1+sT) _bypass__150' if name is None else name)
