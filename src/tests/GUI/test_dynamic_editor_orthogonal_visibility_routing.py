from __future__ import annotations

from VeraGrid.Gui.DynamicModelEditor.Routing.route_builder import (
    OrthogonalVisibilityRouteBuilder,
)
from VeraGrid.Gui.DynamicModelEditor.Routing.routing_elements import RoutingPoint


def _build_visibility_route(
        obstacle_rects: list[tuple[float, float, float, float]],
        reserved_segments: list[tuple[RoutingPoint, RoutingPoint]],
        channel_segments: list[tuple[RoutingPoint, RoutingPoint]],
) -> list[RoutingPoint]:
    """Build one left-to-right route with the shared test geometry.

    :param obstacle_rects: Rectangles as ``left, top, right, bottom``.
    :param reserved_segments: Segments that the route must not collide with.
    :param channel_segments: Existing cables that induce parallel lanes.
    :return: Accepted route point chain.
    """
    route_builder: OrthogonalVisibilityRouteBuilder = OrthogonalVisibilityRouteBuilder(
        source_point=RoutingPoint(0.0, 0.0),
        target_point=RoutingPoint(100.0, 0.0),
        obstacle_rects=obstacle_rects,
        reserved_segments=reserved_segments,
        channel_segments=channel_segments,
        scene_bounds=(-20.0, -60.0, 120.0, 60.0),
        source_stub_length=20.0,
        target_stub_length=20.0,
        channel_separation=10.0,
        bend_penalty=36.0,
        max_search_states=4096,
    )
    route_points: list[RoutingPoint] | None = route_builder.build()
    assert route_points is not None
    return route_points


def _assert_route_is_orthogonal(route_points: list[RoutingPoint]) -> None:
    """Assert that every consecutive route pair shares one coordinate.

    :param route_points: Route point chain to validate.
    :return: None.
    """
    point_index: int
    for point_index in range(len(route_points) - 1):
        start_point: RoutingPoint = route_points[point_index]
        end_point: RoutingPoint = route_points[point_index + 1]
        shares_x: bool = abs(start_point.get_x() - end_point.get_x()) <= 1e-6
        shares_y: bool = abs(start_point.get_y() - end_point.get_y()) <= 1e-6
        assert shares_x or shares_y


def test_visibility_route_avoids_intermediate_obstacle() -> None:
    """Route around an expanded block instead of passing through its body."""
    route_points: list[RoutingPoint] = _build_visibility_route(
        obstacle_rects=list(((40.0, -20.0, 60.0, 20.0),)),
        reserved_segments=list(),
        channel_segments=list(),
    )
    _assert_route_is_orthogonal(route_points)
    assert any(abs(route_point.get_y()) >= 20.0 for route_point in route_points)


def test_visibility_route_separates_reserved_parallel_cable() -> None:
    """Use an induced parallel lane instead of sharing an accepted segment."""
    reserved_segments: list[tuple[RoutingPoint, RoutingPoint]] = list((
        (RoutingPoint(20.0, 0.0), RoutingPoint(80.0, 0.0)),
    ))
    route_points: list[RoutingPoint] = _build_visibility_route(
        obstacle_rects=list(),
        reserved_segments=reserved_segments,
        channel_segments=reserved_segments,
    )
    _assert_route_is_orthogonal(route_points)
    assert any(abs(route_point.get_y()) >= 10.0 for route_point in route_points)


def test_visibility_route_does_not_create_implicit_t_junction() -> None:
    """Avoid ending a grid segment on the interior of an accepted cable."""
    route_builder: OrthogonalVisibilityRouteBuilder = OrthogonalVisibilityRouteBuilder(
        source_point=RoutingPoint(0.0, 0.0),
        target_point=RoutingPoint(100.0, 0.0),
        obstacle_rects=list(),
        reserved_segments=list((
            (RoutingPoint(50.0, -30.0), RoutingPoint(50.0, 30.0)),
        )),
        channel_segments=list(),
        scene_bounds=(-20.0, -60.0, 120.0, 60.0),
        source_stub_length=20.0,
        target_stub_length=20.0,
        channel_separation=10.0,
        bend_penalty=36.0,
        max_search_states=4096,
    )
    assert route_builder._point_is_on_reserved_segment_interior(
        RoutingPoint(50.0, 0.0)
    )
