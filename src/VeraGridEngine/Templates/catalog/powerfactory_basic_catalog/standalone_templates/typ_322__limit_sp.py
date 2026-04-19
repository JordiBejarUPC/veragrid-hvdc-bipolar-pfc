# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_limit_sp_322_emt_template(vf: VarFactory, name: str = 'Limit [sp__322') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Limit_sp_y_max = vf.add_var('Limit [sp__y_max_' + name)
    Limit_sp_y_min = vf.add_var('Limit [sp__y_min_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yi_max = vf.add_var('yi_max_' + name)
    yi_min = vf.add_var('yi_min_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((((Limit_sp_y_min * sym.heaviside((Limit_sp_y_min - yi_min))) + (yi_min * (sym.Const(1) - sym.heaviside((Limit_sp_y_min - yi_min))))) + ((yi - ((Limit_sp_y_min * sym.heaviside((Limit_sp_y_min - yi_min))) + (yi_min * (sym.Const(1) - sym.heaviside((Limit_sp_y_min - yi_min)))))) * sym.heaviside((yi - ((Limit_sp_y_min * sym.heaviside((Limit_sp_y_min - yi_min))) + (yi_min * (sym.Const(1) - sym.heaviside((Limit_sp_y_min - yi_min))))))))) - ((yi - ((Limit_sp_y_max * sym.heaviside((yi_max - Limit_sp_y_max))) + (yi_max * (sym.Const(1) - sym.heaviside((yi_max - Limit_sp_y_max)))))) * sym.heaviside((yi - ((Limit_sp_y_max * sym.heaviside((yi_max - Limit_sp_y_max))) + (yi_max * (sym.Const(1) - sym.heaviside((yi_max - Limit_sp_y_max)))))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, yi_max, yi_min],
        out_vars=[yo],
        name='Limit [sp'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Limit_sp_y_max: vf.add_const(None, name='y_max'),
        Limit_sp_y_min: vf.add_const(None, name='y_min'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_limit_sp_322_emt_template(vf=vf, name='Limit [sp__322' if name is None else name)
