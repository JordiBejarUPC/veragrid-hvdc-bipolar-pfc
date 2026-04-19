# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_sk_1_0_01s_111_emt_template(vf: VarFactory, name: str = 'sK/(1+0.01s)__111') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    sK_1_0_01s_K = vf.add_var('sK/(1+0.01s)__K_' + name)

    # --- State Variables ---
    sK_1_0_01s_x = vf.add_var('sK/(1+0.01s)__x_' + name)

    # --- Algebraic / Shared Variables ---
    sK_1_0_01s_dx = vf.add_var('sK/(1+0.01s)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_sK_1_0_01s_x = vf.add_diff_var('d_sK/(1+0.01s)__x_' + name, base_var=sK_1_0_01s_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            sK_1_0_01s_dx,
        ],
        state_vars=[sK_1_0_01s_x],
        algebraic_eqs=[
            (sK_1_0_01s_dx - ((yi - sK_1_0_01s_x) / sym.Const(0.01))),
            (yo - (sK_1_0_01s_K * sK_1_0_01s_dx)),
        ],
        algebraic_vars=[sK_1_0_01s_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='sK/(1+0.01s)'
    )
    templ.block.diff_vars = [d_sK_1_0_01s_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        sK_1_0_01s_K: vf.add_const(None, name='K'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_sk_1_0_01s_111_emt_template(vf=vf, name='sK/(1+0.01s)__111' if name is None else name)
