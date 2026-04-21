# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_kp_1_sti_443_emt_template(vf: VarFactory, name: str = 'Kp+1/sTi__443') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kp_1_sTi_Kp = vf.add_var('Kp+1/sTi__Kp_' + name)
    Kp_1_sTi_Ti = vf.add_var('Kp+1/sTi__Ti_' + name)

    # --- State Variables ---
    Kp_1_sTi_x = vf.add_var('Kp+1/sTi__x_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Kp_1_sTi_x = vf.add_diff_var('d_Kp+1/sTi__x_' + name, base_var=Kp_1_sTi_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((sym.Const(1.0) / Kp_1_sTi_Ti) * yi),
        ],
        state_vars=[Kp_1_sTi_x],
        algebraic_eqs=[
            (yo - ((Kp_1_sTi_Kp * yi) + Kp_1_sTi_x)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Kp+1/sTi'
    )
    templ.block.diff_vars = [d_Kp_1_sTi_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kp_1_sTi_Kp: vf.add_const(None, name='Kp'),
        Kp_1_sTi_Ti: vf.add_const(None, name='Ti'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kp_1_sti_443_emt_template(vf=vf, name='Kp+1/sTi__443' if name is None else name)
