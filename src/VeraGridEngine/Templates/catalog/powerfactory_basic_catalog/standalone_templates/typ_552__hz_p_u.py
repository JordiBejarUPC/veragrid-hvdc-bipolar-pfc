# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_hz_p_u_552_emt_template(vf: VarFactory, name: str = 'Hz -> p.u.__552') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Hz_p_u_freqbase = vf.add_var('Hz -> p.u.__freqbase_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Freq = vf.add_var('Freq_' + name)
    fpu = vf.add_var('fpu_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (fpu - (Freq / Hz_p_u_freqbase)),
        ],
        algebraic_vars=[fpu],
        in_vars=[Freq],
        out_vars=[fpu],
        name='Hz -> p.u.'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Hz_p_u_freqbase: vf.add_const(None, name='freqbase'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_hz_p_u_552_emt_template(vf=vf, name='Hz -> p.u.__552' if name is None else name)
