# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_inverse_park_transform_dq_537_emt_template(vf: VarFactory, name: str = 'Inverse Park transform (dq)__537') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    alpha = vf.add_var('alpha_' + name)
    beta = vf.add_var('beta_' + name)
    cosphi = vf.add_var('cosphi_' + name)
    d = vf.add_var('d_' + name)
    q = vf.add_var('q_' + name)
    sinphi = vf.add_var('sinphi_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (alpha - ((cosphi * d) - (sinphi * q))),
            (beta - ((sinphi * d) + (cosphi * q))),
        ],
        algebraic_vars=[alpha, beta],
        in_vars=[d, q, cosphi, sinphi],
        out_vars=[alpha, beta],
        name='Inverse Park transform (dq)'
    )
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_inverse_park_transform_dq_537_emt_template(vf=vf, name='Inverse Park transform (dq)__537' if name is None else name)
