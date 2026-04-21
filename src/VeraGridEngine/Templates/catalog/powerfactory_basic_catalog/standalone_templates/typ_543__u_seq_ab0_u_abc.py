# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import movingavg, sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_u_seq_ab0_u_abc_543_emt_template(vf: VarFactory, name: str = 'U seq/ab0 -> U abc__543') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    U_seq_ab0_U_abc_fn = vf.add_var('U seq/ab0 -> U abc__fn_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    U_seq_ab0_U_abc_proc_movingavg_0 = vf.add_var('U seq/ab0 -> U abc__proc_movingavg_0_' + name)
    U_seq_ab0_U_abc_proc_movingavg_10 = vf.add_var('U seq/ab0 -> U abc__proc_movingavg_10_' + name)
    U_seq_ab0_U_abc_proc_movingavg_2 = vf.add_var('U seq/ab0 -> U abc__proc_movingavg_2_' + name)
    U_seq_ab0_U_abc_proc_movingavg_4 = vf.add_var('U seq/ab0 -> U abc__proc_movingavg_4_' + name)
    U_seq_ab0_U_abc_proc_movingavg_6 = vf.add_var('U seq/ab0 -> U abc__proc_movingavg_6_' + name)
    U_seq_ab0_U_abc_proc_movingavg_8 = vf.add_var('U seq/ab0 -> U abc__proc_movingavg_8_' + name)
    U_seq_ab0_U_abc_proc_select_1 = vf.add_var('U seq/ab0 -> U abc__proc_select_1_' + name)
    U_seq_ab0_U_abc_proc_select_11 = vf.add_var('U seq/ab0 -> U abc__proc_select_11_' + name)
    U_seq_ab0_U_abc_proc_select_3 = vf.add_var('U seq/ab0 -> U abc__proc_select_3_' + name)
    U_seq_ab0_U_abc_proc_select_5 = vf.add_var('U seq/ab0 -> U abc__proc_select_5_' + name)
    U_seq_ab0_U_abc_proc_select_7 = vf.add_var('U seq/ab0 -> U abc__proc_select_7_' + name)
    U_seq_ab0_U_abc_proc_select_9 = vf.add_var('U seq/ab0 -> U abc__proc_select_9_' + name)
    U_seq_ab0_U_abc_t = vf.add_var('U seq/ab0 -> U abc_t_' + name)
    U_seq_ab0_U_abc_t0 = vf.add_var('U seq/ab0 -> U abc_t0_' + name)
    U_seq_ab0_U_abc_uai = vf.add_var('U seq/ab0 -> U abc_uai_' + name)
    U_seq_ab0_U_abc_uar = vf.add_var('U seq/ab0 -> U abc_uar_' + name)
    U_seq_ab0_U_abc_ubi = vf.add_var('U seq/ab0 -> U abc_ubi_' + name)
    U_seq_ab0_U_abc_ubr = vf.add_var('U seq/ab0 -> U abc_ubr_' + name)
    U_seq_ab0_U_abc_uci = vf.add_var('U seq/ab0 -> U abc_uci_' + name)
    U_seq_ab0_U_abc_ucr = vf.add_var('U seq/ab0 -> U abc_ucr_' + name)
    glob_time = vf.add_var('glob_time_' + name)
    u0 = vf.add_var('u0_' + name)
    u0i = vf.add_var('u0i_' + name)
    u0r = vf.add_var('u0r_' + name)
    u1 = vf.add_var('u1_' + name)
    u1i = vf.add_var('u1i_' + name)
    u1r = vf.add_var('u1r_' + name)
    u2i = vf.add_var('u2i_' + name)
    u2r = vf.add_var('u2r_' + name)
    ua = vf.add_var('ua_' + name)
    uab = vf.add_var('uab_' + name)
    ub = vf.add_var('ub_' + name)
    ubc = vf.add_var('ubc_' + name)
    uc = vf.add_var('uc_' + name)
    uca = vf.add_var('uca_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (U_seq_ab0_U_abc_uar - (u1r + u0)),
            (U_seq_ab0_U_abc_uai - sym.Const(0.0)),
            (U_seq_ab0_U_abc_ubr - ((((-u1r) / sym.Const(2.0)) + ((u1i * sym.sqrt(sym.Const(3.0))) / sym.Const(2.0))) + u0)),
            (U_seq_ab0_U_abc_ubi - sym.Const(0.0)),
            (U_seq_ab0_U_abc_ucr - ((((-u1r) / sym.Const(2.0)) - ((u1i * sym.sqrt(sym.Const(3.0))) / sym.Const(2.0))) + u0)),
            (U_seq_ab0_U_abc_uci - sym.Const(0.0)),
            (ua - ((U_seq_ab0_U_abc_proc_select_1 * (sym.sqrt(sym.Const(2.0)) * sym.sqrt(((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_0))) + (U_seq_ab0_U_abc_proc_movingavg_0 * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_0)))))))) + ((sym.Const(1.0) - U_seq_ab0_U_abc_proc_select_1) * u1))),
            (ub - ((U_seq_ab0_U_abc_proc_select_3 * (sym.sqrt(sym.Const(2.0)) * sym.sqrt(((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_2))) + (U_seq_ab0_U_abc_proc_movingavg_2 * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_2)))))))) + ((sym.Const(1.0) - U_seq_ab0_U_abc_proc_select_3) * u1))),
            (uc - ((U_seq_ab0_U_abc_proc_select_5 * (sym.sqrt(sym.Const(2.0)) * sym.sqrt(((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_4))) + (U_seq_ab0_U_abc_proc_movingavg_4 * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_4)))))))) + ((sym.Const(1.0) - U_seq_ab0_U_abc_proc_select_5) * u1))),
            (uab - ((U_seq_ab0_U_abc_proc_select_7 * ((sym.sqrt(sym.Const(2.0)) / sym.sqrt(sym.Const(3.0))) * sym.sqrt(((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_6))) + (U_seq_ab0_U_abc_proc_movingavg_6 * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_6)))))))) + ((sym.Const(1.0) - U_seq_ab0_U_abc_proc_select_7) * u1))),
            (ubc - ((U_seq_ab0_U_abc_proc_select_9 * ((sym.sqrt(sym.Const(2.0)) / sym.sqrt(sym.Const(3.0))) * sym.sqrt(((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_8))) + (U_seq_ab0_U_abc_proc_movingavg_8 * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_8)))))))) + ((sym.Const(1.0) - U_seq_ab0_U_abc_proc_select_9) * u1))),
            (uca - ((U_seq_ab0_U_abc_proc_select_11 * ((sym.sqrt(sym.Const(2.0)) / sym.sqrt(sym.Const(3.0))) * sym.sqrt(((sym.Const(0.0) * sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_10))) + (U_seq_ab0_U_abc_proc_movingavg_10 * (sym.Const(1) - sym.heaviside((sym.Const(0.0) - U_seq_ab0_U_abc_proc_movingavg_10)))))))) + ((sym.Const(1.0) - U_seq_ab0_U_abc_proc_select_11) * u1))),
            (U_seq_ab0_U_abc_t - glob_time),
        ],
        algebraic_vars=[U_seq_ab0_U_abc_uar, U_seq_ab0_U_abc_uai, U_seq_ab0_U_abc_ubr, U_seq_ab0_U_abc_ubi, U_seq_ab0_U_abc_ucr, U_seq_ab0_U_abc_uci, ua, ub, uc, uab, ubc, uca, U_seq_ab0_U_abc_t],
        in_vars=[u1, u1r, u1i, u2r, u2i, u0r, u0i, u0],
        out_vars=[ua, ub, uc, uab, ubc, uca],
        name='U seq/ab0 -> U abc'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        U_seq_ab0_U_abc_fn: vf.add_const(None, name='fn'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        U_seq_ab0_U_abc_proc_movingavg_0: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_select_1: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_movingavg_2: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_select_3: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_movingavg_4: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_select_5: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_movingavg_6: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_select_7: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_movingavg_8: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_select_9: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_movingavg_10: vf.add_const(0.0, name=''),
        U_seq_ab0_U_abc_proc_select_11: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        U_seq_ab0_U_abc_t0: glob_time,
    }
    templ.block.procedural_logic = [
        movingavg((U_seq_ab0_U_abc_uar * U_seq_ab0_U_abc_uar), ((1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))) / 20.0), (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))), output=U_seq_ab0_U_abc_proc_movingavg_0),
        sampled_value(output=U_seq_ab0_U_abc_proc_select_1, source=(U_seq_ab0_U_abc_t > (U_seq_ab0_U_abc_t0 + (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))))))))),
        movingavg((U_seq_ab0_U_abc_ubr * U_seq_ab0_U_abc_ubr), ((1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))) / 20.0), (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))), output=U_seq_ab0_U_abc_proc_movingavg_2),
        sampled_value(output=U_seq_ab0_U_abc_proc_select_3, source=(U_seq_ab0_U_abc_t > (U_seq_ab0_U_abc_t0 + (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))))))))),
        movingavg((U_seq_ab0_U_abc_ucr * U_seq_ab0_U_abc_ucr), ((1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))) / 20.0), (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))), output=U_seq_ab0_U_abc_proc_movingavg_4),
        sampled_value(output=U_seq_ab0_U_abc_proc_select_5, source=(U_seq_ab0_U_abc_t > (U_seq_ab0_U_abc_t0 + (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))))))))),
        movingavg(((U_seq_ab0_U_abc_uar - U_seq_ab0_U_abc_ubr) * (U_seq_ab0_U_abc_uar - U_seq_ab0_U_abc_ubr)), ((1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))) / 20.0), (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))), output=U_seq_ab0_U_abc_proc_movingavg_6),
        sampled_value(output=U_seq_ab0_U_abc_proc_select_7, source=(U_seq_ab0_U_abc_t > (U_seq_ab0_U_abc_t0 + (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))))))))),
        movingavg(((U_seq_ab0_U_abc_ubr - U_seq_ab0_U_abc_ucr) * (U_seq_ab0_U_abc_ubr - U_seq_ab0_U_abc_ucr)), ((1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))) / 20.0), (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))), output=U_seq_ab0_U_abc_proc_movingavg_8),
        sampled_value(output=U_seq_ab0_U_abc_proc_select_9, source=(U_seq_ab0_U_abc_t > (U_seq_ab0_U_abc_t0 + (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))))))))),
        movingavg(((U_seq_ab0_U_abc_ucr - U_seq_ab0_U_abc_uar) * (U_seq_ab0_U_abc_ucr - U_seq_ab0_U_abc_uar)), ((1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))) / 20.0), (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0)))))), output=U_seq_ab0_U_abc_proc_movingavg_10),
        sampled_value(output=U_seq_ab0_U_abc_proc_select_11, source=(U_seq_ab0_U_abc_t > (U_seq_ab0_U_abc_t0 + (1.0 / ((U_seq_ab0_U_abc_fn * sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))) + (10.0 * (1 - sym.heaviside((U_seq_ab0_U_abc_fn - 10.0))))))))),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_u_seq_ab0_u_abc_543_emt_template(vf=vf, name='U seq/ab0 -> U abc__543' if name is None else name)
