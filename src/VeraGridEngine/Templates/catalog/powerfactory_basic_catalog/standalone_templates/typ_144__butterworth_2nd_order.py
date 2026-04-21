# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_butterworth_2nd_order_144_emt_template(vf: VarFactory, name: str = 'Butterworth 2nd order__144') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Butterworth_2nd_order_wc = vf.add_var('Butterworth 2nd order__wc_' + name)

    # --- State Variables ---
    Butterworth_2nd_order_x1 = vf.add_var('Butterworth 2nd order__x1_' + name)
    Butterworth_2nd_order_x2 = vf.add_var('Butterworth 2nd order__x2_' + name)

    # --- Algebraic / Shared Variables ---
    Butterworth_2nd_order_wc_2 = vf.add_var('Butterworth 2nd order_wc_2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Butterworth_2nd_order_x1 = vf.add_diff_var('d_Butterworth 2nd order__x1_' + name, base_var=Butterworth_2nd_order_x1)
    d_Butterworth_2nd_order_x2 = vf.add_diff_var('d_Butterworth 2nd order__x2_' + name, base_var=Butterworth_2nd_order_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            Butterworth_2nd_order_x2,
            ((((-Butterworth_2nd_order_wc_2) * Butterworth_2nd_order_x1) - ((sym.Const(1.414) * Butterworth_2nd_order_wc) * Butterworth_2nd_order_x2)) + yi),
        ],
        state_vars=[Butterworth_2nd_order_x1, Butterworth_2nd_order_x2],
        algebraic_eqs=[
            (yo - (Butterworth_2nd_order_wc_2 * Butterworth_2nd_order_x1)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Butterworth 2nd order'
    )
    templ.block.diff_vars = [d_Butterworth_2nd_order_x1, d_Butterworth_2nd_order_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Butterworth_2nd_order_wc: vf.add_const(None, name='wc'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Butterworth_2nd_order_wc_2: (Butterworth_2nd_order_wc * Butterworth_2nd_order_wc),
        Butterworth_2nd_order_x1: (yi / Butterworth_2nd_order_wc_2),
        Butterworth_2nd_order_x2: vf.add_const(0.0, name=''),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_butterworth_2nd_order_144_emt_template(vf=vf, name='Butterworth 2nd order__144' if name is None else name)
