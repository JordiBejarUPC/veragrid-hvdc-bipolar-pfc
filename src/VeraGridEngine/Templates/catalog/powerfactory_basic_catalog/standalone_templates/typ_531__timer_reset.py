# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset
from VeraGridEngine.enumerations import DeviceType

def get_timer_reset_531_emt_template(vf: VarFactory, name: str = 'Timer  _reset__531') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Timer_reset_dt = vf.add_var('Timer  _reset_dt_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    rst = vf.add_var('rst_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - (glob_time - Timer_reset_dt)),
        ],
        algebraic_vars=[yo],
        in_vars=[rst],
        out_vars=[yo],
        name='Timer  _reset'
    )
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Timer_reset_dt: glob_time,
    }
    templ.block.procedural_logic = [
        reset(Timer_reset_dt, rst, glob_time),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_timer_reset_531_emt_template(vf=vf, name='Timer  _reset__531' if name is None else name)
