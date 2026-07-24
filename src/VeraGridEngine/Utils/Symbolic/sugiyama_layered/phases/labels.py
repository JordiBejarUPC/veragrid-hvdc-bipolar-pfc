# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from ..pipeline import LayoutContext


def _section_path_points(section) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    if section.start_point is not None:
        points.append(section.start_point)
    points.extend(section.bend_points)
    if section.end_point is not None:
        points.append(section.end_point)
    return points


def _polyline_midpoint(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not points:
        return None
    if len(points) == 1:
        return points[0]

    segment_lengths: list[float] = []
    total_length = 0.0
    for idx in range(len(points) - 1):
        x1, y1 = points[idx]
        x2, y2 = points[idx + 1]
        length = abs(x2 - x1) + abs(y2 - y1)
        segment_lengths.append(length)
        total_length += length

    if total_length <= 0.0:
        return points[len(points) // 2]

    halfway = total_length / 2.0
    walked = 0.0
    for idx, length in enumerate(segment_lengths):
        if walked + length >= halfway and length > 0.0:
            x1, y1 = points[idx]
            x2, y2 = points[idx + 1]
            ratio = (halfway - walked) / length
            return (x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio)
        walked += length
    return points[-1]


def _longest_segment_midpoint(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if len(points) < 2:
        return _polyline_midpoint(points)
    best_length = -1.0
    best_midpoint: tuple[float, float] | None = None
    for idx in range(len(points) - 1):
        x1, y1 = points[idx]
        x2, y2 = points[idx + 1]
        length = abs(x2 - x1) + abs(y2 - y1)
        if length > best_length:
            best_length = length
            best_midpoint = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    return best_midpoint


def _graph_bounds(context: LayoutContext) -> tuple[float, float, float, float] | None:
    left = None
    top = None
    right = None
    bottom = None

    for node in context.graph.all_nodes():
        if node.x is None or node.y is None:
            continue
        node_left = node.x
        node_top = node.y
        node_right = node.x + node.width
        node_bottom = node.y + node.height
        left = node_left if left is None else min(left, node_left)
        top = node_top if top is None else min(top, node_top)
        right = node_right if right is None else max(right, node_right)
        bottom = node_bottom if bottom is None else max(bottom, node_bottom)

        for port in node.ports:
            if port.x is None or port.y is None:
                continue
            port_left = port.x
            port_top = port.y
            port_right = port.x + port.width
            port_bottom = port.y + port.height
            left = port_left if left is None else min(left, port_left)
            top = port_top if top is None else min(top, port_top)
            right = port_right if right is None else max(right, port_right)
            bottom = port_bottom if bottom is None else max(bottom, port_bottom)

        for label in node.labels:
            if label.x is None or label.y is None:
                continue
            label_left = label.x
            label_top = label.y
            label_right = label.x + label.width
            label_bottom = label.y + label.height
            left = label_left if left is None else min(left, label_left)
            top = label_top if top is None else min(top, label_top)
            right = label_right if right is None else max(right, label_right)
            bottom = label_bottom if bottom is None else max(bottom, label_bottom)

        for port in node.ports:
            for label in port.labels:
                if label.x is None or label.y is None:
                    continue
                label_left = label.x
                label_top = label.y
                label_right = label.x + label.width
                label_bottom = label.y + label.height
                left = label_left if left is None else min(left, label_left)
                top = label_top if top is None else min(top, label_top)
                right = label_right if right is None else max(right, label_right)
                bottom = label_bottom if bottom is None else max(bottom, label_bottom)

    for edge in context.graph.edges:
        for section in edge.sections:
            if section.start_point is not None:
                x, y = section.start_point
                left = x if left is None else min(left, x)
                top = y if top is None else min(top, y)
                right = x if right is None else max(right, x)
                bottom = y if bottom is None else max(bottom, y)
            for x, y in section.bend_points:
                left = x if left is None else min(left, x)
                top = y if top is None else min(top, y)
                right = x if right is None else max(right, x)
                bottom = y if bottom is None else max(bottom, y)
            if section.end_point is not None:
                x, y = section.end_point
                left = x if left is None else min(left, x)
                top = y if top is None else min(top, y)
                right = x if right is None else max(right, x)
                bottom = y if bottom is None else max(bottom, y)
        for label in edge.labels:
            if label.x is None or label.y is None:
                continue
            label_left = label.x
            label_top = label.y
            label_right = label.x + label.width
            label_bottom = label.y + label.height
            left = label_left if left is None else min(left, label_left)
            top = label_top if top is None else min(top, label_top)
            right = label_right if right is None else max(right, label_right)
            bottom = label_bottom if bottom is None else max(bottom, label_bottom)

    if left is None or top is None or right is None or bottom is None:
        return None
    return (left, top, right, bottom)


def _shift_layout(context: LayoutContext, dx: float, dy: float) -> None:
    if abs(dx) <= 1e-9 and abs(dy) <= 1e-9:
        return

    for node in context.graph.all_nodes():
        if node.x is not None:
            node.x += dx
        if node.y is not None:
            node.y += dy
        for label in node.labels:
            if label.x is not None:
                label.x += dx
            if label.y is not None:
                label.y += dy
        for port in node.ports:
            if port.x is not None:
                port.x += dx
            if port.y is not None:
                port.y += dy
            for label in port.labels:
                if label.x is not None:
                    label.x += dx
                if label.y is not None:
                    label.y += dy

    for edge in context.graph.edges:
        for section in edge.sections:
            if section.start_point is not None:
                section.start_point = (section.start_point[0] + dx, section.start_point[1] + dy)
            if section.end_point is not None:
                section.end_point = (section.end_point[0] + dx, section.end_point[1] + dy)
            if section.bend_points:
                section.bend_points = [(x + dx, y + dy) for x, y in section.bend_points]
        for label in edge.labels:
            if label.x is not None:
                label.x += dx
            if label.y is not None:
                label.y += dy


def _layout_direction(context: LayoutContext) -> str:
    options = context.option_resolver.resolve_for_element(context.graph.layout_options)
    return str(options.get("org.vera.sugiyama.direction", "RIGHT")).upper()


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


class LabelPlacementPhase:
    name = "labels"

    def run(self, context: LayoutContext) -> None:
        direction = _layout_direction(context)
        for node in context.graph.all_nodes():
            for label in node.labels:
                if node.x is None or node.y is None:
                    label.x = None
                    label.y = None
                    continue
                label.x = node.x + max((node.width - label.width) / 2.0, 0.0)
                label.y = node.y - label.height if label.height else node.y
            for port in node.ports:
                for label in port.labels:
                    if port.x is None or port.y is None:
                        label.x = None
                        label.y = None
                        continue
                    role = str(port.properties.get("role", "")).lower()
                    side = _effective_port_side(port, role, direction)
                    if side == "WEST":
                        label.x = port.x - label.width - 4.0
                        label.y = port.y + max((port.height - label.height) / 2.0, 0.0)
                    elif side == "EAST":
                        label.x = port.x + port.width + 4.0
                        label.y = port.y + max((port.height - label.height) / 2.0, 0.0)
                    elif side == "NORTH":
                        label.x = port.x + max((port.width - label.width) / 2.0, 0.0)
                        label.y = port.y - label.height - 4.0
                    else:
                        label.x = port.x + max((port.width - label.width) / 2.0, 0.0)
                        label.y = port.y + port.height + 4.0
        for edge in context.graph.edges:
            if not edge.sections:
                continue
            section = edge.sections[0]
            midpoint = _longest_segment_midpoint(_section_path_points(section))
            if midpoint is None:
                continue
            for label in edge.labels:
                label.x = midpoint[0] - label.width / 2.0 if label.width else midpoint[0]
                label.y = midpoint[1] - label.height - 4.0 if label.height else midpoint[1]

        bounds = _graph_bounds(context)
        if bounds is not None:
            left, top, right, bottom = bounds
            _shift_layout(context, -left, -top)
            context.graph.width = max(right - left, 0.0)
            context.graph.height = max(bottom - top, 0.0)
