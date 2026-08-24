from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Tuple

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_editor_support import collect_block_runtime_event_parameters
from VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.dynamic_block_preparation import prepare_block_for_editing
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_library import (
    DynamicEditorLibrary,
    MeasurementBlockDescriptor,
)
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_utilities import create_generic_block
import VeraGrid.Gui.DynamicModelEditor.dynamic_editor_graphics as graph
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.overhead_line_type import OverheadLineType
from VeraGridEngine.Devices.Branches.wire import Wire
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.emt_results import EmtResults
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.Simulations.PowerFlow3ph.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_results import RmsResults
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import (
    get_complete_generator_template_rms,
    get_governor_rms,
)
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.Rms.international_standards.bbsex1 import build_bbsex1_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    RmsPhysicalMeasurementPoint,
    RmsPhysicalMeterKind,
    RmsTerminalSide,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Var, symbolic_to_string
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model, set_rms_model
from VeraGridEngine.enumerations import BlockType, BranchImpedanceMode, DeviceType, DynamicIntegrationMethod, DynamicSimulationMode, DynEditorGraphicsModes, EmtInitializationMethod, EmtSolverTypes, FileType, RmsInitializationMethod, ShuntConnectionType, SolverType, VarPowerFlowReferenceType


def _collect_block_signature(block: Block) -> Dict[str, Any]:
    """
    Collect one structural signature from a symbolic block tree.

    :param block: Root symbolic block to inspect.
    :type block: Block
    :return: Comparable structural signature.
    :rtype: Dict[str, Any]
    """
    signature: Dict[str, Any] = dict()
    all_blocks: List[Block] = block.get_all_blocks()

    signature["block_count"] = len(all_blocks)
    signature["state_var_names"] = [var.name for blk in all_blocks for var in blk.state_vars]
    signature["algebraic_var_names"] = [var.name for blk in all_blocks for var in blk.algebraic_vars]
    signature["diff_var_names"] = [var.name for blk in all_blocks for var in blk.diff_vars]
    signature["parameter_names"] = [var.name for blk in all_blocks for var in blk.parameters.keys()]
    signature["event_names"] = [var.name for blk in all_blocks for var in blk.event_dict.keys()]
    signature["root_in_refs"] = [var.ref for var in block.in_vars]
    signature["root_out_refs"] = [var.ref for var in block.out_vars]
    signature["root_mapping_keys"] = list(block.external_mapping.keys())
    return signature


def _collect_block_semantic_signature(block: Block) -> Dict[str, Any]:
    """
    Collect one order-insensitive semantic signature from a symbolic block tree.

    :param block: Root symbolic block to inspect.
    :type block: Block
    :return: Comparable semantic signature.
    :rtype: Dict[str, Any]
    """
    signature: Dict[str, Any] = dict()
    all_blocks: List[Block] = block.get_all_blocks()

    signature["state_var_names"] = sorted([var.name for blk in all_blocks for var in blk.state_vars])
    signature["algebraic_var_names"] = sorted([var.name for blk in all_blocks for var in blk.algebraic_vars])
    signature["diff_var_names"] = sorted([var.name for blk in all_blocks for var in blk.diff_vars])
    signature["parameter_names"] = sorted([var.name for blk in all_blocks for var in blk.parameters.keys()])
    signature["event_names"] = sorted([var.name for blk in all_blocks for var in blk.event_dict.keys()])
    signature["root_in_refs"] = sorted([str(var.ref) for var in block.in_vars])
    signature["root_out_refs"] = sorted([str(var.ref) for var in block.out_vars])
    signature["root_mapping_keys"] = sorted([str(key) for key in block.external_mapping.keys()])
    return signature


def _build_pf_options() -> PowerFlowOptions:
    """
    Build one common power-flow option set.

    :return: Configured power-flow options.
    :rtype: PowerFlowOptions
    """
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
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


def _build_emt_options() -> EmtOptions:
    """
    Build one EMT option set for equivalence checks.

    :return: Configured EMT options.
    :rtype: EmtOptions
    """
    return EmtOptions(
        time_step=5e-6,
        simulation_time=2e-4,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=EmtInitializationMethod.PseudoTransient,
        verbose=0,
    )


def _build_rms_options() -> RmsOptions:
    """
    Build one RMS option set for equivalence checks.

    :return: Configured RMS options.
    :rtype: RmsOptions
    """
    return RmsOptions(
        time_step=0.001,
        simulation_time=0.02,
        tolerance=1e-6,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=1000,
        verbose=0,
    )


def _build_two_bus_emt_grid() -> Tuple[MultiCircuit, Generator, Line, Load]:
    """
    Build one two-bus EMT benchmark grid.

    :return: Grid and the three dynamic devices.
    :rtype: Tuple[MultiCircuit, Generator, Line, Load]
    """
    grid: MultiCircuit = MultiCircuit(Sbase=2.0, fbase=50.0)
    vnom: float = 10.0

    bus0: Bus = Bus(name="Bus0", Vnom=vnom, is_slack=True)
    bus1: Bus = Bus(name="Bus1", Vnom=vnom)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line0: Line = Line(name="line0", bus_from=bus0, bus_to=bus1, length=10.0, rate=900.0)
    tower: OverheadLineType = OverheadLineType(name="Tower", Vnom=vnom)
    wire: Wire = Wire(name="Panther 30/7 ACSR", diameter=21.0, diameter_internal=9.0, is_tube=True, r=0.1363, max_current=1)
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line0.apply_template(tower, grid.Sbase, grid.fBase)

    r_ph: float = 100.0
    v_ph: float = vnom / (3.0 ** 0.5)
    p_ph: float = (v_ph ** 2) / r_ph
    q_ph: float = 0.0
    load: Load = Load(name="load", P1=p_ph, P2=p_ph, P3=p_ph, Q1=q_ph, Q2=q_ph, Q3=q_ph)
    load.conn = ShuntConnectionType.GroundedStar

    gen0: Generator = Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq=50.0, r1=0.001, x1=1.7)

    grid.add_line(line0)
    grid.add_generator(bus=bus0, api_obj=gen0)
    grid.add_load(bus=bus1, api_obj=load)

    return grid, gen0, line0, load


def _build_two_bus_rms_grid() -> Tuple[MultiCircuit, Generator, Any, Load]:
    """
    Build one two-bus RMS benchmark grid.

    :return: Grid and the three dynamic devices.
    :rtype: Tuple[MultiCircuit, Generator, Any, Load]
    """
    grid: MultiCircuit = MultiCircuit(Sbase=100.0, fbase=50.0)

    bus0: Bus = Bus(name="Bus0", Vnom=10.0, is_slack=True)
    bus1: Bus = Bus(name="Bus1", Vnom=10.0)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    bus_obj: Bus
    for bus_obj in grid.buses:
        initialize_bus_rms(bus_obj, vf=grid.var_factory)

    line0 = Line(name="line 0-2", bus_from=bus0, bus_to=bus1, r=0.029585, x=0.071005, b=0.03, rate=900.0)
    grid.add_line(line0)

    load: Load = Load(P=9.999999, Q=0.999999)
    grid.add_load(bus=bus1, api_obj=load)

    gen0: Generator = Generator(name="Gen0", P=10.0, vset=1.0, Snom=900.0, x1=0.86138701, r1=0.3, freq=50.0)
    grid.add_generator(bus=bus0, api_obj=gen0)

    return grid, gen0, line0, load


def _add_rms_load_step_event(grid: MultiCircuit, load: Load) -> None:
    """Add one GUI-selectable active-power step to an RMS test grid.

    :param grid: Canonical circuit that owns the event collection.
    :param load: Load whose assigned model exposes the runtime parameter.
    :return: None.
    """
    load_model: Block | None = load.rms_model
    assert isinstance(load_model, Block)
    runtime_parameters: List[Var]
    mode_parameter_uids: set[int]
    runtime_parameters, mode_parameter_uids = collect_block_runtime_event_parameters(block=load_model)
    active_power_parameter: Var | None = None
    runtime_parameter: Var

    # Select exactly what the live GUI event editor offers, rather than
    # reaching into an implementation-only parameter collection.
    for runtime_parameter in runtime_parameters:
        if runtime_parameter.name == "Pl0":
            assert active_power_parameter is None
            assert runtime_parameter.uid not in mode_parameter_uids
            active_power_parameter = runtime_parameter
        else:
            pass
    assert active_power_parameter is not None

    event_group: RmsEventsGroup = RmsEventsGroup(
        idtag="real-gui-script-rms-event-group",
        active=True,
        name="Real GUI-script RMS load step",
    )
    event: RmsEvent = RmsEvent(
        idtag="real-gui-script-rms-load-step",
        name="Real GUI-script RMS load step",
        device=load,
        parameter=active_power_parameter,
        time=0.01,
        value=-0.095,
        group=event_group,
    )
    grid.add_rms_events_group(event_group)
    grid.add_rms_event(event)


def _load_nuactis_rms_grid(fixture_name: str) -> MultiCircuit:
    """Load a tracked Nuactis DGS through the production import path.

    :param fixture_name: File name of the tracked DGS fixture.
    :return: Canonical circuit with imported RMS templates assigned by FID.
    """
    fixture_path: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "grids"
        / "DGS"
        / fixture_name
    )
    file_open: FileOpen = FileOpen(
        file_name=str(fixture_path),
        options=FileOpenOptions(
            file_type=FileType.DGS,
            dgs_use_dynamic_information=True,
            dgs_dynamic_simulation_mode=DynamicSimulationMode.RMS,
        ),
    )
    imported_grid: MultiCircuit | None = file_open.open()
    assert imported_grid is not None
    assert file_open.logger.error_count() == 0
    return imported_grid


def _add_nuactis_parameter_event(
        grid: MultiCircuit,
        vsc: VSC,
        event_group: RmsEventsGroup,
        runtime_parameter_name: str,
        event_value: float,
        event_time: float,
        event_idtag: str,
        event_name: str,
) -> Var:
    """Add one GUI-selectable controller-parameter event to Nuactis.

    :param grid: Canonical Nuactis circuit that owns the event.
    :param vsc: Converter whose imported controller is perturbed.
    :param event_group: Scenario group that owns the event.
    :param runtime_parameter_name: Exact imported runtime parameter name.
    :param event_value: Absolute parameter value applied at the event.
    :param event_time: Simulation time at which the value is applied.
    :param event_idtag: Stable identifier for the event.
    :param event_name: Human-readable event name.
    :return: Exact typed runtime parameter targeted by the event.
    """
    vsc_model: Block | None = vsc.rms_model
    assert isinstance(vsc_model, Block)
    runtime_parameters: List[Var]
    mode_parameter_uids: set[int]
    runtime_parameters, mode_parameter_uids = collect_block_runtime_event_parameters(
        block=vsc_model,
    )
    selected_parameter: Var | None = None
    runtime_parameter: Var

    # Select the same typed parameter exposed in the GUI event editor rather
    # than addressing a hidden solver coordinate or matching a display label.
    for runtime_parameter in runtime_parameters:
        if runtime_parameter.name == runtime_parameter_name:
            assert selected_parameter is None
            assert runtime_parameter.uid not in mode_parameter_uids
            selected_parameter = runtime_parameter
        else:
            pass
    assert selected_parameter is not None, "\n".join(
        parameter.name for parameter in runtime_parameters
    )

    event: RmsEvent = RmsEvent(
        idtag=event_idtag,
        name=event_name,
        device=vsc,
        parameter=selected_parameter,
        time=event_time,
        value=event_value,
        group=event_group,
    )
    grid.add_rms_event(event)
    return selected_parameter


def _collect_rms_variable_values(
        problem: RmsProblemDae,
        results: RmsResults,
        variable_names: List[str],
) -> np.ndarray:
    """Collect named RMS variables without depending on solver column order.

    :param problem: Compiled RMS problem that owns the variable indices.
    :param results: RMS trajectory containing every compiled variable.
    :param variable_names: Exact global symbolic names to collect.
    :return: Values arranged as time, requested variable, and event scenario.
    """
    time_count: int = results.values.shape[0]
    variable_count: int = len(variable_names)
    scenario_count: int = results.values.shape[2]
    selected_values: np.ndarray = np.empty(
        (time_count, variable_count, scenario_count),
        dtype=float,
    )
    requested_index: int

    # Resolve names explicitly because GUI persistence may reorder otherwise
    # equivalent symbolic blocks without changing their physical semantics.
    for requested_index in range(variable_count):
        variable_name: str = variable_names[requested_index]
        variable_uid: int | None = problem.vars_glob_name2uid.get(
            variable_name,
            None,
        )
        if variable_uid is not None:
            variable_result_index: int | None = problem.uid2idx_vars.get(
                variable_uid,
                None,
            )
            if variable_result_index is not None:
                selected_values[:, requested_index, :] = results.values[
                    :,
                    variable_result_index,
                    :,
                ]
            else:
                raise AssertionError(
                    f"RMS result index is missing for variable {variable_name}."
                )
        else:
            raise AssertionError(
                f"Compiled RMS variable is missing: {variable_name}."
            )
    return selected_values


def _run_nuactis_short_rms(
        grid: MultiCircuit,
) -> Tuple[PowerFlowResults, RmsResults, RmsProblemDae]:
    """Run PF and a short RMS trajectory for one Nuactis circuit.

    :param grid: Imported circuit to initialize and integrate.
    :return: Converged power-flow results, RMS results, and compiled problem.
    """
    power_flow_driver: PowerFlowDriver = PowerFlowDriver(
        grid=grid,
        options=_build_pf_options(),
    )
    power_flow_driver.run()
    power_flow_results: PowerFlowResults = power_flow_driver.results
    assert power_flow_results.converged

    rms_options: RmsOptions = RmsOptions(
        time_step=0.001,
        simulation_time=0.01,
        tolerance=1e-9,
        integration_method=DynamicIntegrationMethod.DaeBackEuler,
        initialization_method=RmsInitializationMethod.Explicit,
        use_init_values=False,
        max_iter=100,
        verbose=0,
    )
    rms_driver: RmsSimulationDriver = RmsSimulationDriver(
        grid=grid,
        options=rms_options,
        pf_results=power_flow_results,
    )
    rms_driver.run()
    assert rms_driver.results is not None
    assert rms_driver.problem is not None
    return power_flow_results, rms_driver.results, rms_driver.problem


def _run_emt_power_flow(grid: MultiCircuit) -> Any:
    """
    Run one EMT benchmark three-phase power flow.

    :param grid: Network model.
    :type grid: MultiCircuit
    :return: Three-phase power-flow results.
    :rtype: Any
    """
    power_flow: PowerFlowDriver3Ph = PowerFlowDriver3Ph(grid, _build_pf_options())
    power_flow.run()
    return power_flow.results


def _run_emt_driver(grid: MultiCircuit, pf_results_3ph: Any) -> EmtResults:
    """
    Run one EMT simulation.

    :param grid: Network model.
    :type grid: MultiCircuit
    :param pf_results_3ph: Three-phase power-flow results.
    :type pf_results_3ph: Any
    :return: EMT results.
    :rtype: EmtResults
    """
    driver: EmtSimulationDriver = EmtSimulationDriver(grid=grid, options=_build_emt_options(), pf_results_3ph=pf_results_3ph, pf_results=None)
    driver.run()
    if driver.results is None:
        raise AssertionError("EMT driver did not produce results.")
    else:
        return driver.results


def _run_rms_driver(grid: MultiCircuit) -> Tuple[RmsResults, RmsProblemDae]:
    """
    Run one RMS simulation.

    :param grid: Network model.
    :type grid: MultiCircuit
    :return: RMS results and built problem.
    :rtype: Tuple[RmsResults, RmsProblemDae]
    """
    pf_results: Any = MultiCircuit.power_flow(grid, options=_build_pf_options()) if False else None
    pf_results = __import__("VeraGridEngine.api", fromlist=["power_flow"]).power_flow(grid, options=_build_pf_options())
    driver: RmsSimulationDriver = RmsSimulationDriver(grid=grid, options=_build_rms_options(), pf_results=pf_results)
    driver.run()
    if driver.results is None:
        raise AssertionError("RMS driver did not produce results.")
    else:
        problem: RmsProblemDae = RmsProblemDae(grid=grid, options=_build_rms_options(), pf_results=pf_results)
        return driver.results, problem


def _build_gui_editor(qt_app: QtWidgets.QApplication,
                      grid: MultiCircuit,
                      api_object: Any,
                      mode: DynamicSimulationMode,
                      root_block: Block) -> DynamicBlockEditorGUI:
    """
    Build one real dynamic block editor instance for one device.

    :param qt_app: Shared Qt application.
    :type qt_app: QtWidgets.QApplication
    :param grid: Owning circuit.
    :type grid: MultiCircuit
    :param api_object: Edited device.
    :type api_object: Any
    :param mode: Dynamic editor mode.
    :type mode: DynamicSimulationMode
    :param root_block: Root block to edit.
    :type root_block: Block
    :return: Live editor widget.
    :rtype: DynamicBlockEditorGUI
    """
    _app: QtWidgets.QApplication = qt_app
    editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=grid.var_factory,
        api_object=api_object,
        circuit=grid,
        current_theme=DynEditorGraphicsModes.LIGHT,
        mode=mode,
        templates_list=list(),
        is_root_editor=True,
        modal=False,
        workspace_embedded=False,
        root_block=root_block,
        current_block=root_block,
    )
    editor.show()
    _app.processEvents()
    return editor


def _get_connection_path_segments(
        connection: graph.ConnectionItem,
) -> List[tuple[float, float, float, float]]:
    """Extract ordered line segments from one orthogonal graphics path.

    :param connection: Rendered connection whose path is inspected.
    :return: Ordered ``x1, y1, x2, y2`` segment coordinates.
    """
    path: QtGui.QPainterPath = connection.path()
    segment_count: int = max(0, path.elementCount() - 1)
    segments: List[tuple[float, float, float, float]] = [
        (0.0, 0.0, 0.0, 0.0) for unused_index in range(segment_count)
    ]
    segment_index: int
    first_element: QtGui.QPainterPath.Element
    second_element: QtGui.QPainterPath.Element
    for segment_index in range(segment_count):
        first_element = path.elementAt(segment_index)
        second_element = path.elementAt(segment_index + 1)
        segments[segment_index] = (
            first_element.x,
            first_element.y,
            second_element.x,
            second_element.y,
        )
    return segments


def _assert_connection_paths_are_orthogonal_and_perpendicular(
        connections: List[graph.ConnectionItem],
) -> None:
    """Assert non-degenerate orthogonal routes with horizontal port access.

    Every visible input and output port is located on a vertical block side.
    Its adjacent cable segment must therefore be horizontal; a vertical terminal
    segment creates the detached arrowheads and non-perpendicular entries seen in
    the interactive editor.

    :param connections: Complete transient connection collection.
    :return: None.
    """
    connection: graph.ConnectionItem
    for connection in connections:
        segments: List[tuple[float, float, float, float]] = (
            _get_connection_path_segments(connection)
        )
        assert len(segments) > 0
        segment: tuple[float, float, float, float]
        for segment in segments:
            horizontal: bool = abs(segment[1] - segment[3]) <= 1.0e-6
            vertical: bool = abs(segment[0] - segment[2]) <= 1.0e-6
            positive_length: bool = (
                abs(segment[0] - segment[2]) > 1.0e-6
                or abs(segment[1] - segment[3]) > 1.0e-6
            )
            assert positive_length
            assert horizontal or vertical
        first_segment: tuple[float, float, float, float] = segments[0]
        last_segment: tuple[float, float, float, float] = segments[-1]
        source_owner: QtWidgets.QGraphicsItem | None = (
            connection.source_port.parentItem()
        )
        target_owner: QtWidgets.QGraphicsItem | None = (
            connection.target_port.parentItem()
        )
        block_to_block: bool = (
            isinstance(source_owner, (graph.BlockItem, graph.GenericBlockItem))
            and isinstance(target_owner, (graph.BlockItem, graph.GenericBlockItem))
        )
        if isinstance(connection.source_port, graph.BranchingItem):
            pass
        else:
            assert abs(first_segment[1] - first_segment[3]) <= 1.0e-6
            if block_to_block:
                assert abs(first_segment[0] - first_segment[2]) >= 32.0 - 1.0e-6, (
                    connection.source_port.subsystem.name,
                    connection.source_port.base_var.name,
                    connection.target_port.subsystem.name,
                    connection.target_port.base_var.name,
                    first_segment,
                )
            else:
                pass
        if isinstance(connection.target_port, graph.BranchingItem):
            pass
        else:
            assert abs(last_segment[1] - last_segment[3]) <= 1.0e-6, (
                connection.source_port.subsystem.name,
                connection.source_port.base_var.name,
                connection.target_port.subsystem.name,
                connection.target_port.base_var.name,
                last_segment,
            )
            if block_to_block:
                assert abs(last_segment[0] - last_segment[2]) >= 32.0 - 1.0e-6, (
                    connection.source_port.subsystem.name,
                    connection.source_port.base_var.name,
                    connection.target_port.subsystem.name,
                    connection.target_port.base_var.name,
                    last_segment,
                )
            else:
                pass


def _get_block_item_visual_rect(item: QtWidgets.QGraphicsItem) -> QtCore.QRectF:
    """Return one block rectangle including every visible child label.

    :param item: Block or transient signal tag represented in the scene.
    :return: Axis-aligned scene rectangle containing body and child labels.
    """
    local_visual_rect: QtCore.QRectF = item.boundingRect().united(
        item.childrenBoundingRect()
    )
    mapped_visual_rect: QtCore.QRectF | QtGui.QPolygonF = item.mapRectToScene(
        local_visual_rect
    )
    if isinstance(mapped_visual_rect, QtCore.QRectF):
        return mapped_visual_rect
    else:
        return mapped_visual_rect.boundingRect()


def _get_block_item_body_rect(item: QtWidgets.QGraphicsItem) -> QtCore.QRectF:
    """Return one projected item's body without child labels.

    :param item: Block or transient signal tag represented in the scene.
    :return: Body-only scene rectangle used for endpoint-owner collisions.
    """
    if isinstance(item, QtWidgets.QGraphicsRectItem):
        local_body_rect: QtCore.QRectF = item.rect()
    elif isinstance(item, QtWidgets.QGraphicsEllipseItem):
        local_body_rect = item.rect()
    elif isinstance(item, QtWidgets.QGraphicsPolygonItem):
        local_body_rect = item.polygon().boundingRect()
    else:
        local_body_rect = item.boundingRect()
    mapped_body_rect: QtCore.QRectF | QtGui.QPolygonF = item.mapRectToScene(
        local_body_rect
    )
    if isinstance(mapped_body_rect, QtCore.QRectF):
        return mapped_body_rect
    else:
        return mapped_body_rect.boundingRect()


def _assert_block_items_do_not_overlap(
        items: List[QtWidgets.QGraphicsItem],
) -> None:
    """Assert that block bodies and their labels occupy disjoint areas.

    :param items: Complete collection of projected blocks and signal tags.
    :return: None.
    """
    left_index: int
    right_index: int
    left_rect: QtCore.QRectF
    right_rect: QtCore.QRectF
    overlap_rect: QtCore.QRectF
    for left_index in range(len(items)):
        left_rect = _get_block_item_visual_rect(items[left_index])
        for right_index in range(left_index + 1, len(items)):
            right_rect = _get_block_item_visual_rect(items[right_index])
            overlap_rect = left_rect.intersected(right_rect)
            assert overlap_rect.width() <= 1e-6 or overlap_rect.height() <= 1e-6, (
                items[left_index].name,
                items[right_index].name,
                left_rect,
                right_rect,
                overlap_rect,
            )


def _segment_overlaps_rect_or_border(
        segment: tuple[float, float, float, float],
        rect: QtCore.QRectF,
        tolerance: float = 1e-6,
) -> bool:
    """Return whether one orthogonal wire overlaps a rectangle or its border.

    :param segment: Segment represented as ``x1, y1, x2, y2``.
    :param rect: Block, tag, or visible-label scene rectangle.
    :param tolerance: Numerical geometry tolerance.
    :return: Whether positive segment length occupies its body or border.
    """
    horizontal: bool = abs(segment[1] - segment[3]) <= tolerance
    if horizontal:
        crosses_vertical_span: bool = (
            segment[1] >= rect.top() - tolerance
            and segment[1] <= rect.bottom() + tolerance
        )
        overlap_length: float = (
            min(max(segment[0], segment[2]), rect.right())
            - max(min(segment[0], segment[2]), rect.left())
        )
    else:
        crosses_vertical_span = (
            segment[0] >= rect.left() - tolerance
            and segment[0] <= rect.right() + tolerance
        )
        overlap_length = (
            min(max(segment[1], segment[3]), rect.bottom())
            - max(min(segment[1], segment[3]), rect.top())
        )
    return crosses_vertical_span and overlap_length > tolerance


def _assert_connections_avoid_visual_items(
        connections: List[graph.ConnectionItem],
        items: List[QtWidgets.QGraphicsItem],
) -> None:
    """Assert that cables avoid every body and all unrelated labels.

    :param connections: Complete transient connection collection.
    :param items: Blocks and signal tags including visible child text.
    :return: None.
    """
    connection: graph.ConnectionItem
    visual_item: QtWidgets.QGraphicsItem
    segment: tuple[float, float, float, float]
    for connection in connections:
        source_owner: QtWidgets.QGraphicsItem | None = connection.source_port.parentItem()
        target_owner: QtWidgets.QGraphicsItem | None = connection.target_port.parentItem()
        for visual_item in items:
            if visual_item is source_owner or visual_item is target_owner:
                visual_rect: QtCore.QRectF = _get_block_item_body_rect(
                    visual_item
                )
            else:
                visual_rect = _get_block_item_visual_rect(visual_item)
            for segment in _get_connection_path_segments(connection):
                assert not _segment_overlaps_rect_or_border(
                    segment=segment,
                    rect=visual_rect,
                ), (
                    connection.source_port.subsystem.name,
                    connection.target_port.subsystem.name,
                    visual_item.name,
                )


def _orthogonal_segments_collide(
        left_segment: tuple[float, float, float, float],
        right_segment: tuple[float, float, float, float],
        tolerance: float = 1e-6,
) -> bool:
    """Return whether two orthogonal segments cross or overlap internally.

    Endpoint-only contact is allowed because it represents one wire reaching
    its own port. Interior crossings and positive-length collinear overlaps are
    forbidden by the projected DGS canvas contract.

    :param left_segment: First ``x1, y1, x2, y2`` segment.
    :param right_segment: Second ``x1, y1, x2, y2`` segment.
    :param tolerance: Coordinate comparison tolerance.
    :return: ``True`` for an interior crossing or collinear overlap.
    """
    left_horizontal: bool = abs(left_segment[1] - left_segment[3]) <= tolerance
    right_horizontal: bool = abs(right_segment[1] - right_segment[3]) <= tolerance
    if left_horizontal and right_horizontal:
        same_axis: bool = abs(left_segment[1] - right_segment[1]) <= tolerance
        overlap_length: float = (
                min(max(left_segment[0], left_segment[2]), max(right_segment[0], right_segment[2]))
                - max(min(left_segment[0], left_segment[2]), min(right_segment[0], right_segment[2]))
        )
        return same_axis and overlap_length > tolerance
    elif not left_horizontal and not right_horizontal:
        same_axis = abs(left_segment[0] - right_segment[0]) <= tolerance
        overlap_length = (
                min(max(left_segment[1], left_segment[3]), max(right_segment[1], right_segment[3]))
                - max(min(left_segment[1], left_segment[3]), min(right_segment[1], right_segment[3]))
        )
        return same_axis and overlap_length > tolerance
    else:
        pass

    if left_horizontal:
        horizontal_segment: tuple[float, float, float, float] = left_segment
        vertical_segment: tuple[float, float, float, float] = right_segment
    else:
        horizontal_segment = right_segment
        vertical_segment = left_segment

    crossing_x: float = vertical_segment[0]
    crossing_y: float = horizontal_segment[1]
    inside_horizontal: bool = (
            crossing_x > min(horizontal_segment[0], horizontal_segment[2]) + tolerance
            and crossing_x < max(horizontal_segment[0], horizontal_segment[2]) - tolerance
    )
    inside_vertical: bool = (
            crossing_y > min(vertical_segment[1], vertical_segment[3]) + tolerance
            and crossing_y < max(vertical_segment[1], vertical_segment[3]) - tolerance
    )
    return inside_horizontal and inside_vertical


def _assert_connection_paths_do_not_collide(
        connections: List[graph.ConnectionItem],
) -> None:
    """Assert that independently rendered wires never cross or overlap.

    :param connections: Complete transient connection collection.
    :return: None.
    """
    left_index: int
    right_index: int
    left_segments: List[tuple[float, float, float, float]]
    right_segments: List[tuple[float, float, float, float]]
    left_segment: tuple[float, float, float, float]
    right_segment: tuple[float, float, float, float]
    for left_index in range(len(connections)):
        left_segments = _get_connection_path_segments(connections[left_index])
        for right_index in range(left_index + 1, len(connections)):
            right_segments = _get_connection_path_segments(connections[right_index])
            for left_segment in left_segments:
                for right_segment in right_segments:
                        assert not _orthogonal_segments_collide(
                            left_segment=left_segment,
                            right_segment=right_segment,
                        ), (
                            connections[left_index].source_port.subsystem.name,
                            connections[left_index].target_port.subsystem.name,
                            connections[right_index].source_port.subsystem.name,
                            connections[right_index].target_port.subsystem.name,
                        )


def _assert_nuactis_vsc_projection(
        editor: DynamicBlockEditorGUI,
        expected_protected_count: int,
) -> None:
    """Validate the semantic VeraGrid projection of one imported VSC model.

    :param editor: Live root editor showing the converter model.
    :param expected_protected_count: Connected external interface ovals expected.
    :return: None.
    """
    generic_items: List[graph.GenericBlockItem] = list(
        scene_item for scene_item in editor.scene.items()
        if isinstance(scene_item, graph.GenericBlockItem)
    )
    physical_items: List[graph.GenericBlockItem] = list(
        item for item in generic_items
        if item.visual_role is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
    )
    measurement_items: List[graph.GenericBlockItem] = list(
        item for item in generic_items
        if item.visual_role is graph.DynamicBlockVisualRole.MEASUREMENT
    )
    control_items: List[graph.GenericBlockItem] = list(
        item for item in generic_items
        if item.visual_role is graph.DynamicBlockVisualRole.CONTROL
    )
    protected_items: List[graph.ProtectedConnectionBlockItem] = list(
        scene_item for scene_item in editor.scene.items()
        if isinstance(scene_item, graph.ProtectedConnectionBlockItem)
    )
    scene_connections: List[graph.ConnectionItem] = list(
        scene_item for scene_item in editor.scene.items()
        if isinstance(scene_item, graph.ConnectionItem)
    )
    paired_items: List[graph.PairedItem] = list(
        scene_item for scene_item in editor.scene.items()
        if isinstance(scene_item, graph.PairedItem)
    )
    direct_connections: List[graph.ConnectionItem] = list(
        connection for connection in scene_connections
        if not isinstance(connection.source_port.parentItem(), graph.PairedItem)
        and not isinstance(connection.target_port.parentItem(), graph.PairedItem)
    )
    projected_visual_items: List[QtWidgets.QGraphicsItem] = list(
        scene_item for scene_item in editor.scene.items()
        if isinstance(scene_item, (
            graph.BlockItem,
            graph.GenericBlockItem,
            graph.PairedItem,
        ))
    )

    assert len(physical_items) == 1
    assert len(measurement_items) == 3
    assert len(control_items) > 0
    assert len(protected_items) == expected_protected_count
    assert all(
        item.subsys is not editor._physical_root_control_container
        for item in generic_items
    )
    measurement_item: graph.GenericBlockItem
    for measurement_item in measurement_items:
        measurement_point: RmsPhysicalMeasurementPoint | None = (
            measurement_item.subsys.dynamic_model_contract.rms_physical_measurement_point
        )
        assert measurement_point is not None
        assert measurement_item.name.startswith("VeraGrid ")
        assert "powerfactory" not in measurement_item.name.lower()
        assert all(
            "powerfactory" not in output_port.base_var.name.lower()
            for output_port in measurement_item.outputs
        )
        selected_output_uids: set[int] = set(
            measurement_point.get_output_var_uids()
        )
        selected_output_ports: List[graph.PortItem] = list(
            output_port
            for output_port in measurement_item.outputs
            if output_port.base_var.uid in selected_output_uids
        )
        assert measurement_point.get_output_signal_names() == tuple(
            output_port.base_var.name for output_port in selected_output_ports
        )
        output_port: graph.PortItem
        for output_port in selected_output_ports:
            output_uid: int = output_port.base_var.uid
            assert output_port.base_var in measurement_item.subsys.algebraic_vars
            assert output_port.base_var in measurement_item.subsys.init_eqs
            assert len(measurement_item.subsys.algebraic_vars) == len(
                measurement_item.subsys.algebraic_eqs
            )
            residual_owner_indices: List[int] = list(
                algebraic_index
                for algebraic_index in range(
                    len(measurement_item.subsys.algebraic_vars)
                )
                if measurement_item.subsys.algebraic_vars[algebraic_index].uid
                == output_uid
            )
            assert len(residual_owner_indices) == 1
            owned_residual: Expr = measurement_item.subsys.algebraic_eqs[
                residual_owner_indices[0]
            ]
            assert output_uid in set(
                residual_var.uid for residual_var in owned_residual.get_vars()
            )

    physical_item: graph.GenericBlockItem = physical_items[0]
    assert physical_item.name == "VeraGrid VSC physical template"
    assert editor.resolve_block_for_properties(physical_item.subsys) is editor.main_block
    assert len(physical_item.subsys.algebraic_eqs) == 0
    assert len(editor.main_block.algebraic_eqs) == 9
    assert len(editor.main_block.init_eqs) == 6
    editor.request_open_block_properties(physical_item.subsys)
    assert editor._block_properties_dialogue is not None
    assert editor._block_properties_dialogue.is_dae_model_page_active()
    editor.close_block_properties_dock()
    assert {port.base_var.name for port in physical_item.inputs}.issuperset(
        set(("Pmd", "Pmq"))
    )
    assert {port.base_var.name for port in physical_item.outputs} == set(
        ("id", "iq", "uDC")
    )
    assert all(
        port.connections is not None and len(port.connections) > 0
        for port in physical_item.inputs
    ), [
        port.base_var.name
        for port in physical_item.inputs
        if port.connections is None or len(port.connections) == 0
    ]
    assert all(
        port.connections is not None and len(port.connections) > 0
        for port in physical_item.outputs
    ), [
        port.base_var.name
        for port in physical_item.outputs
        if port.connections is None or len(port.connections) == 0
    ]

    assert measurement_items[0].brush().color() == (
        editor.colors_palet.MEASUREMENT_BLOCK_FILL
    )
    assert control_items[0].brush().color() == editor.colors_palet.BLOCK_FILL
    assert physical_item.brush().color() == (
        editor.colors_palet.DEVICE_TEMPLATE_BLOCK_FILL
    )
    assert len(scene_connections) > 0
    assert len(direct_connections) > 0
    assert all(
        paired_item.paired_items is not None and len(paired_item.paired_items) > 0
        for paired_item in paired_items
    )
    assert all(
        paired_item.name == paired_item.subsys.name.split(" ", 1)[1]
        for paired_item in paired_items
    )
    paired_item: graph.PairedItem
    paired_port_collection: List[graph.PortItem]
    paired_port: graph.PortItem
    for paired_item in paired_items:
        for paired_port_collection in (paired_item.inputs, paired_item.outputs):
            for paired_port in paired_port_collection:
                assert paired_port.connections is not None, (
                    paired_item.name,
                    paired_port.base_var.name,
                )
                assert len(paired_port.connections) > 0, (
                    paired_item.name,
                    paired_port.base_var.name,
                )
    assert len(paired_items) < 2 * len(scene_connections)
    _assert_block_items_do_not_overlap(projected_visual_items)
    _assert_connection_paths_do_not_collide(scene_connections)
    _assert_connection_paths_are_orthogonal_and_perpendicular(scene_connections)
    _assert_connections_avoid_visual_items(
        connections=scene_connections,
        items=projected_visual_items,
    )
    assert len(editor.diagram.con_data) > 0
    assert len(scene_connections) > len(editor.diagram.con_data)
    assert all(connection.diagram is None for connection in scene_connections)
    assert all(not connection.path().isEmpty() for connection in scene_connections)
    assert all(
        connection.source_port.scene() is editor.scene
        and connection.target_port.scene() is editor.scene
        for connection in scene_connections
    )
    assert all(
        abs(connection.path().elementAt(0).x - connection.source_port.scenePos().x()) <= 1e-6
        and abs(connection.path().elementAt(0).y - connection.source_port.scenePos().y()) <= 1e-6
        and abs(
            connection.path().elementAt(connection.path().elementCount() - 1).x
            - connection.target_port.scenePos().x()
        ) <= 1e-6
        and abs(
            connection.path().elementAt(connection.path().elementCount() - 1).y
            - connection.target_port.scenePos().y()
        ) <= 1e-6
        for connection in scene_connections
    )
    assert all(
        connection.from_uid in editor.diagram.node_data
        and connection.to_uid in editor.diagram.node_data
        for connection in editor.diagram.con_data.values()
    )
    assert all(
        any(
            port.connections is not None and len(port.connections) > 0
            for port in protected_item.inputs
        )
        or any(
            port.connections is not None and len(port.connections) > 0
            for port in protected_item.outputs
        )
        for protected_item in protected_items
    )


def _run_balanced_pf(grid: MultiCircuit) -> Any:
    power_flow: PowerFlowDriver = PowerFlowDriver(grid, _build_pf_options())
    power_flow.run()
    return power_flow.results


def test_generator_template_selector_and_library_use_typed_categories(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Separate assignable devices, controls and measurements by contract.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit
    generator: Generator
    line: Line
    load: Load
    grid, generator, line, load = _build_two_bus_rms_grid()
    del line
    del load

    physical_template: RmsModelTemplate = get_genrow_rms_template(
        grid.var_factory,
        name="Generator basic",
    )
    governor_template: RmsModelTemplate = get_governor_rms(
        grid.var_factory,
        name="Governor",
    )
    bbsex1_template: RmsModelTemplate = build_bbsex1_template(
        grid.var_factory,
        name="BBSEX1",
    )

    measurement_output: Var = grid.var_factory.add_var("Vm_local")
    measurement_block: Block = Block(
        name="Local voltage measurement",
        out_vars=list((measurement_output,)),
    )
    measurement_block.dynamic_model_contract.rms_physical_measurement_point = (
        RmsPhysicalMeasurementPoint(
            source_fid="local-voltage-meter",
            target_fid=generator.bus.idtag,
            terminal_side=RmsTerminalSide.BUS,
            meter_kind=RmsPhysicalMeterKind.VOLTAGE,
            output_signal_names=(measurement_output.name,),
            output_var_uids=(measurement_output.uid,),
        )
    )
    measurement_template: RmsModelTemplate = RmsModelTemplate(
        name="Local voltage measurement"
    )
    measurement_template.tpe = DeviceType.GeneratorDevice
    measurement_template.block = measurement_block

    grid.add_rms_model(physical_template)
    grid.add_rms_model(governor_template)
    grid.add_rms_model(bbsex1_template)
    grid.add_rms_model(measurement_template)

    template_device: object
    delegate_lists: Dict[DeviceType, List[object]]
    template_device, delegate_lists = grid.get_dictionary_of_lists(
        elm_type=DeviceType.GeneratorDevice
    )
    del template_device
    assignable_templates: List[object] | None = delegate_lists.get(
        DeviceType.RmsModelTemplateDevice,
        None,
    )
    assert assignable_templates == list((physical_template,))

    editor_templates: List[RmsModelTemplate] = grid.get_rms_templates_for_editor(
        DeviceType.GeneratorDevice
    )
    assert set(editor_templates) == set((
        physical_template,
        governor_template,
        bbsex1_template,
        measurement_template,
    ))

    template_block_identities_before: Tuple[Tuple[int, ...], ...] = tuple(
        tuple(id(nested_block) for nested_block in template.block.get_all_blocks())
        for template in editor_templates
    )
    factory_var_identities_before: Tuple[Tuple[int, int], ...] = tuple(
        (var_uid, id(var))
        for var_uid, var in grid.var_factory.get_vars_dict().items()
    )
    factory_diff_var_identities_before: Tuple[Tuple[int, int], ...] = tuple(
        (var_uid, id(var))
        for var_uid, var in grid.var_factory.get_diff_var_dict().items()
    )
    catalog_start_seconds: float = perf_counter()
    library: DynamicEditorLibrary = DynamicEditorLibrary(
        api_object=generator,
        mode=DynamicSimulationMode.RMS,
        templates_list=editor_templates,
    )
    catalog_elapsed_seconds: float = perf_counter() - catalog_start_seconds
    assert catalog_elapsed_seconds <= 2.0, catalog_elapsed_seconds
    template_block_identities_after: Tuple[Tuple[int, ...], ...] = tuple(
        tuple(id(nested_block) for nested_block in template.block.get_all_blocks())
        for template in editor_templates
    )
    factory_var_identities_after: Tuple[Tuple[int, int], ...] = tuple(
        (var_uid, id(var))
        for var_uid, var in grid.var_factory.get_vars_dict().items()
    )
    factory_diff_var_identities_after: Tuple[Tuple[int, int], ...] = tuple(
        (var_uid, id(var))
        for var_uid, var in grid.var_factory.get_diff_var_dict().items()
    )
    assert template_block_identities_after == template_block_identities_before
    assert factory_var_identities_after == factory_var_identities_before
    assert factory_diff_var_identities_after == factory_diff_var_identities_before
    assert library.tree_structure.get("Templates", None) is None
    physical_leaves: object | None = library.tree_structure.get(
        "Physical devices/templates", None
    )
    component_leaves: object | None = library.tree_structure.get(
        "Controls/components", None
    )
    measurement_leaves: object | None = library.tree_structure.get(
        "Measurements", None
    )
    assert isinstance(physical_leaves, list)
    assert isinstance(component_leaves, list)
    assert isinstance(measurement_leaves, list)
    assert physical_template in [leaf.payload for leaf in physical_leaves]
    assert governor_template in [leaf.payload for leaf in component_leaves]
    assert bbsex1_template in [leaf.payload for leaf in component_leaves]
    assert measurement_template not in [leaf.payload for leaf in physical_leaves]
    assert measurement_template not in [leaf.payload for leaf in component_leaves]
    assert len(measurement_leaves) == 1
    assert isinstance(measurement_leaves[0].payload, MeasurementBlockDescriptor)

    editor_root: Block = Block(
        name="Generator composite model",
        external_mapping=dict(physical_template.block.external_mapping),
    )
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=generator,
        mode=DynamicSimulationMode.RMS,
        root_block=editor_root,
    )
    try:
        physical_item: graph.BlockItem | graph.GenericBlockItem | None = (
            editor.create_template_block_item(physical_template, 0.0, 0.0)
        )
        component_item: graph.BlockItem | graph.GenericBlockItem | None = (
            editor.create_template_block_item(bbsex1_template, 300.0, 0.0)
        )
        measurement_item: graph.GenericBlockItem | None = (
            editor.create_measurements_block_item(
                descriptor=measurement_leaves[0].payload,
                x_pos=600.0,
                y_pos=0.0,
            )
        )
        second_measurement_item: graph.GenericBlockItem | None = (
            editor.create_measurements_block_item(
                descriptor=measurement_leaves[0].payload,
                x_pos=900.0,
                y_pos=0.0,
            )
        )
        assert isinstance(physical_item, graph.GenericBlockItem)
        assert isinstance(component_item, graph.GenericBlockItem)
        assert isinstance(measurement_item, graph.GenericBlockItem)
        assert isinstance(second_measurement_item, graph.GenericBlockItem)
        assert physical_item.visual_role is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
        assert component_item.visual_role is graph.DynamicBlockVisualRole.CONTROL
        assert measurement_item.visual_role is graph.DynamicBlockVisualRole.MEASUREMENT
        assert second_measurement_item.visual_role is graph.DynamicBlockVisualRole.MEASUREMENT
        assert physical_item.brush().color() == editor.colors_palet.DEVICE_TEMPLATE_BLOCK_FILL
        assert component_item.brush().color() == editor.colors_palet.BLOCK_FILL
        assert measurement_item.brush().color() == editor.colors_palet.MEASUREMENT_BLOCK_FILL
        assert len(measurement_item.subsys.children) >= 2
        measurement_child: Block
        for measurement_child in measurement_item.subsys.children:
            assert (
                measurement_child.dynamic_model_contract.rms_physical_measurement_point
                is not None
            )
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        library.library_model.deleteLater()


def test_generator_basic_assignment_opens_as_connected_physical_device(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Open the real native Generator basic template as a physical device.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit
    generator: Generator
    line: Line
    load: Load
    grid, generator, line, load = _build_two_bus_rms_grid()
    del line
    del load
    generator.rms_template = get_genrow_rms_template(
        grid.var_factory,
        name="Generator basic",
    )

    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=generator,
        mode=DynamicSimulationMode.RMS,
        root_block=generator.rms_model,
    )
    try:
        generic_items: List[graph.GenericBlockItem] = list(
            item for item in editor.scene.items()
            if isinstance(item, graph.GenericBlockItem)
        )
        physical_items: List[graph.GenericBlockItem] = list(
            item for item in generic_items
            if item.visual_role is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
        )
        measurement_items: List[graph.GenericBlockItem] = list(
            item for item in generic_items
            if item.visual_role is graph.DynamicBlockVisualRole.MEASUREMENT
        )
        assert len(physical_items) == 1
        assert len(measurement_items) == 1
        physical_item: graph.GenericBlockItem = physical_items[0]
        assert all(
            port.connections is not None and len(port.connections) > 0
            for port in physical_item.inputs
        )
        assert editor.resolve_block_for_properties(physical_item.subsys) is (
            physical_item.subsys
        )
        editor.request_open_block_properties(physical_item.subsys)
        assert editor._block_properties_dialogue is not None
        assert editor._block_properties_dialogue.is_dae_model_page_active()
        editor.close_block_properties_dock()
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()


def test_gui_editor_apply_changes_matches_scripting_for_emt(qt_app: QtWidgets.QApplication) -> None:
    """
    Compare the real EMT editor save path against EMT scripting assembly.

    :param qt_app: Shared Qt application fixture.
    :type qt_app: QtWidgets.QApplication
    :return: None.
    :rtype: None
    """
    script_grid: MultiCircuit
    script_gen: Generator
    script_line: Line
    script_load: Load
    script_grid, script_gen, script_line, script_load = _build_two_bus_emt_grid()

    bus_obj: Bus
    for bus_obj in script_grid.buses:
        get_bus_emt_template(script_grid, bus_obj)

    set_emt_model(device=script_gen, model=get_generator_thevenin_rl_emt_template_with_ref(vf=script_grid.var_factory).block, var_factory=script_grid.var_factory)
    set_emt_model(device=script_line, model=get_pi_line_emt_template(vf=script_grid.var_factory, phN=False, phA=True, phB=True, phC=True).block, var_factory=script_grid.var_factory)
    set_emt_model(device=script_load, model=get_load_ZIP_emt_template(vf=script_grid.var_factory, phA=True, phB=True, phC=True).block, var_factory=script_grid.var_factory)

    gui_grid: MultiCircuit
    gui_gen: Generator
    gui_line: Line
    gui_load: Load
    gui_grid, gui_gen, gui_line, gui_load = _build_two_bus_emt_grid()

    gui_gen.emt_template = get_generator_thevenin_rl_emt_template_with_ref(vf=gui_grid.var_factory)
    gui_line.emt_template = get_pi_line_emt_template(vf=gui_grid.var_factory, phN=False, phA=True, phB=True, phC=True)
    gui_load.emt_template = get_load_ZIP_emt_template(vf=gui_grid.var_factory, phA=True, phB=True, phC=True)

    gen_editor: DynamicBlockEditorGUI = _build_gui_editor(qt_app=qt_app, grid=gui_grid, api_object=gui_gen, mode=DynamicSimulationMode.EMT, root_block=gui_gen.emt_model)
    line_editor: DynamicBlockEditorGUI = _build_gui_editor(qt_app=qt_app, grid=gui_grid, api_object=gui_line, mode=DynamicSimulationMode.EMT, root_block=gui_line.emt_model)
    load_editor: DynamicBlockEditorGUI = _build_gui_editor(qt_app=qt_app, grid=gui_grid, api_object=gui_load, mode=DynamicSimulationMode.EMT, root_block=gui_load.emt_model)

    gen_editor.apply_changes()
    line_editor.apply_changes()
    load_editor.apply_changes()
    qt_app.processEvents()

    assert _collect_block_semantic_signature(gui_gen.emt_model) == _collect_block_semantic_signature(script_gen.emt_model)
    assert _collect_block_semantic_signature(gui_line.emt_model) == _collect_block_semantic_signature(script_line.emt_model)
    assert _collect_block_semantic_signature(gui_load.emt_model) == _collect_block_semantic_signature(script_load.emt_model)

    script_pf_results_3ph: Any = _run_emt_power_flow(script_grid)
    gui_pf_results_3ph: Any = _run_emt_power_flow(gui_grid)
    script_problem = __import__("VeraGridEngine.Simulations.EMT.problems.emt_problem_dae", fromlist=["EmtProblemDae"]).EmtProblemDae(grid=script_grid, options=_build_emt_options(), pf_results_3ph=script_pf_results_3ph, pf_results=None)
    gui_problem = __import__("VeraGridEngine.Simulations.EMT.problems.emt_problem_dae", fromlist=["EmtProblemDae"]).EmtProblemDae(grid=gui_grid, options=_build_emt_options(), pf_results_3ph=gui_pf_results_3ph, pf_results=None)
    assert script_problem.get_states_number() == gui_problem.get_states_number()
    assert script_problem.get_algebraic_var_number() == gui_problem.get_algebraic_var_number()
    script_results: EmtResults = _run_emt_driver(script_grid, script_pf_results_3ph)
    gui_results: EmtResults = _run_emt_driver(gui_grid, gui_pf_results_3ph)

    assert list(script_results.variable_array) == list(gui_results.variable_array)
    assert np.allclose(script_results.values, gui_results.values, rtol=1e-8, atol=1e-8)
    assert np.allclose(script_results.diff_values, gui_results.diff_values, rtol=1e-8, atol=1e-8)


def test_gui_editor_apply_changes_matches_scripting_for_emt_with_balanced_pf(
        qt_app: QtWidgets.QApplication) -> None:
    script_grid: MultiCircuit
    script_gen: Generator
    script_line: Line
    script_load: Load
    script_grid, script_gen, script_line, script_load = _build_two_bus_emt_grid()

    bus_obj: Bus
    for bus_obj in script_grid.buses:
        get_bus_emt_template(script_grid, bus_obj)

    set_emt_model(device=script_gen, model=get_generator_thevenin_rl_emt_template_with_ref(vf=script_grid.var_factory).block, var_factory=script_grid.var_factory)
    set_emt_model(device=script_line, model=get_pi_line_emt_template(vf=script_grid.var_factory, phN=False, phA=True, phB=True, phC=True).block, var_factory=script_grid.var_factory)
    set_emt_model(device=script_load, model=get_load_ZIP_emt_template(vf=script_grid.var_factory, phA=True, phB=True, phC=True).block, var_factory=script_grid.var_factory)

    gui_grid: MultiCircuit
    gui_gen: Generator
    gui_line: Line
    gui_load: Load
    gui_grid, gui_gen, gui_line, gui_load = _build_two_bus_emt_grid()

    gui_gen.emt_template = get_generator_thevenin_rl_emt_template_with_ref(vf=gui_grid.var_factory)
    gui_line.emt_template = get_pi_line_emt_template(vf=gui_grid.var_factory, phN=False, phA=True, phB=True, phC=True)
    gui_load.emt_template = get_load_ZIP_emt_template(vf=gui_grid.var_factory, phA=True, phB=True, phC=True)

    gen_editor: DynamicBlockEditorGUI = _build_gui_editor(qt_app=qt_app, grid=gui_grid, api_object=gui_gen, mode=DynamicSimulationMode.EMT, root_block=gui_gen.emt_model)
    line_editor: DynamicBlockEditorGUI = _build_gui_editor(qt_app=qt_app, grid=gui_grid, api_object=gui_line, mode=DynamicSimulationMode.EMT, root_block=gui_line.emt_model)
    load_editor: DynamicBlockEditorGUI = _build_gui_editor(qt_app=qt_app, grid=gui_grid, api_object=gui_load, mode=DynamicSimulationMode.EMT, root_block=gui_load.emt_model)

    gen_editor.apply_changes()
    line_editor.apply_changes()
    load_editor.apply_changes()
    qt_app.processEvents()

    script_pf_results: Any = _run_balanced_pf(script_grid)
    gui_pf_results: Any = _run_balanced_pf(gui_grid)

    script_problem: EmtProblemDae = EmtProblemDae(grid=script_grid, options=_build_emt_options(), pf_results=script_pf_results, pf_results_3ph=None)
    gui_problem: EmtProblemDae = EmtProblemDae(grid=gui_grid, options=_build_emt_options(), pf_results=gui_pf_results, pf_results_3ph=None)

    assert script_problem.initialization_report is not None
    assert gui_problem.initialization_report is not None
    assert script_problem.initialization_report.status == gui_problem.initialization_report.status
    assert script_problem.get_states_number() == gui_problem.get_states_number()
    assert script_problem.get_algebraic_var_number() == gui_problem.get_algebraic_var_number()

    script_driver: EmtSimulationDriver = EmtSimulationDriver(grid=script_grid, options=_build_emt_options(), pf_results_3ph=None, pf_results=script_pf_results)
    gui_driver: EmtSimulationDriver = EmtSimulationDriver(grid=gui_grid, options=_build_emt_options(), pf_results_3ph=None, pf_results=gui_pf_results)
    script_driver.run()
    gui_driver.run()

    assert script_driver.results is not None
    assert gui_driver.results is not None
    assert np.array_equal(script_driver.results.converged, gui_driver.results.converged)
    assert np.array_equal(script_driver.results.well_initialized, gui_driver.results.well_initialized)
    assert np.allclose(script_driver.results.values, gui_driver.results.values, rtol=1e-8, atol=1e-8)


def test_native_emt_template_assignment_matches_set_emt_model_with_balanced_pf() -> None:
    script_grid: MultiCircuit
    script_gen: Generator
    script_line: Line
    script_load: Load
    script_grid, script_gen, script_line, script_load = _build_two_bus_emt_grid()

    bus_obj: Bus
    for bus_obj in script_grid.buses:
        get_bus_emt_template(script_grid, bus_obj)

    set_emt_model(device=script_gen, model=get_generator_thevenin_rl_emt_template_with_ref(vf=script_grid.var_factory).block, var_factory=script_grid.var_factory)
    set_emt_model(device=script_line, model=get_pi_line_emt_template(vf=script_grid.var_factory, phN=False, phA=True, phB=True, phC=True).block, var_factory=script_grid.var_factory)
    set_emt_model(device=script_load, model=get_load_ZIP_emt_template(vf=script_grid.var_factory, phA=True, phB=True, phC=True).block, var_factory=script_grid.var_factory)

    template_grid: MultiCircuit
    template_gen: Generator
    template_line: Line
    template_load: Load
    template_grid, template_gen, template_line, template_load = _build_two_bus_emt_grid()

    for bus_obj in template_grid.buses:
        get_bus_emt_template(template_grid, bus_obj)

    template_gen.emt_template = get_generator_thevenin_rl_emt_template_with_ref(vf=template_grid.var_factory)
    template_line.emt_template = get_pi_line_emt_template(vf=template_grid.var_factory, phN=False, phA=True, phB=True, phC=True)
    template_load.emt_template = get_load_ZIP_emt_template(vf=template_grid.var_factory, phA=True, phB=True, phC=True)

    assert _collect_block_semantic_signature(template_gen.emt_model) == _collect_block_semantic_signature(script_gen.emt_model)
    assert _collect_block_semantic_signature(template_line.emt_model) == _collect_block_semantic_signature(script_line.emt_model)
    assert _collect_block_semantic_signature(template_load.emt_model) == _collect_block_semantic_signature(script_load.emt_model)

    script_pf_results: Any = _run_balanced_pf(script_grid)
    template_pf_results: Any = _run_balanced_pf(template_grid)

    script_driver: EmtSimulationDriver = EmtSimulationDriver(grid=script_grid, options=_build_emt_options(), pf_results_3ph=None, pf_results=script_pf_results)
    template_driver: EmtSimulationDriver = EmtSimulationDriver(grid=template_grid, options=_build_emt_options(), pf_results_3ph=None, pf_results=template_pf_results)
    script_driver.run()
    template_driver.run()

    assert script_driver.results is not None
    assert template_driver.results is not None
    assert np.array_equal(script_driver.results.converged, template_driver.results.converged)
    assert np.array_equal(script_driver.results.well_initialized, template_driver.results.well_initialized)
    assert np.allclose(script_driver.results.values, template_driver.results.values, rtol=1e-8, atol=1e-8)


def test_gui_editor_apply_changes_matches_scripting_for_rms(qt_app: QtWidgets.QApplication) -> None:
    """
    Compare the real RMS editor save path against RMS scripting assembly.

    :param qt_app: Shared Qt application fixture.
    :type qt_app: QtWidgets.QApplication
    :return: None.
    :rtype: None
    """
    script_grid: MultiCircuit
    script_gen: Generator
    script_line: Any
    script_load: Load
    script_grid, script_gen, script_line, script_load = _build_two_bus_rms_grid()

    set_rms_model(device=script_gen, model=get_complete_generator_template_rms(script_grid.var_factory).block, var_factory=script_grid.var_factory)
    set_rms_model(device=script_line, model=get_line_rms_template(script_grid.var_factory).block, var_factory=script_grid.var_factory)
    set_rms_model(device=script_load, model=get_load_rms_template(script_grid.var_factory).block, var_factory=script_grid.var_factory)

    gui_grid: MultiCircuit
    gui_gen: Generator
    gui_line: Any
    gui_load: Load
    gui_grid, gui_gen, gui_line, gui_load = _build_two_bus_rms_grid()

    gui_gen.rms_template = get_complete_generator_template_rms(gui_grid.var_factory)
    gui_line.rms_template = get_line_rms_template(gui_grid.var_factory)
    gui_load.rms_template = get_load_rms_template(gui_grid.var_factory)

    gen_editor: DynamicBlockEditorGUI = _build_gui_editor(qt_app=qt_app, grid=gui_grid, api_object=gui_gen, mode=DynamicSimulationMode.RMS, root_block=gui_gen.rms_model)
    line_editor: DynamicBlockEditorGUI = _build_gui_editor(qt_app=qt_app, grid=gui_grid, api_object=gui_line, mode=DynamicSimulationMode.RMS, root_block=gui_line.rms_model)
    load_editor: DynamicBlockEditorGUI = _build_gui_editor(qt_app=qt_app, grid=gui_grid, api_object=gui_load, mode=DynamicSimulationMode.RMS, root_block=gui_load.rms_model)

    gen_editor.apply_changes()
    line_editor.apply_changes()
    load_editor.apply_changes()
    qt_app.processEvents()

    assert _collect_block_semantic_signature(gui_gen.rms_model) == _collect_block_semantic_signature(script_gen.rms_model)
    assert _collect_block_semantic_signature(gui_line.rms_model) == _collect_block_semantic_signature(script_line.rms_model)
    assert _collect_block_semantic_signature(gui_load.rms_model) == _collect_block_semantic_signature(script_load.rms_model)

    # Make both drivers integrate the same non-trivial trajectory after the
    # real GUI editor has rebuilt and persisted each dynamic block.
    _add_rms_load_step_event(grid=script_grid, load=script_load)
    _add_rms_load_step_event(grid=gui_grid, load=gui_load)

    script_results: RmsResults
    gui_results: RmsResults
    script_problem: RmsProblemDae
    gui_problem: RmsProblemDae
    script_results, script_problem = _run_rms_driver(script_grid)
    gui_results, gui_problem = _run_rms_driver(gui_grid)

    assert script_problem.get_states_number() == gui_problem.get_states_number()
    assert script_problem.get_algebraic_var_number() == gui_problem.get_algebraic_var_number()
    assert list(script_results.variable_array) == list(gui_results.variable_array)
    assert script_results.values.shape[2] == 1
    assert script_results.values.shape == gui_results.values.shape
    assert np.array_equal(script_results.rms_events_group_names, gui_results.rms_events_group_names)
    assert np.array_equal(script_results.rms_events_group_idtags, gui_results.rms_events_group_idtags)
    assert np.array_equal(script_results.has_event_group_results, gui_results.has_event_group_results)
    assert np.all(script_results.has_event_group_results)
    assert np.array_equal(script_results.well_initialized, gui_results.well_initialized)
    assert np.array_equal(script_results.converged, gui_results.converged)
    assert np.all(script_results.well_initialized)
    assert np.all(script_results.converged)
    assert script_results.time_array.equals(gui_results.time_array)
    assert not np.allclose(
        script_results.values[0, :, 0],
        script_results.values[-1, :, 0],
        rtol=1e-10,
        atol=1e-10,
    )
    assert np.allclose(script_results.values, gui_results.values, rtol=1e-8, atol=1e-8)


def test_nuactis_v1_gui_editor_matches_scripting_pf_and_rms(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Keep Nuactis V1 invariant after opening and saving its VSCs in the GUI.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    script_grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    gui_grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    script_vsc_devices: List[VSC] = script_grid.get_vsc()
    gui_vsc_devices: List[VSC] = gui_grid.get_vsc()
    assert len(script_vsc_devices) == 2
    assert len(gui_vsc_devices) == len(script_vsc_devices)

    open_editors: List[DynamicBlockEditorGUI] = list()
    converter_index: int
    try:
        # Exercise the actual editor reconstruction and persistence path for
        # each imported converter while the scripting copy stays untouched.
        for converter_index in range(len(gui_vsc_devices)):
            script_vsc: VSC = script_vsc_devices[converter_index]
            gui_vsc: VSC = gui_vsc_devices[converter_index]
            assert gui_vsc.idtag == script_vsc.idtag
            assert isinstance(gui_vsc.rms_model, Block)
            assert isinstance(script_vsc.rms_model, Block)

            projection_start_seconds: float = perf_counter()
            editor: DynamicBlockEditorGUI = _build_gui_editor(
                qt_app=qt_app,
                grid=gui_grid,
                api_object=gui_vsc,
                mode=DynamicSimulationMode.RMS,
                root_block=gui_vsc.rms_model,
            )
            projection_elapsed_seconds: float = (
                perf_counter() - projection_start_seconds
            )
            assert projection_elapsed_seconds <= 4.0, projection_elapsed_seconds
            open_editors.append(editor)
            _assert_nuactis_vsc_projection(
                editor=editor,
                expected_protected_count=0,
            )
            editor.apply_changes()
            qt_app.processEvents()

            assert _collect_block_semantic_signature(gui_vsc.rms_model) == (
                _collect_block_semantic_signature(script_vsc.rms_model)
            )
            assert gui_vsc.rms_model.dynamic_model_contract.to_data() == (
                script_vsc.rms_model.dynamic_model_contract.to_data()
            )
    finally:
        editor_to_close: DynamicBlockEditorGUI
        for editor_to_close in open_editors:
            editor_to_close.prepare_to_delete()
            editor_to_close.close()
            editor_to_close.deleteLater()
        qt_app.processEvents()

    # Build one reference-step scenario and one independent current-limiter
    # scenario so GUI persistence is exercised across different V1 dynamics.
    script_reference_group: RmsEventsGroup = RmsEventsGroup(
        idtag="nuactis-v1-q-reference-group",
        active=True,
        name="Nuactis V1 Q reference step",
    )
    gui_reference_group: RmsEventsGroup = RmsEventsGroup(
        idtag="nuactis-v1-q-reference-group",
        active=True,
        name="Nuactis V1 Q reference step",
    )
    script_grid.add_rms_events_group(script_reference_group)
    gui_grid.add_rms_events_group(gui_reference_group)
    _add_nuactis_parameter_event(
        grid=script_grid,
        vsc=script_vsc_devices[1],
        event_group=script_reference_group,
        runtime_parameter_name="Q_ref",
        event_value=0.02,
        event_time=0.003,
        event_idtag="nuactis-v1-q-reference-event",
        event_name="Nuactis V1 Q reference step",
    )
    _add_nuactis_parameter_event(
        grid=gui_grid,
        vsc=gui_vsc_devices[1],
        event_group=gui_reference_group,
        runtime_parameter_name="Q_ref",
        event_value=0.02,
        event_time=0.003,
        event_idtag="nuactis-v1-q-reference-event",
        event_name="Nuactis V1 Q reference step",
    )
    script_limit_group: RmsEventsGroup = RmsEventsGroup(
        idtag="nuactis-v1-iq-limit-group",
        active=True,
        name="Nuactis V1 Iq limit reduction",
    )
    gui_limit_group: RmsEventsGroup = RmsEventsGroup(
        idtag="nuactis-v1-iq-limit-group",
        active=True,
        name="Nuactis V1 Iq limit reduction",
    )
    script_grid.add_rms_events_group(script_limit_group)
    gui_grid.add_rms_events_group(gui_limit_group)
    _add_nuactis_parameter_event(
        grid=script_grid,
        vsc=script_vsc_devices[1],
        event_group=script_limit_group,
        runtime_parameter_name="Outer_Ctrl_Q__iq_lim_max",
        event_value=0.1,
        event_time=0.003,
        event_idtag="nuactis-v1-iq-limit-event",
        event_name="Nuactis V1 Iq limit reduction",
    )
    _add_nuactis_parameter_event(
        grid=gui_grid,
        vsc=gui_vsc_devices[1],
        event_group=gui_limit_group,
        runtime_parameter_name="Outer_Ctrl_Q__iq_lim_max",
        event_value=0.1,
        event_time=0.003,
        event_idtag="nuactis-v1-iq-limit-event",
        event_name="Nuactis V1 Iq limit reduction",
    )

    script_pf_results: PowerFlowResults
    script_rms_results: RmsResults
    script_problem: RmsProblemDae
    script_pf_results, script_rms_results, script_problem = _run_nuactis_short_rms(grid=script_grid)
    gui_pf_results: PowerFlowResults
    gui_rms_results: RmsResults
    gui_problem: RmsProblemDae
    gui_pf_results, gui_rms_results, gui_problem = _run_nuactis_short_rms(grid=gui_grid)

    assert script_problem.get_states_number() == gui_problem.get_states_number()
    assert script_problem.get_algebraic_var_number() == gui_problem.get_algebraic_var_number()
    assert np.allclose(script_pf_results.voltage, gui_pf_results.voltage, rtol=1e-10, atol=1e-10)
    assert np.allclose(script_pf_results.Sbus, gui_pf_results.Sbus, rtol=1e-10, atol=1e-10)
    assert np.allclose(script_pf_results.gen_p, gui_pf_results.gen_p, rtol=1e-10, atol=1e-10)
    assert script_rms_results.values.shape[0] == 11
    assert script_rms_results.values.shape[2] == 2
    assert script_rms_results.values.shape == gui_rms_results.values.shape
    assert list(script_rms_results.variable_array) == list(gui_rms_results.variable_array)
    assert np.array_equal(script_rms_results.has_event_group_results, gui_rms_results.has_event_group_results)
    assert np.array_equal(script_rms_results.well_initialized, gui_rms_results.well_initialized)
    assert np.array_equal(script_rms_results.converged, gui_rms_results.converged)
    assert np.all(script_rms_results.has_event_group_results)
    assert np.all(script_rms_results.well_initialized)
    assert np.all(script_rms_results.converged)
    assert script_rms_results.time_array.equals(gui_rms_results.time_array)
    assert not np.allclose(
        script_rms_results.values[0, :, 0],
        script_rms_results.values[-1, :, 0],
        rtol=1e-10,
        atol=1e-10,
    )
    assert not np.allclose(
        script_rms_results.values[0, :, 1],
        script_rms_results.values[-1, :, 1],
        rtol=1e-10,
        atol=1e-10,
    )
    selected_variable_names: List[str] = list(
        (
            "VmSlave_AC",
            "VdcSlave_DC",
            "P_act_VeraGrid Power meter 221Slave_PWM_nl",
            "Q_act_VeraGrid Power meter 221Slave_PWM_nl",
            "iq_refSlave_PWM_nl",
            "idSlave_PWM_nl",
            "iqSlave_PWM_nl",
            "PmdSlave_PWM_nl",
            "PmqSlave_PWM_nl",
        )
    )
    script_selected_values: np.ndarray = _collect_rms_variable_values(
        problem=script_problem,
        results=script_rms_results,
        variable_names=selected_variable_names,
    )
    gui_selected_values: np.ndarray = _collect_rms_variable_values(
        problem=gui_problem,
        results=gui_rms_results,
        variable_names=selected_variable_names,
    )
    assert np.max(np.abs(script_selected_values - gui_selected_values)) <= 1e-6

    # PowerFactory uses Backward Euler with a fixed, synchronized 1 ms grid.
    # Compare both V1 events through 5 ms and the active current-limit response
    # through 10 ms, covering terminal voltages, P/Q measurements, current
    # control, converter currents, and modulation without relative tolerance.
    pf_reference_values: np.ndarray = np.empty((6, 9, 2), dtype=float)
    pf_reference_values[:, :, 0] = np.array(
        [
            [1.0023478247697053, 0.9937002486245272, 0.714285714275504,
             -1.4309751707384878e-09, 0.12593765839191523, 0.7013960786157394,
             0.1259376583919189, 0.7957316913686865, 0.2617067119242375],
            [1.0023478247699102, 0.9937002486245398, 0.71428571427566,
             -1.4304782577515394e-09, 0.12593765839141713, 0.7013960786158381,
             0.1259376583914241, 0.7957316913689262, 0.26170671192426614],
            [1.0023478247701079, 0.9937002486245501, 0.714285714275808,
             -1.430001341467297e-09, 0.1259376583909381, 0.7013960786159308,
             0.1259376583909482, 0.7957316913691584, 0.2617067119242933],
            [1.002347824770298, 0.993700248624559, 0.7142857142759483,
             -1.4295434880295942e-09, 0.12593765839047738, 0.7013960786160179,
             0.12593765839049037, 0.7957316913693828, 0.26170671192431855],
            [1.002650267702457, 0.9936994963755358, 0.714362614597673,
             0.0006988912092386101, 0.12516561403907972, 0.701393230391041,
             0.12517086555674659, 0.7961144024829689, 0.2616789877555235],
            [1.0029419056842648, 0.9936981567408387, 0.7144338388750483,
             0.0013726260934877488, 0.12442051908303207, 0.7013876156998365,
             0.12443073114458662, 0.796484201493644, 0.2616509606590823],
        ],
        dtype=float,
    )
    pf_reference_values[:, :, 1] = np.array(
        [
            [1.0023478247697053, 0.9937002486245272, 0.714285714275504,
             -1.4309751707384878e-09, 0.12593765839191523, 0.7013960786157394,
             0.1259376583919189, 0.7957316913686865, 0.2617067119242375],
            [1.0023478247699102, 0.9937002486245398, 0.71428571427566,
             -1.4304782577515394e-09, 0.12593765839141713, 0.7013960786158381,
             0.1259376583914241, 0.7957316913689262, 0.26170671192426614],
            [1.0023478247701079, 0.9937002486245501, 0.714285714275808,
             -1.430001341467297e-09, 0.1259376583909381, 0.7013960786159308,
             0.1259376583909482, 0.7957316913691584, 0.2617067119242933],
            [1.002347824770298, 0.993700248624559, 0.7142857142759483,
             -1.4295434880295942e-09, 0.12593765839047738, 0.7013960786160179,
             0.12593765839049037, 0.7957316913693828, 0.26170671192431855],
            [1.0125121409469484, 0.9936747117604987, 0.7168890945479252,
             0.02374168111163032, 0.1, 0.7012996212797632,
             0.10017643024153482, 0.8085897877071915, 0.26077495218625024],
            [1.0125036393432534, 0.9936538923095954, 0.716786654434039,
             0.02370060811701951, 0.1, 0.7012026451828423,
             0.10017281312188854, 0.8086051807232046, 0.26073195116438524],
        ],
        dtype=float,
    )
    powerfactory_difference: np.ndarray = np.abs(
        script_selected_values[:6, :, :] - pf_reference_values
    )
    assert np.max(powerfactory_difference) <= 1e-6, (
        np.unravel_index(np.argmax(powerfactory_difference), powerfactory_difference.shape),
        float(np.max(powerfactory_difference)),
    )
    pf_limit_tail: np.ndarray = np.array(
        [
            [1.012495498918238, 0.9936348802504396, 0.7166882368894633,
             0.023661216336155713, 0.1, 0.7011094698068339,
             0.10016927046778065, 0.8086191977806844, 0.2606903713181343],
            [1.012487704870278, 0.9936170448338162, 0.716593684083269,
             0.023623435299427058, 0.1, 0.7010199462188381,
             0.10016580073416284, 0.8086323476667666, 0.2606503041219945],
            [1.0124802429970157, 0.9936002299512899, 0.7165028443996087,
             0.023587201471565466, 0.1, 0.7009339313224762,
             0.10016240240851107, 0.8086447531450459, 0.26061171935984],
            [1.012473099671013, 0.9935843789466962, 0.7164155721624649,
             0.023552452522316563, 0.1, 0.7008512876290728,
             0.10015907401012342, 0.8086564562362878, 0.2605745634940873],
            [1.0124662618164164, 0.9935694565883787, 0.7163317274102283,
             0.02351912862539791, 0.1, 0.7007718830378122,
             0.1001558140894331, 0.8086674817041525, 0.2605387800356318],
        ],
        dtype=float,
    )
    pf_limit_reference_values: np.ndarray = np.vstack(
        (pf_reference_values[:, :, 1], pf_limit_tail)
    )
    limit_powerfactory_difference: np.ndarray = np.abs(
        script_selected_values[:, :, 1] - pf_limit_reference_values
    )
    assert np.max(limit_powerfactory_difference) <= 1e-6, (
        np.unravel_index(
            np.argmax(limit_powerfactory_difference),
            limit_powerfactory_difference.shape,
        ),
        float(np.max(limit_powerfactory_difference)),
    )


def test_nuactis_v2_gui_editor_matches_scripting_pf_and_rms(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Keep Nuactis V2 invariant after saving both VSC models in the GUI.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    script_grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v2_complete_static_dynamic.dgs",
    )
    gui_grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v2_complete_static_dynamic.dgs",
    )
    script_vsc_devices: List[VSC] = script_grid.get_vsc()
    gui_vsc_devices: List[VSC] = gui_grid.get_vsc()
    assert len(script_vsc_devices) == 2
    assert len(gui_vsc_devices) == len(script_vsc_devices)

    open_editors: List[DynamicBlockEditorGUI] = list()
    converter_index: int
    try:
        # Persist each imported V2 model through the same editor path used by
        # an interactive GUI session, while retaining an untouched script copy.
        for converter_index in range(len(gui_vsc_devices)):
            script_vsc: VSC = script_vsc_devices[converter_index]
            gui_vsc: VSC = gui_vsc_devices[converter_index]
            assert gui_vsc.idtag == script_vsc.idtag
            assert isinstance(gui_vsc.rms_model, Block)
            assert isinstance(script_vsc.rms_model, Block)

            projection_start_seconds: float = perf_counter()
            editor: DynamicBlockEditorGUI = _build_gui_editor(
                qt_app=qt_app,
                grid=gui_grid,
                api_object=gui_vsc,
                mode=DynamicSimulationMode.RMS,
                root_block=gui_vsc.rms_model,
            )
            projection_elapsed_seconds: float = (
                perf_counter() - projection_start_seconds
            )
            assert projection_elapsed_seconds <= 4.0, projection_elapsed_seconds
            open_editors.append(editor)
            expected_protected_count: int = 0
            _assert_nuactis_vsc_projection(
                editor=editor,
                expected_protected_count=expected_protected_count,
            )
            editor.apply_changes()
            qt_app.processEvents()

            assert _collect_block_semantic_signature(gui_vsc.rms_model) == (
                _collect_block_semantic_signature(script_vsc.rms_model)
            )
            assert gui_vsc.rms_model.dynamic_model_contract.to_data() == (
                script_vsc.rms_model.dynamic_model_contract.to_data()
            )
    finally:
        editor_to_close: DynamicBlockEditorGUI
        for editor_to_close in open_editors:
            editor_to_close.prepare_to_delete()
            editor_to_close.close()
            editor_to_close.deleteLater()
        qt_app.processEvents()

    # Keep the original Q-amplitude routing scenario and add an independent
    # active-power step that exercises both Amplitude and T_step parameters.
    script_q_amplitude_group: RmsEventsGroup = RmsEventsGroup(
        idtag="nuactis-v2-q-amplitude-group",
        active=True,
        name="Nuactis V2 Q amplitude routing",
    )
    gui_q_amplitude_group: RmsEventsGroup = RmsEventsGroup(
        idtag="nuactis-v2-q-amplitude-group",
        active=True,
        name="Nuactis V2 Q amplitude routing",
    )
    script_grid.add_rms_events_group(script_q_amplitude_group)
    gui_grid.add_rms_events_group(gui_q_amplitude_group)
    _add_nuactis_parameter_event(
        grid=script_grid,
        vsc=script_vsc_devices[1],
        event_group=script_q_amplitude_group,
        runtime_parameter_name="Outer_Ctrl_Q__Amplitude",
        event_value=0.01,
        event_time=0.003,
        event_idtag="nuactis-v2-q-amplitude-event",
        event_name="Nuactis V2 Q amplitude routing",
    )
    _add_nuactis_parameter_event(
        grid=gui_grid,
        vsc=gui_vsc_devices[1],
        event_group=gui_q_amplitude_group,
        runtime_parameter_name="Outer_Ctrl_Q__Amplitude",
        event_value=0.01,
        event_time=0.003,
        event_idtag="nuactis-v2-q-amplitude-event",
        event_name="Nuactis V2 Q amplitude routing",
    )
    script_active_power_group: RmsEventsGroup = RmsEventsGroup(
        idtag="nuactis-v2-active-power-group",
        active=True,
        name="Nuactis V2 active-power internal step",
    )
    gui_active_power_group: RmsEventsGroup = RmsEventsGroup(
        idtag="nuactis-v2-active-power-group",
        active=True,
        name="Nuactis V2 active-power internal step",
    )
    script_grid.add_rms_events_group(script_active_power_group)
    gui_grid.add_rms_events_group(gui_active_power_group)
    _add_nuactis_parameter_event(
        grid=script_grid,
        vsc=script_vsc_devices[1],
        event_group=script_active_power_group,
        runtime_parameter_name="Outer_Ctrl_P_wFFS__Amplitude",
        event_value=0.02,
        event_time=0.003,
        event_idtag="nuactis-v2-active-power-amplitude-event",
        event_name="Nuactis V2 active-power amplitude",
    )
    _add_nuactis_parameter_event(
        grid=script_grid,
        vsc=script_vsc_devices[1],
        event_group=script_active_power_group,
        runtime_parameter_name="Outer_Ctrl_P_wFFS__T_step",
        event_value=0.003,
        event_time=0.003,
        event_idtag="nuactis-v2-active-power-time-event",
        event_name="Nuactis V2 active-power step time",
    )
    _add_nuactis_parameter_event(
        grid=gui_grid,
        vsc=gui_vsc_devices[1],
        event_group=gui_active_power_group,
        runtime_parameter_name="Outer_Ctrl_P_wFFS__Amplitude",
        event_value=0.02,
        event_time=0.003,
        event_idtag="nuactis-v2-active-power-amplitude-event",
        event_name="Nuactis V2 active-power amplitude",
    )
    _add_nuactis_parameter_event(
        grid=gui_grid,
        vsc=gui_vsc_devices[1],
        event_group=gui_active_power_group,
        runtime_parameter_name="Outer_Ctrl_P_wFFS__T_step",
        event_value=0.003,
        event_time=0.003,
        event_idtag="nuactis-v2-active-power-time-event",
        event_name="Nuactis V2 active-power step time",
    )

    script_pf_results: PowerFlowResults
    script_rms_results: RmsResults
    script_problem: RmsProblemDae
    script_pf_results, script_rms_results, script_problem = _run_nuactis_short_rms(
        grid=script_grid,
    )
    gui_pf_results: PowerFlowResults
    gui_rms_results: RmsResults
    gui_problem: RmsProblemDae
    gui_pf_results, gui_rms_results, gui_problem = _run_nuactis_short_rms(
        grid=gui_grid,
    )

    assert script_problem.get_states_number() == gui_problem.get_states_number()
    assert script_problem.get_algebraic_var_number() == gui_problem.get_algebraic_var_number()
    assert np.allclose(script_pf_results.voltage, gui_pf_results.voltage, rtol=0.0, atol=1e-10)
    assert np.allclose(script_pf_results.Sbus, gui_pf_results.Sbus, rtol=0.0, atol=1e-10)
    assert script_rms_results.values.shape == gui_rms_results.values.shape
    assert list(script_rms_results.variable_array) == list(gui_rms_results.variable_array)
    assert np.array_equal(script_rms_results.has_event_group_results, gui_rms_results.has_event_group_results)
    assert np.array_equal(script_rms_results.well_initialized, gui_rms_results.well_initialized)
    assert np.array_equal(script_rms_results.converged, gui_rms_results.converged)
    assert np.all(script_rms_results.has_event_group_results)
    assert np.all(script_rms_results.well_initialized)
    assert np.all(script_rms_results.converged)
    assert script_rms_results.time_array.equals(gui_rms_results.time_array)
    assert script_rms_results.values.shape[2] == 2
    assert np.max(np.abs(script_rms_results.values - gui_rms_results.values)) <= 1e-6
    selected_variable_names: List[str] = list(
        (
            "VmSlave_AC",
            "VdcSlave_DC",
            "P_act_VeraGrid Power meter 229HVDC Slave_PWM",
            "Q_act_VeraGrid Power meter 229HVDC Slave_PWM",
            "id_refHVDC Slave_PWM",
            "idHVDC Slave_PWM",
            "iqHVDC Slave_PWM",
            "PmdHVDC Slave_PWM",
            "PmqHVDC Slave_PWM",
        )
    )
    script_selected_values: np.ndarray = _collect_rms_variable_values(
        problem=script_problem,
        results=script_rms_results,
        variable_names=selected_variable_names,
    )
    gui_selected_values: np.ndarray = _collect_rms_variable_values(
        problem=gui_problem,
        results=gui_rms_results,
        variable_names=selected_variable_names,
    )
    assert np.max(np.abs(script_selected_values - gui_selected_values)) <= 1e-6

    # Compare synchronized traces for a latent Q-amplitude routing event and a
    # physically active P-controller step. The active response covers all 11
    # samples through 10 ms for nine independent electrical, controller,
    # current, and modulation quantities.
    pf_reference_values: np.ndarray = np.empty((8, 9, 2), dtype=float)
    pf_reference_values[:, :, 0] = np.array(
        [
            [0.9843814973092572, 1.0061318797440824, -0.7142857142855416,
             1.3395577980190865e-11, -0.7179655512943582, -0.7179655512943582,
             0.13284415767260976, 0.4212023430543814, -0.19836651541059913],
            [0.9843814973081907, 1.0061318797440797, -0.714285714285515,
             1.3189175466063066e-11, -0.717965551294358, -0.7179655512943579,
             0.13284415767283134, 0.4212023430543063, -0.19836651541059594],
            [0.9843814973080749, 1.0061318797440746, -0.7142857142854899,
             1.2990040789061043e-11, -0.7179655512943579, -0.7179655512943579,
             0.1328441576730453, 0.4212023430542335, -0.19836651541059283],
            [0.9843814973079628, 1.0061318797440688, -0.714285714285465,
             1.2798072443079685e-11, -0.7179655512943579, -0.7179655512943577,
             0.13284415767325136, 0.42120234305416343, -0.19836651541058975],
            [0.9843814973078551, 1.0061318797440628, -0.7142857142854417,
             1.2613026813466734e-11, -0.7179655512943579, -0.717965551294358,
             0.1328441576734503, 0.42120234305409626, -0.19836651541058722],
            [0.9843814973077509, 1.0061318797440564, -0.7142857142854195,
             1.2434396369696645e-11, -0.717965551294358, -0.7179655512943585,
             0.13284415767364235, 0.42120234305403165, -0.19836651541058492],
            [0.9843814973076506, 1.0061318797440497, -0.7142857142853977,
             1.2262282617874527e-11, -0.7179655512943582, -0.7179655512943586,
             0.13284415767382737, 0.42120234305396953, -0.1983665154105827],
            [0.984381497307554, 1.0061318797440426, -0.7142857142853768,
             1.2096178027474837e-11, -0.7179655512943586, -0.7179655512943587,
             0.1328441576740058, 0.42120234305390974, -0.19836651541058062],
        ],
        dtype=float,
    )
    pf_reference_values[:, :, 1] = np.array(
        [
            [0.9843814973092572, 1.0061318797440824, -0.7142857142855416,
             1.3395577980190865e-11, -0.7179655512943582, -0.7179655512943582,
             0.13284415767260976, 0.4212023430543814, -0.19836651541059913],
            [0.9843814973081907, 1.0061318797440797, -0.714285714285515,
             1.3189175466063066e-11, -0.717965551294358, -0.7179655512943579,
             0.13284415767283134, 0.4212023430543063, -0.19836651541059594],
            [0.9843814973080749, 1.0061318797440746, -0.7142857142854899,
             1.2990040789061043e-11, -0.7179655512943579, -0.7179655512943579,
             0.1328441576730453, 0.4212023430542335, -0.19836651541059283],
            [0.9843814973079628, 1.0061318797440688, -0.714285714285465,
             1.2798072443079685e-11, -0.7179655512943579, -0.7179655512943577,
             0.13284415767325136, 0.42120234305416343, -0.19836651541058975],
            [0.9843719086934515, 1.0061312723588598, -0.7142072945517314,
             -3.621440480498807e-05, -0.7178858649732928, -0.7178864068145794,
             0.1328427324189044, 0.4212046412108688, -0.19833889372602098],
            [0.9843631105458035, 1.0061301008704309, -0.7141293344071151,
             -7.099539257930181e-05, -0.7178064904928061, -0.7178075607607995,
             0.13283992486251384, 0.4212076547113653, -0.19831151486618126],
            [0.9843550730036417, 1.0061284211118984, -0.7140518258773308,
             -0.00010439464670751266, -0.7177274260464386, -0.7177290116219334,
             0.13283578971530693, 0.42121134102194485, -0.19828436618506362],
            [0.9843477672752907, 1.0061262975109728, -0.7139747612449869,
             -0.00013646201462689435, -0.7176486698586004, -0.7176507579111814,
             0.1328303797195585, 0.4212156547021974, -0.19825743339670046],
        ],
        dtype=float,
    )
    powerfactory_difference: np.ndarray = np.abs(
        script_selected_values[:8, :, :] - pf_reference_values
    )
    assert np.max(powerfactory_difference) <= 1e-6, (
        np.unravel_index(np.argmax(powerfactory_difference), powerfactory_difference.shape),
        float(np.max(powerfactory_difference)),
    )
    pf_active_tail: np.ndarray = np.array(
        [
            [0.9843411656005945, 1.0061237991659089, -0.7138981330404819,
             -0.00016724556140717693, -0.7175702201835803,
             -0.7175727981652051, 0.13282374571889807,
             0.42122054902237555, -0.1982307013475729],
            [0.9843352412141125, 1.006120996174945, -0.7138219340332167,
             -0.00019679163371802945, -0.7174920753045892,
             -0.7174951309433166, 0.1328159367260879,
             0.4212259774756424, -0.19820415473851105],
            [0.9843299683096303, 1.006117956391999, -0.71374615722312,
             -0.00022514492147426577, -0.7174142335328386,
             -0.7174177548267039, 0.1328069999883731,
             0.42123189511288467, -0.19817777876213108],
        ],
        dtype=float,
    )
    pf_active_reference_values: np.ndarray = np.vstack(
        (pf_reference_values[:, :, 1], pf_active_tail)
    )
    active_powerfactory_difference: np.ndarray = np.abs(
        script_selected_values[:, :, 1] - pf_active_reference_values
    )
    assert np.max(active_powerfactory_difference) <= 1e-6, (
        np.unravel_index(
            np.argmax(active_powerfactory_difference),
            active_powerfactory_difference.shape,
        ),
        float(np.max(active_powerfactory_difference)),
    )
    assert not np.allclose(
        script_selected_values[0, :, 1],
        script_selected_values[10, :, 1],
        rtol=1e-10,
        atol=1e-10,
    )
def test_rms_editor_open_materializes_connection_vars(qt_app: QtWidgets.QApplication) -> None:
    """
    Show every RMS root connection variable immediately when an editor opens.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit
    generator: Generator
    line: Line
    load: Load
    grid, generator, line, load = _build_two_bus_rms_grid()

    generator.rms_template = get_complete_generator_template_rms(grid.var_factory)
    load.rms_template = get_load_rms_template(grid.var_factory)

    generator_editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=generator,
        mode=DynamicSimulationMode.RMS,
        root_block=generator.rms_model,
    )
    line_editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=line,
        mode=DynamicSimulationMode.RMS,
        root_block=line.rms_model,
    )
    load_editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=load,
        mode=DynamicSimulationMode.RMS,
        root_block=load.rms_model,
    )

    editor: DynamicBlockEditorGUI
    expected_refs_by_editor: list[tuple[DynamicBlockEditorGUI, set[VarPowerFlowReferenceType]]] = list([
        (generator_editor, set([
            VarPowerFlowReferenceType.Vm,
            VarPowerFlowReferenceType.Va,
            VarPowerFlowReferenceType.P,
            VarPowerFlowReferenceType.Q,
        ])),
        (line_editor, set([
            VarPowerFlowReferenceType.Vmf,
            VarPowerFlowReferenceType.Vaf,
            VarPowerFlowReferenceType.Vmt,
            VarPowerFlowReferenceType.Vat,
            VarPowerFlowReferenceType.Pf,
            VarPowerFlowReferenceType.Qf,
            VarPowerFlowReferenceType.Pt,
            VarPowerFlowReferenceType.Qt,
        ])),
        (load_editor, set([
            VarPowerFlowReferenceType.Vm,
            VarPowerFlowReferenceType.Va,
            VarPowerFlowReferenceType.P,
            VarPowerFlowReferenceType.Q,
        ])),
    ])

    for editor, _unused_expected_references in expected_refs_by_editor:
        assert editor.ui.toolBox.count() == 1
        assert editor.ui.toolBox.currentWidget() is editor.ui.page_7

    try:
        for editor, expected_refs in expected_refs_by_editor:
            visible_refs: set[VarPowerFlowReferenceType] = set()
            visible_positions: set[tuple[float, float]] = set()
            scene_item: Any
            block_type: BlockType
            semantic_reference: VarPowerFlowReferenceType | None
            for scene_item in editor.scene.items():
                if isinstance(scene_item, graph.ProtectedConnectionBlockItem):
                    if scene_item.subsys is None:
                        pass
                    else:
                        if len(scene_item.subsys.out_vars) == 1 and len(scene_item.subsys.in_vars) == 0:
                            block_type = BlockType.INPUT_CONN
                        else:
                            block_type = BlockType.OUTPUT_CONN
                        semantic_reference = editor._get_semantic_root_interface_reference(
                            wrapper_block=scene_item.subsys,
                            block_type=block_type,
                        )
                        if semantic_reference is not None:
                            visible_refs.add(semantic_reference)
                            visible_positions.add((scene_item.pos().x(), scene_item.pos().y()))
                        else:
                            pass
                else:
                    pass

            assert visible_refs == expected_refs
            assert len(visible_positions) == len(expected_refs)
    finally:
        for editor, _expected_refs in expected_refs_by_editor:
            editor.prepare_to_delete()
            editor.close()
            editor.deleteLater()


def test_rms_editor_reopen_preserves_persisted_connection_arrows(
        qt_app: QtWidgets.QApplication,
) -> None:
    """
    Restore RMS arrows from persisted diagram-node wrapper semantics.

    Root-interface wrapper blocks are persisted through their diagram node
    types. The symbolic ``Block`` must remain unaware of this GUI role, while
    reopening must still reconstruct the same graphical connections.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit
    generator: Generator
    line: Line
    load: Load
    grid, generator, line, load = _build_two_bus_rms_grid()

    # Build the same three RMS models that users assign from the editor library.
    generator.rms_template = get_complete_generator_template_rms(grid.var_factory)
    line.rms_template = get_line_rms_template(grid.var_factory)
    load.rms_template = get_load_rms_template(grid.var_factory)

    devices: List[Generator | Line | Load] = list([generator, line, load])
    initial_editors: List[DynamicBlockEditorGUI] = list()
    expected_connection_counts: Dict[int, int] = dict()
    device: Generator | Line | Load
    editor: DynamicBlockEditorGUI

    # First opening materializes and persists each template's graphical arrows.
    for device in devices:
        editor = _build_gui_editor(
            qt_app=qt_app,
            grid=grid,
            api_object=device,
            mode=DynamicSimulationMode.RMS,
            root_block=device.rms_model,
        )
        initial_editors.append(editor)
        expected_connection_counts[device.rms_model.uid] = len(device.rms_model.diagram.con_data)

    for editor in initial_editors:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
    qt_app.processEvents()

    # Confirm the symbolic tree and its fallback dictionary boundary contain
    # no GUI-only wrapper state before exercising the persisted diagram path.
    for device in devices:
        for child_block in device.rms_model.children:
            assert "is_root_interface_wrapper" not in child_block.__dict__
            assert "is_root_interface_wrapper" not in child_block.to_dict()

    reopened_editors: List[DynamicBlockEditorGUI] = list()
    try:
        for device in devices:
            editor = _build_gui_editor(
                qt_app=qt_app,
                grid=grid,
                api_object=device,
                mode=DynamicSimulationMode.RMS,
                root_block=device.rms_model,
            )
            reopened_editors.append(editor)

            scene_connection_count: int = len([
                scene_item for scene_item in editor.scene.items()
                if isinstance(scene_item, graph.ConnectionItem)
            ])
            expected_connection_count: int | None = expected_connection_counts.get(device.rms_model.uid, None)
            assert expected_connection_count is not None
            assert expected_connection_count > 0
            assert len(editor.diagram.con_data) == expected_connection_count
            assert scene_connection_count == expected_connection_count
    finally:
        for editor in reopened_editors:
            editor.prepare_to_delete()
            editor.close()
            editor.deleteLater()


def test_decomposed_rms_block_persists_and_restores_elk_connections(
        qt_app: QtWidgets.QApplication,
) -> None:
    """
    Keep ELK-generated equation arrows through the immediate scene rebuild.

    Also cover diagrams saved by the regression with nodes but no graphical
    branches: reopening must infer the missing arrows from symbolic block
    connectivity, including arithmetic and unary graphics item types.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit
    generator: Generator
    line: Line
    load: Load
    grid, generator, line, load = _build_two_bus_rms_grid()
    del line
    del load

    wrapper_block: Block = get_genrow_rms_template(grid.var_factory).block
    decomposable_block: Block = wrapper_block.children[0]
    prepared_block: Block
    block_types: Dict[int, BlockType]
    prepared_block, block_types = prepare_block_for_editing(
        block=decomposable_block,
        var_factory=grid.var_factory,
    )
    assert len(prepared_block.children) > 0
    assert len(block_types) == len(prepared_block.children)

    first_editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=grid.var_factory,
        root_block=wrapper_block,
        current_block=prepared_block,
        api_object=generator,
        circuit=grid,
        mode=DynamicSimulationMode.RMS,
        current_theme=DynEditorGraphicsModes.LIGHT,
        templates_list=list(),
        is_root_editor=False,
        modal=False,
        workspace_embedded=False,
        block2blocktype=block_types,
    )
    first_editor.show()
    qt_app.processEvents()

    expected_edge_count: int = len(
        first_editor._build_elk_layout_graph(
            child_blocks=prepared_block.children,
            input_output_blocks=list(),
        ).edges
    )
    first_scene_connections: List[graph.ConnectionItem] = [
        scene_item for scene_item in first_editor.scene.items()
        if isinstance(scene_item, graph.ConnectionItem)
    ]
    assert expected_edge_count > 0
    assert len(first_editor.diagram.con_data) >= expected_edge_count
    assert len(first_scene_connections) >= expected_edge_count
    assert all(not connection.path().isEmpty() for connection in first_scene_connections)

    first_editor.prepare_to_delete()
    first_editor.close()
    first_editor.deleteLater()
    qt_app.processEvents()

    # Emulate a diagram persisted by the regression: all generated nodes were
    # retained, while its transient ELK arrows disappeared during scene rebuild.
    prepared_block.diagram.con_data.clear()
    second_editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=grid.var_factory,
        root_block=wrapper_block,
        current_block=prepared_block,
        api_object=generator,
        circuit=grid,
        mode=DynamicSimulationMode.RMS,
        current_theme=DynEditorGraphicsModes.LIGHT,
        templates_list=list(),
        is_root_editor=False,
        modal=False,
        workspace_embedded=False,
        block2blocktype=block_types,
    )
    second_editor.show()
    qt_app.processEvents()
    restored_scene_connections: List[graph.ConnectionItem] = [
        scene_item for scene_item in second_editor.scene.items()
        if isinstance(scene_item, graph.ConnectionItem)
    ]

    try:
        assert len(second_editor.diagram.con_data) >= expected_edge_count
        assert len(restored_scene_connections) >= expected_edge_count
        assert all(not connection.path().isEmpty() for connection in restored_scene_connections)
    finally:
        second_editor.prepare_to_delete()
        second_editor.close()
        second_editor.deleteLater()


def test_empty_generic_nested_editor_contains_only_boundary_ports(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Keep an empty Generic nested view free from a duplicate central block.

    Also exercise migration of a diagram saved by the former behaviour, where
    the Generic persisted a node representing itself between its own boundary
    ports.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    circuit: MultiCircuit = MultiCircuit()
    generator: Generator = Generator(name="Generic owner")
    generic_block: Block = create_generic_block(
        var_factory=circuit.var_factory,
        inputs=3,
        outputs=1,
        name="GENERIC_1",
    )
    root_block: Block = Block(name="generic_root")
    root_block.add(generic_block)

    # Reproduce a file saved by the regression. The constructor must discard
    # this self node before it creates the legitimate boundary wrappers.
    generic_block.diagram.add_node(
        name=generic_block.name,
        x=480.0,
        y=260.0,
        tpe=BlockType.GENERIC.name,
        device_uid=generic_block.uid,
    )

    editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=circuit.var_factory,
        root_block=root_block,
        current_block=generic_block,
        api_object=generator,
        circuit=circuit,
        mode=DynamicSimulationMode.RMS,
        current_theme=DynEditorGraphicsModes.LIGHT,
        templates_list=list(),
        is_root_editor=False,
        modal=False,
        workspace_embedded=False,
        block2blocktype=dict(),
    )
    editor.show()
    qt_app.processEvents()

    try:
        node_types: List[str] = [node.tpe for node in editor.diagram.node_data.values()]
        assert len(node_types) == 4
        assert node_types.count(BlockType.INPUT_CONN.name) == 3
        assert node_types.count(BlockType.OUTPUT_CONN.name) == 1
        assert BlockType.GENERIC.name not in node_types
        assert all(node.device_uid != generic_block.uid for node in editor.diagram.node_data.values())
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


def test_canvas_copy_paste_clones_blocks_without_parent_connections(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Clone block content and identities while omitting every canvas arrow.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    circuit: MultiCircuit = MultiCircuit()
    generator: Generator = Generator(name="Clipboard owner")
    root_block: Block = Block(name="clipboard_root")
    editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=circuit.var_factory,
        root_block=root_block,
        current_block=root_block,
        api_object=generator,
        circuit=circuit,
        mode=DynamicSimulationMode.RMS,
        current_theme=DynEditorGraphicsModes.LIGHT,
        templates_list=list(),
        is_root_editor=False,
        modal=False,
        workspace_embedded=False,
        block2blocktype=dict(),
    )
    editor.show()
    qt_app.processEvents()

    try:
        source_item: graph.GenericBlockItem | None = editor.create_generic_block_item(
            block_type=BlockType.GENERIC,
            x_pos=100.0,
            y_pos=120.0,
        )
        target_item: graph.GenericBlockItem | None = editor.create_generic_block_item(
            block_type=BlockType.GENERIC,
            x_pos=360.0,
            y_pos=120.0,
        )
        assert source_item is not None
        assert target_item is not None
        source_block: Block = source_item.subsys
        target_block: Block = target_item.subsys

        source_block.algebraic_vars.append(source_block.out_vars[0])
        source_block.algebraic_eqs.append(source_block.out_vars[0] - source_block.in_vars[0])
        editor.scene.connect_ports(source_item.outputs[0], target_item.inputs[0])
        connection_count_before_copy: int = len(editor.diagram.con_data)
        assert connection_count_before_copy == 1

        editor.scene.clearSelection()
        source_item.setSelected(True)
        editor.copy_selected_blocks()
        editor.paste_copied_blocks()
        qt_app.processEvents()

        pasted_candidates: List[Block] = list()
        child_block: Block
        for child_block in root_block.children:
            if child_block.uid not in set((source_block.uid, target_block.uid)):
                pasted_candidates.append(child_block)
            else:
                pass
        assert len(pasted_candidates) == 1
        pasted_block: Block = pasted_candidates[0]
        assert pasted_block.uid != source_block.uid
        source_variable_uids: set[int] = set(
            variable.non_mutable_uid
            for variable in source_block.in_vars + source_block.out_vars + source_block.algebraic_vars
        )
        pasted_variable_uids: set[int] = set(
            variable.non_mutable_uid
            for variable in pasted_block.in_vars + pasted_block.out_vars + pasted_block.algebraic_vars
        )
        assert source_variable_uids.isdisjoint(pasted_variable_uids)
        assert symbolic_to_string(pasted_block.algebraic_eqs[0]) == symbolic_to_string(
            source_block.algebraic_eqs[0]
        )
        assert len(editor.diagram.con_data) == connection_count_before_copy

        editor.remove_selected_canvas_items()
        qt_app.processEvents()
        assert all(child.uid != pasted_block.uid for child in root_block.children)
        assert pasted_block.uid not in editor.diagram.node_data
        assert len(editor.diagram.con_data) == connection_count_before_copy
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()
