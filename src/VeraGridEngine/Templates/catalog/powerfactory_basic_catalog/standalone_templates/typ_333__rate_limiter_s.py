# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue
from VeraGridEngine.enumerations import DeviceType

def get_rate_limiter_s_333_emt_template(vf: VarFactory, name: str = 'Rate limiter {s__333') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Rate_limiter_s_proc_lastvalue_0 = vf.add_var('Rate limiter {s__proc_lastvalue_0_' + name)
    Rate_limiter_s_proc_lastvalue_1 = vf.add_var('Rate limiter {s__proc_lastvalue_1_' + name)
    Rate_limiter_s_dt = vf.add_var('Rate limiter {s_dt_' + name)
    Rate_limiter_s_dy = vf.add_var('Rate limiter {s_dy_' + name)
    Rate_limiter_s_t0 = vf.add_var('Rate limiter {s_t0_' + name)
    Rate_limiter_s_yi0 = vf.add_var('Rate limiter {s_yi0_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    grd_down = vf.add_var('grd_down_' + name)
    grd_up = vf.add_var('grd_up_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Rate_limiter_s_t0 - Rate_limiter_s_proc_lastvalue_0),
            (Rate_limiter_s_yi0 - Rate_limiter_s_proc_lastvalue_1),
            (Rate_limiter_s_dt - (glob_time - Rate_limiter_s_t0)),
            (Rate_limiter_s_dy - (((-sym.abs(grd_down)) + ((((yi - Rate_limiter_s_yi0) / ((Rate_limiter_s_dt * sym.heaviside((Rate_limiter_s_dt - sym.Const(1e-12)))) + (sym.Const(1e-12) * (sym.Const(1) - sym.heaviside((Rate_limiter_s_dt - sym.Const(1e-12))))))) - (-sym.abs(grd_down))) * sym.heaviside((((yi - Rate_limiter_s_yi0) / ((Rate_limiter_s_dt * sym.heaviside((Rate_limiter_s_dt - sym.Const(1e-12)))) + (sym.Const(1e-12) * (sym.Const(1) - sym.heaviside((Rate_limiter_s_dt - sym.Const(1e-12))))))) - (-sym.abs(grd_down)))))) - ((((yi - Rate_limiter_s_yi0) / ((Rate_limiter_s_dt * sym.heaviside((Rate_limiter_s_dt - sym.Const(1e-12)))) + (sym.Const(1e-12) * (sym.Const(1) - sym.heaviside((Rate_limiter_s_dt - sym.Const(1e-12))))))) - sym.abs(grd_up)) * sym.heaviside((((yi - Rate_limiter_s_yi0) / ((Rate_limiter_s_dt * sym.heaviside((Rate_limiter_s_dt - sym.Const(1e-12)))) + (sym.Const(1e-12) * (sym.Const(1) - sym.heaviside((Rate_limiter_s_dt - sym.Const(1e-12))))))) - sym.abs(grd_up)))))),
            (yo - ((Rate_limiter_s_dy * Rate_limiter_s_dt) + Rate_limiter_s_yi0)),
        ],
        algebraic_vars=[Rate_limiter_s_t0, Rate_limiter_s_yi0, Rate_limiter_s_dt, Rate_limiter_s_dy, yo],
        in_vars=[yi, grd_up, grd_down],
        out_vars=[yo],
        name='Rate limiter {s'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Rate_limiter_s_proc_lastvalue_0: vf.add_const(0.0, name=''),
        Rate_limiter_s_proc_lastvalue_1: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Rate_limiter_s_dt: vf.add_const(0.001, name=''),
        Rate_limiter_s_dy: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        lastvalue(glob_time, output=Rate_limiter_s_proc_lastvalue_0),
        lastvalue(yo, output=Rate_limiter_s_proc_lastvalue_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_rate_limiter_s_333_emt_template(vf=vf, name='Rate limiter {s__333' if name is None else name)
