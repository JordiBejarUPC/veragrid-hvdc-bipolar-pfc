# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_h0w0_q_s_w0_2_sw0_q_s_2_117_emt_template(vf: VarFactory, name: str = '(H0w0/Q)s/(w0^2+sw0/Q+s^2)__117') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    H0w0_Q_s_w0_2_sw0_Q_s_2_Fhigh = vf.add_var('(H0w0/Q)s/(w0^2+sw0/Q+s^2)__Fhigh_' + name)
    H0w0_Q_s_w0_2_sw0_Q_s_2_Flow = vf.add_var('(H0w0/Q)s/(w0^2+sw0/Q+s^2)__Flow_' + name)
    H0w0_Q_s_w0_2_sw0_Q_s_2_H0 = vf.add_var('(H0w0/Q)s/(w0^2+sw0/Q+s^2)__H0_' + name)

    # --- State Variables ---
    H0w0_Q_s_w0_2_sw0_Q_s_2_x1 = vf.add_var('(H0w0/Q)s/(w0^2+sw0/Q+s^2)__x1_' + name)
    H0w0_Q_s_w0_2_sw0_Q_s_2_x2 = vf.add_var('(H0w0/Q)s/(w0^2+sw0/Q+s^2)__x2_' + name)

    # --- Algebraic / Shared Variables ---
    H0w0_Q_s_w0_2_sw0_Q_s_2_F0 = vf.add_var('(H0w0/Q)s/(w0^2+sw0/Q+s^2)_F0_' + name)
    H0w0_Q_s_w0_2_sw0_Q_s_2_Q = vf.add_var('(H0w0/Q)s/(w0^2+sw0/Q+s^2)_Q_' + name)
    H0w0_Q_s_w0_2_sw0_Q_s_2_w0 = vf.add_var('(H0w0/Q)s/(w0^2+sw0/Q+s^2)_w0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_H0w0_Q_s_w0_2_sw0_Q_s_2_x1 = vf.add_diff_var('d_(H0w0/Q)s/(w0^2+sw0/Q+s^2)__x1_' + name, base_var=H0w0_Q_s_w0_2_sw0_Q_s_2_x1)
    d_H0w0_Q_s_w0_2_sw0_Q_s_2_x2 = vf.add_diff_var('d_(H0w0/Q)s/(w0^2+sw0/Q+s^2)__x2_' + name, base_var=H0w0_Q_s_w0_2_sw0_Q_s_2_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            H0w0_Q_s_w0_2_sw0_Q_s_2_x2,
            ((yi - ((H0w0_Q_s_w0_2_sw0_Q_s_2_w0 / H0w0_Q_s_w0_2_sw0_Q_s_2_Q) * H0w0_Q_s_w0_2_sw0_Q_s_2_x2)) - ((H0w0_Q_s_w0_2_sw0_Q_s_2_w0 * H0w0_Q_s_w0_2_sw0_Q_s_2_w0) * H0w0_Q_s_w0_2_sw0_Q_s_2_x1)),
        ],
        state_vars=[H0w0_Q_s_w0_2_sw0_Q_s_2_x1, H0w0_Q_s_w0_2_sw0_Q_s_2_x2],
        algebraic_eqs=[
            (yo - (((H0w0_Q_s_w0_2_sw0_Q_s_2_H0 / H0w0_Q_s_w0_2_sw0_Q_s_2_Q) * H0w0_Q_s_w0_2_sw0_Q_s_2_w0) * H0w0_Q_s_w0_2_sw0_Q_s_2_x2)),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(H0w0/Q)s/(w0^2+sw0/Q+s^2)'
    )
    templ.block.diff_vars = [d_H0w0_Q_s_w0_2_sw0_Q_s_2_x1, d_H0w0_Q_s_w0_2_sw0_Q_s_2_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        H0w0_Q_s_w0_2_sw0_Q_s_2_Flow: vf.add_const(None, name='Flow'),
        H0w0_Q_s_w0_2_sw0_Q_s_2_Fhigh: vf.add_const(None, name='Fhigh'),
        H0w0_Q_s_w0_2_sw0_Q_s_2_H0: vf.add_const(None, name='H0'),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        yo: (((H0w0_Q_s_w0_2_sw0_Q_s_2_H0 / H0w0_Q_s_w0_2_sw0_Q_s_2_Q) * H0w0_Q_s_w0_2_sw0_Q_s_2_w0) * H0w0_Q_s_w0_2_sw0_Q_s_2_x2),
        H0w0_Q_s_w0_2_sw0_Q_s_2_F0: sym.sqrt((H0w0_Q_s_w0_2_sw0_Q_s_2_Fhigh * H0w0_Q_s_w0_2_sw0_Q_s_2_Flow)),
        H0w0_Q_s_w0_2_sw0_Q_s_2_w0: (H0w0_Q_s_w0_2_sw0_Q_s_2_F0 * (sym.Const(2.0) * sym.Const(3.141592653589793))),
        H0w0_Q_s_w0_2_sw0_Q_s_2_Q: (H0w0_Q_s_w0_2_sw0_Q_s_2_F0 / (H0w0_Q_s_w0_2_sw0_Q_s_2_Fhigh - H0w0_Q_s_w0_2_sw0_Q_s_2_Flow)),
        H0w0_Q_s_w0_2_sw0_Q_s_2_x1: (yi / ((((sym.Const(4.0) * sym.Const(3.141592653589793)) * sym.Const(3.141592653589793)) * H0w0_Q_s_w0_2_sw0_Q_s_2_F0) * H0w0_Q_s_w0_2_sw0_Q_s_2_F0)),
        H0w0_Q_s_w0_2_sw0_Q_s_2_x2: vf.add_const(0.0, name=''),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_h0w0_q_s_w0_2_sw0_q_s_2_117_emt_template(vf=vf, name='(H0w0/Q)s/(w0^2+sw0/Q+s^2)__117' if name is None else name)
