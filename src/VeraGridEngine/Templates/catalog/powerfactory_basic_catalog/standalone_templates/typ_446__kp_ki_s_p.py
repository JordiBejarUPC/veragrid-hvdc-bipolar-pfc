# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_kp_ki_s_p_446_emt_template(vf: VarFactory, name: str = 'Kp+Ki/s [p__446') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kp_Ki_s_p_Ki = vf.add_var('Kp+Ki/s [p__Ki_' + name)
    Kp_Ki_s_p_Kp = vf.add_var('Kp+Ki/s [p__Kp_' + name)
    Kp_Ki_s_p_ymax = vf.add_var('Kp+Ki/s [p__ymax_' + name)
    Kp_Ki_s_p_ymin = vf.add_var('Kp+Ki/s [p__ymin_' + name)

    # --- State Variables ---
    Kp_Ki_s_p_x = vf.add_var('Kp+Ki/s [p__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Kp_Ki_s_p_x = vf.add_diff_var('d_Kp+Ki/s [p__x_' + name, base_var=Kp_Ki_s_p_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (Kp_Ki_s_p_Ki * yi),
        ],
        state_vars=[Kp_Ki_s_p_x],
        algebraic_eqs=[
            (yo - ((Kp_Ki_s_p_ymin + (((Kp_Ki_s_p_x + (Kp_Ki_s_p_Kp * yi)) - Kp_Ki_s_p_ymin) * sym.heaviside(((Kp_Ki_s_p_x + (Kp_Ki_s_p_Kp * yi)) - Kp_Ki_s_p_ymin)))) - (((Kp_Ki_s_p_x + (Kp_Ki_s_p_Kp * yi)) - Kp_Ki_s_p_ymax) * sym.heaviside(((Kp_Ki_s_p_x + (Kp_Ki_s_p_Kp * yi)) - Kp_Ki_s_p_ymax))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Kp+Ki/s [p'
    )
    templ.block.diff_vars = [d_Kp_Ki_s_p_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kp_Ki_s_p_Kp: vf.add_const(None, name='Kp'),
        Kp_Ki_s_p_Ki: vf.add_const(None, name='Ki'),
        Kp_Ki_s_p_ymax: vf.add_const(None, name='ymax'),
        Kp_Ki_s_p_ymin: vf.add_const(None, name='ymin'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kp_ki_s_p_446_emt_template(vf=vf, name='Kp+Ki/s [p__446' if name is None else name)
