# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_limit_upper_324_emt_template(vf: VarFactory, name: str = 'Limit upper__324') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Limit_upper_y_max = vf.add_var('Limit upper__y_max_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((yi * sym.heaviside((Limit_upper_y_max - yi))) + (Limit_upper_y_max * (sym.Const(1) - sym.heaviside((Limit_upper_y_max - yi)))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Limit upper'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Limit_upper_y_max: vf.add_const(None, name='y_max'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_limit_upper_324_emt_template(vf=vf, name='Limit upper__324' if name is None else name)
