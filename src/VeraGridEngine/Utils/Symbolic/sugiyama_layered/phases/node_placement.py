# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from ..pipeline import LayoutContext


def _node_dimensions(node_id: str, expanded_nodes, node_by_id) -> tuple[float, float]:
    node_info = expanded_nodes.get(node_id)
    if node_info is not None:
        return node_info.width, node_info.height
    node = node_by_id.get(node_id)
    if node is not None:
        return node.width, node.height
    return 30.0, 30.0


def _node_height(node_id: str, expanded_nodes, node_by_id) -> float:
    return _node_dimensions(node_id, expanded_nodes, node_by_id)[1]


def _node_width(node_id: str, expanded_nodes, node_by_id) -> float:
    return _node_dimensions(node_id, expanded_nodes, node_by_id)[0]


def _layout_direction(context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    return str(options.get("org.vera.sugiyama.direction", "RIGHT")).upper()


def _fixed_alignment(context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    return str(options.get("org.vera.sugiyama.layered.nodePlacement.bk.fixedAlignment", "NONE")).upper()


def _port_side(port) -> str:
    side = (
        port.layout_options.get("org.vera.sugiyama.port.side")
        or port.properties.get("side")
        or ""
    )
    return str(side).upper()


def _effective_port_side(port, role: str, direction: str) -> str:
    side = _port_side(port)
    if side and side != "UNDEFINED":
        return side
    if direction == "LEFT":
        return "WEST" if role == "output" else "EAST"
    if direction == "DOWN":
        return "SOUTH" if role == "output" else "NORTH"
    if direction == "UP":
        return "NORTH" if role == "output" else "SOUTH"
    return "EAST" if role == "output" else "WEST"


def _port_sort_key(port) -> tuple[int, int, str]:
    side_rank = {
        "WEST": 0,
        "NORTH": 1,
        "SOUTH": 2,
        "EAST": 3,
    }.get(_port_side(port), 4)
    index = int(port.properties.get("port_index", 0))
    return (side_rank, index, port.identifier)


def _port_alignment(node, context: LayoutContext, side: str) -> str:
    options = context.option_resolver.resolve_for_element(
        context.graph.layout_options,
        getattr(node, "layout_options", {}),
    )
    side_key = f"org.vera.sugiyama.portAlignment.{side.lower()}"
    value = options.get(side_key) or options.get("org.vera.sugiyama.portAlignment.default", "CENTER")
    return str(value).upper()


def _node_port_constraints(node, context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(
        context.graph.layout_options,
        getattr(node, "layout_options", {}),
    )
    return str(options.get("org.vera.sugiyama.portConstraints", "UNDEFINED")).upper()


def _align_norm(norm: float, alignment: str, count: int) -> float:
    if alignment == "BEGIN":
        return min(norm, 0.25 if count > 1 else 0.5)
    if alignment == "END":
        return max(norm, 0.75 if count > 1 else 0.5)
    return norm


def _assign_port_positions(context: LayoutContext, node_by_id) -> None:
    direction = _layout_direction(context)
    for node in context.graph.children:
        if node.x is None or node.y is None or not node.ports:
            continue

        constraints = _node_port_constraints(node, context)

        grouped: dict[str, list] = {"WEST": [], "EAST": [], "NORTH": [], "SOUTH": [], "UNDEFINED": []}
        for port in sorted(node.ports, key=_port_sort_key):
            role = str(port.properties.get("role", "")).lower()
            effective_side = _effective_port_side(port, role, direction)
            grouped.setdefault(effective_side, []).append(port)

        for side, ports in grouped.items():
            if not ports:
                continue
            alignment = _port_alignment(node, context, side if side != "UNDEFINED" else "east")
            count = len(ports)
            for idx, port in enumerate(ports):
                if constraints in {"FIXED_POS", "FIXED_RATIO"} and port.x is not None and port.y is not None:
                    continue
                norm = (idx + 1) / (count + 1) if count else 0.5
                norm = _align_norm(norm, alignment, count)
                if side == "WEST":
                    port.x = node.x - port.width / 2.0
                    port.y = node.y + norm * node.height - port.height / 2.0
                elif side == "NORTH":
                    port.x = node.x + norm * node.width - port.width / 2.0
                    port.y = node.y - port.height / 2.0
                elif side == "SOUTH":
                    port.x = node.x + norm * node.width - port.width / 2.0
                    port.y = node.y + node.height - port.height / 2.0
                else:
                    port.x = node.x + node.width - port.width / 2.0
                    port.y = node.y + norm * node.height - port.height / 2.0


def _assign_node_coordinates(
    context: LayoutContext,
    ordered_layers: dict[int, list[str]],
    expanded_nodes,
    node_by_id,
    spacing_x: float,
    spacing_y: float,
    y_of_node: dict[str, float],
) -> tuple[dict[str, tuple[float, float]], dict[int, float]]:
    direction = _layout_direction(context)
    vertical_flow = direction in {"DOWN", "UP"}
    reverse_flow = direction in {"LEFT", "UP"}

    layer_positions: dict[int, float] = {}
    current_pos = 0.0
    for layer_idx, node_ids in sorted(ordered_layers.items()):
        layer_positions[layer_idx] = current_pos
        if vertical_flow:
            current_pos += max((_node_height(node_id, expanded_nodes, node_by_id) for node_id in node_ids), default=30.0) + spacing_y
        else:
            current_pos += max((_node_width(node_id, expanded_nodes, node_by_id) for node_id in node_ids), default=30.0) + spacing_x

    max_layer_pos = max(layer_positions.values(), default=0.0)
    virtual_positions: dict[str, tuple[float, float]] = {}

    for layer_idx, node_ids in sorted(ordered_layers.items()):
        layer_pos = layer_positions[layer_idx]
        if reverse_flow:
            layer_pos = max_layer_pos - layer_pos
        for node_id in node_ids:
            orth_pos = y_of_node.get(node_id, 0.0)
            if vertical_flow:
                x = orth_pos
                y = layer_pos
            else:
                x = layer_pos
                y = orth_pos
            virtual_positions[node_id] = (x, y)

    return virtual_positions, layer_positions


def _ordered_neighbors(
    node_id: str,
    neighbors: dict[str, set[str]],
    order_in_layer: dict[str, int],
) -> list[str]:
    return sorted(neighbors.get(node_id, set()), key=lambda other: order_in_layer.get(other, 0))


def _median_neighbor(
    node_id: str,
    neighbors: dict[str, set[str]],
    order_in_layer: dict[str, int],
) -> str | None:
    ordered = _ordered_neighbors(node_id, neighbors, order_in_layer)
    if not ordered:
        return None
    return ordered[(len(ordered) - 1) // 2]


def _alignment_pass(
    ordered_layers: dict[int, list[str]],
    layer_ids: list[int],
    order_in_layer: dict[str, int],
    neighbors: dict[str, set[str]],
    reverse_layers: bool,
) -> tuple[dict[str, str], dict[str, str]]:
    all_nodes = [node_id for layer_idx in layer_ids for node_id in ordered_layers[layer_idx]]
    root = {node_id: node_id for node_id in all_nodes}
    align = {node_id: node_id for node_id in all_nodes}

    traversed_layers = list(layer_ids)
    if reverse_layers:
        traversed_layers = list(reversed(traversed_layers))

    for layer_idx in traversed_layers:
        layer = list(ordered_layers[layer_idx])
        if reverse_layers:
            layer.reverse()
            barrier = len(ordered_layers[layer_idx])
        else:
            barrier = -1

        for node_id in layer:
            median = _median_neighbor(node_id, neighbors, order_in_layer)
            if median is None:
                continue
            median_pos = order_in_layer.get(median, 0)
            can_align = median_pos < barrier if reverse_layers else median_pos > barrier
            if can_align and align[node_id] == node_id:
                align[median] = node_id
                root[node_id] = root[median]
                barrier = median_pos

    return root, align


def _build_blocks(root: dict[str, str], align: dict[str, str]) -> list[list[str]]:
    visited: set[str] = set()
    blocks: list[list[str]] = []
    for node_id in root:
        if node_id in visited or root[node_id] != node_id:
            continue
        block = [node_id]
        visited.add(node_id)
        current = node_id
        while align[current] != current:
            current = align[current]
            block.append(current)
            visited.add(current)
        blocks.append(block)
    return blocks


def _block_neighbors(
    ordered_layers: dict[int, list[str]],
    layer_of: dict[str, int],
    order_in_layer: dict[str, int],
    blocks: list[list[str]],
    block_of: dict[str, int],
    block_idx: int,
) -> set[int]:
    neighbors: set[int] = set()
    for node_id in blocks[block_idx]:
        layer_idx = layer_of[node_id]
        order_idx = order_in_layer[node_id]
        layer = ordered_layers[layer_idx]
        if order_idx > 0:
            left_node = layer[order_idx - 1]
            left_block = block_of[left_node]
            if left_block != block_idx:
                neighbors.add(left_block)
        if order_idx < len(layer) - 1:
            right_node = layer[order_idx + 1]
            right_block = block_of[right_node]
            if right_block != block_idx:
                neighbors.add(right_block)
    return neighbors


def _compact_blocks(
    ordered_layers: dict[int, list[str]],
    layer_of: dict[str, int],
    order_in_layer: dict[str, int],
    blocks: list[list[str]],
    block_of: dict[str, int],
    expanded_nodes,
    node_by_id,
    predecessors: dict[str, set[str]],
    successors: dict[str, set[str]],
    spacing_y: float,
) -> dict[int, float]:
    block_y: dict[int, float] = {}
    block_height: dict[int, float] = {}

    for block_idx, block in enumerate(blocks):
        first_node = block[0]
        layer_idx = layer_of[first_node]
        order_idx = order_in_layer[first_node]
        preceding_nodes = ordered_layers[layer_idx][:order_idx]
        base_y = 0.0
        for node_id in preceding_nodes:
            if block_of[node_id] == block_idx:
                continue
            base_y += _node_height(node_id, expanded_nodes, node_by_id) + spacing_y
        block_y[block_idx] = base_y
        block_height[block_idx] = max(_node_height(node_id, expanded_nodes, node_by_id) for node_id in block)

    changed = True
    iteration = 0
    while changed and iteration < 24:
        iteration += 1
        changed = False
        for block_idx, block in enumerate(blocks):
            min_allowed = 0.0
            for neighbor_block in sorted(
                _block_neighbors(
                    ordered_layers=ordered_layers,
                    layer_of=layer_of,
                    order_in_layer=order_in_layer,
                    blocks=blocks,
                    block_of=block_of,
                    block_idx=block_idx,
                )
            ):
                for node_id in block:
                    for other in blocks[neighbor_block]:
                        if layer_of[node_id] == layer_of[other] and order_in_layer[other] < order_in_layer[node_id]:
                            min_allowed = max(
                                min_allowed,
                                block_y[neighbor_block] + _node_height(other, expanded_nodes, node_by_id) + spacing_y,
                            )

            barycenters = []
            for node_id in block:
                connected_blocks = [
                    other
                    for other in (predecessors.get(node_id, set()) | successors.get(node_id, set()))
                    if other in block_of
                ]
                if not connected_blocks:
                    continue
                barycenters.append(
                    sum(
                        block_y[block_of[other]] + _node_height(other, expanded_nodes, node_by_id) / 2.0
                        for other in connected_blocks
                    ) / len(connected_blocks)
                )
            target = (sum(barycenters) / len(barycenters)) - block_height[block_idx] / 2.0 if barycenters else block_y[block_idx]
            new_y = max(min_allowed, target)
            if abs(new_y - block_y[block_idx]) > 1e-6:
                block_y[block_idx] = new_y
                changed = True

    return block_y


def _positions_from_blocks(blocks: list[list[str]], block_y: dict[int, float]) -> dict[str, float]:
    y_of_node: dict[str, float] = {}
    for block_idx, block in enumerate(blocks):
        for node_id in block:
            y_of_node[node_id] = block_y[block_idx]
    return y_of_node


def _compute_vertical_coordinates(
    ordered_layers: dict[int, list[str]],
    layer_of: dict[str, int],
    order_in_layer: dict[str, int],
    predecessors: dict[str, set[str]],
    successors: dict[str, set[str]],
    expanded_nodes,
    node_by_id,
    spacing_y: float,
    fixed_alignment: str,
) -> dict[str, float]:
    layer_ids = sorted(ordered_layers)
    variants: list[dict[str, float]] = []
    all_passes = {
        "LEFT_UP": (predecessors, False),
        "RIGHT_UP": (predecessors, True),
        "LEFT_DOWN": (successors, False),
        "RIGHT_DOWN": (successors, True),
    }
    if fixed_alignment in all_passes:
        passes = [all_passes[fixed_alignment]]
    else:
        passes = list(all_passes.values())

    for neighbors, reverse_layers in passes:
        root, align = _alignment_pass(
            ordered_layers=ordered_layers,
            layer_ids=layer_ids,
            order_in_layer=order_in_layer,
            neighbors=neighbors,
            reverse_layers=reverse_layers,
        )
        blocks = _build_blocks(root, align)
        block_of = {
            node_id: block_idx
            for block_idx, block in enumerate(blocks)
            for node_id in block
        }
        block_y = _compact_blocks(
            ordered_layers=ordered_layers,
            layer_of=layer_of,
            order_in_layer=order_in_layer,
            blocks=blocks,
            block_of=block_of,
            expanded_nodes=expanded_nodes,
            node_by_id=node_by_id,
            predecessors=predecessors,
            successors=successors,
            spacing_y=spacing_y,
        )
        variants.append(_positions_from_blocks(blocks, block_y))

    y_of_node: dict[str, float] = {}
    all_nodes = [node_id for layer_idx in layer_ids for node_id in ordered_layers[layer_idx]]
    for node_id in all_nodes:
        coords = sorted(variant.get(node_id, 0.0) for variant in variants)
        if not coords:
            y_of_node[node_id] = 0.0
        elif len(coords) % 2 == 1:
            y_of_node[node_id] = coords[len(coords) // 2]
        else:
            mid = len(coords) // 2
            y_of_node[node_id] = (coords[mid - 1] + coords[mid]) / 2.0
    return y_of_node


def _stack_layer(
    node_ids: list[str],
    y_of_node: dict[str, float],
    spacing_y: float,
    expanded_nodes,
    node_by_id,
) -> None:
    cursor_y = 0.0
    for node_id in node_ids:
        y = max(cursor_y, y_of_node.get(node_id, 0.0))
        y_of_node[node_id] = y
        cursor_y = y + _node_height(node_id, expanded_nodes, node_by_id) + spacing_y


def _straighten_dummy_chains(
    edge_paths: dict[str, list[str]],
    y_of_node: dict[str, float],
    expanded_nodes,
    node_by_id,
    ordered_layers: dict[int, list[str]],
    spacing_y: float,
) -> None:
    desired_y: dict[str, float] = {}
    for path in edge_paths.values():
        if len(path) <= 2:
            continue
        src = path[0]
        dst = path[-1]
        if src not in y_of_node or dst not in y_of_node:
            continue
        src_center = y_of_node[src] + _node_height(src, expanded_nodes, node_by_id) / 2.0
        dst_center = y_of_node[dst] + _node_height(dst, expanded_nodes, node_by_id) / 2.0
        steps = len(path) - 1
        for idx, node_id in enumerate(path[1:-1], start=1):
            node_info = expanded_nodes.get(node_id)
            if node_info is None or not getattr(node_info, "is_dummy", False):
                continue
            interpolated = src_center + (dst_center - src_center) * (idx / steps)
            desired_y[node_id] = interpolated - _node_height(node_id, expanded_nodes, node_by_id) / 2.0

    if not desired_y:
        return

    for node_ids in ordered_layers.values():
        for node_id in node_ids:
            if node_id in desired_y:
                y_of_node[node_id] = desired_y[node_id]
        _stack_layer(node_ids, y_of_node, spacing_y, expanded_nodes, node_by_id)


def _tile_components(
    virtual_positions: dict[str, tuple[float, float]],
    expanded_nodes,
    components: list[list[str]],
    edge_paths: dict[str, list[str]],
    spacing_components: float,
    direction: str,
) -> None:
    if len(components) <= 1:
        return

    node_to_component: dict[str, int] = {}
    for comp_idx, component in enumerate(components):
        for node_id in component:
            node_to_component[node_id] = comp_idx

    for path in edge_paths.values():
        if not path:
            continue
        comp_idx = node_to_component.get(path[0])
        if comp_idx is None:
            continue
        for node_id in path[1:-1]:
            if node_id in expanded_nodes:
                node_to_component[node_id] = comp_idx

    component_bounds: list[tuple[float, float, float, float] | None] = [None] * len(components)
    for node_id, (x, y) in virtual_positions.items():
        comp_idx = node_to_component.get(node_id)
        node_info = expanded_nodes.get(node_id)
        if comp_idx is None or node_info is None:
            continue
        bounds = component_bounds[comp_idx]
        right = x + node_info.width
        bottom = y + node_info.height
        if bounds is None:
            component_bounds[comp_idx] = (x, y, right, bottom)
        else:
            left, top, curr_right, curr_bottom = bounds
            component_bounds[comp_idx] = (
                min(left, x),
                min(top, y),
                max(curr_right, right),
                max(curr_bottom, bottom),
            )

    vertical_flow = direction in {"DOWN", "UP"}
    cursor = 0.0
    for comp_idx, bounds in enumerate(component_bounds):
        if bounds is None:
            continue
        left, top, right, bottom = bounds
        if vertical_flow:
            shift_x = 0.0
            shift_y = cursor - top
        else:
            shift_x = cursor - left
            shift_y = 0.0
        if abs(shift_x) > 1e-9 or abs(shift_y) > 1e-9:
            for node_id, owner_idx in node_to_component.items():
                if owner_idx != comp_idx or node_id not in virtual_positions:
                    continue
                x, y = virtual_positions[node_id]
                virtual_positions[node_id] = (x + shift_x, y + shift_y)
        cursor += (bottom - top if vertical_flow else right - left) + spacing_components


def _rectangles_overlap(
    left_a: float,
    top_a: float,
    right_a: float,
    bottom_a: float,
    left_b: float,
    top_b: float,
    right_b: float,
    bottom_b: float,
    margin: float = 0.0,
) -> bool:
    return not (
        right_a + margin <= left_b
        or right_b + margin <= left_a
        or bottom_a + margin <= top_b
        or bottom_b + margin <= top_a
    )


def _resolve_node_overlaps(
    virtual_positions: dict[str, tuple[float, float]],
    expanded_nodes,
    spacing_x: float,
    spacing_y: float,
    direction: str,
) -> None:
    horizontal_flow = direction in {"RIGHT", "LEFT"}
    primary_gap = spacing_x if horizontal_flow else spacing_y
    secondary_gap = spacing_y if horizontal_flow else spacing_x

    for _ in range(16):
        moved = False
        items = []
        for node_id, (x, y) in virtual_positions.items():
            node_info = expanded_nodes.get(node_id)
            if node_info is None:
                continue
            items.append((node_id, x, y, x + node_info.width, y + node_info.height))
        items.sort(key=lambda item: (item[1], item[2], item[0]))

        for index, (node_id, left_a, top_a, right_a, bottom_a) in enumerate(items):
            if moved:
                break
            for other_id, left_b, top_b, right_b, bottom_b in items[index + 1:]:
                if not _rectangles_overlap(
                    left_a,
                    top_a,
                    right_a,
                    bottom_a,
                    left_b,
                    top_b,
                    right_b,
                    bottom_b,
                    margin=2.0,
                ):
                    continue

                other_info = expanded_nodes.get(other_id)
                if other_info is None:
                    continue

                x_b, y_b = virtual_positions[other_id]
                if horizontal_flow:
                    same_column = abs(left_a - left_b) < max(primary_gap * 0.5, 1.0)
                    if same_column:
                        y_b = bottom_a + secondary_gap
                    else:
                        x_b = right_a + primary_gap
                else:
                    same_row = abs(top_a - top_b) < max(primary_gap * 0.5, 1.0)
                    if same_row:
                        x_b = right_a + secondary_gap
                    else:
                        y_b = bottom_a + primary_gap

                virtual_positions[other_id] = (x_b, y_b)
                moved = True
                break

        if not moved:
            break


class NodePlacementPhase:
    name = "node-placement"

    def run(self, context: LayoutContext) -> None:
        graph_options = context.option_resolver.resolve_for_element(context.graph.layout_options)
        spacing_x = float(graph_options["org.vera.sugiyama.layered.spacing.nodeNodeBetweenLayers"])
        spacing_y = float(graph_options["org.vera.sugiyama.spacing.nodeNode"])
        spacing_components = float(graph_options["org.vera.sugiyama.spacing.componentComponent"])
        direction = _layout_direction(context)
        fixed_alignment = _fixed_alignment(context)
        ordered_layers: dict[int, list[str]] = context.phase_state.get("ordered_layers", {})
        expanded_nodes = context.phase_state.get("expanded_nodes", {})
        edge_paths: dict[str, list[str]] = context.phase_state.get("edge_paths", {})
        predecessors: dict[str, set[str]] = context.phase_state.get("expanded_predecessors", {})
        successors: dict[str, set[str]] = context.phase_state.get("expanded_successors", {})
        components: list[list[str]] = context.phase_state.get("components", [])
        layer_of: dict[str, int] = {
            node_id: layer_idx
            for layer_idx, node_ids in ordered_layers.items()
            for node_id in node_ids
        }
        order_in_layer: dict[str, int] = context.phase_state.get("order_in_layer", {})
        node_by_id = context.graph.node_by_id()

        y_of_node = _compute_vertical_coordinates(
            ordered_layers=ordered_layers,
            layer_of=layer_of,
            order_in_layer=order_in_layer,
            predecessors=predecessors,
            successors=successors,
            expanded_nodes=expanded_nodes,
            node_by_id=node_by_id,
            spacing_y=spacing_y,
            fixed_alignment=fixed_alignment,
        )
        _straighten_dummy_chains(
            edge_paths=edge_paths,
            y_of_node=y_of_node,
            expanded_nodes=expanded_nodes,
            node_by_id=node_by_id,
            ordered_layers=ordered_layers,
            spacing_y=spacing_y,
        )
        for _, node_ids in sorted(ordered_layers.items()):
            _stack_layer(node_ids, y_of_node, spacing_y, expanded_nodes, node_by_id)

        virtual_positions, layer_positions = _assign_node_coordinates(
            context=context,
            ordered_layers=ordered_layers,
            expanded_nodes=expanded_nodes,
            node_by_id=node_by_id,
            spacing_x=spacing_x,
            spacing_y=spacing_y,
            y_of_node=y_of_node,
        )

        _tile_components(
            virtual_positions=virtual_positions,
            expanded_nodes=expanded_nodes,
            components=components,
            edge_paths=edge_paths,
            spacing_components=spacing_components,
            direction=direction,
        )
        _resolve_node_overlaps(
            virtual_positions=virtual_positions,
            expanded_nodes=expanded_nodes,
            spacing_x=spacing_x,
            spacing_y=spacing_y,
            direction=direction,
        )

        for node_id, (x, y) in virtual_positions.items():
            node = node_by_id.get(node_id)
            if node is not None:
                node.x = x
                node.y = y

        _assign_port_positions(context, node_by_id)

        context.phase_state["virtual_positions"] = virtual_positions
        context.phase_state["layer_x"] = layer_positions
        context.phase_state["y_of_node"] = y_of_node
        context.report.notes.append("Node placement uses a Brandes-Koepf-style multi-pass vertical alignment.")
