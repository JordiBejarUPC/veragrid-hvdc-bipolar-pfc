# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_clock_t_0_sig_476_emt_template(vf: VarFactory, name: str = 'Clock (t>0) _sig__476') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---
    Clock_t_0_sig_x = vf.add_var('Clock (t>0) _sig__x_' + name)

    # --- Algebraic / Shared Variables ---
    Clock_t_0_sig_proc_select_0 = vf.add_var('Clock (t>0) _sig__proc_select_0_' + name)
    Clock_t_0_sig_clock = vf.add_var('Clock (t>0) _sig_clock_' + name)
    extfrq = vf.add_var('extfrq_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    output = vf.add_var('output_' + name)

    # --- Derivative Variables ---
    d_Clock_t_0_sig_x = vf.add_diff_var('d_Clock (t>0) _sig__x_' + name, base_var=Clock_t_0_sig_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Clock_t_0_sig_proc_select_0 * (sym.Const(2.0) * sym.abs(extfrq))) + ((sym.Const(1.0) - Clock_t_0_sig_proc_select_0) * sym.Const(0.0))),
        ],
        state_vars=[Clock_t_0_sig_x],
        algebraic_eqs=[
            (output - Clock_t_0_sig_clock),
        ],
        algebraic_vars=[output],
        in_vars=[extfrq],
        out_vars=[output],
        name='Clock (t>0) _sig'
    )
    templ.block.diff_vars = [d_Clock_t_0_sig_x]
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Clock_t_0_sig_proc_select_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Clock_t_0_sig_clock: vf.add_const(0.0, name=''),
        Clock_t_0_sig_x: vf.add_const(0.0, name=''),
        output: Clock_t_0_sig_clock,
    }
    templ.block.procedural_logic = [
        sampled_value(output=Clock_t_0_sig_proc_select_0, source=(glob_time > 0.0)),
        reset(Clock_t_0_sig_x, (Clock_t_0_sig_x - 1.5), 0.0),
        reset(Clock_t_0_sig_clock, (Clock_t_0_sig_x - 0.5), 0.0),
        reset(Clock_t_0_sig_clock, (Clock_t_0_sig_x - 1.5), 1.0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_clock_t_0_sig_476_emt_template(vf=vf, name='Clock (t>0) _sig__476' if name is None else name)
