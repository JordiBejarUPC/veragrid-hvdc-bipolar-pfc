# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_1_st_p_137_emt_template(vf: VarFactory, name: str = '1/(1+sT) {p__137') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_1_sT_p_T = vf.add_var('1/(1+sT) {p__T_' + name)
    v_1_1_sT_p_rdown = vf.add_var('1/(1+sT) {p__rdown_' + name)
    v_1_1_sT_p_rup = vf.add_var('1/(1+sT) {p__rup_' + name)

    # --- State Variables ---
    v_1_1_sT_p_x = vf.add_var('1/(1+sT) {p__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_1_sT_p_proc_selfix_0 = vf.add_var('1/(1+sT) {p__proc_selfix_0_' + name)
    v_1_1_sT_p_proc_selfix_1 = vf.add_var('1/(1+sT) {p__proc_selfix_1_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_1_sT_p_x = vf.add_diff_var('d_1/(1+sT) {p__x_' + name, base_var=v_1_1_sT_p_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            ((v_1_1_sT_p_rdown + ((((v_1_1_sT_p_proc_selfix_0 * ((yi - v_1_1_sT_p_x) / v_1_1_sT_p_T)) + ((sym.Const(1.0) - v_1_1_sT_p_proc_selfix_0) * sym.Const(0.0))) - v_1_1_sT_p_rdown) * sym.heaviside((((v_1_1_sT_p_proc_selfix_0 * ((yi - v_1_1_sT_p_x) / v_1_1_sT_p_T)) + ((sym.Const(1.0) - v_1_1_sT_p_proc_selfix_0) * sym.Const(0.0))) - v_1_1_sT_p_rdown)))) - ((((v_1_1_sT_p_proc_selfix_0 * ((yi - v_1_1_sT_p_x) / v_1_1_sT_p_T)) + ((sym.Const(1.0) - v_1_1_sT_p_proc_selfix_0) * sym.Const(0.0))) - v_1_1_sT_p_rup) * sym.heaviside((((v_1_1_sT_p_proc_selfix_0 * ((yi - v_1_1_sT_p_x) / v_1_1_sT_p_T)) + ((sym.Const(1.0) - v_1_1_sT_p_proc_selfix_0) * sym.Const(0.0))) - v_1_1_sT_p_rup)))),
        ],
        state_vars=[v_1_1_sT_p_x],
        algebraic_eqs=[
            (yo - ((v_1_1_sT_p_proc_selfix_1 * v_1_1_sT_p_x) + ((sym.Const(1.0) - v_1_1_sT_p_proc_selfix_1) * yi))),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='1/(1+sT) {p'
    )
    templ.block.diff_vars = [d_1_1_sT_p_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_1_sT_p_T: vf.add_const(None, name='T'),
        v_1_1_sT_p_rup: vf.add_const(None, name='rup'),
        v_1_1_sT_p_rdown: vf.add_const(None, name='rdown'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_1_sT_p_proc_selfix_0: vf.add_const(0.0, name=''),
        v_1_1_sT_p_proc_selfix_1: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((v_1_1_sT_p_T > 0.0), output=v_1_1_sT_p_proc_selfix_0),
        selfix((v_1_1_sT_p_T > 0.0), output=v_1_1_sT_p_proc_selfix_1),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_1_st_p_137_emt_template(vf=vf, name='1/(1+sT) {p__137' if name is None else name)
