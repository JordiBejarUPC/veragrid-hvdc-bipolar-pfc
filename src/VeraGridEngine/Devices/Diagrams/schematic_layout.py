#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Dict, Iterable, List, Tuple

from VeraGridEngine.Devices.Diagrams.graphic_location import GraphicLocation

SCHEMATIC_LAYOUT_SCHEMA_VERSION = 1


class SchematicBranchEndpoint(Enum):
    """
    Enumerate the supported branch endpoint identifiers.
    """
    FROM = "from"
    TO = "to"


class SchematicAttachmentSide(Enum):
    """
    Enumerate the supported compatibility attachment sides.
    """
    DEFAULT = "default"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


class SchematicAttachmentOwnerKind(Enum):
    """
    Enumerate the supported owner kinds used in explicit slot keys.
    """
    BUS = "bus"
    FLUID = "fluid"


class SchematicRouteRecord:
    """
    Store one typed route record for runtime behavior.
    """
    __slots__ = ("points", "kind", "locked")

    def __init__(self,
                 points: List[Tuple[float, float]] | None = None,
                 kind: SchematicRouteKind | None = None,
                 locked: bool = False) -> None:
        """
        Initialize one route record.

        :param points: Route polyline points.
        :param kind: Route kind enum.
        :param locked: Locked-state flag.
        """
        self.points: List[Tuple[float, float]] = list() if points is None else list(points)
        self.kind: SchematicRouteKind | None = kind
        self.locked: bool = bool(locked)


class SchematicAttachmentRecord:
    """
    Store one typed attachment record for runtime behavior.
    """
    __slots__ = (
        "owner_device_id",
        "owner_device_type",
        "anchor_x",
        "anchor_y",
        "anchor_auto",
        "side",
        "slot_key",
        "terminal_key",
        "order",
        "auto_slot",
    )

    def __init__(self) -> None:
        """
        Initialize one attachment record with explicit defaults.
        """
        self.owner_device_id: str = ""
        self.owner_device_type: str = ""
        self.anchor_x: float | None = None
        self.anchor_y: float | None = None
        self.anchor_auto: bool = True
        self.side: SchematicAttachmentSide | None = None
        self.slot_key: str | None = None
        self.terminal_key: str | None = None
        self.order: int | None = None
        self.auto_slot: bool = True


class SchematicDockRecord:
    """
    Store one typed dock record for runtime behavior.
    """
    __slots__ = (
        "owner_device_id",
        "owner_device_type",
        "side",
        "offset",
        "order",
    )

    def __init__(self) -> None:
        """
        Initialize one dock record with explicit defaults.
        """
        self.owner_device_id: str = ""
        self.owner_device_type: str = ""
        self.side: SchematicAttachmentSide | None = None
        self.offset: float = 0.0
        self.order: int | None = None


class SchematicRouteKind(Enum):
    """
    Enumerate the supported persisted route kinds.
    """
    ORTHOGONAL = "orthogonal"
    AUTO = "auto"
    AUTO_ORTHOGONAL = "auto-orthogonal"
    AUTO_POLYLINE = "auto-polyline"
    MANUAL_ORTHOGONAL = "manual-orthogonal"
    MANUAL_POLYLINE = "manual-polyline"


def parse_schematic_branch_endpoint(endpoint: SchematicBranchEndpoint | str) -> SchematicBranchEndpoint | None:
    """
    Parse one branch endpoint value from runtime or persisted data.

    :param endpoint: Runtime enum or persisted string.
    :return: Parsed endpoint enum or ``None`` when absent/unknown.
    """
    if isinstance(endpoint, SchematicBranchEndpoint):
        return endpoint
    else:
        endpoint_text: str = str(endpoint)

    endpoint_value: SchematicBranchEndpoint

    for endpoint_value in SchematicBranchEndpoint:
        if endpoint_value.value == endpoint_text:
            return endpoint_value
        else:
            pass

    return None


def parse_schematic_attachment_side(side: SchematicAttachmentSide | str | None) -> SchematicAttachmentSide | None:
    """
    Parse one attachment side value from runtime or persisted data.

    :param side: Runtime enum or persisted string.
    :return: Parsed side enum or ``None`` when absent/unknown.
    """
    if isinstance(side, SchematicAttachmentSide):
        return side
    elif side is None:
        return None
    else:
        side_text: str = str(side)

    side_value: SchematicAttachmentSide

    for side_value in SchematicAttachmentSide:
        if side_value.value == side_text:
            return side_value
        else:
            pass

    return None


def serialize_schematic_attachment_side(side: SchematicAttachmentSide | str | None,
                                        default_side: SchematicAttachmentSide) -> str:
    """
    Serialize one attachment side to the persisted string representation.

    :param side: Runtime enum or persisted string.
    :param default_side: Default side when ``side`` is absent or invalid.
    :return: Persisted side string.
    """
    parsed_side: SchematicAttachmentSide | None = parse_schematic_attachment_side(side=side)

    if parsed_side is None:
        return default_side.value
    else:
        return parsed_side.value


def parse_schematic_route_kind(kind: SchematicRouteKind | str | None) -> SchematicRouteKind | None:
    """
    Parse one route kind value from runtime or persisted data.

    :param kind: Runtime enum or persisted string.
    :return: Parsed route kind or ``None`` when absent/unknown.
    """
    if isinstance(kind, SchematicRouteKind):
        return kind
    elif kind is None:
        return None
    else:
        pass

    kind_text: str = str(kind)
    route_kind: SchematicRouteKind

    for route_kind in SchematicRouteKind:
        if route_kind.value == kind_text:
            return route_kind
        else:
            pass

    return None


def serialize_schematic_route_kind(kind: SchematicRouteKind | str | None,
                                   default_kind: SchematicRouteKind) -> str:
    """
    Serialize one route kind to the persisted string representation.

    :param kind: Runtime enum or persisted string.
    :param default_kind: Default route kind when ``kind`` is absent or invalid.
    :return: Persisted route kind string.
    """
    parsed_kind: SchematicRouteKind | None = parse_schematic_route_kind(kind)

    if parsed_kind is None:
        return default_kind.value
    else:
        return parsed_kind.value


def _normalize_points(points: Iterable[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Normalize persisted route points to plain numeric tuples.
    """
    normalized: List[Tuple[float, float]] = list()

    for point in points:
        if len(point) != 2:
            raise ValueError(f"Expected 2D route point, got {point!r}")

        normalized.append((float(point[0]), float(point[1])))

    return normalized


def ensure_layout_metadata(location: GraphicLocation) -> Dict[str, Any]:
    """
    Ensure the schematic metadata envelope exists and carries a schema version.
    """
    if location.layout_metadata is None:
        location.layout_metadata = dict()

    if "schema_version" not in location.layout_metadata:
        location.layout_metadata["schema_version"] = SCHEMATIC_LAYOUT_SCHEMA_VERSION

    return location.layout_metadata


def copy_layout_metadata(location: GraphicLocation) -> Dict[str, Any]:
    """
    Return a defensive copy of the schematic metadata envelope.
    """
    return deepcopy(ensure_layout_metadata(location))


def get_layout_section(location: GraphicLocation, section: str, default: Any = None) -> Any:
    """
    Return a copied layout metadata section so callers do not mutate persistence by accident.
    """
    metadata = ensure_layout_metadata(location)
    value = metadata.get(section, default)
    return deepcopy(value)


def set_layout_section(location: GraphicLocation, section: str, value: Any) -> Dict[str, Any]:
    """
    Replace a layout metadata section with a defensive copy.
    """
    metadata = ensure_layout_metadata(location)
    metadata[section] = deepcopy(value)
    return metadata


def get_branch_route_points(location: GraphicLocation) -> List[Tuple[float, float]]:
    """
    Return branch route points, preferring structured route metadata but falling back to legacy polyline storage.
    """
    route = get_layout_section(location, "route", default=dict()) or dict()
    points = route.get("points")

    if points:
        return _normalize_points(points)

    return _normalize_points(location.poly_line)


def get_branch_route_record(location: GraphicLocation) -> SchematicRouteRecord | None:
    """
    Return one typed route record from persisted metadata.

    :param location: Graphic location record.
    :return: Typed route record or ``None`` when the structured route section is absent.
    """
    route_section: Any = get_layout_section(location, "route", default=None)

    if not isinstance(route_section, dict):
        return None
    else:
        pass

    route_record: SchematicRouteRecord = SchematicRouteRecord()
    points: Any = route_section.get("points", list())
    route_record.points = _normalize_points(points) if points else list()
    route_record.kind = parse_schematic_route_kind(route_section.get("kind", None))
    route_record.locked = bool(route_section.get("locked", False))
    return route_record


def set_branch_route_record(location: GraphicLocation,
                            route_record: SchematicRouteRecord) -> Dict[str, Any]:
    """
    Persist one typed route record while preserving the persisted schema.

    :param location: Graphic location record.
    :param route_record: Typed route record.
    :return: Updated layout metadata.
    """
    route_section: Dict[str, Any] = get_layout_section(location, "route", default=dict()) or dict()
    normalized_points: List[Tuple[float, float]] = _normalize_points(route_record.points)

    # Keep legacy polyline storage synchronized with the structured route section.
    location.poly_line = list(normalized_points)
    route_section["points"] = list(normalized_points)
    route_section["kind"] = serialize_schematic_route_kind(kind=route_record.kind,
                                                           default_kind=SchematicRouteKind.AUTO_POLYLINE)
    route_section["locked"] = bool(route_record.locked)
    return set_layout_section(location, "route", route_section)


def set_branch_route_points(location: GraphicLocation,
                            points: Iterable[Tuple[float, float]],
                            kind: SchematicRouteKind | str | None = SchematicRouteKind.AUTO_POLYLINE,
                            locked: bool | None = False) -> Dict[str, Any]:
    """
    Persist route points in both the legacy polyline field and the structured layout metadata.
    """
    route_record: SchematicRouteRecord | None = get_branch_route_record(location=location)
    normalized_points: List[Tuple[float, float]] = _normalize_points(points)

    if route_record is None:
        route_record = SchematicRouteRecord()
    else:
        pass

    # Update the typed route state first so the persistence conversion stays in one place.
    route_record.points = list(normalized_points)

    if kind is None:
        route_record.kind = parse_schematic_route_kind(route_record.kind)
    else:
        route_record.kind = parse_schematic_route_kind(kind)

    if locked is None:
        route_record.locked = bool(route_record.locked)
    else:
        route_record.locked = bool(locked)

    return set_branch_route_record(location=location, route_record=route_record)


def compress_route_points(points: Iterable[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Remove redundant route points while preserving orthogonal elbows.

    :param points: Route points.
    :return: Normalized route points without duplicates or collinear interior points.
    """
    normalized_points = _normalize_points(points)
    compressed_points: List[Tuple[float, float]] = list()
    point: Tuple[float, float]

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

    simplified_points: List[Tuple[float, float]] = [compressed_points[0]]
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


def build_route_stub_point(point: Tuple[float, float], side: str, stub_length: float) -> Tuple[float, float]:
    """
    Build the first orthogonal stub point that leaves a node from one side.

    :param point: Endpoint point.
    :param side: Attachment side.
    :param stub_length: Stub length.
    :return: Stub point.
    """
    if side == "left":
        return point[0] - stub_length, point[1]
    elif side == "right":
        return point[0] + stub_length, point[1]
    elif side == "top":
        return point[0], point[1] - stub_length
    else:
        return point[0], point[1] + stub_length


def get_default_route_lane_index(start_order: int | None, end_order: int | None) -> int:
    """
    Build a deterministic lane index from endpoint slot orders.

    :param start_order: Start slot order.
    :param end_order: End slot order.
    :return: One-based lane index.
    """
    orders: List[int] = list()

    if isinstance(start_order, int) and start_order > 0:
        orders.append(start_order)
    else:
        pass

    if isinstance(end_order, int) and end_order > 0:
        orders.append(end_order)
    else:
        pass

    if len(orders) == 0:
        return 1
    elif len(orders) == 1:
        return min(4, orders[0])
    else:
        return min(4, max(1, int(round((orders[0] + orders[1]) * 0.5))))


def is_axis_aligned_route_segment(start: Tuple[float, float], end: Tuple[float, float]) -> bool:
    """
    Determine whether one route segment is orthogonal.

    :param start: Segment start point.
    :param end: Segment end point.
    :return: ``True`` when the segment is horizontal or vertical.
    """
    return float(start[0]) == float(end[0]) or float(start[1]) == float(end[1])


def is_orthogonal_route(points: Iterable[Tuple[float, float]]) -> bool:
    """
    Determine whether a route is already orthogonal.

    :param points: Route points.
    :return: ``True`` when every segment is axis aligned.
    """
    normalized_points: List[Tuple[float, float]] = _normalize_points(points)
    point_count: int = len(normalized_points)
    point_index: int

    if point_count < 2:
        return False
    else:
        pass

    for point_index in range(point_count - 1):
        if is_axis_aligned_route_segment(start=normalized_points[point_index],
                                         end=normalized_points[point_index + 1]):
            pass
        else:
            return False

    return True


def should_preserve_route_shape(route: Dict[str, Any] | None) -> bool:
    """
    Determine whether one persisted route should drive redraw.

    Locked routes always win. Non-locked auto-routed paths are regenerated
    from the current endpoint anchors, while manual polyline routes are kept
    exactly as saved apart from live endpoint replacement.

    :param route: Persisted route metadata section.
    :return: ``True`` when the interior route elbows should be preserved.
    """
    if route is None:
        return False
    else:
        pass

    route_kind: SchematicRouteKind | None = parse_schematic_route_kind(route.get("kind", None))
    locked = bool(route.get("locked", False))
    auto_route_kinds: set[SchematicRouteKind] = {
        SchematicRouteKind.ORTHOGONAL,
        SchematicRouteKind.AUTO,
        SchematicRouteKind.AUTO_ORTHOGONAL,
        SchematicRouteKind.AUTO_POLYLINE,
    }

    if locked:
        return True
    elif route_kind in auto_route_kinds:
        return False
    elif route_kind is None and str(route.get("kind", "")) == "":
        return "points" in route
    else:
        return True


def build_default_branch_route(start: Tuple[float, float],
                               end: Tuple[float, float],
                               start_order: int | None = None,
                               end_order: int | None = None) -> List[Tuple[float, float]]:
    """
    Build one deterministic coordinate-driven orthogonal route.

    :param start: Start point.
    :param end: End point.
    :param start_order: Optional ordering hint used to separate coincident routes.
    :param end_order: Optional ordering hint used to separate coincident routes.
    :return: Orthogonal route points.
    """
    start_point: Tuple[float, float] = (float(start[0]), float(start[1]))
    end_point: Tuple[float, float] = (float(end[0]), float(end[1]))
    lane_pitch: float = 14.0
    lane_index: int = get_default_route_lane_index(start_order=start_order, end_order=end_order)
    lane_offset: float = float(max(0, lane_index - 1)) * lane_pitch
    delta_x: float = end_point[0] - start_point[0]
    delta_y: float = end_point[1] - start_point[1]
    midpoint_x: float = (start_point[0] + end_point[0]) * 0.5
    midpoint_y: float = (start_point[1] + end_point[1]) * 0.5
    route_points: List[Tuple[float, float]] = list()

    if abs(delta_x) >= abs(delta_y):
        if abs(delta_y) <= 1e-9 and lane_offset > 0.0:
            route_y: float = midpoint_y + lane_offset
            route_points = [
                start_point,
                (start_point[0], route_y),
                (end_point[0], route_y),
                end_point,
            ]
        else:
            route_points = [
                start_point,
                (midpoint_x, start_point[1]),
                (midpoint_x, end_point[1]),
                end_point,
            ]
    else:
        if abs(delta_x) <= 1e-9 and lane_offset > 0.0:
            route_x: float = midpoint_x + lane_offset
            route_points = [
                start_point,
                (route_x, start_point[1]),
                (route_x, end_point[1]),
                end_point,
            ]
        else:
            route_points = [
                start_point,
                (start_point[0], midpoint_y),
                (end_point[0], midpoint_y),
                end_point,
            ]

    return compress_route_points(route_points)


def get_attachment(location: GraphicLocation, endpoint: str) -> Dict[str, Any]:
    """
    Return attachment metadata for an endpoint such as 'from', 'to', or a shunt/injection id.
    """
    attachments = get_layout_section(location, "attachments", default=dict()) or dict()
    value = attachments.get(endpoint, dict())
    return deepcopy(value)


def get_attachment_record(location: GraphicLocation,
                          endpoint: SchematicBranchEndpoint | str) -> SchematicAttachmentRecord:
    """
    Return one typed attachment record from persisted metadata.

    :param location: Graphic location record.
    :param endpoint: Runtime endpoint enum or persisted string.
    :return: Typed attachment record.
    """
    endpoint_value: SchematicBranchEndpoint | None = parse_schematic_branch_endpoint(endpoint=endpoint)
    attachment_record: SchematicAttachmentRecord = SchematicAttachmentRecord()

    if endpoint_value is None:
        return attachment_record
    else:
        persisted_attachment: Dict[str, Any] = get_attachment(location=location, endpoint=endpoint_value.value)

    attachment_record.owner_device_id = str(persisted_attachment.get("owner_device_id", ""))
    attachment_record.owner_device_type = str(persisted_attachment.get("owner_device_type", ""))
    attachment_record.anchor_x = (
        float(persisted_attachment.get("anchor_x"))
        if persisted_attachment.get("anchor_x", None) is not None
        else None
    )
    attachment_record.anchor_y = (
        float(persisted_attachment.get("anchor_y"))
        if persisted_attachment.get("anchor_y", None) is not None
        else None
    )
    attachment_record.anchor_auto = bool(persisted_attachment.get("anchor_auto", True))
    attachment_record.side = parse_schematic_attachment_side(persisted_attachment.get("side", None))
    attachment_record.slot_key = (
        str(persisted_attachment.get("slot"))
        if persisted_attachment.get("slot", None) is not None
        else None
    )
    attachment_record.terminal_key = (
        str(persisted_attachment.get("terminal_key"))
        if persisted_attachment.get("terminal_key", None) is not None
        else None
    )
    attachment_record.order = (
        int(persisted_attachment.get("order"))
        if isinstance(persisted_attachment.get("order", None), int)
        else None
    )
    attachment_record.auto_slot = bool(persisted_attachment.get("auto_slot", True))
    return attachment_record


def set_attachment_record(location: GraphicLocation,
                          endpoint: SchematicBranchEndpoint | str,
                          attachment_record: SchematicAttachmentRecord) -> Dict[str, Any]:
    """
    Persist one typed attachment record while preserving the persisted schema.

    :param location: Graphic location record.
    :param endpoint: Runtime endpoint enum or persisted string.
    :param attachment_record: Typed attachment record.
    :return: Updated layout metadata.
    """
    endpoint_value: SchematicBranchEndpoint | None = parse_schematic_branch_endpoint(endpoint=endpoint)

    if endpoint_value is None:
        return ensure_layout_metadata(location)
    else:
        attachment: Dict[str, Any] = get_attachment(location=location, endpoint=endpoint_value.value)

    # Keep compatibility storage intact while replacing the runtime option handling with typed fields.
    attachment["owner_device_id"] = attachment_record.owner_device_id
    attachment["owner_device_type"] = attachment_record.owner_device_type

    if attachment_record.anchor_x is None:
        attachment.pop("anchor_x", None)
    else:
        attachment["anchor_x"] = float(attachment_record.anchor_x)

    if attachment_record.anchor_y is None:
        attachment.pop("anchor_y", None)
    else:
        attachment["anchor_y"] = float(attachment_record.anchor_y)

    attachment["anchor_auto"] = bool(attachment_record.anchor_auto)

    if attachment_record.side is None:
        attachment.pop("side", None)
    else:
        attachment["side"] = attachment_record.side.value

    if attachment_record.slot_key is None:
        attachment.pop("slot", None)
    else:
        attachment["slot"] = attachment_record.slot_key

    if attachment_record.terminal_key is None:
        attachment.pop("terminal_key", None)
    else:
        attachment["terminal_key"] = attachment_record.terminal_key

    if attachment_record.order is None:
        attachment.pop("order", None)
    else:
        attachment["order"] = int(attachment_record.order)

    attachment["auto_slot"] = bool(attachment_record.auto_slot)
    return set_attachment(location=location, endpoint=endpoint_value.value, attachment=attachment)


def set_attachment(location: GraphicLocation, endpoint: str, attachment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set attachment metadata for an endpoint.
    """
    attachments = get_layout_section(location, "attachments", default=dict()) or dict()
    attachments[endpoint] = deepcopy(attachment)
    return set_layout_section(location, "attachments", attachments)


def get_dock(location: GraphicLocation) -> Dict[str, Any]:
    """
    Return dock metadata for a bus-connected child such as a shunt or generator.

    :param location: Graphic location record.
    :return: Dock metadata dictionary.
    """
    value = get_layout_section(location, "dock", default=dict()) or dict()
    return deepcopy(value)


def get_dock_record(location: GraphicLocation) -> SchematicDockRecord:
    """
    Return one typed dock record from persisted metadata.

    :param location: Graphic location record.
    :return: Typed dock record.
    """
    persisted_dock: Dict[str, Any] = get_dock(location=location)
    dock_record: SchematicDockRecord = SchematicDockRecord()
    dock_record.owner_device_id = str(persisted_dock.get("owner_device_id", ""))
    dock_record.owner_device_type = str(persisted_dock.get("owner_device_type", ""))
    dock_record.side = parse_schematic_attachment_side(persisted_dock.get("side", None))
    dock_record.offset = float(persisted_dock.get("offset", 0.0))
    dock_record.order = int(persisted_dock.get("order")) if isinstance(persisted_dock.get("order", None), int) else None
    return dock_record


def set_dock_record(location: GraphicLocation, dock_record: SchematicDockRecord) -> Dict[str, Any]:
    """
    Persist one typed dock record while preserving the persisted schema.

    :param location: Graphic location record.
    :param dock_record: Typed dock record.
    :return: Updated layout metadata.
    """
    dock: Dict[str, Any] = get_dock(location=location)
    dock["owner_device_id"] = dock_record.owner_device_id
    dock["owner_device_type"] = dock_record.owner_device_type

    if dock_record.side is None:
        dock.pop("side", None)
    else:
        dock["side"] = dock_record.side.value

    dock["offset"] = float(dock_record.offset)

    if dock_record.order is None:
        dock.pop("order", None)
    else:
        dock["order"] = int(dock_record.order)

    return set_dock(location=location, dock=dock)


def set_dock(location: GraphicLocation, dock: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set dock metadata for a bus-connected child.

    :param location: Graphic location record.
    :param dock: Dock metadata dictionary.
    :return: Updated layout metadata.
    """
    return set_layout_section(location, "dock", dock)


def is_canonical_attachment_slot(slot_key: str | None) -> bool:
    """
    Determine whether a slot key is one of the compatibility aliases.

    :param slot_key: Persisted slot key.
    :return: ``True`` when the key is a compatibility alias or missing.
    """
    if slot_key is None:
        return True
    elif slot_key == "default":
        return True
    elif slot_key == "left":
        return True
    elif slot_key == "right":
        return True
    elif slot_key == "top":
        return True
    elif slot_key == "bottom":
        return True
    else:
        return False


def build_explicit_attachment_slot_key(owner_kind: str, side: str, order: int) -> str:
    """
    Build a stable explicit slot identifier for persisted schematic attachments.

    :param owner_kind: Node kind prefix such as ``"bus"`` or ``"fluid"``.
    :param side: Attachment side.
    :param order: One-based slot order on that side.
    :return: Explicit slot key.
    """
    return f"{owner_kind}-{side}-{int(order)}"


def parse_explicit_attachment_slot_key(slot_key: str | None) -> Tuple[str, str, int] | None:
    """
    Parse an explicit slot identifier.

    :param slot_key: Persisted slot key.
    :return: Tuple ``(owner_kind, side, order)`` or ``None`` when the key is not explicit.
    """
    if slot_key is None:
        return None
    else:
        parts: List[str] = slot_key.split("-")

    if len(parts) != 3:
        return None
    else:
        owner_kind: str = parts[0]
        side: str = parts[1]
        order_text: str = parts[2]

    if not order_text.isdigit():
        return None
    elif side not in ("left", "right", "top", "bottom"):
        return None
    else:
        return owner_kind, side, int(order_text)
