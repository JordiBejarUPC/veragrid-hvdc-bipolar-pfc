# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import movingavg
from VeraGridEngine.enumerations import DeviceType

def get_movingavg_77_emt_template(vf: VarFactory, name: str = 'movingavg__77') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    movingavg_Tdel = vf.add_var('movingavg__Tdel_' + name)
    movingavg_Tlength = vf.add_var('movingavg__Tlength_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    movingavg_proc_movingavg_0 = vf.add_var('movingavg__proc_movingavg_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - movingavg_proc_movingavg_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='movingavg'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        movingavg_Tdel: vf.add_const(None, name='Tdel'),
        movingavg_Tlength: vf.add_const(None, name='Tlength'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        movingavg_proc_movingavg_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        movingavg(yi, movingavg_Tdel, movingavg_Tlength, output=movingavg_proc_movingavg_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_movingavg_77_emt_template(vf=vf, name='movingavg__77' if name is None else name)
