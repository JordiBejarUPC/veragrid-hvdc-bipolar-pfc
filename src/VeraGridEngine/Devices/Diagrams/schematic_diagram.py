# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Any, Dict, Iterable, List, TYPE_CHECKING, Tuple
from VeraGridEngine.Devices.Diagrams.base_diagram import BaseDiagram
from VeraGridEngine.Devices.Diagrams.graphic_location import GraphicLocation
from VeraGridEngine.Devices.Diagrams.schematic_layout import (build_default_branch_route,
                                                              build_explicit_attachment_slot_key,
                                                              copy_layout_metadata, get_attachment,
                                                              get_branch_route_points, get_dock,
                                                              is_canonical_attachment_slot,
                                                              parse_explicit_attachment_slot_key,
                                                              set_attachment, set_branch_route_points,
                                                              set_dock, should_preserve_route_shape)
from VeraGridEngine.enumerations import DeviceType, DiagramType

if TYPE_CHECKING:
    from VeraGridEngine.Devices.types import ALL_DEV_TYPES


def get_attachment_owner_kind(owner_device: ALL_DEV_TYPES | None) -> str | None:
    """
    Map node device types to persisted attachment slot prefixes.

    :param owner_device: Endpoint owner device.
    :return: Slot prefix such as ``"bus"`` or ``"fluid"``.
    """
    if owner_device is None:
        return None
    elif owner_device.device_type == DeviceType.BusDevice:
        return "bus"
    elif owner_device.device_type == DeviceType.BusBarDevice:
        return "bus"
    elif owner_device.device_type == DeviceType.FluidNodeDevice:
        return "fluid"
    else:
        return None


class SchematicDiagram(BaseDiagram):
    """
    Diagram
    """

    def __init__(self, idtag=None, name=''):
        """

        :param name: Diagram name
        """
        BaseDiagram.__init__(self, idtag=idtag, name=name, diagram_type=DiagramType.Schematic)

    def update_xy(self, api_object: ALL_DEV_TYPES, x: int, y: int) -> None:
        """
        Update the element xy position
        :param api_object: Any DB object
        :param x: x position in px
        :param y: y position in px
        """
        location = self.query_point(api_object)
        if location:
            location.x = x
            location.y = y

    def update_graphic_location(self,
                                api_object: ALL_DEV_TYPES,
                                x: float = 0.0,
                                y: float = 0.0,
                                w: float = 0.0,
                                h: float = 0.0,
                                r: float = 0.0,
                                draw_labels: bool = True) -> GraphicLocation:
        """
        Update basic schematic geometry while preserving any route and attachment metadata already persisted.
        """
        location = self._get_or_create_graphic_location(api_object)
        location.x = x
        location.y = y
        location.w = w
        location.h = h
        location.r = r
        location.draw_labels = draw_labels
        location.api_object = api_object
        return location

    def copy_layout_state(self,
                          source_api_object: ALL_DEV_TYPES,
                          target_api_object: ALL_DEV_TYPES,
                          include_geometry: bool = False) -> GraphicLocation | None:
        """
        Copy persisted schematic route and attachment state from one device to another.
        """
        source_location = self.query_point(source_api_object)

        if source_location is None:
            return None

        copied_location = source_location.copy()
        copied_location.api_object = target_api_object

        if not include_geometry:
            copied_location.x = 0.0
            copied_location.y = 0.0
            copied_location.w = 0.0
            copied_location.h = 0.0
            copied_location.r = 0.0

        self.set_point(device=target_api_object, location=copied_location)
        return copied_location

    def _get_or_create_graphic_location(self, api_object: ALL_DEV_TYPES) -> GraphicLocation:
        """
        Return an existing schematic location or create a placeholder entry for compatibility-layer updates.
        """
        location = self.query_point(api_object)

        if location is None:
            location = GraphicLocation(api_object=api_object)
            self.set_point(device=api_object, location=location)

        return location

    def get_layout_metadata(self, api_object: ALL_DEV_TYPES) -> Dict[str, Any]:
        """
        Return a defensive copy of the persisted schematic layout metadata for this device.
        """
        location = self._get_or_create_graphic_location(api_object)
        return copy_layout_metadata(location)

    def get_branch_route_points(self, api_object: ALL_DEV_TYPES) -> List[Tuple[float, float]]:
        """
        Return route points using the compatibility layer that understands both legacy and structured storage.
        """
        location = self._get_or_create_graphic_location(api_object)
        return get_branch_route_points(location)

    def should_preserve_branch_route_shape(self, api_object: ALL_DEV_TYPES) -> bool:
        """
        Determine whether a branch should keep its persisted interior route elbows.

        :param api_object: Branch API object.
        :return: ``True`` when persisted route elbows should be preserved.
        """
        location = self._get_or_create_graphic_location(api_object)
        route = location.layout_metadata.get("route", None)
        if isinstance(route, dict):
            return should_preserve_route_shape(route=route)
        else:
            return False

    def set_branch_route_points(self,
                                api_object: ALL_DEV_TYPES,
                                points: Iterable[Tuple[float, float]],
                                kind: str | None = "auto-polyline",
                                locked: bool | None = False) -> Dict[str, Any]:
        """
        Persist route points through the compatibility layer while keeping legacy polyline storage in sync.
        """
        location = self._get_or_create_graphic_location(api_object)
        return set_branch_route_points(location=location, points=points, kind=kind, locked=locked)

    def sync_branch_route_points(self,
                                 api_object: ALL_DEV_TYPES,
                                 points: Iterable[Tuple[float, float]]) -> Dict[str, Any]:
        """
        Update route points while preserving existing route kind and lock state.
        """
        location = self._get_or_create_graphic_location(api_object)
        return set_branch_route_points(location=location, points=points, kind=None, locked=None)

    def upgrade_legacy_branch_layout(self,
                                     api_object: ALL_DEV_TYPES,
                                     start: Tuple[float, float],
                                     end: Tuple[float, float]) -> Dict[str, Any]:
        """
        Fill missing structured branch layout metadata for legacy diagrams.
        """
        location = self._get_or_create_graphic_location(api_object)
        attachments = self.sync_branch_attachments(api_object=api_object)
        route_points = get_branch_route_points(location=location)
        route_section = location.layout_metadata.get("route", None)

        if len(route_points) >= 2:
            if route_section is None:
                self.set_branch_route_points(api_object=api_object,
                                             points=route_points,
                                             kind="manual-polyline",
                                             locked=False)
            else:
                pass
        else:
            from_attachment = attachments.get("from", dict())
            to_attachment = attachments.get("to", dict())
            from_side = str(from_attachment.get("side", "bottom"))
            to_side = str(to_attachment.get("side", "bottom"))
            from_order = from_attachment.get("order", None)
            to_order = to_attachment.get("order", None)
            synthesized_route = build_default_branch_route(start=start,
                                                           end=end,
                                                           start_side=from_side,
                                                           end_side=to_side,
                                                           start_order=from_order,
                                                           end_order=to_order)
            self.set_branch_route_points(api_object=api_object,
                                         points=synthesized_route,
                                         kind="auto-polyline",
                                         locked=False)

        return self.get_layout_metadata(api_object=api_object)

    def get_attachment(self, api_object: ALL_DEV_TYPES, endpoint: str) -> Dict[str, Any]:
        """
        Return persisted attachment metadata for a branch endpoint or dockable child.
        """
        location = self._get_or_create_graphic_location(api_object)
        return get_attachment(location=location, endpoint=endpoint)

    def set_attachment(self, api_object: ALL_DEV_TYPES, endpoint: str, attachment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persist attachment metadata through the compatibility layer.
        """
        location = self._get_or_create_graphic_location(api_object)
        return set_attachment(location=location, endpoint=endpoint, attachment=attachment)

    def get_dock(self, api_object: ALL_DEV_TYPES) -> Dict[str, Any]:
        """
        Return persisted dock metadata for a bus-connected child device.
        """
        location = self._get_or_create_graphic_location(api_object)
        return get_dock(location=location)

    def set_dock(self, api_object: ALL_DEV_TYPES, dock: Dict[str, Any]) -> Dict[str, Any]:
        """
        Persist dock metadata through the compatibility layer.
        """
        location = self._get_or_create_graphic_location(api_object)
        return set_dock(location=location, dock=dock)

    def sync_attachment(self,
                        api_object: ALL_DEV_TYPES,
                        endpoint: str,
                        owner_device: ALL_DEV_TYPES | None) -> Dict[str, Any]:
        """
        Update endpoint ownership metadata while preserving any future slot-routing fields already stored.
        """
        # Import branch base lazily to keep the diagram layer light and avoid circular imports
        # during module initialization. The check is only needed when attachment metadata is updated.
        from VeraGridEngine.Devices.Parents.branch_parent import BranchParent

        attachment = self.get_attachment(api_object=api_object, endpoint=endpoint)

        if owner_device is None:
            attachment["owner_device_id"] = ""
            attachment["owner_device_type"] = ""
        else:
            attachment["owner_device_id"] = owner_device.idtag
            attachment["owner_device_type"] = owner_device.device_type.value

        owner_kind = get_attachment_owner_kind(owner_device=owner_device)

        if owner_kind == "bus":
            default_side = "bottom"
        elif endpoint == "from":
            default_side = "right"
        elif endpoint == "to":
            default_side = "left"
        else:
            default_side = "default"

        attachment.setdefault("side", default_side)
        attachment.setdefault("slot", default_side)
        attachment.setdefault("terminal_key", default_side)

        stored_order = attachment.get("order", None)

        if stored_order is not None:
            attachment["order"] = stored_order
        else:
            if isinstance(api_object, BranchParent) and owner_device is not None:
                inferred_order = api_object.get_bus_pos(owner_device)

                if inferred_order != 0:
                    attachment["order"] = inferred_order
                else:
                    attachment.pop("order", None)
            else:
                attachment.pop("order", None)

        side_key = str(attachment.get("side", default_side))
        slot_key = attachment.get("slot", None)
        terminal_key = attachment.get("terminal_key", None)
        auto_slot_enabled = bool(attachment.get("auto_slot", True))
        explicit_slot = parse_explicit_attachment_slot_key(slot_key=str(slot_key)) if slot_key is not None else None
        explicit_terminal_key = (
            parse_explicit_attachment_slot_key(slot_key=str(terminal_key))
            if terminal_key is not None
            else None
        )
        order_value = attachment.get("order", None)

        if not auto_slot_enabled:
            if explicit_slot is not None:
                side_key = explicit_slot[1]
            elif explicit_terminal_key is not None:
                side_key = explicit_terminal_key[1]
            elif is_canonical_attachment_slot(slot_key=str(slot_key) if slot_key is not None else None):
                side_key = str(slot_key)
            elif is_canonical_attachment_slot(slot_key=str(terminal_key) if terminal_key is not None else None):
                side_key = str(terminal_key)
            else:
                pass

            attachment["side"] = side_key

            if explicit_slot is None:
                attachment["slot"] = side_key
            else:
                attachment["slot"] = slot_key

            if explicit_terminal_key is None:
                if explicit_slot is not None and slot_key is not None:
                    attachment["terminal_key"] = slot_key
                else:
                    attachment["terminal_key"] = side_key
            else:
                attachment["terminal_key"] = terminal_key

            self.set_attachment(api_object=api_object, endpoint=endpoint, attachment=attachment)
            return self.get_attachment(api_object=api_object, endpoint=endpoint)
        else:
            pass

        if owner_kind is not None and isinstance(order_value, int) and order_value > 0 and auto_slot_enabled:
            explicit_slot_key = build_explicit_attachment_slot_key(owner_kind=owner_kind,
                                                                   side=side_key,
                                                                   order=order_value)

            if is_canonical_attachment_slot(slot_key=str(slot_key) if slot_key is not None else None):
                attachment["slot"] = explicit_slot_key
            elif explicit_slot is not None:
                attachment["slot"] = explicit_slot_key
            else:
                pass

            if is_canonical_attachment_slot(slot_key=str(terminal_key) if terminal_key is not None else None):
                attachment["terminal_key"] = explicit_slot_key
            elif explicit_terminal_key is not None:
                attachment["terminal_key"] = explicit_slot_key
            else:
                pass
        else:
            if is_canonical_attachment_slot(slot_key=str(slot_key) if slot_key is not None else None):
                attachment["slot"] = side_key
            elif explicit_slot is not None:
                attachment["slot"] = slot_key
            else:
                pass

            if is_canonical_attachment_slot(slot_key=str(terminal_key) if terminal_key is not None else None):
                if explicit_slot is not None and slot_key is not None:
                    attachment["terminal_key"] = slot_key
                else:
                    attachment["terminal_key"] = side_key
            elif explicit_terminal_key is not None:
                attachment["terminal_key"] = terminal_key
            else:
                pass

        self.set_attachment(api_object=api_object, endpoint=endpoint, attachment=attachment)
        return self.get_attachment(api_object=api_object, endpoint=endpoint)

    def sync_branch_attachments(self, api_object: ALL_DEV_TYPES) -> Dict[str, Dict[str, Any]]:
        """
        Synchronize the standard 'from' and 'to' attachment ownership records for branch-like devices.
        """
        # Import concrete branch families lazily so diagram persistence does not force eager initialization
        # of the full engine graph while tests import isolated schematic modules.
        from VeraGridEngine.Devices.Fluid.fluid_path import FluidPath
        from VeraGridEngine.Devices.Parents.branch_parent import BranchParent

        if not isinstance(api_object, (BranchParent, FluidPath)):
            return dict()
        else:
            obj_from, obj_to, ok = api_object.get_from_and_to_objects()

            if not ok:
                return dict()
            else:
                return {
                    "from": self.sync_attachment(api_object=api_object, endpoint="from", owner_device=obj_from),
                    "to": self.sync_attachment(api_object=api_object, endpoint="to", owner_device=obj_to),
                }

    def sync_injection_dock(self,
                            api_object: ALL_DEV_TYPES,
                            owner_device: ALL_DEV_TYPES | None,
                            side: str = "bottom") -> Dict[str, Any]:
        """
        Synchronize dock metadata for a bus-connected child while preserving future docking fields.
        """
        dock = self.get_dock(api_object=api_object)

        if owner_device is None:
            dock["owner_device_id"] = ""
            dock["owner_device_type"] = ""
        else:
            dock["owner_device_id"] = owner_device.idtag
            dock["owner_device_type"] = owner_device.device_type.value

        dock.setdefault("side", side)
        dock.setdefault("offset", 0.0)

        order = dock.get("order", None)

        if order is None and owner_device is not None:
            dock["order"] = api_object.get_bus_pos(owner_device)
        elif order is None:
            dock["order"] = 0
        else:
            dock["order"] = order

        self.set_dock(api_object=api_object, dock=dock)
        return self.get_dock(api_object=api_object)
