# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.001--.0-

from __future__ import annotations

from bisect import bisect_left, bisect_right
import heapq

from VeraGrid.Gui.DynamicModelEditor.Routing.routing_elements import RoutingNode
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_elements import RoutingPoint
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_elements import RoutingSegment
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_graph import RoutingGraph
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_geometry import RoutingGeometry
from VeraGridEngine.enumerations import RoutingNodeKind, RoutingPortSide


def orthogonal_routing_segments_collide(
        first_start: RoutingPoint,
        first_end: RoutingPoint,
        second_start: RoutingPoint,
        second_end: RoutingPoint,
        tolerance: float,
) -> bool:
    """Return whether two orthogonal segments cross or overlap internally.

    Endpoint-only contact is allowed because it represents a cable reaching
    its own port. Perpendicular interior crossings and positive-length
    collinear overlaps are rejected for every routing frontend.

    :param first_start: First segment start.
    :param first_end: First segment end.
    :param second_start: Second segment start.
    :param second_end: Second segment end.
    :param tolerance: Coordinate comparison tolerance.
    :return: ``True`` when the two segments collide beyond a shared endpoint.
    """
    first_horizontal: bool = abs(first_start.get_y() - first_end.get_y()) <= tolerance
    second_horizontal: bool = abs(second_start.get_y() - second_end.get_y()) <= tolerance
    if first_horizontal and second_horizontal:
        same_axis: bool = abs(first_start.get_y() - second_start.get_y()) <= tolerance
        overlap_length: float = (
                min(max(first_start.get_x(), first_end.get_x()),
                    max(second_start.get_x(), second_end.get_x()))
                - max(min(first_start.get_x(), first_end.get_x()),
                      min(second_start.get_x(), second_end.get_x()))
        )
        return same_axis and overlap_length > tolerance
    elif not first_horizontal and not second_horizontal:
        same_axis = abs(first_start.get_x() - second_start.get_x()) <= tolerance
        overlap_length = (
                min(max(first_start.get_y(), first_end.get_y()),
                    max(second_start.get_y(), second_end.get_y()))
                - max(min(first_start.get_y(), first_end.get_y()),
                      min(second_start.get_y(), second_end.get_y()))
        )
        return same_axis and overlap_length > tolerance
    else:
        pass

    # Normalize the perpendicular case so the interior test is independent of
    # the order in which the two candidate segments were supplied.
    if first_horizontal:
        horizontal_start: RoutingPoint = first_start
        horizontal_end: RoutingPoint = first_end
        vertical_start: RoutingPoint = second_start
        vertical_end: RoutingPoint = second_end
    else:
        horizontal_start = second_start
        horizontal_end = second_end
        vertical_start = first_start
        vertical_end = first_end
    crossing_x: float = vertical_start.get_x()
    crossing_y: float = horizontal_start.get_y()
    inside_horizontal: bool = (
            crossing_x > min(horizontal_start.get_x(), horizontal_end.get_x()) + tolerance
            and crossing_x < max(horizontal_start.get_x(), horizontal_end.get_x()) - tolerance
    )
    inside_vertical: bool = (
            crossing_y > min(vertical_start.get_y(), vertical_end.get_y()) + tolerance
            and crossing_y < max(vertical_start.get_y(), vertical_end.get_y()) - tolerance
    )
    return inside_horizontal and inside_vertical


class RouteBuilder:
    """
    Build one deterministic orthogonal routing graph between two ports.

    :return: None.
    """

    __slots__ = (
        "_source_position",
        "_destination_position",
        "_source_port_side",
        "_destination_port_side",
        "_geometry",
        "_grid_size",
    )

    def __init__(
            self,
            source_position: RoutingPoint,
            destination_position: RoutingPoint,
            source_port_side: RoutingPortSide,
            destination_port_side: RoutingPortSide,
            grid_size: float = 20.0,
    ) -> None:
        """
        Build one route builder.

        :param source_position: Source port position.
        :param destination_position: Destination port position.
        :param source_port_side: Physical side of the source port on its block.
        :param destination_port_side: Physical side of the destination port on its block.
        :param grid_size: Positive mesh spacing used for editable route corridors.
        :return: None.
        """
        self._source_position: RoutingPoint = source_position.copy()
        self._destination_position: RoutingPoint = destination_position.copy()
        self._source_port_side: RoutingPortSide = source_port_side
        self._destination_port_side: RoutingPortSide = destination_port_side
        self._geometry: RoutingGeometry = RoutingGeometry()
        self._grid_size: float = max(1.0, float(grid_size))

    def build(self) -> RoutingGraph:
        """
        Build one deterministic orthogonal graph.

        :return: Built routing graph.
        """
        routing_graph: RoutingGraph = RoutingGraph(source_node_id=1, destination_node_id=2)
        source_node: RoutingNode = RoutingNode(
            node_id=1,
            kind=RoutingNodeKind.PORT,
            position=self._source_position.copy(),
            port_side=self._source_port_side,
        )
        destination_node: RoutingNode = RoutingNode(
            node_id=2,
            kind=RoutingNodeKind.PORT,
            position=self._destination_position.copy(),
            port_side=self._destination_port_side,
        )

        # Graph creation is the only place that may construct topology from
        # scratch. All later user interaction must transform the existing graph.
        routing_graph._add_node(source_node)
        routing_graph._add_node(destination_node)

        self._build_stub_topology(routing_graph)

        return routing_graph

    def _build_stub_topology(self, routing_graph: RoutingGraph) -> None:
        """
        Build the route by reusing the existing central path between two stubs.

        The builder still uses the same deterministic orthogonal route
        algorithm for the interior geometry. The only difference is that the
        effective endpoints of that interior route are the two stub points
        rather than the two ports themselves.

        :param routing_graph: Graph under construction.
        :return: None.
        """
        route_points: list[RoutingPoint] = self._build_stubbed_route_points()
        # The builder owns the only topology-from-scratch step. Once the full
        # point chain is known, the graph is materialized in one deterministic
        # pass so later editor operations only transform existing nodes.
        self._build_graph_from_route_points(routing_graph, route_points)

    def _build_stubbed_route_points(self) -> list[RoutingPoint]:
        """
        Build one full route including both terminal stubs.

        :return: Route points including both ports and both stubs.
        """
        route_points: list[RoutingPoint] = list()
        source_stub: RoutingPoint = self._build_stub_point(
            port_position=self._source_position,
            port_side=self._source_port_side,
        )
        destination_stub: RoutingPoint = self._build_stub_point(
            port_position=self._destination_position,
            port_side=self._destination_port_side,
        )
        # The central route owns two or more elbows so at least one full segment
        # can be moved perpendicular to itself without changing endpoint stubs.
        inner_route_points: list[RoutingPoint] = self._build_minimal_route_points(
            start_position=source_stub,
            end_position=destination_stub,
        )

        # The final point chain always includes both real ports so the graph
        # keeps explicit topology for the physical block attachment points.
        route_points.append(self._source_position.copy())
        inner_point: RoutingPoint
        for inner_point in inner_route_points:
            route_points.append(inner_point.copy())
        route_points.append(self._destination_position.copy())
        return route_points

    def _build_minimal_route_points(
            self,
            start_position: RoutingPoint,
            end_position: RoutingPoint,
    ) -> list[RoutingPoint]:
        """
        Build an editable orthogonal route between two endpoint stubs.

        :param start_position: Effective route start.
        :param end_position: Effective route end.
        :return: Ordered route points including both endpoints.
        """
        route_points: list[RoutingPoint] = list()
        route_points.append(start_position.copy())
        source_x: float = start_position.get_x()
        source_y: float = start_position.get_y()
        destination_x: float = end_position.get_x()
        destination_y: float = end_position.get_y()
        x_aligned: bool = self._geometry.are_x_aligned(start_position, end_position)
        y_aligned: bool = self._geometry.are_y_aligned(start_position, end_position)

        if not x_aligned:
            # A horizontal corridor above both stubs gives the editor one
            # ELBOW-to-ELBOW segment whose y coordinate belongs to the mesh.
            corridor_y: float = (
                round((min(source_y, destination_y) - self._grid_size) / self._grid_size)
                * self._grid_size
            )
            route_points.append(RoutingPoint(source_x, corridor_y))
            route_points.append(RoutingPoint(destination_x, corridor_y))
        elif not y_aligned:
            # Vertically separated aligned stubs use the symmetric left-side
            # corridor so the movable segment has one mesh-aligned x coordinate.
            corridor_x: float = (
                round((min(source_x, destination_x) - self._grid_size) / self._grid_size)
                * self._grid_size
            )
            route_points.append(RoutingPoint(corridor_x, source_y))
            route_points.append(RoutingPoint(corridor_x, destination_y))
        else:
            # Coincident or visually coincident stubs need a three-elbow detour
            # to avoid a zero-length central segment while preserving orthogonality.
            detour_x: float = (
                round((max(source_x, destination_x) + self._grid_size) / self._grid_size)
                * self._grid_size
            )
            detour_y: float = (
                round((min(source_y, destination_y) - self._grid_size) / self._grid_size)
                * self._grid_size
            )
            route_points.append(RoutingPoint(source_x, detour_y))
            route_points.append(RoutingPoint(detour_x, detour_y))
            route_points.append(RoutingPoint(detour_x, destination_y))

        route_points.append(end_position.copy())

        return route_points

    def _build_stub_point(self, port_position: RoutingPoint, port_side: RoutingPortSide) -> RoutingPoint:
        """
        Build one stub point offset from a port along its physical side.

        :param port_position: Port position.
        :param port_side: Physical side of the port.
        :return: Stub endpoint.
        """
        return self._geometry.build_port_stub_point(
            port_position=port_position,
            port_side=port_side,
        )

    def _build_graph_from_route_points(
            self,
            routing_graph: RoutingGraph,
            route_points: list[RoutingPoint],
    ) -> None:
        """
        Materialize one ordered route-point chain as one routing graph.

        :param routing_graph: Graph under construction.
        :param route_points: Ordered route points including both ports.
        :return: None.
        """
        node_ids: list[int] = list((1,))
        next_node_id: int = 3
        interior_point_count: int = len(route_points) - 2
        point_index: int
        for point_index in range(1, len(route_points) - 1):
            node_kind: RoutingNodeKind
            if point_index == 1 or point_index == interior_point_count:
                node_kind = RoutingNodeKind.STUB
            else:
                node_kind = RoutingNodeKind.ELBOW

            # The first and last interior nodes are the explicit stubs. Any
            # remaining interior nodes belong to the orthogonal dogleg itself.
            inner_node: RoutingNode = RoutingNode(
                node_id=next_node_id,
                kind=node_kind,
                position=route_points[point_index].copy(),
            )
            routing_graph._add_node(inner_node)
            node_ids.append(next_node_id)
            next_node_id += 1
        node_ids.append(2)

        segment_index: int
        for segment_index in range(len(node_ids) - 1):
            routing_graph._add_segment(
                self._build_segment(
                    segment_id=segment_index + 1,
                    start_node_id=node_ids[segment_index],
                    end_node_id=node_ids[segment_index + 1],
                )
            )

    def _build_segment(self, segment_id: int, start_node_id: int, end_node_id: int) -> RoutingSegment:
        """
        Build one graph segment.

        :param segment_id: Segment identifier.
        :param start_node_id: Start node identifier.
        :param end_node_id: End node identifier.
        :return: Routing segment.
        """
        route_segment: RoutingSegment = RoutingSegment(
            segment_id=segment_id,
            start_node_id=start_node_id,
            end_node_id=end_node_id,
        )
        return route_segment


class OrthogonalVisibilityRouteBuilder:
    """Select a globally valid orthogonal route through visible channels.

    The planner is independent from Qt. Callers provide immutable numerical
    geometry for rectangular obstacles, previously accepted cable segments and
    the complete scene bounds. The returned points can therefore be rendered by
    any frontend without moving routing policy into that frontend.
    """

    __slots__ = (
        "_source_point",
        "_target_point",
        "_obstacle_rects",
        "_reserved_segments",
        "_channel_segments",
        "_scene_bounds",
        "_source_stub_length",
        "_target_stub_length",
        "_channel_separation",
        "_bend_penalty",
        "_max_search_states",
        "_numerical_tolerance",
        "_reserved_horizontal_intervals_by_y",
        "_reserved_vertical_intervals_by_x",
        "_reserved_horizontal_y_values",
        "_reserved_vertical_x_values",
    )

    def __init__(
            self,
            source_point: RoutingPoint,
            target_point: RoutingPoint,
            obstacle_rects: list[tuple[float, float, float, float]],
            reserved_segments: list[tuple[RoutingPoint, RoutingPoint]],
            channel_segments: list[tuple[RoutingPoint, RoutingPoint]],
            scene_bounds: tuple[float, float, float, float],
            source_stub_length: float,
            target_stub_length: float,
            channel_separation: float,
            bend_penalty: float,
            max_search_states: int,
    ) -> None:
        """Initialize one bounded visibility-channel search.

        :param source_point: Producer port position.
        :param target_point: Consumer port position.
        :param obstacle_rects: Rectangles as ``left, top, right, bottom``.
        :param reserved_segments: Accepted cables and protected port corridors.
        :param channel_segments: Accepted cables that induce parallel lanes.
        :param scene_bounds: Search boundary as ``left, top, right, bottom``.
        :param source_stub_length: Horizontal producer access length.
        :param target_stub_length: Horizontal consumer access length.
        :param channel_separation: Separation from existing parallel cables.
        :param bend_penalty: Cost added for each route bend.
        :param max_search_states: Hard cap on expanded visibility states.
        :return: None.
        """
        self._source_point: RoutingPoint = source_point.copy()
        self._target_point: RoutingPoint = target_point.copy()
        self._obstacle_rects: list[tuple[float, float, float, float]] = list(obstacle_rects)
        self._reserved_segments: list[tuple[RoutingPoint, RoutingPoint]] = list()
        reserved_segment: tuple[RoutingPoint, RoutingPoint]
        for reserved_segment in reserved_segments:
            self._reserved_segments.append(
                (reserved_segment[0].copy(), reserved_segment[1].copy())
            )
        self._channel_segments: list[tuple[RoutingPoint, RoutingPoint]] = list()
        channel_segment: tuple[RoutingPoint, RoutingPoint]
        for channel_segment in channel_segments:
            self._channel_segments.append(
                (channel_segment[0].copy(), channel_segment[1].copy())
            )
        self._scene_bounds: tuple[float, float, float, float] = scene_bounds
        self._source_stub_length: float = float(source_stub_length)
        self._target_stub_length: float = float(target_stub_length)
        self._channel_separation: float = float(channel_separation)
        self._bend_penalty: float = float(bend_penalty)
        self._max_search_states: int = int(max_search_states)
        self._numerical_tolerance: float = 1.0e-6
        self._reserved_horizontal_intervals_by_y: dict[
            float,
            list[tuple[float, float]],
        ] = dict()
        self._reserved_vertical_intervals_by_x: dict[
            float,
            list[tuple[float, float]],
        ] = dict()

        # Orthogonal collision queries only depend on one fixed coordinate and
        # one scalar interval. Index those coordinates once so every A* grid
        # edge examines nearby axes instead of rescanning the complete cable set.
        for reserved_segment in self._reserved_segments:
            if self._points_share_y(reserved_segment[0], reserved_segment[1]):
                horizontal_y: float = reserved_segment[0].get_y()
                horizontal_intervals: list[tuple[float, float]] | None = (
                    self._reserved_horizontal_intervals_by_y.get(horizontal_y, None)
                )
                if horizontal_intervals is None:
                    horizontal_intervals = list()
                    self._reserved_horizontal_intervals_by_y[horizontal_y] = horizontal_intervals
                else:
                    pass
                horizontal_intervals.append((
                    min(reserved_segment[0].get_x(), reserved_segment[1].get_x()),
                    max(reserved_segment[0].get_x(), reserved_segment[1].get_x()),
                ))
            else:
                vertical_x: float = reserved_segment[0].get_x()
                vertical_intervals: list[tuple[float, float]] | None = (
                    self._reserved_vertical_intervals_by_x.get(vertical_x, None)
                )
                if vertical_intervals is None:
                    vertical_intervals = list()
                    self._reserved_vertical_intervals_by_x[vertical_x] = vertical_intervals
                else:
                    pass
                vertical_intervals.append((
                    min(reserved_segment[0].get_y(), reserved_segment[1].get_y()),
                    max(reserved_segment[0].get_y(), reserved_segment[1].get_y()),
                ))

        horizontal_interval_collection: list[tuple[float, float]]
        for horizontal_interval_collection in self._reserved_horizontal_intervals_by_y.values():
            horizontal_interval_collection.sort()
        vertical_interval_collection: list[tuple[float, float]]
        for vertical_interval_collection in self._reserved_vertical_intervals_by_x.values():
            vertical_interval_collection.sort()
        self._reserved_horizontal_y_values: list[float] = sorted(
            self._reserved_horizontal_intervals_by_y.keys()
        )
        self._reserved_vertical_x_values: list[float] = sorted(
            self._reserved_vertical_intervals_by_x.keys()
        )

    def build(self) -> list[RoutingPoint] | None:
        """Return the lowest-cost route in a bounded orthogonal visibility grid.

        :return: Accepted point chain, or ``None`` when every candidate fails.
        """
        source_stub: RoutingPoint = RoutingPoint(
            self._source_point.get_x() + self._source_stub_length,
            self._source_point.get_y(),
        )
        target_stub: RoutingPoint = RoutingPoint(
            self._target_point.get_x() - self._target_stub_length,
            self._target_point.get_y(),
        )
        x_channels: set[float] = set((source_stub.get_x(), target_stub.get_x()))
        y_channels: set[float] = set((source_stub.get_y(), target_stub.get_y()))
        obstacle_rect: tuple[float, float, float, float]
        for obstacle_rect in self._obstacle_rects:
            x_channels.add(obstacle_rect[0])
            x_channels.add(obstacle_rect[2])
            y_channels.add(obstacle_rect[1])
            y_channels.add(obstacle_rect[3])

        channel_segment: tuple[RoutingPoint, RoutingPoint]
        for channel_segment in self._channel_segments:
            # Segment endpoints are visibility events. Their coordinates let a
            # later route pass around the end of a reserved cable without an
            # exhaustive Cartesian refinement.
            x_channels.add(channel_segment[0].get_x())
            x_channels.add(channel_segment[1].get_x())
            y_channels.add(channel_segment[0].get_y())
            y_channels.add(channel_segment[1].get_y())
            if self._points_share_y(channel_segment[0], channel_segment[1]):
                y_channels.add(
                    channel_segment[0].get_y() - self._channel_separation
                )
                y_channels.add(
                    channel_segment[0].get_y() + self._channel_separation
                )
            else:
                x_channels.add(
                    channel_segment[0].get_x() - self._channel_separation
                )
                x_channels.add(
                    channel_segment[0].get_x() + self._channel_separation
                )
        x_channels.add(self._scene_bounds[0])
        x_channels.add(self._scene_bounds[2])
        y_channels.add(self._scene_bounds[1])
        y_channels.add(self._scene_bounds[3])

        # Terminal access is fixed by the port side. Reject it before searching
        # so a grid path can never hide an invalid first or final segment.
        if not self._segment_is_available(
                self._source_point,
                source_stub,
                permitted_terminal_point=self._source_point,
        ):
            return None
        elif not self._segment_is_available(
                target_stub,
                self._target_point,
                permitted_terminal_point=self._target_point,
        ):
            return None
        else:
            pass

        x_values: list[float] = sorted(x_channels)
        y_values: list[float] = sorted(y_channels)
        source_x_index: int = x_values.index(source_stub.get_x())
        source_y_index: int = y_values.index(source_stub.get_y())
        target_x_index: int = x_values.index(target_stub.get_x())
        target_y_index: int = y_values.index(target_stub.get_y())
        initial_direction: int = 1 if self._source_stub_length > 0.0 else 0
        initial_state: tuple[int, int, int] = (
            source_x_index,
            source_y_index,
            initial_direction,
        )
        frontier: list[tuple[float, int, int, int, int, int, float]] = list()
        initial_estimate: float = (
            abs(source_stub.get_x() - target_stub.get_x())
            + abs(source_stub.get_y() - target_stub.get_y())
        )
        heapq.heappush(
            frontier,
            (
                initial_estimate,
                0,
                0,
                source_x_index,
                source_y_index,
                initial_direction,
                0.0,
            ),
        )
        distances: dict[tuple[int, int, int], float] = dict()
        distances[initial_state] = 0.0
        predecessors: dict[
            tuple[int, int, int],
            tuple[int, int, int],
        ] = dict()
        accepted_state: tuple[int, int, int] | None = None
        expanded_state_count: int = 0
        queue_sequence: int = 0
        segment_availability_cache: dict[
            tuple[int, int, int, int],
            bool,
        ] = dict()
        point_availability_cache: dict[tuple[int, int], bool] = dict()

        # Adjacent grid nodes are sufficient: every longer visible segment is a
        # chain of collinear adjacent segments and compression removes the extras.
        while len(frontier) > 0 and expanded_state_count < self._max_search_states:
            frontier_entry: tuple[float, int, int, int, int, int, float] = heapq.heappop(frontier)
            current_cost: float = frontier_entry[6]
            current_x_index: int = frontier_entry[3]
            current_y_index: int = frontier_entry[4]
            current_direction: int = frontier_entry[5]
            current_state: tuple[int, int, int] = (
                current_x_index,
                current_y_index,
                current_direction,
            )
            known_cost: float | None = distances.get(current_state, None)
            if known_cost is not None and current_cost <= known_cost + self._numerical_tolerance:
                expanded_state_count += 1
                if current_x_index == target_x_index and current_y_index == target_y_index:
                    accepted_state = current_state
                    frontier.clear()
                else:
                    neighbour_steps: tuple[tuple[int, int, int], ...] = (
                        (-1, 0, 1),
                        (1, 0, 1),
                        (0, -1, 2),
                        (0, 1, 2),
                    )
                    neighbour_step: tuple[int, int, int]
                    for neighbour_step in neighbour_steps:
                        neighbour_x_index: int = current_x_index + neighbour_step[0]
                        neighbour_y_index: int = current_y_index + neighbour_step[1]
                        neighbour_direction: int = neighbour_step[2]
                        inside_grid: bool = (
                            neighbour_x_index >= 0
                            and neighbour_x_index < len(x_values)
                            and neighbour_y_index >= 0
                            and neighbour_y_index < len(y_values)
                        )
                        # Terminal stubs are topology, not optional search
                        # hints. A feedback path must not reverse immediately
                        # over the source stub or enter the target stub from the
                        # block side, because collinear compression would then
                        # reduce the requested access to one pixel.
                        reverses_source_stub: bool = (
                            current_state == initial_state
                            and self._source_stub_length > 0.0
                            and neighbour_x_index < current_x_index
                        )
                        enters_target_stub_from_inside: bool = (
                            neighbour_x_index == target_x_index
                            and neighbour_y_index == target_y_index
                            and self._target_stub_length > 0.0
                            and current_x_index > target_x_index
                        )
                        if (
                                inside_grid
                                and not reverses_source_stub
                                and not enters_target_stub_from_inside
                        ):
                            current_point: RoutingPoint = RoutingPoint(
                                x_values[current_x_index],
                                y_values[current_y_index],
                            )
                            neighbour_point: RoutingPoint = RoutingPoint(
                                x_values[neighbour_x_index],
                                y_values[neighbour_y_index],
                            )
                            neighbour_point_key: tuple[int, int] = (
                                neighbour_x_index,
                                neighbour_y_index,
                            )
                            neighbour_point_available: bool | None = (
                                point_availability_cache.get(neighbour_point_key, None)
                            )
                            if neighbour_point_available is None:
                                neighbour_point_available = not (
                                    self._point_is_on_reserved_segment_interior(neighbour_point)
                                )
                                point_availability_cache[neighbour_point_key] = (
                                    neighbour_point_available
                                )
                            else:
                                pass
                            if (
                                    current_x_index < neighbour_x_index
                                    or (
                                        current_x_index == neighbour_x_index
                                        and current_y_index <= neighbour_y_index
                                    )
                            ):
                                segment_key: tuple[int, int, int, int] = (
                                    current_x_index,
                                    current_y_index,
                                    neighbour_x_index,
                                    neighbour_y_index,
                                )
                            else:
                                segment_key = (
                                    neighbour_x_index,
                                    neighbour_y_index,
                                    current_x_index,
                                    current_y_index,
                                )
                            segment_available: bool | None = (
                                segment_availability_cache.get(segment_key, None)
                            )
                            if segment_available is None:
                                segment_available = self._segment_is_available(
                                    current_point,
                                    neighbour_point,
                                )
                                segment_availability_cache[segment_key] = segment_available
                            else:
                                pass
                            if (
                                    neighbour_point_available
                                    and segment_available
                            ):
                                segment_length: float = (
                                    abs(current_point.get_x() - neighbour_point.get_x())
                                    + abs(current_point.get_y() - neighbour_point.get_y())
                                )
                                changes_direction: bool = (
                                    current_direction > 0
                                    and current_direction != neighbour_direction
                                )
                                bend_cost: float = self._bend_penalty if changes_direction else 0.0
                                neighbour_cost: float = current_cost + segment_length + bend_cost
                                neighbour_state: tuple[int, int, int] = (
                                    neighbour_x_index,
                                    neighbour_y_index,
                                    neighbour_direction,
                                )
                                old_neighbour_cost: float | None = distances.get(neighbour_state, None)
                                if old_neighbour_cost is None or neighbour_cost < old_neighbour_cost:
                                    distances[neighbour_state] = neighbour_cost
                                    predecessors[neighbour_state] = current_state
                                    queue_sequence += 1
                                    remaining_estimate: float = (
                                        abs(
                                            x_values[neighbour_x_index]
                                            - x_values[target_x_index]
                                        )
                                        + abs(
                                            y_values[neighbour_y_index]
                                            - y_values[target_y_index]
                                        )
                                    )
                                    heapq.heappush(
                                        frontier,
                                        (
                                            neighbour_cost + remaining_estimate,
                                            0,
                                            queue_sequence,
                                            neighbour_x_index,
                                            neighbour_y_index,
                                            neighbour_direction,
                                            neighbour_cost,
                                        ),
                                    )
                                else:
                                    pass
                            else:
                                pass
                        else:
                            pass
            else:
                pass

        if accepted_state is None:
            return None
        else:
            pass
        reversed_points: list[RoutingPoint] = list()
        path_state: tuple[int, int, int] = accepted_state
        reversed_points.append(
            RoutingPoint(x_values[path_state[0]], y_values[path_state[1]])
        )
        while path_state != initial_state:
            predecessor_state: tuple[int, int, int] | None = predecessors.get(path_state, None)
            if predecessor_state is None:
                return None
            else:
                path_state = predecessor_state
                reversed_points.append(
                    RoutingPoint(x_values[path_state[0]], y_values[path_state[1]])
                )
        interior_points: list[RoutingPoint] = list(reversed(reversed_points))
        route_points: list[RoutingPoint] = list((self._source_point.copy(),))
        interior_point: RoutingPoint
        for interior_point in interior_points:
            route_points.append(interior_point)
        route_points.append(self._target_point.copy())
        return self._compress_route(route_points)

    def _segment_is_available(
            self,
            segment_start: RoutingPoint,
            segment_end: RoutingPoint,
            permitted_terminal_point: RoutingPoint | None = None,
    ) -> bool:
        """Validate one candidate segment against obstacles and accepted wires.

        :param segment_start: Candidate segment start.
        :param segment_end: Candidate segment end.
        :param permitted_terminal_point: Port allowed inside its one-pixel owner clearance.
        :return: Whether the segment is globally available.
        """
        horizontal: bool = self._points_share_y(segment_start, segment_end)
        vertical: bool = self._points_share_x(segment_start, segment_end)
        if not horizontal and not vertical:
            return False
        else:
            pass

        obstacle_rect: tuple[float, float, float, float]
        for obstacle_rect in self._obstacle_rects:
            if horizontal:
                crosses_vertical_span: bool = (
                        segment_start.get_y() > obstacle_rect[1] + self._numerical_tolerance
                        and segment_start.get_y() < obstacle_rect[3] - self._numerical_tolerance
                )
                overlaps_horizontal_span: bool = (
                        min(segment_start.get_x(), segment_end.get_x())
                        < obstacle_rect[2] - self._numerical_tolerance
                        and max(segment_start.get_x(), segment_end.get_x())
                        > obstacle_rect[0] + self._numerical_tolerance
                )
                if crosses_vertical_span and overlaps_horizontal_span:
                    terminal_is_inside_obstacle: bool = (
                            permitted_terminal_point is not None
                            and permitted_terminal_point.get_x()
                            >= obstacle_rect[0] - self._numerical_tolerance
                            and permitted_terminal_point.get_x()
                            <= obstacle_rect[2] + self._numerical_tolerance
                            and permitted_terminal_point.get_y()
                            >= obstacle_rect[1] - self._numerical_tolerance
                            and permitted_terminal_point.get_y()
                            <= obstacle_rect[3] + self._numerical_tolerance
                    )
                    if terminal_is_inside_obstacle:
                        pass
                    else:
                        return False
                else:
                    pass
            else:
                crosses_horizontal_span: bool = (
                        segment_start.get_x() > obstacle_rect[0] + self._numerical_tolerance
                        and segment_start.get_x() < obstacle_rect[2] - self._numerical_tolerance
                )
                overlaps_vertical_span: bool = (
                        min(segment_start.get_y(), segment_end.get_y())
                        < obstacle_rect[3] - self._numerical_tolerance
                        and max(segment_start.get_y(), segment_end.get_y())
                        > obstacle_rect[1] + self._numerical_tolerance
                )
                if crosses_horizontal_span and overlaps_vertical_span:
                    terminal_is_inside_obstacle = (
                            permitted_terminal_point is not None
                            and permitted_terminal_point.get_x()
                            >= obstacle_rect[0] - self._numerical_tolerance
                            and permitted_terminal_point.get_x()
                            <= obstacle_rect[2] + self._numerical_tolerance
                            and permitted_terminal_point.get_y()
                            >= obstacle_rect[1] - self._numerical_tolerance
                            and permitted_terminal_point.get_y()
                            <= obstacle_rect[3] + self._numerical_tolerance
                    )
                    if terminal_is_inside_obstacle:
                        pass
                    else:
                        return False
                else:
                    pass

        if self._segment_collides_with_reserved_index(
                segment_start=segment_start,
                segment_end=segment_end,
        ):
            return False
        else:
            pass
        return True

    def _segment_collides_with_reserved_index(
            self,
            segment_start: RoutingPoint,
            segment_end: RoutingPoint,
    ) -> bool:
        """Query indexed reserved segments for one orthogonal collision.

        :param segment_start: Candidate segment start.
        :param segment_end: Candidate segment end.
        :return: Whether a crossing, T-junction, or positive overlap exists.
        """
        horizontal: bool = self._points_share_y(segment_start, segment_end)
        if horizontal:
            fixed_coordinate: float = segment_start.get_y()
            span_start: float = min(segment_start.get_x(), segment_end.get_x())
            span_end: float = max(segment_start.get_x(), segment_end.get_x())
            same_axis_values: list[float] = self._reserved_horizontal_y_values
            crossing_axis_values: list[float] = self._reserved_vertical_x_values
            same_axis_intervals: dict[float, list[tuple[float, float]]] = (
                self._reserved_horizontal_intervals_by_y
            )
            crossing_axis_intervals: dict[float, list[tuple[float, float]]] = (
                self._reserved_vertical_intervals_by_x
            )
        else:
            fixed_coordinate = segment_start.get_x()
            span_start = min(segment_start.get_y(), segment_end.get_y())
            span_end = max(segment_start.get_y(), segment_end.get_y())
            same_axis_values = self._reserved_vertical_x_values
            crossing_axis_values = self._reserved_horizontal_y_values
            same_axis_intervals = self._reserved_vertical_intervals_by_x
            crossing_axis_intervals = self._reserved_horizontal_intervals_by_y

        # Collinear segments collide when they share positive length. Nearby
        # fixed coordinates are included to preserve the original tolerance.
        same_axis_start_index: int = bisect_left(
            same_axis_values,
            fixed_coordinate - self._numerical_tolerance,
        )
        same_axis_end_index: int = bisect_right(
            same_axis_values,
            fixed_coordinate + self._numerical_tolerance,
        )
        axis_value: float
        interval: tuple[float, float]
        for axis_value in same_axis_values[same_axis_start_index:same_axis_end_index]:
            for interval in same_axis_intervals[axis_value]:
                overlap_length: float = (
                    min(span_end, interval[1]) - max(span_start, interval[0])
                )
                if overlap_length > self._numerical_tolerance:
                    return True
                else:
                    pass

        # Perpendicular segments collide only when their intersection lies in
        # both interiors. Endpoint contact remains available exactly as before.
        crossing_axis_start_index: int = bisect_right(
            crossing_axis_values,
            span_start + self._numerical_tolerance,
        )
        crossing_axis_end_index: int = bisect_left(
            crossing_axis_values,
            span_end - self._numerical_tolerance,
        )
        for axis_value in crossing_axis_values[
            crossing_axis_start_index:crossing_axis_end_index
        ]:
            for interval in crossing_axis_intervals[axis_value]:
                inside_crossing_interval: bool = (
                    fixed_coordinate
                    > interval[0] + self._numerical_tolerance
                    and fixed_coordinate
                    < interval[1] - self._numerical_tolerance
                )
                if inside_crossing_interval:
                    return True
                else:
                    pass
        return False

    def _segments_collide(
            self,
            first_start: RoutingPoint,
            first_end: RoutingPoint,
            second_start: RoutingPoint,
            second_end: RoutingPoint,
    ) -> bool:
        """Return whether two orthogonal segments collide beyond a shared endpoint.

        :param first_start: First segment start.
        :param first_end: First segment end.
        :param second_start: Second segment start.
        :param second_end: Second segment end.
        :return: ``True`` for a crossing, T-junction, or shared positive length.
        """
        return orthogonal_routing_segments_collide(
            first_start=first_start,
            first_end=first_end,
            second_start=second_start,
            second_end=second_end,
            tolerance=self._numerical_tolerance,
        )

    def _point_is_on_reserved_segment_interior(self, point: RoutingPoint) -> bool:
        """Return whether a grid node would create an implicit cable junction.

        :param point: Candidate visibility-grid node.
        :return: Whether the point lies strictly inside an accepted segment.
        """
        horizontal_start_index: int = bisect_left(
            self._reserved_horizontal_y_values,
            point.get_y() - self._numerical_tolerance,
        )
        horizontal_end_index: int = bisect_right(
            self._reserved_horizontal_y_values,
            point.get_y() + self._numerical_tolerance,
        )
        horizontal_y: float
        horizontal_interval: tuple[float, float]
        for horizontal_y in self._reserved_horizontal_y_values[
            horizontal_start_index:horizontal_end_index
        ]:
            for horizontal_interval in self._reserved_horizontal_intervals_by_y[horizontal_y]:
                inside_horizontal: bool = (
                    point.get_x()
                    > horizontal_interval[0] + self._numerical_tolerance
                    and point.get_x()
                    < horizontal_interval[1] - self._numerical_tolerance
                )
                if inside_horizontal:
                    return True
                else:
                    pass

        vertical_start_index: int = bisect_left(
            self._reserved_vertical_x_values,
            point.get_x() - self._numerical_tolerance,
        )
        vertical_end_index: int = bisect_right(
            self._reserved_vertical_x_values,
            point.get_x() + self._numerical_tolerance,
        )
        vertical_x: float
        vertical_interval: tuple[float, float]
        for vertical_x in self._reserved_vertical_x_values[
            vertical_start_index:vertical_end_index
        ]:
            for vertical_interval in self._reserved_vertical_intervals_by_x[vertical_x]:
                inside_vertical: bool = (
                    point.get_y()
                    > vertical_interval[0] + self._numerical_tolerance
                    and point.get_y()
                    < vertical_interval[1] - self._numerical_tolerance
                )
                if inside_vertical:
                    return True
                else:
                    pass
        return False

    def _compress_route(self, route_points: list[RoutingPoint]) -> list[RoutingPoint]:
        """Remove duplicate and collinear points from one route.

        :param route_points: Raw ordered route points.
        :return: Equivalent minimal orthogonal point chain.
        """
        compressed_points: list[RoutingPoint] = list()
        route_point: RoutingPoint
        for route_point in route_points:
            if (
                    len(compressed_points) > 0
                    and self._points_are_equal(compressed_points[-1], route_point)
            ):
                pass
            else:
                compressed_points.append(route_point.copy())
        point_index: int = 1
        while point_index < len(compressed_points) - 1:
            previous_point: RoutingPoint = compressed_points[point_index - 1]
            current_point: RoutingPoint = compressed_points[point_index]
            next_point: RoutingPoint = compressed_points[point_index + 1]
            same_x: bool = (
                    self._points_share_x(previous_point, current_point)
                    and self._points_share_x(current_point, next_point)
            )
            same_y: bool = (
                    self._points_share_y(previous_point, current_point)
                    and self._points_share_y(current_point, next_point)
            )
            if same_x or same_y:
                del compressed_points[point_index]
            else:
                point_index += 1
        return compressed_points

    def _points_are_equal(self, first_point: RoutingPoint, second_point: RoutingPoint) -> bool:
        """Return whether two points match within routing tolerance.

        :param first_point: First point.
        :param second_point: Second point.
        :return: Numerical equality state.
        """
        if (
                self._points_share_x(first_point, second_point)
                and self._points_share_y(first_point, second_point)
        ):
            return True
        else:
            return False

    def _points_share_x(self, first_point: RoutingPoint, second_point: RoutingPoint) -> bool:
        """Return whether two points share one X coordinate.

        :param first_point: First point.
        :param second_point: Second point.
        :return: X-alignment state.
        """
        return (
                abs(first_point.get_x() - second_point.get_x())
                <= self._numerical_tolerance
        )

    def _points_share_y(self, first_point: RoutingPoint, second_point: RoutingPoint) -> bool:
        """Return whether two points share one Y coordinate.

        :param first_point: First point.
        :param second_point: Second point.
        :return: Y-alignment state.
        """
        return (
                abs(first_point.get_y() - second_point.get_y())
                <= self._numerical_tolerance
        )
