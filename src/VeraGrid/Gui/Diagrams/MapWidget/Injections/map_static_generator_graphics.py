# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtGui import QPen, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QGraphicsTextItem
from VeraGridEngine.Devices.Injections.static_generator import StaticGenerator
from VeraGrid.Gui.Diagrams.generic_graphics import ACTIVE, DEACTIVATED, OTHER, Square, Condenser
from VeraGrid.Gui.Diagrams.MapWidget.Injections.map_injections_template_graphics import MapInjectionTemplateGraphicItem
from VeraGrid.Gui.messages import yes_no_question

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget


class MapStaticGeneratorGraphicItem(MapInjectionTemplateGraphicItem):

    def __init__(self, api_obj: StaticGenerator, editor: "SchematicWidget"):
        """

        :param api_obj:
        """
        MapInjectionTemplateGraphicItem.__init__(self,
                                                 api_obj=api_obj,
                                                 editor=editor,
                                                 device_type_name='static_generator',
                                                 w=40,
                                                 h=40)

    @property
    def api_object(self) -> StaticGenerator:
        return self._api_object
