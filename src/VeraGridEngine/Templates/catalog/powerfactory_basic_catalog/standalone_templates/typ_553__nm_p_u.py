# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_nm_p_u_553_emt_template(vf: VarFactory, name: str = 'Nm -> p.u.__553') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Nm_p_u_Pel_base = vf.add_var('Nm -> p.u.__Pel_base_' + name)
    Nm_p_u_Zp = vf.add_var('Nm -> p.u.__Zp_' + name)
    Nm_p_u_freqbase = vf.add_var('Nm -> p.u.__freqbase_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    M = vf.add_var('M_' + name)
    m = vf.add_var('m_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (m - ((M * ((sym.Const(2.0) * sym.Const(3.141592653589793)) * Nm_p_u_freqbase)) / ((Nm_p_u_Zp * Nm_p_u_Pel_base) * sym.Const(1000.0)))),
        ],
        algebraic_vars=[m],
        in_vars=[M],
        out_vars=[m],
        name='Nm -> p.u.'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Nm_p_u_freqbase: vf.add_const(None, name='freqbase'),
        Nm_p_u_Zp: vf.add_const(None, name='Zp'),
        Nm_p_u_Pel_base: vf.add_const(None, name='Pel_base'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_nm_p_u_553_emt_template(vf=vf, name='Nm -> p.u.__553' if name is None else name)
