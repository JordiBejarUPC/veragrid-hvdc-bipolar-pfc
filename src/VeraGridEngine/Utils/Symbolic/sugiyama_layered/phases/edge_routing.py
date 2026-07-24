# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from collections import defaultdict

from ..model import SugiyamaEdgeSection
from ..pipeline import LayoutContext


def _owner_of_port(context: LayoutContext, port_id: str):
    for node in context.graph.all_nodes():
        for port in node.ports:
            if port.identifier == port_id:
                return node
    return None


def _port_groups(node) -> tuple[list, list]:
    inputs = sorted(
        [port for port in node.ports if str(port.properties.get("role", "")).lower() == "input"],
        key=_port_sort_key,
    )
    outputs = sorted(
        [port for port in node.ports if str(port.properties.get("role", "")).lower() == "output"],
        key=_port_sort_key,
    )
    return inputs, outputs


def _port_sort_key(port) -> tuple[int, int, str]:
    side = _port_side(port)
    side_rank = {
        "WEST": 0,
        "NORTH": 1,
        "SOUTH": 2,
        "EAST": 3,
    }.get(side, 4)
    index = int(port.properties.get("port_index", 0))
    return (side_rank, index, port.identifier)


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


def _port_alignment(node, context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(
        context.graph.layout_options,
        getattr(node, "layout_options", {}),
    )
    return str(options.get("org.vera.sugiyama.portAlignment.default", "CENTER")).upper()


def _layout_direction(context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    return str(options.get("org.vera.sugiyama.direction", "RIGHT")).upper()


def _self_loop_distribution(context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    return str(options.get("org.vera.sugiyama.layered.edgeRouting.selfLoopDistribution", "NORTH")).upper()


def _edge_routing_mode(context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    return str(options.get("org.vera.sugiyama.edgeRouting", "ORTHOGONAL")).upper()


def _feedback_edges_enabled(context: LayoutContext) -> bool:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    value = options.get("org.vera.sugiyama.layered.feedbackEdges", False)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _node_port_constraints(node, context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(
        context.graph.layout_options,
        getattr(node, "layout_options", {}),
    )
    return str(options.get("org.vera.sugiyama.portConstraints", "UNDEFINED")).upper()


def _port_anchor(context: LayoutContext, endpoint_id: str, role: str) -> tuple[float, float] | None:
    direction = _layout_direction(context)
    node_by_id = context.graph.node_by_id()
    node = node_by_id.get(endpoint_id)
    port = None
    if node is None:
        port = context.graph.port_by_id().get(endpoint_id)
        if port is None:
            return None
        node = _owner_of_port(context, port.identifier)
    if node is None or node.x is None or node.y is None:
        return None

    if port is None:
        if role == "output":
            return (node.x + node.width, node.y + node.height / 2.0)
        return (node.x, node.y + node.height / 2.0)

    if port.x is not None and port.y is not None:
        return (port.x + port.width / 2.0, port.y + port.height / 2.0)

    inputs, outputs = _port_groups(node)
    ports = outputs if role == "output" else inputs
    constraints = _node_port_constraints(node, context)
    if port not in ports:
        if constraints in {"FIXED_ORDER", "FIXED_SIDE"}:
            ports = sorted(ports + [port], key=_port_sort_key)
        else:
            ports = [port]
    try:
        index = ports.index(port)
    except ValueError:
        index = 0
    if ports:
        norm = (index + 1) / (len(ports) + 1)
    else:
        norm = 0.5

    alignment = _port_alignment(node, context)
    if alignment == "BEGIN":
        norm = min(norm, 0.25 if len(ports) > 1 else 0.5)
    elif alignment == "END":
        norm = max(norm, 0.75 if len(ports) > 1 else 0.5)

    side = _effective_port_side(port, role, direction)
    if side in {"NORTH", "SOUTH"}:
        x = node.x + norm * node.width
        y = node.y if side == "NORTH" else node.y + node.height
        return (x, y)
    if side == "EAST":
        return (node.x + node.width, node.y + norm * node.height)
    if side == "WEST":
        return (node.x, node.y + norm * node.height)
    if role == "output":
        return (node.x + node.width, node.y + norm * node.height)
    return (node.x, node.y + norm * node.height)


def _all_node_bounds(context: LayoutContext) -> tuple[float, float, float, float]:
    nodes = [node for node in context.graph.children if node.x is not None and node.y is not None]
    if not nodes:
        return (0.0, 0.0, 0.0, 0.0)
    left = min(node.x for node in nodes)
    top = min(node.y for node in nodes)
    right = max(node.x + node.width for node in nodes)
    bottom = max(node.y + node.height for node in nodes)
    return (left, top, right, bottom)


def _node_rects(context: LayoutContext) -> list[tuple[str, float, float, float, float]]:
    rects: list[tuple[str, float, float, float, float]] = []
    for node in context.graph.children:
        if node.x is None or node.y is None:
            continue
        rects.append((node.identifier, node.x, node.y, node.x + node.width, node.y + node.height))
    return rects


def _clean(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for point in points:
        if not cleaned or cleaned[-1] != point:
            cleaned.append(point)
    return cleaned


def _is_between(value: float, a: float, b: float) -> bool:
    low = min(a, b)
    high = max(a, b)
    return low <= value <= high


def _remove_collinear(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return list(points)
    result = [points[0]]
    for index in range(1, len(points) - 1):
        prev = result[-1]
        curr = points[index]
        nxt = points[index + 1]
        if (prev[0] == curr[0] == nxt[0]) or (prev[1] == curr[1] == nxt[1]):
            continue
        result.append(curr)
    result.append(points[-1])
    return result


def _remove_axis_reversals(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return list(points)
    result = [points[0]]
    for point in points[1:]:
        result.append(point)
        while len(result) >= 3:
            a = result[-3]
            b = result[-2]
            c = result[-1]
            if a == c:
                result.pop(-2)
                result.pop(-2)
                continue
            same_x = a[0] == b[0] == c[0]
            same_y = a[1] == b[1] == c[1]
            if same_x and _is_between(b[1], a[1], c[1]):
                result.pop(-2)
                continue
            if same_y and _is_between(b[0], a[0], c[0]):
                result.pop(-2)
                continue
            break
    return result


def _simplify_path(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    simplified = _clean(points)
    previous_length = -1
    while previous_length != len(simplified):
        previous_length = len(simplified)
        simplified = _remove_collinear(simplified)
        simplified = _remove_axis_reversals(simplified)
        simplified = _clean(simplified)
    return simplified


def _feedback_path(
    start: tuple[float, float],
    end: tuple[float, float],
    bounds: tuple[float, float, float, float],
    index: int,
    direction: str,
) -> list[tuple[float, float]]:
    left, top, right, bottom = bounds
    route_gap = 80.0 + index * 18.0
    if direction == "LEFT":
        outer_x = left - route_gap
        return _clean([start, (outer_x, start[1]), (outer_x, end[1]), end])
    if direction == "DOWN":
        outer_y = bottom + route_gap
        return _clean([start, (start[0], outer_y), (end[0], outer_y), end])
    if direction == "UP":
        outer_y = top - route_gap
        return _simplify_path([start, (start[0], outer_y), (end[0], outer_y), end])
    outer_x = right + route_gap
    upper_y = top - route_gap
    return _simplify_path([start, (outer_x, start[1]), (outer_x, upper_y), (end[0] - 24.0, upper_y), (end[0] - 24.0, end[1]), end])


def _self_loop_path(
    node,
    start: tuple[float, float],
    end: tuple[float, float],
    index: int,
    direction: str,
    distribution: str,
) -> list[tuple[float, float]]:
    route_gap = 80.0 + index * 18.0
    if distribution == "SOUTH":
        outer_y = node.y + node.height + route_gap
        return _simplify_path([start, (start[0], outer_y), (end[0], outer_y), end])
    if distribution == "WEST":
        outer_x = node.x - route_gap
        return _simplify_path([start, (outer_x, start[1]), (outer_x, end[1]), end])
    if distribution == "EAST":
        outer_x = node.x + node.width + route_gap
        return _simplify_path([start, (outer_x, start[1]), (outer_x, end[1]), end])
    if direction == "LEFT":
        outer_x = node.x - route_gap
        return _simplify_path([start, (outer_x, start[1]), (outer_x, end[1]), end])
    if direction == "DOWN":
        outer_y = node.y + node.height + route_gap
        return _simplify_path([start, (start[0], outer_y), (end[0], outer_y), end])
    if direction == "UP":
        outer_y = node.y - route_gap
        return _simplify_path([start, (start[0], outer_y), (end[0], outer_y), end])
    outer_x = node.x + node.width + route_gap
    upper_y = node.y - route_gap
    return _simplify_path([start, (outer_x, start[1]), (outer_x, upper_y), (end[0] - 24.0, upper_y), (end[0] - 24.0, end[1]), end])


def _same_layer_path(
    start: tuple[float, float],
    end: tuple[float, float],
    index: int,
    direction: str,
) -> list[tuple[float, float]]:
    route_gap = 36.0 + index * 12.0
    if direction == "LEFT":
        detour_x = min(start[0], end[0]) - route_gap
        return _simplify_path([start, (detour_x, start[1]), (detour_x, end[1]), end])
    if direction == "DOWN":
        detour_y = max(start[1], end[1]) + route_gap
        return _simplify_path([start, (start[0], detour_y), (end[0], detour_y), end])
    if direction == "UP":
        detour_y = min(start[1], end[1]) - route_gap
        return _simplify_path([start, (start[0], detour_y), (end[0], detour_y), end])
    detour_x = max(start[0], end[0]) + route_gap
    return _simplify_path([start, (detour_x, start[1]), (detour_x, end[1]), end])


def _standard_path(
    points: list[tuple[float, float]],
    index_offset: float = 0.0,
    direction: str = "RIGHT",
) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points
    routed: list[tuple[float, float]] = [points[0]]
    for idx in range(len(points) - 1):
        src = points[idx]
        dst = points[idx + 1]
        if idx == len(points) - 2:
            routed.append(dst)
            continue
        if direction in {"DOWN", "UP"}:
            mid_y = (src[1] + dst[1]) / 2.0 + index_offset
            routed.extend([(src[0], mid_y), (dst[0], mid_y), dst])
        else:
            mid_x = (src[0] + dst[0]) / 2.0 + index_offset
            routed.extend([(mid_x, src[1]), (mid_x, dst[1]), dst])
    return _simplify_path(routed)


def _polyline_path(
    points: list[tuple[float, float]],
    index_offset: float = 0.0,
    direction: str = "RIGHT",
) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points
    if len(points) == 2:
        start, end = points
        if direction in {"DOWN", "UP"}:
            mid_y = (start[1] + end[1]) / 2.0 + index_offset
            return _simplify_path([start, (start[0], mid_y), end])
        mid_x = (start[0] + end[0]) / 2.0 + index_offset
        return _simplify_path([start, (mid_x, start[1]), end])
    return _simplify_path(points)


def _segment_intersects_rect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    rect: tuple[float, float, float, float],
    margin: float = 4.0,
) -> bool:
    left, top, right, bottom = rect
    left -= margin
    top -= margin
    right += margin
    bottom += margin
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if not (left <= x1 <= right):
            return False
        seg_top = min(y1, y2)
        seg_bottom = max(y1, y2)
        return not (seg_bottom < top or seg_top > bottom)
    if y1 == y2:
        if not (top <= y1 <= bottom):
            return False
        seg_left = min(x1, x2)
        seg_right = max(x1, x2)
        return not (seg_right < left or seg_left > right)
    return False


def _path_hits_nodes(
    path: list[tuple[float, float]],
    rects: list[tuple[str, float, float, float, float]],
    ignore_ids: set[str],
) -> bool:
    for idx in range(len(path) - 1):
        p1 = path[idx]
        p2 = path[idx + 1]
        for node_id, left, top, right, bottom in rects:
            if node_id in ignore_ids:
                continue
            if _segment_intersects_rect(p1, p2, (left, top, right, bottom)):
                return True
    return False


def _first_hit_node(
    path: list[tuple[float, float]],
    rects: list[tuple[str, float, float, float, float]],
    ignore_ids: set[str],
) -> tuple[int, tuple[str, float, float, float, float]] | None:
    for idx in range(len(path) - 1):
        p1 = path[idx]
        p2 = path[idx + 1]
        for rect_info in rects:
            node_id, left, top, right, bottom = rect_info
            if node_id in ignore_ids:
                continue
            if _segment_intersects_rect(p1, p2, (left, top, right, bottom)):
                return idx, rect_info
    return None


def _detour_path(
    start: tuple[float, float],
    end: tuple[float, float],
    bounds: tuple[float, float, float, float],
    direction: str,
    index: int,
) -> list[tuple[float, float]]:
    left, top, right, bottom = bounds
    gap = 56.0 + index * 12.0
    if direction == "LEFT":
        detour_x = left - gap
        return _clean([start, (detour_x, start[1]), (detour_x, end[1]), end])
    if direction == "DOWN":
        detour_y = bottom + gap
        return _clean([start, (start[0], detour_y), (end[0], detour_y), end])
    if direction == "UP":
        detour_y = top - gap
        return _simplify_path([start, (start[0], detour_y), (end[0], detour_y), end])
    detour_x = right + gap
    return _simplify_path([start, (detour_x, start[1]), (detour_x, end[1]), end])


def _splice_detour(
    path: list[tuple[float, float]],
    segment_index: int,
    replacement: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    return path[:segment_index] + replacement + path[segment_index + 2:]


def _segment_detour_candidates(
    p1: tuple[float, float],
    p2: tuple[float, float],
    rect: tuple[float, float, float, float],
    bounds: tuple[float, float, float, float],
    clearance: float,
) -> list[list[tuple[float, float]]]:
    left, top, right, bottom = rect
    graph_left, graph_top, graph_right, graph_bottom = bounds
    candidates: list[list[tuple[float, float]]] = []
    if p1[0] == p2[0]:
        x = p1[0]
        left_x = min(left - clearance, graph_left - clearance)
        right_x = max(right + clearance, graph_right + clearance)
        candidates.append([p1, (left_x, p1[1]), (left_x, p2[1]), p2])
        candidates.append([p1, (right_x, p1[1]), (right_x, p2[1]), p2])
        candidates.append([p1, (x, top - clearance), (p2[0], top - clearance), p2])
        candidates.append([p1, (x, bottom + clearance), (p2[0], bottom + clearance), p2])
    elif p1[1] == p2[1]:
        y = p1[1]
        candidates.append([p1, (p1[0], top - clearance), (p2[0], top - clearance), p2])
        candidates.append([p1, (p1[0], bottom + clearance), (p2[0], bottom + clearance), p2])
        candidates.append([p1, (left - clearance, y), (left - clearance, p2[1]), p2])
        candidates.append([p1, (right + clearance, y), (right + clearance, p2[1]), p2])
    return candidates


def _path_span(path: list[tuple[float, float]]) -> float:
    total = 0.0
    for idx in range(len(path) - 1):
        total += abs(path[idx + 1][0] - path[idx][0]) + abs(path[idx + 1][1] - path[idx][1])
    return total


def _reroute_around_nodes(
    path: list[tuple[float, float]],
    rects: list[tuple[str, float, float, float, float]],
    ignore_ids: set[str],
    bounds: tuple[float, float, float, float],
) -> list[tuple[float, float]]:
    rerouted = _simplify_path(path)
    for attempt in range(10):
        hit = _first_hit_node(rerouted, rects, ignore_ids)
        if hit is None:
            return _simplify_path(rerouted)
        segment_index, (_, left, top, right, bottom) = hit
        p1 = rerouted[segment_index]
        p2 = rerouted[segment_index + 1]
        candidates = []
        for replacement in _segment_detour_candidates(
            p1,
            p2,
            (left, top, right, bottom),
            bounds,
            clearance=12.0 + attempt * 6.0,
        ):
            candidate = _simplify_path(_splice_detour(rerouted, segment_index, replacement))
            if not _path_hits_nodes(candidate, rects, ignore_ids):
                candidates.append(candidate)
        if not candidates:
            break
        rerouted = min(candidates, key=lambda candidate: (len(candidate), _path_span(candidate)))
    return _simplify_path(rerouted)


class EdgeRoutingPhase:
    name = "edge-routing"

    def run(self, context: LayoutContext) -> None:
        edge_paths: dict[str, list[str]] = context.phase_state.get("edge_paths", {})
        virtual_positions: dict[str, tuple[float, float]] = context.phase_state.get("virtual_positions", {})
        expanded_nodes = context.phase_state.get("expanded_nodes", {})
        feedback_edges = set(context.phase_state.get("feedback_edges", [])) if _feedback_edges_enabled(context) else set()
        bounds = _all_node_bounds(context)
        rects = _node_rects(context)
        direction = _layout_direction(context)
        routing_mode = _edge_routing_mode(context)
        self_loop_distribution = _self_loop_distribution(context)
        layer_of: dict[str, int] = context.phase_state.get("layer_of", {})

        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        feedback_index = 0
        self_loop_index = 0

        for edge in context.graph.edges:
            edge.sections = []
            if not edge.sources or not edge.targets:
                continue

            src_endpoint = edge.sources[0]
            dst_endpoint = edge.targets[0]
            start = _port_anchor(context, src_endpoint, "output")
            end = _port_anchor(context, dst_endpoint, "input")
            if start is None or end is None:
                continue

            source_uid = str(edge.properties.get("source_uid", ""))
            target_uid = str(edge.properties.get("target_uid", ""))
            source_node = context.graph.node_by_id().get(source_uid)

            if source_uid and source_uid == target_uid and source_node is not None:
                path = _self_loop_path(source_node, start, end, self_loop_index, direction, self_loop_distribution)
                self_loop_index += 1
                edge.sections.append(
                    SugiyamaEdgeSection(
                        start_point=path[0],
                        end_point=path[-1],
                        bend_points=path[1:-1],
                    )
                )
                continue

            if edge.identifier in feedback_edges:
                path = _feedback_path(start, end, bounds, feedback_index, direction)
                feedback_index += 1
                edge.sections.append(
                    SugiyamaEdgeSection(
                        start_point=path[0],
                        end_point=path[-1],
                        bend_points=path[1:-1],
                    )
                )
                continue

            source_layer = layer_of.get(source_uid)
            target_layer = layer_of.get(target_uid)
            if source_layer is not None and target_layer is not None and source_layer == target_layer:
                pair_index = pair_counts[(source_uid, target_uid)]
                pair_counts[(source_uid, target_uid)] += 1
                path = _same_layer_path(start, end, pair_index, direction)
                edge.sections.append(
                    SugiyamaEdgeSection(
                        start_point=path[0],
                        end_point=path[-1],
                        bend_points=path[1:-1],
                    )
                )
                continue

            path_ids = edge_paths.get(edge.identifier, [])
            chain_points: list[tuple[float, float]] = []
            if path_ids:
                chain_points.append(start)
                for node_id in path_ids[1:-1]:
                    position = virtual_positions.get(node_id)
                    node_info = expanded_nodes.get(node_id)
                    if position is None or node_info is None:
                        continue
                    x, y = position
                    chain_points.append((x + node_info.width / 2.0, y + node_info.height / 2.0))
                chain_points.append(end)
            else:
                chain_points = [start, end]

            pair_index = pair_counts[(source_uid, target_uid)]
            pair_counts[(source_uid, target_uid)] += 1
            offset = (pair_index - (pair_counts[(source_uid, target_uid)] - 1) / 2.0) * 7.0
            if routing_mode == "POLYLINE":
                path = _polyline_path(chain_points, index_offset=offset, direction=direction)
            elif routing_mode == "SPLINES":
                path = _polyline_path(chain_points, index_offset=offset, direction=direction)
            else:
                path = _standard_path(chain_points, index_offset=offset, direction=direction)
            if _path_hits_nodes(path, rects, {source_uid, target_uid}):
                rerouted = _reroute_around_nodes(path, rects, {source_uid, target_uid}, bounds)
                if _path_hits_nodes(rerouted, rects, {source_uid, target_uid}):
                    path = _detour_path(start, end, bounds, direction, pair_index)
                else:
                    path = rerouted
            path = _simplify_path(path)
            edge.sections.append(
                SugiyamaEdgeSection(
                    start_point=path[0],
                    end_point=path[-1],
                    bend_points=path[1:-1],
                )
            )
