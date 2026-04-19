# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import lastvalue, reset
from VeraGridEngine.enumerations import DeviceType

def get_edge_detector_352_emt_template(vf: VarFactory, name: str = 'Edge detector__352') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Edge_detector_ACTIVATE_ON_FALL = vf.add_var('Edge detector__ACTIVATE_ON_FALL_' + name)
    Edge_detector_ACTIVATE_ON_RISE = vf.add_var('Edge detector__ACTIVATE_ON_RISE_' + name)
    Edge_detector_THRESHOLD = vf.add_var('Edge detector__THRESHOLD_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Edge_detector_proc_lastvalue_0 = vf.add_var('Edge detector__proc_lastvalue_0_' + name)
    Edge_detector_internal_variable = vf.add_var('Edge detector_internal_variable_' + name)
    Edge_detector_yi1 = vf.add_var('Edge detector_yi1_' + name)
    Edge_detector_yi2 = vf.add_var('Edge detector_yi2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - Edge_detector_internal_variable),
            (Edge_detector_yi1 - ((yi - Edge_detector_THRESHOLD) + sym.Const(0.5))),
            (Edge_detector_yi2 - (((-yi) + Edge_detector_THRESHOLD) + sym.Const(0.5))),
        ],
        algebraic_vars=[yo, Edge_detector_yi1, Edge_detector_yi2],
        in_vars=[yi],
        out_vars=[yo],
        name='Edge detector'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Edge_detector_ACTIVATE_ON_RISE: vf.add_const(None, name='ACTIVATE_ON_RISE'),
        Edge_detector_ACTIVATE_ON_FALL: vf.add_const(None, name='ACTIVATE_ON_FALL'),
        Edge_detector_THRESHOLD: vf.add_const(None, name='THRESHOLD'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Edge_detector_proc_lastvalue_0: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Edge_detector_internal_variable: vf.add_const(0.0, name=''),
        yo: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        reset(Edge_detector_internal_variable, (Edge_detector_yi1 * sym.heaviside(((Edge_detector_ACTIVATE_ON_RISE - 0.5) - 1e-06))), 1.0),
        reset(Edge_detector_internal_variable, (Edge_detector_yi2 * sym.heaviside(((Edge_detector_ACTIVATE_ON_FALL - 0.5) - 1e-06))), 1.0),
        lastvalue(Edge_detector_internal_variable, output=Edge_detector_proc_lastvalue_0),
        reset(Edge_detector_internal_variable, Edge_detector_proc_lastvalue_0, 0.0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_edge_detector_352_emt_template(vf=vf, name='Edge detector__352' if name is None else name)
