# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro
from VeraGridEngine.enumerations import DeviceType

def get_sawtooth_wave_generator_ip_482_emt_template(vf: VarFactory, name: str = 'Sawtooth Wave Generator _ip__482') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Sawtooth_Wave_Generator_ip_f = vf.add_var('Sawtooth Wave Generator _ip__f_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Sawtooth_Wave_Generator_ip_proc_picdro_0 = vf.add_var('Sawtooth Wave Generator _ip__proc_picdro_0_' + name)
    Sawtooth_Wave_Generator_ip_proc_picdro_1 = vf.add_var('Sawtooth Wave Generator _ip__proc_picdro_1_' + name)
    Sawtooth_Wave_Generator_ip_t0 = vf.add_var('Sawtooth Wave Generator _ip_t0_' + name)
    Sawtooth_Wave_Generator_ip_trigger = vf.add_var('Sawtooth Wave Generator _ip_trigger_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Sawtooth_Wave_Generator_ip_trigger - ((sym.Const(0.0) * Sawtooth_Wave_Generator_ip_proc_picdro_0) * Sawtooth_Wave_Generator_ip_proc_picdro_1)),
            (yo - (((glob_time - Sawtooth_Wave_Generator_ip_t0) * Sawtooth_Wave_Generator_ip_f) - (sym.floor((((glob_time - Sawtooth_Wave_Generator_ip_t0) * Sawtooth_Wave_Generator_ip_f) / sym.Const(1.0))) * sym.Const(1.0)))),
        ],
        algebraic_vars=[Sawtooth_Wave_Generator_ip_trigger, yo],
        out_vars=[yo],
        name='Sawtooth Wave Generator _ip'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Sawtooth_Wave_Generator_ip_f: vf.add_const(None, name='f'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Sawtooth_Wave_Generator_ip_proc_picdro_0: vf.add_const(0.0, name=''),
        Sawtooth_Wave_Generator_ip_proc_picdro_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: vf.add_const(0.0, name=''),
        Sawtooth_Wave_Generator_ip_t0: glob_time,
        Sawtooth_Wave_Generator_ip_trigger: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        picdro((sym.sin(((((glob_time - Sawtooth_Wave_Generator_ip_t0) + 0.0001) * 3.141592653589793) * Sawtooth_Wave_Generator_ip_f)) + 0.5), 0.0, 0.0, output=Sawtooth_Wave_Generator_ip_proc_picdro_0),
        picdro((sym.sin(((((glob_time - Sawtooth_Wave_Generator_ip_t0) - 0.0001) * 3.141592653589793) * Sawtooth_Wave_Generator_ip_f)) + 0.5), 0.0, 0.0, output=Sawtooth_Wave_Generator_ip_proc_picdro_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_sawtooth_wave_generator_ip_482_emt_template(vf=vf, name='Sawtooth Wave Generator _ip__482' if name is None else name)
