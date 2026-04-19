# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_spring_432_emt_template(vf: VarFactory, name: str = 'Spring__432') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Spring_D = vf.add_var('Spring__D_' + name)
    Spring_K = vf.add_var('Spring__K_' + name)

    # --- State Variables ---
    Spring_xphi = vf.add_var('Spring__xphi_' + name)

    # --- Algebraic / Shared Variables ---
    M = vf.add_var('M_' + name)
    Spring_dxphi = vf.add_var('Spring_dxphi_' + name)
    omega1 = vf.add_var('omega1_' + name)
    omega2 = vf.add_var('omega2_' + name)

    # --- Derivative Variables ---
    d_Spring_xphi = vf.add_diff_var('d_Spring__xphi_' + name, base_var=Spring_xphi)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (Spring_dxphi * Spring_K),
        ],
        state_vars=[Spring_xphi],
        algebraic_eqs=[
            (Spring_dxphi - (omega1 - omega2)),
            (M - (Spring_xphi + (Spring_D * Spring_dxphi))),
        ],
        algebraic_vars=[Spring_dxphi, M],
        in_vars=[omega1, omega2],
        out_vars=[M],
        name='Spring'
    )
    templ.block.diff_vars = [d_Spring_xphi]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Spring_K: vf.add_const(None, name='K'),
        Spring_D: vf.add_const(None, name='D'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_spring_432_emt_template(vf=vf, name='Spring__432' if name is None else name)
