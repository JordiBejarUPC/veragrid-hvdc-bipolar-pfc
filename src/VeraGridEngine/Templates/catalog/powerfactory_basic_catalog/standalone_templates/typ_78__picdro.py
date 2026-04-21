# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import picdro
from VeraGridEngine.enumerations import DeviceType

def get_picdro_78_emt_template(vf: VarFactory, name: str = 'picdro__78') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Tdrop = vf.add_var('Tdrop_' + name)
    Tpick = vf.add_var('Tpick_' + name)
    condition = vf.add_var('condition_' + name)
    picdro_proc_picdro_0 = vf.add_var('picdro__proc_picdro_0_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - picdro_proc_picdro_0),
        ],
        algebraic_vars=[yo],
        in_vars=[condition, Tpick, Tdrop],
        out_vars=[yo],
        name='picdro'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        picdro_proc_picdro_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        picdro(condition, Tpick, Tdrop, output=picdro_proc_picdro_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_picdro_78_emt_template(vf=vf, name='picdro__78' if name is None else name)
