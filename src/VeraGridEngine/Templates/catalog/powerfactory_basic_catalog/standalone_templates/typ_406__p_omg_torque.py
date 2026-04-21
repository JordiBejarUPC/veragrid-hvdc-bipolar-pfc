# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_p_omg_torque_406_emt_template(vf: VarFactory, name: str = 'P/omg -> Torque__406') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Power = vf.add_var('Power_' + name)
    Torque = vf.add_var('Torque_' + name)
    omega = vf.add_var('omega_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Torque - ((Power / omega) * sym.Const(1000.0))),
        ],
        algebraic_vars=[Torque],
        in_vars=[Power, omega],
        out_vars=[Torque],
        name='P/omg -> Torque'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_p_omg_torque_406_emt_template(vf=vf, name='P/omg -> Torque__406' if name is None else name)
