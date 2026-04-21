# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_ax_2_bx_c_3_emt_template(vf: VarFactory, name: str = 'ax^2 + bx + c__3') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    ax_2_bx_c_a = vf.add_var('ax^2 + bx + c__a_' + name)
    ax_2_bx_c_b = vf.add_var('ax^2 + bx + c__b_' + name)
    ax_2_bx_c_c = vf.add_var('ax^2 + bx + c__c_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - (((ax_2_bx_c_a * (yi * yi)) + (ax_2_bx_c_b * yi)) + ax_2_bx_c_c)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='ax^2 + bx + c'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        ax_2_bx_c_a: vf.add_const(None, name='a'),
        ax_2_bx_c_b: vf.add_const(None, name='b'),
        ax_2_bx_c_c: vf.add_const(None, name='c'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_ax_2_bx_c_3_emt_template(vf=vf, name='ax^2 + bx + c__3' if name is None else name)
