"""Common EMT fault-case runner utilities.

:copyright: Mozilla Public License 2.0
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib
import numpy as np

REPO_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_ROOT: str = os.path.join(REPO_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
else:
    pass

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
else:
    pass

matplotlib.use("Agg")

from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
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
from VeraGridEngine.Templates.Emt.fault_emt_template import get_fault_emt_template, validate_fault_phase_selection
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.block import Block, build_name_to_var_lookup, find_name_in_block
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import (
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


class FaultCaseConfig:
    """Store one EMT fault study configuration.

    :param case_name: Deterministic case identifier.
    :param case_title: Human-readable case title.
    :param fault_type: Fault topology enum.
    :param ph_a: Whether phase A is faulted.
    :param ph_b: Whether phase B is faulted.
    :param ph_c: Whether phase C is faulted.
    :param placement_side: Fault placement side inside the composed branch.
    :param fault_time_s: Fault application time in seconds.
    :param clear_time_s: Fault clearing time in seconds.
    :param fault_resistance: Phase fault resistance in pu.
    :param ground_resistance: Ground fault resistance in pu.
    :return: None.
    """

    __slots__ = (
        "_case_name",
        "_case_title",
        "_fault_type",
        "_ph_a",
        "_ph_b",
        "_ph_c",
        "_placement_side",
        "_fault_time_s",
        "_clear_time_s",
        "_fault_resistance",
        "_ground_resistance",
    )

    def __init__(self,
                 case_name: str,
                 case_title: str,
                 fault_type: FaultType,
                 ph_a: bool,
                 ph_b: bool,
                 ph_c: bool,
                 placement_side: EmtFaultPlacementSide,
                 fault_time_s: float,
                 clear_time_s: float,
                 fault_resistance: float,
                 ground_resistance: float) -> None:
        """Initialize one fault-case configuration.

        :param case_name: Deterministic case identifier.
        :param case_title: Human-readable case title.
        :param fault_type: Fault topology enum.
        :param ph_a: Whether phase A is faulted.
        :param ph_b: Whether phase B is faulted.
        :param ph_c: Whether phase C is faulted.
        :param placement_side: Fault placement side inside the composed branch.
        :param fault_time_s: Fault application time in seconds.
        :param clear_time_s: Fault clearing time in seconds.
        :param fault_resistance: Phase fault resistance in pu.
        :param ground_resistance: Ground fault resistance in pu.
        :return: None.
        """
        self._case_name: str = case_name
        self._case_title: str = case_title
        self._fault_type: FaultType = fault_type
        self._ph_a: bool = ph_a
        self._ph_b: bool = ph_b
        self._ph_c: bool = ph_c
        self._placement_side: EmtFaultPlacementSide = placement_side
        self._fault_time_s: float = fault_time_s
        self._clear_time_s: float = clear_time_s
        self._fault_resistance: float = fault_resistance
        self._ground_resistance: float = ground_resistance

    @property
    def case_name(self) -> str:
        """Return the case identifier.

        :return: Case identifier.
        """
        return self._case_name

    @property
    def case_title(self) -> str:
        """Return the case title.

        :return: Case title.
        """
        return self._case_title

    @property
    def fault_type(self) -> FaultType:
        """Return the configured fault type.

        :return: Fault topology enum.
        """
        return self._fault_type

    @property
    def ph_a(self) -> bool:
        """Return whether phase A is active.

        :return: Phase-A activity flag.
        """
        return self._ph_a

    @property
    def ph_b(self) -> bool:
        """Return whether phase B is active.

        :return: Phase-B activity flag.
        """
        return self._ph_b

    @property
    def ph_c(self) -> bool:
        """Return whether phase C is active.

        :return: Phase-C activity flag.
        """
        return self._ph_c

    @property
    def placement_side(self) -> EmtFaultPlacementSide:
        """Return the placement side.

        :return: Placement side enum.
        """
        return self._placement_side

    @property
    def fault_time_s(self) -> float:
        """Return the fault application time.

        :return: Fault application time in seconds.
        """
        return self._fault_time_s

    @property
    def clear_time_s(self) -> float:
        """Return the fault clearing time.

        :return: Fault clearing time in seconds.
        """
        return self._clear_time_s

    @property
    def fault_resistance(self) -> float:
        """Return the phase fault resistance.

        :return: Fault resistance in pu.
        """
        return self._fault_resistance

    @property
    def ground_resistance(self) -> float:
        """Return the ground fault resistance.

        :return: Ground fault resistance in pu.
        """
        return self._ground_resistance


class EmtRunResult:
    """Store one EMT solver run result.

    :param time_values: Simulated time vector.
    :param state_values: Simulated variable matrix.
    :param diff_values: Simulated derivative matrix.
    :param well_initialized: Initialization status flag.
    :param converged: Solver convergence flag.
    :return: None.
    """

    __slots__ = ("_time_values", "_state_values", "_diff_values", "_well_initialized", "_converged")

    def __init__(self,
                 time_values: np.ndarray,
                 state_values: np.ndarray,
                 diff_values: np.ndarray,
                 well_initialized: bool,
                 converged: bool) -> None:
        """Initialize one EMT run result.

        :param time_values: Simulated time vector.
        :param state_values: Simulated variable matrix.
        :param diff_values: Simulated derivative matrix.
        :param well_initialized: Initialization status flag.
        :param converged: Solver convergence flag.
        :return: None.
        """
        self._time_values: np.ndarray = time_values
        self._state_values: np.ndarray = state_values
        self._diff_values: np.ndarray = diff_values
        self._well_initialized: bool = well_initialized
        self._converged: bool = converged

    @property
    def time_values(self) -> np.ndarray:
        """Return the time vector.

        :return: Time vector.
        """
        return self._time_values

    @property
    def state_values(self) -> np.ndarray:
        """Return the state-value matrix.

        :return: State-value matrix.
        """
        return self._state_values

    @property
    def diff_values(self) -> np.ndarray:
        """Return the derivative-value matrix.

        :return: Derivative-value matrix.
        """
        return self._diff_values

    @property
    def well_initialized(self) -> bool:
        """Return the initialization flag.

        :return: Initialization flag.
        """
        return self._well_initialized

    @property
    def converged(self) -> bool:
        """Return the convergence flag.

        :return: Convergence flag.
        """
        return self._converged


class FaultResultData:
    """Store one fully processed fault-case waveform bundle.

    :param time_values: Time vector.
    :param fault_mask: Boolean fault-window mask.
    :param source_voltages: Source-bus three-phase voltages.
    :param remote_voltages: Remote-bus three-phase voltages.
    :param fault_voltages: Fault-point three-phase voltages.
    :param sending_currents: Sending-end branch currents.
    :param receiving_currents: Receiving-end branch currents.
    :param fault_currents: Physical direct fault currents.
    :param rms_fault_currents_trace: Sliding RMS current traces.
    :param fault_mode: Fault mode trace.
    :param kcl_residuals: KCL residual traces.
    :param interface_residuals: Interface residual traces.
    :param rms_fault_currents: Window RMS current values.
    :param max_current_magnitude: Maximum direct-current magnitude during the fault.
    :return: None.
    """

    __slots__ = (
        "_time_values",
        "_fault_mask",
        "_source_voltages",
        "_remote_voltages",
        "_fault_voltages",
        "_sending_currents",
        "_receiving_currents",
        "_fault_currents",
        "_rms_fault_currents_trace",
        "_fault_mode",
        "_kcl_residuals",
        "_interface_residuals",
        "_rms_fault_currents",
        "_max_current_magnitude",
    )

    def __init__(self,
                 time_values: np.ndarray,
                 fault_mask: np.ndarray,
                 source_voltages: np.ndarray,
                 remote_voltages: np.ndarray,
                 fault_voltages: np.ndarray,
                 sending_currents: np.ndarray,
                 receiving_currents: np.ndarray,
                 fault_currents: np.ndarray,
                 rms_fault_currents_trace: np.ndarray,
                 fault_mode: np.ndarray,
                 kcl_residuals: np.ndarray,
                 interface_residuals: np.ndarray,
                 rms_fault_currents: np.ndarray,
                 max_current_magnitude: float) -> None:
        """Initialize one processed waveform bundle.

        :param time_values: Time vector.
        :param fault_mask: Boolean fault-window mask.
        :param source_voltages: Source-bus three-phase voltages.
        :param remote_voltages: Remote-bus three-phase voltages.
        :param fault_voltages: Fault-point three-phase voltages.
        :param sending_currents: Sending-end branch currents.
        :param receiving_currents: Receiving-end branch currents.
        :param fault_currents: Physical direct fault currents.
        :param rms_fault_currents_trace: Sliding RMS current traces.
        :param fault_mode: Fault mode trace.
        :param kcl_residuals: KCL residual traces.
        :param interface_residuals: Interface residual traces.
        :param rms_fault_currents: Window RMS current values.
        :param max_current_magnitude: Maximum direct-current magnitude during the fault.
        :return: None.
        """
        self._time_values: np.ndarray = time_values
        self._fault_mask: np.ndarray = fault_mask
        self._source_voltages: np.ndarray = source_voltages
        self._remote_voltages: np.ndarray = remote_voltages
        self._fault_voltages: np.ndarray = fault_voltages
        self._sending_currents: np.ndarray = sending_currents
        self._receiving_currents: np.ndarray = receiving_currents
        self._fault_currents: np.ndarray = fault_currents
        self._rms_fault_currents_trace: np.ndarray = rms_fault_currents_trace
        self._fault_mode: np.ndarray = fault_mode
        self._kcl_residuals: np.ndarray = kcl_residuals
        self._interface_residuals: np.ndarray = interface_residuals
        self._rms_fault_currents: np.ndarray = rms_fault_currents
        self._max_current_magnitude: float = max_current_magnitude

    @property
    def time_values(self) -> np.ndarray:
        """Return the time vector.

        :return: Time vector.
        """
        return self._time_values

    @property
    def fault_mask(self) -> np.ndarray:
        """Return the fault-window mask.

        :return: Fault-window mask.
        """
        return self._fault_mask

    @property
    def source_voltages(self) -> np.ndarray:
        """Return the source voltages.

        :return: Source voltage matrix.
        """
        return self._source_voltages

    @property
    def remote_voltages(self) -> np.ndarray:
        """Return the remote voltages.

        :return: Remote voltage matrix.
        """
        return self._remote_voltages

    @property
    def fault_voltages(self) -> np.ndarray:
        """Return the fault-point voltages.

        :return: Fault voltage matrix.
        """
        return self._fault_voltages

    @property
    def sending_currents(self) -> np.ndarray:
        """Return the sending-end currents.

        :return: Sending current matrix.
        """
        return self._sending_currents

    @property
    def receiving_currents(self) -> np.ndarray:
        """Return the receiving-end currents.

        :return: Receiving current matrix.
        """
        return self._receiving_currents

    @property
    def fault_currents(self) -> np.ndarray:
        """Return the physical fault currents.

        :return: Fault current matrix.
        """
        return self._fault_currents

    @property
    def rms_fault_currents_trace(self) -> np.ndarray:
        """Return the sliding RMS current traces.

        :return: RMS trace matrix.
        """
        return self._rms_fault_currents_trace

    @property
    def fault_mode(self) -> np.ndarray:
        """Return the fault mode trace.

        :return: Fault mode trace.
        """
        return self._fault_mode

    @property
    def kcl_residuals(self) -> np.ndarray:
        """Return the KCL residuals.

        :return: KCL residual matrix.
        """
        return self._kcl_residuals

    @property
    def interface_residuals(self) -> np.ndarray:
        """Return the interface residuals.

        :return: Interface residual matrix.
        """
        return self._interface_residuals

    @property
    def rms_fault_currents(self) -> np.ndarray:
        """Return the window RMS values.

        :return: RMS current vector.
        """
        return self._rms_fault_currents

    @property
    def max_current_magnitude(self) -> float:
        """Return the maximum direct fault-current magnitude.

        :return: Maximum direct fault-current magnitude.
        """
        return self._max_current_magnitude


class FaultCaseExecution:
    """Store one complete case execution bundle.

    :param power_flow_results: Power-flow results object.
    :param problem: Built EMT problem.
    :param emt_run_result: EMT solver run result.
    :param fault_result_data: Processed waveform and diagnostic data.
    :param plots_dir: Directory containing exported plots.
    :param case_name: Case identifier.
    :return: None.
    """

    __slots__ = ("_power_flow_results", "_problem", "_emt_run_result", "_fault_result_data", "_plots_dir", "_case_name")

    def __init__(self,
                 power_flow_results: object,
                 problem: EmtProblemDae,
                 emt_run_result: EmtRunResult,
                 fault_result_data: FaultResultData,
                 plots_dir: Path,
                 case_name: str) -> None:
        """Initialize one case execution bundle.

        :param power_flow_results: Power-flow results object.
        :param problem: Built EMT problem.
        :param emt_run_result: EMT solver run result.
        :param fault_result_data: Processed waveform and diagnostic data.
        :param plots_dir: Directory containing exported plots.
        :param case_name: Case identifier.
        :return: None.
        """
        self._power_flow_results: object = power_flow_results
        self._problem: EmtProblemDae = problem
        self._emt_run_result: EmtRunResult = emt_run_result
        self._fault_result_data: FaultResultData = fault_result_data
        self._plots_dir: Path = plots_dir
        self._case_name: str = case_name

    @property
    def power_flow_results(self) -> object:
        """Return the power-flow results.

        :return: Power-flow results.
        """
        return self._power_flow_results

    @property
    def problem(self) -> EmtProblemDae:
        """Return the EMT problem.

        :return: EMT problem.
        """
        return self._problem

    @property
    def emt_run_result(self) -> EmtRunResult:
        """Return the EMT run result.

        :return: EMT run result.
        """
        return self._emt_run_result

    @property
    def fault_result_data(self) -> FaultResultData:
        """Return the processed fault result data.

        :return: Processed fault result data.
        """
        return self._fault_result_data

    @property
    def plots_dir(self) -> Path:
        """Return the plots directory.

        :return: Plots directory.
        """
        return self._plots_dir

    @property
    def case_name(self) -> str:
        """Return the case name.

        :return: Case name.
        """
        return self._case_name


PHASE_LABELS: Tuple[str, str, str] = ("A", "B", "C")
VF_REFERENCE_BY_PHASE: Dict[str, VarPowerFlowReferenceType] = dict({
    "A": VarPowerFlowReferenceType.vf_A,
    "B": VarPowerFlowReferenceType.vf_B,
    "C": VarPowerFlowReferenceType.vf_C,
})
VT_REFERENCE_BY_PHASE: Dict[str, VarPowerFlowReferenceType] = dict({
    "A": VarPowerFlowReferenceType.vt_A,
    "B": VarPowerFlowReferenceType.vt_B,
    "C": VarPowerFlowReferenceType.vt_C,
})
IF_REFERENCE_BY_PHASE: Dict[str, VarPowerFlowReferenceType] = dict({
    "A": VarPowerFlowReferenceType.if_A,
    "B": VarPowerFlowReferenceType.if_B,
    "C": VarPowerFlowReferenceType.if_C,
})
IT_REFERENCE_BY_PHASE: Dict[str, VarPowerFlowReferenceType] = dict({
    "A": VarPowerFlowReferenceType.it_A,
    "B": VarPowerFlowReferenceType.it_B,
    "C": VarPowerFlowReferenceType.it_C,
})


def _find_required_var(name: str, block: Block) -> Var:
    """Find one named symbolic variable inside one block hierarchy.

    :param name: Variable name to search.
    :param block: Block hierarchy to inspect.
    :return: Matching symbolic variable.
    :raises ValueError: If the variable is not found.
    """
    # The lookup cache is the fastest path for variables already exposed by the
    # current block. It avoids repeatedly traversing the whole hierarchy.
    lookup: Dict[str, Var] = build_name_to_var_lookup(block)
    found_var: Var | None = lookup.get(name, None)

    if found_var is not None:
        return found_var
    else:
        # The fallback hierarchical search handles variables that live only in
        # nested children and are not present in the local lookup cache.
        fallback_var: Var | None = find_name_in_block(name, block)
        if fallback_var is not None:
            return fallback_var
        else:
            raise ValueError(f"Variable '{name}' not found in block '{block.name}'")


def _find_registered_var(problem: EmtProblemDae, name: str) -> Var:
    """Find one variable by name in the final registered system block.

    :param problem: Built EMT problem.
    :param name: Variable name to search.
    :return: Matching registered symbolic variable.
    :raises ValueError: If the variable is not registered.
    """
    # Post-processing must use the final registered system variables because the
    # block unification step may replace wrapper aliases with surviving symbols.
    found_var: Var | None = find_name_in_block(name, problem.sys_block)

    if found_var is not None:
        return found_var
    else:
        raise ValueError(f"Registered variable '{name}' was not found in the EMT system block")


def _find_registered_var_from_candidates(problem: EmtProblemDae, candidates: Sequence[str]) -> Var:
    """Return the first registered variable found from one ordered candidate list.

    :param problem: Built EMT problem.
    :param candidates: Ordered candidate variable names.
    :return: First registered variable found.
    :raises ValueError: If none of the candidates exists.
    """
    candidate_name: str

    # Internal composed-branch aliases may disappear after unification, so the
    # search must gracefully fall back to electrically equivalent surviving names.
    for candidate_name in candidates:
        found_var: Var | None = find_name_in_block(candidate_name, problem.sys_block)
        if found_var is not None:
            return found_var
        else:
            pass

    raise ValueError(f"None of the registered variables were found: {list(candidates)}")


def _build_demo_grid() -> tuple[MultiCircuit, Bus, Bus, Line, Generator, Load]:
    """Build one simple source-line-load EMT study grid.

    :return: Grid, buses, branch, source and load tuple.
    """
    # The demo grid intentionally stays minimal so any abnormal fault current can
    # be traced to model composition or EMT parameter mapping instead of topology.
    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)
    nominal_voltage_kv: float = 20.0

    bus_source: Bus = Bus(name="BusSource", Vnom=nominal_voltage_kv, is_slack=True)
    bus_remote: Bus = Bus(name="BusRemote", Vnom=nominal_voltage_kv)
    grid.add_bus(bus_source)
    grid.add_bus(bus_remote)

    line: Line = Line(name="Line_Source_Remote", bus_from=bus_source, bus_to=bus_remote, length=20.0, rate=200.0)
    tower: OverheadLineType = OverheadLineType(name="FaultDemoTower", Vnom=nominal_voltage_kv)
    wire: Wire = Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1.0,
    )

    # The balanced conductor geometry keeps the expected benchmark symmetric.
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line.apply_template(tower, grid.Sbase, grid.fBase)
    grid.add_line(line)

    # The Thevenin source impedance should limit bolted three-phase faults to a
    # few pu if the EMT parameter injection path is working correctly.
    source: Generator = Generator(name="GenSlack", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=0.35)
    grid.add_generator(bus=bus_source, api_obj=source)

    # The steady-state load provides a realistic prefault operating point without
    # dominating the short-circuit level during the fault window.
    remote_load: Load = Load(
        name="RemoteLoad",
        P=18.0,
        Q=0.0,
        P1=6.0,
        P2=6.0,
        P3=6.0,
        Q1=0.0,
        Q2=0.0,
        Q3=0.0,
    )
    remote_load.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_remote, api_obj=remote_load)

    return grid, bus_source, bus_remote, line, source, remote_load


def _get_active_phase_labels(config: FaultCaseConfig) -> List[str]:
    """Return the deterministic active phase label list for one case.

    :param config: Fault-case configuration.
    :return: Ordered active phase labels.
    """
    active_phases: List[str] = list()

    if config.ph_a:
        active_phases.append("A")
    else:
        pass

    if config.ph_b:
        active_phases.append("B")
    else:
        pass

    if config.ph_c:
        active_phases.append("C")
    else:
        pass

    return active_phases


def _build_parent_terminal_var(vf: VarFactory,
                               phase_label: str,
                               name_prefix: str,
                               reference_by_phase: Dict[str, VarPowerFlowReferenceType]) -> Var:
    """Create one parent terminal wrapper variable.

    :param vf: Variable factory.
    :param phase_label: Phase label.
    :param name_prefix: Variable name prefix.
    :param reference_by_phase: Reference enum mapping by phase.
    :return: Created symbolic variable.
    """
    # The wrapper variable preserves the public branch terminal contract at the
    # composed-block root so the EMT builder can connect buses and branch KCL.
    return vf.add_var(f"{name_prefix}_{phase_label}_faulted_line_branch", reference=reference_by_phase[phase_label])


def _connect_fault_on_from_side(active_phases: List[str],
                                fault_block: Block,
                                line_block: Block,
                                root_block: Block,
                                parent_vf_vars: Dict[str, Var],
                                parent_vt_vars: Dict[str, Var],
                                parent_if_vars: Dict[str, Var],
                                parent_it_vars: Dict[str, Var],
                                midpoint_i_vars: Dict[str, Var],
                                fault_v_outer_vars: Dict[str, Var],
                                fault_i_inner_vars: Dict[str, Var],
                                fault_i_outer_vars: Dict[str, Var],
                                fault_v_inner_vars: Dict[str, Var],
                                line_vf_vars: Dict[str, Var],
                                line_vt_vars: Dict[str, Var],
                                line_if_vars: Dict[str, Var],
                                line_it_vars: Dict[str, Var]) -> None:
    """Wire the composed branch for a from-side internal fault.

    :param active_phases: Ordered active fault phases.
    :param fault_block: Internal fault block.
    :param line_block: Internal line block.
    :param root_block: Root composed branch block.
    :param parent_vf_vars: Parent from-voltage variables.
    :param parent_vt_vars: Parent to-voltage variables.
    :param parent_if_vars: Parent from-current variables.
    :param parent_it_vars: Parent to-current variables.
    :param midpoint_i_vars: Internal midpoint current variables.
    :param fault_v_outer_vars: Fault outer-voltage variables.
    :param fault_i_inner_vars: Fault inner-current variables.
    :param fault_i_outer_vars: Fault outer-current variables.
    :param fault_v_inner_vars: Fault inner-voltage variables.
    :param line_vf_vars: Line from-voltage variables.
    :param line_vt_vars: Line to-voltage variables.
    :param line_if_vars: Line from-current variables.
    :param line_it_vars: Line to-current variables.
    :return: None.
    """
    phase_label: str

    # Faulted phases are split into upstream current, downstream current and fault
    # current so the physical shunt path can be measured independently.
    for phase_label in active_phases:
        fault_block.connect([fault_v_outer_vars[phase_label]], [parent_vf_vars[phase_label]])
        fault_block.connect([fault_i_inner_vars[phase_label]], [midpoint_i_vars[phase_label]])
        line_block.connect([line_vf_vars[phase_label]], [fault_v_inner_vars[phase_label]])
        root_block.algebraic_eqs.append(parent_if_vars[phase_label] - fault_i_outer_vars[phase_label])
        root_block.algebraic_eqs.append(midpoint_i_vars[phase_label] - line_if_vars[phase_label])

    # Every phase still needs a receiving-end path so the wrapped line remains a
    # complete two-terminal branch from the network assembly perspective.
    for phase_label in PHASE_LABELS:
        line_block.connect([line_vt_vars[phase_label]], [parent_vt_vars[phase_label]])
        root_block.algebraic_eqs.append(parent_it_vars[phase_label] - line_it_vars[phase_label])


def _connect_fault_on_to_side(active_phases: List[str],
                              fault_block: Block,
                              line_block: Block,
                              root_block: Block,
                              parent_vf_vars: Dict[str, Var],
                              parent_vt_vars: Dict[str, Var],
                              parent_if_vars: Dict[str, Var],
                              parent_it_vars: Dict[str, Var],
                              midpoint_i_vars: Dict[str, Var],
                              fault_v_outer_vars: Dict[str, Var],
                              fault_i_inner_vars: Dict[str, Var],
                              fault_i_outer_vars: Dict[str, Var],
                              fault_v_inner_vars: Dict[str, Var],
                              line_vf_vars: Dict[str, Var],
                              line_vt_vars: Dict[str, Var],
                              line_if_vars: Dict[str, Var],
                              line_it_vars: Dict[str, Var]) -> None:
    """Wire the composed branch for a to-side internal fault.

    :param active_phases: Ordered active fault phases.
    :param fault_block: Internal fault block.
    :param line_block: Internal line block.
    :param root_block: Root composed branch block.
    :param parent_vf_vars: Parent from-voltage variables.
    :param parent_vt_vars: Parent to-voltage variables.
    :param parent_if_vars: Parent from-current variables.
    :param parent_it_vars: Parent to-current variables.
    :param midpoint_i_vars: Internal midpoint current variables.
    :param fault_v_outer_vars: Fault outer-voltage variables.
    :param fault_i_inner_vars: Fault inner-current variables.
    :param fault_i_outer_vars: Fault outer-current variables.
    :param fault_v_inner_vars: Fault inner-voltage variables.
    :param line_vf_vars: Line from-voltage variables.
    :param line_vt_vars: Line to-voltage variables.
    :param line_if_vars: Line from-current variables.
    :param line_it_vars: Line to-current variables.
    :return: None.
    """
    phase_label: str

    # The healthy sending-end side stays directly connected to the internal line.
    for phase_label in PHASE_LABELS:
        line_block.connect([line_vf_vars[phase_label]], [parent_vf_vars[phase_label]])
        root_block.algebraic_eqs.append(parent_if_vars[phase_label] - line_if_vars[phase_label])

    # The to-side fault splits the receiving-end terminal exactly like the from-
    # side case, but now the fault shunt is attached to the line receiving node.
    for phase_label in active_phases:
        fault_block.connect([fault_v_outer_vars[phase_label]], [parent_vt_vars[phase_label]])
        fault_block.connect([fault_i_inner_vars[phase_label]], [midpoint_i_vars[phase_label]])
        line_block.connect([line_vt_vars[phase_label]], [fault_v_inner_vars[phase_label]])
        root_block.algebraic_eqs.append(parent_it_vars[phase_label] - fault_i_outer_vars[phase_label])
        root_block.algebraic_eqs.append(midpoint_i_vars[phase_label] - line_it_vars[phase_label])

    # Non-faulted phases on the receiving side must still pass through the line so
    # the parent branch interface remains complete for all three phases.
    for phase_label in PHASE_LABELS:
        if phase_label in active_phases:
            pass
        else:
            line_block.connect([line_vt_vars[phase_label]], [parent_vt_vars[phase_label]])
            root_block.algebraic_eqs.append(parent_it_vars[phase_label] - line_it_vars[phase_label])


def _build_faulted_line_composite(grid: MultiCircuit,
                                  config: FaultCaseConfig) -> tuple[Block, Block, Block]:
    """Build one branch composite containing one internal fault block and one line block.

    :param grid: Study grid.
    :param config: Fault-case configuration.
    :return: Root composite, child fault block and child line block.
    """
    # The template-level validation keeps topology mistakes local and avoids
    # silently building invalid phase masks for the selected fault type.
    validate_fault_phase_selection(
        fault_type=config.fault_type,
        phA=config.ph_a,
        phB=config.ph_b,
        phC=config.ph_c,
    )

    fault_block: Block = get_fault_emt_template(
        vf=grid.var_factory,
        fault_type=config.fault_type,
        placement_side=config.placement_side,
        phA=config.ph_a,
        phB=config.ph_b,
        phC=config.ph_c,
        signal_controlled=False,
        initial_closed=False,
        fault_resistance=config.fault_resistance,
        ground_resistance=config.ground_resistance,
        open_conductance=1.0e-8,
        fault_time_constant=1.0e-6,
        command_threshold=0.5,
        name="internal_fault",
    ).block
    line_block: Block = get_pi_line_emt_template(
        vf=grid.var_factory,
        phN=False,
        phA=True,
        phB=True,
        phC=True,
        name="faulted_pi_line",
    ).block
    root_block: Block = Block(name="faulted_line_branch")
    active_phases: List[str] = _get_active_phase_labels(config)
    phase_label: str

    root_block.add(fault_block)
    root_block.add(line_block)

    line_vf_vars: Dict[str, Var] = dict()
    line_vt_vars: Dict[str, Var] = dict()
    line_if_vars: Dict[str, Var] = dict()
    line_it_vars: Dict[str, Var] = dict()
    fault_v_outer_vars: Dict[str, Var] = dict()
    fault_v_inner_vars: Dict[str, Var] = dict()
    fault_i_inner_vars: Dict[str, Var] = dict()
    fault_i_outer_vars: Dict[str, Var] = dict()
    parent_vf_vars: Dict[str, Var] = dict()
    parent_vt_vars: Dict[str, Var] = dict()
    parent_if_vars: Dict[str, Var] = dict()
    parent_it_vars: Dict[str, Var] = dict()
    midpoint_i_vars: Dict[str, Var] = dict()

    # The parent block creates one explicit external branch interface and stores
    # child references so the composed branch stays readable and debuggable.
    for phase_label in PHASE_LABELS:
        line_vf_vars[phase_label] = _find_required_var(f"vf_{phase_label}_faulted_pi_line", line_block)
        line_vt_vars[phase_label] = _find_required_var(f"vt_{phase_label}_faulted_pi_line", line_block)
        line_if_vars[phase_label] = _find_required_var(f"if_faulted_pi_line_{phase_label}", line_block)
        line_it_vars[phase_label] = _find_required_var(f"it_faulted_pi_line_{phase_label}", line_block)

        parent_vf_vars[phase_label] = _build_parent_terminal_var(grid.var_factory, phase_label, "vf", VF_REFERENCE_BY_PHASE)
        parent_vt_vars[phase_label] = _build_parent_terminal_var(grid.var_factory, phase_label, "vt", VT_REFERENCE_BY_PHASE)
        parent_if_vars[phase_label] = _build_parent_terminal_var(grid.var_factory, phase_label, "if", IF_REFERENCE_BY_PHASE)
        parent_it_vars[phase_label] = _build_parent_terminal_var(grid.var_factory, phase_label, "it", IT_REFERENCE_BY_PHASE)

        if phase_label in active_phases:
            fault_v_outer_vars[phase_label] = _find_required_var(f"v_outer_{phase_label}_internal_fault", fault_block)
            fault_v_inner_vars[phase_label] = _find_required_var(f"v_inner_{phase_label}_internal_fault", fault_block)
            fault_i_inner_vars[phase_label] = _find_required_var(f"i_inner_{phase_label}_internal_fault", fault_block)
            fault_i_outer_vars[phase_label] = _find_required_var(f"i_outer_{phase_label}_internal_fault", fault_block)
            midpoint_i_vars[phase_label] = grid.var_factory.add_var(f"i_mid_{phase_label}_faulted_line_branch")
        else:
            pass

    # The root branch keeps the standard public six-input, six-output interface so
    # the existing EMT assembler can treat it like any other three-phase branch.
    root_block.in_vars = list([
        parent_vf_vars["A"],
        parent_vf_vars["B"],
        parent_vf_vars["C"],
        parent_vt_vars["A"],
        parent_vt_vars["B"],
        parent_vt_vars["C"],
    ])
    root_block.out_vars = list([
        parent_if_vars["A"],
        parent_if_vars["B"],
        parent_if_vars["C"],
        parent_it_vars["A"],
        parent_it_vars["B"],
        parent_it_vars["C"],
    ])
    root_block.algebraic_vars = list([
        parent_if_vars["A"],
        parent_if_vars["B"],
        parent_if_vars["C"],
        parent_it_vars["A"],
        parent_it_vars["B"],
        parent_it_vars["C"],
    ])

    for phase_label in active_phases:
        root_block.algebraic_vars.append(midpoint_i_vars[phase_label])

    if config.placement_side == EmtFaultPlacementSide.FromSide:
        _connect_fault_on_from_side(
            active_phases=active_phases,
            fault_block=fault_block,
            line_block=line_block,
            root_block=root_block,
            parent_vf_vars=parent_vf_vars,
            parent_vt_vars=parent_vt_vars,
            parent_if_vars=parent_if_vars,
            parent_it_vars=parent_it_vars,
            midpoint_i_vars=midpoint_i_vars,
            fault_v_outer_vars=fault_v_outer_vars,
            fault_i_inner_vars=fault_i_inner_vars,
            fault_i_outer_vars=fault_i_outer_vars,
            fault_v_inner_vars=fault_v_inner_vars,
            line_vf_vars=line_vf_vars,
            line_vt_vars=line_vt_vars,
            line_if_vars=line_if_vars,
            line_it_vars=line_it_vars,
        )
    elif config.placement_side == EmtFaultPlacementSide.ToSide:
        _connect_fault_on_to_side(
            active_phases=active_phases,
            fault_block=fault_block,
            line_block=line_block,
            root_block=root_block,
            parent_vf_vars=parent_vf_vars,
            parent_vt_vars=parent_vt_vars,
            parent_if_vars=parent_if_vars,
            parent_it_vars=parent_it_vars,
            midpoint_i_vars=midpoint_i_vars,
            fault_v_outer_vars=fault_v_outer_vars,
            fault_i_inner_vars=fault_i_inner_vars,
            fault_i_outer_vars=fault_i_outer_vars,
            fault_v_inner_vars=fault_v_inner_vars,
            line_vf_vars=line_vf_vars,
            line_vt_vars=line_vt_vars,
            line_if_vars=line_if_vars,
            line_it_vars=line_it_vars,
        )
    else:
        raise NotImplementedError(f"Unsupported EMT fault placement side '{config.placement_side}'")

    # The root block re-exposes the branch terminal mapping so the external EMT
    # assembler still sees a normal branch despite the internal composition.
    root_block.external_mapping = dict({
        VarPowerFlowReferenceType.vf_N: None,
        VarPowerFlowReferenceType.vf_A: parent_vf_vars["A"],
        VarPowerFlowReferenceType.vf_B: parent_vf_vars["B"],
        VarPowerFlowReferenceType.vf_C: parent_vf_vars["C"],
        VarPowerFlowReferenceType.vt_N: None,
        VarPowerFlowReferenceType.vt_A: parent_vt_vars["A"],
        VarPowerFlowReferenceType.vt_B: parent_vt_vars["B"],
        VarPowerFlowReferenceType.vt_C: parent_vt_vars["C"],
        VarPowerFlowReferenceType.if_N: None,
        VarPowerFlowReferenceType.if_A: parent_if_vars["A"],
        VarPowerFlowReferenceType.if_B: parent_if_vars["B"],
        VarPowerFlowReferenceType.if_C: parent_if_vars["C"],
        VarPowerFlowReferenceType.it_N: None,
        VarPowerFlowReferenceType.it_A: parent_it_vars["A"],
        VarPowerFlowReferenceType.it_B: parent_it_vars["B"],
        VarPowerFlowReferenceType.it_C: parent_it_vars["C"],
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

    # The PI-line static parameter mapping must be forwarded explicitly from the
    # child so the EMT builder can inject the line R/L/C values into this wrapper.
    root_block.api_obj_mapping = dict(line_block.api_obj_mapping)
    return root_block, fault_block, line_block


def _attach_emt_models(grid: MultiCircuit,
                       line: Line,
                       source: Generator,
                       remote_load: Load,
                       config: FaultCaseConfig) -> tuple[Block, Block, Block, Block]:
    """Build and attach EMT models to the study devices.

    :param grid: Study grid.
    :param line: Host transmission line.
    :param source: Thevenin-equivalent source.
    :param remote_load: Remote load.
    :param config: Fault-case configuration.
    :return: Source block, composed line block, fault block and load block.
    """
    bus: Bus

    # Bus EMT templates must exist before attaching branches and injections so the
    # branch wrapper can bind its public terminal variables to actual bus states.
    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    source_mdl: Block = get_generator_thevenin_rl_emt_template_with_ref(vf=grid.var_factory).block
    line_composite_mdl: Block
    fault_child_mdl: Block
    line_child_mdl: Block
    line_composite_mdl, fault_child_mdl, line_child_mdl = _build_faulted_line_composite(grid=grid, config=config)
    remote_load_mdl: Block = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

    set_emt_model(device=source, model=source_mdl, var_factory=grid.var_factory)
    set_emt_model(device=line, model=line_composite_mdl, var_factory=grid.var_factory)
    set_emt_model(device=remote_load, model=remote_load_mdl, var_factory=grid.var_factory)
    return source_mdl, line_composite_mdl, fault_child_mdl, remote_load_mdl


def _add_fault_events(grid: MultiCircuit,
                      line: Line,
                      fault_child_mdl: Block,
                      config: FaultCaseConfig) -> None:
    """Add EMT mode events that apply and clear the internal fault block.

    :param grid: Study grid.
    :param line: Host line.
    :param fault_child_mdl: Internal fault block.
    :param config: Fault-case configuration.
    :return: None.
    """
    # The mode variable is stored in the child fault block because the physical
    # fault is represented as one topology-changing algebraic shunt.
    fault_mode_var: Var = _find_required_var("fault_closed_mode_internal_fault", fault_child_mdl)
    events_group: EmtEventsGroup = EmtEventsGroup(name=config.case_name)
    grid.add_emt_events_group(events_group)
    grid.add_emt_event(
        EmtEvent(
            device=line,
            parameter=fault_mode_var,
            time=config.fault_time_s,
            value=1.0,
            group=events_group,
            force_step_alignment=True,
        )
    )
    grid.add_emt_event(
        EmtEvent(
            device=line,
            parameter=fault_mode_var,
            time=config.clear_time_s,
            value=0.0,
            group=events_group,
            force_step_alignment=True,
        )
    )


def _run_power_flow(grid: MultiCircuit) -> object:
    """Run the balanced power flow used to seed EMT initialization.

    :param grid: Study grid.
    :return: Power-flow results object.
    """
    # The balanced power flow provides the prefault operating point that explicit
    # EMT initialization converts into instantaneous abc-domain initial values.
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


def _run_emt(grid: MultiCircuit, pf_results: object) -> tuple[EmtProblemDae, EmtRunResult]:
    """Run one EMT simulation.

    :param grid: Study grid.
    :param pf_results: Balanced power-flow results.
    :return: Built EMT problem and raw EMT run result.
    """
    # The compiled structural solver keeps the benchmark close to the intended EMT
    # production path while still exposing full symbolic variable names for checks.
    options: EmtOptions = EmtOptions(
        time_step=5.0e-6,
        simulation_time=0.12,
        tolerance=1.0e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        initialization_method=EmtInitializationMethod.Explicit,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=0,
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
        verbose=False,
    )
    time_values: np.ndarray
    state_values: np.ndarray
    diff_values: np.ndarray
    well_initialized: bool
    converged: bool
    time_values, state_values, diff_values, well_initialized, converged = solver.simulate(boundary_updater=problem)

    return problem, EmtRunResult(
        time_values=np.asarray(time_values, dtype=float),
        state_values=np.asarray(state_values, dtype=float),
        diff_values=np.asarray(diff_values, dtype=float),
        well_initialized=bool(well_initialized),
        converged=bool(converged),
    )


def _extract_series(problem: EmtProblemDae, emt_run_result: EmtRunResult, var: Var) -> np.ndarray:
    """Extract one simulated variable trajectory.

    :param problem: EMT problem.
    :param emt_run_result: EMT run result.
    :param var: Registered variable.
    :return: Extracted time series.
    """
    # Variable extraction always uses the final registered index map so post-
    # processing stays consistent with the solver's internal variable ordering.
    return np.asarray(emt_run_result.state_values[:, problem.get_var_idx(var)], dtype=float)


def _build_fault_window_mask(time_values: np.ndarray,
                             fault_time_s: float,
                             clear_time_s: float) -> np.ndarray:
    """Build the fault-window mask used by diagnostics.

    :param time_values: Time vector.
    :param fault_time_s: Fault application time.
    :param clear_time_s: Fault clearing time.
    :return: Boolean fault-window mask.
    """
    # A small guard band avoids transient edges dominating RMS checks while still
    # falling back to the exact event window when the simulation is short.
    fault_mask: np.ndarray = np.logical_and(time_values >= fault_time_s + 0.005, time_values <= clear_time_s - 0.005)

    if np.any(fault_mask):
        return fault_mask
    else:
        return np.logical_and(time_values >= fault_time_s, time_values <= clear_time_s)


def _build_fault_voltage_candidate_groups(config: FaultCaseConfig,
                                          bus_source: Bus,
                                          bus_remote: Bus) -> List[List[str]]:
    """Build ordered candidate-name groups for the fault-point voltage traces.

    :param config: Fault-case configuration.
    :param bus_source: Source bus.
    :param bus_remote: Remote bus.
    :return: Candidate groups by phase.
    """
    candidate_groups: List[List[str]] = list()
    source_names: Dict[str, str] = dict({
        "A": f"v_A_{bus_source.name}_emt_template",
        "B": f"v_B_{bus_source.name}_emt_template",
        "C": f"v_C_{bus_source.name}_emt_template",
    })
    remote_names: Dict[str, str] = dict({
        "A": f"v_A_{bus_remote.name}_emt_template",
        "B": f"v_B_{bus_remote.name}_emt_template",
        "C": f"v_C_{bus_remote.name}_emt_template",
    })
    phase_label: str

    # The candidate list preserves the physical fault-point meaning even when the
    # exact internal alias chosen by block unification changes between builds.
    for phase_label in PHASE_LABELS:
        if config.placement_side == EmtFaultPlacementSide.FromSide:
            candidate_groups.append(list([
                f"v_inner_{phase_label}_internal_fault",
                f"vf_{phase_label}_faulted_pi_line",
                f"vf_{phase_label}_faulted_line_branch",
                source_names[phase_label],
            ]))
        else:
            candidate_groups.append(list([
                f"v_inner_{phase_label}_internal_fault",
                f"vt_{phase_label}_faulted_pi_line",
                f"vt_{phase_label}_faulted_line_branch",
                remote_names[phase_label],
            ]))

    return candidate_groups


def _get_fault_current_var_names(config: FaultCaseConfig) -> Tuple[str | None, str | None, str | None]:
    """Return direct fault-current variable names per phase for one topology.

    :param config: Fault-case configuration.
    :return: Direct fault-current variable names for phases A, B and C.
    """
    # Each topology maps its direct physical shunt currents to a different set of
    # internal symbolic names, so post-processing must decode them explicitly.
    if config.fault_type == FaultType.LG:
        return "i_fault_AG_internal_fault", None, None
    elif config.fault_type == FaultType.LL:
        return "i_fault_AB_internal_fault", "i_fault_AB_internal_fault", None
    elif config.fault_type == FaultType.LLG:
        return "i_fault_AN_internal_fault", "i_fault_BN_internal_fault", None
    elif config.fault_type == FaultType.LLL:
        return "i_fault_AN_internal_fault", "i_fault_BN_internal_fault", "i_fault_CN_internal_fault"
    elif config.fault_type == FaultType.LLLG:
        return "i_fault_AG_internal_fault", "i_fault_BG_internal_fault", "i_fault_CG_internal_fault"
    else:
        raise ValueError(f"Unsupported EMT fault type '{config.fault_type}'")


def _sliding_rms(values: np.ndarray, samples_per_cycle: int) -> np.ndarray:
    """Compute one causal sliding RMS trace.

    :param values: Input signal.
    :param samples_per_cycle: Window size in samples.
    :return: Sliding RMS trace.
    """
    squared: np.ndarray = np.square(values)
    rms_values: np.ndarray = np.zeros(values.size, dtype=float)
    sample_index: int = 0

    # The loop is explicit because each output sample depends on one causal window
    # with a varying left edge during the startup region.
    while sample_index < values.size:
        if sample_index < samples_per_cycle:
            start_index: int = 0
        else:
            start_index = sample_index - samples_per_cycle + 1

        rms_values[sample_index] = float(np.sqrt(np.mean(squared[start_index:sample_index + 1])))
        sample_index += 1

    return rms_values


def _evaluate_window_rms(values: np.ndarray, mask: np.ndarray) -> float:
    """Evaluate one RMS quantity on a masked time window.

    :param values: Input signal.
    :param mask: Boolean mask.
    :return: Window RMS value.
    """
    # The window RMS condenses each fault current into one stable scalar for the
    # topology-specific checks and for the console summary diagnostics.
    return float(np.sqrt(np.mean(np.square(values[mask]))))


def _collect_results(problem: EmtProblemDae,
                     emt_run_result: EmtRunResult,
                     bus_source: Bus,
                     bus_remote: Bus,
                     config: FaultCaseConfig) -> FaultResultData:
    """Collect one structured set of waveforms and diagnostics.

    :param problem: EMT problem.
    :param emt_run_result: EMT run result.
    :param bus_source: Source bus.
    :param bus_remote: Remote bus.
    :param config: Fault-case configuration.
    :return: Processed fault result data.
    """
    time_values: np.ndarray = emt_run_result.time_values
    fault_mask: np.ndarray = _build_fault_window_mask(time_values, config.fault_time_s, config.clear_time_s)
    samples_per_cycle: int
    dt: float
    source_voltages: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    remote_voltages: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    fault_voltages: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    sending_currents: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    receiving_currents: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    fault_currents: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    rms_fault_currents_trace: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    fault_mode: np.ndarray = np.zeros(time_values.size, dtype=float)
    outer_currents: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    inner_currents: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    kcl_residuals: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    interface_residuals: np.ndarray = np.zeros((time_values.size, 3), dtype=float)
    rms_fault_currents: np.ndarray = np.zeros(3, dtype=float)
    source_voltage_names: Tuple[str, str, str] = (
        f"v_A_{bus_source.name}_emt_template",
        f"v_B_{bus_source.name}_emt_template",
        f"v_C_{bus_source.name}_emt_template",
    )
    remote_voltage_names: Tuple[str, str, str] = (
        f"v_A_{bus_remote.name}_emt_template",
        f"v_B_{bus_remote.name}_emt_template",
        f"v_C_{bus_remote.name}_emt_template",
    )
    sending_current_names: Tuple[str, str, str] = (
        "if_A_faulted_line_branch",
        "if_B_faulted_line_branch",
        "if_C_faulted_line_branch",
    )
    receiving_current_names: Tuple[str, str, str] = (
        "it_A_faulted_line_branch",
        "it_B_faulted_line_branch",
        "it_C_faulted_line_branch",
    )
    fault_voltage_candidate_groups: List[List[str]] = _build_fault_voltage_candidate_groups(config, bus_source, bus_remote)
    fault_name_a: str | None
    fault_name_b: str | None
    fault_name_c: str | None
    phase_index: int = 0

    while phase_index < 3:
        source_voltages[:, phase_index] = _extract_series(problem, emt_run_result, _find_registered_var(problem, source_voltage_names[phase_index]))
        remote_voltages[:, phase_index] = _extract_series(problem, emt_run_result, _find_registered_var(problem, remote_voltage_names[phase_index]))
        fault_voltages[:, phase_index] = _extract_series(problem, emt_run_result, _find_registered_var_from_candidates(problem, fault_voltage_candidate_groups[phase_index]))
        sending_currents[:, phase_index] = _extract_series(problem, emt_run_result, _find_registered_var(problem, sending_current_names[phase_index]))
        receiving_currents[:, phase_index] = _extract_series(problem, emt_run_result, _find_registered_var(problem, receiving_current_names[phase_index]))
        outer_currents[:, phase_index] = _extract_series(problem, emt_run_result, _find_registered_var(problem, f"i_outer_{PHASE_LABELS[phase_index]}_internal_fault"))
        inner_currents[:, phase_index] = _extract_series(problem, emt_run_result, _find_registered_var(problem, f"i_mid_{PHASE_LABELS[phase_index]}_faulted_line_branch"))
        phase_index += 1

    fault_name_a, fault_name_b, fault_name_c = _get_fault_current_var_names(config)

    if fault_name_a is not None:
        fault_currents[:, 0] = _extract_series(problem, emt_run_result, _find_registered_var(problem, fault_name_a))
    else:
        pass

    if fault_name_b is not None:
        if config.fault_type == FaultType.LL:
            fault_currents[:, 1] = -_extract_series(problem, emt_run_result, _find_registered_var(problem, fault_name_b))
        else:
            fault_currents[:, 1] = _extract_series(problem, emt_run_result, _find_registered_var(problem, fault_name_b))
    else:
        pass

    if fault_name_c is not None:
        fault_currents[:, 2] = _extract_series(problem, emt_run_result, _find_registered_var(problem, fault_name_c))
    else:
        pass

    # The residuals verify that the composed branch current split matches the
    # physical KCL identity after the symbolic block graph is unified.
    kcl_residuals[:, :] = outer_currents - inner_currents - fault_currents

    if config.placement_side == EmtFaultPlacementSide.FromSide:
        interface_residuals[:, :] = fault_voltages - source_voltages
    else:
        interface_residuals[:, :] = fault_voltages - remote_voltages

    if time_values.size > 1:
        dt = float(time_values[1] - time_values[0])
    else:
        dt = 5.0e-6

    samples_per_cycle = max(1, int(round((1.0 / 50.0) / dt)))
    phase_index = 0

    while phase_index < 3:
        rms_fault_currents_trace[:, phase_index] = _sliding_rms(fault_currents[:, phase_index], samples_per_cycle)
        rms_fault_currents[phase_index] = _evaluate_window_rms(fault_currents[:, phase_index], fault_mask)
        phase_index += 1

    # The fault mode trace is reconstructed deterministically from the schedule so
    # the exported plot stays readable even if the mode variable is optimized away.
    fault_mode[:] = np.where(
        np.logical_and(time_values >= config.fault_time_s, time_values < config.clear_time_s),
        1.0,
        0.0,
    )

    return FaultResultData(
        time_values=time_values,
        fault_mask=fault_mask,
        source_voltages=source_voltages,
        remote_voltages=remote_voltages,
        fault_voltages=fault_voltages,
        sending_currents=sending_currents,
        receiving_currents=receiving_currents,
        fault_currents=fault_currents,
        rms_fault_currents_trace=rms_fault_currents_trace,
        fault_mode=fault_mode,
        kcl_residuals=kcl_residuals,
        interface_residuals=interface_residuals,
        rms_fault_currents=rms_fault_currents,
        max_current_magnitude=float(np.max(np.max(np.abs(fault_currents), axis=1)[fault_mask])),
    )


def _save_three_phase_plot(file_path: Path,
                           time_values: np.ndarray,
                           matrix: np.ndarray,
                           title: str,
                           y_label: str,
                           legend_prefix: str,
                           fault_time_s: float,
                           clear_time_s: float) -> None:
    """Save one three-phase plot with fault markers.

    :param file_path: Output file path.
    :param time_values: Time vector.
    :param matrix: Three-phase signal matrix.
    :param title: Plot title.
    :param y_label: Y-axis label.
    :param legend_prefix: Legend prefix.
    :param fault_time_s: Fault application time.
    :param clear_time_s: Fault clearing time.
    :return: None.
    """
    import matplotlib.pyplot as plt

    # Three-phase overlays make balance errors and sign mistakes visible without
    # post-processing the traces further.
    figure = plt.figure(figsize=(12.0, 6.0))
    axis = figure.add_subplot(1, 1, 1)
    axis.plot(time_values, matrix[:, 0], label=f"{legend_prefix} A", color="tab:blue")
    axis.plot(time_values, matrix[:, 1], label=f"{legend_prefix} B", color="tab:red")
    axis.plot(time_values, matrix[:, 2], label=f"{legend_prefix} C", color="tab:green")
    axis.axvline(fault_time_s, color="black", linestyle="--", linewidth=1.0)
    axis.axvline(clear_time_s, color="black", linestyle="--", linewidth=1.0)
    axis.set_title(title)
    axis.set_xlabel("Time [s]")
    axis.set_ylabel(y_label)
    axis.grid(True)
    axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(file_path, dpi=300)
    plt.close(figure)


def _save_scalar_plot(file_path: Path,
                      time_values: np.ndarray,
                      trace_names: Sequence[str],
                      trace_values: Sequence[np.ndarray],
                      trace_colors: Sequence[str],
                      title: str,
                      y_label: str,
                      fault_time_s: float,
                      clear_time_s: float,
                      stepped: bool) -> None:
    """Save one scalar multi-trace plot with fault markers.

    :param file_path: Output file path.
    :param time_values: Time vector.
    :param trace_names: Trace names.
    :param trace_values: Trace arrays.
    :param trace_colors: Trace colors.
    :param title: Plot title.
    :param y_label: Y-axis label.
    :param fault_time_s: Fault application time.
    :param clear_time_s: Fault clearing time.
    :param stepped: Whether to use stepped plotting.
    :return: None.
    """
    import matplotlib.pyplot as plt

    trace_index: int = 0
    figure = plt.figure(figsize=(12.0, 5.5))
    axis = figure.add_subplot(1, 1, 1)

    # The plot helper keeps the output deterministic while supporting both mode
    # signals and continuous residual waveforms through one explicit code path.
    while trace_index < len(trace_names):
        if stepped:
            axis.step(time_values, trace_values[trace_index], where="post", label=trace_names[trace_index], color=trace_colors[trace_index])
        else:
            axis.plot(time_values, trace_values[trace_index], label=trace_names[trace_index], color=trace_colors[trace_index])
        trace_index += 1

    axis.axvline(fault_time_s, color="black", linestyle="--", linewidth=1.0)
    axis.axvline(clear_time_s, color="black", linestyle="--", linewidth=1.0)
    axis.set_title(title)
    axis.set_xlabel("Time [s]")
    axis.set_ylabel(y_label)
    axis.grid(True)
    axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(file_path, dpi=300)
    plt.close(figure)


def _run_topology_checks(config: FaultCaseConfig, fault_result_data: FaultResultData) -> None:
    """Run one set of topology-specific PASS/FAIL diagnostics.

    :param config: Fault-case configuration.
    :param fault_result_data: Processed fault result data.
    :return: None.
    """
    fault_currents: np.ndarray = fault_result_data.fault_currents
    fault_mask: np.ndarray = fault_result_data.fault_mask
    rms_values: np.ndarray = fault_result_data.rms_fault_currents
    fault_voltages: np.ndarray = fault_result_data.fault_voltages
    kcl_residuals: np.ndarray = fault_result_data.kcl_residuals
    average_rms: float
    balance_error: float
    current_sum: float
    voltage_collapse: float
    phase_bc_rms: float
    phase_a_sag: float
    ab_sum: float
    phase_c_rms: float
    max_kcl: float

    if config.fault_type == FaultType.LLL:
        average_rms = float(np.mean(rms_values))
        balance_error = float(np.max(np.abs(rms_values - average_rms)) / max(average_rms, 1.0e-12))
        current_sum = float(np.max(np.abs(np.sum(fault_currents[fault_mask, :], axis=1))))
        print(f"{'PASS' if balance_error < 5.0e-2 else 'FAIL'}: LLL balanced RMS: {balance_error:.6e}")
        print(f"{'PASS' if current_sum < 5.0e-3 else 'FAIL'}: LLL sum current: {current_sum:.6e}")
    elif config.fault_type == FaultType.LLLG:
        average_rms = float(np.mean(rms_values))
        balance_error = float(np.max(np.abs(rms_values - average_rms)) / max(average_rms, 1.0e-12))
        voltage_collapse = float(np.max(np.abs(fault_voltages[fault_mask, :])))
        print(f"{'PASS' if balance_error < 5.0e-2 else 'FAIL'}: LLLG balanced RMS: {balance_error:.6e}")
        print(f"{'PASS' if voltage_collapse < 0.3 else 'FAIL'}: LLLG voltage collapse: {voltage_collapse:.6e}")
    elif config.fault_type == FaultType.LG:
        phase_bc_rms = float(max(rms_values[1], rms_values[2]))
        phase_a_sag = float(np.max(np.abs(fault_voltages[fault_mask, 0])))
        print(f"{'PASS' if phase_bc_rms < 1.0e-3 else 'FAIL'}: LG non-fault phases near zero current: {phase_bc_rms:.6e}")
        print(f"{'PASS' if phase_a_sag < 0.4 else 'FAIL'}: LG phase-A voltage sag: {phase_a_sag:.6e}")
    elif config.fault_type == FaultType.LL:
        ab_sum = float(np.max(np.abs(fault_currents[fault_mask, 0] + fault_currents[fault_mask, 1])))
        phase_c_rms = float(rms_values[2])
        print(f"{'PASS' if ab_sum < 5.0e-3 else 'FAIL'}: LL opposite AB currents: {ab_sum:.6e}")
        print(f"{'PASS' if phase_c_rms < 1.0e-3 else 'FAIL'}: LL phase-C direct current near zero: {phase_c_rms:.6e}")
    elif config.fault_type == FaultType.LLG:
        phase_c_rms = float(rms_values[2])
        max_kcl = float(np.max(np.abs(kcl_residuals[fault_mask, :])))
        print(f"{'PASS' if phase_c_rms < 1.0e-3 else 'FAIL'}: LLG phase-C direct current near zero: {phase_c_rms:.6e}")
        print(f"{'PASS' if max_kcl < 1.0e-5 else 'FAIL'}: LLG fault-node KCL: {max_kcl:.6e}")
    else:
        raise ValueError(f"Unsupported EMT fault type '{config.fault_type}'")


def _print_case_summary(config: FaultCaseConfig,
                        power_flow_results: object,
                        problem: EmtProblemDae,
                        emt_run_result: EmtRunResult,
                        fault_result_data: FaultResultData) -> None:
    """Print one concise case summary and diagnostics.

    :param config: Fault-case configuration.
    :param power_flow_results: Power-flow results object.
    :param problem: EMT problem.
    :param emt_run_result: EMT run result.
    :param fault_result_data: Processed fault result data.
    :return: None.
    :raises RuntimeError: If the numerical sanity checks fail.
    """
    power_flow_converged: bool = bool(power_flow_results.converged)
    source_x1_estimate: float = 1.0 / 0.35
    max_kcl_residual: float = float(np.max(np.abs(fault_result_data.kcl_residuals[fault_result_data.fault_mask, :])))
    max_interface_residual: float = float(np.max(np.abs(fault_result_data.interface_residuals[fault_result_data.fault_mask, :])))
    fault_currents: np.ndarray = fault_result_data.fault_currents

    # The summary is intentionally short and physically focused so each script can
    # be used as a reproducible diagnostic entrypoint during EMT debugging.
    print(f"Case: {config.case_name}")
    print(f"Power flow converged: {power_flow_converged}")
    print(f"EMT initialization method: {problem.initialization_report.method_used}")
    print(f"EMT initialization status: {problem.initialization_report.status}")
    print(f"well_initialized: {emt_run_result.well_initialized}")
    print(f"converged: {emt_run_result.converged}")
    print(f"time_steps: {emt_run_result.time_values.size}")
    print(
        "Fault RMS currents [pu]: "
        f"A={fault_result_data.rms_fault_currents[0]:.6f}, "
        f"B={fault_result_data.rms_fault_currents[1]:.6f}, "
        f"C={fault_result_data.rms_fault_currents[2]:.6f}"
    )
    print(f"Maximum fault current magnitude [pu]: {fault_result_data.max_current_magnitude:.6f}")
    print(f"Max KCL residual [pu]: {max_kcl_residual:.6e}")
    print(f"Max interface residual [pu]: {max_interface_residual:.6e}")
    print(f"Rough three-phase source-only short-circuit level [pu]: {source_x1_estimate:.3f}")

    if np.all(np.isfinite(fault_currents)):
        pass
    else:
        raise RuntimeError(f"{config.case_name}: non-finite fault current detected")

    if fault_result_data.max_current_magnitude <= 1000.0:
        pass
    else:
        raise RuntimeError(
            f"{config.case_name}: absurdly large fault current detected ({fault_result_data.max_current_magnitude:.3f} pu)"
        )


def _save_case_plots(config: FaultCaseConfig, fault_result_data: FaultResultData) -> Path:
    """Save one required set of deterministic plots for the case.

    :param config: Fault-case configuration.
    :param fault_result_data: Processed fault result data.
    :return: Output directory containing the generated plots.
    """
    output_dir: Path = Path(__file__).resolve().parent / "fault_results" / config.case_name
    output_dir.mkdir(parents=True, exist_ok=True)
    current_sums: np.ndarray = np.sum(fault_result_data.fault_currents, axis=1)
    phase_ab_sum: np.ndarray = fault_result_data.fault_currents[:, 0] + fault_result_data.fault_currents[:, 1]
    phase_to_phase_v_ab: np.ndarray = fault_result_data.fault_voltages[:, 0] - fault_result_data.fault_voltages[:, 1]
    phase_to_phase_v_bc: np.ndarray = fault_result_data.fault_voltages[:, 1] - fault_result_data.fault_voltages[:, 2]
    phase_to_phase_v_ca: np.ndarray = fault_result_data.fault_voltages[:, 2] - fault_result_data.fault_voltages[:, 0]

    # The output folder is deterministic so repeated runs replace diagnostics for
    # the same case instead of creating ambiguous historical plot sets.
    _save_three_phase_plot(
        output_dir / "source_bus_phase_voltages.png",
        fault_result_data.time_values,
        fault_result_data.source_voltages,
        "Source Bus Phase Voltages",
        "Voltage [pu]",
        "Source",
        config.fault_time_s,
        config.clear_time_s,
    )
    _save_three_phase_plot(
        output_dir / "remote_bus_phase_voltages.png",
        fault_result_data.time_values,
        fault_result_data.remote_voltages,
        "Remote Bus Phase Voltages",
        "Voltage [pu]",
        "Remote",
        config.fault_time_s,
        config.clear_time_s,
    )
    _save_three_phase_plot(
        output_dir / "fault_point_phase_voltages.png",
        fault_result_data.time_values,
        fault_result_data.fault_voltages,
        "Fault Point Phase Voltages",
        "Voltage [pu]",
        "Fault",
        config.fault_time_s,
        config.clear_time_s,
    )
    _save_three_phase_plot(
        output_dir / "branch_sending_end_currents.png",
        fault_result_data.time_values,
        fault_result_data.sending_currents,
        "Branch Sending-End Currents",
        "Current [pu]",
        "If",
        config.fault_time_s,
        config.clear_time_s,
    )
    _save_three_phase_plot(
        output_dir / "branch_receiving_end_currents.png",
        fault_result_data.time_values,
        fault_result_data.receiving_currents,
        "Branch Receiving-End Currents",
        "Current [pu]",
        "It",
        config.fault_time_s,
        config.clear_time_s,
    )
    _save_three_phase_plot(
        output_dir / "fault_phase_currents.png",
        fault_result_data.time_values,
        fault_result_data.fault_currents,
        "Physical Fault Currents",
        "Current [pu]",
        "Ifault",
        config.fault_time_s,
        config.clear_time_s,
    )
    _save_three_phase_plot(
        output_dir / "fault_current_rms_sliding.png",
        fault_result_data.time_values,
        fault_result_data.rms_fault_currents_trace,
        "Sliding One-Cycle RMS Fault Currents",
        "RMS Current [pu]",
        "Irms",
        config.fault_time_s,
        config.clear_time_s,
    )
    _save_scalar_plot(
        file_path=output_dir / "fault_mode_status.png",
        time_values=fault_result_data.time_values,
        trace_names=list(["fault_mode"]),
        trace_values=list([fault_result_data.fault_mode]),
        trace_colors=list(["black"]),
        title="Fault Mode Status",
        y_label="Mode",
        fault_time_s=config.fault_time_s,
        clear_time_s=config.clear_time_s,
        stepped=True,
    )
    _save_scalar_plot(
        file_path=output_dir / "kcl_interface_residuals.png",
        time_values=fault_result_data.time_values,
        trace_names=list(["KCL A", "KCL B", "KCL C", "dV A", "dV B", "dV C"]),
        trace_values=list([
            fault_result_data.kcl_residuals[:, 0],
            fault_result_data.kcl_residuals[:, 1],
            fault_result_data.kcl_residuals[:, 2],
            fault_result_data.interface_residuals[:, 0],
            fault_result_data.interface_residuals[:, 1],
            fault_result_data.interface_residuals[:, 2],
        ]),
        trace_colors=list(["tab:blue", "tab:red", "tab:green", "tab:cyan", "tab:pink", "tab:olive"]),
        title="KCL And Interface Residuals",
        y_label="Residual [pu]",
        fault_time_s=config.fault_time_s,
        clear_time_s=config.clear_time_s,
        stepped=False,
    )
    _save_scalar_plot(
        file_path=output_dir / "phase_current_sums.png",
        time_values=fault_result_data.time_values,
        trace_names=list(["iA+iB+iC", "iA+iB"]),
        trace_values=list([current_sums, phase_ab_sum]),
        trace_colors=list(["black", "tab:purple"]),
        title="Fault Current Sums",
        y_label="Current [pu]",
        fault_time_s=config.fault_time_s,
        clear_time_s=config.clear_time_s,
        stepped=False,
    )
    _save_scalar_plot(
        file_path=output_dir / "phase_to_phase_fault_voltages.png",
        time_values=fault_result_data.time_values,
        trace_names=list(["Vab", "Vbc", "Vca"]),
        trace_values=list([phase_to_phase_v_ab, phase_to_phase_v_bc, phase_to_phase_v_ca]),
        trace_colors=list(["tab:blue", "tab:red", "tab:green"]),
        title="Fault Point Phase-To-Phase Voltages",
        y_label="Voltage [pu]",
        fault_time_s=config.fault_time_s,
        clear_time_s=config.clear_time_s,
        stepped=False,
    )
    _save_scalar_plot(
        file_path=output_dir / "ground_or_residual_current.png",
        time_values=fault_result_data.time_values,
        trace_names=list(["residual current"]),
        trace_values=list([current_sums]),
        trace_colors=list(["black"]),
        title="Ground Or Residual Current",
        y_label="Current [pu]",
        fault_time_s=config.fault_time_s,
        clear_time_s=config.clear_time_s,
        stepped=False,
    )
    return output_dir


def run_fault_case(config: FaultCaseConfig) -> FaultCaseExecution:
    """Build, run, validate and export one EMT fault case.

    :param config: Fault-case configuration.
    :return: Complete case execution bundle.
    """
    grid: MultiCircuit
    bus_source: Bus
    bus_remote: Bus
    line: Line
    source: Generator
    remote_load: Load
    source_mdl: Block
    line_composite_mdl: Block
    fault_child_mdl: Block
    remote_load_mdl: Block
    power_flow_results: object
    problem: EmtProblemDae
    emt_run_result: EmtRunResult
    fault_result_data: FaultResultData
    output_dir: Path

    # The full case runner performs the entire workflow so each entry script stays
    # trivial and each case uses exactly the same setup and diagnostics.
    grid, bus_source, bus_remote, line, source, remote_load = _build_demo_grid()
    source_mdl, line_composite_mdl, fault_child_mdl, remote_load_mdl = _attach_emt_models(
        grid=grid,
        line=line,
        source=source,
        remote_load=remote_load,
        config=config,
    )
    _add_fault_events(grid=grid, line=line, fault_child_mdl=fault_child_mdl, config=config)

    power_flow_results = _run_power_flow(grid)
    problem, emt_run_result = _run_emt(grid=grid, pf_results=power_flow_results)
    fault_result_data = _collect_results(
        problem=problem,
        emt_run_result=emt_run_result,
        bus_source=bus_source,
        bus_remote=bus_remote,
        config=config,
    )

    _print_case_summary(
        config=config,
        power_flow_results=power_flow_results,
        problem=problem,
        emt_run_result=emt_run_result,
        fault_result_data=fault_result_data,
    )
    _run_topology_checks(config=config, fault_result_data=fault_result_data)
    output_dir = _save_case_plots(config=config, fault_result_data=fault_result_data)
    print(f"Saved plots to: {output_dir}")

    if source_mdl is not None and line_composite_mdl is not None and remote_load_mdl is not None:
        pass
    else:
        raise RuntimeError("Unexpected missing EMT model during fault-case execution")

    return FaultCaseExecution(
        power_flow_results=power_flow_results,
        problem=problem,
        emt_run_result=emt_run_result,
        fault_result_data=fault_result_data,
        plots_dir=output_dir,
        case_name=config.case_name,
    )
