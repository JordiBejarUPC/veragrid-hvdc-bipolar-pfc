# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_kp_1_ti_s_s_s_rst_variant_452_emt_template(vf: VarFactory, name: str = 'Kp(1/Ti+s)/s (s) _rst (variant)__452') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kp_1_Ti_s_s_s_rst_variant_Kaw = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)__Kaw_' + name)
    Kp_1_Ti_s_s_s_rst_variant_Kp = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)__Kp_' + name)
    Kp_1_Ti_s_s_s_rst_variant_Ti = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)__Ti_' + name)
    Kp_1_Ti_s_s_s_rst_variant_y_max = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)__y_max_' + name)
    Kp_1_Ti_s_s_s_rst_variant_y_min = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)__y_min_' + name)

    # --- State Variables ---
    Kp_1_Ti_s_s_s_rst_variant_x = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)__x_' + name)

    # --- Algebraic / Shared Variables ---
    Kp_1_Ti_s_s_s_rst_variant_PIsum = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)_PIsum_' + name)
    Kp_1_Ti_s_s_s_rst_variant_proc_lastvalue_1 = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)__proc_lastvalue_1_' + name)
    Kp_1_Ti_s_s_s_rst_variant_proc_select_0 = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)__proc_select_0_' + name)
    Kp_1_Ti_s_s_s_rst_variant_proc_select_2 = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)__proc_select_2_' + name)
    Kp_1_Ti_s_s_s_rst_variant_x_init = vf.add_var('Kp(1/Ti+s)/s (s) _rst (variant)_x_init_' + name)
    rst = vf.add_var('rst_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Kp_1_Ti_s_s_s_rst_variant_x = vf.add_diff_var('d_Kp(1/Ti+s)/s (s) _rst (variant)__x_' + name, base_var=Kp_1_Ti_s_s_s_rst_variant_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Kp_1_Ti_s_s_s_rst_variant_proc_select_2 * ((yi + (Kp_1_Ti_s_s_s_rst_variant_proc_lastvalue_1 * Kp_1_Ti_s_s_s_rst_variant_Kaw)) / Kp_1_Ti_s_s_s_rst_variant_Ti)) + ((sym.Const(1.0) - Kp_1_Ti_s_s_s_rst_variant_proc_select_2) * sym.Const(0.0))),
        ],
        state_vars=[Kp_1_Ti_s_s_s_rst_variant_x],
        algebraic_eqs=[
            (Kp_1_Ti_s_s_s_rst_variant_PIsum - (((Kp_1_Ti_s_s_s_rst_variant_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - Kp_1_Ti_s_s_s_rst_variant_proc_select_0) * (Kp_1_Ti_s_s_s_rst_variant_Kp * yi))) + ((Kp_1_Ti_s_s_s_rst_variant_y_min + ((Kp_1_Ti_s_s_s_rst_variant_x - Kp_1_Ti_s_s_s_rst_variant_y_min) * sym.heaviside((Kp_1_Ti_s_s_s_rst_variant_x - Kp_1_Ti_s_s_s_rst_variant_y_min)))) - ((Kp_1_Ti_s_s_s_rst_variant_x - Kp_1_Ti_s_s_s_rst_variant_y_max) * sym.heaviside((Kp_1_Ti_s_s_s_rst_variant_x - Kp_1_Ti_s_s_s_rst_variant_y_max)))))),
            (yo - ((Kp_1_Ti_s_s_s_rst_variant_y_min + ((Kp_1_Ti_s_s_s_rst_variant_PIsum - Kp_1_Ti_s_s_s_rst_variant_y_min) * sym.heaviside((Kp_1_Ti_s_s_s_rst_variant_PIsum - Kp_1_Ti_s_s_s_rst_variant_y_min)))) - ((Kp_1_Ti_s_s_s_rst_variant_PIsum - Kp_1_Ti_s_s_s_rst_variant_y_max) * sym.heaviside((Kp_1_Ti_s_s_s_rst_variant_PIsum - Kp_1_Ti_s_s_s_rst_variant_y_max))))),
        ],
        algebraic_vars=[Kp_1_Ti_s_s_s_rst_variant_PIsum, yo],
        in_vars=[yi, rst],
        out_vars=[yo],
        name='Kp(1/Ti+s)/s (s) _rst (variant)'
    )
    templ.block.diff_vars = [d_Kp_1_Ti_s_s_s_rst_variant_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kp_1_Ti_s_s_s_rst_variant_Kp: vf.add_const(None, name='Kp'),
        Kp_1_Ti_s_s_s_rst_variant_Ti: vf.add_const(None, name='Ti'),
        Kp_1_Ti_s_s_s_rst_variant_Kaw: vf.add_const(None, name='Kaw'),
        Kp_1_Ti_s_s_s_rst_variant_y_max: vf.add_const(None, name='y_max'),
        Kp_1_Ti_s_s_s_rst_variant_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Kp_1_Ti_s_s_s_rst_variant_proc_select_0: vf.add_const(0.0, name=''),
        Kp_1_Ti_s_s_s_rst_variant_proc_lastvalue_1: vf.add_const(0.0, name=''),
        Kp_1_Ti_s_s_s_rst_variant_proc_select_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Kp_1_Ti_s_s_s_rst_variant_x_init: Kp_1_Ti_s_s_s_rst_variant_x,
    }
    templ.block.procedural_logic = [
        sampled_value(output=Kp_1_Ti_s_s_s_rst_variant_proc_select_0, source=(rst > 0.5)),
        lastvalue((yo - Kp_1_Ti_s_s_s_rst_variant_PIsum), output=Kp_1_Ti_s_s_s_rst_variant_proc_lastvalue_1),
        sampled_value(output=Kp_1_Ti_s_s_s_rst_variant_proc_select_2, source=(rst < 0.5)),
        reset(Kp_1_Ti_s_s_s_rst_variant_x, rst, Kp_1_Ti_s_s_s_rst_variant_x_init),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kp_1_ti_s_s_s_rst_variant_452_emt_template(vf=vf, name='Kp(1/Ti+s)/s (s) _rst (variant)__452' if name is None else name)
