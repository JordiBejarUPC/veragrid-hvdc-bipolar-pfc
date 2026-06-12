# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import uuid

from typing import Dict, List, Tuple

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import sampled_value
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp, Comparison, Const, Expr, Var
from VeraGridEngine.enumerations import BlockType, DeviceType, EmtFaultPlacementSide, FaultType


def _get_active_phases(phA: bool, phB: bool, phC: bool) -> List[str]:
    """
    Return the enabled phase labels in deterministic A-B-C order.

    :param phA: True when phase A is active.
    :param phB: True when phase B is active.
    :param phC: True when phase C is active.
    :return: Ordered list of active phase labels.
    """
    active_phases: List[str] = list()

    if phA:
        active_phases.append("A")
    else:
        pass

    if phB:
        active_phases.append("B")
    else:
        pass

    if phC:
        active_phases.append("C")
    else:
        pass

    if len(active_phases) == 0:
        raise ValueError("At least one phase must be enabled for an EMT fault template")
    else:
        return active_phases


def _coerce_fault_type(fault_type: FaultType | str) -> FaultType:
    """
    Coerce one incoming fault selector into the project fault enum.

    :param fault_type: Enum instance or textual fault selector.
    :return: Coerced fault enum.
    """
    if isinstance(fault_type, FaultType):
        return fault_type
    else:
        return FaultType.argparse(str(fault_type))


def _coerce_fault_placement_side(placement_side: EmtFaultPlacementSide | str) -> EmtFaultPlacementSide:
    """
    Coerce one incoming placement selector into the placement-side enum.

    :param placement_side: Enum instance or textual selector.
    :return: Coerced placement-side enum.
    """
    if isinstance(placement_side, EmtFaultPlacementSide):
        return placement_side
    else:
        return EmtFaultPlacementSide.argparse(str(placement_side))


def _resolve_fault_shape(fault_type: FaultType, active_phases: List[str]) -> Tuple[List[Tuple[str, str]], bool]:
    """
    Resolve one fault type into phase-pair links and ground usage.

    :param fault_type: Requested fault type.
    :param active_phases: Ordered active phases.
    :return: Tuple ``(phase_pair_list, includes_ground)``.
    """
    active_phase_set = set(active_phases)
    phase_pair_list: List[Tuple[str, str]] = list()
    includes_ground: bool = False

    if fault_type == FaultType.LG:
        if len(active_phases) != 1:
            raise ValueError("LG faults require exactly one enabled phase")
        else:
            includes_ground = True
    else:
        if fault_type == FaultType.LL:
            if len(active_phases) != 2:
                raise ValueError("LL faults require exactly two enabled phases")
            else:
                phase_pair_list.append((active_phases[0], active_phases[1]))
        else:
            if fault_type == FaultType.LLG:
                if len(active_phases) != 2:
                    raise ValueError("LLG faults require exactly two enabled phases")
                else:
                    phase_pair_list.append((active_phases[0], active_phases[1]))
                    includes_ground = True
            else:
                if fault_type == FaultType.LLL:
                    if active_phase_set != {"A", "B", "C"}:
                        raise ValueError("LLL faults require phases A, B, and C")
                    else:
                        phase_pair_list.extend(list([("A", "B"), ("B", "C")]))
                else:
                    if fault_type == FaultType.LLLG:
                        if active_phase_set != {"A", "B", "C"}:
                            raise ValueError("LLLG faults require phases A, B, and C")
                        else:
                            phase_pair_list.extend(list([("A", "B"), ("B", "C")]))
                            includes_ground = True
                    else:
                        raise ValueError(f"Unsupported EMT fault type '{fault_type}'")

    return phase_pair_list, includes_ground


def _create_editor_connection_child(var: Var, is_input: bool, name: str) -> Block:
    """
    Build one visual-only connection child used by the hierarchy editor.

    :param var: Shared root-port variable.
    :param is_input: True for one input connector.
    :param name: Child block name.
    :return: Lightweight block exposing the shared variable.
    """
    child_block: Block = Block(name=name)

    if is_input:
        child_block.out_vars.append(var)
    else:
        child_block.in_vars.append(var)

    return child_block


def _attach_fault_editor_diagram(root_block: Block,
                                 input_vars: List[Var],
                                 output_vars: List[Var],
                                 active_phases: List[str],
                                 phase_pair_list: List[Tuple[str, str]],
                                 includes_ground: bool,
                                 placement_side: EmtFaultPlacementSide) -> None:
    """
    Attach one persisted hierarchy diagram for one internal EMT fault block.

    :param root_block: Root fault block.
    :param input_vars: Public input variables.
    :param output_vars: Public output variables.
    :param active_phases: Ordered active phases.
    :param phase_pair_list: Internal phase-to-phase fault links.
    :param includes_ground: Whether the topology includes ground links.
    :param placement_side: Whether the block sits at the branch from or to side.
    :return: None.
    """
    input_blocks_by_name: Dict[str, Block] = dict()
    phase_node_blocks: Dict[str, Block] = dict()
    input_index: int
    output_index: int
    phase_index: int
    pair_index: int
    input_var: Var
    output_var: Var
    placement_label: str = "From" if placement_side == EmtFaultPlacementSide.FromSide else "To"

    for input_index, input_var in enumerate(input_vars):
        input_block: Block = _create_editor_connection_child(var=input_var, is_input=True, name=input_var.name)
        root_block.add(input_block)
        root_block.diagram.add_node(
            name=input_block.name,
            x=40.0,
            y=70.0 + 60.0 * float(input_index),
            tpe=BlockType.INPUT_CONN.name,
            device_uid=input_block.uid,
        )
        input_blocks_by_name[input_var.name] = input_block

    for output_index, output_var in enumerate(output_vars):
        output_block: Block = _create_editor_connection_child(var=output_var, is_input=False, name=output_var.name)
        root_block.add(output_block)
        root_block.diagram.add_node(
            name=output_block.name,
            x=690.0,
            y=70.0 + 60.0 * float(output_index),
            tpe=BlockType.OUTPUT_CONN.name,
            device_uid=output_block.uid,
        )

    for phase_index, phase_label in enumerate(active_phases):
        phase_node_block: Block = Block(name=f"{placement_label} Phase {phase_label} Node")
        root_block.add(phase_node_block)
        root_block.diagram.add_node(
            name=phase_node_block.name,
            x=330.0,
            y=130.0 + 110.0 * float(phase_index),
            tpe=BlockType.GROUNDING_LINK_EMT.name,
            device_uid=phase_node_block.uid,
        )
        phase_node_blocks[phase_label] = phase_node_block

        outer_input_block: Block | None = input_blocks_by_name.get(f"v_outer_{phase_label}_{root_block.name}", None)
        inner_output_block_name: str = f"v_inner_{phase_label}_{root_block.name}"
        inner_output_block: Block | None = None
        child_block: Block

        for child_block in root_block.children:
            if child_block.name == inner_output_block_name:
                inner_output_block = child_block
            else:
                pass

        if outer_input_block is not None:
            root_block.diagram.add_branch(
                connectionitem_uid=uuid.uuid4().int,
                device_uid_from=outer_input_block.uid,
                device_uid_to=phase_node_block.uid,
                port_number_from=0,
                port_number_to=0,
                color="#587291",
            )
        else:
            pass

        if inner_output_block is not None:
            root_block.diagram.add_branch(
                connectionitem_uid=uuid.uuid4().int,
                device_uid_from=phase_node_block.uid,
                device_uid_to=inner_output_block.uid,
                port_number_from=0,
                port_number_to=0,
                color="#587291",
            )
        else:
            pass

    for pair_index, phase_pair in enumerate(phase_pair_list):
        phase_a: str = phase_pair[0]
        phase_b: str = phase_pair[1]
        pair_block: Block = Block(name=f"Fault Branch {phase_a}-{phase_b}")
        root_block.add(pair_block)
        root_block.diagram.add_node(
            name=pair_block.name,
            x=500.0,
            y=170.0 + 90.0 * float(pair_index),
            tpe=BlockType.SWITCH_EMT.name,
            device_uid=pair_block.uid,
        )
        root_block.diagram.add_branch(
            connectionitem_uid=uuid.uuid4().int,
            device_uid_from=phase_node_blocks[phase_a].uid,
            device_uid_to=pair_block.uid,
            port_number_from=0,
            port_number_to=0,
            color="#587291",
        )
        root_block.diagram.add_branch(
            connectionitem_uid=uuid.uuid4().int,
            device_uid_from=pair_block.uid,
            device_uid_to=phase_node_blocks[phase_b].uid,
            port_number_from=0,
            port_number_to=0,
            color="#587291",
        )

    if includes_ground:
        ground_block: Block = Block(name="Fault Ground")
        root_block.add(ground_block)
        root_block.diagram.add_node(
            name=ground_block.name,
            x=500.0,
            y=90.0 + 110.0 * float(len(active_phases)),
            tpe=BlockType.GROUND_EMT.name,
            device_uid=ground_block.uid,
        )

        for phase_label in active_phases:
            root_block.diagram.add_branch(
                connectionitem_uid=uuid.uuid4().int,
                device_uid_from=phase_node_blocks[phase_label].uid,
                device_uid_to=ground_block.uid,
                port_number_from=0,
                port_number_to=0,
                color="#587291",
            )
    else:
        pass


def get_fault_emt_template(
    vf: VarFactory,
    fault_type: FaultType | str = FaultType.LG,
    placement_side: EmtFaultPlacementSide | str = EmtFaultPlacementSide.FromSide,
    phA: bool = True,
    phB: bool = False,
    phC: bool = False,
    signal_controlled: bool = False,
    initial_closed: bool = False,
    fault_resistance: float = 1.0e-4,
    ground_resistance: float = 1.0e-4,
    open_conductance: float = 1.0e-8,
    fault_time_constant: float = 1.0e-6,
    command_threshold: float = 0.5,
    name: str = "fault_emt_template",
) -> EmtModelTemplate:
    """
    Build one internal-composition EMT fault block with explicit outer/inner ports.

    The block is intended for use inside one parent branch composition built in the
    dynamic block editor. It does not expose standard bus-side branch references.
    Instead, it uses one explicit pass-through interface:

    - ``v_outer_*``: incoming branch-side voltage input.
    - ``i_inner_*``: incoming downstream current input.
    - ``v_inner_*``: outgoing downstream voltage algebraic/output.
    - ``i_outer_*``: outgoing upstream current algebraic/output.

    The outer/inner naming stays fixed regardless of whether the fault is placed at
    the branch from side or to side. The parent branch composition gives those ports
    their actual topological meaning.

    :param vf: EMT variable factory.
    :param fault_type: Requested short-circuit topology.
    :param placement_side: Placement side inside the composed branch.
    :param phA: Enable phase A.
    :param phB: Enable phase B.
    :param phC: Enable phase C.
    :param signal_controlled: If True, expose one control input and procedural logic.
    :param initial_closed: Initial fault status.
    :param fault_resistance: Phase-to-phase fault resistance.
    :param ground_resistance: Phase-to-ground fault resistance.
    :param open_conductance: Open-state leakage conductance.
    :param fault_time_constant: First-order branch-current time constant.
    :param command_threshold: Control threshold for the external command.
    :param name: Symbolic model name.
    :return: EMT fault template.
    """
    active_phases: List[str] = _get_active_phases(phA=phA, phB=phB, phC=phC)
    resolved_fault_type: FaultType = _coerce_fault_type(fault_type)
    resolved_placement_side: EmtFaultPlacementSide = _coerce_fault_placement_side(placement_side)
    phase_pair_list: List[Tuple[str, str]]
    includes_ground: bool
    phase_pair_list, includes_ground = _resolve_fault_shape(fault_type=resolved_fault_type, active_phases=active_phases)

    templ: EmtModelTemplate = EmtModelTemplate()
    templ.tpe = DeviceType.SwitchDevice
    templ.name = name
    templ.block.name = name
    templ.block.external_mapping = dict()

    # The discrete fault mode controls whether the shunt fault branches are active.
    closed_mode: Var = vf.add_var(f"fault_closed_mode_{name}")
    templ.block.mode_dict[closed_mode] = Const(1.0 if initial_closed else 0.0, name="fault_closed_mode")

    fault_r_var: Var = vf.add_var(f"fault_r_{name}")
    ground_r_var: Var = vf.add_var(f"fault_rg_{name}")
    g_open_var: Var = vf.add_var(f"fault_open_g_{name}")
    tau_var: Var = vf.add_var(f"fault_tau_{name}")

    templ.block.event_dict[fault_r_var] = Const(float(fault_resistance), name="fault_r")
    templ.block.event_dict[ground_r_var] = Const(float(ground_resistance), name="fault_rg")
    templ.block.event_dict[g_open_var] = Const(float(open_conductance), name="fault_open_g")
    templ.block.event_dict[tau_var] = Const(float(fault_time_constant), name="fault_tau")

    g_pair_eff: Expr = closed_mode * (Const(1.0) / fault_r_var) + (Const(1.0) - closed_mode) * g_open_var
    g_ground_eff: Expr = closed_mode * (Const(1.0) / ground_r_var) + (Const(1.0) - closed_mode) * g_open_var

    in_vars: List[Var] = list()
    state_vars: List[Var] = list()
    diff_vars: List[Var] = list()
    algebraic_vars: List[Var] = list()
    algebraic_eqs: List[Expr] = list()
    state_eqs: List[Expr] = list()
    out_vars: List[Var] = list()

    phase_outer_voltage_vars: Dict[str, Var] = dict()
    phase_inner_voltage_vars: Dict[str, Var] = dict()
    phase_inner_current_vars: Dict[str, Var] = dict()
    phase_outer_current_vars: Dict[str, Var] = dict()
    phase_fault_current_exprs: Dict[str, Expr] = dict()

    if signal_controlled:
        command_input: Var = vf.add_var(f"fault_cmd_{name}")
        threshold_var: Var = vf.add_var(f"fault_cmd_threshold_{name}")
        templ.block.event_dict[threshold_var] = Const(float(command_threshold), name="fault_cmd_threshold")
        templ.block.procedural_logic.append(
            sampled_value(output=closed_mode, source=Comparison(lhs=command_input, op=CmpOp.GE, rhs=threshold_var))
        )
        in_vars.append(command_input)
    else:
        pass

    phase_label: str
    for phase_label in active_phases:
        # The inner voltage is an algebraic/output variable because it defines the
        # internal midpoint voltage that the downstream line block reads.
        v_outer_var: Var = vf.add_var(f"v_outer_{phase_label}_{name}")
        i_inner_var: Var = vf.add_var(f"i_inner_{phase_label}_{name}")
        v_inner_var: Var = vf.add_var(f"v_inner_{phase_label}_{name}")
        i_outer_var: Var = vf.add_var(f"i_outer_{phase_label}_{name}")

        in_vars.append(v_outer_var)
        in_vars.append(i_inner_var)
        algebraic_vars.append(v_inner_var)
        algebraic_vars.append(i_outer_var)
        out_vars.append(v_inner_var)
        out_vars.append(i_outer_var)

        # The internal series path is ideal, so the midpoint voltage equals the
        # outer voltage. The fault current is added on top through the shunt path.
        algebraic_eqs.append(v_inner_var - v_outer_var)

        phase_outer_voltage_vars[phase_label] = v_outer_var
        phase_inner_voltage_vars[phase_label] = v_inner_var
        phase_inner_current_vars[phase_label] = i_inner_var
        phase_outer_current_vars[phase_label] = i_outer_var
        phase_fault_current_exprs[phase_label] = Const(0.0)

    phase_pair: Tuple[str, str]
    for phase_pair in phase_pair_list:
        phase_a: str = phase_pair[0]
        phase_b: str = phase_pair[1]
        pair_current_var: Var = vf.add_var(f"i_fault_{phase_a}{phase_b}_{name}")
        pair_diff_var: Var = vf.add_diff_var(name=f"di_fault_{phase_a}{phase_b}_{name}", base_var=pair_current_var)
        pair_voltage_drop: Expr = phase_inner_voltage_vars[phase_a] - phase_inner_voltage_vars[phase_b]

        state_vars.append(pair_current_var)
        diff_vars.append(pair_diff_var)
        state_eqs.append((g_pair_eff * pair_voltage_drop - pair_current_var) / tau_var)
        phase_fault_current_exprs[phase_a] = phase_fault_current_exprs[phase_a] + pair_current_var
        phase_fault_current_exprs[phase_b] = phase_fault_current_exprs[phase_b] - pair_current_var

    if includes_ground:
        for phase_label in active_phases:
            ground_current_var: Var = vf.add_var(f"i_fault_g_{phase_label}_{name}")
            ground_diff_var: Var = vf.add_diff_var(name=f"di_fault_g_{phase_label}_{name}", base_var=ground_current_var)
            phase_voltage_drop: Expr = phase_inner_voltage_vars[phase_label]

            state_vars.append(ground_current_var)
            diff_vars.append(ground_diff_var)
            state_eqs.append((g_ground_eff * phase_voltage_drop - ground_current_var) / tau_var)
            phase_fault_current_exprs[phase_label] = phase_fault_current_exprs[phase_label] + ground_current_var
    else:
        pass

    for phase_label in active_phases:
        # KCL at the internal split node enforces that the outer current returned
        # to the parent branch equals downstream current plus local fault current.
        algebraic_eqs.append(
            phase_outer_current_vars[phase_label]
            - phase_inner_current_vars[phase_label]
            - phase_fault_current_exprs[phase_label]
        )

    init_eqs: Dict[Var, Expr | Const] = dict()
    diff_init_eqs: Dict[Var, Expr | Const] = dict()
    diff_var: Var
    state_eq: Expr
    state_var: Var

    for state_var in state_vars:
        init_eqs[state_var] = Const(0.0)

    for diff_var, state_eq in zip(diff_vars, state_eqs):
        diff_init_eqs[diff_var] = state_eq

    templ.block.in_vars = in_vars
    templ.block.state_vars = state_vars
    templ.block.diff_vars = diff_vars
    templ.block.algebraic_vars = algebraic_vars
    templ.block.state_eqs = state_eqs
    templ.block.algebraic_eqs = algebraic_eqs
    templ.block.out_vars = out_vars
    templ.block.init_eqs = init_eqs
    templ.block.diff_init_eqs = diff_init_eqs

    _attach_fault_editor_diagram(
        root_block=templ.block,
        input_vars=in_vars,
        output_vars=out_vars,
        active_phases=active_phases,
        phase_pair_list=phase_pair_list,
        includes_ground=includes_ground,
        placement_side=resolved_placement_side,
    )
    return templ
