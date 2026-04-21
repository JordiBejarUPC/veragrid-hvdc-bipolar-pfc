# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_ats_1_bts_293_emt_template(vf: VarFactory, name: str = '(1+ATs)/(1+BTs)__293') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_ATs_1_BTs_A = vf.add_var('(1+ATs)/(1+BTs)__A_' + name)
    v_1_ATs_1_BTs_B = vf.add_var('(1+ATs)/(1+BTs)__B_' + name)
    v_1_ATs_1_BTs_T = vf.add_var('(1+ATs)/(1+BTs)__T_' + name)

    # --- State Variables ---
    v_1_ATs_1_BTs_x = vf.add_var('(1+ATs)/(1+BTs)__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_ATs_1_BTs_dx = vf.add_var('(1+ATs)/(1+BTs)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_ATs_1_BTs_x = vf.add_diff_var('d_(1+ATs)/(1+BTs)__x_' + name, base_var=v_1_ATs_1_BTs_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_ATs_1_BTs_dx,
        ],
        state_vars=[v_1_ATs_1_BTs_x],
        algebraic_eqs=[
            (v_1_ATs_1_BTs_dx - ((yi - v_1_ATs_1_BTs_x) / (v_1_ATs_1_BTs_B * v_1_ATs_1_BTs_T))),
            (yo - (v_1_ATs_1_BTs_x + ((v_1_ATs_1_BTs_dx * v_1_ATs_1_BTs_A) * v_1_ATs_1_BTs_T))),
        ],
        algebraic_vars=[v_1_ATs_1_BTs_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+ATs)/(1+BTs)'
    )
    templ.block.diff_vars = [d_1_ATs_1_BTs_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_ATs_1_BTs_A: vf.add_const(None, name='A'),
        v_1_ATs_1_BTs_B: vf.add_const(None, name='B'),
        v_1_ATs_1_BTs_T: vf.add_const(None, name='T'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_ats_1_bts_293_emt_template(vf=vf, name='(1+ATs)/(1+BTs)__293' if name is None else name)
