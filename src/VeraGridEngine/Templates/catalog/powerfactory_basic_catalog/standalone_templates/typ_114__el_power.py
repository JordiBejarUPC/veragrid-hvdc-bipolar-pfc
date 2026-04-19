# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_el_power_114_emt_template(vf: VarFactory, name: str = 'El. Power__114') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    El_Power_IPB = vf.add_var('El. Power__IPB_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    El_Power_proc_select_0 = vf.add_var('El. Power__proc_select_0_' + name)
    cosn = vf.add_var('cosn_' + name)
    pelec = vf.add_var('pelec_' + name)
    pgt = vf.add_var('pgt_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (pelec - ((El_Power_proc_select_0 * pgt) + ((sym.Const(1.0) - El_Power_proc_select_0) * (pgt * cosn)))),
        ],
        algebraic_vars=[pelec],
        in_vars=[pgt, cosn],
        out_vars=[pelec],
        name='El. Power'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        El_Power_IPB: vf.add_const(None, name='IPB'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        El_Power_proc_select_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=El_Power_proc_select_0, source=(El_Power_IPB < 0.5)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_el_power_114_emt_template(vf=vf, name='El. Power__114' if name is None else name)
