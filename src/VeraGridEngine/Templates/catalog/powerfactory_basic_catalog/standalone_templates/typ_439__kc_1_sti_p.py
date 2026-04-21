# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_kc_1_sti_p_439_emt_template(vf: VarFactory, name: str = 'Kc+1/sTi [(p__439') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Kc_1_sTi_p_ControlTuning = vf.add_var('Kc+1/sTi [(p__ControlTuning_' + name)
    Kc_1_sTi_p_K_p = vf.add_var('Kc+1/sTi [(p__K_p_' + name)
    Kc_1_sTi_p_T_rise = vf.add_var('Kc+1/sTi [(p__T_rise_' + name)
    Kc_1_sTi_p_theta_p = vf.add_var('Kc+1/sTi [(p__theta_p_' + name)
    Kc_1_sTi_p_y_max = vf.add_var('Kc+1/sTi [(p__y_max_' + name)
    Kc_1_sTi_p_y_min = vf.add_var('Kc+1/sTi [(p__y_min_' + name)

    # --- State Variables ---
    Kc_1_sTi_p_x = vf.add_var('Kc+1/sTi [(p__x_' + name)

    # --- Algebraic / Shared Variables ---
    Kc_1_sTi_p_Kc = vf.add_var('Kc+1/sTi [(p_Kc_' + name)
    Kc_1_sTi_p_T_p = vf.add_var('Kc+1/sTi [(p_T_p_' + name)
    Kc_1_sTi_p_Ti = vf.add_var('Kc+1/sTi [(p_Ti_' + name)
    Kc_1_sTi_p_proc_selfix_0 = vf.add_var('Kc+1/sTi [(p__proc_selfix_0_' + name)
    Kc_1_sTi_p_proc_selfix_1 = vf.add_var('Kc+1/sTi [(p__proc_selfix_1_' + name)
    Kc_1_sTi_p_proc_selfix_10 = vf.add_var('Kc+1/sTi [(p__proc_selfix_10_' + name)
    Kc_1_sTi_p_proc_selfix_2 = vf.add_var('Kc+1/sTi [(p__proc_selfix_2_' + name)
    Kc_1_sTi_p_proc_selfix_3 = vf.add_var('Kc+1/sTi [(p__proc_selfix_3_' + name)
    Kc_1_sTi_p_proc_selfix_4 = vf.add_var('Kc+1/sTi [(p__proc_selfix_4_' + name)
    Kc_1_sTi_p_proc_selfix_5 = vf.add_var('Kc+1/sTi [(p__proc_selfix_5_' + name)
    Kc_1_sTi_p_proc_selfix_6 = vf.add_var('Kc+1/sTi [(p__proc_selfix_6_' + name)
    Kc_1_sTi_p_proc_selfix_7 = vf.add_var('Kc+1/sTi [(p__proc_selfix_7_' + name)
    Kc_1_sTi_p_proc_selfix_8 = vf.add_var('Kc+1/sTi [(p__proc_selfix_8_' + name)
    Kc_1_sTi_p_proc_selfix_9 = vf.add_var('Kc+1/sTi [(p__proc_selfix_9_' + name)
    Kc_1_sTi_p_tau_c = vf.add_var('Kc+1/sTi [(p_tau_c_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_Kc_1_sTi_p_x = vf.add_diff_var('d_Kc+1/sTi [(p__x_' + name, base_var=Kc_1_sTi_p_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((sym.Const(1.0) / Kc_1_sTi_p_Ti) * yi),
        ],
        state_vars=[Kc_1_sTi_p_x],
        algebraic_eqs=[
            (yo - ((Kc_1_sTi_p_y_min + ((((Kc_1_sTi_p_Kc * yi) + ((Kc_1_sTi_p_y_min + ((Kc_1_sTi_p_x - Kc_1_sTi_p_y_min) * sym.heaviside((Kc_1_sTi_p_x - Kc_1_sTi_p_y_min)))) - ((Kc_1_sTi_p_x - Kc_1_sTi_p_y_max) * sym.heaviside((Kc_1_sTi_p_x - Kc_1_sTi_p_y_max))))) - Kc_1_sTi_p_y_min) * sym.heaviside((((Kc_1_sTi_p_Kc * yi) + ((Kc_1_sTi_p_y_min + ((Kc_1_sTi_p_x - Kc_1_sTi_p_y_min) * sym.heaviside((Kc_1_sTi_p_x - Kc_1_sTi_p_y_min)))) - ((Kc_1_sTi_p_x - Kc_1_sTi_p_y_max) * sym.heaviside((Kc_1_sTi_p_x - Kc_1_sTi_p_y_max))))) - Kc_1_sTi_p_y_min)))) - ((((Kc_1_sTi_p_Kc * yi) + ((Kc_1_sTi_p_y_min + ((Kc_1_sTi_p_x - Kc_1_sTi_p_y_min) * sym.heaviside((Kc_1_sTi_p_x - Kc_1_sTi_p_y_min)))) - ((Kc_1_sTi_p_x - Kc_1_sTi_p_y_max) * sym.heaviside((Kc_1_sTi_p_x - Kc_1_sTi_p_y_max))))) - Kc_1_sTi_p_y_max) * sym.heaviside((((Kc_1_sTi_p_Kc * yi) + ((Kc_1_sTi_p_y_min + ((Kc_1_sTi_p_x - Kc_1_sTi_p_y_min) * sym.heaviside((Kc_1_sTi_p_x - Kc_1_sTi_p_y_min)))) - ((Kc_1_sTi_p_x - Kc_1_sTi_p_y_max) * sym.heaviside((Kc_1_sTi_p_x - Kc_1_sTi_p_y_max))))) - Kc_1_sTi_p_y_max))))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='Kc+1/sTi [(p'
    )
    templ.block.diff_vars = [d_Kc_1_sTi_p_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        Kc_1_sTi_p_K_p: vf.add_const(None, name='K_p'),
        Kc_1_sTi_p_T_rise: vf.add_const(None, name='T_rise'),
        Kc_1_sTi_p_theta_p: vf.add_const(None, name='theta_p'),
        Kc_1_sTi_p_ControlTuning: vf.add_const(None, name='ControlTuning'),
        Kc_1_sTi_p_y_max: vf.add_const(None, name='y_max'),
        Kc_1_sTi_p_y_min: vf.add_const(None, name='y_min'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Kc_1_sTi_p_proc_selfix_0: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_1: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_2: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_3: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_4: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_5: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_6: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_7: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_8: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_9: vf.add_const(0.0, name=''),
        Kc_1_sTi_p_proc_selfix_10: vf.add_const(0.0, name=''),
    }
    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        Kc_1_sTi_p_T_p: (Kc_1_sTi_p_T_rise / sym.Const(2.197)),
        Kc_1_sTi_p_tau_c: ((Kc_1_sTi_p_proc_selfix_2 * (((sym.Const(0.1) * Kc_1_sTi_p_T_p) * sym.heaviside(((sym.Const(0.1) * Kc_1_sTi_p_T_p) - (sym.Const(0.8) * Kc_1_sTi_p_theta_p)))) + ((sym.Const(0.8) * Kc_1_sTi_p_theta_p) * (sym.Const(1) - sym.heaviside(((sym.Const(0.1) * Kc_1_sTi_p_T_p) - (sym.Const(0.8) * Kc_1_sTi_p_theta_p))))))) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_2) * ((Kc_1_sTi_p_proc_selfix_1 * (((sym.Const(1.0) * Kc_1_sTi_p_T_p) * sym.heaviside(((sym.Const(1.0) * Kc_1_sTi_p_T_p) - (sym.Const(8.0) * Kc_1_sTi_p_theta_p)))) + ((sym.Const(8.0) * Kc_1_sTi_p_theta_p) * (sym.Const(1) - sym.heaviside(((sym.Const(1.0) * Kc_1_sTi_p_T_p) - (sym.Const(8.0) * Kc_1_sTi_p_theta_p))))))) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_1) * ((Kc_1_sTi_p_proc_selfix_0 * (((sym.Const(10.0) * Kc_1_sTi_p_T_p) * sym.heaviside(((sym.Const(10.0) * Kc_1_sTi_p_T_p) - (sym.Const(80.0) * Kc_1_sTi_p_theta_p)))) + ((sym.Const(80.0) * Kc_1_sTi_p_theta_p) * (sym.Const(1) - sym.heaviside(((sym.Const(10.0) * Kc_1_sTi_p_T_p) - (sym.Const(80.0) * Kc_1_sTi_p_theta_p))))))) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_0) * sym.Const(0.0))))))),
        Kc_1_sTi_p_Kc: ((Kc_1_sTi_p_proc_selfix_6 * (((sym.Const(1.0) / Kc_1_sTi_p_K_p) * Kc_1_sTi_p_T_p) / (Kc_1_sTi_p_theta_p + Kc_1_sTi_p_tau_c))) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_6) * ((Kc_1_sTi_p_proc_selfix_5 * (((sym.Const(1.0) / Kc_1_sTi_p_K_p) * Kc_1_sTi_p_T_p) / (Kc_1_sTi_p_theta_p + Kc_1_sTi_p_tau_c))) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_5) * ((Kc_1_sTi_p_proc_selfix_4 * (((sym.Const(1.0) / Kc_1_sTi_p_K_p) * Kc_1_sTi_p_T_p) / (Kc_1_sTi_p_theta_p + Kc_1_sTi_p_tau_c))) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_4) * ((Kc_1_sTi_p_proc_selfix_3 * ((sym.Const(0.586) / Kc_1_sTi_p_K_p) * ((Kc_1_sTi_p_T_p / ((Kc_1_sTi_p_theta_p * sym.heaviside((Kc_1_sTi_p_theta_p - sym.Const(1e-06)))) + (sym.Const(1e-06) * (sym.Const(1) - sym.heaviside((Kc_1_sTi_p_theta_p - sym.Const(1e-06))))))) ** sym.Const(0.916)))) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_3) * ((sym.Const(0.859) / Kc_1_sTi_p_K_p) * ((Kc_1_sTi_p_T_p / ((Kc_1_sTi_p_theta_p * sym.heaviside((Kc_1_sTi_p_theta_p - sym.Const(1e-06)))) + (sym.Const(1e-06) * (sym.Const(1) - sym.heaviside((Kc_1_sTi_p_theta_p - sym.Const(1e-06))))))) ** sym.Const(0.977))))))))))),
        Kc_1_sTi_p_Ti: ((Kc_1_sTi_p_proc_selfix_10 * Kc_1_sTi_p_T_p) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_10) * ((Kc_1_sTi_p_proc_selfix_9 * Kc_1_sTi_p_T_p) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_9) * ((Kc_1_sTi_p_proc_selfix_8 * Kc_1_sTi_p_T_p) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_8) * ((Kc_1_sTi_p_proc_selfix_7 * (Kc_1_sTi_p_T_p / (sym.Const(1.03) - (sym.Const(0.165) * (((Kc_1_sTi_p_theta_p * sym.heaviside((Kc_1_sTi_p_theta_p - sym.Const(1e-06)))) + (sym.Const(1e-06) * (sym.Const(1) - sym.heaviside((Kc_1_sTi_p_theta_p - sym.Const(1e-06)))))) / Kc_1_sTi_p_T_p))))) + ((sym.Const(1.0) - Kc_1_sTi_p_proc_selfix_7) * ((Kc_1_sTi_p_T_p / sym.Const(0.674)) * ((((Kc_1_sTi_p_theta_p * sym.heaviside((Kc_1_sTi_p_theta_p - sym.Const(1e-06)))) + (sym.Const(1e-06) * (sym.Const(1) - sym.heaviside((Kc_1_sTi_p_theta_p - sym.Const(1e-06)))))) / Kc_1_sTi_p_T_p) ** sym.Const(0.68))))))))))),
    }
    templ.block.procedural_logic = [
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=3.0), output=Kc_1_sTi_p_proc_selfix_0),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=2.0), output=Kc_1_sTi_p_proc_selfix_1),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=1.0), output=Kc_1_sTi_p_proc_selfix_2),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=4.0), output=Kc_1_sTi_p_proc_selfix_3),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=3.0), output=Kc_1_sTi_p_proc_selfix_4),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=2.0), output=Kc_1_sTi_p_proc_selfix_5),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=1.0), output=Kc_1_sTi_p_proc_selfix_6),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=4.0), output=Kc_1_sTi_p_proc_selfix_7),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=3.0), output=Kc_1_sTi_p_proc_selfix_8),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=2.0), output=Kc_1_sTi_p_proc_selfix_9),
        selfix(sym.Comparison(lhs=Kc_1_sTi_p_ControlTuning, op=sym.CmpOp.EQ, rhs=1.0), output=Kc_1_sTi_p_proc_selfix_10),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_kc_1_sti_p_439_emt_template(vf=vf, name='Kc+1/sTi [(p__439' if name is None else name)
