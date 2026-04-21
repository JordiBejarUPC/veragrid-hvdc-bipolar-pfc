# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_rpm_p_u_563_emt_template(vf: VarFactory, name: str = 'rpm -> p.u.__563') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    rpm_p_u_Zp = vf.add_var('rpm -> p.u.__Zp_' + name)
    rpm_p_u_freqbase = vf.add_var('rpm -> p.u.__freqbase_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    n = vf.add_var('n_' + name)
    speed = vf.add_var('speed_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (speed - (((n * rpm_p_u_Zp) / rpm_p_u_freqbase) / sym.Const(60.0))),
        ],
        algebraic_vars=[speed],
        in_vars=[n],
        out_vars=[speed],
        name='rpm -> p.u.'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        rpm_p_u_Zp: vf.add_const(None, name='Zp'),
        rpm_p_u_freqbase: vf.add_const(None, name='freqbase'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_rpm_p_u_563_emt_template(vf=vf, name='rpm -> p.u.__563' if name is None else name)
