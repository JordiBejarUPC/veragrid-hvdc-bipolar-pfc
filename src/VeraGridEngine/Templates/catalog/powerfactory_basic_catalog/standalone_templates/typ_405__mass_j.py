# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_mass_j_405_emt_template(vf: VarFactory, name: str = 'Mass_J__405') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Mass_J_J = vf.add_var('Mass_J__J_' + name)

    # --- State Variables ---
    Mass_J_xomega = vf.add_var('Mass_J__xomega_' + name)

    # --- Algebraic / Shared Variables ---
    M1 = vf.add_var('M1_' + name)
    M2 = vf.add_var('M2_' + name)
    omega = vf.add_var('omega_' + name)

    # --- Derivative Variables ---
    d_Mass_J_xomega = vf.add_diff_var('d_Mass_J__xomega_' + name, base_var=Mass_J_xomega)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((M1 - M2) / Mass_J_J),
        ],
        state_vars=[Mass_J_xomega],
        algebraic_eqs=[
            (omega - Mass_J_xomega),
        ],
        algebraic_vars=[omega],
        in_vars=[M1, M2],
        out_vars=[omega],
        name='Mass_J'
    )
    templ.block.diff_vars = [d_Mass_J_xomega]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Mass_J_J: vf.add_const(None, name='J'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_mass_j_405_emt_template(vf=vf, name='Mass_J__405' if name is None else name)
