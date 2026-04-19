# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_sk_1_st_fb_112_emt_template(vf: VarFactory, name: str = 'sK/(1+sT) _fb__112') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    sK_1_sT_fb_K = vf.add_var('sK/(1+sT) _fb__K_' + name)
    sK_1_sT_fb_T = vf.add_var('sK/(1+sT) _fb__T_' + name)

    # --- State Variables ---
    sK_1_sT_fb_x = vf.add_var('sK/(1+sT) _fb__x_' + name)

    # --- Algebraic / Shared Variables ---
    sK_1_sT_fb_proc_selfix_0 = vf.add_var('sK/(1+sT) _fb__proc_selfix_0_' + name)
    sK_1_sT_fb_dx = vf.add_var('sK/(1+sT) _fb_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_sK_1_sT_fb_x = vf.add_diff_var('d_sK/(1+sT) _fb__x_' + name, base_var=sK_1_sT_fb_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            sK_1_sT_fb_dx,
        ],
        state_vars=[sK_1_sT_fb_x],
        algebraic_eqs=[
            (sK_1_sT_fb_dx - ((sK_1_sT_fb_proc_selfix_0 * ((yi - sK_1_sT_fb_x) / sK_1_sT_fb_T)) + ((sym.Const(1.0) - sK_1_sT_fb_proc_selfix_0) * ((yi - sK_1_sT_fb_x) / sym.Const(0.01))))),
            (yo - (sK_1_sT_fb_K * sK_1_sT_fb_dx)),
        ],
        algebraic_vars=[sK_1_sT_fb_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='sK/(1+sT) _fb'
    )
    templ.block.diff_vars = [d_sK_1_sT_fb_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        sK_1_sT_fb_K: vf.add_const(None, name='K'),
        sK_1_sT_fb_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        sK_1_sT_fb_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((sK_1_sT_fb_T > 0.0), output=sK_1_sT_fb_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_sk_1_st_fb_112_emt_template(vf=vf, name='sK/(1+sT) _fb__112' if name is None else name)
