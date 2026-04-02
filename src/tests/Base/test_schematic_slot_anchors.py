import sys
from typing import Any

from PySide6 import QtWidgets
from PySide6.QtCore import QPointF

from VeraGrid.Gui.Diagrams.SchematicWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Substation.bus_graphics import BusGraphicItem
from VeraGridEngine.Devices.Fluid.fluid_node import FluidNode
from VeraGridEngine.Devices.Substation.bus import Bus


class _EditorStub:
    __slots__ = ("attachments", "diagram")

    def __init__(self) -> None:
        """
        Initialize the editor stub attachment store.

        :return: ``None``.
        """
        self.attachments: dict[tuple[int, str], dict[str, Any]] = dict()
        self.diagram: _DiagramStub = _DiagramStub()

    def update_diagram_element(self,
                               device: Any,
                               x: float,
                               y: float,
                               w: float,
                               h: float,
                               r: float,
                               draw_labels: bool,
                               graphic_object: Any) -> None:
        """
        No-op compatibility stub for graphics tests.

        :param device: Unused.
        :param x: Unused.
        :param y: Unused.
        :param w: Unused.
        :param h: Unused.
        :param r: Unused.
        :param draw_labels: Unused.
        :param graphic_object: Unused.
        :return: ``None``.
        """
        return None

    def start_connection(self, terminal: Any) -> None:
        """
        No-op compatibility stub for terminal interactions.

        :param terminal: Unused.
        :return: ``None``.
        """
        return None

    def get_persisted_attachment(self, api_object: Any, endpoint: str) -> dict[str, Any]:
        """
        Return persisted attachment data for a fake branch endpoint.

        :param api_object: Branch API object.
        :param endpoint: Endpoint key.
        :return: Attachment dictionary.
        """
        return self.diagram.get_attachment(api_object=api_object, endpoint=endpoint)

    def set_persisted_attachment(self, api_object: Any, endpoint: str, attachment: dict[str, Any]) -> None:
        """
        Store persisted attachment data for a fake branch endpoint.

        :param api_object: Branch API object.
        :param endpoint: Endpoint key.
        :param attachment: Attachment dictionary.
        :return: ``None``.
        """
        self.attachments[(id(api_object), endpoint)] = dict(attachment)
        self.diagram.set_attachment(api_object=api_object, endpoint=endpoint, attachment=attachment)


class _BranchGraphicStub:
    __slots__ = ("api_object", "_from_parent", "_to_parent", "pos1", "pos2")

    def __init__(self,
                 api_object: Any,
                 from_parent: Any,
                 to_parent: Any,
                 pos1: QPointF | None = None,
                 pos2: QPointF | None = None) -> None:
        """
        Initialize the fake branch graphic endpoints.

        :param api_object: Branch API object.
        :param from_parent: From-end parent graphic.
        :param to_parent: To-end parent graphic.
        :return: ``None``.
        """
        self.api_object = api_object
        self._from_parent = from_parent
        self._to_parent = to_parent
        self.pos1 = QPointF(0.0, 0.0) if pos1 is None else pos1
        self.pos2 = QPointF(0.0, 0.0) if pos2 is None else pos2

    def get_terminal_from_parent(self) -> Any:
        """
        Return the stored from-end parent graphic.

        :return: Parent graphic.
        """
        return self._from_parent

    def get_terminal_to_parent(self) -> Any:
        """
        Return the stored to-end parent graphic.

        :return: Parent graphic.
        """
        return self._to_parent


class _DiagramStub:
    __slots__ = ("docks", "attachments")

    def __init__(self) -> None:
        """
        Initialize the diagram stub storage.

        :return: ``None``.
        """
        self.docks: dict[int, dict[str, Any]] = dict()
        self.attachments: dict[tuple[int, str], dict[str, Any]] = dict()

    def get_dock(self, api_object: Any) -> dict[str, Any]:
        """
        Return persisted dock metadata.

        :param api_object: Child API object.
        :return: Dock metadata.
        """
        return dict(self.docks.get(id(api_object), dict()))

    def set_dock(self, api_object: Any, dock: dict[str, Any]) -> None:
        """
        Store dock metadata.

        :param api_object: Child API object.
        :param dock: Dock metadata.
        :return: ``None``.
        """
        self.docks[id(api_object)] = dict(dock)

    def get_attachment(self, api_object: Any, endpoint: str) -> dict[str, Any]:
        """
        Return persisted attachment metadata.

        :param api_object: Branch API object.
        :param endpoint: Endpoint key.
        :return: Attachment metadata.
        """
        return dict(self.attachments.get((id(api_object), endpoint), dict()))

    def set_attachment(self, api_object: Any, endpoint: str, attachment: dict[str, Any]) -> None:
        """
        Store persisted attachment metadata.

        :param api_object: Branch API object.
        :param endpoint: Endpoint key.
        :param attachment: Attachment metadata.
        :return: ``None``.
        """
        self.attachments[(id(api_object), endpoint)] = dict(attachment)

    def sync_injection_dock(self, api_object: Any, owner_device: Any, side: str = "bottom") -> dict[str, Any]:
        """
        Emulate the schematic dock sync contract for graphics tests.

        :param api_object: Child API object.
        :param owner_device: Unused owner device.
        :param side: Default dock side.
        :return: Dock metadata.
        """
        dock = self.get_dock(api_object)
        bus_pos = api_object.get_bus_pos(owner_device)

        if "side" not in dock:
            dock["side"] = side
        else:
            pass

        if "offset" not in dock:
            dock["offset"] = 0.0
        else:
            pass

        if "order" not in dock:
            dock["order"] = bus_pos
        else:
            pass

        self.set_dock(api_object, dock)
        return dock


class _ChildApiStub:
    __slots__ = ("_bus_pos",)

    def __init__(self, bus_pos: int) -> None:
        """
        Initialize the fake child API object.

        :param bus_pos: Bus order index.
        :return: ``None``.
        """
        self._bus_pos = bus_pos

    def get_bus_pos(self, bus: Any) -> int:
        """
        Return the configured bus order index.

        :param bus: Unused parent bus.
        :return: Bus order index.
        """
        return self._bus_pos


class _ChildGraphicStub:
    __slots__ = ("api_object", "w", "h", "_pos", "nexus_updates")

    def __init__(self, api_object: Any, w: float = 40.0, h: float = 40.0) -> None:
        """
        Initialize the fake docked child graphic.

        :param api_object: Child API object.
        :param w: Width.
        :param h: Height.
        :return: ``None``.
        """
        self.api_object = api_object
        self.w = w
        self.h = h
        self._pos = QPointF(0.0, 0.0)
        self.nexus_updates: list[tuple[float, float]] = list()

    def setPos(self, x: float, y: float) -> None:
        """
        Store the latest arranged position.

        :param x: X coordinate.
        :param y: Y coordinate.
        :return: ``None``.
        """
        self._pos = QPointF(float(x), float(y))

    def pos(self) -> Any:
        """
        Return the stored position.

        :return: Position object.
        """
        return self._pos

    def x(self) -> float:
        """
        Return the stored X coordinate.

        :return: X coordinate.
        """
        return float(self._pos.x())

    def y(self) -> float:
        """
        Return the stored Y coordinate.

        :return: Y coordinate.
        """
        return float(self._pos.y())

    def update_nexus(self, pos: Any) -> None:
        """
        Record nexus updates during arrangement.

        :param pos: Position.
        :return: ``None``.
        """
        self.nexus_updates.append((float(pos.x()), float(pos.y())))


def _get_app() -> QtWidgets.QApplication:
    """
    Get or create the Qt application used by graphics tests.

    :return: Qt application instance.
    """
    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()

    if app is None:
        return QtWidgets.QApplication(sys.argv)
    else:
        return app


def _noop_callback(value: Any) -> None:
    """
    Ignore terminal callback updates in graphics tests.

    :param value: Unused scene point.
    :return: ``None``.
    """
    return None


def test_bus_graphic_slot_anchors_follow_named_edges() -> None:
    """
    Bus graphics should expose distinct scene anchors for named compatibility slots.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    bus: Bus = Bus(name="B1")
    graphic: BusGraphicItem = BusGraphicItem(editor=editor, bus=bus, w=180.0, h=40.0, x=0.0, y=0.0)

    left_anchor = graphic.get_terminal_anchor_by_key("left")
    right_anchor = graphic.get_terminal_anchor_by_key("right")
    top_anchor = graphic.get_terminal_anchor_by_key("top")

    assert left_anchor.x() == 0.0
    assert left_anchor.y() == 45.0
    assert right_anchor.x() == 180.0
    assert right_anchor.y() == 45.0
    assert top_anchor.x() == 90.0
    assert top_anchor.y() == 40.0


def test_fluid_node_slot_anchors_follow_named_edges() -> None:
    """
    Fluid-node graphics should expose distinct scene anchors for named compatibility slots.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    node: FluidNode = FluidNode(name="N1")
    graphic: FluidNodeGraphicItem = FluidNodeGraphicItem(editor=editor, fluid_node=node, w=180.0, h=40.0, x=0.0, y=0.0)

    left_anchor = graphic.get_terminal_anchor_by_key("left")
    right_anchor = graphic.get_terminal_anchor_by_key("right")
    top_anchor = graphic.get_terminal_anchor_by_key("top")

    assert left_anchor.x() == 0.0
    assert left_anchor.y() == 45.0
    assert right_anchor.x() == 180.0
    assert right_anchor.y() == 45.0
    assert top_anchor.x() == 90.0
    assert top_anchor.y() == 40.0


def test_bus_graphic_terminal_slots_include_explicit_attached_slots() -> None:
    """
    Bus graphics should expose attached explicit slot ids in the slot catalog.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    bus: Bus = Bus(name="B1")
    other_bus: Bus = Bus(name="B2")
    graphic: BusGraphicItem = BusGraphicItem(editor=editor, bus=bus, w=180.0, h=40.0, x=0.0, y=0.0)
    branch_api_object: object = object()
    branch_graphic: _BranchGraphicStub = _BranchGraphicStub(api_object=branch_api_object,
                                                            from_parent=graphic,
                                                            to_parent=other_bus)
    graphic.terminal.add_hosting_connection(branch_graphic, _noop_callback)
    editor.set_persisted_attachment(branch_api_object, "from", {"terminal_key": "bus-right-3"})

    slots = graphic.get_terminal_slots()

    assert "bus-right-3" in slots
    assert slots["bus-right-3"] == {"terminal_key": "bus-right-3", "side": "right"}


def test_bus_graphic_duplicate_explicit_orders_do_not_collapse_anchor_positions() -> None:
    """
    Duplicate explicit slot orders should still spread deterministically by branch identity.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    bus: Bus = Bus(name="B1")
    other_bus: Bus = Bus(name="B2")
    graphic: BusGraphicItem = BusGraphicItem(editor=editor, bus=bus, w=180.0, h=40.0, x=0.0, y=0.0)
    branch_api_object_1: object = object()
    branch_api_object_2: object = object()
    branch_graphic_1: _BranchGraphicStub = _BranchGraphicStub(api_object=branch_api_object_1,
                                                              from_parent=graphic,
                                                              to_parent=other_bus)
    branch_graphic_2: _BranchGraphicStub = _BranchGraphicStub(api_object=branch_api_object_2,
                                                              from_parent=graphic,
                                                              to_parent=other_bus)
    graphic.terminal.add_hosting_connection(branch_graphic_1, _noop_callback)
    graphic.terminal.add_hosting_connection(branch_graphic_2, _noop_callback)
    editor.set_persisted_attachment(branch_api_object_1, "from", {"terminal_key": "bus-right-1"})
    editor.set_persisted_attachment(branch_api_object_2, "from", {"terminal_key": "bus-right-1"})

    anchor_1 = graphic.get_terminal_anchor_by_key("bus-right-1", graphic_object=branch_graphic_1)
    anchor_2 = graphic.get_terminal_anchor_by_key("bus-right-1", graphic_object=branch_graphic_2)

    assert anchor_1.x() == 180.0
    assert anchor_2.x() == 180.0
    assert anchor_1.y() != anchor_2.y()


def test_bus_graphic_detects_duplicate_explicit_slot_orders() -> None:
    """
    Duplicate explicit slot orders should be detectable for compatibility fallback.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    bus: Bus = Bus(name="B1")
    other_bus: Bus = Bus(name="B2")
    graphic: BusGraphicItem = BusGraphicItem(editor=editor, bus=bus, w=180.0, h=40.0, x=0.0, y=0.0)
    branch_api_object_1: object = object()
    branch_api_object_2: object = object()
    branch_graphic_1: _BranchGraphicStub = _BranchGraphicStub(api_object=branch_api_object_1,
                                                              from_parent=graphic,
                                                              to_parent=other_bus)
    branch_graphic_2: _BranchGraphicStub = _BranchGraphicStub(api_object=branch_api_object_2,
                                                              from_parent=graphic,
                                                              to_parent=other_bus)
    graphic.terminal.add_hosting_connection(branch_graphic_1, _noop_callback)
    graphic.terminal.add_hosting_connection(branch_graphic_2, _noop_callback)
    editor.set_persisted_attachment(branch_api_object_1, "from", {"terminal_key": "bus-right-1"})
    editor.set_persisted_attachment(branch_api_object_2, "from", {"terminal_key": "bus-right-1"})

    assert graphic.has_duplicate_explicit_slot_order(side_key="right", order=1) is True


def test_fluid_node_terminal_slots_include_explicit_attached_slots() -> None:
    """
    Fluid-node graphics should expose attached explicit slot ids in the slot catalog.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    node: FluidNode = FluidNode(name="N1")
    other_node: object = object()
    graphic: FluidNodeGraphicItem = FluidNodeGraphicItem(editor=editor, fluid_node=node, w=180.0, h=40.0, x=0.0, y=0.0)
    branch_api_object: object = object()
    branch_graphic: _BranchGraphicStub = _BranchGraphicStub(api_object=branch_api_object,
                                                            from_parent=graphic,
                                                            to_parent=other_node)
    graphic._terminal.add_hosting_connection(branch_graphic, _noop_callback)
    editor.set_persisted_attachment(branch_api_object, "from", {"terminal_key": "fluid-right-2"})

    slots = graphic.get_terminal_slots()

    assert "fluid-right-2" in slots
    assert slots["fluid-right-2"] == {"terminal_key": "fluid-right-2", "side": "right"}


def test_bus_graphic_arrange_children_uses_persisted_dock_sides() -> None:
    """
    Bus graphics should place children according to persisted dock metadata.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    bus: Bus = Bus(name="B1")
    graphic: BusGraphicItem = BusGraphicItem(editor=editor, bus=bus, w=180.0, h=40.0, x=0.0, y=0.0)

    bottom_api = _ChildApiStub(bus_pos=1)
    top_api = _ChildApiStub(bus_pos=2)
    right_api = _ChildApiStub(bus_pos=3)
    bottom_child = _ChildGraphicStub(api_object=bottom_api)
    top_child = _ChildGraphicStub(api_object=top_api)
    right_child = _ChildGraphicStub(api_object=right_api)

    graphic._child_graphics = [bottom_child, top_child, right_child]
    editor.diagram.set_dock(bottom_api, {"side": "bottom", "order": 1, "offset": 5.0})
    editor.diagram.set_dock(top_api, {"side": "top", "order": 1, "offset": 10.0})
    editor.diagram.set_dock(right_api, {"side": "right", "order": 1, "offset": 15.0})

    graphic.arrange_children()

    assert bottom_child.y() == 85.0
    assert top_child.y() == -90.0
    assert right_child.x() == 235.0
    assert len(bottom_child.nexus_updates) == 1
    assert len(top_child.nexus_updates) == 1
    assert len(right_child.nexus_updates) == 1


def test_bus_graphic_nexus_point_for_child_uses_dock_side() -> None:
    """
    Bus nexus anchors should follow the dock side of each child.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    bus: Bus = Bus(name="B1")
    graphic: BusGraphicItem = BusGraphicItem(editor=editor, bus=bus, w=180.0, h=40.0, x=0.0, y=0.0)
    left_api = _ChildApiStub(bus_pos=1)
    left_child = _ChildGraphicStub(api_object=left_api)
    left_child.setPos(-80.0, 20.0)
    editor.diagram.set_dock(left_api, {"side": "left", "order": 1, "offset": 0.0})

    nexus_point = graphic.get_nexus_point_for_child(left_child)

    assert nexus_point.x() == 0.0
    assert nexus_point.y() == 40.0


def test_bus_graphic_auto_assign_branch_slots_uses_geometry_order() -> None:
    """
    Bus graphics should assign explicit branch slots deterministically from scene geometry.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    bus: Bus = Bus(name="B1")
    other_bus: Bus = Bus(name="B2")
    graphic: BusGraphicItem = BusGraphicItem(editor=editor, bus=bus, w=180.0, h=40.0, x=0.0, y=0.0)
    branch_api_object_1: object = object()
    branch_api_object_2: object = object()
    branch_graphic_1: _BranchGraphicStub = _BranchGraphicStub(api_object=branch_api_object_1,
                                                              from_parent=graphic,
                                                              to_parent=other_bus,
                                                              pos1=QPointF(90.0, 25.0),
                                                              pos2=QPointF(40.0, 220.0))
    branch_graphic_2: _BranchGraphicStub = _BranchGraphicStub(api_object=branch_api_object_2,
                                                              from_parent=graphic,
                                                              to_parent=other_bus,
                                                              pos1=QPointF(90.0, 25.0),
                                                              pos2=QPointF(140.0, 220.0))
    graphic.terminal.add_hosting_connection(branch_graphic_1, _noop_callback)
    graphic.terminal.add_hosting_connection(branch_graphic_2, _noop_callback)

    graphic.auto_assign_branch_slots()

    assert editor.diagram.get_attachment(branch_api_object_1, "from")["slot"] == "bus-bottom-1"
    assert editor.diagram.get_attachment(branch_api_object_2, "from")["slot"] == "bus-bottom-2"
    assert editor.diagram.get_attachment(branch_api_object_1, "from")["auto_slot"] is True
    assert editor.diagram.get_attachment(branch_api_object_2, "from")["auto_slot"] is True


def test_bus_graphic_auto_assign_branch_slots_prefers_vertical_feeders_for_bar_buses() -> None:
    """
    Bar-style buses should default to top/bottom feeder slots instead of end-of-bar anchors.
    """
    _get_app()
    editor: _EditorStub = _EditorStub()
    bus: Bus = Bus(name="B1")
    other_bus: Bus = Bus(name="B2")
    graphic: BusGraphicItem = BusGraphicItem(editor=editor, bus=bus, w=180.0, h=40.0, x=0.0, y=0.0)
    branch_api_object: object = object()
    branch_graphic: _BranchGraphicStub = _BranchGraphicStub(api_object=branch_api_object,
                                                            from_parent=graphic,
                                                            to_parent=other_bus,
                                                            pos1=QPointF(90.0, 25.0),
                                                            pos2=QPointF(260.0, 35.0))
    graphic.terminal.add_hosting_connection(branch_graphic, _noop_callback)

    graphic.auto_assign_branch_slots()

    assert editor.diagram.get_attachment(branch_api_object, "from")["side"] == "top"
    assert editor.diagram.get_attachment(branch_api_object, "from")["slot"] == "bus-top-1"
