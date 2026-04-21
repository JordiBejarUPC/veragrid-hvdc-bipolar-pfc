# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import delay
from VeraGridEngine.enumerations import DeviceType

def get_e_std_1_st1_1_st1_204_emt_template(vf: VarFactory, name: str = 'e(-sTd)/((1+sT1)(1+sT1))__204') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    e_sTd_1_sT1_1_sT1_T1 = vf.add_var('e(-sTd)/((1+sT1)(1+sT1))__T1_' + name)
    e_sTd_1_sT1_1_sT1_T2 = vf.add_var('e(-sTd)/((1+sT1)(1+sT1))__T2_' + name)
    e_sTd_1_sT1_1_sT1_Td = vf.add_var('e(-sTd)/((1+sT1)(1+sT1))__Td_' + name)

    # --- State Variables ---
    e_sTd_1_sT1_1_sT1_x1 = vf.add_var('e(-sTd)/((1+sT1)(1+sT1))__x1_' + name)
    e_sTd_1_sT1_1_sT1_x2 = vf.add_var('e(-sTd)/((1+sT1)(1+sT1))__x2_' + name)

    # --- Algebraic / Shared Variables ---
    e_sTd_1_sT1_1_sT1_proc_delay_0 = vf.add_var('e(-sTd)/((1+sT1)(1+sT1))__proc_delay_0_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_e_sTd_1_sT1_1_sT1_x1 = vf.add_diff_var('d_e(-sTd)/((1+sT1)(1+sT1))__x1_' + name, base_var=e_sTd_1_sT1_1_sT1_x1)
    d_e_sTd_1_sT1_1_sT1_x2 = vf.add_diff_var('d_e(-sTd)/((1+sT1)(1+sT1))__x2_' + name, base_var=e_sTd_1_sT1_1_sT1_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            e_sTd_1_sT1_1_sT1_x2,
            (((yi - e_sTd_1_sT1_1_sT1_x1) - ((e_sTd_1_sT1_1_sT1_T1 + e_sTd_1_sT1_1_sT1_T2) * e_sTd_1_sT1_1_sT1_x2)) / (e_sTd_1_sT1_1_sT1_T1 * e_sTd_1_sT1_1_sT1_T2)),
        ],
        state_vars=[e_sTd_1_sT1_1_sT1_x1, e_sTd_1_sT1_1_sT1_x2],
        algebraic_eqs=[
            (yo - e_sTd_1_sT1_1_sT1_proc_delay_0),
        ],
        algebraic_vars=[yo],
        in_vars=[yi],
        out_vars=[yo],
        name='e(-sTd)/((1+sT1)(1+sT1))'
    )
    templ.block.diff_vars = [d_e_sTd_1_sT1_1_sT1_x1, d_e_sTd_1_sT1_1_sT1_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        e_sTd_1_sT1_1_sT1_T1: vf.add_const(None, name='T1'),
        e_sTd_1_sT1_1_sT1_T2: vf.add_const(None, name='T2'),
        e_sTd_1_sT1_1_sT1_Td: vf.add_const(None, name='Td'),
    }
    # --- Retained Runtime Modes ---
    templ.block.mode_dict = {
        e_sTd_1_sT1_1_sT1_proc_delay_0: vf.add_const(0.0, name=''),
    }
    templ.block.procedural_logic = [
        delay(e_sTd_1_sT1_1_sT1_x1, e_sTd_1_sT1_1_sT1_Td, output=e_sTd_1_sT1_1_sT1_proc_delay_0),
    ]
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_e_std_1_st1_1_st1_204_emt_template(vf=vf, name='e(-sTd)/((1+sT1)(1+sT1))__204' if name is None else name)
