# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_k_stb_1_sta_302_emt_template(vf: VarFactory, name: str = '(K+sTb)/(1+sTa)__302') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_sTb_1_sTa_K = vf.add_var('(K+sTb)/(1+sTa)__K_' + name)
    K_sTb_1_sTa_Ta = vf.add_var('(K+sTb)/(1+sTa)__Ta_' + name)
    K_sTb_1_sTa_Tb = vf.add_var('(K+sTb)/(1+sTa)__Tb_' + name)

    # --- State Variables ---
    K_sTb_1_sTa_x = vf.add_var('(K+sTb)/(1+sTa)__x_' + name)

    # --- Algebraic / Shared Variables ---
    K_sTb_1_sTa_proc_selfix_const_0 = vf.add_var('(K+sTb)/(1+sTa)__proc_selfix_const_0_' + name)
    K_sTb_1_sTa_dx = vf.add_var('(K+sTb)/(1+sTa)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_sTb_1_sTa_x = vf.add_diff_var('d_(K+sTb)/(1+sTa)__x_' + name, base_var=K_sTb_1_sTa_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            K_sTb_1_sTa_dx,
        ],
        state_vars=[K_sTb_1_sTa_x],
        algebraic_eqs=[
            (K_sTb_1_sTa_dx - ((yi - K_sTb_1_sTa_x) / ((K_sTb_1_sTa_proc_selfix_const_0 * K_sTb_1_sTa_Ta) + ((sym.Const(1.0) - K_sTb_1_sTa_proc_selfix_const_0) * sym.Const(1.0))))),
            (yo - ((K_sTb_1_sTa_K * K_sTb_1_sTa_x) + (K_sTb_1_sTa_Tb * K_sTb_1_sTa_dx))),
        ],
        algebraic_vars=[K_sTb_1_sTa_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(K+sTb)/(1+sTa)'
    )
    templ.block.diff_vars = [d_K_sTb_1_sTa_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_sTb_1_sTa_K: vf.add_const(None, name='K'),
        K_sTb_1_sTa_Tb: vf.add_const(None, name='Tb'),
        K_sTb_1_sTa_Ta: vf.add_const(None, name='Ta'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        K_sTb_1_sTa_proc_selfix_const_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((K_sTb_1_sTa_Ta > 0.0), output=K_sTb_1_sTa_proc_selfix_const_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_stb_1_sta_302_emt_template(vf=vf, name='(K+sTb)/(1+sTa)__302' if name is None else name)
