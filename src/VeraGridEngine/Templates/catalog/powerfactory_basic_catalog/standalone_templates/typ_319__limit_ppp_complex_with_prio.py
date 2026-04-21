# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.enumerations import DeviceType

def get_limit_ppp_complex_with_prio_319_emt_template(vf: VarFactory, name: str = 'Limit [ppp] (complex with prio)__319') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    Limit_ppp_complex_with_prio_D_MAX = vf.add_var('Limit [ppp] (complex with prio)__D_MAX_' + name)
    Limit_ppp_complex_with_prio_MAG_MAX = vf.add_var('Limit [ppp] (complex with prio)__MAG_MAX_' + name)
    Limit_ppp_complex_with_prio_Q_MAX = vf.add_var('Limit [ppp] (complex with prio)__Q_MAX_' + name)

    # --- State Variables ---

    # --- Algebraic / Shared Variables ---
    Limit_ppp_complex_with_prio_proc_select_0 = vf.add_var('Limit [ppp] (complex with prio)__proc_select_0_' + name)
    Limit_ppp_complex_with_prio_proc_select_1 = vf.add_var('Limit [ppp] (complex with prio)__proc_select_1_' + name)
    Limit_ppp_complex_with_prio_proc_select_2 = vf.add_var('Limit [ppp] (complex with prio)__proc_select_2_' + name)
    Limit_ppp_complex_with_prio_proc_select_3 = vf.add_var('Limit [ppp] (complex with prio)__proc_select_3_' + name)
    Limit_ppp_complex_with_prio_proc_select_4 = vf.add_var('Limit [ppp] (complex with prio)__proc_select_4_' + name)
    Limit_ppp_complex_with_prio_proc_select_5 = vf.add_var('Limit [ppp] (complex with prio)__proc_select_5_' + name)
    Limit_ppp_complex_with_prio_iXref_nonprio = vf.add_var('Limit [ppp] (complex with prio)_iXref_nonprio_' + name)
    Limit_ppp_complex_with_prio_iXref_prio = vf.add_var('Limit [ppp] (complex with prio)_iXref_prio_' + name)
    Limit_ppp_complex_with_prio_max_nonprio = vf.add_var('Limit [ppp] (complex with prio)_max_nonprio_' + name)
    Limit_ppp_complex_with_prio_max_prio = vf.add_var('Limit [ppp] (complex with prio)_max_prio_' + name)
    Limit_ppp_complex_with_prio_remainder = vf.add_var('Limit [ppp] (complex with prio)_remainder_' + name)
    Limit_ppp_complex_with_prio_y_nonprio = vf.add_var('Limit [ppp] (complex with prio)_y_nonprio_' + name)
    Limit_ppp_complex_with_prio_y_prio = vf.add_var('Limit [ppp] (complex with prio)_y_prio_' + name)
    PRIORITISE_AXIS = vf.add_var('PRIORITISE_AXIS_' + name)
    d = vf.add_var('d_' + name)
    q = vf.add_var('q_' + name)
    yo_d = vf.add_var('yo_d_' + name)
    yo_q = vf.add_var('yo_q_' + name)

    # --- Derivative Variables ---

    # --- Block Assembly ---
    templ.block = Block(
        algebraic_eqs=[
            (Limit_ppp_complex_with_prio_iXref_prio - ((Limit_ppp_complex_with_prio_proc_select_0 * d) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_0) * q))),
            (Limit_ppp_complex_with_prio_iXref_nonprio - ((Limit_ppp_complex_with_prio_proc_select_1 * q) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_1) * d))),
            (Limit_ppp_complex_with_prio_max_prio - ((((Limit_ppp_complex_with_prio_proc_select_2 * sym.abs(Limit_ppp_complex_with_prio_D_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_2) * sym.abs(Limit_ppp_complex_with_prio_Q_MAX))) * sym.heaviside((sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) - ((Limit_ppp_complex_with_prio_proc_select_2 * sym.abs(Limit_ppp_complex_with_prio_D_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_2) * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)))))) + (sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) * (sym.Const(1) - sym.heaviside((sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) - ((Limit_ppp_complex_with_prio_proc_select_2 * sym.abs(Limit_ppp_complex_with_prio_D_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_2) * sym.abs(Limit_ppp_complex_with_prio_Q_MAX))))))))),
            (Limit_ppp_complex_with_prio_y_prio - (((-Limit_ppp_complex_with_prio_max_prio) + ((Limit_ppp_complex_with_prio_iXref_prio - (-Limit_ppp_complex_with_prio_max_prio)) * sym.heaviside((Limit_ppp_complex_with_prio_iXref_prio - (-Limit_ppp_complex_with_prio_max_prio))))) - ((Limit_ppp_complex_with_prio_iXref_prio - Limit_ppp_complex_with_prio_max_prio) * sym.heaviside((Limit_ppp_complex_with_prio_iXref_prio - Limit_ppp_complex_with_prio_max_prio))))),
            (Limit_ppp_complex_with_prio_remainder - sym.sqrt(sym.abs(((Limit_ppp_complex_with_prio_MAG_MAX * Limit_ppp_complex_with_prio_MAG_MAX) - (Limit_ppp_complex_with_prio_y_prio * Limit_ppp_complex_with_prio_y_prio))))),
            (Limit_ppp_complex_with_prio_max_nonprio - ((((((Limit_ppp_complex_with_prio_proc_select_3 * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_3) * sym.abs(Limit_ppp_complex_with_prio_D_MAX))) * sym.heaviside((sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) - ((Limit_ppp_complex_with_prio_proc_select_3 * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_3) * sym.abs(Limit_ppp_complex_with_prio_D_MAX)))))) + (sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) * (sym.Const(1) - sym.heaviside((sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) - ((Limit_ppp_complex_with_prio_proc_select_3 * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_3) * sym.abs(Limit_ppp_complex_with_prio_D_MAX)))))))) * sym.heaviside((Limit_ppp_complex_with_prio_remainder - ((((Limit_ppp_complex_with_prio_proc_select_3 * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_3) * sym.abs(Limit_ppp_complex_with_prio_D_MAX))) * sym.heaviside((sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) - ((Limit_ppp_complex_with_prio_proc_select_3 * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_3) * sym.abs(Limit_ppp_complex_with_prio_D_MAX)))))) + (sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) * (sym.Const(1) - sym.heaviside((sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) - ((Limit_ppp_complex_with_prio_proc_select_3 * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_3) * sym.abs(Limit_ppp_complex_with_prio_D_MAX))))))))))) + (Limit_ppp_complex_with_prio_remainder * (sym.Const(1) - sym.heaviside((Limit_ppp_complex_with_prio_remainder - ((((Limit_ppp_complex_with_prio_proc_select_3 * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_3) * sym.abs(Limit_ppp_complex_with_prio_D_MAX))) * sym.heaviside((sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) - ((Limit_ppp_complex_with_prio_proc_select_3 * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_3) * sym.abs(Limit_ppp_complex_with_prio_D_MAX)))))) + (sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) * (sym.Const(1) - sym.heaviside((sym.abs(Limit_ppp_complex_with_prio_MAG_MAX) - ((Limit_ppp_complex_with_prio_proc_select_3 * sym.abs(Limit_ppp_complex_with_prio_Q_MAX)) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_3) * sym.abs(Limit_ppp_complex_with_prio_D_MAX)))))))))))))),
            (Limit_ppp_complex_with_prio_y_nonprio - (((-Limit_ppp_complex_with_prio_max_nonprio) + ((Limit_ppp_complex_with_prio_iXref_nonprio - (-Limit_ppp_complex_with_prio_max_nonprio)) * sym.heaviside((Limit_ppp_complex_with_prio_iXref_nonprio - (-Limit_ppp_complex_with_prio_max_nonprio))))) - ((Limit_ppp_complex_with_prio_iXref_nonprio - Limit_ppp_complex_with_prio_max_nonprio) * sym.heaviside((Limit_ppp_complex_with_prio_iXref_nonprio - Limit_ppp_complex_with_prio_max_nonprio))))),
            (yo_d - ((Limit_ppp_complex_with_prio_proc_select_4 * Limit_ppp_complex_with_prio_y_prio) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_4) * Limit_ppp_complex_with_prio_y_nonprio))),
            (yo_q - ((Limit_ppp_complex_with_prio_proc_select_5 * Limit_ppp_complex_with_prio_y_nonprio) + ((sym.Const(1.0) - Limit_ppp_complex_with_prio_proc_select_5) * Limit_ppp_complex_with_prio_y_prio))),
        ],
        algebraic_vars=[Limit_ppp_complex_with_prio_iXref_prio, Limit_ppp_complex_with_prio_iXref_nonprio, Limit_ppp_complex_with_prio_max_prio, Limit_ppp_complex_with_prio_y_prio, Limit_ppp_complex_with_prio_remainder, Limit_ppp_complex_with_prio_max_nonprio, Limit_ppp_complex_with_prio_y_nonprio, yo_d, yo_q],
        in_vars=[d, q, PRIORITISE_AXIS],
        out_vars=[yo_d, yo_q],
        name='Limit [ppp] (complex with prio)'
    )
    # --- Parameter Values ---
    templ.block.event_dict = {
        Limit_ppp_complex_with_prio_D_MAX: vf.add_const(None, name='D_MAX'),
        Limit_ppp_complex_with_prio_Q_MAX: vf.add_const(None, name='Q_MAX'),
        Limit_ppp_complex_with_prio_MAG_MAX: vf.add_const(None, name='MAG_MAX'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        Limit_ppp_complex_with_prio_proc_select_0: vf.add_const(0.0, name=''),
        Limit_ppp_complex_with_prio_proc_select_1: vf.add_const(0.0, name=''),
        Limit_ppp_complex_with_prio_proc_select_2: vf.add_const(0.0, name=''),
        Limit_ppp_complex_with_prio_proc_select_3: vf.add_const(0.0, name=''),
        Limit_ppp_complex_with_prio_proc_select_4: vf.add_const(0.0, name=''),
        Limit_ppp_complex_with_prio_proc_select_5: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        sampled_value(output=Limit_ppp_complex_with_prio_proc_select_0, source=(PRIORITISE_AXIS < 0.5)),
        sampled_value(output=Limit_ppp_complex_with_prio_proc_select_1, source=(PRIORITISE_AXIS < 0.5)),
        sampled_value(output=Limit_ppp_complex_with_prio_proc_select_2, source=(PRIORITISE_AXIS < 0.5)),
        sampled_value(output=Limit_ppp_complex_with_prio_proc_select_3, source=(PRIORITISE_AXIS < 0.5)),
        sampled_value(output=Limit_ppp_complex_with_prio_proc_select_4, source=(PRIORITISE_AXIS < 0.5)),
        sampled_value(output=Limit_ppp_complex_with_prio_proc_select_5, source=(PRIORITISE_AXIS < 0.5)),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_limit_ppp_complex_with_prio_319_emt_template(vf=vf, name='Limit [ppp] (complex with prio)__319' if name is None else name)
