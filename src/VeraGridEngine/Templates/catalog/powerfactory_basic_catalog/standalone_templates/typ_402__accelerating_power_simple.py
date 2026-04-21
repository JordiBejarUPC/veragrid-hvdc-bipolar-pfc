# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_accelerating_power_simple_402_emt_template(vf: VarFactory, name: str = 'Accelerating Power (simple)__402') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    speed = vf.add_var('speed_' + name)
    xme = vf.add_var('xme_' + name)
    xmt = vf.add_var('xmt_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((((xmt - xme) * sym.Const(2.0)) * sym.Const(3.141592653589793)) * speed)),
        ],
        algebraic_vars=[yo],
        in_vars=[speed, xmt, xme],
        out_vars=[yo],
        name='Accelerating Power (simple)'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_accelerating_power_simple_402_emt_template(vf=vf, name='Accelerating Power (simple)__402' if name is None else name)
