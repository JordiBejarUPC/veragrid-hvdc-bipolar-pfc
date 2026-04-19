# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import flipflop, lastvalue, reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_monostable_353_emt_template(vf: VarFactory, name: str = 'Monostable__353') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Monostable_T = vf.add_var('Monostable__T_' + name)

    # --- State Variables ---
    Monostable_x = vf.add_var('Monostable__x_' + name)

    # --- Algebraic / Shared Variables ---
    Monostable_proc_flipflop_1 = vf.add_var('Monostable__proc_flipflop_1_' + name)
    Monostable_proc_lastvalue_0 = vf.add_var('Monostable__proc_lastvalue_0_' + name)
    Monostable_proc_select_2 = vf.add_var('Monostable__proc_select_2_' + name)
    Monostable_rst = vf.add_var('Monostable_rst_' + name)
    Monostable_set = vf.add_var('Monostable_set_' + name)
    Monostable_t0 = vf.add_var('Monostable_t0_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Monostable_x = vf.add_diff_var('d_Monostable__x_' + name, base_var=Monostable_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Monostable_proc_select_2 * sym.Const(1.0)) + ((sym.Const(1.0) - Monostable_proc_select_2) * sym.Const(0.0))),
        ],
        state_vars=[Monostable_x],
        algebraic_eqs=[
            (Monostable_set - (sym.heaviside(((sym.Const(0.5) - Monostable_proc_lastvalue_0) - sym.Const(1e-06))) * sym.heaviside(((yi - sym.Const(0.5)) + sym.Const(1e-06))))),
            (Monostable_rst - sym.heaviside((((Monostable_x - Monostable_T) - sym.Const(0.0)) - sym.Const(1e-06)))),
            (yo - Monostable_proc_flipflop_1),
        ],
        algebraic_vars=[Monostable_set, Monostable_rst, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Monostable'
    )
    templ.block.diff_vars = [d_Monostable_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Monostable_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Monostable_proc_lastvalue_0: vf.add_const(0.0, name=''),
        Monostable_proc_flipflop_1: vf.add_const(0.0, name=''),
        Monostable_proc_select_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Monostable_t0: glob_time,
        Monostable_set: vf.add_const(0.0, name=''),
        Monostable_rst: vf.add_const(0.0, name=''),
        Monostable_x: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        lastvalue(yi, output=Monostable_proc_lastvalue_0),
        flipflop(Monostable_set, Monostable_rst, output=Monostable_proc_flipflop_1),
        sampled_value(output=Monostable_proc_select_2, source=(sym.heaviside(((glob_time - (Monostable_t0 + 0.001)) - 1e-06)) * sym.heaviside(((yo - 0.5) - 1e-06)))),
        reset(Monostable_x, ((Monostable_x - Monostable_T) + 0.500001), 0.0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_monostable_353_emt_template(vf=vf, name='Monostable__353' if name is None else name)
