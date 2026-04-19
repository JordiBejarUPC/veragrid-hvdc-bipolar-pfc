# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_k_1_st1_1_st2_s_1_st3_p_202_emt_template(vf: VarFactory, name: str = 'K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__202') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    K_1_sT1_1_sT2_s_1_sT3_p_K = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__K_' + name)
    K_1_sT1_1_sT2_s_1_sT3_p_T1 = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__T1_' + name)
    K_1_sT1_1_sT2_s_1_sT3_p_T2 = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__T2_' + name)
    K_1_sT1_1_sT2_s_1_sT3_p_T3 = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__T3_' + name)
    K_1_sT1_1_sT2_s_1_sT3_p_y_max = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__y_max_' + name)
    K_1_sT1_1_sT2_s_1_sT3_p_y_min = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__y_min_' + name)

    # --- State Variables ---
    K_1_sT1_1_sT2_s_1_sT3_p_x1 = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__x1_' + name)
    K_1_sT1_1_sT2_s_1_sT3_p_x2 = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__x2_' + name)

    # --- Algebraic / Shared Variables ---
    K_1_sT1_1_sT2_s_1_sT3_p_dx1 = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p_dx1_' + name)
    K_1_sT1_1_sT2_s_1_sT3_p_yo1 = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p_yo1_' + name)
    K_1_sT1_1_sT2_s_1_sT3_p_yo2 = vf.add_var('K(1+sT1)(1+sT2)/(s(1+sT3)) [(p_yo2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_K_1_sT1_1_sT2_s_1_sT3_p_x1 = vf.add_diff_var('d_K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__x1_' + name, base_var=K_1_sT1_1_sT2_s_1_sT3_p_x1)
    d_K_1_sT1_1_sT2_s_1_sT3_p_x2 = vf.add_diff_var('d_K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__x2_' + name, base_var=K_1_sT1_1_sT2_s_1_sT3_p_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            K_1_sT1_1_sT2_s_1_sT3_p_dx1,
            K_1_sT1_1_sT2_s_1_sT3_p_yo1,
        ],
        state_vars=[K_1_sT1_1_sT2_s_1_sT3_p_x1, K_1_sT1_1_sT2_s_1_sT3_p_x2],
        algebraic_eqs=[
            (K_1_sT1_1_sT2_s_1_sT3_p_dx1 - ((yi - K_1_sT1_1_sT2_s_1_sT3_p_x1) / K_1_sT1_1_sT2_s_1_sT3_p_T3)),
            (K_1_sT1_1_sT2_s_1_sT3_p_yo1 - (K_1_sT1_1_sT2_s_1_sT3_p_K * (K_1_sT1_1_sT2_s_1_sT3_p_x1 + (K_1_sT1_1_sT2_s_1_sT3_p_T1 * K_1_sT1_1_sT2_s_1_sT3_p_dx1)))),
            (K_1_sT1_1_sT2_s_1_sT3_p_yo2 - ((K_1_sT1_1_sT2_s_1_sT3_p_y_min + ((K_1_sT1_1_sT2_s_1_sT3_p_x2 - K_1_sT1_1_sT2_s_1_sT3_p_y_min) * sym.heaviside((K_1_sT1_1_sT2_s_1_sT3_p_x2 - K_1_sT1_1_sT2_s_1_sT3_p_y_min)))) - ((K_1_sT1_1_sT2_s_1_sT3_p_x2 - K_1_sT1_1_sT2_s_1_sT3_p_y_max) * sym.heaviside((K_1_sT1_1_sT2_s_1_sT3_p_x2 - K_1_sT1_1_sT2_s_1_sT3_p_y_max))))),
            (yo - ((K_1_sT1_1_sT2_s_1_sT3_p_y_min + (((K_1_sT1_1_sT2_s_1_sT3_p_yo2 + (K_1_sT1_1_sT2_s_1_sT3_p_T2 * K_1_sT1_1_sT2_s_1_sT3_p_yo1)) - K_1_sT1_1_sT2_s_1_sT3_p_y_min) * sym.heaviside(((K_1_sT1_1_sT2_s_1_sT3_p_yo2 + (K_1_sT1_1_sT2_s_1_sT3_p_T2 * K_1_sT1_1_sT2_s_1_sT3_p_yo1)) - K_1_sT1_1_sT2_s_1_sT3_p_y_min)))) - (((K_1_sT1_1_sT2_s_1_sT3_p_yo2 + (K_1_sT1_1_sT2_s_1_sT3_p_T2 * K_1_sT1_1_sT2_s_1_sT3_p_yo1)) - K_1_sT1_1_sT2_s_1_sT3_p_y_max) * sym.heaviside(((K_1_sT1_1_sT2_s_1_sT3_p_yo2 + (K_1_sT1_1_sT2_s_1_sT3_p_T2 * K_1_sT1_1_sT2_s_1_sT3_p_yo1)) - K_1_sT1_1_sT2_s_1_sT3_p_y_max))))),
        ],
        algebraic_vars=[K_1_sT1_1_sT2_s_1_sT3_p_dx1, K_1_sT1_1_sT2_s_1_sT3_p_yo1, K_1_sT1_1_sT2_s_1_sT3_p_yo2, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='K(1+sT1)(1+sT2)/(s(1+sT3)) [(p'
    )
    templ.block.diff_vars = [d_K_1_sT1_1_sT2_s_1_sT3_p_x1, d_K_1_sT1_1_sT2_s_1_sT3_p_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        K_1_sT1_1_sT2_s_1_sT3_p_K: vf.add_const(None, name='K'),
        K_1_sT1_1_sT2_s_1_sT3_p_T1: vf.add_const(None, name='T1'),
        K_1_sT1_1_sT2_s_1_sT3_p_T2: vf.add_const(None, name='T2'),
        K_1_sT1_1_sT2_s_1_sT3_p_T3: vf.add_const(None, name='T3'),
        K_1_sT1_1_sT2_s_1_sT3_p_y_max: vf.add_const(None, name='y_max'),
        K_1_sT1_1_sT2_s_1_sT3_p_y_min: vf.add_const(None, name='y_min'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_k_1_st1_1_st2_s_1_st3_p_202_emt_template(vf=vf, name='K(1+sT1)(1+sT2)/(s(1+sT3)) [(p__202' if name is None else name)
