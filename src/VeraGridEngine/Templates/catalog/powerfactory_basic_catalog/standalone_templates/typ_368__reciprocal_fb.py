# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_reciprocal_fb_368_emt_template(vf: VarFactory, name: str = 'RECIPROCAL _fb__368') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    RECIPROCAL_fb_proc_select_0 = vf.add_var('RECIPROCAL _fb__proc_select_0_' + name)
    u = vf.add_var('u_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - (((RECIPROCAL_fb_proc_select_0 * sym.Const(1.0)) + ((sym.Const(1.0) - RECIPROCAL_fb_proc_select_0) * (-sym.Const(1.0)))) / ((sym.abs(u) * sym.heaviside((sym.abs(u) - sym.Const(1e-06)))) + (sym.Const(1e-06) * (sym.Const(1) - sym.heaviside((sym.abs(u) - sym.Const(1e-06)))))))),
        ],
        algebraic_vars=[yo],
        in_vars=[u],
        out_vars=[yo],
        name='RECIPROCAL _fb'
    )
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        RECIPROCAL_fb_proc_select_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=RECIPROCAL_fb_proc_select_0, source=(u >= 0.0)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_reciprocal_fb_368_emt_template(vf=vf, name='RECIPROCAL _fb__368' if name is None else name)
