# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass

from VeraGridEngine.Utils.SugiyamaLayered.pipeline import LayoutContext


@dataclass(frozen=True)
class VirtualNode:
    identifier: str
    width: float
    height: float
    is_dummy: bool = False
    original_edge_id: str | None = None
    chain_index: int = 0
    chain_priority: int = 0
    model_order: int = 0


def _node_model_order(node_id: str, fallback: int, node_by_id) -> int:
    node = node_by_id.get(node_id)
    if node is None:
        return fallback
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
    return fallback


def _edge_chain_priority(entry: dict[str, str | bool | None]) -> int:
    if bool(entry.get("reversed", False)):
        return 1
    return 0


class LongEdgePhase:
    name = "long-edges"

    def run(self, context: LayoutContext) -> None:
        layer_of: dict[str, int] = context.phase_state.get("layer_of", {})
        oriented_edges: list[dict[str, str | bool | None]] = context.phase_state.get("oriented_edges", [])
        node_by_id = context.graph.node_by_id()
        node_order = {node_id: idx for idx, node_id in enumerate(context.phase_state.get("topological_order", []))}
        expanded_nodes: dict[str, VirtualNode] = {
            node.identifier: VirtualNode(
                identifier=node.identifier,
                width=node.width,
                height=node.height,
                is_dummy=False,
                model_order=_node_model_order(node.identifier, node_order.get(node.identifier, 0), node_by_id),
            )
            for node in context.graph.children
        }
        expanded_layers: dict[int, list[str]] = {}
        for node_id, layer in layer_of.items():
            expanded_layers.setdefault(int(layer), []).append(node_id)

        dummy_size = 12.0
        expanded_edges: list[tuple[str, str, str, int]] = []
        edge_paths: dict[str, list[str]] = {}
        long_edges: list[str] = []
        dummy_counter = 0

        for edge_index, entry in enumerate(oriented_edges):
            edge_id = str(entry["edge_id"])
            src = str(entry["source"])
            dst = str(entry["target"])
            src_layer = int(layer_of.get(src, 0))
            dst_layer = int(layer_of.get(dst, src_layer))

            if src == dst or dst_layer - src_layer <= 1:
                expanded_edges.append((edge_id, src, dst, 0))
                edge_paths[edge_id] = [src, dst]
                continue

            long_edges.append(edge_id)
            previous = src
            path = [src]
            src_order = _node_model_order(src, node_order.get(src, edge_index), node_by_id)
            dst_order = _node_model_order(dst, node_order.get(dst, edge_index), node_by_id)
            chain_priority = _edge_chain_priority(entry)
            for hop_layer in range(src_layer + 1, dst_layer):
                dummy_id = f"__dummy__{edge_id}__{dummy_counter}"
                dummy_counter += 1
                expanded_nodes[dummy_id] = VirtualNode(
                    identifier=dummy_id,
                    width=dummy_size,
                    height=dummy_size,
                    is_dummy=True,
                    original_edge_id=edge_id,
                    chain_index=hop_layer - src_layer,
                    chain_priority=chain_priority,
                    model_order=min(src_order, dst_order),
                )
                expanded_layers.setdefault(hop_layer, []).append(dummy_id)
                expanded_edges.append((edge_id, previous, dummy_id, hop_layer - src_layer - 1))
                path.append(dummy_id)
                previous = dummy_id
            expanded_edges.append((edge_id, previous, dst, dst_layer - src_layer - 1))
            path.append(dst)
            edge_paths[edge_id] = path

        for layer_idx in expanded_layers:
            expanded_layers[layer_idx] = sorted(
                expanded_layers[layer_idx],
                key=lambda node_id: (
                    expanded_nodes[node_id].chain_priority,
                    expanded_nodes[node_id].model_order,
                    expanded_nodes[node_id].chain_index,
                    expanded_nodes[node_id].is_dummy,
                    node_id,
                ),
            )

        context.phase_state["long_edges"] = sorted(set(long_edges))
        context.phase_state["expanded_nodes"] = expanded_nodes
        context.phase_state["expanded_layers"] = expanded_layers
        context.phase_state["expanded_edges"] = expanded_edges
        context.phase_state["edge_paths"] = edge_paths
        context.report.notes.append(
            f"Long-edge expansion inserted {dummy_counter} dummy node(s) across {len(set(long_edges))} edge(s)."
        )
