# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_kp_ki_s_s_444_emt_template(vf: VarFactory, name: str = 'Kp+Ki/s (s)__444') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kp_Ki_s_s_Ki = vf.add_var('Kp+Ki/s (s)__Ki_' + name)
    Kp_Ki_s_s_Kp = vf.add_var('Kp+Ki/s (s)__Kp_' + name)
    Kp_Ki_s_s_Tt = vf.add_var('Kp+Ki/s (s)__Tt_' + name)

    # --- State Variables ---
    Kp_Ki_s_s_x = vf.add_var('Kp+Ki/s (s)__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)
    yo_lim = vf.add_var('yo_lim_' + name)

    # --- Derivative Variables ---
    d_Kp_Ki_s_s_x = vf.add_diff_var('d_Kp+Ki/s (s)__x_' + name, base_var=Kp_Ki_s_s_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((Kp_Ki_s_s_Ki * yi) + ((yo_lim - yo) / Kp_Ki_s_s_Tt)),
        ],
        state_vars=[Kp_Ki_s_s_x],
        algebraic_eqs=[
            (yo - ((Kp_Ki_s_s_Kp * yi) + Kp_Ki_s_s_x)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi, yo_lim],
        out_vars=[yo],
        name='Kp+Ki/s (s)'
    )
    templ.block.diff_vars = [d_Kp_Ki_s_s_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kp_Ki_s_s_Kp: vf.add_const(None, name='Kp'),
        Kp_Ki_s_s_Ki: vf.add_const(None, name='Ki'),
        Kp_Ki_s_s_Tt: vf.add_const(None, name='Tt'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kp_ki_s_s_444_emt_template(vf=vf, name='Kp+Ki/s (s)__444' if name is None else name)
