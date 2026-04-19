# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_a23_1_a11_a13a21_a23_stw_1_a11stw_309_emt_template(vf: VarFactory, name: str = 'a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__309') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    a23_1_a11_a13a21_a23_sTw_1_a11sTw_Tw = vf.add_var('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__Tw_' + name)
    a23_1_a11_a13a21_a23_sTw_1_a11sTw_a11 = vf.add_var('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__a11_' + name)
    a23_1_a11_a13a21_a23_sTw_1_a11sTw_a13 = vf.add_var('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__a13_' + name)
    a23_1_a11_a13a21_a23_sTw_1_a11sTw_a21 = vf.add_var('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__a21_' + name)
    a23_1_a11_a13a21_a23_sTw_1_a11sTw_a23 = vf.add_var('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__a23_' + name)

    # --- State Variables ---
    a23_1_a11_a13a21_a23_sTw_1_a11sTw_x = vf.add_var('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__x_' + name)

    # --- Algebraic / Shared Variables ---
    a23_1_a11_a13a21_a23_sTw_1_a11sTw_Ta = vf.add_var('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)_Ta_' + name)
    a23_1_a11_a13a21_a23_sTw_1_a11sTw_Tb = vf.add_var('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)_Tb_' + name)
    a23_1_a11_a13a21_a23_sTw_1_a11sTw_dx = vf.add_var('a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_a23_1_a11_a13a21_a23_sTw_1_a11sTw_x = vf.add_diff_var('d_a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__x_' + name, base_var=a23_1_a11_a13a21_a23_sTw_1_a11sTw_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            a23_1_a11_a13a21_a23_sTw_1_a11sTw_dx,
        ],
        state_vars=[a23_1_a11_a13a21_a23_sTw_1_a11sTw_x],
        algebraic_eqs=[
            (a23_1_a11_a13a21_a23_sTw_1_a11sTw_dx - ((yi - a23_1_a11_a13a21_a23_sTw_1_a11sTw_x) / a23_1_a11_a13a21_a23_sTw_1_a11sTw_Ta)),
            (yo - (a23_1_a11_a13a21_a23_sTw_1_a11sTw_a23 * (a23_1_a11_a13a21_a23_sTw_1_a11sTw_x + (a23_1_a11_a13a21_a23_sTw_1_a11sTw_Tb * a23_1_a11_a13a21_a23_sTw_1_a11sTw_dx)))),
        ],
        algebraic_vars=[a23_1_a11_a13a21_a23_sTw_1_a11sTw_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)'
    )
    templ.block.diff_vars = [d_a23_1_a11_a13a21_a23_sTw_1_a11sTw_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        a23_1_a11_a13a21_a23_sTw_1_a11sTw_a11: vf.add_const(None, name='a11'),
        a23_1_a11_a13a21_a23_sTw_1_a11sTw_a13: vf.add_const(None, name='a13'),
        a23_1_a11_a13a21_a23_sTw_1_a11sTw_a21: vf.add_const(None, name='a21'),
        a23_1_a11_a13a21_a23_sTw_1_a11sTw_a23: vf.add_const(None, name='a23'),
        a23_1_a11_a13a21_a23_sTw_1_a11sTw_Tw: vf.add_const(None, name='Tw'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        a23_1_a11_a13a21_a23_sTw_1_a11sTw_Tb: ((a23_1_a11_a13a21_a23_sTw_1_a11sTw_a11 - ((a23_1_a11_a13a21_a23_sTw_1_a11sTw_a13 * a23_1_a11_a13a21_a23_sTw_1_a11sTw_a21) / a23_1_a11_a13a21_a23_sTw_1_a11sTw_a23)) * a23_1_a11_a13a21_a23_sTw_1_a11sTw_Tw),
        a23_1_a11_a13a21_a23_sTw_1_a11sTw_Ta: (a23_1_a11_a13a21_a23_sTw_1_a11sTw_a11 * a23_1_a11_a13a21_a23_sTw_1_a11sTw_Tw),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_a23_1_a11_a13a21_a23_stw_1_a11stw_309_emt_template(vf=vf, name='a23(1+(a11-a13a21/a23)sTw)/(1+a11sTw)__309' if name is None else name)
