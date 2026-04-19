# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_rpm_rad_s_564_emt_template(vf: VarFactory, name: str = 'rpm -> rad/s__564') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    n = vf.add_var('n_' + name)
    omega = vf.add_var('omega_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (omega - ((n * (sym.Const(2.0) * sym.Const(3.141592653589793))) / sym.Const(60.0))),
        ],
        algebraic_vars=[omega],
        in_vars=[n],
        out_vars=[omega],
        name='rpm -> rad/s'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_rpm_rad_s_564_emt_template(vf=vf, name='rpm -> rad/s__564' if name is None else name)
