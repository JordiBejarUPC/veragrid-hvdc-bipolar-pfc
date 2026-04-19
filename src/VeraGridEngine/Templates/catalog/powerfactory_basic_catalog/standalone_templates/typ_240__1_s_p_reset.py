# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import reset
from VeraGridEngine.enumerations import DeviceType

def get_v_1_s_p_reset_240_emt_template(vf: VarFactory, name: str = '1/s [p]  _reset__240') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_s_p_reset_y_max = vf.add_var('1/s [p]  _reset__y_max_' + name)

    # --- State Variables ---
    v_1_s_p_reset_x = vf.add_var('1/s [p]  _reset__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_s_p_reset_xinc = vf.add_var('1/s [p]  _reset_xinc_' + name)
    rst = vf.add_var('rst_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_s_p_reset_x = vf.add_diff_var('d_1/s [p]  _reset__x_' + name, base_var=v_1_s_p_reset_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            yi,
        ],
        state_vars=[v_1_s_p_reset_x],
        algebraic_eqs=[
            (yo - (((-v_1_s_p_reset_y_max) + ((v_1_s_p_reset_x - (-v_1_s_p_reset_y_max)) * sym.heaviside((v_1_s_p_reset_x - (-v_1_s_p_reset_y_max))))) - ((v_1_s_p_reset_x - v_1_s_p_reset_y_max) * sym.heaviside((v_1_s_p_reset_x - v_1_s_p_reset_y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, rst],
        out_vars=[yo],
        name='1/s [p]  _reset'
    )
    templ.block.diff_vars = [d_1_s_p_reset_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_s_p_reset_y_max: vf.add_const(None, name='y_max'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        v_1_s_p_reset_xinc: v_1_s_p_reset_x,
    }
    templ.block.procedural_logic = [
        reset(v_1_s_p_reset_x, rst, v_1_s_p_reset_xinc),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_s_p_reset_240_emt_template(vf=vf, name='1/s [p]  _reset__240' if name is None else name)
