# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_v_1_st_incfreeze_reset_sig_292_emt_template(vf: VarFactory, name: str = '1/sT _incfreeze_reset_sig__292') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sT_incfreeze_reset_sig_T = vf.add_var('1/sT _incfreeze_reset_sig__T_' + name)
    v_1_sT_incfreeze_reset_sig_Tincfreeze = vf.add_var('1/sT _incfreeze_reset_sig__Tincfreeze_' + name)

    # --- State Variables ---
    v_1_sT_incfreeze_reset_sig_x = vf.add_var('1/sT _incfreeze_reset_sig__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sT_incfreeze_reset_sig_proc_select_0 = vf.add_var('1/sT _incfreeze_reset_sig__proc_select_0_' + name)
    v_1_sT_incfreeze_reset_sig_t0 = vf.add_var('1/sT _incfreeze_reset_sig_t0_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    rst = vf.add_var('rst_' + name)
    xrst = vf.add_var('xrst_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sT_incfreeze_reset_sig_x = vf.add_diff_var('d_1/sT _incfreeze_reset_sig__x_' + name, base_var=v_1_sT_incfreeze_reset_sig_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((v_1_sT_incfreeze_reset_sig_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - v_1_sT_incfreeze_reset_sig_proc_select_0) * (yi / v_1_sT_incfreeze_reset_sig_T))),
        ],
        state_vars=[v_1_sT_incfreeze_reset_sig_x],
        algebraic_eqs=[
            (yo - v_1_sT_incfreeze_reset_sig_x),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, xrst, rst],
        out_vars=[yo],
        name='1/sT _incfreeze_reset_sig'
    )
    templ.block.diff_vars = [d_1_sT_incfreeze_reset_sig_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sT_incfreeze_reset_sig_T: vf.add_const(None, name='T'),
        v_1_sT_incfreeze_reset_sig_Tincfreeze: vf.add_const(None, name='Tincfreeze'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_sT_incfreeze_reset_sig_proc_select_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        v_1_sT_incfreeze_reset_sig_t0: glob_time,
    }
    templ.block.procedural_logic = [
        sampled_value(output=v_1_sT_incfreeze_reset_sig_proc_select_0, source=((glob_time - v_1_sT_incfreeze_reset_sig_t0) < v_1_sT_incfreeze_reset_sig_Tincfreeze)),
        reset(v_1_sT_incfreeze_reset_sig_x, rst, xrst),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_st_incfreeze_reset_sig_292_emt_template(vf=vf, name='1/sT _incfreeze_reset_sig__292' if name is None else name)
