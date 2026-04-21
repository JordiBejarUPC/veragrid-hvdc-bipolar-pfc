# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_limit_p_using_min_max_315_emt_template(vf: VarFactory, name: str = 'Limit [p] (using min/max)__315') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Limit_p_using_min_max_y_lim = vf.add_var('Limit [p] (using min/max)__y_lim_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((((yi * sym.heaviside((yi - (-Limit_p_using_min_max_y_lim)))) + ((-Limit_p_using_min_max_y_lim) * (sym.Const(1) - sym.heaviside((yi - (-Limit_p_using_min_max_y_lim)))))) * sym.heaviside((Limit_p_using_min_max_y_lim - ((yi * sym.heaviside((yi - (-Limit_p_using_min_max_y_lim)))) + ((-Limit_p_using_min_max_y_lim) * (sym.Const(1) - sym.heaviside((yi - (-Limit_p_using_min_max_y_lim))))))))) + (Limit_p_using_min_max_y_lim * (sym.Const(1) - sym.heaviside((Limit_p_using_min_max_y_lim - ((yi * sym.heaviside((yi - (-Limit_p_using_min_max_y_lim)))) + ((-Limit_p_using_min_max_y_lim) * (sym.Const(1) - sym.heaviside((yi - (-Limit_p_using_min_max_y_lim)))))))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Limit [p] (using min/max)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Limit_p_using_min_max_y_lim: vf.add_const(None, name='y_lim'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_limit_p_using_min_max_315_emt_template(vf=vf, name='Limit [p] (using min/max)__315' if name is None else name)
