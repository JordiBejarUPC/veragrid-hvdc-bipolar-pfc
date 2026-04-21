# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_p_u_hz_557_emt_template(vf: VarFactory, name: str = 'p.u. -> Hz__557') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    p_u_Hz_freqbase = vf.add_var('p.u. -> Hz__freqbase_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Freq = vf.add_var('Freq_' + name)
    fpu = vf.add_var('fpu_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Freq - (fpu * p_u_Hz_freqbase)),
        ],
        algebraic_vars=[Freq],
        in_vars=[fpu],
        out_vars=[Freq],
        name='p.u. -> Hz'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        p_u_Hz_freqbase: vf.add_const(None, name='freqbase'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_p_u_hz_557_emt_template(vf=vf, name='p.u. -> Hz__557' if name is None else name)
