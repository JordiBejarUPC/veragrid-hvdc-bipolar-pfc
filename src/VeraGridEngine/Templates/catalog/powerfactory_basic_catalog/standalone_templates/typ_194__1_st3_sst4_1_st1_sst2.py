# --- AUTO-GENERATED EMT TEMPLATE FROM DGS ---
# Source: C:\Users\andre\Documents\BASE_CATALOG.dgs

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def get_v_1_st3_sst4_1_st1_sst2_194_emt_template(vf: VarFactory, name: str = '(1+sT3+ssT4)/(1+sT1+ssT2)__194') -> EmtModelTemplate:
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    # --- Parameters ---
    v_1_sT3_ssT4_1_sT1_ssT2_T1 = vf.add_var('(1+sT3+ssT4)/(1+sT1+ssT2)__T1_' + name)
    v_1_sT3_ssT4_1_sT1_ssT2_T2 = vf.add_var('(1+sT3+ssT4)/(1+sT1+ssT2)__T2_' + name)
    v_1_sT3_ssT4_1_sT1_ssT2_T3 = vf.add_var('(1+sT3+ssT4)/(1+sT1+ssT2)__T3_' + name)
    v_1_sT3_ssT4_1_sT1_ssT2_T4 = vf.add_var('(1+sT3+ssT4)/(1+sT1+ssT2)__T4_' + name)

    # --- State Variables ---
    v_1_sT3_ssT4_1_sT1_ssT2_x1 = vf.add_var('(1+sT3+ssT4)/(1+sT1+ssT2)__x1_' + name)
    v_1_sT3_ssT4_1_sT1_ssT2_x2 = vf.add_var('(1+sT3+ssT4)/(1+sT1+ssT2)__x2_' + name)

    # --- Algebraic / Shared Variables ---
    v_1_sT3_ssT4_1_sT1_ssT2_dx1 = vf.add_var('(1+sT3+ssT4)/(1+sT1+ssT2)_dx1_' + name)
    v_1_sT3_ssT4_1_sT1_ssT2_dx2 = vf.add_var('(1+sT3+ssT4)/(1+sT1+ssT2)_dx2_' + name)
    yi = vf.add_var('yi_' + name)
    yo = vf.add_var('yo_' + name)

    # --- Derivative Variables ---
    d_1_sT3_ssT4_1_sT1_ssT2_x1 = vf.add_diff_var('d_(1+sT3+ssT4)/(1+sT1+ssT2)__x1_' + name, base_var=v_1_sT3_ssT4_1_sT1_ssT2_x1)
    d_1_sT3_ssT4_1_sT1_ssT2_x2 = vf.add_diff_var('d_(1+sT3+ssT4)/(1+sT1+ssT2)__x2_' + name, base_var=v_1_sT3_ssT4_1_sT1_ssT2_x2)

    # --- Block Assembly ---
    templ.block = Block(
        state_eqs=[
            v_1_sT3_ssT4_1_sT1_ssT2_dx1,
            v_1_sT3_ssT4_1_sT1_ssT2_dx2,
        ],
        state_vars=[v_1_sT3_ssT4_1_sT1_ssT2_x1, v_1_sT3_ssT4_1_sT1_ssT2_x2],
        algebraic_eqs=[
            (v_1_sT3_ssT4_1_sT1_ssT2_dx1 - v_1_sT3_ssT4_1_sT1_ssT2_x2),
            (v_1_sT3_ssT4_1_sT1_ssT2_dx2 - (((yi - v_1_sT3_ssT4_1_sT1_ssT2_x1) - (v_1_sT3_ssT4_1_sT1_ssT2_x2 * v_1_sT3_ssT4_1_sT1_ssT2_T1)) / v_1_sT3_ssT4_1_sT1_ssT2_T2)),
            (yo - ((v_1_sT3_ssT4_1_sT1_ssT2_x1 + (v_1_sT3_ssT4_1_sT1_ssT2_T3 * v_1_sT3_ssT4_1_sT1_ssT2_dx1)) + (v_1_sT3_ssT4_1_sT1_ssT2_T4 * v_1_sT3_ssT4_1_sT1_ssT2_dx2))),
        ],
        algebraic_vars=[v_1_sT3_ssT4_1_sT1_ssT2_dx1, v_1_sT3_ssT4_1_sT1_ssT2_dx2, yo],
        in_vars=[yi],
        out_vars=[yo],
        name='(1+sT3+ssT4)/(1+sT1+ssT2)'
    )
    templ.block.diff_vars = [d_1_sT3_ssT4_1_sT1_ssT2_x1, d_1_sT3_ssT4_1_sT1_ssT2_x2]
    # --- Parameter Values ---
    templ.block.event_dict = {
        v_1_sT3_ssT4_1_sT1_ssT2_T1: vf.add_const(None, name='T1'),
        v_1_sT3_ssT4_1_sT1_ssT2_T2: vf.add_const(None, name='T2'),
        v_1_sT3_ssT4_1_sT1_ssT2_T3: vf.add_const(None, name='T3'),
        v_1_sT3_ssT4_1_sT1_ssT2_T4: vf.add_const(None, name='T4'),
    }
    templ.block.name = name

    return templ

def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:
    return get_v_1_st3_sst4_1_st1_sst2_194_emt_template(vf=vf, name='(1+sT3+ssT4)/(1+sT1+ssT2)__194' if name is None else name)
