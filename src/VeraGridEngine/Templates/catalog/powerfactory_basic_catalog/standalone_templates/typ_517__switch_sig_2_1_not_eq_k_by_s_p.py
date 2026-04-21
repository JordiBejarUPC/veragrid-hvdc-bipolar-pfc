# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_switch_sig_2_1_not_eq_k_by_s_p_517_emt_template(vf: VarFactory, name: str = 'Switch sig 2->1 (NOT EQ K) by s/p__517') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Switch_sig_2_1_NOT_EQ_K_by_s_p_K = vf.add_var('Switch sig 2->1 (NOT EQ K) by s/p__K_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Switch_sig_2_1_NOT_EQ_K_by_s_p_proc_select_0 = vf.add_var('Switch sig 2->1 (NOT EQ K) by s/p__proc_select_0_' + name)
    sw = vf.add_var('sw_' + name)
    yi1 = vf.add_var('yi1_' + name)
    yi2 = vf.add_var('yi2_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (yo - ((Switch_sig_2_1_NOT_EQ_K_by_s_p_proc_select_0 * yi1) + ((sym.Const(1.0) - Switch_sig_2_1_NOT_EQ_K_by_s_p_proc_select_0) * yi2))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi1, yi2, sw],
        out_vars=[yo],
        name='Switch sig 2->1 (NOT EQ K) by s/p'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Switch_sig_2_1_NOT_EQ_K_by_s_p_K: vf.add_const(None, name='K'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Switch_sig_2_1_NOT_EQ_K_by_s_p_proc_select_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Switch_sig_2_1_NOT_EQ_K_by_s_p_proc_select_0, source=(1.0 - (sym.heaviside(((sw - Switch_sig_2_1_NOT_EQ_K_by_s_p_K) + 1e-06)) * sym.heaviside(((Switch_sig_2_1_NOT_EQ_K_by_s_p_K - sw) + 1e-06))))),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_switch_sig_2_1_not_eq_k_by_s_p_517_emt_template(vf=vf, name='Switch sig 2->1 (NOT EQ K) by s/p__517' if name is None else name)
