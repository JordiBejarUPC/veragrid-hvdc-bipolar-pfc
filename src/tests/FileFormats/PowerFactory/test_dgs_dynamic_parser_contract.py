# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import hashlib
import math
from pathlib import Path
from typing import Sequence

import numpy as np
import pytest

from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_rms_measurement_binding import (
    DgsRmsMeasurementBindingReport,
    bind_dgs_rms_measurements,
)
from VeraGridEngine.IO.dgs.dgs_rms_preparation import (
    bind_dgs_switch_event_runtime,
)
from VeraGridEngine.IO.dgs.dgs_to_veragrid import (
    convert_dgs_to_monopolar_vsc,
    dgs_to_circuit,
)
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    DgsDirectRootBuildResult,
    DgsGraphicTreeResult,
    DgsGraphicalIndexes,
    DgsGraphicalConnectorKind,
    DgsRootBlockResult,
    ElmCompInstanceEntry,
    ParsedDgsBlockDefinition,
    UnsupportedDgsExpression,
    build_dgs_graphical_indexes,
    build_direct_root_elmcomp_block,
    build_graphical_arithmetic_block,
    build_graphical_switch_block,
    build_standalone_blkdef_block_from_parsed_block,
    dgs_to_root_block,
    build_dgs_root_block_from_circuit,
    extract_elmcomp_direct_instances,
    extract_root_slot_block_graphical_tree,
    extract_root_slot_graphical_tree_from_circuit,
    get_unambiguous_elmcomp_direct_instances,
    parse_dgs_block_definitions_from_circuit,
)
from VeraGridEngine.IO.dgs.dgs_objects import (
    BlkDef,
    BlkDiv,
    BlkFrom,
    BlkMul,
    BlkRef,
    BlkSig,
    BlkSlot,
    BlkSum,
    ElmComp,
    ElmDsl,
    ElmVscmono,
    StaCubic,
)
from VeraGridEngine.IO.dgs.dynamic_models.dynamic_model_import import (
    add_dynamic_import_selection_requests_to_circuit,
    apply_dgs_dynamic_templates_to_devices,
    build_dgs_dynamic_model_import_bundle,
    build_dynamic_import_template_fingerprint,
    convert_and_add_dgs_dynamic_templates_to_circuit,
    export_user_dynamic_template_json_from_block,
    load_user_dynamic_template_json_payload,
)
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions
from VeraGridEngine.IO.dynamic_model_import_types import (
    DynamicModelImportBundle,
    DynamicModelImportEntry,
    DynamicModelImportEntryAvailability,
    DynamicModelImportSelectionRequest,
    DynamicModelImportSource,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import (
    EmtProblemTemplate,
)
from VeraGridEngine.Utils.Symbolic.symbolic import (
    CmpOp,
    Comparison,
    Const,
    Expr,
    Var,
)
from VeraGridEngine.Utils.procedural_logic import (
    ConditionalDiagnosticLogic,
    DelayedSwitchEventLogic,
    ProceduralLogicCodec,
)
from VeraGridEngine.Templates.Rms.line_rms_template import (
    get_dc_line_rms_template,
)
from VeraGridEngine.Templates.Rms.transformer_rms_template import (
    get_transformer2w_rms,
)
from VeraGridEngine.basic_structures import LogEntry, Logger
from VeraGridEngine.enumerations import (
    ConverterControlType,
    DeviceType,
    DynamicSimulationMode,
    FileType,
)


class DgsSwitchEventProblem(EmtProblemTemplate):
    """Provide the smallest runtime problem needed to exercise a DGS switch event."""

    __slots__ = tuple()


def _get_dynamic_gain_block_dgs_path() -> Path:
    """Return the versioned DGS fixture containing supported and unsupported blocks."""

    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "DGS"
        / "dynamic_gain_block.dgs"
    )


def _get_native_graphical_operator_dgs_path() -> Path:
    """
    Return the versioned DGS fixture containing native graphical operators.

    :return: Path to the portable ASCII DGS fixture.
    """
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "DGS"
        / "native_graphical_operators.dgs"
    )


def _get_graphical_parent_signal_binding_dgs_path() -> Path:
    """Return the portable DGS fixture for parent-to-child signal binding.

    :return: Path to the versioned graphical parent contract fixture.
    """
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "DGS"
        / "graphical_parent_signal_binding.dgs"
    )


def _get_non_executable_slots_dgs_path() -> Path:
    """Return the portable DGS fixture for non-executable source slots.

    :return: Path to physical and vendor slots without exported pElm targets.
    """
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "DGS"
        / "non_executable_slots.dgs"
    )


# DGS contract: locate complete HVDC fixtures under generic public names.
def _get_complete_hvdc_vsc_dgs_path(file_name: str) -> Path:
    """Return one tracked complete static-and-dynamic HVDC VSC export.

    :param file_name: Exact fixture file name.
    :return: Absolute path to the requested generic HVDC VSC DGS fixture.
    """
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "DGS"
        / file_name
    )


def _parse_native_graphical_operator_fixture() -> DgsCircuit:
    """
    Parse the portable graph containing native arithmetic and switching nodes.

    :return: Parsed circuit containing the native graphical records and cables.
    """
    dgs_path: Path = _get_native_graphical_operator_dgs_path()
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    return circuit


# Dynamic contract: build a minimal fixture for per-instance BlkRef parameters.
def _build_nested_graphical_parent_fixture() -> tuple[
    DgsCircuit,
    ElmComp,
    ElmComp,
    BlkRef,
]:
    """Build one exact nested ElmComp relation reached by a graphical BlkRef.

    :return: Circuit, selected root, nested component and reached BlkRef.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    circuit.blkslots[0].filtmod = "ElmComp"

    nested_component: ElmComp = ElmComp()
    nested_component.ID = "NESTED_COMPONENT"
    nested_component.loc_name = "Nested graphical component"
    nested_component.typ_id = "MACRO"
    circuit.elmcomps.append(nested_component)
    root_element.pelm[0] = nested_component.ID

    child_definition: BlkDef = BlkDef()
    child_definition.ID = "NESTED_CHILD_DEFINITION"
    child_definition.loc_name = "Nested child definition"
    child_definition.inputs.append("external_x")
    circuit.blkdefs.append(child_definition)

    child_reference: BlkRef = BlkRef()
    child_reference.ID = "NESTED_CHILD_REFERENCE"
    child_reference.typ_id = child_definition.ID
    circuit.blkrefs.append(child_reference)

    child_signal: BlkSig = BlkSig()
    child_signal.ID = "ROOT_TO_NESTED_CHILD"
    child_signal.loc_name = "external_x"
    child_signal.inodfrom = 0
    child_signal.iconfrom = 1
    child_signal.inodto = 0
    child_signal.iconto = 1
    child_signal.pnodfrom = "MACRO"
    child_signal.pnodto = child_reference.ID
    circuit.blksigs.append(child_signal)

    return circuit, root_element, nested_component, child_reference


@pytest.mark.parametrize(
    (
        "file_name",
        "expected_sha256",
        "expected_counts",
    ),
    (
        (
            "hvdc_vsc_v1_complete_static_dynamic.dgs",
            "0065D822C38D57F51126D743CEB5BB5665CF0C0A88C65050B1BFC4F93D90E0F0",
            (0, 2, 2, 2, 12, 9, 10),
        ),
        (
            "hvdc_vsc_v2_complete_static_dynamic.dgs",
            "D8D8341DD60632A6A01EE6516324336CC6CB50942BA58C1BC3A520252970D334",
            (0, 2, 2, 2, 11, 11, 10),
        ),
        (
            "hvdc_vsc_v3_complete_static_dynamic.dgs",
            "E34DA6F5DCD229B90379A17940D072E02BAF9382BD8405E96FF7175330294C57",
            (2, 0, 2, 3, 33, 19, 17),
        ),
    ),
)
# DGS contract: verify that the static and dynamic domains survive together.
def test_complete_hvdc_vsc_exports_preserve_static_and_dynamic_sections(
        file_name: str,
        expected_sha256: str,
        expected_counts: tuple[int, int, int, int, int, int, int],
) -> None:
    """Parse immutable generic HVDC exports without losing either model domain.

    :param file_name: Exact tracked fixture name.
    :param expected_sha256: Provenance checksum of the source export.
    :param expected_counts: Expected converter, PLL, composite, DSL, block and bus counts.
    :return: None.
    """
    dgs_path: Path = _get_complete_hvdc_vsc_dgs_path(file_name=file_name)
    source_bytes: bytes = dgs_path.read_bytes()
    source_sha256: str = hashlib.sha256(source_bytes).hexdigest().upper()
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    parsed_counts: tuple[int, int, int, int, int, int, int] = (
        len(circuit.elmvscs),
        len(circuit.elmvscmonos),
        len(circuit.elmphis),
        len(circuit.elmcomps),
        len(circuit.elmdsls),
        len(circuit.blkdefs),
        len(circuit.elmterms),
    )

    assert source_sha256 == expected_sha256
    assert parsed_counts == expected_counts


@pytest.mark.parametrize(
    ("file_name", "equipment_class"),
    (
        ("hvdc_vsc_v1_complete_static_dynamic.dgs", "ElmVscmono"),
        ("hvdc_vsc_v2_complete_static_dynamic.dgs", "ElmVscmono"),
        ("hvdc_vsc_v3_complete_static_dynamic.dgs", "ElmVsc"),
    ),
)
# Dynamic contract: verify the exact physical BlkSlot linking each VSC by FID.
def test_complete_hvdc_vsc_exports_declare_directional_equipment_slots(
        file_name: str,
        equipment_class: str,
) -> None:
    """Retain one directional physical slot per converter composite.

    :param file_name: Exact tracked fixture name.
    :param equipment_class: Native converter class expected in each root.
    :return: None.
    """
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(
        path=str(_get_complete_hvdc_vsc_dgs_path(file_name=file_name))
    )
    physical_entries: list[ElmCompInstanceEntry] = list()
    root_element: ElmComp
    for root_element in dgs_circuit.elmcomps:
        direct_entry: ElmCompInstanceEntry
        for direct_entry in extract_elmcomp_direct_instances(
                circuit=dgs_circuit,
                root_element=root_element,
        ):
            if direct_entry.element_kind == equipment_class:
                physical_entries.append(direct_entry)
            else:
                pass

    assert len(physical_entries) == 2
    physical_entry: ElmCompInstanceEntry
    for physical_entry in physical_entries:
        assert physical_entry.slot_reference_is_resolved
        assert physical_entry.element_reference_is_resolved
        if equipment_class == "ElmVscmono":
            assert {"id", "iq", "uDC"}.issubset(physical_entry.slot_outputs)
            assert {"Pmd", "Pmq"}.issubset(physical_entry.slot_inputs)
            assert {"cosref", "sinref"}.issubset(physical_entry.slot_inputs)
        else:
            assert equipment_class == "ElmVsc"
            assert {"Pmr", "Pmi", "mdc"}.issubset(
                physical_entry.slot_inputs
            )
            assert (
                {"iDC", "yUcell"}.issubset(physical_entry.slot_outputs)
                or {"idc", "Ucap"}.issubset(physical_entry.slot_outputs)
            )


@pytest.mark.parametrize(
    ("file_name", "second_active_power_setpoint"),
    (
        ("hvdc_vsc_v1_complete_static_dynamic.dgs", 1000.0),
        ("hvdc_vsc_v2_complete_static_dynamic.dgs", 1000.0),
        ("hvdc_vsc_v3_complete_static_dynamic.dgs", -1000.0),
    ),
)
# Alex review required: converter controls use configured setpoints, never solved m:* columns.
def test_hvdc_vsc_converter_controls_use_configuration_not_solved_outputs(
        file_name: str,
        second_active_power_setpoint: float,
) -> None:
    """Build generic HVDC converters from configured targets, never ``m:*`` results.

    :param file_name: Exact tracked fixture name.
    :param second_active_power_setpoint: Configured active-power target of converter two.
    :return: None.
    """
    dgs_path: Path = _get_complete_hvdc_vsc_dgs_path(file_name=file_name)
    circuit: MultiCircuit = dgs_to_circuit(path=str(dgs_path))
    first_converter: VSC = circuit.vsc_devices[0]
    second_converter: VSC = circuit.vsc_devices[1]

    assert len(circuit.vsc_devices) == 2
    assert first_converter.control1 is ConverterControlType.Vm_dc
    assert first_converter.control1_val == pytest.approx(1.0)
    assert first_converter.control2 is ConverterControlType.Qac
    assert first_converter.control2_val == pytest.approx(0.0)
    assert second_converter.control1 is ConverterControlType.Pac
    assert second_converter.control1_val == pytest.approx(
        second_active_power_setpoint
    )
    assert second_converter.control2 is ConverterControlType.Qac
    assert second_converter.control2_val == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("file_name", "equipment_class"),
    (
        ("hvdc_vsc_v1_complete_static_dynamic.dgs", "ElmVscmono"),
        ("hvdc_vsc_v2_complete_static_dynamic.dgs", "ElmVscmono"),
        ("hvdc_vsc_v3_complete_static_dynamic.dgs", "ElmVsc"),
    ),
)
# Dynamic contract: V1/V2/V3 follow Block to template to circuit to VSC by FID.
def test_complete_hvdc_vsc_exports_apply_direct_dynamic_templates_by_fid(
        file_name: str,
        equipment_class: str,
) -> None:
    """Register every root and assign each converter template by exact FID.

    :param file_name: Exact tracked fixture name.
    :param equipment_class: Native converter class expected in each root.
    :return: None.
    """
    dgs_path: Path = _get_complete_hvdc_vsc_dgs_path(file_name=file_name)
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(path=str(dgs_path))
    destination: MultiCircuit = dgs_to_circuit(path=str(dgs_path))
    logger: Logger = Logger()
    templates_by_root_id: dict[
        str,
        RmsModelTemplate | EmtModelTemplate,
    ] = convert_and_add_dgs_dynamic_templates_to_circuit(
        dgs_circuit=dgs_circuit,
        circuit=destination,
        target_domain=DynamicSimulationMode.RMS,
        logger=logger,
    )
    apply_dgs_dynamic_templates_to_devices(
        dgs_circuit=dgs_circuit,
        circuit=destination,
        templates_by_root_dgs_id=templates_by_root_id,
        logger=logger,
    )

    expected_root_ids: set[str] = set()
    root_element: ElmComp
    for root_element in dgs_circuit.elmcomps:
        expected_root_ids.add(root_element.ID)
    import_diagnostics: list[tuple[str, str]] = list()
    log_entry: LogEntry
    for log_entry in logger.entries:
        import_diagnostics.append((log_entry.msg, str(log_entry.value)))
    assert set(templates_by_root_id.keys()) == expected_root_ids, import_diagnostics

    assigned_converter_count: int = 0
    for root_element in dgs_circuit.elmcomps:
        root_template: RmsModelTemplate | EmtModelTemplate = (
            templates_by_root_id[root_element.ID]
        )
        assert any(
            registered_template is root_template
            for registered_template in destination.rms_models
        )
        direct_entry: ElmCompInstanceEntry
        for direct_entry in extract_elmcomp_direct_instances(
                circuit=dgs_circuit,
                root_element=root_element,
        ):
            if direct_entry.element_kind == equipment_class:
                assert direct_entry.element_id is not None
                matching_hosts: list[VSC] = [
                    host
                    for host in destination.vsc_devices
                    if host.idtag == direct_entry.element_id
                ]
                assert len(matching_hosts) == 1
                assert matching_hosts[0].rms_template is root_template
                assigned_converter_count += 1
            else:
                pass

    assert assigned_converter_count == 2
    assert logger.warning_count() == 0
    assert logger.error_count() == 0


def test_v3_switch_events_bind_guarded_modes_to_exact_rms_equipment() -> None:
    """Bind every enabled V3 EvtSwitch chain to a physical conduction state.

    :return: None.
    """
    dgs_path: Path = _get_complete_hvdc_vsc_dgs_path(
        file_name="hvdc_vsc_v3_complete_static_dynamic.dgs"
    )
    logger: Logger = Logger()
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(path=str(dgs_path))
    circuit: MultiCircuit = dgs_to_circuit(path=str(dgs_path))
    templates_by_root_id: dict[
        str,
        RmsModelTemplate | EmtModelTemplate,
    ] = convert_and_add_dgs_dynamic_templates_to_circuit(
        dgs_circuit=dgs_circuit,
        circuit=circuit,
        target_domain=DynamicSimulationMode.RMS,
        logger=logger,
    )
    apply_dgs_dynamic_templates_to_devices(
        dgs_circuit=dgs_circuit,
        circuit=circuit,
        templates_by_root_dgs_id=templates_by_root_id,
        logger=logger,
    )

    event_target_ids: set[str] = set(("242", "243", "273", "274"))
    prepared_target_ids: set[str] = set()
    target_device: DynamicDevice
    for target_device in circuit.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=True,
    ):
        if target_device.idtag not in event_target_ids:
            pass
        else:
            if isinstance(target_device, Line):
                target_template: RmsModelTemplate = get_dc_line_rms_template(
                    vfactory=circuit.var_factory,
                    use_dynamic_inductance=False,
                )
            else:
                if isinstance(target_device, Transformer2W):
                    target_template = get_transformer2w_rms(
                        vf=circuit.var_factory,
                    )
                else:
                    raise AssertionError(
                        f"Unexpected switch-event target {target_device.idtag}"
                    )
            target_device.rms_model = target_template.block
            prepared_target_ids.add(target_device.idtag)

    assert prepared_target_ids == event_target_ids

    imported_event_output_names: set[str] = set()
    imported_mode_names: set[str] = set()
    imported_event_count: int = 0
    imported_event_count_by_root_id: dict[str, int] = dict()
    imported_root_template: RmsModelTemplate | EmtModelTemplate
    imported_block: Block
    imported_logic: object
    imported_mode: Var
    for imported_root_template in templates_by_root_id.values():
        root_event_count: int = 0
        for imported_block in imported_root_template.block.get_all_blocks():
            for imported_logic in imported_block.procedural_logic:
                if isinstance(imported_logic, DelayedSwitchEventLogic):
                    imported_event_count += 1
                    root_event_count += 1
                    imported_event_output_names.add(
                        imported_logic.output_var_name
                    )
                else:
                    pass
            for imported_mode in imported_block.mode_dict.keys():
                imported_mode_names.add(imported_mode.name)
        matching_root_ids: list[str] = list(
            root_id
            for root_id, candidate_template in templates_by_root_id.items()
            if candidate_template is imported_root_template
        )
        assert len(matching_root_ids) == 1
        imported_event_count_by_root_id[matching_root_ids[0]] = root_event_count
    assert imported_event_output_names.issubset(imported_mode_names), (
        imported_event_output_names,
        imported_mode_names,
    )
    assert imported_event_count == 16, imported_event_count_by_root_id

    bound_target_count: int = bind_dgs_switch_event_runtime(
        circuit=circuit,
        templates_by_root_dgs_id=templates_by_root_id,
        logger=logger,
    )
    binding_diagnostics: list[tuple[str, str, str]] = list(
        (log_entry.msg, log_entry.device, log_entry.value)
        for log_entry in logger.entries
    )
    assert bound_target_count == 4, binding_diagnostics

    switch_events: list[DelayedSwitchEventLogic] = list()
    registered_template: RmsModelTemplate
    event_block: Block
    logic_entry: object
    for registered_template in circuit.rms_models:
        for event_block in registered_template.block.get_all_blocks():
            for logic_entry in event_block.procedural_logic:
                if isinstance(logic_entry, DelayedSwitchEventLogic):
                    switch_events.append(logic_entry)
                else:
                    pass

    assert len(switch_events) == 16
    assert all(event.initial_closed for event in switch_events)
    assert all(not event.command_closed for event in switch_events)
    switch_ids: set[str] = set(
        event.target_switch_idtag for event in switch_events
    )
    target_device_ids: set[str] = set(
        event.target_device_idtag for event in switch_events
    )
    assert len(switch_ids) == 8
    assert target_device_ids == event_target_ids

    expected_switch_mode_count_by_device: dict[str, int] = dict()
    expected_switch_mode_count_by_device["242"] = 4
    expected_switch_mode_count_by_device["243"] = 4
    expected_switch_mode_count_by_device["273"] = 4
    expected_switch_mode_count_by_device["274"] = 4
    physical_branch: DynamicDevice
    for physical_branch in circuit.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=True,
    ):
        expected_mode_count: int | None = (
            expected_switch_mode_count_by_device.get(
                physical_branch.idtag,
                None,
            )
        )
        if expected_mode_count is None:
            pass
        else:
            conduction_expressions: list[Expr] = list()
            physical_block: Block
            conduction_parameter: Var
            conduction_expression: Expr
            for physical_block in physical_branch.rms_model.get_all_blocks():
                for conduction_parameter, conduction_expression in physical_block.event_dict.items():
                    if conduction_parameter.name == "u":
                        conduction_expressions.append(conduction_expression)
                    else:
                        pass
            assert len(conduction_expressions) == 1
            switch_mode_names: set[str] = set(
                variable.name
                for variable in conduction_expressions[0].get_vars()
                if variable.name.startswith("dgs_switch_")
            )
            assert len(switch_mode_names) == expected_mode_count

    switch_binding_diagnostics: list[str] = list(
        log_entry.msg
        for log_entry in logger.entries
        if log_entry.msg.startswith("DGS switch")
    )
    assert switch_binding_diagnostics == list()


def test_delayed_switch_event_opens_on_the_guarded_trigger_boundary() -> None:
    """Execute a rising trigger and open the retained mode at exact ``dtime``.

    :return: None.
    """
    variable_factory: VarFactory = VarFactory()
    trigger: Var = variable_factory.add_var("switch_trigger")
    switch_mode: Var = variable_factory.add_var("switch_closed")
    event_logic: DelayedSwitchEventLogic = DelayedSwitchEventLogic(
        output_var_name=switch_mode.name,
        guard_expr=Const(1.0),
        trigger_expr=trigger,
        delay_expr=Const(0.25),
        target_device_idtag="TARGET_DEVICE",
        target_switch_idtag="TARGET_SWITCH",
        target_terminal_index=0,
        initial_closed=True,
        command_closed=False,
        name="Open target switch",
    )
    event_values: dict[Var, float] = dict()
    event_values[trigger] = 0.0
    mode_values: dict[Var, float] = dict()
    mode_values[switch_mode] = 1.0
    procedural_entries: list[DelayedSwitchEventLogic] = list()
    procedural_entries.append(event_logic)
    block: Block = Block(
        name="DGS delayed switch event runtime",
        event_dict=event_values,
        mode_dict=mode_values,
        procedural_logic=procedural_entries,
    )
    block.unify_blocks()
    problem: DgsSwitchEventProblem = DgsSwitchEventProblem(
        sys_block=block,
        glob_time=variable_factory.add_var("glob_time"),
        static_parameter_values_mapping=dict(block.parameters),
    )
    event_logic.bind(problem=problem)
    params: np.ndarray = problem.event_params_values.copy()
    state: np.ndarray = problem.get_x0().copy()
    trigger_index: int = problem.uid2idx_event_params[trigger.uid]
    switch_index: int = problem.uid2idx_event_params[switch_mode.uid]

    event_logic.update(t=0.0, x=state, params=params)
    assert params[switch_index] == 1.0

    params[trigger_index] = 1.0
    event_logic.update(t=1.0, x=state, params=params)
    forced_event_time: float | None = event_logic.get_next_forced_event_time(
        t_prev=1.0,
        t_target=2.0,
    )
    assert forced_event_time == pytest.approx(1.25)

    event_logic.update(t=1.249, x=state, params=params)
    assert params[switch_index] == 1.0
    event_logic.update(t=1.25, x=state, params=params)
    assert params[switch_index] == 0.0
    assert event_logic.fired


def test_inc0_is_only_a_fallback_for_explicit_initialization() -> None:
    """Keep inc0 unless a later authoritative inc declaration replaces it.

    :return: None.
    """
    fallback_definition: BlkDef = BlkDef()
    fallback_definition.ID = "inc0_fallback"
    fallback_definition.loc_name = "Inc0Fallback"
    fallback_definition.outputs = list(("y",))
    fallback_definition.states = list(("x",))
    fallback_definition.equations_raw = list(("inc0(x)=1.0;y=x",))

    override_definition: BlkDef = BlkDef()
    override_definition.ID = "inc_override"
    override_definition.loc_name = "IncOverride"
    override_definition.outputs = list(("y",))
    override_definition.states = list(("x",))
    override_definition.equations_raw = list((
        "inc0(x)=1.0;inc(x)=2.0;inc0(x)=3.0;y=x",
    ))

    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.blkdefs = list((fallback_definition, override_definition))
    parsed_blocks: dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=dgs_circuit)
    )

    fallback_expression: Expr = parsed_blocks["inc0_fallback"].init_rhs["x"]
    override_expression: Expr = parsed_blocks["inc_override"].init_rhs["x"]
    fallback_block: Block = build_standalone_blkdef_block_from_parsed_block(
        parsed_block=parsed_blocks["inc0_fallback"],
    )
    override_block: Block = build_standalone_blkdef_block_from_parsed_block(
        parsed_block=parsed_blocks["inc_override"],
    )
    fallback_block_expression: Expr = next(iter(fallback_block.init_eqs.values()))
    override_block_expression: Expr = next(iter(override_block.init_eqs.values()))

    assert fallback_expression.eval_uid(dict()) == pytest.approx(1.0)
    assert override_expression.eval_uid(dict()) == pytest.approx(2.0)
    assert len(fallback_block.init_eqs) == 1
    assert len(override_block.init_eqs) == 1
    assert fallback_block_expression.eval_uid(dict()) == pytest.approx(1.0)
    assert override_block_expression.eval_uid(dict()) == pytest.approx(2.0)


# Alex review required: an additional VSC cubicle invalidates the complete topology.
def test_monopolar_vsc_rejects_an_unexpected_extra_cubicle() -> None:
    """Reject topology that contains the expected roles plus an extra cubicle.

    :return: None.
    """
    source: ElmVscmono = ElmVscmono()
    source.ID = "VSC_SOURCE"
    source.loc_name = "Generic monopolar converter"
    ac_bus: Bus = Bus(name="AC bus", Vnom=220.0)
    dc_bus: Bus = Bus(name="DC bus", Vnom=320.0)
    extra_bus: Bus = Bus(name="Unexpected bus", Vnom=320.0)

    ac_cubicle: StaCubic = StaCubic()
    ac_cubicle.ID = "AC_CUBICLE"
    ac_cubicle.fold_id = "AC_TERMINAL"
    ac_cubicle.obj_bus = 0
    dc_cubicle: StaCubic = StaCubic()
    dc_cubicle.ID = "DC_CUBICLE"
    dc_cubicle.fold_id = "DC_TERMINAL"
    dc_cubicle.obj_bus = 1
    extra_cubicle: StaCubic = StaCubic()
    extra_cubicle.ID = "EXTRA_CUBICLE"
    extra_cubicle.fold_id = "EXTRA_TERMINAL"
    extra_cubicle.obj_bus = 2
    logger: Logger = Logger()

    converter: VSC | None = convert_dgs_to_monopolar_vsc(
        source=source,
        cubics_by_objid={
            source.ID: [ac_cubicle, dc_cubicle, extra_cubicle],
        },
        bus_by_term_id={
            "AC_TERMINAL": ac_bus,
            "DC_TERMINAL": dc_bus,
            "EXTRA_TERMINAL": extra_bus,
        },
        switch_by_cubic_id=dict(),
        system_base_mva=100.0,
        frequency_hz=50.0,
        logger=logger,
    )

    assert converter is None
    assert logger.warning_count() == 1


def test_dgs_parser_preserves_dynamic_composite_rows_without_inventing_types() -> None:
    """Preserve exact dynamic rows from a tracked PowerFactory DGS export."""

    dgs_path: Path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "test_ieee14_svs.dgs"
    )
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))

    composite_rows: list[tuple[str, str, str, int, str | None]] = [
        (model.ID, model.loc_name, model.fold_id, model.outserv, model.typ_id)
        for model in circuit.elmcomps
    ]
    assert composite_rows == [
        ("2", "WECC WT Control System Type 4B(1)", "85", 0, None),
        ("3", "WECC WT Control System Type 4B(2)", "85", 0, None),
        ("4", "WECC WT Control System Type 4B(3)", "85", 0, None),
        ("5", "WECC WT Control System Type 4B(4)", "85", 0, None),
        ("6", "WECC WT Control System Type 4B(6)", "85", 0, None),
        ("7", "WECC WT Control System Type 4B(7)", "85", 0, None),
        ("8", "WECC WT Control System Type 4B(8)", "85", 0, None),
        ("9", "WECC WT Control System Type 4B", "85", 0, None),
    ]
    assert len(circuit.elmdsls) == 40
    assert len(circuit.blkdefs) == 0
    assert len(circuit.blkslots) == 0


def test_dgs_parser_preserves_static_var_system_runtime_constants() -> None:
    """Keep the exact SVC values consumed by the dynamic runtime adapter."""

    dgs_path: Path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "test_ieee14_svs.dgs"
    )
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))

    static_var_system_rows: list[
        tuple[str, str, float, float, int, int, float]
    ] = [
        (
            device.ID,
            device.loc_name,
            device.tcrmax,
            device.qmin,
            device.nxcap,
            device.nfixcap,
            device.Qfixcap,
        )
        for device in circuit.elmsvss
    ]
    assert static_var_system_rows == [
        ("86", "SVS_Droop", 10.0, -20.0, 2, 0, 0.0),
        ("87", "SVS_NoControl", 5.0, -10.0, 1, 0, 0.0),
        ("88", "SVS_Qcontrol", 30.0, -15.0, 2, 1, -5.0),
        ("89", "SVS_Ucontrol", 0.0, 0.0, 0, 0, 0.0),
    ]


def test_dgs_parser_preserves_native_graphical_operator_records() -> None:
    """
    Preserve native arithmetic and switch records for later graph materialization.

    :return: None.
    """
    circuit: DgsCircuit = _parse_native_graphical_operator_fixture()

    division_rows: list[tuple[str, str, str]] = [
        (operator.ID, operator.OP, operator.loc_name)
        for operator in circuit.blkdivs
    ]
    multiplication_rows: list[tuple[str, str, str]] = [
        (operator.ID, operator.OP, operator.loc_name)
        for operator in circuit.blkmuls
    ]
    switch_rows: list[tuple[str, str, str, int]] = [
        (operator.ID, operator.OP, operator.loc_name, operator.iNeg)
        for operator in circuit.blkswts
    ]
    assert division_rows == [("DIV", "C", "Divide power by voltage")]
    assert multiplication_rows == [("MUL", "C", "Multiply signals")]
    assert switch_rows == [("SWT", "C", "Select signal", 0)]
    assert circuit.blkgotos[0].signals == ["route_a", "route_b"]


def test_native_graphical_arithmetic_records_build_executable_blocks(
) -> None:
    """
    Execute the ordered division and multiplication encoded by native DGS nodes.

    :return: None.
    """
    circuit: DgsCircuit = _parse_native_graphical_operator_fixture()
    arithmetic_nodes: tuple[BlkDiv | BlkMul, ...] = (
        circuit.blkdivs[0],
        circuit.blkmuls[0],
    )
    arithmetic_results: list[
        tuple[
            Block,
            list[str],
            list[str],
            dict[tuple[DgsGraphicalConnectorKind, int], int],
        ]
    ] = list()
    arithmetic_node: BlkDiv | BlkMul

    for arithmetic_node in arithmetic_nodes:
        arithmetic_results.append(
            build_graphical_arithmetic_block(
                node=arithmetic_node,
                circuit=circuit,
            )
        )

    division_block: Block
    division_inputs: list[str]
    division_outputs: list[str]
    division_input_index_by_connector: dict[
        tuple[DgsGraphicalConnectorKind, int],
        int,
    ]
    (
        division_block,
        division_inputs,
        division_outputs,
        division_input_index_by_connector,
    ) = arithmetic_results[0]
    multiplication_block: Block
    multiplication_inputs: list[str]
    multiplication_outputs: list[str]
    multiplication_input_index_by_connector: dict[
        tuple[DgsGraphicalConnectorKind, int],
        int,
    ]
    (
        multiplication_block,
        multiplication_inputs,
        multiplication_outputs,
        multiplication_input_index_by_connector,
    ) = arithmetic_results[1]

    assert division_inputs == ["Pord", "Vt"]
    assert division_outputs == ["Ip_unlim"]
    assert division_input_index_by_connector == {
        (DgsGraphicalConnectorKind.Input, 0): 0,
        (DgsGraphicalConnectorKind.Input, 1): 1,
    }
    assert division_block.post_init_seed_eqs[
        division_block.out_vars[0]
    ].eval(Pord=0.8, Vt=0.5) == pytest.approx(1.6)
    assert multiplication_inputs == ["a", "b", "c"]
    assert multiplication_outputs == ["product"]
    assert multiplication_input_index_by_connector == {
        (DgsGraphicalConnectorKind.Input, 0): 0,
        (DgsGraphicalConnectorKind.Input, 1): 1,
        (DgsGraphicalConnectorKind.Input, 2): 2,
    }
    assert multiplication_block.post_init_seed_eqs[
        multiplication_block.out_vars[0]
    ].eval(a=2.0, b=3.0, c=4.0) == pytest.approx(24.0)


def test_native_graphical_switch_record_builds_threshold_logic() -> None:
    """
    Execute both native switch positions and the exported inverted position.

    :return: None.
    """
    circuit: DgsCircuit = _parse_native_graphical_operator_fixture()
    switch_block: Block
    switch_inputs: list[str]
    switch_outputs: list[str]
    switch_input_index_by_connector: dict[
        tuple[DgsGraphicalConnectorKind, int],
        int,
    ]
    (
        switch_block,
        switch_inputs,
        switch_outputs,
        switch_input_index_by_connector,
    ) = build_graphical_switch_block(
        node=circuit.blkswts[0],
        circuit=circuit,
    )
    switch_expression: Expr = switch_block.post_init_seed_eqs[switch_block.out_vars[0]]

    assert switch_inputs == ["default_input", "changed_input", "control"]
    assert switch_outputs == ["selected"]
    assert switch_input_index_by_connector == {
        (DgsGraphicalConnectorKind.Input, 0): 0,
        (DgsGraphicalConnectorKind.Input, 1): 1,
        (DgsGraphicalConnectorKind.UpperLimitInput, 0): 2,
    }
    assert switch_expression.eval(
        default_input=10.0,
        changed_input=20.0,
        control=0.4,
    ) == pytest.approx(10.0)
    assert switch_expression.eval(
        default_input=10.0,
        changed_input=20.0,
        control=0.6,
    ) == pytest.approx(20.0)

    circuit.blkswts[0].iNeg = 1
    inverted_block: Block = build_graphical_switch_block(
        node=circuit.blkswts[0],
        circuit=circuit,
    )[0]
    inverted_expression: Expr = inverted_block.post_init_seed_eqs[inverted_block.out_vars[0]]
    assert inverted_expression.eval(
        default_input=10.0,
        changed_input=20.0,
        control=0.4,
    ) == pytest.approx(20.0)
    assert inverted_expression.eval(
        default_input=10.0,
        changed_input=20.0,
        control=0.6,
    ) == pytest.approx(10.0)


# Dynamic contract: a sparse BlkSum retains raw output port four.
def test_sparse_native_sum_resolves_its_exported_output_port() -> None:
    """Resolve a sum with active raw inputs zero and three to output pin four.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    circuit.blksigs = [
        signal
        for signal in circuit.blksigs
        if signal.ID != "MUL_TO_ROOT"
    ]
    sparse_sum: BlkSum = BlkSum()
    sparse_sum.ID = "SPARSE_SUM"
    sparse_sum.loc_name = "Sparse sum producer"
    sparse_sum.iInput0 = 0
    sparse_sum.iInput3 = 0
    circuit.blksums.append(sparse_sum)

    raw_input_index: int
    for raw_input_index in (0, 3):
        input_signal: BlkSig = BlkSig()
        input_signal.ID = f"ROOT_TO_SPARSE_SUM_{raw_input_index}"
        input_signal.loc_name = "external_x"
        input_signal.inodfrom = 0
        input_signal.iconfrom = 1
        input_signal.inodto = raw_input_index
        input_signal.iconto = 0
        input_signal.pnodfrom = "MACRO"
        input_signal.pnodto = sparse_sum.ID
        circuit.blksigs.append(input_signal)

    output_signal: BlkSig = BlkSig()
    output_signal.ID = "SPARSE_SUM_TO_ROOT"
    output_signal.loc_name = "public_y"
    output_signal.inodfrom = 4
    output_signal.iconfrom = 0
    output_signal.inodto = 0
    output_signal.iconto = 2
    output_signal.pnodfrom = sparse_sum.ID
    output_signal.pnodto = "MACRO"
    circuit.blksigs.append(output_signal)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    graphical_tree: DgsGraphicTreeResult | None = (
        extract_root_slot_graphical_tree_from_circuit(
            circuit=circuit,
            result=root_result,
            slot_name="Graphical parent",
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )
    )

    assert graphical_tree is not None
    sparse_block: Block | None = None
    child_block: Block
    for child_block in graphical_tree.view_block.children:
        if child_block.name == sparse_sum.loc_name:
            sparse_block = child_block
        else:
            pass
    assert sparse_block is not None
    assert graphical_tree.view_block.out_vars[0].uid == sparse_block.out_vars[0].uid


def test_graphical_parent_binds_exact_child_signals_and_keeps_live_gaps() -> None:
    """Bind parent initialization through a complete portable DGS graph.

    :return: None.
    """
    graphical_tree: DgsGraphicTreeResult | None = (
        extract_root_slot_block_graphical_tree(
            dgs_path=str(_get_graphical_parent_signal_binding_dgs_path()),
            slot_name="Graphical parent",
            root_name="Graphical root",
            root_typ_id="FRAME",
        )
    )

    assert graphical_tree is not None
    assert graphical_tree.parent_bindings.resolved_internal_names == [
        "blank_internal",
        "produced_internal",
    ]
    assert graphical_tree.parent_bindings.disconnected_input_names == [
        "blank_internal",
    ]
    assert graphical_tree.parent_bindings.unresolved_input_names == [
        "routed_internal",
    ]

    produced_output_uid: int | None = None
    disconnected_input_uid: int | None = None
    disconnected_event: Expr | None = None
    child_block: Block

    # Locate the concrete child identities that must replace the parent's raw
    # internal variables.
    for child_block in graphical_tree.view_block.children:
        if child_block.name == "Multiply parent inputs":
            produced_output_uid = child_block.out_vars[0].uid
        else:
            pass
        if child_block.name == "Consume disconnected input":
            assert len(child_block.event_dict) == 1
            disconnected_input_uid = list(child_block.event_dict.keys())[0].uid
            disconnected_event = list(child_block.event_dict.values())[0]
        else:
            pass

    assert produced_output_uid is not None
    assert disconnected_input_uid is not None
    assert disconnected_event is not None
    assert disconnected_event.eval() == 0.0
    assert graphical_tree.view_block.out_vars[0].uid == produced_output_uid
    assert graphical_tree.view_block.out_vars[0].name == "public_y"

    parent_init_expressions: list[Expr] = list(
        graphical_tree.view_block.init_eqs.values()
    )
    assert len(parent_init_expressions) == 1
    parent_dependency_uids: set[int] = set(
        dependency_var.uid
        for dependency_var in parent_init_expressions[0].get_vars()
    )
    parent_dependency_names: set[str] = set(
        dependency_var.name
        for dependency_var in parent_init_expressions[0].get_vars()
    )
    assert produced_output_uid in parent_dependency_uids
    assert disconnected_input_uid in parent_dependency_uids
    assert "routed_internal" in parent_dependency_names


# Dynamic contract: a macro output without a producer does not retain a dead Var.
def test_graphical_macro_rejects_an_output_without_semantics() -> None:
    """Reject a public macro output with no producer or explicit equation.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    dynamic_element: ElmDsl = circuit.elmdsls[0]
    dynamic_definition: BlkDef | None = None
    candidate_definition: BlkDef
    for candidate_definition in circuit.blkdefs:
        if candidate_definition.ID == dynamic_element.typ_id:
            dynamic_definition = candidate_definition
        else:
            pass
    assert dynamic_definition is not None
    dynamic_definition.outputs.append("unproduced_output")

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="Graphical DGS macro output has no producer",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: inc(y) alone replaces neither a producer nor a runtime equation.
def test_graphical_macro_rejects_an_init_only_output() -> None:
    """Reject a macro output that has initialization but no runtime producer.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    remaining_signals: list[BlkSig] = [
        signal
        for signal in circuit.blksigs
        if signal.ID != "MUL_TO_ROOT"
    ]
    circuit.blksigs = remaining_signals

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="Graphical DGS macro output has no producer",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: two explicit cables cannot silently select the first one.
def test_graphical_macro_rejects_multiple_explicit_input_cables() -> None:
    """Reject two exact graphical cables targeting the same runtime input.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]

    duplicate_signal: BlkSig = BlkSig()
    duplicate_signal.ID = "DUPLICATE_ROOT_TO_MUL_0"
    duplicate_signal.loc_name = "external_x"
    duplicate_signal.inodfrom = 0
    duplicate_signal.iconfrom = 1
    duplicate_signal.inodto = 0
    duplicate_signal.iconto = 0
    duplicate_signal.pnodfrom = "MACRO"
    duplicate_signal.pnodto = "MUL"
    circuit.blksigs.append(duplicate_signal)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="Graphical DGS input has multiple explicit cables",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: an invalid root source connector does not fall back to aliases.
def test_graphical_macro_rejects_an_invalid_explicit_source_connector() -> None:
    """Reject an exact cable whose root endpoint declares output direction.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    graphical_signal: BlkSig
    for graphical_signal in circuit.blksigs:
        if graphical_signal.ID == "ROOT_TO_MUL_0":
            graphical_signal.iconfrom = 2
        else:
            pass

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="invalid root source connector",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


@pytest.mark.parametrize(
    ("source_id", "source_connector", "source_output_index", "diagnostic"),
    (
        ("MUL", 1, 2, "invalid child source connector"),
        ("MISSING_SOURCE", 0, 2, "missing source FID"),
        ("MUL", 0, 999, "invalid source output"),
    ),
)
# Dynamic contract: every macro output validates its exact source.
def test_graphical_macro_rejects_an_invalid_explicit_output_source(
        source_id: str,
        source_connector: int,
        source_output_index: int,
        diagnostic: str,
) -> None:
    """Reject a malformed source endpoint on a child-to-root cable.

    :param source_id: Mutated source FID.
    :param source_connector: Mutated source connector category.
    :param source_output_index: Mutated raw source port.
    :param diagnostic: Expected fail-closed diagnostic fragment.
    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    graphical_signal: BlkSig
    for graphical_signal in circuit.blksigs:
        if graphical_signal.ID == "MUL_TO_ROOT":
            graphical_signal.pnodfrom = source_id
            graphical_signal.iconfrom = source_connector
            graphical_signal.inodfrom = source_output_index
        else:
            pass

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(ValueError, match=diagnostic):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


@pytest.mark.parametrize(
    ("target_id", "target_connector", "target_output_index", "diagnostic"),
    (
        ("MACRO", 1, 0, "invalid root output"),
        ("MACRO", 2, 999, "invalid root output"),
        ("MISSING_TARGET", 2, 0, "missing target FID"),
    ),
)
# Dynamic contract: every macro output validates its exact target.
def test_graphical_macro_rejects_an_invalid_explicit_output_target(
        target_id: str,
        target_connector: int,
        target_output_index: int,
        diagnostic: str,
) -> None:
    """Reject a malformed macro endpoint on a child-to-root cable.

    :param target_id: Mutated target FID.
    :param target_connector: Mutated target connector category.
    :param target_output_index: Mutated raw target port.
    :param diagnostic: Expected fail-closed diagnostic fragment.
    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    graphical_signal: BlkSig
    for graphical_signal in circuit.blksigs:
        if graphical_signal.ID == "MUL_TO_ROOT":
            graphical_signal.pnodto = target_id
            graphical_signal.iconto = target_connector
            graphical_signal.inodto = target_output_index
        else:
            pass

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(ValueError, match=diagnostic):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: a root output does not accept two exact cables.
def test_graphical_macro_rejects_multiple_explicit_output_cables() -> None:
    """Reject two exact graphical cables targeting one macro output.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    duplicate_signal: BlkSig = BlkSig()
    duplicate_signal.ID = "DUPLICATE_MUL_TO_ROOT"
    duplicate_signal.loc_name = "public_y"
    duplicate_signal.inodfrom = 2
    duplicate_signal.iconfrom = 0
    duplicate_signal.inodto = 0
    duplicate_signal.iconto = 2
    duplicate_signal.pnodfrom = "MUL"
    duplicate_signal.pnodto = "MACRO"
    circuit.blksigs.append(duplicate_signal)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="root output has multiple explicit cables",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: an explicitly blank root output does not fall back to aliases.
def test_graphical_macro_rejects_an_explicit_blank_output_source() -> None:
    """Reject a blank child-to-root cable despite a compatible producer alias.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    graphical_signal: BlkSig
    for graphical_signal in circuit.blksigs:
        if graphical_signal.ID == "MUL_TO_ROOT":
            graphical_signal.pnodfrom = ""
        else:
            pass
    alias_signal: BlkSig = BlkSig()
    alias_signal.ID = "UNCONNECTED_PUBLIC_OUTPUT_ALIAS"
    alias_signal.loc_name = "public_y"
    alias_signal.inodfrom = 2
    alias_signal.iconfrom = 0
    alias_signal.inodto = 0
    alias_signal.iconto = 0
    alias_signal.pnodfrom = "MUL"
    alias_signal.pnodto = ""
    circuit.blksigs.append(alias_signal)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="root output cable has no exact source",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: an explicitly blank cable does not re-enter through aliases.
def test_graphical_macro_does_not_invent_a_source_for_an_explicit_blank_cable(
) -> None:
    """Keep a live blank-source pin unresolved despite a compatible alias.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    route_reader: BlkFrom = circuit.blkfroms[0]
    route_reader.signals.append("external_x")

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="unresolved live inputs: routed_internal",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: multiple root aliases are not resolved by list order.
def test_graphical_macro_rejects_ambiguous_root_aliases() -> None:
    """Reject a routed input compatible with two macro-boundary variables.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    dynamic_element: ElmDsl = circuit.elmdsls[0]
    dynamic_definition: BlkDef | None = None
    candidate_definition: BlkDef
    for candidate_definition in circuit.blkdefs:
        if candidate_definition.ID == dynamic_element.typ_id:
            dynamic_definition = candidate_definition
        else:
            pass
    assert dynamic_definition is not None
    dynamic_definition.inputs.append("secondary_input")
    route_reader: BlkFrom = circuit.blkfroms[0]
    route_reader.signals = [
        "ambiguous_route",
        "external_x",
        "secondary_input",
    ]

    alias_definition: BlkDef = BlkDef()
    alias_definition.ID = "AMBIGUOUS_ALIAS_DEFINITION"
    alias_definition.loc_name = "Ambiguous alias consumer"
    alias_definition.inputs.append("ambiguous_route")
    alias_definition.outputs.append("unused_alias_output")
    alias_definition.equations_raw.append(
        "unused_alias_output=ambiguous_route"
    )
    circuit.blkdefs.append(alias_definition)
    alias_reference: BlkRef = BlkRef()
    alias_reference.ID = "AMBIGUOUS_ALIAS_REFERENCE"
    alias_reference.typ_id = alias_definition.ID
    alias_reference.cdisName = alias_definition.loc_name
    circuit.blkrefs.append(alias_reference)
    rescue_signal: BlkSig = BlkSig()
    rescue_signal.ID = "RESCUE_AMBIGUOUS_ALIAS_REFERENCE"
    rescue_signal.loc_name = "external_x"
    rescue_signal.inodfrom = 0
    rescue_signal.iconfrom = 2
    rescue_signal.inodto = 0
    rescue_signal.iconto = 0
    rescue_signal.pnodfrom = alias_reference.ID
    rescue_signal.pnodto = ""
    circuit.blksigs.append(rescue_signal)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="Graphical DGS input has ambiguous root aliases",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: tied graphical producers fail closed.
def test_graphical_macro_rejects_ambiguous_output_producers() -> None:
    """Reject two equally ranked producers for one public macro output.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    source_signal: BlkSig
    for source_signal in circuit.blksigs:
        if source_signal.ID == "MUL_TO_ROOT":
            source_signal.iconto = 0
            source_signal.pnodto = ""
        else:
            pass

    duplicate_multiplier: BlkMul = BlkMul()
    duplicate_multiplier.ID = "DUPLICATE_MULTIPLIER"
    duplicate_multiplier.loc_name = "Duplicate output producer"
    circuit.blkmuls.append(duplicate_multiplier)

    duplicate_input_zero: BlkSig = BlkSig()
    duplicate_input_zero.ID = "ROOT_TO_DUPLICATE_0"
    duplicate_input_zero.loc_name = "external_x"
    duplicate_input_zero.inodfrom = 0
    duplicate_input_zero.iconfrom = 1
    duplicate_input_zero.inodto = 0
    duplicate_input_zero.iconto = 0
    duplicate_input_zero.pnodfrom = "MACRO"
    duplicate_input_zero.pnodto = duplicate_multiplier.ID
    circuit.blksigs.append(duplicate_input_zero)

    duplicate_input_one: BlkSig = BlkSig()
    duplicate_input_one.ID = "ROOT_TO_DUPLICATE_1"
    duplicate_input_one.loc_name = "external_x"
    duplicate_input_one.inodfrom = 0
    duplicate_input_one.iconfrom = 1
    duplicate_input_one.inodto = 1
    duplicate_input_one.iconto = 0
    duplicate_input_one.pnodfrom = "MACRO"
    duplicate_input_one.pnodto = duplicate_multiplier.ID
    circuit.blksigs.append(duplicate_input_one)

    duplicate_output: BlkSig = BlkSig()
    duplicate_output.ID = "DUPLICATE_TO_ROOT"
    duplicate_output.loc_name = "public_y"
    duplicate_output.inodfrom = 2
    duplicate_output.iconfrom = 0
    duplicate_output.inodto = 0
    duplicate_output.iconto = 0
    duplicate_output.pnodfrom = duplicate_multiplier.ID
    duplicate_output.pnodto = ""
    circuit.blksigs.append(duplicate_output)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="Graphical DGS macro output has ambiguous producers",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: a reached BlkRef requires a typ_id resolvable by FID.
def test_graphical_macro_rejects_a_missing_nested_blkdef() -> None:
    """Reject an exact graphical child whose block definition is absent.

    :return: None.
    """
    fixture: tuple[DgsCircuit, ElmComp, ElmComp, BlkRef] = (
        _build_nested_graphical_parent_fixture()
    )
    circuit: DgsCircuit = fixture[0]
    root_element: ElmComp = fixture[1]
    source_reference: BlkRef = fixture[3]
    source_reference.typ_id = "MISSING_NESTED_BLOCK_DEFINITION"

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="references missing BlkDef FID",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: an unsupported typed graphical child cannot disappear.
def test_graphical_macro_rejects_an_unsupported_reached_child() -> None:
    """Reject a reached BlkSlot that cannot materialize as a runtime child.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    unsupported_slot: BlkSlot = BlkSlot()
    unsupported_slot.ID = "UNSUPPORTED_GRAPHICAL_SLOT"
    unsupported_slot.loc_name = "Unsupported graphical slot"
    circuit.blkslots.append(unsupported_slot)
    unsupported_signal: BlkSig = BlkSig()
    unsupported_signal.ID = "ROOT_TO_UNSUPPORTED_GRAPHICAL_SLOT"
    unsupported_signal.loc_name = "external_x"
    unsupported_signal.inodfrom = 0
    unsupported_signal.iconfrom = 1
    unsupported_signal.inodto = 0
    unsupported_signal.iconto = 1
    unsupported_signal.pnodfrom = "MACRO"
    unsupported_signal.pnodto = unsupported_slot.ID
    circuit.blksigs.append(unsupported_signal)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="component contains an unsupported child type",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: nested parameters do not select repeated names.
def test_graphical_macro_rejects_an_ambiguous_nested_instance_label() -> None:
    """Reject two nested parameter sources sharing one BlkRef label.

    :return: None.
    """
    circuit: DgsCircuit
    root_element: ElmComp
    nested_component: ElmComp
    child_reference: BlkRef
    (
        circuit,
        root_element,
        nested_component,
        child_reference,
    ) = _build_nested_graphical_parent_fixture()
    child_reference.cdisName = "Repeated nested instance"

    relation_index: int
    for relation_index in range(2):
        nested_slot: BlkSlot = BlkSlot()
        nested_slot.ID = f"NESTED_SLOT_{relation_index}"
        nested_slot.loc_name = child_reference.cdisName
        nested_slot.filtmod = "ElmDsl"
        nested_element: ElmDsl = ElmDsl()
        nested_element.ID = f"NESTED_ELEMENT_{relation_index}"
        nested_element.loc_name = f"Nested element {relation_index}"
        nested_element.typ_id = child_reference.typ_id
        nested_slot.element = nested_element.ID
        circuit.blkslots.append(nested_slot)
        circuit.elmdsls.append(nested_element)
        nested_component.pblk.append(nested_slot.ID)
        nested_component.pelm.append(nested_element.ID)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="Graphical BlkRef instance label is ambiguous",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: nested parameters require the same typ_id FID.
def test_graphical_macro_rejects_nested_parameters_from_another_blkdef() -> None:
    """Reject a named nested parameter source owned by another BlkDef FID.

    :return: None.
    """
    circuit: DgsCircuit
    root_element: ElmComp
    nested_component: ElmComp
    child_reference: BlkRef
    (
        circuit,
        root_element,
        nested_component,
        child_reference,
    ) = _build_nested_graphical_parent_fixture()
    child_reference.cdisName = "Mismatched nested instance"

    nested_slot: BlkSlot = BlkSlot()
    nested_slot.ID = "MISMATCHED_NESTED_SLOT"
    nested_slot.loc_name = child_reference.cdisName
    nested_slot.filtmod = "ElmDsl"
    nested_element: ElmDsl = ElmDsl()
    nested_element.ID = "MISMATCHED_NESTED_ELEMENT"
    nested_element.loc_name = "Mismatched nested element"
    nested_element.typ_id = "FRAME"
    nested_slot.element = nested_element.ID
    circuit.blkslots.append(nested_slot)
    circuit.elmdsls.append(nested_element)
    nested_component.pblk.append(nested_slot.ID)
    nested_component.pelm.append(nested_element.ID)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="resolved parameters from a different BlkDef FID",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


def test_dgs_root_selection_does_not_require_a_model_specific_name() -> None:
    """Select the only valid document root without a hard-coded model name.

    :return: None.
    """
    root_result: DgsRootBlockResult = dgs_to_root_block(
        path=str(_get_graphical_parent_signal_binding_dgs_path()),
    )

    assert root_result.root_element.ID == "ROOT"
    assert root_result.root_element.loc_name == "Graphical root"
    assert root_result.root_element.typ_id == "FRAME"


def test_dgs_root_selection_rejects_distinct_resolvable_roots() -> None:
    """Reject an ambiguous document even when candidate sizes differ.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))

    alternate_frame: BlkDef = BlkDef()
    alternate_frame.ID = "ALTERNATE_FRAME"
    alternate_frame.loc_name = "Alternate frame"
    alternate_frame.inputs.append("alternate_x")
    alternate_frame.outputs.append("alternate_y")
    alternate_frame.outputs.append("alternate_z")
    circuit.blkdefs.append(alternate_frame)

    alternate_root: ElmComp = ElmComp()
    alternate_root.ID = "ALTERNATE_ROOT"
    alternate_root.loc_name = "Alternate root"
    alternate_root.typ_id = alternate_frame.ID
    circuit.elmcomps.append(alternate_root)

    parsed_blocks: dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)
    )
    with pytest.raises(
        ValueError,
        match="Several ElmComp roots match the available selectors",
    ):
        build_dgs_root_block_from_circuit(
            circuit=circuit,
            parsed_blocks=parsed_blocks,
            root_name=None,
        )


def test_dgs_direct_instances_reject_incomplete_and_ambiguous_relations() -> None:
    """Keep malformed source relations visible without executing them.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    parsed_blocks: dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)
    )
    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parsed_blocks,
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    graphical_indexes: DgsGraphicalIndexes = (
        build_dgs_graphical_indexes(circuit=circuit)
    )
    slot_id_value: str | None = root_element.pblk[0]
    element_id_value: str | None = root_element.pelm[0]
    assert slot_id_value is not None
    assert element_id_value is not None
    slot_id: str = slot_id_value
    element_id: str = element_id_value

    selected_counts: list[int] = list()
    relation_stage: int
    for relation_stage in range(3):
        if relation_stage == 0:
            # The extra pElm stays reportable, but cannot create a child.
            root_element.pelm.append(element_id)
        elif relation_stage == 1:
            # Reusing the slot makes both complete rows ambiguous.
            root_element.pblk.append(slot_id)
        else:
            # A non-resolving pblk cannot become valid through name fallback.
            root_element.pblk.clear()
            root_element.pblk.append("MISSING_SLOT")
            root_element.pelm.clear()
            root_element.pelm.append(element_id)

        entries: list[ElmCompInstanceEntry] = (
            extract_elmcomp_direct_instances(circuit, root_element)
        )
        selected_entries: list[ElmCompInstanceEntry] = (
            get_unambiguous_elmcomp_direct_instances(entries=entries)
        )
        with pytest.raises(
            ValueError,
            match="Direct ElmComp relations contain",
        ):
            build_direct_root_elmcomp_block(
                circuit=circuit,
                result=root_result,
                graphical_indexes=graphical_indexes,
            )
        if relation_stage == 0:
            assert len(entries) == 2
            assert entries[1].slot_id is None
            assert len(selected_entries) == 1
            assert selected_entries[0].slot_id == slot_id
        elif relation_stage == 1:
            assert len(entries) == 2
            assert len(selected_entries) == 0
        else:
            assert len(entries) == 1
            assert not entries[0].slot_reference_is_resolved
            assert len(selected_entries) == 0

        selected_counts.append(len(selected_entries))

    assert tuple(selected_counts) == (1, 0, 0)


# Dynamic contract: a duplicated BlkDef FID can never select the last record.
def test_dgs_block_definition_index_rejects_duplicate_fids() -> None:
    """Reject ambiguous block definitions before selecting a root type.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    source_definition: BlkDef = circuit.blkdefs[0]
    duplicate_definition: BlkDef = BlkDef()
    duplicate_definition.ID = source_definition.ID
    duplicate_definition.loc_name = "Duplicate block definition"
    circuit.blkdefs.append(duplicate_definition)

    with pytest.raises(
        ValueError,
        match="DGS BlkDef FID is duplicated",
    ):
        parse_dgs_block_definitions_from_circuit(circuit=circuit)


# Dynamic contract: an ambiguous pblk cannot resolve by list order.
def test_dgs_element_index_rejects_duplicate_blkslot_fids() -> None:
    """Reject an ambiguous exact slot relation before materialization.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    source_slot: BlkSlot = circuit.blkslots[0]
    duplicate_slot: BlkSlot = BlkSlot()
    duplicate_slot.ID = source_slot.ID
    duplicate_slot.loc_name = "Duplicate slot"
    circuit.blkslots.append(duplicate_slot)

    with pytest.raises(
        ValueError,
        match="DGS element FID is duplicated",
    ):
        extract_elmcomp_direct_instances(
            circuit=circuit,
            root_element=root_element,
        )


# Dynamic contract: an ambiguous pelm cannot resolve by list order.
def test_dgs_element_index_rejects_duplicate_pelm_fids() -> None:
    """Reject an ambiguous exact dynamic-instance relation.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    source_element: ElmDsl = circuit.elmdsls[0]
    duplicate_element: ElmDsl = ElmDsl()
    duplicate_element.ID = source_element.ID
    duplicate_element.loc_name = "Duplicate dynamic instance"
    circuit.elmdsls.append(duplicate_element)

    with pytest.raises(
        ValueError,
        match="DGS element FID is duplicated",
    ):
        extract_elmcomp_direct_instances(
            circuit=circuit,
            root_element=root_element,
        )


def test_dgs_direct_builder_rejects_a_missing_dynamic_blkdef() -> None:
    """Reject a resolved dynamic slot whose declared type cannot materialize.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    circuit.elmdsls[0].typ_id = "MISSING_BLOCK_DEFINITION"

    with pytest.raises(
        ValueError,
        match="references a missing parsed BlkDef",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


def test_dgs_direct_builder_rejects_a_physical_target_in_a_dynamic_slot() -> None:
    """Reject a resolved physical object where BlkSlot requires ElmDsl.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    physical_target: StaCubic = StaCubic()
    physical_target.ID = "PHYSICAL_SLOT_TARGET"
    physical_target.loc_name = "Physical slot target"
    circuit.stacubics.append(physical_target)
    root_element.pelm[0] = physical_target.ID
    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )

    with pytest.raises(
        ValueError,
        match="has no resolved ElmDsl or ElmComp instance",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: ElmDsl cannot impersonate a registered physical class.
def test_dgs_direct_builder_requires_an_exact_slot_element_class() -> None:
    """Reject a generic dynamic container in a concrete equipment slot.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    dynamic_slot: BlkSlot = circuit.blkslots[0]
    dynamic_slot.filtmod = "ElmVsc*"

    with pytest.raises(
        ValueError,
        match="does not satisfy its typed BlkSlot filter",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


# Dynamic contract: unregistered Elm roles retain their ElmDsl container.
def test_dgs_direct_builder_accepts_a_specialized_dynamic_role() -> None:
    """Accept an ElmDsl container for an unregistered specialized role.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    dynamic_element: ElmDsl = circuit.elmdsls[0]
    dynamic_definition: BlkDef | None = None
    candidate_definition: BlkDef
    for candidate_definition in circuit.blkdefs:
        if candidate_definition.ID == dynamic_element.typ_id:
            dynamic_definition = candidate_definition
        else:
            pass
    assert dynamic_definition is not None
    dynamic_definition.isMacro = 0
    dynamic_slot: BlkSlot = circuit.blkslots[0]
    dynamic_slot.filtmod = "ElmEpc*"

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    direct_result: DgsDirectRootBuildResult = build_direct_root_elmcomp_block(
        circuit=circuit,
        result=root_result,
        graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
    )

    assert direct_result.root_block is root_result.root_block
    assert len(direct_result.root_block.children) == 1
    assert direct_result.root_block.children[0].name == dynamic_definition.loc_name


# Dynamic contract: a specialized dynamic role requires a resolvable pelm.
def test_dgs_direct_builder_rejects_a_missing_specialized_dynamic_role() -> None:
    """Reject an unregistered wildcard role whose dynamic wrapper is absent.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    dynamic_slot: BlkSlot = circuit.blkslots[0]
    dynamic_slot.filtmod = "ElmEpc*"
    root_element.pelm.clear()

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    with pytest.raises(
        ValueError,
        match="has no resolved ElmDsl or ElmComp instance",
    ):
        build_direct_root_elmcomp_block(
            circuit=circuit,
            result=root_result,
            graphical_indexes=build_dgs_graphical_indexes(circuit=circuit),
        )


def test_direct_dynamic_import_rejects_partial_graphical_topology() -> None:
    """Do not register a root whose live graphical input has no producer.

    :return: None.
    """
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    destination: MultiCircuit = MultiCircuit()
    logger: Logger = Logger()

    templates_by_root_id: dict[str, RmsModelTemplate | EmtModelTemplate] = (
        convert_and_add_dgs_dynamic_templates_to_circuit(
            dgs_circuit=dgs_circuit,
            circuit=destination,
            target_domain=DynamicSimulationMode.RMS,
            logger=logger,
        )
    )

    assert templates_by_root_id == dict()
    assert len(destination.rms_models) == 0
    assert any(
        entry.msg == "DGS dynamic root could not be materialized"
        and "unresolved live inputs" in str(entry.value)
        for entry in logger.entries
    )


def test_direct_dynamic_import_rejects_unsupported_root_syntax() -> None:
    """Do not register a root after any source statement failed to parse.

    :return: None.
    """
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(
        str(
            _get_complete_hvdc_vsc_dgs_path(
                file_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
            )
        )
    )
    source_root: ElmComp = dgs_circuit.elmcomps[0]
    dgs_circuit.elmcomps = [source_root]
    root_definition: BlkDef | None = None
    candidate_definition: BlkDef
    for candidate_definition in dgs_circuit.blkdefs:
        if candidate_definition.ID == source_root.typ_id:
            root_definition = candidate_definition
        else:
            pass
    assert root_definition is not None
    root_definition.equations_raw.append("unsupported syntax")

    destination: MultiCircuit = MultiCircuit()
    logger: Logger = Logger()
    templates_by_root_id: dict[str, RmsModelTemplate | EmtModelTemplate] = (
        convert_and_add_dgs_dynamic_templates_to_circuit(
            dgs_circuit=dgs_circuit,
            circuit=destination,
            target_domain=DynamicSimulationMode.RMS,
            logger=logger,
        )
    )

    assert templates_by_root_id == dict()
    assert len(destination.rms_models) == 0
    assert any(
        entry.msg == "DGS dynamic root could not be materialized"
        and "unsupported source statements" in str(entry.value)
        for entry in logger.entries
    )


# Dynamic contract: a supported root equation cannot be omitted either.
def test_direct_dynamic_import_rejects_supported_root_equations() -> None:
    """Reject supported equations instead of dropping them from the root shell.

    :return: None.
    """
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(
        str(
            _get_complete_hvdc_vsc_dgs_path(
                file_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
            )
        )
    )
    source_root: ElmComp = dgs_circuit.elmcomps[0]
    dgs_circuit.elmcomps = [source_root]
    root_definition: BlkDef | None = None
    candidate_definition: BlkDef
    for candidate_definition in dgs_circuit.blkdefs:
        if candidate_definition.ID == source_root.typ_id:
            root_definition = candidate_definition
        else:
            pass
    assert root_definition is not None
    root_definition.equations_raw.append("synthetic_root_signal=1")

    destination: MultiCircuit = MultiCircuit()
    logger: Logger = Logger()
    templates_by_root_id: dict[str, RmsModelTemplate | EmtModelTemplate] = (
        convert_and_add_dgs_dynamic_templates_to_circuit(
            dgs_circuit=dgs_circuit,
            circuit=destination,
            target_domain=DynamicSimulationMode.RMS,
            logger=logger,
        )
    )

    assert templates_by_root_id == dict()
    assert len(destination.rms_models) == 0
    assert any(
        entry.msg == "DGS dynamic root could not be materialized"
        and "purely structural frame" in str(entry.value)
        for entry in logger.entries
    )


# Dynamic contract: a root inequality cannot be lost in the shell either.
def test_direct_dynamic_import_rejects_root_parameter_limits() -> None:
    """Reject root inequalities that the structural shell cannot own.

    :return: None.
    """
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(
        str(
            _get_complete_hvdc_vsc_dgs_path(
                file_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
            )
        )
    )
    source_root: ElmComp = dgs_circuit.elmcomps[0]
    dgs_circuit.elmcomps = [source_root]
    root_definition: BlkDef | None = None
    candidate_definition: BlkDef
    for candidate_definition in dgs_circuit.blkdefs:
        if candidate_definition.ID == source_root.typ_id:
            root_definition = candidate_definition
        else:
            pass
    assert root_definition is not None
    root_definition.internals.append("synthetic_internal")
    root_definition.equations_raw.append(
        "limfix(synthetic_internal)=[0,1]"
    )

    destination: MultiCircuit = MultiCircuit()
    logger: Logger = Logger()
    templates_by_root_id: dict[str, RmsModelTemplate | EmtModelTemplate] = (
        convert_and_add_dgs_dynamic_templates_to_circuit(
            dgs_circuit=dgs_circuit,
            circuit=destination,
            target_domain=DynamicSimulationMode.RMS,
            logger=logger,
        )
    )

    assert templates_by_root_id == dict()
    assert len(destination.rms_models) == 0
    assert any(
        entry.msg == "DGS dynamic root could not be materialized"
        and "purely structural frame" in str(entry.value)
        for entry in logger.entries
    )


# Dynamic contract: non-executable root comments preserve the valid frame.
def test_structural_root_accepts_ignored_comment_statements() -> None:
    """Allow source comments that carry no executable root semantics.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    root_definition: BlkDef | None = None
    candidate_definition: BlkDef
    for candidate_definition in circuit.blkdefs:
        if candidate_definition.ID == root_element.typ_id:
            root_definition = candidate_definition
        else:
            pass
    assert root_definition is not None
    root_definition.equations_raw.append(
        "! Structural frame comment without runtime semantics"
    )

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )

    assert root_result.root_element is root_element
    assert root_result.root_block.children == list()


# Dynamic contract: overlapping names do not create implicit children.
def test_root_shell_does_not_materialize_signal_overlap_candidates() -> None:
    """Keep an unrelated BlkDef out of the exact direct-root hierarchy.

    :return: None.
    """
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    root_element: ElmComp = circuit.elmcomps[0]
    root_definition: BlkDef | None = None
    candidate_definition: BlkDef
    for candidate_definition in circuit.blkdefs:
        if candidate_definition.ID == root_element.typ_id:
            root_definition = candidate_definition
        else:
            pass
    assert root_definition is not None
    assert len(root_definition.inputs) > 0

    overlap_definition: BlkDef = BlkDef()
    overlap_definition.ID = "UNRELATED_OVERLAP_BLOCK"
    overlap_definition.loc_name = "Unrelated overlap block"
    overlap_definition.inputs.append(root_definition.inputs[0])
    overlap_definition.outputs.append("unrelated_overlap_output")
    overlap_definition.equations_raw.append(
        f"unrelated_overlap_output={root_definition.inputs[0]}"
    )
    circuit.blkdefs.append(overlap_definition)

    root_result: DgsRootBlockResult = build_dgs_root_block_from_circuit(
        circuit=circuit,
        parsed_blocks=parse_dgs_block_definitions_from_circuit(circuit=circuit),
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        root_dgs_id=root_element.ID,
    )
    retained_overlap: ParsedDgsBlockDefinition | None = (
        root_result.parsed_blocks.get(overlap_definition.ID, None)
    )

    assert retained_overlap is not None
    assert root_result.root_block.children == list()


def test_direct_dynamic_import_excludes_every_empty_or_duplicate_root_fid() -> None:
    """Never retain the first root when its supposedly exact FID is not unique.

    :return: None.
    """
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(str(_get_graphical_parent_signal_binding_dgs_path()))
    source_root: ElmComp = dgs_circuit.elmcomps[0]

    duplicate_root: ElmComp = ElmComp()
    duplicate_root.ID = source_root.ID
    duplicate_root.loc_name = "Duplicate root"
    duplicate_root.typ_id = source_root.typ_id
    duplicate_root.pblk = list(source_root.pblk)
    duplicate_root.pelm = list(source_root.pelm)
    dgs_circuit.elmcomps.append(duplicate_root)

    empty_id_root: ElmComp = ElmComp()
    empty_id_root.loc_name = "Empty FID root"
    empty_id_root.typ_id = source_root.typ_id
    dgs_circuit.elmcomps.append(empty_id_root)

    destination: MultiCircuit = MultiCircuit()
    logger: Logger = Logger()
    templates_by_root_id: dict[str, RmsModelTemplate | EmtModelTemplate] = (
        convert_and_add_dgs_dynamic_templates_to_circuit(
            dgs_circuit=dgs_circuit,
            circuit=destination,
            target_domain=DynamicSimulationMode.RMS,
            logger=logger,
        )
    )
    logged_messages: set[str] = set()
    log_entry: LogEntry
    for log_entry in logger.entries:
        logged_messages.add(log_entry.msg)

    assert templates_by_root_id == dict()
    assert len(destination.rms_models) == 0
    assert "DGS dynamic root skipped because its FID is empty" in logged_messages
    assert (
        "DGS dynamic roots skipped because their FID is duplicated"
        in logged_messages
    )


def test_rms_measurement_binding_rejects_a_duplicated_root_with_a_shell() -> None:
    """Do not treat a prepared standard RMS shell as DGS activation evidence.

    :return: None.
    """
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(
        str(
            _get_complete_hvdc_vsc_dgs_path(
                file_name="hvdc_vsc_v1_complete_static_dynamic.dgs",
            )
        )
    )
    source_root: ElmComp = dgs_circuit.elmcomps[0]
    duplicate_root: ElmComp = ElmComp()
    duplicate_root.ID = source_root.ID
    duplicate_root.loc_name = "Duplicate measurement root"
    duplicate_root.typ_id = source_root.typ_id
    duplicate_root.pblk = list(source_root.pblk)
    duplicate_root.pelm = list(source_root.pelm)
    dgs_circuit.elmcomps = [source_root, duplicate_root]

    host_source_id: str | None = None
    direct_entry: ElmCompInstanceEntry
    for direct_entry in extract_elmcomp_direct_instances(
            circuit=dgs_circuit,
            root_element=source_root,
    ):
        if direct_entry.element_kind == "ElmVscmono":
            host_source_id = direct_entry.element_id
        else:
            pass
    assert host_source_id is not None

    destination: MultiCircuit = MultiCircuit()
    dc_bus: Bus = Bus(name="DC host bus", is_dc=True)
    ac_bus: Bus = Bus(name="AC host bus")
    destination.add_bus(dc_bus)
    destination.add_bus(ac_bus)
    physical_host: VSC = VSC(
        bus_from=dc_bus,
        bus_to=ac_bus,
        idtag=host_source_id,
    )
    destination.add_vsc(physical_host)
    prepared_shell: RmsModelTemplate = RmsModelTemplate(
        name="Prepared standard shell",
    )
    shell_var: Var = Var(name="shell_signal")
    prepared_shell.block = Block(
        name="Prepared standard shell",
        algebraic_vars=[shell_var],
        algebraic_eqs=[shell_var],
    )
    physical_host.rms_template = prepared_shell

    report: DgsRmsMeasurementBindingReport = bind_dgs_rms_measurements(
        circuit=destination,
        dgs_circuit=dgs_circuit,
        templates_by_root_dgs_id={source_root.ID: prepared_shell},
        logger=Logger(),
    )

    assert report.get_bound_meter_count() == 0
    assert report.get_bound_signal_count() == 0
    assert report.get_skipped_meter_count() == 0
    assert report.get_failed_meter_count() == 0


def test_dgs_dynamic_import_catalog_reports_live_graphical_binding_gaps() -> None:
    """Carry typed parent-binding diagnostics into the DGS import catalogue.

    :return: None.
    """
    bundle: DynamicModelImportBundle
    bundle_logger: Logger
    bundle, bundle_logger = build_dgs_dynamic_model_import_bundle(
        dgs_path=str(_get_graphical_parent_signal_binding_dgs_path()),
    )
    graphical_entries: list[DynamicModelImportEntry] = [
        entry
        for entry in bundle.get_entries()
        if entry.get_display_name() == "Graphical parent"
    ]
    assert len(graphical_entries) == 1
    graphical_entry: DynamicModelImportEntry = graphical_entries[0]
    source_block: Block | None = graphical_entry.get_source_block()
    topology_warnings: list[LogEntry] = [
        entry
        for entry in bundle_logger.entries
        if entry.msg == "DGS graphical operator topology incomplete"
    ]

    assert source_block is not None
    assert graphical_entry.get_persistence_spec() is None
    assert len(topology_warnings) == 1
    assert "routed_internal" in str(topology_warnings[0].value)
    assert "blank_internal" not in str(topology_warnings[0].value)


def test_dgs_block_definition_builds_one_self_contained_symbolic_block() -> None:
    """Materialize the equation declared by a versioned DGS block definition."""

    dgs_path: Path = _get_dynamic_gain_block_dgs_path()
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    parsed_blocks: dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)
    )
    parsed_gain_block = parsed_blocks["2"]
    block: Block = build_standalone_blkdef_block_from_parsed_block(
        parsed_block=parsed_gain_block,
    )

    assert parsed_gain_block.unsupported_lines == []
    assert block.name == "Dynamic gain"
    assert tuple(var.name for var in block.in_vars) == ("u",)
    assert tuple(var.name for var in block.out_vars) == ("y",)
    assert len(block.algebraic_eqs) == 1
    parameter_vars: list[Var] = list(block.event_dict)
    assert len(parameter_vars) == 1
    parameter_var: Var = parameter_vars[0]
    assert parameter_var.name == "Dynamic gain__K"
    equation_bindings: dict[str, float] = dict()
    equation_bindings[block.in_vars[0].name] = 3.0
    equation_bindings[block.out_vars[0].name] = 6.0
    equation_bindings[parameter_var.name] = 2.0
    assert block.algebraic_eqs[0].eval(**equation_bindings) == 0.0


def test_dgs_block_definition_preserves_open_and_closed_limfix_bounds() -> None:
    """Keep infinite endpoints and bracket semantics as canonical inequalities.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "PARAMETER_LIMIT_DEFINITION"
    definition.loc_name = "Parameter limits"
    definition.params = [
        "Kp",
        "Ki",
        "upper_closed",
        "upper_open",
        "bounded",
        "expression_bound",
        "Kmin",
    ]
    definition.equations_raw = [
        "limfix(Kp)=(0,)",
        "limfix(Ki)=[0,)",
        "limfix(upper_closed)=(,0]",
        "limfix(upper_open)=(,0)",
        "limfix(bounded)=[0,1]",
        "limfix(expression_bound)=[max(0,Kmin),)",
    ]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )
    block: Block = build_standalone_blkdef_block_from_parsed_block(
        parsed_block=parsed,
    )
    constraints: list[Comparison] = [
        constraint
        for constraint in block.inequalities
        if isinstance(constraint, Comparison)
    ]

    assert parsed.unsupported_lines == []
    assert len(constraints) == 7
    assert [constraint.op for constraint in constraints] == [
        CmpOp.GT,
        CmpOp.GE,
        CmpOp.LE,
        CmpOp.LT,
        CmpOp.GE,
        CmpOp.LE,
        CmpOp.GE,
    ]
    assert [constraint.lhs.name for constraint in constraints] == [
        "Parameter limits__Kp",
        "Parameter limits__Ki",
        "Parameter limits__upper_closed",
        "Parameter limits__upper_open",
        "Parameter limits__bounded",
        "Parameter limits__bounded",
        "Parameter limits__expression_bound",
    ]
    assert constraints[0].rhs.eval() == 0.0
    assert constraints[1].rhs.eval() == 0.0
    assert constraints[2].rhs.eval() == 0.0
    assert constraints[3].rhs.eval() == 0.0


@pytest.mark.parametrize(
    "statement",
    (
        "limfix(unknown)=(0,)",
        "limfix(Kp)=(,)",
        "limfix(Kp)={0,1]",
        "limfix(Kp)=[0,1,2]",
        "limfix(Kp)=[Kp<1,)",
    ),
)
def test_dgs_block_definition_rejects_malformed_limfix_bounds(
        statement: str,
) -> None:
    """Reject ambiguous parameter domains instead of ignoring their text.

    :param statement: Invalid PowerFactory parameter-domain declaration.
    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "INVALID_PARAMETER_LIMIT_DEFINITION"
    definition.loc_name = "Invalid parameter limits"
    definition.params = ["Kp"]
    definition.equations_raw = [statement]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )

    assert parsed.unsupported_lines == [statement]


def test_dgs_boolean_helpers_accept_comparisons_only_as_conditions() -> None:
    """Convert nested selector conditions without weakening numeric positions.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "BOOLEAN_HELPER_DEFINITION"
    definition.loc_name = "Boolean helpers"
    definition.inputs = ["u1", "flag"]
    definition.outputs = ["selected", "fixed"]
    definition.params = ["u_db_low", "high_value", "low_value"]
    definition.equations_raw = [
        "selected=select(u1<(1+u_db_low),high_value,low_value)",
        "fixed=selfix(u1<(1+u_db_low),high_value,low_value)",
        "latched=flipflop("
        "{selfix(high_value,u1<low_value,u1>high_value).and.flag},"
        "{.not.selfix(low_value,u1>high_value,u1<low_value)}"
        ")",
    ]
    definition.outputs.append("latched")
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )
    block: Block = build_standalone_blkdef_block_from_parsed_block(
        parsed_block=parsed,
    )

    assert parsed.unsupported_lines == []
    assert len(block.algebraic_eqs) == 3
    assert len(block.procedural_logic) == 5


def test_dgs_numeric_helper_rejects_a_comparison_argument() -> None:
    """Fail closed when a boolean comparison occupies a numeric helper slot.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "INVALID_BOOLEAN_POSITION_DEFINITION"
    definition.loc_name = "Invalid boolean position"
    definition.inputs = ["u1"]
    definition.outputs = ["result"]
    definition.params = ["limit"]
    definition.equations_raw = ["result=max(u1<limit,limit)"]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )

    assert parsed.unsupported_lines == definition.equations_raw


def test_dgs_conditional_diagnostics_are_canonical_and_round_trip() -> None:
    """Preserve ``output`` and ``outfix`` as inert typed block declarations.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "CONDITIONAL_DIAGNOSTIC_DEFINITION"
    definition.loc_name = "Conditional diagnostics"
    definition.inputs = ["enabled", "measured"]
    definition.params = ["limit"]
    definition.equations_raw = [
        "output(enabled.and.{measured>limit},'Limit exceeded, controller active!')",
        "outfix(measured<0.0,'Measured value has wrong polarity.')",
    ]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )
    block: Block = build_standalone_blkdef_block_from_parsed_block(
        parsed_block=parsed,
    )
    diagnostics: list[ConditionalDiagnosticLogic] = [
        entry
        for entry in block.procedural_logic
        if isinstance(entry, ConditionalDiagnosticLogic)
    ]
    rebuilt_block: Block = Block.parse(
        data=block.to_dict(),
        procedural_logic_codec=ProceduralLogicCodec(),
    )
    rebuilt_diagnostics: list[ConditionalDiagnosticLogic] = [
        entry
        for entry in rebuilt_block.procedural_logic
        if isinstance(entry, ConditionalDiagnosticLogic)
    ]

    assert parsed.unsupported_lines == []
    assert len(diagnostics) == 2
    assert [entry.initialization_only for entry in diagnostics] == [False, True]
    assert [entry.message for entry in diagnostics] == [
        "Limit exceeded, controller active!",
        "Measured value has wrong polarity.",
    ]
    assert len(rebuilt_diagnostics) == 2
    assert [entry.initialization_only for entry in rebuilt_diagnostics] == [
        False,
        True,
    ]
    assert [entry.message for entry in rebuilt_diagnostics] == [
        "Limit exceeded, controller active!",
        "Measured value has wrong polarity.",
    ]


@pytest.mark.parametrize(
    "statement",
    (
        "event(enabled,trigger,'create=EvtSwitch target=CB1 "
        "name=Open_CB1 i_switch=0 dtime=delay')",
        "event(enabled,trigger)",
        "event(enabled,trigger,configuration_symbol)",
        "event(enabled,trigger,'')",
    ),
)
def test_dgs_external_event_fails_closed_without_runtime_actuation(
        statement: str,
) -> None:
    """Reject every event until its switch action can execute at runtime.

    :param statement: External event declaration lacking canonical actuation.
    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "INVALID_EXTERNAL_EVENT_DEFINITION"
    definition.loc_name = "Invalid external event"
    definition.inputs = ["enabled", "trigger", "configuration_symbol"]
    definition.equations_raw = [statement]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )

    assert parsed.unsupported_lines == [statement]


@pytest.mark.parametrize(
    "statement",
    (
        "output(enabled)",
        "output(enabled,message_symbol)",
        "output(enabled,'message','extra')",
        "outfix(,'message')",
    ),
)
def test_dgs_conditional_diagnostics_reject_ambiguous_surfaces(
        statement: str,
) -> None:
    """Fail closed for unsupported diagnostic arity or nonliteral messages.

    :param statement: Malformed diagnostic declaration.
    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "INVALID_CONDITIONAL_DIAGNOSTIC_DEFINITION"
    definition.loc_name = "Invalid conditional diagnostic"
    definition.inputs = ["enabled", "message_symbol"]
    definition.equations_raw = [statement]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )

    assert parsed.unsupported_lines == [statement]


def test_dgs_bracket_unit_metadata_preserves_exact_known_symbol_unit() -> None:
    """Retain the exact PowerFactory ``[symbol]='unit'`` declaration.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "BRACKET_UNIT_METADATA_DEFINITION"
    definition.loc_name = "Bracket unit metadata"
    definition.internals = ["theta1"]
    definition.equations_raw = ["[theta1]='rad'"]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )

    assert parsed.unsupported_lines == []
    assert len(parsed.variable_units) == 1
    assert parsed.variable_units[0].symbol_name == "theta1"
    assert parsed.variable_units[0].unit_text == "rad"


def test_dgs_bracket_unit_metadata_rejects_an_unknown_symbol() -> None:
    """Fail closed when bracket unit metadata names no declared block symbol.

    :return: None.
    """
    statement: str = "[unknown]='rad'"
    definition: BlkDef = BlkDef()
    definition.ID = "UNKNOWN_BRACKET_UNIT_METADATA_DEFINITION"
    definition.loc_name = "Unknown bracket unit metadata"
    definition.equations_raw = [statement]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )

    assert parsed.unsupported_lines == [statement]


def test_dgs_equation_continuation_preserves_one_nested_expression() -> None:
    """Join exact ``;&`` continuation markers before splitting statements.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "CONTINUED_EXPRESSION_DEFINITION"
    definition.loc_name = "Continued expression"
    definition.inputs = ["trip", "trigger", "voltage", "power"]
    definition.outputs = ["result"]
    definition.params = ["minimum"]
    definition.equations_raw = [
        "result=select(trip,minimum,; &"
        " select(trigger,sqr(voltage)/max(abs(power),0.000001),minimum))"
    ]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )

    assert parsed.unsupported_lines == []
    assert "result" in parsed.algebraic_rhs


def test_dgs_equation_continuation_discards_interleaved_comments() -> None:
    """Join a continued expression across bounded PowerFactory comments.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "COMMENTED_CONTINUED_EXPRESSION_DEFINITION"
    definition.loc_name = "Commented continued expression"
    definition.inputs = ["trip", "trigger", "voltage", "power"]
    definition.outputs = ["result"]
    definition.params = ["minimum"]
    definition.equations_raw = [
        "result=select(trip,minimum, ! first branch",
        "& select(trigger,sqr(voltage)/max(abs(power),0.000001),"
        " ! second branch",
        "! exported note",
        "& minimum))",
    ]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )

    assert parsed.unsupported_lines == []
    assert "result" in parsed.algebraic_rhs


def test_dgs_blkslot_preserves_filter_after_quoted_semicolons() -> None:
    """Keep typed slot columns aligned after quoted signal declarations.

    :return: None.
    """
    dgs_path: Path = _get_complete_hvdc_vsc_dgs_path(
        file_name="hvdc_vsc_v3_complete_static_dynamic.dgs",
    )
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    island_control_slot: BlkSlot | None = None
    candidate_slot: BlkSlot
    for candidate_slot in circuit.blkslots:
        if candidate_slot.ID == "186":
            island_control_slot = candidate_slot
        else:
            pass

    assert island_control_slot is not None
    assert island_control_slot.element is None
    assert island_control_slot.filtmod == "ElmV_f*"
    assert "uac_loc" in island_control_slot.inputs


def test_dgs_runtime_limits_become_continuous_diagnostics() -> None:
    """Preserve ``limits`` as runtime violation declarations, not constraints.

    :return: None.
    """
    statement: str = "limits(enabled)=[0,1]"
    definition: BlkDef = BlkDef()
    definition.ID = "RUNTIME_LIMIT_DEFINITION"
    definition.loc_name = "Runtime limit"
    definition.inputs = ["enabled"]
    definition.equations_raw = [statement]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )
    diagnostics: list[ConditionalDiagnosticLogic] = [
        entry
        for entry in parsed.procedural_logic
        if isinstance(entry, ConditionalDiagnosticLogic)
    ]
    diagnostic_conditions: list[Comparison] = [
        entry.condition_expr
        for entry in diagnostics
        if isinstance(entry.condition_expr, Comparison)
    ]

    assert parsed.unsupported_lines == []
    assert parsed.parameter_limits == []
    assert len(diagnostics) == 2
    assert len(diagnostic_conditions) == 2
    assert [condition.op for condition in diagnostic_conditions] == [
        CmpOp.LT,
        CmpOp.GT,
    ]
    assert [entry.message for entry in diagnostics] == [statement, statement]
    assert [entry.initialization_only for entry in diagnostics] == [
        False,
        False,
    ]


def test_dgs_modulo_and_variadic_extrema_preserve_numeric_semantics() -> None:
    """Materialize documented modulo and multi-operand extrema expressions.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "MODULO_VARIADIC_EXTREMA_DEFINITION"
    definition.loc_name = "modulo_variadic_extrema"
    definition.inputs = ["angle"]
    definition.outputs = ["wrapped", "limited"]
    definition.equations_raw = [
        "wrapped=modulo(angle+pi(),twopi())-pi()",
        "limited=min(4.0,max(-2.0,angle,1.0),3.0)",
    ]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )
    wrapped_expr: Expr = parsed.algebraic_rhs["wrapped"]
    limited_expr: Expr = parsed.algebraic_rhs["limited"]
    angle_name: str = parsed.symbol_table["angle"].name

    assert parsed.unsupported_lines == []
    assert angle_name == "angle"
    assert wrapped_expr.eval(angle=-1.5 * math.pi) == pytest.approx(
        0.5 * math.pi,
    )
    assert limited_expr.eval(angle=-3.0) == 1.0
    assert limited_expr.eval(angle=5.0) == 3.0


def test_dgs_not_equal_is_supported_inside_a_selector_condition() -> None:
    """Parse PowerFactory ``<>`` only through its declared boolean context.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "NOT_EQUAL_SELECTOR_DEFINITION"
    definition.loc_name = "Not equal selector"
    definition.inputs = ["T1", "T2", "selected", "alternate"]
    definition.outputs = ["result"]
    definition.equations_raw = [
        "result=select(T1-T2<>0.and.T2<>0,selected,alternate)"
    ]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)[definition.ID]
    )

    assert parsed.unsupported_lines == []


def test_dgs_network_mode_helpers_use_the_explicit_target_domain() -> None:
    """Resolve ``rms()`` and ``balanced()`` from RMS or EMT import context.

    :return: None.
    """
    definition: BlkDef = BlkDef()
    definition.ID = "NETWORK_MODE_HELPER_DEFINITION"
    definition.loc_name = "Network mode helpers"
    definition.outputs = ["balanced_result", "rms_result"]
    definition.equations_raw = [
        "balanced_result=selfix(balanced(),1.0,0.0)",
        "rms_result=selfix(rms(),1.0,0.0)",
    ]
    circuit: DgsCircuit = DgsCircuit()
    circuit.blkdefs.append(definition)

    rms_parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(
            circuit=circuit,
            simulation_domain=DynamicSimulationMode.RMS,
        )[definition.ID]
    )
    emt_parsed: ParsedDgsBlockDefinition = (
        parse_dgs_block_definitions_from_circuit(
            circuit=circuit,
            simulation_domain=DynamicSimulationMode.EMT,
        )[definition.ID]
    )

    assert rms_parsed.unsupported_lines == []
    assert emt_parsed.unsupported_lines == []
    assert rms_parsed.algebraic_rhs["balanced_result"].eval() == 1.0
    assert rms_parsed.algebraic_rhs["rms_result"].eval() == 1.0
    assert emt_parsed.algebraic_rhs["balanced_result"].eval() == 0.0
    assert emt_parsed.algebraic_rhs["rms_result"].eval() == 0.0


def test_dgs_block_definition_rejects_unsupported_syntax() -> None:
    """Reject a partial template when one DGS equation cannot be represented."""

    dgs_path: Path = _get_dynamic_gain_block_dgs_path()
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    parsed_blocks: dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)
    )

    with pytest.raises(
        UnsupportedDgsExpression,
        match="Unsupported dynamic block.*unsupported syntax",
    ):
        build_standalone_blkdef_block_from_parsed_block(
            parsed_block=parsed_blocks["3"],
        )


def test_dynamic_template_fingerprint_uses_declarative_block_identity() -> None:
    """Fingerprint a final block without rendering or executing Python source."""

    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(_get_dynamic_gain_block_dgs_path()))
    parsed_blocks: dict[str, ParsedDgsBlockDefinition] = (
        parse_dgs_block_definitions_from_circuit(circuit=circuit)
    )
    source_block: Block = build_standalone_blkdef_block_from_parsed_block(
        parsed_block=parsed_blocks["2"],
    )
    rms_template: RmsModelTemplate = RmsModelTemplate(name="First display name")
    rms_template.block = source_block
    first_fingerprint: str | None = build_dynamic_import_template_fingerprint(
        rms_template
    )
    rms_template.name = "Second display name"
    second_fingerprint: str | None = build_dynamic_import_template_fingerprint(
        rms_template
    )
    emt_template: EmtModelTemplate = EmtModelTemplate(name="Second display name")
    emt_template.block = source_block
    emt_fingerprint: str | None = build_dynamic_import_template_fingerprint(
        emt_template
    )

    assert first_fingerprint is not None
    assert second_fingerprint == first_fingerprint
    assert emt_fingerprint is not None
    assert emt_fingerprint != first_fingerprint


def test_user_dynamic_template_json_round_trips_the_typed_identity(
        tmp_path: Path,
) -> None:
    """Preserve the block and its typed catalogue identity through JSON."""

    source_block: Block = Block(name="Portable dynamic template")
    output_path: Path = tmp_path / "portable_dynamic_template.json"
    exported_path: Path = export_user_dynamic_template_json_from_block(
        block=source_block,
        output_path=str(output_path),
        template_name="Portable dynamic template",
        target_domain=DynamicSimulationMode.RMS,
        device_tpe=DeviceType.GeneratorDevice,
    )
    loaded_payload: (
        tuple[Block, str, DynamicSimulationMode, DeviceType] | None
    ) = load_user_dynamic_template_json_payload(str(exported_path))

    assert loaded_payload is not None

    loaded_block: Block = loaded_payload[0]
    loaded_name: str = loaded_payload[1]
    loaded_domain: DynamicSimulationMode = loaded_payload[2]
    loaded_device_tpe: DeviceType = loaded_payload[3]

    assert loaded_block.name == source_block.name
    assert loaded_name == "Portable dynamic template"
    assert loaded_domain is DynamicSimulationMode.RMS
    assert loaded_device_tpe is DeviceType.GeneratorDevice


def test_dgs_dynamic_import_bundle_reports_supported_and_failed_blocks() -> None:
    """Expose valid DGS equations while retaining unsupported blocks as failures."""

    dgs_path: Path = _get_dynamic_gain_block_dgs_path()
    bundle, _logger = build_dgs_dynamic_model_import_bundle(
        dgs_path=str(dgs_path),
    )
    entries_by_name = {
        entry.get_display_name(): entry
        for entry in bundle.get_entries()
    }

    assert bundle.get_source_tpe() is DynamicModelImportSource.PowerFactoryDgs
    assert set(entries_by_name) == {
        "Dynamic gain",
        "Unsupported dynamic block",
    }
    assert entries_by_name["Dynamic gain"].is_importable()
    assert (
        entries_by_name["Unsupported dynamic block"].get_availability()
        is DynamicModelImportEntryAvailability.Failed
    )


def test_dgs_dynamic_import_keeps_empty_physical_and_vendor_slot_metadata() -> None:
    """Preserve valid empty slots as visible, non-executable metadata.

    :return: None.
    """
    bundle: DynamicModelImportBundle
    bundle, _logger = build_dgs_dynamic_model_import_bundle(
        dgs_path=str(_get_non_executable_slots_dgs_path()),
    )
    entries_by_name: dict[str, DynamicModelImportEntry] = {
        entry.get_display_name(): entry
        for entry in bundle.get_entries()
    }
    reference_name: str
    for reference_name in (
            "Physical phase measurement",
            "Vendor extension reference",
    ):
        reference_entry: DynamicModelImportEntry = entries_by_name[reference_name]
        assert (
            reference_entry.get_availability()
            is DynamicModelImportEntryAvailability.MetadataOnly
        )
        assert reference_entry.get_source_block() is None
        assert not reference_entry.is_importable()

    assert (
        "physical slot has no exported pElm target"
        in entries_by_name["Physical phase measurement"].get_notes_text()
    )
    assert (
        "slot has no exported pElm target"
        in entries_by_name["Vendor extension reference"].get_notes_text()
    )


@pytest.mark.parametrize(
    "target_domain",
    [
        DynamicSimulationMode.RMS,
        DynamicSimulationMode.EMT,
    ],
)
def test_dgs_dynamic_import_materializes_the_selected_domain_end_to_end(
        target_domain: DynamicSimulationMode,
) -> None:
    """Preserve one DGS equation through parsing, selection and installation."""

    bundle, bundle_logger = build_dgs_dynamic_model_import_bundle(
        dgs_path=str(_get_dynamic_gain_block_dgs_path()),
    )
    gain_entry = next(
        entry
        for entry in bundle.get_entries()
        if entry.get_display_name() == "Dynamic gain"
    )
    source_block: Block | None = gain_entry.get_source_block()
    circuit: MultiCircuit = MultiCircuit()
    install_logger: Logger = Logger()

    assert bundle_logger.error_count() == 0
    assert source_block is not None

    added_count: int = add_dynamic_import_selection_requests_to_circuit(
        circuit=circuit,
        bundle=bundle,
        selection_requests=[
            DynamicModelImportSelectionRequest(
                entry_key=gain_entry.get_unique_key(),
                target_domain=target_domain,
                device_tpe=DeviceType.NoDevice,
            )
        ],
        logger=install_logger,
    )
    installed_templates: Sequence[RmsModelTemplate | EmtModelTemplate]
    other_template_count: int
    if target_domain is DynamicSimulationMode.RMS:
        installed_templates = circuit.rms_models
        other_template_count = len(circuit.emt_models)
    else:
        assert target_domain is DynamicSimulationMode.EMT
        installed_templates = circuit.emt_models
        other_template_count = len(circuit.rms_models)

    assert len(installed_templates) == 1
    assert other_template_count == 0

    installed_template: RmsModelTemplate | EmtModelTemplate = (
        installed_templates[0]
    )

    assert added_count == 1
    assert install_logger.error_count() == 0
    assert installed_template.name == "Dynamic gain"
    assert installed_template.tpe is DeviceType.NoDevice
    assert installed_template.block is not source_block
    assert len(installed_template.block.algebraic_eqs) == 1


@pytest.mark.parametrize(
    "dynamic_simulation_mode",
    [
        DynamicSimulationMode.RMS,
        DynamicSimulationMode.EMT,
    ],
)
def test_file_open_installs_dgs_models_in_the_explicit_dynamic_simulation_mode(
        dynamic_simulation_mode: DynamicSimulationMode,
) -> None:
    """Carry the selected RMS or EMT mode through the public DGS file-open path."""

    file_open: FileOpen = FileOpen(
        file_name=str(_get_dynamic_gain_block_dgs_path()),
        options=FileOpenOptions(
            file_type=FileType.DGS,
            dgs_use_dynamic_information=True,
            dgs_dynamic_simulation_mode=dynamic_simulation_mode,
        ),
    )
    circuit: MultiCircuit | None = file_open.open()

    assert circuit is not None

    installed_template: RmsModelTemplate | EmtModelTemplate
    if dynamic_simulation_mode is DynamicSimulationMode.RMS:
        assert len(circuit.rms_models) == 1
        assert len(circuit.emt_models) == 0
        installed_template = circuit.rms_models[0]
    else:
        assert dynamic_simulation_mode is DynamicSimulationMode.EMT
        assert len(circuit.emt_models) == 1
        assert len(circuit.rms_models) == 0
        installed_template = circuit.emt_models[0]

    assert installed_template.name == "Dynamic gain"
    logged_messages: set[str] = set(
        entry.msg for entry in file_open.logger.entries
    )
    assert "DGS dynamic template conversion completed" in logged_messages
    assert "DGS dynamic device assignment completed" in logged_messages


def test_file_open_rejects_dynamic_dgs_import_without_an_explicit_mode() -> None:
    """Keep the static DGS result and report the missing RMS/EMT selection."""

    file_open: FileOpen = FileOpen(
        file_name=str(_get_dynamic_gain_block_dgs_path()),
        options=FileOpenOptions(
            file_type=FileType.DGS,
            dgs_use_dynamic_information=True,
        ),
    )
    circuit: MultiCircuit | None = file_open.open()

    assert circuit is not None

    assert len(circuit.rms_models) == 0
    assert len(circuit.emt_models) == 0
    assert any(
        entry.msg == "DGS dynamic model import requires an explicit RMS or EMT simulation mode"
        for entry in file_open.logger.entries
    )
