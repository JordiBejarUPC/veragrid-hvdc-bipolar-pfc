# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\DGS_test_type_models.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_pi_with_hold_and_reset_emt_template(vf: VarFactory, name: str = 'PI with hold and reset') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    PI_with_hold_and_reset_GFOR_QREG_Kp = vf.add_var('PI with hold and reset__GFOR_QREG_Kp_' + name)
    PI_with_hold_and_reset_GFOR_QREG_Ti = vf.add_var('PI with hold and reset__GFOR_QREG_Ti_' + name)

    # --- State Variables ---
    PI_with_hold_and_reset_x = vf.add_var('PI with hold and reset__x_' + name)

    # --- Algebraic / Shared Variables ---
    PI_with_hold_and_reset_proc_lastvalue_1 = vf.add_var('PI with hold and reset__proc_lastvalue_1_' + name)
    PI_with_hold_and_reset_proc_select_0 = vf.add_var('PI with hold and reset__proc_select_0_' + name)
    PI_with_hold_and_reset_proc_select_2 = vf.add_var('PI with hold and reset__proc_select_2_' + name)
    hold = vf.add_var('hold_' + name)
    rst = vf.add_var('rst_' + name)
    x_init = vf.add_var('x_init_' + name)
    y_max_PI = vf.add_var('y_max_PI_' + name)
    y_min_PI = vf.add_var('y_min_PI_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_PI_with_hold_and_reset_x = vf.add_diff_var('d_PI with hold and reset__x_' + name, base_var=PI_with_hold_and_reset_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((PI_with_hold_and_reset_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - PI_with_hold_and_reset_proc_select_0) * ((PI_with_hold_and_reset_GFOR_QREG_Kp / PI_with_hold_and_reset_GFOR_QREG_Ti) * yi))),
        ],
        state_vars=[PI_with_hold_and_reset_x],
        algebraic_eqs=[
            (yo - ((PI_with_hold_and_reset_proc_select_2 * PI_with_hold_and_reset_proc_lastvalue_1) + ((sym.Const(1.0) - PI_with_hold_and_reset_proc_select_2) * ((y_min_PI + ((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_min_PI) * sym.heaviside((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_min_PI)))) - ((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_max_PI) * sym.heaviside((((PI_with_hold_and_reset_GFOR_QREG_Kp * yi) + ((y_min_PI + ((PI_with_hold_and_reset_x - y_min_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_min_PI)))) - ((PI_with_hold_and_reset_x - y_max_PI) * sym.heaviside((PI_with_hold_and_reset_x - y_max_PI))))) - y_max_PI))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, hold, rst, y_max_PI, y_min_PI, x_init],
        out_vars=[yo],
        name='PI with hold and reset'
    )
    templ.block.diff_vars = [d_PI_with_hold_and_reset_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        PI_with_hold_and_reset_GFOR_QREG_Kp: vf.add_const(None, name='GFOR_QREG_Kp'),
        PI_with_hold_and_reset_GFOR_QREG_Ti: vf.add_const(None, name='GFOR_QREG_Ti'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        PI_with_hold_and_reset_proc_select_0: vf.add_const(0.0, name=''),
        PI_with_hold_and_reset_proc_lastvalue_1: vf.add_const(0.0, name=''),
        PI_with_hold_and_reset_proc_select_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        PI_with_hold_and_reset_x: x_init,
    }
    templ.block.procedural_logic = [
        sampled_value(output=PI_with_hold_and_reset_proc_select_0, source=hold),
        lastvalue(yo, output=PI_with_hold_and_reset_proc_lastvalue_1),
        sampled_value(output=PI_with_hold_and_reset_proc_select_2, source=hold),
        reset(PI_with_hold_and_reset_x, rst, x_init),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_pi_with_hold_and_reset_emt_template(vf=vf, name='PI with hold and reset' if name is None else name)
