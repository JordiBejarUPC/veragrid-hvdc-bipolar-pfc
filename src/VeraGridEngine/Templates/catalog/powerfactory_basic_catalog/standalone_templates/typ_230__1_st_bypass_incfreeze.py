# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value, selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_st_bypass_incfreeze_230_emt_template(vf: VarFactory, name: str = '1/sT _bypass_incfreeze__230') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sT_bypass_incfreeze_T = vf.add_var('1/sT _bypass_incfreeze__T_' + name)
    v_1_sT_bypass_incfreeze_Tincfreeze = vf.add_var('1/sT _bypass_incfreeze__Tincfreeze_' + name)

    # --- State Variables ---
    v_1_sT_bypass_incfreeze_x = vf.add_var('1/sT _bypass_incfreeze__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sT_bypass_incfreeze_proc_select_0 = vf.add_var('1/sT _bypass_incfreeze__proc_select_0_' + name)
    v_1_sT_bypass_incfreeze_proc_selfix_1 = vf.add_var('1/sT _bypass_incfreeze__proc_selfix_1_' + name)
    v_1_sT_bypass_incfreeze_proc_selfix_2 = vf.add_var('1/sT _bypass_incfreeze__proc_selfix_2_' + name)
    v_1_sT_bypass_incfreeze_t0 = vf.add_var('1/sT _bypass_incfreeze_t0_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sT_bypass_incfreeze_x = vf.add_diff_var('d_1/sT _bypass_incfreeze__x_' + name, base_var=v_1_sT_bypass_incfreeze_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((v_1_sT_bypass_incfreeze_proc_selfix_1 * ((v_1_sT_bypass_incfreeze_proc_select_0 * sym.Const(0.0)) + ((sym.Const(1.0) - v_1_sT_bypass_incfreeze_proc_select_0) * (yi / v_1_sT_bypass_incfreeze_T)))) + ((sym.Const(1.0) - v_1_sT_bypass_incfreeze_proc_selfix_1) * sym.Const(0.0))),
        ],
        state_vars=[v_1_sT_bypass_incfreeze_x],
        algebraic_eqs=[
            (yo - ((v_1_sT_bypass_incfreeze_proc_selfix_2 * v_1_sT_bypass_incfreeze_x) + ((sym.Const(1.0) - v_1_sT_bypass_incfreeze_proc_selfix_2) * yi))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='1/sT _bypass_incfreeze'
    )
    templ.block.diff_vars = [d_1_sT_bypass_incfreeze_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sT_bypass_incfreeze_T: vf.add_const(None, name='T'),
        v_1_sT_bypass_incfreeze_Tincfreeze: vf.add_const(None, name='Tincfreeze'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_sT_bypass_incfreeze_proc_select_0: vf.add_const(0.0, name=''),
        v_1_sT_bypass_incfreeze_proc_selfix_1: vf.add_const(0.0, name=''),
        v_1_sT_bypass_incfreeze_proc_selfix_2: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        v_1_sT_bypass_incfreeze_t0: glob_time,
    }
    templ.block.procedural_logic = [
        sampled_value(output=v_1_sT_bypass_incfreeze_proc_select_0, source=((glob_time - v_1_sT_bypass_incfreeze_t0) < v_1_sT_bypass_incfreeze_Tincfreeze)),
        selfix((v_1_sT_bypass_incfreeze_T > 0.0), output=v_1_sT_bypass_incfreeze_proc_selfix_1),
        selfix((v_1_sT_bypass_incfreeze_T > 0.0), output=v_1_sT_bypass_incfreeze_proc_selfix_2),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_st_bypass_incfreeze_230_emt_template(vf=vf, name='1/sT _bypass_incfreeze__230' if name is None else name)
