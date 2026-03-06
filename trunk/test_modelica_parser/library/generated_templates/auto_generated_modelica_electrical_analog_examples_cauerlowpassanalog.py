# --- AUTO-GENERATED EMT TEMPLATE ---
# Source: Modelica Flat XML Transpilation

import numpy as np
from abc import ABC, abstractmethod
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def apply_boundary_logic_modelica_electrical_analog_examples_cauerlowpassanalog(state):
    """Procedural logic for switching and discrete events."""
    state.V_v = (0.0 if (state.time < state.V_signalSource_startTime) else state.V_signalSource_height)


def get_modelica_electrical_analog_examples_cauerlowpassanalog_emt_template(vf: VarFactory, name: str='Modelica.Electrical.Analog.Examples.CauerLowPassAnalog') -> EmtModelTemplate:
    """Initializes the continuous DAE block and factory variables."""
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice  # TODO: Verify correct DeviceType
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---
    C2_v = vf.add_var('C2.v_' + name)
    C4_v = vf.add_var('C4.v_' + name)
    L1_i = vf.add_var('L1.i_' + name)
    L1_v = vf.add_var('L1.v_' + name)
    L2_i = vf.add_var('L2.i_' + name)
    L2_v = vf.add_var('L2.v_' + name)

    # --- Algebraic Variables ---
    C1_i = vf.add_var('C1.i_' + name)
    C1_v = vf.add_var('C1.v_' + name)
    C3_i = vf.add_var('C3.i_' + name)
    C3_v = vf.add_var('C3.v_' + name)
    C5_i = vf.add_var('C5.i_' + name)
    C5_v = vf.add_var('C5.v_' + name)
    G_p_i = vf.add_var('G.p.i_' + name)
    L1_L = vf.add_var('L1.L_' + name)
    L2_L = vf.add_var('L2.L_' + name)
    R1_LossPower = vf.add_var('R1.LossPower_' + name)
    R1_R_actual = vf.add_var('R1.R_actual_' + name)
    R1_v = vf.add_var('R1.v_' + name)
    R2_LossPower = vf.add_var('R2.LossPower_' + name)
    R2_R_actual = vf.add_var('R2.R_actual_' + name)
    R2_i = vf.add_var('R2.i_' + name)
    V_i = vf.add_var('V.i_' + name)
    V_signalSource_height = vf.add_var('V.signalSource.height_' + name)
    V_signalSource_startTime = vf.add_var('V.signalSource.startTime_' + name)
    V_v = vf.add_var('V.v_' + name)
    time = vf.add_var('time_' + name)

    # --- Derivative Variables ---
    d_C2_v = vf.add_diff_var('d_C2.v', base_var=C2_v)
    d_C4_v = vf.add_diff_var('d_C4.v', base_var=C4_v)
    d_L1_i = vf.add_diff_var('d_L1.i', base_var=L1_i)
    d_L1_v = vf.add_diff_var('d_L1.v', base_var=L1_v)
    d_L2_i = vf.add_diff_var('d_L2.i', base_var=L2_i)
    d_L2_v = vf.add_diff_var('d_L2.v', base_var=L2_v)

    # --- Continuous Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (d_L2_v - d_C4_v),
            (d_L1_v - d_C2_v),
            (d_L2_i - (C4_v / L2_L)),
            (d_L1_i - (C2_v / L1_L)),
        ],
        state_vars=[C2_v, C4_v, L1_i, L1_v, L2_i, L2_v],

        algebraic_eqs=[
            (R2_i - (C5_v / R2_R_actual)),
            (R2_LossPower - (C5_v * R2_i)),
            (R1_v - (V_v - C1_v)),
            (V_i - ((-R1_v) / R1_R_actual)),
            0.0,
            (G_p_i - (C1_i - ((((-R2_i) - V_i) - C5_i) - C3_i))),
            (R1_LossPower - ((-R1_v) * V_i)),
            (C4_v - (C3_v - C5_v)),
            (L2_v - C4_v),
            (C2_v - (C1_v - C3_v)),
            (L1_v - C2_v),
        ],
        algebraic_vars=[C1_i, C1_v, C3_i, C3_v, C5_i, C5_v, G_p_i, L1_L, L2_L, R1_LossPower, R1_R_actual, R1_v, R2_LossPower, R2_R_actual, R2_i, V_i, V_signalSource_height, V_signalSource_startTime, V_v, time],
    )

    # --- Parameter Values ---
    templ.block.event_dict = {
    }

    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        C1_v: vf.add_const(0.0),
        C3_v: vf.add_const(0.0),
        C5_v: vf.add_const(0.0),
        L1_i: vf.add_const(0.0),
        L2_i: vf.add_const(0.0),
        d_C3_v: vf.add_const(0.0),
        d_C5_v: vf.add_const(0.0),
        C2_v: L1_v,
        C4_v: L2_v,
        L1_v: (C1_v - C3_v),
        L2_v: (C3_v - C5_v),
        R1_v: vf.add_const(0.0),
        R2_LossPower: vf.add_const(0.0),
        R2_i: vf.add_const(0.0),
        V_v: vf.add_const(0.0),
        R2_R_actual: (R2_R * (1.0 + (R2_alpha * (R2_T - R2_T_ref)))),
        R1_R_actual: (R1_R * (1.0 + (R1_alpha * (R1_T - R1_T_ref)))),
        d_L1_i: (L1_v / L1_L),
        d_L2_i: (L2_v / L2_L),
        G_p_v: vf.add_const(0.0),
        C1_i: vf.add_const(0.0),
        C3_i: vf.add_const(0.0),
        C5_i: vf.add_const(0.0),
        G_p_i: vf.add_const(0.0),
        L1_L: vf.add_const(0.0),
        L2_L: vf.add_const(0.0),
        R1_LossPower: vf.add_const(0.0),
        V_i: vf.add_const(0.0),
        V_signalSource_height: vf.add_const(0.0),
        V_signalSource_startTime: vf.add_const(0.0),
        time: vf.add_const(0.0),
    }

    return templ
