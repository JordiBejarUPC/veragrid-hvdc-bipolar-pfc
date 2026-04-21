# --- AUTO-GENERATED EMT TEMPLATE ---
# Source: Modelica Flat XML Transpilation

import numpy as np
from abc import ABC, abstractmethod
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

def apply_boundary_logic_modelica_electrical_powerconverters_examples_acdc_rectifiercentertapmpulse_thyristorcentertapmpulse_rl(state):
    """Procedural logic for switching and discrete events."""
    state.rectifier_vAC_1 = (0.0 if (state.time < state.sineVoltage_p_sineVoltage_1) else (state.sineVoltage_p_sineVoltage_1 * sym.sin(((6.283185307179586 * (state.sineVoltage_p_sineVoltage_1 * (state.time - state.sineVoltage_p_sineVoltage_1))) + state.sineVoltage_p_sineVoltage_1))))
    state.rectifier_vAC_2 = (0.0 if (state.time < state.sineVoltage_p_sineVoltage_2) else (state.sineVoltage_p_sineVoltage_2 * sym.sin(((6.283185307179586 * (state.sineVoltage_p_sineVoltage_2 * (state.time - state.sineVoltage_p_sineVoltage_2))) + state.sineVoltage_p_sineVoltage_2))))
    state.v_whenCondition5 = (state.pulsem_twomPulse_v_2 > state.pulsem_twomPulse_positiveThreshold_2)
    state.pulsem_twomPulse_timerPositive_2 = ((state.time - state.pulsem_twomPulse_timerPositive_2) if state.v_whenCondition5 else 0.0)
    state.pulsem_fire_p_2 = (state.pulsem_twomPulse_gainPositive_2 > state.pulsem_twomPulse_replicator_y_3)
    state.rectifier_andCondition_p_2 = (state.pulsem_fire_p_2 and state.rectifier_enableLogic_enableConstantSource_k)
    state.v_whenCondition2 = (state.pulsem_twomPulse_v_2 < state.pulsem_twomPulse_negativeThreshold_2)
    state.pulsem_twomPulse_timerNegative_2 = ((state.time - state.pulsem_twomPulse_timerNegative_2) if state.v_whenCondition2 else 0.0)
    state.pulsem_fire_n_2 = (state.pulsem_twomPulse_gainNegative_2 > state.pulsem_twomPulse_replicator_y_3)
    state.rectifier_vAC_3 = (0.0 if (state.time < state.sineVoltage_p_sineVoltage_3) else (state.sineVoltage_p_sineVoltage_3 * sym.sin(((6.283185307179586 * (state.sineVoltage_p_sineVoltage_3 * (state.time - state.sineVoltage_p_sineVoltage_3))) + state.sineVoltage_p_sineVoltage_3))))
    state.v_whenCondition4 = (state.pulsem_twomPulse_v_3 > state.pulsem_twomPulse_positiveThreshold_3)
    state.pulsem_twomPulse_timerPositive_3 = ((state.time - state.pulsem_twomPulse_timerPositive_3) if state.v_whenCondition4 else 0.0)
    state.pulsem_fire_p_3 = (state.pulsem_twomPulse_gainPositive_3 > state.pulsem_twomPulse_replicator_y_3)
    state.rectifier_andCondition_p_3 = (state.pulsem_fire_p_3 and state.rectifier_enableLogic_enableConstantSource_k)
    state.v_whenCondition1 = (state.pulsem_twomPulse_v_3 < state.pulsem_twomPulse_negativeThreshold_3)
    state.pulsem_twomPulse_timerNegative_3 = ((state.time - state.pulsem_twomPulse_timerNegative_3) if state.v_whenCondition1 else 0.0)
    state.pulsem_fire_n_3 = (state.pulsem_twomPulse_gainNegative_3 > state.pulsem_twomPulse_replicator_y_3)
    state.v_whenCondition6 = (state.pulsem_twomPulse_v_1 > state.pulsem_twomPulse_positiveThreshold_1)
    state.pulsem_twomPulse_timerPositive_1 = ((state.time - state.pulsem_twomPulse_timerPositive_1) if state.v_whenCondition6 else 0.0)
    state.pulsem_fire_p_1 = (state.pulsem_twomPulse_gainPositive_1 > state.pulsem_twomPulse_replicator_y_3)
    state.rectifier_andCondition_p_1 = (state.pulsem_fire_p_1 and state.rectifier_enableLogic_enableConstantSource_k)
    state.v_whenCondition3 = (state.pulsem_twomPulse_v_1 < state.pulsem_twomPulse_negativeThreshold_1)
    state.pulsem_twomPulse_timerNegative_1 = ((state.time - state.pulsem_twomPulse_timerNegative_1) if state.v_whenCondition3 else 0.0)
    state.pulsem_fire_n_1 = (state.pulsem_twomPulse_gainNegative_1 > state.pulsem_twomPulse_replicator_y_3)
    state.rectifier_thyristor_idealThyristor_3 = (state.rectifier_thyristor_idealThyristor_3 < 0.0)
    state.rectifier_thyristor_v_3 = (1.0 if state.rectifier_thyristor_idealThyristor_3 else state.rectifier_thyristor_idealThyristor_3)
    state.rectifier_iAC_3 = (state.rectifier_thyristor_idealThyristor_3 if state.rectifier_thyristor_idealThyristor_3 else 1.0)
    state.rectifier_thyristor_idealThyristor_1 = (state.rectifier_thyristor_idealThyristor_1 < 0.0)
    state.rectifier_iAC_1 = (state.rectifier_thyristor_idealThyristor_1 if state.rectifier_thyristor_idealThyristor_1 else 1.0)
    state.rectifier_thyristor_v_1 = (1.0 if state.rectifier_thyristor_idealThyristor_1 else state.rectifier_thyristor_idealThyristor_1)
    state.rectifier_thyristor_idealThyristor_2 = (state.rectifier_thyristor_idealThyristor_2 < 0.0)
    state.rectifier_thyristor_v_2 = (1.0 if state.rectifier_thyristor_idealThyristor_2 else state.rectifier_thyristor_idealThyristor_2)
    state.rectifier_iAC_2 = (state.rectifier_thyristor_idealThyristor_2 if state.rectifier_thyristor_idealThyristor_2 else 1.0)

    # --- Discrete Event Handlers (When Blocks) ---
    if ext_funcs.event_triggered(state.v_whenCondition5):
        state.pulsem_twomPulse_timerPositive_2 = state.time
    if ext_funcs.event_triggered(state.v_whenCondition2):
        state.pulsem_twomPulse_timerNegative_2 = state.time
    if ext_funcs.event_triggered(state.v_whenCondition4):
        state.pulsem_twomPulse_timerPositive_3 = state.time
    if ext_funcs.event_triggered(state.v_whenCondition1):
        state.pulsem_twomPulse_timerNegative_3 = state.time
    if ext_funcs.event_triggered(state.v_whenCondition6):
        state.pulsem_twomPulse_timerPositive_1 = state.time
    if ext_funcs.event_triggered(state.v_whenCondition3):
        state.pulsem_twomPulse_timerNegative_1 = state.time
    if ext_funcs.event_triggered(state.v_whenCondition7):
        state.meanCurrent_y_last = (state.meanCurrent_f * ext_funcs.pre(state.meanCurrent_x))
        state.meanCurrent_x = 0.0
    if ext_funcs.event_triggered(state.v_whenCondition8):
        state.rootMeanSquareVoltage_mean_y_last = sym.max(0.0, (state.rootMeanSquareVoltage_mean_f * ext_funcs.pre(state.rootMeanSquareVoltage_mean_x)))
        state.rootMeanSquareVoltage_mean_x = 0.0
    if ext_funcs.event_triggered(state.v_whenCondition9):
        state.meanVoltage_y_last = (state.meanVoltage_f * ext_funcs.pre(state.meanVoltage_x))
        state.meanVoltage_x = 0.0

    # --- Procedural Initialization Logic ---
    # Evaluates logic blocks during the first step (t=0) to feed the symbolic solver
    if state.time == 0.0:
        state.pulsem_twomPulse_negativeThreshold_1 = (state.pulsem_twomPulse_v_1 < state.pulsem_twomPulse_negativeThreshold_1)
        state.pulsem_twomPulse_positiveThreshold_1 = (state.pulsem_twomPulse_v_1 > state.pulsem_twomPulse_positiveThreshold_1)
        state.pulsem_twomPulse_negativeThreshold_2 = (state.pulsem_twomPulse_v_2 < state.pulsem_twomPulse_negativeThreshold_2)
        state.pulsem_twomPulse_positiveThreshold_2 = (state.pulsem_twomPulse_v_2 > state.pulsem_twomPulse_positiveThreshold_2)
        state.pulsem_twomPulse_negativeThreshold_3 = (state.pulsem_twomPulse_v_3 < state.pulsem_twomPulse_negativeThreshold_3)
        state.pulsem_twomPulse_positiveThreshold_3 = (state.pulsem_twomPulse_v_3 > state.pulsem_twomPulse_positiveThreshold_3)
        state.pulsem_twomPulse_timerNegative_3 = ((state.time - state.pulsem_twomPulse_timerNegative_3) if state.pulsem_twomPulse_negativeThreshold_3 else 0.0)
        state.pulsem_twomPulse_timerNegative_2 = ((state.time - state.pulsem_twomPulse_timerNegative_2) if state.pulsem_twomPulse_negativeThreshold_2 else 0.0)
        state.pulsem_twomPulse_timerNegative_1 = ((state.time - state.pulsem_twomPulse_timerNegative_1) if state.pulsem_twomPulse_negativeThreshold_1 else 0.0)
        state.pulsem_twomPulse_timerPositive_3 = ((state.time - state.pulsem_twomPulse_timerPositive_3) if state.pulsem_twomPulse_positiveThreshold_3 else 0.0)
        state.pulsem_twomPulse_timerPositive_2 = ((state.time - state.pulsem_twomPulse_timerPositive_2) if state.pulsem_twomPulse_positiveThreshold_2 else 0.0)
        state.pulsem_twomPulse_timerPositive_1 = ((state.time - state.pulsem_twomPulse_timerPositive_1) if state.pulsem_twomPulse_positiveThreshold_1 else 0.0)
        state.rectifier_thyristor_idealThyristor_1 = (state.rectifier_thyristor_idealThyristor_1 < 0.0)
        state.rectifier_thyristor_idealThyristor_1 = (1.0 if state.rectifier_thyristor_idealThyristor_1 else state.rectifier_thyristor_idealThyristor_1)
        state.rectifier_iAC_1 = (state.rectifier_thyristor_idealThyristor_1 if state.rectifier_thyristor_idealThyristor_1 else 1.0)
        state.rectifier_thyristor_idealThyristor_2 = (state.rectifier_thyristor_idealThyristor_2 < 0.0)
        state.rectifier_iAC_2 = (state.rectifier_thyristor_idealThyristor_2 if state.rectifier_thyristor_idealThyristor_2 else 1.0)
        state.rectifier_thyristor_idealThyristor_2 = (1.0 if state.rectifier_thyristor_idealThyristor_2 else state.rectifier_thyristor_idealThyristor_2)
        state.rectifier_thyristor_idealThyristor_3 = (state.rectifier_thyristor_idealThyristor_3 < 0.0)
        state.rectifier_thyristor_idealThyristor_3 = (1.0 if state.rectifier_thyristor_idealThyristor_3 else state.rectifier_thyristor_idealThyristor_3)
        state.rectifier_iAC_3 = (state.rectifier_thyristor_idealThyristor_3 if state.rectifier_thyristor_idealThyristor_3 else 1.0)


def get_modelica_electrical_powerconverters_examples_acdc_rectifiercentertapmpulse_thyristorcentertapmpulse_rl_emt_template(vf: VarFactory, name: str='Modelica.Electrical.PowerConverters.Examples.ACDC.RectifierCenterTapmPulse.ThyristorCenterTapmPulse_RL') -> EmtModelTemplate:
    """Initializes the continuous DAE block and factory variables."""
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice  # TODO: Verify correct DeviceType
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---
    inductor_i = vf.add_var('inductor.i_' + name)
    meanCurrent_x = vf.add_var('meanCurrent.x_' + name)
    meanVoltage_x = vf.add_var('meanVoltage.x_' + name)
    rootMeanSquareVoltage_mean_x = vf.add_var('rootMeanSquareVoltage.mean.x_' + name)

    # --- Algebraic Variables ---
    v_whenCondition1 = vf.add_var('$whenCondition1_' + name)
    v_whenCondition2 = vf.add_var('$whenCondition2_' + name)
    v_whenCondition3 = vf.add_var('$whenCondition3_' + name)
    v_whenCondition4 = vf.add_var('$whenCondition4_' + name)
    v_whenCondition5 = vf.add_var('$whenCondition5_' + name)
    v_whenCondition6 = vf.add_var('$whenCondition6_' + name)
    v_whenCondition7 = vf.add_var('$whenCondition7_' + name)
    v_whenCondition8 = vf.add_var('$whenCondition8_' + name)
    v_whenCondition9 = vf.add_var('$whenCondition9_' + name)
    ground_p_i = vf.add_var('ground.p.i_' + name)
    inductor_v = vf.add_var('inductor.v_' + name)
    pulsem_fire_n_1 = vf.add_var('pulsem.fire_n[1]_' + name)
    pulsem_fire_n_2 = vf.add_var('pulsem.fire_n[2]_' + name)
    pulsem_fire_n_3 = vf.add_var('pulsem.fire_n[3]_' + name)
    pulsem_fire_p_1 = vf.add_var('pulsem.fire_p[1]_' + name)
    pulsem_fire_p_2 = vf.add_var('pulsem.fire_p[2]_' + name)
    pulsem_fire_p_3 = vf.add_var('pulsem.fire_p[3]_' + name)
    pulsem_twomPulse_gainNegative_1 = vf.add_var('pulsem.twomPulse.gainNegative[1]_' + name)
    pulsem_twomPulse_gainNegative_2 = vf.add_var('pulsem.twomPulse.gainNegative[2]_' + name)
    pulsem_twomPulse_gainNegative_3 = vf.add_var('pulsem.twomPulse.gainNegative[3]_' + name)
    pulsem_twomPulse_gainPositive_1 = vf.add_var('pulsem.twomPulse.gainPositive[1]_' + name)
    pulsem_twomPulse_gainPositive_2 = vf.add_var('pulsem.twomPulse.gainPositive[2]_' + name)
    pulsem_twomPulse_gainPositive_3 = vf.add_var('pulsem.twomPulse.gainPositive[3]_' + name)
    pulsem_twomPulse_limiter_y = vf.add_var('pulsem.twomPulse.limiter.y_' + name)
    pulsem_twomPulse_negativeThreshold_1 = vf.add_var('pulsem.twomPulse.negativeThreshold[1]_' + name)
    pulsem_twomPulse_negativeThreshold_2 = vf.add_var('pulsem.twomPulse.negativeThreshold[2]_' + name)
    pulsem_twomPulse_negativeThreshold_3 = vf.add_var('pulsem.twomPulse.negativeThreshold[3]_' + name)
    pulsem_twomPulse_positiveThreshold_1 = vf.add_var('pulsem.twomPulse.positiveThreshold[1]_' + name)
    pulsem_twomPulse_positiveThreshold_2 = vf.add_var('pulsem.twomPulse.positiveThreshold[2]_' + name)
    pulsem_twomPulse_positiveThreshold_3 = vf.add_var('pulsem.twomPulse.positiveThreshold[3]_' + name)
    pulsem_twomPulse_replicator_y_3 = vf.add_var('pulsem.twomPulse.replicator.y[3]_' + name)
    pulsem_twomPulse_timerNegative_1 = vf.add_var('pulsem.twomPulse.timerNegative[1]_' + name)
    pulsem_twomPulse_timerNegative_2 = vf.add_var('pulsem.twomPulse.timerNegative[2]_' + name)
    pulsem_twomPulse_timerNegative_3 = vf.add_var('pulsem.twomPulse.timerNegative[3]_' + name)
    pulsem_twomPulse_timerPositive_1 = vf.add_var('pulsem.twomPulse.timerPositive[1]_' + name)
    pulsem_twomPulse_timerPositive_2 = vf.add_var('pulsem.twomPulse.timerPositive[2]_' + name)
    pulsem_twomPulse_timerPositive_3 = vf.add_var('pulsem.twomPulse.timerPositive[3]_' + name)
    pulsem_twomPulse_v_1 = vf.add_var('pulsem.twomPulse.v[1]_' + name)
    pulsem_twomPulse_v_2 = vf.add_var('pulsem.twomPulse.v[2]_' + name)
    pulsem_twomPulse_v_3 = vf.add_var('pulsem.twomPulse.v[3]_' + name)
    rectifier_LossPower = vf.add_var('rectifier.LossPower_' + name)
    rectifier_andCondition_p_1 = vf.add_var('rectifier.andCondition_p[1]_' + name)
    rectifier_andCondition_p_2 = vf.add_var('rectifier.andCondition_p[2]_' + name)
    rectifier_andCondition_p_3 = vf.add_var('rectifier.andCondition_p[3]_' + name)
    rectifier_enableLogic_enableConstantSource_k = vf.add_var('rectifier.enableLogic.enableConstantSource.k_' + name)
    rectifier_iAC_1 = vf.add_var('rectifier.iAC[1]_' + name)
    rectifier_iAC_2 = vf.add_var('rectifier.iAC[2]_' + name)
    rectifier_iAC_3 = vf.add_var('rectifier.iAC[3]_' + name)
    rectifier_powerAC_1 = vf.add_var('rectifier.powerAC[1]_' + name)
    rectifier_powerAC_2 = vf.add_var('rectifier.powerAC[2]_' + name)
    rectifier_powerAC_3 = vf.add_var('rectifier.powerAC[3]_' + name)
    rectifier_powerDC = vf.add_var('rectifier.powerDC_' + name)
    rectifier_powerTotalAC = vf.add_var('rectifier.powerTotalAC_' + name)
    rectifier_thyristor_idealThyristor_1 = vf.add_var('rectifier.thyristor.idealThyristor[1]_' + name)
    rectifier_thyristor_idealThyristor_2 = vf.add_var('rectifier.thyristor.idealThyristor[2]_' + name)
    rectifier_thyristor_idealThyristor_3 = vf.add_var('rectifier.thyristor.idealThyristor[3]_' + name)
    rectifier_thyristor_v_1 = vf.add_var('rectifier.thyristor.v[1]_' + name)
    rectifier_thyristor_v_2 = vf.add_var('rectifier.thyristor.v[2]_' + name)
    rectifier_thyristor_v_3 = vf.add_var('rectifier.thyristor.v[3]_' + name)
    rectifier_vAC_1 = vf.add_var('rectifier.vAC[1]_' + name)
    rectifier_vAC_2 = vf.add_var('rectifier.vAC[2]_' + name)
    rectifier_vAC_3 = vf.add_var('rectifier.vAC[3]_' + name)
    rectifier_vDC = vf.add_var('rectifier.vDC_' + name)
    resistor_LossPower = vf.add_var('resistor.LossPower_' + name)
    resistor_R_actual = vf.add_var('resistor.R_actual_' + name)
    resistor_v = vf.add_var('resistor.v_' + name)
    rootMeanSquareVoltage_product_y = vf.add_var('rootMeanSquareVoltage.product.y_' + name)
    rootMeanSquareVoltage_y = vf.add_var('rootMeanSquareVoltage.y_' + name)
    sineVoltage_p_sineVoltage_1 = vf.add_var('sineVoltage_p.sineVoltage[1]_' + name)
    sineVoltage_p_sineVoltage_2 = vf.add_var('sineVoltage_p.sineVoltage[2]_' + name)
    sineVoltage_p_sineVoltage_3 = vf.add_var('sineVoltage_p.sineVoltage[3]_' + name)
    star_pin_n_i = vf.add_var('star.pin_n.i_' + name)
    time = vf.add_var('time_' + name)

    # --- Derivative Variables ---
    d_inductor_i = vf.add_diff_var('d_inductor.i', base_var=inductor_i)
    d_meanCurrent_x = vf.add_diff_var('d_meanCurrent.x', base_var=meanCurrent_x)
    d_meanVoltage_x = vf.add_diff_var('d_meanVoltage.x', base_var=meanVoltage_x)
    d_rootMeanSquareVoltage_mean_x = vf.add_diff_var('d_rootMeanSquareVoltage.mean.x', base_var=rootMeanSquareVoltage_mean_x)

    # --- Continuous Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (d_meanVoltage_x - rectifier_vDC),
            (d_rootMeanSquareVoltage_mean_x - rootMeanSquareVoltage_product_y),
            (d_meanCurrent_x - inductor_i),
            (d_inductor_i - inductor_v),
        ],
        state_vars=[inductor_i, meanCurrent_x, meanVoltage_x, rootMeanSquareVoltage_mean_x],

        algebraic_eqs=[
            (ground_p_i - 0.0),
            (pulsem_twomPulse_limiter_y - 0.0),
            (pulsem_twomPulse_replicator_y_3 - (0.3183098861837907 * pulsem_twomPulse_limiter_y)),
            (star_pin_n_i - inductor_i),
            (pulsem_twomPulse_v_2 - (rectifier_vAC_2 - rectifier_vAC_1)),
            (pulsem_twomPulse_gainPositive_2 - (pulsem_twomPulse_gainPositive_2 * pulsem_twomPulse_timerPositive_2)),
            (pulsem_twomPulse_positiveThreshold_2 - v_whenCondition5),
            (pulsem_twomPulse_gainNegative_2 - (pulsem_twomPulse_gainNegative_2 * pulsem_twomPulse_timerNegative_2)),
            (pulsem_twomPulse_negativeThreshold_2 - v_whenCondition2),
            (pulsem_twomPulse_v_3 - (rectifier_vAC_3 - rectifier_vAC_2)),
            (pulsem_twomPulse_gainPositive_3 - (pulsem_twomPulse_gainPositive_3 * pulsem_twomPulse_timerPositive_3)),
            (pulsem_twomPulse_positiveThreshold_3 - v_whenCondition4),
            (pulsem_twomPulse_gainNegative_3 - (pulsem_twomPulse_gainNegative_3 * pulsem_twomPulse_timerNegative_3)),
            (pulsem_twomPulse_negativeThreshold_3 - v_whenCondition1),
            (pulsem_twomPulse_v_1 - (rectifier_vAC_1 - rectifier_vAC_3)),
            (pulsem_twomPulse_gainPositive_1 - (pulsem_twomPulse_gainPositive_1 * pulsem_twomPulse_timerPositive_1)),
            (pulsem_twomPulse_positiveThreshold_1 - v_whenCondition6),
            (pulsem_twomPulse_gainNegative_1 - (pulsem_twomPulse_gainNegative_1 * pulsem_twomPulse_timerNegative_1)),
            (pulsem_twomPulse_negativeThreshold_1 - v_whenCondition3),
            (rectifier_vDC - (rectifier_vAC_3 - rectifier_thyristor_v_3)),
            (rectifier_powerAC_2 - (rectifier_vAC_2 * rectifier_iAC_2)),
            (rectifier_thyristor_idealThyristor_2 - (rectifier_thyristor_v_2 * rectifier_iAC_2)),
            (rectifier_thyristor_idealThyristor_2 - rectifier_thyristor_v_2),
            (rootMeanSquareVoltage_product_y - 0.0),
            (rectifier_powerDC - ((-rectifier_vDC) * inductor_i)),
            (rectifier_thyristor_idealThyristor_1 - rectifier_thyristor_v_1),
            (rectifier_powerAC_1 - (rectifier_vAC_1 * rectifier_iAC_1)),
            (rectifier_thyristor_idealThyristor_1 - (rectifier_thyristor_v_1 * rectifier_iAC_1)),
            (rectifier_thyristor_idealThyristor_3 - (rectifier_thyristor_v_3 * rectifier_iAC_3)),
            (rectifier_LossPower - (rectifier_thyristor_idealThyristor_1 + (rectifier_thyristor_idealThyristor_2 + rectifier_thyristor_idealThyristor_3))),
            (rectifier_thyristor_idealThyristor_3 - rectifier_thyristor_v_3),
            (rectifier_powerAC_3 - (rectifier_vAC_3 * rectifier_iAC_3)),
            (rectifier_powerTotalAC - ((rectifier_powerAC_1 + rectifier_powerAC_2) + rectifier_powerAC_3)),
            (resistor_v - (resistor_R_actual * inductor_i)),
            (resistor_LossPower - (resistor_v * inductor_i)),
            (inductor_v - (rectifier_vDC - resistor_v)),
            (v_whenCondition7 - 0.0),
            (v_whenCondition8 - 0.0),
            (rootMeanSquareVoltage_y - 0.0),
            (v_whenCondition9 - 0.0),
        ],
        algebraic_vars=[v_whenCondition1, v_whenCondition2, v_whenCondition3, v_whenCondition4, v_whenCondition5, v_whenCondition6, v_whenCondition7, v_whenCondition8, v_whenCondition9, ground_p_i, inductor_v, pulsem_fire_n_1, pulsem_fire_n_2, pulsem_fire_n_3, pulsem_fire_p_1, pulsem_fire_p_2, pulsem_fire_p_3, pulsem_twomPulse_gainNegative_1, pulsem_twomPulse_gainNegative_2, pulsem_twomPulse_gainNegative_3, pulsem_twomPulse_gainPositive_1, pulsem_twomPulse_gainPositive_2, pulsem_twomPulse_gainPositive_3, pulsem_twomPulse_limiter_y, pulsem_twomPulse_negativeThreshold_1, pulsem_twomPulse_negativeThreshold_2, pulsem_twomPulse_negativeThreshold_3, pulsem_twomPulse_positiveThreshold_1, pulsem_twomPulse_positiveThreshold_2, pulsem_twomPulse_positiveThreshold_3, pulsem_twomPulse_replicator_y_3, pulsem_twomPulse_timerNegative_1, pulsem_twomPulse_timerNegative_2, pulsem_twomPulse_timerNegative_3, pulsem_twomPulse_timerPositive_1, pulsem_twomPulse_timerPositive_2, pulsem_twomPulse_timerPositive_3, pulsem_twomPulse_v_1, pulsem_twomPulse_v_2, pulsem_twomPulse_v_3, rectifier_LossPower, rectifier_andCondition_p_1, rectifier_andCondition_p_2, rectifier_andCondition_p_3, rectifier_enableLogic_enableConstantSource_k, rectifier_iAC_1, rectifier_iAC_2, rectifier_iAC_3, rectifier_powerAC_1, rectifier_powerAC_2, rectifier_powerAC_3, rectifier_powerDC, rectifier_powerTotalAC, rectifier_thyristor_idealThyristor_1, rectifier_thyristor_idealThyristor_2, rectifier_thyristor_idealThyristor_3, rectifier_thyristor_v_1, rectifier_thyristor_v_2, rectifier_thyristor_v_3, rectifier_vAC_1, rectifier_vAC_2, rectifier_vAC_3, rectifier_vDC, resistor_LossPower, resistor_R_actual, resistor_v, rootMeanSquareVoltage_product_y, rootMeanSquareVoltage_y, sineVoltage_p_sineVoltage_1, sineVoltage_p_sineVoltage_2, sineVoltage_p_sineVoltage_3, star_pin_n_i, time],
    )

    # --- Parameter Values ---
    templ.block.event_dict = {
    }

    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        inductor_i: vf.add_const(0.0),
        ground_p_i: vf.add_const(0.0),
        rectifier_LossPower: vf.add_const(0.0),
        rectifier_T_heatPort: vf.add_const(293.15),
        rectifier_iAC_1: vf.add_const(0.0),
        rectifier_iAC_2: vf.add_const(0.0),
        rectifier_iAC_3: vf.add_const(0.0),
        rectifier_thyristor_idealThyristor_1: (rectifier_thyristor_idealThyristor_1 * rectifier_iAC_1),
        rectifier_thyristor_idealThyristor_2: (rectifier_thyristor_idealThyristor_2 * rectifier_iAC_2),
        rectifier_thyristor_idealThyristor_3: (rectifier_thyristor_idealThyristor_3 * rectifier_iAC_3),
        rectifier_thyristor_v_1: rectifier_thyristor_idealThyristor_1,
        rectifier_thyristor_v_2: rectifier_thyristor_idealThyristor_2,
        rectifier_thyristor_v_3: rectifier_thyristor_idealThyristor_3,
        resistor_LossPower: vf.add_const(0.0),
        resistor_v: vf.add_const(0.0),
        resistor_R_actual: (resistor_R * (1.0 + (resistor_alpha * (resistor_T - resistor_T_ref)))),
        pulsem_twomPulse_limiter_y: vf.add_const(0.0),
        v_whenCondition1: pulsem_twomPulse_negativeThreshold_3,
        v_whenCondition2: pulsem_twomPulse_negativeThreshold_2,
        v_whenCondition3: pulsem_twomPulse_negativeThreshold_1,
        v_whenCondition4: pulsem_twomPulse_positiveThreshold_3,
        v_whenCondition5: pulsem_twomPulse_positiveThreshold_2,
        v_whenCondition6: pulsem_twomPulse_positiveThreshold_1,
        v_PRE_rectifier_thyristor_idealThyristor_3: rectifier_offStart_3,
        v_PRE_rectifier_thyristor_idealThyristor_2: rectifier_offStart_2,
        v_PRE_rectifier_thyristor_idealThyristor_1: rectifier_offStart_1,
        v_PRE_pulsem_twomPulse_timerNegative_3: vf.add_const(0.0),
        pulsem_twomPulse_timerNegative_3: v_PRE_pulsem_twomPulse_timerNegative_3,
        v_PRE_pulsem_twomPulse_timerNegative_2: vf.add_const(0.0),
        pulsem_twomPulse_timerNegative_2: v_PRE_pulsem_twomPulse_timerNegative_2,
        v_PRE_pulsem_twomPulse_timerNegative_1: vf.add_const(0.0),
        pulsem_twomPulse_timerNegative_1: v_PRE_pulsem_twomPulse_timerNegative_1,
        v_PRE_pulsem_twomPulse_timerPositive_3: vf.add_const(0.0),
        pulsem_twomPulse_timerPositive_3: v_PRE_pulsem_twomPulse_timerPositive_3,
        v_PRE_pulsem_twomPulse_timerPositive_2: vf.add_const(0.0),
        pulsem_twomPulse_timerPositive_2: v_PRE_pulsem_twomPulse_timerPositive_2,
        v_PRE_pulsem_twomPulse_timerPositive_1: vf.add_const(0.0),
        pulsem_twomPulse_timerPositive_1: v_PRE_pulsem_twomPulse_timerPositive_1,
        rectifier_vDC: (rectifier_vAC_2 - rectifier_thyristor_idealThyristor_2),
        pulsem_ac_pin_3: vf.add_const(0.0),
        pulsem_ac_pin_2: vf.add_const(0.0),
        pulsem_ac_pin_1: vf.add_const(0.0),
        voltagesensor_p_i: vf.add_const(0.0),
        voltagesensor_n_i: vf.add_const(0.0),
        ground_p_v: vf.add_const(0.0),
        pulsem_voltageSensor_voltageSensor_1: vf.add_const(0.0),
        pulsem_voltageSensor_voltageSensor_2: vf.add_const(0.0),
        pulsem_voltageSensor_voltageSensor_3: vf.add_const(0.0),
        pulsem_delta_plug_p_pin_3: vf.add_const(0.0),
        pulsem_delta_plug_p_pin_2: vf.add_const(0.0),
        pulsem_delta_plug_p_pin_1: vf.add_const(0.0),
        rootMeanSquareVoltage_mean_y_last: rootMeanSquareVoltage_mean_y0,
        v_PRE_rootMeanSquareVoltage_mean_y_last: rootMeanSquareVoltage_mean_y_last,
        v_whenCondition7: vf.add_const(0.0),
        v_whenCondition8: vf.add_const(0.0),
        v_whenCondition9: vf.add_const(0.0),
        meanCurrent_y_last: meanCurrent_y0,
        v_PRE_meanCurrent_y_last: meanCurrent_y_last,
        meanVoltage_y_last: meanVoltage_y0,
        v_PRE_meanVoltage_y_last: meanVoltage_y_last,
        meanCurrent_x: meanCurrent_x0,
        meanCurrent_t0: time,
        rootMeanSquareVoltage_mean_x: rootMeanSquareVoltage_mean_x0,
        rootMeanSquareVoltage_mean_t0: time,
        meanVoltage_x: meanVoltage_x0,
        meanVoltage_t0: time,
        inductor_v: vf.add_const(0.0),
        pulsem_fire_n_1: vf.add_const(0.0),
        pulsem_fire_n_2: vf.add_const(0.0),
        pulsem_fire_n_3: vf.add_const(0.0),
        pulsem_fire_p_1: vf.add_const(0.0),
        pulsem_fire_p_2: vf.add_const(0.0),
        pulsem_fire_p_3: vf.add_const(0.0),
        pulsem_twomPulse_gainNegative_1: vf.add_const(0.0),
        pulsem_twomPulse_gainNegative_2: vf.add_const(0.0),
        pulsem_twomPulse_gainNegative_3: vf.add_const(0.0),
        pulsem_twomPulse_gainPositive_1: vf.add_const(0.0),
        pulsem_twomPulse_gainPositive_2: vf.add_const(0.0),
        pulsem_twomPulse_gainPositive_3: vf.add_const(0.0),
        pulsem_twomPulse_negativeThreshold_1: vf.add_const(0.0),
        pulsem_twomPulse_negativeThreshold_2: vf.add_const(0.0),
        pulsem_twomPulse_negativeThreshold_3: vf.add_const(0.0),
        pulsem_twomPulse_positiveThreshold_1: vf.add_const(0.0),
        pulsem_twomPulse_positiveThreshold_2: vf.add_const(0.0),
        pulsem_twomPulse_positiveThreshold_3: vf.add_const(0.0),
        pulsem_twomPulse_replicator_y_3: vf.add_const(0.0),
        pulsem_twomPulse_v_1: vf.add_const(0.0),
        pulsem_twomPulse_v_2: vf.add_const(0.0),
        pulsem_twomPulse_v_3: vf.add_const(0.0),
        rectifier_andCondition_p_1: vf.add_const(0.0),
        rectifier_andCondition_p_2: vf.add_const(0.0),
        rectifier_andCondition_p_3: vf.add_const(0.0),
        rectifier_enableLogic_enableConstantSource_k: vf.add_const(0.0),
        rectifier_powerAC_1: vf.add_const(0.0),
        rectifier_powerAC_2: vf.add_const(0.0),
        rectifier_powerAC_3: vf.add_const(0.0),
        rectifier_powerDC: vf.add_const(0.0),
        rectifier_powerTotalAC: vf.add_const(0.0),
        rectifier_vAC_1: vf.add_const(0.0),
        rectifier_vAC_2: vf.add_const(0.0),
        rectifier_vAC_3: vf.add_const(0.0),
        rootMeanSquareVoltage_product_y: vf.add_const(0.0),
        rootMeanSquareVoltage_y: vf.add_const(0.0),
        sineVoltage_p_sineVoltage_1: vf.add_const(0.0),
        sineVoltage_p_sineVoltage_2: vf.add_const(0.0),
        sineVoltage_p_sineVoltage_3: vf.add_const(0.0),
        star_pin_n_i: vf.add_const(0.0),
        time: vf.add_const(0.0),
    }

    return templ
