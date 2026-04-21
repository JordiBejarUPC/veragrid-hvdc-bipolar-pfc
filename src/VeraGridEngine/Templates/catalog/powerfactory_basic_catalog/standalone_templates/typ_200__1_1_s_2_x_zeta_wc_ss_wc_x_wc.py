# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_200_emt_template(vf: VarFactory, name: str = '1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__200') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_wc = vf.add_var('1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__wc_' + name)
    v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_zeta = vf.add_var('1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__zeta_' + name)

    # --- State Variables ---
    v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x1 = vf.add_var('1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__x1_' + name)
    v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x2 = vf.add_var('1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__x2_' + name)

    # --- Algebraic / Shared Variables ---
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x1 = vf.add_diff_var('d_1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__x1_' + name, base_var=v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x1)
    d_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x2 = vf.add_diff_var('d_1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__x2_' + name, base_var=v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x2,
            ((((v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_wc * v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_wc) * yi) - (((sym.Const(2.0) * v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_zeta) * v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_wc) * v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x2)) - ((v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_wc * v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_wc) * v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x1)),
        ],
        state_vars=[v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x1, v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x2],
        algebraic_eqs=[
            (yo - v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x1),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='1/(1+s(2 x zeta)/wc+ ss/(wc x wc))'
    )
    templ.block.diff_vars = [d_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x1, d_1_1_s_2_x_zeta_wc_ss_wc_x_wc_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_wc: vf.add_const(None, name='wc'),
        v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_zeta: vf.add_const(None, name='zeta'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_1_s_2_x_zeta_wc_ss_wc_x_wc_200_emt_template(vf=vf, name='1/(1+s(2 x zeta)/wc+ ss/(wc x wc))__200' if name is None else name)
