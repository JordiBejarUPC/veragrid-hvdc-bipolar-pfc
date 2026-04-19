# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_stb_1_sta_bypass_297_emt_template(vf: VarFactory, name: str = '(1+sTb)/(1+sTa) _bypass__297') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sTb_1_sTa_bypass_Ta = vf.add_var('(1+sTb)/(1+sTa) _bypass__Ta_' + name)
    v_1_sTb_1_sTa_bypass_Tb = vf.add_var('(1+sTb)/(1+sTa) _bypass__Tb_' + name)

    # --- State Variables ---
    v_1_sTb_1_sTa_bypass_x = vf.add_var('(1+sTb)/(1+sTa) _bypass__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sTb_1_sTa_bypass_proc_selfix_1 = vf.add_var('(1+sTb)/(1+sTa) _bypass__proc_selfix_1_' + name)
    v_1_sTb_1_sTa_bypass_proc_selfix_2 = vf.add_var('(1+sTb)/(1+sTa) _bypass__proc_selfix_2_' + name)
    v_1_sTb_1_sTa_bypass_proc_selfix_const_0 = vf.add_var('(1+sTb)/(1+sTa) _bypass__proc_selfix_const_0_' + name)
    v_1_sTb_1_sTa_bypass_dx = vf.add_var('(1+sTb)/(1+sTa) _bypass_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sTb_1_sTa_bypass_x = vf.add_diff_var('d_(1+sTb)/(1+sTa) _bypass__x_' + name, base_var=v_1_sTb_1_sTa_bypass_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_sTb_1_sTa_bypass_dx,
        ],
        state_vars=[v_1_sTb_1_sTa_bypass_x],
        algebraic_eqs=[
            (v_1_sTb_1_sTa_bypass_dx - ((v_1_sTb_1_sTa_bypass_proc_selfix_1 * ((yi - v_1_sTb_1_sTa_bypass_x) / ((v_1_sTb_1_sTa_bypass_proc_selfix_const_0 * v_1_sTb_1_sTa_bypass_Ta) + ((sym.Const(1.0) - v_1_sTb_1_sTa_bypass_proc_selfix_const_0) * sym.Const(1.0))))) + ((sym.Const(1.0) - v_1_sTb_1_sTa_bypass_proc_selfix_1) * sym.Const(0.0)))),
            (yo - ((v_1_sTb_1_sTa_bypass_proc_selfix_2 * (v_1_sTb_1_sTa_bypass_x + (v_1_sTb_1_sTa_bypass_Tb * v_1_sTb_1_sTa_bypass_dx))) + ((sym.Const(1.0) - v_1_sTb_1_sTa_bypass_proc_selfix_2) * yi))),
        ],
        algebraic_vars=[v_1_sTb_1_sTa_bypass_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+sTb)/(1+sTa) _bypass'
    )
    templ.block.diff_vars = [d_1_sTb_1_sTa_bypass_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sTb_1_sTa_bypass_Tb: vf.add_const(None, name='Tb'),
        v_1_sTb_1_sTa_bypass_Ta: vf.add_const(None, name='Ta'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_sTb_1_sTa_bypass_proc_selfix_const_0: vf.add_const(0.0, name=''),
        v_1_sTb_1_sTa_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
        v_1_sTb_1_sTa_bypass_proc_selfix_2: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((v_1_sTb_1_sTa_bypass_Ta > 0.0), output=v_1_sTb_1_sTa_bypass_proc_selfix_const_0),
        selfix((sym.heaviside(((v_1_sTb_1_sTa_bypass_Ta - 0.0) - 1e-06)) * (1.0 - (sym.heaviside(((v_1_sTb_1_sTa_bypass_Ta - v_1_sTb_1_sTa_bypass_Tb) + 1e-06)) * sym.heaviside(((v_1_sTb_1_sTa_bypass_Tb - v_1_sTb_1_sTa_bypass_Ta) + 1e-06))))), output=v_1_sTb_1_sTa_bypass_proc_selfix_1),
        selfix((sym.heaviside(((v_1_sTb_1_sTa_bypass_Ta - 0.0) - 1e-06)) * (1.0 - (sym.heaviside(((v_1_sTb_1_sTa_bypass_Ta - v_1_sTb_1_sTa_bypass_Tb) + 1e-06)) * sym.heaviside(((v_1_sTb_1_sTa_bypass_Tb - v_1_sTb_1_sTa_bypass_Ta) + 1e-06))))), output=v_1_sTb_1_sTa_bypass_proc_selfix_2),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_stb_1_sta_bypass_297_emt_template(vf=vf, name='(1+sTb)/(1+sTa) _bypass__297' if name is None else name)
