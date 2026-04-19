# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import gradlim_const
from VeraGridEngine.enumerations import DeviceType

def get_rate_limiter_p_330_emt_template(vf: VarFactory, name: str = 'Rate limiter {p__330') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Rate_limiter_p_grd_down = vf.add_var('Rate limiter {p__grd_down_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Rate_limiter_p_proc_gradlim_const_0 = vf.add_var('Rate limiter {p__proc_gradlim_const_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - Rate_limiter_p_proc_gradlim_const_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Rate limiter {p'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Rate_limiter_p_grd_down: vf.add_const(None, name='grd_down'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Rate_limiter_p_proc_gradlim_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        gradlim_const(yi, (-sym.abs(Rate_limiter_p_grd_down)), 999999999.0, output=Rate_limiter_p_proc_gradlim_const_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_rate_limiter_p_330_emt_template(vf=vf, name='Rate limiter {p__330' if name is None else name)
