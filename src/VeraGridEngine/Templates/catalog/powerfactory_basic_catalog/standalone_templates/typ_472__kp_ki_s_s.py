# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_kp_ki_s_s_472_emt_template(vf: VarFactory, name: str = 'Kp+Ki/s [s__472') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kp_Ki_s_s_Ki = vf.add_var('Kp+Ki/s [s__Ki_' + name)
    Kp_Ki_s_s_Kp = vf.add_var('Kp+Ki/s [s__Kp_' + name)

    # --- State Variables ---
    Kp_Ki_s_s_x = vf.add_var('Kp+Ki/s [s__x_' + name)

    # --- Algebraic / Shared Variables ---
    Kp_Ki_s_s_proc_lastvalue_1 = vf.add_var('Kp+Ki/s [s__proc_lastvalue_1_' + name)
    Kp_Ki_s_s_proc_select_0 = vf.add_var('Kp+Ki/s [s__proc_select_0_' + name)
    Kp_Ki_s_s_proc_select_2 = vf.add_var('Kp+Ki/s [s__proc_select_2_' + name)
    hold = vf.add_var('hold_' + name)
    rst = vf.add_var('rst_' + name)
    x_rst = vf.add_var('x_rst_' + name)
    yi = vf.add_var('yi_' + name)
    ymax = vf.add_var('ymax_' + name)
    ymin = vf.add_var('ymin_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Kp_Ki_s_s_x = vf.add_diff_var('d_Kp+Ki/s [s__x_' + name, base_var=Kp_Ki_s_s_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Kp_Ki_s_s_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Kp_Ki_s_s_proc_select_0) * (Kp_Ki_s_s_Ki * yi))),
        ],
        state_vars=[Kp_Ki_s_s_x],
        algebraic_eqs=[
            (yo - ((Kp_Ki_s_s_proc_select_2 * Kp_Ki_s_s_proc_lastvalue_1) + ((sym.Const(1.0) - Kp_Ki_s_s_proc_select_2) * ((ymin + (((Kp_Ki_s_s_x + (Kp_Ki_s_s_Kp * yi)) - ymin) * sym.heaviside(((Kp_Ki_s_s_x + (Kp_Ki_s_s_Kp * yi)) - ymin)))) - (((Kp_Ki_s_s_x + (Kp_Ki_s_s_Kp * yi)) - ymax) * sym.heaviside(((Kp_Ki_s_s_x + (Kp_Ki_s_s_Kp * yi)) - ymax))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, hold, x_rst, ymax, rst, ymin],
        out_vars=[yo],
        name='Kp+Ki/s [s'
    )
    templ.block.diff_vars = [d_Kp_Ki_s_s_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kp_Ki_s_s_Kp: vf.add_const(None, name='Kp'),
        Kp_Ki_s_s_Ki: vf.add_const(None, name='Ki'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Kp_Ki_s_s_proc_select_0: vf.add_const(0.0, name=''),
        Kp_Ki_s_s_proc_lastvalue_1: vf.add_const(0.0, name=''),
        Kp_Ki_s_s_proc_select_2: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Kp_Ki_s_s_proc_select_0, source=hold),
        lastvalue(yo, output=Kp_Ki_s_s_proc_lastvalue_1),
        sampled_value(output=Kp_Ki_s_s_proc_select_2, source=hold),
        reset(Kp_Ki_s_s_x, rst, x_rst),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kp_ki_s_s_472_emt_template(vf=vf, name='Kp+Ki/s [s__472' if name is None else name)
