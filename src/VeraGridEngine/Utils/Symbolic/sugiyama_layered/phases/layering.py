# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from collections import deque

from ..pipeline import LayoutContext


def _node_model_order(node_id: str, fallback: int, node_by_id) -> int:
    node = node_by_id.get(node_id)
    if node is None:
        return fallback
    candidates = (
        node.properties.get("modelOrder"),
        node.properties.get("model_order"),
        node.layout_options.get("org.vera.sugiyama.layered.considerModelOrder.groupModelOrder.layeringId"),
        node.layout_options.get("org.vera.sugiyama.layered.considerModelOrder.groupModelOrder.cycleBreakingId"),
    )
    for value in candidates:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return fallback


def _consider_model_order_enabled(context: LayoutContext) -> bool:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    strategy = str(options.get("org.vera.sugiyama.layered.considerModelOrder.strategy", "NONE")).upper()
    return strategy != "NONE"


def _layering_strategy(context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    return str(options.get("org.vera.sugiyama.layered.layering.strategy", "NETWORK_SIMPLEX")).upper()


def _topological_order(
    node_ids: list[str],
    successors: dict[str, set[str]],
    predecessors: dict[str, set[str]],
    node_by_id,
    prefer_model_order: bool,
) -> list[str]:
    indegree = {node_id: len(predecessors.get(node_id, set())) for node_id in node_ids}
    node_order = {node_id: idx for idx, node_id in enumerate(node_ids)}
    queue = deque(
        sorted(
            (node_id for node_id, degree in indegree.items() if degree == 0),
            key=lambda node_id: (
                _node_model_order(node_id, node_order.get(node_id, 0), node_by_id)
                if prefer_model_order else node_order.get(node_id, 0),
                node_id,
            ),
        )
    )
    order: list[str] = []

    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for successor in sorted(
            successors.get(node_id, set()),
            key=lambda other: (
                _node_model_order(other, node_order.get(other, 0), node_by_id)
                if prefer_model_order else node_order.get(other, 0),
                other,
            ),
        ):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)

    for node_id in sorted(
        node_ids,
        key=lambda other: (
            _node_model_order(other, node_order.get(other, 0), node_by_id)
            if prefer_model_order else node_order.get(other, 0),
            other,
        ),
    ):
        if node_id not in order:
            order.append(node_id)
    return order


def _longest_path_layers(order: list[str], predecessors: dict[str, set[str]]) -> dict[str, int]:
    layer_of = {node_id: 0 for node_id in order}
    for node_id in order:
        preds = predecessors.get(node_id, set())
        if preds:
            layer_of[node_id] = max(layer_of[pred] + 1 for pred in preds)
    return layer_of


def _compact_to_sinks(
    order: list[str],
    layer_of: dict[str, int],
    successors: dict[str, set[str]],
) -> None:
    changed = True
    while changed:
        changed = False
        for node_id in reversed(order):
            succs = successors.get(node_id, set())
            if not succs:
                continue
            upper_bound = min(layer_of[succ] - 1 for succ in succs)
            if upper_bound > layer_of[node_id]:
                layer_of[node_id] = upper_bound
                changed = True


def _layer_bounds(
    node_id: str,
    layer_of: dict[str, int],
    predecessors: dict[str, set[str]],
    successors: dict[str, set[str]],
) -> tuple[int, int]:
    lower = 0
    upper = max(layer_of.values(), default=0)
    preds = predecessors.get(node_id, set())
    succs = successors.get(node_id, set())
    if preds:
        lower = max(layer_of[pred] + 1 for pred in preds)
    if succs:
        upper = min(layer_of[succ] - 1 for succ in succs)
    if upper < lower:
        upper = lower
    return lower, upper


def _node_span_cost(
    node_id: str,
    candidate_layer: int,
    layer_of: dict[str, int],
    predecessors: dict[str, set[str]],
    successors: dict[str, set[str]],
) -> int:
    cost = 0
    for pred in predecessors.get(node_id, set()):
        cost += candidate_layer - layer_of[pred]
    for succ in successors.get(node_id, set()):
        cost += layer_of[succ] - candidate_layer
    return cost


def _promote_nodes(
    order: list[str],
    layer_of: dict[str, int],
    predecessors: dict[str, set[str]],
    successors: dict[str, set[str]],
) -> None:
    for _ in range(8):
        moved = False
        for node_id in order:
            lower, upper = _layer_bounds(node_id, layer_of, predecessors, successors)
            current = layer_of[node_id]
            best_layer = current
            best_cost = _node_span_cost(node_id, current, layer_of, predecessors, successors)
            for candidate in range(lower, upper + 1):
                candidate_cost = _node_span_cost(node_id, candidate, layer_of, predecessors, successors)
                if candidate_cost < best_cost:
                    best_cost = candidate_cost
                    best_layer = candidate
            if best_layer != current:
                layer_of[node_id] = best_layer
                moved = True
        _compact_to_sinks(order, layer_of, successors)
        if not moved:
            break


def _node_layer_constraint(node) -> str:
    if node is None:
        return ""
    value = (
        node.properties.get("layer_constraint")
        or node.properties.get("layerConstraint")
        or node.layout_options.get("org.vera.sugiyama.layered.layering.layerConstraint")
        or ""
    )
    return str(value).upper()


def _node_layer_id(node) -> int | None:
    if node is None:
        return None
    value = (
        node.properties.get("layer_id")
        or node.properties.get("layerId")
        or node.layout_options.get("org.vera.sugiyama.layered.layering.layerId")
    )
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _apply_constraints(
    node_by_id,
    layer_of: dict[str, int],
    order: list[str],
    predecessors: dict[str, set[str]],
    successors: dict[str, set[str]],
) -> None:
    first_nodes = [node_id for node_id in order if _node_layer_constraint(node_by_id.get(node_id)) == "FIRST"]
    last_nodes = [node_id for node_id in order if _node_layer_constraint(node_by_id.get(node_id)) == "LAST"]
    exact_nodes = [node_id for node_id in order if _node_layer_id(node_by_id.get(node_id)) is not None]

    if first_nodes:
        for node_id in first_nodes:
            layer_of[node_id] = 0
        changed = True
        while changed:
            changed = False
            for node_id in order:
                preds = predecessors.get(node_id, set())
                if preds:
                    required = max(layer_of[pred] + 1 for pred in preds)
                    if required > layer_of[node_id]:
                        layer_of[node_id] = required
                        changed = True

    if last_nodes:
        max_other = max((layer for node_id, layer in layer_of.items() if node_id not in set(last_nodes)), default=0)
        target_last = max_other + 1
        for node_id in last_nodes:
            layer_of[node_id] = max(layer_of[node_id], target_last)

    for node_id in exact_nodes:
        exact_layer = _node_layer_id(node_by_id.get(node_id))
        if exact_layer is not None:
            layer_of[node_id] = max(layer_of[node_id], exact_layer)


def _normalize_layers(layer_of: dict[str, int]) -> dict[str, int]:
    used_layers = sorted(set(layer_of.values()))
    remap = {layer: idx for idx, layer in enumerate(used_layers)}
    return {node_id: remap[layer] for node_id, layer in layer_of.items()}


class LayeringPhase:
    name = "layering"

    def run(self, context: LayoutContext) -> None:
        node_ids = [node.identifier for node in context.graph.children]
        node_by_id = context.graph.node_by_id()
        prefer_model_order = _consider_model_order_enabled(context)
        strategy = _layering_strategy(context)
        successors: dict[str, set[str]] = context.phase_state.get("dag_successors", {})
        predecessors: dict[str, set[str]] = context.phase_state.get("dag_predecessors", {})
        if not successors:
            successors = {node_id: set() for node_id in node_ids}
        if not predecessors:
            predecessors = {node_id: set() for node_id in node_ids}

        order = _topological_order(node_ids, successors, predecessors, node_by_id, prefer_model_order)
        layer_of = _longest_path_layers(order, predecessors)
        if strategy in {"NETWORK_SIMPLEX", "INTERACTIVE"}:
            _compact_to_sinks(order, layer_of, successors)
            _promote_nodes(order, layer_of, predecessors, successors)
        elif strategy in {"LONGEST_PATH", "LONGEST_PATH_SOURCE"}:
            pass
        else:
            _compact_to_sinks(order, layer_of, successors)
        _apply_constraints(node_by_id, layer_of, order, predecessors, successors)
        layer_of = _normalize_layers(layer_of)

        context.phase_state["topological_order"] = order
        context.phase_state["layer_of"] = layer_of
        context.report.notes.append("Layering uses longest-path assignment, sink compaction, local node promotion, basic layer constraints and layer normalization.")
