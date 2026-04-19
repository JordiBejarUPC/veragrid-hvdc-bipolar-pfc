# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_st_kst_p_p_434_emt_template(vf: VarFactory, name: str = '(1+sT)/KsT {p}[(p__434') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sT_KsT_p_p_K = vf.add_var('(1+sT)/KsT {p}[(p__K_' + name)
    v_1_sT_KsT_p_p_T = vf.add_var('(1+sT)/KsT {p}[(p__T_' + name)
    v_1_sT_KsT_p_p_y_max = vf.add_var('(1+sT)/KsT {p}[(p__y_max_' + name)
    v_1_sT_KsT_p_p_y_min = vf.add_var('(1+sT)/KsT {p}[(p__y_min_' + name)
    v_1_sT_KsT_p_p_ylim = vf.add_var('(1+sT)/KsT {p}[(p__ylim_' + name)

    # --- State Variables ---
    v_1_sT_KsT_p_p_x = vf.add_var('(1+sT)/KsT {p}[(p__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sT_KsT_p_p_dx = vf.add_var('(1+sT)/KsT {p}[(p_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sT_KsT_p_p_x = vf.add_diff_var('d_(1+sT)/KsT {p}[(p__x_' + name, base_var=v_1_sT_KsT_p_p_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (((-v_1_sT_KsT_p_p_ylim) + ((v_1_sT_KsT_p_p_dx - (-v_1_sT_KsT_p_p_ylim)) * sym.heaviside((v_1_sT_KsT_p_p_dx - (-v_1_sT_KsT_p_p_ylim))))) - ((v_1_sT_KsT_p_p_dx - v_1_sT_KsT_p_p_ylim) * sym.heaviside((v_1_sT_KsT_p_p_dx - v_1_sT_KsT_p_p_ylim)))),
        ],
        state_vars=[v_1_sT_KsT_p_p_x],
        algebraic_eqs=[
            (v_1_sT_KsT_p_p_dx - (yi / (v_1_sT_KsT_p_p_K * v_1_sT_KsT_p_p_T))),
            (yo - ((v_1_sT_KsT_p_p_y_min + (((((v_1_sT_KsT_p_p_y_min + ((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_min) * sym.heaviside((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_min)))) - ((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_max) * sym.heaviside((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_max)))) + (yi / v_1_sT_KsT_p_p_K)) - v_1_sT_KsT_p_p_y_min) * sym.heaviside(((((v_1_sT_KsT_p_p_y_min + ((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_min) * sym.heaviside((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_min)))) - ((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_max) * sym.heaviside((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_max)))) + (yi / v_1_sT_KsT_p_p_K)) - v_1_sT_KsT_p_p_y_min)))) - (((((v_1_sT_KsT_p_p_y_min + ((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_min) * sym.heaviside((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_min)))) - ((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_max) * sym.heaviside((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_max)))) + (yi / v_1_sT_KsT_p_p_K)) - v_1_sT_KsT_p_p_y_max) * sym.heaviside(((((v_1_sT_KsT_p_p_y_min + ((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_min) * sym.heaviside((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_min)))) - ((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_max) * sym.heaviside((v_1_sT_KsT_p_p_x - v_1_sT_KsT_p_p_y_max)))) + (yi / v_1_sT_KsT_p_p_K)) - v_1_sT_KsT_p_p_y_max))))),
        ],
        algebraic_vars=[v_1_sT_KsT_p_p_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+sT)/KsT {p}[(p'
    )
    templ.block.diff_vars = [d_1_sT_KsT_p_p_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sT_KsT_p_p_K: vf.add_const(None, name='K'),
        v_1_sT_KsT_p_p_T: vf.add_const(None, name='T'),
        v_1_sT_KsT_p_p_ylim: vf.add_const(None, name='ylim'),
        v_1_sT_KsT_p_p_y_max: vf.add_const(None, name='y_max'),
        v_1_sT_KsT_p_p_y_min: vf.add_const(None, name='y_min'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_st_kst_p_p_434_emt_template(vf=vf, name='(1+sT)/KsT {p}[(p__434' if name is None else name)
