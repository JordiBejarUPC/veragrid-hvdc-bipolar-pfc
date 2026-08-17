from __future__ import annotations

import copy
from typing import Dict, Iterable, List, Set, Tuple

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import (
    DeviceType,
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)


def _flatten_slot_signal_names(raw_signals: object | None) -> Set[str]:
    """Return individual signal names from one DGS slot declaration.

    PowerFactory writes multiple aliases in one slot cell separated by a
    semicolon. The runtime contract is based on individual cable names, so the
    raw declaration must be normalized before it is inspected.

    :param raw_signals: Raw ``incoming_signals`` or ``outgoing_signals`` value.
    :return: Normalized non-empty signal names.
    """
    result: Set[str] = set()
    raw_signal: object
    signal_part: str

    if isinstance(raw_signals, list):
        for raw_signal in raw_signals:
            if isinstance(raw_signal, str):
                for signal_part in raw_signal.split(";"):
                    if signal_part.strip() == "":
                        pass
                    else:
                        result.add(signal_part.strip())
            else:
                pass
    else:
        pass
    return result


def _get_elmsvs_interface(block: Block) -> Dict[str, object] | None:
    """Return the exact physical ``ElmSvs`` slot metadata.

    :param block: Imported PowerFactory composite root.
    :return: Physical slot metadata or ``None`` when the contract is absent.
    """
    interfaces_raw: object | None = block.__dict__.get(
        "dgs_direct_slot_interfaces",
        None,
    )
    interface_raw: object

    if isinstance(interfaces_raw, list):
        for interface_raw in interfaces_raw:
            if isinstance(interface_raw, dict):
                element_kind_raw: object | None = interface_raw.get(
                    "element_kind",
                    None,
                )
                slot_filter_raw: object | None = interface_raw.get(
                    "slot_filter",
                    None,
                )
                element_kind: str = (
                    element_kind_raw
                    if isinstance(element_kind_raw, str)
                    else ""
                )
                slot_filter: str = (
                    slot_filter_raw
                    if isinstance(slot_filter_raw, str)
                    else ""
                )
                if element_kind == "ElmSvs" or "ElmSvs" in slot_filter:
                    return interface_raw
                else:
                    pass
            else:
                pass
    else:
        pass
    return None


def is_dgs_elmsvs_slot_contract(block: Block) -> bool:
    """Return whether a DGS root contains the native SVC equipment boundary.

    :param block: Imported PowerFactory composite root.
    :return: ``True`` when the controller is wired to one physical ``ElmSvs``.
    """
    interface_spec: Dict[str, object] | None = _get_elmsvs_interface(block=block)

    if interface_spec is None:
        return False
    else:
        incoming_signals: Set[str] = _flatten_slot_signal_names(
            raw_signals=interface_spec.get("incoming_signals", None),
        )
        outgoing_signals: Set[str] = _flatten_slot_signal_names(
            raw_signals=interface_spec.get("outgoing_signals", None),
        )
        required_outputs: Set[str] = set([
            "ysvs",
            "qreact",
            "qcap",
            "qfixcap",
            "nxcap",
            "nfixcap",
        ])
        return "bsvs" in incoming_signals and required_outputs.issubset(
            outgoing_signals,
        )


def _find_produced_var_recursive(block: Block, var_name: str) -> Var | None:
    """Find one exact controller-produced variable recursively.

    :param block: Imported controller root.
    :param var_name: Exact DGS cable name.
    :return: Matching produced variable or ``None``.
    """
    produced_var: Var
    child_block: Block
    child_result: Var | None

    for produced_var in block.algebraic_vars:
        if produced_var.name == var_name:
            return produced_var
        else:
            pass
    for produced_var in block.state_vars:
        if produced_var.name == var_name:
            return produced_var
        else:
            pass
    for child_block in block.children:
        child_result = _find_produced_var_recursive(
            block=child_block,
            var_name=var_name,
        )
        if child_result is None:
            pass
        else:
            return child_result
    return None


def _connect_named_inputs(block: Block, signal_name: str, source_var: Var) -> int:
    """Connect every exact named controller input to one physical signal.

    :param block: Imported controller hierarchy updated in place.
    :param signal_name: Exact input cable name.
    :param source_var: Canonical equipment-owned signal.
    :return: Number of distinct input variables replaced.
    """
    matching_inputs: List[Var] = list()
    matching_uids: Set[int] = set()
    candidate_block: Block
    input_var: Var

    # Collect before replacing because ``update_model`` mutates interfaces.
    for candidate_block in block.get_all_blocks():
        for input_var in candidate_block.in_vars:
            if input_var.name == signal_name and input_var.uid not in matching_uids:
                matching_inputs.append(input_var)
                matching_uids.add(input_var.uid)
            else:
                pass
        else:
            pass
    else:
        pass

    for input_var in matching_inputs:
        block.update_model(input_var, source_var)
    else:
        pass
    return len(matching_inputs)


def _append_unique_var(variables: List[Var], variable: Var) -> None:
    """Append one symbolic variable exactly once by UID.

    :param variables: Ordered destination variables.
    :param variable: Candidate variable.
    :return: None.
    """
    existing_variable: Var

    for existing_variable in variables:
        if existing_variable.uid == variable.uid:
            return
        else:
            pass
    variables.append(variable)


def _copy_dgs_runtime_signal_identity(
        source_block: Block,
        destination_block: Block,
) -> None:
    """Preserve controller signal aliases and element ownership on a wrapper.

    RMS compilation flattens the wrapped SVC hierarchy.  Copying these lookup
    tables to the physical wrapper keeps each runtime parameter traceable to
    both its humanized identifier and immutable DGS block FID afterwards.

    :param source_block: Exact imported graphical controller hierarchy.
    :param destination_block: Physical SVC wrapper receiving the metadata.
    :return: None.
    """
    persisted_identifiers: Dict[int, str] = dict()
    element_ids: Dict[int, str] = dict()
    candidate_block: Block
    raw_identifier_map: object | None
    raw_identifier_uid: object
    raw_identifier: object
    raw_element_id: object | None
    variable_groups: Tuple[Iterable[Var], ...]
    variable_group: Iterable[Var]
    candidate_variable: Var

    # Traverse the complete source tree because a graphical composite stores
    # its stable identifier map at the root and its FIDs on nested DSL blocks.
    for candidate_block in source_block.get_all_blocks():
        raw_identifier_map = candidate_block.__dict__.get(
            "dgs_persisted_identifier_by_uid",
            None,
        )
        if isinstance(raw_identifier_map, dict):
            for raw_identifier_uid, raw_identifier in raw_identifier_map.items():
                if isinstance(raw_identifier_uid, int) and isinstance(
                        raw_identifier,
                        str,
                ):
                    persisted_identifiers[raw_identifier_uid] = raw_identifier
                else:
                    pass
            else:
                pass
        else:
            pass

        raw_element_id = candidate_block.__dict__.get("dgs_element_id", None)
        if raw_element_id is None:
            pass
        else:
            variable_groups = (
                candidate_block.in_vars,
                candidate_block.out_vars,
                candidate_block.algebraic_vars,
                candidate_block.state_vars,
                candidate_block.diff_vars,
                tuple(candidate_block.event_dict.keys()),
                tuple(candidate_block.mode_dict.keys()),
                tuple(candidate_block.parameters.keys()),
            )
            for variable_group in variable_groups:
                for candidate_variable in variable_group:
                    element_ids[candidate_variable.uid] = str(raw_element_id)
                else:
                    pass
            else:
                pass
    else:
        pass

    if len(persisted_identifiers) == 0:
        pass
    else:
        destination_block.__dict__["dgs_persisted_identifier_by_uid"] = dict(
            persisted_identifiers,
        )
    if len(element_ids) == 0:
        pass
    else:
        destination_block.__dict__["dgs_element_id_by_uid"] = dict(element_ids)


def _read_float_metadata(
        interface_spec: Dict[str, object],
        key: str,
) -> float | None:
    """Read one finite numeric SVC metadata field.

    :param interface_spec: Exact physical slot metadata.
    :param key: Metadata key.
    :return: Numeric value or ``None`` for an invalid/missing field.
    """
    value_raw: object | None = interface_spec.get(key, None)

    if isinstance(value_raw, bool):
        return None
    else:
        if isinstance(value_raw, (int, float)):
            return float(value_raw)
        else:
            return None


def build_dgs_elmsvs_rms_runtime_template(
        control_template: RmsModelTemplate,
        clone_control_block: bool = True,
) -> RmsModelTemplate | None:
    """Wrap one graphical ``ElmSvs`` controller in its physical RMS equations.

    The DGS contains the graphical controller but PowerFactory keeps the
    ``ElmSvs`` electrical equations built in. This adapter restores only that
    documented physical boundary: the controller command ``bsvs`` becomes the
    shunt susceptance in MVAr at 1 p.u., and its terminal reactive injection is
    converted to the VeraGrid system base.

    :param control_template: Imported exact graphical controller template.
    :param clone_control_block: Clone the controller before modifying its ports.
    :return: Assignable controllable-shunt template or ``None`` if incomplete.
    """
    control_block: Block

    if clone_control_block:
        control_block = copy.deepcopy(control_template.block)
    else:
        control_block = control_template.block

    if is_dgs_elmsvs_slot_contract(block=control_block):
        pass
    else:
        return None

    interface_spec: Dict[str, object] | None = _get_elmsvs_interface(
        block=control_block,
    )
    bsvs: Var | None = _find_produced_var_recursive(
        block=control_block,
        var_name="bsvs",
    )
    if interface_spec is None or bsvs is None:
        return None
    else:
        pass

    qreact_value: float | None = _read_float_metadata(
        interface_spec=interface_spec,
        key="svs_qreact_mvar",
    )
    qcap_value: float | None = _read_float_metadata(
        interface_spec=interface_spec,
        key="svs_qcap_mvar",
    )
    qfixcap_value: float | None = _read_float_metadata(
        interface_spec=interface_spec,
        key="svs_qfixcap_mvar",
    )
    nxcap_value: float | None = _read_float_metadata(
        interface_spec=interface_spec,
        key="svs_nxcap",
    )
    nfixcap_value: float | None = _read_float_metadata(
        interface_spec=interface_spec,
        key="svs_nfixcap",
    )
    metadata_values: List[float | None] = list([
        qreact_value,
        qcap_value,
        qfixcap_value,
        nxcap_value,
        nfixcap_value,
    ])
    metadata_is_complete: bool = True
    metadata_value: float | None
    for metadata_value in metadata_values:
        if metadata_value is None:
            metadata_is_complete = False
        else:
            pass
    else:
        pass
    if metadata_is_complete:
        pass
    else:
        return None

    # The explicit guard above narrows every physical constant to float.
    qreact_constant: float = float(qreact_value)
    qcap_constant: float = float(qcap_value)
    qfixcap_constant: float = float(qfixcap_value)
    nxcap_constant: float = float(nxcap_value)
    nfixcap_constant: float = float(nfixcap_value)

    terminal_voltage: Var = Var(
        name="Vm",
        reference=VarPowerFlowReferenceType.Vm,
    )
    terminal_angle: Var = Var(
        name="Va",
        reference=VarPowerFlowReferenceType.Va,
    )
    remote_voltage: Var = Var(name="Vm_remote")
    active_power: Var = Var(
        name="Psvs",
        reference=VarPowerFlowReferenceType.P,
    )
    reactive_power: Var = Var(
        name="Qsvs",
        reference=VarPowerFlowReferenceType.Q,
    )
    qreact: Var = Var(name="qreact")
    qcap: Var = Var(name="qcap")
    qfixcap: Var = Var(name="qfixcap")
    nxcap: Var = Var(name="nxcap")
    nfixcap: Var = Var(name="nfixcap")
    system_power_base: Var = Var(name="Sbase")

    # Restore the exact equipment/controller cables exported by the frame.
    _connect_named_inputs(control_block, "u", terminal_voltage)
    _connect_named_inputs(control_block, "uremote", remote_voltage)
    _connect_named_inputs(control_block, "ysvs", bsvs)
    _connect_named_inputs(control_block, "qreact", qreact)
    _connect_named_inputs(control_block, "qcap", qcap)
    _connect_named_inputs(control_block, "qfixcap", qfixcap)
    _connect_named_inputs(control_block, "nxcap", nxcap)
    _connect_named_inputs(control_block, "nfixcap", nfixcap)

    reactive_power_expression: Expr = (
            bsvs * terminal_voltage * terminal_voltage / system_power_base
    )
    susceptance_seed_expression: Expr = reactive_power * system_power_base / terminal_voltage * terminal_voltage

    wrapper_outputs: List[Var] = list([active_power, reactive_power])
    controller_output: Var
    for controller_output in control_block.out_vars:
        _append_unique_var(wrapper_outputs, controller_output)

    _append_unique_var(wrapper_outputs, bsvs)

    api_mapping: Dict[ParamPowerFlowReferenceType, Var] = dict()
    api_mapping[ParamPowerFlowReferenceType.Sbase] = system_power_base

    wrapper_block: Block = Block(
        name=control_template.name,
        children=list([control_block]),
        in_vars=list([terminal_voltage, terminal_angle, remote_voltage]),
        out_vars=wrapper_outputs,
        algebraic_vars=list([active_power, reactive_power]),
        algebraic_eqs=list([
            active_power,
            reactive_power - reactive_power_expression,
        ]),
        init_eqs=dict([
            (active_power, Const(0.0)),
            (bsvs, susceptance_seed_expression),
            (reactive_power, reactive_power_expression),
        ]),
        post_init_seed_eqs=dict([
            (active_power, Const(0.0)),
            (bsvs, susceptance_seed_expression),
            (reactive_power, reactive_power_expression),
        ]),
        parameters=dict([
            (system_power_base, Const(100.0)),
            (qreact, Const(qreact_constant)),
            (qcap, Const(qcap_constant)),
            (qfixcap, Const(qfixcap_constant)),
            (nxcap, Const(nxcap_constant)),
            (nfixcap, Const(nfixcap_constant)),
        ]),
        external_mapping=dict([
            (VarPowerFlowReferenceType.P, active_power),
            (VarPowerFlowReferenceType.Q, reactive_power),
            (VarPowerFlowReferenceType.Vm, terminal_voltage),
            (VarPowerFlowReferenceType.Va, terminal_angle),
        ]),
        api_obj_mapping=api_mapping,
    )
    wrapper_block.__dict__["dgs_elmsvs_runtime_adapter"] = True
    _copy_dgs_runtime_signal_identity(
        source_block=control_block,
        destination_block=wrapper_block,
    )
    # The solved terminal Q is a physical initialization boundary, not another
    # controller assignment. Keep it outside the local explicit-init graph and
    # make the derived susceptance equation outrank the graphical limiter's
    # duplicate ``inc(bsvs)`` target. The remaining OEM chain then initializes
    # SV03 from that physical value exactly as declared in the source DGS.
    wrapper_block.__dict__["explicit_init_excluded_var_names"] = list([
        reactive_power.name,
    ])
    wrapper_block.__dict__["explicit_init_override_init_exprs"] = dict([
        (bsvs.name, susceptance_seed_expression),
    ])
    # The physical susceptance is reconstructed from the solved terminal Q at
    # t=0. Mark that equipment assignment as authoritative so graphical helper
    # closure cannot replace it with a provisional controller iterate before
    # the SVC states reach the same operating point.
    wrapper_block.__dict__["dgs_explicit_initialization_uids"] = set([
        bsvs.uid,
    ])
    wrapper_block.__dict__["dgs_elmsvs_remote_voltage_var_uid"] = remote_voltage.uid
    wrapper_block.__dict__["dgs_equipment_owned_signal_names"] = list([
        "u",
        "uremote",
        "ysvs",
        "qreact",
        "qcap",
        "qfixcap",
        "nxcap",
        "nfixcap",
    ])

    runtime_template: RmsModelTemplate = RmsModelTemplate(
        name=control_template.name,
    )
    runtime_template.tpe = DeviceType.ControllableShuntDevice
    runtime_template.block = wrapper_block
    return runtime_template
