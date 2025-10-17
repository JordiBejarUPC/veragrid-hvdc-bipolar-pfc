#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import json, sys, uuid, math
from typing import Dict, List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainterPath, QAction, QPen, QBrush, QFont, QTransform, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsSimpleTextItem,
    QListWidget, QListWidgetItem, QSplitter, QWidget, QVBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox, QDockWidget, QFileDialog, QMessageBox, QToolBar
)


def new_id() -> str:
    return uuid.uuid4().hex


GRID_STEP = 20
PORT_R = 5.0
PORT_D = 2 * PORT_R
HANDLE_S = 9.0
AUTO_ATTACH_THRESHOLD = 42.0

PEN_NORMAL = QPen(Qt.GlobalColor.black, 2)
PEN_LIGHT = QPen(Qt.GlobalColor.gray, 1, Qt.PenStyle.DashLine)
PEN_CONN = QPen(Qt.GlobalColor.black, 2)
PEN_SEL = QPen(Qt.GlobalColor.darkGreen, 2)
BRUSH_PORT = QBrush(Qt.GlobalColor.white)
BRUSH_HANDLE = QBrush(Qt.GlobalColor.yellow)


class PortItem(QGraphicsEllipseItem):
    """
    Port that can initiate and accept drag-to-connect, only one connection allowed.
    """

    def __init__(self, parent: QGraphicsItem, rel_pos: QPointF, pid: Optional[str] = None):
        super().__init__(-PORT_R, -PORT_R, PORT_D, PORT_D, parent)
        self.id = pid or new_id()
        self.rel_pos = QPointF(rel_pos)
        self.setBrush(BRUSH_PORT)
        self.setPen(PEN_NORMAL)
        self.setZValue(20)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setAcceptDrops(True)
        self.connections: List["ConnectionItem"] = []
        self.drag_line: Optional[QGraphicsPathItem] = None
        self.update_position()
        self._hover = False

    def update_position(self):
        """

        :return:
        """
        self.setPos(self.rel_pos)

    def add_connection(self, c: "ConnectionItem"):
        """
        Add a connection to the list of connections.
        :param c:
        :return:
        """
        if c not in self.connections:
            self.connections.append(c)
            self.update_color()

    def remove_connection(self, c: "ConnectionItem"):
        """
        Remove a connection from the list of connections.
        :param c:
        :return:
        """
        if c in self.connections:
            self.connections.remove(c)
            self.update_color()

    def is_free(self) -> bool:
        """
        Return True if the port can accept a new connection.
        """
        # BusBarItem in connectivity mode -> unlimited connections
        if isinstance(self.parentItem(), BusBarItem):
            bus = self.parentItem()
            if getattr(bus, "mode", "bar") == "connectivity":
                return True
        # otherwise, only one connection allowed
        return len(self.connections) == 0

    def update_color(self):
        """
        Change colour to indicate free/occupied.
        """
        if self.is_free():
            self.setBrush(Qt.GlobalColor.white if not self._hover else Qt.GlobalColor.yellow)
        else:
            self.setBrush(Qt.GlobalColor.lightGray)  # visually mark as used

    def notify(self):
        """
        Notify all connected ports.
        :return:
        """
        for c in list(self.connections):
            c.update_path()

    def mousePressEvent(self, event):
        """
        Handle a mouse press event.
        :param event:
        :return:
        """
        if event.button() == Qt.MouseButton.LeftButton and self.is_free():
            # start temporary preview line
            self.drag_line = QGraphicsPathItem()
            self.drag_line.setPen(QPen(Qt.GlobalColor.darkGray, 1, Qt.PenStyle.DashLine))
            self.scene().addItem(self.drag_line)
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """

        :param event:
        :return:
        """
        if self.drag_line:
            p1 = self.scenePos()
            p2 = event.scenePos()
            # optional orthogonal preview
            path = QPainterPath(p1)
            if abs(p1.x() - p2.x()) > abs(p1.y() - p2.y()):
                midx = (p1.x() + p2.x()) / 2
                path.lineTo(midx, p1.y())
                path.lineTo(midx, p2.y())
            else:
                midy = (p1.y() + p2.y()) / 2
                path.lineTo(p1.x(), midy)
                path.lineTo(p2.x(), midy)
            path.lineTo(p2)
            self.drag_line.setPath(path)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Handle mouse release: finalize connection only if electrical rules allow it.
        """
        if self.drag_line:
            # find valid target port under cursor
            target = None
            for item in self.scene().items(event.scenePos()):
                if isinstance(item, PortItem) and item is not self:
                    target = item
                    break

            # remove preview line
            self.scene().removeItem(self.drag_line)
            self.drag_line = None

            # ---- connection rules ----
            def is_bus_port(p: PortItem) -> bool:
                return isinstance(p.parentItem(), BusBarItem)

            def is_device_port(p: PortItem) -> bool:
                return not is_bus_port(p)

            allowed = False
            if target:
                # Only allow device↔bus (in either direction)
                if (is_device_port(self) and is_bus_port(target)) or \
                        (is_bus_port(self) and is_device_port(target)):
                    allowed = True

            # ---- create connection if allowed ----
            if allowed and target.is_free() and self.is_free():
                conn = ConnectionItem(self, target)
                self.scene().addItem(conn)
                if hasattr(self.scene().views()[0], "window"):
                    win = self.scene().views()[0].window()
                    win.connections.append(conn)
            else:
                # feedback (optional)
                if target and not allowed:
                    QtWidgets.QApplication.beep()

            event.accept()

        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        """
        Handle a mouse enter event.
        :param event:
        :return:
        """
        self._hover = True
        self.update_color()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """
        Handle a mouse leave event.
        :param event:
        :return:
        """
        self._hover = False
        self.update_color()
        super().hoverLeaveEvent(event)


class NodeItem(QGraphicsItem):
    """
    NodeItem
    """

    def __init__(self):
        """

        """
        super().__init__()
        self.id = new_id()
        self.ports: List[PortItem] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self._rotation = 0.0

    def shape(self) -> QtGui.QPainterPath:
        """Return a clickable shape matching the bounding rect."""
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def add_port(self, rel: QPointF) -> PortItem:
        """

        :param rel:
        :return:
        """
        p = PortItem(self, rel)
        self.ports.append(p)
        return p

    def itemChange(self, change, value):
        """

        :param change:
        :param value:
        :return:
        """
        if change in (QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
                      QGraphicsItem.GraphicsItemChange.ItemTransformHasChanged):
            for p in self.ports:
                p.notify()
        return super().itemChange(change, value)

    def to_json_common(self) -> Dict:
        """

        :return:
        """
        return {
            "id": self.id,
            "type": type(self).__name__,
            "pos": [self.pos().x(), self.pos().y()],
            "rotation": self.rotation(),
            "ports": [p.to_json() for p in self.ports]
        }

    def set_angle(self, ang: float):
        """
        Set the rotation angle of the node
        """
        self.setTransformOriginPoint(self.boundingRect().center())
        self.setRotation(ang % 360)

    def to_json(self) -> dict:
        """
        Serialize this port using its local position.
        """
        return {
            "id": self.id,
            "parent": getattr(self.parentItem(), "id", None),
            "x": float(self.pos().x()),
            "y": float(self.pos().y()),
        }

    @classmethod
    def from_json(cls, parent, data: dict):
        """
        Rebuild a port from JSON record.
        """
        pos = QtCore.QPointF(data.get("x", 0.0), data.get("y", 0.0))
        p = cls(parent, pos, pid=data.get("id"))
        return p


class BusBarItem(NodeItem):
    """
    Bus representation: either full bar with ports or single connectivity node.
    """

    def __init__(self, length: float = 260.0, label: str = "Bus",
                 n_ports: int = 6, mode: str = "bar"):
        super().__init__()
        self.mode = mode  # "bar" or "connectivity"
        self.length = float(length)
        self.height = 10.0
        self.label_text = label
        self.label = QGraphicsSimpleTextItem(label, self)
        self.label.setBrush(Qt.GlobalColor.darkRed)
        self.label.setPos(0, -22)

        if self.mode == "bar":
            self._rebuild_ports(n_ports)
        else:
            # connectivity point = one circular node, single port at center
            self.add_port(QPointF(0, 0))

    def boundingRect(self) -> QRectF:
        """

        :return:
        """
        if self.mode == "bar":
            return QRectF(0, -self.height / 2, self.length, self.height)
        else:
            r = 12
            return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter, option, widget=None):
        """

        :param painter:
        :param option:
        :param widget:
        :return:
        """
        painter.setPen(PEN_NORMAL)
        painter.setBrush(Qt.GlobalColor.white)
        if self.mode == "bar":
            painter.drawRect(self.boundingRect())
        else:
            # single-port connectivity point
            painter.drawEllipse(self.boundingRect())

    def _rebuild_ports(self, n: int, keep_scene: bool = False):
        """
        Rebuild ports while preserving connections:
        - If mode="bar": recreate N ports and reattach old connections to nearest new port.
        - If mode="connectivity": enforce a single central port, reattach everything to it.
        """
        # Collect old port info (port object, scene pos, and its connections)
        old_info = []
        for p in list(self.ports):
            old_info.append({
                "port": p,
                "scene_pos": p.scenePos(),
                "connections": list(p.connections)
            })

        # Detach all connections from old ports (keep ConnectionItem objects alive)
        for info in old_info:
            p = info["port"]
            for c in list(p.connections):
                c.detach_from(p)
            if p.scene():
                p.scene().removeItem(p)

        # Clear ports
        self.ports.clear()

        # Create new ports depending on mode
        if self.mode == "bar":
            n = max(1, int(n))
            for i in range(n):
                x = (i + 0.5) * (self.length / n)
                y = self.height / 2
                self.add_port(QPointF(x, y))
        else:
            # connectivity node: single port at center
            self.add_port(QPointF(0, 0))

        # Map old connections to nearest new port(s)
        if old_info:
            if self.mode == "connectivity":
                target = self.ports[0]
                for info in old_info:
                    for c in info["connections"]:
                        if c.a is info["port"]:
                            c.attach_to(info["port"], target)
                        elif c.b is info["port"]:
                            c.attach_to(info["port"], target)
            else:
                for info in old_info:
                    if not info["connections"]:
                        continue
                    old_pos = info["scene_pos"]
                    # choose nearest new port by manhattan distance
                    target = min(self.ports, key=lambda np: (np.scenePos() - old_pos).manhattanLength())
                    for c in info["connections"]:
                        if c.a is info["port"]:
                            c.attach_to(info["port"], target)
                        elif c.b is info["port"]:
                            c.attach_to(info["port"], target)

        # Re-register ports and refresh all connection paths
        self.update_ports_registry()
        self.notify_all_connections()

    # ---------- helpers ----------

    def update_ports_registry(self):
        """Re-register ports in MainWindow. Safe if window is not accessible."""
        win = None
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            if hasattr(view, "window"):
                win = view.window()
        if win:
            for p in self.ports:
                win.ports_by_id[p.id] = p

    def notify_all_connections(self):
        """Force all connections attached to this bus to recompute their paths."""
        seen = set()
        for p in self.ports:
            for c in p.connections:
                if c not in seen:
                    c.update_path()
                    seen.add(c)

    def set_angle(self, ang: float):
        """Rotate and refresh connections."""
        self.setTransformOriginPoint(self.boundingRect().center())
        self.setRotation(ang % 360)
        self.notify_all_connections()

    def itemChange(self, change, value):
        # Update when position/transform changes (covers move + rotate + scale)
        if change in (QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
                      QGraphicsItem.GraphicsItemChange.ItemTransformHasChanged,
                      QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged,):
            for p in self.ports:
                p.notify()
        return super().itemChange(change, value)

    def to_json(self) -> Dict:
        d = self.to_json_common()
        d.update({
            "length": self.length,
            "height": self.height,
            "label": self.label_text,
            "mode": self.mode,
            "n_ports": len(self.ports)
        })
        return d


class RoundNode(NodeItem):
    def __init__(self, r: float = 18.0, caption: str = ""):
        super().__init__()
        self.r = r
        self.caption = QGraphicsSimpleTextItem(caption, self)
        self.caption.setFont(QFont("Arial", 10, QFont.Bold))
        self.caption.setPos(-self.r / 2, -self.r - 14)

    def boundingRect(self) -> QRectF:
        """

        :return:
        """
        return QRectF(-self.r, -self.r, 2 * self.r, 2 * self.r)

    def paint(self, p, opt, w=None):
        """

        :param p:
        :param opt:
        :param w:
        :return:
        """
        p.setPen(PEN_NORMAL)
        p.setBrush(Qt.GlobalColor.white)
        p.drawEllipse(self.boundingRect())


class GeneratorItem(RoundNode):
    def __init__(self):
        super().__init__(20, )

        # Main "G" label
        self.text = QtWidgets.QGraphicsSimpleTextItem("G", self)
        self.text.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        self.text.setPos(-6, -9)

        # Make label completely transparent to mouse events
        self.text.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        self.text.setAcceptHoverEvents(False)
        self.text.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIgnoresParentOpacity, True)
        self.text.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.text.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.text.setFiltersChildEvents(True)  # important: lets parent receive events even under child

        # One port at the top
        self.add_port(QtCore.QPointF(0, -self.r))

    def to_json(self) -> Dict:
        return self.to_json_common()


class LoadItem(NodeItem):
    def __init__(self):
        super().__init__()
        self.w = 28
        self.h = 24
        self.add_port(QPointF(0, -self.h / 2))

    def boundingRect(self) -> QRectF:
        """

        :return:
        """
        return QRectF(-self.w / 2 - 2, -self.h / 2 - 2, self.w + 4, self.h + 6)

    def paint(self, p, opt, w=None):
        """

        :param p:
        :param opt:
        :param w:
        :return:
        """
        p.setPen(PEN_NORMAL)
        p.setBrush(Qt.GlobalColor.white)
        path = QPainterPath()
        path.moveTo(-self.w / 2, -self.h / 2)
        path.lineTo(self.w / 2, -self.h / 2)
        path.lineTo(0, self.h / 2)
        path.closeSubpath()
        p.drawPath(path)

    def to_json(self) -> Dict: return self.to_json_common()


class TransformerItem(NodeItem):
    """Two vertically aligned transparent circles transformer, with tangent ports."""

    def __init__(self):
        super().__init__()
        self.r = 12  # circle radius
        self.spacing = 18  # vertical spacing between circle centres

        # Total half-height from centre to top/bottom circle edge
        top_y = -self.spacing / 2 - self.r
        bottom_y = self.spacing / 2 + self.r

        # Ports tangent to circles (just outside)
        self.port_top = self.add_port(QtCore.QPointF(0, top_y - PORT_R * 1.5))
        self.port_bottom = self.add_port(QtCore.QPointF(0, bottom_y + PORT_R * 1.5))

        # Central "T" label
        # self.label = QtWidgets.QGraphicsSimpleTextItem("T", self)
        # self.label.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        # self.label.setPos(-5, -8)

    def boundingRect(self) -> QtCore.QRectF:
        """Bounding box covering both circles and ports."""
        margin = 4
        total_h = self.spacing + 4 * self.r + PORT_R * 4
        total_w = 2 * self.r + margin
        return QtCore.QRectF(-total_w / 2 - margin,
                             -total_h / 2 - margin,
                             total_w + 2 * margin,
                             total_h + 2 * margin)

    def paint(self, p: QtGui.QPainter, opt, w=None):
        """Draw two transparent circles vertically aligned."""
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setPen(QtGui.QPen(Qt.GlobalColor.black, 2))
        p.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        # Circle centres
        upper_center_y = -self.spacing / 2
        lower_center_y = self.spacing / 2

        # Draw the two circles
        p.drawEllipse(QtCore.QRectF(-self.r, upper_center_y - self.r, 2 * self.r, 2 * self.r))
        p.drawEllipse(QtCore.QRectF(-self.r, lower_center_y - self.r, 2 * self.r, 2 * self.r))

    def to_json(self) -> Dict:
        return self.to_json_common()


class DragHandle(QGraphicsRectItem):
    def __init__(self, owner: "ConnectionItem", is_endpoint: bool = False, endpoint_index: int = 0):
        """

        :param owner:
        :param is_endpoint:
        :param endpoint_index:
        """
        super().__init__(-HANDLE_S / 2, -HANDLE_S / 2, HANDLE_S, HANDLE_S)
        self.setBrush(BRUSH_HANDLE)
        self.setPen(PEN_NORMAL)
        self.setZValue(50)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.owner = owner
        self.is_endpoint = is_endpoint
        self.endpoint_index = endpoint_index  # 0 for A, 1 for B

    def itemChange(self, change, value):
        """

        :param change:
        :param value:
        :return:
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.owner.handle_moved(self)
        return super().itemChange(change, value)


class WaypointHandle(QtWidgets.QGraphicsEllipseItem):
    """Draggable waypoint handle that never gets deleted mid-drag."""

    def __init__(self, connection: "ConnectionItem", index: int, pos: QPointF):
        """

        :param connection:
        :param index:
        :param pos:
        """
        super().__init__(-4, -4, 8, 8)
        self.connection = connection
        self.index = index
        self.setBrush(Qt.GlobalColor.gray)
        self.setPen(Qt.PenStyle.NoPen)
        self.setPos(pos)
        self.setZValue(5)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.normal_size = 8
        self.hover_size = 14

    def hoverEnterEvent(self, event):
        """

        :param event:
        :return:
        """
        self.setRect(-self.hover_size / 2, -self.hover_size / 2, self.hover_size, self.hover_size)
        self.setBrush(Qt.GlobalColor.darkGray)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """

        :param event:
        :return:
        """
        self.setRect(-self.normal_size / 2, -self.normal_size / 2, self.normal_size, self.normal_size)
        self.setBrush(Qt.GlobalColor.gray)
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        """

        :param change:
        :param value:
        :return:
        """
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_scene_pos = self.mapToScene(value)
            if 0 <= self.index < len(self.connection.waypoints):
                self.connection.waypoints[self.index] = new_scene_pos
                self.connection.recompute_only_path()

        elif change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if 0 <= self.index < len(self.connection.waypoints):
                self.connection.waypoints[self.index] = self.scenePos()
                self.connection.update_handles_positions()

        return super().itemChange(change, value)


class ConnectionItem(QGraphicsPathItem):
    """Simple orthogonal connection between two ports, no visual handles."""

    def __init__(self, a: PortItem, b: PortItem, cid: Optional[str] = None,
                 waypoints: Optional[List[Tuple[float, float]]] = None,
                 mode: str = "manhattan"):
        """

        :param a:
        :param b:
        :param cid:
        :param waypoints:
        :param mode:
        """
        super().__init__()
        self.id = cid or new_id()
        self.a = a
        self.b = b
        self.mode = mode
        self.waypoints: List[QPointF] = [QPointF(*pt) for pt in (waypoints or [])]
        self.handles: List[WaypointHandle] = []

        self.a.add_connection(self)
        self.b.add_connection(self)

        self.setZValue(-1)
        self.setPen(PEN_CONN)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        # keep waypoints list in case you want to preserve old files, but not used
        self.setAcceptHoverEvents(True)
        self.setAcceptDrops(True)
        self.setAcceptTouchEvents(True)
        self.update_path()

    def compute_path(self) -> QtGui.QPainterPath:
        p_a = self.a.scenePos()
        p_b = self.b.scenePos()
        pts = [p_a] + self.waypoints + [p_b]

        path = QtGui.QPainterPath(pts[0])
        if self.mode == "straight":
            for p in pts[1:]:
                path.lineTo(p)
        else:
            for i in range(1, len(pts)):
                p1, p2 = pts[i - 1], pts[i]
                if abs(p1.x() - p2.x()) > abs(p1.y() - p2.y()):
                    midx = (p1.x() + p2.x()) / 2
                    path.lineTo(midx, p1.y())
                    path.lineTo(midx, p2.y())
                else:
                    midy = (p1.y() + p2.y()) / 2
                    path.lineTo(p1.x(), midy)
                    path.lineTo(p2.x(), midy)
                path.lineTo(p2)
        return path

    def update_path(self):
        """Recompute path and reposition handles accurately."""
        # force our item to be at (0,0) in scene space
        # self.setPos(QtCore.QPointF(0, 0))
        self.setPath(self.compute_path())
        self.update_handles_positions()

    def recompute_only_path(self):
        """Update just the path without touching handles."""
        self.setPos(QtCore.QPointF(0, 0))
        self.setPath(self.compute_path())

    def create_handles(self):
        """Create handles once and keep them persistent."""
        if not self.scene():
            return
        for i, wp in enumerate(self.waypoints):
            h = WaypointHandle(self, i, wp)
            self.scene().addItem(h)
            self.handles.append(h)

    def update_handles_positions(self):
        """Keep handle positions synced with waypoint list."""
        # Create new handles if more waypoints than handles
        if len(self.handles) < len(self.waypoints):
            for i in range(len(self.handles), len(self.waypoints)):
                h = WaypointHandle(self, i, self.waypoints[i])
                if self.scene():
                    self.scene().addItem(h)
                self.handles.append(h)

        # Sync all existing handles
        for i, wp in enumerate(self.waypoints):
            if i < len(self.handles):
                self.handles[i].setPos(wp)

        # Remove any extra handles if waypoints were deleted
        while len(self.handles) > len(self.waypoints):
            h = self.handles.pop()
            if h.scene():
                h.scene().removeItem(h)

    def add_waypoint(self, pos: QPointF):
        """Add new waypoint and sync handles."""
        self.waypoints.append(QPointF(pos))
        self.update_path()

    def toggle_mode(self):
        """

        :return:
        """
        self.mode = "straight" if self.mode == "manhattan" else "manhattan"
        self.update_path()

    # ------------------------------------------------------------------
    #  Mouse / context menu
    # ------------------------------------------------------------------
    def contextMenuEvent(self, event: QtWidgets.QGraphicsSceneContextMenuEvent):
        """

        :param event:
        :return:
        """
        menu = QtWidgets.QMenu()
        act_toggle = menu.addAction("Toggle Manhattan/Straight")
        act_add_wp = menu.addAction("Add Waypoint Here")
        chosen = menu.exec(event.screenPos())
        if chosen == act_toggle:
            self.toggle_mode()
        elif chosen == act_add_wp:
            self.add_waypoint(event.scenePos())
        event.accept()

    # ------------------------------------------------------------------
    #  Connectivity management
    # ------------------------------------------------------------------
    def detach_from(self, port: PortItem):
        """

        :param port:
        :return:
        """
        if port is self.a:
            self.a.remove_connection(self)
        elif port is self.b:
            self.b.remove_connection(self)

    def attach_to(self, replaced: PortItem, new_port: PortItem):
        """

        :param replaced:
        :param new_port:
        :return:
        """
        if replaced is self.a:
            self.a.remove_connection(self)
            self.a = new_port
            self.a.add_connection(self)
        elif replaced is self.b:
            self.b.remove_connection(self)
            self.b = new_port
            self.b.add_connection(self)
        self.update_path()

    def delete(self):
        """

        :return:
        """
        for h in self.handles:
            if h.scene():
                h.scene().removeItem(h)

        if self.a:
            self.a.remove_connection(self)

        if self.b:
            self.b.remove_connection(self)

        if self.scene():
            self.scene().removeItem(self)

    def to_json(self) -> Dict:
        """

        :return:
        """
        return {
            "id": self.id,
            "a": self.a.id,
            "b": self.b.id,
            "mode": self.mode,
            "waypoints": [[p.x(), p.y()] for p in self.waypoints],
        }


class DiagramScene(QGraphicsScene):
    """
    DiagramScene
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-4000, -3000, 8000, 6000)
        self.setBackgroundBrush(Qt.GlobalColor.white)


class DiagramView(QGraphicsView):
    """
    DiagramView
    """

    def __init__(self, scene: DiagramScene):
        """

        :param scene:
        """
        super().__init__(scene)
        self.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing |
                            QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.zoom_factor = 1.15

        # internal state for manual panning
        self._panning = False
        self._pan_start = QtCore.QPoint()

        # selection-rectangle state
        self._rubber_band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self)
        self._rubber_origin = QtCore.QPoint()
        self._rubber_selecting = False

    def wheelEvent(self, event: QtGui.QWheelEvent):
        """

        :param event:
        :return:
        """
        # standard wheel delta is in eighths of a degree
        angle = event.angleDelta().y()
        if angle == 0:
            return

        # Zoom keeping mouse position as anchor
        factor = self.zoom_factor if event.angleDelta().y() > 0 else 1 / self.zoom_factor
        current_scale = self.transform().m11()  # x-scale
        if 0.05 < current_scale * factor < 10:  # reasonable range
            self.scale(factor, factor)
        event.accept()
        event.accept()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """

        :param event:
        :return:
        """
        scene_pos = self.mapToScene(event.position().toPoint())
        item_under = self.scene().itemAt(scene_pos, self.transform())

        # --- 1) Ctrl + Drag → Pan ---
        if event.button() == Qt.LeftButton and event.modifiers() & Qt.ControlModifier:
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        # --- 2) If clicking on a movable/selectable item → let QGraphicsView handle it normally ---
        if item_under and (
                isinstance(item_under, (NodeItem, PortItem, ConnectionItem))
                or item_under.flags() & QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        ):
            super().mousePressEvent(event)
            return

        # --- 3) Otherwise (empty area) → start rubber-band selection ---
        if event.button() == Qt.LeftButton:
            self._rubber_origin = event.position().toPoint()
            self._rubber_band.setGeometry(QtCore.QRect(self._rubber_origin, QtCore.QSize()))
            self._rubber_band.show()
            self._rubber_selecting = True
            event.accept()
            return

        # --- 4) Fallback ---
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """

        :param event:
        :return:
        """
        if self._panning:
            current = event.position().toPoint()
            delta = QtCore.QPoint(current.x() - self._pan_start.x(),
                                  current.y() - self._pan_start.y())
            self._pan_start = current
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()

        elif self._rubber_selecting:
            rect = QtCore.QRect(self._rubber_origin, event.position().toPoint()).normalized()
            self._rubber_band.setGeometry(rect)
            event.accept()

        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        """

        :param event:
        :return:
        """
        if self._panning and event.button() == QtCore.Qt.LeftButton:
            self._panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()

        elif self._rubber_selecting and event.button() == QtCore.Qt.LeftButton:

            self._rubber_selecting = False
            self._rubber_band.hide()

            # compute scene rectangle properly

            view_rect = self._rubber_band.geometry()
            top_left = self.mapToScene(view_rect.topLeft())
            bottom_right = self.mapToScene(view_rect.bottomRight())
            scene_rect = QtCore.QRectF(top_left, bottom_right).normalized()

            # clear and apply selection
            for item in self.scene().selectedItems():
                item.setSelected(False)

            for item in self.scene().items(scene_rect, QtCore.Qt.IntersectsItemShape):
                item.setSelected(True)

            event.accept()

        else:
            super().mouseReleaseEvent(event)

    # accept drags from palette
    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        """

        :param e:
        :return:
        """
        if e.mimeData().hasFormat("application/x-diagram-item"):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e: QtGui.QDragMoveEvent):
        """

        :param e:
        :return:
        """
        if e.mimeData().hasFormat("application/x-diagram-item"):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e: QtGui.QDropEvent):
        """

        :param e:
        :return:
        """
        if not e.mimeData().hasFormat("application/x-diagram-item"):
            return super().dropEvent(e)
        kind = bytes(e.mimeData().data("application/x-diagram-item")).decode("utf-8")
        pos = self.mapToScene(e.position().toPoint())
        self.parentWidget().window().create_item_from_kind(kind, pos)  # call MainWindow
        e.acceptProposedAction()


class DeviceTree(QtWidgets.QTreeWidget):
    """Hierarchical palette with drag-and-drop and live item preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setAnimated(True)
        self.setIndentation(14)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setStyleSheet("QTreeWidget::item { padding: 4px 6px; }")

        # --- Root categories ---
        root_substation = QtWidgets.QTreeWidgetItem(self, ["Substation"])
        root_injection = QtWidgets.QTreeWidgetItem(self, ["Injection"])
        root_branch = QtWidgets.QTreeWidgetItem(self, ["Branch"])
        self.addTopLevelItems([root_substation, root_injection, root_branch])

        # --- Substation elements ---
        item_bus = QtWidgets.QTreeWidgetItem(root_substation, ["Bus"])
        item_bus.setData(0, Qt.ItemDataRole.UserRole, "Bus")

        item_conn = QtWidgets.QTreeWidgetItem(root_substation, ["Connectivity"])
        item_conn.setData(0, Qt.ItemDataRole.UserRole, "Connectivity")

        # --- Injection elements ---
        item_gen = QtWidgets.QTreeWidgetItem(root_injection, ["Generator"])
        item_gen.setData(0, Qt.ItemDataRole.UserRole, "Generator")
        item_load = QtWidgets.QTreeWidgetItem(root_injection, ["Load"])
        item_load.setData(0, Qt.ItemDataRole.UserRole, "Load")

        # --- Branch elements ---
        item_tr = QtWidgets.QTreeWidgetItem(root_branch, ["Transformer"])
        item_tr.setData(0, Qt.ItemDataRole.UserRole, "Transformer")

        self.setStyleSheet("""
        QTreeWidget::item:hover { background: #e5f3ff; }
        QTreeWidget::item:selected { background: #cce6ff; font-weight: bold; }
        """)

        self.expandAll()

    # ------------------------------
    # Drag start with live pixmap
    # ------------------------------
    def startDrag(self, supportedActions):
        """

        :param supportedActions:
        :return:
        """
        item = self.currentItem()
        if not item or not item.data(0, Qt.ItemDataRole.UserRole):
            return
        kind = item.data(0, Qt.ItemDataRole.UserRole)

        mime = QtCore.QMimeData()
        mime.setData("application/x-diagram-item", str(kind).encode("utf-8"))

        # Generate small pixmap preview depending on type
        pixmap = self._make_pixmap_preview(kind)

        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(pixmap)
        drag.setHotSpot(QtCore.QPoint(pixmap.width() // 2, pixmap.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)

    def _make_pixmap_preview(self, kind: str) -> QtGui.QPixmap:
        """
        Draw a small symbol preview pixmap for dragging feedback.
        """
        w, h = 60, 40
        pm = QtGui.QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        pen = QtGui.QPen(Qt.GlobalColor.black, 2)
        p.setPen(pen)
        p.setBrush(Qt.GlobalColor.white)

        if kind == "Bus":
            p.drawRect(10, h // 2 - 3, w - 20, 6)

        elif kind == "Connectivity":
            p.drawEllipse(w // 2 - 5, h // 2 - 5, 10, 10)

        elif kind == "Generator":
            p.drawEllipse(w // 2 - 10, h // 2 - 10, 20, 20)
            p.drawText(w // 2 - 5, h // 2 + 5, "G")

        elif kind == "Load":
            pts = [QtCore.QPointF(10, h // 2 + 10),
                   QtCore.QPointF(w - 10, h // 2 + 10),
                   QtCore.QPointF(w // 2, h // 2 - 10)]
            p.drawPolygon(QtGui.QPolygonF(pts))

        elif kind == "Transformer":
            p.drawEllipse(w // 2 - 18, h // 2 - 8, 14, 14)
            p.drawEllipse(w // 2 + 4, h // 2 - 8, 14, 14)

        p.end()
        return pm


class PropertyPanel(QWidget):
    """Simple dynamic editor bound to the current selection."""
    value_changed = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.form = QFormLayout(self)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._controls: Dict[str, QtWidgets.QWidget] = {}
        self.current: Optional[QGraphicsItem] = None

    def clear(self):
        """

        :return:
        """
        while self.form.count():
            it = self.form.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._controls.clear()
        self.current = None

    def bind(self, item: Optional[QGraphicsItem]):
        """

        :param item:
        :return:
        """
        self.clear()
        self.current = item
        if item is None: return

        # common rotation for NodeItem
        if isinstance(item, NodeItem):
            rot = QDoubleSpinBox()
            rot.setRange(0, 359)
            rot.setDecimals(0)
            rot.setValue(item.rotation())
            rot.valueChanged.connect(lambda v, n=item: (n.set_angle(v), self.value_changed.emit()))
            self.form.addRow("Rotation (deg)", rot)
            self._controls["rotation"] = rot

        if isinstance(item, BusBarItem):
            name = QLineEdit(item.label_text)
            name.textEdited.connect(
                lambda s, n=item: (setattr(n, "label_text", s), n.label.setText(s), self.value_changed.emit()))
            self.form.addRow("Label", name)

            length = QDoubleSpinBox()
            length.setRange(40, 4000)
            length.setValue(item.length)

            def _set_len(v, n=item):
                n.length = v
                n.prepareGeometryChange()
                n._rebuild_ports(len(n.ports), keep_scene=True)
                n.label.setPos(0, -22)
                self.value_changed.emit()

            length.valueChanged.connect(_set_len)
            self.form.addRow("Length", length)

            ports = QSpinBox();
            ports.setRange(1, 60);
            ports.setValue(len(item.ports))

            def _set_ports(v, n=item):
                n._rebuild_ports(v, keep_scene=True)
                self.value_changed.emit()

            ports.valueChanged.connect(_set_ports)
            self.form.addRow("Ports", ports)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Power Diagrammer Pro (PySide6)")
        self.resize(1300, 800)

        # Scene & View
        self.scene = DiagramScene(self)
        self.view = DiagramView(self.scene)
        self.setCentralWidget(self.view)

        # Left palette + canvas in splitter
        self.palette = DeviceTree()

        self.splitter = QSplitter()
        self.splitter.addWidget(self.palette)
        self.splitter.addWidget(self.view)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)

        # Right property dock
        self.prop_dock = QDockWidget("Properties", self)
        self.prop_panel = PropertyPanel()
        self.prop_dock.setWidget(self.prop_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.prop_dock)
        self.prop_panel.value_changed.connect(lambda: None)

        self.nodes_by_id: Dict[str, NodeItem] = {}
        self.ports_by_id: Dict[str, PortItem] = {}
        self.connections: List[ConnectionItem] = []

        self._build_toolbar()

    def _start_drag(self, supportedActions):
        """

        :param supportedActions:
        :return:
        """
        it = self.palette.currentItem()
        if not it:
            return
        mime = QtCore.QMimeData()
        mime.setData("application/x-diagram-item", str(it.data(Qt.ItemDataRole.UserRole)).encode("utf-8"))
        drag = QtGui.QDrag(self.palette)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    def _build_toolbar(self):
        """

        :return:
        """
        tb = QToolBar("File")
        self.addToolBar(tb)

        save_act = QAction("Save JSON", self)
        save_act.triggered.connect(self.save_json)
        tb.addAction(save_act)
        load_act = QAction("Load JSON", self)
        load_act.triggered.connect(self.load_json)
        tb.addAction(load_act)
        tb.addSeparator()
        svg_act = QAction("Export SVG", self)
        svg_act.triggered.connect(self.export_svg)
        tb.addAction(svg_act)
        png_act = QAction("Export PNG", self)
        png_act.triggered.connect(self.export_png)
        tb.addAction(png_act)

    def _on_selection(self):
        sel = self.scene.selectedItems()
        self.prop_panel.bind(sel[0] if sel else None)

    def create_item_from_kind(self, kind: str, pos: QPointF):
        """

        :param kind:
        :param pos:
        :return:
        """
        item: NodeItem
        if kind == "Bus":
            item = BusBarItem(mode="bar")
        elif kind == "Connectivity":
            item = BusBarItem(mode="connectivity")
        elif kind == "Load":
            item = LoadItem()
        elif kind == "Generator":
            item = GeneratorItem()
        elif kind == "Transformer":
            item = TransformerItem()
        else:
            return
        self.scene.addItem(item)
        item.setPos(pos)
        self.nodes_by_id[item.id] = item
        for p in item.ports:
            self.ports_by_id[p.id] = p

        # Auto-attach to nearest bus if applicable
        if isinstance(item, (LoadItem, GeneratorItem, TransformerItem)):
            my_port = item.ports[0] if item.ports else None
            if my_port:
                nearest = self.find_nearest_bus_port(my_port.scenePos())
                if nearest and (nearest.scenePos() - my_port.scenePos()).manhattanLength() < AUTO_ATTACH_THRESHOLD:
                    c = ConnectionItem(my_port, nearest)
                    self.scene.addItem(c)
                    self.connections.append(c)

    def find_nearest_bus_port(self, scene_pos: QPointF) -> Optional[PortItem]:
        """

        :param scene_pos:
        :return:
        """
        best = None
        bestd = 1e9
        for it in self.scene.items():
            if isinstance(it, PortItem) and isinstance(it.parentItem(), BusBarItem):
                d = (it.scenePos() - scene_pos).manhattanLength()
                if d < bestd:
                    best, bestd = it, d
        return best

    # -------- keyboard shortcuts --------
    def keyPressEvent(self, ev: QtGui.QKeyEvent):
        """

        :param ev:
        :return:
        """
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for it in list(self.scene.selectedItems()):
                if isinstance(it, ConnectionItem):
                    it.delete()
                    if it in self.connections:
                        self.connections.remove(it)

                elif isinstance(it, NodeItem):
                    # delete connections first
                    for p in list(it.ports):
                        for c in list(p.connections):
                            c.delete()
                            if c in self.connections:
                                self.connections.remove(c)

                    self.scene.removeItem(it)
        else:
            super().keyPressEvent(ev)

    # -------- persistence --------
    def save_json(self):
        """

        :return:
        """
        path, _ = QFileDialog.getSaveFileName(self, "Save diagram", "", "JSON (*.json)")

        if not path:
            return

        data = {
            "nodes": [],
            "connections": [c.to_json() for c in self.connections]
        }
        for it in self.scene.items():
            if isinstance(it, NodeItem):
                if isinstance(it, BusBarItem):
                    data["nodes"].append(it.to_json())
                else:
                    data["nodes"].append(it.to_json())

        data["meta"] = {"version": "1.1"}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.statusBar().showMessage(f"Saved {path}")

    def load_json(self):
        """

        :return:
        """
        path, _ = QFileDialog.getOpenFileName(self, "Load diagram", "", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        # clear
        for it in list(self.scene.items()):
            if isinstance(it, ConnectionItem):
                it.delete()

            if isinstance(it, NodeItem):
                for p in list(it.ports):
                    for c in list(p.connections):
                        c.delete()

                self.scene.removeItem(it)

        self.nodes_by_id.clear()
        self.ports_by_id.clear()
        self.connections.clear()

        id2port: Dict[str, PortItem] = {}

        for nd in data.get("nodes", []):
            t = nd.get("type")
            if t == "BusBarItem":
                mode = nd.get("mode", "bar")
                item = BusBarItem(length=nd.get("length", 260.0),
                                  label=nd.get("label", "Bus"),
                                  n_ports=nd.get("n_ports", 6),
                                  mode=mode)
            elif t == "LoadItem":
                item = LoadItem()
            elif t == "GeneratorItem":
                item = GeneratorItem()
            elif t == "TransformerItem":
                item = TransformerItem()
            else:
                continue
            item.id = nd.get("id", new_id())
            px, py = nd.get("pos", [0, 0])
            item.setPos(QPointF(px, py))
            item.set_angle(nd.get("rotation", 0.0))
            # rebuild exact ports from JSON
            for p in list(item.ports):
                if p.scene():
                    self.scene.removeItem(p)
            item.ports.clear()
            for pj in nd.get("ports", []):
                rx, ry = pj["rel_pos"]
                p = item.add_port(QPointF(rx, ry))
                p.id = pj["id"]
                id2port[p.id] = p
                self.ports_by_id[p.id] = p
            self.scene.addItem(item)
            self.nodes_by_id[item.id] = item

        for cj in data.get("connections", []):
            a = id2port.get(cj["a"])
            b = id2port.get(cj["b"])
            if a and b:
                c = ConnectionItem(
                    a, b,
                    cid=cj.get("id"),
                    waypoints=cj.get("waypoints", []),
                    mode=cj.get("mode", "manhattan")
                )
                self.scene.addItem(c)
                self.connections.append(c)

        self.statusBar().showMessage(f"Loaded {path}")

    def export_svg(self):
        """

        :return:
        """
        try:
            from PySide6.QtSvg import QSvgGenerator
        except Exception:
            QMessageBox.warning(self, "SVG", "QtSvg not available in this environment.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", "", "SVG (*.svg)")
        if not path:
            return

        gen = QSvgGenerator()
        gen.setFileName(path)
        rect = self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        gen.setSize(QtCore.QSize(int(rect.width()), int(rect.height())))
        gen.setViewBox(rect)
        painter = QPainter(gen)
        self.scene.render(painter, target=QtCore.QRectF(), source=rect)
        painter.end()
        self.statusBar().showMessage(f"Exported SVG {path}")

    def export_png(self):
        """

        :return:
        """
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", "", "PNG (*.png)")
        if not path:
            return

        rect = self.scene.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        img = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        p = QPainter(img)
        self.scene.render(p, target=QtCore.QRectF(img.rect()), source=rect)
        p.end()
        img.save(path)
        self.statusBar().showMessage(f"Exported PNG {path}")


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
