# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_sine_wave_generator_t_t0_484_emt_template(vf: VarFactory, name: str = 'Sine Wave Generator (t>t0)__484') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Sine_Wave_Generator_t_t0_a = vf.add_var('Sine Wave Generator (t>t0)__a_' + name)
    Sine_Wave_Generator_t_t0_f = vf.add_var('Sine Wave Generator (t>t0)__f_' + name)
    Sine_Wave_Generator_t_t0_phi = vf.add_var('Sine Wave Generator (t>t0)__phi_' + name)
    Sine_Wave_Generator_t_t0_t0 = vf.add_var('Sine Wave Generator (t>t0)__t0_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Sine_Wave_Generator_t_t0_proc_select_1 = vf.add_var('Sine Wave Generator (t>t0)__proc_select_1_' + name)
    Sine_Wave_Generator_t_t0_proc_selfix_0 = vf.add_var('Sine Wave Generator (t>t0)__proc_selfix_0_' + name)
    Sine_Wave_Generator_t_t0_deg_to_rad = vf.add_var('Sine Wave Generator (t>t0)_deg_to_rad_' + name)
    Sine_Wave_Generator_t_t0_t = vf.add_var('Sine Wave Generator (t>t0)_t_' + name)
    Sine_Wave_Generator_t_t0_two_pi = vf.add_var('Sine Wave Generator (t>t0)_two_pi_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Sine_Wave_Generator_t_t0_t - glob_time),
            (yo - ((Sine_Wave_Generator_t_t0_proc_select_1 * (Sine_Wave_Generator_t_t0_a * sym.sin((((Sine_Wave_Generator_t_t0_two_pi * Sine_Wave_Generator_t_t0_f) * (Sine_Wave_Generator_t_t0_t - Sine_Wave_Generator_t_t0_t0)) + (Sine_Wave_Generator_t_t0_phi / Sine_Wave_Generator_t_t0_deg_to_rad))))) + ((sym.Const(1.0) - Sine_Wave_Generator_t_t0_proc_select_1) * sym.Const(0.0)))),
        ],
        algebraic_vars=[Sine_Wave_Generator_t_t0_t, yo],
        out_vars=[yo],
        name='Sine Wave Generator (t>t0)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Sine_Wave_Generator_t_t0_a: vf.add_const(None, name='a'),
        Sine_Wave_Generator_t_t0_f: vf.add_const(None, name='f'),
        Sine_Wave_Generator_t_t0_phi: vf.add_const(None, name='phi'),
        Sine_Wave_Generator_t_t0_t0: vf.add_const(None, name='t0'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Sine_Wave_Generator_t_t0_proc_selfix_0: vf.add_const(0.0, name=''),
        Sine_Wave_Generator_t_t0_proc_select_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Sine_Wave_Generator_t_t0_deg_to_rad: (sym.Const(180.0) / sym.Const(3.141592653589793)),
        Sine_Wave_Generator_t_t0_two_pi: (sym.Const(2.0) * sym.Const(3.141592653589793)),
        yo: ((Sine_Wave_Generator_t_t0_proc_selfix_0 * (Sine_Wave_Generator_t_t0_a * sym.sin((((Sine_Wave_Generator_t_t0_two_pi * Sine_Wave_Generator_t_t0_f) * (Sine_Wave_Generator_t_t0_t - Sine_Wave_Generator_t_t0_t0)) + (Sine_Wave_Generator_t_t0_phi / Sine_Wave_Generator_t_t0_deg_to_rad))))) + ((sym.Const(1.0) - Sine_Wave_Generator_t_t0_proc_selfix_0) * sym.Const(0.0))),
    }
    templ.block.procedural_logic = [
        selfix((Sine_Wave_Generator_t_t0_t >= Sine_Wave_Generator_t_t0_t0), output=Sine_Wave_Generator_t_t0_proc_selfix_0),
        sampled_value(output=Sine_Wave_Generator_t_t0_proc_select_1, source=(Sine_Wave_Generator_t_t0_t >= Sine_Wave_Generator_t_t0_t0)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_sine_wave_generator_t_t0_484_emt_template(vf=vf, name='Sine Wave Generator (t>t0)__484' if name is None else name)
