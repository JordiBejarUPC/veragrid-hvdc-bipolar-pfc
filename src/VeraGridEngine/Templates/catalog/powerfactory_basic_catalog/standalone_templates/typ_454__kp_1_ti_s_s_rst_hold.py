# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_kp_1_ti_s_s_rst_hold_454_emt_template(vf: VarFactory, name: str = 'Kp(1/Ti+s)/s _rst_hold__454') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kp_1_Ti_s_s_rst_hold_Kp = vf.add_var('Kp(1/Ti+s)/s _rst_hold__Kp_' + name)
    Kp_1_Ti_s_s_rst_hold_Ti = vf.add_var('Kp(1/Ti+s)/s _rst_hold__Ti_' + name)

    # --- State Variables ---
    Kp_1_Ti_s_s_rst_hold_x = vf.add_var('Kp(1/Ti+s)/s _rst_hold__x_' + name)

    # --- Algebraic / Shared Variables ---
    Kp_1_Ti_s_s_rst_hold_proc_lastvalue_1 = vf.add_var('Kp(1/Ti+s)/s _rst_hold__proc_lastvalue_1_' + name)
    Kp_1_Ti_s_s_rst_hold_proc_select_0 = vf.add_var('Kp(1/Ti+s)/s _rst_hold__proc_select_0_' + name)
    Kp_1_Ti_s_s_rst_hold_proc_select_2 = vf.add_var('Kp(1/Ti+s)/s _rst_hold__proc_select_2_' + name)
    Kp_1_Ti_s_s_rst_hold_x_init = vf.add_var('Kp(1/Ti+s)/s _rst_hold_x_init_' + name)
    hold = vf.add_var('hold_' + name)
    rst = vf.add_var('rst_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Kp_1_Ti_s_s_rst_hold_x = vf.add_diff_var('d_Kp(1/Ti+s)/s _rst_hold__x_' + name, base_var=Kp_1_Ti_s_s_rst_hold_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Kp_1_Ti_s_s_rst_hold_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Kp_1_Ti_s_s_rst_hold_proc_select_0) * ((Kp_1_Ti_s_s_rst_hold_Kp / Kp_1_Ti_s_s_rst_hold_Ti) * yi))),
        ],
        state_vars=[Kp_1_Ti_s_s_rst_hold_x],
        algebraic_eqs=[
            (yo - ((Kp_1_Ti_s_s_rst_hold_proc_select_2 * Kp_1_Ti_s_s_rst_hold_proc_lastvalue_1) + ((sym.Const(1.0) - Kp_1_Ti_s_s_rst_hold_proc_select_2) * ((Kp_1_Ti_s_s_rst_hold_Kp * yi) + Kp_1_Ti_s_s_rst_hold_x)))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, hold, rst],
        out_vars=[yo],
        name='Kp(1/Ti+s)/s _rst_hold'
    )
    templ.block.diff_vars = [d_Kp_1_Ti_s_s_rst_hold_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kp_1_Ti_s_s_rst_hold_Kp: vf.add_const(None, name='Kp'),
        Kp_1_Ti_s_s_rst_hold_Ti: vf.add_const(None, name='Ti'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Kp_1_Ti_s_s_rst_hold_proc_select_0: vf.add_const(0.0, name=''),
        Kp_1_Ti_s_s_rst_hold_proc_lastvalue_1: vf.add_const(0.0, name=''),
        Kp_1_Ti_s_s_rst_hold_proc_select_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Kp_1_Ti_s_s_rst_hold_x_init: Kp_1_Ti_s_s_rst_hold_x,
    }
    templ.block.procedural_logic = [
        sampled_value(output=Kp_1_Ti_s_s_rst_hold_proc_select_0, source=hold),
        lastvalue(yo, output=Kp_1_Ti_s_s_rst_hold_proc_lastvalue_1),
        sampled_value(output=Kp_1_Ti_s_s_rst_hold_proc_select_2, source=hold),
        reset(Kp_1_Ti_s_s_rst_hold_x, rst, Kp_1_Ti_s_s_rst_hold_x_init),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kp_1_ti_s_s_rst_hold_454_emt_template(vf=vf, name='Kp(1/Ti+s)/s _rst_hold__454' if name is None else name)
