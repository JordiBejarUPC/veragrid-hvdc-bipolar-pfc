# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_v_1_1_st_enable_135_emt_template(vf: VarFactory, name: str = '1/(1+sT) _enable__135') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_1_sT_enable_T = vf.add_var('1/(1+sT) _enable__T_' + name)

    # --- State Variables ---
    v_1_1_sT_enable_x = vf.add_var('1/(1+sT) _enable__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_1_sT_enable_proc_select_0 = vf.add_var('1/(1+sT) _enable__proc_select_0_' + name)
    enable = vf.add_var('enable_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_1_sT_enable_x = vf.add_diff_var('d_1/(1+sT) _enable__x_' + name, base_var=v_1_1_sT_enable_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((v_1_1_sT_enable_proc_select_0 * ((yi - v_1_1_sT_enable_x) / v_1_1_sT_enable_T)) + ((sym.Const(1.0) - v_1_1_sT_enable_proc_select_0) * sym.Const(0.0))),
        ],
        state_vars=[v_1_1_sT_enable_x],
        algebraic_eqs=[
            (yo - v_1_1_sT_enable_x),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, enable],
        out_vars=[yo],
        name='1/(1+sT) _enable'
    )
    templ.block.diff_vars = [d_1_1_sT_enable_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_1_sT_enable_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_1_sT_enable_proc_select_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=v_1_1_sT_enable_proc_select_0, source=((enable - 0.5) > 0.0)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_1_st_enable_135_emt_template(vf=vf, name='1/(1+sT) _enable__135' if name is None else name)
