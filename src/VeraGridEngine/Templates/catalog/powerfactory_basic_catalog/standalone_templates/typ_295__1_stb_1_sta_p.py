# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_stb_1_sta_p_295_emt_template(vf: VarFactory, name: str = '(1+sTb)/(1+sTa) [(p__295') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sTb_1_sTa_p_Ta = vf.add_var('(1+sTb)/(1+sTa) [(p__Ta_' + name)
    v_1_sTb_1_sTa_p_Tb = vf.add_var('(1+sTb)/(1+sTa) [(p__Tb_' + name)
    v_1_sTb_1_sTa_p_y_max = vf.add_var('(1+sTb)/(1+sTa) [(p__y_max_' + name)
    v_1_sTb_1_sTa_p_y_min = vf.add_var('(1+sTb)/(1+sTa) [(p__y_min_' + name)

    # --- State Variables ---
    v_1_sTb_1_sTa_p_x = vf.add_var('(1+sTb)/(1+sTa) [(p__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sTb_1_sTa_p_proc_selfix_0 = vf.add_var('(1+sTb)/(1+sTa) [(p__proc_selfix_0_' + name)
    v_1_sTb_1_sTa_p_dx = vf.add_var('(1+sTb)/(1+sTa) [(p_dx_' + name)
    v_1_sTb_1_sTa_p_yox = vf.add_var('(1+sTb)/(1+sTa) [(p_yox_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sTb_1_sTa_p_x = vf.add_diff_var('d_(1+sTb)/(1+sTa) [(p__x_' + name, base_var=v_1_sTb_1_sTa_p_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_sTb_1_sTa_p_dx,
        ],
        state_vars=[v_1_sTb_1_sTa_p_x],
        algebraic_eqs=[
            (v_1_sTb_1_sTa_p_dx - ((v_1_sTb_1_sTa_p_proc_selfix_0 * ((yi - v_1_sTb_1_sTa_p_x) / v_1_sTb_1_sTa_p_Ta)) + ((sym.Const(1.0) - v_1_sTb_1_sTa_p_proc_selfix_0) * ((yi - v_1_sTb_1_sTa_p_x) / sym.Const(0.01))))),
            (v_1_sTb_1_sTa_p_yox - ((v_1_sTb_1_sTa_p_y_min + ((v_1_sTb_1_sTa_p_x - v_1_sTb_1_sTa_p_y_min) * sym.heaviside((v_1_sTb_1_sTa_p_x - v_1_sTb_1_sTa_p_y_min)))) - ((v_1_sTb_1_sTa_p_x - v_1_sTb_1_sTa_p_y_max) * sym.heaviside((v_1_sTb_1_sTa_p_x - v_1_sTb_1_sTa_p_y_max))))),
            (yo - ((v_1_sTb_1_sTa_p_y_min + (((v_1_sTb_1_sTa_p_yox + (v_1_sTb_1_sTa_p_Tb * v_1_sTb_1_sTa_p_dx)) - v_1_sTb_1_sTa_p_y_min) * sym.heaviside(((v_1_sTb_1_sTa_p_yox + (v_1_sTb_1_sTa_p_Tb * v_1_sTb_1_sTa_p_dx)) - v_1_sTb_1_sTa_p_y_min)))) - (((v_1_sTb_1_sTa_p_yox + (v_1_sTb_1_sTa_p_Tb * v_1_sTb_1_sTa_p_dx)) - v_1_sTb_1_sTa_p_y_max) * sym.heaviside(((v_1_sTb_1_sTa_p_yox + (v_1_sTb_1_sTa_p_Tb * v_1_sTb_1_sTa_p_dx)) - v_1_sTb_1_sTa_p_y_max))))),
        ],
        algebraic_vars=[v_1_sTb_1_sTa_p_dx, v_1_sTb_1_sTa_p_yox, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+sTb)/(1+sTa) [(p'
    )
    templ.block.diff_vars = [d_1_sTb_1_sTa_p_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sTb_1_sTa_p_Tb: vf.add_const(None, name='Tb'),
        v_1_sTb_1_sTa_p_Ta: vf.add_const(None, name='Ta'),
        v_1_sTb_1_sTa_p_y_max: vf.add_const(None, name='y_max'),
        v_1_sTb_1_sTa_p_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_sTb_1_sTa_p_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((1.0 - ((1.0 - sym.heaviside(((v_1_sTb_1_sTa_p_Ta - 0.0) - 1e-06))) * (1.0 - (1.0 - (sym.heaviside(((v_1_sTb_1_sTa_p_Ta - v_1_sTb_1_sTa_p_Tb) + 1e-06)) * sym.heaviside(((v_1_sTb_1_sTa_p_Tb - v_1_sTb_1_sTa_p_Ta) + 1e-06))))))), output=v_1_sTb_1_sTa_p_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_stb_1_sta_p_295_emt_template(vf=vf, name='(1+sTb)/(1+sTa) [(p__295' if name is None else name)
