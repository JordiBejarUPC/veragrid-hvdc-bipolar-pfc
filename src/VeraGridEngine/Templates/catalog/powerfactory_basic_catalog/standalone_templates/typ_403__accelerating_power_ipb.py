# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_accelerating_power_ipb_403_emt_template(vf: VarFactory, name: str = 'Accelerating Power IPB__403') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Accelerating_Power_IPB_IPB = vf.add_var('Accelerating Power IPB__IPB_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Accelerating_Power_IPB_proc_select_0 = vf.add_var('Accelerating Power IPB__proc_select_0_' + name)
    Pa = vf.add_var('Pa_' + name)
    cosn = vf.add_var('cosn_' + name)
    speed = vf.add_var('speed_' + name)
    xme = vf.add_var('xme_' + name)
    xmt = vf.add_var('xmt_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Pa - ((Accelerating_Power_IPB_proc_select_0 * ((xmt - xme) * speed)) + ((sym.Const(1.0) - Accelerating_Power_IPB_proc_select_0) * (((xmt - xme) * cosn) * speed)))),
        ],
        algebraic_vars=[Pa],
        in_vars=[cosn, speed, xmt, xme],
        out_vars=[Pa],
        name='Accelerating Power IPB'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Accelerating_Power_IPB_IPB: vf.add_const(None, name='IPB'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Accelerating_Power_IPB_proc_select_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Accelerating_Power_IPB_proc_select_0, source=(Accelerating_Power_IPB_IPB < 0.5)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_accelerating_power_ipb_403_emt_template(vf=vf, name='Accelerating Power IPB__403' if name is None else name)
