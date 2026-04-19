# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_k_t1_t2_1_1_1_st2_142_emt_template(vf: VarFactory, name: str = '1/K(T1/T2-1)(1/(1+sT2))__142') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_K_T1_T2_1_1_1_sT2_K = vf.add_var('1/K(T1/T2-1)(1/(1+sT2))__K_' + name)
    v_1_K_T1_T2_1_1_1_sT2_T1 = vf.add_var('1/K(T1/T2-1)(1/(1+sT2))__T1_' + name)
    v_1_K_T1_T2_1_1_1_sT2_T2 = vf.add_var('1/K(T1/T2-1)(1/(1+sT2))__T2_' + name)

    # --- State Variables ---
    v_1_K_T1_T2_1_1_1_sT2_x = vf.add_var('1/K(T1/T2-1)(1/(1+sT2))__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_K_T1_T2_1_1_1_sT2_x = vf.add_diff_var('d_1/K(T1/T2-1)(1/(1+sT2))__x_' + name, base_var=v_1_K_T1_T2_1_1_1_sT2_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((yi - v_1_K_T1_T2_1_1_1_sT2_x) / v_1_K_T1_T2_1_1_1_sT2_T2),
        ],
        state_vars=[v_1_K_T1_T2_1_1_1_sT2_x],
        algebraic_eqs=[
            (yo - ((v_1_K_T1_T2_1_1_1_sT2_x * ((v_1_K_T1_T2_1_1_1_sT2_T1 / v_1_K_T1_T2_1_1_1_sT2_T2) - sym.Const(1.0))) / v_1_K_T1_T2_1_1_1_sT2_K)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='1/K(T1/T2-1)(1/(1+sT2))'
    )
    templ.block.diff_vars = [d_1_K_T1_T2_1_1_1_sT2_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_K_T1_T2_1_1_1_sT2_K: vf.add_const(None, name='K'),
        v_1_K_T1_T2_1_1_1_sT2_T1: vf.add_const(None, name='T1'),
        v_1_K_T1_T2_1_1_1_sT2_T2: vf.add_const(None, name='T2'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_k_t1_t2_1_1_1_st2_142_emt_template(vf=vf, name='1/K(T1/T2-1)(1/(1+sT2))__142' if name is None else name)
