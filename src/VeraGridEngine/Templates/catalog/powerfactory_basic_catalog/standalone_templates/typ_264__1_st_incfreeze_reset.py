# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_v_1_st_incfreeze_reset_264_emt_template(vf: VarFactory, name: str = '1/sT _incfreeze_reset__264') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sT_incfreeze_reset_T = vf.add_var('1/sT _incfreeze_reset__T_' + name)
    v_1_sT_incfreeze_reset_Tincfreeze = vf.add_var('1/sT _incfreeze_reset__Tincfreeze_' + name)

    # --- State Variables ---
    v_1_sT_incfreeze_reset_x = vf.add_var('1/sT _incfreeze_reset__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sT_incfreeze_reset_proc_select_0 = vf.add_var('1/sT _incfreeze_reset__proc_select_0_' + name)
    v_1_sT_incfreeze_reset_t0 = vf.add_var('1/sT _incfreeze_reset_t0_' + name)
    v_1_sT_incfreeze_reset_xinc = vf.add_var('1/sT _incfreeze_reset_xinc_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    rst = vf.add_var('rst_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sT_incfreeze_reset_x = vf.add_diff_var('d_1/sT _incfreeze_reset__x_' + name, base_var=v_1_sT_incfreeze_reset_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((v_1_sT_incfreeze_reset_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - v_1_sT_incfreeze_reset_proc_select_0) * (yi / v_1_sT_incfreeze_reset_T))),
        ],
        state_vars=[v_1_sT_incfreeze_reset_x],
        algebraic_eqs=[
            (yo - v_1_sT_incfreeze_reset_x),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, rst],
        out_vars=[yo],
        name='1/sT _incfreeze_reset'
    )
    templ.block.diff_vars = [d_1_sT_incfreeze_reset_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sT_incfreeze_reset_T: vf.add_const(None, name='T'),
        v_1_sT_incfreeze_reset_Tincfreeze: vf.add_const(None, name='Tincfreeze'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_sT_incfreeze_reset_proc_select_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        v_1_sT_incfreeze_reset_t0: glob_time,
        v_1_sT_incfreeze_reset_xinc: v_1_sT_incfreeze_reset_x,
    }
    templ.block.procedural_logic = [
        sampled_value(output=v_1_sT_incfreeze_reset_proc_select_0, source=((glob_time - v_1_sT_incfreeze_reset_t0) < v_1_sT_incfreeze_reset_Tincfreeze)),
        reset(v_1_sT_incfreeze_reset_x, rst, v_1_sT_incfreeze_reset_xinc),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_st_incfreeze_reset_264_emt_template(vf=vf, name='1/sT _incfreeze_reset__264' if name is None else name)
