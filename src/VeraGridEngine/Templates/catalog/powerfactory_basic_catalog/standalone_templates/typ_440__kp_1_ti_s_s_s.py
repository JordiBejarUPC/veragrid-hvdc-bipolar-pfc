# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_kp_1_ti_s_s_s_440_emt_template(vf: VarFactory, name: str = 'Kp(1/Ti+s)/s (s)__440') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kp_1_Ti_s_s_s_Kp = vf.add_var('Kp(1/Ti+s)/s (s)__Kp_' + name)
    Kp_1_Ti_s_s_s_Ti = vf.add_var('Kp(1/Ti+s)/s (s)__Ti_' + name)
    Kp_1_Ti_s_s_s_Tt = vf.add_var('Kp(1/Ti+s)/s (s)__Tt_' + name)

    # --- State Variables ---
    Kp_1_Ti_s_s_s_x = vf.add_var('Kp(1/Ti+s)/s (s)__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)
    yo_lim = vf.add_var('yo_lim_' + name)

    # --- Derivative Variables ---
    d_Kp_1_Ti_s_s_s_x = vf.add_diff_var('d_Kp(1/Ti+s)/s (s)__x_' + name, base_var=Kp_1_Ti_s_s_s_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (((Kp_1_Ti_s_s_s_Kp / Kp_1_Ti_s_s_s_Ti) * yi) + ((yo_lim - yo) / Kp_1_Ti_s_s_s_Tt)),
        ],
        state_vars=[Kp_1_Ti_s_s_s_x],
        algebraic_eqs=[
            (yo - ((Kp_1_Ti_s_s_s_Kp * yi) + Kp_1_Ti_s_s_s_x)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, yo_lim],
        out_vars=[yo],
        name='Kp(1/Ti+s)/s (s)'
    )
    templ.block.diff_vars = [d_Kp_1_Ti_s_s_s_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kp_1_Ti_s_s_s_Kp: vf.add_const(None, name='Kp'),
        Kp_1_Ti_s_s_s_Ti: vf.add_const(None, name='Ti'),
        Kp_1_Ti_s_s_s_Tt: vf.add_const(None, name='Tt'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kp_1_ti_s_s_s_440_emt_template(vf=vf, name='Kp(1/Ti+s)/s (s)__440' if name is None else name)
