# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro
from VeraGridEngine.enumerations import DeviceType

def get_square_wave_generator_ip_487_emt_template(vf: VarFactory, name: str = 'Square Wave Generator_ip__487') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Square_Wave_Generator_ip_f = vf.add_var('Square Wave Generator_ip__f_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Square_Wave_Generator_ip_proc_picdro_0 = vf.add_var('Square Wave Generator_ip__proc_picdro_0_' + name)
    Square_Wave_Generator_ip_t0 = vf.add_var('Square Wave Generator_ip_t0_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - Square_Wave_Generator_ip_proc_picdro_0),
        ],
        algebraic_vars=[yo],
        out_vars=[yo],
        name='Square Wave Generator_ip'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Square_Wave_Generator_ip_f: vf.add_const(None, name='f'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Square_Wave_Generator_ip_proc_picdro_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: vf.add_const(0.0, name=''),
        Square_Wave_Generator_ip_t0: glob_time,
    }
    templ.block.procedural_logic = [
        picdro((((glob_time - Square_Wave_Generator_ip_t0) * Square_Wave_Generator_ip_f) - (sym.floor((((glob_time - Square_Wave_Generator_ip_t0) * Square_Wave_Generator_ip_f) / 1.0)) * 1.0)), 0.0, 0.0, output=Square_Wave_Generator_ip_proc_picdro_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_square_wave_generator_ip_487_emt_template(vf=vf, name='Square Wave Generator_ip__487' if name is None else name)
