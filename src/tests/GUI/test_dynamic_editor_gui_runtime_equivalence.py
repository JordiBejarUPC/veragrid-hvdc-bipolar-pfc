from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.DynamicEventsDialog.dynamic_events_editor_support import collect_block_runtime_event_parameters
from VeraGrid.Gui.DynamicModelEditor.dynamic_block_editor import (
    DynamicBlockEditorGUI,
    block_has_internal_equation_content,
    get_rms_measurement_terminal_side_for_reference,
    get_single_interface_var,
    is_root_interface_wrapper_block,
)
from VeraGrid.Gui.DynamicModelEditor.dynamic_block_properties import (
    DynamicBlockPropertiesDialog,
    MeasurementTargetPickerDialog,
    RmsMeasurementEditOption,
)
from VeraGrid.Gui.DynamicModelEditor.dynamic_block_preparation import prepare_block_for_editing
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_library import (
    DynamicEditorLibrary,
    MeasurementBlockDescriptor,
    MeasurementStationDescriptor,
)
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_tab import DynamicEditorTab
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_workspace_window import (
    DynamicEditorWorkspaceWindow,
)
from VeraGrid.Gui.DynamicModelEditor.dynamic_editor_utilities import create_generic_block
from VeraGrid.Session.dynamic_editor_workspace_session import DynamicEditorWorkspaceSession
import VeraGrid.Gui.DynamicModelEditor.dynamic_editor_graphics as graph
import VeraGrid.Gui.DynamicModelEditor.dynamic_editor_validation as validation
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
from VeraGridEngine.Devices.Diagrams.block_diagram import BlockDiagramConnection
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions
from VeraGridEngine.IO.file_save import FileSave
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
from VeraGridEngine.Templates.Rms.rms_meter_templates import (
    build_rms_physical_signal_meter_block,
    build_rms_voltage_meter_outputs_from_polar,
    normalize_rms_meter_symbol_fragment,
    select_basic_balanced_rms_meter_outputs,
)
from VeraGridEngine.Utils.Symbolic.block import (
    Block,
    RmsPhysicalMeasurementPoint,
    RmsPhysicalMeterKind,
    RmsTerminalSide,
    validate_dynamic_model_contract,
)
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, symbolic_to_string
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model, set_rms_model
from VeraGridEngine.Utils.procedural_logic import ProceduralLogicCodec
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import BlockType, BranchImpedanceMode, DeviceType, DynamicIntegrationMethod, DynamicSimulationMode, DynEditorGraphicsModes, EmtInitializationMethod, EmtSolverTypes, FileType, RmsInitializationMethod, ShuntConnectionType, SolverType, VarPowerFlowReferenceType


class RmsGuiSignalBridge(QtCore.QObject):
    """Expose the Qt signals assigned by the real GUI simulation session."""

    __slots__ = ()

    progress_signal = QtCore.Signal(float)
    progress_text = QtCore.Signal(str)


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


def _build_nine_bus_rms_measurement_grid() -> Tuple[MultiCircuit, Generator]:
    """Build a deterministic connected nine-bus RMS network with public APIs.

    The chain topology keeps every connection easy to audit: endpoint buses
    own one branch and internal buses own two. Every physical device receives
    a canonical RMS model so the network can be compiled after GUI meters are
    added to the slack-generator model.

    :return: Nine-bus circuit and its slack generator.
    """
    grid: MultiCircuit = MultiCircuit(
        name="Nine-bus measurement audit",
        Sbase=100.0,
        fbase=50.0,
        idtag="nine-bus-measurement-grid",
    )
    buses: List[Bus] = list(
        Bus(
            name=f"Bus {bus_index + 1}",
            idtag=f"measurement-bus-{bus_index + 1}",
            Vnom=110.0,
            is_slack=bus_index == 0,
        )
        for bus_index in range(9)
    )
    bus: Bus
    for bus in buses:
        grid.add_bus(bus)
        initialize_bus_rms(bus=bus, vf=grid.var_factory)

    generator: Generator = Generator(
        name="Nine-bus slack generator",
        idtag="nine-bus-slack-generator",
        P=4.0,
        vset=1.0,
        Snom=100.0,
        x1=0.3,
        r1=0.01,
        freq=50.0,
    )
    grid.add_generator(bus=buses[0], api_obj=generator)
    generator_template: RmsModelTemplate = get_complete_generator_template_rms(
        grid.var_factory,
    )
    line_template: RmsModelTemplate = get_line_rms_template(grid.var_factory)
    load_template: RmsModelTemplate = get_load_rms_template(grid.var_factory)
    grid.add_rms_model(generator_template)
    grid.add_rms_model(line_template)
    grid.add_rms_model(load_template)
    generator.rms_template = generator_template

    branch_index: int
    for branch_index in range(8):
        line: Line = Line(
            name=f"Line {branch_index + 1}-{branch_index + 2}",
            bus_from=buses[branch_index],
            bus_to=buses[branch_index + 1],
            r=0.005,
            x=0.04,
            b=0.01,
            rate=100.0,
        )
        grid.add_line(line)
        line.rms_template = line_template

    load_index: int
    for load_index in range(1, 9):
        load: Load = Load(
            name=f"Load {load_index + 1}",
            P=0.5,
            Q=0.1,
        )
        grid.add_load(bus=buses[load_index], api_obj=load)
        load.rms_template = load_template

    return grid, generator


def _add_scripted_balanced_voltage_meters(
        grid: MultiCircuit,
        generator: Generator,
) -> List[Block]:
    """Add one public canonical balanced-RMS voltage meter per bus.

    :param grid: Nine-bus circuit that owns the bus variables and factory.
    :param generator: Device whose root model owns the measurement blocks.
    :return: Added meter blocks ordered by target bus.
    """
    if isinstance(generator.rms_model, Block):
        generator_model: Block = generator.rms_model
    else:
        raise TypeError("The nine-bus generator must own an RMS model.")

    meters: List[Block] = list()
    meter_index: int
    for meter_index in range(len(grid.buses)):
        measured_bus: Bus = grid.buses[meter_index]
        vm: Var | None = measured_bus.rms_model.external_mapping.get(
            VarPowerFlowReferenceType.Vm,
            None,
        )
        va: Var | None = measured_bus.rms_model.external_mapping.get(
            VarPowerFlowReferenceType.Va,
            None,
        )
        if vm is None or va is None:
            raise ValueError("Every audited AC bus must expose Vm and Va.")
        else:
            pass
        compatibility_outputs: Dict[str, Expr] = (
            build_rms_voltage_meter_outputs_from_polar(
                vm=vm,
                va=va,
                measured_frequency_hz=Const(grid.fBase),
                nominal_frequency_hz=Const(grid.fBase),
            )
        )
        basic_outputs: Dict[str, Expr] = select_basic_balanced_rms_meter_outputs(
            signal_expressions=compatibility_outputs,
            meter_kind=RmsPhysicalMeterKind.VOLTAGE,
        )
        meter_name: str = f"Voltage meter {meter_index + 1}"
        meter_block: Block
        output_by_name: Dict[str, Var]
        meter_block, output_by_name = build_rms_physical_signal_meter_block(
            vf=grid.var_factory,
            signal_expressions=basic_outputs,
            output_signal_names=tuple(basic_outputs.keys()),
            name=meter_name,
            source_fid=(
                "veragrid-meter:"
                + generator.idtag
                + ":voltage:bus:"
                + str(meter_index + 1)
            ),
            target_fid=measured_bus.idtag,
            terminal_side=RmsTerminalSide.BUS,
            meter_kind=RmsPhysicalMeterKind.VOLTAGE,
            symbol_suffix=normalize_rms_meter_symbol_fragment(meter_name),
        )
        del output_by_name
        generator_model.add(meter_block)
        meters.append(meter_block)
    return meters


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
    assert file_open.logger.warning_count() == 0
    return imported_grid


def _assert_nuactis_grid_uses_canonical_public_data(grid: MultiCircuit) -> None:
    """Prove that one imported Nuactis grid contains only canonical model data.

    :param grid: Imported Nuactis circuit to inspect and round-trip.
    :return: None.
    """
    assert not type(grid).__module__.startswith("VeraGridEngine.IO.dgs")

    bus: Bus
    for bus in grid.buses:
        assert not type(bus).__module__.startswith("VeraGridEngine.IO.dgs")
    else:
        pass

    line: Line
    for line in grid.lines:
        assert not type(line).__module__.startswith("VeraGridEngine.IO.dgs")
    else:
        pass

    rms_template: RmsModelTemplate
    for rms_template in grid.rms_models:
        assert not type(rms_template).__module__.startswith("VeraGridEngine.IO.dgs")
        assert not type(rms_template.block).__module__.startswith("VeraGridEngine.IO.dgs")
    else:
        pass

    vsc: VSC
    for vsc in grid.get_vsc():
        assert not type(vsc).__module__.startswith("VeraGridEngine.IO.dgs")
        assert isinstance(vsc.rms_model, Block)

        current_block: Block
        for current_block in vsc.rms_model.get_all_blocks():
            assert not type(current_block).__module__.startswith("VeraGridEngine.IO.dgs")
            assert not type(current_block.dynamic_model_contract).__module__.startswith(
                "VeraGridEngine.IO.dgs"
            )

            contract_data: Dict[str, object] = current_block.dynamic_model_contract.to_data()
            contract_key: str
            contract_value: object
            for contract_key, contract_value in contract_data.items():
                if contract_key.startswith("dgs_"):
                    assert (
                        contract_value is None
                        or contract_value is False
                        or contract_value == list()
                    ), (current_block.name, contract_key, contract_value)
                else:
                    pass

            procedural_entry: object
            for procedural_entry in current_block.procedural_logic:
                assert not type(procedural_entry).__module__.startswith(
                    "VeraGridEngine.IO.dgs"
                )
            else:
                pass
        else:
            pass

        # Reconstruct the entire visible symbolic hierarchy using only the
        # declarative Block contract and its public canonical procedural codec.
        block_data: Dict[str, object] = vsc.rms_model.to_dict()
        restored_block: Block = Block.parse(
            data=block_data,
            procedural_logic_codec=ProceduralLogicCodec(),
        )
        assert restored_block.to_dict() == block_data
        assert _collect_block_semantic_signature(restored_block) == (
            _collect_block_semantic_signature(vsc.rms_model)
        )
    else:
        pass


def _assert_editor_dynamic_check_is_clean(editor: DynamicBlockEditorGUI) -> None:
    """Require the public GUI model-consistency check to report no issues.

    :param editor: Live dynamic editor whose working model must be clean.
    :return: None.
    """
    sections: List[validation.ValidationSection] = (
        editor.collect_model_consistency_sections()
    )
    issue_details: List[str] = list()
    section: validation.ValidationSection
    row: validation.ValidationRow
    detail: str
    for section in sections:
        for row in section.get_rows():
            for detail in row.get_details():
                issue_details.append(
                    section.get_title()
                    + ": "
                    + row.get_block_label()
                    + ": "
                    + detail
                )
            else:
                pass
        else:
            pass
    else:
        pass

    assert issue_details == list(), (
        editor.api_object.name
        + " / "
        + editor.main_block.name
        + "\n"
        + "\n".join(issue_details)
    )


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
        signal_bridge: RmsGuiSignalBridge | None = None,
) -> Tuple[PowerFlowResults, RmsResults, RmsProblemDae]:
    """Run PF and a short RMS trajectory for one Nuactis circuit.

    :param grid: Imported circuit to initialize and integrate.
    :param signal_bridge: Optional real GUI signals attached to the RMS driver.
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
    if signal_bridge is None:
        pass
    else:
        # Match SessionThread, which replaces the engine's DummySignal objects
        # with Qt SignalInstance objects before executing the simulation.
        rms_driver.progress_signal = signal_bridge.progress_signal
        rms_driver.progress_text = signal_bridge.progress_text
    rms_driver.run()
    assert rms_driver.results is not None
    assert rms_driver.problem is not None
    assert rms_driver.logger.error_count() == 0
    assert rms_driver.logger.warning_count() == 0
    return power_flow_results, rms_driver.results, rms_driver.problem


def test_nuactis_v1_rms_qt_signals_keep_vsc_editors_openable(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Reopen both VSC editors after an RMS run driven by real Qt signals.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    signal_bridge: RmsGuiSignalBridge = RmsGuiSignalBridge()
    _power_flow_results: PowerFlowResults
    rms_results: RmsResults
    _rms_problem: RmsProblemDae
    _power_flow_results, rms_results, _rms_problem = _run_nuactis_short_rms(
        grid=grid,
        signal_bridge=signal_bridge,
    )
    assert np.all(rms_results.well_initialized)
    assert np.all(rms_results.converged)

    open_editors: List[DynamicBlockEditorGUI] = list()
    try:
        vsc: VSC
        for vsc in grid.get_vsc():
            assert isinstance(vsc.rms_model, Block)
            editor: DynamicBlockEditorGUI = _build_gui_editor(
                qt_app=qt_app,
                grid=grid,
                api_object=vsc,
                mode=DynamicSimulationMode.RMS,
                root_block=vsc.rms_model,
            )
            open_editors.append(editor)
            _assert_nuactis_vsc_projection(
                editor=editor,
                expected_protected_count=0,
            )
            _assert_editor_dynamic_check_is_clean(editor=editor)
        else:
            pass
    finally:
        editor_to_close: DynamicBlockEditorGUI
        for editor_to_close in open_editors:
            editor_to_close.prepare_to_delete()
            editor_to_close.close()
            editor_to_close.deleteLater()
        else:
            pass
        qt_app.processEvents()


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


def _build_nested_gui_editor(
        qt_app: QtWidgets.QApplication,
        grid: MultiCircuit,
        api_object: DynamicDevice,
        root_block: Block,
        current_block: Block,
) -> DynamicBlockEditorGUI:
    """Build the editor state used after navigating into one nested block.

    :param qt_app: Shared Qt application.
    :param grid: Owning circuit.
    :param api_object: Physical device that owns the complete model.
    :param root_block: Complete assigned device model.
    :param current_block: Nested block selected by the user.
    :return: Live nested editor widget.
    """
    editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
        var_factory=grid.var_factory,
        api_object=api_object,
        circuit=grid,
        current_theme=DynEditorGraphicsModes.LIGHT,
        mode=DynamicSimulationMode.RMS,
        templates_list=list(),
        is_root_editor=False,
        modal=False,
        workspace_embedded=False,
        root_block=root_block,
        current_block=current_block,
    )
    editor.show()
    qt_app.processEvents()
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
        assert not measurement_item.name.startswith("VeraGrid ")
        assert "powerfactory" not in measurement_item.name.lower()
        assert all(
            "powerfactory" not in output_port.base_var.name.lower()
            and "_veragrid" not in output_port.base_var.name.lower()
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
        assert all(
            output_port.connections is not None
            and len(output_port.connections) > 0
            for output_port in selected_output_ports
        ), list(
            output_port.base_var.name
            for output_port in selected_output_ports
            if output_port.connections is None
            or len(output_port.connections) == 0
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
    assert isinstance(measurement_leaves, dict)
    rms_measurement_leaves: object | None = measurement_leaves.get(
        "RMS (balanced)",
        None,
    )
    assert isinstance(rms_measurement_leaves, list)
    assert physical_template in [leaf.payload for leaf in physical_leaves]
    assert governor_template in [leaf.payload for leaf in component_leaves]
    assert bbsex1_template in [leaf.payload for leaf in component_leaves]
    assert measurement_template not in [leaf.payload for leaf in physical_leaves]
    assert measurement_template not in [leaf.payload for leaf in component_leaves]
    assert len(rms_measurement_leaves) == 5
    measurement_descriptors: List[MeasurementBlockDescriptor] = list()
    station_descriptors: List[MeasurementStationDescriptor] = list()
    measurement_leaf: object
    for measurement_leaf in rms_measurement_leaves:
        if isinstance(measurement_leaf.payload, MeasurementBlockDescriptor):
            measurement_descriptors.append(measurement_leaf.payload)
        elif isinstance(measurement_leaf.payload, MeasurementStationDescriptor):
            station_descriptors.append(measurement_leaf.payload)
        else:
            raise AssertionError("Unexpected RMS measurement library payload")
    assert len(measurement_descriptors) == 4
    assert len(station_descriptors) == 1
    assert set(
        descriptor.get_meter_kind() for descriptor in measurement_descriptors
    ) == set(RmsPhysicalMeterKind)
    assert all(
        descriptor.get_terminal_side() is RmsTerminalSide.BUS
        for descriptor in measurement_descriptors
    )
    emt_library: DynamicEditorLibrary = DynamicEditorLibrary(
        api_object=generator,
        mode=DynamicSimulationMode.EMT,
        templates_list=list(),
    )
    emt_measurement_parent: object | None = emt_library.tree_structure.get(
        "Measurements", None
    )
    assert isinstance(emt_measurement_parent, dict)
    emt_measurement_leaves: object | None = emt_measurement_parent.get("EMT", None)
    assert isinstance(emt_measurement_leaves, list)
    assert len(emt_measurement_leaves) == 3
    assert all(
        isinstance(leaf.payload, MeasurementBlockDescriptor)
        and leaf.payload.get_mode() is DynamicSimulationMode.EMT
        for leaf in emt_measurement_leaves
    )

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
        measurement_items: List[graph.GenericBlockItem] = list()
        descriptor_index: int
        descriptor: MeasurementBlockDescriptor
        for descriptor_index, descriptor in enumerate(measurement_descriptors):
            created_measurement_item: graph.GenericBlockItem | None = (
                editor.create_measurements_block_item(
                    descriptor=descriptor,
                    x_pos=600.0 + (300.0 * descriptor_index),
                    y_pos=0.0,
                )
            )
            assert isinstance(created_measurement_item, graph.GenericBlockItem)
            measurement_items.append(created_measurement_item)
        measurement_item: graph.GenericBlockItem = measurement_items[0]
        second_measurement_item: graph.GenericBlockItem | None = (
            editor.create_measurements_block_item(
                descriptor=measurement_descriptors[0],
                x_pos=1800.0,
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
        assert len(measurement_item.subsys.children) == 0
        created_meter_kinds: set[RmsPhysicalMeterKind] = set()
        created_meter_item: graph.GenericBlockItem
        for created_meter_item in measurement_items:
            created_meter_block: Block = created_meter_item.subsys
            measurement_point: RmsPhysicalMeasurementPoint | None = (
                created_meter_block.dynamic_model_contract.rms_physical_measurement_point
            )
            assert measurement_point is not None
            created_meter_kinds.add(measurement_point.get_meter_kind())
            assert len(created_meter_block.algebraic_eqs) == len(
                created_meter_block.out_vars
            )
            assert len(created_meter_block.init_eqs) == len(
                created_meter_block.out_vars
            )
            assert "PowerFactory" not in created_meter_block.name
        assert created_meter_kinds == set(RmsPhysicalMeterKind)

        voltage_meter_item: graph.GenericBlockItem | None = None
        for created_meter_item in measurement_items:
            created_meter_point: RmsPhysicalMeasurementPoint | None = (
                created_meter_item.subsys.dynamic_model_contract.rms_physical_measurement_point
            )
            if (
                    created_meter_point is not None
                    and created_meter_point.get_meter_kind()
                    is RmsPhysicalMeterKind.VOLTAGE
            ):
                voltage_meter_item = created_meter_item
            else:
                pass
        assert voltage_meter_item is not None
        editable_meter_block: Block = voltage_meter_item.subsys
        editor.request_open_block_properties(editable_meter_block)
        assert isinstance(
            editor._block_properties_dialogue,
            DynamicBlockPropertiesDialog,
        )
        measurement_dialogue: DynamicBlockPropertiesDialog = (
            editor._block_properties_dialogue
        )
        power_mode_index: int = measurement_dialogue.ui.measurement_mode_combo.findData(
            RmsPhysicalMeterKind.POWER
        )
        assert power_mode_index >= 0
        measurement_dialogue.ui.measurement_mode_combo.setCurrentIndex(
            power_mode_index
        )
        qt_app.processEvents()
        assert measurement_dialogue.ui.measurement_target_button.isEnabled()
        assert measurement_dialogue.ui.measurement_target_value.text() == (
            generator.name
            + " — BUS terminal → "
            + generator.bus.name
        )
        assert measurement_dialogue.ui.measurement_terminal_value.text() == "BUS"
        assert measurement_dialogue.has_measurement_configuration_changes()

        measurement_dialogue.apply_changes()
        qt_app.processEvents()
        rebuilt_measurement_point: RmsPhysicalMeasurementPoint | None = (
            editable_meter_block.dynamic_model_contract.rms_physical_measurement_point
        )
        assert rebuilt_measurement_point is not None
        assert (
            rebuilt_measurement_point.get_meter_kind()
            is RmsPhysicalMeterKind.POWER
        ), measurement_dialogue._status_label.text()
        assert rebuilt_measurement_point.get_target_fid() == generator.idtag
        assert (
            rebuilt_measurement_point.get_terminal_side()
            is RmsTerminalSide.BUS
        )
        assert len(editable_meter_block.out_vars) == 2
        assert len(editable_meter_block.algebraic_eqs) == 2
        assert len(editable_meter_block.init_eqs) == 2
        assert tuple(output_var.name for output_var in editable_meter_block.out_vars) == (
            rebuilt_measurement_point.get_output_signal_names()
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


def test_native_emt_library_meter_builds_from_the_shared_measurement_parent(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Create one basic EMT meter through the shared measurement descriptor.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit
    generator: Generator
    line: Line
    load: Load
    grid, generator, line, load = _build_two_bus_emt_grid()
    del line
    del load
    generator.emt_template = get_generator_thevenin_rl_emt_template_with_ref(
        vf=grid.var_factory
    )
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=generator,
        mode=DynamicSimulationMode.EMT,
        root_block=generator.emt_model,
    )
    try:
        descriptor: MeasurementBlockDescriptor = MeasurementBlockDescriptor(
            mode=DynamicSimulationMode.EMT,
            meter_kind=RmsPhysicalMeterKind.VOLTAGE,
            terminal_side=RmsTerminalSide.BUS,
        )
        meter_item: graph.GenericBlockItem | None = (
            editor.create_measurements_block_item(descriptor, 0.0, 0.0)
        )
        assert isinstance(meter_item, graph.GenericBlockItem)
        assert meter_item.visual_role is graph.DynamicBlockVisualRole.MEASUREMENT
        assert meter_item.name == "Voltage meter 1"
        assert len(meter_item.subsys.out_vars) >= 3
        assert all(
            "veragrid" not in output_var.name.lower()
            for output_var in meter_item.subsys.out_vars
        )
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


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


def test_gui_editor_apply_changes_matches_scripting_for_rms(
        qt_app: QtWidgets.QApplication,
) -> None:
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
    _assert_nuactis_grid_uses_canonical_public_data(grid=script_grid)

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
            _assert_editor_dynamic_check_is_clean(editor=editor)
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
    assert np.max(np.abs(script_rms_results.values - gui_rms_results.values)) < 1e-6
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
            "P_act_Power meter 221Slave_PWM_nl",
            "Q_act_Power meter 221Slave_PWM_nl",
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
    assert np.max(np.abs(script_selected_values - gui_selected_values)) < 1e-6

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
    assert np.max(powerfactory_difference) < 1e-6, (
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
    assert np.max(limit_powerfactory_difference) < 1e-6, (
        np.unravel_index(
            np.argmax(limit_powerfactory_difference),
            limit_powerfactory_difference.shape,
        ),
        float(np.max(limit_powerfactory_difference)),
    )


def test_native_voltage_meter_can_release_and_select_another_bus(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Rebuild a native meter against a bus selected from the circuit database.

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
    editor_root: Block = Block(
        name="Generator remote measurement model",
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
        descriptor: MeasurementBlockDescriptor = MeasurementBlockDescriptor(
            mode=DynamicSimulationMode.RMS,
            meter_kind=RmsPhysicalMeterKind.VOLTAGE,
            terminal_side=RmsTerminalSide.BUS,
        )
        meter_item: graph.GenericBlockItem | None = (
            editor.create_measurements_block_item(descriptor, 0.0, 0.0)
        )
        assert isinstance(meter_item, graph.GenericBlockItem)
        meter_block: Block = meter_item.subsys
        editor.request_open_block_properties(meter_block)
        assert isinstance(
            editor._block_properties_dialogue,
            DynamicBlockPropertiesDialog,
        )
        dialogue: DynamicBlockPropertiesDialog = editor._block_properties_dialogue
        voltage_options: List[RmsMeasurementEditOption] = list()
        option: RmsMeasurementEditOption
        for option in editor.build_rms_measurement_edit_options(meter_block):
            if option.get_meter_kind() is RmsPhysicalMeterKind.VOLTAGE:
                voltage_options.append(option)
            else:
                pass
        assert set(option.get_target_fid() for option in voltage_options) == set(
            bus.idtag for bus in grid.buses
        )
        remote_bus: Bus = grid.buses[1]
        remote_option: RmsMeasurementEditOption | None = None
        for option in voltage_options:
            if option.get_target_fid() == remote_bus.idtag:
                remote_option = option
            else:
                pass
        assert remote_option is not None

        dialogue.release_measurement_target()
        assert dialogue.get_selected_measurement_option() is None
        assert dialogue.select_measurement_target_option(remote_option)
        assert remote_bus.name in dialogue.ui.measurement_target_value.text()
        dialogue.apply_changes()
        qt_app.processEvents()

        rebuilt_point: RmsPhysicalMeasurementPoint | None = (
            meter_block.dynamic_model_contract.rms_physical_measurement_point
        )
        assert rebuilt_point is not None
        assert rebuilt_point.get_target_fid() == remote_bus.idtag
        validate_dynamic_model_contract(block=meter_block)
        remote_voltage_uids: set[int] = set(
            mapped_var.uid
            for mapped_var in remote_bus.rms_model.external_mapping.values()
            if mapped_var is not None
        )
        equation_var_uids: set[int] = set()
        equation: Expr
        equation_var: Var
        for equation in meter_block.algebraic_eqs:
            for equation_var in equation.get_vars():
                equation_var_uids.add(equation_var.uid)
        assert len(remote_voltage_uids.intersection(equation_var_uids)) > 0
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


def test_measurement_target_picker_searches_and_pages_five_hundred_devices(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Keep the consolidated target selector bounded for a large network.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    target_count: int = 525
    options: List[RmsMeasurementEditOption] = list(
        RmsMeasurementEditOption(
            meter_kind=RmsPhysicalMeterKind.CURRENT,
            source_terminal_side=RmsTerminalSide.FROM,
            target_fid=f"measurement-target-{target_index:04d}",
            target_label=f"Branch device {target_index:04d} — FROM terminal",
        )
        for target_index in range(target_count)
    )
    selected_option: RmsMeasurementEditOption = options[520]
    picker: MeasurementTargetPickerDialog = MeasurementTargetPickerDialog(
        options=options,
        selected_option=selected_option,
    )
    try:
        picker.show()
        qt_app.processEvents()
        assert picker._current_page == 5
        assert picker._source_model.rowCount() == 25
        assert "525 targets" in picker._page_label.text()
        assert picker._previous_page_button.isEnabled()
        assert not picker._next_page_button.isEnabled()
        assert picker.get_selected_option() is selected_option

        picker.show_previous_page()
        assert picker._current_page == 4
        assert picker._source_model.rowCount() == 100
        assert picker._next_page_button.isEnabled()

        picker.filter_targets("measurement-target-0499")
        assert picker._current_page == 0
        assert picker._source_model.rowCount() == 1
        searched_option: RmsMeasurementEditOption | None = (
            picker.get_selected_option()
        )
        assert searched_option is options[499]
        assert "1 targets" in picker._page_label.text()
        assert not picker._previous_page_button.isEnabled()
        assert not picker._next_page_button.isEnabled()
    finally:
        picker.close()
        picker.deleteLater()
        qt_app.processEvents()


def test_native_current_meter_can_select_a_remote_branch_terminal(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Rebuild a meter against a branch outside the owning device model.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit
    generator: Generator
    remote_line: Line
    load: Load
    grid, generator, remote_line, load = _build_two_bus_rms_grid()
    del load
    generator_template: RmsModelTemplate = get_genrow_rms_template(
        grid.var_factory,
        name="Generator basic",
    )
    remote_line.rms_template = get_line_rms_template(grid.var_factory)
    editor_root: Block = Block(
        name="Generator remote current measurement model",
        external_mapping=dict(generator_template.block.external_mapping),
    )
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=generator,
        mode=DynamicSimulationMode.RMS,
        root_block=editor_root,
    )
    try:
        descriptor: MeasurementBlockDescriptor = MeasurementBlockDescriptor(
            mode=DynamicSimulationMode.RMS,
            meter_kind=RmsPhysicalMeterKind.CURRENT,
            terminal_side=RmsTerminalSide.BUS,
        )
        meter_item: graph.GenericBlockItem | None = (
            editor.create_measurements_block_item(descriptor, 0.0, 0.0)
        )
        assert isinstance(meter_item, graph.GenericBlockItem)
        meter_block: Block = meter_item.subsys
        current_options: List[RmsMeasurementEditOption] = list()
        option: RmsMeasurementEditOption
        for option in editor.build_rms_measurement_edit_options(meter_block):
            if option.get_meter_kind() is RmsPhysicalMeterKind.CURRENT:
                current_options.append(option)
            else:
                pass
        remote_from_option: RmsMeasurementEditOption | None = None
        for option in current_options:
            if (
                    option.get_target_fid() == remote_line.idtag
                    and option.get_source_terminal_side()
                    is RmsTerminalSide.FROM
            ):
                remote_from_option = option
            else:
                pass
        assert remote_from_option is not None

        editor.request_open_block_properties(meter_block)
        assert isinstance(
            editor._block_properties_dialogue,
            DynamicBlockPropertiesDialog,
        )
        dialogue: DynamicBlockPropertiesDialog = editor._block_properties_dialogue
        assert dialogue.select_measurement_target_option(remote_from_option)
        dialogue.apply_changes()
        qt_app.processEvents()

        rebuilt_point: RmsPhysicalMeasurementPoint | None = (
            meter_block.dynamic_model_contract.rms_physical_measurement_point
        )
        assert rebuilt_point is not None
        assert rebuilt_point.get_target_fid() == remote_line.idtag
        assert rebuilt_point.get_terminal_side() is RmsTerminalSide.FROM
        remote_line_var_uids: set[int] = set(
            mapped_var.uid
            for mapped_var in remote_line.rms_model.external_mapping.values()
            if mapped_var is not None
        )
        equation_var_uids: set[int] = set()
        equation: Expr
        equation_var: Var
        for equation in meter_block.algebraic_eqs:
            for equation_var in equation.get_vars():
                equation_var_uids.add(equation_var.uid)
        assert len(remote_line_var_uids.intersection(equation_var_uids)) > 0
        validate_dynamic_model_contract(block=meter_block)
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


def test_nine_bus_balanced_rms_measurements_match_gui_and_scripting(
        qt_app: QtWidgets.QApplication,
        tmp_path: Path,
) -> None:
    """Audit nine searchable bus targets through GUI and public scripting APIs.

    The balanced RMS solver owns only positive-sequence magnitude and angle.
    The test therefore also proves that native basic meters do not expose
    negative- or zero-sequence channels while retaining exact target-variable
    connections through GUI persistence and RMS compilation.

    :param qt_app: Shared Qt application fixture.
    :param tmp_path: Isolated path for the declarative save/reopen cycle.
    :return: None.
    """
    script_grid: MultiCircuit
    script_generator: Generator
    gui_grid: MultiCircuit
    gui_generator: Generator
    script_grid, script_generator = _build_nine_bus_rms_measurement_grid()
    gui_grid, gui_generator = _build_nine_bus_rms_measurement_grid()
    script_meters: List[Block] = _add_scripted_balanced_voltage_meters(
        grid=script_grid,
        generator=script_generator,
    )
    assert isinstance(gui_generator.rms_model, Block)
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=gui_grid,
        api_object=gui_generator,
        mode=DynamicSimulationMode.RMS,
        root_block=gui_generator.rms_model,
    )
    forbidden_sequence_names: set[str] = set((
        "u2r", "u2i", "u2", "u0r", "u0i", "u0",
        "i2r", "i2i", "i2", "i0r", "i0i", "i0",
        "p2", "q2", "p0", "q0",
    ))
    gui_meters: List[Block] = list()
    try:
        descriptor: MeasurementBlockDescriptor = MeasurementBlockDescriptor(
            mode=DynamicSimulationMode.RMS,
            meter_kind=RmsPhysicalMeterKind.VOLTAGE,
            terminal_side=RmsTerminalSide.BUS,
        )
        meter_index: int
        for meter_index in range(len(gui_grid.buses)):
            meter_item: graph.GenericBlockItem | None = (
                editor.create_measurements_block_item(
                    descriptor=descriptor,
                    x_pos=float(260 * (meter_index % 3)),
                    y_pos=float(180 * (meter_index // 3)),
                )
            )
            assert isinstance(meter_item, graph.GenericBlockItem)
            meter_block: Block = meter_item.subsys
            editor.request_open_block_properties(meter_block)
            assert isinstance(
                editor._block_properties_dialogue,
                DynamicBlockPropertiesDialog,
            )
            dialogue: DynamicBlockPropertiesDialog = editor._block_properties_dialogue
            voltage_options: List[RmsMeasurementEditOption] = list()
            option: RmsMeasurementEditOption
            for option in editor.build_rms_measurement_edit_options(meter_block):
                if option.get_meter_kind() is RmsPhysicalMeterKind.VOLTAGE:
                    voltage_options.append(option)
                else:
                    pass
            assert len(voltage_options) == 9
            assert len(set(
                option.get_target_fid() for option in voltage_options
            )) == 9
            target_bus: Bus = gui_grid.buses[meter_index]
            target_option: RmsMeasurementEditOption | None = None
            for option in voltage_options:
                if option.get_target_fid() == target_bus.idtag:
                    target_option = option
                else:
                    pass
            assert target_option is not None

            if meter_index == 8:
                picker: MeasurementTargetPickerDialog = (
                    MeasurementTargetPickerDialog(
                        options=voltage_options,
                        selected_option=None,
                        parent=dialogue,
                    )
                )
                picker.filter_targets("Bus 9")
                searched_option: RmsMeasurementEditOption | None = (
                    picker.get_selected_option()
                )
                assert searched_option is not None
                assert searched_option.get_target_fid() == target_bus.idtag
                picker.close()
            else:
                pass

            dialogue.release_measurement_target()
            assert dialogue.select_measurement_target_option(target_option)
            dialogue.apply_changes()
            qt_app.processEvents()
            editor.close_block_properties_dock()
            measurement_point: RmsPhysicalMeasurementPoint | None = (
                meter_block.dynamic_model_contract.rms_physical_measurement_point
            )
            assert measurement_point is not None
            assert measurement_point.get_target_fid() == target_bus.idtag
            assert len(meter_block.out_vars) == 5
            assert all(
                output_var.name.split("_", 1)[0] not in forbidden_sequence_names
                for output_var in meter_block.out_vars
            )

            target_voltage_uids: set[int] = set(
                target_var.uid
                for target_var in target_bus.rms_model.external_mapping.values()
                if target_var is not None
            )
            equation_source_uids: set[int] = set()
            equation: Expr
            equation_var: Var
            for equation in meter_block.algebraic_eqs:
                for equation_var in equation.get_vars():
                    if equation_var.uid not in measurement_point.get_output_var_uids():
                        equation_source_uids.add(equation_var.uid)
                    else:
                        pass
            assert len(target_voltage_uids.intersection(equation_source_uids)) > 0
            restored_meter: Block = Block.parse(
                data=meter_block.to_dict(),
                procedural_logic_codec=ProceduralLogicCodec(),
            )
            assert restored_meter.to_dict() == meter_block.to_dict()
            gui_meters.append(meter_block)

        _assert_editor_dynamic_check_is_clean(editor=editor)
        editor.apply_changes()
        qt_app.processEvents()
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()

    assert len(script_meters) == len(gui_meters) == 9
    script_meter: Block
    gui_meter: Block
    for script_meter, gui_meter in zip(script_meters, gui_meters):
        script_point: RmsPhysicalMeasurementPoint | None = (
            script_meter.dynamic_model_contract.rms_physical_measurement_point
        )
        gui_point: RmsPhysicalMeasurementPoint | None = (
            gui_meter.dynamic_model_contract.rms_physical_measurement_point
        )
        assert script_point is not None
        assert gui_point is not None
        assert script_meter.name == gui_meter.name
        assert script_point.get_source_fid() == gui_point.get_source_fid()
        assert script_point.get_target_fid() == gui_point.get_target_fid()
        assert script_point.get_meter_kind() is gui_point.get_meter_kind()
        assert script_point.get_terminal_side() is gui_point.get_terminal_side()
        assert list(
            output_var.name for output_var in script_meter.out_vars
        ) == list(output_var.name for output_var in gui_meter.out_vars)
        assert list(
            symbolic_to_string(equation) for equation in script_meter.algebraic_eqs
        ) == list(
            symbolic_to_string(equation) for equation in gui_meter.algebraic_eqs
        )

    script_bus_branches: Dict[Bus, List[Any]] = script_grid.get_bus_branch_dict()
    gui_bus_branches: Dict[Bus, List[Any]] = gui_grid.get_bus_branch_dict()
    assert list(
        len(script_bus_branches[bus]) for bus in script_grid.buses
    ) == list((1, 2, 2, 2, 2, 2, 2, 2, 1))
    assert list(
        len(gui_bus_branches[bus]) for bus in gui_grid.buses
    ) == list((1, 2, 2, 2, 2, 2, 2, 2, 1))

    script_results: RmsResults
    script_problem: RmsProblemDae
    gui_results: RmsResults
    gui_problem: RmsProblemDae
    script_results, script_problem = _run_rms_driver(script_grid)
    gui_results, gui_problem = _run_rms_driver(gui_grid)
    assert script_problem.get_states_number() == gui_problem.get_states_number()
    assert script_problem.get_algebraic_var_number() == gui_problem.get_algebraic_var_number()
    assert list(script_results.variable_array) == list(gui_results.variable_array)
    assert np.array_equal(script_results.well_initialized, gui_results.well_initialized)
    assert np.array_equal(script_results.converged, gui_results.converged)
    assert np.all(script_results.well_initialized)
    assert np.all(script_results.converged)
    assert np.allclose(script_results.values, gui_results.values, rtol=1e-8, atol=1e-8)

    # Persist the public circuit and reopen it through the production file path.
    saved_file_path: Path = tmp_path / "nine_bus_balanced_measurements.veragrid"
    save_logger: Logger = FileSave(
        circuit=gui_grid,
        file_name=str(saved_file_path),
    ).save()
    assert save_logger.error_count() == 0
    assert save_logger.warning_count() == 0

    reopened_file: FileOpen = FileOpen(file_name=str(saved_file_path))
    reopened_grid: MultiCircuit | None = reopened_file.open()
    assert reopened_grid is not None
    assert reopened_file.logger.error_count() == 0, str(reopened_file.logger)
    assert reopened_file.logger.warning_count() == 0, str(reopened_file.logger)
    reopened_generators: List[Generator] = reopened_grid.get_generators()
    assert len(reopened_generators) == 1
    reopened_generator: Generator = reopened_generators[0]
    assert isinstance(reopened_generator.rms_model, Block)
    reopened_meters: List[Block] = list(
        child for child in reopened_generator.rms_model.children
        if child.dynamic_model_contract.rms_physical_measurement_point is not None
    )
    assert len(reopened_meters) == 9
    assert list(
        meter.dynamic_model_contract.rms_physical_measurement_point.get_target_fid()
        for meter in reopened_meters
        if meter.dynamic_model_contract.rms_physical_measurement_point is not None
    ) == list(bus.idtag for bus in reopened_grid.buses)
    assert list(meter.to_dict() for meter in reopened_meters) == list(
        meter.to_dict() for meter in gui_meters
    )

    # Reopen the RMS editor and public checker on the reconstructed objects.
    reopened_editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=reopened_grid,
        api_object=reopened_generator,
        mode=DynamicSimulationMode.RMS,
        root_block=reopened_generator.rms_model,
    )
    try:
        _assert_editor_dynamic_check_is_clean(editor=reopened_editor)
        reopened_editor.apply_changes()
        qt_app.processEvents()
    finally:
        reopened_editor.prepare_to_delete()
        reopened_editor.close()
        reopened_editor.deleteLater()
        qt_app.processEvents()

    # The round-tripped declaration must compile and solve identically.
    reopened_results: RmsResults
    reopened_problem: RmsProblemDae
    reopened_results, reopened_problem = _run_rms_driver(reopened_grid)
    assert reopened_problem.get_states_number() == gui_problem.get_states_number()
    assert reopened_problem.get_algebraic_var_number() == (
        gui_problem.get_algebraic_var_number()
    )
    assert list(reopened_results.variable_array) == list(gui_results.variable_array)
    assert np.array_equal(reopened_results.well_initialized, gui_results.well_initialized)
    assert np.array_equal(reopened_results.converged, gui_results.converged)
    assert np.allclose(reopened_results.values, gui_results.values, rtol=1e-8, atol=1e-8)


def test_nuactis_all_rms_equipment_editors_are_populated_connected_and_clean(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Open every imported RMS equipment model, not only both converters.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    fixture_names: tuple[str, ...] = (
        "hvdc_vsc_v1_complete_static_dynamic.dgs",
        "hvdc_vsc_v2_complete_static_dynamic.dgs",
    )
    fixture_name: str
    for fixture_name in fixture_names:
        grid: MultiCircuit = _load_nuactis_rms_grid(fixture_name=fixture_name)
        equipment_collections: tuple[Sequence[DynamicDevice], ...] = (
            grid.get_generators(),
            grid.get_loads(),
            grid.get_lines(),
            grid.get_transformers2w(),
            grid.get_vsc(),
        )
        equipment_collection: Sequence[DynamicDevice]
        api_object: DynamicDevice
        for equipment_collection in equipment_collections:
            for api_object in equipment_collection:
                assert isinstance(api_object.rms_model, Block), api_object.name
                editor: DynamicBlockEditorGUI = _build_gui_editor(
                    qt_app=qt_app,
                    grid=grid,
                    api_object=api_object,
                    mode=DynamicSimulationMode.RMS,
                    root_block=api_object.rms_model,
                )
                try:
                    physical_items: List[graph.GenericBlockItem] = list(
                        scene_item for scene_item in editor.scene.items()
                        if isinstance(scene_item, graph.GenericBlockItem)
                        and scene_item.visual_role
                        is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
                    )
                    assert len(physical_items) == 1, (
                        fixture_name,
                        type(api_object).__name__,
                        api_object.name,
                    )
                    physical_item: graph.GenericBlockItem = physical_items[0]
                    assert all(
                        port.connections is not None and len(port.connections) > 0
                        for port in physical_item.inputs
                    ), (
                        fixture_name,
                        api_object.name,
                        list(
                            port.base_var.name for port in physical_item.inputs
                            if port.connections is None or len(port.connections) == 0
                        ),
                    )
                    _assert_editor_dynamic_check_is_clean(editor=editor)
                finally:
                    editor.prepare_to_delete()
                    editor.close()
                    editor.deleteLater()
                    qt_app.processEvents()

                nested_block: Block
                for nested_block in api_object.rms_model.get_all_blocks():
                    if (
                            nested_block is api_object.rms_model
                            or get_single_interface_var(nested_block) is not None
                            or (
                                not block_has_internal_equation_content(nested_block)
                                and len(nested_block.children) == 0
                                and len(nested_block.in_vars)
                                + len(nested_block.out_vars) == 1
                            )
                            or is_root_interface_wrapper_block(
                                block_model=nested_block,
                                diagram=api_object.rms_model.diagram,
                            )
                    ):
                        pass
                    else:
                        nested_editor: DynamicBlockEditorGUI = (
                            _build_nested_gui_editor(
                                qt_app=qt_app,
                                grid=grid,
                                api_object=api_object,
                                root_block=api_object.rms_model,
                                current_block=nested_block,
                            )
                        )
                        try:
                            assert len(nested_editor.scene.items()) > 0, (
                                fixture_name,
                                api_object.name,
                                nested_block.name,
                            )
                            _assert_editor_dynamic_check_is_clean(
                                editor=nested_editor,
                            )
                        finally:
                            nested_editor.prepare_to_delete()
                            nested_editor.close()
                            nested_editor.deleteLater()
                    qt_app.processEvents()


def test_nuactis_v1_real_workspace_route_preserves_physical_projections(
        qt_app: QtWidgets.QApplication,
        tmp_path: Path,
) -> None:
    """Open V1 equipment through the same workspace route used by VeraGrid.

    This regression deliberately does not instantiate the block editor
    directly. It exercises the document copy, root preparation, workspace tab,
    and embedded editor that the network context-menu action reaches.

    :param qt_app: Shared Qt application fixture.
    :param tmp_path: Isolated directory for minimized-workspace captures.
    :return: None.
    """
    grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    session: DynamicEditorWorkspaceSession = DynamicEditorWorkspaceSession()
    workspace: DynamicEditorWorkspaceWindow = DynamicEditorWorkspaceWindow(
        session=session,
    )
    workspace.resize(1920, 1080)
    workspace.showMinimized()
    qt_app.processEvents()
    opened_editors: List[DynamicBlockEditorGUI] = list()
    capture_index: int = 0

    equipment_collections: tuple[Sequence[DynamicDevice], ...] = (
        grid.get_generators(),
        grid.get_loads(),
        grid.get_lines(),
        grid.get_transformers2w(),
        grid.get_vsc(),
    )
    equipment_collection: Sequence[DynamicDevice]
    api_object: DynamicDevice

    try:
        for equipment_collection in equipment_collections:
            for api_object in equipment_collection:
                page: DynamicEditorTab | None = workspace.open_dynamic_editor_for(
                    api_object=api_object,
                    circuit=grid,
                    preferred_mode=DynamicSimulationMode.RMS,
                )
                assert isinstance(page, DynamicEditorTab)
                editor: DynamicBlockEditorGUI | None = page.editor
                assert isinstance(editor, DynamicBlockEditorGUI)
                opened_editors.append(editor)
                qt_app.processEvents()
                assert not editor.has_unapplied_changes, api_object.name

                physical_items: List[graph.GenericBlockItem] = list(
                    scene_item for scene_item in editor.scene.items()
                    if isinstance(scene_item, graph.GenericBlockItem)
                    and scene_item.visual_role
                    is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
                )
                measurement_items: List[graph.GenericBlockItem] = list(
                    scene_item for scene_item in editor.scene.items()
                    if isinstance(scene_item, graph.GenericBlockItem)
                    and scene_item.visual_role
                    is graph.DynamicBlockVisualRole.MEASUREMENT
                )
                assert len(physical_items) == 1, api_object.name
                assert len(measurement_items) >= 1, api_object.name
                physical_ports: List[graph.PortItem] = (
                    list(physical_items[0].inputs)
                    + list(physical_items[0].outputs)
                )
                required_physical_refs: set[VarPowerFlowReferenceType] = set(
                    measurement_port.base_var.ref
                    for measurement_item in measurement_items
                    for measurement_port in measurement_item.outputs
                    if isinstance(
                        measurement_port.base_var.ref,
                        VarPowerFlowReferenceType,
                    )
                )
                assert all(
                    port.connections is not None
                    and len(port.connections) > 0
                    for port in physical_ports
                    if port.base_var.ref in required_physical_refs
                ), (
                    api_object.name,
                    list(
                        port.base_var.name for port in physical_ports
                        if port.connections is None or len(port.connections) == 0
                    ),
                )
                _assert_editor_dynamic_check_is_clean(editor=editor)

                # ``QWidget.grab`` renders the complete child editor even while
                # its workspace stays minimized. This provides one auditable
                # image per device without stealing focus from the desktop.
                editor.setFixedSize(1600, 1000)
                editor.view.center_items()
                qt_app.processEvents()
                capture_index += 1
                capture_path: Path = tmp_path / (
                    f"{capture_index:02d}_{type(api_object).__name__}.png"
                )
                capture_pixmap: QtGui.QPixmap = editor.grab()
                assert not capture_pixmap.isNull(), api_object.name
                assert capture_pixmap.width() == 1600, api_object.name
                assert capture_pixmap.height() == 1000, api_object.name
                assert capture_pixmap.save(str(capture_path), "PNG"), capture_path
                assert capture_path.stat().st_size > 0, capture_path
                print(str(capture_path), api_object.name)
                editor.setMinimumSize(0, 0)
                editor.setMaximumSize(16777215, 16777215)

                if (
                        isinstance(api_object, Generator)
                        and api_object.name
                        in ("External Grid A", "External Grid B")
                ):
                    thevenin_template_names: List[str] = list(
                        rms_template.name
                        for rms_template in editor.templates_list
                        if rms_template.name
                        == "DGS external grid Thevenin RMS shell"
                    )
                    assert thevenin_template_names == list((
                        "DGS external grid Thevenin RMS shell",
                    ))
                else:
                    pass
        assert capture_index == 11
    finally:
        opened_editor: DynamicBlockEditorGUI
        for opened_editor in opened_editors:
            opened_editor.has_unapplied_changes = False
        session.reset_for_tests()
        qt_app.processEvents()


def test_nuactis_v1_captures_every_rms_equipment_editor(
        qt_app: QtWidgets.QApplication,
        tmp_path: Path,
) -> None:
    """Capture one auditable GUI image for every Nuactis V1 RMS device.

    Each image is taken from the real editor window after its complete scene is
    fitted into view. Structural assertions run before capture so an image can
    never be accepted merely because a blank window rendered successfully.

    :param qt_app: Shared Qt application fixture.
    :param tmp_path: Isolated persistent artifact directory selected by pytest.
    :return: None.
    """
    grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    ideal_transformer_templates: List[RmsModelTemplate] = list(
        rms_template for rms_template in grid.rms_models
        if rms_template.tpe is DeviceType.Transformer2WDevice
        and rms_template.name == "rms_ideal_trafo_template"
    )
    assert len(ideal_transformer_templates) == 1
    transformer_device: DynamicDevice
    for transformer_device in grid.get_transformers2w():
        assert transformer_device.rms_template is ideal_transformer_templates[0]
    else:
        pass
    equipment_collections: tuple[Sequence[DynamicDevice], ...] = (
        grid.get_generators(),
        grid.get_loads(),
        grid.get_lines(),
        grid.get_transformers2w(),
        grid.get_vsc(),
    )
    capture_index: int = 0
    equipment_collection: Sequence[DynamicDevice]
    api_object: DynamicDevice
    for equipment_collection in equipment_collections:
        for api_object in equipment_collection:
            assert isinstance(api_object.rms_model, Block), api_object.name
            editor: DynamicBlockEditorGUI = _build_gui_editor(
                qt_app=qt_app,
                grid=grid,
                api_object=api_object,
                mode=DynamicSimulationMode.RMS,
                root_block=api_object.rms_model,
            )
            try:
                _assert_editor_dynamic_check_is_clean(editor=editor)
                physical_items: List[graph.GenericBlockItem] = list(
                    scene_item for scene_item in editor.scene.items()
                    if isinstance(scene_item, graph.GenericBlockItem)
                    and scene_item.visual_role
                    is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
                )
                assert len(physical_items) == 1, api_object.name
                assert all(
                    input_port.connections is not None
                    and len(input_port.connections) > 0
                    for input_port in physical_items[0].inputs
                ), api_object.name
                measurement_items: List[graph.GenericBlockItem] = list(
                    scene_item for scene_item in editor.scene.items()
                    if isinstance(scene_item, graph.GenericBlockItem)
                    and scene_item.visual_role
                    is graph.DynamicBlockVisualRole.MEASUREMENT
                )
                if isinstance(api_object, Generator):
                    assert len(measurement_items) == 1, api_object.name
                    device_library: DynamicEditorLibrary = DynamicEditorLibrary(
                        api_object=api_object,
                        mode=DynamicSimulationMode.RMS,
                        templates_list=list(),
                    )
                    measurement_parent: object | None = (
                        device_library.tree_structure.get("Measurements", None)
                    )
                    assert isinstance(measurement_parent, dict)
                    consolidated_measurements: object | None = (
                        measurement_parent.get("RMS (balanced)", None)
                    )
                    assert isinstance(consolidated_measurements, list)
                    assert len(consolidated_measurements) == 5
                else:
                    pass
                assert len(editor.scene.items()) > 0, api_object.name

                # Use a stable large viewport and fit the complete scene so the
                # artifact shows all blocks and wires of this device at once.
                editor.resize(1600, 1000)
                editor.view.center_items()
                qt_app.processEvents()
                capture_index += 1
                capture_path: Path = tmp_path / (
                    f"{capture_index:02d}_{type(api_object).__name__}.png"
                )
                capture_pixmap: QtGui.QPixmap = editor.grab()
                assert not capture_pixmap.isNull(), api_object.name
                assert capture_pixmap.save(str(capture_path), "PNG"), capture_path
                assert capture_path.stat().st_size > 0, capture_path
                print(str(capture_path), api_object.name)
            finally:
                editor.prepare_to_delete()
                editor.close()
                editor.deleteLater()
                qt_app.processEvents()
    assert capture_index == sum(
        len(equipment_collection)
        for equipment_collection in equipment_collections
    )


def test_nuactis_v1_v2_save_reopen_preserves_models_and_visible_connections(
        qt_app: QtWidgets.QApplication,
        tmp_path: Path,
) -> None:
    """Persist both Nuactis revisions and reopen their complete RMS editors.

    :param qt_app: Shared Qt application fixture.
    :param tmp_path: Isolated path for both declarative VeraGrid archives.
    :return: None.
    """
    fixture_names: tuple[str, ...] = (
        "hvdc_vsc_v1_complete_static_dynamic.dgs",
        "hvdc_vsc_v2_complete_static_dynamic.dgs",
    )
    fixture_name: str
    for fixture_name in fixture_names:
        original_grid: MultiCircuit = _load_nuactis_rms_grid(
            fixture_name=fixture_name,
        )
        original_vsc_devices: List[VSC] = original_grid.get_vsc()
        original_signatures: List[Dict[str, Any]] = list(
            _collect_block_semantic_signature(vsc.rms_model)
            for vsc in original_vsc_devices
            if isinstance(vsc.rms_model, Block)
        )
        assert len(original_signatures) == len(original_vsc_devices)

        saved_file_path: Path = tmp_path / (Path(fixture_name).stem + ".veragrid")
        save_logger: Logger = FileSave(
            circuit=original_grid,
            file_name=str(saved_file_path),
        ).save()
        assert save_logger.error_count() == 0
        assert save_logger.warning_count() == 0

        reopened_file: FileOpen = FileOpen(file_name=str(saved_file_path))
        reopened_grid: MultiCircuit | None = reopened_file.open()
        assert reopened_grid is not None
        assert reopened_file.logger.error_count() == 0, (
            reopened_file.logger.to_df().to_string()
        )
        assert reopened_file.logger.warning_count() == 0, (
            reopened_file.logger.to_df().to_string()
        )
        _assert_nuactis_grid_uses_canonical_public_data(grid=reopened_grid)
        reopened_vsc_devices: List[VSC] = reopened_grid.get_vsc()
        assert len(reopened_vsc_devices) == len(original_vsc_devices)

        converter_index: int
        for converter_index in range(len(reopened_vsc_devices)):
            reopened_vsc: VSC = reopened_vsc_devices[converter_index]
            assert isinstance(reopened_vsc.rms_model, Block)
            assert _collect_block_semantic_signature(reopened_vsc.rms_model) == (
                original_signatures[converter_index]
            )
            reopened_editor: DynamicBlockEditorGUI = _build_gui_editor(
                qt_app=qt_app,
                grid=reopened_grid,
                api_object=reopened_vsc,
                mode=DynamicSimulationMode.RMS,
                root_block=reopened_vsc.rms_model,
            )
            try:
                _assert_nuactis_vsc_projection(
                    editor=reopened_editor,
                    expected_protected_count=0,
                )
                _assert_editor_dynamic_check_is_clean(editor=reopened_editor)
            finally:
                reopened_editor.prepare_to_delete()
                reopened_editor.close()
                reopened_editor.deleteLater()
                qt_app.processEvents()

        original_results: RmsResults
        original_problem: RmsProblemDae
        reopened_results: RmsResults
        reopened_problem: RmsProblemDae
        original_results, original_problem = _run_rms_driver(original_grid)
        reopened_results, reopened_problem = _run_rms_driver(reopened_grid)
        assert original_problem.get_states_number() == reopened_problem.get_states_number()
        assert original_problem.get_algebraic_var_number() == (
            reopened_problem.get_algebraic_var_number()
        )
        assert list(original_results.variable_array) == list(
            reopened_results.variable_array
        )
        assert np.array_equal(
            original_results.well_initialized,
            reopened_results.well_initialized,
        )
        assert np.array_equal(original_results.converged, reopened_results.converged)
        assert np.allclose(
            original_results.values,
            reopened_results.values,
            rtol=1e-8,
            atol=1e-8,
        )


def test_nuactis_v2_imported_meter_rebuilds_to_native_branch_terminal(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Replace one historical imported meter through the native `.ui` path.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v2_complete_static_dynamic.dgs",
    )
    vsc: VSC = grid.get_vsc()[0]
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=vsc,
        mode=DynamicSimulationMode.RMS,
        root_block=vsc.rms_model,
    )
    try:
        voltage_meter_block: Block | None = None
        scene_item: QtWidgets.QGraphicsItem
        for scene_item in editor.scene.items():
            if (
                    isinstance(scene_item, graph.GenericBlockItem)
                    and scene_item.visual_role
                    is graph.DynamicBlockVisualRole.MEASUREMENT
            ):
                measurement_point: RmsPhysicalMeasurementPoint | None = (
                    scene_item.subsys.dynamic_model_contract.rms_physical_measurement_point
                )
                if (
                        measurement_point is not None
                        and measurement_point.get_meter_kind()
                        is RmsPhysicalMeterKind.VOLTAGE
                ):
                    voltage_meter_block = scene_item.subsys
                else:
                    pass
            else:
                pass
        assert voltage_meter_block is not None
        assert any(
            not output_var.name.isidentifier()
            for output_var in voltage_meter_block.out_vars
        )

        editor.request_open_block_properties(voltage_meter_block)
        assert isinstance(
            editor._block_properties_dialogue,
            DynamicBlockPropertiesDialog,
        )
        measurement_dialogue: DynamicBlockPropertiesDialog = (
            editor._block_properties_dialogue
        )
        power_mode_index: int = measurement_dialogue.ui.measurement_mode_combo.findData(
            RmsPhysicalMeterKind.POWER
        )
        assert power_mode_index >= 0
        measurement_dialogue.ui.measurement_mode_combo.setCurrentIndex(
            power_mode_index
        )
        qt_app.processEvents()
        assert vsc.bus_from is not None
        assert measurement_dialogue.ui.measurement_target_value.text() == (
            vsc.name
            + " — FROM terminal → "
            + vsc.bus_from.name
        )
        measurement_dialogue.apply_changes()
        qt_app.processEvents()

        rebuilt_point: RmsPhysicalMeasurementPoint | None = (
            voltage_meter_block.dynamic_model_contract.rms_physical_measurement_point
        )
        assert rebuilt_point is not None
        assert rebuilt_point.get_meter_kind() is RmsPhysicalMeterKind.POWER
        assert rebuilt_point.get_target_fid() == vsc.idtag
        assert rebuilt_point.get_terminal_side() is RmsTerminalSide.FROM
        assert voltage_meter_block.name == "Power meter 258"
        assert len(voltage_meter_block.out_vars) == 2
        assert all(
            output_var.name.isidentifier()
            for output_var in voltage_meter_block.out_vars
        )
        assert len(voltage_meter_block.algebraic_eqs) == 2
        assert len(voltage_meter_block.init_eqs) == 2
        validate_dynamic_model_contract(block=voltage_meter_block)
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


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
    _assert_nuactis_grid_uses_canonical_public_data(grid=script_grid)

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
            _assert_editor_dynamic_check_is_clean(editor=editor)
            measurement_block_for_options: Block | None = None
            scene_item: QtWidgets.QGraphicsItem
            for scene_item in editor.scene.items():
                if (
                        isinstance(scene_item, graph.GenericBlockItem)
                        and scene_item.visual_role
                        is graph.DynamicBlockVisualRole.MEASUREMENT
                ):
                    measurement_block_for_options = scene_item.subsys
                else:
                    pass
            assert measurement_block_for_options is not None
            measurement_edit_options: List[RmsMeasurementEditOption] = (
                editor.build_rms_measurement_edit_options(
                    block=measurement_block_for_options,
                )
            )
            option_pairs: set[tuple[RmsPhysicalMeterKind, RmsTerminalSide]] = set()
            valid_bus_fids: set[str] = set(
                bus.idtag for bus in gui_grid.buses
            )
            valid_branch_fids: set[str] = set()
            valid_physical_fids: set[str] = set()
            physical_device: DynamicDevice
            for physical_device in gui_grid.get_branches(
                    add_vsc=True,
                    add_hvdc=True,
                    add_switch=True,
            ):
                valid_branch_fids.add(physical_device.idtag)
                valid_physical_fids.add(physical_device.idtag)
            else:
                pass
            for physical_device in gui_grid.get_injection_devices_iter():
                valid_physical_fids.add(physical_device.idtag)
            else:
                pass
            remote_branch_option_found: bool = False
            measurement_edit_option: RmsMeasurementEditOption
            for measurement_edit_option in measurement_edit_options:
                option_kind: RmsPhysicalMeterKind = (
                    measurement_edit_option.get_meter_kind()
                )
                option_side: RmsTerminalSide = (
                    measurement_edit_option.get_source_terminal_side()
                )
                option_pairs.add((option_kind, option_side))
                option_label_lower: str = (
                    measurement_edit_option.get_target_label().lower()
                )
                assert "cubicle" not in option_label_lower
                assert "powerfactory" not in option_label_lower
                if option_kind in (
                        RmsPhysicalMeterKind.VOLTAGE,
                        RmsPhysicalMeterKind.PHASE_LOCKED_LOOP,
                ):
                    assert option_side is RmsTerminalSide.BUS
                    assert measurement_edit_option.get_target_fid() in valid_bus_fids
                else:
                    physical_target_fid: str = (
                        measurement_edit_option.get_target_fid()
                    )
                    assert physical_target_fid in valid_physical_fids
                    if (
                            physical_target_fid in valid_branch_fids
                            and physical_target_fid != gui_vsc.idtag
                    ):
                        remote_branch_option_found = True
                    else:
                        pass
            assert remote_branch_option_found
            assert option_pairs == set((
                (RmsPhysicalMeterKind.CURRENT, RmsTerminalSide.FROM),
                (RmsPhysicalMeterKind.POWER, RmsTerminalSide.FROM),
                (RmsPhysicalMeterKind.CURRENT, RmsTerminalSide.TO),
                (RmsPhysicalMeterKind.POWER, RmsTerminalSide.TO),
                (RmsPhysicalMeterKind.CURRENT, RmsTerminalSide.BUS),
                (RmsPhysicalMeterKind.POWER, RmsTerminalSide.BUS),
                (RmsPhysicalMeterKind.VOLTAGE, RmsTerminalSide.BUS),
                (RmsPhysicalMeterKind.PHASE_LOCKED_LOOP, RmsTerminalSide.BUS),
            ))
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
    assert np.max(np.abs(script_rms_results.values - gui_rms_results.values)) < 1e-6
    selected_variable_names: List[str] = list(
        (
            "VmSlave_AC",
            "VdcSlave_DC",
            "P_act_Power meter 229HVDC Slave_PWM",
            "Q_act_Power meter 229HVDC Slave_PWM",
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
    assert np.max(np.abs(script_selected_values - gui_selected_values)) < 1e-6

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
    assert np.max(powerfactory_difference) < 1e-6, (
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
    assert np.max(active_powerfactory_difference) < 1e-6, (
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
            visible_ref_port_count: int = 0
            scene_item: Any
            block_type: BlockType
            semantic_reference: VarPowerFlowReferenceType | None
            port_item: graph.PortItem
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
                            visible_ref_port_count += 1
                        else:
                            pass
                elif isinstance(scene_item, graph.GenericBlockItem):
                    # A physical projection can absorb the root ovals while
                    # retaining their typed variables as editable ports.
                    for port_item in scene_item.inputs:
                        if isinstance(
                                port_item.base_var.ref,
                                VarPowerFlowReferenceType,
                        ):
                            visible_refs.add(port_item.base_var.ref)
                            visible_ref_port_count += 1
                        else:
                            pass
                    for port_item in scene_item.outputs:
                        if isinstance(
                                port_item.base_var.ref,
                                VarPowerFlowReferenceType,
                        ):
                            visible_refs.add(port_item.base_var.ref)
                            visible_ref_port_count += 1
                        else:
                            pass
                else:
                    pass

            assert visible_refs == expected_refs
            assert visible_ref_port_count >= len(expected_refs)
    finally:
        for editor, _expected_refs in expected_refs_by_editor:
            editor.prepare_to_delete()
            editor.close()
            editor.deleteLater()


def test_injection_projection_uses_one_required_port_measurement_station(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Replace Network exchange with one draggable BUS measurement station.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    generators: List[Generator] = list(grid.get_generators())
    assert len(generators) > 0
    generator: Generator = generators[0]
    assert isinstance(generator.rms_template, RmsModelTemplate)
    assert isinstance(generator.rms_model, Block)
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=generator,
        mode=DynamicSimulationMode.RMS,
        root_block=generator.rms_model,
    )
    try:
        generic_items: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.GenericBlockItem)
        )
        assert len(generic_items) == 2
        assert all(
            "Network exchange" not in generic_item.subsys.name
            for generic_item in generic_items
        )
        physical_items: List[graph.GenericBlockItem] = list(
            generic_item for generic_item in generic_items
            if generic_item.visual_role
            is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
        )
        station_items: List[graph.GenericBlockItem] = list(
            generic_item for generic_item in generic_items
            if generic_item.visual_role
            is graph.DynamicBlockVisualRole.MEASUREMENT
        )
        assert len(physical_items) == 1
        assert len(station_items) == 1
        physical_item: graph.GenericBlockItem = physical_items[0]
        station_item: graph.GenericBlockItem = station_items[0]
        assert station_item.subsys.name == "Measurement station"
        assert len(station_item.subsys.children) == 4
        assert len(station_item.subsys.in_vars) == 4
        assert len(station_item.inputs) == 0
        station_refs: set[VarPowerFlowReferenceType] = set(
            station_port.base_var.ref for station_port in station_item.outputs
            if isinstance(station_port.base_var.ref, VarPowerFlowReferenceType)
        )
        required_refs: set[VarPowerFlowReferenceType] = set((
            VarPowerFlowReferenceType.Vm,
            VarPowerFlowReferenceType.Va,
            VarPowerFlowReferenceType.P,
            VarPowerFlowReferenceType.Q,
        ))
        assert station_refs == required_refs
        assert len(station_item.outputs) == len(required_refs)
        station_port_y_by_ref: Dict[VarPowerFlowReferenceType, float] = dict()
        station_port: graph.PortItem
        for station_port in station_item.outputs:
            if isinstance(station_port.base_var.ref, VarPowerFlowReferenceType):
                station_port_y_by_ref[station_port.base_var.ref] = station_port.pos().y()
            else:
                pass
        input_tag_bottom: float = max(
            station_port_y_by_ref[VarPowerFlowReferenceType.Vm],
            station_port_y_by_ref[VarPowerFlowReferenceType.Va],
        )
        output_tag_top: float = min(
            station_port_y_by_ref[VarPowerFlowReferenceType.P],
            station_port_y_by_ref[VarPowerFlowReferenceType.Q],
        )
        assert output_tag_top - input_tag_bottom >= editor.get_grid_size()
        assert all(
            physical_port.connections is not None
            and len(physical_port.connections) > 0
            for physical_port in list(physical_item.inputs) + list(physical_item.outputs)
            if physical_port.base_var.ref in required_refs
        )
        physical_body_rect: QtCore.QRectF = physical_item.mapRectToScene(
            physical_item.rect()
        )
        station_body_rect: QtCore.QRectF = station_item.mapRectToScene(
            station_item.rect()
        )
        station_port_by_ref: Dict[VarPowerFlowReferenceType, graph.PortItem] = dict()
        for station_port in station_item.outputs:
            if isinstance(station_port.base_var.ref, VarPowerFlowReferenceType):
                station_port_by_ref[station_port.base_var.ref] = station_port
            else:
                pass
        station_tag_rect_by_ref: Dict[VarPowerFlowReferenceType, QtCore.QRectF] = dict()
        signal_tag: graph.PairedItem
        for signal_tag in list(
                scene_item for scene_item in editor.scene.items()
                if isinstance(scene_item, graph.PairedItem)
        ):
            assert not physical_body_rect.intersects(
                signal_tag.sceneBoundingRect()
            ), signal_tag.name
            signal_var: Var | None = signal_tag.get_signal_var()
            if signal_var is not None and isinstance(
                    signal_var.ref,
                    VarPowerFlowReferenceType,
            ):
                signal_ref: VarPowerFlowReferenceType = signal_var.ref
                belongs_to_station_column: bool = (
                    signal_tag.is_signal_in
                    and signal_ref in (
                        VarPowerFlowReferenceType.Vm,
                        VarPowerFlowReferenceType.Va,
                    )
                ) or (
                    not signal_tag.is_signal_in
                    and signal_ref in (
                        VarPowerFlowReferenceType.P,
                        VarPowerFlowReferenceType.Q,
                    )
                )
                if belongs_to_station_column:
                    station_tag_rect: QtCore.QRectF = signal_tag.sceneBoundingRect()
                    station_port = station_port_by_ref[signal_ref]
                    station_right_boundary: float = max(
                        station_body_rect.right(),
                        station_port.scenePos().x(),
                    )
                    # A complete routing-grid cell must remain visible between
                    # the station/port boundary and every tag in its outer column.
                    assert (
                        station_tag_rect.left() - station_right_boundary
                        >= float(editor.get_grid_size())
                    ), signal_tag.name
                    station_tag_rect_by_ref[signal_ref] = station_tag_rect

                    # Every station stub must remain a sequence of visible
                    # orthogonal segments after tag placement.
                    assert station_port.connections is not None
                    station_connection: graph.ConnectionItem | None = None
                    port_connection: graph.ConnectionItem
                    for port_connection in station_port.connections:
                        if (
                                port_connection.source_port.subsystem is signal_tag
                                or port_connection.target_port.subsystem is signal_tag
                        ):
                            station_connection = port_connection
                        else:
                            pass
                    assert station_connection is not None
                    station_path: QtGui.QPainterPath = station_connection.path()
                    path_index: int
                    for path_index in range(1, station_path.elementCount()):
                        previous_element: QtGui.QPainterPath.Element = (
                            station_path.elementAt(path_index - 1)
                        )
                        current_element: QtGui.QPainterPath.Element = (
                            station_path.elementAt(path_index)
                        )
                        assert (
                            previous_element.x == current_element.x
                            or previous_element.y == current_element.y
                        ), signal_tag.name
                else:
                    pass
            else:
                pass

        assert set(station_tag_rect_by_ref.keys()) == required_refs
        station_tag_column_lefts: List[float] = list(
            station_tag_rect.left()
            for station_tag_rect in station_tag_rect_by_ref.values()
        )
        assert (
            max(station_tag_column_lefts) - min(station_tag_column_lefts)
            <= 1.0
        )
        input_tag_bottom: float = max(
            station_tag_rect_by_ref[VarPowerFlowReferenceType.Vm].bottom(),
            station_tag_rect_by_ref[VarPowerFlowReferenceType.Va].bottom(),
        )
        output_tag_top: float = min(
            station_tag_rect_by_ref[VarPowerFlowReferenceType.P].top(),
            station_tag_rect_by_ref[VarPowerFlowReferenceType.Q].top(),
        )
        assert output_tag_top >= input_tag_bottom

        measurement_parent: object | None = editor.library.tree_structure.get(
            "Measurements",
            None,
        )
        assert isinstance(measurement_parent, dict)
        measurement_leaves: object | None = measurement_parent.get(
            "RMS (balanced)",
            None,
        )
        assert isinstance(measurement_leaves, list)
        station_descriptors: List[MeasurementStationDescriptor] = list(
            measurement_leaf.payload for measurement_leaf in measurement_leaves
            if isinstance(
                measurement_leaf.payload,
                MeasurementStationDescriptor,
            )
        )
        assert len(station_descriptors) == 1
        station_model_indexes: List[QtCore.QModelIndex] = (
            editor.library.library_model.match(
                editor.library.library_model.index(0, 0),
                QtCore.Qt.ItemDataRole.DisplayRole,
                "Measurement station",
                1,
                (
                    QtCore.Qt.MatchFlag.MatchExactly
                    | QtCore.Qt.MatchFlag.MatchRecursive
                ),
            )
        )
        assert len(station_model_indexes) == 1
        station_mime_data: QtCore.QMimeData = (
            editor.library.library_model.mimeData(station_model_indexes)
        )
        decoded_station_payload: object | None = (
            editor.get_library_payload_from_mime_data(station_mime_data)
        )
        assert decoded_station_payload is station_descriptors[0]
        passive_branch_library: DynamicEditorLibrary = DynamicEditorLibrary(
            api_object=generator,
            mode=DynamicSimulationMode.RMS,
            templates_list=grid.get_rms_templates_for_editor(
                DeviceType.LineDevice
            ),
        )
        physical_library_leaves: object | None = (
            passive_branch_library.tree_structure.get(
            "Physical devices/templates",
            None,
            )
        )
        assert isinstance(physical_library_leaves, list)
        passive_shell_leaves: list[object] = list(
            library_leaf for library_leaf in physical_library_leaves
            if library_leaf.label == "DGS passive branch RMS shell"
        )
        assert len(passive_shell_leaves) == 1
        placed_station: object | None = editor.create_library_payload_item(
            payload=station_descriptors[0],
            x_pos=station_item.pos().x() + 37.0,
            y_pos=station_item.pos().y() + 43.0,
        )
        assert isinstance(placed_station, graph.GenericBlockItem)
        assert placed_station is not station_item
        assert placed_station.subsys in editor.main_block.children
        assert len(placed_station.subsys.children) == 4
        assert set(
            station_var.ref for station_var in placed_station.subsys.in_vars
            if isinstance(station_var.ref, VarPowerFlowReferenceType)
        ) == required_refs
        editor.request_open_block_properties(placed_station.subsys)
        assert isinstance(
            editor._block_properties_dialogue,
            DynamicBlockPropertiesDialog,
        )
        station_dialogue: DynamicBlockPropertiesDialog = (
            editor._block_properties_dialogue
        )
        station_meter_combo: QtWidgets.QComboBox | None = (
            station_dialogue.findChild(
                QtWidgets.QComboBox,
                "measurement_block_combo",
            )
        )
        assert station_meter_combo is not None
        assert station_meter_combo.count() == len(placed_station.subsys.children)
        configured_kinds: set[RmsPhysicalMeterKind] = set()
        meter_combo_index: int
        for meter_combo_index in range(station_meter_combo.count()):
            station_meter_combo.setCurrentIndex(meter_combo_index)
            qt_app.processEvents()
            assert station_dialogue.ui.measurement_mode_combo.count() == 1
            active_kind_data: object = (
                station_dialogue.ui.measurement_mode_combo.currentData()
            )
            assert isinstance(active_kind_data, RmsPhysicalMeterKind)
            configured_kinds.add(active_kind_data)
            selected_target: RmsMeasurementEditOption | None = (
                station_dialogue.get_selected_measurement_option()
            )
            assert selected_target is not None
            if active_kind_data in (
                    RmsPhysicalMeterKind.VOLTAGE,
                    RmsPhysicalMeterKind.PHASE_LOCKED_LOOP,
            ):
                assert (
                    selected_target.get_source_terminal_side()
                    is RmsTerminalSide.BUS
                )
                assert selected_target.get_target_fid() in set(
                    bus.idtag for bus in grid.buses
                )
            else:
                assert selected_target.get_target_fid() == generator.idtag
                assert (
                    selected_target.get_source_terminal_side()
                    is RmsTerminalSide.BUS
                )
        assert configured_kinds == set(RmsPhysicalMeterKind)
        editor.close_block_properties_dock()
        qt_app.processEvents()
        station_output: graph.PortItem
        for station_output in station_item.outputs:
            assert station_output.connections is not None
            assert len(station_output.connections) > 0
            station_connection: graph.ConnectionItem
            for station_connection in station_output.connections:
                station_path: QtGui.QPainterPath = station_connection.path()
                assert station_path.elementCount() >= 2
                first_element: QtGui.QPainterPath.Element = station_path.elementAt(0)
                last_element: QtGui.QPainterPath.Element = station_path.elementAt(
                    station_path.elementCount() - 1
                )
                assert (
                    first_element.x
                    == station_connection.source_port.scenePos().x()
                )
                assert (
                    first_element.y
                    == station_connection.source_port.scenePos().y()
                )
                assert (
                    last_element.x
                    == station_connection.target_port.scenePos().x()
                )
                assert (
                    last_element.y
                    == station_connection.target_port.scenePos().y()
                )
        assert len(
            list(
                scene_item for scene_item in editor.scene.items()
                if isinstance(scene_item, graph.GenericBlockItem)
                and scene_item.visual_role
                is graph.DynamicBlockVisualRole.MEASUREMENT
            )
        ) == 2
        _assert_editor_dynamic_check_is_clean(editor=editor)
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


def test_new_injection_boundary_materializes_station_before_first_drop(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Project a fresh Vm/Va/P/Q device boundary as a measurement station.

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
    new_root: Block = Block(name="New generator RMS model")
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=generator,
        mode=DynamicSimulationMode.RMS,
        root_block=new_root,
    )
    try:
        assert set(input_var.name for input_var in new_root.in_vars) == set((
            "Vm",
            "Va",
        ))
        assert set(output_var.name for output_var in new_root.out_vars) == set((
            "net_conn_P",
            "net_conn_Q",
        ))
        automatic_stations: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.GenericBlockItem)
            and scene_item.visual_role
            is graph.DynamicBlockVisualRole.MEASUREMENT
        )
        assert len(automatic_stations) == 1
        assert len(automatic_stations[0].inputs) == 0
        assert set(
            station_port.base_var.ref
            for station_port in automatic_stations[0].outputs
        ) == set((
            VarPowerFlowReferenceType.Vm,
            VarPowerFlowReferenceType.Va,
            VarPowerFlowReferenceType.P,
            VarPowerFlowReferenceType.Q,
        ))

        measurement_parent: object | None = editor.library.tree_structure.get(
            "Measurements",
            None,
        )
        assert isinstance(measurement_parent, dict)
        measurement_leaves: object | None = measurement_parent.get(
            "RMS (balanced)",
            None,
        )
        assert isinstance(measurement_leaves, list)
        station_descriptor: MeasurementStationDescriptor | None = None
        measurement_leaf: object
        for measurement_leaf in measurement_leaves:
            if isinstance(
                    measurement_leaf.payload,
                    MeasurementStationDescriptor,
            ):
                station_descriptor = measurement_leaf.payload
            else:
                pass
        assert station_descriptor is not None
        dropped_station: object | None = editor.create_library_payload_item(
            payload=station_descriptor,
            x_pos=automatic_stations[0].pos().x() + 80.0,
            y_pos=automatic_stations[0].pos().y() + 80.0,
        )
        assert isinstance(dropped_station, graph.GenericBlockItem)
        assert dropped_station is not automatic_stations[0]
        assert dropped_station.subsys in new_root.children
        assert len(
            list(
                scene_item for scene_item in editor.scene.items()
                if isinstance(scene_item, graph.GenericBlockItem)
                and scene_item.visual_role
                is graph.DynamicBlockVisualRole.MEASUREMENT
            )
        ) == 2
        _assert_editor_dynamic_check_is_clean(editor=editor)
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


def test_transformer_projection_splits_measurements_by_terminal_without_collisions(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Give every two-winding transformer separate FROM and TO stations.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    transformer_devices: Sequence[DynamicDevice] = grid.get_transformers2w()
    assert len(transformer_devices) > 0
    transformer: DynamicDevice = transformer_devices[0]
    assert isinstance(transformer.rms_model, Block)
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=transformer,
        mode=DynamicSimulationMode.RMS,
        root_block=transformer.rms_model,
    )
    try:
        physical_items: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.GenericBlockItem)
            and scene_item.visual_role
            is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
        )
        station_items: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.GenericBlockItem)
            and scene_item.visual_role
            is graph.DynamicBlockVisualRole.MEASUREMENT
        )
        assert len(physical_items) == 1
        assert len(station_items) == 2
        assert station_items[0].pos().x() == station_items[1].pos().x()
        assert station_items[0].pos().y() != station_items[1].pos().y()

        station_sides: set[RmsTerminalSide] = set()
        station_item: graph.GenericBlockItem
        for station_item in station_items:
            reference_sides: set[RmsTerminalSide] = set(
                get_rms_measurement_terminal_side_for_reference(
                    reference=station_port.base_var.ref,
                )
                for station_port in station_item.outputs
                if isinstance(
                    station_port.base_var.ref,
                    VarPowerFlowReferenceType,
                )
            )
            assert len(reference_sides) == 1
            station_side: RmsTerminalSide = next(iter(reference_sides))
            assert station_side in (
                RmsTerminalSide.FROM,
                RmsTerminalSide.TO,
            )
            station_sides.add(station_side)
        assert station_sides == set((
            RmsTerminalSide.FROM,
            RmsTerminalSide.TO,
        ))

        physical_item: graph.GenericBlockItem = physical_items[0]
        physical_body_rect: QtCore.QRectF = physical_item.mapRectToScene(
            physical_item.rect()
        )
        signal_tag: graph.PairedItem
        for signal_tag in list(
                scene_item for scene_item in editor.scene.items()
                if isinstance(scene_item, graph.PairedItem)
        ):
            assert not physical_body_rect.intersects(
                signal_tag.sceneBoundingRect()
            ), signal_tag.name
        _assert_editor_dynamic_check_is_clean(editor=editor)
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


def test_line_projection_uses_standard_blocks_and_scalar_from_goto_pairs(
        qt_app: QtWidgets.QApplication,
        tmp_path: Path,
) -> None:
    """Group four real meters per terminal and shorten scalar wiring with tags.

    :param qt_app: Shared Qt application fixture.
    :param tmp_path: Isolated save/reopen directory.
    :return: None.
    """
    grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    line_devices: List[Line] = list(grid.get_lines())
    assert len(line_devices) > 0
    line: Line = line_devices[0]
    assert isinstance(line.rms_template, RmsModelTemplate)
    assert isinstance(line.rms_model, Block)
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=line,
        mode=DynamicSimulationMode.RMS,
        root_block=line.rms_model,
    )
    try:
        generic_items: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.GenericBlockItem)
        )
        assert len(generic_items) == 3
        station_items: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in generic_items
            if scene_item.visual_role is graph.DynamicBlockVisualRole.MEASUREMENT
        )
        assert len(station_items) == 2
        station_by_side: Dict[RmsTerminalSide, graph.GenericBlockItem] = dict()
        station_item: graph.GenericBlockItem
        for station_item in station_items:
            station_anchor_refs: set[VarPowerFlowReferenceType] = set(
                station_port.base_var.ref for station_port in station_item.outputs
                if isinstance(
                    station_port.base_var.ref,
                    VarPowerFlowReferenceType,
                )
            )
            if (
                    VarPowerFlowReferenceType.Pf in station_anchor_refs
                    and VarPowerFlowReferenceType.Pt not in station_anchor_refs
            ):
                station_by_side[RmsTerminalSide.FROM] = station_item
            elif (
                    VarPowerFlowReferenceType.Pt in station_anchor_refs
                    and VarPowerFlowReferenceType.Pf not in station_anchor_refs
            ):
                station_by_side[RmsTerminalSide.TO] = station_item
            else:
                pass
        assert set(station_by_side.keys()) == set((
            RmsTerminalSide.FROM,
            RmsTerminalSide.TO,
        ))
        assert (
            station_by_side[RmsTerminalSide.FROM].pos().x()
            == station_by_side[RmsTerminalSide.TO].pos().x()
        )
        assert (
            station_by_side[RmsTerminalSide.FROM].pos().y()
            < station_by_side[RmsTerminalSide.TO].pos().y()
        )

        expected_meter_kinds: set[RmsPhysicalMeterKind] = set((
            RmsPhysicalMeterKind.POWER,
            RmsPhysicalMeterKind.CURRENT,
            RmsPhysicalMeterKind.VOLTAGE,
            RmsPhysicalMeterKind.PHASE_LOCKED_LOOP,
        ))
        meter_signatures_by_side: Dict[
            RmsTerminalSide,
            Dict[RmsPhysicalMeterKind, Tuple[str, Tuple[str, ...]]],
        ] = dict()
        expected_station_anchor_refs: Dict[
            RmsTerminalSide,
            set[VarPowerFlowReferenceType],
        ] = dict((
            (
                RmsTerminalSide.FROM,
                set((
                    VarPowerFlowReferenceType.Vmf,
                    VarPowerFlowReferenceType.Vaf,
                    VarPowerFlowReferenceType.Pf,
                    VarPowerFlowReferenceType.Qf,
                )),
            ),
            (
                RmsTerminalSide.TO,
                set((
                    VarPowerFlowReferenceType.Vmt,
                    VarPowerFlowReferenceType.Vat,
                    VarPowerFlowReferenceType.Pt,
                    VarPowerFlowReferenceType.Qt,
                )),
            ),
        ))
        station_side: RmsTerminalSide
        for station_side, station_item in station_by_side.items():
            assert len(station_item.subsys.children) == 4
            assert len(station_item.subsys.in_vars) == 4
            assert len(station_item.inputs) == 0
            assert len(station_item.subsys.out_vars) > 4
            assert len(station_item.outputs) == 4
            assert set(
                station_port.base_var.ref for station_port in station_item.outputs
                if isinstance(
                    station_port.base_var.ref,
                    VarPowerFlowReferenceType,
                )
            ) == expected_station_anchor_refs[station_side]
            meter_kinds: set[RmsPhysicalMeterKind] = set()
            meter_signatures: Dict[
                RmsPhysicalMeterKind,
                Tuple[str, Tuple[str, ...]],
            ] = dict()
            meter_block: Block
            for meter_block in station_item.subsys.children:
                measurement_point: RmsPhysicalMeasurementPoint | None = (
                    meter_block.dynamic_model_contract.rms_physical_measurement_point
                )
                assert measurement_point is not None
                meter_kind: RmsPhysicalMeterKind = measurement_point.get_meter_kind()
                meter_kinds.add(meter_kind)
                meter_signatures[meter_kind] = (
                    meter_block.name,
                    measurement_point.get_output_signal_names(),
                )
                if meter_kind in (
                        RmsPhysicalMeterKind.VOLTAGE,
                        RmsPhysicalMeterKind.PHASE_LOCKED_LOOP,
                ):
                    expected_bus: Bus | None
                    if station_side is RmsTerminalSide.FROM:
                        expected_bus = line.bus_from
                    else:
                        expected_bus = line.bus_to
                    assert expected_bus is not None
                    assert measurement_point.get_target_fid() == expected_bus.idtag
                    assert measurement_point.get_terminal_side() is RmsTerminalSide.BUS
                else:
                    assert measurement_point.get_target_fid() == line.idtag
                    assert measurement_point.get_terminal_side() is station_side
            assert meter_kinds == expected_meter_kinds
            meter_signatures_by_side[station_side] = meter_signatures
        assert (
            meter_signatures_by_side[RmsTerminalSide.FROM]
            == meter_signatures_by_side[RmsTerminalSide.TO]
        )
        physical_items: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in generic_items
            if scene_item.visual_role is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
        )
        assert len(physical_items) == 1
        assert all(
            station_item.pos().x() < physical_items[0].pos().x()
            for station_item in station_items
        )
        measurement_parent: object | None = editor.library.tree_structure.get(
            "Measurements",
            None,
        )
        assert isinstance(measurement_parent, dict)
        rms_measurement_leaves: object | None = measurement_parent.get(
            "RMS (balanced)",
            None,
        )
        assert isinstance(rms_measurement_leaves, list)
        station_descriptors: List[MeasurementStationDescriptor] = list(
            leaf.payload for leaf in rms_measurement_leaves
            if isinstance(leaf.payload, MeasurementStationDescriptor)
        )
        assert len(station_descriptors) == 1

        tag_items: List[graph.PairedItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.PairedItem)
        )
        from_tags: List[graph.PairedItem] = list(
            tag_item for tag_item in tag_items
            if tag_item.subsys is not None and tag_item.subsys.name.startswith("From ")
        )
        goto_tags: List[graph.PairedItem] = list(
            tag_item for tag_item in tag_items
            if tag_item.subsys is not None and tag_item.subsys.name.startswith("Goto ")
        )
        expected_association_count: int = 8
        assert len(from_tags) == expected_association_count
        assert len(goto_tags) == expected_association_count
        assert all(
            any(
                port_item.connections is not None and len(port_item.connections) > 0
                for port_item in list(tag_item.inputs) + list(tag_item.outputs)
            )
            for tag_item in tag_items
        )

        scalar_connections: List[graph.ConnectionItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.ConnectionItem)
        )
        assert len(scalar_connections) == expected_association_count * 2
        output_to_output_connections: List[graph.ConnectionItem] = list(
            connection for connection in scalar_connections
            if (
                isinstance(connection.source_port, graph.PortItem)
                and isinstance(connection.target_port, graph.PortItem)
                and not connection.source_port.is_input
                and not connection.target_port.is_input
            )
        )
        expected_output_to_output_count: int = len(physical_items[0].outputs)
        assert len(output_to_output_connections) == expected_output_to_output_count
        assert all(
            connection.target_port.subsystem in station_items
            for connection in output_to_output_connections
        )
        scalar_connection: graph.ConnectionItem
        for scalar_connection in scalar_connections:
            source_subsystem: object = scalar_connection.source_port.subsystem
            target_subsystem: object = scalar_connection.target_port.subsystem
            assert (
                isinstance(source_subsystem, graph.PairedItem)
                or isinstance(target_subsystem, graph.PairedItem)
            )

        # Every normal boundary block remains movable. Its local From/Goto
        # stubs must follow the real port and stay orthogonal on the mesh.
        generic_item: graph.GenericBlockItem
        for generic_item in generic_items:
            incident_connections: set[graph.ConnectionItem] = set()
            generic_port: graph.PortItem
            for generic_port in list(generic_item.inputs) + list(generic_item.outputs):
                if generic_port.connections is not None:
                    incident_connection: graph.ConnectionItem
                    for incident_connection in generic_port.connections:
                        incident_connections.add(incident_connection)
                else:
                    pass
            assert len(incident_connections) > 0
            generic_item.setPos(generic_item.pos() + QtCore.QPointF(37.0, 43.0))
            qt_app.processEvents()
            assert generic_item.pos().x() % editor.get_grid_size() == 0.0
            assert generic_item.pos().y() % editor.get_grid_size() == 0.0
            for incident_connection in incident_connections:
                incident_path: QtGui.QPainterPath = incident_connection.path()
                assert incident_path.elementCount() >= 2
                first_element: QtGui.QPainterPath.Element = incident_path.elementAt(0)
                last_element: QtGui.QPainterPath.Element = incident_path.elementAt(
                    incident_path.elementCount() - 1
                )
                source_position: QtCore.QPointF = incident_connection.source_port.scenePos()
                target_position: QtCore.QPointF = incident_connection.target_port.scenePos()
                assert first_element.x == source_position.x()
                assert first_element.y == source_position.y()
                assert last_element.x == target_position.x()
                assert last_element.y == target_position.y()
                path_element_index: int
                for path_element_index in range(incident_path.elementCount() - 1):
                    segment_start: QtGui.QPainterPath.Element = incident_path.elementAt(
                        path_element_index
                    )
                    segment_end: QtGui.QPainterPath.Element = incident_path.elementAt(
                        path_element_index + 1
                    )
                    assert (
                        segment_start.x == segment_end.x
                        or segment_start.y == segment_end.y
                    )

        canonical_block_uids: set[int] = set(
            block_model.uid for block_model in line.rms_model.get_all_blocks()
        )
        assert all(
            tag_item.subsys is not None
            and tag_item.subsys.uid not in canonical_block_uids
            for tag_item in tag_items
        )

        # Persist one moved tag and all three derived block positions through
        # the public declarative archive. Reopening must rebuild the same view
        # without generating symbolic placeholder blocks.
        moved_tag: graph.PairedItem = from_tags[0]
        assert moved_tag.subsys is not None
        moved_tag_name: str = moved_tag.subsys.name
        moved_tag.setPos(moved_tag.pos() + QtCore.QPointF(40.0, 60.0))
        qt_app.processEvents()
        moved_tag_position: QtCore.QPointF = QtCore.QPointF(moved_tag.pos())
        saved_station_positions: Dict[RmsTerminalSide, QtCore.QPointF] = dict(
            (station_side, QtCore.QPointF(station_item.pos()))
            for station_side, station_item in station_by_side.items()
        )
        saved_physical_position: QtCore.QPointF = QtCore.QPointF(
            physical_items[0].pos()
        )
        assert len(editor.diagram.projection_node_data) == 19

        saved_path: Path = tmp_path / "line_from_goto_layout.veragrid"
        save_logger: Logger = FileSave(
            circuit=grid,
            file_name=str(saved_path),
        ).save()
        assert save_logger.error_count() == 0
        assert save_logger.warning_count() == 0
        reopened_file: FileOpen = FileOpen(file_name=str(saved_path))
        reopened_grid: MultiCircuit | None = reopened_file.open()
        assert reopened_grid is not None
        assert reopened_file.logger.error_count() == 0
        assert reopened_file.logger.warning_count() == 0
        reopened_line: Line | None = None
        candidate_line: Line
        for candidate_line in reopened_grid.get_lines():
            if candidate_line.idtag == line.idtag:
                reopened_line = candidate_line
            else:
                pass
        assert reopened_line is not None
        assert isinstance(reopened_line.rms_model, Block)
        reopened_editor: DynamicBlockEditorGUI = _build_gui_editor(
            qt_app=qt_app,
            grid=reopened_grid,
            api_object=reopened_line,
            mode=DynamicSimulationMode.RMS,
            root_block=reopened_line.rms_model,
        )
        try:
            assert (
                reopened_editor.diagram.get_projection_node_data_dict()
                == editor.diagram.get_projection_node_data_dict()
            )
            reopened_station_count: int = 0
            reopened_generic_item: graph.GenericBlockItem
            for reopened_generic_item in list(
                    scene_item for scene_item in reopened_editor.scene.items()
                    if isinstance(scene_item, graph.GenericBlockItem)
            ):
                if (
                        reopened_generic_item.visual_role
                        is graph.DynamicBlockVisualRole.MEASUREMENT
                ):
                    reopened_anchor_refs: set[VarPowerFlowReferenceType] = set(
                        station_port.base_var.ref
                        for station_port in reopened_generic_item.outputs
                        if isinstance(
                            station_port.base_var.ref,
                            VarPowerFlowReferenceType,
                        )
                    )
                    if (
                            VarPowerFlowReferenceType.Pf in reopened_anchor_refs
                            and VarPowerFlowReferenceType.Pt not in reopened_anchor_refs
                    ):
                        reopened_side: RmsTerminalSide = RmsTerminalSide.FROM
                    elif (
                            VarPowerFlowReferenceType.Pt in reopened_anchor_refs
                            and VarPowerFlowReferenceType.Pf not in reopened_anchor_refs
                    ):
                        reopened_side = RmsTerminalSide.TO
                    else:
                        raise AssertionError(
                            "Reopened station has no typed terminal anchor"
                        )
                    assert (
                        reopened_generic_item.pos()
                        == saved_station_positions[reopened_side]
                    )
                    reopened_station_count += 1
                else:
                    assert reopened_generic_item.pos() == saved_physical_position
            assert reopened_station_count == 2
            reopened_moved_tags: List[graph.PairedItem] = list(
                scene_item for scene_item in reopened_editor.scene.items()
                if isinstance(scene_item, graph.PairedItem)
                and scene_item.subsys is not None
                and scene_item.subsys.name == moved_tag_name
            )
            assert len(reopened_moved_tags) == 1
            assert reopened_moved_tags[0].pos() == moved_tag_position
        finally:
            reopened_editor.prepare_to_delete()
            reopened_editor.close()
            reopened_editor.deleteLater()
            qt_app.processEvents()
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


def test_line_direct_model_without_template_keeps_physical_measurement_projection(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Open the same physical and measurement view without a template link.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit
    generator: Generator
    candidate_line: Any
    load: Load
    grid, generator, candidate_line, load = _build_two_bus_rms_grid()
    del generator
    del load
    assert isinstance(candidate_line, Line)
    line: Line = candidate_line
    direct_model: Block = get_line_rms_template(grid.var_factory).block
    set_rms_model(
        device=line,
        model=direct_model,
        var_factory=grid.var_factory,
    )
    line.rms_template = None
    assert line.rms_template is None
    assert line.rms_model is direct_model

    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=line,
        mode=DynamicSimulationMode.RMS,
        root_block=line.rms_model,
    )
    try:
        physical_items: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.GenericBlockItem)
            and scene_item.visual_role
            is graph.DynamicBlockVisualRole.DEVICE_TEMPLATE
        )
        station_items: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.GenericBlockItem)
            and scene_item.visual_role
            is graph.DynamicBlockVisualRole.MEASUREMENT
        )
        assert len(physical_items) == 1
        assert len(station_items) == 2
        assert all(len(station_item.subsys.children) == 4 for station_item in station_items)
        physical_ports: List[graph.PortItem] = (
            list(physical_items[0].inputs) + list(physical_items[0].outputs)
        )
        assert all(
            physical_port.connections is not None
            and len(physical_port.connections) > 0
            for physical_port in physical_ports
        )
        _assert_editor_dynamic_check_is_clean(editor=editor)
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


def test_workspace_grid_split_button_controls_active_editor(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Place all mesh controls in one split button on the workspace toolbar.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    line_devices: List[Line] = list(grid.get_lines())
    assert len(line_devices) > 0
    session: DynamicEditorWorkspaceSession = DynamicEditorWorkspaceSession()
    workspace: DynamicEditorWorkspaceWindow = DynamicEditorWorkspaceWindow(
        session=session,
    )
    workspace.show()
    page: DynamicEditorTab | None = workspace.open_dynamic_editor_for(
        api_object=line_devices[0],
        circuit=grid,
        preferred_mode=DynamicSimulationMode.RMS,
    )
    qt_app.processEvents()
    assert isinstance(page, DynamicEditorTab)
    editor: DynamicBlockEditorGUI = page.editor
    try:
        grid_button: QtWidgets.QToolButton | None = workspace.findChild(
            QtWidgets.QToolButton,
            "dynamicEditorGridToolButton",
        )
        assert isinstance(grid_button, QtWidgets.QToolButton)
        assert grid_button.parent() is workspace.ui.toolBar
        assert (
            grid_button.popupMode()
            is QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        assert editor.findChild(
            QtWidgets.QToolBar,
            "dynamicEditorCanvasToolbar",
        ) is None

        assert editor.is_grid_visible() is True
        workspace._grid_visibility_action.trigger()
        qt_app.processEvents()
        assert editor.is_grid_visible() is False
        workspace._grid_visibility_action.trigger()
        assert editor.is_grid_visible() is True

        workspace._snap_to_grid_action.setChecked(False)
        assert editor.is_snap_to_grid_enabled() is False
        workspace._snap_to_grid_action.setChecked(True)
        assert editor.is_snap_to_grid_enabled() is True
        workspace._grid_size_spin_box.setValue(35)
        assert editor.get_grid_size() == 35
        assert "cable segments always move by grid cells" in (
            workspace._grid_size_spin_box.toolTip()
        )
    finally:
        page.prepare_to_delete()
        workspace.session.unregister_page(page)
        workspace.remove_page(page)
        page.setParent(None)
        page.deleteLater()
        workspace.close()
        workspace.deleteLater()
        qt_app.processEvents()


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
    expected_scene_connection_counts: Dict[int, int] = dict()
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
        expected_scene_connection_counts[device.rms_model.uid] = len(list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.ConnectionItem)
        ))

    for editor in initial_editors:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
    qt_app.processEvents()

    # Confirm the symbolic tree and its fallback dictionary boundary contain
    # no GUI-only wrapper state before exercising the persisted diagram path.
    for device in devices:
        for child_block in device.rms_model.children:
            child_data: Dict[str, Any] = child_block.to_dict()
            assert "is_root_interface_wrapper" not in child_data

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
            expected_scene_connection_count: int | None = (
                expected_scene_connection_counts.get(device.rms_model.uid, None)
            )
            assert expected_scene_connection_count is not None
            assert expected_scene_connection_count > 0
            assert scene_connection_count == expected_scene_connection_count
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


def test_connected_block_programmatic_move_keeps_wire_endpoint_attached(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Keep one persisted wire attached when its source block moves.

    Programmatic ``setPos`` exercises the same public graphics-item API used by
    Qt drag handling while avoiding mouse-event timing in the regression.  The
    route must be recomputed from the committed scene position, and the moved
    block must remain a child of the authoritative symbolic model.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    circuit: MultiCircuit = MultiCircuit()
    generator: Generator = Generator(name="Routing owner")
    root_block: Block = Block(name="routing_root")
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
            x_pos=420.0,
            y_pos=260.0,
        )
        assert source_item is not None
        assert target_item is not None

        editor.scene.connect_ports(source_item.outputs[0], target_item.inputs[0])
        qt_app.processEvents()
        connections: List[graph.ConnectionItem] = [
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.ConnectionItem)
        ]
        assert len(connections) == 1
        connection: graph.ConnectionItem = connections[0]

        # Moving through the public Qt item API must update both the persisted
        # diagram position and the live route after Qt commits the new scene pos.
        source_item.setPos(QtCore.QPointF(180.0, 200.0))
        qt_app.processEvents()
        source_endpoint: QtCore.QPointF = source_item.outputs[0].scenePos()
        path_start: QtGui.QPainterPath.Element = connection.path().elementAt(0)
        assert path_start.x == source_endpoint.x()
        assert path_start.y == source_endpoint.y()
        assert editor.diagram.node_data[source_item.subsys.uid].x == source_item.pos().x()
        assert editor.diagram.node_data[source_item.subsys.uid].y == source_item.pos().y()
        assert source_item.subsys in root_block.children
        assert target_item.subsys in root_block.children
        assert connection.con_uid in editor.diagram.con_data

        # Toolbar state is mirrored by public APIs, and block placement snaps
        # independently from whether the visual mesh is currently painted.
        assert editor.is_grid_visible() is True
        editor.set_grid_visible(False)
        assert editor.grid_visibility_action.isChecked() is False
        editor.set_grid_visible(True)
        editor.set_grid_size(20)
        editor.set_snap_to_grid_enabled(False)
        assert editor.snap_to_grid_action.isChecked() is False
        source_item.setPos(QtCore.QPointF(223.0, 247.0))
        qt_app.processEvents()
        assert source_item.pos() == QtCore.QPointF(223.0, 247.0)
        editor.set_snap_to_grid_enabled(True)
        source_item.setPos(QtCore.QPointF(224.0, 248.0))
        qt_app.processEvents()
        assert source_item.pos() == QtCore.QPointF(220.0, 240.0)
        snapped_source_endpoint: QtCore.QPointF = source_item.outputs[0].scenePos()
        snapped_path_start: QtGui.QPainterPath.Element = connection.path().elementAt(0)
        assert snapped_path_start.x == snapped_source_endpoint.x()
        assert snapped_path_start.y == snapped_source_endpoint.y()

        # A bent cable owns only the one-cell band traversed by its segments,
        # never the complete rectangle enclosed by the route.  This is also the
        # interaction shape used by Qt for pointer selection.
        original_path: QtGui.QPainterPath = connection.path()
        neighborhood_path: QtGui.QPainterPath = QtGui.QPainterPath(
            QtCore.QPointF(0.0, 0.0)
        )
        neighborhood_path.lineTo(QtCore.QPointF(100.0, 0.0))
        neighborhood_path.lineTo(QtCore.QPointF(100.0, 100.0))
        connection.setPath(neighborhood_path)
        assert connection.shape().contains(QtCore.QPointF(50.0, 5.0))
        assert not connection.shape().contains(QtCore.QPointF(50.0, 50.0))

        # Selected painting decorates the traversed cable itself. The bottom
        # edge of the enclosing 100x100 rectangle must remain fully transparent.
        selection_image: QtGui.QImage = QtGui.QImage(
            130,
            130,
            QtGui.QImage.Format.Format_ARGB32_Premultiplied,
        )
        selection_image.fill(QtCore.Qt.GlobalColor.transparent)
        selection_painter: QtGui.QPainter = QtGui.QPainter(selection_image)
        selection_painter.translate(15.0, 15.0)
        connection.setSelected(True)
        paint_option: QtWidgets.QStyleOptionGraphicsItem = (
            QtWidgets.QStyleOptionGraphicsItem()
        )
        connection.paint(selection_painter, paint_option, None)
        selection_painter.end()
        selection_sample_x: int
        for selection_sample_x in range(30, 90):
            assert selection_image.pixelColor(selection_sample_x, 115).alpha() == 0
        connection.setSelected(False)
        connection.setPath(original_path)

        # The routing graph exposes a real ELBOW-to-ELBOW segment.  Its hit-test
        # and public move API must agree, and the displaced coordinate must land
        # on the same mesh used by block snapping.
        route_segments: List[Tuple[int, QtCore.QPointF, QtCore.QPointF]] = (
            editor.get_connection_routing_graph_segments(connection)
        )
        editable_segment_index: int = -1
        route_segment_index: int
        for route_segment_index in range(len(route_segments)):
            route_segment_id: int = route_segments[route_segment_index][0]
            if (
                    editable_segment_index < 0
                    and editor.is_connection_routing_graph_segment_movable(
                item=connection,
                segment_id=route_segment_id,
            )
            ):
                editable_segment_index = route_segment_index
            else:
                pass
        assert editable_segment_index >= 0
        editable_start: QtCore.QPointF = route_segments[editable_segment_index][1]
        editable_end: QtCore.QPointF = route_segments[editable_segment_index][2]
        editable_midpoint: QtCore.QPointF = QtCore.QPointF(
            (editable_start.x() + editable_end.x()) * 0.5,
            (editable_start.y() + editable_end.y()) * 0.5,
        )
        hit_segment_index: int
        hit_is_horizontal: bool
        hit_segment_index, hit_is_horizontal = connection.find_segment_at_scene_position(
            pos=editable_midpoint,
            threshold=4.0,
            editable_only=True,
        )
        assert hit_segment_index == editable_segment_index
        assert hit_is_horizontal == (abs(editable_start.y() - editable_end.y()) < 1.0)
        # Block snap may be disabled, but cable corridors are mesh-owned and
        # must still move only by complete grid coordinates.
        editor.set_snap_to_grid_enabled(False)
        if hit_is_horizontal:
            moved: bool = editor.move_connection_segment_with_routing_graph(
                item=connection,
                segment_index=editable_segment_index,
                delta_x=0.0,
                delta_y=-13.0,
            )
        else:
            moved = editor.move_connection_segment_with_routing_graph(
                item=connection,
                segment_index=editable_segment_index,
                delta_x=-13.0,
                delta_y=0.0,
            )
        assert moved is True
        moved_segments: List[Tuple[int, QtCore.QPointF, QtCore.QPointF]] = (
            editor.get_connection_routing_graph_segments(connection)
        )
        moved_start: QtCore.QPointF = moved_segments[editable_segment_index][1]
        if hit_is_horizontal:
            assert moved_start.y() != editable_start.y()
            assert moved_start.y() % float(editor.get_grid_size()) == 0.0
        else:
            assert moved_start.x() != editable_start.x()
            assert moved_start.x() % float(editor.get_grid_size()) == 0.0

        # The canonical Block declaration owns node positions, connectivity and
        # the complete routing graph.  Reconstructing from that public contract
        # must preserve the user-authored segment displacement exactly.
        connection_record: BlockDiagramConnection = editor.diagram.con_data[connection.con_uid]
        assert connection_record.routing_payload is not None
        persisted_routing_payload: Dict[str, object] = dict(connection_record.routing_payload)
        block_data: Dict[str, object] = root_block.to_dict()
        restored_root: Block = Block.parse(
            data=block_data,
            procedural_logic_codec=ProceduralLogicCodec(),
        )
        restored_record: BlockDiagramConnection = restored_root.diagram.con_data[connection.con_uid]
        assert restored_record.routing_payload == persisted_routing_payload
        assert restored_root.diagram.node_data[source_item.subsys.uid].x == 220.0
        assert restored_root.diagram.node_data[source_item.subsys.uid].y == 240.0
        assert len(restored_root.children) == 2

        reopened_circuit: MultiCircuit = MultiCircuit()
        reopened_generator: Generator = Generator(name="Reopened routing owner")
        reopened_block_types: Dict[int, BlockType] = dict()
        restored_child: Block
        for restored_child in restored_root.children:
            reopened_block_types[restored_child.uid] = BlockType.GENERIC
        reopened_editor: DynamicBlockEditorGUI = DynamicBlockEditorGUI(
            var_factory=reopened_circuit.var_factory,
            root_block=restored_root,
            current_block=restored_root,
            api_object=reopened_generator,
            circuit=reopened_circuit,
            mode=DynamicSimulationMode.RMS,
            current_theme=DynEditorGraphicsModes.LIGHT,
            templates_list=list(),
            is_root_editor=False,
            modal=False,
            workspace_embedded=False,
            block2blocktype=reopened_block_types,
        )
        reopened_editor.show()
        qt_app.processEvents()
        try:
            reopened_connections: List[graph.ConnectionItem] = [
                scene_item for scene_item in reopened_editor.scene.items()
                if isinstance(scene_item, graph.ConnectionItem)
            ]
            assert len(reopened_connections) == 1
            reopened_connection: graph.ConnectionItem = reopened_connections[0]
            reopened_path_start: QtGui.QPainterPath.Element = reopened_connection.path().elementAt(0)
            reopened_source_endpoint: QtCore.QPointF = reopened_connection.source_port.scenePos()
            assert reopened_path_start.x == reopened_source_endpoint.x()
            assert reopened_path_start.y == reopened_source_endpoint.y()
            assert (
                reopened_editor.diagram.con_data[reopened_connection.con_uid].routing_payload
                == persisted_routing_payload
            )
        finally:
            reopened_editor.prepare_to_delete()
            reopened_editor.close()
            reopened_editor.deleteLater()
            qt_app.processEvents()
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()


def test_nuactis_transient_projection_move_keeps_every_wire_attached(
        qt_app: QtWidgets.QApplication,
) -> None:
    """Keep transient semantic-projection routes attached after a block move.

    Projected device, measurement and control items intentionally have no
    diagram-position callback because they are reconstructed from canonical
    model semantics. Their visible routes must nevertheless follow live port
    coordinates when the user moves one of those items.

    :param qt_app: Shared Qt application fixture.
    :return: None.
    """
    grid: MultiCircuit = _load_nuactis_rms_grid(
        fixture_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
    )
    vsc_devices: List[VSC] = grid.get_vsc()
    assert len(vsc_devices) > 0
    vsc: VSC = vsc_devices[0]
    assert isinstance(vsc.rms_model, Block)
    editor: DynamicBlockEditorGUI = _build_gui_editor(
        qt_app=qt_app,
        grid=grid,
        api_object=vsc,
        mode=DynamicSimulationMode.RMS,
        root_block=vsc.rms_model,
    )
    try:
        projected_items: List[graph.GenericBlockItem] = list(
            scene_item for scene_item in editor.scene.items()
            if isinstance(scene_item, graph.GenericBlockItem)
            and scene_item.position_changed_callback is None
        )
        moved_item: graph.GenericBlockItem | None = None
        incident_connections: List[graph.ConnectionItem] = list()
        projected_item: graph.GenericBlockItem
        for projected_item in projected_items:
            projected_connections: List[graph.ConnectionItem] = list()
            projected_port: graph.PortItem
            for projected_port in projected_item.inputs:
                if projected_port.connections is not None:
                    projected_connections.extend(projected_port.connections)
                else:
                    pass
            for projected_port in projected_item.outputs:
                if projected_port.connections is not None:
                    projected_connections.extend(projected_port.connections)
                else:
                    pass
            if moved_item is None and len(projected_connections) > 0:
                moved_item = projected_item
                incident_connections = projected_connections
            else:
                pass
        assert moved_item is not None
        assert len(incident_connections) > 0

        moved_item.setPos(moved_item.pos() + QtCore.QPointF(37.0, 43.0))
        qt_app.processEvents()

        connection: graph.ConnectionItem
        for connection in incident_connections:
            connection_path: QtGui.QPainterPath = connection.path()
            assert connection_path.elementCount() >= 2
            first_element: QtGui.QPainterPath.Element = connection_path.elementAt(0)
            last_element: QtGui.QPainterPath.Element = connection_path.elementAt(
                connection_path.elementCount() - 1
            )
            source_position: QtCore.QPointF = connection.source_port.scenePos()
            target_position: QtCore.QPointF = connection.target_port.scenePos()
            assert first_element.x == source_position.x()
            assert first_element.y == source_position.y()
            assert last_element.x == target_position.x()
            assert last_element.y == target_position.y()

            element_index: int
            for element_index in range(connection_path.elementCount() - 1):
                segment_start: QtGui.QPainterPath.Element = connection_path.elementAt(
                    element_index
                )
                segment_end: QtGui.QPainterPath.Element = connection_path.elementAt(
                    element_index + 1
                )
                horizontal: bool = abs(segment_start.y - segment_end.y) <= 1.0e-6
                vertical: bool = abs(segment_start.x - segment_end.x) <= 1.0e-6
                assert horizontal or vertical
    finally:
        editor.prepare_to_delete()
        editor.close()
        editor.deleteLater()
        qt_app.processEvents()
