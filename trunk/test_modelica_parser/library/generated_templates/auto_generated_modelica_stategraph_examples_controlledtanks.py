# --- AUTO-GENERATED EMT TEMPLATE ---
# Source: Modelica Flat XML Transpilation

import numpy as np
from abc import ABC, abstractmethod
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

class IControlledTanksExternalFunctions(ABC):
    """
    Abstract interface for external functions detected in the Modelica XML.
    The user MUST implement these methods or register them in the symbolic engine.
    """
    @abstractmethod
    def getTimeTableValueNoDer(self, *args):
        pass
    @abstractmethod
    def pre(self, *args):
        pass


def apply_boundary_logic_modelica_stategraph_examples_controlledtanks(state):
    """Procedural logic for switching and discrete events."""
    state.tankController_s1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_s1_active else 0.0)
    state.valve1_outflow1_Fo = (state.source_maxflow if state.tankController_makeProduct_fillTank1_localActive else 0.0)
    state.tankController_makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_fillTank1_localActive else 0.0)
    state.tankController_makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_fillTank2_active else 0.0)
    state.tankController_makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_emptyTank2_active else 0.0)
    state.tankController_makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_wait1_active else 0.0)
    state.v_whenCondition15 = (state.tankController_makeProduct_wait1_active and (not state.tankController_makeProduct_fillTank2_active))
    state.tankController_makeProduct_T2_t = (state.tankController_makeProduct_T2_t_dummy if state.v_whenCondition15 else 0.0)
    state.tankController_makeProduct_T2_fire = (state.time >= (state.tankController_makeProduct_T2_t_start + state.tankController_makeProduct_T2_waitTime))
    state.tankController_makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_wait2_active else 0.0)
    state.v_whenCondition13 = (state.tankController_makeProduct_wait2_active and (not state.tankController_makeProduct_emptyTank2_active))
    state.tankController_makeProduct_T4_t = (state.tankController_makeProduct_T4_t_dummy if state.v_whenCondition13 else 0.0)
    state.tankController_makeProduct_T4_fire = (state.time >= (state.tankController_makeProduct_T4_t_start + state.tankController_makeProduct_T4_waitTime))
    state.tankController_makeProduct_outerState_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_active else 0.0)
    state.tankController_s2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_s2_active else 0.0)
    state.tankController_emptyTanks_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_emptyTanks_active else 0.0)
    state.valve3_valveControl = (state.tankController_makeProduct_emptyTank2_active or state.tankController_emptyTanks_active)
    state.valve3_outflow1_Fo = ((sym.sqrt(sym.max(0.0, ((19.6133 * state.tank2_hmax) * state.tank2_level))) * state.tank2_a) if state.valve3_valveControl else 0.0)
    state.valve2_valveControl = (state.tankController_makeProduct_fillTank2_active or state.tankController_emptyTanks_active)
    state.valve2_outflow1_Fo = ((sym.sqrt(sym.max(0.0, ((19.6133 * state.tank1_hmax) * state.tank1_level))) * state.tank1_a) if state.valve2_valveControl else 0.0)
    state.tankController_makeProduct_T1_localCondition = (state.tank1_level > state.tankController_makeProduct_limit)
    state.tankController_makeProduct_T1_enableFire = ((state.tankController_makeProduct_T1_localCondition and state.tankController_makeProduct_fillTank1_localActive) and (not state.tankController_makeProduct_wait1_active))
    state.tankController_makeProduct_T3_localCondition = (state.tank1_level < 0.001)
    state.tankController_makeProduct_T3_enableFire = ((state.tankController_makeProduct_T3_localCondition and state.tankController_makeProduct_fillTank2_active) and (not state.tankController_makeProduct_wait2_active))
    state.tankController_T2_localCondition = (state.tank2_level < 0.001)
    state.tankController_T2_enableFire = ((state.tankController_T2_localCondition and state.tankController_makeProduct_emptyTank2_active) and (not state.tankController_s1_active))
    state.tankController_s1_inPort_2 = (state.tankController_s1_active or state.tankController_T2_enableFire)
    state.tankController_T6_localCondition = ((state.tank1_level + state.tank2_level) < 0.001)
    state.tankController_T6_enableFire = ((state.tankController_T6_localCondition and state.tankController_emptyTanks_active) and (not state.tankController_s1_inPort_2))
    state.v_whenCondition10 = (state.time >= ext_funcs.pre(state.shut_table_combiTimeTable_nextTimeEvent))
    state.shut_table_y = (state.shut_table_combiTimeTable_y_1 >= state.shut_table_realToBoolean_threshold)
    state.tankController_T5_enableFire = ((state.shut_on and state.tankController_s2_active) and (not state.tankController_emptyTanks_active))
    state.tankController_s2_outPort_2 = (state.tankController_s2_active and (not state.tankController_T5_enableFire))
    state.tankController_emptyTanks_newActive = (state.tankController_T5_enableFire or (state.tankController_emptyTanks_active and (not state.tankController_T6_enableFire)))
    state.v_whenCondition11 = (state.time >= ext_funcs.pre(state.stop_table_combiTimeTable_nextTimeEvent))
    state.stop_table_y = (state.stop_table_combiTimeTable_y_1 >= state.stop_table_realToBoolean_threshold)
    state.v_whenCondition14 = ((state.stop_on and state.tankController_makeProduct_active) and (not state.tankController_s2_active))
    state.v_whenCondition12 = (state.time >= ext_funcs.pre(state.start_table_combiTimeTable_nextTimeEvent))
    state.start_table_y = (state.start_table_combiTimeTable_y_1 >= state.start_table_realToBoolean_threshold)
    state.tankController_T1_enableFire = ((state.start_on and state.tankController_s1_active) and (not state.tankController_makeProduct_fillTank1_localActive))
    state.tankController_s1_newActive = ((state.tankController_T2_enableFire or state.tankController_T6_enableFire) or (state.tankController_s1_active and (not state.tankController_T1_enableFire)))
    state.tankController_T4_enableFire = ((state.start_on and state.tankController_s2_outPort_2) and (not state.tankController_makeProduct_active))
    state.tankController_makeProduct_fillTank1_newActive = (state.tankController_makeProduct_fillTank1_oldActive if state.tankController_T4_enableFire else ((state.tankController_T1_enableFire or (state.tankController_makeProduct_fillTank1_localActive and (not state.tankController_makeProduct_T1_enableFire))) and (not state.v_whenCondition14)))
    state.tankController_makeProduct_fillTank2_newActive = (state.tankController_makeProduct_fillTank2_oldActive if state.tankController_T4_enableFire else ((state.tankController_makeProduct_T2_fire or (state.tankController_makeProduct_fillTank2_active and (not state.tankController_makeProduct_T3_enableFire))) and (not state.v_whenCondition14)))
    state.tankController_makeProduct_emptyTank2_newActive = (state.tankController_makeProduct_emptyTank2_oldActive if state.tankController_T4_enableFire else ((state.tankController_makeProduct_T4_fire or (state.tankController_makeProduct_emptyTank2_active and (not state.tankController_T2_enableFire))) and (not state.v_whenCondition14)))
    state.tankController_makeProduct_wait1_newActive = (state.tankController_makeProduct_wait1_oldActive if state.tankController_T4_enableFire else ((state.tankController_makeProduct_T1_enableFire or (state.tankController_makeProduct_wait1_active and (not state.tankController_makeProduct_T2_fire))) and (not state.v_whenCondition14)))
    state.tankController_makeProduct_wait2_newActive = (state.tankController_makeProduct_wait2_oldActive if state.tankController_T4_enableFire else ((state.tankController_makeProduct_T3_enableFire or (state.tankController_makeProduct_wait2_active and (not state.tankController_makeProduct_T4_fire))) and (not state.v_whenCondition14)))
    state.tankController_makeProduct_newActive = (state.tankController_makeProduct_activeSteps > 0.0)
    state.tankController_s2_newActive = (state.v_whenCondition14 or (state.tankController_s2_active and (not (state.tankController_T5_enableFire or state.tankController_T4_enableFire))))

    # --- Discrete Event Handlers (When Blocks) ---
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_s1_oldActive = state.tankController_s1_active
    if ext_funcs.event_triggered(state.v_whenCondition15):
        state.tankController_makeProduct_T2_t_start = state.time
    if ext_funcs.event_triggered(state.v_whenCondition13):
        state.tankController_makeProduct_T4_t_start = state.time
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_s2_oldActive = state.tankController_s2_active
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_emptyTanks_oldActive = state.tankController_emptyTanks_active
    if ext_funcs.event_triggered(state.v_whenCondition10):
        state.shut_table_combiTimeTable_nextTimeEventScaled = ext_funcs.getNextTimeEvent(state.shut_table_combiTimeTable_tableID, state.shut_table_combiTimeTable_timeScaled)
        state.shut_table_combiTimeTable_nextTimeEvent = (state.shut_table_combiTimeTable_nextTimeEventScaled if (state.shut_table_combiTimeTable_nextTimeEventScaled < 1e+60) else 1e+60)
    if ext_funcs.event_triggered(state.v_whenCondition11):
        state.stop_table_combiTimeTable_nextTimeEventScaled = ext_funcs.getNextTimeEvent(state.stop_table_combiTimeTable_tableID, state.stop_table_combiTimeTable_timeScaled)
        state.stop_table_combiTimeTable_nextTimeEvent = (state.stop_table_combiTimeTable_nextTimeEventScaled if (state.stop_table_combiTimeTable_nextTimeEventScaled < 1e+60) else 1e+60)
    if ext_funcs.event_triggered(state.v_whenCondition14):
        state.tankController_makeProduct_wait2_oldActive = state.tankController_makeProduct_wait2_active
        state.tankController_makeProduct_wait1_oldActive = state.tankController_makeProduct_wait1_active
        state.tankController_makeProduct_emptyTank2_oldActive = state.tankController_makeProduct_emptyTank2_active
        state.tankController_makeProduct_fillTank2_oldActive = state.tankController_makeProduct_fillTank2_active
        state.tankController_makeProduct_fillTank1_oldActive = state.tankController_makeProduct_fillTank1_localActive
    if ext_funcs.event_triggered(state.v_whenCondition12):
        state.start_table_combiTimeTable_nextTimeEventScaled = ext_funcs.getNextTimeEvent(state.start_table_combiTimeTable_tableID, state.start_table_combiTimeTable_timeScaled)
        state.start_table_combiTimeTable_nextTimeEvent = (state.start_table_combiTimeTable_nextTimeEventScaled if (state.start_table_combiTimeTable_nextTimeEventScaled < 1e+60) else 1e+60)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_makeProduct_T1_t_start = ext_funcs.pre(state.tankController_makeProduct_T1_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_makeProduct_T3_t_start = ext_funcs.pre(state.tankController_makeProduct_T3_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_T1_t_start = ext_funcs.pre(state.tankController_T1_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_T2_t_start = ext_funcs.pre(state.tankController_T2_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_T3_t_start = ext_funcs.pre(state.tankController_T3_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_T4_t_start = ext_funcs.pre(state.tankController_T4_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_T5_t_start = ext_funcs.pre(state.tankController_T5_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.tankController_T6_t_start = ext_funcs.pre(state.tankController_T6_t_start)

    # --- Procedural Initialization Logic ---
    # Evaluates logic blocks during the first step (t=0) to feed the symbolic solver
    if state.time == 0.0:
        state.start_table_combiTimeTable_nextTimeEvent = (state.start_table_combiTimeTable_nextTimeEventScaled if (state.start_table_combiTimeTable_nextTimeEventScaled < 1e+60) else 1e+60)
        state.stop_table_combiTimeTable_nextTimeEvent = (state.stop_table_combiTimeTable_nextTimeEventScaled if (state.stop_table_combiTimeTable_nextTimeEventScaled < 1e+60) else 1e+60)
        state.shut_table_combiTimeTable_nextTimeEvent = (state.shut_table_combiTimeTable_nextTimeEventScaled if (state.shut_table_combiTimeTable_nextTimeEventScaled < 1e+60) else 1e+60)
        state.tankController_emptyTanks_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_emptyTanks_localActive else 0.0)
        state.tankController_T5_enableFire = ((state.shut_on and state.tankController_s2_localActive) and (not state.tankController_emptyTanks_localActive))
        state.tankController_s2_outPort_2 = (state.tankController_s2_localActive and (not state.tankController_T5_enableFire))
        state.tankController_s2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_s2_localActive else 0.0)
        state.tankController_T3_enableFire = ((state.stop_on and state.tankController_makeProduct_active) and (not state.tankController_s2_localActive))
        state.tankController_s2_newActive = (state.tankController_T3_enableFire or (state.tankController_s2_localActive and (not (state.tankController_T5_enableFire or state.tankController_T4_enableFire))))
        state.tankController_makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_wait2_localActive else 0.0)
        state.tankController_makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_wait1_localActive else 0.0)
        state.tankController_makeProduct_T4_enableFire = (state.tankController_makeProduct_wait2_localActive and (not state.tankController_makeProduct_emptyTank2_localActive))
        state.tankController_makeProduct_T4_fire = (state.time >= (state.tankController_makeProduct_T4_t_start + state.tankController_makeProduct_T4_waitTime))
        state.tankController_makeProduct_T4_t = (state.tankController_makeProduct_T4_t_dummy if state.tankController_makeProduct_T4_enableFire else 0.0)
        state.tankController_makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_emptyTank2_localActive else 0.0)
        state.tankController_makeProduct_T2_enableFire = (state.tankController_makeProduct_wait1_localActive and (not state.tankController_makeProduct_fillTank2_localActive))
        state.tankController_makeProduct_T2_fire = (state.time >= (state.tankController_makeProduct_T2_t_start + state.tankController_makeProduct_T2_waitTime))
        state.tankController_makeProduct_T2_t = (state.tankController_makeProduct_T2_t_dummy if state.tankController_makeProduct_T2_enableFire else 0.0)
        state.tankController_makeProduct_T3_enableFire = ((state.tankController_makeProduct_T3_localCondition and state.tankController_makeProduct_fillTank2_localActive) and (not state.tankController_makeProduct_wait2_localActive))
        state.tankController_makeProduct_wait2_newActive = (state.tankController_makeProduct_wait2_oldActive if state.tankController_T4_enableFire else ((state.tankController_makeProduct_T3_enableFire or (state.tankController_makeProduct_wait2_localActive and (not state.tankController_makeProduct_T4_fire))) and (not state.tankController_T3_enableFire)))
        state.tankController_makeProduct_fillTank2_newActive = (state.tankController_makeProduct_fillTank2_oldActive if state.tankController_T4_enableFire else ((state.tankController_makeProduct_T2_fire or (state.tankController_makeProduct_fillTank2_localActive and (not state.tankController_makeProduct_T3_enableFire))) and (not state.tankController_T3_enableFire)))
        state.tankController_makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_fillTank2_localActive else 0.0)
        state.valve1_outflow1_Fo = (state.source_maxflow if state.tankController_makeProduct_fillTank1_active else 0.0)
        state.tankController_makeProduct_T1_enableFire = ((state.tankController_makeProduct_T1_localCondition and state.tankController_makeProduct_fillTank1_active) and (not state.tankController_makeProduct_wait1_localActive))
        state.tankController_makeProduct_wait1_newActive = (state.tankController_makeProduct_wait1_oldActive if state.tankController_T4_enableFire else ((state.tankController_makeProduct_T1_enableFire or (state.tankController_makeProduct_wait1_localActive and (not state.tankController_makeProduct_T2_fire))) and (not state.tankController_T3_enableFire)))
        state.tankController_makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_makeProduct_fillTank1_active else 0.0)
        state.tankController_makeProduct_newActive = (state.tankController_makeProduct_activeSteps > 0.0)
        state.tankController_T2_enableFire = ((state.tankController_T2_localCondition and state.tankController_makeProduct_emptyTank2_localActive) and (not state.tankController_s1_localActive))
        state.tankController_makeProduct_emptyTank2_newActive = (state.tankController_makeProduct_emptyTank2_oldActive if state.tankController_T4_enableFire else ((state.tankController_makeProduct_T4_fire or (state.tankController_makeProduct_emptyTank2_localActive and (not state.tankController_T2_enableFire))) and (not state.tankController_T3_enableFire)))
        state.tankController_T1_enableFire = ((state.start_on and state.tankController_s1_localActive) and (not state.tankController_makeProduct_fillTank1_active))
        state.tankController_makeProduct_fillTank1_newActive = (state.tankController_makeProduct_fillTank1_oldActive if state.tankController_T4_enableFire else ((state.tankController_T1_enableFire or (state.tankController_makeProduct_fillTank1_localActive and (not state.tankController_makeProduct_T1_enableFire))) and (not state.tankController_T3_enableFire)))
        state.tankController_s1_inPort_2 = (state.tankController_s1_localActive or state.tankController_T2_enableFire)
        state.tankController_T6_enableFire = ((state.tankController_T6_localCondition and state.tankController_emptyTanks_localActive) and (not state.tankController_s1_inPort_2))
        state.tankController_emptyTanks_newActive = (state.tankController_T5_enableFire or (state.tankController_emptyTanks_localActive and (not state.tankController_T6_enableFire)))
        state.tankController_s1_newActive = ((state.tankController_T2_enableFire or state.tankController_T6_enableFire) or (state.tankController_s1_localActive and (not state.tankController_T1_enableFire)))
        state.tankController_s1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.tankController_s1_localActive else 0.0)
        state.v_whenCondition10 = (state.time >= state.v_PRE_shut_table_combiTimeTable_nextTimeEvent)
        state.v_whenCondition11 = (state.time >= state.v_PRE_stop_table_combiTimeTable_nextTimeEvent)
        state.v_whenCondition12 = (state.time >= state.v_PRE_start_table_combiTimeTable_nextTimeEvent)


def get_modelica_stategraph_examples_controlledtanks_emt_template(vf: VarFactory, name: str='Modelica.StateGraph.Examples.ControlledTanks') -> EmtModelTemplate:
    """Initializes the continuous DAE block and factory variables."""
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice  # TODO: Verify correct DeviceType
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---
    tank1_level = vf.add_var('tank1.level_' + name)
    tank2_level = vf.add_var('tank2.level_' + name)

    # --- Algebraic Variables ---
    v_cse1 = vf.add_var('$cse1_' + name)
    v_cse2 = vf.add_var('$cse2_' + name)
    v_cse3 = vf.add_var('$cse3_' + name)
    v_whenCondition10 = vf.add_var('$whenCondition10_' + name)
    v_whenCondition11 = vf.add_var('$whenCondition11_' + name)
    v_whenCondition12 = vf.add_var('$whenCondition12_' + name)
    v_whenCondition13 = vf.add_var('$whenCondition13_' + name)
    v_whenCondition14 = vf.add_var('$whenCondition14_' + name)
    v_whenCondition15 = vf.add_var('$whenCondition15_' + name)
    shut_on = vf.add_var('shut.on_' + name)
    shut_reset_1 = vf.add_var('shut.reset[1]_' + name)
    shut_reset_2 = vf.add_var('shut.reset[2]_' + name)
    shut_table_combiTimeTable_nextTimeEvent = vf.add_var('shut.table.combiTimeTable.nextTimeEvent_' + name)
    shut_table_combiTimeTable_nextTimeEventScaled = vf.add_var('shut.table.combiTimeTable.nextTimeEventScaled_' + name)
    shut_table_combiTimeTable_p_offset_1 = vf.add_var('shut.table.combiTimeTable.p_offset[1]_' + name)
    shut_table_combiTimeTable_tableID = vf.add_var('shut.table.combiTimeTable.tableID_' + name)
    shut_table_combiTimeTable_timeScaled = vf.add_var('shut.table.combiTimeTable.timeScaled_' + name)
    shut_table_combiTimeTable_y_1 = vf.add_var('shut.table.combiTimeTable.y[1]_' + name)
    shut_table_realToBoolean_threshold = vf.add_var('shut.table.realToBoolean.threshold_' + name)
    shut_table_y = vf.add_var('shut.table.y_' + name)
    source_maxflow = vf.add_var('source.maxflow_' + name)
    start_on = vf.add_var('start.on_' + name)
    start_reset_1 = vf.add_var('start.reset[1]_' + name)
    start_reset_2 = vf.add_var('start.reset[2]_' + name)
    start_table_combiTimeTable_nextTimeEvent = vf.add_var('start.table.combiTimeTable.nextTimeEvent_' + name)
    start_table_combiTimeTable_nextTimeEventScaled = vf.add_var('start.table.combiTimeTable.nextTimeEventScaled_' + name)
    start_table_combiTimeTable_p_offset_1 = vf.add_var('start.table.combiTimeTable.p_offset[1]_' + name)
    start_table_combiTimeTable_tableID = vf.add_var('start.table.combiTimeTable.tableID_' + name)
    start_table_combiTimeTable_timeScaled = vf.add_var('start.table.combiTimeTable.timeScaled_' + name)
    start_table_combiTimeTable_y_1 = vf.add_var('start.table.combiTimeTable.y[1]_' + name)
    start_table_realToBoolean_threshold = vf.add_var('start.table.realToBoolean.threshold_' + name)
    start_table_y = vf.add_var('start.table.y_' + name)
    stateGraphRoot_activeSteps = vf.add_var('stateGraphRoot.activeSteps_' + name)
    stateGraphRoot_subgraphStatePort_activeSteps = vf.add_var('stateGraphRoot.subgraphStatePort.activeSteps_' + name)
    stop_on = vf.add_var('stop.on_' + name)
    stop_reset_1 = vf.add_var('stop.reset[1]_' + name)
    stop_reset_2 = vf.add_var('stop.reset[2]_' + name)
    stop_table_combiTimeTable_nextTimeEvent = vf.add_var('stop.table.combiTimeTable.nextTimeEvent_' + name)
    stop_table_combiTimeTable_nextTimeEventScaled = vf.add_var('stop.table.combiTimeTable.nextTimeEventScaled_' + name)
    stop_table_combiTimeTable_p_offset_1 = vf.add_var('stop.table.combiTimeTable.p_offset[1]_' + name)
    stop_table_combiTimeTable_tableID = vf.add_var('stop.table.combiTimeTable.tableID_' + name)
    stop_table_combiTimeTable_timeScaled = vf.add_var('stop.table.combiTimeTable.timeScaled_' + name)
    stop_table_combiTimeTable_y_1 = vf.add_var('stop.table.combiTimeTable.y[1]_' + name)
    stop_table_realToBoolean_threshold = vf.add_var('stop.table.realToBoolean.threshold_' + name)
    stop_table_y = vf.add_var('stop.table.y_' + name)
    tank1_A = vf.add_var('tank1.A_' + name)
    tank1_a = vf.add_var('tank1.a_' + name)
    tank1_hmax = vf.add_var('tank1.hmax_' + name)
    tank2_A = vf.add_var('tank2.A_' + name)
    tank2_a = vf.add_var('tank2.a_' + name)
    tank2_hmax = vf.add_var('tank2.hmax_' + name)
    tankController_T1_enableFire = vf.add_var('tankController.T1.enableFire_' + name)
    tankController_T2_enableFire = vf.add_var('tankController.T2.enableFire_' + name)
    tankController_T2_localCondition = vf.add_var('tankController.T2.localCondition_' + name)
    tankController_T3_enableFire = vf.add_var('tankController.T3.enableFire_' + name)
    tankController_T4_enableFire = vf.add_var('tankController.T4.enableFire_' + name)
    tankController_T5_enableFire = vf.add_var('tankController.T5.enableFire_' + name)
    tankController_T6_enableFire = vf.add_var('tankController.T6.enableFire_' + name)
    tankController_T6_localCondition = vf.add_var('tankController.T6.localCondition_' + name)
    tankController_emptyTanks_active = vf.add_var('tankController.emptyTanks.active_' + name)
    tankController_emptyTanks_localActive = vf.add_var('tankController.emptyTanks.localActive_' + name)
    tankController_emptyTanks_newActive = vf.add_var('tankController.emptyTanks.newActive_' + name)
    tankController_emptyTanks_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('tankController.emptyTanks.outerStatePort.subgraphStatePort.activeSteps_' + name)
    tankController_makeProduct_T1_enableFire = vf.add_var('tankController.makeProduct.T1.enableFire_' + name)
    tankController_makeProduct_T1_localCondition = vf.add_var('tankController.makeProduct.T1.localCondition_' + name)
    tankController_makeProduct_T2_enableFire = vf.add_var('tankController.makeProduct.T2.enableFire_' + name)
    tankController_makeProduct_T2_fire = vf.add_var('tankController.makeProduct.T2.fire_' + name)
    tankController_makeProduct_T2_t = vf.add_var('tankController.makeProduct.T2.t_' + name)
    tankController_makeProduct_T2_t_dummy = vf.add_var('tankController.makeProduct.T2.t_dummy_' + name)
    tankController_makeProduct_T2_t_start = vf.add_var('tankController.makeProduct.T2.t_start_' + name)
    tankController_makeProduct_T2_waitTime = vf.add_var('tankController.makeProduct.T2.waitTime_' + name)
    tankController_makeProduct_T3_enableFire = vf.add_var('tankController.makeProduct.T3.enableFire_' + name)
    tankController_makeProduct_T3_localCondition = vf.add_var('tankController.makeProduct.T3.localCondition_' + name)
    tankController_makeProduct_T4_enableFire = vf.add_var('tankController.makeProduct.T4.enableFire_' + name)
    tankController_makeProduct_T4_fire = vf.add_var('tankController.makeProduct.T4.fire_' + name)
    tankController_makeProduct_T4_t = vf.add_var('tankController.makeProduct.T4.t_' + name)
    tankController_makeProduct_T4_t_dummy = vf.add_var('tankController.makeProduct.T4.t_dummy_' + name)
    tankController_makeProduct_T4_t_start = vf.add_var('tankController.makeProduct.T4.t_start_' + name)
    tankController_makeProduct_T4_waitTime = vf.add_var('tankController.makeProduct.T4.waitTime_' + name)
    tankController_makeProduct_active = vf.add_var('tankController.makeProduct.active_' + name)
    tankController_makeProduct_activeSteps = vf.add_var('tankController.makeProduct.activeSteps_' + name)
    tankController_makeProduct_emptyTank2_active = vf.add_var('tankController.makeProduct.emptyTank2.active_' + name)
    tankController_makeProduct_emptyTank2_localActive = vf.add_var('tankController.makeProduct.emptyTank2.localActive_' + name)
    tankController_makeProduct_emptyTank2_newActive = vf.add_var('tankController.makeProduct.emptyTank2.newActive_' + name)
    tankController_makeProduct_emptyTank2_oldActive = vf.add_var('tankController.makeProduct.emptyTank2.oldActive_' + name)
    tankController_makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('tankController.makeProduct.emptyTank2.outerStatePort.subgraphStatePort.activeSteps_' + name)
    tankController_makeProduct_fillTank1_active = vf.add_var('tankController.makeProduct.fillTank1.active_' + name)
    tankController_makeProduct_fillTank1_localActive = vf.add_var('tankController.makeProduct.fillTank1.localActive_' + name)
    tankController_makeProduct_fillTank1_newActive = vf.add_var('tankController.makeProduct.fillTank1.newActive_' + name)
    tankController_makeProduct_fillTank1_oldActive = vf.add_var('tankController.makeProduct.fillTank1.oldActive_' + name)
    tankController_makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('tankController.makeProduct.fillTank1.outerStatePort.subgraphStatePort.activeSteps_' + name)
    tankController_makeProduct_fillTank2_active = vf.add_var('tankController.makeProduct.fillTank2.active_' + name)
    tankController_makeProduct_fillTank2_localActive = vf.add_var('tankController.makeProduct.fillTank2.localActive_' + name)
    tankController_makeProduct_fillTank2_newActive = vf.add_var('tankController.makeProduct.fillTank2.newActive_' + name)
    tankController_makeProduct_fillTank2_oldActive = vf.add_var('tankController.makeProduct.fillTank2.oldActive_' + name)
    tankController_makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('tankController.makeProduct.fillTank2.outerStatePort.subgraphStatePort.activeSteps_' + name)
    tankController_makeProduct_limit = vf.add_var('tankController.makeProduct.limit_' + name)
    tankController_makeProduct_newActive = vf.add_var('tankController.makeProduct.newActive_' + name)
    tankController_makeProduct_outerState_subgraphStatePort_activeSteps = vf.add_var('tankController.makeProduct.outerState.subgraphStatePort.activeSteps_' + name)
    tankController_makeProduct_stateGraphRoot_subgraphStatePort_activeSteps = vf.add_var('tankController.makeProduct.stateGraphRoot.subgraphStatePort.activeSteps_' + name)
    tankController_makeProduct_wait1_active = vf.add_var('tankController.makeProduct.wait1.active_' + name)
    tankController_makeProduct_wait1_localActive = vf.add_var('tankController.makeProduct.wait1.localActive_' + name)
    tankController_makeProduct_wait1_newActive = vf.add_var('tankController.makeProduct.wait1.newActive_' + name)
    tankController_makeProduct_wait1_oldActive = vf.add_var('tankController.makeProduct.wait1.oldActive_' + name)
    tankController_makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('tankController.makeProduct.wait1.outerStatePort.subgraphStatePort.activeSteps_' + name)
    tankController_makeProduct_wait2_active = vf.add_var('tankController.makeProduct.wait2.active_' + name)
    tankController_makeProduct_wait2_localActive = vf.add_var('tankController.makeProduct.wait2.localActive_' + name)
    tankController_makeProduct_wait2_newActive = vf.add_var('tankController.makeProduct.wait2.newActive_' + name)
    tankController_makeProduct_wait2_oldActive = vf.add_var('tankController.makeProduct.wait2.oldActive_' + name)
    tankController_makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('tankController.makeProduct.wait2.outerStatePort.subgraphStatePort.activeSteps_' + name)
    tankController_s1_active = vf.add_var('tankController.s1.active_' + name)
    tankController_s1_inPort_2 = vf.add_var('tankController.s1.inPort[2]_' + name)
    tankController_s1_localActive = vf.add_var('tankController.s1.localActive_' + name)
    tankController_s1_newActive = vf.add_var('tankController.s1.newActive_' + name)
    tankController_s1_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('tankController.s1.outerStatePort.subgraphStatePort.activeSteps_' + name)
    tankController_s2_active = vf.add_var('tankController.s2.active_' + name)
    tankController_s2_localActive = vf.add_var('tankController.s2.localActive_' + name)
    tankController_s2_newActive = vf.add_var('tankController.s2.newActive_' + name)
    tankController_s2_outPort_2 = vf.add_var('tankController.s2.outPort[2]_' + name)
    tankController_s2_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('tankController.s2.outerStatePort.subgraphStatePort.activeSteps_' + name)
    time = vf.add_var('time_' + name)
    valve1_outflow1_Fo = vf.add_var('valve1.outflow1.Fo_' + name)
    valve2_outflow1_Fo = vf.add_var('valve2.outflow1.Fo_' + name)
    valve2_valveControl = vf.add_var('valve2.valveControl_' + name)
    valve3_outflow1_Fo = vf.add_var('valve3.outflow1.Fo_' + name)
    valve3_valveControl = vf.add_var('valve3.valveControl_' + name)

    # --- Derivative Variables ---
    d_tank1_level = vf.add_diff_var('d_tank1.level', base_var=tank1_level)
    d_tank2_level = vf.add_diff_var('d_tank2.level', base_var=tank2_level)

    # --- Continuous Block Assembly ---
    templ.block = Block(
        state_eqs=[
            (d_tank2_level - ((valve2_outflow1_Fo - valve3_outflow1_Fo) / (tank2_hmax * tank2_A))),
            (d_tank1_level - ((valve1_outflow1_Fo - valve2_outflow1_Fo) / (tank1_hmax * tank1_A))),
        ],
        state_vars=[tank1_level, tank2_level],

        algebraic_eqs=[
            (tankController_s1_active - sym.pre(tankController_s1_newActive)),
            (tankController_s1_localActive - tankController_s1_active),
            (tankController_makeProduct_fillTank1_localActive - sym.pre(tankController_makeProduct_fillTank1_newActive)),
            (tankController_makeProduct_fillTank1_active - tankController_makeProduct_fillTank1_localActive),
            (tankController_makeProduct_fillTank2_active - sym.pre(tankController_makeProduct_fillTank2_newActive)),
            (tankController_makeProduct_fillTank2_localActive - tankController_makeProduct_fillTank2_active),
            (tankController_makeProduct_emptyTank2_active - sym.pre(tankController_makeProduct_emptyTank2_newActive)),
            (tankController_makeProduct_emptyTank2_localActive - tankController_makeProduct_emptyTank2_active),
            (tankController_makeProduct_wait1_active - sym.pre(tankController_makeProduct_wait1_newActive)),
            (tankController_makeProduct_T2_t_dummy - (time - tankController_makeProduct_T2_t_start)),
            (tankController_makeProduct_T2_enableFire - v_whenCondition15),
            (tankController_makeProduct_wait1_localActive - tankController_makeProduct_wait1_active),
            (tankController_makeProduct_wait2_active - sym.pre(tankController_makeProduct_wait2_newActive)),
            (tankController_makeProduct_stateGraphRoot_subgraphStatePort_activeSteps - (((((-tankController_makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps) - tankController_makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps) - tankController_makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps) - tankController_makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps) - tankController_makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps)),
            (tankController_makeProduct_activeSteps - (-0.0)),
            (tankController_makeProduct_T4_t_dummy - (time - tankController_makeProduct_T4_t_start)),
            (tankController_makeProduct_T4_enableFire - v_whenCondition13),
            (tankController_makeProduct_wait2_localActive - tankController_makeProduct_wait2_active),
            (tankController_makeProduct_active - sym.pre(tankController_makeProduct_newActive)),
            (tankController_s2_active - sym.pre(tankController_s2_newActive)),
            (tankController_s2_localActive - tankController_s2_active),
            (tankController_emptyTanks_active - sym.pre(tankController_emptyTanks_newActive)),
            (stateGraphRoot_subgraphStatePort_activeSteps - ((((-tankController_emptyTanks_outerStatePort_subgraphStatePort_activeSteps) - tankController_s2_outerStatePort_subgraphStatePort_activeSteps) - tankController_makeProduct_outerState_subgraphStatePort_activeSteps) - tankController_s1_outerStatePort_subgraphStatePort_activeSteps)),
            (stateGraphRoot_activeSteps - (-0.0)),
            (tankController_emptyTanks_localActive - tankController_emptyTanks_active),
            (start_table_combiTimeTable_timeScaled - time),
            (stop_table_combiTimeTable_timeScaled - time),
            (shut_table_combiTimeTable_timeScaled - time),
            (v_cse3 - sym.getTimeTableValueNoDer(shut_table_combiTimeTable_tableID, 1.0, shut_table_combiTimeTable_timeScaled, shut_table_combiTimeTable_nextTimeEventScaled, sym.pre(shut_table_combiTimeTable_nextTimeEventScaled))),
            (shut_table_combiTimeTable_y_1 - (shut_table_combiTimeTable_p_offset_1 + v_cse3)),
            (start_reset_2 - shut_on),
            (stop_reset_2 - start_reset_2),
            (v_cse2 - sym.getTimeTableValueNoDer(stop_table_combiTimeTable_tableID, 1.0, stop_table_combiTimeTable_timeScaled, stop_table_combiTimeTable_nextTimeEventScaled, sym.pre(stop_table_combiTimeTable_nextTimeEventScaled))),
            (stop_table_combiTimeTable_y_1 - (stop_table_combiTimeTable_p_offset_1 + v_cse2)),
            (tankController_T3_enableFire - v_whenCondition14),
            (start_reset_1 - stop_on),
            (shut_reset_2 - start_reset_1),
            (v_cse1 - sym.getTimeTableValueNoDer(start_table_combiTimeTable_tableID, 1.0, start_table_combiTimeTable_timeScaled, start_table_combiTimeTable_nextTimeEventScaled, sym.pre(start_table_combiTimeTable_nextTimeEventScaled))),
            (start_table_combiTimeTable_y_1 - (start_table_combiTimeTable_p_offset_1 + v_cse1)),
            (stop_reset_1 - start_on),
            (shut_reset_1 - stop_reset_1),
        ],
        algebraic_vars=[v_cse1, v_cse2, v_cse3, v_whenCondition10, v_whenCondition11, v_whenCondition12, v_whenCondition13, v_whenCondition14, v_whenCondition15, shut_on, shut_reset_1, shut_reset_2, shut_table_combiTimeTable_nextTimeEvent, shut_table_combiTimeTable_nextTimeEventScaled, shut_table_combiTimeTable_p_offset_1, shut_table_combiTimeTable_tableID, shut_table_combiTimeTable_timeScaled, shut_table_combiTimeTable_y_1, shut_table_realToBoolean_threshold, shut_table_y, source_maxflow, start_on, start_reset_1, start_reset_2, start_table_combiTimeTable_nextTimeEvent, start_table_combiTimeTable_nextTimeEventScaled, start_table_combiTimeTable_p_offset_1, start_table_combiTimeTable_tableID, start_table_combiTimeTable_timeScaled, start_table_combiTimeTable_y_1, start_table_realToBoolean_threshold, start_table_y, stateGraphRoot_activeSteps, stateGraphRoot_subgraphStatePort_activeSteps, stop_on, stop_reset_1, stop_reset_2, stop_table_combiTimeTable_nextTimeEvent, stop_table_combiTimeTable_nextTimeEventScaled, stop_table_combiTimeTable_p_offset_1, stop_table_combiTimeTable_tableID, stop_table_combiTimeTable_timeScaled, stop_table_combiTimeTable_y_1, stop_table_realToBoolean_threshold, stop_table_y, tank1_A, tank1_a, tank1_hmax, tank2_A, tank2_a, tank2_hmax, tankController_T1_enableFire, tankController_T2_enableFire, tankController_T2_localCondition, tankController_T3_enableFire, tankController_T4_enableFire, tankController_T5_enableFire, tankController_T6_enableFire, tankController_T6_localCondition, tankController_emptyTanks_active, tankController_emptyTanks_localActive, tankController_emptyTanks_newActive, tankController_emptyTanks_outerStatePort_subgraphStatePort_activeSteps, tankController_makeProduct_T1_enableFire, tankController_makeProduct_T1_localCondition, tankController_makeProduct_T2_enableFire, tankController_makeProduct_T2_fire, tankController_makeProduct_T2_t, tankController_makeProduct_T2_t_dummy, tankController_makeProduct_T2_t_start, tankController_makeProduct_T2_waitTime, tankController_makeProduct_T3_enableFire, tankController_makeProduct_T3_localCondition, tankController_makeProduct_T4_enableFire, tankController_makeProduct_T4_fire, tankController_makeProduct_T4_t, tankController_makeProduct_T4_t_dummy, tankController_makeProduct_T4_t_start, tankController_makeProduct_T4_waitTime, tankController_makeProduct_active, tankController_makeProduct_activeSteps, tankController_makeProduct_emptyTank2_active, tankController_makeProduct_emptyTank2_localActive, tankController_makeProduct_emptyTank2_newActive, tankController_makeProduct_emptyTank2_oldActive, tankController_makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps, tankController_makeProduct_fillTank1_active, tankController_makeProduct_fillTank1_localActive, tankController_makeProduct_fillTank1_newActive, tankController_makeProduct_fillTank1_oldActive, tankController_makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps, tankController_makeProduct_fillTank2_active, tankController_makeProduct_fillTank2_localActive, tankController_makeProduct_fillTank2_newActive, tankController_makeProduct_fillTank2_oldActive, tankController_makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps, tankController_makeProduct_limit, tankController_makeProduct_newActive, tankController_makeProduct_outerState_subgraphStatePort_activeSteps, tankController_makeProduct_stateGraphRoot_subgraphStatePort_activeSteps, tankController_makeProduct_wait1_active, tankController_makeProduct_wait1_localActive, tankController_makeProduct_wait1_newActive, tankController_makeProduct_wait1_oldActive, tankController_makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps, tankController_makeProduct_wait2_active, tankController_makeProduct_wait2_localActive, tankController_makeProduct_wait2_newActive, tankController_makeProduct_wait2_oldActive, tankController_makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps, tankController_s1_active, tankController_s1_inPort_2, tankController_s1_localActive, tankController_s1_newActive, tankController_s1_outerStatePort_subgraphStatePort_activeSteps, tankController_s2_active, tankController_s2_localActive, tankController_s2_newActive, tankController_s2_outPort_2, tankController_s2_outerStatePort_subgraphStatePort_activeSteps, time, valve1_outflow1_Fo, valve2_outflow1_Fo, valve2_valveControl, valve3_outflow1_Fo, valve3_valveControl],
    )

    # --- Parameter Values ---
    templ.block.event_dict = {
    }

    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        tank1_level: vf.add_const(0.0),
        tank2_level: vf.add_const(0.0),
        shut_table_combiTimeTable_timeScaled: vf.add_const(0.0),
        start_table_combiTimeTable_timeScaled: vf.add_const(0.0),
        stop_table_combiTimeTable_timeScaled: vf.add_const(0.0),
        shut_table_combiTimeTable_nextTimeEvent: vf.add_const(0.0),
        shut_table_combiTimeTable_nextTimeEventScaled: vf.add_const(0.0),
        start_table_combiTimeTable_nextTimeEvent: vf.add_const(0.0),
        start_table_combiTimeTable_nextTimeEventScaled: vf.add_const(0.0),
        stop_table_combiTimeTable_nextTimeEvent: vf.add_const(0.0),
        stop_table_combiTimeTable_nextTimeEventScaled: vf.add_const(0.0),
        shut_on: vf.add_const(0.0),
        shut_reset_1: vf.add_const(0.0),
        shut_reset_2: vf.add_const(0.0),
        shut_table_y: vf.add_const(0.0),
        start_on: vf.add_const(0.0),
        start_reset_1: vf.add_const(0.0),
        start_reset_2: vf.add_const(0.0),
        start_table_y: vf.add_const(0.0),
        stop_on: vf.add_const(0.0),
        stop_reset_1: vf.add_const(0.0),
        stop_reset_2: vf.add_const(0.0),
        stop_table_y: vf.add_const(0.0),
        tankController_T2_localCondition: vf.add_const(1.0),
        tankController_T6_localCondition: vf.add_const(1.0),
        tankController_makeProduct_T1_localCondition: vf.add_const(0.0),
        tankController_makeProduct_T3_localCondition: vf.add_const(1.0),
        tankController_makeProduct_stateGraphRoot_subgraphStatePort_activeStepsDummy: vf.add_const(0.0),
        tankController_makeProduct_T1_t_dummy: vf.add_const(0.0),
        tankController_makeProduct_T1_t: vf.add_const(0.0),
        tankController_makeProduct_T3_t_dummy: vf.add_const(0.0),
        tankController_makeProduct_T3_t: vf.add_const(0.0),
        tankController_T1_t_dummy: vf.add_const(0.0),
        tankController_T1_t: vf.add_const(0.0),
        tankController_T2_t_dummy: vf.add_const(0.0),
        tankController_T2_t: vf.add_const(0.0),
        tankController_T3_t_dummy: vf.add_const(0.0),
        tankController_T3_t: vf.add_const(0.0),
        tankController_T4_t_dummy: vf.add_const(0.0),
        tankController_T4_t: vf.add_const(0.0),
        tankController_T5_t_dummy: vf.add_const(0.0),
        tankController_T5_t: vf.add_const(0.0),
        tankController_T6_t_dummy: vf.add_const(0.0),
        tankController_T6_t: vf.add_const(0.0),
        stateGraphRoot_subgraphStatePort_activeStepsDummy: vf.add_const(0.0),
        tankController_makeProduct_T2_condition: vf.add_const(1.0),
        tankController_makeProduct_T4_condition: vf.add_const(1.0),
        stateGraphRoot_suspend: vf.add_const(0.0),
        stateGraphRoot_resume: vf.add_const(0.0),
        v_PRE_tankController_T6_t_start: time,
        tankController_T6_t_start: v_PRE_tankController_T6_t_start,
        v_PRE_tankController_T5_t_start: time,
        tankController_T5_t_start: v_PRE_tankController_T5_t_start,
        v_PRE_tankController_T4_t_start: time,
        tankController_T4_t_start: v_PRE_tankController_T4_t_start,
        v_PRE_tankController_T3_t_start: time,
        tankController_T3_t_start: v_PRE_tankController_T3_t_start,
        v_PRE_tankController_T2_t_start: time,
        tankController_T2_t_start: v_PRE_tankController_T2_t_start,
        v_PRE_tankController_T1_t_start: time,
        tankController_T1_t_start: v_PRE_tankController_T1_t_start,
        v_PRE_tankController_makeProduct_T3_t_start: time,
        tankController_makeProduct_T3_t_start: v_PRE_tankController_makeProduct_T3_t_start,
        v_PRE_tankController_makeProduct_T1_t_start: time,
        tankController_makeProduct_T1_t_start: v_PRE_tankController_makeProduct_T1_t_start,
        v_PRE_start_table_y: vf.add_const(0.0),
        v_PRE_start_table_combiTimeTable_nextTimeEventScaled: vf.add_const(0.0),
        start_table_combiTimeTable_y_1: (start_table_combiTimeTable_p_offset_1 + sym.getTimeTableValueNoDer(start_table_combiTimeTable_tableID, 1.0, start_table_combiTimeTable_timeScaled, start_table_combiTimeTable_nextTimeEventScaled, v_PRE_start_table_combiTimeTable_nextTimeEventScaled)),
        v_PRE_start_reset_2: vf.add_const(0.0),
        v_PRE_start_reset_1: vf.add_const(0.0),
        v_PRE_stop_table_y: vf.add_const(0.0),
        v_PRE_stop_table_combiTimeTable_nextTimeEventScaled: vf.add_const(0.0),
        stop_table_combiTimeTable_y_1: (stop_table_combiTimeTable_p_offset_1 + sym.getTimeTableValueNoDer(stop_table_combiTimeTable_tableID, 1.0, stop_table_combiTimeTable_timeScaled, stop_table_combiTimeTable_nextTimeEventScaled, v_PRE_stop_table_combiTimeTable_nextTimeEventScaled)),
        v_PRE_stop_reset_2: vf.add_const(0.0),
        v_PRE_stop_reset_1: vf.add_const(0.0),
        v_PRE_shut_table_y: vf.add_const(0.0),
        v_PRE_shut_table_combiTimeTable_nextTimeEventScaled: vf.add_const(0.0),
        shut_table_combiTimeTable_y_1: (shut_table_combiTimeTable_p_offset_1 + sym.getTimeTableValueNoDer(shut_table_combiTimeTable_tableID, 1.0, shut_table_combiTimeTable_timeScaled, shut_table_combiTimeTable_nextTimeEventScaled, v_PRE_shut_table_combiTimeTable_nextTimeEventScaled)),
        v_PRE_shut_reset_2: vf.add_const(0.0),
        v_PRE_shut_reset_1: vf.add_const(0.0),
        v_PRE_start_on: vf.add_const(0.0),
        v_PRE_stop_on: vf.add_const(0.0),
        v_PRE_shut_on: vf.add_const(0.0),
        tankController_emptyTanks_active: vf.add_const(0.0),
        v_PRE_tankController_emptyTanks_newActive: tankController_emptyTanks_localActive,
        v_PRE_tankController_emptyTanks_localActive: v_PRE_tankController_emptyTanks_newActive,
        v_PRE_tankController_emptyTanks_oldActive: v_PRE_tankController_emptyTanks_localActive,
        tankController_emptyTanks_oldActive: v_PRE_tankController_emptyTanks_oldActive,
        tankController_s2_active: vf.add_const(0.0),
        v_PRE_tankController_s2_newActive: tankController_s2_localActive,
        v_PRE_tankController_s2_localActive: v_PRE_tankController_s2_newActive,
        v_PRE_tankController_s2_oldActive: v_PRE_tankController_s2_localActive,
        tankController_s2_oldActive: v_PRE_tankController_s2_oldActive,
        v_PRE_tankController_makeProduct_newActive: vf.add_const(0.0),
        tankController_makeProduct_active: v_PRE_tankController_makeProduct_newActive,
        v_whenCondition14: tankController_T3_enableFire,
        v_PRE_tankController_makeProduct_T4_t_start: time,
        tankController_makeProduct_T4_t_start: v_PRE_tankController_makeProduct_T4_t_start,
        tankController_makeProduct_wait2_active: vf.add_const(0.0),
        v_PRE_tankController_makeProduct_wait2_newActive: tankController_makeProduct_wait2_localActive,
        v_PRE_tankController_makeProduct_wait2_localActive: v_PRE_tankController_makeProduct_wait2_newActive,
        v_PRE_tankController_makeProduct_wait2_oldActive: v_PRE_tankController_makeProduct_wait2_localActive,
        tankController_makeProduct_wait2_oldActive: v_PRE_tankController_makeProduct_wait2_oldActive,
        v_PRE_tankController_makeProduct_T2_t_start: time,
        tankController_makeProduct_T2_t_start: v_PRE_tankController_makeProduct_T2_t_start,
        tankController_makeProduct_wait1_active: vf.add_const(0.0),
        v_PRE_tankController_makeProduct_wait1_newActive: tankController_makeProduct_wait1_localActive,
        v_PRE_tankController_makeProduct_wait1_localActive: v_PRE_tankController_makeProduct_wait1_newActive,
        v_PRE_tankController_makeProduct_wait1_oldActive: v_PRE_tankController_makeProduct_wait1_localActive,
        tankController_makeProduct_wait1_oldActive: v_PRE_tankController_makeProduct_wait1_oldActive,
        tankController_makeProduct_emptyTank2_active: vf.add_const(0.0),
        v_whenCondition13: tankController_makeProduct_T4_enableFire,
        v_PRE_tankController_makeProduct_emptyTank2_newActive: tankController_makeProduct_emptyTank2_localActive,
        v_PRE_tankController_makeProduct_emptyTank2_localActive: v_PRE_tankController_makeProduct_emptyTank2_newActive,
        v_PRE_tankController_makeProduct_emptyTank2_oldActive: v_PRE_tankController_makeProduct_emptyTank2_localActive,
        tankController_makeProduct_emptyTank2_oldActive: v_PRE_tankController_makeProduct_emptyTank2_oldActive,
        tankController_makeProduct_fillTank2_active: vf.add_const(0.0),
        v_whenCondition15: tankController_makeProduct_T2_enableFire,
        v_PRE_tankController_makeProduct_fillTank2_newActive: tankController_makeProduct_fillTank2_localActive,
        v_PRE_tankController_makeProduct_fillTank2_localActive: v_PRE_tankController_makeProduct_fillTank2_newActive,
        v_PRE_tankController_makeProduct_fillTank2_oldActive: v_PRE_tankController_makeProduct_fillTank2_localActive,
        tankController_makeProduct_fillTank2_oldActive: v_PRE_tankController_makeProduct_fillTank2_oldActive,
        tankController_makeProduct_fillTank1_active: vf.add_const(0.0),
        tankController_makeProduct_fillTank1_localActive: tankController_makeProduct_fillTank1_active,
        v_PRE_tankController_makeProduct_fillTank1_newActive: tankController_makeProduct_fillTank1_localActive,
        v_PRE_tankController_makeProduct_fillTank1_localActive: v_PRE_tankController_makeProduct_fillTank1_newActive,
        v_PRE_tankController_makeProduct_fillTank1_oldActive: v_PRE_tankController_makeProduct_fillTank1_localActive,
        tankController_makeProduct_fillTank1_oldActive: v_PRE_tankController_makeProduct_fillTank1_oldActive,
        tankController_makeProduct_activeSteps: (-tankController_makeProduct_stateGraphRoot_subgraphStatePort_activeSteps),
        tankController_s1_active: vf.add_const(1.0),
        v_PRE_tankController_s1_newActive: tankController_s1_localActive,
        v_PRE_tankController_s1_localActive: v_PRE_tankController_s1_newActive,
        v_PRE_tankController_s1_oldActive: v_PRE_tankController_s1_localActive,
        tankController_s1_oldActive: v_PRE_tankController_s1_oldActive,
        stateGraphRoot_activeSteps: (-stateGraphRoot_subgraphStatePort_activeSteps),
        v_PRE_shut_table_combiTimeTable_nextTimeEvent: vf.add_const(0.0),
        v_PRE_stop_table_combiTimeTable_nextTimeEvent: vf.add_const(0.0),
        v_PRE_start_table_combiTimeTable_nextTimeEvent: vf.add_const(0.0),
        v_PRE_shut_pre_reset_2: vf.add_const(0.0),
        v_PRE_shut_pre_reset_1: vf.add_const(0.0),
        v_PRE_stop_pre_reset_2: vf.add_const(0.0),
        v_PRE_stop_pre_reset_1: vf.add_const(0.0),
        v_PRE_start_pre_reset_2: vf.add_const(0.0),
        v_PRE_start_pre_reset_1: vf.add_const(0.0),
        v_PRE_tankController_T6_enableFire: vf.add_const(0.0),
        v_PRE_tankController_T5_enableFire: vf.add_const(0.0),
        v_PRE_tankController_T4_enableFire: vf.add_const(0.0),
        v_PRE_tankController_T3_enableFire: vf.add_const(0.0),
        v_PRE_tankController_T2_enableFire: vf.add_const(0.0),
        v_PRE_tankController_T1_enableFire: vf.add_const(0.0),
        v_PRE_tankController_makeProduct_T4_enableFire: vf.add_const(0.0),
        v_PRE_tankController_makeProduct_T2_enableFire: vf.add_const(0.0),
        v_PRE_tankController_makeProduct_T3_enableFire: vf.add_const(0.0),
        v_PRE_tankController_makeProduct_T1_enableFire: vf.add_const(0.0),
        shut_table_realToBoolean_threshold: vf.add_const(0.5),
        source_maxflow: vf.add_const(1.0),
        start_table_realToBoolean_threshold: vf.add_const(0.5),
        stop_table_realToBoolean_threshold: vf.add_const(0.5),
        tank1_A: vf.add_const(1.0),
        tank1_a: vf.add_const(0.2),
        tank1_hmax: vf.add_const(1.0),
        tank2_A: vf.add_const(1.0),
        tank2_a: vf.add_const(0.2),
        tank2_hmax: vf.add_const(1.0),
        v_cse1: vf.add_const(0.0),
        v_cse2: vf.add_const(0.0),
        v_cse3: vf.add_const(0.0),
        v_whenCondition10: vf.add_const(0.0),
        v_whenCondition11: vf.add_const(0.0),
        v_whenCondition12: vf.add_const(0.0),
        shut_table_combiTimeTable_p_offset_1: vf.add_const(0.0),
        shut_table_combiTimeTable_tableID: vf.add_const(0.0),
        start_table_combiTimeTable_p_offset_1: vf.add_const(0.0),
        start_table_combiTimeTable_tableID: vf.add_const(0.0),
        stateGraphRoot_subgraphStatePort_activeSteps: vf.add_const(0.0),
        stop_table_combiTimeTable_p_offset_1: vf.add_const(0.0),
        stop_table_combiTimeTable_tableID: vf.add_const(0.0),
        tankController_T1_enableFire: vf.add_const(0.0),
        tankController_T2_enableFire: vf.add_const(0.0),
        tankController_T3_enableFire: vf.add_const(0.0),
        tankController_T4_enableFire: vf.add_const(0.0),
        tankController_T5_enableFire: vf.add_const(0.0),
        tankController_T6_enableFire: vf.add_const(0.0),
        tankController_emptyTanks_localActive: vf.add_const(0.0),
        tankController_emptyTanks_newActive: vf.add_const(0.0),
        tankController_emptyTanks_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        tankController_makeProduct_T1_enableFire: vf.add_const(0.0),
        tankController_makeProduct_T2_enableFire: vf.add_const(0.0),
        tankController_makeProduct_T2_fire: vf.add_const(0.0),
        tankController_makeProduct_T2_t: vf.add_const(0.0),
        tankController_makeProduct_T2_t_dummy: vf.add_const(0.0),
        tankController_makeProduct_T2_waitTime: vf.add_const(0.0),
        tankController_makeProduct_T3_enableFire: vf.add_const(0.0),
        tankController_makeProduct_T4_enableFire: vf.add_const(0.0),
        tankController_makeProduct_T4_fire: vf.add_const(0.0),
        tankController_makeProduct_T4_t: vf.add_const(0.0),
        tankController_makeProduct_T4_t_dummy: vf.add_const(0.0),
        tankController_makeProduct_T4_waitTime: vf.add_const(0.0),
        tankController_makeProduct_emptyTank2_localActive: vf.add_const(0.0),
        tankController_makeProduct_emptyTank2_newActive: vf.add_const(0.0),
        tankController_makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        tankController_makeProduct_fillTank1_newActive: vf.add_const(0.0),
        tankController_makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        tankController_makeProduct_fillTank2_localActive: vf.add_const(0.0),
        tankController_makeProduct_fillTank2_newActive: vf.add_const(0.0),
        tankController_makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        tankController_makeProduct_limit: vf.add_const(0.0),
        tankController_makeProduct_newActive: vf.add_const(0.0),
        tankController_makeProduct_outerState_subgraphStatePort_activeSteps: vf.add_const(0.0),
        tankController_makeProduct_stateGraphRoot_subgraphStatePort_activeSteps: vf.add_const(0.0),
        tankController_makeProduct_wait1_localActive: vf.add_const(0.0),
        tankController_makeProduct_wait1_newActive: vf.add_const(0.0),
        tankController_makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        tankController_makeProduct_wait2_localActive: vf.add_const(0.0),
        tankController_makeProduct_wait2_newActive: vf.add_const(0.0),
        tankController_makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        tankController_s1_inPort_2: vf.add_const(0.0),
        tankController_s1_localActive: vf.add_const(0.0),
        tankController_s1_newActive: vf.add_const(0.0),
        tankController_s1_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        tankController_s2_localActive: vf.add_const(0.0),
        tankController_s2_newActive: vf.add_const(0.0),
        tankController_s2_outPort_2: vf.add_const(0.0),
        tankController_s2_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        time: vf.add_const(0.0),
        valve1_outflow1_Fo: vf.add_const(0.0),
        valve2_outflow1_Fo: vf.add_const(0.0),
        valve2_valveControl: vf.add_const(0.0),
        valve3_outflow1_Fo: vf.add_const(0.0),
        valve3_valveControl: vf.add_const(0.0),
    }

    return templ
