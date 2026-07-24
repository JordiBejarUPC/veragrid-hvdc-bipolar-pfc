# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from VeraGridEngine.Utils.SugiyamaLayered.pipeline import LayoutContext


def _barycenter(values: list[float], fallback: float) -> float:
    if not values:
        return fallback
    return sum(values) / len(values)


def _median(values: list[float], fallback: float) -> float:
    if not values:
        return fallback
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _neighbor_positions(
    node_id: str,
    neighbors: dict[str, set[str]],
    reference_order: dict[str, int],
) -> list[float]:
    return [
        float(reference_order[other])
        for other in sorted(neighbors.get(node_id, set()))
        if other in reference_order
    ]


def _crossings_between(
    upper: list[str],
    lower: list[str],
    successors: dict[str, set[str]],
) -> int:
    lower_pos = {node_id: idx for idx, node_id in enumerate(lower)}
    count = 0
    for idx, left_node in enumerate(upper):
        left_targets = [node for node in successors.get(left_node, set()) if node in lower_pos]
        if not left_targets:
            continue
        for right_node in upper[idx + 1:]:
            right_targets = [node for node in successors.get(right_node, set()) if node in lower_pos]
            if not right_targets:
                continue
            for left_target in left_targets:
                left_pos = lower_pos[left_target]
                for right_target in right_targets:
                    if lower_pos[right_target] < left_pos:
                        count += 1
    return count


def _node_model_order(node_id: str, fallback: int, expanded_nodes, node_by_id) -> int:
    node_info = expanded_nodes.get(node_id)
    if node_info is not None:
        model_order = getattr(node_info, "model_order", None)
        if isinstance(model_order, int):
            return model_order
    node = node_by_id.get(node_id)
    if node is None:
        return fallback
    candidates = (
        node.properties.get("modelOrder"),
        node.properties.get("model_order"),
        node.layout_options.get("org.vera.sugiyama.layered.considerModelOrder.groupModelOrder.crossingMinimizationId"),
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


def _crossing_strategy(context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    return str(options.get("org.vera.sugiyama.layered.crossingMinimization.strategy", "LAYER_SWEEP")).upper()


def _sweep_order(
    layer: list[str],
    reference_layer: list[str],
    neighbors: dict[str, set[str]],
    chain_order: dict[str, int],
    expanded_nodes,
    model_order: dict[str, int],
    prefer_model_order: bool,
    use_median: bool,
) -> list[str]:
    reference_order = {node_id: idx for idx, node_id in enumerate(reference_layer)}
    current_order = {node_id: idx for idx, node_id in enumerate(layer)}
    scored: list[tuple[tuple[float, float, int, str], str]] = []
    for node_id in layer:
        values = _neighbor_positions(node_id, neighbors, reference_order)
        fallback = float(current_order.get(node_id, 0))
        primary = _median(values, fallback) if use_median else _barycenter(values, fallback)
        secondary = _barycenter(values, fallback) if use_median else _median(values, fallback)
        node_info = expanded_nodes.get(node_id)
        dummy_bias = -0.25 if node_info is not None and getattr(node_info, "is_dummy", False) else 0.0
        scored.append(
            (
                (
                    primary + dummy_bias,
                    secondary,
                    chain_order.get(node_id, 0),
                    model_order.get(node_id, current_order.get(node_id, 0)) if prefer_model_order else current_order.get(node_id, 0),
                    current_order.get(node_id, 0),
                    node_id,
                ),
                node_id,
            )
        )
    scored.sort(key=lambda item: item[0])
    return [node_id for _, node_id in scored]


def _transpose_layer_pair(
    upper: list[str],
    lower: list[str],
    successors: dict[str, set[str]],
) -> None:
    changed = True
    iteration = 0
    while changed and iteration < 4:
        changed = False
        iteration += 1
        idx = 0
        while idx < len(upper) - 1:
            current = _crossings_between(upper, lower, successors)
            swapped = list(upper)
            swapped[idx], swapped[idx + 1] = swapped[idx + 1], swapped[idx]
            swapped_crossings = _crossings_between(swapped, lower, successors)
            if swapped_crossings < current:
                upper[idx], upper[idx + 1] = upper[idx + 1], upper[idx]
                changed = True
            idx += 1


def _crossings_for_upper_pair(
    left: str,
    right: str,
    lower_pos: dict[str, int],
    successors: dict[str, set[str]],
) -> tuple[int, int]:
    left_targets = [lower_pos[node] for node in successors.get(left, set()) if node in lower_pos]
    right_targets = [lower_pos[node] for node in successors.get(right, set()) if node in lower_pos]
    before = 0
    after = 0
    for left_pos in left_targets:
        for right_pos in right_targets:
            if right_pos < left_pos:
                before += 1
            if left_pos < right_pos:
                after += 1
    return before, after


def _crossings_for_lower_pair(
    left: str,
    right: str,
    upper_pos: dict[str, int],
    predecessors: dict[str, set[str]],
) -> tuple[int, int]:
    left_sources = [upper_pos[node] for node in predecessors.get(left, set()) if node in upper_pos]
    right_sources = [upper_pos[node] for node in predecessors.get(right, set()) if node in upper_pos]
    before = 0
    after = 0
    for left_pos in left_sources:
        for right_pos in right_sources:
            if right_pos < left_pos:
                before += 1
            if left_pos < right_pos:
                after += 1
    return before, after


def _prefer_swap_tie_break(
    left: str,
    right: str,
    chain_order: dict[str, int],
    model_order: dict[str, int],
    prefer_model_order: bool,
) -> bool:
    if prefer_model_order:
        left_model = model_order.get(left, 0)
        right_model = model_order.get(right, 0)
        if left_model != right_model:
            return left_model > right_model
    left_chain = chain_order.get(left, 0)
    right_chain = chain_order.get(right, 0)
    if left_chain != right_chain:
        return left_chain > right_chain
    return left > right


def _transpose_layer_pair_local(
    upper: list[str],
    lower: list[str],
    successors: dict[str, set[str]],
    predecessors: dict[str, set[str]],
    chain_order: dict[str, int],
    model_order: dict[str, int],
    prefer_model_order: bool,
) -> None:
    changed = True
    iteration = 0
    while changed and iteration < 4:
        changed = False
        iteration += 1
        lower_pos = {node_id: idx for idx, node_id in enumerate(lower)}
        idx = 0
        while idx < len(upper) - 1:
            left = upper[idx]
            right = upper[idx + 1]
            before, after = _crossings_for_upper_pair(left, right, lower_pos, successors)
            if after < before or (
                after == before and _prefer_swap_tie_break(left, right, chain_order, model_order, prefer_model_order)
            ):
                upper[idx], upper[idx + 1] = upper[idx + 1], upper[idx]
                changed = True
            idx += 1

        upper_pos = {node_id: idx for idx, node_id in enumerate(upper)}
        idx = 0
        while idx < len(lower) - 1:
            left = lower[idx]
            right = lower[idx + 1]
            before, after = _crossings_for_lower_pair(left, right, upper_pos, predecessors)
            if after < before or (
                after == before and _prefer_swap_tie_break(left, right, chain_order, model_order, prefer_model_order)
            ):
                lower[idx], lower[idx + 1] = lower[idx + 1], lower[idx]
                changed = True
            idx += 1


def _total_crossings(layers: dict[int, list[str]], successors: dict[str, set[str]]) -> int:
    layer_ids = sorted(layers)
    return sum(
        _crossings_between(layers[upper], layers[lower], successors)
        for upper, lower in zip(layer_ids[:-1], layer_ids[1:])
    )


class CrossingMinimizationPhase:
    name = "crossing-minimization"

    def run(self, context: LayoutContext) -> None:
        expanded_layers: dict[int, list[str]] = context.phase_state.get("expanded_layers", {})
        expanded_edges: list[tuple[str, str, str, int]] = context.phase_state.get("expanded_edges", [])
        expanded_nodes = context.phase_state.get("expanded_nodes", {})
        edge_paths: dict[str, list[str]] = context.phase_state.get("edge_paths", {})
        node_by_id = context.graph.node_by_id()
        prefer_model_order = _consider_model_order_enabled(context)
        strategy = _crossing_strategy(context)
        if not expanded_layers:
            context.phase_state["ordered_layers"] = {}
            return

        layers = {layer_idx: list(nodes) for layer_idx, nodes in expanded_layers.items()}
        successors: dict[str, set[str]] = {}
        predecessors: dict[str, set[str]] = {}
        for _, src, dst, _ in expanded_edges:
            successors.setdefault(src, set()).add(dst)
            predecessors.setdefault(dst, set()).add(src)

        chain_order: dict[str, int] = {}
        for path in edge_paths.values():
            for idx, node_id in enumerate(path):
                if node_id not in chain_order or idx < chain_order[node_id]:
                    chain_order[node_id] = idx

        model_order: dict[str, int] = {}
        for layer_idx, nodes in layers.items():
            for idx, node_id in enumerate(nodes):
                fallback = layer_idx * 1000 + idx
                model_order[node_id] = _node_model_order(node_id, fallback, expanded_nodes, node_by_id)

        best_layers = {layer_idx: list(nodes) for layer_idx, nodes in layers.items()}
        best_crossings = _total_crossings(best_layers, successors)
        layer_ids = sorted(layers)

        if strategy == "NONE":
            order_in_layer = {
                node_id: idx
                for layer in best_layers.values()
                for idx, node_id in enumerate(layer)
            }
            context.phase_state["ordered_layers"] = best_layers
            context.phase_state["expanded_successors"] = successors
            context.phase_state["expanded_predecessors"] = predecessors
            context.phase_state["order_in_layer"] = order_in_layer
            context.report.notes.append("Crossing minimization disabled by strategy option.")
            return

        for sweep_idx in range(8):
            use_median = sweep_idx % 2 == 1
            for layer_idx in layer_ids[1:]:
                layers[layer_idx] = _sweep_order(
                    layer=layers[layer_idx],
                    reference_layer=layers[layer_idx - 1],
                    neighbors=predecessors,
                    chain_order=chain_order,
                    expanded_nodes=expanded_nodes,
                    model_order=model_order,
                    prefer_model_order=prefer_model_order,
                    use_median=use_median,
                )

            for layer_idx in reversed(layer_ids[:-1]):
                layers[layer_idx] = _sweep_order(
                    layer=layers[layer_idx],
                    reference_layer=layers[layer_idx + 1],
                    neighbors=successors,
                    chain_order=chain_order,
                    expanded_nodes=expanded_nodes,
                    model_order=model_order,
                    prefer_model_order=prefer_model_order,
                    use_median=use_median,
                )

            for upper_idx, lower_idx in zip(layer_ids[:-1], layer_ids[1:]):
                _transpose_layer_pair_local(
                    layers[upper_idx],
                    layers[lower_idx],
                    successors,
                    predecessors,
                    chain_order,
                    model_order,
                    prefer_model_order,
                )

            current_crossings = _total_crossings(layers, successors)
            if current_crossings < best_crossings:
                best_crossings = current_crossings
                best_layers = {layer_idx: list(nodes) for layer_idx, nodes in layers.items()}

        order_in_layer = {
            node_id: idx
            for layer in best_layers.values()
            for idx, node_id in enumerate(layer)
        }
        context.phase_state["ordered_layers"] = best_layers
        context.phase_state["expanded_successors"] = successors
        context.phase_state["expanded_predecessors"] = predecessors
        context.phase_state["order_in_layer"] = order_in_layer
        context.report.notes.append(
            f"Crossing minimization runs alternating barycenter/median sweeps with local transpose; best crossing count={best_crossings}."
        )
