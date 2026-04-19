# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_shaft_i_j_426_emt_template(vf: VarFactory, name: str = 'Shaft i-J__426') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Shaft_i_J_D_ji = vf.add_var('Shaft i-J__D_ji_' + name)
    Shaft_i_J_D_jj = vf.add_var('Shaft i-J__D_jj_' + name)
    Shaft_i_J_H_j = vf.add_var('Shaft i-J__H_j_' + name)
    Shaft_i_J_K_ji = vf.add_var('Shaft i-J__K_ji_' + name)
    Shaft_i_J_fnom = vf.add_var('Shaft i-J__fnom_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Shaft_i_J_xdtheta_ji = vf.add_var('Shaft i-J__xdtheta_ji_' + name)
    Shaft_i_J_xomega_j = vf.add_var('Shaft i-J__xomega_j_' + name)
    omega_i = vf.add_var('omega_i_' + name)
    torque_ji = vf.add_var('torque_ji_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        in_vars=[omega_i],
        out_vars=[torque_ji],
        name='Shaft i-J'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Shaft_i_J_K_ji: vf.add_const(None, name='K_ji'),
        Shaft_i_J_D_ji: vf.add_const(None, name='D_ji'),
        Shaft_i_J_D_jj: vf.add_const(None, name='D_jj'),
        Shaft_i_J_H_j: vf.add_const(None, name='H_j'),
        Shaft_i_J_fnom: vf.add_const(None, name='fnom'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Shaft_i_J_xdtheta_ji: ((sym.Const(1.0) / Shaft_i_J_K_ji) * ((-Shaft_i_J_D_jj) * Shaft_i_J_xomega_j)),
        Shaft_i_J_xomega_j: omega_i,
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_shaft_i_j_426_emt_template(vf=vf, name='Shaft i-J__426' if name is None else name)
