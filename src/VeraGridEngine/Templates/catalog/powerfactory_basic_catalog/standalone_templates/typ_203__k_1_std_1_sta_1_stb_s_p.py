# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_k_1_std_1_sta_1_stb_s_p_203_emt_template(vf: VarFactory, name: str = 'K(1+sTd)/((1+sTa)(1+sTb)s) (p__203') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_1_sTd_1_sTa_1_sTb_s_p_K = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__K_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_Ta = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__Ta_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_Tb = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__Tb_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_Td = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__Td_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_y_max = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__y_max_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_y_min = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__y_min_' + name)

    # --- State Variables ---
    K_1_sTd_1_sTa_1_sTb_s_p_xa = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__xa_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_xb = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__xb_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_xc = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__xc_' + name)

    # --- Algebraic / Shared Variables ---
    K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_0 = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__proc_selfix_0_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_1 = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__proc_selfix_1_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_2 = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__proc_selfix_2_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_3 = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p__proc_selfix_3_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_dxa = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p_dxa_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_xaout = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p_xaout_' + name)
    K_1_sTd_1_sTa_1_sTb_s_p_xbout = vf.add_var('K(1+sTd)/((1+sTa)(1+sTb)s) (p_xbout_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_1_sTd_1_sTa_1_sTb_s_p_xa = vf.add_diff_var('d_K(1+sTd)/((1+sTa)(1+sTb)s) (p__xa_' + name, base_var=K_1_sTd_1_sTa_1_sTb_s_p_xa)
    d_K_1_sTd_1_sTa_1_sTb_s_p_xb = vf.add_diff_var('d_K(1+sTd)/((1+sTa)(1+sTb)s) (p__xb_' + name, base_var=K_1_sTd_1_sTa_1_sTb_s_p_xb)
    d_K_1_sTd_1_sTa_1_sTb_s_p_xc = vf.add_diff_var('d_K(1+sTd)/((1+sTa)(1+sTb)s) (p__xc_' + name, base_var=K_1_sTd_1_sTa_1_sTb_s_p_xc)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            K_1_sTd_1_sTa_1_sTb_s_p_dxa,
            ((K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_2 * ((K_1_sTd_1_sTa_1_sTb_s_p_xaout - K_1_sTd_1_sTa_1_sTb_s_p_xb) / K_1_sTd_1_sTa_1_sTb_s_p_Tb)) + ((sym.Const(1.0) - K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_2) * sym.Const(0.0))),
            K_1_sTd_1_sTa_1_sTb_s_p_xbout,
        ],
        state_vars=[K_1_sTd_1_sTa_1_sTb_s_p_xa, K_1_sTd_1_sTa_1_sTb_s_p_xb, K_1_sTd_1_sTa_1_sTb_s_p_xc],
        algebraic_eqs=[
            (K_1_sTd_1_sTa_1_sTb_s_p_dxa - ((K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_0 * (((K_1_sTd_1_sTa_1_sTb_s_p_K * yi) - K_1_sTd_1_sTa_1_sTb_s_p_xa) / K_1_sTd_1_sTa_1_sTb_s_p_Ta)) + ((sym.Const(1.0) - K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_0) * sym.Const(0.0)))),
            (K_1_sTd_1_sTa_1_sTb_s_p_xaout - ((K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_1 * (K_1_sTd_1_sTa_1_sTb_s_p_xa + (K_1_sTd_1_sTa_1_sTb_s_p_Td * K_1_sTd_1_sTa_1_sTb_s_p_dxa))) + ((sym.Const(1.0) - K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_1) * (K_1_sTd_1_sTa_1_sTb_s_p_K * yi)))),
            (K_1_sTd_1_sTa_1_sTb_s_p_xbout - ((K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_3 * K_1_sTd_1_sTa_1_sTb_s_p_xb) + ((sym.Const(1.0) - K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_3) * K_1_sTd_1_sTa_1_sTb_s_p_xaout))),
            (yo - ((K_1_sTd_1_sTa_1_sTb_s_p_y_min + ((K_1_sTd_1_sTa_1_sTb_s_p_xc - K_1_sTd_1_sTa_1_sTb_s_p_y_min) * sym.heaviside((K_1_sTd_1_sTa_1_sTb_s_p_xc - K_1_sTd_1_sTa_1_sTb_s_p_y_min)))) - ((K_1_sTd_1_sTa_1_sTb_s_p_xc - K_1_sTd_1_sTa_1_sTb_s_p_y_max) * sym.heaviside((K_1_sTd_1_sTa_1_sTb_s_p_xc - K_1_sTd_1_sTa_1_sTb_s_p_y_max))))),
        ],
        algebraic_vars=[K_1_sTd_1_sTa_1_sTb_s_p_dxa, K_1_sTd_1_sTa_1_sTb_s_p_xaout, K_1_sTd_1_sTa_1_sTb_s_p_xbout, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='K(1+sTd)/((1+sTa)(1+sTb)s) (p'
    )
    templ.block.diff_vars = [d_K_1_sTd_1_sTa_1_sTb_s_p_xa, d_K_1_sTd_1_sTa_1_sTb_s_p_xb, d_K_1_sTd_1_sTa_1_sTb_s_p_xc]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_1_sTd_1_sTa_1_sTb_s_p_K: vf.add_const(None, name='K'),
        K_1_sTd_1_sTa_1_sTb_s_p_Td: vf.add_const(None, name='Td'),
        K_1_sTd_1_sTa_1_sTb_s_p_Ta: vf.add_const(None, name='Ta'),
        K_1_sTd_1_sTa_1_sTb_s_p_Tb: vf.add_const(None, name='Tb'),
        K_1_sTd_1_sTa_1_sTb_s_p_y_max: vf.add_const(None, name='y_max'),
        K_1_sTd_1_sTa_1_sTb_s_p_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_0: vf.add_const(0.0, name=''),
        K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_1: vf.add_const(0.0, name=''),
        K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_2: vf.add_const(0.0, name=''),
        K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_3: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((K_1_sTd_1_sTa_1_sTb_s_p_Ta > 0.0), output=K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_0),
        selfix((K_1_sTd_1_sTa_1_sTb_s_p_Ta > 0.0), output=K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_1),
        selfix((K_1_sTd_1_sTa_1_sTb_s_p_Tb > 0.0), output=K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_2),
        selfix((K_1_sTd_1_sTa_1_sTb_s_p_Tb > 0.0), output=K_1_sTd_1_sTa_1_sTb_s_p_proc_selfix_3),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_1_std_1_sta_1_stb_s_p_203_emt_template(vf=vf, name='K(1+sTd)/((1+sTa)(1+sTb)s) (p__203' if name is None else name)
