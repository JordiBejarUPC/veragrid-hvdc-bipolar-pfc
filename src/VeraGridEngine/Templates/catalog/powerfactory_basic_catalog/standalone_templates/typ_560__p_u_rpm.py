# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_p_u_rpm_560_emt_template(vf: VarFactory, name: str = 'p.u. -> rpm__560') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    p_u_rpm_Zp = vf.add_var('p.u. -> rpm__Zp_' + name)
    p_u_rpm_freqbase = vf.add_var('p.u. -> rpm__freqbase_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    n = vf.add_var('n_' + name)
    speed = vf.add_var('speed_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (n - (((speed * p_u_rpm_freqbase) * sym.Const(60.0)) / p_u_rpm_Zp)),
        ],
        algebraic_vars=[n],
        in_vars=[speed],
        out_vars=[n],
        name='p.u. -> rpm'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        p_u_rpm_Zp: vf.add_const(None, name='Zp'),
        p_u_rpm_freqbase: vf.add_const(None, name='freqbase'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_p_u_rpm_560_emt_template(vf=vf, name='p.u. -> rpm__560' if name is None else name)
