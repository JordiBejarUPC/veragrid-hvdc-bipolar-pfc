# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_min4_366_emt_template(vf: VarFactory, name: str = 'MIN4__366') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yi3 = vf.add_var('yi3_' + name)
    yi4 = vf.add_var('yi4_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((((((yi1 * sym.heaviside((yi2 - yi1))) + (yi2 * (sym.Const(1) - sym.heaviside((yi2 - yi1))))) * sym.heaviside((yi3 - ((yi1 * sym.heaviside((yi2 - yi1))) + (yi2 * (sym.Const(1) - sym.heaviside((yi2 - yi1)))))))) + (yi3 * (sym.Const(1) - sym.heaviside((yi3 - ((yi1 * sym.heaviside((yi2 - yi1))) + (yi2 * (sym.Const(1) - sym.heaviside((yi2 - yi1)))))))))) * sym.heaviside((yi4 - ((((yi1 * sym.heaviside((yi2 - yi1))) + (yi2 * (sym.Const(1) - sym.heaviside((yi2 - yi1))))) * sym.heaviside((yi3 - ((yi1 * sym.heaviside((yi2 - yi1))) + (yi2 * (sym.Const(1) - sym.heaviside((yi2 - yi1)))))))) + (yi3 * (sym.Const(1) - sym.heaviside((yi3 - ((yi1 * sym.heaviside((yi2 - yi1))) + (yi2 * (sym.Const(1) - sym.heaviside((yi2 - yi1))))))))))))) + (yi4 * (sym.Const(1) - sym.heaviside((yi4 - ((((yi1 * sym.heaviside((yi2 - yi1))) + (yi2 * (sym.Const(1) - sym.heaviside((yi2 - yi1))))) * sym.heaviside((yi3 - ((yi1 * sym.heaviside((yi2 - yi1))) + (yi2 * (sym.Const(1) - sym.heaviside((yi2 - yi1)))))))) + (yi3 * (sym.Const(1) - sym.heaviside((yi3 - ((yi1 * sym.heaviside((yi2 - yi1))) + (yi2 * (sym.Const(1) - sym.heaviside((yi2 - yi1)))))))))))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi1, yi2, yi3, yi4],
        out_vars=[yo],
        name='MIN4'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_min4_366_emt_template(vf=vf, name='MIN4__366' if name is None else name)
