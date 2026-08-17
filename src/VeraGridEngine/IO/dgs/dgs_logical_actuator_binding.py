from __future__ import annotations

import math
from typing import Dict, List

from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.dgs.dynamic_models.dgs_dynamic_association import DgsDynamicAssociation, \
    DgsDynamicAssociationRole
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Devices.Branches.series_reactance import SeriesReactance
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import DGSElement, ElmComp, ElmSind, StaVmea
from VeraGridEngine.IO.dgs.dgs_rms_measurement_binding import (
    _build_dgs_element_index,
    _resolve_terminal_id,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var, heaviside
from VeraGridEngine.enumerations import (

    ParamPowerFlowReferenceType,
)


def _association_slot_sort_key(association: DgsDynamicAssociation) -> int:
    """Return the exported frame order of one association.

    :param association: Persisted DGS association.
    :return: Source slot index, with absent indices sorted last.
    """
    slot_index: int | None = association.get_slot_index()
    if slot_index is None:
        return 2_147_483_647
    else:
        return slot_index


def _find_common_passive_bus(
        lines: List[Line | SeriesReactance],
) -> Bus | None:
    """Find the shared neutral node of one multi-branch passive actuator.

    :param lines: Passive branches referenced by one logical composite.
    :return: Shared or grounded bus, or ``None`` when topology is ambiguous.
    """
    endpoint_counts: Dict[Bus, int] = dict()
    line: Line | SeriesReactance
    endpoint_bus: Bus
    for line in lines:
        for endpoint_bus in list([line.bus_from, line.bus_to]):
            endpoint_count: int | None = endpoint_counts.get(endpoint_bus, None)
            if endpoint_count is None:
                endpoint_counts[endpoint_bus] = 1
            else:
                endpoint_counts[endpoint_bus] = endpoint_count + 1

    common_bus: Bus | None = None
    common_count: int = 0
    candidate_bus: Bus
    candidate_count: int
    for candidate_bus, candidate_count in endpoint_counts.items():
        if candidate_bus.is_grounded and candidate_count >= common_count:
            common_bus = candidate_bus
            common_count = candidate_count
        else:
            if candidate_count > common_count and candidate_count > 1:
                common_bus = candidate_bus
                common_count = candidate_count
            else:
                pass
    return common_bus


def synchronize_dgs_logical_actuator_service_states(
        circuit: MultiCircuit,
        dgs_circuit: DgsCircuit,
        logger: Logger,
) -> int:
    """Apply each source ``ElmComp.outserv`` state to its complete RMS group.

    A composite controller is not physical equipment. Its service state must
    therefore be retained on the logical association instead of changing the
    static host device. Matching by the exported FID keeps identical display
    names and structurally deduplicated templates independent.

    :param circuit: Imported circuit containing logical DGS associations.
    :param dgs_circuit: Parsed source DGS tables.
    :param logger: Import diagnostic sink.
    :return: Number of logical associations synchronized.
    """
    composite_by_id: Dict[str, ElmComp] = dict()
    source_composite: ElmComp
    for source_composite in dgs_circuit.elmcomps:
        composite_by_id[str(source_composite.ID)] = source_composite

    synchronized_count: int = 0
    association: DgsDynamicAssociation
    for association in circuit.get_dgs_dynamic_associations():
        source_root: ElmComp | None = composite_by_id.get(
            association.root_dgs_id,
            None,
        )
        if source_root is None:
            if association.role == DgsDynamicAssociationRole.CompositeController:
                logger.add_warning(
                    msg="DGS logical controller service state could not be resolved",
                    device=association.name,
                    value=association.root_dgs_id,
                )
            else:
                pass
        else:
            # PowerFactory initialises a composite only when its controller,
            # measurement and actuator slots participate as one atomic group.
            association.active = int(source_root.outserv) == 0
            synchronized_count += 1

    return synchronized_count


def set_dgs_logical_actuator_service_state(
        circuit: MultiCircuit,
        root_dgs_id: str,
        in_service: bool,
) -> int:
    """Set one logical composite, every slot and passive shell in service.

    This operation is intended before constructing an RMS problem. The fixed
    DAE then contains either the complete controller-actuator system or none of
    it, matching PowerFactory's study-case service selection without changing
    the physical network representation.

    :param circuit: Circuit containing the imported logical composite.
    :param root_dgs_id: Exact owning ``ElmComp`` FID.
    :param in_service: Whether the controller participates in the next run.
    :return: Number of logical associations and passive branches updated.
    """
    updated_count: int = 0
    association: DgsDynamicAssociation
    for association in circuit.get_dgs_dynamic_associations():
        is_target_root: bool = association.root_dgs_id == root_dgs_id
        if is_target_root:
            association.active = in_service
            updated_count += 1
        else:
            pass

    physical_branch: object
    for physical_branch in circuit.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=False,
    ):
        if isinstance(physical_branch, (Line, SeriesReactance)):
            actuator_root_raw: object | None = physical_branch.rms_model.__dict__.get(
                "dgs_logical_actuator_root_id",
                None,
            )
            if actuator_root_raw == root_dgs_id:
                physical_branch.rms_model.__dict__["rms_force_compile"] = in_service
                updated_count += 1
            else:
                pass
        else:
            pass

    return updated_count


def _collect_unique_named_vars(block: Block, variable_name: str) -> List[Var]:
    """Collect UID-distinct variables carrying one exact exported name.

    :param block: Imported logical controller root.
    :param variable_name: Exact PowerFactory interface name.
    :return: UID-distinct matching variables.
    """
    matches_by_uid: Dict[int, Var] = dict()
    child_block: Block
    variable_collections: List[List[Var]]
    variable_collection: List[Var]
    variable: Var
    for child_block in block.get_all_blocks():
        variable_collections = list([
            child_block.in_vars,
            child_block.out_vars,
            child_block.state_vars,
            child_block.algebraic_vars,
            list(child_block.event_dict.keys()),
            list(child_block.parameters.keys()),
            list(child_block.init_eqs.keys()),
        ])
        for variable_collection in variable_collections:
            for variable in variable_collection:
                if variable.name == variable_name:
                    matches_by_uid[variable.uid] = variable
                else:
                    pass
    return list(matches_by_uid.values())


def _collect_unique_exported_leaf_vars(
        block: Block,
        variable_name: str,
) -> List[Var]:
    """Collect exact interface variables and humanized child-name variants.

    :param block: Imported logical controller root.
    :param variable_name: Exported PowerFactory leaf identifier.
    :return: UID-distinct variables with the requested semantic leaf name.
    """
    matches_by_uid: Dict[int, Var] = dict()
    child_block: Block
    variable_collections: List[List[Var]]
    variable_collection: List[Var]
    variable: Var
    for child_block in block.get_all_blocks():
        variable_collections = list([
            child_block.in_vars,
            child_block.out_vars,
            child_block.state_vars,
            child_block.algebraic_vars,
            list(child_block.event_dict.keys()),
            list(child_block.parameters.keys()),
            list(child_block.init_eqs.keys()),
        ])
        for variable_collection in variable_collections:
            for variable in variable_collection:
                is_exact_name: bool = variable.name == variable_name
                is_humanized_child_name: bool = variable.name.endswith(
                    "__" + variable_name
                )
                if is_exact_name or is_humanized_child_name:
                    matches_by_uid[variable.uid] = variable
                else:
                    pass
    return list(matches_by_uid.values())


def _seed_open_resistive_actuator(
        block: Block,
        open_resistance_ohm: float | None = None,
) -> None:
    """Seed an open gated resistor from its exported physical resistance.

    PowerFactory models can leave ``inc(R)=inc(Rinc)=inc(xR)`` as a neutral
    initialization cycle because the physical valve is open. VeraGrid still
    needs a deterministic state before that valve first closes. The exported
    An enriched DGS carries the physical ``ElmSind.s:Rin`` boundary and that
    value has precedence. Older DGS files omit it, so the exported ``Rmax``
    runtime equation remains a deterministic compatibility fallback. A late
    symbolic seed copies the selected value only after all DGS parameters and
    procedural mode selectors have been initialized.

    :param block: Imported logical controller root.
    :param open_resistance_ohm: Optional native open resistance in Ohm.
    :return: None.
    """
    maximum_vars: List[Var] = _collect_unique_exported_leaf_vars(
        block=block,
        variable_name="Rmax",
    )
    target_vars: List[Var] = list()
    complete_target_set: bool = True
    target_name: str
    for target_name in list(["R", "Rinc", "Rx", "xR"]):
        named_vars: List[Var] = _collect_unique_exported_leaf_vars(
            block=block,
            variable_name=target_name,
        )
        if len(named_vars) > 0:
            target_var: Var
            for target_var in named_vars:
                target_vars.append(target_var)
        else:
            complete_target_set = False

    has_physical_seed: bool = (
            open_resistance_ohm is not None
            and math.isfinite(open_resistance_ohm)
            and open_resistance_ohm > 0.0
    )
    if has_physical_seed:
        seed_expression: Expr | None = Const(float(open_resistance_ohm))
    else:
        if len(maximum_vars) == 1:
            seed_expression = maximum_vars[0]
        else:
            seed_expression = None

    if seed_expression is not None and complete_target_set:
        target_var: Var
        for target_var in target_vars:
            block.post_init_seed_eqs[target_var] = seed_expression
            is_initial_resistance: bool = (
                    target_var.name == "Rinc"
                    or target_var.name.endswith("__Rinc")
            )
            if is_initial_resistance:
                child_block: Block
                for child_block in block.get_all_blocks():
                    if target_var in child_block.event_dict:
                        # ``inc(Rinc)=R`` is an initialization assignment, not
                        # a continuous algebraic equation. Retain the resolved
                        # off-state value after the startup pass.
                        child_block.event_dict[target_var] = seed_expression
                    else:
                        pass
            else:
                pass
    else:
        pass


def prepare_dgs_logical_actuator_topology(
        circuit: MultiCircuit,
        dgs_circuit: DgsCircuit,
        logger: Logger,
) -> int:
    """Reconstruct zero-impedance valve placement for logical composites.

    PowerFactory frames may export valve slots without physical ``ElmValve``
    rows. The paired passive branch and voltage-measurement terminals still
    define the exact series topology. Replacing the isolated valve-side node by
    the measured rail is electrically equivalent once the passive RMS branch
    receives the exported gate status.

    :param circuit: Imported VeraGrid circuit.
    :param dgs_circuit: Parsed source DGS tables.
    :param logger: Import diagnostic sink.
    :return: Number of passive actuator branches prepared for RMS.
    """
    associations: List[DgsDynamicAssociation] = circuit.get_dgs_dynamic_associations()
    dgs_element_by_id: Dict[str, DGSElement] = _build_dgs_element_index(
        dgs_circuit=dgs_circuit,
    )

    bus_by_id: Dict[str, Bus] = dict()
    bus: Bus
    for bus in circuit.buses:
        bus_by_id[str(bus.idtag)] = bus

    line_by_id: Dict[str, Line | SeriesReactance] = dict()
    physical_branch: object
    for physical_branch in circuit.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=False,
    ):
        if isinstance(physical_branch, (Line, SeriesReactance)):
            line_by_id[str(physical_branch.idtag)] = physical_branch
        else:
            pass

    prepared_count: int = 0
    root_association: DgsDynamicAssociation
    for root_association in associations:
        if (
                root_association.role == DgsDynamicAssociationRole.CompositeController
                and not root_association.rms_model.empty()
        ):
            root_id: str = root_association.root_dgs_id
            passive_associations: List[DgsDynamicAssociation] = list()
            voltage_associations: List[DgsDynamicAssociation] = list()
            candidate_association: DgsDynamicAssociation
            for candidate_association in associations:
                if candidate_association.root_dgs_id == root_id:
                    if candidate_association.role == DgsDynamicAssociationRole.PassiveActuator:
                        passive_associations.append(candidate_association)
                    else:
                        source_element_id: str | None = candidate_association.get_source_element_dgs_id()
                        source_element: DGSElement | None = (
                            dgs_element_by_id.get(source_element_id, None)
                            if source_element_id is not None
                            else None
                        )
                        if (
                                candidate_association.role == DgsDynamicAssociationRole.Measurement
                                and isinstance(source_element, StaVmea)
                        ):
                            voltage_associations.append(candidate_association)
                        else:
                            pass
                else:
                    pass

            passive_associations.sort(key=_association_slot_sort_key)
            voltage_associations.sort(key=_association_slot_sort_key)
            passive_lines: List[Line | SeriesReactance] = list()
            passive_association: DgsDynamicAssociation
            for passive_association in passive_associations:
                passive_source_id: str | None = passive_association.get_source_element_dgs_id()
                passive_line: Line | SeriesReactance | None = (
                    line_by_id.get(passive_source_id, None)
                    if passive_source_id is not None
                    else None
                )
                if passive_line is None:
                    pass
                else:
                    passive_lines.append(passive_line)

            common_bus: Bus | None = _find_common_passive_bus(lines=passive_lines)
            if (
                    common_bus is None
                    or len(passive_lines) == 0
                    or len(passive_lines) != len(voltage_associations)
            ):
                if len(passive_lines) > 0:
                    logger.add_warning(
                        msg="DGS logical actuator topology is ambiguous",
                        device=root_association.name,
                        value=len(passive_lines),
                        expected_value=len(voltage_associations),
                    )
                else:
                    pass
            else:
                pair_index: int
                for pair_index, passive_line in enumerate(passive_lines):
                    voltage_source_id: str | None = voltage_associations[
                        pair_index
                    ].get_source_element_dgs_id()
                    voltage_meter: DGSElement | None = (
                        dgs_element_by_id.get(voltage_source_id, None)
                        if voltage_source_id is not None
                        else None
                    )
                    terminal_id: str | None = (
                        _resolve_terminal_id(
                            pointer_id=voltage_meter.pbusbar,
                            dgs_element_by_id=dgs_element_by_id,
                        )
                        if isinstance(voltage_meter, StaVmea)
                        else None
                    )
                    rail_bus: Bus | None = (
                        bus_by_id.get(terminal_id, None)
                        if terminal_id is not None
                        else None
                    )
                    if rail_bus is None:
                        logger.add_warning(
                            msg="DGS logical actuator rail could not be resolved",
                            device=passive_line.name,
                            value=voltage_source_id,
                        )
                    else:
                        if passive_line.bus_from is common_bus:
                            passive_line.bus_to = rail_bus
                        else:
                            if passive_line.bus_to is common_bus:
                                passive_line.bus_from = rail_bus
                            else:
                                logger.add_warning(
                                    msg="DGS passive actuator does not touch the shared node",
                                    device=passive_line.name,
                                    value=root_id,
                                )
                        existing_template: RmsModelTemplate | None = passive_line.rms_template
                        if isinstance(existing_template, RmsModelTemplate):
                            # The first shell was connected to the source's
                            # valve-side placeholder bus. Reassigning the same
                            # template reconnects it to the resolved rail.
                            passive_line.rms_template = existing_template

                            # The retained impedance is only one part of the
                            # PowerFactory valve-plus-impedance assembly. An
                            # exported in-service ElmSind must therefore not
                            # enter the static power flow by itself when the
                            # omitted ElmValve is open. Keep the physical shell
                            # out of the static admittance matrix and compile it
                            # explicitly for RMS, where gate and resistance are
                            # projected from the logical controller.
                            passive_line.active = False
                            passive_line.rms_model.__dict__["rms_force_compile"] = (
                                root_association.active
                            )
                            passive_line.rms_model.__dict__["dgs_logical_actuator_root_id"] = root_id
                            passive_source_id: str | None = passive_associations[
                                pair_index
                            ].get_source_element_dgs_id()
                            passive_source_element: DGSElement | None = (
                                dgs_element_by_id.get(passive_source_id, None)
                                if passive_source_id is not None
                                else None
                            )
                            if (
                                    isinstance(passive_source_element, ElmSind)
                                    and passive_source_element.Rin is not None
                                    and math.isfinite(passive_source_element.Rin)
                                    and passive_source_element.Rin > 0.0
                            ):
                                passive_line.rms_model.__dict__["dgs_open_resistance_ohm"] = float(
                                    passive_source_element.Rin
                                )
                            else:
                                pass
                            prepared_count += 1
                        else:
                            logger.add_warning(
                                msg="DGS passive actuator has no RMS template",
                                device=passive_line.name,
                                value=root_id,
                            )
        else:
            pass
    return prepared_count


def bind_dgs_logical_actuator_runtime(
        circuit: MultiCircuit,
        logger: Logger,
) -> int:
    """Bind logical gate and resistance outputs to prepared passive branches.

    :param circuit: Imported circuit after standard RMS shell preparation.
    :param logger: Import diagnostic sink.
    :return: Number of passive actuator RMS models bound.
    """
    root_by_id: Dict[str, DgsDynamicAssociation] = dict()
    association: DgsDynamicAssociation
    for association in circuit.get_dgs_dynamic_associations():
        if (
                association.role == DgsDynamicAssociationRole.CompositeController
                and not association.rms_model.empty()
        ):
            root_by_id[association.root_dgs_id] = association
        else:
            pass

    # Resolve one coherent physical open resistance per composite before any
    # controller is seeded. Conflicting pole values remain explicit and use
    # the model-defined Rmax compatibility path.
    open_resistance_by_root_id: Dict[str, float] = dict()
    conflicting_open_resistance_root_ids: set[str] = set()
    candidate_branch: object
    for candidate_branch in circuit.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=False,
    ):
        if isinstance(candidate_branch, (Line, SeriesReactance)):
            candidate_root_raw: object | None = candidate_branch.rms_model.__dict__.get(
                "dgs_logical_actuator_root_id",
                None,
            )
            candidate_resistance_raw: object | None = candidate_branch.rms_model.__dict__.get(
                "dgs_open_resistance_ohm",
                None,
            )
            if (
                    isinstance(candidate_root_raw, str)
                    and isinstance(candidate_resistance_raw, (int, float))
                    and math.isfinite(float(candidate_resistance_raw))
                    and float(candidate_resistance_raw) > 0.0
            ):
                existing_resistance: float | None = open_resistance_by_root_id.get(
                    candidate_root_raw,
                    None,
                )
                if existing_resistance is None:
                    open_resistance_by_root_id[candidate_root_raw] = float(
                        candidate_resistance_raw
                    )
                else:
                    if math.isclose(
                            existing_resistance,
                            float(candidate_resistance_raw),
                            rel_tol=1.0e-12,
                            abs_tol=1.0e-12,
                    ):
                        pass
                    else:
                        conflicting_open_resistance_root_ids.add(candidate_root_raw)
            else:
                pass
        else:
            pass

    conflicting_root_id: str
    for conflicting_root_id in conflicting_open_resistance_root_ids:
        open_resistance_by_root_id.pop(conflicting_root_id, None)
        logger.add_warning(
            msg="DGS logical actuator has conflicting physical open resistances",
            device=conflicting_root_id,
        )
    else:
        pass

    bound_count: int = 0
    physical_branch: object
    for physical_branch in circuit.get_branches_iter(
            add_vsc=False,
            add_hvdc=False,
            add_switch=False,
    ):
        if isinstance(physical_branch, (Line, SeriesReactance)):
            line: Line | SeriesReactance | None = physical_branch
        else:
            line = None
        if line is None:
            pass
        else:
            root_id_raw: object | None = line.rms_model.__dict__.get(
                "dgs_logical_actuator_root_id",
                None,
            )
            if isinstance(root_id_raw, str):
                root_association: DgsDynamicAssociation | None = root_by_id.get(
                    root_id_raw,
                    None,
                )
            else:
                root_association = None

            if root_association is None or line.rms_model.empty():
                pass
            else:
                _seed_open_resistive_actuator(
                    block=root_association.rms_model,
                    open_resistance_ohm=open_resistance_by_root_id.get(
                        root_association.root_dgs_id,
                        None,
                    ),
                )
                gate_vars: List[Var] = _collect_unique_named_vars(
                    block=root_association.rms_model,
                    variable_name="gate",
                )
                resistance_vars: List[Var] = _collect_unique_named_vars(
                    block=root_association.rms_model,
                    variable_name="R",
                )
                resistance_parameter: Var | None = line.rms_model.api_obj_mapping.get(
                    ParamPowerFlowReferenceType.r,
                    None,
                )
                inductance_parameter: Var | None = line.rms_model.api_obj_mapping.get(
                    ParamPowerFlowReferenceType.dc_line_l_pu_seconds,
                    None,
                )
                status_uid_raw: object | None = line.rms_model.__dict__.get(
                    "rms_conduction_status_var_uid",
                    None,
                )
                status_var: Var | None = None
                status_owner: Block | None = None
                child_block: Block
                event_var: Var
                if isinstance(status_uid_raw, int):
                    for child_block in line.rms_model.get_all_blocks():
                        for event_var in child_block.event_dict.keys():
                            if event_var.uid == status_uid_raw:
                                status_var = event_var
                                status_owner = child_block
                            else:
                                pass
                else:
                    pass

                if (
                        len(gate_vars) != 1
                        or len(resistance_vars) != 1
                        or resistance_parameter is None
                        or status_var is None
                        or status_owner is None
                ):
                    logger.add_warning(
                        msg="DGS logical actuator runtime interface is incomplete",
                        device=line.name,
                        value=root_id_raw,
                    )
                else:
                    gate_expression: Expr = heaviside(gate_vars[0])
                    status_owner.event_dict[status_var] = gate_expression

                    # PowerFactory exports chopper R in Ohm, while the standard
                    # DC branch shell uses system pu on the connected rail base.
                    impedance_base_ohm: float = (
                            float(line.bus_from.Vnom) * float(line.bus_from.Vnom)
                            / float(circuit.Sbase)
                    )
                    if impedance_base_ohm > 0.0:
                        parameter_owner: Block | None = None
                        for child_block in line.rms_model.get_all_blocks():
                            if resistance_parameter in child_block.parameters:
                                parameter_owner = child_block
                            else:
                                pass
                        if parameter_owner is None:
                            logger.add_warning(
                                msg="DGS passive actuator resistance parameter has no owner",
                                device=line.name,
                                value=resistance_parameter.name,
                            )
                        else:
                            parameter_owner.parameters.pop(resistance_parameter, None)
                            parameter_owner.event_dict[resistance_parameter] = resistance_vars[0] / Const(
                                impedance_base_ohm)

                            if inductance_parameter is None:
                                # A purely resistive actuator intentionally has
                                # no inductance parameter. Its gate and dynamic
                                # resistance remain fully executable without a
                                # fictitious energy-storage state.
                                pass
                            else:
                                if isinstance(line, Line):
                                    inductance_pu_seconds: float = float(
                                        line.dc_series_inductance_pu_seconds
                                    )
                                else:
                                    inductance_pu_seconds = float(line.X) / (
                                            2.0 * math.pi * float(circuit.fBase)
                                    )
                                inductance_owner: Block | None = None
                                for child_block in line.rms_model.get_all_blocks():
                                    if inductance_parameter in child_block.parameters:
                                        inductance_owner = child_block
                                    else:
                                        pass
                                if inductance_owner is None:
                                    logger.add_warning(
                                        msg="DGS passive actuator inductance parameter has no owner",
                                        device=line.name,
                                        value=inductance_parameter.name,
                                    )
                                else:
                                    # ElmSind exports X on the nominal-frequency
                                    # pu base. Convert it to the seconds coefficient
                                    # used by the DC R-L shell.
                                    inductance_owner.parameters[inductance_parameter] = Const(
                                        inductance_pu_seconds
                                    )
                            # Runtime event expressions that depend on solved
                            # DAE variables are seeded at startup and projected
                            # explicitly at each solver boundary. Store typed
                            # fixed-size specifications for that projection.
                            line.rms_model.__dict__["dgs_runtime_parameter_projections"] = list([
                                (
                                    status_var.uid,
                                    gate_vars[0].uid,
                                    1.0,
                                    True,
                                ),
                                (
                                    resistance_parameter.uid,
                                    resistance_vars[0].uid,
                                    1.0 / impedance_base_ohm,
                                    False,
                                ),
                            ])
                            bound_count += 1
                    else:
                        logger.add_warning(
                            msg="DGS passive actuator has invalid impedance base",
                            device=line.name,
                            value=line.bus_from.Vnom,
                        )

    return bound_count
