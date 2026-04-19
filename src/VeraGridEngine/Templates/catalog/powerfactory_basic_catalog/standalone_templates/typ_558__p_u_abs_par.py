# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_p_u_abs_par_558_emt_template(vf: VarFactory, name: str = 'p.u. -> abs (par)__558') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    p_u_abs_par_base = vf.add_var('p.u. -> abs (par)__base_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - (p_u_abs_par_base * yi)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='p.u. -> abs (par)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        p_u_abs_par_base: vf.add_const(None, name='base'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_p_u_abs_par_558_emt_template(vf=vf, name='p.u. -> abs (par)__558' if name is None else name)
