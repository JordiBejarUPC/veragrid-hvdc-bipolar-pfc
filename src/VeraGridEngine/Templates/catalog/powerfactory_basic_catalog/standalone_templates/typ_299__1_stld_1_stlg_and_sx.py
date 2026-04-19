# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import selfix
from VeraGridEngine.enumerations import DeviceType

def get_v_1_stld_1_stlg_and_sx_299_emt_template(vf: VarFactory, name: str = '(1+sTld)/(1+sTlg) and sx__299') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sTld_1_sTlg_and_sx_Tld = vf.add_var('(1+sTld)/(1+sTlg) and sx__Tld_' + name)
    v_1_sTld_1_sTlg_and_sx_Tlg = vf.add_var('(1+sTld)/(1+sTlg) and sx__Tlg_' + name)

    # --- State Variables ---
    v_1_sTld_1_sTlg_and_sx_x = vf.add_var('(1+sTld)/(1+sTlg) and sx__x_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sTld_1_sTlg_and_sx_proc_selfix_0 = vf.add_var('(1+sTld)/(1+sTlg) and sx__proc_selfix_0_' + name)
    v_1_sTld_1_sTlg_and_sx_dx = vf.add_var('(1+sTld)/(1+sTlg) and sx_dx_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sTld_1_sTlg_and_sx_x = vf.add_diff_var('d_(1+sTld)/(1+sTlg) and sx__x_' + name, base_var=v_1_sTld_1_sTlg_and_sx_x)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_sTld_1_sTlg_and_sx_dx,
        ],
        state_vars=[v_1_sTld_1_sTlg_and_sx_x],
        algebraic_eqs=[
            (v_1_sTld_1_sTlg_and_sx_dx - ((v_1_sTld_1_sTlg_and_sx_proc_selfix_0 * ((yi - v_1_sTld_1_sTlg_and_sx_x) / v_1_sTld_1_sTlg_and_sx_Tlg)) + ((sym.Const(1.0) - v_1_sTld_1_sTlg_and_sx_proc_selfix_0) * ((yi - v_1_sTld_1_sTlg_and_sx_x) / sym.Const(0.01))))),
            (yo - (v_1_sTld_1_sTlg_and_sx_x + (v_1_sTld_1_sTlg_and_sx_Tld * v_1_sTld_1_sTlg_and_sx_dx))),
        ],
        algebraic_vars=[v_1_sTld_1_sTlg_and_sx_dx, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+sTld)/(1+sTlg) and sx'
    )
    templ.block.diff_vars = [d_1_sTld_1_sTlg_and_sx_x]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sTld_1_sTlg_and_sx_Tld: vf.add_const(None, name='Tld'),
        v_1_sTld_1_sTlg_and_sx_Tlg: vf.add_const(None, name='Tlg'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        v_1_sTld_1_sTlg_and_sx_proc_selfix_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        selfix((v_1_sTld_1_sTlg_and_sx_Tlg > 0.0), output=v_1_sTld_1_sTlg_and_sx_proc_selfix_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_stld_1_stlg_and_sx_299_emt_template(vf=vf, name='(1+sTld)/(1+sTlg) and sx__299' if name is None else name)
