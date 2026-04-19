# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset
from VeraGridEngine.enumerations import DeviceType

def get_clock_par_479_emt_template(vf: VarFactory, name: str = 'Clock _par__479') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Clock_par_cFreq = vf.add_var('Clock _par__cFreq_' + name)

    # --- State Variables ---
    Clock_par_x = vf.add_var('Clock _par__x_' + name)

    # --- Algebraic / Shared Variables ---
    Clock_par_clock = vf.add_var('Clock _par_clock_' + name)
    output = vf.add_var('output_' + name)

    # --- Derivative Variables ---
    d_Clock_par_x = vf.add_diff_var('d_Clock _par__x_' + name, base_var=Clock_par_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (sym.Const(2.0) * sym.abs(Clock_par_cFreq)),
        ],
        state_vars=[Clock_par_x],
        algebraic_eqs=[
            (output - Clock_par_clock),
        ],
        algebraic_vars=[output],
        out_vars=[output],
        name='Clock _par'
    )
    templ.block.diff_vars = [d_Clock_par_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Clock_par_cFreq: vf.add_const(None, name='cFreq'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Clock_par_clock: vf.add_const(0.0, name=''),
        Clock_par_x: vf.add_const(0.0, name=''),
        output: Clock_par_clock,
    }
    templ.block.procedural_logic = [
        reset(Clock_par_x, (Clock_par_x - 1.5), 0.0),
        reset(Clock_par_clock, (Clock_par_x - 0.5), 0.0),
        reset(Clock_par_clock, (Clock_par_x - 1.5), 1.0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_clock_par_479_emt_template(vf=vf, name='Clock _par__479' if name is None else name)
