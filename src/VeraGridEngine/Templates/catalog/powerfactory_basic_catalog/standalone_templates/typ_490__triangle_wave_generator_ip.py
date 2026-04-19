# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro
from VeraGridEngine.enumerations import DeviceType

def get_triangle_wave_generator_ip_490_emt_template(vf: VarFactory, name: str = 'Triangle Wave Generator_ip__490') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Triangle_Wave_Generator_ip_f = vf.add_var('Triangle Wave Generator_ip__f_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Triangle_Wave_Generator_ip_proc_picdro_0 = vf.add_var('Triangle Wave Generator_ip__proc_picdro_0_' + name)
    Triangle_Wave_Generator_ip_toffset = vf.add_var('Triangle Wave Generator_ip_toffset_' + name)
    Triangle_Wave_Generator_ip_trigger = vf.add_var('Triangle Wave Generator_ip_trigger_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Triangle_Wave_Generator_ip_trigger - (sym.Const(0.0) * Triangle_Wave_Generator_ip_proc_picdro_0)),
            (yo - sym.abs((((((glob_time - Triangle_Wave_Generator_ip_toffset) * Triangle_Wave_Generator_ip_f) * sym.Const(2.0)) - (sym.floor(((((glob_time - Triangle_Wave_Generator_ip_toffset) * Triangle_Wave_Generator_ip_f) * sym.Const(2.0)) / sym.Const(2.0))) * sym.Const(2.0))) - sym.Const(1.0)))),
        ],
        algebraic_vars=[Triangle_Wave_Generator_ip_trigger, yo],
        out_vars=[yo],
        name='Triangle Wave Generator_ip'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Triangle_Wave_Generator_ip_f: vf.add_const(None, name='f'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Triangle_Wave_Generator_ip_proc_picdro_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: vf.add_const(0.0, name=''),
        Triangle_Wave_Generator_ip_toffset: (glob_time - (sym.Const(1.0) / (sym.Const(2.0) * Triangle_Wave_Generator_ip_f))),
        Triangle_Wave_Generator_ip_trigger: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        picdro((sym.cos((((((glob_time - Triangle_Wave_Generator_ip_toffset) * 2.0) * 3.141592653589793) * 2.0) * Triangle_Wave_Generator_ip_f)) + 0.5), 0.0, 0.0, output=Triangle_Wave_Generator_ip_proc_picdro_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_triangle_wave_generator_ip_490_emt_template(vf=vf, name='Triangle Wave Generator_ip__490' if name is None else name)
