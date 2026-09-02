# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import heapq

from VeraGrid.Gui.DynamicModelEditor.Routing.routing_constraint_engine import RoutingConstraintEngine
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_elements import RoutingNode
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_elements import RoutingPoint
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_elements import RoutingSegment
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_graph import RoutingGraph
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_policy import AutomaticRoutingPolicy
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_scene_geometry import RoutingBlockGeometry
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_scene_geometry import RoutingBounds
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_scene_geometry import RoutingConnectionGeometry
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_scene_geometry import RoutingSegmentObstacle
from VeraGridEngine.enumerations import RoutingAxis, RoutingNodeKind, RoutingPortSide


class AutomaticRouteBuilder:
    """
    Rebuild the central continuation-to-continuation interval of one route.

    The builder never mutates the supplied graph. It preserves both mandatory
    PORT -> STUB -> continuation attachments, searches a sparse orthogonal
    visibility graph between both continuation elbows and returns one
    independently validated candidate.
    Blocks remain hard obstacles. Wire crossings are attempted only after the
    strict search fails and then receive a dominant cost.

    :param graph: Existing route whose conflicting interval must be replaced.
    :param connection_geometry: Point-in-time block and wire obstacles.
    :return: None.
    """

    __slots__ = (
        "_graph",
        "_connection_geometry",
        "_clearance",
        "_search_margin",
    )

    def __init__(
            self,
            graph: RoutingGraph,
            connection_geometry: RoutingConnectionGeometry,
    ) -> None:
        """
        Build one automatic route reconstruction request.

        :param graph: Existing route whose conflicting interval must be replaced.
        :param connection_geometry: Point-in-time block and wire obstacles.
        :return: None.
        """
        self._graph: RoutingGraph = graph
        self._connection_geometry: RoutingConnectionGeometry = connection_geometry
        self._clearance: float = 12.0
        self._search_margin: float = 250.0

    def build_alternative(self) -> RoutingGraph | None:
        """
        Build a valid replacement while preserving both port attachments.

        Strict search runs before wire crossings are relaxed. A candidate is
        returned only after complete graph and constraint validation under the
        policy that produced it.

        :return: Detached alternative graph, or ``None`` when no route exists.
        """
        # Automatic reconstruction always operates on a detached graph whose
        # endpoint stubs have first been synchronized with the current ports.
        # This prevents stale PORT -> STUB geometry from contaminating either
        # conflict detection or the later visibility search.
        prepared_graph: RoutingGraph | None = self._prepare_graph_with_mandatory_stubs()
        if prepared_graph is None:
            return None
        else:
            self._graph = prepared_graph

        conflict_interval: tuple[int, int] | None = self._find_conflict_interval()
        if conflict_interval is None:
            return self._graph.clone()
        else:
            detected_first_conflict_index: int = conflict_interval[0]
            detected_last_conflict_index: int = conflict_interval[1]

        ordered_nodes: list[RoutingNode] = self._graph.get_ordered_nodes()
        if len(ordered_nodes) < 6:
            return None
        else:
            # Ports, stubs and minimum continuations never participate in path
            # finding. Automatic reconstruction replaces only the central route
            # between the two continuation elbows.
            first_conflict_index: int = 2
            last_conflict_index: int = len(ordered_nodes) - 4
            start_anchor: RoutingNode = ordered_nodes[2]
            end_anchor: RoutingNode = ordered_nodes[-3]
            if (start_anchor.get_kind() != RoutingNodeKind.ELBOW
                    or end_anchor.get_kind() != RoutingNodeKind.ELBOW):
                return None
            else:
                pass
            search_start_anchor: RoutingNode = self._build_detached_continuation_anchor(
                anchor_node=start_anchor,
                temporary_node_id=-1,
            )
            search_end_anchor: RoutingNode = self._build_detached_continuation_anchor(
                anchor_node=end_anchor,
                temporary_node_id=-2,
            )
            local_geometry: RoutingConnectionGeometry = self._build_central_search_connection_geometry()
            search_bounds: RoutingBounds = self._build_conflict_search_bounds(
                ordered_nodes=ordered_nodes,
                first_conflict_index=detected_first_conflict_index,
                last_conflict_index=detected_last_conflict_index,
            )
            filtered_local_geometry: RoutingConnectionGeometry = self._build_search_connection_geometry(
                local_geometry=local_geometry,
                minimum_search_x=search_bounds.get_left() - self._clearance,
                maximum_search_x=search_bounds.get_right() + self._clearance,
                minimum_search_y=search_bounds.get_top() - self._clearance,
                maximum_search_y=search_bounds.get_bottom() + self._clearance,
            )
            visibility_graph: RoutingGraph
            visibility_start_node_id: int
            visibility_end_node_id: int
            visibility_graph, visibility_start_node_id, visibility_end_node_id = (
                self._build_visibility_search_graph(
                    start_anchor=search_start_anchor,
                    end_anchor=search_end_anchor,
                    local_geometry=filtered_local_geometry,
                    search_bounds=search_bounds,
                )
            )
            crossing_count_by_segment_id: dict[int, int] = self._build_crossing_count_lookup(
                search_graph=visibility_graph,
                local_geometry=filtered_local_geometry,
            )

        local_strict_candidate: RoutingGraph | None = self._build_valid_search_candidate(
            search_graph=visibility_graph,
            start_node_id=visibility_start_node_id,
            end_node_id=visibility_end_node_id,
            crossing_count_by_segment_id=crossing_count_by_segment_id,
            routing_policy=AutomaticRoutingPolicy.STRICT,
            ordered_nodes=ordered_nodes,
            first_conflict_index=first_conflict_index,
            last_conflict_index=last_conflict_index,
        )
        if local_strict_candidate is not None:
            return local_strict_candidate
        else:
            pass

        # A failed local search does not justify crossing another connection.
        # First construct a wider frame around every relevant obstacle and
        # explicitly attempt the strict exterior corridor on that graph.
        exterior_margins: tuple[float, ...] = self._build_exterior_search_margins(
            start_position=search_start_anchor.get_position(),
            end_position=search_end_anchor.get_position(),
            local_geometry=local_geometry,
        )
        last_exterior_graph: RoutingGraph | None = None
        last_exterior_start_node_id: int | None = None
        last_exterior_end_node_id: int | None = None
        last_crossing_count_by_segment_id: dict[int, int] | None = None
        exterior_margin: float
        for exterior_margin in exterior_margins:
            exterior_search_bounds: RoutingBounds = self._build_exterior_search_bounds(
                start_position=search_start_anchor.get_position(),
                end_position=search_end_anchor.get_position(),
                local_geometry=local_geometry,
                exterior_margin=exterior_margin,
            )
            exterior_graph: RoutingGraph
            exterior_start_node_id: int
            exterior_end_node_id: int
            exterior_graph, exterior_start_node_id, exterior_end_node_id = self._build_visibility_search_graph(
                start_anchor=search_start_anchor,
                end_anchor=search_end_anchor,
                local_geometry=local_geometry,
                search_bounds=exterior_search_bounds,
            )
            exterior_crossing_count_by_segment_id: dict[int, int] = self._build_crossing_count_lookup(
                search_graph=exterior_graph,
                local_geometry=local_geometry,
            )
            exterior_strict_candidate: RoutingGraph | None = self._build_valid_search_candidate(
                search_graph=exterior_graph,
                start_node_id=exterior_start_node_id,
                end_node_id=exterior_end_node_id,
                crossing_count_by_segment_id=exterior_crossing_count_by_segment_id,
                routing_policy=AutomaticRoutingPolicy.STRICT,
                ordered_nodes=ordered_nodes,
                first_conflict_index=first_conflict_index,
                last_conflict_index=last_conflict_index,
            )
            if exterior_strict_candidate is not None:
                return exterior_strict_candidate
            else:
                last_exterior_graph = exterior_graph
                last_exterior_start_node_id = exterior_start_node_id
                last_exterior_end_node_id = exterior_end_node_id
                last_crossing_count_by_segment_id = exterior_crossing_count_by_segment_id

        if (last_exterior_graph is None
                or last_exterior_start_node_id is None
                or last_exterior_end_node_id is None
                or last_crossing_count_by_segment_id is None):
            return None
        else:
            pass

        return self._build_valid_search_candidate(
            search_graph=last_exterior_graph,
            start_node_id=last_exterior_start_node_id,
            end_node_id=last_exterior_end_node_id,
            crossing_count_by_segment_id=last_crossing_count_by_segment_id,
            routing_policy=AutomaticRoutingPolicy.ALLOW_WIRE_CROSSINGS,
            ordered_nodes=ordered_nodes,
            first_conflict_index=first_conflict_index,
            last_conflict_index=last_conflict_index,
        )

    def _build_conflict_search_bounds(
            self,
            ordered_nodes: list[RoutingNode],
            first_conflict_index: int,
            last_conflict_index: int,
    ) -> RoutingBounds:
        """
        Build the bounded search environment around the real conflict interval.

        Both continuation elbows are included because path finding spans the
        full central route. Conflict nodes extend the bounds when preserved
        manual routing previously travelled outside the direct endpoint rectangle.

        :param ordered_nodes: Prepared route nodes from source to destination.
        :param first_conflict_index: First invalid segment index.
        :param last_conflict_index: Last invalid segment index.
        :return: Expanded non-Qt search bounds.
        """
        relevant_positions: list[RoutingPoint] = list((
            ordered_nodes[2].get_position(),
            ordered_nodes[-3].get_position(),
        ))
        node_index: int
        for node_index in range(first_conflict_index, last_conflict_index + 2):
            if 0 <= node_index < len(ordered_nodes):
                relevant_positions.append(ordered_nodes[node_index].get_position())
            else:
                pass

        minimum_x: float = relevant_positions[0].get_x()
        maximum_x: float = relevant_positions[0].get_x()
        minimum_y: float = relevant_positions[0].get_y()
        maximum_y: float = relevant_positions[0].get_y()
        relevant_position: RoutingPoint
        for relevant_position in relevant_positions:
            minimum_x = min(minimum_x, relevant_position.get_x())
            maximum_x = max(maximum_x, relevant_position.get_x())
            minimum_y = min(minimum_y, relevant_position.get_y())
            maximum_y = max(maximum_y, relevant_position.get_y())

        return RoutingBounds(
            left=minimum_x - self._search_margin,
            top=minimum_y - self._search_margin,
            right=maximum_x + self._search_margin,
            bottom=maximum_y + self._search_margin,
        )

    def _build_exterior_search_bounds(
            self,
            start_position: RoutingPoint,
            end_position: RoutingPoint,
            local_geometry: RoutingConnectionGeometry,
            exterior_margin: float,
    ) -> RoutingBounds:
        """
        Build a frame outside every block and foreign wire endpoint.

        :param start_position: Source continuation position.
        :param end_position: Destination continuation position.
        :param local_geometry: Complete central-search obstacle geometry.
        :param exterior_margin: Required free-space margin around all geometry.
        :return: Bounds exposing an exterior strict-routing corridor.
        """
        minimum_x: float = min(start_position.get_x(), end_position.get_x())
        maximum_x: float = max(start_position.get_x(), end_position.get_x())
        minimum_y: float = min(start_position.get_y(), end_position.get_y())
        maximum_y: float = max(start_position.get_y(), end_position.get_y())

        block_geometry: RoutingBlockGeometry
        for block_geometry in local_geometry.get_other_blocks():
            block_bounds: RoutingBounds = block_geometry.get_bounds()
            minimum_x = min(minimum_x, block_bounds.get_left())
            maximum_x = max(maximum_x, block_bounds.get_right())
            minimum_y = min(minimum_y, block_bounds.get_top())
            maximum_y = max(maximum_y, block_bounds.get_bottom())

        obstacle_segment: RoutingSegmentObstacle
        for obstacle_segment in local_geometry.get_other_connection_segments():
            obstacle_position: RoutingPoint
            for obstacle_position in (
                    obstacle_segment.get_start_position(),
                    obstacle_segment.get_end_position(),
            ):
                minimum_x = min(minimum_x, obstacle_position.get_x())
                maximum_x = max(maximum_x, obstacle_position.get_x())
                minimum_y = min(minimum_y, obstacle_position.get_y())
                maximum_y = max(maximum_y, obstacle_position.get_y())

        return RoutingBounds(
            left=minimum_x - exterior_margin,
            top=minimum_y - exterior_margin,
            right=maximum_x + exterior_margin,
            bottom=maximum_y + exterior_margin,
        )

    def _build_exterior_search_margins(
            self,
            start_position: RoutingPoint,
            end_position: RoutingPoint,
            local_geometry: RoutingConnectionGeometry,
    ) -> tuple[float, ...]:
        """
        Build progressive exterior margins ending beyond the scene span.

        :param start_position: Source continuation position.
        :param end_position: Destination continuation position.
        :param local_geometry: Complete central-search obstacle geometry.
        :return: Increasing unique exterior margins.
        """
        geometry_bounds: RoutingBounds = self._build_exterior_search_bounds(
            start_position=start_position,
            end_position=end_position,
            local_geometry=local_geometry,
            exterior_margin=0.0,
        )
        geometry_width: float = geometry_bounds.get_right() - geometry_bounds.get_left()
        geometry_height: float = geometry_bounds.get_bottom() - geometry_bounds.get_top()
        scene_scale_margin: float = max(
            1000.0,
            geometry_width,
            geometry_height,
        ) + self._clearance
        candidate_margins: tuple[float, ...] = (
            self._search_margin + self._clearance,
            500.0 + self._clearance,
            1000.0 + self._clearance,
            scene_scale_margin,
        )
        unique_margins: list[float] = list()
        candidate_margin: float
        for candidate_margin in candidate_margins:
            if candidate_margin in unique_margins:
                pass
            else:
                unique_margins.append(candidate_margin)
        unique_margins.sort()
        return tuple(unique_margins)

    def _build_valid_search_candidate(
            self,
            search_graph: RoutingGraph,
            start_node_id: int,
            end_node_id: int,
            crossing_count_by_segment_id: dict[int, int],
            routing_policy: AutomaticRoutingPolicy,
            ordered_nodes: list[RoutingNode],
            first_conflict_index: int,
            last_conflict_index: int,
    ) -> RoutingGraph | None:
        """
        Search, splice and validate one candidate under a selected policy.

        :param search_graph: Reusable visibility graph.
        :param start_node_id: Visibility source identifier.
        :param end_node_id: Visibility destination identifier.
        :param crossing_count_by_segment_id: Cached crossings per edge.
        :param routing_policy: Strict or relaxed wire policy.
        :param ordered_nodes: Prepared original route nodes.
        :param first_conflict_index: First central segment to replace.
        :param last_conflict_index: Last central segment to replace.
        :return: Fully validated candidate or ``None``.
        """
        replacement_points: list[RoutingPoint] | None = self._search_replacement_points(
            search_graph=search_graph,
            start_node_id=start_node_id,
            end_node_id=end_node_id,
            crossing_count_by_segment_id=crossing_count_by_segment_id,
            routing_policy=routing_policy,
        )
        if replacement_points is None:
            return None
        else:
            candidate_graph: RoutingGraph | None = self._splice_replacement_points(
                ordered_nodes=ordered_nodes,
                first_conflict_index=first_conflict_index,
                last_conflict_index=last_conflict_index,
                replacement_points=replacement_points,
            )

        if candidate_graph is None:
            return None
        elif self._is_graph_valid(graph=candidate_graph, routing_policy=routing_policy):
            return candidate_graph
        else:
            return None

    def _prepare_graph_with_mandatory_stubs(self) -> RoutingGraph | None:
        """
        Clone the route and synchronize mandatory stubs and continuations.

        The route requires one explicit STUB and one continuation ELBOW next to
        each PORT. The automatic builder does not invent missing topology; it
        recalculates those existing positions through the shared
        :class:`RoutingGeometry` policy before any search begins.

        :return: Detached graph with synchronized endpoint geometry, or
            ``None`` when the required topology is unavailable.
        """
        prepared_graph: RoutingGraph = self._graph.clone()
        ordered_nodes: list[RoutingNode] = prepared_graph.get_ordered_nodes()
        if len(ordered_nodes) < 6:
            return None
        else:
            source_port: RoutingNode = ordered_nodes[0]
            source_stub: RoutingNode = ordered_nodes[1]
            source_continuation: RoutingNode = ordered_nodes[2]
            destination_continuation: RoutingNode = ordered_nodes[-3]
            destination_stub: RoutingNode = ordered_nodes[-2]
            destination_port: RoutingNode = ordered_nodes[-1]

        source_port_side: RoutingPortSide | None = source_port.get_port_side()
        destination_port_side: RoutingPortSide | None = destination_port.get_port_side()
        endpoint_kinds_valid: bool = (
            source_port.get_kind() == RoutingNodeKind.PORT
            and source_stub.get_kind() == RoutingNodeKind.STUB
            and source_continuation.get_kind() == RoutingNodeKind.ELBOW
            and destination_continuation.get_kind() == RoutingNodeKind.ELBOW
            and destination_stub.get_kind() == RoutingNodeKind.STUB
            and destination_port.get_kind() == RoutingNodeKind.PORT
        )
        if not endpoint_kinds_valid:
            return None
        else:
            pass

        if source_port_side is None or destination_port_side is None:
            return None
        else:
            pass

        source_stub_position: RoutingPoint = prepared_graph.get_geometry().build_port_stub_point(
            port_position=source_port.get_position(),
            port_side=source_port_side,
        )
        destination_stub_position: RoutingPoint = prepared_graph.get_geometry().build_port_stub_point(
            port_position=destination_port.get_position(),
            port_side=destination_port_side,
        )
        source_continuation_position: RoutingPoint = prepared_graph.get_geometry().build_stub_continuation_point(
            stub_position=source_stub_position,
            port_side=source_port_side,
        )
        destination_continuation_position: RoutingPoint = prepared_graph.get_geometry().build_stub_continuation_point(
            stub_position=destination_stub_position,
            port_side=destination_port_side,
        )
        source_stub.set_position(source_stub_position)
        destination_stub.set_position(destination_stub_position)
        source_continuation.set_position(source_continuation_position)
        destination_continuation.set_position(destination_continuation_position)
        return prepared_graph

    def _build_detached_continuation_anchor(
            self,
            anchor_node: RoutingNode,
            temporary_node_id: int,
    ) -> RoutingNode:
        """
        Build one detached continuation anchor for path finding.

        :param anchor_node: Source or destination continuation elbow.
        :param temporary_node_id: Identifier used only before search graph remapping.
        :return: Detached local search anchor.
        """
        return RoutingNode(
            node_id=temporary_node_id,
            kind=RoutingNodeKind.ELBOW,
            position=anchor_node.get_position().copy(),
        )

    def _find_conflict_interval(self) -> tuple[int, int] | None:
        """
        Return the first and last invalid ordered segment indexes.

        The interval is used to decide whether reconstruction is required. The
        actual search still spans the complete central route between both
        mandatory continuation elbows.

        :return: Inclusive conflict interval or ``None`` for an already valid route.
        """
        ordered_segments: list[RoutingSegment] = self._graph.get_ordered_segments()
        first_conflict_index: int | None = None
        last_conflict_index: int | None = None
        segment_index: int
        route_segment: RoutingSegment

        for segment_index, route_segment in enumerate(ordered_segments):
            if self._is_segment_valid(
                    graph=self._graph,
                    segment=route_segment,
                    connection_geometry=self._connection_geometry,
                    routing_policy=AutomaticRoutingPolicy.STRICT,
            ):
                pass
            else:
                if first_conflict_index is None:
                    first_conflict_index = segment_index
                else:
                    pass
                last_conflict_index = segment_index

        if first_conflict_index is None or last_conflict_index is None:
            return None
        else:
            return first_conflict_index, last_conflict_index

    def _build_central_search_connection_geometry(self) -> RoutingConnectionGeometry:
        """
        Build obstacle ownership for a search between continuation elbows.

        Neither PORT participates in this search. Both endpoint owners must
        therefore behave as full obstacles, while a shared owner is inserted
        only once.

        :return: Geometry context for the local search graph.
        """
        source_owner: RoutingBlockGeometry | None = self._connection_geometry.get_source_owner()
        destination_owner: RoutingBlockGeometry | None = self._connection_geometry.get_destination_owner()
        local_other_blocks: list[RoutingBlockGeometry] = list(self._connection_geometry.get_other_blocks())
        same_endpoint_owner: bool = source_owner is destination_owner and source_owner is not None

        if source_owner is not None:
            local_other_blocks.append(source_owner)
        else:
            pass

        if destination_owner is not None and not same_endpoint_owner:
            local_other_blocks.append(destination_owner)
        else:
            pass

        return RoutingConnectionGeometry(
            source_owner=None,
            destination_owner=None,
            other_blocks=tuple(local_other_blocks),
            other_connection_segments=self._connection_geometry.get_other_connection_segments(),
        )

    def _search_replacement_points(
            self,
            search_graph: RoutingGraph,
            start_node_id: int,
            end_node_id: int,
            crossing_count_by_segment_id: dict[int, int],
            routing_policy: AutomaticRoutingPolicy,
    ) -> list[RoutingPoint] | None:
        """
        Search one previously materialized sparse visibility graph.

        :param search_graph: Reusable block-safe visibility graph.
        :param start_node_id: Visibility source-continuation identifier.
        :param end_node_id: Visibility destination-continuation identifier.
        :param crossing_count_by_segment_id: Cached foreign-wire crossings.
        :param routing_policy: Strict or crossing-penalized search policy.
        :return: Compressed replacement points or ``None``.
        """
        path_node_ids: list[int] | None = self._run_lexicographic_search(
            search_graph=search_graph,
            start_node_id=start_node_id,
            end_node_id=end_node_id,
            crossing_count_by_segment_id=crossing_count_by_segment_id,
            routing_policy=routing_policy,
        )
        if path_node_ids is None:
            return None
        else:
            path_points: list[RoutingPoint] = list()
            path_node_id: int
            for path_node_id in path_node_ids:
                path_node: RoutingNode | None = search_graph.get_node(path_node_id)
                if path_node is not None:
                    path_points.append(path_node.get_position().copy())
                else:
                    return None
            return self._compress_collinear_points(path_points=path_points)

    def _build_crossing_count_lookup(
            self,
            search_graph: RoutingGraph,
            local_geometry: RoutingConnectionGeometry,
    ) -> dict[int, int]:
        """
        Count foreign-wire intersections once for every visibility edge.

        :param search_graph: Block-safe reusable visibility graph.
        :param local_geometry: Filtered foreign-wire geometry.
        :return: Segment identifier to crossing-count lookup.
        """
        crossing_count_by_segment_id: dict[int, int] = dict()
        constraint_engine: RoutingConstraintEngine = RoutingConstraintEngine(graph=search_graph)
        route_segment: RoutingSegment
        for route_segment in search_graph.get_segments():
            crossing_count_by_segment_id[route_segment.get_segment_id()] = (
                constraint_engine.count_other_connection_intersections(
                    segment=route_segment,
                    connection_geometry=local_geometry,
                )
            )
        return crossing_count_by_segment_id

    def _build_visibility_search_graph(
            self,
            start_anchor: RoutingNode,
            end_anchor: RoutingNode,
            local_geometry: RoutingConnectionGeometry,
            search_bounds: RoutingBounds,
    ) -> tuple[RoutingGraph, int, int]:
        """
        Materialize one visibility graph shared by every search policy.

        Blocks are hard constraints and therefore define graph topology.
        Foreign wires affect only policy-specific traversal, so they remain
        available as annotated crossings without forcing graph reconstruction.

        :param start_anchor: Detached source continuation.
        :param end_anchor: Detached destination continuation.
        :param local_geometry: Filtered obstacle snapshot.
        :param search_bounds: Conflict-local search environment.
        :return: Visibility graph and its source/destination identifiers.
        """
        x_coordinates: list[float]
        y_coordinates: list[float]
        x_coordinates, y_coordinates = self._build_candidate_coordinates(
            start_position=start_anchor.get_position(),
            end_position=end_anchor.get_position(),
            local_geometry=local_geometry,
            search_bounds=search_bounds,
        )
        candidate_positions: tuple[RoutingPoint, ...] = self._build_sparse_candidate_positions(
            x_coordinates=x_coordinates,
            y_coordinates=y_coordinates,
            start_position=start_anchor.get_position(),
            end_position=end_anchor.get_position(),
            local_geometry=local_geometry,
        )
        return self._build_search_graph(
            x_coordinates=x_coordinates,
            y_coordinates=y_coordinates,
            candidate_positions=candidate_positions,
            start_anchor=start_anchor,
            end_anchor=end_anchor,
            local_geometry=local_geometry,
        )

    def _build_sparse_candidate_positions(
            self,
            x_coordinates: list[float],
            y_coordinates: list[float],
            start_position: RoutingPoint,
            end_position: RoutingPoint,
            local_geometry: RoutingConnectionGeometry,
    ) -> tuple[RoutingPoint, ...]:
        """
        Build sparse visibility waypoints without materializing an X/Y product.

        Anchors, obstacle-clearance corners and their projections onto both
        anchors and the exterior frame are sufficient to expose direct local
        corridors plus a guaranteed exterior detour corridor. Visibility
        edges are selected later by connecting only nearest aligned points.

        :param x_coordinates: Sorted relevant horizontal coordinates.
        :param y_coordinates: Sorted relevant vertical coordinates.
        :param start_position: Search start anchor.
        :param end_position: Search end anchor.
        :param local_geometry: Filtered block and wire geometry.
        :return: Immutable sparse candidate positions.
        """
        minimum_x: float = x_coordinates[0]
        maximum_x: float = x_coordinates[-1]
        minimum_y: float = y_coordinates[0]
        maximum_y: float = y_coordinates[-1]
        seed_coordinates: set[tuple[float, float]] = set((
            (start_position.get_x(), start_position.get_y()),
            (end_position.get_x(), end_position.get_y()),
            (minimum_x, minimum_y),
            (minimum_x, maximum_y),
            (maximum_x, minimum_y),
            (maximum_x, maximum_y),
        ))

        block_geometry: RoutingBlockGeometry
        for block_geometry in local_geometry.get_other_blocks():
            block_bounds: RoutingBounds = block_geometry.get_bounds()
            left_x: float = block_bounds.get_left() - self._clearance
            right_x: float = block_bounds.get_right() + self._clearance
            top_y: float = block_bounds.get_top() - self._clearance
            bottom_y: float = block_bounds.get_bottom() + self._clearance
            seed_coordinates.add((left_x, top_y))
            seed_coordinates.add((left_x, bottom_y))
            seed_coordinates.add((right_x, top_y))
            seed_coordinates.add((right_x, bottom_y))

        obstacle_segment: RoutingSegmentObstacle
        for obstacle_segment in local_geometry.get_other_connection_segments():
            obstacle_endpoint: RoutingPoint
            for obstacle_endpoint in (
                    obstacle_segment.get_start_position(),
                    obstacle_segment.get_end_position(),
            ):
                left_x = obstacle_endpoint.get_x() - self._clearance
                right_x = obstacle_endpoint.get_x() + self._clearance
                top_y = obstacle_endpoint.get_y() - self._clearance
                bottom_y = obstacle_endpoint.get_y() + self._clearance
                seed_coordinates.add((left_x, top_y))
                seed_coordinates.add((left_x, bottom_y))
                seed_coordinates.add((right_x, top_y))
                seed_coordinates.add((right_x, bottom_y))

        # Project every meaningful coordinate onto the anchors and exterior
        # frame. This keeps the graph linear in candidate coordinate count and
        # always provides a strict route around the complete local obstacle set.
        x_pos: float
        for x_pos in x_coordinates:
            seed_coordinates.add((x_pos, start_position.get_y()))
            seed_coordinates.add((x_pos, end_position.get_y()))
            seed_coordinates.add((x_pos, minimum_y))
            seed_coordinates.add((x_pos, maximum_y))
        y_pos: float
        for y_pos in y_coordinates:
            seed_coordinates.add((start_position.get_x(), y_pos))
            seed_coordinates.add((end_position.get_x(), y_pos))
            seed_coordinates.add((minimum_x, y_pos))
            seed_coordinates.add((maximum_x, y_pos))

        candidate_positions: list[RoutingPoint] = list()
        candidate_x: float
        candidate_y: float
        for candidate_x, candidate_y in sorted(seed_coordinates):
            candidate_positions.append(RoutingPoint(x_pos=candidate_x, y_pos=candidate_y))
        return tuple(candidate_positions)

    def _build_search_connection_geometry(
            self,
            local_geometry: RoutingConnectionGeometry,
            minimum_search_x: float,
            maximum_search_x: float,
            minimum_search_y: float,
            maximum_search_y: float,
    ) -> RoutingConnectionGeometry:
        """
        Reduce obstacle checks to geometry overlapping the local search area.

        Complete candidate validation still uses the original scene snapshot.
        This filtered snapshot only accelerates edge expansion inside a bounded
        area, where geometrically disjoint objects cannot invalidate an edge.

        :param local_geometry: Complete ownership-adjusted obstacle snapshot.
        :param minimum_search_x: Left search limit.
        :param maximum_search_x: Right search limit.
        :param minimum_search_y: Top search limit.
        :param maximum_search_y: Bottom search limit.
        :return: Local obstacle snapshot used during graph search.
        """
        relevant_blocks: list[RoutingBlockGeometry] = list()
        block_geometry: RoutingBlockGeometry
        for block_geometry in local_geometry.get_other_blocks():
            if self._bounds_intersect_search_area(
                    block_bounds=block_geometry.get_bounds(),
                    minimum_search_x=minimum_search_x,
                    maximum_search_x=maximum_search_x,
                    minimum_search_y=minimum_search_y,
                    maximum_search_y=maximum_search_y,
            ):
                relevant_blocks.append(block_geometry)
            else:
                pass

        relevant_segments: list[RoutingSegmentObstacle] = list()
        obstacle_segment: RoutingSegmentObstacle
        for obstacle_segment in local_geometry.get_other_connection_segments():
            if self._segment_intersects_search_area(
                    start_position=obstacle_segment.get_start_position(),
                    end_position=obstacle_segment.get_end_position(),
                    minimum_search_x=minimum_search_x,
                    maximum_search_x=maximum_search_x,
                    minimum_search_y=minimum_search_y,
                    maximum_search_y=maximum_search_y,
            ):
                relevant_segments.append(obstacle_segment)
            else:
                pass

        return RoutingConnectionGeometry(
            source_owner=local_geometry.get_source_owner(),
            destination_owner=local_geometry.get_destination_owner(),
            other_blocks=tuple(relevant_blocks),
            other_connection_segments=tuple(relevant_segments),
        )

    def _build_candidate_coordinates(
            self,
            start_position: RoutingPoint,
            end_position: RoutingPoint,
            local_geometry: RoutingConnectionGeometry,
            search_bounds: RoutingBounds,
    ) -> tuple[list[float], list[float]]:
        """
        Build sparse x and y coordinate lines around anchors and obstacles.

        :param start_position: Local search start position.
        :param end_position: Local search end position.
        :param local_geometry: Block and wire obstacle geometry.
        :param search_bounds: Conflict-local exterior search frame.
        :return: Sorted unique horizontal and vertical coordinates.
        """
        minimum_search_x: float = search_bounds.get_left()
        maximum_search_x: float = search_bounds.get_right()
        minimum_search_y: float = search_bounds.get_top()
        maximum_search_y: float = search_bounds.get_bottom()
        x_values: set[float] = set((
            start_position.get_x(),
            end_position.get_x(),
            minimum_search_x,
            maximum_search_x,
        ))
        y_values: set[float] = set((
            start_position.get_y(),
            end_position.get_y(),
            minimum_search_y,
            maximum_search_y,
        ))
        block_geometry: RoutingBlockGeometry
        endpoint_owner: RoutingBlockGeometry | None
        for endpoint_owner in (local_geometry.get_source_owner(), local_geometry.get_destination_owner()):
            if endpoint_owner is not None:
                endpoint_bounds: RoutingBounds = endpoint_owner.get_bounds()
                if self._bounds_intersect_search_area(
                        block_bounds=endpoint_bounds,
                        minimum_search_x=minimum_search_x,
                        maximum_search_x=maximum_search_x,
                        minimum_search_y=minimum_search_y,
                        maximum_search_y=maximum_search_y,
                ):
                    self._add_block_candidate_coordinates(
                        x_values=x_values,
                        y_values=y_values,
                        block_bounds=endpoint_bounds,
                    )
                else:
                    pass
            else:
                pass

        for block_geometry in local_geometry.get_other_blocks():
            block_bounds: RoutingBounds = block_geometry.get_bounds()
            if self._bounds_intersect_search_area(
                    block_bounds=block_bounds,
                    minimum_search_x=minimum_search_x,
                    maximum_search_x=maximum_search_x,
                    minimum_search_y=minimum_search_y,
                    maximum_search_y=maximum_search_y,
            ):
                self._add_block_candidate_coordinates(
                    x_values=x_values,
                    y_values=y_values,
                    block_bounds=block_bounds,
                )
            else:
                pass

        obstacle_segment: RoutingSegmentObstacle
        for obstacle_segment in local_geometry.get_other_connection_segments():
            obstacle_start: RoutingPoint = obstacle_segment.get_start_position()
            obstacle_end: RoutingPoint = obstacle_segment.get_end_position()
            if self._segment_intersects_search_area(
                    start_position=obstacle_start,
                    end_position=obstacle_end,
                    minimum_search_x=minimum_search_x,
                    maximum_search_x=maximum_search_x,
                    minimum_search_y=minimum_search_y,
                    maximum_search_y=maximum_search_y,
            ):
                x_values.add(obstacle_start.get_x() - self._clearance)
                x_values.add(obstacle_start.get_x() + self._clearance)
                x_values.add(obstacle_end.get_x() - self._clearance)
                x_values.add(obstacle_end.get_x() + self._clearance)
                y_values.add(obstacle_start.get_y() - self._clearance)
                y_values.add(obstacle_start.get_y() + self._clearance)
                y_values.add(obstacle_end.get_y() - self._clearance)
                y_values.add(obstacle_end.get_y() + self._clearance)
            else:
                pass

        return sorted(x_values), sorted(y_values)

    def _add_block_candidate_coordinates(
            self,
            x_values: set[float],
            y_values: set[float],
            block_bounds: RoutingBounds,
    ) -> None:
        """
        Add clearance coordinate lines around one relevant block.

        :param x_values: Mutable horizontal candidate-coordinate set.
        :param y_values: Mutable vertical candidate-coordinate set.
        :param block_bounds: Relevant block bounds.
        :return: None.
        """
        x_values.add(block_bounds.get_left() - self._clearance)
        x_values.add(block_bounds.get_right() + self._clearance)
        y_values.add(block_bounds.get_top() - self._clearance)
        y_values.add(block_bounds.get_bottom() + self._clearance)

    def _bounds_intersect_search_area(
            self,
            block_bounds: RoutingBounds,
            minimum_search_x: float,
            maximum_search_x: float,
            minimum_search_y: float,
            maximum_search_y: float,
    ) -> bool:
        """
        Return whether one block can affect the bounded local search.

        :param block_bounds: Candidate block bounds.
        :param minimum_search_x: Left search limit.
        :param maximum_search_x: Right search limit.
        :param minimum_search_y: Top search limit.
        :param maximum_search_y: Bottom search limit.
        :return: ``True`` when both closed rectangles overlap.
        """
        horizontally_disjoint: bool = (
            block_bounds.get_right() < minimum_search_x
            or block_bounds.get_left() > maximum_search_x
        )
        vertically_disjoint: bool = (
            block_bounds.get_bottom() < minimum_search_y
            or block_bounds.get_top() > maximum_search_y
        )
        if horizontally_disjoint or vertically_disjoint:
            return False
        else:
            return True

    def _segment_intersects_search_area(
            self,
            start_position: RoutingPoint,
            end_position: RoutingPoint,
            minimum_search_x: float,
            maximum_search_x: float,
            minimum_search_y: float,
            maximum_search_y: float,
    ) -> bool:
        """
        Return whether one foreign segment can affect the local search.

        :param start_position: Foreign segment start.
        :param end_position: Foreign segment end.
        :param minimum_search_x: Left search limit.
        :param maximum_search_x: Right search limit.
        :param minimum_search_y: Top search limit.
        :param maximum_search_y: Bottom search limit.
        :return: ``True`` when the segment bounding rectangle overlaps the area.
        """
        segment_minimum_x: float = min(start_position.get_x(), end_position.get_x())
        segment_maximum_x: float = max(start_position.get_x(), end_position.get_x())
        segment_minimum_y: float = min(start_position.get_y(), end_position.get_y())
        segment_maximum_y: float = max(start_position.get_y(), end_position.get_y())
        horizontally_disjoint: bool = (
            segment_maximum_x < minimum_search_x
            or segment_minimum_x > maximum_search_x
        )
        vertically_disjoint: bool = (
            segment_maximum_y < minimum_search_y
            or segment_minimum_y > maximum_search_y
        )
        if horizontally_disjoint or vertically_disjoint:
            return False
        else:
            return True

    def _build_search_graph(
            self,
            x_coordinates: list[float],
            y_coordinates: list[float],
            candidate_positions: tuple[RoutingPoint, ...],
            start_anchor: RoutingNode,
            end_anchor: RoutingNode,
            local_geometry: RoutingConnectionGeometry,
    ) -> tuple[RoutingGraph, int, int]:
        """
        Materialize sparse visibility waypoints as routing nodes.

        :param x_coordinates: Sorted candidate horizontal coordinates.
        :param y_coordinates: Sorted candidate vertical coordinates.
        :param candidate_positions: Sparse visibility waypoint positions.
        :param start_anchor: Local source anchor.
        :param end_anchor: Local destination anchor.
        :param local_geometry: Block obstacles used to discard unusable nodes.
        :return: Sparse visibility graph and endpoint node identifiers.
        """
        search_graph: RoutingGraph = RoutingGraph(source_node_id=1, destination_node_id=2)
        node_ids_by_grid_position: dict[tuple[int, int], int] = dict()
        next_node_id: int = 3
        start_node_id: int = 1
        end_node_id: int = 2
        x_index_by_value: dict[float, int] = dict()
        y_index_by_value: dict[float, int] = dict()
        coordinate_index: int
        coordinate_value: float
        for coordinate_index, coordinate_value in enumerate(x_coordinates):
            x_index_by_value[coordinate_value] = coordinate_index
        for coordinate_index, coordinate_value in enumerate(y_coordinates):
            y_index_by_value[coordinate_value] = coordinate_index
        constraint_engine: RoutingConstraintEngine = RoutingConstraintEngine(graph=search_graph)

        candidate_position: RoutingPoint
        for candidate_position in candidate_positions:
            x_pos: float = candidate_position.get_x()
            y_pos: float = candidate_position.get_y()
            x_index: int | None = x_index_by_value.get(x_pos, None)
            y_index: int | None = y_index_by_value.get(y_pos, None)
            if x_index is None or y_index is None:
                pass
            else:
                is_start: bool = (
                    x_pos == start_anchor.get_position().get_x()
                    and y_pos == start_anchor.get_position().get_y()
                )
                is_end: bool = (
                    x_pos == end_anchor.get_position().get_x()
                    and y_pos == end_anchor.get_position().get_y()
                )
                point_is_blocked: bool = self._point_is_blocked(
                    point=candidate_position,
                    connection_geometry=local_geometry,
                    constraint_engine=constraint_engine,
                )
                if point_is_blocked and not is_start and not is_end:
                    pass
                else:
                    route_node: RoutingNode
                    assigned_node_id: int
                    if is_start:
                        route_node = RoutingNode(
                            node_id=start_node_id,
                            kind=start_anchor.get_kind(),
                            position=candidate_position,
                            port_side=start_anchor.get_port_side(),
                        )
                        assigned_node_id = start_node_id
                    elif is_end:
                        route_node = RoutingNode(
                            node_id=end_node_id,
                            kind=end_anchor.get_kind(),
                            position=candidate_position,
                            port_side=end_anchor.get_port_side(),
                        )
                        assigned_node_id = end_node_id
                    else:
                        route_node = RoutingNode(
                            node_id=next_node_id,
                            kind=RoutingNodeKind.ELBOW,
                            position=candidate_position,
                        )
                        assigned_node_id = next_node_id
                        next_node_id += 1
                    search_graph._add_node(route_node)
                    node_ids_by_grid_position[(x_index, y_index)] = assigned_node_id

        self._build_visibility_segments(
            search_graph=search_graph,
            node_ids_by_grid_position=node_ids_by_grid_position,
            x_coordinate_count=len(x_coordinates),
            y_coordinate_count=len(y_coordinates),
            local_geometry=local_geometry,
        )
        return search_graph, start_node_id, end_node_id

    def _build_visibility_segments(
            self,
            search_graph: RoutingGraph,
            node_ids_by_grid_position: dict[tuple[int, int], int],
            x_coordinate_count: int,
            y_coordinate_count: int,
            local_geometry: RoutingConnectionGeometry,
    ) -> None:
        """
        Connect every waypoint to its nearest visible orthogonal neighbours.

        Block constraints are applied while materializing the graph, so an
        absent edge represents blocked line of sight. Wire crossings remain
        structurally available because strict and relaxed policies reuse the
        same visibility topology in a later step.

        :param search_graph: Sparse waypoint graph under construction.
        :param node_ids_by_grid_position: Coordinate-index waypoint lookup.
        :param x_coordinate_count: Number of relevant x coordinates.
        :param y_coordinate_count: Number of relevant y coordinates.
        :param local_geometry: Block and wire obstacle snapshot.
        :return: None.
        """
        constraint_engine: RoutingConstraintEngine = RoutingConstraintEngine(graph=search_graph)
        next_segment_id: int = 1
        grid_position: tuple[int, int]
        route_node_id: int
        for grid_position, route_node_id in node_ids_by_grid_position.items():
            neighbour_positions: tuple[tuple[int, int], ...] = self._build_neighbour_grid_positions(
                grid_position=grid_position,
                x_coordinate_count=x_coordinate_count,
                y_coordinate_count=y_coordinate_count,
                node_ids_by_grid_position=node_ids_by_grid_position,
            )
            neighbour_position: tuple[int, int]
            for neighbour_position in neighbour_positions:
                neighbour_node_id: int | None = node_ids_by_grid_position.get(neighbour_position, None)
                if neighbour_node_id is None or route_node_id >= neighbour_node_id:
                    pass
                else:
                    visibility_segment: RoutingSegment = RoutingSegment(
                        segment_id=next_segment_id,
                        start_node_id=route_node_id,
                        end_node_id=neighbour_node_id,
                    )
                    if constraint_engine.validate_hard_segment_constraints(
                            segment=visibility_segment,
                            connection_geometry=local_geometry,
                    ):
                        if search_graph._add_segment(visibility_segment):
                            next_segment_id += 1
                        else:
                            pass
                    else:
                        pass

    def _point_is_blocked(
            self,
            point: RoutingPoint,
            connection_geometry: RoutingConnectionGeometry,
            constraint_engine: RoutingConstraintEngine,
    ) -> bool:
        """
        Return whether a candidate point occupies any full block obstacle.

        :param point: Candidate coordinate-grid point.
        :param connection_geometry: Local geometry where owners are full obstacles.
        :param constraint_engine: Engine providing the shared closed-bound rule.
        :return: ``True`` when a block contains or touches the point.
        """
        block_geometry: RoutingBlockGeometry
        for block_geometry in connection_geometry.get_other_blocks():
            if constraint_engine.is_point_inside_foreign_block(
                    point=point,
                    block_bounds=block_geometry.get_bounds(),
            ):
                return True
            else:
                pass
        return False

    def _run_lexicographic_search(
            self,
            search_graph: RoutingGraph,
            start_node_id: int,
            end_node_id: int,
            crossing_count_by_segment_id: dict[int, int],
            routing_policy: AutomaticRoutingPolicy,
    ) -> list[int] | None:
        """
        Run Dijkstra using ``(crossings, bends, length)`` tuple ordering.

        Python compares tuples lexicographically. Consequently, no reduction
        in bends or length can compensate for one additional crossing, and no
        reduction in length can compensate for one additional bend.

        :param search_graph: Candidate-node graph used for geometry queries.
        :param start_node_id: Search source node identifier.
        :param end_node_id: Search destination node identifier.
        :param crossing_count_by_segment_id: Cached foreign-wire crossings.
        :param routing_policy: Strict or crossing-permitted search policy.
        :return: Ordered path node identifiers or ``None``.
        """
        start_state: tuple[int, int] = (start_node_id, 0)
        initial_cost: tuple[int, int, float] = (0, 0, 0.0)
        distances: dict[tuple[int, int], tuple[int, int, float]] = dict(((start_state, initial_cost),))
        previous_states: dict[tuple[int, int], tuple[int, int] | None] = dict(((start_state, None),))
        queue: list[tuple[int, int, float, int, int]] = list(((0, 0, 0.0, start_node_id, 0),))
        final_state: tuple[int, int] | None = None

        while len(queue) > 0 and final_state is None:
            current_crossing_count: int
            current_bend_count: int
            current_length: float
            current_node_id: int
            previous_axis_code: int
            current_crossing_count, current_bend_count, current_length, current_node_id, previous_axis_code = (
                heapq.heappop(queue)
            )
            current_state: tuple[int, int] = (current_node_id, previous_axis_code)
            current_cost: tuple[int, int, float] = (
                current_crossing_count,
                current_bend_count,
                current_length,
            )
            # The heap and distance lookup store the same ordered tuple. This
            # keeps Dijkstra's stale-entry check consistent with relaxation and
            # avoids converting priorities into an imprecise scalar penalty.
            known_cost: tuple[int, int, float] | None = distances.get(current_state, None)
            if known_cost is None or current_cost > known_cost:
                pass
            elif current_node_id == end_node_id:
                final_state = current_state
            else:
                adjacent_segment: RoutingSegment
                for adjacent_segment in search_graph.adjacent_segments(current_node_id):
                    if adjacent_segment.get_start_node_id() == current_node_id:
                        neighbour_node_id: int = adjacent_segment.get_end_node_id()
                    else:
                        neighbour_node_id = adjacent_segment.get_start_node_id()
                    self._relax_search_edge(
                        search_graph=search_graph,
                        route_segment=adjacent_segment,
                        current_node_id=current_node_id,
                        neighbour_node_id=neighbour_node_id,
                        previous_axis_code=previous_axis_code,
                        current_cost=current_cost,
                        crossing_count_by_segment_id=crossing_count_by_segment_id,
                        routing_policy=routing_policy,
                        distances=distances,
                        previous_states=previous_states,
                        queue=queue,
                    )

        if final_state is None:
            return None
        else:
            return self._reconstruct_search_path(
                final_state=final_state,
                previous_states=previous_states,
            )

    def _build_neighbour_grid_positions(
            self,
            grid_position: tuple[int, int],
            x_coordinate_count: int,
            y_coordinate_count: int,
            node_ids_by_grid_position: dict[tuple[int, int], int],
    ) -> tuple[tuple[int, int], ...]:
        """
        Return existing immediate orthogonal neighbours of one grid position.

        :param grid_position: Current x/y grid indexes.
        :param x_coordinate_count: Number of x coordinate lines.
        :param y_coordinate_count: Number of y coordinate lines.
        :param node_ids_by_grid_position: Existing non-blocked grid nodes.
        :return: Immutable sequence of adjacent grid positions.
        """
        x_index: int = grid_position[0]
        y_index: int = grid_position[1]
        neighbour_positions: list[tuple[int, int]] = list()
        candidate_x_index: int = x_index - 1
        while candidate_x_index >= 0 and (candidate_x_index, y_index) not in node_ids_by_grid_position:
            candidate_x_index -= 1
        if candidate_x_index >= 0:
            neighbour_positions.append((candidate_x_index, y_index))
        else:
            pass
        candidate_x_index = x_index + 1
        while (candidate_x_index < x_coordinate_count
               and (candidate_x_index, y_index) not in node_ids_by_grid_position):
            candidate_x_index += 1
        if candidate_x_index < x_coordinate_count:
            neighbour_positions.append((candidate_x_index, y_index))
        else:
            pass
        candidate_y_index: int = y_index - 1
        while candidate_y_index >= 0 and (x_index, candidate_y_index) not in node_ids_by_grid_position:
            candidate_y_index -= 1
        if candidate_y_index >= 0:
            neighbour_positions.append((x_index, candidate_y_index))
        else:
            pass
        candidate_y_index = y_index + 1
        while (candidate_y_index < y_coordinate_count
               and (x_index, candidate_y_index) not in node_ids_by_grid_position):
            candidate_y_index += 1
        if candidate_y_index < y_coordinate_count:
            neighbour_positions.append((x_index, candidate_y_index))
        else:
            pass
        return tuple(neighbour_positions)

    def _relax_search_edge(
            self,
            search_graph: RoutingGraph,
            route_segment: RoutingSegment,
            current_node_id: int,
            neighbour_node_id: int,
            previous_axis_code: int,
            current_cost: tuple[int, int, float],
            crossing_count_by_segment_id: dict[int, int],
            routing_policy: AutomaticRoutingPolicy,
            distances: dict[tuple[int, int], tuple[int, int, float]],
            previous_states: dict[tuple[int, int], tuple[int, int] | None],
            queue: list[tuple[int, int, float, int, int]],
    ) -> None:
        """
        Validate and relax one candidate Dijkstra edge.

        :param search_graph: Candidate-node graph.
        :param route_segment: Materialized visibility segment being traversed.
        :param current_node_id: Current search node identifier.
        :param neighbour_node_id: Candidate neighbour identifier.
        :param previous_axis_code: Axis code used to reach the current node.
        :param current_cost: Accumulated crossings, bends and length.
        :param crossing_count_by_segment_id: Cached foreign-wire crossings.
        :param routing_policy: Strict or crossing-permitted policy.
        :param distances: Mutable best-cost lookup.
        :param previous_states: Mutable predecessor lookup.
        :param queue: Mutable Dijkstra priority queue.
        :return: None.
        """
        current_node: RoutingNode | None = search_graph.get_node(current_node_id)
        neighbour_node: RoutingNode | None = search_graph.get_node(neighbour_node_id)
        if current_node is None or neighbour_node is None:
            return
        else:
            pass

        added_crossing_count: int | None = crossing_count_by_segment_id.get(
            route_segment.get_segment_id(),
            None,
        )
        if added_crossing_count is None:
            return
        elif (routing_policy == AutomaticRoutingPolicy.STRICT
              and added_crossing_count > 0):
            return
        else:
            pass

        segment_axis: RoutingAxis | None = search_graph.get_geometry().derive_axis(
            start_x=current_node.get_position().get_x(),
            start_y=current_node.get_position().get_y(),
            end_x=neighbour_node.get_position().get_x(),
            end_y=neighbour_node.get_position().get_y(),
        )
        if segment_axis == RoutingAxis.HORIZONTAL:
            axis_code: int = 1
        elif segment_axis == RoutingAxis.VERTICAL:
            axis_code = 2
        else:
            return

        segment_length: float = abs(
            current_node.get_position().get_x() - neighbour_node.get_position().get_x()
        ) + abs(
            current_node.get_position().get_y() - neighbour_node.get_position().get_y()
        )
        added_bend_count: int
        if previous_axis_code == 0 or previous_axis_code == axis_code:
            added_bend_count = 0
        else:
            added_bend_count = 1
        # Tuple comparison is the routing policy: crossings have absolute
        # priority, then bends, while length only breaks equal structural costs.
        candidate_cost: tuple[int, int, float] = (
            current_cost[0] + added_crossing_count,
            current_cost[1] + added_bend_count,
            current_cost[2] + segment_length,
        )
        neighbour_state: tuple[int, int] = (neighbour_node_id, axis_code)
        existing_cost: tuple[int, int, float] | None = distances.get(neighbour_state, None)
        if existing_cost is None or candidate_cost < existing_cost:
            distances[neighbour_state] = candidate_cost
            previous_states[neighbour_state] = (current_node_id, previous_axis_code)
            heapq.heappush(
                queue,
                (
                    candidate_cost[0],
                    candidate_cost[1],
                    candidate_cost[2],
                    neighbour_node_id,
                    axis_code,
                ),
            )
        else:
            pass

    def _reconstruct_search_path(
            self,
            final_state: tuple[int, int],
            previous_states: dict[tuple[int, int], tuple[int, int] | None],
    ) -> list[int]:
        """
        Reconstruct ordered node identifiers from Dijkstra predecessors.

        :param final_state: Reached destination state.
        :param previous_states: Search predecessor lookup.
        :return: Ordered search node identifiers.
        """
        reversed_node_ids: list[int] = list()
        current_state: tuple[int, int] | None = final_state
        while current_state is not None:
            reversed_node_ids.append(current_state[0])
            current_state = previous_states.get(current_state, None)
        reversed_node_ids.reverse()
        return reversed_node_ids

    def _compress_collinear_points(self, path_points: list[RoutingPoint]) -> list[RoutingPoint]:
        """
        Remove intermediate points that do not create an orthogonal bend.

        :param path_points: Ordered points returned by the coordinate search.
        :return: Minimal point sequence with identical visible geometry.
        """
        if len(path_points) <= 2:
            return path_points
        else:
            compressed_points: list[RoutingPoint] = list((path_points[0].copy(),))

        point_index: int
        for point_index in range(1, len(path_points) - 1):
            previous_point: RoutingPoint = compressed_points[-1]
            current_point: RoutingPoint = path_points[point_index]
            next_point: RoutingPoint = path_points[point_index + 1]
            first_axis: RoutingAxis | None = self._graph.get_geometry().derive_axis(
                start_x=previous_point.get_x(),
                start_y=previous_point.get_y(),
                end_x=current_point.get_x(),
                end_y=current_point.get_y(),
            )
            second_axis: RoutingAxis | None = self._graph.get_geometry().derive_axis(
                start_x=current_point.get_x(),
                start_y=current_point.get_y(),
                end_x=next_point.get_x(),
                end_y=next_point.get_y(),
            )
            if first_axis == second_axis:
                pass
            else:
                compressed_points.append(current_point.copy())
        compressed_points.append(path_points[-1].copy())
        return compressed_points

    def _splice_replacement_points(
            self,
            ordered_nodes: list[RoutingNode],
            first_conflict_index: int,
            last_conflict_index: int,
            replacement_points: list[RoutingPoint],
    ) -> RoutingGraph | None:
        """
        Replace one conflicting interval while preserving both route ends.

        :param ordered_nodes: Original nodes ordered from source to destination.
        :param first_conflict_index: First conflicting segment index.
        :param last_conflict_index: Last conflicting segment index.
        :param replacement_points: New point chain including both anchors.
        :return: Rebuilt candidate graph or ``None`` for malformed input.
        """
        if len(replacement_points) < 2:
            return None
        else:
            pass

        prefix_nodes: list[RoutingNode] = ordered_nodes[:first_conflict_index + 1]
        suffix_nodes: list[RoutingNode] = ordered_nodes[last_conflict_index + 1:]
        if len(prefix_nodes) == 0 or len(suffix_nodes) == 0:
            return None
        else:
            pass

        candidate_graph: RoutingGraph = RoutingGraph(
            source_node_id=self._graph.get_source_node_id(),
            destination_node_id=self._graph.get_destination_node_id(),
        )
        rebuilt_nodes: list[RoutingNode] = list()
        preserved_node: RoutingNode
        for preserved_node in prefix_nodes:
            rebuilt_nodes.append(preserved_node.clone())

        existing_node_ids: list[int] = list(
            route_node.get_node_id() for route_node in self._graph.get_nodes()
        )
        next_node_id: int = max(existing_node_ids) + 1
        replacement_index: int
        for replacement_index in range(1, len(replacement_points) - 1):
            node_kind: RoutingNodeKind = RoutingNodeKind.ELBOW
            if first_conflict_index == 0 and replacement_index == 1:
                node_kind = RoutingNodeKind.STUB
            elif last_conflict_index == len(ordered_nodes) - 2 and replacement_index == len(replacement_points) - 2:
                node_kind = RoutingNodeKind.STUB
            else:
                pass
            rebuilt_nodes.append(
                RoutingNode(
                    node_id=next_node_id,
                    kind=node_kind,
                    position=replacement_points[replacement_index].copy(),
                )
            )
            next_node_id += 1

        for preserved_node in suffix_nodes:
            rebuilt_nodes.append(preserved_node.clone())

        rebuilt_node: RoutingNode
        for rebuilt_node in rebuilt_nodes:
            if candidate_graph._add_node(rebuilt_node):
                pass
            else:
                return None

        node_index: int
        for node_index in range(len(rebuilt_nodes) - 1):
            route_segment: RoutingSegment = RoutingSegment(
                segment_id=node_index + 1,
                start_node_id=rebuilt_nodes[node_index].get_node_id(),
                end_node_id=rebuilt_nodes[node_index + 1].get_node_id(),
            )
            if candidate_graph._add_segment(route_segment):
                pass
            else:
                return None
        return candidate_graph

    def _is_graph_valid(
            self,
            graph: RoutingGraph,
            routing_policy: AutomaticRoutingPolicy,
    ) -> bool:
        """
        Validate one complete candidate through graph and constraint APIs.

        :param graph: Candidate graph to inspect.
        :param routing_policy: Policy used to build the candidate.
        :return: ``True`` when topology and every active constraint are valid.
        """
        if not graph.validate().is_valid():
            return False
        else:
            pass

        route_segment: RoutingSegment
        constraint_engine: RoutingConstraintEngine = RoutingConstraintEngine(graph=graph)
        for route_segment in graph.get_segments():
            if constraint_engine.segment_has_invalid_own_route_intersection(segment=route_segment):
                return False
            elif self._is_segment_valid(
                    graph=graph,
                    segment=route_segment,
                    connection_geometry=self._connection_geometry,
                    routing_policy=routing_policy,
            ):
                pass
            else:
                return False
        return True

    def _is_segment_valid(
            self,
            graph: RoutingGraph,
            segment: RoutingSegment,
            connection_geometry: RoutingConnectionGeometry,
            routing_policy: AutomaticRoutingPolicy,
    ) -> bool:
        """
        Validate one segment with port-specific composition when required.

        :param graph: Graph that owns the segment and endpoint roles.
        :param segment: Segment to validate.
        :param connection_geometry: Point-in-time obstacle geometry.
        :param routing_policy: Strict or crossing-penalized policy.
        :return: ``True`` when the segment satisfies the selected policy.
        """
        start_node: RoutingNode | None = graph.get_node(segment.get_start_node_id())
        end_node: RoutingNode | None = graph.get_node(segment.get_end_node_id())
        if start_node is None or end_node is None:
            return False
        else:
            constraint_engine: RoutingConstraintEngine = RoutingConstraintEngine(graph=graph)

        if start_node.get_kind() == RoutingNodeKind.PORT:
            owner_bounds: RoutingBounds | None = self._get_owner_bounds(
                graph=graph,
                port_node=start_node,
                connection_geometry=connection_geometry,
            )
            return constraint_engine.validate_connection(
                port_node=start_node,
                neighbour_node=end_node,
                segment=segment,
                block_bounds=owner_bounds,
                connection_geometry=connection_geometry,
                routing_policy=routing_policy,
            )
        elif end_node.get_kind() == RoutingNodeKind.PORT:
            owner_bounds = self._get_owner_bounds(
                graph=graph,
                port_node=end_node,
                connection_geometry=connection_geometry,
            )
            return constraint_engine.validate_connection(
                port_node=end_node,
                neighbour_node=start_node,
                segment=segment,
                block_bounds=owner_bounds,
                connection_geometry=connection_geometry,
                routing_policy=routing_policy,
            )
        else:
            return constraint_engine.validate_segment(
                segment=segment,
                connection_geometry=connection_geometry,
                routing_policy=routing_policy,
            )

    def _get_owner_bounds(
            self,
            graph: RoutingGraph,
            port_node: RoutingNode,
            connection_geometry: RoutingConnectionGeometry,
    ) -> RoutingBounds | None:
        """
        Return owner bounds matching one graph endpoint role.

        :param graph: Graph whose source and destination roles must be resolved.
        :param port_node: Port endpoint being validated.
        :param connection_geometry: Geometry containing both endpoint owners.
        :return: Matching owner bounds or ``None``.
        """
        if port_node.get_node_id() == graph.get_source_node_id():
            source_owner: RoutingBlockGeometry | None = connection_geometry.get_source_owner()
            if source_owner is not None:
                return source_owner.get_bounds()
            else:
                return None
        elif port_node.get_node_id() == graph.get_destination_node_id():
            destination_owner: RoutingBlockGeometry | None = connection_geometry.get_destination_owner()
            if destination_owner is not None:
                return destination_owner.get_bounds()
            else:
                return None
        else:
            return None
