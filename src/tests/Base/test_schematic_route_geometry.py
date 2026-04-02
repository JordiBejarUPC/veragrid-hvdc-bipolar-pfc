from PySide6.QtCore import QPointF

from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import (get_opposite_attachment_side,
                                                                                           get_rect_side_anchor)
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.route_geometry import (merge_route_with_endpoints,
                                                                           move_orthogonal_route_segment,
                                                                           move_orthogonal_route_vertex,
                                                                           normalize_route_points,
                                                                           sample_route_segment)


def test_normalize_route_points_casts_to_float():
    assert normalize_route_points([(1, 2), (3.5, 4)]) == [(1.0, 2.0), (3.5, 4.0)]


def test_merge_route_with_endpoints_preserves_interior_elbows():
    merged = merge_route_with_endpoints(start=(0, 0),
                                        end=(100, 100),
                                        persisted_points=[(10, 20), (10, 40), (70, 40), (90, 90)])

    assert merged == [(0.0, 0.0), (10.0, 40.0), (70.0, 40.0), (100.0, 100.0)]


def test_merge_route_with_endpoints_preserves_orthogonality_with_side_hints():
    merged = merge_route_with_endpoints(start=(20, 0),
                                        end=(120, 120),
                                        persisted_points=[(0, 0), (0, 80), (120, 80), (120, 100)],
                                        start_side="bottom",
                                        end_side="top")

    assert merged == [(20.0, 0.0), (20.0, 80.0), (120.0, 80.0), (120.0, 120.0)]


def test_merge_route_with_endpoints_falls_back_to_straight_line():
    merged = merge_route_with_endpoints(start=(5, 6), end=(7, 8), persisted_points=[])

    assert merged == [(5.0, 6.0), (7.0, 8.0)]


def test_sample_route_segment_follows_path_length():
    point, segment = sample_route_segment([(0, 0), (0, 10), (20, 10)], 0.75)

    assert point == (12.5, 10.0)
    assert segment == ((0.0, 10.0), (20.0, 10.0))


def test_sample_route_segment_clamps_out_of_range_positions():
    point, segment = sample_route_segment([(0, 0), (0, 10), (20, 10)], 5.0)

    assert point == (20.0, 10.0)
    assert segment == ((0.0, 10.0), (20.0, 10.0))


def test_move_orthogonal_route_segment_moves_middle_horizontal_segment():
    moved = move_orthogonal_route_segment(points=[(10.0, 20.0), (10.0, 80.0), (110.0, 80.0), (110.0, 40.0)],
                                          segment_index=1,
                                          delta_x=0.0,
                                          delta_y=15.0)

    assert moved == [(10.0, 20.0), (10.0, 95.0), (110.0, 95.0), (110.0, 40.0)]


def test_move_orthogonal_route_segment_ignores_endpoint_segments():
    moved = move_orthogonal_route_segment(points=[(10.0, 20.0), (10.0, 80.0), (110.0, 80.0), (110.0, 40.0)],
                                          segment_index=0,
                                          delta_x=25.0,
                                          delta_y=0.0)

    assert moved == [(10.0, 20.0), (10.0, 80.0), (110.0, 80.0), (110.0, 40.0)]


def test_move_orthogonal_route_vertex_moves_adjacent_segments() -> None:
    moved = move_orthogonal_route_vertex(points=[(10.0, 20.0), (10.0, 80.0), (110.0, 80.0), (110.0, 40.0)],
                                         vertex_index=2,
                                         new_x=140.0,
                                         new_y=95.0)

    assert moved == [(10.0, 20.0), (10.0, 95.0), (110.0, 95.0), (110.0, 40.0)]


def test_move_orthogonal_route_vertex_keeps_endpoint_anchor_fixed() -> None:
    moved = move_orthogonal_route_vertex(points=[(10.0, 20.0), (10.0, 80.0), (110.0, 80.0), (110.0, 40.0)],
                                         vertex_index=1,
                                         new_x=60.0,
                                         new_y=95.0)

    assert moved == [(10.0, 20.0), (10.0, 95.0), (110.0, 95.0), (110.0, 40.0)]


def test_get_opposite_attachment_side_matches_expected_pairs() -> None:
    assert get_opposite_attachment_side("top") == "bottom"
    assert get_opposite_attachment_side("bottom") == "top"
    assert get_opposite_attachment_side("left") == "right"
    assert get_opposite_attachment_side("right") == "left"


def test_get_rect_side_anchor_uses_alignment_on_selected_side() -> None:
    assert get_rect_side_anchor(origin=QPointF(10.0, 20.0),
                                width=80.0,
                                height=40.0,
                                side="top",
                                alignment=0.25) == QPointF(30.0, 20.0)
    assert get_rect_side_anchor(origin=QPointF(10.0, 20.0),
                                width=80.0,
                                height=40.0,
                                side="right",
                                alignment=0.75) == QPointF(90.0, 50.0)
