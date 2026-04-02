# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from math import hypot
from typing import Iterable, List, Tuple

RoutePoint = Tuple[float, float]
RouteSegment = Tuple[RoutePoint, RoutePoint]


def normalize_route_points(points: Iterable[RoutePoint]) -> List[RoutePoint]:
    """
    Normalize arbitrary numeric route points to float tuples.
    """
    normalized: List[RoutePoint] = list()

    for point in points:
        if len(point) != 2:
            raise ValueError(f"Expected 2D route point, got {point!r}")
        normalized.append((float(point[0]), float(point[1])))

    return normalized


def compress_route_points(points: Iterable[RoutePoint]) -> List[RoutePoint]:
    """
    Remove duplicate and collinear route points.

    :param points: Route points.
    :return: Simplified route points.
    """
    normalized_points = normalize_route_points(points)
    compressed_points: List[RoutePoint] = list()
    point: RoutePoint

    for point in normalized_points:
        if len(compressed_points) == 0:
            compressed_points.append(point)
        elif compressed_points[-1] != point:
            compressed_points.append(point)
        else:
            pass

    if len(compressed_points) < 3:
        return compressed_points
    else:
        pass

    simplified_points: List[RoutePoint] = [compressed_points[0]]
    point_index: int

    for point_index in range(1, len(compressed_points) - 1):
        previous_point = simplified_points[-1]
        current_point = compressed_points[point_index]
        next_point = compressed_points[point_index + 1]
        is_vertical_chain = previous_point[0] == current_point[0] and current_point[0] == next_point[0]
        is_horizontal_chain = previous_point[1] == current_point[1] and current_point[1] == next_point[1]

        if is_vertical_chain or is_horizontal_chain:
            pass
        else:
            simplified_points.append(current_point)

    simplified_points.append(compressed_points[-1])
    return simplified_points


def align_adjacent_point_to_endpoint(endpoint_point: RoutePoint,
                                     adjacent_point: RoutePoint,
                                     side: str | None) -> RoutePoint:
    """
    Align one endpoint-adjacent elbow to preserve orthogonality after the endpoint moves.

    :param endpoint_point: Live endpoint position.
    :param adjacent_point: Persisted adjacent route point.
    :param side: Endpoint attachment side.
    :return: Realigned adjacent route point.
    """
    if side in ("top", "bottom"):
        return float(endpoint_point[0]), float(adjacent_point[1])
    elif side in ("left", "right"):
        return float(adjacent_point[0]), float(endpoint_point[1])
    else:
        return float(adjacent_point[0]), float(adjacent_point[1])


def merge_route_with_endpoints(start: RoutePoint,
                               end: RoutePoint,
                               persisted_points: Iterable[RoutePoint],
                               start_side: str | None = None,
                               end_side: str | None = None) -> List[RoutePoint]:
    """
    Replace persisted route endpoints with the live endpoint positions while keeping interior elbows.
    """
    normalized_points = normalize_route_points(persisted_points)
    start_point = (float(start[0]), float(start[1]))
    end_point = (float(end[0]), float(end[1]))

    if len(normalized_points) >= 2:
        merged_points = [start_point] + normalized_points[1:-1] + [end_point]

        if len(merged_points) >= 3:
            merged_points[1] = align_adjacent_point_to_endpoint(endpoint_point=start_point,
                                                                adjacent_point=merged_points[1],
                                                                side=start_side)
            merged_points[-2] = align_adjacent_point_to_endpoint(endpoint_point=end_point,
                                                                 adjacent_point=merged_points[-2],
                                                                 side=end_side)
        else:
            pass

        return compress_route_points(merged_points)

    return [start_point, end_point]


def move_orthogonal_route_segment(points: Iterable[RoutePoint],
                                  segment_index: int,
                                  delta_x: float,
                                  delta_y: float) -> List[RoutePoint]:
    """
    Move one interior orthogonal route segment while keeping the route orthogonal.

    The editable segment must not be the first or last segment because branch
    endpoints remain attached to their owning nodes.

    :param points: Route points.
    :param segment_index: Zero-based segment index.
    :param delta_x: Horizontal scene delta.
    :param delta_y: Vertical scene delta.
    :return: Updated route points.
    """
    normalized_points = normalize_route_points(points)
    point_count = len(normalized_points)

    if point_count < 4:
        return normalized_points
    elif segment_index <= 0:
        return normalized_points
    elif segment_index >= point_count - 2:
        return normalized_points
    else:
        pass

    start_point = normalized_points[segment_index]
    end_point = normalized_points[segment_index + 1]
    moved_points = list(normalized_points)

    if start_point[0] == end_point[0]:
        moved_x = start_point[0] + float(delta_x)
        moved_points[segment_index] = (moved_x, start_point[1])
        moved_points[segment_index + 1] = (moved_x, end_point[1])
    else:
        moved_y = start_point[1] + float(delta_y)
        moved_points[segment_index] = (start_point[0], moved_y)
        moved_points[segment_index + 1] = (end_point[0], moved_y)

    return moved_points


def move_orthogonal_route_vertex(points: Iterable[RoutePoint],
                                 vertex_index: int,
                                 new_x: float,
                                 new_y: float) -> List[RoutePoint]:
    """
    Move one interior orthogonal route vertex while preserving orthogonality.

    :param points: Route points.
    :param vertex_index: Index of the vertex to move.
    :param new_x: New scene X coordinate.
    :param new_y: New scene Y coordinate.
    :return: Updated route points.
    """
    normalized_points = normalize_route_points(points)
    point_count = len(normalized_points)

    if point_count < 3:
        return normalized_points
    elif vertex_index <= 0:
        return normalized_points
    elif vertex_index >= point_count - 1:
        return normalized_points
    else:
        pass

    moved_points = list(normalized_points)
    previous_point = normalized_points[vertex_index - 1]
    current_point = normalized_points[vertex_index]
    next_point = normalized_points[vertex_index + 1]
    target_x = float(new_x)
    target_y = float(new_y)

    if previous_point[0] == current_point[0]:
        if vertex_index - 1 == 0:
            target_x = previous_point[0]
        else:
            moved_points[vertex_index - 1] = (target_x, previous_point[1])
    elif previous_point[1] == current_point[1]:
        if vertex_index - 1 == 0:
            target_y = previous_point[1]
        else:
            moved_points[vertex_index - 1] = (previous_point[0], target_y)
    else:
        return normalized_points

    if current_point[0] == next_point[0]:
        if vertex_index + 1 == point_count - 1:
            target_x = next_point[0]
        else:
            moved_points[vertex_index + 1] = (target_x, next_point[1])
    elif current_point[1] == next_point[1]:
        if vertex_index + 1 == point_count - 1:
            target_y = next_point[1]
        else:
            moved_points[vertex_index + 1] = (next_point[0], target_y)
    else:
        return normalized_points

    moved_points[vertex_index] = (target_x, target_y)
    return moved_points


def sample_route_segment(points: Iterable[RoutePoint], position: float) -> Tuple[RoutePoint, RouteSegment]:
    """
    Sample a route at a normalized path position and return the point plus its local segment.
    """
    normalized_points = normalize_route_points(points)

    if len(normalized_points) < 2:
        raise ValueError("At least two route points are required")

    clamped_position = min(max(float(position), 0.0), 1.0)
    segments: List[Tuple[RouteSegment, float]] = list()
    total_length = 0.0

    for idx in range(len(normalized_points) - 1):
        p1 = normalized_points[idx]
        p2 = normalized_points[idx + 1]
        length = hypot(p2[0] - p1[0], p2[1] - p1[1])
        if length > 0.0:
            segments.append((((p1[0], p1[1]), (p2[0], p2[1])), length))
            total_length += length

    if not segments:
        point = normalized_points[0]
        return point, (point, point)

    target_length = total_length * clamped_position
    traversed = 0.0

    for segment, length in segments:
        next_traversed = traversed + length

        if target_length <= next_traversed:
            remaining = target_length - traversed
            factor = remaining / length if length > 0.0 else 0.0
            p1, p2 = segment
            point = (p1[0] + (p2[0] - p1[0]) * factor,
                     p1[1] + (p2[1] - p1[1]) * factor)
            return point, segment

        traversed = next_traversed

    last_segment = segments[-1][0]
    return last_segment[1], last_segment
