# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_stld_1_stlg_fb_126_emt_template(vf: VarFactory, name: str = 'sTld/(1+sTlg) _fb__126') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    sTld_1_sTlg_fb_Tld = vf.add_var('sTld/(1+sTlg) _fb__Tld_' + name)
    sTld_1_sTlg_fb_Tlg = vf.add_var('sTld/(1+sTlg) _fb__Tlg_' + name)

    # --- State Variables ---
    sTld_1_sTlg_fb_x = vf.add_var('sTld/(1+sTlg) _fb__x_' + name)

    # --- Algebraic / Shared Variables ---
    sTld_1_sTlg_fb_proc_selfix_0 = vf.add_var('sTld/(1+sTlg) _fb__proc_selfix_0_' + name)
    sTld_1_sTlg_fb_dx = vf.add_var('sTld/(1+sTlg) _fb_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_sTld_1_sTlg_fb_x = vf.add_diff_var('d_sTld/(1+sTlg) _fb__x_' + name, base_var=sTld_1_sTlg_fb_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            sTld_1_sTlg_fb_dx,
        ],
        state_vars=[sTld_1_sTlg_fb_x],
        algebraic_eqs=[
            (sTld_1_sTlg_fb_dx - ((sTld_1_sTlg_fb_proc_selfix_0 * ((yi - sTld_1_sTlg_fb_x) / sTld_1_sTlg_fb_Tlg)) + ((sym.Const(1.0) - sTld_1_sTlg_fb_proc_selfix_0) * ((yi - sTld_1_sTlg_fb_x) / sym.Const(0.01))))),
            (yo - (sTld_1_sTlg_fb_Tld * sTld_1_sTlg_fb_dx)),
        ],
        algebraic_vars=[sTld_1_sTlg_fb_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='sTld/(1+sTlg) _fb'
    )
    templ.block.diff_vars = [d_sTld_1_sTlg_fb_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        sTld_1_sTlg_fb_Tld: vf.add_const(None, name='Tld'),
        sTld_1_sTlg_fb_Tlg: vf.add_const(None, name='Tlg'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        sTld_1_sTlg_fb_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((sTld_1_sTlg_fb_Tlg > 0.0), output=sTld_1_sTlg_fb_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_stld_1_stlg_fb_126_emt_template(vf=vf, name='sTld/(1+sTlg) _fb__126' if name is None else name)
