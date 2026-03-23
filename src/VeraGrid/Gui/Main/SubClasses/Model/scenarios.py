# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGrid.Gui.Main.SubClasses.Model.time_events import TimeEventsMain
from VeraGrid.Gui.scenario_tree_model import ScenarioTreeModel


class ScenariosMain(TimeEventsMain):
    """
    Scenarios Main
    """

    def __init__(self, parent=None):
        """

        @param parent:
        """

        # create main window
        TimeEventsMain.__init__(self, parent)

        self.scenario_tree_model: ScenarioTreeModel = ScenarioTreeModel(multiverse=self.multiverse)

        self.ui.multiverseTreeView.setModel(self.scenario_tree_model)