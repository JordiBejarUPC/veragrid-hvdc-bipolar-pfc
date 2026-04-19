# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_s_w0_2_s_2_118_emt_template(vf: VarFactory, name: str = 's/(w0^2+s^2)__118') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    s_w0_2_s_2_f0 = vf.add_var('s/(w0^2+s^2)__f0_' + name)

    # --- State Variables ---
    s_w0_2_s_2_x1 = vf.add_var('s/(w0^2+s^2)__x1_' + name)
    s_w0_2_s_2_x2 = vf.add_var('s/(w0^2+s^2)__x2_' + name)

    # --- Algebraic / Shared Variables ---
    s_w0_2_s_2_w0 = vf.add_var('s/(w0^2+s^2)_w0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_s_w0_2_s_2_x1 = vf.add_diff_var('d_s/(w0^2+s^2)__x1_' + name, base_var=s_w0_2_s_2_x1)
    d_s_w0_2_s_2_x2 = vf.add_diff_var('d_s/(w0^2+s^2)__x2_' + name, base_var=s_w0_2_s_2_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            s_w0_2_s_2_x2,
            (yi - ((s_w0_2_s_2_w0 * s_w0_2_s_2_w0) * s_w0_2_s_2_x1)),
        ],
        state_vars=[s_w0_2_s_2_x1, s_w0_2_s_2_x2],
        algebraic_eqs=[
            (yo - s_w0_2_s_2_x2),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='s/(w0^2+s^2)'
    )
    templ.block.diff_vars = [d_s_w0_2_s_2_x1, d_s_w0_2_s_2_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        s_w0_2_s_2_f0: vf.add_const(None, name='f0'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: s_w0_2_s_2_x2,
        s_w0_2_s_2_x1: (yi / (s_w0_2_s_2_w0 * s_w0_2_s_2_w0)),
        s_w0_2_s_2_x2: vf.add_const(0.0, name=''),
        s_w0_2_s_2_w0: ((sym.Const(2.0) * sym.Const(3.141592653589793)) * s_w0_2_s_2_f0),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_s_w0_2_s_2_118_emt_template(vf=vf, name='s/(w0^2+s^2)__118' if name is None else name)
