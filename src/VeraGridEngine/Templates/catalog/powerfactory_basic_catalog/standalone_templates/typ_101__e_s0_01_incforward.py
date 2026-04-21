# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import delay
from VeraGridEngine.enumerations import DeviceType

def get_e_s0_01_incforward_101_emt_template(vf: VarFactory, name: str = 'e^-s0.01 _incforward__101') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    e_s0_01_incforward_proc_delay_0 = vf.add_var('e^-s0.01 _incforward__proc_delay_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - e_s0_01_incforward_proc_delay_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='e^-s0.01 _incforward'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        e_s0_01_incforward_proc_delay_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: yi,
    }
    templ.block.procedural_logic = [
        delay(yi, 0.01, output=e_s0_01_incforward_proc_delay_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_e_s0_01_incforward_101_emt_template(vf=vf, name='e^-s0.01 _incforward__101' if name is None else name)
