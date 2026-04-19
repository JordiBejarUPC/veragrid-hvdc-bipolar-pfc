# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_rad_s_rpm_562_emt_template(vf: VarFactory, name: str = 'rad/s -> rpm__562') -> EmtModelTemplate:
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
            (n - ((omega / (sym.Const(2.0) * sym.Const(3.141592653589793))) * sym.Const(60.0))),
        ],
        algebraic_vars=[n],
        in_vars=[omega],
        out_vars=[n],
        name='rad/s -> rpm'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_rad_s_rpm_562_emt_template(vf=vf, name='rad/s -> rpm__562' if name is None else name)
