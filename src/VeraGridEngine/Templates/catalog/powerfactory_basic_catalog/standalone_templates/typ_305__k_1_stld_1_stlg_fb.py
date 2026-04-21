# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_k_1_stld_1_stlg_fb_305_emt_template(vf: VarFactory, name: str = 'K(1+sTld)/(1+sTlg) _fb__305') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_1_sTld_1_sTlg_fb_K = vf.add_var('K(1+sTld)/(1+sTlg) _fb__K_' + name)
    K_1_sTld_1_sTlg_fb_Tld = vf.add_var('K(1+sTld)/(1+sTlg) _fb__Tld_' + name)
    K_1_sTld_1_sTlg_fb_Tlg = vf.add_var('K(1+sTld)/(1+sTlg) _fb__Tlg_' + name)

    # --- State Variables ---
    K_1_sTld_1_sTlg_fb_x = vf.add_var('K(1+sTld)/(1+sTlg) _fb__x_' + name)

    # --- Algebraic / Shared Variables ---
    K_1_sTld_1_sTlg_fb_proc_selfix_0 = vf.add_var('K(1+sTld)/(1+sTlg) _fb__proc_selfix_0_' + name)
    K_1_sTld_1_sTlg_fb_dx = vf.add_var('K(1+sTld)/(1+sTlg) _fb_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_1_sTld_1_sTlg_fb_x = vf.add_diff_var('d_K(1+sTld)/(1+sTlg) _fb__x_' + name, base_var=K_1_sTld_1_sTlg_fb_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            K_1_sTld_1_sTlg_fb_dx,
        ],
        state_vars=[K_1_sTld_1_sTlg_fb_x],
        algebraic_eqs=[
            (K_1_sTld_1_sTlg_fb_dx - ((K_1_sTld_1_sTlg_fb_proc_selfix_0 * (((K_1_sTld_1_sTlg_fb_K * yi) - K_1_sTld_1_sTlg_fb_x) / K_1_sTld_1_sTlg_fb_Tlg)) + ((sym.Const(1.0) - K_1_sTld_1_sTlg_fb_proc_selfix_0) * (((K_1_sTld_1_sTlg_fb_K * yi) - K_1_sTld_1_sTlg_fb_x) / sym.Const(0.01))))),
            (yo - (K_1_sTld_1_sTlg_fb_x + (K_1_sTld_1_sTlg_fb_Tld * K_1_sTld_1_sTlg_fb_dx))),
        ],
        algebraic_vars=[K_1_sTld_1_sTlg_fb_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='K(1+sTld)/(1+sTlg) _fb'
    )
    templ.block.diff_vars = [d_K_1_sTld_1_sTlg_fb_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_1_sTld_1_sTlg_fb_K: vf.add_const(None, name='K'),
        K_1_sTld_1_sTlg_fb_Tld: vf.add_const(None, name='Tld'),
        K_1_sTld_1_sTlg_fb_Tlg: vf.add_const(None, name='Tlg'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        K_1_sTld_1_sTlg_fb_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((K_1_sTld_1_sTlg_fb_Tlg > 0.0), output=K_1_sTld_1_sTlg_fb_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_1_stld_1_stlg_fb_305_emt_template(vf=vf, name='K(1+sTld)/(1+sTlg) _fb__305' if name is None else name)
