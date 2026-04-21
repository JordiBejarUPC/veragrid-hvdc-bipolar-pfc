# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_triangle_wave_generator_489_emt_template(vf: VarFactory, name: str = 'Triangle Wave Generator__489') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Triangle_Wave_Generator_f = vf.add_var('Triangle Wave Generator__f_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Triangle_Wave_Generator_toffset = vf.add_var('Triangle Wave Generator_toffset_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - sym.abs((((((glob_time - Triangle_Wave_Generator_toffset) * Triangle_Wave_Generator_f) * sym.Const(2.0)) - (sym.floor(((((glob_time - Triangle_Wave_Generator_toffset) * Triangle_Wave_Generator_f) * sym.Const(2.0)) / sym.Const(2.0))) * sym.Const(2.0))) - sym.Const(1.0)))),
        ],
        algebraic_vars=[yo],
        out_vars=[yo],
        name='Triangle Wave Generator'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Triangle_Wave_Generator_f: vf.add_const(None, name='f'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: vf.add_const(0.0, name=''),
        Triangle_Wave_Generator_toffset: (glob_time - (sym.Const(1.0) / (sym.Const(2.0) * Triangle_Wave_Generator_f))),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_triangle_wave_generator_489_emt_template(vf=vf, name='Triangle Wave Generator__489' if name is None else name)
