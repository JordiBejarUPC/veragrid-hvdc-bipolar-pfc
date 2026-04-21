# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_k_a1_st1_a2_st2_fb_307_emt_template(vf: VarFactory, name: str = 'K(A1+sT1)/(A2+sT2) _fb__307') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_A1_sT1_A2_sT2_fb_A1 = vf.add_var('K(A1+sT1)/(A2+sT2) _fb__A1_' + name)
    K_A1_sT1_A2_sT2_fb_A2 = vf.add_var('K(A1+sT1)/(A2+sT2) _fb__A2_' + name)
    K_A1_sT1_A2_sT2_fb_K = vf.add_var('K(A1+sT1)/(A2+sT2) _fb__K_' + name)
    K_A1_sT1_A2_sT2_fb_T1 = vf.add_var('K(A1+sT1)/(A2+sT2) _fb__T1_' + name)
    K_A1_sT1_A2_sT2_fb_T2 = vf.add_var('K(A1+sT1)/(A2+sT2) _fb__T2_' + name)

    # --- State Variables ---
    K_A1_sT1_A2_sT2_fb_x = vf.add_var('K(A1+sT1)/(A2+sT2) _fb__x_' + name)

    # --- Algebraic / Shared Variables ---
    K_A1_sT1_A2_sT2_fb_proc_selfix_0 = vf.add_var('K(A1+sT1)/(A2+sT2) _fb__proc_selfix_0_' + name)
    K_A1_sT1_A2_sT2_fb_dx = vf.add_var('K(A1+sT1)/(A2+sT2) _fb_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_A1_sT1_A2_sT2_fb_x = vf.add_diff_var('d_K(A1+sT1)/(A2+sT2) _fb__x_' + name, base_var=K_A1_sT1_A2_sT2_fb_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            K_A1_sT1_A2_sT2_fb_dx,
        ],
        state_vars=[K_A1_sT1_A2_sT2_fb_x],
        algebraic_eqs=[
            (K_A1_sT1_A2_sT2_fb_dx - ((K_A1_sT1_A2_sT2_fb_proc_selfix_0 * (((K_A1_sT1_A2_sT2_fb_K * yi) - (K_A1_sT1_A2_sT2_fb_A2 * K_A1_sT1_A2_sT2_fb_x)) / K_A1_sT1_A2_sT2_fb_T2)) + ((sym.Const(1.0) - K_A1_sT1_A2_sT2_fb_proc_selfix_0) * (((K_A1_sT1_A2_sT2_fb_K * yi) - (K_A1_sT1_A2_sT2_fb_A2 * K_A1_sT1_A2_sT2_fb_x)) / sym.Const(0.01))))),
            (yo - ((K_A1_sT1_A2_sT2_fb_A1 * K_A1_sT1_A2_sT2_fb_x) + (K_A1_sT1_A2_sT2_fb_T1 * K_A1_sT1_A2_sT2_fb_dx))),
        ],
        algebraic_vars=[K_A1_sT1_A2_sT2_fb_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='K(A1+sT1)/(A2+sT2) _fb'
    )
    templ.block.diff_vars = [d_K_A1_sT1_A2_sT2_fb_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_A1_sT1_A2_sT2_fb_K: vf.add_const(None, name='K'),
        K_A1_sT1_A2_sT2_fb_A1: vf.add_const(None, name='A1'),
        K_A1_sT1_A2_sT2_fb_T1: vf.add_const(None, name='T1'),
        K_A1_sT1_A2_sT2_fb_A2: vf.add_const(None, name='A2'),
        K_A1_sT1_A2_sT2_fb_T2: vf.add_const(None, name='T2'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        K_A1_sT1_A2_sT2_fb_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((K_A1_sT1_A2_sT2_fb_T2 > 0.0), output=K_A1_sT1_A2_sT2_fb_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_a1_st1_a2_st2_fb_307_emt_template(vf=vf, name='K(A1+sT1)/(A2+sT2) _fb__307' if name is None else name)
