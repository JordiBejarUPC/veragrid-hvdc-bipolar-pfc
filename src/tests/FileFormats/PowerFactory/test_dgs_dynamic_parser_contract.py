# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import runpy
from pathlib import Path
from types import FunctionType
from typing import Sequence

import pytest

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    DgsDirectRootBuildResult,
    DgsGraphicTreeResult,
    DgsGraphicalIndexes,
    DgsGraphicalConnectorKind,
    DgsRootBlockResult,
    ElmCompInstanceEntry,
    UnsupportedDgsExpression,
    build_dgs_graphical_indexes,
    build_direct_root_elmcomp_block,
    build_graphical_arithmetic_block,
    build_graphical_switch_block,
    build_standalone_blkdef_block_from_parsed_block,
    dgs_to_root_block,
    build_dgs_root_block_from_circuit,
    export_standalone_blkdef_to_python,
    extract_elmcomp_direct_instances,
    extract_root_slot_block_graphical_tree,
    get_unambiguous_elmcomp_direct_instances,
    parse_dgs_block_definitions_from_circuit,
)
from VeraGridEngine.IO.dgs.dgs_objects import BlkDef, BlkDiv, BlkMul, ElmComp
from VeraGridEngine.IO.dgs.dynamic_models.dynamic_model_import import (
    add_dynamic_import_selection_requests_to_circuit,
    build_dgs_dynamic_model_import_bundle,
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
    DynamicModelPersistenceKind,
    DynamicModelPersistenceSpec,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from VeraGridEngine.basic_structures import LogEntry, Logger
from VeraGridEngine.enumerations import DeviceType, DynamicSimulationMode, FileType


class ExportedBlockPythonModule:
    """Provide a typed boundary around one module loaded through ``runpy``.

    :param module_members: Runtime namespace produced from the exported module.
    """

    __slots__ = ("_block_builder",)

    def __init__(self, module_members: dict[str, object]) -> None:
        """Validate and store the generated module's block builder.

        :param module_members: Runtime namespace produced from the exported
            module.
        :return: None.
        """
        block_builder: object | None = module_members.get("get_block", None)
        if isinstance(block_builder, FunctionType):
            self._block_builder: FunctionType = block_builder
        else:
            raise AssertionError(
                "The exported DGS module must define a get_block function"
            )

    def build(
        self,
        variable_factory: VarFactory,
        block_name: str,
    ) -> Block:
        """Build and validate one block through the generated function.

        :param variable_factory: Factory that owns rebuilt symbolic variables.
        :param block_name: Runtime name assigned to the rebuilt block.
        :return: Validated rebuilt symbolic block.
        """
        rebuilt_block: object = self._block_builder(
            variable_factory,
            block_name,
        )
        if isinstance(rebuilt_block, Block):
            return rebuilt_block
        else:
            raise AssertionError(
                "The exported DGS get_block function must return a Block"
            )


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


def _parse_native_graphical_operator_fixture() -> DgsCircuit:
    """
    Parse the portable graph containing native arithmetic and switching nodes.

    :return: Parsed circuit containing the native graphical records and cables.
    """
    dgs_path: Path = _get_native_graphical_operator_dgs_path()
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    return circuit


def _build_exported_block(
        module_members: dict[str, object],
        variable_factory: VarFactory,
        block_name: str,
) -> Block:
    """
    Build one exported block after validating the generated callable and result.

    :param module_members: Runtime namespace produced from the exported module.
    :param variable_factory: Variable factory passed to the generated builder.
    :param block_name: Name assigned to the rebuilt block.
    :return: Validated rebuilt symbolic block.
    """
    exported_module: ExportedBlockPythonModule = ExportedBlockPythonModule(
        module_members=module_members,
    )
    return exported_module.build(
        variable_factory=variable_factory,
        block_name=block_name,
    )


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
    child_counts: list[int] = list()
    child_cache_counts: list[int] = list()
    graphical_cache_counts: list[int] = list()
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
        direct_build: DgsDirectRootBuildResult = (
            build_direct_root_elmcomp_block(
                circuit=circuit,
                result=root_result,
                graphical_indexes=graphical_indexes,
            )
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
        child_counts.append(len(direct_build.root_block.children))
        child_cache_counts.append(len(direct_build.child_block_by_slot_id))
        graphical_cache_counts.append(
            len(direct_build.graphical_tree_by_slot_id)
        )

    assert tuple(selected_counts) == (1, 0, 0)
    assert tuple(child_counts) == (1, 0, 0)
    assert tuple(child_cache_counts) == (1, 0, 0)
    assert tuple(graphical_cache_counts) == (1, 0, 0)


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
    persistence_spec: DynamicModelPersistenceSpec | None = (
        graphical_entry.get_persistence_spec()
    )
    topology_warnings: list[LogEntry] = [
        entry
        for entry in bundle_logger.entries
        if entry.msg == "DGS graphical operator topology incomplete"
    ]

    assert source_block is not None
    assert persistence_spec is not None
    assert (
        persistence_spec.get_kind()
        is DynamicModelPersistenceKind.DgsRootSlotGraphicalTree
    )
    assert len(topology_warnings) == 1
    assert "routed_internal" in str(topology_warnings[0].value)
    assert "blank_internal" not in str(topology_warnings[0].value)


def test_dgs_block_definition_builds_one_self_contained_symbolic_block() -> None:
    """Materialize the equation declared by a versioned DGS block definition."""

    dgs_path: Path = _get_dynamic_gain_block_dgs_path()
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    parsed_blocks = parse_dgs_block_definitions_from_circuit(circuit=circuit)
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


def test_dgs_block_definition_rejects_unsupported_syntax() -> None:
    """Reject a partial template when one DGS equation cannot be represented."""

    dgs_path: Path = _get_dynamic_gain_block_dgs_path()
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    parsed_blocks = parse_dgs_block_definitions_from_circuit(circuit=circuit)

    with pytest.raises(
        UnsupportedDgsExpression,
        match="Unsupported dynamic block.*unsupported syntax",
    ):
        build_standalone_blkdef_block_from_parsed_block(
            parsed_block=parsed_blocks["3"],
        )


def test_exported_dgs_block_module_rebuilds_the_source_equation(
        tmp_path: Path,
) -> None:
    """Execute a generated DGS block module without selecting RMS or EMT."""

    output_path: Path = tmp_path / "dynamic_gain_block.py"
    exported_path: Path = export_standalone_blkdef_to_python(
        dgs_path=str(_get_dynamic_gain_block_dgs_path()),
        output_path=str(output_path),
        block_id="2",
    )
    generated_source: str = exported_path.read_text(encoding="utf-8")
    module_members: dict[str, object] = runpy.run_path(str(exported_path))
    rebuilt_block: Block = _build_exported_block(
        module_members=module_members,
        variable_factory=VarFactory(),
        block_name="Rebuilt dynamic gain",
    )

    assert "EmtModelTemplate" not in generated_source
    assert "RmsModelTemplate" not in generated_source
    assert rebuilt_block.name == "Rebuilt dynamic gain"
    assert [var.name for var in rebuilt_block.in_vars] == [
        "u_Rebuilt dynamic gain"
    ]
    assert [var.name for var in rebuilt_block.out_vars] == [
        "y_Rebuilt dynamic gain"
    ]
    assert len(rebuilt_block.algebraic_eqs) == 1

    rebuilt_parameter = next(iter(rebuilt_block.event_dict))
    rebuilt_bindings: dict[str, float] = {
        rebuilt_block.in_vars[0].name: 3.0,
        rebuilt_block.out_vars[0].name: 6.0,
        rebuilt_parameter.name: 2.0,
    }
    assert rebuilt_block.algebraic_eqs[0].eval(**rebuilt_bindings) == 0.0


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
    assert any(
        entry.msg == "DGS dynamic model import completed"
        for entry in file_open.logger.entries
    )


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
