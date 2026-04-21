# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_stb_1_sta_fb_125_emt_template(vf: VarFactory, name: str = 'sTb/(1+sTa) _fb__125') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    sTb_1_sTa_fb_Ta = vf.add_var('sTb/(1+sTa) _fb__Ta_' + name)
    sTb_1_sTa_fb_Tb = vf.add_var('sTb/(1+sTa) _fb__Tb_' + name)

    # --- State Variables ---
    sTb_1_sTa_fb_x = vf.add_var('sTb/(1+sTa) _fb__x_' + name)

    # --- Algebraic / Shared Variables ---
    sTb_1_sTa_fb_proc_selfix_0 = vf.add_var('sTb/(1+sTa) _fb__proc_selfix_0_' + name)
    sTb_1_sTa_fb_dx = vf.add_var('sTb/(1+sTa) _fb_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_sTb_1_sTa_fb_x = vf.add_diff_var('d_sTb/(1+sTa) _fb__x_' + name, base_var=sTb_1_sTa_fb_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            sTb_1_sTa_fb_dx,
        ],
        state_vars=[sTb_1_sTa_fb_x],
        algebraic_eqs=[
            (sTb_1_sTa_fb_dx - ((sTb_1_sTa_fb_proc_selfix_0 * ((yi - sTb_1_sTa_fb_x) / sTb_1_sTa_fb_Ta)) + ((sym.Const(1.0) - sTb_1_sTa_fb_proc_selfix_0) * ((yi - sTb_1_sTa_fb_x) / sym.Const(0.01))))),
            (yo - (sTb_1_sTa_fb_Tb * sTb_1_sTa_fb_dx)),
        ],
        algebraic_vars=[sTb_1_sTa_fb_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='sTb/(1+sTa) _fb'
    )
    templ.block.diff_vars = [d_sTb_1_sTa_fb_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        sTb_1_sTa_fb_Tb: vf.add_const(None, name='Tb'),
        sTb_1_sTa_fb_Ta: vf.add_const(None, name='Ta'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        sTb_1_sTa_fb_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((sTb_1_sTa_fb_Ta > 0.0), output=sTb_1_sTa_fb_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_stb_1_sta_fb_125_emt_template(vf=vf, name='sTb/(1+sTa) _fb__125' if name is None else name)
