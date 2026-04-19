# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_shaft_i_j_k_and_pin_414_emt_template(vf: VarFactory, name: str = 'Shaft i-J-k and Pin__414') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Shaft_i_J_k_and_Pin_D_ij = vf.add_var('Shaft i-J-k and Pin__D_ij_' + name)
    Shaft_i_J_k_and_Pin_D_jj = vf.add_var('Shaft i-J-k and Pin__D_jj_' + name)
    Shaft_i_J_k_and_Pin_D_jk = vf.add_var('Shaft i-J-k and Pin__D_jk_' + name)
    Shaft_i_J_k_and_Pin_H_j = vf.add_var('Shaft i-J-k and Pin__H_j_' + name)
    Shaft_i_J_k_and_Pin_K_jk = vf.add_var('Shaft i-J-k and Pin__K_jk_' + name)
    Shaft_i_J_k_and_Pin_fnom = vf.add_var('Shaft i-J-k and Pin__fnom_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Pin = vf.add_var('Pin_' + name)
    Shaft_i_J_k_and_Pin_xdtheta_jk = vf.add_var('Shaft i-J-k and Pin__xdtheta_jk_' + name)
    Shaft_i_J_k_and_Pin_xomega_j = vf.add_var('Shaft i-J-k and Pin__xomega_j_' + name)
    omega_i = vf.add_var('omega_i_' + name)
    omega_j = vf.add_var('omega_j_' + name)
    omega_k = vf.add_var('omega_k_' + name)
    torque_ij = vf.add_var('torque_ij_' + name)
    torque_jk = vf.add_var('torque_jk_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        in_vars=[omega_k, omega_i, torque_ij, Pin],
        out_vars=[omega_j, torque_jk],
        name='Shaft i-J-k and Pin'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Shaft_i_J_k_and_Pin_K_jk: vf.add_const(None, name='K_jk'),
        Shaft_i_J_k_and_Pin_D_jk: vf.add_const(None, name='D_jk'),
        Shaft_i_J_k_and_Pin_D_ij: vf.add_const(None, name='D_ij'),
        Shaft_i_J_k_and_Pin_D_jj: vf.add_const(None, name='D_jj'),
        Shaft_i_J_k_and_Pin_H_j: vf.add_const(None, name='H_j'),
        Shaft_i_J_k_and_Pin_fnom: vf.add_const(None, name='fnom'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Shaft_i_J_k_and_Pin_xdtheta_jk: ((sym.Const(1.0) / Shaft_i_J_k_and_Pin_K_jk) * (((Pin / Shaft_i_J_k_and_Pin_xomega_j) + torque_ij) - (Shaft_i_J_k_and_Pin_D_jj * omega_j))),
        Shaft_i_J_k_and_Pin_xomega_j: omega_k,
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_shaft_i_j_k_and_pin_414_emt_template(vf=vf, name='Shaft i-J-k and Pin__414' if name is None else name)
