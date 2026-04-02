# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import numpy as np
from typing import Union, TYPE_CHECKING, List, Dict, Tuple
import webbrowser
from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QRectF, QRect, QPointF
from PySide6.QtGui import QPen, QCursor, QBrush, QColor
from PySide6.QtWidgets import QMenu, QGraphicsSceneMouseEvent, QGraphicsItem

from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.injections_template_graphics import InjectionTemplateGraphicItem
from VeraGrid.Gui.messages import yes_no_question, warning_msg
from VeraGrid.Gui.gui_functions import add_menu_entry
from VeraGrid.Gui.general_dialogues import ShortCircuitSelector
from VeraGrid.Gui.Diagrams.generic_graphics import (GenericDiagramWidget, ACTIVE, DEACTIVATED,
                                                    FONT_SCALE, TRANSPARENT)
from VeraGrid.Gui.Diagrams.SchematicWidget.terminal_item import BarTerminalItem, HandleItem, RoundTerminalItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.load_graphics import LoadGraphicItem, Load
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.generator_graphics import GeneratorGraphicItem, Generator
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.static_generator_graphics import (StaticGeneratorGraphicItem,
                                                                                        StaticGenerator)
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.battery_graphics import (BatteryGraphicItem, Battery)
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.shunt_graphics import (ShuntGraphicItem, Shunt)
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.external_grid_graphics import (ExternalGridGraphicItem,
                                                                                     ExternalGrid)
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.current_injection_graphics import (
    CurrentInjectionGraphicItem,
    CurrentInjection)
from VeraGrid.Gui.Diagrams.SchematicWidget.Injections.controllable_shunt_graphics import (
    ControllableShuntGraphicItem,
    ControllableShunt)
from VeraGrid.Gui.Diagrams.SchematicWidget.Branches.slot_geometry import (SchematicAttachmentSlot,
                                                                          build_explicit_slot_key,
                                                                          clamp_attachment_alignment,
                                                                          get_distributed_anchor,
                                                                          get_bar_slot_anchor,
                                                                          get_round_slot_anchor,
                                                                          infer_attachment_side_from_points,
                                                                          parse_explicit_slot_key)
from VeraGridEngine.enumerations import DeviceType, BusGraphicType
from VeraGridEngine.Devices.types import INJECTION_DEVICE_TYPES
from VeraGridEngine.Devices.Substation import Bus
from VeraGridEngine.Devices.Aggregation.short_cirtcuit_event import ShortCircuitEvent

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget

INJECTION_GRAPHICS = Union[
    BatteryGraphicItem,
    ShuntGraphicItem,
    ExternalGridGraphicItem,
    ControllableShuntGraphicItem,
    LoadGraphicItem,
    GeneratorGraphicItem,
    StaticGeneratorGraphicItem,
    CurrentInjectionGraphicItem
]


def get_dock_sort_key(entry: Tuple[int, int, float, float | None, bool, INJECTION_GRAPHICS]) -> Tuple[bool, int, int]:
    """
    Build the ordering key for docked child graphics.
    """
    return entry[0] == 0, entry[0], entry[1]


class ShortCircuitFlags:
    """
    Short circuit flags
    """

    def __init__(self, sc_3p: bool = False, sc_lg: bool = False, sc_ll: bool = False, sc_llg: bool = False):
        self.sc_3p = sc_3p
        self.sc_lg = sc_lg
        self.sc_ll = sc_ll
        self.sc_llg = sc_llg

    def disable_all(self):
        """

        :return:
        """
        self.sc_3p = False
        self.sc_lg = False
        self.sc_ll = False
        self.sc_llg = False


class BusGraphicItem(GenericDiagramWidget, QtWidgets.QGraphicsRectItem):
    """
      Represents a block in the diagram
      Has an x and y and width and height
      width and height can only be adjusted with a tip in the lower right corner.

      - in and output ports
      - parameters
      - description
    """

    def __init__(self,
                 parent=None,
                 index=0,
                 editor: SchematicWidget = None,
                 bus: Bus = None,
                 h: float = 40,
                 w: float = 80,
                 x: float = 0,
                 y: float = 0,
                 draw_labels: bool = True,
                 r: float = 0):
        """

        :param parent:
        :param index:
        :param editor:
        :param bus:
        :param h:
        :param w:
        :param x:
        :param y:
        """
        GenericDiagramWidget.__init__(self, parent=parent, api_object=bus, editor=editor, draw_labels=draw_labels)
        QtWidgets.QGraphicsRectItem.__init__(self, parent)

        # Label:
        self.label = QtWidgets.QGraphicsTextItem(self.api_object.name if self.api_object is not None else "", self)
        self.label.setDefaultTextColor(ACTIVE['text'])
        self.label.setScale(FONT_SCALE)

        # loads, shunts, generators, etc...
        self._child_graphics: List[INJECTION_GRAPHICS] = list()

        # index
        self.index = index

        self.big_marker = None

        self.connectivity_graph = False

        # connection terminals the block
        if self.api_object.graphic_type == BusGraphicType.BusBar:
            self._terminal = BarTerminalItem('s', parent=self, editor=self.editor)
            self.min_w = 180.0
            self.min_h = 40.0
            self.offset = 20

            self.h = h if h >= self.min_h else self.min_h
            self.w = w if w >= self.min_w else self.min_w
            self.r = r

            # square
            self.tile = QtWidgets.QGraphicsRectItem(0, 0, 20, 20, self)
            self.tile.setOpacity(0.7)

            # Create corner for resize:
            self.sizer = HandleItem(self._terminal, callback=self.change_size)
            self.sizer.setPos(self.w, self.h)
            self.sizer.setFlag(self.GraphicsItemFlag.ItemIsMovable)

        elif self.api_object.graphic_type == BusGraphicType.Connectivity:
            self._terminal = RoundTerminalItem('s', parent=self, editor=self.editor, h=20, w=20)  # , h=self.h))
            self.min_w = 50.0
            self.min_h = 50.0
            self.offset = 20

            self.h = h if h >= self.min_h else self.min_h
            self.w = w if w >= self.min_w else self.min_w
            self.r = r

            self._terminal.setPos(self.w / 2 - self._terminal.w / 2, self.h / 2 - self._terminal.h / 2)
            # self._terminal.setPos(self.w / 2 + 10, self.h / 2 + 10)

            # square
            self.tile = QtWidgets.QGraphicsRectItem(0, 0, 5, 5, self)
            self.tile.setOpacity(1.0)

            # Create corner for resize:
            self.sizer = None

            self.connectivity_graph = True

        else:
            self._terminal = BarTerminalItem('s', parent=self, editor=self._editor)
            self.min_w = 180.0
            self.min_h = 40.0
            self.offset = 20

            self.h = h if h >= self.min_h else self.min_h
            self.w = w if w >= self.min_w else self.min_w
            self.r = r

            # square
            self.tile = QtWidgets.QGraphicsRectItem(0, 0, 20, 20, self)
            self.tile.setOpacity(0.7)

            # Create corner for resize:
            self.sizer = HandleItem(self._terminal, callback=self.change_size)
            self.sizer.setPos(self.w, self.h)
            self.sizer.setFlag(self.GraphicsItemFlag.ItemIsMovable)

        self.y0 = self.h + 40  # y position of the shunt element icons

        # Enabled for short circuit
        self.pen_width = 4

        self._terminal.setPen(QPen(TRANSPARENT, self.pen_width, self.style,
                                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        self.set_tile_color(self.color)

        self.setPen(QPen(TRANSPARENT, self.pen_width, self.style))
        self.setBrush(TRANSPARENT)
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Update size:
        self.change_size(w=self.w)

        self.set_position(x, y)
        self.apply_rotation_state(refresh_geometry=False)

    @property
    def api_object(self) -> Bus:
        """

        :return:
        """
        return self._api_object

    @property
    def editor(self) -> SchematicWidget:
        """

        :return:
        """
        return self._editor

    @property
    def terminal(self):
        """

        :return:
        """
        return self._terminal

    def get_associated_branch_graphics(self) -> List[GenericDiagramWidget]:
        """
        Get a list of all associated branch graphics
        :return:
        """
        conn: List[GenericDiagramWidget | INJECTION_GRAPHICS] = self._terminal.get_hosted_graphics()

        return conn

    def get_associated_shunt_graphics(self) -> List[INJECTION_GRAPHICS]:
        """
        List of associated shunt graphics
        :return:
        """
        return self._child_graphics

    def get_associated_widgets(self) -> List[GenericDiagramWidget | INJECTION_GRAPHICS]:
        """
        Get a list of all associated graphics
        :return:
        """
        conn: List[GenericDiagramWidget | INJECTION_GRAPHICS] = self.get_associated_branch_graphics()

        for graphics in self._child_graphics:
            conn.append(graphics)
            conn.append(graphics.nexus)

        return conn

    def get_extra_graphics(self) -> List[QGraphicsItem]:
        return self.get_associated_widgets()

    def get_nexus_point(self) -> QPointF:
        """
        Get the connection point for the children nexus line
        (connection points for loads, shunts, generators, etc.)
        :return: QPointF
        """
        return self.get_terminal_anchor_by_key(terminal_key=SchematicAttachmentSlot.BOTTOM.value,
                                               alignment=0.5)

    def get_nexus_point_for_child(self, child_graphic: INJECTION_GRAPHICS) -> QPointF:
        """
        Get the connection point for one docked child graphic.
        """
        dock = self._editor.diagram.get_dock(child_graphic.api_object)
        side = str(dock.get("side", SchematicAttachmentSlot.BOTTOM.value))
        alignment_value = dock.get("nexus_parent_alignment", dock.get("alignment", None))

        if alignment_value is None:
            child_center_x: float = child_graphic.pos().x() + child_graphic.w * 0.5
            child_center_y: float = child_graphic.pos().y() + child_graphic.h * 0.5

            if side in (SchematicAttachmentSlot.TOP.value,
                        SchematicAttachmentSlot.BOTTOM.value,
                        SchematicAttachmentSlot.DEFAULT.value):
                if self.rect().width() <= 0.0:
                    alignment_value = 0.5
                else:
                    alignment_value = clamp_attachment_alignment(child_center_x / self.rect().width())
            else:
                if self.rect().height() <= 0.0:
                    alignment_value = 0.5
                else:
                    alignment_value = clamp_attachment_alignment(child_center_y / self.rect().height())
        else:
            alignment_value = clamp_attachment_alignment(alignment_value)

        return self.get_terminal_anchor_by_key(terminal_key=side,
                                               alignment=alignment_value)

    def recolour_mode(self) -> None:
        """
        Change the colour according to the system theme
        """
        super().recolour_mode()

        self.label.setDefaultTextColor(ACTIVE['text'])
        self.set_tile_color(self.color)

        for e in self._child_graphics:
            if e is not None:
                e.recolour_mode()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """
        On mouse move of this object...
        Args:
            event: QGraphicsSceneMouseEvent inherited
        """
        super().mouseMoveEvent(event)
        self._editor.update_diagram_element(device=self.api_object,
                                            x=self.pos().x(),
                                            y=self.pos().y(),
                                            w=self.w,
                                            h=self.h,
                                            r=self.rotation(),
                                            draw_labels=self.draw_labels,
                                            graphic_object=self)

    def add_big_marker(self, color: Union[None, QColor] = QColor(255, 0, 0, 255), tool_tip_text: str = ""):
        """
        Add a big marker to the bus
        :param color: Qt Color ot the marker
        :param tool_tip_text: tool tip text to display
        """
        if color is not None:
            if self.big_marker is None:
                self.big_marker = QtWidgets.QGraphicsEllipseItem(0, 0, 180, 180, parent=self)

            self.big_marker.setBrush(color)
            self.big_marker.setOpacity(0.5)
            self.big_marker.setToolTip(tool_tip_text)

    def delete_big_marker(self) -> None:
        """
        Delete the big marker
        """
        if self.big_marker is not None:
            self._editor._remove_from_scene(self.big_marker)
            self.big_marker = None

    def set_position(self, x: float, y: float) -> None:
        """
        Set the bus x, y position
        :param x: x in pixels
        :param y: y in pixels
        """
        if np.isnan(x):
            x = 0.0
        if np.isnan(y):
            y = 0.0
        self.setPos(QPointF(x, y))

    def set_tile_color(self, brush: QBrush | QColor) -> None:
        """
        Set the color of the bus
        Args:
            brush:  Qt Color
        """
        if self.tile is not None:
            self.tile.setBrush(brush)
        self._terminal.setBrush(brush)

    def merge(self, other_bus_graphic: "BusGraphicItem") -> None:
        """
        Merge another BusGraphicItem into this
        :param other_bus_graphic: BusGraphicItem
        """
        self._child_graphics += other_bus_graphic._child_graphics

    def update(self, rect: Union[QRectF, QRect] = ...):
        """
        Update the object
        :return:
        """
        self.change_size(w=self.w)

    def set_height(self, h: int):
        """
        Set the height of the
        :param h:
        :return:
        """
        self.setRect(0.0, 0.0, self.w, h)
        self.h = h

    def get_terminal_center(self, val: QPointF) -> QPointF:
        """
        Get the center of the terminal
        :param val: position of a branch point
        :return:
        """
        return self._terminal.get_center_pos(val)

    def change_size(self, w: int | float, dummy: float = 0.0):
        """
        Resize block function
        :param w:
        :param dummy:
        :return:
        """
        # Limit the block size to the minimum size:
        self.w = w if w > self.min_w else self.min_w
        self.setRect(0.0, 0.0, self.w, self.min_h)
        y0 = self.offset
        x0 = 0

        # center label:
        self.label.setPos(self.w + 5, -20)

        # lower
        if not self.connectivity_graph:
            self._terminal.setPos(x0, y0)
            self._terminal.setRect(0, 20, self.w, 10)
        else:
            pass

        # Keep the rotation pivot aligned with the electrical connection bar.
        self.setTransformOriginPoint(self.get_rotation_origin_local_point())
        self.setRotation(self.r)

        # rearrange children
        self.arrange_children()

        # update editor diagram position
        self._editor.update_diagram_element(device=self.api_object,
                                            x=self.pos().x(),
                                            y=self.pos().y(),
                                            w=self.w,
                                            h=int(self.min_h),
                                            r=self.rotation(),
                                            draw_labels=self.draw_labels,
                                            graphic_object=self)

        return self.w, self.min_h

    def get_rotation_origin_local_point(self) -> QPointF:
        """
        Return the local rotation origin used for saved/loadable bus orientation.

        Bar-style buses rotate around the terminal bar centerline so branch anchors
        and docked children keep following the electrical bar instead of the body
        rectangle corners.

        :return: Local rotation origin.
        """
        if self.connectivity_graph:
            return self.rect().center()
        else:
            pass

        terminal_y: float = self._terminal.pos().y() + self._terminal.rect().y()
        terminal_h: float = self._terminal.rect().height()
        return QPointF(self.rect().width() * 0.5,
                       terminal_y + terminal_h * 0.5)

    def apply_rotation_state(self, refresh_geometry: bool) -> None:
        """
        Apply the persisted rotation state to the live graphics item.

        :param refresh_geometry: Refresh attached routes and docked children afterwards.
        :return: ``None``.
        """
        self.setTransformOriginPoint(self.get_rotation_origin_local_point())
        self.setRotation(self.r)

        if refresh_geometry:
            self.refresh_connected_geometry_after_rotation()
        else:
            pass

    def refresh_connected_geometry_after_rotation(self) -> None:
        """
        Refresh docked children and attached branches after one rotation change.

        :return: ``None``.
        """
        self.arrange_children()
        self._terminal.update()
        self._terminal.process_callbacks(self._terminal.scenePos())
        self.auto_assign_branch_slots()

        branch_graphic: GenericDiagramWidget

        for branch_graphic in self.get_associated_branch_graphics():
            branch_graphic.update_ports()
            branch_graphic.load_route_points_from_diagram()
            branch_graphic.redraw()

    def set_rotation_angle(self, angle_degrees: float, persist: bool) -> None:
        """
        Set one persisted bus rotation angle.

        :param angle_degrees: Rotation angle in degrees.
        :param persist: Update the backing diagram location.
        :return: ``None``.
        """
        normalized_angle: float = float(angle_degrees) % 360.0
        self.r = normalized_angle
        self.apply_rotation_state(refresh_geometry=True)

        if persist:
            self._editor.update_diagram_element(device=self._api_object,
                                                x=self.pos().x(),
                                                y=self.pos().y(),
                                                w=self.w,
                                                h=self.h,
                                                r=self.r,
                                                draw_labels=self.draw_labels,
                                                graphic_object=self)
        else:
            pass

    def arrange_children(self) -> None:
        """
        This function sorts the load and generators icons
        Returns:
            Nothing
        """
        dock_groups: Dict[str, List[Tuple[int, int, float, float | None, bool, INJECTION_GRAPHICS]]] = {
            SchematicAttachmentSlot.TOP.value: list(),
            SchematicAttachmentSlot.BOTTOM.value: list(),
            SchematicAttachmentSlot.LEFT.value: list(),
            SchematicAttachmentSlot.RIGHT.value: list(),
        }
        child_index: int

        for child_index, elm in enumerate(self._child_graphics):
            dock = self._editor.diagram.sync_injection_dock(api_object=elm.api_object,
                                                            owner_device=self.api_object,
                                                            side=SchematicAttachmentSlot.BOTTOM.value)
            side = str(dock.get("side", SchematicAttachmentSlot.BOTTOM.value))
            order = int(dock.get("order", 0))
            offset = float(dock.get("offset", 0.0))
            alignment = dock.get("alignment", None)
            auto_layout = bool(dock.get("auto_layout", True))

            if side not in dock_groups:
                side = SchematicAttachmentSlot.BOTTOM.value
            else:
                pass

            dock_groups[side].append((order, child_index, offset, alignment, auto_layout, elm))

        self._arrange_child_group(side=SchematicAttachmentSlot.TOP.value,
                                  dock_entries=dock_groups[SchematicAttachmentSlot.TOP.value])
        self._arrange_child_group(side=SchematicAttachmentSlot.BOTTOM.value,
                                  dock_entries=dock_groups[SchematicAttachmentSlot.BOTTOM.value])
        self._arrange_child_group(side=SchematicAttachmentSlot.LEFT.value,
                                  dock_entries=dock_groups[SchematicAttachmentSlot.LEFT.value])
        self._arrange_child_group(side=SchematicAttachmentSlot.RIGHT.value,
                                  dock_entries=dock_groups[SchematicAttachmentSlot.RIGHT.value])

        # Arrange line positions
        self._terminal.process_callbacks(self.pos() + self._terminal.pos())

    def _arrange_child_group(self,
                             side: str,
                             dock_entries: List[Tuple[int, int, float, float | None, bool, INJECTION_GRAPHICS]]) -> None:
        """
        Arrange one dock side of child graphics.
        """
        if len(dock_entries) == 0:
            return
        else:
            pass

        sorted_entries = sorted(dock_entries, key=get_dock_sort_key)
        slot_count: int = len(sorted_entries)
        slot_index: int

        for slot_index, (_, _, offset, alignment, auto_layout, elm) in enumerate(sorted_entries, start=1):
            if auto_layout:
                span_fraction: float = float(slot_index) / float(slot_count + 1)
            else:
                span_fraction = clamp_attachment_alignment(alignment)

            if side == SchematicAttachmentSlot.TOP.value:
                x_pos = self.w * span_fraction - elm.w * 0.5
                y_pos = -elm.h - 40.0 - offset
            elif side == SchematicAttachmentSlot.LEFT.value:
                x_pos = -elm.w - 40.0 - offset
                y_pos = self.rect().height() * span_fraction - elm.h * 0.5
            elif side == SchematicAttachmentSlot.RIGHT.value:
                x_pos = self.w + 40.0 + offset
                y_pos = self.rect().height() * span_fraction - elm.h * 0.5
            else:
                x_pos = self.w * span_fraction - elm.w * 0.5
                y_pos = self.y0 + offset

            elm.setPos(x_pos, y_pos)
            elm.update_nexus(elm.pos())

    def get_bottom_dock_baseline(self) -> float:
        """
        Return the baseline local Y coordinate used for bottom-docked children.

        :return: Bottom dock baseline.
        """
        return float(self.y0)

    def create_children_widgets(self, injections_by_tpe: Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]):
        """
        Create the icons of the elements that are attached to the API bus object
        Returns: Nothing
        """

        for tpe, dev_list in injections_by_tpe.items():

            if tpe == DeviceType.LoadDevice:
                for elm in dev_list:
                    self.add_load(elm)

            elif tpe == DeviceType.StaticGeneratorDevice:
                for elm in dev_list:
                    self.add_static_generator(elm)

            elif tpe == DeviceType.GeneratorDevice:
                for elm in dev_list:
                    self.add_generator(elm)

            elif tpe == DeviceType.ShuntDevice:
                for elm in dev_list:
                    self.add_shunt(elm)

            elif tpe == DeviceType.BatteryDevice:
                for elm in dev_list:
                    self.add_battery(elm)

            elif tpe == DeviceType.ExternalGridDevice:
                for elm in dev_list:
                    self.add_external_grid(elm)

            elif tpe == DeviceType.CurrentInjectionDevice:
                for elm in dev_list:
                    self.add_current_injection(elm)

            elif tpe == DeviceType.ControllableShuntDevice:
                for elm in dev_list:
                    self.add_controllable_shunt(elm)

            else:
                raise Exception("Unknown device type:" + str(tpe))

        self.arrange_children()

    def contextMenuEvent(self, event: QtWidgets.QGraphicsSceneContextMenuEvent):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = QMenu()
        menu.addSection("Bus")

        add_menu_entry(menu=menu,
                       text="Active",
                       icon_path="",
                       function_ptr=self.enable_disable_toggle,
                       checkeable=True,
                       checked_value=self.api_object.active)

        add_menu_entry(menu=menu,
                       text="Draw labels",
                       icon_path="",
                       function_ptr=self.enable_disable_label_drawing,
                       checkeable=True,
                       checked_value=self.draw_labels)

        add_menu_entry(menu=menu,
                       text="add Short circuit",
                       icon_path=":/Icons/icons/short_circuit_plus.png",
                       function_ptr=self.add_short_circuit)

        add_menu_entry(menu=menu,
                       text="Is a DC bus",
                       icon_path=":/Icons/icons/dc.png",
                       function_ptr=self.enable_disable_dc,
                       checkeable=True,
                       checked_value=self.api_object.is_dc)

        add_menu_entry(menu=menu,
                       text="Plot profiles",
                       icon_path=":/Icons/icons/plot.png",
                       function_ptr=self.plot_profiles)

        add_menu_entry(menu,
                       text='Arrange',
                       icon_path=":/Icons/icons/automatic_layout.png",
                       function_ptr=self.arrange_children)

        add_menu_entry(menu,
                       text='Rotate 90',
                       icon_path=":/Icons/icons/rotate.svg",
                       function_ptr=self.rotate)

        add_menu_entry(menu,
                       text='Assign active state to profile',
                       icon_path=":/Icons/icons/assign_to_profile.png",
                       function_ptr=self.assign_status_to_profile)

        add_menu_entry(menu, text='Delete',
                       icon_path=":/Icons/icons/delete_schematic.png",
                       function_ptr=self.delete)

        add_menu_entry(menu, text='Convert to voltage level',
                       icon_path=":/Icons/icons/voltage_level.png",
                       function_ptr=self.convert_to_voltage_level)

        add_menu_entry(menu, text='Convert to impedances circuit',
                       icon_path=":/Icons/icons/voltage_level.png",
                       function_ptr=self.convert_to_connectivity_grid)

        add_menu_entry(menu, text='Expand schematic',
                       icon_path=":/Icons/icons/grid_icon.png",
                       function_ptr=self.expand_diagram_from_bus)

        add_menu_entry(menu, text='Vicinity diagram from here',
                       icon_path=":/Icons/icons/grid_icon.png",
                       function_ptr=self.new_vicinity_diagram_from_here)

        add_menu_entry(menu=menu,
                       text="Open in street view",
                       icon_path=":/Icons/icons/map.png",
                       function_ptr=self.open_street_view)

        menu.addSection("Add")

        # Actions under the "Add" section
        add_menu_entry(menu, text='Load',
                       icon_path=":/Icons/icons/add_load.png",
                       function_ptr=self.add_load)

        add_menu_entry(menu, text='Current injection',
                       icon_path=":/Icons/icons/add_load.png",
                       function_ptr=self.add_current_injection)

        add_menu_entry(menu, text='Shunt',
                       icon_path=":/Icons/icons/add_shunt.png",
                       function_ptr=self.add_shunt)

        add_menu_entry(menu,
                       text='Controllable shunt',
                       icon_path=":/Icons/icons/add_shunt.png",
                       function_ptr=self.add_controllable_shunt)

        add_menu_entry(menu, text='Generator',
                       icon_path=":/Icons/icons/add_gen.png",
                       function_ptr=self.add_generator)

        add_menu_entry(menu, text='Static generator',
                       icon_path=":/Icons/icons/add_stagen.png",
                       function_ptr=self.add_static_generator)

        add_menu_entry(menu, text='Battery',
                       icon_path=":/Icons/icons/add_batt.png",
                       function_ptr=self.add_battery)

        add_menu_entry(menu,
                       text='External grid',
                       icon_path=":/Icons/icons/add_external_grid.png",
                       function_ptr=self.add_external_grid)

        menu.exec_(event.screenPos())

    def assign_status_to_profile(self):
        """
        Assign the snapshot rate to the profile
        """
        self._editor.set_active_status_to_profile(self.api_object)

    def delete(self) -> None:
        """
        Remove this element
        @return:
        """
        deleted, delete_from_db_final = self.editor.delete_with_dialogue(selected=[self], delete_from_db=False)
        if deleted:
            self._terminal.clear()

    def delete_child(self, obj: INJECTION_GRAPHICS | InjectionTemplateGraphicItem):
        """
        Delete a child object
        :param obj:
        """
        self._child_graphics.remove(obj)

    def update_color(self):
        """
        Update the colour
        """
        if self.api_object.active:
            self.set_tile_color(QBrush(ACTIVE['color']))
        else:
            self.set_tile_color(QBrush(DEACTIVATED['color']))

    def convert_to_voltage_level(self) -> None:
        """
        Open the voltage level conversion wizard
        """
        self.editor.convert_busbar_to_voltage_level(bus_graphics=self)

    def convert_to_connectivity_grid(self) -> None:
        """
        Transform this bus into a grid of buses to be able to compute the bus currents
        and delete this bus afterward
        """
        self.editor.transform_busbar_to_connectivity_grid(bus_graphics=self)

    def expand_diagram_from_bus(self) -> None:
        """
        Expands the diagram from this bus
        """
        self._editor.expand_diagram_from_bus(root_bus=self.api_object)

    def new_vicinity_diagram_from_here(self):
        """
        Create new vicinity diagram
        :return:
        """
        if self.api_object is not None:
            self.editor.gui.new_bus_branch_diagram_from_bus(root_bus=self.api_object)
        else:
            warning_msg("The api object is none :(")

    def enable_disable_toggle(self):
        """
        Toggle bus element state
        @return:
        """
        if self.api_object is not None:

            # change the bus state (snapshot)
            self.api_object.active = not self.api_object.active

            # change the Branches state (snapshot)
            for host in self._terminal.hosting_connections:
                if host.api_object is not None:
                    host.set_enable(val=self.api_object.active)

            if not self.api_object.active:
                self.clear_label()

            self.update_color()

            if self._editor.circuit.has_time_series:
                ok = yes_no_question('Do you want to update the time series active status accordingly?',
                                     'Update time series active status')

                if ok:
                    # change the bus state (time series)
                    self._editor.set_active_status_to_profile(self.api_object, override_question=True)

                    # change the Branches state (time series)
                    for host in self._terminal.hosting_connections:
                        if host.api_object is not None:
                            self._editor.set_active_status_to_profile(host.api_object, override_question=True)

    def add_short_circuit(self) -> None:
        """
        Enable 3-phase short circuit
        """
        self.w = ShortCircuitSelector()
        self.w.exec()

        if self.w.was_accepted:
            sc = ShortCircuitEvent(
                name=f"{self.api_object.name} {self.w.fault.value}",
                device=self.api_object,
                fault_type=self.w.fault,
                method=self.w.method,
                phases=self.w.phases
            )

            self.editor.circuit.add_short_circuit_event(sc)

    def enable_disable_dc(self):
        """
        Activates or deactivates the bus as a DC bus
        """
        if self._api_object.is_dc:
            self._api_object.is_dc = False
        else:
            self._api_object.is_dc = True

    def rotate(self):
        """

        :return:
        """
        self.set_rotation_angle(angle_degrees=self.r + 90.0,
                                persist=True)

    def plot_profiles(self) -> None:
        """
        Plot profiles
        """
        # get the index of this object
        i = self._editor.circuit.get_buses().index(self._api_object)
        self._editor.plot_bus(i, self._api_object)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param event: QGraphicsSceneMouseEvent
        """

        if self._api_object.device_type == DeviceType.BusDevice:
            self._editor.set_editor_model(api_object=self._api_object)

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent):
        """
        Mouse double click
        :param event: event object
        """
        title = self._api_object.name if self._api_object is not None else ""
        msg = ""
        self.label.setHtml(f'<html><head/><body><p><span style=" font-size:10pt;">{title}<br/></span>'
                           f'<span style=" font-size:6pt;">{msg}</span></p></body></html>')

        self.setToolTip(msg)

    def get_terminal(self) -> BarTerminalItem:
        """
        Get the hosting terminal of this bus object
        :return: TerminalItem
        """
        return self._terminal

    def get_terminal_slots(self) -> Dict[str, Dict[str, str]]:
        """
        Compatibility catalog for named bus attachment slots.
        """
        slots: Dict[str, Dict[str, str]] = {
            SchematicAttachmentSlot.DEFAULT.value: {"terminal_key": SchematicAttachmentSlot.DEFAULT.value,
                                                    "side": SchematicAttachmentSlot.DEFAULT.value},
            SchematicAttachmentSlot.LEFT.value: {"terminal_key": SchematicAttachmentSlot.LEFT.value,
                                                 "side": SchematicAttachmentSlot.LEFT.value},
            SchematicAttachmentSlot.RIGHT.value: {"terminal_key": SchematicAttachmentSlot.RIGHT.value,
                                                  "side": SchematicAttachmentSlot.RIGHT.value},
            SchematicAttachmentSlot.TOP.value: {"terminal_key": SchematicAttachmentSlot.TOP.value,
                                                "side": SchematicAttachmentSlot.TOP.value},
            SchematicAttachmentSlot.BOTTOM.value: {"terminal_key": SchematicAttachmentSlot.BOTTOM.value,
                                                   "side": SchematicAttachmentSlot.BOTTOM.value},
        }

        explicit_slots: Dict[str, Dict[str, str]] = self.get_explicit_terminal_slots()
        slot_key: str

        for slot_key, slot_data in explicit_slots.items():
            slots[slot_key] = slot_data

        return slots

    def get_explicit_terminal_slots(self) -> Dict[str, Dict[str, str]]:
        """
        Build the explicit slot catalog currently attached to this bus.
        """
        slots: Dict[str, Dict[str, str]] = dict()
        side_key: str

        for side_key in (
            SchematicAttachmentSlot.LEFT.value,
            SchematicAttachmentSlot.RIGHT.value,
            SchematicAttachmentSlot.TOP.value,
            SchematicAttachmentSlot.BOTTOM.value,
        ):
            order: int

            for order in self.get_explicit_slot_orders(side_key=side_key):
                slot_key: str = build_explicit_slot_key(owner_kind="bus", side=side_key, order=order)
                slots[slot_key] = {"terminal_key": slot_key, "side": side_key}

        return slots

    @staticmethod
    def get_default_terminal_key(endpoint: str | None = None) -> str:
        """
        Return the compatibility slot key for a branch endpoint.
        """
        if endpoint == "from":
            return SchematicAttachmentSlot.RIGHT.value
        if endpoint == "to":
            return SchematicAttachmentSlot.LEFT.value
        return SchematicAttachmentSlot.DEFAULT.value

    def get_terminal_anchor_by_key(self,
                                   terminal_key: str = "default",
                                   graphic_object: GenericDiagramWidget | INJECTION_GRAPHICS | None = None,
                                   alignment: float | None = None) -> QPointF:
        """
        Resolve the scene anchor point for a named attachment slot.
        """
        local_x: float
        local_y: float
        terminal_y: float = self._terminal.pos().y() + self._terminal.rect().y()
        terminal_h: float = self._terminal.rect().height()
        explicit_slot = parse_explicit_slot_key(slot_key=terminal_key)

        if explicit_slot is not None:
            _, side_key, order = explicit_slot
            explicit_entries = self.get_explicit_slot_entries(side_key=side_key)

            if graphic_object is not None:
                if not any(entry[2] is graphic_object for entry in explicit_entries):
                    explicit_entries.append((order, str(id(graphic_object.api_object)), graphic_object))
                else:
                    pass
            else:
                pass

            explicit_entries.sort(key=lambda entry: (entry[0], entry[1]))
            slot_count: int = len(explicit_entries)

            if graphic_object is not None and slot_count > 0:
                order_index = next(index + 1 for index, entry in enumerate(explicit_entries) if entry[2] is graphic_object)
            else:
                ordered_slots: List[int] = [entry[0] for entry in explicit_entries]
                order_index = ordered_slots.index(order) + 1

            local_x, local_y = get_distributed_anchor(side=side_key,
                                                      width=self.rect().width(),
                                                      height=self.rect().height(),
                                                      terminal_y=terminal_y,
                                                      terminal_h=terminal_h,
                                                      order_index=order_index,
                                                      slot_count=slot_count,
                                                      alignment=alignment)
            return self.mapToScene(QPointF(local_x, local_y))
        else:
            pass

        if self.connectivity_graph:
            local_x, local_y = get_round_slot_anchor(width=self.rect().width(),
                                                     height=self.rect().height(),
                                                     slot_key=terminal_key,
                                                     alignment=alignment)
        else:
            local_x, local_y = get_bar_slot_anchor(width=self.w,
                                                   terminal_y=terminal_y,
                                                   terminal_h=terminal_h,
                                                   slot_key=terminal_key,
                                                   alignment=alignment)

        return self.mapToScene(QPointF(local_x, local_y))

    def get_terminal_alignment_from_scene_point(self, side_key: str, scene_point: QPointF) -> float:
        """
        Convert one scene point to a normalized alignment value on the requested side.

        :param side_key: Attachment side.
        :param scene_point: Scene point selected by the user.
        :return: Normalized alignment factor.
        """
        local_point: QPointF = self.mapFromScene(scene_point)

        if side_key in (SchematicAttachmentSlot.TOP.value,
                        SchematicAttachmentSlot.BOTTOM.value,
                        SchematicAttachmentSlot.DEFAULT.value):
            span_value = self.rect().width()
            coordinate = local_point.x()
        else:
            span_value = self.rect().height()
            coordinate = local_point.y()

        if span_value <= 0.0:
            return 0.5
        else:
            pass

        alignment = coordinate / span_value

        if alignment < 0.0:
            return 0.0
        elif alignment > 1.0:
            return 1.0
        else:
            return float(alignment)

    def get_explicit_slot_orders(self, side_key: str) -> List[int]:
        """
        Collect persisted explicit slot orders for this graphic on one side.
        """
        orders: List[int] = list()
        explicit_entries = self.get_explicit_slot_entries(side_key=side_key)
        entry: Tuple[int, str, GenericDiagramWidget | INJECTION_GRAPHICS]

        for entry in explicit_entries:
            orders.append(entry[0])

        return orders

    def get_explicit_slot_entries(self,
                                  side_key: str) -> List[Tuple[int, str, GenericDiagramWidget | INJECTION_GRAPHICS]]:
        """
        Collect persisted explicit slot entries for this graphic on one side.
        """
        entries: List[Tuple[int, str, GenericDiagramWidget | INJECTION_GRAPHICS]] = list()
        branch_graphics: List[GenericDiagramWidget | INJECTION_GRAPHICS] = self.get_associated_branch_graphics()
        graphic_object: GenericDiagramWidget | INJECTION_GRAPHICS

        for graphic_object in branch_graphics:
            endpoint: str = self.get_branch_endpoint_for_graphic(graphic_object)

            if endpoint == "":
                pass
            else:
                attachment = self.editor.get_persisted_attachment(api_object=graphic_object.api_object, endpoint=endpoint)
                terminal_key = str(attachment.get("terminal_key", ""))
                explicit_slot = parse_explicit_slot_key(slot_key=terminal_key)

                if explicit_slot is None:
                    pass
                elif explicit_slot[1] != side_key:
                    pass
                else:
                    entries.append((explicit_slot[2], str(id(graphic_object.api_object)), graphic_object))

        return entries

    def has_duplicate_explicit_slot_order(self, side_key: str, order: int) -> bool:
        """
        Check whether an explicit slot order is duplicated on one side.
        """
        count: int = 0
        entry: Tuple[int, str, GenericDiagramWidget | INJECTION_GRAPHICS]

        for entry in self.get_explicit_slot_entries(side_key=side_key):
            if entry[0] == order:
                count += 1
            else:
                pass

        return count > 1

    def get_branch_endpoint_for_graphic(self, graphic_object: GenericDiagramWidget | INJECTION_GRAPHICS) -> str:
        """
        Determine which endpoint of a branch graphic is attached to this node.
        """
        from_parent = graphic_object.get_terminal_from_parent()
        to_parent = graphic_object.get_terminal_to_parent()

        if from_parent is self:
            return "from"
        elif to_parent is self:
            return "to"
        else:
            return ""

    def get_branch_attachment_center(self) -> QPointF:
        """
        Get the scene center used to infer branch attachment sides.
        """
        if self.connectivity_graph:
            local_point = QPointF(self.rect().width() * 0.5, self.rect().height() * 0.5)
        else:
            terminal_y: float = self._terminal.pos().y() + self._terminal.rect().y()
            terminal_h: float = self._terminal.rect().height()
            local_point = QPointF(self.w * 0.5, terminal_y + terminal_h * 0.5)

        return self.mapToScene(local_point)

    def infer_branch_slot_side_and_sort_value(self, other_point: QPointF) -> Tuple[str, float]:
        """
        Infer the attachment side and sorting coordinate for one connected branch.

        Bar-style buses are routed as vertical feeders by default, so they only use
        ``top`` and ``bottom`` during automatic legacy migration. Connectivity nodes
        still use all four sides.
        """
        local_other_point: QPointF = self.mapFromScene(other_point)
        local_center_x: float = self.rect().width() * 0.5
        terminal_y: float = self._terminal.pos().y() + self._terminal.rect().y()
        terminal_h: float = self._terminal.rect().height()
        local_center_y: float = terminal_y + terminal_h * 0.5
        side_key: str
        sort_value: float

        if self.connectivity_graph:
            side_key = infer_attachment_side_from_points(origin=(local_center_x, local_center_y),
                                                         other=(local_other_point.x(), local_other_point.y()),
                                                         vertical_bias=1.0)

            if side_key in (SchematicAttachmentSlot.TOP.value, SchematicAttachmentSlot.BOTTOM.value):
                sort_value = float(local_other_point.x())
            else:
                sort_value = float(local_other_point.y())
        else:
            if local_other_point.y() < local_center_y:
                side_key = SchematicAttachmentSlot.TOP.value
            else:
                side_key = SchematicAttachmentSlot.BOTTOM.value

            sort_value = float(local_other_point.x())

        return side_key, sort_value

    def auto_assign_branch_slots(self) -> None:
        """
        Assign deterministic explicit slots to attached branches from current geometry.
        """
        grouped_entries: Dict[str, List[Tuple[float, str, GenericDiagramWidget, str, Dict[str, str]]]] = {
            SchematicAttachmentSlot.LEFT.value: list(),
            SchematicAttachmentSlot.RIGHT.value: list(),
            SchematicAttachmentSlot.TOP.value: list(),
            SchematicAttachmentSlot.BOTTOM.value: list(),
        }
        branch_graphic: GenericDiagramWidget

        for branch_graphic in self.get_associated_branch_graphics():
            endpoint: str = self.get_branch_endpoint_for_graphic(branch_graphic)

            if endpoint == "":
                continue
            else:
                pass

            attachment = self.editor.get_persisted_attachment(api_object=branch_graphic.api_object, endpoint=endpoint)
            has_saved_endpoint_state = any(key in attachment for key in ("side", "slot", "terminal_key", "alignment", "order"))

            if self.editor.is_loading_diagram():
                if has_saved_endpoint_state:
                    continue
                else:
                    pass
            else:
                pass

            existing_slot = str(attachment.get("slot", ""))
            auto_slot = bool(attachment.get("auto_slot", existing_slot in ("", "default", "left", "right", "top", "bottom")))

            if not auto_slot:
                continue
            else:
                pass

            if endpoint == "from":
                other_point = branch_graphic.pos2
            else:
                other_point = branch_graphic.pos1

            side_key, sort_value = self.infer_branch_slot_side_and_sort_value(other_point=other_point)

            grouped_entries[side_key].append((sort_value,
                                              str(id(branch_graphic.api_object)),
                                              branch_graphic,
                                              endpoint,
                                              attachment))

        side_key: str

        for side_key, entries in grouped_entries.items():
            entries.sort(key=lambda entry: (entry[0], entry[1]))

            for order_index, (_, _, branch_graphic, endpoint, attachment) in enumerate(entries, start=1):
                slot_key = build_explicit_slot_key(owner_kind="bus", side=side_key, order=order_index)
                attachment["side"] = side_key
                attachment["order"] = order_index
                attachment["slot"] = slot_key
                attachment["terminal_key"] = slot_key
                attachment["auto_slot"] = True
                self.editor.diagram.set_attachment(api_object=branch_graphic.api_object,
                                                   endpoint=endpoint,
                                                   attachment=attachment)

    def get_terminal_by_key(self, terminal_key: str = "default") -> BarTerminalItem:
        """
        Compatibility hook for future named attachment slots.
        """
        return self._terminal

    def add_object(self, api_obj: Union[None, INJECTION_DEVICE_TYPES] = None):
        """
        Add any recognized object
        :param api_obj: EditableDevice
        """

        if api_obj.device_type == DeviceType.GeneratorDevice:
            self.add_generator(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.LoadDevice:
            self.add_load(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.StaticGeneratorDevice:
            self.add_static_generator(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.ShuntDevice:
            self.add_shunt(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.BatteryDevice:
            self.add_battery(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.ExternalGridDevice:
            self.add_external_grid(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.CurrentInjectionDevice:
            self.add_current_injection(api_obj=api_obj)

        elif api_obj.device_type == DeviceType.ControllableShuntDevice:
            self.add_controllable_shunt(api_obj=api_obj)

        else:
            raise Exception("Cannot add device of type {}".format(api_obj.device_type.value))

    def add_child_graphic(self, elm: INJECTION_DEVICE_TYPES, graphic: INJECTION_GRAPHICS):
        """
        Add a api object and its graphic to this bus graphics domain
        :param elm:
        :param graphic:
        :return:
        """
        location = self.editor.diagram.query_point(elm)

        if location is None:
            pass
        else:
            graphic.setTransformOriginPoint(float(graphic.w) * 0.5, float(graphic.h) * 0.5)
            graphic.setRotation(float(location.r))
            graphic.update_nexus(graphic.scenePos())

        self._child_graphics.append(graphic)
        self.arrange_children()
        self.editor.graphics_manager.add_device(elm=elm, graphic=graphic)

    def add_load(self, api_obj: Union[Load, None] = None):
        """
        Add load object to bus
        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self._editor.circuit.add_load(bus=self._api_object)

        _grph = LoadGraphicItem(parent=self, api_obj=api_obj, editor=self._editor)
        self.add_child_graphic(elm=api_obj, graphic=_grph)
        return _grph

    def add_shunt(self, api_obj: Union[Shunt, None] = None):
        """
        Add shunt device
        :param api_obj: If None, a new shunt is created
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self._editor.circuit.add_shunt(bus=self._api_object)

        _grph = ShuntGraphicItem(parent=self, api_obj=api_obj, editor=self._editor)
        self.add_child_graphic(elm=api_obj, graphic=_grph)
        return _grph

    def add_generator(self, api_obj: Union[Generator, None] = None):
        """
        Add generator
        :param api_obj: if None, a new generator is created
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self._editor.circuit.add_generator(bus=self._api_object)

        _grph = GeneratorGraphicItem(parent=self, api_obj=api_obj, editor=self._editor)
        self.add_child_graphic(elm=api_obj, graphic=_grph)
        return _grph

    def add_static_generator(self, api_obj: Union[StaticGenerator, None] = None):
        """
        Add static generator
        :param api_obj: If none, a new static generator is created
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self._editor.circuit.add_static_generator(bus=self._api_object)

        _grph = StaticGeneratorGraphicItem(parent=self, api_obj=api_obj, editor=self._editor)
        self.add_child_graphic(elm=api_obj, graphic=_grph)

        return _grph

    def add_battery(self, api_obj: Union[Battery, None] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self._editor.circuit.add_battery(bus=self._api_object)

        _grph = BatteryGraphicItem(parent=self, api_obj=api_obj, editor=self._editor)
        self.add_child_graphic(elm=api_obj, graphic=_grph)

        return _grph

    def add_external_grid(self, api_obj: Union[ExternalGrid, None] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self._editor.circuit.add_external_grid(bus=self._api_object)

        _grph = ExternalGridGraphicItem(parent=self, api_obj=api_obj, editor=self._editor)
        self.add_child_graphic(elm=api_obj, graphic=_grph)
        return _grph

    def add_current_injection(self, api_obj: Union[CurrentInjection, None] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self._editor.circuit.add_current_injection(bus=self._api_object)

        _grph = CurrentInjectionGraphicItem(parent=self, api_obj=api_obj, editor=self._editor)
        self.add_child_graphic(elm=api_obj, graphic=_grph)
        return _grph

    def add_controllable_shunt(self, api_obj: Union[ControllableShunt, None] = None):
        """

        :param api_obj:
        :return:
        """
        if api_obj is None or type(api_obj) is bool:
            api_obj = self._editor.circuit.add_controllable_shunt(bus=self._api_object)

        _grph = ControllableShuntGraphicItem(parent=self, api_obj=api_obj, editor=self._editor)
        self.add_child_graphic(elm=api_obj, graphic=_grph)

        return _grph

    def set_values(self, i: int, Vm: float, Va: float, P: float | None, Q: float | None,
                   tpe: str, format_str="{:10.2f}"):
        """

        :param i:
        :param Vm:
        :param Va:
        :param P:
        :param Q:
        :param tpe:
        :param format_str:
        :return:
        """
        if self.draw_labels:

            msg = f"Bus {i}"
            if tpe is not None:
                msg += f" [{tpe}]"
            msg += "<br>"

            vm = format_str.format(Vm)
            vm_kv = format_str.format(Vm * self._api_object.Vnom)
            va = format_str.format(Va)
            msg += f"V={vm_kv} kV<br>  {vm}&lt;{va}º p.u.<br>"

            if P is not None:
                p = format_str.format(P)
                q = format_str.format(Q)
                msg += f"P={p} MW<br>Q={q} MVAr"

        else:
            msg = ""

        title = self._api_object.name if self._api_object is not None else ""
        self.label.setHtml(f'<html><head/><body><p><span style=" font-size:10pt;">{title}<br/></span>'
                           f'<span style=" font-size:6pt;">{msg}</span></p></body></html>')

        self.setToolTip(msg)

    def set_values_3ph(self, i: int,
                       VmA: float, VmB: float, VmC: float,
                       VaA: float, VaB: float, VaC: float,
                       tpe: str, format_str="{:10.2f}"):
        """
        Set three phase tags
        :param i: Bus index
        :param VmA:
        :param VmB:
        :param VmC:
        :param VaA:
        :param VaB:
        :param VaC:
        :param PA:
        :param PB:
        :param PC:
        :param QA:
        :param QB:
        :param QC:
        :param tpe: Bus type
        :param format_str: number formatting string
        """
        if self.draw_labels:

            msg = f"Bus {i}"
            if tpe is not None:
                msg += f" [{tpe}]"
            msg += "<br>"

            for Vm_i, Va_i, ph in zip([VmA, VmB, VmC], [VaA, VaB, VaC], ["a", "b", "c"]):
                if not (Vm_i == 0.0 and Va_i == 0.0):
                    vm = format_str.format(Vm_i)
                    vm_kv = format_str.format(Vm_i * self._api_object.Vnom)
                    va = format_str.format(Va_i)
                    msg += f"V{ph}={vm_kv} kV / {vm}&lt;{va}º p.u.<br>"

        else:
            msg = ""

        title = self._api_object.name if self._api_object is not None else ""
        self.label.setHtml(f'<html><head/><body><p><span style=" font-size:10pt;">{title}<br/></span>'
                           f'<span style=" font-size:6pt;">{msg}</span></p></body></html>')

        self.setToolTip(msg)

    def clear_label(self):
        msg = ""
        title = self._api_object.name if self._api_object is not None else ""
        self.label.setHtml(f'<html><head/><body><p><span style=" font-size:10pt;">{title}<br/></span>'
                           f'<span style=" font-size:6pt;">{msg}</span></p></body></html>')

        self.setToolTip(msg)

    def open_street_view(self):
        """
        Call open street maps
        :return:
        """
        # https://maps.google.com/?q=<lat>,<lng>
        if self._api_object is not None:
            url = f"https://www.google.com/maps/?q={self._api_object.latitude},{self._api_object.longitude}"
            webbrowser.open(url)
        else:
            warning_msg(f"No API object available :(")

    def __str__(self):

        if self._api_object is None:
            return f"Bus graphics {hex(id(self))}"
        else:
            return f"Graphics of {self._api_object.name} [{hex(id(self))}]"

    def __repr__(self):
        return str(self)
