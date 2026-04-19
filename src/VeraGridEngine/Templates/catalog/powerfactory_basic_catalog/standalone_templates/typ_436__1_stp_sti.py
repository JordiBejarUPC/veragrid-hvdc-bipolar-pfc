# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_stp_sti_436_emt_template(vf: VarFactory, name: str = '(1+sTp)/sTi__436') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sTp_sTi_Ti = vf.add_var('(1+sTp)/sTi__Ti_' + name)
    v_1_sTp_sTi_Tp = vf.add_var('(1+sTp)/sTi__Tp_' + name)
    v_1_sTp_sTi_y_max = vf.add_var('(1+sTp)/sTi__y_max_' + name)

    # --- State Variables ---
    v_1_sTp_sTi_x = vf.add_var('(1+sTp)/sTi__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sTp_sTi_dx = vf.add_var('(1+sTp)/sTi_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sTp_sTi_x = vf.add_diff_var('d_(1+sTp)/sTi__x_' + name, base_var=v_1_sTp_sTi_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_sTp_sTi_dx,
        ],
        state_vars=[v_1_sTp_sTi_x],
        algebraic_eqs=[
            (v_1_sTp_sTi_dx - (yi / v_1_sTp_sTi_Ti)),
            (yo - (((-sym.Const(999999999999.0)) + (((((yi * v_1_sTp_sTi_Tp) / v_1_sTp_sTi_Ti) + (((-sym.Const(999999999999.0)) + ((v_1_sTp_sTi_x - (-sym.Const(999999999999.0))) * sym.heaviside((v_1_sTp_sTi_x - (-sym.Const(999999999999.0)))))) - ((v_1_sTp_sTi_x - v_1_sTp_sTi_y_max) * sym.heaviside((v_1_sTp_sTi_x - v_1_sTp_sTi_y_max))))) - (-sym.Const(999999999999.0))) * sym.heaviside(((((yi * v_1_sTp_sTi_Tp) / v_1_sTp_sTi_Ti) + (((-sym.Const(999999999999.0)) + ((v_1_sTp_sTi_x - (-sym.Const(999999999999.0))) * sym.heaviside((v_1_sTp_sTi_x - (-sym.Const(999999999999.0)))))) - ((v_1_sTp_sTi_x - v_1_sTp_sTi_y_max) * sym.heaviside((v_1_sTp_sTi_x - v_1_sTp_sTi_y_max))))) - (-sym.Const(999999999999.0)))))) - (((((yi * v_1_sTp_sTi_Tp) / v_1_sTp_sTi_Ti) + (((-sym.Const(999999999999.0)) + ((v_1_sTp_sTi_x - (-sym.Const(999999999999.0))) * sym.heaviside((v_1_sTp_sTi_x - (-sym.Const(999999999999.0)))))) - ((v_1_sTp_sTi_x - v_1_sTp_sTi_y_max) * sym.heaviside((v_1_sTp_sTi_x - v_1_sTp_sTi_y_max))))) - v_1_sTp_sTi_y_max) * sym.heaviside(((((yi * v_1_sTp_sTi_Tp) / v_1_sTp_sTi_Ti) + (((-sym.Const(999999999999.0)) + ((v_1_sTp_sTi_x - (-sym.Const(999999999999.0))) * sym.heaviside((v_1_sTp_sTi_x - (-sym.Const(999999999999.0)))))) - ((v_1_sTp_sTi_x - v_1_sTp_sTi_y_max) * sym.heaviside((v_1_sTp_sTi_x - v_1_sTp_sTi_y_max))))) - v_1_sTp_sTi_y_max))))),
        ],
        algebraic_vars=[v_1_sTp_sTi_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+sTp)/sTi'
    )
    templ.block.diff_vars = [d_1_sTp_sTi_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sTp_sTi_Ti: vf.add_const(None, name='Ti'),
        v_1_sTp_sTi_Tp: vf.add_const(None, name='Tp'),
        v_1_sTp_sTi_y_max: vf.add_const(None, name='y_max'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_stp_sti_436_emt_template(vf=vf, name='(1+sTp)/sTi__436' if name is None else name)
