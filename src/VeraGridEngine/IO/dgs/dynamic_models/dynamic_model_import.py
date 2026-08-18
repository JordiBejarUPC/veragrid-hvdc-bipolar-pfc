# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Set, Tuple

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Parents.dynamic_parent import DynamicDevice
from VeraGridEngine.Devices.Branches.vsc import VSC
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_to_blocks import DgsStandaloneBlockCatalogEntry
from VeraGridEngine.IO.dgs.dgs_to_blocks import ElmCompInstanceEntry
from VeraGridEngine.IO.dgs.dgs_to_blocks import ParsedDgsBlockDefinition
from VeraGridEngine.IO.dgs.dgs_to_blocks import _TemplateModuleVariableGroups
from VeraGridEngine.IO.dgs.dgs_to_blocks import _build_template_module_variable_groups
from VeraGridEngine.IO.dgs.dgs_to_blocks import _emit_block_code
from VeraGridEngine.IO.dgs.dgs_to_blocks import _make_identifier_map
from VeraGridEngine.IO.dgs.dgs_to_blocks import _procedural_logic_import_names
from VeraGridEngine.IO.dgs.dgs_to_blocks import _safe_name
from VeraGridEngine.IO.dgs.dgs_to_blocks import export_named_block_subgraph_to_python
from VeraGridEngine.IO.dgs.dgs_to_blocks import export_root_elmcomp_template_to_python
from VeraGridEngine.IO.dgs.dgs_to_blocks import export_root_slot_block_graphical_template_to_python
from VeraGridEngine.IO.dgs.dgs_to_blocks import export_standalone_blkdef_to_python
from VeraGridEngine.IO.dgs.dgs_discrete_event import (
    DgsDiscreteEventAction,
    dgs_discrete_event_action_from_dict,
)
from VeraGridEngine.IO.dgs.dgs_to_blocks import DgsGraphicTreeResult
from VeraGridEngine.IO.dgs.dgs_to_blocks import extract_elmcomp_direct_instances
from VeraGridEngine.IO.dgs.dgs_objects import BlkSlot
from VeraGridEngine.IO.dgs.dgs_objects import ElmComp
from VeraGridEngine.IO.dynamic_model_import_types import (
    DgsDynamicModelActivationReport,
    DynamicModelImportBundle,
    DynamicModelImportEntry,
    DynamicModelImportEntryAvailability,
    DynamicModelImportEntryResult,
    DynamicModelImportEntryStatus,
    DynamicModelImportReport,
    DynamicModelImportSelectionRequest,
    DynamicModelImportSource,
    DynamicModelImportSourceContext,
    DynamicModelImportTargetDomain,
    DynamicModelLoadedUserTemplate,
    DynamicModelPersistenceKind,
    DynamicModelPersistenceSpec,
    SelectedDynamicImportWork,
    _DynamicUserTemplatePythonModule,
    _emit_dynamic_model_import_progress,
)
from VeraGridEngine.IO.dgs.dynamic_models.dgs_dynamic_association import DgsDynamicAssociationRecord
from VeraGridEngine.IO.dgs.dynamic_models.dgs_dynamic_association import infer_dgs_dynamic_association_role
from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmvsc_runtime_adapter import (
    build_dgs_elmvscmono_rms_runtime_template,
    build_dgs_elmvsc_rms_runtime_template,
    configure_dgs_elmvscmono_runtime_template_for_device,
    configure_dgs_elmvsc_runtime_template_for_device,
    is_dgs_elmvscmono_slot_contract,
    is_dgs_elmvsc_slot_contract,
)
from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmsym_runtime_adapter import (
    build_dgs_elmsym_rms_runtime_template,
    configure_dgs_elmsym_runtime_template_for_device,
    is_dgs_elmsym_slot_contract,
)
from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmgenstat_runtime_adapter import (
    build_dgs_elmgenstat_rms_runtime_template,
    is_dgs_elmgenstat_slot_contract,
)
from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmsvs_runtime_adapter import (
    build_dgs_elmsvs_rms_runtime_template,
    is_dgs_elmsvs_slot_contract,
)
from VeraGridEngine.IO.file_system import get_create_veragrid_folder
from VeraGridEngine.IO.dynamic_model_import_utils import (
    append_python_syntax_assignment,
    sanitize_dynamic_model_file_stem,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.procedural_logic import AnalogFlipFlopLogic
from VeraGridEngine.Utils.procedural_logic import FixedSampleLogic
from VeraGridEngine.Utils.procedural_logic import FlipFlopLogic
from VeraGridEngine.Utils.procedural_logic import GradientLimiterLogic
from VeraGridEngine.Utils.procedural_logic import HardSaturationLogic
from VeraGridEngine.Utils.procedural_logic import MovingAverageLogic
from VeraGridEngine.Utils.procedural_logic import PickupDropoffLogic
from VeraGridEngine.Utils.procedural_logic import ProceduralLogicBase
from VeraGridEngine.Utils.procedural_logic import ResetOnRisingEdgeLogic
from VeraGridEngine.Utils.procedural_logic import SampledValueLogic
from VeraGridEngine.Utils.procedural_logic import TimeDelayLogic
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (
    BlockScopeMode,
    BlockType,
    DeviceType,
    VarPowerFlowReferenceType,
)

class DgsDynamicParserContractError(RuntimeError):
    """Report that the dynamic DGS parser boundary is incomplete."""


def _wrap_block_as_generic_emt_template(block: Block, template_name: str) -> EmtModelTemplate:
    """
    Wrap one runtime block as a generic EMT template.

    :param block: Runtime block to expose.
    :param template_name: Imported template name.
    :return: Generic EMT template.
    """
    template: EmtModelTemplate = EmtModelTemplate(name=template_name)
    template.tpe = DeviceType.NoDevice
    template.block = block
    template.name = template_name
    return template




def _select_root_frame_display_name(root_block: Block) -> str | None:
    """
    Select the composite frame name used to group one imported PWM root.

    :param root_block: Parsed imported root block.
    :return: Preferred frame display name, or ``None``.
    """
    candidate_names: List[str] = list()
    child_block: Block
    child_name: str

    for child_block in root_block.children:
        child_name = str(child_block.name)

        if child_name == "VSC_Frame":
            return child_name
        else:
            if child_name.startswith("VSC_Frame"):
                candidate_names.append(child_name)
            else:
                pass

    if len(candidate_names) == 0:
        return None
    else:
        candidate_names.sort(key=len)
        return candidate_names[0]


def _build_dgs_context_slot_notes(circuit: DgsCircuit, root_name: str, entry: ElmCompInstanceEntry) -> str:
    """
    Build one readable note string for a DGS context slot without a materialized block.

    :param circuit: Parsed DGS circuit.
    :param root_name: Root ElmComp display name.
    :param entry: Direct slot entry.
    :return: Human-readable notes text.
    """
    from VeraGridEngine.IO.dgs.dgs_to_blocks import get_blkslot_signal_interface

    incoming_signals, outgoing_signals = get_blkslot_signal_interface(
        circuit=circuit,
        slot_id=entry.slot_id,
    )
    notes_parts: List[str] = [f"Root: {root_name}", "Context slot"]
    slot_obj: BlkSlot | None = None
    candidate_slot: BlkSlot

    if entry.slot_id is None:
        pass
    else:
        # The raw BlkSlot carries the physical interface metadata even when no ElmDsl/BlkDef exists behind it.
        for candidate_slot in circuit.blkslots:
            if str(candidate_slot.ID) == str(entry.slot_id):
                slot_obj = candidate_slot
                break
            else:
                pass

    if slot_obj is None:
        pass
    else:
        # The filter and slot IO names make the imported topology readable for valves, switches and measurements.
        if str(slot_obj.filtmod).strip() != "":
            notes_parts.append(f"filter: {slot_obj.filtmod}")
        else:
            pass

        if len(slot_obj.outputs) > 0:
            notes_parts.append(f"slot outputs: {', '.join(slot_obj.outputs)}")
        else:
            pass

        if len(slot_obj.inputs) > 0:
            notes_parts.append(f"slot inputs: {', '.join(slot_obj.inputs)}")
        else:
            pass

    if len(outgoing_signals) > 0:
        notes_parts.append(f"outputs: {', '.join(outgoing_signals)}")
    else:
        pass

    if len(incoming_signals) > 0:
        notes_parts.append(f"inputs: {', '.join(incoming_signals)}")
    else:
        pass

    return " | ".join(notes_parts)


def _build_dgs_import_source_context(
        root_element: ElmComp,
        direct_entry: ElmCompInstanceEntry | None = None,
) -> DynamicModelImportSourceContext:
    """
    Build typed provenance for one root or direct ElmComp slot entry.

    :param root_element: Owning root ElmComp.
    :param direct_entry: Optional direct pBlk/pElm slot relation.
    :return: Typed root/slot/element source context.
    """
    if direct_entry is None:
        slot_dgs_id: str | None = None
        slot_name: str | None = None
        slot_index: int | None = None
        slot_element: str | None = None
        slot_filter: str | None = None
        source_element_dgs_id: str | None = None
        source_element_name: str | None = None
        source_element_class: str | None = None
    else:
        slot_dgs_id = direct_entry.slot_id
        slot_name = direct_entry.slot_name
        slot_index = direct_entry.slot_index
        slot_element = direct_entry.slot_element
        slot_filter = direct_entry.slot_filter
        source_element_dgs_id = direct_entry.element_id
        source_element_name = direct_entry.element_name
        source_element_class = direct_entry.element_kind

    source_context: DynamicModelImportSourceContext = DynamicModelImportSourceContext(
        root_dgs_id=root_element.ID,
        root_name=root_element.loc_name,
        root_typ_id=root_element.typ_id,
        slot_dgs_id=slot_dgs_id,
        slot_name=slot_name,
        slot_index=slot_index,
        slot_element=slot_element,
        slot_filter=slot_filter,
        source_element_dgs_id=source_element_dgs_id,
        source_element_name=source_element_name,
        source_element_class=source_element_class,
    )
    return source_context


def _build_dgs_root_elmcomp_entries_with_progress(
        dgs_path: str,
        progress_callback: Callable[[int, str], None] | None,
        progress_start: int,
        progress_end: int,
        dgs_circuit: DgsCircuit | None = None,
        parsed_dgs_blocks: Dict[str, ParsedDgsBlockDefinition] | None = None,
) -> Tuple[List[DynamicModelImportEntry], Logger]:
    """
    Build root ``ElmComp`` import entries while emitting progress updates.

    :param dgs_path: Source DGS path.
    :param progress_callback: Optional UI progress callback.
    :param progress_start: Inclusive start percentage for this phase.
    :param progress_end: Inclusive end percentage for this phase.
    :param dgs_circuit: Optional already parsed massive-import context.
    :param parsed_dgs_blocks: Optional definitions parsed from ``dgs_circuit``.
    :return: Pair ``(entries, logger)``.
    """
    from VeraGridEngine.IO.dgs.dgs_to_blocks import (
        DgsDirectRootBuildResult,
        DgsGraphicalParseContext,
        build_dgs_graphical_parse_context,
        build_direct_root_elmcomp_result_from_context,
        build_standalone_blkdef_emt_template,
        build_standalone_blkdef_emt_template_from_parsed_block,
        dgs_to_root_block_from_context,
        extract_root_slot_block_graphical_tree_from_context,
        parse_dgs_block_definitions_from_context,
    )

    circuit: DgsCircuit
    entries: List[DynamicModelImportEntry] = list()
    logger: Logger = Logger()
    root_element: ElmComp
    root_result = None
    root_template: EmtModelTemplate
    root_entry: DynamicModelImportEntry
    root_direct_entries: List[ElmCompInstanceEntry]
    direct_entry: ElmCompInstanceEntry
    frame_display_name: str | None
    frame_entry_key: str | None
    slot_display_name: str
    slot_parent_key: str
    slot_identity: str
    slot_availability: DynamicModelImportEntryAvailability
    graph_tree: DgsGraphicTreeResult | None = None
    cached_slot_block: Block | None = None
    materialized_slot_block: Block | None = None
    slot_was_graphical: bool = False
    slot_persistence_spec: DynamicModelPersistenceSpec
    parsed_slot_block: ParsedDgsBlockDefinition | None = None
    total_root_count: int
    total_slot_count: int = 0
    total_steps: int
    completed_steps: int = 0
    processed_root_count: int = 0
    processed_slot_count: int = 0
    progress_span: int = progress_end - progress_start
    current_progress_value: int
    root_source_context: DynamicModelImportSourceContext
    slot_source_context: DynamicModelImportSourceContext
    direct_child_block_by_slot_id: Dict[str, Block] = dict()
    direct_graphical_slot_ids: Set[str] = set()
    reported_unresolved_graphical_contracts: Set[Tuple[str, ...]] = set()

    if dgs_circuit is None:
        circuit = DgsCircuit()
        circuit.parse_dgs(dgs_path)
    else:
        circuit = dgs_circuit
    total_root_count = len(circuit.elmcomps)

    for root_element in circuit.elmcomps:
        total_slot_count += len(extract_elmcomp_direct_instances(circuit, root_element))

    total_steps = total_root_count + total_slot_count
    if total_steps <= 0:
        _emit_dynamic_model_import_progress(progress_callback, progress_end, "DGS root catalogue ready")
        return entries, logger
    else:
        pass

    # Parsing BlkDef expressions is independent of the concrete ElmDsl
    # parameters. Share that immutable context across every root in a massive
    # DGS import, while each root below still materializes its own instances.
    shared_parsed_dgs_blocks: Dict[str, ParsedDgsBlockDefinition]
    if parsed_dgs_blocks is None:
        shared_parsed_dgs_blocks = parse_dgs_block_definitions_from_context(
            circuit=circuit
        )
    else:
        shared_parsed_dgs_blocks = parsed_dgs_blocks
    graphical_context: DgsGraphicalParseContext = (
        build_dgs_graphical_parse_context(circuit=circuit)
    )

    for root_element in circuit.elmcomps:
        root_direct_entries = list(extract_elmcomp_direct_instances(circuit, root_element))
        root_entry_key: str = f"dgs-root|{root_element.ID}"
        root_source_context = _build_dgs_import_source_context(root_element=root_element)
        try:
            root_result = dgs_to_root_block_from_context(
                circuit=circuit,
                parsed_blocks=shared_parsed_dgs_blocks,
                root_name=root_element.loc_name,
                root_typ_id=root_element.typ_id,
                root_dgs_id=root_element.ID,
            )
        except Exception as exc:
            logger.add_warning(
                msg="DGS root ElmComp import skipped",
                value=f"{root_element.loc_name}: {exc}",
            )
            root_result = None
        else:
            pass

        processed_root_count += 1
        completed_steps += 1
        current_progress_value = progress_start + int(round(progress_span * float(completed_steps) / float(total_steps)))
        _emit_dynamic_model_import_progress(
            progress_callback,
            current_progress_value,
            f"Importing DGS roots: {processed_root_count}/{total_root_count}",
        )

        if root_result is None:
            # A failed root remains a catalogue node so the report does not
            # hide the source object or any of its exact pblk/pelm relations.
            entries.append(
                DynamicModelImportEntry(
                    unique_key=root_entry_key,
                    display_name=root_element.loc_name,
                    source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                    template=None,
                    notes_text="Root ElmComp could not be materialized",
                    source_context=root_source_context,
                )
            )

            for direct_entry in root_direct_entries:
                if direct_entry.slot_id is None:
                    slot_identity = f"index-{direct_entry.slot_index}"
                else:
                    slot_identity = str(direct_entry.slot_id)

                if direct_entry.slot_name is None:
                    slot_display_name = f"Slot {direct_entry.slot_index}"
                else:
                    slot_display_name = str(direct_entry.slot_name)

                slot_source_context = _build_dgs_import_source_context(
                    root_element=root_element,
                    direct_entry=direct_entry,
                )
                entries.append(
                    DynamicModelImportEntry(
                        unique_key=f"dgs-unavailable|{root_element.ID}|{slot_identity}|{direct_entry.element_id}",
                        display_name=slot_display_name,
                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                        template=None,
                        notes_text=(
                            f"Root: {root_element.loc_name} | "
                            "Slot unavailable because its root could not be materialized"
                        ),
                        parent_key=root_entry_key,
                        source_context=slot_source_context,
                    )
                )
                processed_slot_count += 1
                completed_steps += 1
                current_progress_value = progress_start + int(
                    round(progress_span * float(completed_steps) / float(total_steps))
                )
                _emit_dynamic_model_import_progress(
                    progress_callback,
                    current_progress_value,
                    f"Importing DGS slots: {processed_slot_count}/{total_slot_count}",
                )
        else:
            try:
                direct_root_build_result: DgsDirectRootBuildResult = (
                    build_direct_root_elmcomp_result_from_context(
                        circuit=circuit,
                        result=root_result,
                        graphical_context=graphical_context,
                    )
                )
                direct_root_block: Block = direct_root_build_result.root_block
                direct_child_block_by_slot_id = (
                    direct_root_build_result.child_block_by_slot_id
                )
                direct_graphical_slot_ids = (
                    direct_root_build_result.graphical_slot_ids
                )
                root_template = _wrap_block_as_generic_emt_template(
                    block=direct_root_block,
                    template_name=root_element.loc_name,
                )
            except Exception as exc:
                logger.add_warning(
                    msg="DGS root ElmComp materialization skipped",
                    value=f"{root_element.loc_name}: {exc}",
                )
                root_template = None
                direct_child_block_by_slot_id = dict()
                direct_graphical_slot_ids = set()
                # Keep the independently parsed pblk/pelm relations so every
                # failed slot remains visible in the partial-import report.
                root_direct_entries = list(root_direct_entries)

            if root_template is None:
                frame_display_name = None
            else:
                frame_display_name = _select_root_frame_display_name(root_result.root_block)
            frame_entry_key = None

            if root_template is None:
                entries.append(
                    DynamicModelImportEntry(
                        unique_key=root_entry_key,
                        display_name=root_element.loc_name,
                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                        template=None,
                        notes_text="Root ElmComp block could not be materialized",
                        source_context=root_source_context,
                    )
                )
            else:
                root_entry = DynamicModelImportEntry(
                    unique_key=root_entry_key,
                    display_name=root_element.loc_name,
                    source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                    template=root_template,
                    notes_text="Root ElmComp block",
                    persistence_spec=DynamicModelPersistenceSpec(
                        kind=DynamicModelPersistenceKind.DgsRootElmComp,
                        source_path=dgs_path,
                        template_name=root_element.loc_name,
                        module_stem=_sanitize_file_stem(root_element.loc_name),
                        root_name=root_element.loc_name,
                        root_typ_id=root_element.typ_id,
                    ),
                    source_context=root_source_context,
                )
                entries.append(root_entry)

            if frame_display_name is None:
                pass
            else:
                frame_entry_key = f"dgs-frame|{root_element.ID}|{root_element.typ_id}"
                entries.append(
                    DynamicModelImportEntry(
                        unique_key=frame_entry_key,
                        display_name=frame_display_name,
                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                        template=None,
                        notes_text=f"Root: {root_element.loc_name} | Composite frame",
                        parent_key=root_entry_key,
                        source_context=root_source_context,
                        availability=DynamicModelImportEntryAvailability.ContextOnly,
                    )
                )

            direct_entry = None
            for direct_entry in root_direct_entries:
                if direct_entry.slot_name is None:
                    if direct_entry.slot_id is None:
                        slot_identity = f"index-{direct_entry.slot_index}"
                    else:
                        slot_identity = str(direct_entry.slot_id)
                    slot_source_context = _build_dgs_import_source_context(
                        root_element=root_element,
                        direct_entry=direct_entry,
                    )
                    if direct_entry.type_id is None:
                        slot_availability = DynamicModelImportEntryAvailability.ContextOnly
                    else:
                        slot_availability = DynamicModelImportEntryAvailability.Failed
                    entries.append(
                        DynamicModelImportEntry(
                            unique_key=(
                                f"dgs-unavailable|{root_element.ID}|"
                                f"{slot_identity}|{direct_entry.element_id}"
                            ),
                            display_name=f"Slot {direct_entry.slot_index}",
                            source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                            template=None,
                            notes_text=f"Root: {root_element.loc_name} | Slot has no exported name",
                            parent_key=root_entry_key if frame_entry_key is None else frame_entry_key,
                            source_context=slot_source_context,
                            availability=slot_availability,
                        )
                    )
                    processed_slot_count += 1
                    completed_steps += 1
                    current_progress_value = progress_start + int(
                        round(progress_span * float(completed_steps) / float(total_steps))
                    )
                    _emit_dynamic_model_import_progress(
                        progress_callback,
                        current_progress_value,
                        f"Importing DGS slots: {processed_slot_count}/{total_slot_count}",
                    )
                else:
                    slot_parent_key = root_entry_key if frame_entry_key is None else frame_entry_key
                    slot_display_name = str(direct_entry.slot_name)
                    if direct_entry.slot_id is None:
                        slot_identity = f"index-{direct_entry.slot_index}"
                    else:
                        slot_identity = str(direct_entry.slot_id)
                    slot_source_context = _build_dgs_import_source_context(
                        root_element=root_element,
                        direct_entry=direct_entry,
                    )

                    slot_template_name: str = f"{root_element.loc_name}::{direct_entry.slot_name}"
                    slot_template: EmtModelTemplate | None = None

                    if direct_entry.type_id is None:
                        entries.append(
                            DynamicModelImportEntry(
                                unique_key=f"dgs-context|{root_element.ID}|{slot_identity}|{direct_entry.element_id}",
                                display_name=slot_display_name,
                                source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                template=None,
                                notes_text=_build_dgs_context_slot_notes(circuit=circuit, root_name=root_element.loc_name, entry=direct_entry),
                                parent_key=slot_parent_key,
                                source_context=slot_source_context,
                                availability=DynamicModelImportEntryAvailability.ContextOnly,
                            )
                        )
                    else:
                        # Reuse the exact child materialized while building the
                        # composite root. This avoids parsing the same graphical
                        # controller twice during a massive DGS import.
                        if direct_entry.slot_id is None:
                            cached_slot_block = None
                        else:
                            cached_slot_block = direct_child_block_by_slot_id.get(
                                str(direct_entry.slot_id),
                                None,
                            )

                        if cached_slot_block is None:
                            try:
                                graph_tree = extract_root_slot_block_graphical_tree_from_context(
                                    circuit=circuit,
                                    result=root_result,
                                    slot_name=direct_entry.slot_name,
                                    slot_dgs_id=direct_entry.slot_id,
                                    graphical_context=graphical_context,
                                )
                            except Exception as exc:
                                logger.add_warning(
                                    msg="DGS slot import skipped",
                                    value=f"{root_element.loc_name}/{direct_entry.slot_name}: {exc}",
                                )
                                graph_tree = None
                            else:
                                pass

                            if graph_tree is None:
                                materialized_slot_block = None
                                slot_was_graphical = False
                            else:
                                materialized_slot_block = graph_tree.view_block
                                slot_was_graphical = True
                        else:
                            graph_tree = None
                            materialized_slot_block = cached_slot_block
                            if direct_entry.slot_id is None:
                                slot_was_graphical = False
                            else:
                                slot_was_graphical = (
                                    str(direct_entry.slot_id) in direct_graphical_slot_ids
                                )

                        if materialized_slot_block is None:
                            unresolved_graphical_input_names: List[str] = list()
                        else:
                            raw_unresolved_graphical_input_names: object | None = (
                                materialized_slot_block.__dict__.get(
                                    "dgs_unresolved_graphical_input_names",
                                    None,
                                )
                            )
                            unresolved_graphical_input_names = list()
                            if isinstance(raw_unresolved_graphical_input_names, list):
                                raw_unresolved_graphical_input_name: object
                                for raw_unresolved_graphical_input_name in raw_unresolved_graphical_input_names:
                                    if isinstance(raw_unresolved_graphical_input_name, str):
                                        unresolved_graphical_input_names.append(
                                            raw_unresolved_graphical_input_name
                                        )
                                    else:
                                        pass
                                else:
                                    pass
                            else:
                                pass
                        unresolved_graphical_input_names.sort()
                        if len(unresolved_graphical_input_names) == 0:
                            pass
                        else:
                            unresolved_contract_parts: List[str] = list()
                            unresolved_contract_parts.append(str(direct_entry.type_id))
                            unresolved_contract_parts.extend(
                                unresolved_graphical_input_names
                            )
                            unresolved_contract_key: Tuple[str, ...] = tuple(
                                unresolved_contract_parts
                            )
                            if unresolved_contract_key in reported_unresolved_graphical_contracts:
                                pass
                            else:
                                reported_unresolved_graphical_contracts.add(
                                    unresolved_contract_key
                                )
                                logger.add_warning(
                                    msg="DGS graphical operator topology incomplete",
                                    value=(
                                        f"{direct_entry.type_name}: live routed inputs "
                                        f"{unresolved_graphical_input_names} have no exported "
                                        "producer. Re-export with BlkDiv, BlkMul and BlkSwt "
                                        "monitors in DGS Export Definitions 7_2/Export DGS."
                                    ),
                                )

                        if materialized_slot_block is None:
                            parsed_slot_block = root_result.parsed_blocks.get(str(direct_entry.type_id), None)
                            try:
                                if parsed_slot_block is None:
                                    slot_template = build_standalone_blkdef_emt_template(
                                        dgs_path=dgs_path,
                                        typ_id=direct_entry.type_id,
                                        template_name=slot_template_name,
                                    )
                                else:
                                    slot_template = build_standalone_blkdef_emt_template_from_parsed_block(
                                        parsed_block=parsed_slot_block,
                                        template_name=slot_template_name,
                                    )
                            except Exception as exc:
                                logger.add_warning(
                                    msg="DGS slot block materialization skipped",
                                    value=f"{root_element.loc_name}/{direct_entry.slot_name}: {exc}",
                                )
                                slot_template = None

                            if slot_template is None:
                                entries.append(
                                    DynamicModelImportEntry(
                                        unique_key=(
                                            f"dgs-unavailable|{root_element.ID}|"
                                            f"{slot_identity}|{direct_entry.element_id}"
                                        ),
                                        display_name=slot_display_name,
                                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                        template=None,
                                        notes_text=(
                                            f"Root: {root_element.loc_name} | "
                                            f"Slot: {direct_entry.slot_name} | Block could not be materialized"
                                        ),
                                        parent_key=slot_parent_key,
                                        source_context=slot_source_context,
                                    )
                                )
                            else:
                                entries.append(
                                    DynamicModelImportEntry(
                                        unique_key=f"dgs-slot|{root_element.ID}|{slot_identity}|{direct_entry.element_id}",
                                        display_name=slot_display_name,
                                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                        template=slot_template,
                                        notes_text=f"Root: {root_element.loc_name} | Slot: {direct_entry.slot_name}",
                                        parent_key=slot_parent_key,
                                        persistence_spec=DynamicModelPersistenceSpec(
                                            kind=DynamicModelPersistenceKind.DgsStandaloneBlkdef,
                                            source_path=dgs_path,
                                            template_name=slot_template_name,
                                            module_stem=_sanitize_file_stem(slot_template_name),
                                            block_id=str(direct_entry.type_id),
                                            block_name=str(direct_entry.type_name),
                                        ),
                                        source_context=slot_source_context,
                                    )
                                )
                        else:
                            try:
                                slot_template = _wrap_block_as_generic_emt_template(
                                    block=materialized_slot_block,
                                    template_name=slot_template_name,
                                )
                            except Exception as exc:
                                logger.add_warning(
                                    msg="DGS graphical slot materialization skipped",
                                    value=f"{root_element.loc_name}/{direct_entry.slot_name}: {exc}",
                                )
                                slot_template = None

                            if slot_template is None:
                                entries.append(
                                    DynamicModelImportEntry(
                                        unique_key=(
                                            f"dgs-unavailable|{root_element.ID}|"
                                            f"{slot_identity}|{direct_entry.element_id}"
                                        ),
                                        display_name=slot_display_name,
                                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                        template=None,
                                        notes_text=(
                                            f"Root: {root_element.loc_name} | "
                                            f"Slot: {direct_entry.slot_name} | Graph could not be materialized"
                                        ),
                                        parent_key=slot_parent_key,
                                        source_context=slot_source_context,
                                    )
                                )
                            else:
                                if slot_was_graphical:
                                    slot_persistence_spec = DynamicModelPersistenceSpec(
                                        kind=DynamicModelPersistenceKind.DgsRootSlotGraphicalTree,
                                        source_path=dgs_path,
                                        template_name=slot_template_name,
                                        module_stem=_sanitize_file_stem(slot_template_name),
                                        root_name=root_element.loc_name,
                                        root_typ_id=root_element.typ_id,
                                        slot_name=direct_entry.slot_name,
                                    )
                                else:
                                    slot_persistence_spec = DynamicModelPersistenceSpec(
                                        kind=DynamicModelPersistenceKind.DgsStandaloneBlkdef,
                                        source_path=dgs_path,
                                        template_name=slot_template_name,
                                        module_stem=_sanitize_file_stem(slot_template_name),
                                        block_id=str(direct_entry.type_id),
                                        block_name=str(direct_entry.type_name),
                                    )
                                entries.append(
                                    DynamicModelImportEntry(
                                        unique_key=f"dgs-slot|{root_element.ID}|{slot_identity}|{direct_entry.element_id}",
                                        display_name=slot_display_name,
                                        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                                        template=slot_template,
                                        notes_text=f"Root: {root_element.loc_name} | Slot: {direct_entry.slot_name}",
                                        parent_key=slot_parent_key,
                                        persistence_spec=slot_persistence_spec,
                                        source_context=slot_source_context,
                                    )
                                )

                    processed_slot_count += 1
                    completed_steps += 1
                    current_progress_value = progress_start + int(round(progress_span * float(completed_steps) / float(total_steps)))
                    _emit_dynamic_model_import_progress(
                        progress_callback,
                        current_progress_value,
                        f"Importing DGS slots: {processed_slot_count}/{total_slot_count}",
                    )

    _emit_dynamic_model_import_progress(progress_callback, progress_end, "DGS root and slot catalogue ready")
    return entries, logger






def build_dgs_dynamic_model_import_bundle(
        dgs_path: str,
        progress_callback: Callable[[int, str], None] | None = None,
        dgs_circuit: DgsCircuit | None = None,
) -> Tuple[DynamicModelImportBundle, Logger]:
    """
    Parse one PowerFactory DGS file into a bundle of EMT template candidates.

    :param dgs_path: Source DGS path.
    :param progress_callback: Optional UI progress callback.
    :param dgs_circuit: Optional circuit already parsed by the static importer.
    :return: Pair ``(bundle, logger)``.
    """
    try:
        from VeraGridEngine.IO.dgs.dgs_to_blocks import (
            build_dgs_standalone_block_catalog_from_context,
            build_standalone_blkdef_emt_template_from_parsed_block,
            parse_dgs_block_definitions_from_context,
        )
    except ImportError as error:
        raise DgsDynamicParserContractError(
            "The dynamic DGS importer requires parser functions that are not "
            "present after the parser reversion. Restore and test that parser "
            "boundary before importing dynamic DGS models."
        ) from error

    logger: Logger = Logger()
    shared_circuit: DgsCircuit
    shared_parsed_blocks: Dict[str, ParsedDgsBlockDefinition]
    catalog_entries: List[DgsStandaloneBlockCatalogEntry]
    bundle_entries: List[DynamicModelImportEntry] = list()
    root_entries: List[DynamicModelImportEntry]
    root_logger: Logger
    catalog_entry: DgsStandaloneBlockCatalogEntry

    # Static and dynamic import consume the same ASCII object graph. Reuse that
    # graph so a massive DGS is parsed once and every catalogue/root view is
    # guaranteed to observe the same source objects.
    if dgs_circuit is None:
        shared_circuit = DgsCircuit()
        shared_circuit.parse_dgs(dgs_path)
    else:
        shared_circuit = dgs_circuit
    shared_parsed_blocks = parse_dgs_block_definitions_from_context(
        circuit=shared_circuit
    )

    _emit_dynamic_model_import_progress(progress_callback, 0, "Scanning DGS dynamic model structure...")
    try:
        catalog_entries = build_dgs_standalone_block_catalog_from_context(
            circuit=shared_circuit,
            parsed_blocks=shared_parsed_blocks,
            isolated_only=False,
        )
    except Exception as exc:
        catalog_entries = list()
        logger.add_warning(
            msg="Standalone DGS dynamic-model catalogue skipped",
            value=str(exc),
        )
    _emit_dynamic_model_import_progress(progress_callback, 15, "Building standalone DGS block catalogue...")

    for catalog_entry in catalog_entries:
        template: EmtModelTemplate | None = None
        notes_lines: List[str] = list()
        notes_text: str

        if catalog_entry.build_error is None:
            try:
                template = build_standalone_blkdef_emt_template_from_parsed_block(
                    parsed_block=shared_parsed_blocks[catalog_entry.typ_id],
                    template_name=catalog_entry.blkdef_name,
                )
            except Exception as exc:
                notes_lines.append(f"Build error: {exc}")
                logger.add_warning(
                    msg="DGS dynamic block build error",
                    value=f"{catalog_entry.blkdef_name}: {exc}",
                )
        else:
            notes_lines.append(f"Build error: {catalog_entry.build_error}")
            logger.add_warning(msg="DGS dynamic block build error", value=catalog_entry.build_error)

        if len(catalog_entry.unsupported_lines) > 0:
            notes_lines.append(f"Unsupported statements: {len(catalog_entry.unsupported_lines)}")
        else:
            pass

        notes_lines.append(
            f"Occurrences: {catalog_entry.occurrence_count} | Isolated: {catalog_entry.isolated_occurrence_count} | Connected: {catalog_entry.connected_occurrence_count}"
        )
        notes_text = "\n".join(notes_lines)

        bundle_entries.append(
            DynamicModelImportEntry(
                unique_key=f"dgs|{catalog_entry.typ_id}|{catalog_entry.blkdef_name}",
                display_name=catalog_entry.blkdef_name,
                source_tpe=DynamicModelImportSource.PowerFactoryDgs,
                template=template,
                notes_text=notes_text,
                persistence_spec=DynamicModelPersistenceSpec(
                    kind=DynamicModelPersistenceKind.DgsStandaloneBlkdef,
                    source_path=dgs_path,
                    template_name=catalog_entry.blkdef_name,
                    module_stem=_sanitize_file_stem(catalog_entry.blkdef_name),
                    block_id=catalog_entry.typ_id,
                    block_name=catalog_entry.blkdef_name,
                ),
            )
        )

    try:
        root_entries, root_logger = _build_dgs_root_elmcomp_entries_with_progress(
            dgs_path=dgs_path,
            progress_callback=progress_callback,
            progress_start=15,
            progress_end=95,
            dgs_circuit=shared_circuit,
            parsed_dgs_blocks=shared_parsed_blocks,
        )
    except Exception as exc:
        root_entries = list()
        root_logger = Logger()
        logger.add_warning(
            msg="Root DGS dynamic-model catalogue skipped",
            value=str(exc),
        )
    if root_logger.has_logs():
        logger += root_logger
    else:
        pass

    bundle_entries.extend(root_entries)
    _emit_dynamic_model_import_progress(progress_callback, 100, "DGS dynamic model catalogue ready")

    bundle: DynamicModelImportBundle = DynamicModelImportBundle(
        source_tpe=DynamicModelImportSource.PowerFactoryDgs,
        source_path=dgs_path,
        entries=bundle_entries,
    )
    return bundle, logger


def get_dynamic_model_import_supported_device_types() -> List[DeviceType]:
    """
    Return the supported host-device types exposed by the import dialog.

    Imported external templates do not reliably encode the final VeraGrid device
    type, so the user must choose one explicit compatible target from a curated
    list instead of the full internal ``DeviceType`` enumeration.

    :return: Supported host-device types.
    """
    return list([
        DeviceType.NoDevice,
        DeviceType.DynamicModelHostDevice,
        DeviceType.GeneratorDevice,
        DeviceType.StaticGeneratorDevice,
        DeviceType.BatteryDevice,
        DeviceType.LoadDevice,
        DeviceType.ShuntDevice,
        DeviceType.ControllableShuntDevice,
        DeviceType.CurrentInjectionDevice,
        DeviceType.ExternalGridDevice,
        DeviceType.LineDevice,
        DeviceType.Transformer2WDevice,
        DeviceType.VscDevice,
        DeviceType.HVDCLineDevice,
        DeviceType.DCLineDevice,
        DeviceType.SwitchDevice,
    ])


def _collect_block_names_recursive(block: Block) -> List[str]:
    """
    Collect the visible block names from one imported block tree.

    :param block: Imported symbolic block.
    :return: Recursive block-name list.
    """
    names: List[str] = list([str(block.name)])
    child_block: Block

    for child_block in block.children:
        names.extend(_collect_block_names_recursive(child_block))

    return names


def guess_dynamic_model_import_default_target_domain(entry: "DynamicModelImportEntry") -> DynamicModelImportTargetDomain:
    """
    Guess the most likely default target domain for one imported entry.

    Some PowerFactory root controls describe RMS phasor controllers even when they
    arrive through the generic DGS path. The dialog keeps EMT as the generic
    fallback, but roots explicitly labelled as RMS default to that domain.

    :param entry: Imported entry.
    :return: Default target domain guess.
    """
    source_template: EmtModelTemplate | None = entry.get_template()
    searchable_names: List[str] = list([entry.get_display_name().lower()])
    searchable_text: str

    if entry.get_source_tpe() != DynamicModelImportSource.PowerFactoryDgs:
        return DynamicModelImportTargetDomain.Emt
    else:
        pass

    if source_template is None:
        pass
    else:
        searchable_names.extend(name.lower() for name in _collect_block_names_recursive(source_template.block))

    searchable_text = "\n".join(searchable_names)

    if "(rms" in searchable_text or "rms balanced" in searchable_text:
        return DynamicModelImportTargetDomain.Rms
    else:
        return DynamicModelImportTargetDomain.Emt


def guess_dynamic_model_import_hierarchy_target_domain(
        bundle: "DynamicModelImportBundle",
        entry: "DynamicModelImportEntry",
) -> DynamicModelImportTargetDomain:
    """
    Infer the target domain once for an entire DGS composite hierarchy.

    PowerFactory child ``ElmDsl`` occurrences do not independently declare the
    simulation domain.  Their use domain comes from the owning composite frame,
    so every entry with the same root FID must receive one coherent target.

    :param bundle: Bundle containing the complete source hierarchy.
    :param entry: Entry whose owning hierarchy is being classified.
    :return: Coherent RMS or EMT catalogue target for the hierarchy.
    """
    target_domain: DynamicModelImportTargetDomain = guess_dynamic_model_import_default_target_domain(entry)
    source_context: DynamicModelImportSourceContext | None = entry.get_source_context()
    candidate_entry: DynamicModelImportEntry
    candidate_context: DynamicModelImportSourceContext | None
    candidate_domain: DynamicModelImportTargetDomain
    candidate_source_class: str | None
    rms_equipment_classes: Set[str] = set([
        "ElmVsc",
        "ElmVscmono",
        "ElmSym",
        "ElmGenstat",
        "ElmSvs",
        "ElmXnet",
    ])

    if entry.get_source_tpe() != DynamicModelImportSource.PowerFactoryDgs or source_context is None:
        pass
    else:
        # Any explicit RMS evidence in the root/frame subtree governs every
        # occurrence.  The existing EMT value remains the conservative storage
        # fallback only when the DGS hierarchy carries no RMS evidence.
        for candidate_entry in bundle.get_entries():
            candidate_context = candidate_entry.get_source_context()
            if candidate_context is None:
                pass
            else:
                if candidate_context.get_root_dgs_id() != source_context.get_root_dgs_id():
                    pass
                else:
                    candidate_source_class = (
                        candidate_context.get_source_element_class()
                    )
                    candidate_domain = guess_dynamic_model_import_default_target_domain(candidate_entry)
                    if (
                            candidate_domain == DynamicModelImportTargetDomain.Rms
                            or candidate_source_class in rms_equipment_classes
                    ):
                        # Native RMS equipment slots determine the use domain
                        # even when a controller's display name contains no
                        # ``RMS`` token. The physical class is exported in the
                        # DGS and therefore requires no licensed API inference.
                        target_domain = DynamicModelImportTargetDomain.Rms
                    else:
                        pass

    return target_domain


def guess_dynamic_model_import_default_device_tpe(entry: "DynamicModelImportEntry") -> DeviceType:
    """
    Return the conservative non-physical classification for an imported entry.

    DGS ``ElmComp.pelm`` values describe slot occupancy and do not prove that a
    composite root is the active RMS or EMT model of one physical device. Composite
    ``ElmComp`` entries use VeraGrid's non-physical dynamic-host catalogue tag;
    standalone DSL blocks keep ``NoDevice``.

    :param entry: Imported entry.
    :return: Default device type guess.
    """
    persistence_spec: DynamicModelPersistenceSpec | None = entry.get_persistence_spec()
    source_context: DynamicModelImportSourceContext | None = entry.get_source_context()
    is_root_composite: bool = (
        persistence_spec is not None and
        persistence_spec.get_kind() == DynamicModelPersistenceKind.DgsRootElmComp
    )
    is_nested_composite: bool = (
        source_context is not None and
        source_context.get_source_element_class() == "ElmComp"
    )

    if is_root_composite or is_nested_composite:
        device_tpe: DeviceType = DeviceType.DynamicModelHostDevice
    else:
        device_tpe = DeviceType.NoDevice

    return device_tpe


def get_dgs_dynamic_host_device_tpe(source_element_class: str | None) -> DeviceType | None:
    """
    Map one authoritative PowerFactory host class to a VeraGrid device type.

    Auxiliary composite references such as ``StaSwitch`` and ``ElmSind`` are
    intentionally absent. They provide controller inputs or switching actions,
    but they do not identify the physical device that owns the composite model.

    :param source_element_class: Referenced DGS ``pElm`` class.
    :return: Compatible VeraGrid device type or ``None`` for non-host classes.
    """
    result: DeviceType | None

    if source_element_class in {"ElmVsc", "ElmVscmono"}:
        result = DeviceType.VscDevice
    else:
        if source_element_class == "ElmSvs":
            result = DeviceType.ControllableShuntDevice
        else:
            if source_element_class == "ElmSym":
                result = DeviceType.GeneratorDevice
            else:
                if source_element_class == "ElmGenstat":
                    # A composite-controlled ElmGenstat is a dynamic current
                    # injection. The static importer materializes that contract
                    # as Generator (or its Battery subclass), not as a fixed-PQ
                    # StaticGenerator.
                    result = DeviceType.GeneratorDevice
                else:
                    if source_element_class in {"ElmLod", "ElmLodlv", "ElmLodmv"}:
                        result = DeviceType.LoadDevice
                    else:
                        if source_element_class == "ElmBat":
                            result = DeviceType.BatteryDevice
                        else:
                            if source_element_class == "ElmLne":
                                result = DeviceType.LineDevice
                            else:
                                if source_element_class == "ElmTr2":
                                    result = DeviceType.Transformer2WDevice
                                else:
                                    if source_element_class == "ElmXnet":
                                        # The normal DGS path materializes an
                                        # external grid as a dynamic Generator.
                                        result = DeviceType.GeneratorDevice
                                    else:
                                        result = None

    return result


def is_dgs_dynamic_template_runtime_assignable(
        template_obj: RmsModelTemplate | EmtModelTemplate,
        device_tpe: DeviceType,
) -> bool:
    """
    Check that an imported root exposes a complete VeraGrid runtime contract.

    Exact DGS ownership does not imply that the symbolic root includes the
    built-in PowerFactory equipment equations. Promotion therefore requires the
    external power-flow outputs and bus-facing inputs consumed by VeraGrid's
    device compiler. Unsupported families remain catalogue-only until their
    typed adapters are implemented and validated.

    :param template_obj: Materialized external root template.
    :param device_tpe: Exact physical host type inferred from DGS.
    :return: ``True`` only for a complete supported runtime interface.
    """
    block: Block = template_obj.block
    mapping_refs: Set[VarPowerFlowReferenceType] = set(block.external_mapping)
    input_refs: Set[VarPowerFlowReferenceType] = set()
    input_var: Var

    for input_var in block.in_vars:
        if isinstance(input_var.ref, VarPowerFlowReferenceType):
            input_refs.add(input_var.ref)
        else:
            pass

    if device_tpe == DeviceType.VscDevice:
        required_mapping_refs: Set[VarPowerFlowReferenceType] = set([
            VarPowerFlowReferenceType.Pf,
            VarPowerFlowReferenceType.Pt,
            VarPowerFlowReferenceType.Qt,
        ])
        if block.__dict__.get("dgs_elmvscmono_runtime_adapter", None) is True:
            required_input_refs: Set[VarPowerFlowReferenceType] = set([
                VarPowerFlowReferenceType.Vf_dc,
                VarPowerFlowReferenceType.Vmt,
                VarPowerFlowReferenceType.Vat,
            ])
        else:
            required_input_refs = set([
                VarPowerFlowReferenceType.Vf_dc,
                VarPowerFlowReferenceType.Vt_dc,
                VarPowerFlowReferenceType.Vmt,
                VarPowerFlowReferenceType.Vat,
            ])
    else:
        if device_tpe == DeviceType.ControllableShuntDevice:
            required_mapping_refs = set([
                VarPowerFlowReferenceType.P,
                VarPowerFlowReferenceType.Q,
            ])
            required_input_refs = set([
                VarPowerFlowReferenceType.Vm,
                VarPowerFlowReferenceType.Va,
            ])
        else:
            if device_tpe == DeviceType.GeneratorDevice:
                required_mapping_refs = set([
                    VarPowerFlowReferenceType.P,
                    VarPowerFlowReferenceType.Q,
                ])
                required_input_refs = set([
                    VarPowerFlowReferenceType.Vm,
                    VarPowerFlowReferenceType.Va,
                ])
            else:
                required_mapping_refs = set()
                required_input_refs = set()

    if len(required_mapping_refs) == 0 or len(required_input_refs) == 0:
        result: bool = False
    else:
        result = (
            required_mapping_refs.issubset(mapping_refs)
            and required_input_refs.issubset(input_refs)
        )

    return result


def guess_dynamic_model_import_hierarchy_device_tpe(
        bundle: "DynamicModelImportBundle",
        entry: "DynamicModelImportEntry",
) -> DeviceType:
    """
    Infer one physical host type from an exact DGS composite hierarchy.

    A root becomes directly assignable only when all supported physical host
    relations reduce to one source FID and one compatible VeraGrid device type.
    Roots with several hosts remain generic catalogue objects because assigning
    a plant controller independently to every device would duplicate its states.

    :param bundle: Bundle containing the complete source hierarchy.
    :param entry: Entry whose owning hierarchy is being classified.
    :return: Physical device type or the conservative generic classification.
    """
    fallback_tpe: DeviceType = guess_dynamic_model_import_default_device_tpe(entry=entry)
    source_context: DynamicModelImportSourceContext | None = entry.get_source_context()
    persistence_spec: DynamicModelPersistenceSpec | None = entry.get_persistence_spec()
    is_root_composite: bool = (
        persistence_spec is not None
        and persistence_spec.get_kind() == DynamicModelPersistenceKind.DgsRootElmComp
    )
    host_identities: Set[Tuple[str, DeviceType]] = set()
    candidate_entry: DynamicModelImportEntry
    candidate_context: DynamicModelImportSourceContext | None
    candidate_class: str | None
    candidate_device_tpe: DeviceType | None
    candidate_element_id: str | None
    source_template: EmtModelTemplate | None = entry.get_template()

    if (
            entry.get_source_tpe() != DynamicModelImportSource.PowerFactoryDgs
            or source_context is None
            or not is_root_composite
    ):
        result: DeviceType = fallback_tpe
    else:
        # FID and class are the only admissible join keys. Display names remain
        # provenance and never participate in host inference.
        for candidate_entry in bundle.get_entries():
            candidate_context = candidate_entry.get_source_context()
            if candidate_context is None:
                pass
            else:
                if candidate_context.get_root_dgs_id() != source_context.get_root_dgs_id():
                    pass
                else:
                    candidate_class = candidate_context.get_source_element_class()
                    candidate_device_tpe = get_dgs_dynamic_host_device_tpe(
                        source_element_class=candidate_class,
                    )
                    candidate_element_id = candidate_context.get_source_element_dgs_id()
                    if candidate_device_tpe is None or candidate_element_id is None:
                        pass
                    else:
                        host_identities.add((candidate_element_id, candidate_device_tpe))

        if len(host_identities) == 1:
            host_identity: Tuple[str, DeviceType] = next(iter(host_identities))
            if source_template is None:
                result = fallback_tpe
            else:
                runtime_contract_ready: bool = is_dgs_dynamic_template_runtime_assignable(
                    template_obj=source_template,
                    device_tpe=host_identity[1],
                )
                elmvsc_adapter_supported: bool = (
                    host_identity[1] == DeviceType.VscDevice
                    and (
                        is_dgs_elmvsc_slot_contract(source_template.block)
                        or is_dgs_elmvscmono_slot_contract(source_template.block)
                    )
                )
                elmsym_adapter_supported: bool = (
                    host_identity[1] == DeviceType.GeneratorDevice
                    and is_dgs_elmsym_slot_contract(source_template.block)
                )
                elmgenstat_adapter_supported: bool = (
                    host_identity[1] == DeviceType.GeneratorDevice
                    and is_dgs_elmgenstat_slot_contract(source_template.block)
                )
                elmsvs_adapter_supported: bool = (
                    host_identity[1] == DeviceType.ControllableShuntDevice
                    and is_dgs_elmsvs_slot_contract(source_template.block)
                )
                if (
                        runtime_contract_ready
                        or elmvsc_adapter_supported
                        or elmsym_adapter_supported
                        or elmgenstat_adapter_supported
                        or elmsvs_adapter_supported
                ):
                    result = host_identity[1]
                else:
                    result = fallback_tpe
        else:
            result = fallback_tpe

    return result


def _apply_composite_child_interface_if_missing(block: Block) -> None:
    """
    Synthesize one composite interface from child ports when the root lacks one.

    :param block: Candidate composite root block.
    :return: None.
    """
    input_vars_by_uid: Dict[int, Var] = dict()
    output_vars_by_uid: Dict[int, Var] = dict()
    child_block: Block
    input_var: Var
    output_var: Var

    if len(block.children) == 0:
        return
    else:
        pass

    if len(block.in_vars) > 0 or len(block.out_vars) > 0:
        return
    else:
        pass

    for child_block in block.children:
        # Preserve the child order so imported reusable-template ports stay stable.
        for input_var in child_block.in_vars:
            if input_var.uid in input_vars_by_uid:
                pass
            else:
                input_vars_by_uid[input_var.uid] = input_var

        for output_var in child_block.out_vars:
            if output_var.uid in output_vars_by_uid:
                pass
            else:
                output_vars_by_uid[output_var.uid] = output_var

    block.in_vars = list(input_vars_by_uid.values())
    block.out_vars = list(output_vars_by_uid.values())


def mark_imported_template_editor_only(block: Block) -> None:
    """
    Mark one imported reusable template block as editor-only.

    Imported control-code templates must remain available in the editor library and
    the template database, but they must not appear as assignable physical-device
    templates in the object properties table.

    :param block: Imported reusable template block.
    :return: None.
    """
    block.__dict__["imported_template_editor_only"] = True


def _clone_import_block(block: Block) -> Block:
    """
    Clone one imported symbolic block for one selected target template.

    :param block: Imported symbolic block.
    :return: Deep-copied block.
    """
    cloned_block: Block = copy.deepcopy(block)
    _apply_composite_child_interface_if_missing(cloned_block)
    return cloned_block


def _build_selected_template_from_import_entry(
        entry: DynamicModelImportEntry,
        selection_request: DynamicModelImportSelectionRequest,
        clone_source_block: bool = True,
) -> RmsModelTemplate | EmtModelTemplate | None:
    """
    Materialize one selected reusable template using the user import choices.

    :param entry: Imported entry.
    :param selection_request: Explicit user import request.
    :param clone_source_block: Clone the source block for reusable GUI bundles.
    :return: Materialized RMS or EMT reusable template, or ``None``.
    """
    source_template: EmtModelTemplate | None = entry.get_template()
    cloned_block: Block
    emt_template: EmtModelTemplate
    rms_template: RmsModelTemplate

    if source_template is None:
        return None
    else:
        pass

    if clone_source_block:
        cloned_block = _clone_import_block(source_template.block)
    else:
        # A normal massive DGS open owns an ephemeral bundle. Transfer its
        # symbolic block into the circuit wrapper instead of retaining a second
        # deep copy of every OEM model at peak memory.
        cloned_block = source_template.block
        _apply_composite_child_interface_if_missing(cloned_block)
    if selection_request.get_device_tpe() in {
        DeviceType.NoDevice,
        DeviceType.DynamicModelHostDevice,
    }:
        mark_imported_template_editor_only(cloned_block)
    else:
        # An exact one-host DGS composite is a real assignable device template,
        # so the ordinary GUI property selector must expose it.
        pass

    if selection_request.get_target_domain() == DynamicModelImportTargetDomain.Emt:
        emt_template = EmtModelTemplate(name=source_template.name)
        emt_template.tpe = selection_request.get_device_tpe()
        emt_template.block = cloned_block
        emt_template.name = source_template.name
        return emt_template
    else:
        if selection_request.get_target_domain() == DynamicModelImportTargetDomain.Rms:
            rms_template = RmsModelTemplate(name=source_template.name)
            rms_template.tpe = selection_request.get_device_tpe()
            rms_template.block = cloned_block
            if (
                    entry.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs
                    and selection_request.get_device_tpe() == DeviceType.VscDevice
                    and (
                        is_dgs_elmvsc_slot_contract(cloned_block)
                        or is_dgs_elmvscmono_slot_contract(cloned_block)
                    )
            ):
                if is_dgs_elmvscmono_slot_contract(cloned_block):
                    adapted_template: RmsModelTemplate | None = (
                        build_dgs_elmvscmono_rms_runtime_template(
                            control_template=rms_template,
                            clone_control_block=clone_source_block,
                        )
                    )
                else:
                    adapted_template = (
                        build_dgs_elmvsc_rms_runtime_template(
                            control_template=rms_template,
                            clone_control_block=clone_source_block,
                        )
                    )
                if adapted_template is None:
                    return rms_template
                else:
                    return adapted_template
            else:
                if (
                        entry.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs
                        and selection_request.get_device_tpe() == DeviceType.GeneratorDevice
                        and is_dgs_elmsym_slot_contract(cloned_block)
                ):
                    adapted_generator_template: RmsModelTemplate | None = (
                        build_dgs_elmsym_rms_runtime_template(
                            control_template=rms_template,
                            clone_control_block=clone_source_block,
                        )
                    )
                    if adapted_generator_template is None:
                        return rms_template
                    else:
                        return adapted_generator_template
                else:
                    if (
                            entry.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs
                            and selection_request.get_device_tpe() == DeviceType.GeneratorDevice
                            and is_dgs_elmgenstat_slot_contract(cloned_block)
                    ):
                        adapted_static_generator_template: RmsModelTemplate | None = (
                            build_dgs_elmgenstat_rms_runtime_template(
                                control_template=rms_template,
                                clone_control_block=clone_source_block,
                            )
                        )
                        if adapted_static_generator_template is None:
                            return rms_template
                        else:
                            return adapted_static_generator_template
                    else:
                        if (
                                entry.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs
                                and selection_request.get_device_tpe() == DeviceType.ControllableShuntDevice
                                and is_dgs_elmsvs_slot_contract(cloned_block)
                        ):
                            adapted_svs_template: RmsModelTemplate | None = (
                                build_dgs_elmsvs_rms_runtime_template(
                                    control_template=rms_template,
                                    clone_control_block=clone_source_block,
                                )
                            )
                            if adapted_svs_template is None:
                                return rms_template
                            else:
                                return adapted_svs_template
                        else:
                            return rms_template
        else:
            return None


def _build_default_import_selection_request(entry_key: str) -> DynamicModelImportSelectionRequest:
    """
    Build the backward-compatible default selection used by non-interactive callers.

    :param entry_key: Stable entry key.
    :return: Default import request.
    """
    return DynamicModelImportSelectionRequest(
        entry_key=entry_key,
        target_domain=DynamicModelImportTargetDomain.Emt,
        device_tpe=DeviceType.NoDevice,
    )


def _normalize_procedural_logic_runtime_variable_names(
        block: Block,
        runtime_suffix: str,
) -> None:
    """
    Normalize generated variable suffixes stored as procedural-logic strings.

    Procedural logic retains its output or target variable by name.  Those names
    must be normalized together with the symbolic :class:`Var` instances so the
    canonical emitter can still resolve the local variable after a persisted
    template has been materialized with a runtime suffix.

    :param block: Block whose complete child tree is normalized.
    :param runtime_suffix: Generated template suffix to remove.
    :return: None.
    """
    logic: ProceduralLogicBase
    child_block: Block

    for logic in block.procedural_logic:
        if isinstance(logic, ResetOnRisingEdgeLogic):
            old_target_name: str = logic.target_var_name
            if len(runtime_suffix) > 1 and old_target_name.endswith(runtime_suffix):
                new_target_name: str = old_target_name[:-len(runtime_suffix)]
                if logic.name == f"{old_target_name}_reset":
                    logic.name = f"{new_target_name}_reset"
                else:
                    pass
                logic.target_var_name = new_target_name
            else:
                pass
        else:
            if isinstance(
                    logic,
                    (
                        FixedSampleLogic,
                        SampledValueLogic,
                        FlipFlopLogic,
                        AnalogFlipFlopLogic,
                        PickupDropoffLogic,
                        TimeDelayLogic,
                        MovingAverageLogic,
                        GradientLimiterLogic,
                        HardSaturationLogic,
                    ),
            ):
                old_output_name: str = logic.output_var_name
                if len(runtime_suffix) > 1 and old_output_name.endswith(runtime_suffix):
                    new_output_name: str = old_output_name[:-len(runtime_suffix)]
                    if logic.name == old_output_name:
                        logic.name = new_output_name
                    else:
                        pass
                    logic.output_var_name = new_output_name
                else:
                    pass
            else:
                pass

    for child_block in block.children:
        _normalize_procedural_logic_runtime_variable_names(
            block=child_block,
            runtime_suffix=runtime_suffix,
        )


def _normalize_dynamic_import_runtime_variable_names(block: Block,
                                                     template_name: str) -> None:
    """
    Remove one generated runtime-template suffix from every symbolic variable.

    Persisted template modules append ``_<template name>`` when allocating
    variables in a :class:`VarFactory`.  The suffix prevents collisions at
    runtime but is not part of the model structure, so structural fingerprints
    must remove it before comparing a direct DGS block with a reloaded module.

    :param block: Persistable block copied for canonicalization.
    :param template_name: Runtime template name whose suffix is normalized.
    :return: None.
    """
    variable_groups: _TemplateModuleVariableGroups = _build_template_module_variable_groups(block)
    variable_collections: List[List[Var]] = list()
    runtime_suffix: str = f"_{template_name}"
    variable_collection: List[Var]
    var_obj: Var
    variable_count: int = 0
    every_variable_has_runtime_suffix: bool = True

    # Keep the collections separate so the variable groups remain explicit and
    # no temporary concatenated list is allocated for this normalization pass.
    variable_collections.append(variable_groups.param_vars)
    variable_collections.append(variable_groups.state_vars)
    variable_collections.append(variable_groups.algebraic_vars)
    variable_collections.append(variable_groups.diff_vars)

    # Direct DGS variables may naturally end with the template name, for
    # example parameter ``K__K`` in template ``K``.  A loaded canonical Python
    # module is distinguishable because the emitter appends the runtime suffix
    # to every allocated variable.  Normalize only that complete surface so a
    # coincidental source suffix is never truncated.
    for variable_collection in variable_collections:
        for var_obj in variable_collection:
            variable_count += 1
            if len(runtime_suffix) > 1 and var_obj.name.endswith(runtime_suffix):
                pass
            else:
                every_variable_has_runtime_suffix = False

    should_normalize_runtime_suffix: bool = (
        variable_count > 0 and every_variable_has_runtime_suffix
    )
    if should_normalize_runtime_suffix:
        # Procedural records store variable names as strings, so normalize
        # those records before the referenced variables lose their suffix.
        _normalize_procedural_logic_runtime_variable_names(
            block=block,
            runtime_suffix=runtime_suffix,
        )
    else:
        return

    for variable_collection in variable_collections:
        for var_obj in variable_collection:
            if len(runtime_suffix) > 1 and var_obj.name.endswith(runtime_suffix):
                var_obj.name = var_obj.name[:-len(runtime_suffix)]
            else:
                pass


def build_dynamic_import_template_canonical_text(
        template_obj: RmsModelTemplate | EmtModelTemplate,
        logger: Logger | None = None,
) -> str | None:
    """
    Build deterministic canonical Python for one reusable template.

    The same readable Python emitter used by persisted user templates is also a
    useful canonical representation once the root name is neutralized.  Exposing
    the canonical text lets validators report exact roundtrip differences instead
    of reducing every mismatch immediately to a digest.

    :param template_obj: Materialized reusable template.
    :param logger: Optional diagnostics sink for canonicalization failures.
    :return: Canonical Python module text, or ``None`` when canonicalization fails.
    """
    fingerprint_block: Block
    target_domain: DynamicModelImportTargetDomain
    module_text: str
    can_use_read_only_block: bool

    try:
        # Use the same canonical block surface that is written to the user
        # catalogue. Imported editor-only interface nodes are intentionally
        # omitted because the generated module recreates the semantic model,
        # not those transient visual helpers.
        can_use_read_only_block = (
            _can_build_dynamic_import_canonical_text_read_only(
                block=template_obj.block,
                template_name=template_obj.name,
            )
        )
        if can_use_read_only_block:
            # DGS materialization has already deep-copied and consolidated this
            # block. A shallow root copy lets canonicalization neutralize only
            # the root name while every large immutable symbolic collection is
            # shared read-only during Python source emission.
            fingerprint_block = copy.copy(template_obj.block)
        else:
            fingerprint_block = build_user_dynamic_template_persistable_block(
                template_obj.block
            )
            _normalize_dynamic_import_runtime_variable_names(
                block=fingerprint_block,
                template_name=template_obj.name,
            )
        fingerprint_block.name = "__veragrid_dynamic_template_root__"

        if isinstance(template_obj, RmsModelTemplate):
            target_domain = DynamicModelImportTargetDomain.Rms
        else:
            target_domain = DynamicModelImportTargetDomain.Emt

        module_text = _build_user_dynamic_template_module_text(
            block=fingerprint_block,
            template_name="__veragrid_dynamic_template__",
            target_domain=target_domain,
            device_tpe=template_obj.tpe,
        )
    except Exception as err:
        if logger is None:
            pass
        else:
            logger.add_error(
                msg="Dynamic template canonicalization failed",
                value=f"{template_obj.name}: {err}",
            )
        return None

    return module_text


def _can_build_dynamic_import_canonical_text_read_only(
        block: Block,
        template_name: str,
) -> bool:
    """Return whether canonical Python can read the materialized block directly.

    The fallback remains mandatory for editor wrapper nodes, incomplete legacy
    composite interfaces, and templates loaded from canonical Python whose
    runtime suffix must be stripped from every variable. Direct DGS templates
    already satisfy those transformations during materialization and therefore
    need no second recursive clone.

    :param block: Materialized reusable-template block.
    :type block: Block
    :param template_name: Runtime template name used by suffix detection.
    :type template_name: str
    :return: ``True`` when Python source emission is strictly read-only.
    :rtype: bool
    """
    node_data: object
    has_editor_interface_wrapper: bool = False
    variable_groups: _TemplateModuleVariableGroups
    variable_collections: List[List[Var]] = list()
    variable_collection: List[Var]
    variable: Var
    runtime_suffix: str = f"_{template_name}"
    variable_count: int = 0
    every_variable_has_runtime_suffix: bool = True

    # Persisted catalogues deliberately remove lateral GUI connection blocks.
    for node_data in block.diagram.node_data.values():
        if (
                node_data.tpe == BlockType.INPUT_CONN.name
                or node_data.tpe == BlockType.OUTPUT_CONN.name
        ):
            has_editor_interface_wrapper = True
        else:
            pass

    has_incomplete_composite_interface: bool = bool(
        len(block.children) > 0
        and len(block.in_vars) == 0
        and len(block.out_vars) == 0
    )

    # A module loaded from disk carries the runtime template suffix on every
    # allocated variable. It must retain the established normalized deep-copy
    # path because variable names are shared throughout the expression graph.
    variable_groups = _build_template_module_variable_groups(block)
    variable_collections.append(variable_groups.param_vars)
    variable_collections.append(variable_groups.state_vars)
    variable_collections.append(variable_groups.algebraic_vars)
    variable_collections.append(variable_groups.diff_vars)
    for variable_collection in variable_collections:
        for variable in variable_collection:
            variable_count += 1
            if len(runtime_suffix) > 1 and variable.name.endswith(runtime_suffix):
                pass
            else:
                every_variable_has_runtime_suffix = False

    requires_runtime_suffix_normalization: bool = bool(
        variable_count > 0 and every_variable_has_runtime_suffix
    )
    return not bool(
        has_editor_interface_wrapper
        or has_incomplete_composite_interface
        or requires_runtime_suffix_normalization
    )


def build_dynamic_import_template_fingerprint(
        template_obj: RmsModelTemplate | EmtModelTemplate,
) -> str | None:
    """
    Build a deterministic structural fingerprint for one reusable template.

    :param template_obj: Materialized reusable template.
    :return: SHA-256 fingerprint, or ``None`` when canonicalization fails.
    """
    module_text: str | None = build_dynamic_import_template_canonical_text(
        template_obj=template_obj,
        logger=None,
    )

    if module_text is None:
        return None
    else:
        return hashlib.sha256(module_text.encode("utf-8")).hexdigest()


def _build_contextual_dynamic_import_template_name(
        entry: DynamicModelImportEntry,
        existing_names: Set[str],
) -> str:
    """
    Build a readable unique name for a non-equivalent name collision.

    :param entry: Imported entry whose display name already exists.
    :param existing_names: Names already present in the target domain.
    :return: Unique human-readable template name.
    """
    base_name: str = entry.get_display_name()
    key_parts: List[str] = entry.get_unique_key().split("|")
    source_context: DynamicModelImportSourceContext | None = entry.get_source_context()
    context_label: str = "imported variant"
    candidate_name: str
    suffix_index: int = 2

    if source_context is None:
        if len(key_parts) >= 3 and key_parts[0] == "dgs-slot":
            context_label = "child slot"
        else:
            if len(key_parts) >= 2 and key_parts[0].startswith("dgs-"):
                context_label = "DGS variant"
            else:
                pass
    else:
        # Stable FIDs belong in metadata; collision names remain readable by
        # presenting the exported root/slot labels to humans.
        if source_context.get_root_name().casefold() == base_name.casefold():
            if source_context.get_slot_name() is None:
                context_label = "root variant"
            else:
                context_label = source_context.get_slot_name()
        else:
            context_label = source_context.get_root_name()

    candidate_name = f"{base_name} [{context_label}]"
    while candidate_name in existing_names:
        candidate_name = f"{base_name} [{context_label} {suffix_index}]"
        suffix_index += 1

    return candidate_name


def _append_dynamic_model_import_entry_result(
        report: DynamicModelImportReport | None,
        entry: DynamicModelImportEntry,
        selection_request: DynamicModelImportSelectionRequest,
        final_name: str | None,
        status: DynamicModelImportEntryStatus,
        message: str,
) -> DynamicModelImportEntryResult | None:
    """
    Append one structured result when the caller requested reporting.

    :param report: Optional aggregate report.
    :param entry: Processed source catalogue entry.
    :param selection_request: Explicit target-domain selection.
    :param final_name: Final circuit template name, when available.
    :param status: Explicit processing status.
    :param message: Human-readable outcome diagnostic.
    :return: Appended result or ``None`` when reporting is disabled.
    """
    if report is None:
        entry_result: DynamicModelImportEntryResult | None = None
    else:
        entry_result = DynamicModelImportEntryResult(
            unique_key=entry.get_unique_key(),
            requested_name=entry.get_display_name(),
            final_name=final_name,
            domain=selection_request.get_target_domain(),
            status=status,
            source_context=entry.get_source_context(),
            message=message,
        )
        report.add_entry_result(entry_result=entry_result)

    return entry_result


def build_dgs_dynamic_association_records(
        report: DynamicModelImportReport,
) -> List[DgsDynamicAssociationRecord]:
    """
    Build the source association records from one DGS import.

    The records preserve the DGS composite hierarchy and final catalogue
    identity without activating a runtime dynamic model during file import.

    :param report: Completed massive-import report.
    :return: Ordered source association records.
    """
    records: List[DgsDynamicAssociationRecord] = list()
    root_template_name_by_dgs_id: Dict[str, str] = dict()
    entry_result: DynamicModelImportEntryResult
    source_context: DynamicModelImportSourceContext | None
    final_template_name: str | None

    # Resolve the reusable composite template once per exact ElmComp FID.  The
    # root result and its physical pElm slot results are deliberately separate
    # catalogue entries, so this first pass provides the safe join key between
    # them without relying on display names.
    for entry_result in report.get_entry_results():
        source_context = entry_result.get_source_context()
        final_template_name = entry_result.get_final_name()
        is_root_result: bool = (
            source_context is not None
            and source_context.get_slot_index() is None
            and final_template_name is not None
        )
        if is_root_result and source_context is not None and final_template_name is not None:
            root_template_name_by_dgs_id[source_context.get_root_dgs_id()] = final_template_name
        else:
            pass

    for entry_result in report.get_entry_results():
        source_context = entry_result.get_source_context()
        if source_context is None:
            pass
        else:
            final_template_name = entry_result.get_final_name()
            source_element_class: str | None = source_context.get_source_element_class()
            is_physical_root_slot: bool = (
                source_context.get_slot_index() is not None
                and source_element_class is not None
                and source_element_class not in {"ElmDsl", "ElmComp"}
            )
            if final_template_name is None and is_physical_root_slot:
                # A physical pElm is context rather than a reusable template.
                # Carry the owning root-template identity onto its association
                # record so consumers can answer which composite controls the
                # exact equipment FID while keeping activation as a distinct,
                # explicitly validated runtime step.
                final_template_name = root_template_name_by_dgs_id.get(
                    source_context.get_root_dgs_id(),
                    None,
                )
            else:
                pass
            records.append(
                DgsDynamicAssociationRecord(
                    unique_key=entry_result.get_unique_key(),
                    root_dgs_id=source_context.get_root_dgs_id(),
                    root_name=source_context.get_root_name(),
                    root_typ_id=source_context.get_root_typ_id(),
                    slot_dgs_id=source_context.get_slot_dgs_id(),
                    slot_name=source_context.get_slot_name(),
                    slot_index=source_context.get_slot_index(),
                    slot_element=source_context.get_slot_element(),
                    slot_filter=source_context.get_slot_filter(),
                    source_element_dgs_id=source_context.get_source_element_dgs_id(),
                    source_element_name=source_context.get_source_element_name(),
                    source_element_class=source_context.get_source_element_class(),
                    final_template_name=final_template_name,
                    role=infer_dgs_dynamic_association_role(
                        slot_index=source_context.get_slot_index(),
                        source_element_class=source_context.get_source_element_class(),
                        slot_filter=source_context.get_slot_filter(),
                    ),
                    target_domain=entry_result.get_domain(),
                    status=entry_result.get_status(),
                )
            )

    return records


def add_dynamic_import_selection_requests_to_circuit(
        circuit: MultiCircuit,
        bundle: DynamicModelImportBundle,
        selection_requests: Sequence[DynamicModelImportSelectionRequest],
        logger: Logger,
        progress_callback: Callable[[int, str], None] | None = None,
        user_root_folder: str | None = None,
        rename_conflicting_templates: bool = False,
        persist_to_user_catalog: bool = False,
        report: DynamicModelImportReport | None = None,
        template_fingerprint_by_object_id: Dict[int, str | None] | None = None,
        clone_source_blocks: bool = True,
) -> int:
    """
    Add the selected imported dynamic models to the circuit using explicit metadata.

    :param circuit: Target circuit.
    :param bundle: Imported dynamic-model bundle.
    :param selection_requests: Explicit selected import requests.
    :param logger: Logger receiving duplicate or importability diagnostics.
    :param progress_callback: Optional UI progress callback.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :param rename_conflicting_templates: Rename non-equivalent name collisions instead of dropping them.
    :param persist_to_user_catalog: Persist successfully added templates as readable Python modules.
    :param report: Optional structured outcome report populated entry by entry.
    :param template_fingerprint_by_object_id: Optional identity cache shared
        with deferred DGS persistence.
    :param clone_source_blocks: Clone bundle blocks before installation. Disable
        only when the caller owns and consumes one ephemeral massive bundle.
    :return: Number of templates added to the circuit.
    """
    request_by_entry_key: Dict[str, DynamicModelImportSelectionRequest] = dict()
    existing_rms_names: Set[str] = set()
    existing_emt_names: Set[str] = set()
    existing_rms_templates_by_fingerprint: Dict[str, RmsModelTemplate] = dict()
    existing_emt_templates_by_fingerprint: Dict[str, EmtModelTemplate] = dict()
    persistable_work_list: List[SelectedDynamicImportWork] = list()
    processed_entry_keys: Set[str] = set()
    entry: DynamicModelImportEntry
    selection_request: DynamicModelImportSelectionRequest
    template_obj: RmsModelTemplate | EmtModelTemplate | None
    total_selected_count: int
    processed_selected_count: int = 0
    entry_result: DynamicModelImportEntryResult | None
    template_deduplicated: bool
    template_renamed: bool
    outcome_message: str
    fingerprint_cache: Dict[int, str | None]

    if template_fingerprint_by_object_id is None:
        fingerprint_cache = dict()
    else:
        fingerprint_cache = template_fingerprint_by_object_id

    for selection_request in selection_requests:
        entry_key: str = selection_request.get_entry_key()
        if entry_key in request_by_entry_key:
            logger.add_info(
                msg="Duplicate dynamic model selection ignored",
                value=entry_key,
            )
        else:
            request_by_entry_key[entry_key] = selection_request

    total_selected_count = len(request_by_entry_key)

    for template in circuit.rms_models:
        existing_rms_names.add(template.name)
        template_fingerprint: str | None = build_dynamic_import_template_fingerprint(template)
        fingerprint_cache[id(template)] = template_fingerprint
        if template_fingerprint is not None:
            existing_rms_templates_by_fingerprint[template_fingerprint] = template
        else:
            pass

    for template in circuit.emt_models:
        existing_emt_names.add(template.name)
        template_fingerprint = build_dynamic_import_template_fingerprint(template)
        fingerprint_cache[id(template)] = template_fingerprint
        if template_fingerprint is not None:
            existing_emt_templates_by_fingerprint[template_fingerprint] = template
        else:
            pass

    added_count: int = 0

    for entry in bundle.get_entries():
        entry.set_installed_template(None)
        selection_request = request_by_entry_key.get(entry.get_unique_key(), None)

        if selection_request is None or entry.get_unique_key() in processed_entry_keys:
            if selection_request is None:
                pass
            else:
                logger.add_info(
                    msg="Duplicate dynamic model catalogue entry ignored",
                    value=entry.get_unique_key(),
                )
                _append_dynamic_model_import_entry_result(
                    report=report,
                    entry=entry,
                    selection_request=selection_request,
                    final_name=None,
                    status=DynamicModelImportEntryStatus.Skipped,
                    message="Duplicate catalogue entry key ignored",
                )
        else:
            processed_entry_keys.add(entry.get_unique_key())

            processed_selected_count += 1
            if total_selected_count == 0:
                pass
            else:
                _emit_dynamic_model_import_progress(
                    progress_callback,
                    int(round(60.0 * float(processed_selected_count - 1) / float(total_selected_count))),
                    f"Adding selected dynamic models: {processed_selected_count}/{total_selected_count}",
                )

            outcome_message = ""
            try:
                template_obj = _build_selected_template_from_import_entry(
                    entry=entry,
                    selection_request=selection_request,
                    clone_source_block=clone_source_blocks,
                )
            except Exception as exc:
                template_obj = None
                outcome_message = str(exc)
                logger.add_warning(
                    msg="Dynamic model entry skipped after a materialization error",
                    value=f"{entry.get_display_name()}: {exc}",
                )

            if template_obj is None:
                logger.add_warning(msg="Dynamic model entry skipped because it is not importable", value=entry.get_display_name())
                if len(outcome_message) == 0:
                    outcome_message = "Source entry is not importable"
                else:
                    pass
                _append_dynamic_model_import_entry_result(
                    report=report,
                    entry=entry,
                    selection_request=selection_request,
                    final_name=None,
                    status=DynamicModelImportEntryStatus.Failed,
                    message=outcome_message,
                )
            else:
                template_added: bool = False
                template_deduplicated = False
                template_renamed = False
                outcome_message = "Template name already exists"
                template_fingerprint: str | None = build_dynamic_import_template_fingerprint(template_obj)
                fingerprint_cache[id(template_obj)] = template_fingerprint
                if isinstance(template_obj, RmsModelTemplate):
                    equivalent_rms_template: RmsModelTemplate | None = None
                    if template_fingerprint is None:
                        pass
                    else:
                        equivalent_rms_template = existing_rms_templates_by_fingerprint.get(
                            template_fingerprint,
                            None,
                        )

                    if rename_conflicting_templates and equivalent_rms_template is not None:
                        logger.add_info(
                            msg="Equivalent dynamic model entry deduplicated",
                            value=f"{template_obj.name} -> {equivalent_rms_template.name}",
                        )
                        entry.set_installed_template(equivalent_rms_template)
                        template_deduplicated = True
                        outcome_message = "Equivalent template reused by structural fingerprint"
                    else:
                        if template_obj.name in existing_rms_names:
                            if rename_conflicting_templates:
                                original_name: str = template_obj.name
                                template_obj.name = _build_contextual_dynamic_import_template_name(
                                    entry=entry,
                                    existing_names=existing_rms_names,
                                )
                                template_obj.block.name = template_obj.name
                                logger.add_info(
                                    msg="Dynamic model name collision renamed",
                                    value=f"{original_name} -> {template_obj.name}",
                                )
                                circuit.add_rms_model(template_obj)
                                existing_rms_names.add(template_obj.name)
                                template_added = True
                                template_renamed = True
                                outcome_message = f"Name collision renamed to {template_obj.name}"
                            else:
                                logger.add_warning(msg="Dynamic model entry skipped because the template name already exists", value=template_obj.name)
                        else:
                            circuit.add_rms_model(template_obj)
                            existing_rms_names.add(template_obj.name)
                            template_added = True
                            outcome_message = "Template added"

                    if template_added and template_fingerprint is not None:
                        existing_rms_templates_by_fingerprint[template_fingerprint] = template_obj
                    else:
                        pass
                else:
                    if isinstance(template_obj, EmtModelTemplate):
                        equivalent_emt_template: EmtModelTemplate | None = None
                        if template_fingerprint is None:
                            pass
                        else:
                            equivalent_emt_template = existing_emt_templates_by_fingerprint.get(
                                template_fingerprint,
                                None,
                            )

                        if rename_conflicting_templates and equivalent_emt_template is not None:
                            logger.add_info(
                                msg="Equivalent dynamic model entry deduplicated",
                                value=f"{template_obj.name} -> {equivalent_emt_template.name}",
                            )
                            entry.set_installed_template(equivalent_emt_template)
                            template_deduplicated = True
                            outcome_message = "Equivalent template reused by structural fingerprint"
                        else:
                            if template_obj.name in existing_emt_names:
                                if rename_conflicting_templates:
                                    original_name = template_obj.name
                                    template_obj.name = _build_contextual_dynamic_import_template_name(
                                        entry=entry,
                                        existing_names=existing_emt_names,
                                    )
                                    template_obj.block.name = template_obj.name
                                    logger.add_info(
                                        msg="Dynamic model name collision renamed",
                                        value=f"{original_name} -> {template_obj.name}",
                                    )
                                    circuit.add_emt_model(template_obj)
                                    existing_emt_names.add(template_obj.name)
                                    template_added = True
                                    template_renamed = True
                                    outcome_message = f"Name collision renamed to {template_obj.name}"
                                else:
                                    logger.add_warning(msg="Dynamic model entry skipped because the template name already exists", value=template_obj.name)
                            else:
                                circuit.add_emt_model(template_obj)
                                existing_emt_names.add(template_obj.name)
                                template_added = True
                                outcome_message = "Template added"

                        if template_added and template_fingerprint is not None:
                            existing_emt_templates_by_fingerprint[template_fingerprint] = template_obj
                        else:
                            pass
                    else:
                        outcome_message = "Materialized object has an unsupported template type"

                if template_added:
                    entry.set_installed_template(template_obj)
                    added_count += 1
                    if template_renamed:
                        entry_status: DynamicModelImportEntryStatus = DynamicModelImportEntryStatus.Renamed
                    else:
                        entry_status = DynamicModelImportEntryStatus.Added
                    entry_result = _append_dynamic_model_import_entry_result(
                        report=report,
                        entry=entry,
                        selection_request=selection_request,
                        final_name=template_obj.name,
                        status=entry_status,
                        message=outcome_message,
                    )
                    if persist_to_user_catalog:
                        persistable_work_list.append(
                            SelectedDynamicImportWork(
                                selection_request=selection_request,
                                template_obj=template_obj,
                                entry_result=entry_result,
                                template_fingerprint=template_fingerprint,
                                # A massive DGS import can contain thousands of
                                # parameterized variants. Its human-readable
                                # Python module is canonical and syntax-checked;
                                # duplicating the complete graph as JSON would
                                # multiply disk and cold-import cost without
                                # adding runtime information.
                                include_validation_snapshot=(
                                    entry.get_source_tpe()
                                    is not DynamicModelImportSource.PowerFactoryDgs
                                ),
                            )
                        )
                    else:
                        pass
                else:
                    if template_deduplicated:
                        deduplicated_template: RmsModelTemplate | EmtModelTemplate | None = (
                            entry.get_installed_template()
                        )
                        if deduplicated_template is None:
                            final_name: str | None = template_obj.name
                        else:
                            final_name = deduplicated_template.name
                        _append_dynamic_model_import_entry_result(
                            report=report,
                            entry=entry,
                            selection_request=selection_request,
                            final_name=final_name,
                            status=DynamicModelImportEntryStatus.Deduplicated,
                            message=outcome_message,
                        )
                    else:
                        _append_dynamic_model_import_entry_result(
                            report=report,
                            entry=entry,
                            selection_request=selection_request,
                            final_name=None,
                            status=DynamicModelImportEntryStatus.Skipped,
                            message=outcome_message,
                        )

            if total_selected_count == 0:
                pass
            else:
                _emit_dynamic_model_import_progress(
                    progress_callback,
                    int(round(60.0 * float(processed_selected_count) / float(total_selected_count))),
                    f"Adding selected dynamic models: {processed_selected_count}/{total_selected_count}",
                )

    if len(persistable_work_list) > 0:
        _persist_selected_dynamic_import_work_list(
            persistable_work_list=persistable_work_list,
            logger=logger,
            progress_callback=progress_callback,
            user_root_folder=user_root_folder,
        )
    else:
        pass

    _emit_dynamic_model_import_progress(progress_callback, 100, "Selected dynamic models imported")

    return added_count


def _find_exact_dgs_dynamic_host_devices(
        circuit: MultiCircuit,
        source_element_dgs_id: str,
        device_tpe: DeviceType,
        source_element_class: str | None,
) -> List[DynamicDevice]:
    """
    Find dynamic-capable devices by exact imported DGS FID and device type.

    Parallel-device suffixes are not expanded here. One PowerFactory composite
    does not define whether its states should be duplicated across VeraGrid
    parallel expansions, so such cases must remain unresolved and inspectable.

    :param circuit: Imported VeraGrid circuit.
    :param source_element_dgs_id: Authoritative source equipment FID.
    :param device_tpe: Expected VeraGrid host type.
    :param source_element_class: Authoritative PowerFactory equipment class.
    :return: Exact compatible dynamic devices.
    """
    matches: List[DynamicDevice] = list()
    candidate_obj: object
    candidate_device_types: List[DeviceType] = list([device_tpe])

    # Batteries inherit the Generator RMS contract but live in a separate
    # circuit collection. PowerFactory exports both wind/HVDC sources and
    # storage through ElmGenstat, so exact FID resolution must inspect both
    # compatible VeraGrid collections without relying on display categories.
    if (
            source_element_class == "ElmGenstat"
            and DeviceType.BatteryDevice not in candidate_device_types
    ):
        candidate_device_types.append(DeviceType.BatteryDevice)
    else:
        pass

    candidate_device_type: DeviceType
    for candidate_device_type in candidate_device_types:
        for candidate_obj in circuit.get_elements_by_type(
                device_type=candidate_device_type,
        ):
            if isinstance(candidate_obj, DynamicDevice):
                if candidate_obj.idtag == source_element_dgs_id:
                    matches.append(candidate_obj)
                else:
                    pass
            else:
                pass
        else:
            pass
    else:
        pass

    return matches


def _find_dgs_dynamic_activation_template(
        circuit: MultiCircuit,
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
) -> RmsModelTemplate | EmtModelTemplate | None:
    """
    Resolve one unique installed template by exact final name and domain.

    :param circuit: Circuit containing the imported reusable catalogue.
    :param template_name: Collision-resolved final template name.
    :param target_domain: RMS or EMT target domain retained by the association.
    :return: Unique template or ``None`` when missing or ambiguous.
    """
    matching_templates: List[RmsModelTemplate | EmtModelTemplate] = list()
    rms_template: RmsModelTemplate
    emt_template: EmtModelTemplate

    if target_domain == DynamicModelImportTargetDomain.Rms:
        for rms_template in circuit.rms_models:
            if rms_template.name == template_name:
                matching_templates.append(rms_template)
            else:
                pass
    else:
        for emt_template in circuit.emt_models:
            if emt_template.name == template_name:
                matching_templates.append(emt_template)
            else:
                pass

    if len(matching_templates) == 1:
        result: RmsModelTemplate | EmtModelTemplate | None = matching_templates[0]
    else:
        result = None

    return result


def _assign_dgs_dynamic_template_to_host(
        host_device: DynamicDevice,
        template_obj: RmsModelTemplate | EmtModelTemplate,
        activation_report: DgsDynamicModelActivationReport,
) -> None:
    """
    Assign one exact imported template without overwriting another controller.

    :param host_device: Exact physical host resolved by DGS FID.
    :param template_obj: Unique imported template.
    :param activation_report: Mutable structured outcome report.
    :return: None.
    """
    if isinstance(template_obj, RmsModelTemplate):
        current_template: RmsModelTemplate | EmtModelTemplate | None = host_device.rms_template
    else:
        current_template = host_device.emt_template

    if isinstance(template_obj, RmsModelTemplate):
        if current_template is template_obj:
            activation_report.record_already_active()
        else:
            if current_template is None:
                try:
                    host_device.rms_template = template_obj
                except (TypeError, ValueError, KeyError):
                    activation_report.record_failed()
                else:
                    activation_report.record_physical_activated()
            else:
                activation_report.record_conflict()
    else:
        if current_template is template_obj:
            activation_report.record_already_active()
        else:
            if current_template is None:
                try:
                    host_device.emt_template = template_obj
                except (TypeError, ValueError, KeyError):
                    activation_report.record_failed()
                else:
                    activation_report.record_physical_activated()
            else:
                activation_report.record_conflict()


def activate_unambiguous_dgs_dynamic_models_in_circuit(
        circuit: MultiCircuit,
        records: Sequence[DgsDynamicAssociationRecord],
        logger: Logger,
) -> DgsDynamicModelActivationReport:
    """
    Activate unambiguous DGS composite models on their exact physical hosts.

    A root is activated only when its supported host relations collapse to one
    ``(FID, device type)`` identity, that identity resolves to exactly one
    imported device and the final template name resolves uniquely. Auxiliary
    pElm references remain provenance and multi-host plant controllers remain
    explicit catalogue objects for a later user-directed composition workflow.

    :param circuit: Destination circuit with static devices and templates.
    :param records: Exact root-slot-pElm source associations.
    :param logger: Diagnostic sink for handled unresolved roots.
    :return: Structured activation report.
    """
    activation_report: DgsDynamicModelActivationReport = DgsDynamicModelActivationReport()
    records_by_root_id: Dict[str, List[DgsDynamicAssociationRecord]] = dict()
    record: DgsDynamicAssociationRecord
    root_records: List[DgsDynamicAssociationRecord]
    existing_root_records: List[DgsDynamicAssociationRecord] | None
    host_record_by_identity: Dict[Tuple[str, DeviceType], DgsDynamicAssociationRecord]
    source_element_id: str | None
    host_device_tpe: DeviceType | None
    host_identity: Tuple[str, DeviceType]
    host_record: DgsDynamicAssociationRecord
    template_name: str | None
    host_devices: List[DynamicDevice]
    template_obj: RmsModelTemplate | EmtModelTemplate | None

    # Group once by exact root FID so the ambiguity decision is linear in the
    # number of source associations even for large PowerFactory catalogues.
    for record in records:
        existing_root_records = records_by_root_id.get(record.get_root_dgs_id(), None)
        if existing_root_records is None:
            root_records = list()
            root_records.append(record)
            records_by_root_id[record.get_root_dgs_id()] = root_records
        else:
            existing_root_records.append(record)

    for root_records in records_by_root_id.values():
        host_record_by_identity = dict()
        for record in root_records:
            source_element_id = record.get_source_element_dgs_id()
            host_device_tpe = get_dgs_dynamic_host_device_tpe(
                source_element_class=record.get_source_element_class(),
            )
            template_name = record.get_final_template_name()
            if source_element_id is None or host_device_tpe is None or template_name is None:
                pass
            else:
                host_identity = source_element_id, host_device_tpe
                if host_identity in host_record_by_identity:
                    pass
                else:
                    host_record_by_identity[host_identity] = record

        if len(host_record_by_identity) == 0:
            # Roots without one exact physical host remain local catalogue
            # metadata. They are not promoted to global circuit devices.
            pass
        else:
            if len(host_record_by_identity) > 1:
                activation_report.record_ambiguous()
                logger.add_warning(
                    msg="DGS dynamic root retained without activation because it has several physical hosts",
                    value=root_records[0].get_root_name(),
                )
            else:
                host_identity = next(iter(host_record_by_identity))
                host_record = host_record_by_identity[host_identity]
                template_name = host_record.get_final_template_name()
                if template_name is None:
                    activation_report.record_unresolved()
                else:
                    host_devices = _find_exact_dgs_dynamic_host_devices(
                        circuit=circuit,
                        source_element_dgs_id=host_identity[0],
                        device_tpe=host_identity[1],
                        source_element_class=(
                            host_record.get_source_element_class()
                        ),
                    )
                    template_obj = _find_dgs_dynamic_activation_template(
                        circuit=circuit,
                        template_name=template_name,
                        target_domain=host_record.get_target_domain(),
                    )
                    adapter_configuration_ready: bool = True
                    if (
                            isinstance(template_obj, RmsModelTemplate)
                            and len(host_devices) == 1
                            and isinstance(host_devices[0], VSC)
                            and template_obj.block.__dict__.get(
                                "dgs_elmvscmono_runtime_adapter",
                                None,
                            ) is True
                    ):
                        # Monopolar bridges use the grounded return represented
                        # by their one exported DC terminal and native base.
                        adapter_configuration_ready = (
                            configure_dgs_elmvscmono_runtime_template_for_device(
                                template=template_obj,
                                device=host_devices[0],
                                system_base_mva=float(circuit.Sbase),
                            )
                        )
                    else:
                        if (
                            isinstance(template_obj, RmsModelTemplate)
                            and len(host_devices) == 1
                            and isinstance(host_devices[0], VSC)
                            and template_obj.block.__dict__.get(
                                "dgs_elmvsc_runtime_adapter",
                                None,
                            ) is True
                        ):
                            # Bipolar bridges use both exported pole bases.
                            adapter_configuration_ready = (
                                configure_dgs_elmvsc_runtime_template_for_device(
                                    template=template_obj,
                                    device=host_devices[0],
                                    system_base_mva=float(circuit.Sbase),
                                )
                            )
                        else:
                            if (
                                    isinstance(template_obj, RmsModelTemplate)
                                    and len(host_devices) == 1
                                    and isinstance(host_devices[0], Generator)
                                    and template_obj.block.__dict__.get(
                                        "dgs_elmsym_runtime_adapter_pending",
                                        None,
                                    ) is True
                            ):
                                # The exact TypSym selects salient or round
                                # rotor structure and supplies every physical
                                # parameter before the runtime contract check.
                                adapter_configuration_ready = (
                                    configure_dgs_elmsym_runtime_template_for_device(
                                        template=template_obj,
                                        device=host_devices[0],
                                        system_base_mva=float(circuit.Sbase),
                                    )
                                )
                            else:
                                pass
                    runtime_contract_ready: bool = (
                        template_obj is not None
                        and template_obj.tpe == host_identity[1]
                        and adapter_configuration_ready
                        and is_dgs_dynamic_template_runtime_assignable(
                            template_obj=template_obj,
                            device_tpe=host_identity[1],
                        )
                    )
                    if len(host_devices) != 1 or not runtime_contract_ready:
                        activation_report.record_unresolved()
                        logger.add_warning(
                            msg=(
                                "DGS dynamic host retained without activation because exact "
                                "resolution or its runtime adapter contract is incomplete"
                            ),
                            device=host_record.get_source_element_name(),
                            device_class=host_record.get_source_element_class(),
                            value=host_identity[0],
                        )
                    else:
                        if template_obj is None:
                            # The explicit runtime-contract condition above makes
                            # this branch unreachable, while the local guard keeps
                            # the type state evident for static analysis.
                            activation_report.record_unresolved()
                            pass
                        else:
                            _assign_dgs_dynamic_template_to_host(
                                host_device=host_devices[0],
                                template_obj=template_obj,
                                activation_report=activation_report,
                            )

    return activation_report


def add_all_dynamic_import_bundle_to_circuit_with_report(
        circuit: MultiCircuit,
        bundle: DynamicModelImportBundle,
        logger: Logger,
        progress_callback: Callable[[int, str], None] | None = None,
        user_root_folder: str | None = None,
        persist_to_user_catalog: bool = False,
        consume_bundle_templates: bool = False,
) -> DynamicModelImportReport:
    """
    Add every importable bundle entry to a circuit for non-interactive DGS loading.

    Structurally equivalent entries are deduplicated across names within the same
    target domain and device classification.  Same-name entries with a different
    symbolic structure receive a deterministic human-readable contextual name so
    the bulk path never discards a valid variant merely because another root
    exposed the same slot label.

    :param circuit: Target circuit.
    :param bundle: Parsed dynamic-model bundle.
    :param logger: Logger receiving partial-failure and deduplication diagnostics.
    :param progress_callback: Optional UI progress callback.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :param persist_to_user_catalog: Persist added models as readable Python user templates.
    :param consume_bundle_templates: Transfer source blocks from an ephemeral
        bundle to avoid a second massive symbolic graph in memory.
    :return: Structured massive-import report.
    """
    selection_requests: List[DynamicModelImportSelectionRequest] = list()
    selected_entry_keys: Set[str] = set()
    entry: DynamicModelImportEntry
    importable_count: int = 0
    selection_request: DynamicModelImportSelectionRequest
    entry_availability: DynamicModelImportEntryAvailability
    unavailable_status: DynamicModelImportEntryStatus
    unavailable_message: str
    defer_dgs_catalog_persistence: bool = (
        persist_to_user_catalog
        and bundle.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs
    )
    template_fingerprint_by_object_id: Dict[int, str | None] = dict()

    for entry in bundle.get_entries():
        if entry.is_importable():
            importable_count += 1
        else:
            pass

    report: DynamicModelImportReport = DynamicModelImportReport(
        discovered_count=len(bundle.get_entries()),
        importable_count=importable_count,
    )

    for entry in bundle.get_entries():
        if not entry.is_importable():
            entry_availability = entry.get_availability()
            if entry_availability == DynamicModelImportEntryAvailability.ContextOnly:
                unavailable_status = DynamicModelImportEntryStatus.Skipped
                unavailable_message = "Source hierarchy/association context retained without a reusable template"
            else:
                unavailable_status = DynamicModelImportEntryStatus.Failed
                unavailable_message = "Source entry could not be materialized"
            selection_request = DynamicModelImportSelectionRequest(
                entry_key=entry.get_unique_key(),
                target_domain=guess_dynamic_model_import_hierarchy_target_domain(bundle=bundle, entry=entry),
                device_tpe=guess_dynamic_model_import_hierarchy_device_tpe(bundle=bundle, entry=entry),
            )
            _append_dynamic_model_import_entry_result(
                report=report,
                entry=entry,
                selection_request=selection_request,
                final_name=None,
                status=unavailable_status,
                message=unavailable_message,
            )
        else:
            entry_key: str = entry.get_unique_key()
            if entry_key in selected_entry_keys:
                logger.add_info(
                    msg="Duplicate dynamic model catalogue entry ignored",
                    value=entry_key,
                )
            else:
                selected_entry_keys.add(entry_key)
                selection_requests.append(
                    DynamicModelImportSelectionRequest(
                        entry_key=entry_key,
                        target_domain=guess_dynamic_model_import_hierarchy_target_domain(bundle=bundle, entry=entry),
                        device_tpe=guess_dynamic_model_import_hierarchy_device_tpe(bundle=bundle, entry=entry),
                    )
                )

    add_dynamic_import_selection_requests_to_circuit(
        circuit=circuit,
        bundle=bundle,
        selection_requests=selection_requests,
        logger=logger,
        progress_callback=progress_callback,
        user_root_folder=user_root_folder,
        rename_conflicting_templates=True,
        # DGS physical adapters need the exact host bus bases before their
        # canonical Python is final. Persist them after association activation.
        persist_to_user_catalog=(
            persist_to_user_catalog
            and not defer_dgs_catalog_persistence
        ),
        report=report,
        template_fingerprint_by_object_id=template_fingerprint_by_object_id,
        clone_source_blocks=not consume_bundle_templates,
    )

    # DGS source relations remain separate metadata.  Building one record per
    # report result preserves aliases after many-to-one template deduplication
    # without assigning any template to an electrical device.
    if bundle.get_source_tpe() == DynamicModelImportSource.PowerFactoryDgs:
        association_records: List[DgsDynamicAssociationRecord] = build_dgs_dynamic_association_records(
            report=report,
        )

        # Exact single-host composites can now follow the same end state as a
        # manual GUI template assignment. Ambiguous plant controllers and
        # unsupported equipment remain safely available in the catalogue.
        activation_report: DgsDynamicModelActivationReport = (
            activate_unambiguous_dgs_dynamic_models_in_circuit(
                circuit=circuit,
                records=association_records,
                logger=logger,
            )
        )
        report.set_activation_report(activation_report=activation_report)
        logger.add_info(
            msg="DGS dynamic device models activated by exact source identity",
            value=activation_report.get_activated_count(),
        )

        if defer_dgs_catalog_persistence:
            deferred_work_list: List[SelectedDynamicImportWork] = list()
            entry_result_by_key: Dict[str, DynamicModelImportEntryResult] = dict()
            report_entry_result: DynamicModelImportEntryResult
            for report_entry_result in report.get_entry_results():
                entry_result_by_key[report_entry_result.get_unique_key()] = report_entry_result

            for selection_request in selection_requests:
                selected_entry: DynamicModelImportEntry | None = bundle.get_entry_by_key(
                    selection_request.get_entry_key(),
                )
                selected_result: DynamicModelImportEntryResult | None = (
                    entry_result_by_key.get(selection_request.get_entry_key(), None)
                )
                if selected_entry is None or selected_result is None:
                    pass
                else:
                    selected_template: RmsModelTemplate | EmtModelTemplate | None = (
                        selected_entry.get_installed_template()
                    )
                    should_persist_result: bool = selected_result.get_status() in {
                        DynamicModelImportEntryStatus.Added,
                        DynamicModelImportEntryStatus.Renamed,
                    }
                    if selected_template is None or not should_persist_result:
                        pass
                    else:
                        selected_template_object_id: int = id(selected_template)
                        adapter_requires_refingerprint: bool = (
                            selected_template.block.__dict__.get(
                                "dgs_elmvscmono_runtime_adapter",
                                None,
                            ) is True
                            or selected_template.block.__dict__.get(
                                "dgs_elmvsc_runtime_adapter",
                                None,
                            ) is True
                            or selected_template.block.__dict__.get(
                                "dgs_elmsym_runtime_adapter",
                                None,
                            ) is True
                        )
                        if (
                                not adapter_requires_refingerprint
                                and selected_template_object_id
                                in template_fingerprint_by_object_id
                        ):
                            selected_template_fingerprint: str | None = (
                                template_fingerprint_by_object_id[
                                    selected_template_object_id
                                ]
                            )
                        else:
                            # Exact VSC adapter activation writes host base
                            # values into its reusable template. Only those
                            # mutated templates need a fresh canonical digest.
                            selected_template_fingerprint = (
                                build_dynamic_import_template_fingerprint(
                                    selected_template
                                )
                            )
                            template_fingerprint_by_object_id[
                                selected_template_object_id
                            ] = selected_template_fingerprint
                        deferred_work_list.append(
                            SelectedDynamicImportWork(
                                selection_request=selection_request,
                                template_obj=selected_template,
                                entry_result=selected_result,
                                template_fingerprint=(
                                    selected_template_fingerprint
                                ),
                                include_validation_snapshot=False,
                            )
                        )

            _persist_selected_dynamic_import_work_list(
                persistable_work_list=deferred_work_list,
                logger=logger,
                progress_callback=progress_callback,
                user_root_folder=user_root_folder,
            )
        else:
            pass

    else:
        pass

    return report


def add_all_dynamic_import_bundle_to_circuit(
        circuit: MultiCircuit,
        bundle: DynamicModelImportBundle,
        logger: Logger,
        progress_callback: Callable[[int, str], None] | None = None,
        user_root_folder: str | None = None,
        persist_to_user_catalog: bool = False,
) -> int:
    """
    Add every importable entry and return the backward-compatible added count.

    :param circuit: Target circuit.
    :param bundle: Parsed dynamic-model bundle.
    :param logger: Logger receiving partial-failure and deduplication diagnostics.
    :param progress_callback: Optional UI progress callback.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :param persist_to_user_catalog: Persist added models as readable Python user templates.
    :return: Number of added templates, including collision-safe renamed variants.
    """
    report: DynamicModelImportReport = add_all_dynamic_import_bundle_to_circuit_with_report(
        circuit=circuit,
        bundle=bundle,
        logger=logger,
        progress_callback=progress_callback,
        user_root_folder=user_root_folder,
        persist_to_user_catalog=persist_to_user_catalog,
    )
    return report.get_added_count()


def add_dynamic_import_bundle_to_circuit(
        circuit: MultiCircuit,
        bundle: DynamicModelImportBundle,
        selected_keys: Sequence[str],
        logger: Logger,
) -> int:
    """
    Add the selected imported dynamic models to the circuit.

    Imported templates are stored as generic ``NoDevice`` EMT templates so they
    remain visible in every Dynamic Editor template library.

    :param circuit: Target circuit.
    :param bundle: Imported dynamic-model bundle.
    :param selected_keys: Selected entry keys.
    :param logger: Logger receiving duplicate or importability diagnostics.
    :return: Number of templates added to the circuit.
    """
    selection_requests: List[DynamicModelImportSelectionRequest] = list()
    entry_key: str

    for entry_key in selected_keys:
        selection_requests.append(_build_default_import_selection_request(entry_key))

    return add_dynamic_import_selection_requests_to_circuit(
        circuit=circuit,
        bundle=bundle,
        selection_requests=selection_requests,
        logger=logger,
    )


def load_user_dynamic_model_templates_into_circuit(
        circuit: MultiCircuit,
        logger: Logger | None = None,
        user_root_folder: str | None = None,
        allow_executable_python: bool = False,
) -> int:
    """
    Load persisted user dynamic templates from the VeraGrid user folder.

    The loader only targets the importer-managed ``user_templates`` folder so the
    GUI can restore previously imported EMT templates across sessions without
    coupling that behavior to generic ``MultiCircuit`` construction.

    :param circuit: Target circuit receiving the persisted templates.
    :param logger: Optional logger receiving load diagnostics.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :param allow_executable_python: Execute trusted Python template modules. Disabled by default.
    :return: Number of templates added to the circuit.
    """
    effective_logger: Logger = Logger() if logger is None else logger
    existing_rms_names: Set[str] = set()
    existing_emt_names: Set[str] = set()
    loaded_template: DynamicModelLoadedUserTemplate
    template_obj: RmsModelTemplate | EmtModelTemplate
    added_count: int = 0

    # The catalogue must stay idempotent inside one circuit even if the same user
    # template file is scanned more than once across GUI actions.
    for template in circuit.rms_models:
        existing_rms_names.add(template.name)

    for template in circuit.emt_models:
        existing_emt_names.add(template.name)

    # Reuse the shared folder scanner so the GUI catalogue and the importer load
    # exactly the same persisted template modules.
    for loaded_template in load_user_dynamic_model_templates(
            var_factory=circuit.var_factory,
            logger=effective_logger,
            user_root_folder=user_root_folder,
            allow_executable_python=allow_executable_python,
    ):
        template_obj = loaded_template.get_template_obj()

        if isinstance(template_obj, RmsModelTemplate):
            if template_obj.name in existing_rms_names:
                effective_logger.add_debug(
                    "Skipped persisted user RMS model because the template name already exists",
                    template_obj.name,
                )
            else:
                circuit.add_rms_model(template_obj)
                existing_rms_names.add(template_obj.name)
                added_count += 1
        else:
            if isinstance(template_obj, EmtModelTemplate):
                if template_obj.name in existing_emt_names:
                    effective_logger.add_debug(
                        "Skipped persisted user EMT model because the template name already exists",
                        template_obj.name,
                    )
                else:
                    circuit.add_emt_model(template_obj)
                    existing_emt_names.add(template_obj.name)
                    added_count += 1
            else:
                pass

    return added_count


def load_user_dynamic_model_templates(
        var_factory: VarFactory,
        logger: Logger | None = None,
        user_root_folder: str | None = None,
        allow_executable_python: bool = False,
) -> List[DynamicModelLoadedUserTemplate]:
    """
    Materialize all persisted user dynamic templates from the VeraGrid user folder.

    :param var_factory: Variable factory used to build the template blocks.
    :param logger: Optional logger receiving load diagnostics.
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :param allow_executable_python: Execute trusted Python template modules. Disabled by default.
    :return: Materialized persisted user templates.
    """
    effective_logger: Logger = Logger() if logger is None else logger
    templates: List[DynamicModelLoadedUserTemplate] = list()
    seen_template_signatures: Set[tuple[DynamicModelImportTargetDomain, str]] = set()
    folder_path: Path
    module_path: Path
    payload_path: Path
    template: DynamicModelLoadedUserTemplate | None
    loaded_module_stems: Set[str]

    for folder_path in _iter_user_dynamic_models_folder_paths(user_root_folder=user_root_folder):
        loaded_module_stems = set()

        # Python user modules are executable code. Only materialize them after an
        # explicit trust decision; JSON sidecars remain available as data-only
        # fallbacks when execution is disabled.
        for module_path in sorted(folder_path.glob("*.py")):
            if module_path.name == "__init__.py":
                template = None
            elif allow_executable_python:
                template = _load_user_dynamic_template_from_module_path(
                    module_path=module_path,
                    var_factory=var_factory,
                    logger=effective_logger,
                )
            else:
                effective_logger.add_warning(
                    msg="Skipped executable user dynamic-model module because trust was not granted",
                    value=str(module_path),
                )
                template = None

            if template is None:
                pass
            else:
                loaded_module_stems.add(module_path.stem)
                _report_user_dynamic_template_snapshot_difference(
                    loaded_module_template=template,
                    payload_path=module_path.with_suffix(".payload.json"),
                    var_factory=var_factory,
                    logger=effective_logger,
                )
                _append_loaded_user_dynamic_template_once(
                    template=template,
                    seen_template_signatures=seen_template_signatures,
                    templates=templates,
                )

        # JSON sidecars are validation snapshots and a compatibility fallback.
        # They are loaded only when the corresponding canonical Python module is
        # absent or failed validation/materialization.
        for payload_path in sorted(folder_path.glob("*.payload.json")):
            payload_module_stem: str = payload_path.name[:-len(".payload.json")]
            if payload_module_stem in loaded_module_stems:
                template = None
            else:
                template = _load_user_dynamic_template_from_payload_path(
                    payload_path=payload_path,
                    var_factory=var_factory,
                    logger=effective_logger,
                )

            if template is None:
                pass
            else:
                effective_logger.add_warning(
                    msg="Loaded legacy user dynamic model from JSON snapshot fallback",
                    value=str(payload_path),
                )
                _append_loaded_user_dynamic_template_once(
                    template=template,
                    seen_template_signatures=seen_template_signatures,
                    templates=templates,
                )

    return templates


def _append_loaded_user_dynamic_template_once(
        template: DynamicModelLoadedUserTemplate,
        seen_template_signatures: Set[tuple[DynamicModelImportTargetDomain, str]],
        templates: List[DynamicModelLoadedUserTemplate],
) -> None:
    """
    Append one loaded template unless its domain and name were already restored.

    :param template: Loaded user-template descriptor.
    :param seen_template_signatures: Mutable set of already accepted signatures.
    :param templates: Mutable ordered output collection.
    :return: None.
    """
    template_signature: tuple[DynamicModelImportTargetDomain, str] = (
        template.get_domain(),
        template.get_template_obj().name,
    )

    # Domain-separated folders are scanned before the legacy folder, so keeping
    # the first signature deterministically preserves the modern catalogue.
    if template_signature in seen_template_signatures:
        pass
    else:
        seen_template_signatures.add(template_signature)
        templates.append(template)


def _get_user_dynamic_models_root_folder_path(create: bool = True,
                                              user_root_folder: str | None = None) -> Path:
    """
    Return the VeraGrid user root folder used to persist imported dynamic models.

    :param create: Create the folder when it does not exist?
    :return: Persistent user dynamic-model root folder path.
    """
    root_folder_path: Path
    folder_path: Path

    if user_root_folder is None:
        root_folder_path = Path(get_create_veragrid_folder())
    else:
        root_folder_path = Path(user_root_folder)

    folder_path = root_folder_path / "user_defined_models"

    if create:
        folder_path.mkdir(parents=True, exist_ok=True)
    else:
        pass

    return folder_path


def _get_legacy_user_dynamic_models_folder_path(create: bool = False,
                                                user_root_folder: str | None = None) -> Path:
    """
    Return the legacy flat folder used by older VeraGrid builds.

    :param create: Create the folder when it does not exist?
    :return: Legacy persisted user dynamic-model folder path.
    """
    root_folder_path: Path
    folder_path: Path

    if user_root_folder is None:
        root_folder_path = Path(get_create_veragrid_folder())
    else:
        root_folder_path = Path(user_root_folder)

    folder_path = root_folder_path / "user_templates"

    if create:
        folder_path.mkdir(parents=True, exist_ok=True)
    else:
        pass

    return folder_path


def _get_user_dynamic_models_domain_folder_path(
        target_domain: DynamicModelImportTargetDomain,
        create: bool = True,
        user_root_folder: str | None = None,
) -> Path:
    """
    Return the domain-specific VeraGrid user folder used to persist one template.

    :param target_domain: Selected persisted template domain.
    :param create: Create the folder when it does not exist?
    :param user_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Persistent domain-specific user dynamic-model folder path.
    """
    folder_name: str

    if target_domain == DynamicModelImportTargetDomain.Rms:
        folder_name = "rms"
    else:
        if target_domain == DynamicModelImportTargetDomain.Emt:
            folder_name = "emt"
        else:
            raise ValueError(f"Unsupported user dynamic-model domain {target_domain}")

    folder_path: Path = _get_user_dynamic_models_root_folder_path(create=create, user_root_folder=user_root_folder) / folder_name

    if create:
        folder_path.mkdir(parents=True, exist_ok=True)
    else:
        pass

    return folder_path


def _iter_user_dynamic_models_folder_paths(user_root_folder: str | None = None) -> List[Path]:
    """
    Return the existing persisted user-template folders to scan.

    The loader prefers the new domain-separated layout while still scanning the
    legacy flat folder so existing user templates keep loading without migration.

    :return: Existing persisted user-template folders in deterministic order.
    """
    folder_paths: List[Path] = list()
    rms_folder_path: Path = _get_user_dynamic_models_domain_folder_path(
        DynamicModelImportTargetDomain.Rms,
        create=False,
        user_root_folder=user_root_folder,
    )
    emt_folder_path: Path = _get_user_dynamic_models_domain_folder_path(
        DynamicModelImportTargetDomain.Emt,
        create=False,
        user_root_folder=user_root_folder,
    )
    legacy_folder_path: Path = _get_legacy_user_dynamic_models_folder_path(create=False, user_root_folder=user_root_folder)

    if rms_folder_path.exists():
        folder_paths.append(rms_folder_path)
    else:
        pass

    if emt_folder_path.exists():
        folder_paths.append(emt_folder_path)
    else:
        pass

    if legacy_folder_path.exists():
        folder_paths.append(legacy_folder_path)
    else:
        pass

    return folder_paths


def _sanitize_file_stem(text: str) -> str:
    """
    Convert one display name into a filesystem-safe stem.

    :param text: Source text.
    :return: Filesystem-safe stem.
    """
    return sanitize_dynamic_model_file_stem(text=text)


def build_user_dynamic_template_catalog_output_path(
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        catalog_root_folder: str | None = None,
) -> Path:
    """
    Build the preferred unsuffixed path for one persisted user template module.

    The save operation may add a structural-fingerprint suffix when this base
    name collides with a different existing catalogue artifact.

    :param template_name: Human-facing template name.
    :param target_domain: Selected RMS or EMT user folder.
    :param catalog_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Preferred Python module output path before collision resolution.
    """
    output_folder: Path
    safe_stem: str = _sanitize_file_stem(template_name)

    if catalog_root_folder is None:
        output_folder = _get_user_dynamic_models_domain_folder_path(target_domain=target_domain, create=True)
    else:
        output_folder = _get_user_dynamic_models_domain_folder_path(
            target_domain=target_domain,
            create=True,
            user_root_folder=catalog_root_folder,
        )

    if len(safe_stem) == 0:
        safe_stem = "user_dynamic_model"
    else:
        pass

    return output_folder / f"{safe_stem}.py"


def build_user_dynamic_template_payload_output_path(
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        catalog_root_folder: str | None = None,
) -> Path:
    """
    Build the preferred unsuffixed sidecar path for one persisted user template.

    :param template_name: Human-facing template name.
    :param target_domain: Selected RMS or EMT user folder.
    :param catalog_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :return: Preferred JSON payload path before collision resolution.
    """
    module_path: Path = build_user_dynamic_template_catalog_output_path(
        template_name=template_name,
        target_domain=target_domain,
        catalog_root_folder=catalog_root_folder,
    )
    return module_path.with_suffix(".payload.json")


def _build_user_dynamic_template_catalog_identity(
        block: Block,
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        device_tpe: DeviceType,
) -> RmsModelTemplate | EmtModelTemplate:
    """
    Materialize the fixed metadata used to fingerprint one catalogue artifact.

    :param block: Persistable symbolic block.
    :param template_name: Final catalogue template name.
    :param target_domain: Selected RMS or EMT domain.
    :param device_tpe: Selected supported device type.
    :return: Typed template identity used only for structural comparison.
    """
    template_obj: RmsModelTemplate | EmtModelTemplate

    if target_domain == DynamicModelImportTargetDomain.Rms:
        template_obj = RmsModelTemplate(name=template_name)
    else:
        if target_domain == DynamicModelImportTargetDomain.Emt:
            template_obj = EmtModelTemplate(name=template_name)
        else:
            raise ValueError(f"Unsupported user dynamic-model domain {target_domain}")

    # Fingerprints include the target class and the declared device family, so
    # two files are reusable only when their complete catalogue meaning agrees.
    template_obj.tpe = device_tpe
    template_obj.block = copy.deepcopy(block)
    return template_obj


def _build_casefold_catalog_module_lookup(output_folder: Path) -> Dict[str, List[Path]]:
    """
    Index existing Python catalogue modules by Windows-safe casefolded name.

    :param output_folder: Domain-specific user catalogue folder.
    :return: Existing module paths grouped by casefolded file name.
    """
    module_lookup: Dict[str, List[Path]] = dict()
    module_path: Path
    payload_path: Path
    represented_module_path: Path
    represented_module_name: str
    casefolded_name: str

    for module_path in sorted(output_folder.glob("*.py")):
        if module_path.name == "__init__.py":
            pass
        else:
            casefolded_name = module_path.name.casefold()
            if casefolded_name in module_lookup:
                module_lookup[casefolded_name].append(module_path)
            else:
                module_lookup[casefolded_name] = list([module_path])

    # Payload-only artifacts left by older versions still reserve their logical
    # module name.  They are compared structurally before either being repaired
    # in place or preserved beside a collision-safe new pair.
    for payload_path in sorted(output_folder.glob("*.payload.json")):
        represented_module_name = payload_path.name[:-len(".payload.json")] + ".py"
        represented_module_path = output_folder / represented_module_name
        casefolded_name = represented_module_name.casefold()
        if casefolded_name in module_lookup:
            pass
        else:
            module_lookup[casefolded_name] = list([represented_module_path])

    return module_lookup


def _read_user_dynamic_template_payload_identity(
        payload_path: Path,
) -> Tuple[str, str, str, str] | None:
    """Read only the small identity header of one catalogue sidecar.

    The deterministic payload writes identity fields before the large symbolic
    block. Reading line by line avoids deserializing a multi-megabyte controller
    merely to decide that its already-persisted catalogue artifact is current.

    :param payload_path: JSON sidecar belonging to one Python template module.
    :return: Name, domain, device type and fingerprint, or ``None`` for a legacy
        or incomplete payload.
    """
    identity_values: Dict[str, str] = dict()
    required_keys: Set[str] = set([
        "template_name",
        "target_domain",
        "device_tpe",
        "template_fingerprint",
    ])
    payload_line: str
    stripped_line: str
    identity_key: str
    raw_value: str
    decoded_value: object

    if payload_path.is_file():
        try:
            with payload_path.open(mode="r", encoding="utf-8") as payload_file:
                for payload_line in payload_file:
                    stripped_line = payload_line.strip()
                    if stripped_line.startswith('"block_data"'):
                        break
                    else:
                        pass
                    for identity_key in required_keys:
                        if stripped_line.startswith(f'"{identity_key}"'):
                            raw_value = stripped_line.split(":", 1)[1].rstrip(",")
                            decoded_value = json.loads(raw_value)
                            if isinstance(decoded_value, str):
                                identity_values[identity_key] = decoded_value
                            else:
                                pass
                        else:
                            pass
        except (OSError, ValueError, json.JSONDecodeError):
            identity_values = dict()
    else:
        pass

    if required_keys.issubset(identity_values.keys()):
        return (
            identity_values["template_name"],
            identity_values["target_domain"],
            identity_values["device_tpe"],
            identity_values["template_fingerprint"],
        )
    else:
        return None


def _build_user_dynamic_template_module_identity_header(
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        device_tpe: DeviceType,
        template_fingerprint: str | None,
) -> str:
    """Build a compact identity header for one canonical Python template.

    Massive DGS catalogues intentionally omit the redundant full-graph JSON
    snapshot.  Keeping the immutable identity in Python comments lets repeated
    imports deduplicate those modules without executing multi-megabyte symbolic
    builders merely to discover their fingerprints.

    :param template_name: Exact reusable-template name.
    :param target_domain: RMS or EMT catalogue domain.
    :param device_tpe: Supported device-family classification.
    :param template_fingerprint: Structural SHA-256 identity, when available.
    :return: Deterministic comment header, including its final newline.
    """
    identity_payload: Dict[str, str] = dict()
    header_text: str

    identity_payload["template_name"] = template_name
    identity_payload["target_domain"] = target_domain.value
    identity_payload["device_tpe"] = device_tpe.name
    if template_fingerprint is None:
        header_text = ""
    else:
        identity_payload["template_fingerprint"] = template_fingerprint
        header_text = (
            "# VeraGrid dynamic template identity: "
            + json.dumps(identity_payload, sort_keys=True, ensure_ascii=True)
            + "\n"
        )
    return header_text


def _read_user_dynamic_template_module_identity(
        module_path: Path,
) -> Tuple[str, str, str, str] | None:
    """Read the compact identity header without importing the Python module.

    :param module_path: Canonical human-readable Python template module.
    :return: Name, domain, device type and fingerprint, or ``None`` for a legacy
        module without a valid identity header.
    """
    header_prefix: str = "# VeraGrid dynamic template identity: "
    module_line: str
    stripped_line: str
    decoded_payload: object
    identity_payload: Dict[str, object]
    required_keys: Set[str] = set([
        "template_name",
        "target_domain",
        "device_tpe",
        "template_fingerprint",
    ])
    identity: Tuple[str, str, str, str] | None = None
    inspected_line_count: int = 0

    if module_path.is_file():
        try:
            with module_path.open(mode="r", encoding="utf-8") as module_file:
                for module_line in module_file:
                    stripped_line = module_line.strip()
                    if stripped_line.startswith(header_prefix):
                        decoded_payload = json.loads(
                            stripped_line[len(header_prefix):]
                        )
                        if isinstance(decoded_payload, dict):
                            identity_payload = decoded_payload
                            if required_keys.issubset(identity_payload.keys()):
                                identity = (
                                    str(identity_payload["template_name"]),
                                    str(identity_payload["target_domain"]),
                                    str(identity_payload["device_tpe"]),
                                    str(identity_payload["template_fingerprint"]),
                                )
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass

                    inspected_line_count += 1
                    if identity is None and inspected_line_count < 16:
                        pass
                    else:
                        break
        except (OSError, ValueError, json.JSONDecodeError):
            identity = None
    else:
        pass

    return identity


def _find_current_user_dynamic_template_catalog_module(
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        device_tpe: DeviceType,
        template_fingerprint: str,
        catalog_root_folder: str | None,
) -> Path | None:
    """Find one already-current module from its lightweight sidecar identity.

    :param template_name: Exact reusable-template name.
    :param target_domain: RMS or EMT catalogue domain.
    :param device_tpe: Supported device-family classification.
    :param template_fingerprint: Precomputed structural SHA-256 identity.
    :param catalog_root_folder: Optional explicit VeraGrid user root.
    :return: Matching Python module or ``None``.
    """
    base_path: Path = build_user_dynamic_template_catalog_output_path(
        template_name=template_name,
        target_domain=target_domain,
        catalog_root_folder=catalog_root_folder,
    )
    candidate_patterns: List[str] = list([
        base_path.name,
        f"{base_path.stem}__*{base_path.suffix}",
    ])
    candidate_pattern: str
    candidate_path: Path
    module_identity: Tuple[str, str, str, str] | None
    payload_identity: Tuple[str, str, str, str] | None
    desired_identity: Tuple[str, str, str, str] = (
        template_name,
        target_domain.value,
        device_tpe.name,
        template_fingerprint,
    )

    for candidate_pattern in candidate_patterns:
        for candidate_path in sorted(base_path.parent.glob(candidate_pattern)):
            module_identity = _read_user_dynamic_template_module_identity(
                module_path=candidate_path,
            )
            if module_identity == desired_identity:
                return candidate_path
            else:
                payload_identity = _read_user_dynamic_template_payload_identity(
                    payload_path=candidate_path.with_suffix(".payload.json"),
                )
                if payload_identity == desired_identity:
                    return candidate_path
                else:
                    pass

    return None


def _catalog_module_matches_template_identity(
        module_path: Path,
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        device_tpe: DeviceType,
        desired_fingerprint: str | None,
) -> bool:
    """
    Check whether one existing module is the same complete catalogue template.

    :param module_path: Existing canonical Python module.
    :param template_name: Desired exact template name.
    :param target_domain: Desired RMS or EMT domain.
    :param device_tpe: Desired device-family classification.
    :param desired_fingerprint: Desired structural fingerprint.
    :return: ``True`` when the existing artifact can be safely refreshed in place.
    """
    load_logger: Logger = Logger()
    loaded_template: DynamicModelLoadedUserTemplate | None
    loaded_payload: Tuple[Block, str, DynamicModelImportTargetDomain, DeviceType] | None
    existing_template: RmsModelTemplate | EmtModelTemplate
    payload_path: Path = module_path.with_suffix(".payload.json")
    existing_fingerprint: str | None
    matches_identity: bool

    if desired_fingerprint is None:
        matches_identity = False
    else:
        if module_path.is_file():
            loaded_template = _load_user_dynamic_template_from_module_path(
                module_path=module_path,
                var_factory=VarFactory(),
                logger=load_logger,
            )
            if loaded_template is None:
                matches_identity = False
            else:
                existing_fingerprint = build_dynamic_import_template_fingerprint(
                    loaded_template.get_template_obj(),
                )
                matches_identity = (
                    loaded_template.get_template_obj().name == template_name and
                    loaded_template.get_domain() == target_domain and
                    loaded_template.get_device_tpe() == device_tpe and
                    existing_fingerprint == desired_fingerprint
                )
        else:
            if payload_path.is_file():
                loaded_payload = load_user_dynamic_template_json_payload(json_path=str(payload_path))
            else:
                loaded_payload = None

            if loaded_payload is None:
                matches_identity = False
            else:
                existing_template = _build_user_dynamic_template_catalog_identity(
                    block=loaded_payload[0],
                    template_name=loaded_payload[1],
                    target_domain=loaded_payload[2],
                    device_tpe=loaded_payload[3],
                )
                existing_fingerprint = build_dynamic_import_template_fingerprint(existing_template)
                matches_identity = (
                    loaded_payload[1] == template_name and
                    loaded_payload[2] == target_domain and
                    loaded_payload[3] == device_tpe and
                    existing_fingerprint == desired_fingerprint
                )

    return matches_identity


def _resolve_user_dynamic_template_catalog_output_path(
        block: Block,
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        device_tpe: DeviceType,
        module_text: str,
        catalog_root_folder: str | None,
        template_fingerprint: str | None = None,
) -> Path:
    """
    Resolve a collision-safe path without overwriting a different catalogue model.

    Name sanitization and case-insensitive filesystems may map distinct template
    names to the same file.  Existing paths are reused only after exact metadata
    and structural-fingerprint comparison; otherwise a deterministic fingerprint
    suffix preserves both artifacts.

    :param block: Persistable symbolic block.
    :param template_name: Final catalogue template name.
    :param target_domain: Selected RMS or EMT domain.
    :param device_tpe: Selected supported device type.
    :param module_text: Canonical generated Python module text.
    :param catalog_root_folder: Optional explicit VeraGrid user root.
    :param template_fingerprint: Optional precomputed structural identity.
    :return: Collision-safe canonical Python module path.
    """
    base_path: Path = build_user_dynamic_template_catalog_output_path(
        template_name=template_name,
        target_domain=target_domain,
        catalog_root_folder=catalog_root_folder,
    )
    module_lookup: Dict[str, List[Path]] = _build_casefold_catalog_module_lookup(
        output_folder=base_path.parent,
    )
    desired_template: RmsModelTemplate | EmtModelTemplate = _build_user_dynamic_template_catalog_identity(
        block=block,
        template_name=template_name,
        target_domain=target_domain,
        device_tpe=device_tpe,
    )
    desired_fingerprint: str | None
    if template_fingerprint is None:
        desired_fingerprint = build_dynamic_import_template_fingerprint(
            desired_template
        )
    else:
        desired_fingerprint = template_fingerprint
    fallback_digest: str = hashlib.sha256(module_text.encode("utf-8")).hexdigest()
    suffix_digest: str
    candidate_path: Path = base_path
    resolved_path: Path | None = None
    existing_paths: List[Path]
    existing_path: Path
    matching_path: Path | None
    collision_index: int = 1

    if desired_fingerprint is None:
        suffix_digest = fallback_digest[:12]
    else:
        suffix_digest = desired_fingerprint[:12]

    while resolved_path is None:
        existing_paths = module_lookup.get(candidate_path.name.casefold(), list())
        if len(existing_paths) == 0:
            resolved_path = candidate_path
        else:
            matching_path = None
            for existing_path in existing_paths:
                if matching_path is None and _catalog_module_matches_template_identity(
                        module_path=existing_path,
                        template_name=template_name,
                        target_domain=target_domain,
                        device_tpe=device_tpe,
                        desired_fingerprint=desired_fingerprint,
                ):
                    matching_path = existing_path
                else:
                    pass

            if matching_path is None:
                if collision_index == 1:
                    candidate_path = base_path.with_name(
                        f"{base_path.stem}__{suffix_digest}{base_path.suffix}"
                    )
                else:
                    candidate_path = base_path.with_name(
                        f"{base_path.stem}__{suffix_digest}_{collision_index}{base_path.suffix}"
                    )
                collision_index += 1
            else:
                resolved_path = matching_path

    return resolved_path


def _build_sorted_identifier_var_pairs(
        variables: Sequence[Var],
        identifier_map: Dict[int, str],
) -> List[Tuple[str, Var]]:
    """
    Order emitted variable declarations by their persistent Python alias.

    Semantic names are not sufficient because a valid composite may expose
    several distinct variables named, for example, ``uconv_i``. The persistent
    alias is unique and survives module reload, so it is the deterministic
    declaration-order key.

    :param variables: Variables belonging to one emitted declaration group.
    :param identifier_map: Persistent Python alias indexed by variable UID.
    :return: Alias-variable pairs in deterministic order.
    """
    ordered_pairs: List[Tuple[str, Var]] = list()
    variable: Var
    for variable in variables:
        ordered_pairs.append((identifier_map[variable.uid], variable))
    ordered_pairs.sort()
    return ordered_pairs


def _build_user_dynamic_variable_allocation_text(
        variable: Var,
        identifier_map: Dict[int, str],
        is_derivative: bool,
) -> str:
    """Build one metadata-preserving Python VarFactory allocation.

    Power-flow references are executable wiring metadata, not cosmetic labels.
    Persisting only the variable name leaves a reloaded RMS input disconnected
    from its bus even though the symbolic equation text remains identical.

    :param variable: Symbolic variable being declared.
    :param identifier_map: Persistent Python aliases indexed by UID.
    :param is_derivative: Include the exact base-variable allocation link.
    :return: Executable ``VarFactory`` allocation expression.
    """
    allocation_arguments: List[str] = list([
        repr(variable.name + "_") + " + template_name_runtime",
    ])
    if variable.ref is None:
        pass
    else:
        allocation_arguments.append(
            "reference=VarPowerFlowReferenceType." + variable.ref.name
        )
    if variable.network_conn:
        allocation_arguments.append("network_conn=True")
    else:
        pass
    if variable.shared_ref is None:
        pass
    else:
        allocation_arguments.append(
            "shared_reference=" + repr(variable.shared_ref.name)
        )
    if is_derivative:
        if variable.base_var is None:
            raise ValueError(
                "A persisted derivative variable requires one base variable"
            )
        else:
            allocation_arguments.append(
                "base_var=" + identifier_map[variable.base_var.uid]
            )
        factory_method_name: str = "add_diff_var"
    else:
        factory_method_name = "add_var"
    return "vf." + factory_method_name + "(" + ", ".join(
        allocation_arguments
    ) + ")"


def _build_user_dynamic_template_module_text(block: Block,
                                             template_name: str,
                                             target_domain: DynamicModelImportTargetDomain,
                                             device_tpe: DeviceType) -> str:
    """
    Build one persisted Python module that recreates one symbolic user template.

    :param block: Symbolic block exported from the editor.
    :param template_name: Default runtime template name.
    :param target_domain: Selected RMS or EMT template domain.
    :param device_tpe: Selected supported device type.
    :return: Python module text.
    """
    identifier_map: Dict[int, str] = _make_identifier_map(block)
    child_ref_names: Dict[int, str]
    variable_groups = _build_template_module_variable_groups(block)
    procedural_import_names: List[str] = _procedural_logic_import_names(block)
    has_dgs_discrete_events: bool = False
    event_block: Block
    event_blocks: List[Block] = list([block])
    event_blocks.extend(_iter_child_blocks_recursive(block))
    for event_block in event_blocks:
        raw_discrete_actions: object | None = event_block.__dict__.get(
            "dgs_discrete_event_actions",
            None,
        )
        if isinstance(raw_discrete_actions, list) and len(raw_discrete_actions) > 0:
            has_dgs_discrete_events = True
        else:
            pass
    lines: List[str] = list()
    template_class_name: str
    template_class_import: str

    if target_domain == DynamicModelImportTargetDomain.Rms:
        template_class_name = "RmsModelTemplate"
        template_class_import = "from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate"
    else:
        if target_domain == DynamicModelImportTargetDomain.Emt:
            template_class_name = "EmtModelTemplate"
            template_class_import = "from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate"
        else:
            raise ValueError(f"Unsupported user dynamic-model domain {target_domain}")

    reserved_identifiers: Set[str] = set(identifier_map.values())
    generated_scope_identifiers: Set[str] = set([
        "Block",
        "DeviceType",
        "DgsDiscreteEventAction",
        "DgsDiscreteEventCommand",
        "EmtModelTemplate",
        "Expr",
        "ParamPowerFlowReferenceType",
        "RmsModelTemplate",
        "Var",
        "VarPowerFlowReferenceType",
        "get_template",
        "name",
        "sym",
        "template",
        "template_name_runtime",
        "vf",
    ])
    # Child block references share the generated function namespace with
    # imports, arguments and local variables. Reserving that complete surface
    # prevents a DGS block such as ``delay`` from hiding the imported
    # procedural constructor ``delay()`` when the Python module reloads.
    generated_scope_identifiers.update(procedural_import_names)
    reserved_identifiers.update(generated_scope_identifiers)
    child_ref_names = _build_recursive_child_ref_names(
        block=block,
        reserved_identifiers=reserved_identifiers,
    )

    lines.append("# This Source Code Form is subject to the terms of the Mozilla Public")
    lines.append("# License, v. 2.0. If a copy of the MPL was not distributed with this")
    lines.append("# file, You can obtain one at https://mozilla.org/MPL/2.0/.")
    lines.append("# SPDX-License-Identifier: MPL-2.0")
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append(template_class_import)
    lines.append("from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory")
    lines.append("import VeraGridEngine.Utils.Symbolic.symbolic as sym")
    lines.append("from VeraGridEngine.Utils.Symbolic.block import Block")
    lines.append("from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var")

    if len(procedural_import_names) > 0:
        lines.append("from VeraGridEngine.Utils.procedural_logic import " + ", ".join(procedural_import_names))
    else:
        pass

    if has_dgs_discrete_events:
        lines.append(
            "from VeraGridEngine.IO.dgs.dgs_discrete_event import "
            "DgsDiscreteEventAction, DgsDiscreteEventCommand"
        )
    else:
        pass

    lines.append("from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType")
    lines.append("")
    lines.append(f"def get_template(vf: VarFactory, name: str | None = None) -> {template_class_name}:")
    lines.append("    \"\"\"")
    lines.append("    Materialize the persisted user dynamic template.")
    lines.append("")
    lines.append("    :param vf: Variable factory used to allocate the symbolic surface.")
    lines.append("    :param name: Optional explicit runtime template name.")
    lines.append("    :return: Materialized reusable template.")
    lines.append("    \"\"\"")
    lines.append("    template_name_runtime: str")
    lines.append(f"    template: {template_class_name} = {template_class_name}()")
    lines.append("")
    lines.append("    if name is None:")
    lines.append(f"        template_name_runtime = {repr(template_name)}")
    lines.append("    else:")
    lines.append("        template_name_runtime = str(name)")
    lines.append("")
    lines.append(f"    template.tpe = DeviceType.{device_tpe.name}")
    lines.append("    template.name = template_name_runtime")
    lines.append("")
    lines.append("    # --- Parameters ---")
    identifier_name: str
    for identifier_name, var_obj in _build_sorted_identifier_var_pairs(
            variables=variable_groups.param_vars,
            identifier_map=identifier_map,
    ):
        allocation_text: str = _build_user_dynamic_variable_allocation_text(
            variable=var_obj,
            identifier_map=identifier_map,
            is_derivative=False,
        )
        lines.append(
            f"    {identifier_map[var_obj.uid]}: Var = {allocation_text}"
        )
    lines.append("")
    lines.append("    # --- State Variables ---")
    for identifier_name, var_obj in _build_sorted_identifier_var_pairs(
            variables=variable_groups.state_vars,
            identifier_map=identifier_map,
    ):
        allocation_text = _build_user_dynamic_variable_allocation_text(
            variable=var_obj,
            identifier_map=identifier_map,
            is_derivative=False,
        )
        lines.append(
            f"    {identifier_map[var_obj.uid]}: Var = {allocation_text}"
        )
    lines.append("")
    lines.append("    # --- Algebraic / Shared Variables ---")
    for identifier_name, var_obj in _build_sorted_identifier_var_pairs(
            variables=variable_groups.algebraic_vars,
            identifier_map=identifier_map,
    ):
        allocation_text = _build_user_dynamic_variable_allocation_text(
            variable=var_obj,
            identifier_map=identifier_map,
            is_derivative=False,
        )
        lines.append(
            f"    {identifier_map[var_obj.uid]}: Var = {allocation_text}"
        )
    lines.append("")
    lines.append("    # --- Derivative Variables ---")
    for identifier_name, var_obj in _build_sorted_identifier_var_pairs(
            variables=variable_groups.diff_vars,
            identifier_map=identifier_map,
    ):
        allocation_text = _build_user_dynamic_variable_allocation_text(
            variable=var_obj,
            identifier_map=identifier_map,
            is_derivative=True,
        )
        lines.append(
            f"    {identifier_map[var_obj.uid]}: Var = {allocation_text}"
        )
    lines.append("")
    lines.append("    # --- Block Assembly ---")
    _append_recursive_child_block_code(block, identifier_map, lines, child_ref_names)
    _emit_block_code(block, identifier_map, "template.block", lines, child_ref_names)
    lines.append("    # Preserve exact aliases for distinct PowerFactory signals sharing one name.")
    lines.append("    template.block.__dict__['dgs_persisted_identifier_by_uid'] = {")
    identifier_uid: int
    identifier_name: str
    for identifier_uid, identifier_name in identifier_map.items():
        lines.append(
            f"        {identifier_name}.uid: {repr(identifier_name)},"
        )
    lines.append("    }")
    direct_slot_interfaces_raw: object | None = block.__dict__.get(
        "dgs_direct_slot_interfaces",
        None,
    )
    if isinstance(direct_slot_interfaces_raw, list):
        # The native equipment adapter is selected from this exported signal
        # contract after the Python template is loaded again.
        lines.append("    # Preserve native DGS slot contracts for typed runtime adapters.")
        append_python_syntax_assignment(
            lines=lines,
            prefix="dgs_direct_slot_interfaces: list[dict[str, object]] = ",
            value=direct_slot_interfaces_raw,
            indentation=4,
        )
        lines.append(
            "    template.block.__dict__['dgs_direct_slot_interfaces'] = "
            "dgs_direct_slot_interfaces"
        )
    else:
        pass
    lines.append("    template.block.name = template_name_runtime")
    lines.append("    return template")

    return "\n".join(lines) + "\n"


def _iter_child_blocks_recursive(block: Block) -> List[Block]:
    """
    Return every descendant child block in depth-first order.

    :param block: Root block.
    :return: Recursive child block list.
    """
    child_blocks: List[Block] = list()
    child_block: Block

    for child_block in block.children:
        child_blocks.append(child_block)
        child_blocks.extend(_iter_child_blocks_recursive(child_block))

    return child_blocks


def _build_recursive_child_ref_names(
        block: Block,
        reserved_identifiers: Set[str],
) -> Dict[int, str]:
    """
    Build deterministic reference names for every descendant child block.

    :param block: Root block.
    :param reserved_identifiers: Variable identifiers already used in the generated function.
    :return: Reference name by child object identity.
    """
    child_ref_names: Dict[int, str] = dict()
    used_names: Set[str] = set(reserved_identifiers)
    child_block: Block
    base_name: str
    candidate_name: str
    suffix_index: int

    for child_block in _iter_child_blocks_recursive(block):
        base_name = _safe_name(child_block.name)
        candidate_name = base_name
        suffix_index = 1
        while candidate_name in used_names:
            candidate_name = f"{base_name}_{suffix_index}"
            suffix_index += 1
        used_names.add(candidate_name)
        child_ref_names[id(child_block)] = candidate_name

    return child_ref_names


def _append_recursive_child_block_code(block: Block,
                                       identifier_map: Dict[int, str],
                                       lines: List[str],
                                       child_ref_names: Dict[int, str]) -> None:
    """
    Emit every descendant child block before the parent block constructor uses it.

    :param block: Root block whose descendants must be emitted.
    :param identifier_map: Python identifier map by variable uid.
    :param lines: Output line buffer.
    :param child_ref_names: Deterministic child reference names.
    :return: None.
    """
    child_block: Block

    for child_block in block.children:
        _append_recursive_child_block_code(child_block, identifier_map, lines, child_ref_names)
        _emit_block_code(child_block, identifier_map, child_ref_names[id(child_block)], lines, child_ref_names)
        lines.append("")


def build_user_dynamic_template_persistable_block(block: Block) -> Block:
    """
    Build the reusable block payload persisted into catalogue `.py` templates.

    Device-bound editors expose lateral `INPUT_CONN` and `OUTPUT_CONN` blocks only
    as one visual wrapper around the reusable template interface. Persisting those
    GUI-only children into the catalogue would duplicate the lateral interface when
    the template gets opened again. The persisted `.py` template therefore keeps the
    root symbolic ports but removes the wrapper connection blocks and their diagram
    branches.

    :param block: Editor working block.
    :return: Persistable reusable block without GUI-only lateral wrappers.
    """
    export_block: Block = copy.deepcopy(block)
    interface_block_uids: Set[int] = set()
    filtered_children: List[Block] = list()
    child_block: Block
    node_uid: int
    node_data: object
    connection_uid: int
    connection_data: object
    filtered_node_data: Dict[int, object] = dict()
    filtered_connection_data: Dict[int, object] = dict()

    for node_uid, node_data in export_block.diagram.node_data.items():
        if node_data.tpe == BlockType.INPUT_CONN.name or node_data.tpe == BlockType.OUTPUT_CONN.name:
            interface_block_uids.add(int(node_data.device_uid))
        else:
            filtered_node_data[node_uid] = node_data

    for child_block in export_block.children:
        if child_block.uid in interface_block_uids:
            pass
        else:
            filtered_children.append(child_block)

    for connection_uid, connection_data in export_block.diagram.con_data.items():
        if connection_data.from_uid in interface_block_uids or connection_data.to_uid in interface_block_uids:
            pass
        else:
            filtered_connection_data[connection_uid] = connection_data

    export_block.children = filtered_children
    export_block.diagram.node_data = filtered_node_data
    export_block.diagram.con_data = filtered_connection_data
    _apply_composite_child_interface_if_missing(export_block)
    return export_block


def export_user_dynamic_template_module_from_block(
        block: Block,
        output_path: str,
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        device_tpe: DeviceType,
        progress_callback: Callable[[int, str], None] | None = None,
) -> Path:
    """
    Export one editor block to one persisted Python user-template module.

    :param block: Exported symbolic block.
    :param output_path: Destination Python module path.
    :param template_name: Default runtime template name.
    :param target_domain: Selected RMS or EMT catalogue domain.
    :param device_tpe: Selected supported device type.
    :param progress_callback: Optional UI progress callback.
    :return: Written Python module path.
    """
    export_block: Block = build_user_dynamic_template_persistable_block(block)
    destination_path: Path = Path(output_path)
    module_text: str

    _emit_dynamic_model_import_progress(progress_callback, 0, "Preparing reusable Python template export...")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    _emit_dynamic_model_import_progress(progress_callback, 20, "Consolidating reusable block payload...")
    module_text = _build_user_dynamic_template_module_text(
        block=export_block,
        template_name=template_name,
        target_domain=target_domain,
        device_tpe=device_tpe,
    )
    _emit_dynamic_model_import_progress(progress_callback, 65, "Writing Python template module...")
    destination_path.write_text(module_text, encoding="utf-8")
    _emit_dynamic_model_import_progress(progress_callback, 100, "Reusable Python template saved")
    return destination_path


def _build_user_dynamic_template_payload_text(
        block: Block,
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        device_tpe: DeviceType,
        template_fingerprint: str | None = None,
) -> str:
    """
    Build the complete JSON validation snapshot before filesystem mutation.

    :param block: Persistable symbolic block.
    :param template_name: Final catalogue template name.
    :param target_domain: Selected RMS or EMT domain.
    :param device_tpe: Selected supported device type.
    :param template_fingerprint: Optional precomputed structural identity.
    :return: Deterministic JSON sidecar text.
    """
    payload: Dict[str, object] = dict()

    payload["template_name"] = template_name
    payload["target_domain"] = target_domain.value
    payload["device_tpe"] = device_tpe.name
    if template_fingerprint is None:
        pass
    else:
        payload["template_fingerprint"] = template_fingerprint
    payload["block_data"] = block.to_dict()
    payload["dgs_discrete_event_actions"] = (
        _serialize_dgs_discrete_event_actions(block=block)
    )
    payload["runtime_post_update_helper_names"] = (
        _serialize_runtime_post_update_helper_names(block=block)
    )
    payload["dgs_powerfactory_astable_integration"] = (
        _serialize_powerfactory_astable_integration(block=block)
    )
    direct_slot_interfaces_raw: object | None = block.__dict__.get(
        "dgs_direct_slot_interfaces",
        None,
    )
    if isinstance(direct_slot_interfaces_raw, list):
        payload["dgs_direct_slot_interfaces"] = direct_slot_interfaces_raw
    else:
        pass
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def _serialize_powerfactory_astable_integration(
        block: Block,
) -> List[Dict[str, object]]:
    """Serialize native per-model A-stable selectors by child path.

    :param block: Root symbolic block.
    :return: Enabled and disabled selector records with deterministic paths.
    """
    records: List[Dict[str, object]] = list()
    pending_blocks: List[Tuple[List[int], Block]] = list([(list(), block)])
    while len(pending_blocks) > 0:
        block_path: List[int]
        current_block: Block
        block_path, current_block = pending_blocks.pop(0)
        raw_selector: object | None = current_block.__dict__.get(
            "dgs_powerfactory_astable_integration",
            None,
        )
        if isinstance(raw_selector, bool):
            record: Dict[str, object] = dict()
            record["block_path"] = list(block_path)
            record["enabled"] = raw_selector
            records.append(record)
        else:
            pass
        child_index: int
        child_block: Block
        for child_index, child_block in enumerate(current_block.children):
            child_path: List[int] = list(block_path)
            child_path.append(child_index)
            pending_blocks.append((child_path, child_block))
        else:
            pass
    return records


def _restore_powerfactory_astable_integration(
        block: Block,
        raw_records: object,
) -> None:
    """Restore native per-model A-stable selectors from JSON records.

    :param block: Rebuilt root symbolic block.
    :param raw_records: Raw selector records.
    :return: None.
    """
    if isinstance(raw_records, list):
        raw_record: object
        for raw_record in raw_records:
            if isinstance(raw_record, dict):
                raw_block_path: object | None = raw_record.get(
                    "block_path",
                    None,
                )
                raw_enabled: object | None = raw_record.get("enabled", None)
                if isinstance(raw_block_path, list) and isinstance(
                        raw_enabled,
                        bool,
                ):
                    current_block: Block = block
                    valid_path: bool = True
                    raw_child_index: object
                    for raw_child_index in raw_block_path:
                        if (
                                isinstance(raw_child_index, int)
                                and not isinstance(raw_child_index, bool)
                                and 0 <= raw_child_index
                                and raw_child_index < len(current_block.children)
                        ):
                            current_block = current_block.children[
                                raw_child_index
                            ]
                        else:
                            valid_path = False
                    else:
                        pass
                    if valid_path:
                        current_block.__dict__[
                            "dgs_powerfactory_astable_integration"
                        ] = raw_enabled
                    else:
                        pass
                else:
                    pass
            else:
                pass
        else:
            pass
    else:
        pass


def _serialize_runtime_post_update_helper_names(
        block: Block,
) -> List[Dict[str, object]]:
    """
    Serialize procedural algebraic-closure declarations by child path.

    :param block: Root symbolic block.
    :return: Helper-name records with deterministic child-index paths.
    """
    records: List[Dict[str, object]] = list()
    pending_blocks: List[Tuple[List[int], Block]] = list([(list(), block)])
    while len(pending_blocks) > 0:
        block_path: List[int]
        current_block: Block
        block_path, current_block = pending_blocks.pop(0)
        raw_helper_names: object | None = current_block.__dict__.get(
            "runtime_post_update_helper_names",
            None,
        )
        if isinstance(raw_helper_names, list) and len(raw_helper_names) > 0:
            helper_names: List[str] = list()
            raw_helper_name: object
            for raw_helper_name in raw_helper_names:
                if isinstance(raw_helper_name, str) and raw_helper_name != "":
                    helper_names.append(raw_helper_name)
                else:
                    pass
            else:
                pass
            if len(helper_names) > 0:
                record: Dict[str, object] = dict()
                record["block_path"] = list(block_path)
                record["helper_names"] = helper_names
                records.append(record)
            else:
                pass
        else:
            pass

        child_index: int
        child_block: Block
        for child_index, child_block in enumerate(current_block.children):
            child_path: List[int] = list(block_path)
            child_path.append(child_index)
            pending_blocks.append((child_path, child_block))
        else:
            pass
    return records


def _restore_runtime_post_update_helper_names(
        block: Block,
        raw_records: object,
) -> None:
    """
    Restore procedural algebraic-closure declarations from JSON records.

    :param block: Rebuilt root symbolic block.
    :param raw_records: Raw serialized helper-name records.
    :return: None.
    """
    if isinstance(raw_records, list):
        raw_record: object
        for raw_record in raw_records:
            if isinstance(raw_record, dict):
                raw_block_path: object | None = raw_record.get(
                    "block_path",
                    None,
                )
                raw_helper_names: object | None = raw_record.get(
                    "helper_names",
                    None,
                )
                if isinstance(raw_block_path, list) and isinstance(
                        raw_helper_names,
                        list,
                ):
                    current_block: Block = block
                    valid_path: bool = True
                    raw_child_index: object
                    for raw_child_index in raw_block_path:
                        if (
                                isinstance(raw_child_index, int)
                                and not isinstance(raw_child_index, bool)
                                and 0 <= raw_child_index
                                and raw_child_index < len(current_block.children)
                        ):
                            current_block = current_block.children[
                                raw_child_index
                            ]
                        else:
                            valid_path = False
                    else:
                        pass
                    if valid_path:
                        helper_names: List[str] = list()
                        raw_helper_name: object
                        for raw_helper_name in raw_helper_names:
                            if (
                                    isinstance(raw_helper_name, str)
                                    and raw_helper_name != ""
                            ):
                                helper_names.append(raw_helper_name)
                            else:
                                pass
                        else:
                            pass
                        current_block.__dict__[
                            "runtime_post_update_helper_names"
                        ] = helper_names
                    else:
                        pass
                else:
                    pass
            else:
                pass
        else:
            pass
    else:
        pass


def _serialize_dgs_discrete_event_actions(
        block: Block,
) -> List[Dict[str, object]]:
    """
    Serialize deferred DGS actions without coupling ``Block`` to DGS imports.

    :param block: Root symbolic block.
    :return: Action records with deterministic child-index paths.
    """
    records: List[Dict[str, object]] = list()
    pending_blocks: List[Tuple[List[int], Block]] = list([(
        list(),
        block,
    )])
    while len(pending_blocks) > 0:
        block_path: List[int]
        current_block: Block
        block_path, current_block = pending_blocks.pop(0)
        raw_actions: object | None = current_block.__dict__.get(
            "dgs_discrete_event_actions",
            None,
        )
        if isinstance(raw_actions, list):
            raw_action: object
            for raw_action in raw_actions:
                if isinstance(raw_action, DgsDiscreteEventAction):
                    record: Dict[str, object] = raw_action.to_dict()
                    record["block_path"] = list(block_path)
                    records.append(record)
                else:
                    pass
        else:
            pass

        child_index: int
        child_block: Block
        for child_index, child_block in enumerate(current_block.children):
            child_path: List[int] = list(block_path)
            child_path.append(child_index)
            pending_blocks.append((child_path, child_block))
    return records


def _restore_dgs_discrete_event_actions(
        block: Block,
        raw_records: object,
) -> None:
    """
    Restore optional deferred DGS actions onto their exact child blocks.

    :param block: Root block rebuilt from the generic JSON snapshot.
    :param raw_records: Parsed optional action records.
    :return: None.
    """
    if isinstance(raw_records, list):
        records: List[object] = raw_records
    else:
        records = list()

    raw_record: object
    for raw_record in records:
        if isinstance(raw_record, dict):
            record: Dict[str, object] = raw_record
            raw_path: object | None = record.get("block_path", None)
            action: DgsDiscreteEventAction | None = (
                dgs_discrete_event_action_from_dict(payload=record)
            )
            path_ready: bool = isinstance(raw_path, list)
        else:
            record = dict()
            raw_path = None
            action = None
            path_ready = False

        target_block: Block = block
        if path_ready and isinstance(raw_path, list):
            raw_child_index: object
            for raw_child_index in raw_path:
                child_index_ready: bool = (
                    isinstance(raw_child_index, int)
                    and not isinstance(raw_child_index, bool)
                    and raw_child_index >= 0
                    and raw_child_index < len(target_block.children)
                )
                if child_index_ready:
                    target_block = target_block.children[raw_child_index]
                else:
                    path_ready = False
        else:
            pass

        if path_ready and action is not None:
            target_actions_raw: object | None = target_block.__dict__.get(
                "dgs_discrete_event_actions",
                None,
            )
            if isinstance(target_actions_raw, list):
                target_actions: List[object] = target_actions_raw
            else:
                target_actions = list()
                target_block.__dict__["dgs_discrete_event_actions"] = target_actions
            target_actions.append(action)
        else:
            pass


def _try_remove_catalog_transaction_file(path: Path) -> bool:
    """
    Remove one regular transaction artifact without masking the primary result.

    :param path: Temporary or backup artifact path.
    :return: ``True`` when the path is absent after the cleanup attempt.
    """
    removed: bool

    if path.exists():
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                removed = False
            else:
                removed = True
        else:
            removed = False
    else:
        removed = True

    return removed


def _try_rollback_catalog_transaction_target(
        target_path: Path,
        backup_path: Path,
        original_existed: bool,
        backup_created: bool,
        new_published: bool,
) -> bool:
    """
    Restore one target after a failed two-file catalogue transaction.

    :param target_path: Final catalogue artifact path.
    :param backup_path: Transaction backup path.
    :param original_existed: Whether a prior final artifact existed.
    :param backup_created: Whether that prior artifact reached the backup path.
    :param new_published: Whether the new artifact reached the final path.
    :return: ``True`` when the target returned to its pre-transaction state.
    """
    restored: bool = True

    if backup_created:
        if target_path.exists():
            restored = _try_remove_catalog_transaction_file(path=target_path)
        else:
            pass

        if restored and backup_path.is_file():
            try:
                backup_path.replace(target_path)
            except OSError:
                restored = False
            else:
                restored = True
        else:
            if restored:
                restored = False
            else:
                pass
    else:
        if original_existed:
            # The original never moved, so no action is required.
            pass
        else:
            if new_published:
                restored = _try_remove_catalog_transaction_file(path=target_path)
            else:
                pass

    return restored


def _write_user_dynamic_template_module_transactionally(
        module_output_path: Path,
        module_text: str,
) -> None:
    """Atomically publish one canonical Python catalogue module.

    This path is used for massive DGS catalogues, where the executable,
    human-readable Python source already contains the complete model and an
    additional full-graph JSON snapshot would be pure duplication.

    :param module_output_path: Final canonical Python module path.
    :param module_text: Complete syntax-validated Python module text.
    :return: None.
    """
    transaction_token: str = uuid.uuid4().hex
    temporary_path: Path = module_output_path.with_name(
        f"{module_output_path.name}.transaction-{transaction_token}.tmp"
    )
    backup_path: Path = module_output_path.with_name(
        f"{module_output_path.name}.transaction-{transaction_token}.bak"
    )
    original_existed: bool = module_output_path.exists()
    backup_created: bool = False
    published: bool = False
    restored: bool

    # Refuse non-file collisions before preparing an atomic replacement.
    if original_existed:
        if module_output_path.is_file():
            pass
        else:
            raise IsADirectoryError(str(module_output_path))
    else:
        pass

    module_output_path.parent.mkdir(parents=True, exist_ok=True)
    compile(module_text, str(module_output_path), "exec")
    try:
        temporary_path.write_text(module_text, encoding="utf-8")
    except OSError:
        _try_remove_catalog_transaction_file(path=temporary_path)
        raise
    else:
        pass

    try:
        if original_existed:
            module_output_path.replace(backup_path)
            backup_created = True
        else:
            pass
        temporary_path.replace(module_output_path)
        published = True
    except OSError as exc:
        restored = _try_rollback_catalog_transaction_target(
            target_path=module_output_path,
            backup_path=backup_path,
            original_existed=original_existed,
            backup_created=backup_created,
            new_published=published,
        )
        _try_remove_catalog_transaction_file(path=temporary_path)
        if restored:
            raise
        else:
            raise OSError(
                f"Catalogue module publication and rollback both failed for {module_output_path}"
            ) from exc
    else:
        _try_remove_catalog_transaction_file(path=backup_path)
        _try_remove_catalog_transaction_file(path=temporary_path)


def _write_user_dynamic_template_catalog_pair_transactionally(
        module_output_path: Path,
        module_text: str,
        payload_text: str,
) -> None:
    """
    Atomically replace the canonical Python module and JSON snapshot as one pair.

    Both complete texts are written to same-directory temporary files first.
    Existing artifacts move to transaction-specific backups before publication;
    any failed publication restores both prior files or removes both new files.

    :param module_output_path: Final canonical Python module path.
    :param module_text: Complete validated Python module text.
    :param payload_text: Complete JSON snapshot text.
    :return: None.
    """
    payload_output_path: Path = module_output_path.with_suffix(".payload.json")
    transaction_token: str = uuid.uuid4().hex
    module_temporary_path: Path = module_output_path.with_name(
        f"{module_output_path.name}.transaction-{transaction_token}.tmp"
    )
    payload_temporary_path: Path = payload_output_path.with_name(
        f"{payload_output_path.name}.transaction-{transaction_token}.tmp"
    )
    module_backup_path: Path = module_output_path.with_name(
        f"{module_output_path.name}.transaction-{transaction_token}.bak"
    )
    payload_backup_path: Path = payload_output_path.with_name(
        f"{payload_output_path.name}.transaction-{transaction_token}.bak"
    )
    module_original_existed: bool = module_output_path.exists()
    payload_original_existed: bool = payload_output_path.exists()
    module_backup_created: bool = False
    payload_backup_created: bool = False
    module_published: bool = False
    payload_published: bool = False
    module_restored: bool
    payload_restored: bool

    # Reject non-file targets before creating temporaries so the catalogue never
    # converts a user directory or another filesystem object into a model file.
    if module_original_existed:
        if module_output_path.is_file():
            pass
        else:
            raise IsADirectoryError(str(module_output_path))
    else:
        pass

    if payload_original_existed:
        if payload_output_path.is_file():
            pass
        else:
            raise IsADirectoryError(str(payload_output_path))
    else:
        pass

    module_output_path.parent.mkdir(parents=True, exist_ok=True)
    compile(module_text, str(module_output_path), "exec")

    # Preparation happens entirely outside the final names.  A preparation
    # failure therefore cannot leave either member of the published pair.
    try:
        module_temporary_path.write_text(module_text, encoding="utf-8")
        payload_temporary_path.write_text(payload_text, encoding="utf-8")
    except OSError:
        _try_remove_catalog_transaction_file(path=module_temporary_path)
        _try_remove_catalog_transaction_file(path=payload_temporary_path)
        raise
    else:
        pass

    try:
        if module_original_existed:
            module_output_path.replace(module_backup_path)
            module_backup_created = True
        else:
            pass

        if payload_original_existed:
            payload_output_path.replace(payload_backup_path)
            payload_backup_created = True
        else:
            pass

        # Publish the JSON snapshot first and the canonical Python module last.
        # The module remains the catalogue's primary artifact and commit point.
        payload_temporary_path.replace(payload_output_path)
        payload_published = True
        module_temporary_path.replace(module_output_path)
        module_published = True
    except OSError as exc:
        module_restored = _try_rollback_catalog_transaction_target(
            target_path=module_output_path,
            backup_path=module_backup_path,
            original_existed=module_original_existed,
            backup_created=module_backup_created,
            new_published=module_published,
        )
        payload_restored = _try_rollback_catalog_transaction_target(
            target_path=payload_output_path,
            backup_path=payload_backup_path,
            original_existed=payload_original_existed,
            backup_created=payload_backup_created,
            new_published=payload_published,
        )
        _try_remove_catalog_transaction_file(path=module_temporary_path)
        _try_remove_catalog_transaction_file(path=payload_temporary_path)

        if module_restored and payload_restored:
            raise
        else:
            raise OSError(
                f"Catalogue pair publication and rollback both failed for {module_output_path}"
            ) from exc
    else:
        # Backups are outside loader globs and can be safely cleaned only after
        # both final paths have been published successfully.
        _try_remove_catalog_transaction_file(path=module_backup_path)
        _try_remove_catalog_transaction_file(path=payload_backup_path)
        _try_remove_catalog_transaction_file(path=module_temporary_path)
        _try_remove_catalog_transaction_file(path=payload_temporary_path)


def save_user_dynamic_template_module_to_catalog(
        block: Block,
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        device_tpe: DeviceType,
        catalog_root_folder: str | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
        template_fingerprint: str | None = None,
        include_validation_snapshot: bool = True,
) -> Path:
    """
    Save one editor block directly into the persistent VeraGrid user catalogue.

    :param block: Exported symbolic block.
    :param template_name: Default runtime template name.
    :param target_domain: Selected RMS or EMT catalogue domain.
    :param device_tpe: Selected supported device type.
    :param catalog_root_folder: Optional explicit VeraGrid user root used mainly by tests.
    :param progress_callback: Optional UI progress callback.
    :param template_fingerprint: Optional precomputed structural identity.
    :param include_validation_snapshot: Persist the optional JSON validation sidecar.
    :return: Collision-safe written catalogue module path.
    """
    persistable_block: Block
    module_text: str
    payload_text: str | None
    output_path: Path
    current_output_path: Path | None
    can_emit_read_only: bool

    if template_fingerprint is None:
        current_output_path = None
    else:
        current_output_path = _find_current_user_dynamic_template_catalog_module(
            template_name=template_name,
            target_domain=target_domain,
            device_tpe=device_tpe,
            template_fingerprint=template_fingerprint,
            catalog_root_folder=catalog_root_folder,
        )

    if current_output_path is None:
        pass
    else:
        _emit_dynamic_model_import_progress(
            progress_callback,
            100,
            "Reusable Python template already current",
        )
        return current_output_path

    _emit_dynamic_model_import_progress(progress_callback, 0, "Preparing transactional catalogue export...")
    # Massive DGS imports already materialize canonical, wrapper-free blocks.
    # Emit those graphs read-only instead of recursively cloning every OEM
    # expression tree a second time. Editor wrappers and loaded runtime-suffix
    # templates retain the established normalization/copy path.
    can_emit_read_only = _can_build_dynamic_import_canonical_text_read_only(
        block=block,
        template_name=template_name,
    )
    if can_emit_read_only:
        persistable_block = block
    else:
        persistable_block = build_user_dynamic_template_persistable_block(block)
    module_text = _build_user_dynamic_template_module_text(
        block=persistable_block,
        template_name=template_name,
        target_domain=target_domain,
        device_tpe=device_tpe,
    )
    # The compact comment is part of the canonical Python artifact and makes
    # massive catalogue imports resumable without a redundant JSON graph.
    module_text = (
        _build_user_dynamic_template_module_identity_header(
            template_name=template_name,
            target_domain=target_domain,
            device_tpe=device_tpe,
            template_fingerprint=template_fingerprint,
        )
        + module_text
    )
    if include_validation_snapshot:
        payload_text = _build_user_dynamic_template_payload_text(
            block=persistable_block,
            template_name=template_name,
            target_domain=target_domain,
            device_tpe=device_tpe,
            template_fingerprint=template_fingerprint,
        )
    else:
        payload_text = None
    _emit_dynamic_model_import_progress(progress_callback, 35, "Resolving collision-safe catalogue identity...")
    output_path = _resolve_user_dynamic_template_catalog_output_path(
        block=persistable_block,
        template_name=template_name,
        target_domain=target_domain,
        device_tpe=device_tpe,
        module_text=module_text,
        catalog_root_folder=catalog_root_folder,
        template_fingerprint=template_fingerprint,
    )
    if payload_text is None:
        _emit_dynamic_model_import_progress(
            progress_callback,
            65,
            "Publishing canonical Python catalogue module...",
        )
        _write_user_dynamic_template_module_transactionally(
            module_output_path=output_path,
            module_text=module_text,
        )
        _emit_dynamic_model_import_progress(
            progress_callback,
            100,
            "Reusable Python template saved",
        )
    else:
        _emit_dynamic_model_import_progress(
            progress_callback,
            65,
            "Publishing Python and JSON catalogue pair...",
        )
        _write_user_dynamic_template_catalog_pair_transactionally(
            module_output_path=output_path,
            module_text=module_text,
            payload_text=payload_text,
        )
        _emit_dynamic_model_import_progress(
            progress_callback,
            100,
            "Reusable Python template and snapshot saved",
        )
    return output_path


def export_user_dynamic_template_json_from_block(
        block: Block,
        output_path: str,
        template_name: str,
        target_domain: DynamicModelImportTargetDomain,
        device_tpe: DeviceType,
        progress_callback: Callable[[int, str], None] | None = None,
) -> Path:
    """
    Export one editor block to one standalone JSON payload.

    :param block: Exported symbolic block.
    :param output_path: Destination JSON file path.
    :param template_name: Default runtime template name.
    :param target_domain: Selected RMS or EMT catalogue domain.
    :param device_tpe: Selected supported device type.
    :param progress_callback: Optional UI progress callback.
    :return: Written JSON file path.
    """
    export_block: Block = copy.deepcopy(block)
    destination_path: Path = Path(output_path)
    payload_text: str

    _emit_dynamic_model_import_progress(progress_callback, 0, "Preparing JSON snapshot export...")
    _apply_composite_child_interface_if_missing(export_block)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    _emit_dynamic_model_import_progress(progress_callback, 25, "Serializing block snapshot...")
    payload_text = _build_user_dynamic_template_payload_text(
        block=export_block,
        template_name=template_name,
        target_domain=target_domain,
        device_tpe=device_tpe,
    )
    _emit_dynamic_model_import_progress(progress_callback, 75, "Writing JSON snapshot...")
    destination_path.write_text(payload_text, encoding="utf-8")
    _emit_dynamic_model_import_progress(progress_callback, 100, "JSON snapshot saved")
    return destination_path


def load_user_dynamic_template_json_payload(
        json_path: str,
        progress_callback: Callable[[int, str], None] | None = None,
) -> Tuple[Block, str, DynamicModelImportTargetDomain, DeviceType] | None:
    """
    Load one intermediate JSON snapshot exported from the dynamic block editor.

    :param json_path: Source JSON snapshot path.
    :param progress_callback: Optional UI progress callback.
    :return: Tuple ``(block, template_name, target_domain, device_tpe)`` or ``None`` when the payload is invalid.
    """
    _emit_dynamic_model_import_progress(progress_callback, 0, "Reading JSON snapshot...")
    payload_text: str = Path(json_path).read_text(encoding="utf-8")
    _emit_dynamic_model_import_progress(progress_callback, 20, "Parsing JSON snapshot...")
    payload_obj = json.loads(payload_text)
    block_data_obj = None
    template_name_obj = None
    target_domain_obj = None
    device_tpe_obj = None
    dgs_discrete_event_actions_obj = None
    dgs_direct_slot_interfaces_obj = None
    runtime_post_update_helper_names_obj = None
    powerfactory_astable_integration_obj: object | None = None
    template_name: str
    target_domain: DynamicModelImportTargetDomain
    device_tpe: DeviceType
    block: Block

    if isinstance(payload_obj, dict):
        block_data_obj = payload_obj.get("block_data", None)
        template_name_obj = payload_obj.get("template_name", None)
        target_domain_obj = payload_obj.get("target_domain", None)
        device_tpe_obj = payload_obj.get("device_tpe", None)
        dgs_discrete_event_actions_obj = payload_obj.get(
            "dgs_discrete_event_actions",
            None,
        )
        dgs_direct_slot_interfaces_obj = payload_obj.get(
            "dgs_direct_slot_interfaces",
            None,
        )
        runtime_post_update_helper_names_obj = payload_obj.get(
            "runtime_post_update_helper_names",
            None,
        )
        powerfactory_astable_integration_obj = payload_obj.get(
            "dgs_powerfactory_astable_integration",
            None,
        )
    else:
        return None

    if isinstance(block_data_obj, dict):
        _emit_dynamic_model_import_progress(progress_callback, 55, "Rebuilding symbolic block from JSON...")
        block = Block.parse(block_data_obj)
        _restore_dgs_discrete_event_actions(
            block=block,
            raw_records=dgs_discrete_event_actions_obj,
        )
        _restore_runtime_post_update_helper_names(
            block=block,
            raw_records=runtime_post_update_helper_names_obj,
        )
        _restore_powerfactory_astable_integration(
            block=block,
            raw_records=powerfactory_astable_integration_obj,
        )
        if isinstance(dgs_direct_slot_interfaces_obj, list):
            # The JSON sidecar mirrors the canonical Python adapter contract so
            # structural validation compares the same physical model surface.
            block.__dict__["dgs_direct_slot_interfaces"] = (
                dgs_direct_slot_interfaces_obj
            )
        else:
            pass
    else:
        return None

    if isinstance(template_name_obj, str):
        template_name = template_name_obj.strip()
    else:
        template_name = ""

    if len(template_name) == 0:
        template_name = block.name.strip()
    else:
        pass

    if len(template_name) == 0:
        template_name = Path(json_path).stem
    else:
        pass

    if target_domain_obj == DynamicModelImportTargetDomain.Rms.value:
        target_domain = DynamicModelImportTargetDomain.Rms
    else:
        if target_domain_obj == DynamicModelImportTargetDomain.Emt.value:
            target_domain = DynamicModelImportTargetDomain.Emt
        else:
            return None

    if isinstance(device_tpe_obj, str):
        if device_tpe_obj in DeviceType.__members__:
            device_tpe = DeviceType[device_tpe_obj]
