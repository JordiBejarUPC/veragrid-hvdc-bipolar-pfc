# --- AUTO-GENERATED EMT TEMPLATE ---
# Source: Modelica Flat XML Transpilation

import numpy as np
from abc import ABC, abstractmethod
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType

class ITankControllerExternalFunctions(ABC):
    """
    Abstract interface for external functions detected in the Modelica XML.
    The user MUST implement these methods or register them in the symbolic engine.
    """
    @abstractmethod
    def pre(self, *args):
        pass


def apply_boundary_logic_modelica_stategraph_examples_utilities_tankcontroller(state):
    """Procedural logic for switching and discrete events."""
    state.s1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.s1_active else 0.0)
    state.makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.valve1 else 0.0)
    state.T1_enableFire = ((state.start and state.s1_active) and (not state.valve1))
    state.makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.makeProduct_fillTank2_active else 0.0)
    state.makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.makeProduct_emptyTank2_active else 0.0)
    state.makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.makeProduct_wait1_active else 0.0)
    state.v_whenCondition3 = (state.makeProduct_wait1_active and (not state.makeProduct_fillTank2_active))
    state.makeProduct_T2_t = (state.makeProduct_T2_t_dummy if state.v_whenCondition3 else 0.0)
    state.makeProduct_T2_fire = (state.time >= (state.makeProduct_T2_t_start + state.makeProduct_T2_waitTime))
    state.makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.makeProduct_wait2_active else 0.0)
    state.v_whenCondition1 = (state.makeProduct_wait2_active and (not state.makeProduct_emptyTank2_active))
    state.makeProduct_T4_t = (state.makeProduct_T4_t_dummy if state.v_whenCondition1 else 0.0)
    state.makeProduct_T4_fire = (state.time >= (state.makeProduct_T4_t_start + state.makeProduct_T4_waitTime))
    state.makeProduct_outerState_subgraphStatePort_activeSteps = (1.0 if state.makeProduct_active else 0.0)
    state.s2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.s2_active else 0.0)
    state.v_whenCondition2 = ((state.stop and state.makeProduct_active) and (not state.s2_active))
    state.emptyTanks_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.emptyTanks_active else 0.0)
    state.T5_enableFire = ((state.shut and state.s2_active) and (not state.emptyTanks_active))
    state.s2_outPort_2 = (state.s2_active and (not state.T5_enableFire))
    state.T4_enableFire = ((state.start and state.s2_outPort_2) and (not state.makeProduct_active))
    state.makeProduct_newActive = (state.makeProduct_activeSteps > 0.0)
    state.s2_newActive = (state.v_whenCondition2 or (state.s2_active and (not (state.T5_enableFire or state.T4_enableFire))))
    state.valve3 = (state.makeProduct_emptyTank2_active or state.emptyTanks_active)
    state.valve2 = (state.makeProduct_fillTank2_active or state.emptyTanks_active)
    state.makeProduct_T1_localCondition = (state.level1 > state.makeProduct_limit)
    state.makeProduct_T1_enableFire = ((state.makeProduct_T1_localCondition and state.valve1) and (not state.makeProduct_wait1_active))
    state.makeProduct_wait1_newActive = (state.makeProduct_wait1_oldActive if state.T4_enableFire else ((state.makeProduct_T1_enableFire or (state.makeProduct_wait1_active and (not state.makeProduct_T2_fire))) and (not state.v_whenCondition2)))
    state.makeProduct_fillTank1_newActive = (state.makeProduct_fillTank1_oldActive if state.T4_enableFire else ((state.T1_enableFire or (state.valve1 and (not state.makeProduct_T1_enableFire))) and (not state.v_whenCondition2)))
    state.makeProduct_T3_localCondition = (state.level1 < 0.001)
    state.makeProduct_T3_enableFire = ((state.makeProduct_T3_localCondition and state.makeProduct_fillTank2_active) and (not state.makeProduct_wait2_active))
    state.makeProduct_wait2_newActive = (state.makeProduct_wait2_oldActive if state.T4_enableFire else ((state.makeProduct_T3_enableFire or (state.makeProduct_wait2_active and (not state.makeProduct_T4_fire))) and (not state.v_whenCondition2)))
    state.makeProduct_fillTank2_newActive = (state.makeProduct_fillTank2_oldActive if state.T4_enableFire else ((state.makeProduct_T2_fire or (state.makeProduct_fillTank2_active and (not state.makeProduct_T3_enableFire))) and (not state.v_whenCondition2)))
    state.T2_localCondition = (state.level2 < 0.001)
    state.T2_enableFire = ((state.T2_localCondition and state.makeProduct_emptyTank2_active) and (not state.s1_active))
    state.s1_inPort_2 = (state.s1_active or state.T2_enableFire)
    state.makeProduct_emptyTank2_newActive = (state.makeProduct_emptyTank2_oldActive if state.T4_enableFire else ((state.makeProduct_T4_fire or (state.makeProduct_emptyTank2_active and (not state.T2_enableFire))) and (not state.v_whenCondition2)))
    state.T6_localCondition = ((state.level1 + state.level2) < 0.001)
    state.T6_enableFire = ((state.T6_localCondition and state.emptyTanks_active) and (not state.s1_inPort_2))
    state.s1_newActive = ((state.T2_enableFire or state.T6_enableFire) or (state.s1_active and (not state.T1_enableFire)))
    state.emptyTanks_newActive = (state.T5_enableFire or (state.emptyTanks_active and (not state.T6_enableFire)))

    # --- Discrete Event Handlers (When Blocks) ---
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.s1_oldActive = state.s1_active
    if ext_funcs.event_triggered(state.v_whenCondition3):
        state.makeProduct_T2_t_start = state.time
    if ext_funcs.event_triggered(state.v_whenCondition1):
        state.makeProduct_T4_t_start = state.time
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.s2_oldActive = state.s2_active
    if ext_funcs.event_triggered(state.v_whenCondition2):
        state.makeProduct_wait2_oldActive = state.makeProduct_wait2_active
        state.makeProduct_wait1_oldActive = state.makeProduct_wait1_active
        state.makeProduct_emptyTank2_oldActive = state.makeProduct_emptyTank2_active
        state.makeProduct_fillTank2_oldActive = state.makeProduct_fillTank2_active
        state.makeProduct_fillTank1_oldActive = state.valve1
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.emptyTanks_oldActive = state.emptyTanks_active
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.makeProduct_T1_t_start = ext_funcs.pre(state.makeProduct_T1_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.makeProduct_T3_t_start = ext_funcs.pre(state.makeProduct_T3_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.T1_t_start = ext_funcs.pre(state.T1_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.T2_t_start = ext_funcs.pre(state.T2_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.T3_t_start = ext_funcs.pre(state.T3_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.T4_t_start = ext_funcs.pre(state.T4_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.T5_t_start = ext_funcs.pre(state.T5_t_start)
    if ext_funcs.event_triggered(state.INITIALIZATION_EVENT):
        state.T6_t_start = ext_funcs.pre(state.T6_t_start)

    # --- Procedural Initialization Logic ---
    # Evaluates logic blocks during the first step (t=0) to feed the symbolic solver
    if state.time == 0.0:
        state.emptyTanks_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.emptyTanks_localActive else 0.0)
        state.T5_enableFire = ((state.shut and state.s2_localActive) and (not state.emptyTanks_localActive))
        state.s2_outPort_2 = (state.s2_localActive and (not state.T5_enableFire))
        state.s2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.s2_localActive else 0.0)
        state.T3_enableFire = ((state.stop and state.makeProduct_active) and (not state.s2_localActive))
        state.s2_newActive = (state.T3_enableFire or (state.s2_localActive and (not (state.T5_enableFire or state.T4_enableFire))))
        state.makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.makeProduct_wait2_localActive else 0.0)
        state.makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.makeProduct_wait1_localActive else 0.0)
        state.makeProduct_T4_enableFire = (state.makeProduct_wait2_localActive and (not state.makeProduct_emptyTank2_localActive))
        state.makeProduct_T4_fire = (state.time >= (state.makeProduct_T4_t_start + state.makeProduct_T4_waitTime))
        state.makeProduct_T4_t = (state.makeProduct_T4_t_dummy if state.makeProduct_T4_enableFire else 0.0)
        state.makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.makeProduct_emptyTank2_localActive else 0.0)
        state.makeProduct_T2_enableFire = (state.makeProduct_wait1_localActive and (not state.makeProduct_fillTank2_localActive))
        state.makeProduct_T2_fire = (state.time >= (state.makeProduct_T2_t_start + state.makeProduct_T2_waitTime))
        state.makeProduct_T2_t = (state.makeProduct_T2_t_dummy if state.makeProduct_T2_enableFire else 0.0)
        state.makeProduct_T3_enableFire = ((state.makeProduct_T3_localCondition and state.makeProduct_fillTank2_localActive) and (not state.makeProduct_wait2_localActive))
        state.makeProduct_wait2_newActive = (state.makeProduct_wait2_oldActive if state.T4_enableFire else ((state.makeProduct_T3_enableFire or (state.makeProduct_wait2_localActive and (not state.makeProduct_T4_fire))) and (not state.T3_enableFire)))
        state.makeProduct_fillTank2_newActive = (state.makeProduct_fillTank2_oldActive if state.T4_enableFire else ((state.makeProduct_T2_fire or (state.makeProduct_fillTank2_localActive and (not state.makeProduct_T3_enableFire))) and (not state.T3_enableFire)))
        state.makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.makeProduct_fillTank2_localActive else 0.0)
        state.makeProduct_T1_enableFire = ((state.makeProduct_T1_localCondition and state.valve1) and (not state.makeProduct_wait1_localActive))
        state.makeProduct_wait1_newActive = (state.makeProduct_wait1_oldActive if state.T4_enableFire else ((state.makeProduct_T1_enableFire or (state.makeProduct_wait1_localActive and (not state.makeProduct_T2_fire))) and (not state.T3_enableFire)))
        state.makeProduct_newActive = (state.makeProduct_activeSteps > 0.0)
        state.T2_enableFire = ((state.T2_localCondition and state.makeProduct_emptyTank2_localActive) and (not state.s1_localActive))
        state.makeProduct_emptyTank2_newActive = (state.makeProduct_emptyTank2_oldActive if state.T4_enableFire else ((state.makeProduct_T4_fire or (state.makeProduct_emptyTank2_localActive and (not state.T2_enableFire))) and (not state.T3_enableFire)))
        state.T1_enableFire = ((state.start and state.s1_localActive) and (not state.valve1))
        state.makeProduct_fillTank1_newActive = (state.makeProduct_fillTank1_oldActive if state.T4_enableFire else ((state.T1_enableFire or (state.makeProduct_fillTank1_localActive and (not state.makeProduct_T1_enableFire))) and (not state.T3_enableFire)))
        state.s1_inPort_2 = (state.s1_localActive or state.T2_enableFire)
        state.T6_enableFire = ((state.T6_localCondition and state.emptyTanks_localActive) and (not state.s1_inPort_2))
        state.emptyTanks_newActive = (state.T5_enableFire or (state.emptyTanks_localActive and (not state.T6_enableFire)))
        state.s1_newActive = ((state.T2_enableFire or state.T6_enableFire) or (state.s1_localActive and (not state.T1_enableFire)))
        state.s1_outerStatePort_subgraphStatePort_activeSteps = (1.0 if state.s1_localActive else 0.0)


def get_modelica_stategraph_examples_utilities_tankcontroller_emt_template(vf: VarFactory, name: str='Modelica.StateGraph.Examples.Utilities.TankController') -> EmtModelTemplate:
    """Initializes the continuous DAE block and factory variables."""
    templ = EmtModelTemplate()
    templ.tpe = DeviceType.GeneratorDevice  # TODO: Verify correct DeviceType
    templ.name = name

    # --- Parameters ---

    # --- State Variables ---

    # --- Algebraic Variables ---
    v_whenCondition1 = vf.add_var('$whenCondition1_' + name)
    v_whenCondition2 = vf.add_var('$whenCondition2_' + name)
    v_whenCondition3 = vf.add_var('$whenCondition3_' + name)
    T1_enableFire = vf.add_var('T1.enableFire_' + name)
    T2_enableFire = vf.add_var('T2.enableFire_' + name)
    T2_localCondition = vf.add_var('T2.localCondition_' + name)
    T3_enableFire = vf.add_var('T3.enableFire_' + name)
    T4_enableFire = vf.add_var('T4.enableFire_' + name)
    T5_enableFire = vf.add_var('T5.enableFire_' + name)
    T6_enableFire = vf.add_var('T6.enableFire_' + name)
    T6_localCondition = vf.add_var('T6.localCondition_' + name)
    emptyTanks_active = vf.add_var('emptyTanks.active_' + name)
    emptyTanks_localActive = vf.add_var('emptyTanks.localActive_' + name)
    emptyTanks_newActive = vf.add_var('emptyTanks.newActive_' + name)
    emptyTanks_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('emptyTanks.outerStatePort.subgraphStatePort.activeSteps_' + name)
    level1 = vf.add_var('level1_' + name)
    level2 = vf.add_var('level2_' + name)
    makeProduct_T1_enableFire = vf.add_var('makeProduct.T1.enableFire_' + name)
    makeProduct_T1_localCondition = vf.add_var('makeProduct.T1.localCondition_' + name)
    makeProduct_T2_enableFire = vf.add_var('makeProduct.T2.enableFire_' + name)
    makeProduct_T2_fire = vf.add_var('makeProduct.T2.fire_' + name)
    makeProduct_T2_t = vf.add_var('makeProduct.T2.t_' + name)
    makeProduct_T2_t_dummy = vf.add_var('makeProduct.T2.t_dummy_' + name)
    makeProduct_T2_t_start = vf.add_var('makeProduct.T2.t_start_' + name)
    makeProduct_T2_waitTime = vf.add_var('makeProduct.T2.waitTime_' + name)
    makeProduct_T3_enableFire = vf.add_var('makeProduct.T3.enableFire_' + name)
    makeProduct_T3_localCondition = vf.add_var('makeProduct.T3.localCondition_' + name)
    makeProduct_T4_enableFire = vf.add_var('makeProduct.T4.enableFire_' + name)
    makeProduct_T4_fire = vf.add_var('makeProduct.T4.fire_' + name)
    makeProduct_T4_t = vf.add_var('makeProduct.T4.t_' + name)
    makeProduct_T4_t_dummy = vf.add_var('makeProduct.T4.t_dummy_' + name)
    makeProduct_T4_t_start = vf.add_var('makeProduct.T4.t_start_' + name)
    makeProduct_T4_waitTime = vf.add_var('makeProduct.T4.waitTime_' + name)
    makeProduct_active = vf.add_var('makeProduct.active_' + name)
    makeProduct_activeSteps = vf.add_var('makeProduct.activeSteps_' + name)
    makeProduct_emptyTank2_active = vf.add_var('makeProduct.emptyTank2.active_' + name)
    makeProduct_emptyTank2_localActive = vf.add_var('makeProduct.emptyTank2.localActive_' + name)
    makeProduct_emptyTank2_newActive = vf.add_var('makeProduct.emptyTank2.newActive_' + name)
    makeProduct_emptyTank2_oldActive = vf.add_var('makeProduct.emptyTank2.oldActive_' + name)
    makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('makeProduct.emptyTank2.outerStatePort.subgraphStatePort.activeSteps_' + name)
    makeProduct_fillTank1_active = vf.add_var('makeProduct.fillTank1.active_' + name)
    makeProduct_fillTank1_localActive = vf.add_var('makeProduct.fillTank1.localActive_' + name)
    makeProduct_fillTank1_newActive = vf.add_var('makeProduct.fillTank1.newActive_' + name)
    makeProduct_fillTank1_oldActive = vf.add_var('makeProduct.fillTank1.oldActive_' + name)
    makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('makeProduct.fillTank1.outerStatePort.subgraphStatePort.activeSteps_' + name)
    makeProduct_fillTank2_active = vf.add_var('makeProduct.fillTank2.active_' + name)
    makeProduct_fillTank2_localActive = vf.add_var('makeProduct.fillTank2.localActive_' + name)
    makeProduct_fillTank2_newActive = vf.add_var('makeProduct.fillTank2.newActive_' + name)
    makeProduct_fillTank2_oldActive = vf.add_var('makeProduct.fillTank2.oldActive_' + name)
    makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('makeProduct.fillTank2.outerStatePort.subgraphStatePort.activeSteps_' + name)
    makeProduct_limit = vf.add_var('makeProduct.limit_' + name)
    makeProduct_newActive = vf.add_var('makeProduct.newActive_' + name)
    makeProduct_outerState_subgraphStatePort_activeSteps = vf.add_var('makeProduct.outerState.subgraphStatePort.activeSteps_' + name)
    makeProduct_stateGraphRoot_subgraphStatePort_activeSteps = vf.add_var('makeProduct.stateGraphRoot.subgraphStatePort.activeSteps_' + name)
    makeProduct_wait1_active = vf.add_var('makeProduct.wait1.active_' + name)
    makeProduct_wait1_localActive = vf.add_var('makeProduct.wait1.localActive_' + name)
    makeProduct_wait1_newActive = vf.add_var('makeProduct.wait1.newActive_' + name)
    makeProduct_wait1_oldActive = vf.add_var('makeProduct.wait1.oldActive_' + name)
    makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('makeProduct.wait1.outerStatePort.subgraphStatePort.activeSteps_' + name)
    makeProduct_wait2_active = vf.add_var('makeProduct.wait2.active_' + name)
    makeProduct_wait2_localActive = vf.add_var('makeProduct.wait2.localActive_' + name)
    makeProduct_wait2_newActive = vf.add_var('makeProduct.wait2.newActive_' + name)
    makeProduct_wait2_oldActive = vf.add_var('makeProduct.wait2.oldActive_' + name)
    makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('makeProduct.wait2.outerStatePort.subgraphStatePort.activeSteps_' + name)
    s1_active = vf.add_var('s1.active_' + name)
    s1_inPort_2 = vf.add_var('s1.inPort[2]_' + name)
    s1_localActive = vf.add_var('s1.localActive_' + name)
    s1_newActive = vf.add_var('s1.newActive_' + name)
    s1_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('s1.outerStatePort.subgraphStatePort.activeSteps_' + name)
    s2_active = vf.add_var('s2.active_' + name)
    s2_localActive = vf.add_var('s2.localActive_' + name)
    s2_newActive = vf.add_var('s2.newActive_' + name)
    s2_outPort_2 = vf.add_var('s2.outPort[2]_' + name)
    s2_outerStatePort_subgraphStatePort_activeSteps = vf.add_var('s2.outerStatePort.subgraphStatePort.activeSteps_' + name)
    shut = vf.add_var('shut_' + name)
    start = vf.add_var('start_' + name)
    stateGraphRoot_subgraphStatePort_activeSteps = vf.add_var('stateGraphRoot.subgraphStatePort.activeSteps_' + name)
    stop = vf.add_var('stop_' + name)
    time = vf.add_var('time_' + name)
    valve1 = vf.add_var('valve1_' + name)
    valve2 = vf.add_var('valve2_' + name)
    valve3 = vf.add_var('valve3_' + name)

    # --- Derivative Variables ---

    # --- Continuous Block Assembly ---
    templ.block = Block(
        state_eqs=[
        ],
        state_vars=[],

        algebraic_eqs=[
            (s1_active - sym.pre(s1_newActive)),
            (s1_localActive - s1_active),
            (valve1 - sym.pre(makeProduct_fillTank1_newActive)),
            (makeProduct_fillTank1_localActive - valve1),
            (makeProduct_fillTank1_active - valve1),
            (makeProduct_fillTank2_active - sym.pre(makeProduct_fillTank2_newActive)),
            (makeProduct_fillTank2_localActive - makeProduct_fillTank2_active),
            (makeProduct_emptyTank2_active - sym.pre(makeProduct_emptyTank2_newActive)),
            (makeProduct_emptyTank2_localActive - makeProduct_emptyTank2_active),
            (makeProduct_wait1_active - sym.pre(makeProduct_wait1_newActive)),
            (makeProduct_T2_t_dummy - (time - makeProduct_T2_t_start)),
            (makeProduct_T2_enableFire - v_whenCondition3),
            (makeProduct_wait1_localActive - makeProduct_wait1_active),
            (makeProduct_wait2_active - sym.pre(makeProduct_wait2_newActive)),
            (makeProduct_stateGraphRoot_subgraphStatePort_activeSteps - (((((-makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps) - makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps) - makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps) - makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps) - makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps)),
            (makeProduct_activeSteps - (-0.0)),
            (makeProduct_T4_t_dummy - (time - makeProduct_T4_t_start)),
            (makeProduct_T4_enableFire - v_whenCondition1),
            (makeProduct_wait2_localActive - makeProduct_wait2_active),
            (makeProduct_active - sym.pre(makeProduct_newActive)),
            (s2_active - sym.pre(s2_newActive)),
            (T3_enableFire - v_whenCondition2),
            (s2_localActive - s2_active),
            (emptyTanks_active - sym.pre(emptyTanks_newActive)),
            (stateGraphRoot_subgraphStatePort_activeSteps - ((((-emptyTanks_outerStatePort_subgraphStatePort_activeSteps) - s2_outerStatePort_subgraphStatePort_activeSteps) - makeProduct_outerState_subgraphStatePort_activeSteps) - s1_outerStatePort_subgraphStatePort_activeSteps)),
            (emptyTanks_localActive - emptyTanks_active),
        ],
        algebraic_vars=[v_whenCondition1, v_whenCondition2, v_whenCondition3, T1_enableFire, T2_enableFire, T2_localCondition, T3_enableFire, T4_enableFire, T5_enableFire, T6_enableFire, T6_localCondition, emptyTanks_active, emptyTanks_localActive, emptyTanks_newActive, emptyTanks_outerStatePort_subgraphStatePort_activeSteps, level1, level2, makeProduct_T1_enableFire, makeProduct_T1_localCondition, makeProduct_T2_enableFire, makeProduct_T2_fire, makeProduct_T2_t, makeProduct_T2_t_dummy, makeProduct_T2_t_start, makeProduct_T2_waitTime, makeProduct_T3_enableFire, makeProduct_T3_localCondition, makeProduct_T4_enableFire, makeProduct_T4_fire, makeProduct_T4_t, makeProduct_T4_t_dummy, makeProduct_T4_t_start, makeProduct_T4_waitTime, makeProduct_active, makeProduct_activeSteps, makeProduct_emptyTank2_active, makeProduct_emptyTank2_localActive, makeProduct_emptyTank2_newActive, makeProduct_emptyTank2_oldActive, makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps, makeProduct_fillTank1_active, makeProduct_fillTank1_localActive, makeProduct_fillTank1_newActive, makeProduct_fillTank1_oldActive, makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps, makeProduct_fillTank2_active, makeProduct_fillTank2_localActive, makeProduct_fillTank2_newActive, makeProduct_fillTank2_oldActive, makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps, makeProduct_limit, makeProduct_newActive, makeProduct_outerState_subgraphStatePort_activeSteps, makeProduct_stateGraphRoot_subgraphStatePort_activeSteps, makeProduct_wait1_active, makeProduct_wait1_localActive, makeProduct_wait1_newActive, makeProduct_wait1_oldActive, makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps, makeProduct_wait2_active, makeProduct_wait2_localActive, makeProduct_wait2_newActive, makeProduct_wait2_oldActive, makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps, s1_active, s1_inPort_2, s1_localActive, s1_newActive, s1_outerStatePort_subgraphStatePort_activeSteps, s2_active, s2_localActive, s2_newActive, s2_outPort_2, s2_outerStatePort_subgraphStatePort_activeSteps, shut, start, stateGraphRoot_subgraphStatePort_activeSteps, stop, time, valve1, valve2, valve3],
    )

    # --- Parameter Values ---
    templ.block.event_dict = {
    }

    # --- Initial Equations and Guesses ---
    templ.block.init_eqs = {
        makeProduct_stateGraphRoot_subgraphStatePort_activeStepsDummy: vf.add_const(0.0),
        makeProduct_T1_t_dummy: vf.add_const(0.0),
        makeProduct_T1_t: vf.add_const(0.0),
        makeProduct_T3_t_dummy: vf.add_const(0.0),
        makeProduct_T3_t: vf.add_const(0.0),
        T1_t_dummy: vf.add_const(0.0),
        T1_t: vf.add_const(0.0),
        T2_t_dummy: vf.add_const(0.0),
        T2_t: vf.add_const(0.0),
        T3_t_dummy: vf.add_const(0.0),
        T3_t: vf.add_const(0.0),
        T4_t_dummy: vf.add_const(0.0),
        T4_t: vf.add_const(0.0),
        T5_t_dummy: vf.add_const(0.0),
        T5_t: vf.add_const(0.0),
        T6_t_dummy: vf.add_const(0.0),
        T6_t: vf.add_const(0.0),
        stateGraphRoot_subgraphStatePort_activeStepsDummy: vf.add_const(0.0),
        makeProduct_T2_condition: vf.add_const(1.0),
        makeProduct_T4_condition: vf.add_const(1.0),
        stateGraphRoot_suspend: vf.add_const(0.0),
        stateGraphRoot_resume: vf.add_const(0.0),
        v_PRE_T6_t_start: time,
        T6_t_start: v_PRE_T6_t_start,
        v_PRE_T5_t_start: time,
        T5_t_start: v_PRE_T5_t_start,
        v_PRE_T4_t_start: time,
        T4_t_start: v_PRE_T4_t_start,
        v_PRE_T3_t_start: time,
        T3_t_start: v_PRE_T3_t_start,
        v_PRE_T2_t_start: time,
        T2_t_start: v_PRE_T2_t_start,
        v_PRE_T1_t_start: time,
        T1_t_start: v_PRE_T1_t_start,
        v_PRE_makeProduct_T3_t_start: time,
        makeProduct_T3_t_start: v_PRE_makeProduct_T3_t_start,
        v_PRE_makeProduct_T1_t_start: time,
        makeProduct_T1_t_start: v_PRE_makeProduct_T1_t_start,
        emptyTanks_active: vf.add_const(0.0),
        v_PRE_emptyTanks_newActive: emptyTanks_localActive,
        v_PRE_emptyTanks_localActive: v_PRE_emptyTanks_newActive,
        v_PRE_emptyTanks_oldActive: v_PRE_emptyTanks_localActive,
        emptyTanks_oldActive: v_PRE_emptyTanks_oldActive,
        s2_active: vf.add_const(0.0),
        v_PRE_s2_newActive: s2_localActive,
        v_PRE_s2_localActive: v_PRE_s2_newActive,
        v_PRE_s2_oldActive: v_PRE_s2_localActive,
        s2_oldActive: v_PRE_s2_oldActive,
        v_PRE_makeProduct_newActive: vf.add_const(0.0),
        makeProduct_active: v_PRE_makeProduct_newActive,
        v_whenCondition2: T3_enableFire,
        v_PRE_makeProduct_T4_t_start: time,
        makeProduct_T4_t_start: v_PRE_makeProduct_T4_t_start,
        makeProduct_wait2_active: vf.add_const(0.0),
        v_PRE_makeProduct_wait2_newActive: makeProduct_wait2_localActive,
        v_PRE_makeProduct_wait2_localActive: v_PRE_makeProduct_wait2_newActive,
        v_PRE_makeProduct_wait2_oldActive: v_PRE_makeProduct_wait2_localActive,
        makeProduct_wait2_oldActive: v_PRE_makeProduct_wait2_oldActive,
        v_PRE_makeProduct_T2_t_start: time,
        makeProduct_T2_t_start: v_PRE_makeProduct_T2_t_start,
        makeProduct_wait1_active: vf.add_const(0.0),
        v_PRE_makeProduct_wait1_newActive: makeProduct_wait1_localActive,
        v_PRE_makeProduct_wait1_localActive: v_PRE_makeProduct_wait1_newActive,
        v_PRE_makeProduct_wait1_oldActive: v_PRE_makeProduct_wait1_localActive,
        makeProduct_wait1_oldActive: v_PRE_makeProduct_wait1_oldActive,
        makeProduct_emptyTank2_active: vf.add_const(0.0),
        v_whenCondition1: makeProduct_T4_enableFire,
        v_PRE_makeProduct_emptyTank2_newActive: makeProduct_emptyTank2_localActive,
        v_PRE_makeProduct_emptyTank2_localActive: v_PRE_makeProduct_emptyTank2_newActive,
        v_PRE_makeProduct_emptyTank2_oldActive: v_PRE_makeProduct_emptyTank2_localActive,
        makeProduct_emptyTank2_oldActive: v_PRE_makeProduct_emptyTank2_oldActive,
        makeProduct_fillTank2_active: vf.add_const(0.0),
        v_whenCondition3: makeProduct_T2_enableFire,
        v_PRE_makeProduct_fillTank2_newActive: makeProduct_fillTank2_localActive,
        v_PRE_makeProduct_fillTank2_localActive: v_PRE_makeProduct_fillTank2_newActive,
        v_PRE_makeProduct_fillTank2_oldActive: v_PRE_makeProduct_fillTank2_localActive,
        makeProduct_fillTank2_oldActive: v_PRE_makeProduct_fillTank2_oldActive,
        makeProduct_fillTank1_active: vf.add_const(0.0),
        valve1: makeProduct_fillTank1_active,
        v_PRE_makeProduct_fillTank1_newActive: makeProduct_fillTank1_localActive,
        v_PRE_makeProduct_fillTank1_localActive: v_PRE_makeProduct_fillTank1_newActive,
        v_PRE_makeProduct_fillTank1_oldActive: v_PRE_makeProduct_fillTank1_localActive,
        makeProduct_fillTank1_oldActive: v_PRE_makeProduct_fillTank1_oldActive,
        makeProduct_activeSteps: (-makeProduct_stateGraphRoot_subgraphStatePort_activeSteps),
        s1_active: vf.add_const(1.0),
        v_PRE_s1_newActive: s1_localActive,
        v_PRE_s1_localActive: v_PRE_s1_newActive,
        v_PRE_s1_oldActive: v_PRE_s1_localActive,
        s1_oldActive: v_PRE_s1_oldActive,
        v_PRE_T6_enableFire: vf.add_const(0.0),
        v_PRE_T5_enableFire: vf.add_const(0.0),
        v_PRE_T4_enableFire: vf.add_const(0.0),
        v_PRE_T3_enableFire: vf.add_const(0.0),
        v_PRE_T2_enableFire: vf.add_const(0.0),
        v_PRE_T1_enableFire: vf.add_const(0.0),
        v_PRE_makeProduct_T4_enableFire: vf.add_const(0.0),
        v_PRE_makeProduct_T2_enableFire: vf.add_const(0.0),
        v_PRE_makeProduct_T3_enableFire: vf.add_const(0.0),
        v_PRE_makeProduct_T1_enableFire: vf.add_const(0.0),
        T1_enableFire: vf.add_const(0.0),
        T2_enableFire: vf.add_const(0.0),
        T2_localCondition: vf.add_const(0.0),
        T3_enableFire: vf.add_const(0.0),
        T4_enableFire: vf.add_const(0.0),
        T5_enableFire: vf.add_const(0.0),
        T6_enableFire: vf.add_const(0.0),
        T6_localCondition: vf.add_const(0.0),
        emptyTanks_localActive: vf.add_const(0.0),
        emptyTanks_newActive: vf.add_const(0.0),
        emptyTanks_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        level1: vf.add_const(0.0),
        level2: vf.add_const(0.0),
        makeProduct_T1_enableFire: vf.add_const(0.0),
        makeProduct_T1_localCondition: vf.add_const(0.0),
        makeProduct_T2_enableFire: vf.add_const(0.0),
        makeProduct_T2_fire: vf.add_const(0.0),
        makeProduct_T2_t: vf.add_const(0.0),
        makeProduct_T2_t_dummy: vf.add_const(0.0),
        makeProduct_T2_waitTime: vf.add_const(0.0),
        makeProduct_T3_enableFire: vf.add_const(0.0),
        makeProduct_T3_localCondition: vf.add_const(0.0),
        makeProduct_T4_enableFire: vf.add_const(0.0),
        makeProduct_T4_fire: vf.add_const(0.0),
        makeProduct_T4_t: vf.add_const(0.0),
        makeProduct_T4_t_dummy: vf.add_const(0.0),
        makeProduct_T4_waitTime: vf.add_const(0.0),
        makeProduct_emptyTank2_localActive: vf.add_const(0.0),
        makeProduct_emptyTank2_newActive: vf.add_const(0.0),
        makeProduct_emptyTank2_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        makeProduct_fillTank1_localActive: vf.add_const(0.0),
        makeProduct_fillTank1_newActive: vf.add_const(0.0),
        makeProduct_fillTank1_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        makeProduct_fillTank2_localActive: vf.add_const(0.0),
        makeProduct_fillTank2_newActive: vf.add_const(0.0),
        makeProduct_fillTank2_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        makeProduct_limit: vf.add_const(0.0),
        makeProduct_newActive: vf.add_const(0.0),
        makeProduct_outerState_subgraphStatePort_activeSteps: vf.add_const(0.0),
        makeProduct_stateGraphRoot_subgraphStatePort_activeSteps: vf.add_const(0.0),
        makeProduct_wait1_localActive: vf.add_const(0.0),
        makeProduct_wait1_newActive: vf.add_const(0.0),
        makeProduct_wait1_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        makeProduct_wait2_localActive: vf.add_const(0.0),
        makeProduct_wait2_newActive: vf.add_const(0.0),
        makeProduct_wait2_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        s1_inPort_2: vf.add_const(0.0),
        s1_localActive: vf.add_const(0.0),
        s1_newActive: vf.add_const(0.0),
        s1_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        s2_localActive: vf.add_const(0.0),
        s2_newActive: vf.add_const(0.0),
        s2_outPort_2: vf.add_const(0.0),
        s2_outerStatePort_subgraphStatePort_activeSteps: vf.add_const(0.0),
        shut: vf.add_const(0.0),
        start: vf.add_const(0.0),
        stateGraphRoot_subgraphStatePort_activeSteps: vf.add_const(0.0),
        stop: vf.add_const(0.0),
        time: vf.add_const(0.0),
        valve2: vf.add_const(0.0),
        valve3: vf.add_const(0.0),
    }

    return templ
