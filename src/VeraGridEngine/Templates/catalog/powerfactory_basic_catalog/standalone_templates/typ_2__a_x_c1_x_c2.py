# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_a_x_c1_x_c2_2_emt_template(vf: VarFactory, name: str = 'a(x-c1)(x-c2)__2') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    a_x_c1_x_c2_a = vf.add_var('a(x-c1)(x-c2)__a_' + name)
    a_x_c1_x_c2_c1 = vf.add_var('a(x-c1)(x-c2)__c1_' + name)
    a_x_c1_x_c2_c2 = vf.add_var('a(x-c1)(x-c2)__c2_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((a_x_c1_x_c2_a * (yi - a_x_c1_x_c2_c1)) * (yi - a_x_c1_x_c2_c2))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='a(x-c1)(x-c2)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        a_x_c1_x_c2_a: vf.add_const(None, name='a'),
        a_x_c1_x_c2_c1: vf.add_const(None, name='c1'),
        a_x_c1_x_c2_c2: vf.add_const(None, name='c2'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_a_x_c1_x_c2_2_emt_template(vf=vf, name='a(x-c1)(x-c2)__2' if name is None else name)
