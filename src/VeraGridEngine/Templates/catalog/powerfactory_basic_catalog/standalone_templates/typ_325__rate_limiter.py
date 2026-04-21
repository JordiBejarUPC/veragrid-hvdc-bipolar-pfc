# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import gradlim_const
from VeraGridEngine.enumerations import DeviceType

def get_rate_limiter_325_emt_template(vf: VarFactory, name: str = 'Rate limiter__325') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Rate_limiter_grd_up = vf.add_var('Rate limiter__grd_up_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Rate_limiter_proc_gradlim_const_0 = vf.add_var('Rate limiter__proc_gradlim_const_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - Rate_limiter_proc_gradlim_const_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Rate limiter'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Rate_limiter_grd_up: vf.add_const(None, name='grd_up'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Rate_limiter_proc_gradlim_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        gradlim_const(yi, (-999999999.0), sym.abs(Rate_limiter_grd_up), output=Rate_limiter_proc_gradlim_const_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_rate_limiter_325_emt_template(vf=vf, name='Rate limiter__325' if name is None else name)
