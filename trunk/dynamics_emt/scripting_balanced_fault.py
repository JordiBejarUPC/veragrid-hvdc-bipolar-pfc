# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import sys
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_ROOT = os.path.join(REPO_ROOT, 'src')

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
else:
    pass

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
else:
    pass

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Events.emt_event import EmtEvent
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, PowerFlowOptions
from VeraGridEngine.Templates.Emt.fault_emt_template import get_fault_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.block import Block, build_name_to_var_lookup, find_name_in_block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
    BlockType,
    BranchImpedanceMode,
    DynamicIntegrationMethod,
    EmtFaultPlacementSide,
    EmtInitializationMethod,
    EmtSolverTypes,
    FaultType,
    ShuntConnectionType,
    SolverType,
    VarPowerFlowReferenceType,
)


def _find_required_var(name: str, block: Block) -> Any:
    """
    Find one named symbolic variable inside one block hierarchy.

    :param name: Variable name to search.
    :param block: Block to inspect.
    :return: Matching symbolic variable.
    :raises ValueError: If the variable is not found.
    """
    lookup: Dict[str, Any] = build_name_to_var_lookup(block)
    found_var: Any = lookup.get(name, None)

    if found_var is not None:
        return found_var
    else:
        fallback_var: Any = find_name_in_block(name, block)

        if fallback_var is not None:
            return fallback_var
        else:
            raise ValueError(f"Variable '{name}' not found in block '{block.name}'")


def _build_demo_grid() -> tuple[MultiCircuit, Bus, Bus, Line, Generator, Load]:
    """
    Build one simple source-line-load EMT study grid.

    :return: Tuple with the grid and its main devices.
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)

    vnom: float = 20.0
    bus_source: Bus = Bus(name="BusSource", Vnom=vnom, is_slack=True)
    bus_remote: Bus = Bus(name="BusRemote", Vnom=vnom)
    grid.add_bus(bus_source)
    grid.add_bus(bus_remote)

    line: Line = Line(name="Line_Source_Remote", bus_from=bus_source, bus_to=bus_remote, length=20.0, rate=200.0)
    tower: OverheadLineType = OverheadLineType(name="BalancedFaultTower", Vnom=vnom)
    wire: Wire = Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1.0,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line.apply_template(tower, grid.Sbase, grid.fBase)
    grid.add_line(line)

    source: Generator = Generator(name="GenSlack", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.35)
    grid.add_generator(bus=bus_source, api_obj=source)

    p_total_mw: float = 18.0
    p_phase_mw: float = p_total_mw / 3.0
    remote_load: Load = Load(
        name="RemoteLoad",
        P=3.0 * p_phase_mw,
        Q=0.0,
        P1=p_phase_mw,
        P2=p_phase_mw,
        P3=p_phase_mw,
        Q1=0.0,
        Q2=0.0,
        Q3=0.0,
    )
    remote_load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_remote, api_obj=remote_load)

    return grid, bus_source, bus_remote, line, source, remote_load


def _build_faulted_line_composite(grid: MultiCircuit) -> tuple[Block, Block, Block]:
    """
    Build one branch composite containing the internal fault block and line block.

    The composite keeps the standard branch external mapping while internally
    wiring one from-side fault block to one PI-line block through the explicit
    ``outer`` / ``inner`` fault ports.

    :param grid: Study grid.
    :return: Tuple ``(composite_block, fault_block, line_block)``.
    """
    fault_block: Block = get_fault_emt_template(
        vf=grid.var_factory,
        fault_type=FaultType.LLL,
        placement_side=EmtFaultPlacementSide.FromSide,
        phA=True,
        phB=True,
        phC=True,
        signal_controlled=False,
        initial_closed=False,
        fault_resistance=1.0e-4,
        ground_resistance=1.0e-4,
        open_conductance=1.0e-8,
        fault_time_constant=1.0e-6,
        command_threshold=0.5,
        name="internal_fault",
    ).block
    line_block: Block = get_pi_line_emt_template(vf=grid.var_factory, phN=False, phA=True, phB=True, phC=True, name="faulted_pi_line").block

    root_block: Block = Block(name="faulted_line_branch")
    root_block.add(fault_block)
    root_block.add(line_block)

    # The branch parent keeps the standard two-terminal public contract expected
    # by the EMT network assembly. The midpoint variables are owned by the parent,
    # exactly like one manual composition built in the block editor.
    vf_a: Any = _find_required_var("vf_A_faulted_pi_line", line_block)
    vf_b: Any = _find_required_var("vf_B_faulted_pi_line", line_block)
    vf_c: Any = _find_required_var("vf_C_faulted_pi_line", line_block)
    vt_a: Any = _find_required_var("vt_A_faulted_pi_line", line_block)
    vt_b: Any = _find_required_var("vt_B_faulted_pi_line", line_block)
    vt_c: Any = _find_required_var("vt_C_faulted_pi_line", line_block)
    if_a: Any = _find_required_var("if_faulted_pi_line_A", line_block)
    if_b: Any = _find_required_var("if_faulted_pi_line_B", line_block)
    if_c: Any = _find_required_var("if_faulted_pi_line_C", line_block)
    it_a: Any = _find_required_var("it_faulted_pi_line_A", line_block)
    it_b: Any = _find_required_var("it_faulted_pi_line_B", line_block)
    it_c: Any = _find_required_var("it_faulted_pi_line_C", line_block)

    v_outer_a: Any = _find_required_var("v_outer_A_internal_fault", fault_block)
    v_outer_b: Any = _find_required_var("v_outer_B_internal_fault", fault_block)
    v_outer_c: Any = _find_required_var("v_outer_C_internal_fault", fault_block)
    v_inner_a: Any = _find_required_var("v_inner_A_internal_fault", fault_block)
    v_inner_b: Any = _find_required_var("v_inner_B_internal_fault", fault_block)
    v_inner_c: Any = _find_required_var("v_inner_C_internal_fault", fault_block)
    i_inner_a: Any = _find_required_var("i_inner_A_internal_fault", fault_block)
    i_inner_b: Any = _find_required_var("i_inner_B_internal_fault", fault_block)
    i_inner_c: Any = _find_required_var("i_inner_C_internal_fault", fault_block)
    i_outer_a: Any = _find_required_var("i_outer_A_internal_fault", fault_block)
    i_outer_b: Any = _find_required_var("i_outer_B_internal_fault", fault_block)
    i_outer_c: Any = _find_required_var("i_outer_C_internal_fault", fault_block)

    parent_vf_a: Any = grid.var_factory.add_var("vf_A_faulted_line_branch", reference=VarPowerFlowReferenceType.vf_A)
    parent_vf_b: Any = grid.var_factory.add_var("vf_B_faulted_line_branch", reference=VarPowerFlowReferenceType.vf_B)
    parent_vf_c: Any = grid.var_factory.add_var("vf_C_faulted_line_branch", reference=VarPowerFlowReferenceType.vf_C)
    parent_vt_a: Any = grid.var_factory.add_var("vt_A_faulted_line_branch", reference=VarPowerFlowReferenceType.vt_A)
    parent_vt_b: Any = grid.var_factory.add_var("vt_B_faulted_line_branch", reference=VarPowerFlowReferenceType.vt_B)
    parent_vt_c: Any = grid.var_factory.add_var("vt_C_faulted_line_branch", reference=VarPowerFlowReferenceType.vt_C)
    parent_if_a: Any = grid.var_factory.add_var("if_A_faulted_line_branch", reference=VarPowerFlowReferenceType.if_A)
    parent_if_b: Any = grid.var_factory.add_var("if_B_faulted_line_branch", reference=VarPowerFlowReferenceType.if_B)
    parent_if_c: Any = grid.var_factory.add_var("if_C_faulted_line_branch", reference=VarPowerFlowReferenceType.if_C)
    parent_it_a: Any = grid.var_factory.add_var("it_A_faulted_line_branch", reference=VarPowerFlowReferenceType.it_A)
    parent_it_b: Any = grid.var_factory.add_var("it_B_faulted_line_branch", reference=VarPowerFlowReferenceType.it_B)
    parent_it_c: Any = grid.var_factory.add_var("it_C_faulted_line_branch", reference=VarPowerFlowReferenceType.it_C)

    midpoint_i_a: Any = grid.var_factory.add_var("i_mid_A_faulted_line_branch")
    midpoint_i_b: Any = grid.var_factory.add_var("i_mid_B_faulted_line_branch")
    midpoint_i_c: Any = grid.var_factory.add_var("i_mid_C_faulted_line_branch")

    # The parent drives every child input through explicit wrapper variables.
    fault_block.connect([v_outer_a, v_outer_b, v_outer_c], [parent_vf_a, parent_vf_b, parent_vf_c])
    fault_block.connect([i_inner_a, i_inner_b, i_inner_c], [midpoint_i_a, midpoint_i_b, midpoint_i_c])
    line_block.connect([vf_a, vf_b, vf_c], [v_inner_a, v_inner_b, v_inner_c])
    line_block.connect([vt_a, vt_b, vt_c], [parent_vt_a, parent_vt_b, parent_vt_c])

    root_block.in_vars = list([parent_vf_a, parent_vf_b, parent_vf_c, parent_vt_a, parent_vt_b, parent_vt_c])
    root_block.out_vars = list([parent_if_a, parent_if_b, parent_if_c, parent_it_a, parent_it_b, parent_it_c])
    root_block.algebraic_vars = list([
        parent_if_a,
        parent_if_b,
        parent_if_c,
        parent_it_a,
        parent_it_b,
        parent_it_c,
        midpoint_i_a,
        midpoint_i_b,
        midpoint_i_c,
    ])
    root_block.algebraic_eqs = list([
        parent_if_a - i_outer_a,
        parent_if_b - i_outer_b,
        parent_if_c - i_outer_c,
        parent_it_a - it_a,
        parent_it_b - it_b,
        parent_it_c - it_c,
        midpoint_i_a - if_a,
        midpoint_i_b - if_b,
        midpoint_i_c - if_c,
    ])
    root_block.external_mapping = dict({
        VarPowerFlowReferenceType.vf_N: None,
        VarPowerFlowReferenceType.vf_A: parent_vf_a,
        VarPowerFlowReferenceType.vf_B: parent_vf_b,
        VarPowerFlowReferenceType.vf_C: parent_vf_c,
        VarPowerFlowReferenceType.vt_N: None,
        VarPowerFlowReferenceType.vt_A: parent_vt_a,
        VarPowerFlowReferenceType.vt_B: parent_vt_b,
        VarPowerFlowReferenceType.vt_C: parent_vt_c,
        VarPowerFlowReferenceType.if_N: None,
        VarPowerFlowReferenceType.if_A: parent_if_a,
        VarPowerFlowReferenceType.if_B: parent_if_b,
        VarPowerFlowReferenceType.if_C: parent_if_c,
        VarPowerFlowReferenceType.it_N: None,
        VarPowerFlowReferenceType.it_A: parent_it_a,
        VarPowerFlowReferenceType.it_B: parent_it_b,
        VarPowerFlowReferenceType.it_C: parent_it_c,
        VarPowerFlowReferenceType.Sf_A: None,
        VarPowerFlowReferenceType.Sf_B: None,
        VarPowerFlowReferenceType.Sf_C: None,
        VarPowerFlowReferenceType.St_A: None,
        VarPowerFlowReferenceType.St_B: None,
        VarPowerFlowReferenceType.St_C: None,
        VarPowerFlowReferenceType.d_v_N_f: None,
        VarPowerFlowReferenceType.d_v_A_f: None,
        VarPowerFlowReferenceType.d_v_B_f: None,
        VarPowerFlowReferenceType.d_v_C_f: None,
        VarPowerFlowReferenceType.d_v_N_t: None,
        VarPowerFlowReferenceType.d_v_A_t: None,
        VarPowerFlowReferenceType.d_v_B_t: None,
        VarPowerFlowReferenceType.d_v_C_t: None,
    })

    return root_block, fault_block, line_block


def _attach_emt_models(grid: MultiCircuit,
                       line: Line,
                       source: Generator,
                       remote_load: Load) -> tuple[Block, Block, Block, Block]:
    """
    Build and attach EMT models to the study devices.

    :param grid: Study grid.
    :param line: Host line device.
    :param source: Slack-equivalent source.
    :param remote_load: Steady-state load.
    :return: Tuple with the attached source, composite line, fault child, and load models.
    """
    bus: Bus

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)
    else:
        pass

    source_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    line_composite_mdl: Block
    fault_child_mdl: Block
    line_child_mdl: Block
    line_composite_mdl, fault_child_mdl, line_child_mdl = _build_faulted_line_composite(grid)
    remote_load_mdl: Block = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

    set_emt_model(device=source, model=source_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line, model=line_composite_mdl, var_factory=grid.var_factory)
    set_emt_model(device=remote_load, model=remote_load_mdl, var_factory=grid.var_factory)

    return source_mdl, line_composite_mdl, fault_child_mdl, remote_load_mdl


def _add_fault_events(grid: MultiCircuit, line: Line, fault_child_mdl: Block) -> None:
    """
    Add EMT mode events that apply and clear the internal fault block.

    :param grid: Study grid.
    :param line: Host line device that owns the composed branch model.
    :param fault_child_mdl: Internal fault block.
    :return: None.
    """
    fault_mode_var: Any = _find_required_var("fault_closed_mode_internal_fault", fault_child_mdl)
    events_group: EmtEventsGroup = EmtEventsGroup(name="balanced_fault_case")
    grid.add_emt_events_group(events_group)

    grid.add_emt_event(EmtEvent(device=line, parameter=fault_mode_var, time=0.04, value=1.0, group=events_group))
    grid.add_emt_event(EmtEvent(device=line, parameter=fault_mode_var, time=0.08, value=0.0, group=events_group))


def _run_power_flow(grid: MultiCircuit) -> Any:
    """
    Run the steady-state power flow used to seed the EMT initialization.

    :param grid: Study grid.
    :return: Power-flow results object.
    """
    pf_options: PowerFlowOptions = PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1.0e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    power_flow: PowerFlowDriver = PowerFlowDriver(grid, pf_options)
    power_flow.run()
    return power_flow.results


def _run_emt(grid: MultiCircuit, pf_results: Any) -> tuple[EmtProblemDae, Any]:
    """
    Run the EMT simulation for the balanced-fault case.

    :param grid: Study grid.
    :param pf_results: Steady-state initialization results.
    :return: Tuple ``(problem, solver_results)``.
    """
    options: EmtOptions = EmtOptions(
        time_step=5.0e-6,
        simulation_time=0.12,
        tolerance=1.0e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=1,
    )
    problem: EmtProblemDae = EmtProblemDae(grid=grid, options=options, pf_results_3ph=None, pf_results=pf_results)
    solver: StructuralCompiledSolver = StructuralCompiledSolver(
        problem=problem,
        t0=0.0,
        t_end=options.simulation_time,
        h=options.time_step,
        method=options.integration_method,
        pred_method=DynamicIntegrationMethod.OdeEuler,
        dense_threshold=0,
        verbose=True,
    )
    time_values: np.ndarray
    state_values: np.ndarray
    diff_values: np.ndarray
    well_initialized: bool
    converged: bool
    time_values, state_values, diff_values, well_initialized, converged = solver.simulate(boundary_updater=problem)

    solver_results: Dict[str, Any] = dict({
        "t": time_values,
        "y": state_values,
        "dy": diff_values,
        "well_initialized": well_initialized,
        "converged": converged,
    })
    return problem, solver_results


def _extract_series(problem: EmtProblemDae, solver_results: Any, var: Any) -> np.ndarray:
    """
    Extract one simulated variable trajectory from the solver results.

    :param problem: EMT problem instance.
    :param solver_results: Solver results object.
    :param var: Symbolic variable to extract.
    :return: One-dimensional trajectory array.
    """
    var_index: int = problem.get_var_idx(var)
    return np.asarray(solver_results["y"][:, var_index], dtype=float)


def _plot_results(problem: EmtProblemDae,
                  solver_results: Any,
                  bus_source: Bus,
                  bus_remote: Bus,
                  fault_child_mdl: Block,
                  source_mdl: Block,
                  line_composite_mdl: Block) -> None:
    """
    Plot the main electrical response of the composed balanced-fault branch case.

    :param problem: EMT problem instance.
    :param solver_results: Solver results object.
    :param bus_source: Sending-end bus.
    :param bus_remote: Receiving-end bus.
    :param fault_child_mdl: Internal fault block.
    :param source_mdl: Source EMT model.
    :param line_composite_mdl: Composed branch model.
    :return: None.
    """
    fault_apply_time_s: float = 0.04
    fault_clear_time_s: float = 0.08
    tme: np.ndarray = np.asarray(solver_results["t"], dtype=float)
    v_a_source_var: Any = _find_required_var("v_A", bus_source.emt_model)
    v_b_source_var: Any = _find_required_var("v_B", bus_source.emt_model)
    v_c_source_var: Any = _find_required_var("v_C", bus_source.emt_model)
    v_a_remote_var: Any = _find_required_var("v_A", bus_remote.emt_model)
    v_b_remote_var: Any = _find_required_var("v_B", bus_remote.emt_model)
    v_c_remote_var: Any = _find_required_var("v_C", bus_remote.emt_model)
    i_ser_a_var: Any = _find_required_var("i_ser_faulted_pi_line_A", line_composite_mdl)
    i_ser_b_var: Any = _find_required_var("i_ser_faulted_pi_line_B", line_composite_mdl)
    i_ser_c_var: Any = _find_required_var("i_ser_faulted_pi_line_C", line_composite_mdl)
    if_line_a_var: Any = _find_required_var("if_faulted_pi_line_A", line_composite_mdl)
    if_line_b_var: Any = _find_required_var("if_faulted_pi_line_B", line_composite_mdl)
    if_line_c_var: Any = _find_required_var("if_faulted_pi_line_C", line_composite_mdl)
    it_line_a_var: Any = _find_required_var("it_faulted_pi_line_A", line_composite_mdl)
    it_line_b_var: Any = _find_required_var("it_faulted_pi_line_B", line_composite_mdl)
    it_line_c_var: Any = _find_required_var("it_faulted_pi_line_C", line_composite_mdl)
    i_cap_f_a_var: Any = _find_required_var("i_cap_f_faulted_pi_line_A", line_composite_mdl)
    i_cap_f_b_var: Any = _find_required_var("i_cap_f_faulted_pi_line_B", line_composite_mdl)
    i_cap_f_c_var: Any = _find_required_var("i_cap_f_faulted_pi_line_C", line_composite_mdl)
    i_cap_t_a_var: Any = _find_required_var("i_cap_t_faulted_pi_line_A", line_composite_mdl)
    i_cap_t_b_var: Any = _find_required_var("i_cap_t_faulted_pi_line_B", line_composite_mdl)
    i_cap_t_c_var: Any = _find_required_var("i_cap_t_faulted_pi_line_C", line_composite_mdl)
    i_fault_a_var: Any = _find_required_var("i_fault_AN_internal_fault", fault_child_mdl)
    i_fault_b_var: Any = _find_required_var("i_fault_BN_internal_fault", fault_child_mdl)
    i_fault_c_var: Any = _find_required_var("i_fault_CN_internal_fault", fault_child_mdl)
    i_outer_a_var: Any = _find_required_var("i_outer_A_internal_fault", line_composite_mdl)
    i_outer_b_var: Any = _find_required_var("i_outer_B_internal_fault", line_composite_mdl)
    i_outer_c_var: Any = _find_required_var("i_outer_C_internal_fault", line_composite_mdl)
    pe_var: Any = _find_required_var("Pe_emt_thevenin_eq_generator_template", source_mdl)
    qe_var: Any = _find_required_var("Qe_emt_thevenin_eq_generator_template", source_mdl)
    fault_mode_var: Any = _find_required_var("fault_closed_mode_internal_fault", fault_child_mdl)

    v_source_a: np.ndarray = _extract_series(problem, solver_results, v_a_source_var)
    v_source_b: np.ndarray = _extract_series(problem, solver_results, v_b_source_var)
    v_source_c: np.ndarray = _extract_series(problem, solver_results, v_c_source_var)
    v_remote_a: np.ndarray = _extract_series(problem, solver_results, v_a_remote_var)
    v_remote_b: np.ndarray = _extract_series(problem, solver_results, v_b_remote_var)
    v_remote_c: np.ndarray = _extract_series(problem, solver_results, v_c_remote_var)
    i_ser_a: np.ndarray = _extract_series(problem, solver_results, i_ser_a_var)
    i_ser_b: np.ndarray = _extract_series(problem, solver_results, i_ser_b_var)
    i_ser_c: np.ndarray = _extract_series(problem, solver_results, i_ser_c_var)
    if_line_a: np.ndarray = _extract_series(problem, solver_results, if_line_a_var)
    if_line_b: np.ndarray = _extract_series(problem, solver_results, if_line_b_var)
    if_line_c: np.ndarray = _extract_series(problem, solver_results, if_line_c_var)
    it_line_a: np.ndarray = _extract_series(problem, solver_results, it_line_a_var)
    it_line_b: np.ndarray = _extract_series(problem, solver_results, it_line_b_var)
    it_line_c: np.ndarray = _extract_series(problem, solver_results, it_line_c_var)
    i_cap_f_a: np.ndarray = _extract_series(problem, solver_results, i_cap_f_a_var)
    i_cap_f_b: np.ndarray = _extract_series(problem, solver_results, i_cap_f_b_var)
    i_cap_f_c: np.ndarray = _extract_series(problem, solver_results, i_cap_f_c_var)
    i_cap_t_a: np.ndarray = _extract_series(problem, solver_results, i_cap_t_a_var)
    i_cap_t_b: np.ndarray = _extract_series(problem, solver_results, i_cap_t_b_var)
    i_cap_t_c: np.ndarray = _extract_series(problem, solver_results, i_cap_t_c_var)
    i_fault_a: np.ndarray = _extract_series(problem, solver_results, i_fault_a_var)
    i_fault_b: np.ndarray = _extract_series(problem, solver_results, i_fault_b_var)
    i_fault_c: np.ndarray = _extract_series(problem, solver_results, i_fault_c_var)
    i_outer_a: np.ndarray = _extract_series(problem, solver_results, i_outer_a_var)
    i_outer_b: np.ndarray = _extract_series(problem, solver_results, i_outer_b_var)
    i_outer_c: np.ndarray = _extract_series(problem, solver_results, i_outer_c_var)
    pe_vals: np.ndarray = _extract_series(problem, solver_results, pe_var)
    qe_vals: np.ndarray = _extract_series(problem, solver_results, qe_var)
    fault_mode_vals: np.ndarray = np.full_like(tme, 0.0)

    for idx_time, time_value in enumerate(tme):
        if time_value < fault_apply_time_s:
            fault_mode_vals[idx_time] = 0.0
        else:
            if time_value < fault_clear_time_s:
                fault_mode_vals[idx_time] = 1.0
            else:
                fault_mode_vals[idx_time] = 0.0

    i_fault_sum: np.ndarray = i_fault_a + i_fault_b + i_fault_c
    kcl_a: np.ndarray = i_outer_a - if_line_a - i_fault_a
    kcl_b: np.ndarray = i_outer_b - if_line_b - i_fault_b
    kcl_c: np.ndarray = i_outer_c - if_line_c - i_fault_c
    outer_match_a: np.ndarray = i_outer_a - if_line_a
    outer_match_b: np.ndarray = i_outer_b - if_line_b
    outer_match_c: np.ndarray = i_outer_c - if_line_c

    fault_window_mask: np.ndarray = np.logical_and(tme >= 0.05, tme <= 0.075)
    i_fault_a_rms: float = float(np.sqrt(np.mean(np.square(i_fault_a[fault_window_mask]))))
    i_fault_b_rms: float = float(np.sqrt(np.mean(np.square(i_fault_b[fault_window_mask]))))
    i_fault_c_rms: float = float(np.sqrt(np.mean(np.square(i_fault_c[fault_window_mask]))))
    rms_average: float = (i_fault_a_rms + i_fault_b_rms + i_fault_c_rms) / 3.0
    rms_imbalance_max: float = float(max(
        abs(i_fault_a_rms - rms_average),
        abs(i_fault_b_rms - rms_average),
        abs(i_fault_c_rms - rms_average),
    ) / rms_average)

    print(f"Fault RMS current A [0.05-0.075 s]: {i_fault_a_rms:.6f} p.u.")
    print(f"Fault RMS current B [0.05-0.075 s]: {i_fault_b_rms:.6f} p.u.")
    print(f"Fault RMS current C [0.05-0.075 s]: {i_fault_c_rms:.6f} p.u.")
    print(f"Max relative RMS imbalance: {rms_imbalance_max:.6e}")
    print(f"Max |i_A + i_B + i_C| during fault: {float(np.max(np.abs(i_fault_sum[fault_window_mask]))):.6e}")
    print(f"Max KCL residual A: {float(np.max(np.abs(kcl_a[fault_window_mask]))):.6e}")
    print(f"Max KCL residual B: {float(np.max(np.abs(kcl_b[fault_window_mask]))):.6e}")
    print(f"Max KCL residual C: {float(np.max(np.abs(kcl_c[fault_window_mask]))):.6e}")

    def _add_fault_markers() -> None:
        """
        Add vertical markers for fault application and clearing times.

        :return: None.
        """
        plt.axvline(fault_apply_time_s, color='black', linestyle='--', linewidth=1.0)
        plt.axvline(fault_clear_time_s, color='black', linestyle='--', linewidth=1.0)

    plt.figure(figsize=(12.0, 8.0))
    plt.subplot(2, 1, 1)
    plt.plot(tme, v_source_a[:len(tme)], label='Source bus Va', color='blue')
    plt.plot(tme, v_source_b[:len(tme)], label='Source bus Vb', color='red')
    plt.plot(tme, v_source_c[:len(tme)], label='Source bus Vc', color='green')
    _add_fault_markers()
    plt.ylabel('Voltage [p.u.]')
    plt.title('Sending-End Bus Voltages')
    plt.grid(True)
    plt.legend()

    plt.subplot(2, 1, 2)
    plt.plot(tme, v_remote_a[:len(tme)], label='Remote bus Va', color='blue')
    plt.plot(tme, v_remote_b[:len(tme)], label='Remote bus Vb', color='red')
    plt.plot(tme, v_remote_c[:len(tme)], label='Remote bus Vc', color='green')
    _add_fault_markers()
    plt.xlabel('Time [s]')
    plt.ylabel('Voltage [p.u.]')
    plt.title('Remote Bus Voltages During Internal Balanced Fault')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.figure(figsize=(12.0, 8.0))
    plt.subplot(2, 1, 1)
    plt.plot(tme, i_outer_a[:len(tme)], label='Branch current A', color='blue')
    plt.plot(tme, i_outer_b[:len(tme)], label='Branch current B', color='red')
    plt.plot(tme, i_outer_c[:len(tme)], label='Branch current C', color='green')
    _add_fault_markers()
    plt.ylabel('Current [p.u.]')
    plt.title('Composite Branch Sending-End Currents')
    plt.grid(True)
    plt.legend()

    plt.subplot(2, 1, 2)
    plt.plot(tme, i_fault_a[:len(tme)], label='Fault phase current A', color='blue')
    plt.plot(tme, i_fault_b[:len(tme)], label='Fault phase current B', color='red')
    plt.plot(tme, i_fault_c[:len(tme)], label='Fault phase current C', color='green')
    plt.plot(tme, i_fault_sum[:len(tme)], label='Fault current sum', color='black')
    _add_fault_markers()
    plt.xlabel('Time [s]')
    plt.ylabel('Current [p.u.]')
    plt.title('Physical Fault Phase Currents')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.figure(figsize=(12.0, 5.0))
    plt.plot(tme, kcl_a[:len(tme)], label='KCL residual A', color='blue')
    plt.plot(tme, kcl_b[:len(tme)], label='KCL residual B', color='red')
    plt.plot(tme, kcl_c[:len(tme)], label='KCL residual C', color='green')
    plt.plot(tme, outer_match_a[:len(tme)], label='Outer-line match A', color='cyan')
    plt.plot(tme, outer_match_b[:len(tme)], label='Outer-line match B', color='magenta')
    plt.plot(tme, outer_match_c[:len(tme)], label='Outer-line match C', color='lime')
    _add_fault_markers()
    plt.xlabel('Time [s]')
    plt.ylabel('Residual [p.u.]')
    plt.title('Fault KCL and Interface Residuals')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.figure(figsize=(12.0, 8.0))
    plt.subplot(2, 1, 1)
    plt.plot(tme, i_ser_a[:len(tme)], label='Line series current A', color='blue')
    plt.plot(tme, i_ser_b[:len(tme)], label='Line series current B', color='red')
    plt.plot(tme, i_ser_c[:len(tme)], label='Line series current C', color='green')
    _add_fault_markers()
    plt.ylabel('Current [p.u.]')
    plt.title('Internal Line Series Currents')
    plt.grid(True)
    plt.legend()

    plt.subplot(2, 1, 2)
    plt.plot(tme, if_line_a[:len(tme)], label='Line from current A', color='blue')
    plt.plot(tme, if_line_b[:len(tme)], label='Line from current B', color='red')
    plt.plot(tme, if_line_c[:len(tme)], label='Line from current C', color='green')
    plt.plot(tme, it_line_a[:len(tme)], label='Line to current A', color='cyan')
    plt.plot(tme, it_line_b[:len(tme)], label='Line to current B', color='magenta')
    plt.plot(tme, it_line_c[:len(tme)], label='Line to current C', color='lime')
    _add_fault_markers()
    plt.xlabel('Time [s]')
    plt.ylabel('Current [p.u.]')
    plt.title('Line Terminal Currents')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.figure(figsize=(12.0, 8.0))
    plt.subplot(2, 1, 1)
    plt.plot(tme, i_outer_a[:len(tme)], label='Fault outer current A', color='blue')
    plt.plot(tme, i_outer_b[:len(tme)], label='Fault outer current B', color='red')
    plt.plot(tme, i_outer_c[:len(tme)], label='Fault outer current C', color='green')
    plt.plot(tme, if_line_a[:len(tme)], label='Line from current A', color='cyan')
    plt.plot(tme, if_line_b[:len(tme)], label='Line from current B', color='magenta')
    plt.plot(tme, if_line_c[:len(tme)], label='Line from current C', color='lime')
    _add_fault_markers()
    plt.ylabel('Current [p.u.]')
    plt.title('Fault Outer Currents Versus Line From Currents')
    plt.grid(True)
    plt.legend()

    plt.subplot(2, 1, 2)
    plt.plot(tme, i_cap_f_a[:len(tme)], label='From shunt current A', color='blue')
    plt.plot(tme, i_cap_f_b[:len(tme)], label='From shunt current B', color='red')
    plt.plot(tme, i_cap_f_c[:len(tme)], label='From shunt current C', color='green')
    plt.plot(tme, i_cap_t_a[:len(tme)], label='To shunt current A', color='cyan')
    plt.plot(tme, i_cap_t_b[:len(tme)], label='To shunt current B', color='magenta')
    plt.plot(tme, i_cap_t_c[:len(tme)], label='To shunt current C', color='lime')
    _add_fault_markers()
    plt.xlabel('Time [s]')
    plt.ylabel('Current [p.u.]')
    plt.title('Line Shunt Capacitive Currents')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.figure(figsize=(10.0, 4.0))
    plt.plot(tme, pe_vals[:len(tme)], label='Source Pe', color='blue')
    plt.plot(tme, qe_vals[:len(tme)], label='Source Qe', color='red')
    _add_fault_markers()
    plt.xlabel('Time [s]')
    plt.ylabel('Power [p.u.]')
    plt.title('Source Electrical Power Response')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.figure(figsize=(10.0, 3.5))
    plt.step(tme, fault_mode_vals[:len(tme)], where='post', label='fault_closed_mode', color='black')
    _add_fault_markers()
    plt.xlabel('Time [s]')
    plt.ylabel('Mode')
    plt.title('Fault Mode Event Status')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    plt.show()


def main() -> None:
    """
    Run one EMT balanced-fault example using the internal fault template.

    :return: None.
    """
    grid: MultiCircuit
    bus_source: Bus
    bus_remote: Bus
    line: Line
    source: Generator
    remote_load: Load
    grid, bus_source, bus_remote, line, source, remote_load = _build_demo_grid()

    source_mdl: Block
    line_composite_mdl: Block
    fault_child_mdl: Block
    remote_load_mdl: Block
    source_mdl, line_composite_mdl, fault_child_mdl, remote_load_mdl = _attach_emt_models(
        grid=grid,
        line=line,
        source=source,
        remote_load=remote_load,
    )
    _add_fault_events(grid=grid, line=line, fault_child_mdl=fault_child_mdl)

    pf_results: Any = _run_power_flow(grid)
    problem: EmtProblemDae
    solver_results: Any
    problem, solver_results = _run_emt(grid=grid, pf_results=pf_results)

    print(f"EMT initialization method used: {problem.initialization_report.method_used}")
    print(f"EMT initialization status: {problem.initialization_report.status}")
    print(f"EMT well initialized: {solver_results['well_initialized']}")
    print(f"EMT converged: {solver_results['converged']}")
    print(f"Recorded EMT time steps: {len(solver_results['t'])}")

    _plot_results(
        problem=problem,
        solver_results=solver_results,
        bus_source=bus_source,
        bus_remote=bus_remote,
        fault_child_mdl=fault_child_mdl,
        source_mdl=source_mdl,
        line_composite_mdl=line_composite_mdl,
    )


if __name__ == "__main__":
    main()
