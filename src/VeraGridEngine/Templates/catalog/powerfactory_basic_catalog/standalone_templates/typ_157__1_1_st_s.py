# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_v_1_1_st_s_157_emt_template(vf: VarFactory, name: str = '1/(1+sT) (s__157') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_1_sT_s_T = vf.add_var('1/(1+sT) (s__T_' + name)

    # --- State Variables ---
    v_1_1_sT_s_x = vf.add_var('1/(1+sT) (s__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_1_sT_s_proc_lastvalue_1 = vf.add_var('1/(1+sT) (s__proc_lastvalue_1_' + name)
    v_1_1_sT_s_proc_select_0 = vf.add_var('1/(1+sT) (s__proc_select_0_' + name)
    v_1_1_sT_s_proc_select_2 = vf.add_var('1/(1+sT) (s__proc_select_2_' + name)
    v_1_1_sT_s_x_init = vf.add_var('1/(1+sT) (s_x_init_' + name)
    hold = vf.add_var('hold_' + name)
    rst = vf.add_var('rst_' + name)
    y_max = vf.add_var('y_max_' + name)
    y_min = vf.add_var('y_min_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_1_sT_s_x = vf.add_diff_var('d_1/(1+sT) (s__x_' + name, base_var=v_1_1_sT_s_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((v_1_1_sT_s_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - v_1_1_sT_s_proc_select_0) * ((yi - yo) / v_1_1_sT_s_T))),
        ],
        state_vars=[v_1_1_sT_s_x],
        algebraic_eqs=[
            (yo - ((v_1_1_sT_s_proc_select_2 * v_1_1_sT_s_proc_lastvalue_1) + ((sym.Const(1.0) - v_1_1_sT_s_proc_select_2) * ((y_min + ((v_1_1_sT_s_x - y_min) * sym.heaviside((v_1_1_sT_s_x - y_min)))) - ((v_1_1_sT_s_x - y_max) * sym.heaviside((v_1_1_sT_s_x - y_max))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, hold, y_max, rst, y_min],
        out_vars=[yo],
        name='1/(1+sT) (s'
    )
    templ.block.diff_vars = [d_1_1_sT_s_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_1_sT_s_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_1_sT_s_proc_select_0: vf.add_const(0.0, name=''),
        v_1_1_sT_s_proc_lastvalue_1: vf.add_const(0.0, name=''),
        v_1_1_sT_s_proc_select_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        v_1_1_sT_s_x_init: v_1_1_sT_s_x,
    }
    templ.block.procedural_logic = [
        sampled_value(output=v_1_1_sT_s_proc_select_0, source=hold),
        lastvalue(yo, output=v_1_1_sT_s_proc_lastvalue_1),
        sampled_value(output=v_1_1_sT_s_proc_select_2, source=hold),
        reset(v_1_1_sT_s_x, rst, v_1_1_sT_s_x_init),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_1_st_s_157_emt_template(vf=vf, name='1/(1+sT) (s__157' if name is None else name)
