# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset, selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_st_p_fb_reset_sig_276_emt_template(vf: VarFactory, name: str = '1/sT (p) _fb _reset_sig__276') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sT_p_fb_reset_sig_T = vf.add_var('1/sT (p) _fb _reset_sig__T_' + name)
    v_1_sT_p_fb_reset_sig_y_max = vf.add_var('1/sT (p) _fb _reset_sig__y_max_' + name)

    # --- State Variables ---
    v_1_sT_p_fb_reset_sig_x = vf.add_var('1/sT (p) _fb _reset_sig__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sT_p_fb_reset_sig_proc_selfix_0 = vf.add_var('1/sT (p) _fb _reset_sig__proc_selfix_0_' + name)
    rst = vf.add_var('rst_' + name)
    xrst = vf.add_var('xrst_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sT_p_fb_reset_sig_x = vf.add_diff_var('d_1/sT (p) _fb _reset_sig__x_' + name, base_var=v_1_sT_p_fb_reset_sig_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((v_1_sT_p_fb_reset_sig_proc_selfix_0 * (yi / v_1_sT_p_fb_reset_sig_T)) + ((sym.Const(1.0) - v_1_sT_p_fb_reset_sig_proc_selfix_0) * sym.Const(0.0))),
        ],
        state_vars=[v_1_sT_p_fb_reset_sig_x],
        algebraic_eqs=[
            (yo - (((-v_1_sT_p_fb_reset_sig_y_max) + ((v_1_sT_p_fb_reset_sig_x - (-v_1_sT_p_fb_reset_sig_y_max)) * sym.heaviside((v_1_sT_p_fb_reset_sig_x - (-v_1_sT_p_fb_reset_sig_y_max))))) - ((v_1_sT_p_fb_reset_sig_x - v_1_sT_p_fb_reset_sig_y_max) * sym.heaviside((v_1_sT_p_fb_reset_sig_x - v_1_sT_p_fb_reset_sig_y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, xrst, rst],
        out_vars=[yo],
        name='1/sT (p) _fb _reset_sig'
    )
    templ.block.diff_vars = [d_1_sT_p_fb_reset_sig_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sT_p_fb_reset_sig_T: vf.add_const(None, name='T'),
        v_1_sT_p_fb_reset_sig_y_max: vf.add_const(None, name='y_max'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_sT_p_fb_reset_sig_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((v_1_sT_p_fb_reset_sig_T > 0.0), output=v_1_sT_p_fb_reset_sig_proc_selfix_0),
        reset(v_1_sT_p_fb_reset_sig_x, rst, xrst),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_st_p_fb_reset_sig_276_emt_template(vf=vf, name='1/sT (p) _fb _reset_sig__276' if name is None else name)
