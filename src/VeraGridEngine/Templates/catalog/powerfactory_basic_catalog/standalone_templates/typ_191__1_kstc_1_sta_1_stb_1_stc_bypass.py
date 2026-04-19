# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_kstc_1_sta_1_stb_1_stc_bypass_191_emt_template(vf: VarFactory, name: str = '(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__191') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_K = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__K_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Ta = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__Ta_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tb = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__Tb_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tc = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__Tc_' + name)

    # --- State Variables ---
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xa = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__xa_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xb = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__xb_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xc = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__xc_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_0 = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__proc_selfix_0_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_1 = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__proc_selfix_1_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_2 = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__proc_selfix_2_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_3 = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__proc_selfix_3_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_4 = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__proc_selfix_4_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_5 = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__proc_selfix_5_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_dxc = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass_dxc_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxa = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass_yxa_' + name)
    v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxb = vf.add_var('(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass_yxb_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xa = vf.add_diff_var('d_(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__xa_' + name, base_var=v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xa)
    d_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xb = vf.add_diff_var('d_(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__xb_' + name, base_var=v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xb)
    d_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xc = vf.add_diff_var('d_(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__xc_' + name, base_var=v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xc)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_0 * ((yi - v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xa) / v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Ta)) + ((sym.Const(1.0) - v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_0) * sym.Const(0.0))),
            ((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_2 * ((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxa - v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xb) / v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tb)) + ((sym.Const(1.0) - v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_2) * sym.Const(0.0))),
            v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_dxc,
        ],
        state_vars=[v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xa, v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xb, v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xc],
        algebraic_eqs=[
            (v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxa - ((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_1 * v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xa) + ((sym.Const(1.0) - v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_1) * yi))),
            (v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxb - ((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_3 * v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xb) + ((sym.Const(1.0) - v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_3) * v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxa))),
            (v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_dxc - ((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_4 * ((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxb - v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xc) / v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tc)) + ((sym.Const(1.0) - v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_4) * sym.Const(0.0)))),
            (yo - ((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_5 * (v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xc + ((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_dxc * v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_K) * v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tc))) + ((sym.Const(1.0) - v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_5) * v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxb))),
        ],
        algebraic_vars=[v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxa, v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_yxb, v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_dxc, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass'
    )
    templ.block.diff_vars = [d_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xa, d_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xb, d_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_xc]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Ta: vf.add_const(None, name='Ta'),
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tb: vf.add_const(None, name='Tb'),
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tc: vf.add_const(None, name='Tc'),
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_K: vf.add_const(None, name='K'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_0: vf.add_const(0.0, name=''),
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_1: vf.add_const(0.0, name=''),
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_2: vf.add_const(0.0, name=''),
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_3: vf.add_const(0.0, name=''),
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_4: vf.add_const(0.0, name=''),
        v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_5: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Ta > 0.0), output=v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_0),
        selfix((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Ta > 0.0), output=v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_1),
        selfix((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tb > 0.0), output=v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_2),
        selfix((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tb > 0.0), output=v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_3),
        selfix((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tc > 0.0), output=v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_4),
        selfix((v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_Tc > 0.0), output=v_1_KsTc_1_sTa_1_sTb_1_sTc_bypass_proc_selfix_5),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_kstc_1_sta_1_stb_1_stc_bypass_191_emt_template(vf=vf, name='(1+KsTc)/((1+sTa)(1+sTb)(1+sTc)) _bypass__191' if name is None else name)
