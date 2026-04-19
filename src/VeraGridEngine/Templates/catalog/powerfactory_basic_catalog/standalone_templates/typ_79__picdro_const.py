# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro
from VeraGridEngine.enumerations import DeviceType

def get_picdro_const_79_emt_template(vf: VarFactory, name: str = 'picdro_const__79') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    picdro_const_Tdrop = vf.add_var('picdro_const__Tdrop_' + name)
    picdro_const_Tpick = vf.add_var('picdro_const__Tpick_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    condition = vf.add_var('condition_' + name)
    picdro_const_proc_picdro_const_0 = vf.add_var('picdro_const__proc_picdro_const_0_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - picdro_const_proc_picdro_const_0),
        ],
        algebraic_vars=[yo],
        in_vars=[condition],
        out_vars=[yo],
        name='picdro_const'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        picdro_const_Tpick: vf.add_const(None, name='Tpick'),
        picdro_const_Tdrop: vf.add_const(None, name='Tdrop'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        picdro_const_proc_picdro_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        picdro(condition, picdro_const_Tpick, picdro_const_Tdrop, output=picdro_const_proc_picdro_const_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_picdro_const_79_emt_template(vf=vf, name='picdro_const__79' if name is None else name)
