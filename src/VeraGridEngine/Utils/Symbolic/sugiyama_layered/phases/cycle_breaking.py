# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass

from ..pipeline import LayoutContext


@dataclass(frozen=True)
class FlatEdge:
    edge_id: str
    source: str
    target: str
    source_port: str | None = None
    target_port: str | None = None


def _edge_direction_priority(edge) -> int:
    candidates = (
        edge.properties.get("directionPriority"),
        edge.properties.get("direction_priority"),
        edge.layout_options.get("org.vera.sugiyama.layered.priority.direction"),
    )
    for value in candidates:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _node_model_order(node_id: str, node_order: dict[str, int], node_by_id) -> int:
    node = node_by_id.get(node_id)
    if node is None:
        return node_order.get(node_id, 0)
    candidates = (
        node.properties.get("modelOrder"),
        node.properties.get("model_order"),
        node.layout_options.get("org.vera.sugiyama.layered.considerModelOrder.groupModelOrder.cycleBreakingId"),
    )
    for value in candidates:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return node_order.get(node_id, 0)


def _node_kind_bias(node_id: str, node_by_id) -> int:
    node = node_by_id.get(node_id)
    if node is None:
        return 0
    kind = str(node.properties.get("kind", "")).upper()
    if kind == "INPUT_CONN":
        return 2
    if kind == "OUTPUT_CONN":
        return -2
    return 0


def _consider_model_order_strength(context: LayoutContext) -> int:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    strategy = str(options.get("org.vera.sugiyama.layered.considerModelOrder.strategy", "NONE")).upper()
    if strategy == "NONE":
        return 0
    if strategy in {"NODES", "NODES_AND_EDGES", "PREFER_NODES"}:
        return 1
    return 0


def _feedback_edges_enabled(context: LayoutContext) -> bool:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    value = options.get("org.vera.sugiyama.layered.feedbackEdges", False)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _cycle_breaking_strategy(context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    return str(options.get("org.vera.sugiyama.layered.cycleBreaking.strategy", "GREEDY")).upper()


def _flatten_edges(context: LayoutContext) -> tuple[list[FlatEdge], list[str]]:
    node_ids = {node.identifier for node in context.graph.children}
    flat_edges: list[FlatEdge] = []
    skipped_edges: list[str] = []
    port_to_owner: dict[str, str] = {}
    for node in context.graph.children:
        for port in node.ports:
            port_to_owner[port.identifier] = node.identifier

    for edge in context.graph.edges:
        if not edge.sources or not edge.targets:
            skipped_edges.append(edge.identifier)
            continue
        for source in edge.sources:
            for target in edge.targets:
                source_node = source if source in node_ids else port_to_owner.get(source)
                target_node = target if target in node_ids else port_to_owner.get(target)
                if source_node is None or target_node is None:
                    skipped_edges.append(edge.identifier)
                    continue
                flat_edges.append(
                    FlatEdge(
                        edge_id=edge.identifier,
                        source=source_node,
                        target=target_node,
                        source_port=None if source in node_ids else source,
                        target_port=None if target in node_ids else target,
                    )
                )
    return flat_edges, skipped_edges


def _build_adjacency(
    node_ids: list[str],
    flat_edges: list[FlatEdge],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    successors = {node_id: set() for node_id in node_ids}
    predecessors = {node_id: set() for node_id in node_ids}
    for edge in flat_edges:
        if edge.source == edge.target:
            continue
        successors.setdefault(edge.source, set()).add(edge.target)
        predecessors.setdefault(edge.target, set()).add(edge.source)
    return successors, predecessors


def _build_weighted_adjacency(
    node_ids: list[str],
    flat_edges: list[FlatEdge],
    edge_by_id,
) -> tuple[dict[str, int], dict[str, int]]:
    weighted_out = {node_id: 0 for node_id in node_ids}
    weighted_in = {node_id: 0 for node_id in node_ids}
    for edge in flat_edges:
        if edge.source == edge.target:
            continue
        input_edge = edge_by_id.get(edge.edge_id)
        priority = _edge_direction_priority(input_edge) if input_edge is not None else 0
        weight = 1 + abs(priority)
        weighted_out[edge.source] = weighted_out.get(edge.source, 0) + weight
        weighted_in[edge.target] = weighted_in.get(edge.target, 0) + weight
    return weighted_out, weighted_in


def _greedy_order(
    node_ids: list[str],
    successors: dict[str, set[str]],
    predecessors: dict[str, set[str]],
    weighted_out: dict[str, int],
    weighted_in: dict[str, int],
    node_by_id,
    model_order_strength: int,
) -> list[str]:
    remaining = set(node_ids)
    left: list[str] = []
    right: list[str] = []
    node_order = {node_id: idx for idx, node_id in enumerate(node_ids)}

    while remaining:
        sinks = sorted(
            (
                node_id for node_id in remaining
                if len(successors.get(node_id, set()) & remaining) == 0
            ),
            key=lambda node_id: (_node_model_order(node_id, node_order, node_by_id), node_id),
        )
        if sinks:
            right.append(sinks[0])
            remaining.remove(sinks[0])
            continue

        sources = sorted(
            (
                node_id for node_id in remaining
                if len(predecessors.get(node_id, set()) & remaining) == 0
            ),
            key=lambda node_id: (
                _node_model_order(node_id, node_order, node_by_id) if model_order_strength else node_order.get(node_id, 0),
                node_id,
            ),
        )
        if sources:
            left.append(sources[0])
            remaining.remove(sources[0])
            continue

        def score(node_id: str) -> tuple[int, int, int, str]:
            out_degree = len(successors.get(node_id, set()) & remaining)
            in_degree = len(predecessors.get(node_id, set()) & remaining)
            model_order = _node_model_order(node_id, node_order, node_by_id)
            kind_bias = _node_kind_bias(node_id, node_by_id)
            weighted_bias = weighted_out.get(node_id, 0) - weighted_in.get(node_id, 0)
            return (
                out_degree - in_degree + kind_bias,
                weighted_bias,
                -model_order if model_order_strength else -node_order.get(node_id, 0),
                kind_bias,
                node_id,
            )

        chosen = max(sorted(remaining), key=score)
        left.append(chosen)
        remaining.remove(chosen)

    return left + list(reversed(right))


class CycleBreakingPhase:
    name = "cycle-breaking"

    def run(self, context: LayoutContext) -> None:
        node_ids = [node.identifier for node in context.graph.children]
        node_by_id = context.graph.node_by_id()
        model_order_strength = _consider_model_order_strength(context)
        feedback_edges_enabled = _feedback_edges_enabled(context)
        strategy = _cycle_breaking_strategy(context)
        flat_edges, skipped_edges = _flatten_edges(context)
        successors, predecessors = _build_adjacency(node_ids, flat_edges)
        edge_by_id = {edge.identifier: edge for edge in context.graph.edges}
        weighted_out, weighted_in = _build_weighted_adjacency(node_ids, flat_edges, edge_by_id)
        if strategy == "NONE":
            greedy_order = list(node_ids)
        else:
            greedy_order = _greedy_order(
                node_ids,
                successors,
                predecessors,
                weighted_out,
                weighted_in,
                node_by_id,
                model_order_strength,
            )
        rank = {node_id: idx for idx, node_id in enumerate(greedy_order)}

        reversed_edges: list[str] = []
        feedback_edges: list[str] = []
        dag_successors = {node_id: set() for node_id in node_ids}
        dag_predecessors = {node_id: set() for node_id in node_ids}
        oriented_edges: list[dict[str, str | bool | None]] = []

        for flat_edge in flat_edges:
            source = flat_edge.source
            target = flat_edge.target
            if source == target:
                if feedback_edges_enabled:
                    feedback_edges.append(flat_edge.edge_id)
                oriented_edges.append(
                    {
                        "edge_id": flat_edge.edge_id,
                        "source": source,
                        "target": target,
                        "reversed": False,
                        "source_port": flat_edge.source_port,
                        "target_port": flat_edge.target_port,
                    }
                )
                continue

            input_edge = edge_by_id.get(flat_edge.edge_id)
            priority = _edge_direction_priority(input_edge) if input_edge is not None else 0
            source_rank = rank.get(source, 0)
            target_rank = rank.get(target, 0)
            reverse = source_rank > target_rank
            if source_rank == target_rank and model_order_strength:
                source_model = _node_model_order(source, rank, node_by_id)
                target_model = _node_model_order(target, rank, node_by_id)
                reverse = source_model > target_model
            if priority > 0:
                reverse = False
            elif priority < 0:
                reverse = True

            if reverse:
                source, target = target, source
                reversed_edges.append(flat_edge.edge_id)
                if feedback_edges_enabled:
                    feedback_edges.append(flat_edge.edge_id)

            dag_successors.setdefault(source, set()).add(target)
            dag_predecessors.setdefault(target, set()).add(source)
            oriented_edges.append(
                {
                    "edge_id": flat_edge.edge_id,
                    "source": source,
                    "target": target,
                    "reversed": reverse,
                    "source_port": flat_edge.source_port,
                    "target_port": flat_edge.target_port,
                }
            )

        context.phase_state["flat_edges"] = flat_edges
        context.phase_state["node_order"] = greedy_order
        context.phase_state["reversed_edges"] = reversed_edges
        context.phase_state["feedback_edges"] = feedback_edges
        context.phase_state["dag_successors"] = dag_successors
        context.phase_state["dag_predecessors"] = dag_predecessors
        context.phase_state["oriented_edges"] = oriented_edges
        if skipped_edges:
            context.phase_state["skipped_edges"] = skipped_edges

        context.report.notes.append(
            f"Cycle breaking oriented {len(oriented_edges)} flat edge(s) and reversed {len(reversed_edges)}."
        )
