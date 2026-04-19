# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_sine_wave_generator_485_emt_template(vf: VarFactory, name: str = 'Sine Wave Generator__485') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Sine_Wave_Generator_a = vf.add_var('Sine Wave Generator__a_' + name)
    Sine_Wave_Generator_f = vf.add_var('Sine Wave Generator__f_' + name)
    Sine_Wave_Generator_phi = vf.add_var('Sine Wave Generator__phi_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Sine_Wave_Generator_deg_to_rad = vf.add_var('Sine Wave Generator_deg_to_rad_' + name)
    Sine_Wave_Generator_t = vf.add_var('Sine Wave Generator_t_' + name)
    Sine_Wave_Generator_two_pi = vf.add_var('Sine Wave Generator_two_pi_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Sine_Wave_Generator_t - glob_time),
            (yo - (Sine_Wave_Generator_a * sym.sin((((Sine_Wave_Generator_two_pi * Sine_Wave_Generator_f) * Sine_Wave_Generator_t) + (Sine_Wave_Generator_phi / Sine_Wave_Generator_deg_to_rad))))),
        ],
        algebraic_vars=[Sine_Wave_Generator_t, yo],
        out_vars=[yo],
        name='Sine Wave Generator'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Sine_Wave_Generator_a: vf.add_const(None, name='a'),
        Sine_Wave_Generator_f: vf.add_const(None, name='f'),
        Sine_Wave_Generator_phi: vf.add_const(None, name='phi'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Sine_Wave_Generator_deg_to_rad: (sym.Const(180.0) / sym.Const(3.141592653589793)),
        Sine_Wave_Generator_two_pi: (sym.Const(2.0) * sym.Const(3.141592653589793)),
        yo: (Sine_Wave_Generator_a * sym.sin((((Sine_Wave_Generator_two_pi * Sine_Wave_Generator_f) * Sine_Wave_Generator_t) + (Sine_Wave_Generator_phi / Sine_Wave_Generator_deg_to_rad)))),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_sine_wave_generator_485_emt_template(vf=vf, name='Sine Wave Generator__485' if name is None else name)
