#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal power-diagram editor (PySide6)
- Drag/Drop bus bars, loads, generators, transformers
- Click-to-connect with orthogonal (Manhattan) polylines
- Selectable/clickable everything
- Save/Load diagram to/from JSON
"""

from __future__ import annotations
import json
import sys
import uuid
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QBrush, QFont, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
    QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsView, QGraphicsScene,
    QFileDialog, QMainWindow, QToolBar, QMessageBox
)

# ---------- Helpers ----------

def new_id() -> str:
    return uuid.uuid4().hex

PORT_RADIUS = 5.0
PORT_DIAM = 2 * PORT_RADIUS
PEN_NORMAL = QPen(Qt.black, 2)
PEN_FAINT = QPen(Qt.gray, 1, Qt.DashLine)
PEN_CONN   = QPen(Qt.darkBlue, 2)
BRUSH_PORT = QBrush(Qt.white)

# ---------- Tools ----------

class Tool(Enum):
    SELECT = auto()
    ADD_BUS = auto()
    ADD_LOAD = auto()
    ADD_GEN = auto()
    ADD_TRAFO = auto()
    CONNECT = auto()

# ---------- Port & Connection ----------

class PortItem(QGraphicsEllipseItem):
    """Small circular port that belongs to a parent node and accepts connections."""
    def __init__(self, parent: QGraphicsItem, rel_pos: QPointF, port_id: Optional[str] = None):
        # rel_pos: position in parent's local coordinates where the port center should be
        self.id = port_id or new_id()
        self.rel_pos = rel_pos
        super().__init__(-PORT_RADIUS, -PORT_RADIUS, PORT_DIAM, PORT_DIAM, parent)
        self.setBrush(BRUSH_PORT)
        self.setPen(PEN_NORMAL)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(10)  # above shapes
        self.connections: List["ConnectionItem"] = []
        self.update_position()

        # Make ports easy to click
        self.setAcceptHoverEvents(True)
        self._hover = False

    def update_position(self):
        self.setPos(self.rel_pos)

    def add_connection(self, c: "ConnectionItem"):
        if c not in self.connections:
            self.connections.append(c)

    def remove_connection(self, c: "ConnectionItem"):
        if c in self.connections:
            self.connections.remove(c)

    def notify_connections(self):
        for c in list(self.connections):
            c.update_path()

    def hoverEnterEvent(self, event):
        self._hover = True
        self.setBrush(Qt.yellow)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover = False
        self.setBrush(BRUSH_PORT)
        super().hoverLeaveEvent(event)

    def to_json(self) -> Dict:
        return {
            "id": self.id,
            "rel_pos": [self.rel_pos.x(), self.rel_pos.y()]
        }

# ---------- Base node that can hold ports ----------

class NodeItem(QGraphicsItem):
    """Abstract base node with movable/selectable behavior and ports."""
    def __init__(self):
        super().__init__()
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.id = new_id()
        self.ports: List[PortItem] = []

    def add_port(self, rel_pos: QPointF) -> PortItem:
        p = PortItem(self, rel_pos)
        self.ports.append(p)
        return p

    def itemChange(self, change, value):
        if change in (QGraphicsItem.ItemPositionHasChanged, QGraphicsItem.ItemTransformHasChanged):
            # when node moves, all ports' connections should update
            for p in self.ports:
                p.notify_connections()
        return super().itemChange(change, value)

    # subclasses must implement:
    def boundingRect(self) -> QRectF:
        raise NotImplementedError

    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionGraphicsItem, widget=None):
        raise NotImplementedError

    def to_json_common(self) -> Dict:
        return {
            "id": self.id,
            "type": type(self).__name__,
            "pos": [self.pos().x(), self.pos().y()],
            "ports": [p.to_json() for p in self.ports],
        }

# ---------- Specific nodes ----------

class BusBarItem(NodeItem):
    """Horizontal bar (bus) with multiple ports along its length."""
    def __init__(self, length: float = 240.0, label: str = "Bus"):
        super().__init__()
        self.length = length
        self.height = 10.0
        self.label_text = label
        self.label = QGraphicsSimpleTextItem(self.label_text, self)
        self.label.setBrush(Qt.darkRed)
        self.label.setPos(0, -22)
        # Add 6 evenly spaced ports on the lower edge
        n = 6
        for i in range(n):
            x = (i + 0.5) * (self.length / n)
            y = self.height / 2
            self.add_port(QPointF(x, y))

    def boundingRect(self) -> QRectF:
        return QRectF(0, -self.height/2, self.length, self.height)

    def paint(self, painter, option, widget=None):
        painter.setPen(PEN_NORMAL)
        painter.drawRect(self.boundingRect())

    def to_json(self) -> Dict:
        d = self.to_json_common()
        d["length"] = self.length
        d["height"] = self.height
        d["label"] = self.label_text
        return d

class RoundNode(NodeItem):
    """Base for circle-like nodes (generator, etc.)"""
    def __init__(self, radius: float = 18.0, text: str = ""):
        super().__init__()
        self.radius = radius
        self.text = QGraphicsSimpleTextItem(text, self)
        self.text.setFont(QFont("Arial", 10, QFont.Bold))
        self.text.setBrush(Qt.black)
        self.text.setPos(-self.radius/2, -self.radius - 14)

    def boundingRect(self) -> QRectF:
        r = self.radius
        return QRectF(-r, -r, 2*r, 2*r)

    def paint(self, painter, option, widget=None):
        painter.setPen(PEN_NORMAL)
        painter.setBrush(Qt.white)
        painter.drawEllipse(self.boundingRect())

class GeneratorItem(RoundNode):
    def __init__(self):
        super().__init__(20, "Gen")
        # symbol G
        self.symbol = QGraphicsSimpleTextItem("G", self)
        self.symbol.setFont(QFont("Arial", 12, QFont.Bold))
        self.symbol.setPos(-6, -9)
        # one top port
        self.add_port(QPointF(0, -self.radius))

    def to_json(self) -> Dict:
        return self.to_json_common()

class LoadItem(NodeItem):
    """Simple load symbol: triangle pointing down."""
    def __init__(self):
        super().__init__()
        self.w = 28
        self.h = 24
        # one top port
        self.add_port(QPointF(0, -self.h/2))

    def boundingRect(self) -> QRectF:
        return QRectF(-self.w/2-2, -self.h/2-2, self.w+4, self.h+6)

    def paint(self, painter, option, widget=None):
        painter.setPen(PEN_NORMAL)
        painter.setBrush(Qt.white)
        p = QPainterPath()
        p.moveTo(-self.w/2, self.h/2)
        p.lineTo(self.w/2, self.h/2)
        p.lineTo(0, -self.h/2)
        p.closeSubpath()
        painter.drawPath(p)

    def to_json(self) -> Dict:
        return self.to_json_common()

class TransformerItem(NodeItem):
    """Very simple two-coil transformer with a port on left and right."""
    def __init__(self):
        super().__init__()
        self.w = 60
        self.h = 36
        # Ports left/right mid
        self.port_left = self.add_port(QPointF(-self.w/2, 0))
        self.port_right = self.add_port(QPointF(self.w/2, 0))

    def boundingRect(self) -> QRectF:
        return QRectF(-self.w/2-4, -self.h/2-6, self.w+8, self.h+12)

    def paint(self, painter, option, widget=None):
        painter.setPen(PEN_NORMAL)
        # draw two coils (approx)
        r = 10
        x1 = -self.w/4
        x2 = self.w/4
        y0 = -self.h/4
        y1 = self.h/4
        for y in (y0, y1):
            painter.drawArc(QRectF(x1-r, y-r, 2*r, 2*r), 0, 16*180)
            painter.drawArc(QRectF(x2-r, y-r, 2*r, 2*r), 0, 16*180)
        # body
        painter.setPen(PEN_FAINT)
        painter.drawRect(-self.w/2, -self.h/2, self.w, self.h)

    def to_json(self) -> Dict:
        return self.to_json_common()

# ---------- Connection (orthogonal) ----------

def make_manhattan_path(p1: QPointF, p2: QPointF) -> QPainterPath:
    """Simple 3-segment orthogonal path between scene points p1 -> p2."""
    path = QPainterPath(p1)
    # choose middle x or y to avoid crossing shapes too much
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

class ConnectionItem(QGraphicsPathItem):
    def __init__(self, a: PortItem, b: PortItem, conn_id: Optional[str] = None):
        super().__init__()
        self.id = conn_id or new_id()
        self.a = a
        self.b = b
        self.setZValue(-1)  # behind nodes
        self.setPen(PEN_CONN)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        a.add_connection(self)
        b.add_connection(self)
        self.update_path()

    def update_path(self):
        p1 = self.a.scenePos()
        p2 = self.b.scenePos()
        self.setPath(make_manhattan_path(p1, p2))

    def delete(self):
        self.a.remove_connection(self)
        self.b.remove_connection(self)
        if self.scene():
            self.scene().removeItem(self)

    def to_json(self) -> Dict:
        return {"id": self.id, "a": self.a.id, "b": self.b.id}

# ---------- Scene & View ----------

class DiagramScene(QGraphicsScene):
    port_clicked = QtCore.Signal(PortItem)

    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), QtGui.QTransform())
        if isinstance(item, PortItem):
            self.port_clicked.emit(item)
            # also select the parent to make it feel responsive
            item.setSelected(True)
            if item.parentItem():
                item.parentItem().setSelected(True)
        super().mousePressEvent(event)

class DiagramView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

# ---------- Main Window ----------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Power Diagrammer (PySide6)")
        self.resize(1100, 700)

        self.scene = DiagramScene(self)
        self.scene.setSceneRect(-2000, -2000, 4000, 4000)
        self.scene.setBackgroundBrush(Qt.white)

        self.view = DiagramView()
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)

        self.tool: Tool = Tool.SELECT
        self.pending_port: Optional[PortItem] = None
        self.nodes_by_id: Dict[str, NodeItem] = {}
        self.ports_by_id: Dict[str, PortItem] = {}
        self.connections: List[ConnectionItem] = []

        self._build_toolbar()
        self.scene.port_clicked.connect(self._on_port_clicked)

        # grid (optional visual aid)
        self._install_grid()

    # --- UI ---

    def _build_toolbar(self):
        tb = QToolBar("Tools")
        tb.setIconSize(QtCore.QSize(22, 22))
        self.addToolBar(tb)

        def add_act(text, tool: Tool, shortcut=None):
            act = QAction(text, self)
            if shortcut:
                act.setShortcut(shortcut)
            act.triggered.connect(lambda: self._set_tool(tool))
            tb.addAction(act)
            return act

        add_act("Select [Esc]", Tool.SELECT, "Esc")
        tb.addSeparator()
        add_act("Add Bus", Tool.ADD_BUS)
        add_act("Add Load", Tool.ADD_LOAD)
        add_act("Add Gen", Tool.ADD_GEN)
        add_act("Add Trafo", Tool.ADD_TRAFO)
        add_act("Connect", Tool.CONNECT)
        tb.addSeparator()

        save_act = QAction("Save JSON", self)
        save_act.triggered.connect(self.save_json)
        tb.addAction(save_act)

        load_act = QAction("Load JSON", self)
        load_act.triggered.connect(self.load_json)
        tb.addAction(load_act)

    def _set_tool(self, tool: Tool):
        self.tool = tool
        self.pending_port = None
        if tool == Tool.SELECT:
            self.view.setDragMode(QGraphicsView.RubberBandDrag)
        else:
            self.view.setDragMode(QGraphicsView.NoDrag)
        self.statusBar().showMessage(f"Tool: {tool.name}")

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self._set_tool(Tool.SELECT)
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            for item in self.scene.selectedItems():
                if isinstance(item, ConnectionItem):
                    item.delete()
                    if item in self.connections:
                        self.connections.remove(item)
                elif isinstance(item, NodeItem):
                    # delete its connections first
                    for p in list(item.ports):
                        for c in list(p.connections):
                            c.delete()
                            if c in self.connections:
                                self.connections.remove(c)
                    if item.scene():
                        self.scene.removeItem(item)
        else:
            super().keyPressEvent(event)

    # --- Grid background ---

    def _install_grid(self):
        grid = self._make_grid_item(20, Qt.lightGray)
        self.scene.addItem(grid)
        grid.setZValue(-1000)

    def _make_grid_item(self, step: int, color: Qt.GlobalColor) -> QGraphicsPathItem:
        path = QPainterPath()
        rect = self.scene.sceneRect()
        x0 = int(rect.left())
        y0 = int(rect.top())
        x1 = int(rect.right())
        y1 = int(rect.bottom())
        for x in range(x0, x1, step):
            path.moveTo(x, y0)
            path.lineTo(x, y1)
        for y in range(y0, y1, step):
            path.moveTo(x0, y)
            path.lineTo(x1, y)
        item = QGraphicsPathItem(path)
        item.setPen(QPen(color, 0))
        item.setFlag(QGraphicsItem.ItemIsSelectable, False)
        item.setAcceptedMouseButtons(Qt.NoButton)
        return item

    # --- Scene interactions ---

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if self.tool in (Tool.ADD_BUS, Tool.ADD_LOAD, Tool.ADD_GEN, Tool.ADD_TRAFO):
            scene_pt = self.view.mapToScene(event.pos())
            self._place_node(scene_pt)
            event.accept()
            return
        super().mousePressEvent(event)

    def _place_node(self, pos: QPointF):
        item: NodeItem
        if self.tool == Tool.ADD_BUS:
            item = BusBarItem(260.0, f"Bus-{len(self.nodes_by_id)+1}")
        elif self.tool == Tool.ADD_LOAD:
            item = LoadItem()
        elif self.tool == Tool.ADD_GEN:
            item = GeneratorItem()
        elif self.tool == Tool.ADD_TRAFO:
            item = TransformerItem()
        else:
            return

        self.scene.addItem(item)
        item.setPos(pos)
        self.nodes_by_id[item.id] = item
        for p in item.ports:
            self.ports_by_id[p.id] = p

    def _on_port_clicked(self, port: PortItem):
        if self.tool != Tool.CONNECT:
            return
        if self.pending_port is None:
            self.pending_port = port
            self.statusBar().showMessage("Select second port…")
        else:
            if self.pending_port is port:
                self.pending_port = None
                return
            conn = ConnectionItem(self.pending_port, port)
            self.scene.addItem(conn)
            self.connections.append(conn)
            self.pending_port = None
            self.statusBar().showMessage("Connected.")

    # --- JSON persistence ---

    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save diagram to JSON", "", "JSON (*.json)")
        if not path:
            return
        data = {
            "nodes": [],
            "connections": [c.to_json() for c in self.connections],
        }
        for item in self.scene.items():
            if isinstance(item, NodeItem):
                if isinstance(item, BusBarItem):
                    data["nodes"].append(item.to_json())
                elif isinstance(item, (LoadItem, GeneratorItem, TransformerItem)):
                    data["nodes"].append(item.to_json())

        # Ports map (id->node, rel_pos) is already inside nodes, but we also dump absolute pos for convenience
        data["port_abs_pos"] = {
            p.id: [p.scenePos().x(), p.scenePos().y()] for p in self.ports_by_id.values()
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.statusBar().showMessage(f"Saved to {path}")

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load diagram from JSON", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read JSON:\n{e}")
            return

        # Clear current scene (except grid)
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

        # Recreate nodes
        id_to_port: Dict[str, PortItem] = {}
        for nd in data.get("nodes", []):
            t = nd.get("type")
            if t == "BusBarItem":
                item = BusBarItem(length=nd.get("length", 240.0), label=nd.get("label", "Bus"))
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
            # Remove auto ports and recreate exact ones from JSON
            for p in list(item.ports):
                if p.scene():
                    self.scene.removeItem(p)
            item.ports.clear()

            for pjson in nd.get("ports", []):
                rx, ry = pjson["rel_pos"]
                p = item.add_port(QPointF(rx, ry))
                p.id = pjson["id"]
                id_to_port[p.id] = p
                self.ports_by_id[p.id] = p

            self.scene.addItem(item)
            self.nodes_by_id[item.id] = item

        # Recreate connections
        for cj in data.get("connections", []):
            a = id_to_port.get(cj["a"])
            b = id_to_port.get(cj["b"])
            if a and b:
                c = ConnectionItem(a, b, conn_id=cj.get("id"))
                self.scene.addItem(c)
                self.connections.append(c)

        self.statusBar().showMessage(f"Loaded from {path}")

# ---------- Main ----------

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
