# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_max3_362_emt_template(vf: VarFactory, name: str = 'MAX3__362') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yi3 = vf.add_var('yi3_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((((yi1 * sym.heaviside((yi1 - yi2))) + (yi2 * (sym.Const(1) - sym.heaviside((yi1 - yi2))))) * sym.heaviside((((yi1 * sym.heaviside((yi1 - yi2))) + (yi2 * (sym.Const(1) - sym.heaviside((yi1 - yi2))))) - yi3))) + (yi3 * (sym.Const(1) - sym.heaviside((((yi1 * sym.heaviside((yi1 - yi2))) + (yi2 * (sym.Const(1) - sym.heaviside((yi1 - yi2))))) - yi3)))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi1, yi2, yi3],
        out_vars=[yo],
        name='MAX3'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_max3_362_emt_template(vf=vf, name='MAX3__362' if name is None else name)
