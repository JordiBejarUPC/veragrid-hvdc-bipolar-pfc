# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import flipflop, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_bistable_351_emt_template(vf: VarFactory, name: str = 'Bistable__351') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Bistable_PRIO_SET = vf.add_var('Bistable__PRIO_SET_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Bistable_proc_flipflop_0 = vf.add_var('Bistable__proc_flipflop_0_' + name)
    Bistable_proc_select_1 = vf.add_var('Bistable__proc_select_1_' + name)
    Bistable_proc_select_2 = vf.add_var('Bistable__proc_select_2_' + name)
    Bistable_xSR = vf.add_var('Bistable_xSR_' + name)
    Q = vf.add_var('Q_' + name)
    R = vf.add_var('R_' + name)
    S = vf.add_var('S_' + name)
    not_Q = vf.add_var('not_Q_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Bistable_xSR - Bistable_proc_flipflop_0),
            (Q - ((Bistable_proc_select_2 * ((Bistable_proc_select_1 * sym.Const(0.0)) + ((sym.Const(1.0) - Bistable_proc_select_1) * sym.Const(1.0)))) + ((sym.Const(1.0) - Bistable_proc_select_2) * Bistable_xSR))),
            (not_Q - (sym.Const(1.0) - Q)),
        ],
        algebraic_vars=[Bistable_xSR, Q, not_Q],
        in_vars=[S, R],
        out_vars=[Q, not_Q],
        name='Bistable'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Bistable_PRIO_SET: vf.add_const(None, name='PRIO_SET'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Bistable_proc_flipflop_0: vf.add_const(0.0, name=''),
        Bistable_proc_select_1: vf.add_const(0.0, name=''),
        Bistable_proc_select_2: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        flipflop(S, R, output=Bistable_proc_flipflop_0),
        sampled_value(output=Bistable_proc_select_1, source=(Bistable_PRIO_SET < 0.5)),
        sampled_value(output=Bistable_proc_select_2, source=(S * R)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_bistable_351_emt_template(vf=vf, name='Bistable__351' if name is None else name)
