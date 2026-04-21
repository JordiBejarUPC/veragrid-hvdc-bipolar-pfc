# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_st_1_st_enable_124_emt_template(vf: VarFactory, name: str = 'sT/(1+sT) _enable__124') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    sT_1_sT_enable_T = vf.add_var('sT/(1+sT) _enable__T_' + name)

    # --- State Variables ---
    sT_1_sT_enable_x = vf.add_var('sT/(1+sT) _enable__x_' + name)

    # --- Algebraic / Shared Variables ---
    sT_1_sT_enable_proc_selfix_0 = vf.add_var('sT/(1+sT) _enable__proc_selfix_0_' + name)
    sT_1_sT_enable_dx = vf.add_var('sT/(1+sT) _enable_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_sT_1_sT_enable_x = vf.add_diff_var('d_sT/(1+sT) _enable__x_' + name, base_var=sT_1_sT_enable_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            sT_1_sT_enable_dx,
        ],
        state_vars=[sT_1_sT_enable_x],
        algebraic_eqs=[
            (sT_1_sT_enable_dx - ((sT_1_sT_enable_proc_selfix_0 * ((yi - sT_1_sT_enable_x) / sT_1_sT_enable_T)) + ((sym.Const(1.0) - sT_1_sT_enable_proc_selfix_0) * sym.Const(0.0)))),
            (yo - (sT_1_sT_enable_T * sT_1_sT_enable_dx)),
        ],
        algebraic_vars=[sT_1_sT_enable_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='sT/(1+sT) _enable'
    )
    templ.block.diff_vars = [d_sT_1_sT_enable_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        sT_1_sT_enable_T: vf.add_const(None, name='T'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        sT_1_sT_enable_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((sT_1_sT_enable_T > 0.0), output=sT_1_sT_enable_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_st_1_st_enable_124_emt_template(vf=vf, name='sT/(1+sT) _enable__124' if name is None else name)
