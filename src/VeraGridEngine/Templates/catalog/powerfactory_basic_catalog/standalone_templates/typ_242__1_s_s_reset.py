# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset
from VeraGridEngine.enumerations import DeviceType

def get_v_1_s_s_reset_242_emt_template(vf: VarFactory, name: str = '1/s [s]  _reset__242') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---
    v_1_s_s_reset_x = vf.add_var('1/s [s]  _reset__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_s_s_reset_xinc = vf.add_var('1/s [s]  _reset_xinc_' + name)
    rst = vf.add_var('rst_' + name)
    y_max = vf.add_var('y_max_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_s_s_reset_x = vf.add_diff_var('d_1/s [s]  _reset__x_' + name, base_var=v_1_s_s_reset_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            yi,
        ],
        state_vars=[v_1_s_s_reset_x],
        algebraic_eqs=[
            (yo - (((-y_max) + ((v_1_s_s_reset_x - (-y_max)) * sym.heaviside((v_1_s_s_reset_x - (-y_max))))) - ((v_1_s_s_reset_x - y_max) * sym.heaviside((v_1_s_s_reset_x - y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, rst, y_max],
        out_vars=[yo],
        name='1/s [s]  _reset'
    )
    templ.block.diff_vars = [d_1_s_s_reset_x]
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        v_1_s_s_reset_xinc: v_1_s_s_reset_x,
    }
    templ.block.procedural_logic = [
        reset(v_1_s_s_reset_x, rst, v_1_s_s_reset_xinc),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_s_s_reset_242_emt_template(vf=vf, name='1/s [s]  _reset__242' if name is None else name)
