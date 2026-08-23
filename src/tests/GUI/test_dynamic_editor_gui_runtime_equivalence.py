from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PySide6 import QtWidgets

from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_editor_support import collect_block_runtime_event_parameters
from VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor import DynamicBlockEditorGUI
from VeraGrid.Gui.DynamicModelEditor.dynamic_block_preparation import prepare_block_for_editing
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
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, symbolic_to_string
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model, set_rms_model
from VeraGridEngine.enumerations import BlockType, BranchImpedanceMode, DynamicIntegrationMethod, DynamicSimulationMode, DynEditorGraphicsModes, EmtInitializationMethod, EmtSolverTypes, FileType, RmsInitializationMethod, ShuntConnectionType, SolverType, VarPowerFlowReferenceType


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


def _add_nuactis_q_reference_step(
        grid: MultiCircuit,
        vsc: VSC,
        runtime_parameter_name: str = "Q_ref",
        event_value: float = 0.02,
) -> Var:
    """Add one GUI-selectable controller-parameter step to Nuactis.

    :param grid: Canonical Nuactis circuit that owns the event.
    :param vsc: Slave converter whose imported controller is perturbed.
    :param runtime_parameter_name: Exact imported runtime parameter name.
    :param event_value: Absolute parameter value applied at the event.
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

    event_group: RmsEventsGroup = RmsEventsGroup(
        idtag="nuactis-gui-script-controller-step-group",
        active=True,
        name="Nuactis GUI-script controller step",
    )
    event: RmsEvent = RmsEvent(
        idtag="nuactis-gui-script-controller-step",
        name="Nuactis GUI-script controller step",
        device=vsc,
        parameter=selected_parameter,
        time=0.003,
        value=event_value,
        group=event_group,
    )
    grid.add_rms_events_group(event_group)
    grid.add_rms_event(event)
    return selected_parameter


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
        tolerance=1e-6,
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


def _run_balanced_pf(grid: MultiCircuit) -> Any:
    power_flow: PowerFlowDriver = PowerFlowDriver(grid, _build_pf_options())
    power_flow.run()
    return power_flow.results


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

            editor: DynamicBlockEditorGUI = _build_gui_editor(
                qt_app=qt_app,
                grid=gui_grid,
                api_object=gui_vsc,
                mode=DynamicSimulationMode.RMS,
                root_block=gui_vsc.rms_model,
            )
            open_editors.append(editor)
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

    # Perturb the same controller reference through the parameter exposed by
    # the GUI event editor so equality covers an actual dynamic response.
    _add_nuactis_q_reference_step(
        grid=script_grid,
        vsc=script_vsc_devices[1],
    )
    _add_nuactis_q_reference_step(
        grid=gui_grid,
        vsc=gui_vsc_devices[1],
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
    assert script_rms_results.values.shape[2] == 1
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
    slave_q_active_uid: int | None = script_problem.vars_glob_name2uid.get(
        "Q_act_PowerFactory StaPqmea 221Slave_PWM_nl",
        None,
    )
    assert slave_q_active_uid is not None
    slave_q_active_index: int = script_problem.uid2idx_vars[slave_q_active_uid]
    slave_q_active_trace: np.ndarray = script_rms_results.values[
        :,
        slave_q_active_index,
        0,
    ]
    # PowerFactory keeps the state unchanged on the event sample and applies
    # the new Q reference while integrating the immediately following interval.
    assert np.isclose(slave_q_active_trace[3], slave_q_active_trace[0])
    assert not np.isclose(slave_q_active_trace[4], slave_q_active_trace[3])
    # Isolated PowerFactory V1 gives Q_act=0.0044611085247 pu at 10 ms with
    # the same 1 ms step. Backward-Euler discretization remains within 2%.
    assert np.isclose(
        slave_q_active_trace[10],
        0.0044611085247,
        rtol=2.0e-2,
        atol=1.0e-6,
    )
    assert np.allclose(script_rms_results.values, gui_rms_results.values, rtol=1e-8, atol=1e-8)


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

            editor: DynamicBlockEditorGUI = _build_gui_editor(
                qt_app=qt_app,
                grid=gui_grid,
                api_object=gui_vsc,
                mode=DynamicSimulationMode.RMS,
                root_block=gui_vsc.rms_model,
            )
            open_editors.append(editor)
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

    # Apply the same GUI-selectable controller event to both canonical grids.
    script_amplitude_parameter: Var = _add_nuactis_q_reference_step(
        grid=script_grid,
        vsc=script_vsc_devices[1],
        runtime_parameter_name="Outer_Ctrl_Q__Amplitude",
        event_value=0.01,
    )
    _add_nuactis_q_reference_step(
        grid=gui_grid,
        vsc=gui_vsc_devices[1],
        runtime_parameter_name="Outer_Ctrl_Q__Amplitude",
        event_value=0.01,
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
    assert np.max(np.abs(script_rms_results.values - gui_rms_results.values)) <= 1e-6
    # Compare the complete 1 ms trace exported by licensed PowerFactory after
    # its normal ComInc initialization. The directed amplitude event is present
    # in both runs at 3 ms; its internal T_step remains 2 s, so these first
    # 10 ms validate initialization and time routing before the delayed step.
    pf_reference_values: np.ndarray = np.array(
        [
            [0.9843814973093796, 1.0061318797440864, 1.3500718003862338e-11],
            [0.9843814973050085, 1.0061318797440393, 7.765907282321548e-12],
            [0.9843814973050056, 1.0061318797440400, 7.760953784392250e-12],
            [0.9843814973050028, 1.0061318797440406, 7.756020587683972e-12],
            [0.9843814973049996, 1.0061318797440413, 7.751615222722258e-12],
            [0.9843814973049967, 1.0061318797440420, 7.747209857760546e-12],
            [0.9843814973049935, 1.0061318797440426, 7.742905998903942e-12],
            [0.9843814973049914, 1.0061318797440433, 7.738622441268361e-12],
            [0.9843814973049886, 1.0061318797440437, 7.734480992179929e-12],
            [0.9843814973049857, 1.0061318797440442, 7.730501952859673e-12],
            [0.9843814973049835, 1.0061318797440446, 7.726847733075763e-12],
        ],
        dtype=float,
    )
    slave_ac_voltage_uid: int | None = script_problem.vars_glob_name2uid.get(
        "VmSlave_AC",
        None,
    )
    slave_dc_voltage_uid: int | None = script_problem.vars_glob_name2uid.get(
        "VdcSlave_DC",
        None,
    )
    slave_q_active_uid: int | None = script_problem.vars_glob_name2uid.get(
        "Q_act_PowerFactory StaPqmea 229HVDC Slave_PWM",
        None,
    )
    assert slave_ac_voltage_uid is not None
    assert slave_dc_voltage_uid is not None
    assert slave_q_active_uid is not None
    veragrid_values: np.ndarray = np.column_stack(
        (
            script_rms_results.values[
                :, script_problem.uid2idx_vars[slave_ac_voltage_uid], 0
            ],
            script_rms_results.values[
                :, script_problem.uid2idx_vars[slave_dc_voltage_uid], 0
            ],
            script_rms_results.values[
                :, script_problem.uid2idx_vars[slave_q_active_uid], 0
            ],
        )
    )
    assert np.max(np.abs(veragrid_values - pf_reference_values)) <= 1e-6
    amplitude_parameter_index: int = script_problem._uid2idx_event_params[
        script_amplitude_parameter.uid
    ]
    assert float(
        script_problem._variable_parameters_values[amplitude_parameter_index]
    ) == 0.01


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
