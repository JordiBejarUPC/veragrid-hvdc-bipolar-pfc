# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset
from VeraGridEngine.enumerations import DeviceType

def get_clock_sig_480_emt_template(vf: VarFactory, name: str = 'Clock _sig__480') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---
    Clock_sig_x = vf.add_var('Clock _sig__x_' + name)

    # --- Algebraic / Shared Variables ---
    Clock_sig_clock = vf.add_var('Clock _sig_clock_' + name)
    extfrq = vf.add_var('extfrq_' + name)
    output = vf.add_var('output_' + name)

    # --- Derivative Variables ---
    d_Clock_sig_x = vf.add_diff_var('d_Clock _sig__x_' + name, base_var=Clock_sig_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (sym.Const(2.0) * sym.abs(extfrq)),
        ],
        state_vars=[Clock_sig_x],
        algebraic_eqs=[
            (output - Clock_sig_clock),
        ],
        algebraic_vars=[output],
        in_vars=[extfrq],
        out_vars=[output],
        name='Clock _sig'
    )
    templ.block.diff_vars = [d_Clock_sig_x]
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Clock_sig_clock: vf.add_const(0.0, name=''),
        Clock_sig_x: vf.add_const(0.0, name=''),
        output: Clock_sig_clock,
    }
    templ.block.procedural_logic = [
        reset(Clock_sig_x, (Clock_sig_x - 1.5), 0.0),
        reset(Clock_sig_clock, (Clock_sig_x - 0.5), 0.0),
        reset(Clock_sig_clock, (Clock_sig_x - 1.5), 1.0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_clock_sig_480_emt_template(vf=vf, name='Clock _sig__480' if name is None else name)
