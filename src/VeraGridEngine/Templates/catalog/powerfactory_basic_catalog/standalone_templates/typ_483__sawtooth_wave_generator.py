# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_sawtooth_wave_generator_483_emt_template(vf: VarFactory, name: str = 'Sawtooth Wave Generator__483') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Sawtooth_Wave_Generator_f = vf.add_var('Sawtooth Wave Generator__f_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Sawtooth_Wave_Generator_t0 = vf.add_var('Sawtooth Wave Generator_t0_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - (((glob_time - Sawtooth_Wave_Generator_t0) * Sawtooth_Wave_Generator_f) - (sym.floor((((glob_time - Sawtooth_Wave_Generator_t0) * Sawtooth_Wave_Generator_f) / sym.Const(1.0))) * sym.Const(1.0)))),
        ],
        algebraic_vars=[yo],
        out_vars=[yo],
        name='Sawtooth Wave Generator'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Sawtooth_Wave_Generator_f: vf.add_const(None, name='f'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: vf.add_const(0.0, name=''),
        Sawtooth_Wave_Generator_t0: glob_time,
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_sawtooth_wave_generator_483_emt_template(vf=vf, name='Sawtooth Wave Generator__483' if name is None else name)
