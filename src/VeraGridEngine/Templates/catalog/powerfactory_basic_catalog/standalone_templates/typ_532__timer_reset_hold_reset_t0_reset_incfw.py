# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_timer_reset_hold_reset_t0_reset_incfw_532_emt_template(vf: VarFactory, name: str = 'Timer (reset/hold reset/t0) _reset_incfw__532') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Timer_reset_hold_reset_t0_reset_incfw_flank = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw__flank_' + name)
    Timer_reset_hold_reset_t0_reset_incfw_t_start_delay = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw__t_start_delay_' + name)

    # --- State Variables ---
    Timer_reset_hold_reset_t0_reset_incfw_x = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw__x_' + name)

    # --- Algebraic / Shared Variables ---
    Timer_reset_hold_reset_t0_reset_incfw_proc_lastvalue_3 = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw__proc_lastvalue_3_' + name)
    Timer_reset_hold_reset_t0_reset_incfw_proc_select_2 = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw__proc_select_2_' + name)
    Timer_reset_hold_reset_t0_reset_incfw_proc_select_4 = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw__proc_select_4_' + name)
    Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_0 = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw__proc_selfix_0_' + name)
    Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_1 = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw__proc_selfix_1_' + name)
    Timer_reset_hold_reset_t0_reset_incfw_dir = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw_dir_' + name)
    Timer_reset_hold_reset_t0_reset_incfw_tinc = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw_tinc_' + name)
    Timer_reset_hold_reset_t0_reset_incfw_tldf = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw_tldf_' + name)
    Timer_reset_hold_reset_t0_reset_incfw_tx = vf.add_var('Timer (reset/hold reset/t0) _reset_incfw_tx_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    rst = vf.add_var('rst_' + name)
    t0 = vf.add_var('t0_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Timer_reset_hold_reset_t0_reset_incfw_x = vf.add_diff_var('d_Timer (reset/hold reset/t0) _reset_incfw__x_' + name, base_var=Timer_reset_hold_reset_t0_reset_incfw_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Timer_reset_hold_reset_t0_reset_incfw_proc_select_2 * sym.Const(1.0)) + ((sym.Const(1.0) - Timer_reset_hold_reset_t0_reset_incfw_proc_select_2) * sym.Const(0.0))),
        ],
        state_vars=[Timer_reset_hold_reset_t0_reset_incfw_x],
        algebraic_eqs=[
            (Timer_reset_hold_reset_t0_reset_incfw_dir - ((Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_1 * rst) + ((sym.Const(1.0) - Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_1) * ((-rst) + sym.Const(1.0))))),
            (Timer_reset_hold_reset_t0_reset_incfw_tx - ((Timer_reset_hold_reset_t0_reset_incfw_proc_select_4 * Timer_reset_hold_reset_t0_reset_incfw_x) + ((sym.Const(1.0) - Timer_reset_hold_reset_t0_reset_incfw_proc_select_4) * Timer_reset_hold_reset_t0_reset_incfw_proc_lastvalue_3))),
            (yo - ((Timer_reset_hold_reset_t0_reset_incfw_x - Timer_reset_hold_reset_t0_reset_incfw_tx) + Timer_reset_hold_reset_t0_reset_incfw_tinc)),
        ],
        algebraic_vars=[Timer_reset_hold_reset_t0_reset_incfw_dir, Timer_reset_hold_reset_t0_reset_incfw_tx, yo],
        in_vars=[rst, t0],
        out_vars=[yo],
        name='Timer (reset/hold reset/t0) _reset_incfw'
    )
    templ.block.diff_vars = [d_Timer_reset_hold_reset_t0_reset_incfw_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Timer_reset_hold_reset_t0_reset_incfw_flank: vf.add_const(None, name='flank'),
        Timer_reset_hold_reset_t0_reset_incfw_t_start_delay: vf.add_const(None, name='t_start_delay'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_0: vf.add_const(0.0, name=''),
        Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_1: vf.add_const(0.0, name=''),
        Timer_reset_hold_reset_t0_reset_incfw_proc_select_2: vf.add_const(0.0, name=''),
        Timer_reset_hold_reset_t0_reset_incfw_proc_lastvalue_3: vf.add_const(0.0, name=''),
        Timer_reset_hold_reset_t0_reset_incfw_proc_select_4: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Timer_reset_hold_reset_t0_reset_incfw_dir: ((Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_0 * rst) + ((sym.Const(1.0) - Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_0) * ((-rst) + sym.Const(1.0)))),
        Timer_reset_hold_reset_t0_reset_incfw_tldf: glob_time,
        Timer_reset_hold_reset_t0_reset_incfw_tx: vf.add_const(0.0, name=''),
        Timer_reset_hold_reset_t0_reset_incfw_x: vf.add_const(0.0, name=''),
        Timer_reset_hold_reset_t0_reset_incfw_tinc: t0,
        yo: t0,
    }
    templ.block.procedural_logic = [
        selfix((Timer_reset_hold_reset_t0_reset_incfw_flank < 0.5), output=Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_0),
        selfix((Timer_reset_hold_reset_t0_reset_incfw_flank < 0.5), output=Timer_reset_hold_reset_t0_reset_incfw_proc_selfix_1),
        sampled_value(output=Timer_reset_hold_reset_t0_reset_incfw_proc_select_2, source=((glob_time - Timer_reset_hold_reset_t0_reset_incfw_tldf) > Timer_reset_hold_reset_t0_reset_incfw_t_start_delay)),
        lastvalue(Timer_reset_hold_reset_t0_reset_incfw_tx, output=Timer_reset_hold_reset_t0_reset_incfw_proc_lastvalue_3),
        sampled_value(output=Timer_reset_hold_reset_t0_reset_incfw_proc_select_4, source=(Timer_reset_hold_reset_t0_reset_incfw_dir > 0.5)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_timer_reset_hold_reset_t0_reset_incfw_532_emt_template(vf=vf, name='Timer (reset/hold reset/t0) _reset_incfw__532' if name is None else name)
