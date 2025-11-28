# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING, List, Union
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QCursor
from PySide6.QtWidgets import (QGraphicsLineItem, QGraphicsItemGroup, QMenu,
                               QGraphicsSceneContextMenuEvent)
from VeraGrid.Gui.gui_functions import add_menu_entry
from VeraGrid.Gui.Diagrams.generic_graphics import (GenericDiagramWidget)

from VeraGridEngine.Devices.types import INJECTION_DEVICE_TYPES

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapInjectionTemplateGraphicItem(GenericDiagramWidget, QGraphicsItemGroup):
    """
    InjectionTemplateGraphicItem
    """

    def __init__(self,
                 api_obj: INJECTION_DEVICE_TYPES,
                 device_type_name: str,
                 w: int,
                 h: int,
                 editor: GridMapWidget):
        """

        :param api_obj:
        :param device_type_name:
        :param w:
        :param h:
        """
        GenericDiagramWidget.__init__(self, parent=None, api_object=api_obj, editor=editor, draw_labels=True)
        QGraphicsItemGroup.__init__(self, None)

        self.device_type_name = device_type_name

        # Properties of the container:
        self.setFlags(self.GraphicsItemFlag.ItemIsSelectable | self.GraphicsItemFlag.ItemIsMovable)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    @property
    def api_object(self) -> INJECTION_DEVICE_TYPES:
        """

        :return:
        """
        return self._api_object

    @property
    def editor(self) -> GridMapWidget:
        """

        :return:
        """
        return self._editor

    def get_associated_widgets(self) -> List[GenericDiagramWidget | QGraphicsLineItem]:
        """
        Get a list of all associated graphics
        :return:
        """
        return list()

    def get_extra_graphics(self):
        """
        Get a list of all QGraphicsItem that are not GenericDiagramWidget elements associated with this widget.
        :return:
        """
        return [self.nexus, self.glyph]

    def recolour_mode(self):
        """
        Change the colour according to the system theme
        """
        super().recolour_mode()

        pen = QPen(self.color, self.width, self.style)
        self.nexus.setPen(pen)
        self.glyph.setPen(pen)

        return pen

    def delete(self):
        """
        Remove this element
        @return:
        """

        deleted, delete_from_db_final = self.editor.delete_with_dialogue(selected=[self], delete_from_db=False)

    def plot(self):
        """
        Plot API objects profiles
        """
        # time series object from the last simulation
        ts = self.editor.circuit.time_profile

        # plot the profiles
        self.api_object.plot_profiles(time=ts)

    def mousePressEvent(self, QGraphicsSceneMouseEvent):
        """
        mouse press: display the editor
        :param QGraphicsSceneMouseEvent:
        :return:
        """
        self._editor.set_editor_model(api_object=self.api_object)

    def get_base_context_menu(self) -> QMenu:
        """
        Generate the base menu for injections
        :return:
        """
        menu = QMenu()

        add_menu_entry(menu=menu,
                       text="Plot profiles",
                       function_ptr=self.plot,
                       icon_path=":/Icons/icons/plot.png")

        menu.addSeparator()

        add_menu_entry(menu=menu,
                       text="Delete",
                       function_ptr=self.delete,
                       icon_path=":/Icons/icons/delete_schematic.png")

        return menu

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent):
        """
        Display context menu
        @param event:
        @return:
        """
        menu = self.get_base_context_menu()

        menu.exec(event.screenPos())
