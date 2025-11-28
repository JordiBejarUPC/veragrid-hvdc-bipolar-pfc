# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING

from VeraGridEngine.Devices.Injections.battery import Battery
from VeraGrid.Gui.Diagrams.MapWidget.Injections.map_injections_template_graphics import MapInjectionTemplateGraphicItem

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGrid.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


class MapBatteryGraphicItem(MapInjectionTemplateGraphicItem):

    def __init__(self, api_obj: Battery, editor: GridMapWidget):
        """

        :param api_obj:
        :param editor:
        """
        MapInjectionTemplateGraphicItem.__init__(self,
                                                 api_obj=api_obj,
                                                 editor=editor,
                                                 device_type_name='generator',
                                                 w=40,
                                                 h=40)

    @property
    def api_object(self) -> Battery:
        """

        :return:
        """
        return self._api_object
