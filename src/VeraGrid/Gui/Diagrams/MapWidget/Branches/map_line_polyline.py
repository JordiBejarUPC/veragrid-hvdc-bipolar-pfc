# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import TYPE_CHECKING, List

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QCursor, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsSceneContextMenuEvent, QGraphicsSceneMouseEvent

if TYPE_CHECKING:
    from VeraGrid.Gui.Diagrams.MapWidget.Branches.map_line_container import MapLineContainer


class MapLinePolyline(QGraphicsPathItem):
    """
    Interactive polyline used to represent one map line as a single selectable item.
    """

    def __init__(self, container: MapLineContainer, width: float):
        """
        Build a line polyline item.

        :param container: owner line container
        :param width: initial pen width
        """
        QGraphicsPathItem.__init__(self)
        self.container: MapLineContainer = container
        self.width: float = width

        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # Keep the selectable polyline below substations and waypoint handles,
        # so moving nodes/substations has priority over line selection.
        self.setZValue(-1.0)

    @property
    def api_object(self):
        """
        Proxy API object for selection-based workflows.
        """
        return self.container.api_object

    def set_path_points(self, points: List[QPointF]) -> None:
        """
        Replace the rendered path from ordered scene points.

        :param points: line points in scene coordinates
        """
        path = QPainterPath()
        if len(points) > 0:
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
        self.setPath(path)

    def set_width(self, width: float) -> None:
        """
        Update width while preserving color/style.

        :param width: target width
        """
        self.width = width
        pen = self.pen()
        pen.setWidthF(width)
        self.setPen(pen)

    def set_pen(self, pen: QPen) -> None:
        """
        Replace the rendering pen.

        :param pen: source pen
        """
        self.setPen(pen)
        self.width = pen.widthF()

    def shape(self) -> QPainterPath:
        """
        Return a widened stroke shape to make line picking reliable.
        """
        stroker = QPainterPathStroker()
        # Keep picking very close to the rendered stroke to avoid blocking nearby drags.
        stroker.setWidth(max(1.0, self.width * 1.15))
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return stroker.createStroke(self.path())

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Handle click by selecting and opening the line editor panel.
        """
        self.container.on_polyline_mouse_press(event)
        if event.button() == Qt.MouseButton.RightButton:
            # Keep existing multi-selection (e.g. selected substations) for context actions.
            event.accept()
            return
        QGraphicsPathItem.mousePressEvent(self, event)

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:
        """
        Delegate context menu construction to the line container.
        """
        self.container.show_context_menu(scene_pos=event.scenePos(), screen_pos=event.screenPos())
        event.accept()
